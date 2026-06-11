"""Role: batch-runner — single batch runner for matchup_db.db.

For each civ × eligible imperial unit, simulates 1v1 against every other
(civ, unit) at 30v30 and 3k-resource scales.  Mirror symmetry (A vs B
== B vs A from opposite sides) halves work; fingerprint dedup collapses
identical-stat units.

Hard requirement: PyPy 3.  Run with `pypy3 -m aoe2x.batch.run_matchup_battles`.
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

from aoe2x.sim.battle_outcome import signed_score, average_outcomes
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
from aoe2x.batch.matchup_db import create_db, insert_outcome, has_row_with_version, _short_hash, DEFAULT_DB_PATH
from aoe2x.sim.simulation_real import simulate_real_battle, prepare_combat_unit
from aoe2x.sim.sim_outcome_cache import unit_fingerprint
from aoe2x.sim.sim_version import compute_sim_version
from aoe2x.sim.unit_lines import UNIT_LINES, CIV_MISSING_UNITS

from aoe2x.paths import WEBAPP_DIR as _DATA_DIR

REF_DB_PATH = os.path.join(str(_DATA_DIR), "aoe2_reference.db")

RANKED_LINES = frozenset({
    "militia", "spear", "shock_infantry",
    "skirmisher", "archer", "cav_archer", "gunpowder", "scorpion",
    "light_cav", "knight", "camel", "steppe_lancer", "elephant",
})

SCALES = [("30v30", 30, None), ("3k", None, 3000)]
CLOSE_MATCH_THRESHOLD = 5.0
REPEAT_SEEDS = (0, 1, 2)
DEFAULT_SEED = 0


def _build_slug_to_line():
    out = {}
    for line_slug, info in UNIT_LINES.items():
        for k in ("castle_slug", "imperial_slug"):
            if info.get(k):
                out[info[k]] = line_slug
        for k in ("castle_slugs", "imperial_slugs",
                  "extra_castle_slugs", "extra_imperial_slugs"):
            for s in (info.get(k) or []):
                if s:
                    out[s] = line_slug
        for civ_slugs in (info.get("unique_units") or {}).values():
            if isinstance(civ_slugs, list):
                for tup in civ_slugs:
                    for s in tup:
                        if s:
                            out[s] = line_slug
            else:
                for s in civ_slugs:
                    if s:
                        out[s] = line_slug
    return out


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


def _units_for_civ(ref_conn, civ, slug_to_line):
    rows = ref_conn.execute(
        "SELECT unit_slug FROM ref_units WHERE civ_name=? AND age='Imperial'",
        (civ,),
    ).fetchall()
    seen, out = set(), []
    for r in rows:
        slug = r["unit_slug"]
        if slug in seen:
            continue
        if slug_to_line.get(slug) not in RANKED_LINES:
            continue
        if (civ, slug) in CIV_MISSING_UNITS:
            continue
        seen.add(slug)
        out.append(slug)
    return out


def _run_group(my_unit, opp_unit, fixed_count, resources):
    """Run sims for one dedup group; close-match repeats apply."""
    outcomes = []
    for seed in REPEAT_SEEDS:
        if not outcomes and seed != DEFAULT_SEED:
            continue
        o = simulate_real_battle(
            my_unit, opp_unit,
            resources=resources or 0,
            fixed_count=fixed_count,
            seed=seed,
        )
        outcomes.append(o)
        if seed == DEFAULT_SEED:
            if abs(signed_score(o)) > CLOSE_MATCH_THRESHOLD:
                break

    if len(outcomes) == 1:
        return outcomes[0], 1, None
    avg = average_outcomes(outcomes)
    scores = [signed_score(o) for o in outcomes]
    stddev = round(statistics.pstdev(scores), 3) if len(scores) > 1 else None
    return avg, len(outcomes), stddev


def _worker_run(task):
    """task = (group_key, my_unit_dict, opp_unit_dict, fixed_count, resources)
    Returns (group_key, BattleOutcome, runs_count, score_stddev)."""
    group_key, my_unit, opp_unit, fixed_count, resources = task
    avg, runs_count, stddev = _run_group(my_unit, opp_unit, fixed_count, resources)
    return group_key, avg, runs_count, stddev


def _flip_outcome(o):
    """Swap team1/team2 in a BattleOutcome (for mirrored row insertion)."""
    from dataclasses import replace
    flipped_winner = 0 if o.winner == 0 else (2 if o.winner == 1 else 1)
    return replace(
        o,
        winner=flipped_winner,
        team1_hp_pct=o.team2_hp_pct, team2_hp_pct=o.team1_hp_pct,
        team1_survivors=o.team2_survivors, team2_survivors=o.team1_survivors,
        team1_resources_lost=o.team2_resources_lost, team2_resources_lost=o.team1_resources_lost,
        team1_start_count=o.team2_start_count, team2_start_count=o.team1_start_count,
        team1_food_lost=o.team2_food_lost, team1_wood_lost=o.team2_wood_lost, team1_gold_lost=o.team2_gold_lost,
        team2_food_lost=o.team1_food_lost, team2_wood_lost=o.team1_wood_lost, team2_gold_lost=o.team1_gold_lost,
        team1_food_gained=o.team2_food_gained, team1_wood_gained=o.team2_wood_gained, team1_gold_gained=o.team2_gold_gained,
        team2_food_gained=o.team1_food_gained, team2_wood_gained=o.team1_wood_gained, team2_gold_gained=o.team1_gold_gained,
        team1_value_lost=o.team2_value_lost, team2_value_lost=o.team1_value_lost,
        my_cost_food=o.opp_cost_food, my_cost_wood=o.opp_cost_wood, my_cost_gold=o.opp_cost_gold,
        opp_cost_food=o.my_cost_food, opp_cost_wood=o.my_cost_wood, opp_cost_gold=o.my_cost_gold,
    )


def _group_pending(has_row_fn, members, scale_label, sim_version, force=False):
    """Return True if this dedup group must be (re-)simmed.

    force=True bypasses the version-skip (used after a stat-only patch where
    sim_version is unchanged but the unit stats changed)."""
    if force:
        return True
    return not all(
        has_row_fn(m[0], m[1], m[3], m[4], scale_label, sim_version)
        for m in members
    )


def main():
    if platform.python_implementation() != "PyPy":
        sys.stderr.write(
            "\nERROR: run_matchup_battles.py requires PyPy 3.\n"
            "  Then run: pypy3 -m aoe2x.batch.run_matchup_battles\n\n")
        sys.exit(2)
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing matchup DB before running")
    parser.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--civs", nargs="+",
                        help="Limit BOTH sides to specific civs (full subset matrix)")
    parser.add_argument("--my-civs", nargs="+", dest="my_civs",
                        help="Limit MY side to these civs; opp side stays as all civs")
    parser.add_argument("--changed-units", dest="changed_units",
                        help="Path to a JSON list of unit slugs. Only (re-)sim "
                             "matchups where AT LEAST ONE side is in this set; "
                             "all other pairs keep their existing rows. This is "
                             "the 'update only what changed' incremental path.")
    parser.add_argument("--force", action="store_true",
                        help="Re-sim matched groups even if a row already exists "
                             "at the current sim_version (use after a stat-only "
                             "patch). Combine with --changed-units.")
    args = parser.parse_args()

    changed_units = None
    if args.changed_units:
        with open(args.changed_units) as f:
            changed_units = set(json.load(f))
        print(f"Changed-unit filter: {len(changed_units)} slugs — only matchups "
              f"touching one of these will be (re-)simmed.")

    if args.reset and os.path.exists(args.db):
        os.remove(args.db)

    out_conn = create_db(args.db)
    # Bulk-write tuning: this is a batch job writing to a local DB with a backup,
    # so skip per-commit fsync and use WAL. Dedup groups can have 1000+ members
    # (one sim, many rows); without this each row's commit fsyncs and dominates
    # runtime. Combined with per-group (not per-row) commits below.
    out_conn.execute("PRAGMA synchronous=OFF")
    out_conn.execute("PRAGMA journal_mode=WAL")
    sim_version = compute_sim_version()
    print(f"Sim version: {sim_version}")

    ref_conn = sqlite3.connect(REF_DB_PATH)
    ref_conn.row_factory = sqlite3.Row
    slug_to_line = _build_slug_to_line()

    all_civs = sorted({r["civ_name"] for r in ref_conn.execute(
        "SELECT DISTINCT civ_name FROM ref_units"
    ).fetchall()})

    if args.civs:
        my_civs = opp_civs = args.civs
    elif args.my_civs:
        my_civs = args.my_civs
        opp_civs = all_civs
    else:
        my_civs = opp_civs = all_civs

    # Build separate my-side and opp-side unit lists.
    # all_units holds the union (with fingerprints); my_indices marks which
    # entries are eligible to BE the "my side" of a matchup.
    all_units = []   # list of (civ, slug, cu, fingerprint)
    my_indices = set()
    seen_keys = set()
    civs_union = sorted(set(my_civs) | set(opp_civs))
    for civ in civs_union:
        for slug in _units_for_civ(ref_conn, civ, slug_to_line):
            key = (civ, slug)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            cu = _load_unit(ref_conn, civ, slug)
            if cu is None:
                continue
            idx = len(all_units)
            all_units.append((civ, slug, cu, unit_fingerprint(cu)))
            if civ in my_civs:
                my_indices.add(idx)

    ref_conn.close()
    print(f"Eligible units: {len(all_units)} (civ, slug) pairs total; "
          f"{len(my_indices)} on my side")

    # Build (my, opp) pairs with mirror-symmetry dedup.
    # i must be a my-side index; j ranges across all units.
    # When both i and j are my-side, we still apply mirror dedup (i <= j)
    # because the result of A vs B is the mirror of B vs A.
    # When i is my-side but j is opp-only, we ALWAYS create the pair (no mirror needed).
    groups = defaultdict(list)            # key -> list of (my_civ, my_slug, my_fp, opp_civ, opp_slug, opp_fp)
    representatives = {}                   # key -> (my_unit, opp_unit, my_fp, fixed, resources)

    total_slots = 0
    for i in range(len(all_units)):
        if i not in my_indices:
            continue
        for j in range(len(all_units)):
            # Mirror dedup only applies when BOTH sides are my-eligible:
            # otherwise we always need the (my=i, opp=j) row.
            if j in my_indices and j < i:
                continue
            my_civ, my_slug, my_cu, my_fp = all_units[i]
            opp_civ, opp_slug, opp_cu, opp_fp = all_units[j]
            # Incremental scope: a matchup's outcome can only have changed if at
            # least one side is a changed unit. Skip pairs of two unchanged units
            # entirely — their existing rows stay valid.
            if (changed_units is not None
                    and my_slug not in changed_units
                    and opp_slug not in changed_units):
                continue
            for scale_label, fixed_count, resources in SCALES:
                # Add the (my, opp) direction always.
                # Add the mirror (opp, my) only when opp is also my-eligible
                # (otherwise we'd be recording rows where opp-only civs are
                # the my side, which we explicitly said we don't want).
                add_mirror = (i != j) and (j in my_indices)
                total_slots += 2 if add_mirror else 1
                fp_key = tuple(sorted((my_fp, opp_fp)))
                key = (fp_key, scale_label)
                groups[key].append((my_civ, my_slug, my_fp, opp_civ, opp_slug, opp_fp))
                if add_mirror:
                    groups[key].append((opp_civ, opp_slug, opp_fp, my_civ, my_slug, my_fp))
                if key not in representatives:
                    representatives[key] = (my_cu, opp_cu, my_fp, fixed_count, resources)

    # Skip groups whose every member already has a row at the current sim_version.
    pending_keys = []
    skipped = 0
    for key, members in groups.items():
        scale_label = key[1]
        def _has(a, b, c, d, e, f):
            return has_row_with_version(out_conn, a, b, c, d, e, f)
        if _group_pending(_has, members, scale_label, sim_version, force=args.force):
            pending_keys.append(key)
        else:
            skipped += len(members)

    print(f"Total raw slots:        {total_slots}")
    print(f"Unique dedup groups:    {len(groups)}")
    print(f"  Pending:              {len(pending_keys)}")
    print(f"  Skipped (cur ver):    {skipped} slots")

    if not pending_keys:
        print("All groups already complete at current sim_version.")
        out_conn.close()
        return

    # Worker task: (key, my_unit, opp_unit, fixed, resources)
    tasks = []
    for key in pending_keys:
        my_unit, opp_unit, _rep_my_fp, fixed, resources = representatives[key]
        tasks.append((key, my_unit, opp_unit, fixed, resources))
    print(f"Dispatching {len(tasks)} group tasks across {args.workers} workers")
    t0 = time.perf_counter()

    with mp.Pool(processes=args.workers) as pool:
        for i, (group_key, avg, runs_count, stddev) in enumerate(
            pool.imap_unordered(_worker_run, tasks), start=1
        ):
            scale_label = group_key[1]
            members = groups[group_key]
            rep_my_fp = representatives[group_key][2]
            dg = _short_hash(group_key)
            for m_my_civ, m_my_slug, m_my_fp, m_opp_civ, m_opp_slug, m_opp_fp in members:
                # Direction detection by fingerprint:
                # if member's my_fp == rep's my_fp, the rep ran with this side
                # as team1; insert avg as-is.  Otherwise flip team1/team2.
                out = avg if m_my_fp == rep_my_fp else _flip_outcome(avg)
                insert_outcome(
                    out_conn,
                    my_civ=m_my_civ, my_unit_slug=m_my_slug,
                    opp_civ=m_opp_civ, opp_unit_slug=m_opp_slug,
                    scale=scale_label,
                    my_count=out.team1_start_count, opp_count=out.team2_start_count,
                    outcome=out, runs_count=runs_count, score_stddev=stddev,
                    dedup_group=dg, sim_version=sim_version,
                    commit=False,
                )
            out_conn.commit()  # one commit per dedup group, not per row
            if i <= 5 or i % 20 == 0 or i == len(tasks):
                elapsed = time.perf_counter() - t0
                rep_civ, rep_slug, _, _, _, _ = members[0]
                print(f"[{i}/{len(tasks)}] {rep_civ}/{rep_slug} × {scale_label} "
                      f"(group has {len(members)} members) "
                      f"end={avg.end_reason} score={signed_score(avg):.1f}  "
                      f"({elapsed:.0f}s)")

    print(f"\nDone in {time.perf_counter() - t0:.0f}s.")
    out_conn.close()


if __name__ == "__main__":
    main()
