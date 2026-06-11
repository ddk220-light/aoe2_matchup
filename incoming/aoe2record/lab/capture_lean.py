"""capture_lean.py — LIVE, lean capture of exactly the ground-truth we need.

Connects to CadeRemote, DISABLES FOG OF WAR (full vision -> both players' units),
then streams frames and extracts on the fly (no 993 MB raw dump):

  * CREATES  -> {entity_id (= .aoe2record instance_id): master_id, owner, model_type, created_ms}
                via the desync-immune byte-anchored decode (08 01 <mt> <key> ...).
  * DEATHS   -> entity_id -> died_ms (EntityKilled events + op9/op12 World.entities).
  * PRODUCTION -> MultiQueue/Make/Build commands (type/player/time) for cross-check.
  * SNAPSHOTS -> first + latest full-state patch saved to disk (initial/survivor sets).

Writes incrementally to capture_lean.json (+ flushes), so an interrupt is safe.
Auto-reconnects so you can replay from the start at fast speed.

Run:  python capture_lean.py [wall_seconds]
"""
import json
import os
import struct
import sys
import time

import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg
import decode_state_v2 as D

DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 1800.0
SCH = D.SCHEMA
ENT = {9, 11, 12, 14}          # real units (Entity/Action/Combat/Building)
OUT = "capture_lean.json"


def chan():
    ca = open("certificate-authority.pem", "rb").read()
    cert = open("cade-client.pem", "rb").read()
    key = open("cade-client.key", "rb").read()
    creds = grpc.ssl_channel_credentials(ca, key, cert)
    return grpc.secure_channel("ipv6:[::1]:4341", creds,
                               options=[("grpc.ssl_target_name_override", "ca-game-api"),
                                        ("grpc.max_receive_message_length", 512 * 1024 * 1024)])


def decode_create(p, j, L):
    """At candidate `08 01 mt key`, read the entity's leading op2 assigns -> (mt,key,master,owner)."""
    mt = p[j + 2]
    key = struct.unpack_from("<i", p, j + 3)[0]
    if not (0 < key < 1_000_000):
        return None
    if j + 7 >= L or p[j + 7] != 2:
        return None
    r = D.Reader(p); r.p = j + 7
    master = owner = None
    for _ in range(8):
        if r.p >= L or p[r.p] != 2:
            break
        r.p += 1
        f = r.u8()
        fi = SCH.get(mt, {}).get(f, ("value", False, None))
        try:
            v = D.read_value(r, *fi)
        except Exception:
            break
        if f == 1:
            master = v
        elif f == 2:
            owner = v
        if master is not None and owner is not None:
            break
    if master is None or master < 0:
        return None
    return mt, key, master, owner


def scan_patch(p, units, deaths, t):
    """Record new creates and op9/op12 World.entities deaths from one patch."""
    L = len(p); j = 0
    while j < L - 8:
        b = p[j]
        if b == 8 and p[j + 1] == 1 and p[j + 2] in ENT:
            res = decode_create(p, j, L)
            if res:
                mt, key, master, owner = res
                if key not in units:
                    units[key] = [master, owner, mt, t]   # compact
                j += 7
                continue
        j += 1


def flush(units, deaths, prod, meta):
    json.dump({"meta": meta, "units": {str(k): v for k, v in units.items()},
               "deaths": {str(k): v for k, v in deaths.items()}, "production": prod},
              open(OUT, "w"))


def main():
    units = {}      # entity_id -> [master, owner, model_type, created_ms]
    deaths = {}     # entity_id -> died_ms
    prod = []       # [ms, player, type_master_id, count, kind]
    t0 = time.time()
    seg = 0
    total_frames = 0; last_t = 0; n_kill_ev = 0
    last_wait_msg = 0.0
    print(f"LEAN capture armed (fog OFF), up to {DUR:.0f}s. Start the replay now...", flush=True)

    while time.time() - t0 < DUR:
        try:
            ch = chan()
            grpc.channel_ready_future(ch).result(timeout=5)
            stub = pbg.CadeRemoteStub(ch)
            info = stub.Info(pb.InfoRequest(), timeout=5)
            seg += 1
            try:
                stub.SetFogOfWar(pb.SetFogOfWarRequest(fogOfWar=False), timeout=5)
                fog = "fog OFF"
            except Exception as e:  # noqa
                fog = f"fog FAILED({e})"
            print(f"[seg {seg}] connected gv={info.gameVersion} {fog}", flush=True)
            saved_first = False
            for sq in stub.Frames(pb.FramesRequest(disableParticles=True,
                                                   disableParticleCulling=True),
                                  timeout=DUR + 10):
                for fr in sq.frame:
                    total_frames += 1
                    last_t = fr.time
                    for ev in fr.event:
                        if ev.WhichOneof("event") == "entityKilled":
                            k = ev.entityKilled.id
                            n_kill_ev += 1
                            if k not in deaths:
                                deaths[k] = fr.time
                    for c in fr.command:
                        w = c.WhichOneof("command")
                        if w == "multiQueue":
                            m = c.multiQueue
                            prod.append([fr.time, m.playerId, m.trainId, m.trainCount or 1, "mq"])
                        elif w == "make":
                            m = c.make
                            prod.append([fr.time, m.unitPlayerId, m.unitId, 1, "make"])
                        elif w == "build":
                            b = c.build
                            prod.append([fr.time, b.unitPlayerId, b.objId, 1, "build"])
                    p = fr.patch
                    if not p:
                        continue
                    if len(p) > 500_000:
                        fnp = f"snap_seg{seg}.bin"
                        open(fnp, "wb").write(p)        # latest full snapshot (overwritten per seg)
                        if not saved_first:
                            open(f"first_snap_seg{seg}.bin", "wb").write(p)
                            saved_first = True
                        continue
                    scan_patch(p, units, deaths, fr.time)
                if total_frames % 2000 == 0:
                    flush(units, deaths, prod, {"frames": total_frames, "last_ms": last_t,
                                                "kill_events": n_kill_ev, "seg": seg})
                    print(f"  {total_frames} frames / {last_t/60000:.1f}min / "
                          f"units={len(units)} deaths={len(deaths)} prod={len(prod)}", flush=True)
                if time.time() - t0 > DUR:
                    break
        except grpc.FutureTimeoutError:
            now = time.time()
            if now - last_wait_msg > 15:
                print(f"  ...waiting for the game/replay on :4341 "
                      f"({now-t0:.0f}s elapsed)", flush=True)
                last_wait_msg = now
            time.sleep(2.0)
        except grpc.RpcError as e:
            now = time.time()
            if now - last_wait_msg > 15:
                print(f"  ...stream not active ({e.code() if hasattr(e,'code') else e}); "
                      f"reconnecting", flush=True)
                last_wait_msg = now
            time.sleep(2.0)
        except Exception as e:  # noqa
            print("err:", type(e).__name__, repr(e)[:160], flush=True)
            time.sleep(2.0)

    flush(units, deaths, prod, {"frames": total_frames, "last_ms": last_t,
                                "kill_events": n_kill_ev, "seg": seg, "done": True})
    print(f"\nDONE. frames={total_frames} gametime={last_t/60000:.1f}min  "
          f"units(created)={len(units)}  deaths={len(deaths)}  kill_events={n_kill_ev}  "
          f"production_cmds={len(prod)}", flush=True)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
