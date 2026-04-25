"""
Real-sim variant of generate_matchup_db.py.

Same matchup-combo logic (top units, sidekicks, gold combos) but uses the
position-aware simulation (simulation_real.py) instead of the fast
tick-based one.  Output goes to a separate DB so we can compare results
side by side without disturbing the existing matchup_combos.db.

Multiprocessing: 1225 civ-pairs at ~30s/pair single-threaded would take
~10 hours.  We pool across N workers (default: half of available cores)
to bring it down to ~30-60 minutes on a multi-core box.

Usage:
    cd webapp && python3 generate_matchup_db_real.py
    cd webapp && python3 generate_matchup_db_real.py --workers 16

Output:
    webapp/matchup_combos_real.db
"""

import argparse
import itertools
import json
import multiprocessing as mp
import os
import sqlite3
import sys
import time

from best_units import get_matchup_sims, load_civ_power_units
from simulation_real import simulate_real_battle

# Reuse the ranking helpers from the fast-sim batch script.
from generate_matchup_db import (
    CIVS,
    _collect_all_units,
    _get_gold_slugs,
    analyze_matchup_side,
    create_db as _create_fast_db_unused,  # we redefine create_db below
    insert_combos,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "matchup_combos_real.db")


# ---------------------------------------------------------------------------
# Database (same schema as matchup_combos.db, separate file)
# ---------------------------------------------------------------------------


def create_db(reset=True):
    conn = sqlite3.connect(DB_PATH)
    if reset:
        conn.executescript("DROP TABLE IF EXISTS matchup_combos;")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS matchup_combos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ TEXT NOT NULL,
            opponent TEXT NOT NULL,
            combo_type TEXT NOT NULL,
            combo_rank INTEGER NOT NULL,
            sidekick_rank INTEGER DEFAULT 0,
            is_perfect INTEGER NOT NULL DEFAULT 0,
            top_unit_slug TEXT NOT NULL,
            top_unit_name TEXT NOT NULL,
            partner_slug TEXT,
            partner_name TEXT,
            partner_type TEXT NOT NULL,
            gap TEXT,
            gap_names TEXT,
            gap_count INTEGER NOT NULL DEFAULT 0,
            top_unit_score REAL NOT NULL DEFAULT 0,
            partner_score REAL NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_civ ON matchup_combos(civ);
        CREATE INDEX IF NOT EXISTS idx_opponent ON matchup_combos(opponent);
        CREATE INDEX IF NOT EXISTS idx_civ_opponent ON matchup_combos(civ, opponent);
        CREATE INDEX IF NOT EXISTS idx_top_unit ON matchup_combos(top_unit_slug);
        CREATE INDEX IF NOT EXISTS idx_partner ON matchup_combos(partner_slug);
        CREATE INDEX IF NOT EXISTS idx_combo_type ON matchup_combos(combo_type);
        CREATE INDEX IF NOT EXISTS idx_perfect ON matchup_combos(is_perfect);
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


# Per-worker cache of power_data (loaded once per process via _init_worker)
_WORKER_POWER_DATA = None


def _init_worker():
    """Pool initializer: load civ_power_units.json once per worker process."""
    global _WORKER_POWER_DATA
    _WORKER_POWER_DATA = load_civ_power_units()


def process_pair(args):
    """Worker entry point.  Runs sims for one civ pair and returns the
    insertable combo rows for both directions (a-vs-b and b-vs-a).
    """
    civ_a, civ_b, age = args
    power_data = _WORKER_POWER_DATA

    sim_result = get_matchup_sims(
        civ_a, civ_b, age=age, sim_func=simulate_real_battle
    )
    if "error" in sim_result:
        return civ_a, civ_b, None, None, sim_result["error"]

    sim_data = {"left": sim_result["left"], "right": sim_result["right"]}
    name_map = sim_result.get("name_map", {})

    pu_left = power_data[civ_a].get(age, {}).get("power_units", {})
    pu_right = power_data[civ_b].get(age, {}).get("power_units", {})

    left_units = _collect_all_units(pu_left)
    right_units = _collect_all_units(pu_right)

    left_gold_slugs = _get_gold_slugs(left_units)
    right_gold_slugs = _get_gold_slugs(right_units)

    left_by_slug = {u["unit_slug"]: u for u in left_units}
    right_by_slug = {u["unit_slug"]: u for u in right_units}

    left_combos = analyze_matchup_side(
        "left", "right", left_by_slug, right_gold_slugs,
        left_gold_slugs, sim_data, name_map,
    )
    right_combos = analyze_matchup_side(
        "right", "left", right_by_slug, left_gold_slugs,
        right_gold_slugs, sim_data, name_map,
    )
    return civ_a, civ_b, left_combos, right_combos, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, mp.cpu_count() // 2),
        help="parallel worker processes (default: half of CPU count)",
    )
    parser.add_argument(
        "--age",
        default="imperial",
        choices=("imperial", "castle"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="if >0, only process the first N civ pairs (for testing)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="keep existing rows, skip pairs already present in the DB",
    )
    args = parser.parse_args()

    print(f"Loading civ power units...")
    power_data = load_civ_power_units()
    if not power_data:
        print("ERROR: civ_power_units.json missing.  Run: python3 best_units.py")
        sys.exit(1)

    available = [c for c in CIVS if c in power_data]
    missing = [c for c in CIVS if c not in power_data]
    if missing:
        print(f"WARNING: {len(missing)} civs not in power data: {missing}")

    pairs = list(itertools.combinations(available, 2))
    if args.limit > 0:
        pairs = pairs[: args.limit]

    # In resume mode, skip pairs that already have rows in the DB
    # (we only need ONE direction present — both directions are written
    # together when a pair is processed).
    skipped = 0
    if args.resume and os.path.exists(DB_PATH):
        existing = sqlite3.connect(DB_PATH).execute(
            "SELECT DISTINCT civ, opponent FROM matchup_combos"
        ).fetchall()
        done_set = set()
        for c, o in existing:
            done_set.add(frozenset((c, o)))
        before = len(pairs)
        pairs = [p for p in pairs if frozenset(p) not in done_set]
        skipped = before - len(pairs)

    print(f"Pairs to process: {len(pairs)} ({args.workers} workers)")
    if skipped:
        print(f"  Resuming: skipped {skipped} pairs already in DB")
    print(f"Output DB: {DB_PATH}")

    # Each worker loads its own copy of power_data via _init_worker.
    work_items = [(a, b, args.age) for (a, b) in pairs]

    conn = create_db(reset=not args.resume)
    start = time.time()
    done = 0
    errors = []

    with mp.Pool(args.workers, initializer=_init_worker) as pool:
        for civ_a, civ_b, left_combos, right_combos, err in pool.imap_unordered(
            process_pair, work_items, chunksize=1
        ):
            done += 1
            if err:
                errors.append((civ_a, civ_b, err))
                continue
            insert_combos(conn, civ_a, civ_b, left_combos)
            insert_combos(conn, civ_b, civ_a, right_combos)

            if done % 25 == 0 or done == len(pairs):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                eta_min = (len(pairs) - done) / rate / 60 if rate > 0 else 0
                print(f"  {done}/{len(pairs)} pairs "
                      f"({elapsed/60:.1f} min elapsed, ~{eta_min:.1f} min remaining)")
                conn.commit()

    conn.commit()

    elapsed = time.time() - start
    cur = conn.cursor()
    total_rows = cur.execute("SELECT COUNT(*) FROM matchup_combos").fetchone()[0]
    perfect = cur.execute(
        "SELECT COUNT(*) FROM matchup_combos WHERE is_perfect=1"
    ).fetchone()[0]
    gold_gold = cur.execute(
        "SELECT COUNT(*) FROM matchup_combos WHERE combo_type='gold_gold'"
    ).fetchone()[0]
    top_sk = cur.execute(
        "SELECT COUNT(*) FROM matchup_combos WHERE combo_type='top_sidekick'"
    ).fetchone()[0]

    print(f"\nDone in {elapsed/60:.1f} min")
    print(f"Wrote {DB_PATH}")
    print(f"  {total_rows} total rows")
    print(f"  {top_sk} top+sidekick combos ({perfect} perfect)")
    print(f"  {gold_gold} gold+gold combos")

    if errors:
        print(f"\n{len(errors)} pairs errored:")
        for civ_a, civ_b, err in errors[:10]:
            print(f"  {civ_a} vs {civ_b}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    print("\nMost common top units (real sim):")
    rows = cur.execute("""
        SELECT top_unit_name, COUNT(*) as cnt, COUNT(DISTINCT civ) as civ_cnt
        FROM matchup_combos
        WHERE combo_rank = 1 AND combo_type = 'top_sidekick'
        GROUP BY top_unit_slug
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0]}: {r[1]} matchups across {r[2]} civs")

    conn.close()


if __name__ == "__main__":
    main()
