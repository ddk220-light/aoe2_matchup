"""Side-by-side melee-gate table for two sim-run directories.

Same inputs and same numbers as melee_hp_report.py -- this only puts a BEFORE
and an AFTER run next to each other so a sweep can be read in one pass, and
prints the per-recording family blocks the E14 brief asks for by name.

    python tools/simjs/melee_hp_compare.py --before <dir> --after <dir>
    python tools/simjs/melee_hp_compare.py --before <dir> --after <dir> \
        --family champion__vs__paladin
"""
from __future__ import annotations

import argparse
from pathlib import Path

from melee_hp_report import collect, summarise


def key(r):
    return (r["run_id"], r["side"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--worst", type=int, default=12)
    ap.add_argument("--family", default=None,
                    help="comma-separated run_id prefixes to print in full")
    args = ap.parse_args()

    seeds = range(1, args.seeds + 1)
    br, bf = collect(args.before, seeds)
    ar, af = collect(args.after, seeds)
    bs, as_ = summarise(br, bf), summarise(ar, af)

    print(f"before: {args.before}\nafter : {args.after}\n")
    print(f"{'block':16s} {'n':>3s} {'<=10':>9s} {'<=5':>9s} {'<=1':>9s} {'mean|err|':>13s}")
    for name in ("all_melee", "basic_melee", "steppe_eleph"):
        b, a = bs[name], as_[name]
        if not b:
            continue
        print(f"{name:16s} {b['n']:3d} {b['within_10']:4d}->{a['within_10']:<4d} "
              f"{b['within_5']:4d}->{a['within_5']:<4d} {b['within_1']:4d}->{a['within_1']:<4d} "
              f"{b['mean_abs_err']:6.2f}->{a['mean_abs_err']:<6.2f}")
    print(f"winners all {bs['winners_all']} -> {as_['winners_all']}   "
          f"basic {bs['winners_basic']} -> {as_['winners_basic']}")
    print(f"duration ratio basic {bs['dur_ratio_basic_mean']} -> {as_['dur_ratio_basic_mean']}")

    bmap = {key(r): r for r in br}
    amap = {key(r): r for r in ar}
    print(f"\nworst {args.worst} sides AFTER (tape / before / after, HP-pts):")
    for r in sorted(ar, key=lambda r: -r["abs_err"])[:args.worst]:
        b = bmap.get(key(r))
        print(f"  {r['run_id']:32s} {r['slug']:14s} tape {r['tape_pct']:6.1f}%  "
              f"before {b['sim_pct']:6.1f}% ({b['err_pts']:+6.1f})  "
              f"after {r['sim_pct']:6.1f}% ({r['err_pts']:+6.1f})")

    print(f"\nbiggest MOVERS (|after err| - |before err|):")
    movers = sorted(ar, key=lambda r: r["abs_err"] - bmap[key(r)]["abs_err"])
    for r in movers[:8] + [None] + movers[-8:]:
        if r is None:
            print("  ---")
            continue
        b = bmap[key(r)]
        print(f"  {r['run_id']:32s} {r['slug']:14s} tape {r['tape_pct']:6.1f}%  "
              f"{b['sim_pct']:6.1f}% -> {r['sim_pct']:6.1f}%   "
              f"|err| {b['abs_err']:5.1f} -> {r['abs_err']:5.1f}")

    if args.family:
        for fam in args.family.split(","):
            print(f"\nfamily {fam}:")
            for k in sorted(amap):
                if not k[0].startswith(fam):
                    continue
                r, b = amap[k], bmap[k]
                print(f"  {r['run_id']:32s} {r['slug']:14s} tape {r['tape_pct']:6.1f}%  "
                      f"{b['sim_pct']:6.1f}% -> {r['sim_pct']:6.1f}%")
            for f in af:
                if f["run_id"].startswith(fam):
                    bfr = next(x for x in bf if x["run_id"] == f["run_id"])
                    print(f"  {f['run_id']:32s} winner tape={f['tape_winner']} "
                          f"sim {bfr['sim_winner']}->{f['sim_winner']}  "
                          f"match {bfr['winner_match']}->{f['winner_match']}")


if __name__ == "__main__":
    main()
