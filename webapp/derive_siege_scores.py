"""Role: derive — re-derive anti-building (siege) scores into derived_data.db.

The live app reads `derived_data.db` battle_scores. Historically the siege rows
there were written once and only carried forward build-to-build
(`patch_pipeline.carry_forward_battle_scores`), so they held ONLY the aggregate
`anti_building_score` — never the per-castle
`ab_<castle>_<mode>_{ttk,dmg}` breakdown that the rankings hover
(`_buildSiegeBreakdownHtml`) needs. As a result the "Anti-Building Effectiveness"
tab showed "—" for every castle in the breakdown.

This script recomputes the full siege output via
`compute_battle_scores.compute_siege_antibuilding_scores()` (aggregate +
breakdown) and writes it into `derived_data.db` for a target build, then
recomputes rank + median_delta per (line_slug, age, score_type). It is the
siege/anti-building analogue of `derive_unit_rankings.py` (land) — run it
whenever siege stats, the sim, or the siege-line membership change.

Run from the repo root:

    python -m webapp.derive_siege_scores [--build 177723] \
        [--derived-db webapp/derived_data.db]
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from statistics import median as _median

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from compute_battle_scores import compute_siege_antibuilding_scores, SIEGE_LINE_SLUGS
from patches_db import get_current_build

DEFAULT_DERIVED = os.path.join(_here, "derived_data.db")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=None,
                    help="Target build_number (default: current build).")
    ap.add_argument("--derived-db", default=DEFAULT_DERIVED)
    args = ap.parse_args(argv)
    build = args.build or get_current_build() or "170934"

    # {f"{line_slug}|{age}": {f"{civ}|{unit_slug}": {score_type: value, ...}}}
    scores = compute_siege_antibuilding_scores()

    conn = sqlite3.connect(args.derived_db)
    c = conn.cursor()

    # 1) Wipe the existing siege rows for this build (aggregate-only carried-forward
    #    rows) so we replace them with the full aggregate + breakdown set.
    ph = ",".join("?" for _ in SIEGE_LINE_SLUGS)
    c.execute(
        f"DELETE FROM battle_scores WHERE build_number=? AND line_slug IN ({ph})",
        [build, *SIEGE_LINE_SLUGS],
    )

    # 2) Insert fresh rows — one per (civ, unit, score_type), covering the
    #    aggregate anti_building_score AND every ab_*_{ttk,dmg} breakdown key.
    n_rows = 0
    for group_key, members in scores.items():
        line_slug, age = group_key.split("|", 1)
        for sk, score_dict in members.items():
            civ, unit_slug = sk.split("|", 1)
            for score_type, value in score_dict.items():
                c.execute(
                    "INSERT INTO battle_scores "
                    "(line_slug, age, civ_name, unit_slug, score_type, score_value, build_number) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (line_slug, age, civ, unit_slug, score_type, value, build),
                )
                n_rows += 1

    # 3) Recompute rank + median_delta per (line_slug, age, score_type) at this build.
    #    Matches recompute_ranks in compute_battle_scores.py: rank by score_value
    #    desc (1 = highest), median_delta = score_value - median. (Only the
    #    anti_building_score column is surfaced/sorted in the UI; ranking the
    #    breakdown rows too is harmless and keeps every row populated.)
    c.execute(
        "SELECT DISTINCT line_slug, age, score_type FROM battle_scores "
        f"WHERE build_number=? AND line_slug IN ({ph})",
        [build, *SIEGE_LINE_SLUGS],
    )
    groups = c.fetchall()
    for line_slug, age, score_type in groups:
        rows = c.execute(
            "SELECT id, score_value FROM battle_scores "
            "WHERE line_slug=? AND age=? AND score_type=? AND build_number=?",
            (line_slug, age, score_type, build),
        ).fetchall()
        if not rows:
            continue
        med = float(_median([r[1] for r in rows]))
        for rank, (row_id, sv) in enumerate(
            sorted(rows, key=lambda r: r[1], reverse=True), start=1
        ):
            c.execute(
                "UPDATE battle_scores SET rank=?, median_delta=? WHERE id=?",
                (rank, round(sv - med, 4), row_id),
            )

    conn.commit()
    conn.close()
    print(f"derive_siege_scores: wrote {n_rows} rows for build {build} "
          f"across {len(groups)} (line, age, score_type) groups.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
