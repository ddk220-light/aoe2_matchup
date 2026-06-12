"""_wf_desync_probe3.py — time-base + death-channel measurements.

Questions answered (Guecha-vs-Jaguar ground truth):
  1. Is the 'stretched ~1.9x' curve a TIME-BASE effect (fr.time = in-game clock at a
     game-speed multiple of footage seconds)?  Fit scale s + offset b minimizing rmse
     of pred(v) = 24 - #(raw_death/s <= v + b) over the 11 OCR samples.
  2. With the scale fixed at the AoE2:DE 'Fast' speed 1.7, does a rigid offset in
     [-2,+2]s reach rmse <= 1.0 for (a) the RAW marker-walker death curve (perfect
     decode upper bound) and (b) the CURRENT broken-decoder death curve?
  3. Per side1 unit: raw death time (op9 marker / HP<=0) vs broken-decoder death time
     (entity removed or HP<=0 in entity_store), and whether the op9 marker sat in the
     post-desync (lost) region of its patch.

ASCII-only output. Run with cwd C:\\dev\\aoe2grpc.
"""
import bisect
import math
import struct
import sys
from collections import Counter

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D                              # noqa: E402
import cade_api_pb2 as pb                                # noqa: E402
from _wf_desync_probe import (apply_patch_probe, scan_07, derive_army)  # noqa: E402
from _wf_desync_probe2 import extract_record, scan_deaths               # noqa: E402

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs).frames.bin")
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_seed_tmp3.bin"
F_HP = 12

OCR_S1 = [(0.5, 24), (6.5, 21), (7.5, 18), (8.5, 17), (9.5, 14), (10.5, 11),
          (11.5, 10), (12.5, 8), (13.5, 5), (15.5, 2), (16.5, 0)]


def fit_curve(death_times, scales, offs):
    """rmse of pred(v)=24-#(d/s <= v+b) over OCR_S1; returns (rmse, s, b) minimum."""
    ds = sorted(death_times)
    best = (1e9, None, None)
    for s in scales:
        dv = [d / s for d in ds]
        for b in offs:
            tot = 0.0
            for (v, c) in OCR_S1:
                pred = 24 - bisect.bisect_right(dv, v + b)
                tot += (pred - c) ** 2
            r = math.sqrt(tot / len(OCR_S1))
            if r < best[0]:
                best = (r, s, b)
    return best


def curve_table(death_times, s, b):
    ds = sorted(d / s for d in death_times)
    rows = []
    for (v, c) in OCR_S1:
        pred = 24 - bisect.bisect_right(ds, v + b)
        rows.append((v, c, pred))
    return rows


def main():
    print("=" * 78)
    print("_wf_desync_probe3.py -- time-base + death-channel measurements")
    print("=" * 78)

    doc = es = army = None
    world_id = None
    fight = False
    last_sec = None
    army_keys = set()
    known_keys = set()
    key_type = {}

    raw_death = {}            # key -> (t, op, marker_pos, first_exc_pos_or_None, size)
    raw_hp0 = {}              # key -> t of first raw HP<=0 sample
    dec_removed = {}          # key -> t entity disappeared from store (broken decoder)
    dec_hp0 = {}              # key -> t hp in store first <= 0
    sec_counts = {}           # int fr-second -> decoded side1 alive count (redecode-style)
    n_patches = 0

    with open(GT, "rb") as f:
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
                if p and len(p) > 400_000:
                    with open(TMP, "wb") as sf:
                        sf.write(p)
                    doc = D.Doc()
                    es2 = {}
                    _, world_id = D.seed_from_snapshot(TMP, doc, es2)
                    es = es2
                    a = derive_army(es)
                    if len(a[2]) == 24 and len(a[3]) == 30 and not fight:
                        fight = True
                        army = a
                        army_keys = a[2] | a[3]
                        known_keys = set(es.keys())
                        key_type = {k: e.get("__type__") for k, e in es.items()}
                        print("[seed] fight snapshot t=%.2fs  army 24 v 30 ok" % t)
                    continue
                if not fight or es is None:
                    continue
                if last_sec is not None and t < last_sec - 2:
                    continue
                last_sec = t
                if not p:
                    continue
                n_patches += 1
                pre = {k: (es.get(k) or {}).get(F_HP) if k in es else None
                       for k in army_keys}
                pre_in = {k: (k in es) for k in army_keys}
                rec = apply_patch_probe(doc, p, es, world_id, army_keys)
                for (pos, k, mt, after) in rec["creates"]:
                    if not after:
                        known_keys.add(k)
                        key_type.setdefault(k, mt)
                first_exc = rec["exc"][0]["op_pos"] if rec["exc"] else None
                # broken-decoder death channels
                for k in army_keys:
                    if pre_in[k] and k not in es and k not in dec_removed:
                        dec_removed[k] = t
                    hv = (es.get(k) or {}).get(F_HP) if k in es else None
                    if (isinstance(hv, (int, float)) and hv <= 0
                            and k not in dec_hp0
                            and not (isinstance(pre[k], (int, float)) and pre[k] <= 0)):
                        dec_hp0[k] = t
                # raw channels
                for (pos, op, k) in scan_deaths(p, army_keys):
                    if k not in raw_death:
                        raw_death[k] = (t, op, pos, first_exc, len(p))
                for (pos, k) in scan_07(p, army_keys):
                    if k in raw_hp0:
                        continue
                    ok, endp, flds, ops, reason = extract_record(p, pos, key_type.get(k))
                    if F_HP in flds and flds[F_HP] <= 0:
                        raw_hp0[k] = t
                # redecode-style per-second side1 alive count
                sec = int(t)
                alive1 = 0
                for k in army[2]:
                    e = es.get(k)
                    v = e.get(F_HP) if e else None
                    if isinstance(v, (int, float)) and v > 0:
                        alive1 += 1
                sec_counts[sec] = alive1

    print("[run] %d delta patches applied" % n_patches)

    # ---- per-unit death table (side1) ----
    print("\n[3] SIDE1 PER-UNIT DEATH TIMES: raw markers vs broken decoder")
    print("    key    raw_t  raw_ch    marker_in_lost_region   dec_removed  dec_hp0")
    s1raw = []
    s1dec = []
    lost_region = 0
    for k in sorted(army[2]):
        rt = None
        ch = "-"
        in_lost = "-"
        if k in raw_death and k in raw_hp0:
            rt = min(raw_death[k][0], raw_hp0[k])
            ch = "op9" if raw_death[k][0] <= raw_hp0[k] else "hp<=0"
        elif k in raw_death:
            rt, ch = raw_death[k][0], "op9"
        elif k in raw_hp0:
            rt, ch = raw_hp0[k], "hp<=0"
        if k in raw_death:
            t_, op_, pos_, fe_, sz_ = raw_death[k]
            in_lost = ("YES(pos=%d>exc=%s)" % (pos_, fe_)
                       if (fe_ is not None and pos_ > fe_) else "no")
            if fe_ is not None and pos_ > fe_:
                lost_region += 1
        dr = dec_removed.get(k)
        dh = dec_hp0.get(k)
        dt = min(x for x in (dr, dh) if x is not None) if (dr or dh) else None
        if rt is not None:
            s1raw.append(rt)
        if dt is not None:
            s1dec.append(dt)
        print("  %5d  %6s  %6s  %22s  %10s  %8s"
              % (k, ("%.2f" % rt) if rt else "-", ch, in_lost,
                 ("%.2f" % dr) if dr else "-", ("%.2f" % dh) if dh else "-"))
    print("  side1: raw-timed deaths %d/24, broken-decoder-timed %d/24, "
          "op9 markers in post-desync lost region: %d"
          % (len(s1raw), len(s1dec), lost_region))

    # side2 quick numbers
    s2raw = []
    for k in army[3]:
        c = [v for v in (raw_death.get(k, (None,))[0], raw_hp0.get(k)) if v is not None]
        if c:
            s2raw.append(min(c))
    print("  side2: raw-timed deaths %d/30 at %s"
          % (len(s2raw), [round(x, 2) for x in sorted(s2raw)]))

    # ---- fits ----
    print("\n[1/2] TIME-BASE FITS (pred(v) = 24 - #(death/scale <= v + off))")
    offs = [o / 100.0 for o in range(-200, 201, 2)]
    scales_free = [s / 200.0 for s in range(200, 441)]      # 1.000 .. 2.205
    for name, deaths in (("RAW marker-walker", s1raw),
                         ("BROKEN decoder", s1dec)):
        if not deaths:
            print("  %s: no deaths timed" % name)
            continue
        r10, _, b10 = fit_curve(deaths, [1.0], offs)
        r17, _, b17 = fit_curve(deaths, [1.7], offs)
        rf, sf, bf = fit_curve(deaths, scales_free, offs)
        print("  %s (n=%d):" % (name, len(deaths)))
        print("    scale=1.0 (acceptance as-written): best rmse=%.3f at off=%+.2f"
              % (r10, b10))
        print("    scale=1.7 (AoE2 Fast):             best rmse=%.3f at off=%+.2f"
              % (r17, b17))
        print("    free scale:                        best rmse=%.3f at scale=%.3f "
              "off=%+.2f" % (rf, sf, bf))
        for (v, c, pred) in curve_table(deaths, 1.7, b17):
            print("      t=%5.1f  ocr=%2d  pred(s=1.7)=%2d  err=%+d" % (v, c, pred, pred - c))

    # redecode-style count curve at scale 1.7: pred(v) = sec_counts[floor(1.7v+b)]
    print("\n  redecode-style per-second decoded side1 counts (broken decoder):")
    secs = sorted(sec_counts)
    print("    " + " ".join("%d:%d" % (s, sec_counts[s]) for s in secs if s <= 35))
    best = (1e9, None)
    for b in offs:
        tot = 0.0
        for (v, c) in OCR_S1:
            sec = int(1.7 * v + 1.7 * b)
            cc = sec_counts.get(sec)
            if cc is None:
                cc = sec_counts.get(sec - 1, 24)
            tot += (cc - c) ** 2
        r = math.sqrt(tot / len(OCR_S1))
        if r < best[0]:
            best = (r, b)
    print("    fit at scale=1.7: rmse=%.3f at off=%+.2f" % best)

    print("\ndone.")


if __name__ == "__main__":
    main()
