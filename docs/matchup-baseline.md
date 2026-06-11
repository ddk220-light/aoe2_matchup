# The Matchup Baseline (build 177723)

A reliable, multi-seed, verdict-tagged simulation of **every different-unit matchup**,
used as the source of truth for the Rankings, Matchup Advisor, and civ power-units,
and as the baseline-of-record for future patch diffs.

## Why it exists

The position-based battle engine (`simulation_real.py`) is **not deterministic** — at a
fixed seed, contested matchups vary widely (per-seed stdev 14–25). The old matchup
cache stored **single-seed (or 1-or-3-seed)** results, so any close matchup could show a
different winner from one run to the next. That made site-wide win/loss data unreliable
for exactly the matchups people care about, and a patch "flip" was often just noise.

The fix: re-sim every matchup with an **escalating multi-seed sampler** (cheap on
decisive fights, many seeds on contested ones), record the **mean, standard deviation,
seed count, and a verdict** (`win` / `loss` / `tossup`), and derive everything downstream
from that. Coin-flips are now reported as coin-flips instead of a confident W/L.

## How it was built — `webapp/rebuild_matchup_baseline.py`

Run (PyPy 3 required):

```
pypy3 -m webapp.rebuild_matchup_baseline --out D:/AI/matchup_baseline.db --workers 12
```

Pipeline inside the script:

1. **Enumerate** every eligible Imperial unit per civ (`RANKED_LINES`, post-phantom-fix
   availability, excludes `CIV_MISSING_UNITS`). 515 (civ, unit) pairs for build 177723.
2. **Pair** them with mirror symmetry (A-vs-B computed once, B-vs-A is its flip) and
   **fingerprint dedup** — units with identical stats collapse to ONE sim group
   (`sim_outcome_cache.unit_fingerprint`). 515 units → **67,654 unique dedup groups**.
   *Note (2026-06-11): a fingerprint dead-key bug (fixed; see
   `docs/architecture/derived-data.md`) made this dedup over-aggressive — the corrected
   fingerprint yields ~111,664 groups, so the next full rebuild at `sim_version
   e221c8a3a0437bd8` simulates ~63% more groups than this baseline did.*
3. **Exclude same-unit mirrors** (`my_slug == opp_slug`, e.g. halb-vs-halb): inherently
   ~50/50, pure noise, not worth sims.
4. **Escalating sampler** per group (`_escalating`): run seeds in batches, stop when the
   standard error of the mean is tight or the ceiling is hit.
   - `START_SEEDS=8`, `BATCH_SEEDS=8`, `MAX_SEEDS=40`, `SE_TARGET=4.0` (95% CI ≈ ±8).
   - For 177723: ~460k matchups settled at 8 seeds (decisive); ~31k escalated to 16–40
     (the contested ~6%).
5. **Verdict** (`verdict_of`): `tossup` if `|mean| ≤ BAND (10)` **or** `SD > |mean|`
   (a genuine coin-flip — more sims won't make it definitive); else `win`/`loss` by sign.
6. **Expand** each group's result back to all member matchups (flipping the outcome for
   mirror members) and write rows.

### Robustness (for long unattended runs)

- **Resumable**: completed groups are recorded in `groups_done`; re-running skips them.
- **Per-worker error isolation**: a sim that raises is caught and the group is marked
  done with `n=0` (skipped) instead of killing the whole pool.
- **PyPy SQLite**: the output connection uses `isolation_level=None` (autocommit) to
  avoid PyPy's "cannot commit — SQL statements in progress" error.

## Output — `D:/AI/matchup_baseline_177723.db`

The build-177723 **baseline-of-record** (276 MB — kept local, **not committed**, same as
`matchup_db.db`). Three tables:

| Table            | Contents |
|------------------|----------|
| `matchup_battles`| Full averaged `BattleOutcome` per matchup (same schema as `matchup_db`, so the derive scripts read it unchanged) + `runs_count` (n), `score_stddev`. |
| `matchup_means`  | `(my_civ, my_slug, opp_civ, opp_slug, scale)` → `mean, sd, n, verdict`. The compact, queryable verdict table. |
| `groups_done`    | Resume checkpoint (dedup-group hash → n). |

**491,384 matchup rows** (= the 67,654 groups expanded). Verdict split: 47.8% win /
47.8% loss (exactly symmetric — a correctness check) / **4.4% (21,744) toss-ups**.

> **Mixed sim_version (2026-06-10):** after the Konnik dismount port, the 4,124 rows
> involving `elite_konnik_bulgarians` / `jian_swordsman_wu` were deleted and re-simmed on
> sim_version `e221c8a3a0437bd8`; the other 491,316 rows (proven outcome-identical under
> the new engine) stay on `f6ab0051d5cd4fff` — an intentional patchwork per
> `docs/patch-workflow.md` (derive with `--allow-stale`).

## Deriving the live site data from it

The deployed app reads `pool_scores.db`, `derived_data.db` (battle_scores), and
`civ_power_units/<build>.json` — NOT the matchup DB directly. Re-derive all three off the
baseline (regular python, build-versioned):

```
python3 -m webapp.derive_pool_scores  --matchup-db D:/AI/matchup_baseline_177723.db --out webapp/pool_scores.db --build 177723
python3 -m webapp.derive_unit_rankings --matchup-db D:/AI/matchup_baseline_177723.db --build 177723
python3 -c "import sys; sys.path.insert(0,'webapp'); import best_units; best_units.save_civ_power_units('177723')"
```

Old-vs-new diff for the 177723 re-derive: mean unit-rank move ≈ 4.6 (median 1). Big
movers split cleanly into **genuine corrections** that single-seed noise had hidden
(e.g. hand cannoneer vs halberdier #67→#1 — it wins ~100–0) and **near-tie reshuffles**
where the field is ~even (the matchups the toss-up verdict flags).

## Run management (unattended)

Two local helper scripts (at `D:/AI/`, machine-specific paths):

- **`baseline_runner.py`** — launches the builder and **auto-resumes** it on any death
  (native crash, worker segfault, external kill); gives up after 3 no-progress restarts.
  Coordinates with the watchdog via a `STOP` flag and writes a `DONE` flag when finished.
  *(Lesson: a detect-and-stop monitor is not enough — a crashed run sits idle. You need
  auto-restart.)*
- **`baseline_watchdog.py`** — every 15 min logs progress/CPU/RAM to
  `baseline_watchdog.log` (+ snapshot to `baseline_status.txt`) and **stops the run** on:
  error in the run log, runaway RAM (>16 GB), or no progress for 2 checks. Writes `STOP`
  so the runner doesn't restart.

CPU/thermal: **12 workers = physical core count** ≈ 58–66% CPU — the thermal-safe sweet
spot for CPU-bound sims (HT beyond 12 adds heat, not throughput). True core temp is not
readable here (MSAcpi access-denied, no LibreHardwareMonitor); the worker cap is the
thermal safeguard. Full run ≈ 4.5 h on a Ryzen 9 9900X.

> GPU note: not usable. The engine is branchy, sequential, object-oriented Python; a GPU
> would need a full vectorized/CUDA rewrite of every ability + re-validation. Out of scope.

## Prerequisites established this session

The baseline is only trustworthy because two earlier fixes landed first:

- **Phantom-unit fix** — the availability model is a *blocklist* (a civ has a unit unless
  its make-avail tech is disabled); the 177723 `.dat` doesn't disable ~9 "allowlist" unit
  lines, so every civ wrongly got them (776 phantom rows). Fixed with authoritative
  `civ_only` overrides in `analysis/config_units.py` (`_AVAILABILITY_OVERRIDES`), sourced
  from SiegeEngineers per-civ availability verified per upgrade-tier.
- **Imperial-only** — the app deals only with fully-upgraded Imperial units; the baseline
  enumerates Imperial units, with each civ's actual top tier (e.g. Koreans knight line =
  Cavalier, Persians = Savar) resolved via `webapp/top_units.py` / `civ_top_units.json`.

## Open item

The **≈ Even badge** UI: surface the `tossup` verdict in the Matchup Advisor (bucket
toss-ups into an "≈ Even" row instead of Beats/Loses, in `best_units.get_matchup_sims`).
The data is ready (`matchup_means.verdict`); this is a frontend + classification pass.
