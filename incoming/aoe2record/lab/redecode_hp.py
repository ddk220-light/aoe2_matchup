"""redecode_hp.py — OFFLINE decode of a recorded Frames() stream (<pfx>.frames.bin)
into the exact per-second per-side HP+count timeline the overlay needs.

Uses the REAL apply_patch decoder + entity_store (alive = present with hp>0), with
full hindsight: deaths land on the game-second the unit actually left the world —
no carry-forward, no lag. Run with the SYSTEM python (grpcio/protobuf installed).

Robustness (lessons from real captures):
  * The recorder may start in the EDITOR; clicking Test switches game instance, the
    stream reconnects, and the game clock RESTARTS. The dump is therefore split into
    SEGMENTS on clock resets / mid-stream full snapshots, each segment re-seeded and
    its army membership re-derived from its own snapshot.
  * The FIGHT segment is chosen by evidence: both sides must field a plausible army
    and the segment must contain deaths; ties go to the LATEST such segment. A stale
    seed_snap.bin can therefore never poison the result (the old failure mode).

Writes <pfx>.hp_log.jsonl (one row per game-second) — the same shape the pipeline's
grpc_capture.read_rows expects.

  python redecode_hp.py <out_prefix>
"""
import json
import struct
import sys

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402

PFX = sys.argv[1] if len(sys.argv) > 1 else r"C:\dev\aoe2\aoe2record\lab\run1"
F_MASTER, F_OWNER, F_HP = 1, 2, 12
ARMY_MT = {9, 11, 12}
SCOUT = 448
SNAP_RESEED = 400_000                # mid-stream patches above this are full snapshots
MIN_ARMY, MAX_ARMY = 3, 80           # plausible per-side army size


def derive_army(es):
    army = {2: set(), 3: set()}
    for k, e in es.items():
        if (e.get("__type__") in ARMY_MT and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != SCOUT
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            army[e.get(F_OWNER)].add(k)
    return army


def totals(es, army):
    out = {}
    for o in (2, 3):
        cnt, hp = 0, 0.0
        for k in army[o]:
            e = es.get(k)
            v = e.get(F_HP) if e else None
            if isinstance(v, (int, float)) and v > 0:
                cnt += 1
                hp += v
    # noqa: E501 — count/hp per side
        out[o] = (cnt, round(hp, 1))
    return out


class Segment:
    def __init__(self):
        self.rows = []
        self.start_counts = None

    def add(self, sec, t):
        if self.start_counts is None:
            self.start_counts = (t[2][0], t[3][0])
        self.rows.append({"game_s": sec,
                          "side1": {"count": t[2][0], "hp": t[2][1]},
                          "side2": {"count": t[3][0], "hp": t[3][1]}})

    def deaths(self):
        if not self.rows:
            return 0
        f, l = self.rows[0], self.rows[-1]
        return ((f["side1"]["count"] - l["side1"]["count"])
                + (f["side2"]["count"] - l["side2"]["count"]))

    def plausible(self):
        return (self.start_counts is not None
                and all(MIN_ARMY <= c <= MAX_ARMY for c in self.start_counts))


def main():
    doc, es, army, world_id = None, None, None, None
    seg, segments = Segment(), []
    last_sec = None

    def reseed(patch_bytes):
        nonlocal doc, es, army, world_id, seg, last_sec
        with open(PFX + ".reseed.bin", "wb") as f:
            f.write(patch_bytes)
        doc = D.Doc()
        es2 = {}
        _, world_id = D.seed_from_snapshot(PFX + ".reseed.bin", doc, es2)
        es = es2
        army = derive_army(es)
        if seg.rows:
            segments.append(seg)
        seg = Segment()
        last_sec = None

    with open(PFX + ".frames.bin", "rb") as f:
        while True:
            hdr = f.read(4)
            if len(hdr) < 4:
                break
            ln = struct.unpack("<I", hdr)[0]
            buf = f.read(ln)
            if len(buf) < ln:
                break
            sq = pb.FrameSequence()
            sq.ParseFromString(buf)
            for fr in sq.frame:
                p = fr.patch
                if p and len(p) > SNAP_RESEED:
                    reseed(p)            # full snapshot: fresh doc + army membership
                    continue
                if es is None:
                    continue             # nothing decodable until the first snapshot
                if p:
                    D.apply_patch(doc, p, es, world_id)
                sec = fr.time // 1000
                if last_sec is not None and sec < last_sec - 2:
                    # clock went backwards: new game instance without a snapshot yet —
                    # close the segment; rows resume after the next snapshot reseed
                    if seg.rows:
                        segments.append(seg)
                    seg = Segment()
                    last_sec = None
                    es = None
                    continue
                if last_sec is None or sec > last_sec:
                    last_sec = sec
                    seg.add(sec, totals(es, army))
    if seg.rows:
        segments.append(seg)

    # the FIGHT = a plausible two-army segment containing deaths; latest such wins
    fights = [s for s in segments if s.plausible() and s.deaths() >= 2]
    if not fights:
        fights = [s for s in segments if s.plausible()]
    if not fights:
        print(f"rows=0  (no plausible fight segment among {len(segments)} segments)")
        return
    best = fights[-1]
    rows = best.rows
    with open(PFX + ".hp_log.jsonl", "w") as o:
        for r in rows:
            o.write(json.dumps(r) + "\n")
    end_s = next((r["game_s"] for r in rows
                  if min(r["side1"]["count"], r["side2"]["count"]) == 0), None)
    print(f"segments={len(segments)}  picked start={best.start_counts} "
          f"rows={len(rows)}  battle_end_game_s={end_s}")
    for r in rows:
        if r["game_s"] % 2 == 0 or r["game_s"] == end_s:
            m = "  <-- END" if r["game_s"] == end_s else ""
            print(f"  t={r['game_s']:3}s   S1 {r['side1']['count']:2}u /"
                  f"{r['side1']['hp']:6.0f}hp    S2 {r['side2']['count']:2}u /"
                  f"{r['side2']['hp']:6.0f}hp{m}")
        if end_s is not None and r["game_s"] > end_s + 2:
            break


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
