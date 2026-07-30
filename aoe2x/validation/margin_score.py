"""Score a tape run's MARGINS (survivor counts, HP%) against recorded truth.

The corpus win/loss bit was simulation_real.py's training set and can no longer
rank engines; margins were never fitted against, and they move on rows whose bit
never flips. Reads data/validation/tape_runs.db, so it is engine-agnostic and
retro-scores every historical run.

    python -m aoe2x.validation.margin_score --run <run_tag>
    python -m aoe2x.validation.margin_score --diff <before_tag> <after_tag>

MAE convention (pinned here so numbers are reproducible): average the seeds'
values FIRST, then take the absolute error against truth, then mean over rows.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

FIXTURE = Path(__file__).resolve().parent / "tape_margins.json"
REF_DB = REPO / "data" / "golden" / "aoe2_reference.db"
DEFAULT_DB = REPO / "data" / "validation" / "tape_runs.db"


def tape_hp_pct(tape_hp, starting_count, per_unit_hp):
    """Recorded HP as a fraction of the STARTING team's max HP.

    Starting count, not survivors -- the same denominator as
    simulation_real.total_max_hp, so tape truth and sim output share a scale.
    """
    denom = float(starting_count) * float(per_unit_hp)
    return (tape_hp / denom) if denom > 0 else 0.0


def _unit_hp(civ, slug):
    con = sqlite3.connect(str(REF_DB))
    row = con.execute(
        "SELECT final_hp FROM ref_units WHERE civ_name=? AND unit_slug=?"
        " AND age='Imperial'", (civ, slug)).fetchone()
    if row is None:
        raise SystemExit(f"no ref_units row for {civ}/{slug}")
    return float(row[0])


def score_run(db_path, run_tag):
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
    db = sqlite3.connect(str(db_path))

    surv_errs, hp_errs, out = [], [], []
    for f in fx:
        row = db.execute(
            "SELECT AVG(team1_survivors), AVG(team2_survivors),"
            "       AVG(team1_hp_pct), AVG(team2_hp_pct),"
            "       AVG(my_count), AVG(opp_count), COUNT(*)"
            " FROM tape_battles"
            " WHERE run_tag=? AND scale='tape' AND my_civ=? AND my_unit_slug=?"
            "   AND opp_civ=? AND opp_unit_slug=?",
            (run_tag, f["subject_civ"], f["subject_slug"],
             f["opp_civ"], f["opp_slug"])).fetchone()
        if row is None or row[6] == 0:
            continue
        s1, s2, hp1, hp2, n1, n2, n = row

        # Which side does the tape report? Score that side.
        if f["opp_survivors"] is not None:
            side, sim_surv, truth_surv = "opp", s2, f["opp_survivors"]
        else:
            side, sim_surv, truth_surv = "subject", s1, f["subject_survivors"]
        surv_err = abs(sim_surv - truth_surv)
        surv_errs.append(surv_err)

        hp_err = None
        if f["opp_hp"] is not None:
            truth_hp = tape_hp_pct(f["opp_hp"], n2, _unit_hp(f["opp_civ"], f["opp_slug"]))
            hp_err = abs(hp2 - truth_hp) * 100.0
            hp_errs.append(hp_err)

        out.append({
            "opp": f'{f["opp_civ"]}/{f["opp_slug"]}', "side": side, "seeds": n,
            "sim_survivors": round(sim_surv, 2), "tape_survivors": truth_surv,
            "survivor_err": round(surv_err, 2),
            "hp_err_pp": None if hp_err is None else round(hp_err, 2),
        })

    return {
        "run_tag": run_tag,
        "survivor_mae": (sum(surv_errs) / len(surv_errs)) if surv_errs else 0.0,
        "hp_mae_pp": (sum(hp_errs) / len(hp_errs)) if hp_errs else 0.0,
        "n_survivor_rows": len(surv_errs), "n_hp_rows": len(hp_errs),
        "rows": out,
    }


def _print(res):
    print(f"\n=== MARGINS {res['run_tag']} ===")
    print(f"survivor MAE {res['survivor_mae']:.2f} units  ({res['n_survivor_rows']} rows)")
    print(f"HP MAE       {res['hp_mae_pp']:.2f} pp     ({res['n_hp_rows']} rows)")
    for r in sorted(res["rows"], key=lambda x: -x["survivor_err"]):
        hp = "    -" if r["hp_err_pp"] is None else f"{r['hp_err_pp']:5.1f}pp"
        print(f"  {r['opp'][:44]:<44} [{r['side']:<7}]"
              f" sim={r['sim_survivors']:>5} tape={r['tape_survivors']:>3}"
              f" err={r['survivor_err']:>5.2f}  hp_err={hp}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--run")
    ap.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()
    if a.diff:
        b, c = score_run(a.db, a.diff[0]), score_run(a.db, a.diff[1])
        _print(b)
        _print(c)
        print(f"\nsurvivor MAE {b['survivor_mae']:.2f} -> {c['survivor_mae']:.2f}"
              f"   ({c['survivor_mae'] - b['survivor_mae']:+.2f})")
        print(f"HP MAE       {b['hp_mae_pp']:.2f} -> {c['hp_mae_pp']:.2f}"
              f"   ({c['hp_mae_pp'] - b['hp_mae_pp']:+.2f} pp)")
    elif a.run:
        _print(score_run(a.db, a.run))
    else:
        sys.exit("pass --run <tag> or --diff <before> <after>")


if __name__ == "__main__":
    main()
