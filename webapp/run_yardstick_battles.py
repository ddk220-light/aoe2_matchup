"""Batch runner: per (civ, power_unit) × (yardstick, scale) → yardstick_battles.db.

Uses fingerprint-based outcome dedup and close-match (|score| <= 10) repeat
runs for noise reduction.  Multi-process pool with resume support.
"""

import argparse
import json
import multiprocessing as mp
import os
import sqlite3
import statistics
import time

from webapp.battle_outcome import BattleOutcome, signed_score, average_outcomes
from webapp.combat_unit_loader import build_combat_dict_from_ref
from webapp.simulation import prepare_combat_unit
from webapp.simulation_real import simulate_real_battle
from webapp.sim_outcome_cache import OutcomeCache, unit_fingerprint
from webapp.yardstick_db import create_db, insert_outcome, has_row, DEFAULT_DB_PATH

REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
POWER_UNITS_PATH = os.path.join(os.path.dirname(__file__), "civ_power_units.json")

# Yardsticks: (slug, canonical_civ).  Canonical civ keeps the yardstick's
# fingerprint identical regardless of who's fighting it — so we measure
# vs a reference Halberdier, not "this civ's Halberdier".
YARDSTICKS = [
    ("champion",         "Vikings"),
    ("paladin",          "Franks"),
    ("arbalester",       "Britons"),
    ("halberdier",       "Britons"),
    ("imp_elite_skirm",  "Britons"),
    ("hussar",           "Magyars"),
]

# Scales: (label, fixed_count_or_None, resources_or_None)
SCALES = [
    ("30v30", 30, None),
    ("3k",    None, 3000),
]

CLOSE_MATCH_THRESHOLD = 10.0
REPEAT_SEEDS = (0, 1, 2)
DEFAULT_SEED = 0


# ---------------------------------------------------------------------------
# Unit-loading helpers
# ---------------------------------------------------------------------------


def _load_unit(conn, civ, slug, age="Imperial"):
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ, slug, age),
    ).fetchone()
    if row is None:
        return None
    cd = build_combat_dict_from_ref(row)
    cu = prepare_combat_unit(cd)
    cu["cost_food"] = cd["cost_food"]
    cu["cost_wood"] = cd["cost_wood"]
    cu["cost_gold"] = cd["cost_gold"]
    cu["outline_size"] = cd.get("outline_size", 0.2)
    cu["cost"] = cd["cost_food"] + cd["cost_wood"] + cd["cost_gold"]
    return cu


def _load_yardsticks(conn):
    out = {}
    for slug, civ in YARDSTICKS:
        unit = _load_unit(conn, civ, slug)
        if unit is None:
            raise RuntimeError(f"Yardstick {civ}/{slug} not in ref DB")
        out[slug] = unit
    return out


def _power_units_for_civ(power_units_data, civ):
    """Return list of unit_slug strings for imperial-age power units of this civ.

    civ_power_units.json maps line slugs (knight, militia, ...) to a list of
    unit entries.  The actual DB slug lives inside each entry as 'unit_slug'.
    Values of None mean the unit line is unavailable for this civ.
    """
    civ_data = power_units_data.get(civ, {})
    imp = civ_data.get("imperial", {}).get("power_units", {})
    slugs = []
    for category_units in imp.values():
        if not isinstance(category_units, dict):
            continue
        for entries in category_units.values():
            # entries is either None (line unavailable) or a list of dicts
            if not entries:
                continue
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        slug = entry.get("unit_slug")
                        if slug:
                            slugs.append(slug)
                        break  # only the first entry per line
            # If entries is a dict (unexpected structure), skip it
    # de-dupe preserving order
    seen, out = set(), []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ---------------------------------------------------------------------------
# Per-pair sim with cache + close-match repeat
# ---------------------------------------------------------------------------


def _run_pair(my_unit, opp_unit, scale_label, fixed_count, resources, cache):
    fp1 = unit_fingerprint(my_unit)
    fp2 = unit_fingerprint(opp_unit)

    outcomes = []
    seeds_used = []
    for seed in REPEAT_SEEDS:
        if not outcomes and seed != DEFAULT_SEED:
            continue  # only the first seed is mandatory
        cached = cache.get(fp1, fp2, fixed_count or 0, 0, scale_label, seed)
        if cached is not None:
            o = cached
        else:
            o = simulate_real_battle(
                my_unit, opp_unit,
                resources=resources or 0,
                fixed_count=fixed_count,
                seed=seed,
            )
            cache.put(fp1, fp2, fixed_count or 0, 0, scale_label, seed, o)
        outcomes.append(o)
        seeds_used.append(seed)

        if seed == DEFAULT_SEED:
            sc = signed_score(o)
            if abs(sc) > CLOSE_MATCH_THRESHOLD:
                break  # decisive — no repeats needed

    if len(outcomes) == 1:
        return outcomes[0], 1, None
    avg = average_outcomes(outcomes)
    scores = [signed_score(o) for o in outcomes]
    stddev = round(statistics.pstdev(scores), 3) if len(scores) > 1 else None
    return avg, len(outcomes), stddev


# ---------------------------------------------------------------------------
# Worker function
# ---------------------------------------------------------------------------


_WORKER_STATE = {}


def _init_worker():
    """Per-process: open ref DB, load yardsticks, init cache."""
    conn = sqlite3.connect(REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    _WORKER_STATE["ref_conn"] = conn
    _WORKER_STATE["yardsticks"] = _load_yardsticks(conn)
    _WORKER_STATE["cache"] = OutcomeCache()


def _worker_run(task):
    """task = (civ, my_slug)"""
    civ, my_slug = task
    conn = _WORKER_STATE["ref_conn"]
    yardsticks = _WORKER_STATE["yardsticks"]
    cache = _WORKER_STATE["cache"]
    my_unit = _load_unit(conn, civ, my_slug)
    if my_unit is None:
        return civ, my_slug, [], "skipped: my unit not found"

    rows = []
    for ys_slug, _ in YARDSTICKS:
        opp = yardsticks[ys_slug]
        for scale_label, fixed_count, resources in SCALES:
            avg, runs_count, stddev = _run_pair(
                my_unit, opp, scale_label, fixed_count, resources, cache
            )
            rows.append({
                "civ": civ, "my_unit_slug": my_slug, "yardstick_slug": ys_slug,
                "scale": scale_label,
                "my_count": avg.team1_start_count, "opp_count": avg.team2_start_count,
                "outcome": avg, "runs_count": runs_count, "score_stddev": stddev,
            })
    return civ, my_slug, rows, None


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing yardstick DB before running")
    parser.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--civs", nargs="+", help="Limit to specific civs")
    args = parser.parse_args()

    if args.reset and os.path.exists(args.db):
        os.remove(args.db)

    out_conn = create_db(args.db)

    with open(POWER_UNITS_PATH) as f:
        power_units = json.load(f)

    civs = args.civs or sorted(power_units.keys())
    tasks = []
    for civ in civs:
        for slug in _power_units_for_civ(power_units, civ):
            # Skip pairs already complete (all yardsticks × all scales).
            if all(
                has_row(out_conn, civ, slug, ys[0], sc[0])
                for ys in YARDSTICKS for sc in SCALES
            ):
                continue
            tasks.append((civ, slug))

    print(f"Running {len(tasks)} (civ, unit) tasks across {args.workers} workers")
    t0 = time.perf_counter()

    with mp.Pool(processes=args.workers, initializer=_init_worker) as pool:
        for i, (civ, slug, rows, err) in enumerate(
            pool.imap_unordered(_worker_run, tasks), start=1
        ):
            if err:
                print(f"[{i}/{len(tasks)}] {civ} {slug} :: {err}")
                continue
            for row in rows:
                insert_outcome(out_conn, **row)
            if i % 10 == 0 or i == len(tasks):
                elapsed = time.perf_counter() - t0
                print(f"[{i}/{len(tasks)}] {civ} {slug} ({elapsed:.0f}s)")

    out_conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
