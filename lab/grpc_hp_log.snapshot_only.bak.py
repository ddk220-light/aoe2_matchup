"""grpc_hp_log.py — LIVE per-side HP + unit-count timeline for the matchup video overlay
+ exact battle-end detection, via the CadeRemote gRPC API during a scenario Test.

SNAPSHOT-ONLY + CARRY-FORWARD (reliable on gameVersion 178524 despite the version-drifted
master-entity defs):
  * Reconnect ~every RESEED_S s; each new stream begins with a fresh full-state snapshot.
    seed_from_snapshot (with re-anchor recovery) decodes army HP; the per-frame DELTA path
    is NOT trusted (it desyncs).
  * A complex combat snapshot can still lose ~3/30 units to in-entity drift, and WHICH units
    differs per snapshot. So we CARRY FORWARD: a unit absent from one snapshot keeps its last
    HP (it reappears next snapshot); only after MAX_MISS consecutive absences is it dead.
  * Whole-snapshot failures (few entities decoded) are skipped, not applied.

Outputs: <out>.hp_log.jsonl (per game-second {game_s,wall_s,side1/side2:{count,hp}}),
<out>.END (winner) on battle-end, <out>.meta.json (wall0_epoch for VIDEO SYNC).

  python grpc_hp_log.py <out_prefix> [seconds]
"""
import json, os, struct, sys, time

D_DIR = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D_DIR)
import grpc
import cade_api_pb2 as pb
import cade_api_pb2_grpc as pbg
import decode_state_v2 as D

F_MASTER, F_OWNER, F_HP = 1, 2, 12
ARMY_MT = {9, 11, 12}
SCOUT = 448
SNAP_MIN = 5_000_000        # a full snapshot is ~9.7 MB
MIN_ENTITIES = 300          # a good snapshot decodes ~430 entities; skip if far fewer
MAX_MISS = 3                # absences before a unit is counted dead (~MAX_MISS*RESEED_S sec)
RESEED_S = 2.0
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D_DIR, "run")
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
def rd(n): return open(os.path.join(D_DIR, n), "rb").read()


def chan():
    creds = grpc.ssl_channel_credentials(rd("certificate-authority.pem"),
                                         rd("cade-client.key"), rd("cade-client.pem"))
    return grpc.secure_channel("ipv6:[::1]:4341", creds,
        options=[("grpc.ssl_target_name_override", "ca-game-api"),
                 ("grpc.max_receive_message_length", 512 * 1024 * 1024)])


def main():
    jf = open(OUT + ".hp_log.jsonl", "w")
    st = {"gv": None, "wall0": None, "end_game_s": None, "rows": 0, "seeded": False}
    army = {2: set(), 3: set()}
    seen = {}            # entity_key -> {"hp": float, "miss": int, "dead": bool}
    last_sec = -1; t0 = time.time()

    def write_meta():
        json.dump({"game_version": st["gv"], "wall0_epoch": st["wall0"],
                   "end_game_s": st["end_game_s"], "rows": st["rows"], "seed_ok": st["seeded"]},
                  open(OUT + ".meta.json", "w"), indent=2)

    def side(o):
        cnt = 0; hp = 0.0
        for k in army[o]:
            s = seen.get(k)
            if s and not s["dead"] and s["hp"] > 0:
                cnt += 1; hp += s["hp"]
        return [cnt, round(hp, 1)]

    def apply_snapshot(es):
        for o in (2, 3):
            for k in army[o]:
                e = es.get(k); v = e.get(F_HP) if e else None
                s = seen.setdefault(k, {"hp": 0.0, "miss": 0, "dead": False})
                if isinstance(v, (int, float)) and v > 0:
                    s["hp"] = v; s["miss"] = 0; s["dead"] = False
                else:
                    s["miss"] += 1
                    if s["miss"] >= MAX_MISS:
                        s["dead"] = True

    print(f"[hp_log] armed (DUR={DUR:.0f}s, snapshot-only +carry-forward) -> {OUT}.*  waiting ...", flush=True)
    while time.time() - t0 < DUR:
        try:
            ch = chan(); grpc.channel_ready_future(ch).result(timeout=5)
            stub = pbg.CadeRemoteStub(ch)
            st["gv"] = stub.Info(pb.InfoRequest(), timeout=5).gameVersion
            try: stub.SetFogOfWar(pb.SetFogOfWarRequest(fogOfWar=False), timeout=5)
            except Exception: pass
            got = False
            for sq in stub.Frames(pb.FramesRequest(disableParticles=True), timeout=20):
                for fr in sq.frame:
                    if fr.patch and len(fr.patch) >= SNAP_MIN:
                        open(OUT + ".snap.bin", "wb").write(fr.patch)
                        doc = D.Doc(); es = {}
                        D.seed_from_snapshot(OUT + ".snap.bin", doc, es)
                        if len(es) < MIN_ENTITIES:
                            got = True; break                 # bad/partial snapshot — skip
                        if not st["seeded"]:
                            for k, e in es.items():
                                if (e.get("__type__") in ARMY_MT and e.get(F_OWNER) in (2, 3)
                                        and e.get(F_MASTER) != SCOUT
                                        and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
                                    army[e.get(F_OWNER)].add(k)
                            st["seeded"] = True; st["wall0"] = time.time(); write_meta()
                        apply_snapshot(es)
                        sec = fr.time // 1000
                        if sec > last_sec:
                            last_sec = sec; s1, s2 = side(2), side(3)
                            row = {"game_s": sec, "wall_s": round(time.time() - st["wall0"], 2),
                                   "side1": {"count": s1[0], "hp": s1[1]},
                                   "side2": {"count": s2[0], "hp": s2[1]}}
                            jf.write(json.dumps(row) + "\n"); jf.flush(); st["rows"] += 1
                            z1, z2 = s1[0] == 0, s2[0] == 0
                            if st["end_game_s"] is None and sec >= 2 and (z1 != z2):
                                st["end_game_s"] = sec
                                winner = "side2" if z1 else "side1"
                                json.dump({"end_game_s": sec, "winner": winner, "wall_epoch": time.time(),
                                           "side1": row["side1"], "side2": row["side2"]},
                                          open(OUT + ".END", "w"))
                                write_meta()
                                print(f"[hp_log] BATTLE END game_s={sec} winner={winner}", flush=True)
                            print(f"  t={sec:3}s  S1 {s1[0]:2}u/{s1[1]:6.0f}hp   S2 {s2[0]:2}u/{s2[1]:6.0f}hp", flush=True)
                        got = True; break
                if got:
                    break
            time.sleep(RESEED_S)
        except grpc.FutureTimeoutError:
            time.sleep(1.0)
        except grpc.RpcError:
            time.sleep(0.5)
        except Exception as e:
            print("  err:", type(e).__name__, str(e)[:90], flush=True); time.sleep(0.8)
    jf.close(); write_meta()
    print(f"\n[hp_log] DONE rows={st['rows']} end_game_s={st['end_game_s']}  -> {OUT}.hp_log.jsonl", flush=True)


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    main()
