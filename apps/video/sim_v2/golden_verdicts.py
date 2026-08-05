"""golden_verdicts.py — for every matchup recorded more than once, did the result HOLD
or FLIP across runs?

This is the reliability check on the golden set. A matchup whose winner changes between
runs cannot be used as a calibration target on the strength of one recording — and the
kite diagnostic showed that does happen (Champion vs Heavy Cav Archer read as a Champion
win once, then lost 3/3 on repeat).

  python golden_verdicts.py <decoded_dir> [--md OUT.md]
"""
import argparse
import glob
import json
import os
import statistics
import sys
from collections import defaultdict


def base_tag(tag):
    return tag.split("_r")[0] if "_r" in tag else tag


def load(decoded_dir):
    runs = defaultdict(list)
    for p in sorted(glob.glob(os.path.join(decoded_dir, "*.summary.json"))):
        tag = os.path.basename(p)[: -len(".summary.json")]
        try:
            s = json.load(open(p))
            m = json.load(open(str(p).replace(".summary.", ".meta.")))
        except Exception:
            continue
        s2, s3 = s["sides"]["side2"], s["sides"]["side3"]
        win = s["outcome"]
        # margin, signed from side2's perspective: survivors kept minus opponent's
        margin = ((s2["survivors"] / max(1, s2["start_count"]))
                  - (s3["survivors"] / max(1, s3["start_count"])))
        runs[base_tag(tag)].append({
            "tag": tag, "outcome": win, "margin": margin,
            "s2": s2, "s3": s3, "dur": m.get("duration_s"),
        })
    return runs


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("decoded_dir")
    ap.add_argument("--md")
    args = ap.parse_args(argv)

    runs = load(args.decoded_dir)
    repeated = {k: v for k, v in runs.items() if len(v) > 1}
    out = ["# Repeat verdicts — did the result hold?", ""]
    out.append(f"- {len(runs)} matchups recorded, {len(repeated)} with more than one run")
    out.append("")

    holds, flips = [], []
    for tag, rs in sorted(repeated.items()):
        outcomes = {r["outcome"] for r in rs}
        unit2 = rs[0]["s2"]["unit"]
        unit3 = rs[0]["s3"]["unit"]
        wins2 = sum(1 for r in rs if r["outcome"] == "side2")
        wins3 = sum(1 for r in rs if r["outcome"] == "side3")
        other = len(rs) - wins2 - wins3
        margins = [r["margin"] for r in rs]
        rec = {
            "tag": tag, "n": len(rs), "unit2": unit2, "unit3": unit3,
            "wins2": wins2, "wins3": wins3, "other": other,
            "margin_mean": statistics.mean(margins),
            "margin_spread": (max(margins) - min(margins)),
        }
        (flips if len(outcomes) > 1 else holds).append(rec)

    if flips:
        out.append(f"## {len(flips)} matchups FLIPPED — do not calibrate on a single run")
        out.append("")
        out.append("| matchup | runs | side2 wins | side3 wins | other | margin spread |")
        out.append("|---|---|---|---|---|---|")
        for r in flips:
            out.append(f"| {r['unit2']} vs {r['unit3']} | {r['n']} | {r['wins2']} | "
                       f"{r['wins3']} | {r['other']} | {r['margin_spread']:.2f} |")
        out.append("")

    out.append(f"## {len(holds)} matchups HELD across every run")
    out.append("")
    out.append("| matchup | runs | winner | mean margin | margin spread |")
    out.append("|---|---|---|---|---|")
    for r in sorted(holds, key=lambda x: -x["margin_spread"]):
        w = r["unit2"] if r["wins2"] else (r["unit3"] if r["wins3"] else "—")
        out.append(f"| {r['unit2']} vs {r['unit3']} | {r['n']} | {w} | "
                   f"{r['margin_mean']:+.2f} | {r['margin_spread']:.2f} |")

    text = "\n".join(out)
    if args.md:
        open(args.md, "w", encoding="utf-8").write(text)
        print(f"-> {args.md}")
        print(f"{len(flips)} flipped, {len(holds)} held")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))
