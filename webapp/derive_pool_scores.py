"""Role: derive — pool scores for every (civ, unit_slug, scale) in a matchup DB.

`--matchup-db` is REQUIRED — point it at the external baseline-of-record
(the committed webapp/matchup_db.db is an Armenians-only stub):

    python -m webapp.derive_pool_scores \\
        --matchup-db D:/AI/matchup_baseline_<build>.db --out webapp/pool_scores.db

A pre-flight guard (matchup_db.preflight_derive_guard) aborts on small
(<40-civ) source DBs unless --allow-small-db, and on rows simmed under a
non-current sim_version unless --allow-stale.

For each combat unit in the three pools (infantry/stable/archer), writes
six rows to pool_scores.db: 3 axes (hp, cost, speed) × 2 scales (30v30, 3k).
Units outside those pools (siege, naval, monks) are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict

# Allow `python -m webapp.derive_pool_scores` from the repo root: make this
# directory (webapp/) importable for the bare sibling imports below.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from matchup_db import preflight_derive_guard
from pool_scores_lib import derive_unit_scores, unit_to_pool
from pool_scores_db import create_db, insert_score
from unit_lines import UNIT_LINES
from patches_db import get_current_build

_WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
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


def _migrate_role_line_means_column(conn: sqlite3.Connection) -> None:
    """Add role_line_means column to legacy DBs that pre-date this column.

    Idempotent: PRAGMA table_info reports current columns; only ALTER if missing.
    NOTE: build_number versioning is NOT migrated here — that requires a full
    table rebuild (the PRIMARY KEY must change), which is owned by
    migrate_baseline.py. derive_pool_scores assumes a current schema (either a
    fresh create_db or a DB already migrated by migrate_baseline).
    """
    cur = conn.execute("PRAGMA table_info(pool_scores)")
    cols = {r[1] for r in cur.fetchall()}
    if "role_line_means" not in cols:
        conn.execute("ALTER TABLE pool_scores ADD COLUMN role_line_means TEXT")
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--matchup-db", required=True,
                   help="Path to the matchup DB to derive from (REQUIRED — "
                        "e.g. D:/AI/matchup_baseline_<build>.db; the committed "
                        "webapp/matchup_db.db is an Armenians-only stub).")
    p.add_argument("--out", default=DEFAULT_OUT_DB)
    p.add_argument("--build", default=None)
    p.add_argument("--allow-small-db", action="store_true",
                   help="Skip the >=40-distinct-civs sanity check "
                        "(deliberately partial source DBs only).")
    p.add_argument("--allow-stale", action="store_true",
                   help="Proceed even if rows were simmed under a non-current "
                        "sim_version (needed after scoped --changed-units re-sims).")
    args = p.parse_args(argv)

    preflight_derive_guard(args.matchup_db,
                           allow_small_db=args.allow_small_db,
                           allow_stale=args.allow_stale)

    build_number = args.build or get_current_build() or "170934"

    matchup_conn = sqlite3.connect(args.matchup_db)
    out_conn = create_db(args.out)
    _migrate_role_line_means_column(out_conn)

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
                # JSON-encode the per-line breakdown for the TEXT column.
                rlm = row.get("role_line_means")
                row["role_line_means"] = json.dumps(rlm) if rlm is not None else None
                row["build_number"] = build_number
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
