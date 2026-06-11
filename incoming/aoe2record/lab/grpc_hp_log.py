"""grpc_hp_log.py — STREAM RECORDER for the matchup-video overlay: dump the CadeRemote
Frames() stream to <out>.frames.bin during a scenario Test. The EXACT per-second
HP/count timeline is decoded OFFLINE afterwards by redecode_hp.py (full hindsight:
frame-accurate deaths from the delta stream, no carry-forward lag).

This REPLACES the old live snapshot-only decoder (kept as grpc_hp_log.snapshot_only
.bak.py): that design reconnected every 2s for fresh snapshots and carried units
forward across decode dropouts, which confirmed deaths ~6-10s late and desynced the
timeline vs the footage. Recording the raw stream and decoding offline is both
simpler (the live process has almost no failure modes) and exact.

A LIVE TAILER decodes the same frames incrementally AS they are dumped (same fixed
apply_patch the offline redecode uses) purely to detect the moment the fight
resolves: when one army's alive count hits 0 it writes <out>.END so the orchestrator
can stop the recording at the exact battle end instead of OCR-watching the WINS
banner. The tailer is failure-proof by construction — any decode exception disables
it for the run and the dump (+ offline redecode) is unaffected.

Outputs:
  <out>.frames.bin     length-prefixed FrameSequence dump (what redecode_hp.py reads)
  <out>.seed_snap.bin  the first full snapshot seen (fallback army seed)
  <out>.meta.json      game_version, wall0_epoch (wall time of first frame), counters
  <out>.END            written the moment one army is wiped (fight-end signal)

  python grpc_hp_log.py <out_prefix> [seconds]
"""
import json
import os
import struct
import sys
import time

D_DIR = r"C:\dev\aoe2\aoe2record\lab"
sys.path.insert(0, D_DIR)
import grpc                          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402
import cade_api_pb2_grpc as pbg      # noqa: E402
import decode_state_v2 as D          # noqa: E402

SNAP_MIN = 5_000_000                 # a full snapshot patch is ~9.7 MB
SNAP_RESEED = 400_000                # any patch this big is a fresh snapshot (reseed)
F_MASTER, F_OWNER, F_HP = 1, 2, 12
ARMY_MT = (9, 11, 12)                # combat-entity model types
SCOUT = 448                          # never counted (the AI's explorer)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D_DIR, "run")
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0


class LiveEnd:
    """Incremental decode of the stream for ONE purpose: write <out>.END the moment
    exactly one army reaches 0 alive. Mirrors redecode_hp's army rules (owner 2/3,
    model type 9/11/12, master != scout, seed HP > 30; clock reset = new instance).
    Requires 3 consecutive zero reads so a single corrupt frame can't end a run."""

    def __init__(self, out):
        self.out = out
        self.ok = True
        self.doc = self.es = self.world_id = None
        self.army = None
        self.last_sec = None
        self.zero_streak = 0
        self.done = False

    def _derive_army(self):
        a = {2: set(), 3: set()}
        for k, e in self.es.items():
            if (e.get("__type__") in ARMY_MT and e.get(F_OWNER) in (2, 3)
                    and e.get(F_MASTER) != SCOUT
                    and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
                a[e.get(F_OWNER)].add(k)
        return a

    def _alive(self, owner):
        n = 0
        for k in self.army[owner]:
            e = self.es.get(k)
            v = e.get(F_HP) if e else None
            if isinstance(v, (int, float)) and v > 0:
                n += 1
        return n

    def feed(self, fr):
        if not self.ok or self.done or not fr.patch:
            return
        try:
            t, p = fr.time / 1000.0, fr.patch
            if self.last_sec is not None and t < self.last_sec - 2:
                self.doc = self.es = self.army = None     # new game instance
            self.last_sec = t
            if len(p) > SNAP_RESEED:
                tmp = self.out + ".live_seed.bin"
                with open(tmp, "wb") as f:
                    f.write(p)
                self.doc, es = D.Doc(), {}
                _, self.world_id = D.seed_from_snapshot(tmp, self.doc, es)
                self.es = es
                a = self._derive_army()
                self.army = a if min(len(a[2]), len(a[3])) >= 2 else None
                self.zero_streak = 0
                if self.army:
                    print(f"[live] armies seeded {len(a[2])} vs {len(a[3])} "
                          f"at stream t={t:.1f}s", flush=True)
                return
            if self.es is None:
                return
            D.apply_patch(self.doc, p, self.es, self.world_id)
            if not self.army:
                return
            a1, a2 = self._alive(2), self._alive(3)
            if (a1 == 0) != (a2 == 0):
                self.zero_streak += 1
                if self.zero_streak >= 3:
                    self.done = True
                    with open(self.out + ".END", "w") as f:
                        json.dump({"end_stream_s": round(t, 2), "side1": a1,
                                   "side2": a2, "winner": 1 if a2 == 0 else 2,
                                   "wall_epoch": time.time()}, f)
                    print(f"[live] FIGHT END at stream {t:.1f}s  "
                          f"s1={a1} s2={a2} -> {self.out}.END", flush=True)
            else:
                self.zero_streak = 0
        except Exception as e:
            self.ok = False
            print(f"[live] live decode disabled ({type(e).__name__}: {str(e)[:80]}) "
                  f"— dump unaffected", flush=True)


def rd(n):
    return open(os.path.join(D_DIR, n), "rb").read()


def chan():
    creds = grpc.ssl_channel_credentials(rd("certificate-authority.pem"),
                                         rd("cade-client.key"), rd("cade-client.pem"))
    return grpc.secure_channel("ipv6:[::1]:4341", creds,
        options=[("grpc.ssl_target_name_override", "ca-game-api"),
                 ("grpc.max_receive_message_length", 512 * 1024 * 1024)])


def main():
    t0 = time.time()
    meta = {"game_version": None, "wall0_epoch": None, "frames": 0, "bytes": 0,
            "recorder": "stream_dump_v3_live_end"}

    def write_meta():
        with open(OUT + ".meta.json", "w") as f:
            json.dump(meta, f, indent=2)

    fb = open(OUT + ".frames.bin", "wb")
    live = LiveEnd(OUT)
    seed_saved = False
    print(f"[hp_log] stream-recorder armed (DUR={DUR:.0f}s) -> {OUT}.frames.bin", flush=True)
    while time.time() - t0 < DUR:
        try:
            ch = chan()
            grpc.channel_ready_future(ch).result(timeout=5)
            stub = pbg.CadeRemoteStub(ch)
            meta["game_version"] = stub.Info(pb.InfoRequest(), timeout=5).gameVersion
            try:
                stub.SetFogOfWar(pb.SetFogOfWarRequest(fogOfWar=False), timeout=5)
            except Exception:
                pass
            # one long-lived stream; if the game switches instance (clicking Test) the
            # stream ends with an RpcError and we reconnect — the new stream re-opens
            # with a fresh full snapshot, which redecode_hp treats as a reseed point.
            for sq in stub.Frames(pb.FramesRequest(disableParticles=True),
                                  timeout=DUR + 30):
                buf = sq.SerializeToString()
                fb.write(struct.pack("<I", len(buf)))
                fb.write(buf)
                meta["frames"] += len(sq.frame)
                meta["bytes"] += 4 + len(buf)
                if meta["wall0_epoch"] is None:
                    meta["wall0_epoch"] = time.time()
                    write_meta()
                if not seed_saved:
                    for fr in sq.frame:
                        if fr.patch and len(fr.patch) >= SNAP_MIN:
                            with open(OUT + ".seed_snap.bin", "wb") as sf:
                                sf.write(fr.patch)
                            seed_saved = True
                            print(f"[hp_log] seed snapshot saved ({len(fr.patch):,} bytes)",
                                  flush=True)
                            break
                for fr in sq.frame:           # live fight-end tailer (failure-proof)
                    live.feed(fr)
                if time.time() - t0 >= DUR:
                    break
        except grpc.FutureTimeoutError:
            time.sleep(1.0)
        except grpc.RpcError:
            time.sleep(0.5)
        except Exception as e:
            print("  err:", type(e).__name__, str(e)[:90], flush=True)
            time.sleep(0.8)
    fb.flush()
    fb.close()
    write_meta()
    print(f"[hp_log] DONE frames={meta['frames']} bytes={meta['bytes']:,} -> "
          f"{OUT}.frames.bin", flush=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
