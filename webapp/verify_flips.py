"""verify_flips.py — adversarial, confidence-driven re-sim of candidate patch
matchup changes.

Why this exists
---------------
The adaptive sampler in patch_resim uses an agreement-based stopping rule
("run 5; if all 5 agree on sign, stop") which SELECTS for lucky clustering in
high-variance matchups, biasing |mean| high for the kept-at-5 tier. When BEFORE
keeps n=5 (biased) and AFTER escalates to n=15 (unbiased), the diff fabricates a
swing — e.g. a pure +10 HP buff appearing to LOSE a high-variance camel fight.

Strategy
--------
1. Candidates  = matchups present in both DBs whose raw |after-before| >= PREFILTER.
2. Drop MIRRORS = matchups where my-unit and opponent are the SAME unit line
   (halb vs halb, skirm vs skirm, ...). Those are inherently ~50/50 coin-flips
   with huge variance; a cost-driven "flip" there is noise, not a patch story.
3. Dedup by (my_unit, scale, opp_fingerprint_old, opp_fingerprint_new) so an
   opponent that differs across DBs (e.g. the phantom Cumans camel) keeps its
   own group instead of being merged.
4. UNBIASED, MATCHED, ESCALATING sampler per representative: run seeds in equal
   batches on BOTH DBs and keep going until each side's standard error is tight
   (SE_TARGET) or we hit MAX_SEEDS. This spends few sims on decisive fights and
   pours sims into the genuinely contested cross-archetype ones (guecha vs camel)
   so their outcome is actually concluded.

PyPy 3 required:
    pypy3 -m webapp.verify_flips --before-db ... --after-db ... \
        --ref-old ... --ref-new ... --out verified.db
"""
import argparse
import multiprocessing as mp
import os
import platform
import sqlite3
import statistics
import sys
from collections import defaultdict

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from battle_outcome import signed_score
from run_matchup_battles import _load_unit, _build_slug_to_line, SCALES
from sim_outcome_cache import unit_fingerprint
from simulation_real import simulate_real_battle

PREFILTER = 10.0     # only verify matchups whose raw |after-before| >= this
START_SEEDS = 12     # first matched batch
BATCH_SEEDS = 12     # escalation step
MAX_SEEDS = 72       # ceiling for genuinely contested matchups
SE_TARGET = 3.5      # stop once max(SE_before, SE_after) < this (95% CI ~ +/-7)
SCALE_PARAMS = {label: (fc, res) for label, fc, res in SCALES}

OUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_means (
  my_civ TEXT, my_slug TEXT, my_age TEXT, opp_civ TEXT, opp_slug TEXT, scale TEXT,
  before_mean REAL, before_sd REAL, after_mean REAL, after_sd REAL, n INTEGER,
  PRIMARY KEY (my_civ, my_slug, opp_civ, opp_slug, scale)
);
"""


def _load_raw(path):
    c = sqlite3.connect(path); c.row_factory = sqlite3.Row
    out = {}
    for r in c.execute("SELECT * FROM matchup_means"):
        out[(r["my_civ"], r["my_slug"], r["opp_civ"], r["opp_slug"], r["scale"])] = \
            (r["mean_score"], r["my_age"])
    c.close()
    return out


def _verify_rep(task):
    """Escalating, matched sampler for one representative matchup.
    task = (rep_key, fc, res, my_old, opp_old, my_new, opp_new)
    Returns (rep_key, before_mean, before_sd, after_mean, after_sd, n_used)."""
    rep_key, fc, res, my_old, opp_old, my_new, opp_new = task
    bs, as_ = [], []
    n = 0
    while n < MAX_SEEDS:
        target = min(n + (START_SEEDS if n == 0 else BATCH_SEEDS), MAX_SEEDS)
        for s in range(n, target):
            bs.append(signed_score(simulate_real_battle(
                my_old, opp_old, resources=res or 0, fixed_count=fc, seed=s)))
            as_.append(signed_score(simulate_real_battle(
                my_new, opp_new, resources=res or 0, fixed_count=fc, seed=s)))
        n = target
        sd_b = statistics.pstdev(bs)
        sd_a = statistics.pstdev(as_)
        se = max(sd_b, sd_a) / (n ** 0.5)
        if se < SE_TARGET:
            break
    return (rep_key, round(sum(bs) / n, 3), round(statistics.pstdev(bs), 3),
            round(sum(as_) / n, 3), round(statistics.pstdev(as_), 3), n)


def main():
    if platform.python_implementation() != "PyPy":
        sys.stderr.write("ERROR: verify_flips.py requires PyPy 3.\n")
        sys.exit(2)
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-db", required=True)
    ap.add_argument("--after-db", required=True)
    ap.add_argument("--ref-old", required=True)
    ap.add_argument("--ref-new", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=max(1, int(mp.cpu_count() * 0.75)))
    args = ap.parse_args()

    before = _load_raw(args.before_db)
    after = _load_raw(args.after_db)
    slug_to_line = _build_slug_to_line()

    def is_mirror(my_slug, opp_slug):
        lm = slug_to_line.get(my_slug, my_slug)
        lo = slug_to_line.get(opp_slug, opp_slug)
        return lm == lo

    # candidate keys: in both, raw |swing| >= PREFILTER, NOT a same-line mirror
    cand = []
    n_mirror = 0
    for key, (am, my_age) in after.items():
        if key not in before:
            continue
        my_civ, my_slug, opp_civ, opp_slug, scale = key
        if abs(am - before[key][0]) < PREFILTER:
            continue
        if is_mirror(my_slug, opp_slug):
            n_mirror += 1
            continue
        cand.append((key, my_age))
    print(f"raw candidates (|swing|>={PREFILTER}): {len(cand)+n_mirror}  "
          f"(dropped {n_mirror} same-line mirrors)  -> {len(cand)} to consider")

    # unit caches per DB
    old_conn = sqlite3.connect(args.ref_old); old_conn.row_factory = sqlite3.Row
    new_conn = sqlite3.connect(args.ref_new); new_conn.row_factory = sqlite3.Row
    cache_old, cache_new = {}, {}

    def cu(conn, cache, civ, slug, age):
        k = (civ, slug, age)
        if k not in cache:
            cache[k] = _load_unit(conn, civ, slug, age)
        return cache[k]

    # dedup -> representatives + members
    rep_tasks = {}                     # rep_key -> task tuple
    rep_members = defaultdict(list)    # rep_key -> [(my_age, full_key), ...]
    age_of = {}
    skipped = 0
    for key, my_age in cand:
        my_civ, my_slug, opp_civ, opp_slug, scale = key
        age_of[(my_civ, my_slug)] = my_age
        fc, res = SCALE_PARAMS[scale]
        my_old = cu(old_conn, cache_old, my_civ, my_slug, my_age)
        my_new = cu(new_conn, cache_new, my_civ, my_slug, my_age)
        opp_old = cu(old_conn, cache_old, opp_civ, opp_slug, "Imperial")
        opp_new = cu(new_conn, cache_new, opp_civ, opp_slug, "Imperial")
        if None in (my_old, my_new, opp_old, opp_new):
            skipped += 1
            continue
        fp_old = unit_fingerprint(opp_old)
        fp_new = unit_fingerprint(opp_new)
        rep_key = (my_civ, my_slug, scale, fp_old, fp_new)
        if rep_key not in rep_tasks:
            rep_tasks[rep_key] = (rep_key, fc, res, my_old, opp_old, my_new, opp_new)
        rep_members[rep_key].append(key)
    old_conn.close(); new_conn.close()
    print(f"representatives to sim: {len(rep_tasks)} (covering {sum(len(v) for v in rep_members.values())} "
          f"matchups; skipped {skipped} missing); workers={args.workers}; "
          f"seeds {START_SEEDS}..{MAX_SEEDS} (SE<{SE_TARGET})")

    out = sqlite3.connect(args.out)
    out.execute("PRAGMA synchronous=OFF"); out.execute("PRAGMA journal_mode=WAL")
    out.executescript(OUT_SCHEMA)

    rows = []
    n_done = 0
    import time
    t0 = time.perf_counter()
    seed_hist = defaultdict(int)
    with mp.Pool(processes=args.workers) as pool:
        for rep_key, bmean, bsd, amean, asd, n in pool.imap_unordered(
                _verify_rep, list(rep_tasks.values())):
            seed_hist[n] += 1
            for key in rep_members[rep_key]:
                my_civ, my_slug, opp_civ, opp_slug, scale = key
                rows.append((my_civ, my_slug, age_of[(my_civ, my_slug)], opp_civ,
                             opp_slug, scale, bmean, bsd, amean, asd, n))
            n_done += 1
            if n_done % 50 == 0 or n_done == len(rep_tasks):
                print(f"  [{n_done}/{len(rep_tasks)}] {time.perf_counter()-t0:.0f}s")

    out.executemany(
        "INSERT OR REPLACE INTO verified_means "
        "(my_civ,my_slug,my_age,opp_civ,opp_slug,scale,before_mean,before_sd,after_mean,after_sd,n) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    out.commit(); out.close()
    print(f"\nDone. {len(rows)} matchups written from {len(rep_tasks)} reps in "
          f"{time.perf_counter()-t0:.0f}s.")
    print("seed-count histogram (reps):", dict(sorted(seed_hist.items())))


if __name__ == "__main__":
    main()
