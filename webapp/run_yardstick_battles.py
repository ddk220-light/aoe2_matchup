"""Batch runner: per (civ, power_unit) × (yardstick, scale) → yardstick_battles.db.

Global cross-process dedup: units whose fingerprints are identical across civs
(same final stats, costs, special properties) share a single sim execution.
The result is then distributed to every member of the dedup group.

dedup_group key: (yardstick_slug, scale_label, my_fingerprint_tuple)
  — opp fingerprint is implied by yardstick_slug (canonical civ, fixed).

Close-match (|score| <= 10) repeat runs for noise reduction still apply
within each group's single worker execution.
"""

import argparse
import json
import multiprocessing as mp
import os
import sqlite3
import statistics
import time
from collections import defaultdict

from webapp.battle_outcome import BattleOutcome, signed_score, average_outcomes
from webapp.combat_unit_loader import build_combat_dict_from_ref
from webapp.simulation import prepare_combat_unit
from webapp.simulation_real import simulate_real_battle
from webapp.sim_outcome_cache import unit_fingerprint
from webapp.yardstick_db import (
    create_db, insert_outcome, has_row, DEFAULT_DB_PATH, _short_hash,
)

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
# Per-group sim with close-match repeat
# ---------------------------------------------------------------------------


def _run_group(my_unit, opp_unit, scale_label, fixed_count, resources):
    """Run a sim for one dedup group (one unique fingerprint combo).

    Returns (BattleOutcome, runs_count, score_stddev).
    Close-match repeats: if |score| <= CLOSE_MATCH_THRESHOLD on the first
    seed, run up to 2 more seeds and average for noise reduction.
    """
    outcomes = []
    for seed in REPEAT_SEEDS:
        if not outcomes and seed != DEFAULT_SEED:
            continue  # only run first seed initially
        o = simulate_real_battle(
            my_unit, opp_unit,
            resources=resources or 0,
            fixed_count=fixed_count,
            seed=seed,
        )
        outcomes.append(o)

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
# Worker function (one task = one dedup group)
# ---------------------------------------------------------------------------


def _worker_run(task):
    """task = (group_key, my_unit_dict, opp_unit_dict, fixed_count, resources)

    Returns (group_key, BattleOutcome, runs_count, score_stddev).
    """
    group_key, my_unit, opp_unit, fixed_count, resources = task
    avg, runs_count, stddev = _run_group(my_unit, opp_unit,
                                         group_key[1],  # scale_label
                                         fixed_count, resources)
    return group_key, avg, runs_count, stddev


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

    # -----------------------------------------------------------------------
    # Pre-pass: build dedup groups in the main process
    # -----------------------------------------------------------------------

    ref_conn = sqlite3.connect(REF_DB_PATH)
    ref_conn.row_factory = sqlite3.Row
    yardsticks = _load_yardsticks(ref_conn)

    civs = args.civs or sorted(power_units.keys())

    # groups[key]          = list of (civ, my_unit_slug) members
    # representatives[key] = (my_unit_dict, opp_unit_dict, fixed_count, resources)
    groups = defaultdict(list)
    representatives = {}

    total_slots = 0
    skipped_complete = 0

    for civ in civs:
        for slug in _power_units_for_civ(power_units, civ):
            my_unit = _load_unit(ref_conn, civ, slug)
            if my_unit is None:
                continue
            my_fp = unit_fingerprint(my_unit)

            for ys_slug, _ in YARDSTICKS:
                opp = yardsticks[ys_slug]
                for scale_label, fixed_count, resources in SCALES:
                    total_slots += 1
                    key = (ys_slug, scale_label, my_fp)
                    groups[key].append((civ, slug))
                    if key not in representatives:
                        representatives[key] = (my_unit, opp, fixed_count, resources)

    ref_conn.close()

    # Resume support: skip groups where EVERY member already has a DB row
    pending_keys = []
    for key, members in groups.items():
        ys_slug, scale_label, _fp = key
        all_done = all(
            has_row(out_conn, civ, slug, ys_slug, scale_label)
            for civ, slug in members
        )
        if all_done:
            skipped_complete += len(members)
        else:
            pending_keys.append(key)

    unique_groups = len(groups)
    pending_groups = len(pending_keys)
    reduction = total_slots / unique_groups if unique_groups else 1.0

    print(f"Pre-pass complete:")
    print(f"  Total raw slots : {total_slots}")
    print(f"  Unique dedup groups : {unique_groups}  (pending: {pending_groups})")
    print(f"  Reduction factor  : {reduction:.2f}x")
    print(f"  Skipped (complete): {skipped_complete} slots in {unique_groups - pending_groups} groups")

    if not pending_keys:
        print("All groups already complete — nothing to do.")
        out_conn.close()
        return

    # Build pool tasks for pending groups only
    tasks = [
        (key, *representatives[key])  # (key, my_unit, opp, fixed_count, resources)
        for key in pending_keys
    ]

    print(f"Dispatching {len(tasks)} group tasks across {args.workers} workers")
    t0 = time.perf_counter()

    with mp.Pool(processes=args.workers) as pool:
        for i, (group_key, avg, runs_count, stddev) in enumerate(
            pool.imap_unordered(_worker_run, tasks), start=1
        ):
            ys_slug, scale_label, my_fp = group_key
            members = groups[group_key]

            # Stable dedup_group label: hash of (yardstick, scale, my_fingerprint)
            # so all civs sharing this fingerprint for this matchup are tagged identically.
            dg = _short_hash((ys_slug, scale_label, my_fp))

            for civ, slug in members:
                insert_outcome(
                    out_conn,
                    civ=civ, my_unit_slug=slug,
                    yardstick_slug=ys_slug, scale=scale_label,
                    my_count=avg.team1_start_count, opp_count=avg.team2_start_count,
                    outcome=avg, runs_count=runs_count, score_stddev=stddev,
                    dedup_group=dg,
                )

            if i % 10 == 0 or i == len(tasks):
                elapsed = time.perf_counter() - t0
                rep_civ, rep_slug = members[0]
                print(f"[{i}/{len(tasks)}] {ys_slug} × {scale_label} "
                      f"(rep: {rep_civ}/{rep_slug}, {len(members)} civs share) "
                      f"end={avg.end_reason} score={signed_score(avg):.1f}  "
                      f"({elapsed:.0f}s)")

    elapsed_total = time.perf_counter() - t0

    # -----------------------------------------------------------------------
    # Summary: top-5 groups by member count
    # -----------------------------------------------------------------------
    top5 = sorted(
        ((len(groups[k]), k) for k in groups),
        reverse=True,
    )[:5]
    print("\nTop-5 dedup groups by member count:")
    for count, (ys_slug, scale_label, _fp) in top5:
        rep_civ, rep_slug = groups[(ys_slug, scale_label, _fp)][0]
        print(f"  {rep_slug} × {scale_label} vs {ys_slug} — {count} civs share "
              f"(rep: {rep_civ})")

    print(f"\nDone in {elapsed_total:.0f}s.")

    out_conn.close()


if __name__ == "__main__":
    main()
