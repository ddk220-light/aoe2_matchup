"""patch_resim.py — stable multi-seed matchup means for patch-diff analysis.

Run the "my-side" units (a small set of changed units) against the full
opponent pool, averaging N seeds per matchup so that the mean score is
stable enough to diff across two reference DBs (e.g. 170934 vs 177723).

Hard requirement: PyPy 3.  Run with:
    pypy3 -m webapp.patch_resim --my-units my_units.json --out patch_means.db

Invoke twice — once per reference DB — then diff the two output DBs to see
how patch-changed units fared against each opponent.
"""

import argparse
import json
import multiprocessing as mp
import os
import platform
import sqlite3
import statistics
import sys
import time
from collections import defaultdict

# Ensure webapp/ is on the path when run as `pypy3 patch_resim.py`
# (no-op when run as `pypy3 -m webapp.patch_resim`).
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from battle_outcome import signed_score
from run_matchup_battles import (
    _build_slug_to_line,
    _load_unit,
    _units_for_civ,
    SCALES,
    REF_DB_PATH,
)
from sim_outcome_cache import unit_fingerprint
from simulation_real import simulate_real_battle


# ---------------------------------------------------------------------------
# Output DB helpers
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS matchup_means (
  my_civ    TEXT,
  my_slug   TEXT,
  my_age    TEXT,
  opp_civ   TEXT,
  opp_slug  TEXT,
  scale     TEXT,
  mean_score REAL,
  stddev     REAL,
  winner     INTEGER,
  n_seeds    INTEGER,
  PRIMARY KEY (my_civ, my_slug, opp_civ, opp_slug, scale)
);
"""


def _create_out_db(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _insert_row(conn, my_civ, my_slug, my_age, opp_civ, opp_slug,
                scale, mean_score, stddev, winner, n_seeds, commit=True):
    conn.execute(
        """INSERT OR REPLACE INTO matchup_means
               (my_civ, my_slug, my_age, opp_civ, opp_slug, scale,
                mean_score, stddev, winner, n_seeds)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (my_civ, my_slug, my_age, opp_civ, opp_slug, scale,
         mean_score, stddev, winner, n_seeds),
    )
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

_MIN_SEEDS = 5       # second tier: run this many if seed 0 isn't a blowout
_BLOWOUT = 50.0      # |seed-0 score| above this -> 1 sim is enough (clear winner)


def _one(my_cu, opp_cu, fixed_count, resources, seed):
    return signed_score(simulate_real_battle(
        my_cu, opp_cu, resources=resources or 0, fixed_count=fixed_count, seed=seed))


def _sgn(x):
    return 1 if x > 0 else (2 if x < 0 else 0)


def _worker_task(task):
    """task = (rep_key, my_cu, opp_cu, fixed_count, resources, max_seeds)
    Adaptive sampling to spend seeds only where the outcome is in doubt:
      * seed 0 already a blowout (|score| > 50)        -> keep it (1 sim)
      * else run 5; if all 5 agree on the winner       -> keep them (5 sims)
      * else (a genuine coin-flip) run up to max_seeds  -> average all
    Returns (rep_key, mean_score, stddev, winner, n_used).
    """
    rep_key, my_cu, opp_cu, fixed_count, resources, max_seeds = task
    scores = [_one(my_cu, opp_cu, fixed_count, resources, 0)]

    if abs(scores[0]) <= _BLOWOUT:                   # not an obvious blowout -> sample more
        floor = min(_MIN_SEEDS, max_seeds)
        scores += [_one(my_cu, opp_cu, fixed_count, resources, s)
                   for s in range(1, floor)]
        if len({_sgn(x) for x in scores}) > 1:       # the 5 disagree -> contested
            scores += [_one(my_cu, opp_cu, fixed_count, resources, s)
                       for s in range(floor, max_seeds)]

    n = len(scores)
    mean_s = round(sum(scores) / n, 4)
    stddev_s = round(statistics.pstdev(scores), 4) if n > 1 else 0.0
    winner = 1 if mean_s > 0 else (2 if mean_s < 0 else 0)
    return rep_key, mean_s, stddev_s, winner, n


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if platform.python_implementation() != "PyPy":
        sys.stderr.write(
            "\nERROR: patch_resim.py requires PyPy 3.\n"
            "  Run with: pypy3 -m webapp.patch_resim\n\n"
        )
        sys.exit(2)

    parser = argparse.ArgumentParser(
        description="Re-sim a small my-side unit set against the full pool, "
                    "averaging N seeds for stable patch-diff analysis."
    )
    parser.add_argument(
        "--ref", default=REF_DB_PATH,
        help="Path to the reference DB (aoe2_reference.db). Pass different "
             "paths to compare 170934 vs 177723 outcomes."
    )
    parser.add_argument(
        "--my-units", required=True, dest="my_units",
        help='Path to a JSON file containing a list of [civ, slug] or '
             '[civ, slug, age] triples. Age defaults to "Imperial".'
    )
    parser.add_argument(
        "--seeds", type=int, default=15,
        help="MAX seeds per matchup (adaptive). Always runs 5; if those 5 "
             "agree on the winner it stops there, else escalates to this max "
             "and averages all. Default: 15."
    )
    parser.add_argument(
        "--out", required=True,
        help="Output sqlite DB path."
    )
    parser.add_argument(
        "--workers", type=int, default=max(1, int(mp.cpu_count() * 0.75)),
        help="Worker processes (default ~75%% of CPUs, leaving headroom)."
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Load my-units spec
    # ------------------------------------------------------------------
    with open(args.my_units) as f:
        raw_my_units = json.load(f)

    # Normalise to (civ, slug, age) triples.
    my_unit_specs = []
    for entry in raw_my_units:
        if len(entry) == 2:
            civ, slug = entry
            age = "Imperial"
        else:
            civ, slug, age = entry[0], entry[1], entry[2]
        my_unit_specs.append((civ, slug, age))

    # ------------------------------------------------------------------
    # Open reference DB
    # ------------------------------------------------------------------
    ref_conn = sqlite3.connect(args.ref)
    ref_conn.row_factory = sqlite3.Row
    slug_to_line = _build_slug_to_line()

    # ------------------------------------------------------------------
    # Load my-side combat units
    # ------------------------------------------------------------------
    my_units = []  # list of (civ, slug, age, cu)
    for civ, slug, age in my_unit_specs:
        cu = _load_unit(ref_conn, civ, slug, age)
        if cu is None:
            print(f"WARNING: my-unit ({civ}, {slug}, {age}) not found in ref DB — skipping.")
            continue
        my_units.append((civ, slug, age, cu))

    if not my_units:
        sys.stderr.write("ERROR: No my-units loaded. Check --my-units and --ref.\n")
        sys.exit(1)

    print(f"My-side units loaded: {len(my_units)}")

    # ------------------------------------------------------------------
    # Build opponent pool — same logic as run_matchup_battles
    # ------------------------------------------------------------------
    all_civs = sorted({r["civ_name"] for r in ref_conn.execute(
        "SELECT DISTINCT civ_name FROM ref_units"
    ).fetchall()})

    opp_pool = []   # list of (opp_civ, opp_slug, opp_cu, opp_fp)
    seen_opp_keys = set()
    for civ in all_civs:
        for slug in _units_for_civ(ref_conn, civ, slug_to_line):
            key = (civ, slug)
            if key in seen_opp_keys:
                continue
            seen_opp_keys.add(key)
            cu = _load_unit(ref_conn, civ, slug, "Imperial")
            if cu is None:
                continue
            opp_pool.append((civ, slug, cu, unit_fingerprint(cu)))

    ref_conn.close()
    print(f"Opponent pool: {len(opp_pool)} (civ, slug) pairs")

    # ------------------------------------------------------------------
    # Build representative tasks with fingerprint dedup PER (my-unit, scale)
    # ------------------------------------------------------------------
    # rep_key  -> (my_civ, my_slug, my_age, my_cu, fixed_count, resources, opp_fp_rep)
    # members  -> list of (opp_civ, opp_slug) that share this rep
    #
    # Dedup key: for a fixed (my_unit, scale), opponents with identical
    # fingerprints produce identical outcomes for every seed — sim the
    # representative once and copy to all members.

    # rep_key is (my_civ, my_slug, my_age, scale_label, opp_fp)
    rep_tasks = {}          # rep_key -> (my_cu, opp_cu, fixed_count, resources)
    rep_members = defaultdict(list)  # rep_key -> [(opp_civ, opp_slug), ...]

    for my_civ, my_slug, my_age, my_cu in my_units:
        for scale_label, fixed_count, resources in SCALES:
            seen_fps = {}   # opp_fp -> rep_key (first occurrence becomes rep)
            for opp_civ, opp_slug, opp_cu, opp_fp in opp_pool:
                rep_key = (my_civ, my_slug, my_age, scale_label, opp_fp)
                if opp_fp not in seen_fps:
                    seen_fps[opp_fp] = rep_key
                    rep_tasks[rep_key] = (my_cu, opp_cu, fixed_count, resources)
                else:
                    rep_key = seen_fps[opp_fp]
                rep_members[rep_key].append((opp_civ, opp_slug))

    total_reps = len(rep_tasks)
    total_matchups = sum(len(v) for v in rep_members.values())

    print(f"Total matchup rows to write: {total_matchups}")
    print(f"Representative sim tasks (after fingerprint dedup): {total_reps}")
    print(f"Seeds per matchup: {args.seeds}")
    print(f"Workers: {args.workers}")

    # ------------------------------------------------------------------
    # Open output DB
    # ------------------------------------------------------------------
    out_conn = _create_out_db(args.out)

    # ------------------------------------------------------------------
    # Dispatch workers
    # ------------------------------------------------------------------
    worker_tasks = [
        (rep_key, my_cu, opp_cu, fixed_count, resources, args.seeds)
        for rep_key, (my_cu, opp_cu, fixed_count, resources) in rep_tasks.items()
    ]

    t0 = time.perf_counter()
    all_rows = []  # accumulate; one bulk insert after the pool closes (PyPy sqlite

    # dislikes commit() while the worker generator is being consumed)
    with mp.Pool(processes=args.workers) as pool:
        for i, (rep_key, mean_s, stddev_s, winner, n_used) in enumerate(
            pool.imap_unordered(_worker_task, worker_tasks), start=1
        ):
            my_civ, my_slug, my_age, scale_label, _opp_fp = rep_key
            members = rep_members[rep_key]

            for opp_civ, opp_slug in members:
                all_rows.append((
                    my_civ, my_slug, my_age, opp_civ, opp_slug, scale_label,
                    mean_s, stddev_s, winner, n_used,
                ))

            if i <= 5 or i % 20 == 0 or i == total_reps:
                elapsed = time.perf_counter() - t0
                print(
                    f"[{i}/{total_reps}] {my_civ}/{my_slug} × {scale_label} "
                    f"({len(members)} opp) mean={mean_s:+.1f} sd={stddev_s:.1f} "
                    f"seeds={n_used}  ({elapsed:.0f}s)"
                )

    out_conn.executemany(
        "INSERT OR REPLACE INTO matchup_means "
        "(my_civ, my_slug, my_age, opp_civ, opp_slug, scale, "
        " mean_score, stddev, winner, n_seeds) VALUES (?,?,?,?,?,?,?,?,?,?)",
        all_rows,
    )
    out_conn.commit()
    elapsed_total = time.perf_counter() - t0
    print(f"\nDone. {len(all_rows)} matchup rows written in {elapsed_total:.0f}s.")
    out_conn.close()


if __name__ == "__main__":
    main()
