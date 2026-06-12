"""_validate_capture.py — GO/NO-GO: does the CadeRemote gRPC stream carry live entity
state during an AoE2 editor scenario Test? Connects to :4341, SetFogOfWar(false), streams
Frames, and reports frames / creates / EntityKilled deaths / production / snapshots.

Periodically reconnects (every ~22s of streaming) so each new stream begins with a fresh
full-state snapshot -> the LAST one saved (val_latest_snap.bin) is the most recent state
(after the battle, if it's still on screen). All paths absolute (cwd-independent).

  python _validate_capture.py [seconds]
"""
import json, os, struct, sys, time

D = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D)
import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg
import decode_state_v2 as DS

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 240.0
ENT = {9, 11, 12, 14}
SCH = DS.SCHEMA
def rd(n): return open(os.path.join(D, n), "rb").read()


def chan():
    creds = grpc.ssl_channel_credentials(rd("certificate-authority.pem"),
                                         rd("cade-client.key"), rd("cade-client.pem"))
    return grpc.secure_channel("ipv6:[::1]:4341", creds,
        options=[("grpc.ssl_target_name_override", "ca-game-api"),
                 ("grpc.max_receive_message_length", 512 * 1024 * 1024)])


def decode_create(p, j, L):
    mt = p[j + 2]; key = struct.unpack_from("<i", p, j + 3)[0]
    if not (0 < key < 1_000_000): return None
    if j + 7 >= L or p[j + 7] != 2: return None
    r = DS.Reader(p); r.p = j + 7; master = owner = None
    for _ in range(8):
        if r.p >= L or p[r.p] != 2: break
        r.p += 1; f = r.u8(); fi = SCH.get(mt, {}).get(f, ("value", False, None))
        try: v = DS.read_value(r, *fi)
        except Exception: break
        if f == 1: master = v
        elif f == 2: owner = v
        if master is not None and owner is not None: break
    if master is None or master < 0: return None
    return mt, key, master, owner


def scan(p, units, t):
    L = len(p); j = 0
    while j < L - 8:
        if p[j] == 8 and p[j + 1] == 1 and p[j + 2] in ENT:
            res = decode_create(p, j, L)
            if res:
                mt, key, master, owner = res
                if key not in units: units[key] = [master, owner, mt, t]
                j += 7; continue
        j += 1


def main():
    units = {}; deaths = {}; prod = []
    t0 = time.time(); frames = 0; last_ms = 0; n_kill = 0; n_snap = 0
    latest_snap_ms = -1; first_seen = None
    print(f"[validate] armed (DUR={DUR:.0f}s), waiting for the Test on :4341 ...", flush=True)
    while time.time() - t0 < DUR:
        try:
            ch = chan(); grpc.channel_ready_future(ch).result(timeout=5)
            stub = pbg.CadeRemoteStub(ch)
            info = stub.Info(pb.InfoRequest(), timeout=5)
            try: stub.SetFogOfWar(pb.SetFogOfWarRequest(fogOfWar=False), timeout=5); fog = "OFF"
            except Exception as e: fog = f"fail({type(e).__name__})"
            seg_t0 = time.time(); seg_frames = 0
            for sq in stub.Frames(pb.FramesRequest(disableParticles=True), timeout=DUR + 10):
                for fr in sq.frame:
                    frames += 1; seg_frames += 1; last_ms = fr.time
                    if first_seen is None:
                        first_seen = time.time() - t0
                        print(f"[validate] FIRST FRAMES at +{first_seen:.0f}s  gv={info.gameVersion} fog={fog}", flush=True)
                    for ev in fr.event:
                        if ev.WhichOneof("event") == "entityKilled":
                            n_kill += 1; k = ev.entityKilled.id
                            if k not in deaths: deaths[k] = fr.time
                    for c in fr.command:
                        if c.WhichOneof("command") == "multiQueue":
                            m = c.multiQueue
                            prod.append([fr.time, m.playerId, m.trainId, m.trainCount or 1])
                    p = fr.patch
                    if p and len(p) > 400_000:
                        n_snap += 1; latest_snap_ms = fr.time
                        open(os.path.join(D, "val_latest_snap.bin"), "wb").write(p)
                        if n_snap == 1:
                            open(os.path.join(D, "val_first_snap.bin"), "wb").write(p)
                    elif p:
                        try: scan(p, units, fr.time)
                        except Exception: pass
                if frames % 400 == 0 and frames:
                    print(f"  frames={frames} gt={last_ms/1000:.1f}s creates={len(units)} "
                          f"kills={n_kill} prod={len(prod)} snaps={n_snap}", flush=True)
                if time.time() - seg_t0 > 22 and seg_frames > 0:
                    break        # reconnect -> fresh full snapshot of the CURRENT state
                if time.time() - t0 > DUR:
                    break
        except grpc.FutureTimeoutError:
            time.sleep(1.5)
        except grpc.RpcError:
            time.sleep(1.5)
        except Exception as e:
            print("  err:", type(e).__name__, str(e)[:90], flush=True); time.sleep(1.5)

    summary = {"streamed_during_test": frames > 0, "first_frame_at_s": first_seen,
               "frames": frames, "game_seconds": round(last_ms / 1000, 1),
               "creates": len(units), "kill_events": n_kill, "deaths": len(deaths),
               "production_cmds": len(prod), "snapshots": n_snap,
               "latest_snap_game_s": round(latest_snap_ms / 1000, 1) if latest_snap_ms >= 0 else None}
    json.dump({"summary": summary, "units": {str(k): v for k, v in units.items()},
               "deaths": {str(k): v for k, v in deaths.items()}, "production": prod},
              open(os.path.join(D, "val_capture.json"), "w"), indent=2)
    print("\n[validate] SUMMARY: " + json.dumps(summary), flush=True)


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    main()
