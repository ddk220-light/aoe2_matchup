"""Derive pool scores for every (civ, unit_slug, scale) in matchup_db.

Run from the webapp/ directory (matches the project's existing
script-running convention — see CLAUDE.md):

    cd webapp && python derive_pool_scores.py

Or with explicit paths:

    cd webapp && python derive_pool_scores.py \\
        --matchup-db matchup_db.db --out pool_scores.db

For each combat unit in the three pools (infantry/stable/archer), writes
six rows to pool_scores.db: 3 axes (hp, cost, speed) × 2 scales (30v30, 3k).
Units outside those pools (siege, naval, monks) are skipped.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from collections import defaultdict

from pool_scores_lib import derive_unit_scores, unit_to_pool
from pool_scores_db import create_db, insert_score
from unit_lines import UNIT_LINES

_WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MATCHUP_DB = os.path.join(_WEBAPP_DIR, "matchup_db.db")
DEFAULT_OUT_DB = os.path.join(_WEBAPP_DIR, "pool_scores.db")

ROW_KEYS = (
    "opp_unit_slug", "winner", "team1_hp_pct", "team2_hp_pct",
    "my_count", "my_cost_food", "my_cost_wood", "my_cost_gold",
    "opp_count", "opp_cost_food", "opp_cost_wood", "opp_cost_gold",
    "game_time_s", "dedup_group",
)


def _fetch_unit_rows(matchup_conn: sqlite3.Connection,
                     civ: str, unit_slug: str, scale: str) -> list[dict]:
    cur = matchup_conn.cursor()
    cur.execute(f"""
        SELECT {", ".join(ROW_KEYS)}
        FROM matchup_battles
        WHERE my_civ = ? AND my_unit_slug = ? AND scale = ?
    """, (civ, unit_slug, scale))
    return [dict(zip(ROW_KEYS, r)) for r in cur.fetchall()]


def _list_unit_pairs(matchup_conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """All (civ, unit_slug) pairs that have at least one battle row."""
    cur = matchup_conn.cursor()
    cur.execute("""
        SELECT DISTINCT my_civ, my_unit_slug
        FROM matchup_battles
        ORDER BY my_civ, my_unit_slug
    """)
    return [(r[0], r[1]) for r in cur.fetchall()]


def _sim_version_for(matchup_conn: sqlite3.Connection,
                     civ: str, unit_slug: str) -> str | None:
    cur = matchup_conn.cursor()
    cur.execute("""
        SELECT sim_version FROM matchup_battles
        WHERE my_civ = ? AND my_unit_slug = ?
        LIMIT 1
    """, (civ, unit_slug))
    row = cur.fetchone()
    return row[0] if row else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--matchup-db", default=DEFAULT_MATCHUP_DB)
    p.add_argument("--out", default=DEFAULT_OUT_DB)
    args = p.parse_args(argv)

    matchup_conn = sqlite3.connect(args.matchup_db)
    out_conn = create_db(args.out)

    pairs = _list_unit_pairs(matchup_conn)
    written = 0
    skipped_no_pool = 0
    by_pool: dict[str, int] = defaultdict(int)

    for civ, unit_slug in pairs:
        if unit_to_pool(UNIT_LINES, unit_slug) is None:
            skipped_no_pool += 1
            continue
        sim_version = _sim_version_for(matchup_conn, civ, unit_slug)
        for scale in ("30v30", "3k"):
            rows = _fetch_unit_rows(matchup_conn, civ, unit_slug, scale)
            if not rows:
                continue
            out_rows = derive_unit_scores(
                civ=civ, unit_slug=unit_slug, scale=scale, rows=rows,
                sim_version=sim_version,
            )
            for row in out_rows:
                insert_score(out_conn, row)
                written += 1
                by_pool[row["pool"]] += 1
        out_conn.commit()

    matchup_conn.close()
    out_conn.close()

    print(f"Wrote {written} rows to {args.out}")
    print(f"  by pool: {dict(by_pool)}")
    print(f"  skipped (no pool): {skipped_no_pool} (civ, unit) pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
