"""The Round-4 PURE MELEE GATE scoreboard (the user's own KPI).

The campaign's headline number since Round 4 is not winner-agreement but
*HP-remaining similarity* on pure-melee fights: for every side of every fight
where BOTH armies are melee units, how far is the sim's median surviving HP
from the tape's, expressed in **HP-points** = percent of that side's own army
max HP (count x per-unit max HP). "Within 10 pts" is the pass line; the
62-side corpus is 31 fights x 2 sides.

Why percent-of-army-max and not raw HP: a 21-champion side has 1470 max HP
and a 7-paladin side has 1260 - a flat raw-HP tolerance would mean two very
different things on the two sides of a single fight. Percent makes the two
sides of a fight, and the champion and elephant families, directly
comparable.

Usage:

    python tools/simjs/melee_hp_report.py --sim-runs-dir D:/AI/aoe2_golden/simruns_e12_tapebox
    python tools/simjs/melee_hp_report.py --sim-runs-dir <dir> --json out.json

Reads the SAME inputs as aoe2x.calibration.score (manifest + truth cards +
<run_id>/seed-<n>.json), and takes hp_remaining straight off each side
summary rather than re-deriving it from the damage stream, so it cannot
disagree with the scorer about what survived.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from aoe2x.paths import REPO_ROOT

CALIB = REPO_ROOT / "data" / "calibration"

# Melee = fights the Round-4 gate covers. elite_fire_lancer is deliberately
# NOT here (it has a ranged volley); scorpion/onager/archers obviously not.
MELEE_SLUGS = {
    "champion", "halberdier", "paladin", "heavy_camel", "hussar",
    "elite_steppe", "elite_elephant",
}
# "Basic melee" = the five vanilla-trash/knight-line units the user named
# first; the steppe/elephant fights are melee too but carry their own quirks
# (1-tile reach, trample) so they are reported as a separate block.
BASIC_SLUGS = {"champion", "halberdier", "paladin", "heavy_camel", "hussar"}


def load_manifest():
    return json.loads((CALIB / "manifest.json").read_text(encoding="utf-8"))["fights"]


def load_dicts():
    return json.loads((CALIB / "combat_dicts.json").read_text(encoding="utf-8"))


def melee_fights(fights, *, basic_only=False):
    want = BASIC_SLUGS if basic_only else MELEE_SLUGS
    return [
        f for f in fights
        if f["side1"]["slug"] in want and f["side2"]["slug"] in want
    ]


def _outcome_rank(side):
    return (side.get("survivors") or 0, side.get("hp_remaining") or 0.0,
            side.get("kills") or 0)


def _winner(sides):
    keys = list(sides)
    if len(keys) != 2:
        return None
    a, b = keys
    ra, rb = _outcome_rank(sides[a]), _outcome_rank(sides[b])
    return None if ra == rb else (a if ra > rb else b)


def collect(sim_runs_dir: Path, seeds=range(1, 21)):
    fights = load_manifest()
    dicts = load_dicts()
    rows, fight_rows = [], []

    for fight in melee_fights(fights):
        run_id = fight["run_id"]
        truth_p = CALIB / "truth" / f"{run_id}.json"
        run_dir = sim_runs_dir / run_id
        if not truth_p.exists():
            continue
        truth = json.loads(truth_p.read_text(encoding="utf-8"))

        seed_files = [run_dir / f"seed-{s}.json" for s in seeds]
        raws = [json.loads(p.read_text(encoding="utf-8"))
                for p in seed_files if p.exists()]
        if not raws:
            continue

        # Truth cards key sides "side<owner>" (extract_card's composition
        # shape); the sim runner writes raw "<owner>". Normalise BOTH to the
        # bare owner string here rather than anywhere downstream.
        tape_sides = {k.replace("side", ""): v for k, v in truth["sides"].items()}
        tape_win = _winner(tape_sides)
        sim_wins = [_winner(r["sides"]) for r in raws]
        # median-outcome winner, same rule the main scorer uses
        med_sides = {}
        for key in tape_sides:
            present = [r["sides"][key] for r in raws if key in r["sides"]]
            if present:
                med_sides[key] = {
                    n: statistics.median([s.get(n) or 0 for s in present])
                    for n in ("survivors", "hp_remaining", "kills")
                }
        sim_win = _winner(med_sides)

        fr = {
            "run_id": run_id,
            "basic": (fight["side1"]["slug"] in BASIC_SLUGS
                      and fight["side2"]["slug"] in BASIC_SLUGS),
            "tape_winner": tape_win,
            "sim_winner": sim_win,
            "winner_match": (None if tape_win is None or sim_win is None
                             else tape_win == sim_win),
            "seed_agreement": (round(sum(1 for w in sim_wins if w == tape_win)
                                     / len(sim_wins), 3) if tape_win else None),
            "tape_duration": truth.get("duration_s"),
            "sim_duration": statistics.median([r["duration_s"] for r in raws]),
            "sides": [],
        }

        for side in (fight["side1"], fight["side2"]):
            key = str(side["owner"])
            if key not in tape_sides:
                continue
            maxhp = float(dicts[f"{side['civ']}|{side['slug']}"]["hp"])
            army = maxhp * side["count"]
            tape_hp = tape_sides[key].get("hp_remaining") or 0.0
            sim_hps = [r["sides"][key]["hp_remaining"] for r in raws
                       if key in r["sides"]]
            sim_hp = statistics.median(sim_hps)
            tape_pct = 100.0 * tape_hp / army
            sim_pct = 100.0 * sim_hp / army
            row = {
                "run_id": run_id, "side": key, "slug": side["slug"],
                "count": side["count"], "army_hp": army,
                "basic": fr["basic"],
                "tape_hp": tape_hp, "sim_hp": sim_hp,
                "tape_pct": round(tape_pct, 2), "sim_pct": round(sim_pct, 2),
                "err_pts": round(sim_pct - tape_pct, 2),
                "abs_err": round(abs(sim_pct - tape_pct), 2),
            }
            rows.append(row)
            fr["sides"].append(row)
        fight_rows.append(fr)

    return rows, fight_rows


def summarise(rows, fight_rows):
    def block(rs):
        if not rs:
            return None
        errs = [r["abs_err"] for r in rs]
        return {
            "n": len(rs),
            "within_10": sum(1 for e in errs if e <= 10),
            "within_5": sum(1 for e in errs if e <= 5),
            "within_1": sum(1 for e in errs if e <= 1),
            "mean_abs_err": round(statistics.mean(errs), 3),
            "median_abs_err": round(statistics.median(errs), 3),
        }

    basic_f = [f for f in fight_rows if f["basic"]]
    dur = [f["sim_duration"] / f["tape_duration"] for f in basic_f
           if f.get("tape_duration")]
    all_dur = [f["sim_duration"] / f["tape_duration"] for f in fight_rows
               if f.get("tape_duration")]
    return {
        "all_melee": block(rows),
        "basic_melee": block([r for r in rows if r["basic"]]),
        "steppe_eleph": block([r for r in rows if not r["basic"]]),
        "winners_all": f"{sum(1 for f in fight_rows if f['winner_match'])}/{len(fight_rows)}",
        "winners_basic": f"{sum(1 for f in basic_f if f['winner_match'])}/{len(basic_f)}",
        "dur_ratio_basic_mean": round(statistics.mean(dur), 3) if dur else None,
        "dur_ratio_all_mean": round(statistics.mean(all_dur), 3) if all_dur else None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim-runs-dir", type=Path, required=True)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--worst", type=int, default=12)
    args = ap.parse_args()

    rows, fight_rows = collect(args.sim_runs_dir, range(1, args.seeds + 1))
    summ = summarise(rows, fight_rows)

    print(f"sim runs: {args.sim_runs_dir}")
    for name in ("all_melee", "basic_melee", "steppe_eleph"):
        b = summ[name]
        if b:
            print(f"  {name:14s} n={b['n']:3d}  <=10pts {b['within_10']:3d}  "
                  f"<=5 {b['within_5']:3d}  <=1 {b['within_1']:3d}  "
                  f"mean {b['mean_abs_err']:6.2f}  median {b['median_abs_err']:6.2f}")
    print(f"  winners all {summ['winners_all']}  basic {summ['winners_basic']}")
    print(f"  duration ratio (sim/tape): basic {summ['dur_ratio_basic_mean']}  "
          f"all {summ['dur_ratio_all_mean']}")

    print(f"\nworst {args.worst} sides by |err| (HP-pts):")
    for r in sorted(rows, key=lambda r: -r["abs_err"])[:args.worst]:
        print(f"  {r['run_id']:34s} {r['slug']:15s} tape {r['tape_pct']:6.1f}%  "
              f"sim {r['sim_pct']:6.1f}%  err {r['err_pts']:+7.1f}")

    if args.json:
        args.json.write_text(json.dumps(
            {"sim_runs_dir": str(args.sim_runs_dir), "summary": summ,
             "sides": rows, "fights": fight_rows}, indent=1) + "\n",
            encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
