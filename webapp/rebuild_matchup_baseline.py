"""Role: batch-runner — rebuild the COMPLETE matchup table as a reliable multi-seed baseline.

Why: the live matchup_db was sampled at 1-or-3 seeds, so contested matchups
(high per-seed variance) flip win/loss between seeds -> inconsistent results.
This re-sims every DIFFERENT-unit matchup (skips same-unit mirrors like
halb-vs-halb) with an ESCALATING sampler: few seeds on decisive fights, many
on contested ones, stopping when the standard error of the mean is tight. The
output is the solid baseline for build 177723 and for future patch diffs.

Each unit's matchup gets: mean signed score, per-seed SD, seeds used (n), and a
VERDICT (win / loss / tossup). "tossup" = |mean| < BAND or SD > |mean| (a
genuine coin-flip; more sims won't make it definitive).

Reuses run_matchup_battles' enumeration + fingerprint dedup (one sim per unique
stat-pair, expanded to all members). Resumable: completed dedup groups are
recorded in `groups_done`; re-running skips them.

PyPy 3 required:
    pypy3 -m webapp.rebuild_matchup_baseline --out D:/AI/matchup_baseline.db \
        --workers 16 [--dry-run] [--sample N]
"""
import argparse
import math
import multiprocessing as mp
import os
import platform
import sqlite3
import statistics
import sys
import time
from collections import defaultdict

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from battle_outcome import signed_score, average_outcomes
from matchup_db import create_db, insert_outcome, _short_hash, DEFAULT_DB_PATH
from sim_outcome_cache import unit_fingerprint
from sim_version import compute_sim_version
from simulation_real import simulate_real_battle
from run_matchup_battles import (
    _build_slug_to_line, _load_unit, _units_for_civ, _flip_outcome,
    REF_DB_PATH, RANKED_LINES, SCALES,
)

# Escalating sampler knobs (tuned for full-table throughput).
START_SEEDS = 8       # first batch
BATCH_SEEDS = 8       # escalation step
MAX_SEEDS = 40        # ceiling for genuinely contested matchups
SE_TARGET = 4.0       # stop once SD/sqrt(n) < this (95% CI ~ +/-8)
BAND = 10.0           # |mean| <= BAND -> tossup

MEANS_SCHEMA = """
CREATE TABLE IF NOT EXISTS matchup_means (
  my_civ TEXT, my_slug TEXT, opp_civ TEXT, opp_slug TEXT, scale TEXT,
  mean REAL, sd REAL, n INTEGER, verdict TEXT, dedup_group TEXT,
  PRIMARY KEY (my_civ, my_slug, opp_civ, opp_slug, scale)
);
CREATE TABLE IF NOT EXISTS groups_done (dg TEXT PRIMARY KEY, scale TEXT, n INTEGER);
"""


def verdict_of(mean, sd):
    if abs(mean) <= BAND or (sd is not None and sd > abs(mean)):
        return "tossup"
    return "win" if mean > 0 else "loss"


def _escalating(my_unit, opp_unit, fixed_count, resources):
    """Matched-seed escalating sampler for one matchup. Returns
    (avg_outcome, n_used, score_sd, mean_score)."""
    outcomes, scores, n = [], [], 0
    while n < MAX_SEEDS:
        target = min(n + (START_SEEDS if n == 0 else BATCH_SEEDS), MAX_SEEDS)
        for s in range(n, target):
            o = simulate_real_battle(my_unit, opp_unit, resources=resources or 0,
                                     fixed_count=fixed_count, seed=s)
            outcomes.append(o)
            scores.append(signed_score(o))
        n = target
        sd = statistics.pstdev(scores)
        if sd / math.sqrt(n) < SE_TARGET:
            break
    return (average_outcomes(outcomes), n, round(statistics.pstdev(scores), 3),
            round(sum(scores) / n, 3))


def _worker(task):
    key, my_unit, opp_unit, fixed, res = task
    try:
        avg, n, sd, mean = _escalating(my_unit, opp_unit, fixed, res)
        return key, avg, n, sd, mean
    except Exception:
        return key, None, 0, 0.0, 0.0      # poison-pill matchup: skip, don't kill the pool


def _build_groups(workers_print=True):
    """Enumerate eligible units, build fingerprint-dedup groups, EXCLUDING
    same-unit mirrors (my_slug == opp_slug). Returns (groups, representatives)."""
    ref = sqlite3.connect(REF_DB_PATH)
    ref.row_factory = sqlite3.Row
    slug_to_line = _build_slug_to_line()
    all_civs = sorted({r["civ_name"] for r in ref.execute(
        "SELECT DISTINCT civ_name FROM ref_units")})

    all_units, seen = [], set()
    for civ in all_civs:
        for slug in _units_for_civ(ref, civ, slug_to_line):
            if (civ, slug) in seen:
                continue
            seen.add((civ, slug))
            cu = _load_unit(ref, civ, slug)
            if cu is not None:
                all_units.append((civ, slug, cu, unit_fingerprint(cu)))
    ref.close()

    groups = defaultdict(list)       # key -> [(my_civ,my_slug,my_fp,opp_civ,opp_slug,opp_fp)]
    representatives = {}
    n_units = len(all_units)
    for i in range(n_units):
        my_civ, my_slug, my_cu, my_fp = all_units[i]
        for j in range(n_units):
            if j < i:                                    # mirror symmetry A/B == B/A
                continue
            opp_civ, opp_slug, opp_cu, opp_fp = all_units[j]
            if my_slug == opp_slug:                      # skip same-unit mirrors (halb v halb)
                continue
            for scale_label, fixed_count, resources in SCALES:
                fp_key = tuple(sorted((my_fp, opp_fp)))
                key = (fp_key, scale_label)
                groups[key].append((my_civ, my_slug, my_fp, opp_civ, opp_slug, opp_fp))
                if i != j:
                    groups[key].append((opp_civ, opp_slug, opp_fp, my_civ, my_slug, my_fp))
                if key not in representatives:
                    representatives[key] = (my_cu, opp_cu, my_fp, fixed_count, resources)
    return all_units, groups, representatives


def main():
    if platform.python_implementation() != "PyPy":
        sys.stderr.write("ERROR: rebuild_matchup_baseline.py requires PyPy 3.\n")
        sys.exit(2)
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("D:/AI", "matchup_baseline.db"))
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--dry-run", action="store_true", help="count groups, no sim")
    ap.add_argument("--sample", type=int, default=0, help="sim only N groups (timing)")
    args = ap.parse_args()

    sim_version = compute_sim_version()
    all_units, groups, representatives = _build_groups()
    total_members = sum(len(v) for v in groups.values())
    print(f"Units: {len(all_units)} | unique dedup groups (non-mirror): {len(groups)} "
          f"| total matchup rows they expand to: {total_members}", flush=True)
    print(f"Sim version: {sim_version} | escalating {START_SEEDS}..{MAX_SEEDS} "
          f"(SE<{SE_TARGET}) | workers={args.workers}", flush=True)
    if args.dry_run:
        return

    out = create_db(args.out)
    out.isolation_level = None      # autocommit: avoids PyPy "stmt in progress" on commit
    out.execute("PRAGMA synchronous=OFF")
    out.execute("PRAGMA journal_mode=WAL")
    out.executescript(MEANS_SCHEMA)
    _cur = out.execute("SELECT dg FROM groups_done")
    done = {r[0] for r in _cur.fetchall()}
    _cur.close()

    keys = list(groups.keys())
    if args.sample:
        keys = keys[: args.sample]
    tasks = []
    for key in keys:
        dg = _short_hash(key)
        if dg in done:
            continue
        my_unit, opp_unit, _fp, fixed, res = representatives[key]
        tasks.append((key, my_unit, opp_unit, fixed, res))
    print(f"Pending groups: {len(tasks)} (skipped {len(keys) - len(tasks)} already done)",
          flush=True)
    if not tasks:
        print("Nothing to do.", flush=True)
        out.close()
        return

    t0 = time.perf_counter()
    n_done = n_rows = 0
    seed_hist = defaultdict(int)
    with mp.Pool(processes=args.workers) as pool:
        for key, avg, n, sd, mean in pool.imap_unordered(_worker, tasks):
            scale_label = key[1]
            if avg is None:                 # worker hit an error on this matchup
                out.execute("INSERT OR REPLACE INTO groups_done (dg, scale, n) "
                            "VALUES (?,?,?)", (_short_hash(key), scale_label, 0))
                n_done += 1
                print(f"  [skip] group {_short_hash(key)} sim error -> marked done(n=0)",
                      flush=True)
                continue
            members = groups[key]
            rep_my_fp = representatives[key][2]
            dg = _short_hash(key)
            vd = verdict_of(mean, sd)
            for m_my_civ, m_my_slug, m_my_fp, m_opp_civ, m_opp_slug, m_opp_fp in members:
                o = avg if m_my_fp == rep_my_fp else _flip_outcome(avg)
                ms = mean if m_my_fp == rep_my_fp else -mean
                insert_outcome(
                    out, my_civ=m_my_civ, my_unit_slug=m_my_slug,
                    opp_civ=m_opp_civ, opp_unit_slug=m_opp_slug, scale=scale_label,
                    my_count=o.team1_start_count, opp_count=o.team2_start_count,
                    outcome=o, runs_count=n, score_stddev=sd,
                    dedup_group=dg, sim_version=sim_version, commit=False)
                out.execute(
                    "INSERT OR REPLACE INTO matchup_means "
                    "(my_civ,my_slug,opp_civ,opp_slug,scale,mean,sd,n,verdict,dedup_group) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (m_my_civ, m_my_slug, m_opp_civ, m_opp_slug, scale_label,
                     ms, sd, n, verdict_of(ms, sd), dg))
                n_rows += 1
            out.execute("INSERT OR REPLACE INTO groups_done (dg, scale, n) VALUES (?,?,?)",
                        (dg, scale_label, n))
            n_done += 1
            seed_hist[n] += 1
            if n_done % 25 == 0 or n_done == len(tasks):
                el = time.perf_counter() - t0
                rate = n_done / el if el else 0
                eta = (len(tasks) - n_done) / rate if rate else 0
                print(f"[{n_done}/{len(tasks)}] rows={n_rows} {el:.0f}s "
                      f"rate={rate:.2f} grp/s eta={eta/60:.0f}min "
                      f"seeds={dict(sorted(seed_hist.items()))}", flush=True)
    print(f"\nDone. {n_done} groups, {n_rows} matchup rows in "
          f"{time.perf_counter()-t0:.0f}s.", flush=True)
    out.close()


if __name__ == "__main__":
    main()
