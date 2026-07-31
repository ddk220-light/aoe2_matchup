"""E14 validation: do the tape's contact-loss rates EMERGE from the engine?

E13 injected them (a per-swing break probability, a post-kill fumble
probability and a fixed gap). E14 deleted those constants and replaced them
with physical rules, so the same three numbers now have to come out of the
geometry on their own. This script measures exactly the quantities E13 fitted
to, with one implementation fed either a tape's damage stream or a sim run's,
so an "emerged" number and an "injected" one are directly comparable:

  breaks/swing      consecutive landed hits by one attacker, more than
                    reload + SLACK apart, where the EARLIER hit did not kill --
                    i.e. the unit lost contact with a foe that was still alive.
                    Tape 0.0383, pre-E13 engine 0.0036.
  post-kill slow    share of killing blows whose attacker's next landed hit
                    came more than reload + SLACK later. Tape 0.343,
                    pre-E13 engine 0.117.
  break gap         the length of those live-break gaps. Tape median 4.50 s,
                    mean 5.79 s.

    python tools/simjs/melee_break_rates.py --sim-runs-dir <dir>
    python tools/simjs/melee_break_rates.py --sim-runs-dir <dir> --detail
"""
from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from pathlib import Path

from melee_bout_forensics import (
    load_manifest, load_dicts, tape_damage, sim_damage, pick_fights, _q,
)

SLACK = 0.5


def rates(events, owner, reload_s):
    by_attacker = defaultdict(list)
    for e in events:
        if e.get("attacker_owner") == owner:
            by_attacker[e["attacker"]].append(e)
    thresh = reload_s + SLACK
    swings = live_breaks = kills = slow_kills = 0
    gaps = []
    for hits in by_attacker.values():
        hits.sort(key=lambda e: e["t"])
        swings += len(hits)
        for a, b in zip(hits, hits[1:]):
            gap = b["t"] - a["t"]
            slow = gap > thresh
            if a.get("kill"):
                if slow:
                    slow_kills += 1
            elif slow:
                live_breaks += 1
                gaps.append(gap)
        kills += sum(1 for e in hits[:-1] if e.get("kill"))
    return {
        "swings": swings,
        "breaks_per_swing": live_breaks / swings if swings else None,
        "post_kill_slow_frac": slow_kills / kills if kills else None,
        "break_gap_median": statistics.median(gaps) if gaps else None,
        "break_gap_mean": statistics.mean(gaps) if gaps else None,
        "n_breaks": live_breaks,
        "n_kills": kills,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fights", default="melee")
    ap.add_argument("--sim-runs-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()

    dicts = load_dicts()
    rows = []
    for fight in pick_fights(args.fights):
        try:
            tev = tape_damage(fight["tag"])
            sev = sim_damage(args.sim_runs_dir, fight["run_id"], args.seed)
        except FileNotFoundError:
            continue
        for side in (fight["side1"], fight["side2"]):
            u = dicts[f"{side['civ']}|{side['slug']}"]
            r = 1.0 / u["attack_speed"]
            rows.append({
                "run_id": fight["run_id"], "slug": side["slug"],
                "tape": rates(tev, side["owner"], r),
                "sim": rates(sev, side["owner"], r),
            })

    def pooled(stream, num, den):
        n = sum(r[stream][num] for r in rows)
        d = sum(r[stream][den] for r in rows)
        return n / d if d else None

    print(f"{len(rows)} melee sides   sim={args.sim_runs_dir}\n")
    print(f"{'quantity':26s} {'tape':>9s} {'engine':>9s}   ratio")
    for label, num, den in [
        ("breaks per swing", "n_breaks", "swings"),
        ("post-kill slow fraction", None, None),
    ]:
        if num:
            t, s = pooled("tape", num, den), pooled("sim", num, den)
        else:
            t = sum(r["tape"]["post_kill_slow_frac"] * r["tape"]["n_kills"]
                    for r in rows if r["tape"]["post_kill_slow_frac"] is not None) \
                / max(1, sum(r["tape"]["n_kills"] for r in rows))
            s = sum(r["sim"]["post_kill_slow_frac"] * r["sim"]["n_kills"]
                    for r in rows if r["sim"]["post_kill_slow_frac"] is not None) \
                / max(1, sum(r["sim"]["n_kills"] for r in rows))
        print(f"{label:26s} {t:9.4f} {s:9.4f}   {s / t if t else 0:.3f}")

    for label, key in [("break gap median", "break_gap_median"),
                       ("break gap mean", "break_gap_mean")]:
        t = [r["tape"][key] for r in rows if r["tape"][key] is not None]
        s = [r["sim"][key] for r in rows if r["sim"][key] is not None]
        tv = statistics.median(t) if t else 0
        sv = statistics.median(s) if s else 0
        print(f"{label:26s} {tv:9.3f} {sv:9.3f}   {sv / tv if tv else 0:.3f}")

    print(f"{'total swings':26s} {sum(r['tape']['swings'] for r in rows):9d} "
          f"{sum(r['sim']['swings'] for r in rows):9d}")
    print(f"{'total live breaks':26s} {sum(r['tape']['n_breaks'] for r in rows):9d} "
          f"{sum(r['sim']['n_breaks'] for r in rows):9d}")

    if args.detail:
        print(f"\n{'run_id':30s} {'side':14s} {'breaks/swing t/e':>20s}")
        for r in rows:
            t, s = r["tape"], r["sim"]
            print(f"{r['run_id']:30s} {r['slug']:14s} "
                  f"{t['breaks_per_swing']:8.4f}/{s['breaks_per_swing']:<8.4f}")
    void = _q
    del void


if __name__ == "__main__":
    main()
