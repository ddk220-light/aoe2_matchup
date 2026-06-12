"""_wf_probe_scale.py — decoder-INDEPENDENT test of the stream-clock vs footage-clock
scale, using raw-scanned op9 (ResetKey on World.entities, corpse removal) byte patterns
for the 54 seeded army keys. No apply_patch involved: just byte scan + frame times.

Model: death_time_stream = op9_time - decay_gap;  death_time_video = death_time_stream/scale.
Fit pred(v) = 24 - #side1 deaths <= v against OCR_S1 for scale in {1.0, 1.5, 1.7, 2.0}
with rigid offset in [-2, +2] (0.01 grid).
"""
import struct
import sys
import math

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D          # noqa: E402
import cade_api_pb2 as pb            # noqa: E402

PFX = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
       r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs)")
F_MASTER, F_OWNER, F_HP = 1, 2, 12
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_reseed.bin"
OCR_S1 = [(0.5, 24), (6.5, 21), (7.5, 18), (8.5, 17), (9.5, 14), (10.5, 11),
          (11.5, 10), (12.5, 8), (13.5, 5), (15.5, 2), (16.5, 0)]


def derive_army(es):
    a = {2: set(), 3: set()}
    for k, e in es.items():
        if (e.get("__type__") in (9, 11, 12) and e.get(F_OWNER) in (2, 3)
                and e.get(F_MASTER) != 448
                and isinstance(e.get(F_HP), (int, float)) and e.get(F_HP) > 30):
            a[e.get(F_OWNER)].add(k)
    return a


def main():
    fight = False
    army = None
    seeded = set()
    op9_times = {}    # key -> first op9 time (stream s)
    last_t = 0.0

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
                t = fr.time / 1000.0
                last_t = max(last_t, t)
                if p and len(p) > 400_000:
                    with open(TMP, "wb") as sf:
                        sf.write(p)
                    doc = D.Doc()
                    es2 = {}
                    D.seed_from_snapshot(TMP, doc, es2)
                    a = derive_army(es2)
                    if len(a[2]) == 24 and len(a[3]) == 30:
                        fight = True
                        army = a
                        seeded = set(es2.keys())
                    continue
                if not fight or not p:
                    continue
                i, n = 0, len(p)
                while i < n - 6:
                    if p[i] in (9, 12) and p[i + 1] == 1:
                        k = struct.unpack_from("<i", p, i + 2)[0]
                        if k in seeded and k not in op9_times:
                            op9_times[k] = t
                    i += 1

    s1 = sorted(op9_times[k] for k in op9_times if k in army[2])
    s2 = sorted(op9_times[k] for k in op9_times if k in army[3])
    print(f"stream end t={last_t:.2f}")
    print(f"side1 op9 removals: {len(s1)}/24: {[round(x,2) for x in s1]}")
    print(f"side2 op9 removals: {len(s2)}/30: {[round(x,2) for x in s2]}")

    decay = 1.06   # measured median gap HP<=0 -> op9 from probe 2
    deaths = [x - decay for x in s1]

    def rmse_for(scale):
        best = (None, 1e9)
        off = -2.0
        while off <= 2.0001:
            sse = 0.0
            for v, cnt in OCR_S1:
                pred = 24 - sum(1 for d in deaths if d / scale + off <= v)
                sse += (pred - cnt) ** 2
            r = math.sqrt(sse / len(OCR_S1))
            if r < best[1]:
                best = (off, r)
            off += 0.01
        return best

    for scale in (1.0, 1.5, 1.7, 2.0):
        off, r = rmse_for(scale)
        print(f"scale={scale:4.2f}  best_off={off:+.2f}  rmse={r:.3f}  "
              f"(n_deaths={len(deaths)})")
    # continuous scale sweep
    best = (None, None, 1e9)
    sc = 1.40
    while sc <= 2.2001:
        off, r = rmse_for(sc)
        if r < best[2]:
            best = (sc, off, r)
        sc += 0.01
    print(f"best continuous: scale={best[0]:.2f} off={best[1]:+.2f} rmse={best[2]:.3f}")


if __name__ == "__main__":
    main()
