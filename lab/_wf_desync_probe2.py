"""_wf_desync_probe2.py — follow-up measurements to _wf_desync_probe.py.

Adds:
  A. corrected dry-parse-filter precision numbers (probe1 print bug),
  B. marker recall with a GROWING keyset (seed + delta-created entities),
  C. a raw marker-walker prototype: extract army HP writes + death markers per patch
     straight from patch bytes (immune to decoder desync), then reconstruct side1's
     count curve and fit it to the footage OCR with one rigid offset in [-2,+2]s,
  D. per-desynced-patch lost-HP-write counts (raw-extracted vs decoder-mirrored),
  E. create-key ranges (explains 08-marker recall), skip-only patch stats.

ASCII-only output. Run with cwd C:\\dev\\aoe2grpc.
"""
import struct
import sys
import math
from collections import Counter

sys.path.insert(0, r"C:\dev\aoe2\aoe2record\lab")
import decode_state_v2 as D                              # noqa: E402
import cade_api_pb2 as pb                                # noqa: E402
from _wf_desync_probe import (apply_patch_probe, scan_07, scan_08,   # noqa: E402
                              derive_army, hexdump)

GT = (r"C:\Users\ddk22\Videos\aoe2_matchups\guecha_sweep\raw recordings"
      r"\Elite Guecha Warrior vs Elite Jaguar Warrior (Muisca vs Aztecs).frames.bin")
TMP = r"C:\dev\aoe2\aoe2record\lab\_wf_seed_tmp2.bin"
F_HP = 12
ENTITY_TYPES = D.ENTITY_TYPES

OCR_S1 = [(0.5, 24), (6.5, 21), (7.5, 18), (8.5, 17), (9.5, 14), (10.5, 11),
          (11.5, 10), (12.5, 8), (13.5, 5), (15.5, 2), (16.5, 0)]


# ---------------------------------------------------------------------------
# Raw record extractor: structural parse from a 07 01 <key> marker, collecting
# scalar field assigns (op2) on the entity itself (relative depth 1).
# ---------------------------------------------------------------------------
def _guess_width(data, p):
    for w in (1, 2, 4, 8):
        if D._op_ok(data, p + w, 2):
            return p + w
    return p + 4


def extract_record(data, pos, ent_type, max_ops=300):
    """Parse one entity record starting AT the 07 01 <key> marker at pos.
    Returns (ok, end_pos, fields_dict, n_ops, reason). fields_dict has only
    depth-1 op2 scalar assigns where the schema knows the type."""
    n = len(data)
    p = pos + 6
    tstack = [None, ent_type]
    fields = {}
    ops = 0
    while p < n and ops < max_ops:
        op = data[p]
        p += 1
        if not (1 <= op <= 14):
            return False, p - 1, fields, ops, "nonop 0x%02x" % op
        ops += 1
        if op == 1:
            if len(tstack) > 1:
                tstack.pop()
            if len(tstack) == 1:
                return True, p, fields, ops, "clean pop"
        elif op in (2, 6, 10):
            if p >= n:
                return False, p, fields, ops, "eof"
            f = data[p]; p += 1
            if op in (6, 10):
                p += 4
            tty = tstack[-1]
            fi = D.SCHEMA.get(tty, {}).get(f) if tty is not None else None
            if fi:
                vt, ism, scal = fi
                if ism or scal is None:
                    p = _guess_width(data, p)
                elif scal == "String":
                    if p + 4 > n:
                        return False, p, fields, ops, "eof strlen"
                    ln = struct.unpack_from("<i", data, p)[0]
                    if ln < 0 or ln > 65536:
                        return False, p, fields, ops, "bad strlen"
                    p += 4 + ln
                else:
                    if op == 2 and len(tstack) == 2 and p + D.SCALARS[scal][1] <= n:
                        fields[f] = struct.unpack_from(D.SCALARS[scal][0], data, p)[0]
                    p += D.SCALARS[scal][1]
            else:
                p = _guess_width(data, p)
        elif op == 3:
            p += 1; tstack.append(None)
        elif op == 4:
            if p + 2 > n:
                return False, p, fields, ops, "eof"
            tstack.append(data[p + 1]); p += 2
        elif op == 5:
            p += 1
        elif op == 7:
            p += 5; tstack.append(None)
        elif op in (8, 11):
            if p + 6 > n:
                return False, p, fields, ops, "eof"
            tstack.append(data[p + 1]); p += 6
        elif op in (9, 12):
            p += 5
        elif op == 13:
            p += 9
        elif op == 14:
            p += 5
        if p > n:
            return False, n, fields, ops, "past eof"
    return True, p, fields, ops, "max ops"


def scan_deaths(data, keys):
    """09 01 <key> (ResetKey) or 0c 01 <key> (Remove) with key in keys."""
    hits = []
    n = len(data)
    i = 0
    while i + 6 <= n:
        if (data[i] == 9 or data[i] == 12) and data[i + 1] == 1:
            k = struct.unpack_from("<i", data, i + 2)[0]
            if k in keys:
                hits.append((i, data[i], k))
        i += 1
    return hits


def main():
    print("=" * 78)
    print("_wf_desync_probe2.py -- marker-walker prototype + corrected marker stats")
    print("=" * 78)

    doc = es = army = None
    world_id = None
    fight = False
    last_sec = None
    army_keys = set()
    seed_keys = set()
    key_type = {}
    known_keys = set()        # seed + pre-desync creates (grows over time)

    records = []

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
                        seed_keys = set(es.keys())
                        known_keys = set(seed_keys)
                        key_type = {k: e.get("__type__") for k, e in es.items()}
                        print("[seed] fight snapshot t=%.2fs entities=%d army %d v %d"
                              % (t, len(es), len(a[2]), len(a[3])))
                    continue
                if not fight or es is None:
                    continue
                if last_sec is not None and t < last_sec - 2:
                    continue
                last_sec = t
                if p:
                    rec = apply_patch_probe(doc, p, es, world_id, army_keys)
                    # growing keyset: trust only pre-desync op8 creates
                    for (pos, k, mt, after) in rec["creates"]:
                        if not after:
                            known_keys.add(k)
                            key_type.setdefault(k, mt)
                    h07k = scan_07(p, known_keys)
                    records.append({"t": round(t, 3), "p": p, "rec": rec, "h07k": h07k})

    desync = [r for r in records if r["rec"]["exc"]]
    clean = [r for r in records if not r["rec"]["exc"] and r["rec"]["skip_before"] == 0]
    skiponly = [r for r in records if not r["rec"]["exc"] and r["rec"]["skip_before"] > 0]
    print("[run] %d delta patches: clean=%d skiponly=%d desynced=%d"
          % (len(records), len(clean), len(skiponly), len(desync)))

    # ---------- A+B: marker eval, growing keyset, corrected dry-parse numbers ----
    print("\n[A/B] 07 01 <key in GROWING known set> on CLEAN patches:")
    tp = fp = 0
    tpc = fpc = 0
    truth_total = 0
    for r in clean:
        truth = set(v[0] for v in r["rec"]["visits"])
        truth_total += len(truth)
        for (pos, k) in r["h07k"]:
            ok, endp, flds, ops, reason = extract_record(r["p"], pos, key_type.get(k))
            if pos in truth:
                tp += 1
                if ok:
                    tpc += 1
            else:
                fp += 1
                if ok:
                    fpc += 1
    print("  hits=%d  TP=%d  FP=%d  precision=%.3f%%  recall=%.2f%% (truth visits=%d)"
          % (tp + fp, tp, fp, 100.0 * tp / max(1, tp + fp),
             100.0 * tp / max(1, truth_total), truth_total))
    print("  dry-parse(extract) filter: TP pass=%d/%d (%.2f%%)  FP pass=%d/%d  "
          "filtered precision=%.3f%%"
          % (tpc, tp, 100.0 * tpc / max(1, tp), fpc, fp,
             100.0 * tpc / max(1, tpc + fpc)))

    # why is recall < 100? whose visits are not in known_keys
    missing = Counter()
    miss_keys = set()
    for r in clean[:600]:
        hitpos = set(pos for (pos, k) in r["h07k"])
        for (pos, k, depth, after) in r["rec"]["visits"]:
            if pos not in hitpos:
                missing[k in seed_keys] += 1
                miss_keys.add(k)
    print("  visits NOT matched by scan (first 600 clean patches): %d  "
          "(key-in-seed=%s)  distinct keys=%d  sample=%s"
          % (sum(missing.values()), dict(missing), len(miss_keys),
             sorted(miss_keys)[:10]))

    # create-key ranges (explains 08-marker recall)
    ckeys = [k for r in clean for (pos, k, mt, after) in r["rec"]["creates"]]
    if ckeys:
        print("  delta-created entity keys: n=%d  min=%d  max=%d  >=1e6: %d"
              % (len(ckeys), min(ckeys), max(ckeys),
                 sum(1 for k in ckeys if k >= 1_000_000)))

    # skip-only patches
    if skiponly:
        sz = sorted(r["rec"]["size"] for r in skiponly)
        atend = sum(1 for r in skiponly
                    if r["rec"]["skip_runs"] and
                    r["rec"]["skip_runs"][0][0] + r["rec"]["skip_runs"][0][1]
                    >= r["rec"]["size"] - 2)
        tot_sk = sum(r["rec"]["skip_before"] for r in skiponly)
        print("  skip-only patches: n=%d sizes median=%d  total skipped bytes=%d  "
              "runs-ending-at-EOF=%d" % (len(skiponly), sz[len(sz) // 2], tot_sk, atend))

    # ---------- C: raw marker-walker prototype --------------------------------
    print("\n[C] RAW MARKER-WALKER (immune to desync): army HP + deaths from bytes")
    hp_series = {}            # key -> list of (t, hp)
    death_marks = {}          # key -> (t, op)
    raw_hp_per_patch = []     # (record_idx, n_army_hp_writes_raw)
    hist = Counter()
    for idx, r in enumerate(records):
        p = r["p"]
        nhp = 0
        for (pos, k) in r["h07k"]:
            if k not in army_keys:
                continue
            ok, endp, flds, ops, reason = extract_record(p, pos, key_type.get(k))
            if F_HP in flds:
                hp_series.setdefault(k, []).append((r["t"], flds[F_HP]))
                nhp += 1
                hist[int(r["t"])] += 1
        for (pos, op, k) in scan_deaths(p, army_keys):
            if k not in death_marks:
                death_marks[k] = (r["t"], op)
        raw_hp_per_patch.append(nhp)

    n_cov = sum(1 for k in army_keys if k in hp_series)
    tot_raw_hp = sum(len(v) for v in hp_series.values())
    print("  army units with raw HP samples: %d/54   total raw HP writes: %d"
          % (n_cov, tot_raw_hp))
    print("  raw HP writes per game-second: %s" % dict(sorted(hist.items())))
    last_hp_t = max((v[-1][0] for v in hp_series.values()), default=-1)
    print("  last raw army HP write at t=%.2f" % last_hp_t)
    nz = sum(1 for k, v in hp_series.items() if min(h for _, h in v) <= 0)
    print("  units whose raw HP series reaches <=0: %d" % nz)
    print("  death markers (op9/op12 on key): %d units  ops=%s"
          % (len(death_marks), Counter(op for _, op in death_marks.values())))

    # death time per army key: earliest of HP<=0 sample or death marker
    deaths = {}
    for k in army_keys:
        cand = []
        if k in hp_series:
            zt = [t for (t, h) in hp_series[k] if h <= 0]
            if zt:
                cand.append(min(zt))
        if k in death_marks:
            cand.append(death_marks[k][0])
        if cand:
            deaths[k] = min(cand)
    s1_deaths = sorted(deaths[k] for k in army[2] if k in deaths)
    s2_deaths = sorted(deaths[k] for k in army[3] if k in deaths)
    print("  side1 deaths timed: %d/24   side2 deaths timed: %d/30"
          % (len(s1_deaths), len(s2_deaths)))
    print("  side1 death times: %s" % [round(x, 2) for x in s1_deaths])
    print("  side2 death times: %s" % [round(x, 2) for x in s2_deaths])

    # acceptance-style fit: pred(t) = 24 - #(deaths <= t + off), off in [-2,2]
    def rmse_for(off):
        errs = []
        for (t, c) in OCR_S1:
            pred = 24 - sum(1 for d in s1_deaths if d <= t + off)
            errs.append((pred - c) ** 2)
        return math.sqrt(sum(errs) / len(errs))

    best = min(((rmse_for(o / 100.0), o / 100.0)
                for o in range(-200, 201)), key=lambda x: x[0])
    print("  OCR fit: rmse at off=0: %.3f   BEST rmse=%.3f at off=%+.2fs"
          % (rmse_for(0.0), best[0], best[1]))
    off = best[1]
    print("  curve at OCR sample times (off=%+.2f):" % off)
    for (t, c) in OCR_S1:
        pred = 24 - sum(1 for d in s1_deaths if d <= t + off)
        print("    t=%5.1f  ocr=%2d  raw-walker=%2d  err=%+d" % (t, c, pred, pred - c))

    # ---------- D: per-desynced-patch lost HP writes ---------------------------
    print("\n[D] LOST ARMY HP WRITES PER DESYNCED PATCH (raw-extracted vs decoded)")
    print("      t   size  1stexc@  raw_hp  decoded_hp  lost")
    tot_raw = tot_dec = 0
    shown = 0
    for idx, r in enumerate(records):
        rc = r["rec"]
        raw_n = raw_hp_per_patch[idx]
        dec_n = len(rc["hp_writes"])
        if rc["exc"]:
            tot_raw += raw_n
            tot_dec += dec_n
            if shown < 40:
                first = rc["exc"][0]["op_pos"]
                print("  %6.2f %6d   %.3f  %6d  %10d  %4d"
                      % (r["t"], rc["size"], first / max(1, rc["size"]),
                         raw_n, dec_n, raw_n - dec_n))
                shown += 1
    print("  desynced-patch totals: raw=%d decoded=%d lost=%d (%.1f%% of raw)"
          % (tot_raw, tot_dec, tot_raw - tot_dec,
             100.0 * (tot_raw - tot_dec) / max(1, tot_raw)))
    all_raw = sum(raw_hp_per_patch)
    all_dec = sum(len(r["rec"]["hp_writes"]) for r in records)
    print("  ALL-patch totals: raw=%d decoded=%d lost=%d (%.1f%% of raw)"
          % (all_raw, all_dec, all_raw - all_dec,
             100.0 * (all_raw - all_dec) / max(1, all_raw)))

    # big-patch census
    big = [r for r in records if r["rec"]["size"] > 4000]
    bigd = [r for r in big if r["rec"]["exc"]]
    print("  patches >4000 bytes: %d, of which desynced: %d" % (len(big), len(bigd)))

    print("\ndone.")


if __name__ == "__main__":
    main()
