"""Report on / compare tape-validation runs recorded by tape_rig.

    python -m aoe2x.validation.report --list
    python -m aoe2x.validation.report --run  <run_tag>
    python -m aoe2x.validation.report --diff <before_tag> <after_tag>

`--diff` is the gate for every engine change: it names the matchups whose
verdict flipped, so a fix that repairs three rows while quietly breaking two
cannot be mistaken for progress. FIXED/BROKE are what matter; STILL-BAD and
unchanged rows are summarised only.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO / "data" / "validation" / "tape_runs.db"


def _rows(db, run_tag, scale):
    """Per-matchup majority verdict for one run+scale."""
    q = """
        SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug,
               my_count, opp_count, tape_outcome,
               AVG(CASE WHEN winner=1 THEN 1.0 ELSE 0.0 END) AS wr,
               AVG(signed_score) AS s,
               AVG(game_time_s)  AS t,
               AVG(team1_hp_pct) AS hp1,
               AVG(team2_hp_pct) AS hp2,
               COUNT(*)          AS n
        FROM tape_battles WHERE run_tag=? AND scale=?
        GROUP BY my_civ, my_unit_slug, opp_civ, opp_unit_slug
    """
    out = {}
    for r in db.execute(q, (run_tag, scale)):
        key = (r[0], r[1], r[2], r[3])
        sim = "win" if r[7] >= 0.5 else "loss"
        out[key] = {
            "n1": r[4], "n2": r[5], "tape": r[6], "wr": r[7], "s": r[8],
            "t": r[9], "hp1": r[10], "hp2": r[11], "seeds": r[12],
            "sim": sim, "ok": sim == r[6],
        }
    return out


def _scales(db, run_tag):
    return [r[0] for r in db.execute(
        "SELECT DISTINCT scale FROM tape_battles WHERE run_tag=? ORDER BY scale",
        (run_tag,))]


def cmd_list(db):
    q = ("SELECT run_tag, run_label, started_utc, python_impl, sim_version,"
         " git_branch, git_dirty, seeds, scales, n_fights, wall_s"
         " FROM tape_runs ORDER BY started_utc")
    rows = list(db.execute(q))
    if not rows:
        print("no runs recorded")
        return
    for r in rows:
        dirty = " *dirty" if r[6] else ""
        print(f"{r[0]}")
        print(f"    {r[2][:19]}  {r[3]}  sv={r[4][:12]}  {r[5]}{dirty}")
        print(f"    seeds={r[7]} scales={r[8]} fights={r[9]} wall={r[10]}s")


def cmd_run(db, run_tag):
    for scale in _scales(db, run_tag):
        rows = _rows(db, run_tag, scale)
        ok = sum(1 for v in rows.values() if v["ok"])
        print(f"\n=== {run_tag}  [{scale}] — {ok}/{len(rows)} agree "
              f"({100.0*ok/max(1,len(rows)):.0f}%) ===")
        for (c1, s1, c2, s2), v in sorted(rows.items(),
                                          key=lambda kv: (kv[1]["ok"], kv[0])):
            print(f"  {'OK ' if v['ok'] else 'XX '}{s1[:26]:<26} vs {s2[:26]:<26}"
                  f" {v['n1']:>3}v{v['n2']:<3} tape={v['tape']:<4} sim={v['sim']:<4}"
                  f" S={v['s']:+7.1f} t={v['t']:5.0f}s")


def cmd_diff(db, before, after):
    any_scale = False
    for scale in _scales(db, before):
        if scale not in _scales(db, after):
            continue
        any_scale = True
        b, a = _rows(db, before, scale), _rows(db, after, scale)
        keys = sorted(set(b) & set(a))
        fixed = [k for k in keys if not b[k]["ok"] and a[k]["ok"]]
        broke = [k for k in keys if b[k]["ok"] and not a[k]["ok"]]
        still = [k for k in keys if not b[k]["ok"] and not a[k]["ok"]]
        good = [k for k in keys if b[k]["ok"] and a[k]["ok"]]

        n_before = sum(1 for k in keys if b[k]["ok"])
        n_after = sum(1 for k in keys if a[k]["ok"])
        print(f"\n=== [{scale}]  {n_before}/{len(keys)} -> {n_after}/{len(keys)} ===")
        for label, ks in (("FIXED", fixed), ("BROKE", broke)):
            for k in ks:
                bb, aa = b[k], a[k]
                print(f"  {label}  {k[1][:24]:<24} vs {k[3][:24]:<24}"
                      f" tape={aa['tape']:<4}"
                      f" {bb['sim']}(S{bb['s']:+.0f}) -> {aa['sim']}(S{aa['s']:+.0f})")
        print(f"  unchanged-good {len(good)}   still-wrong {len(still)}")
        if len(set(b) ^ set(a)):
            print(f"  NOTE: {len(set(b) ^ set(a))} matchups present in only one run")

        # Wall-clock / fight-length movement matters for batch cost.
        bt = sum(b[k]["t"] for k in keys) / max(1, len(keys))
        at = sum(a[k]["t"] for k in keys) / max(1, len(keys))
        print(f"  mean fight length {bt:.0f}s -> {at:.0f}s")
    if not any_scale:
        print("no shared scales between those runs")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--run", metavar="RUN_TAG")
    g.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    a = ap.parse_args()

    p = Path(a.db)
    if not p.exists():
        sys.exit(f"no validation DB at {p} — run tape_rig first")
    db = sqlite3.connect(str(p))

    if a.list:
        cmd_list(db)
    elif a.run:
        cmd_run(db, a.run)
    else:
        cmd_diff(db, a.diff[0], a.diff[1])


if __name__ == "__main__":
    main()
