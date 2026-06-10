# Derived Data — Everything Computed from Sim Outcomes

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This document maps the layer that sits **after** the battle simulators: the raw matchup
outcome store, the derive scripts that turn raw outcomes into the tables and JSON the
deployed site actually reads, and the build-number versioning / patch machinery that keeps
those artifacts consistent across game patches.

Neighboring subsystems: the `.dat` → `aoe2_reference.db` → `aoe2_units.db` pipeline is in
[data-pipeline.md](data-pipeline.md); the engines that produce the outcomes
(`webapp/simulation.py`, `webapp/simulation_real.py`) are in
[simulation-engines.md](simulation-engines.md); the routes that serve the derived data are
in [webapp.md](webapp.md). Two procedure docs are linked rather than duplicated here:
[docs/matchup-baseline.md](../matchup-baseline.md) (how the 491k-row baseline was built and
operated) and [docs/patch-workflow.md](../patch-workflow.md) (the end-to-end patch checklist).

## The big picture

```
simulation_real.py (position-based engine, seeded, non-deterministic across seeds)
        │
        ▼
matchup_battles table  ←─ run_matchup_battles.py (incremental) / rebuild_matchup_baseline.py (full)
  (webapp/matchup_db.db committed stub · D:/AI/matchup_baseline_177723.db = real baseline)
        │
        ├─ derive_unit_rankings.py ──► derived_data.db · battle_scores      ─┐
        ├─ derive_pool_scores.py   ──► pool_scores.db  · pool_scores        ─┤
        ├─ derive_advisor_recs.py  ──► derived_data.db · advisor_recommendations (unread)
        ├─ derive_siege_scores.py  ──► derived_data.db · battle_scores (siege rows)
        └─ best_units.save_civ_power_units() ──► civ_power_units/<build>.json ─┘
                                                                              │
                       patches.db (build registry, is_current) ◄── patch_pipeline.py
                                                                              │
                                                              webapp/app.py reads these
```

The webapp never queries a matchup DB at serve time. Everything it shows comes from
`derived_data.db`, `pool_scores.db`, `patches.db`, `civ_power_units/<build>.json`, and
`civ_top_units.json` — all committed to git, which is how both Railway environments get
their data.

## 1. The raw outcome store: `matchup_battles`

Schema lives in `webapp/matchup_db.py`. One row per
`(my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale)` (UNIQUE constraint; upsert on
conflict). 41 columns:

| Group | Columns |
|---|---|
| Identity | `id`, `my_civ`, `my_unit_slug`, `opp_civ`, `opp_unit_slug`, `scale` (`'30v30'` or `'3k'`), `my_count`, `opp_count` |
| Unit costs | `my_cost_{food,wood,gold}`, `opp_cost_{food,wood,gold}` |
| Result | `winner` (0 tie / 1 / 2), `end_reason`, `game_time_s` |
| Per-team outcome | `team{1,2}_hp_pct`, `_survivors`, `_{food,wood,gold}_lost`, `_{food,wood,gold}_gained`, `_value_lost`, `team{1,2}_start_count` |
| Provenance | `runs_count` (seeds averaged), `score_stddev`, `dedup_group`, `sim_version` |

Two provenance mechanisms matter everywhere downstream:

- **`sim_version`** (`webapp/sim_version.py`) — 16-hex SHA-256 prefix of
  `webapp/simulation_real.py` + `analysis/config_combat.py` concatenated. Rows stamped with
  a stale version are re-simulated on the next batch run; current-version rows are skipped.
- **`dedup_group`** — 16-hex MD5 of the dedup-group key. Units with identical
  simulation-relevant stats get the same fingerprint
  (`webapp/sim_outcome_cache.py` `unit_fingerprint()`: rounded final stats, costs,
  `outline_size`, bonus-damage table, armors, special properties), so e.g. 20 civs' generic
  Halberdier collapse into one sim whose result is copied to every member row. Downstream
  consumers that average scores collapse by `dedup_group` first so stat-clones do not get
  double-weighted.

### `run_matchup_battles.py` — the incremental batch runner

`pypy3 -m webapp.run_matchup_battles [--db <path>] [--civs ...] [--my-civs ...]
[--changed-units <slugs.json>] [--force] [--reset] [--workers N]` (refuses to run on
CPython — PyPy 3 is a hard requirement).

What it does, in order:

1. Enumerates every Imperial-age `(civ, unit)` in `aoe2_reference.db` whose slug maps into
   the 13 `RANKED_LINES` (militia, spear, shock_infantry, skirmisher, archer, cav_archer,
   gunpowder, scorpion, light_cav, knight, camel, steppe_lancer, elephant), skipping
   `CIV_MISSING_UNITS`.
2. Builds all pairs with **mirror symmetry**: A-vs-B is simulated once; the B-vs-A row is
   the team-flipped copy (`_flip_outcome`). Mirror dedup only applies when both sides are
   "my-side eligible" (relevant with `--my-civs`).
3. Groups pairs by **fingerprint dedup**: key = (sorted fingerprint pair, scale). One sim
   per group; the result is inserted for every member, flipping when the member's my-side
   fingerprint differs from the representative's.
4. Skips groups whose every member already has a row at the current `sim_version`
   (`--force` bypasses this — needed after a stat-only patch, where unit stats changed but
   the sim source hash did not).
5. `--changed-units` restricts work to pairs where at least one side's slug is in the JSON
   list — the incremental path used by `patch_pipeline.py`.
6. Seeds: runs seed 0; if `|signed_score| <= 5.0` (a close match) it re-runs seeds 1 and 2
   and stores the average with `runs_count=3` and `score_stddev`; otherwise `runs_count=1`.

### `rebuild_matchup_baseline.py` — the full multi-seed baseline builder

This is what produced the 491k-matchup baseline; methodology and run-management details are
in [docs/matchup-baseline.md](../matchup-baseline.md). Architecturally: it reuses
`run_matchup_battles`' enumeration, fingerprint dedup, and mirror flip, but **excludes
same-unit mirrors** (`my_slug == opp_slug`) and replaces the 1-or-3-seed rule with an
**escalating sampler** (`START_SEEDS=8`, batches of 8, `MAX_SEEDS=40`, stop when
`SD/sqrt(n) < 4.0`). It writes two extra tables alongside `matchup_battles`:

- `matchup_means(my_civ, my_slug, opp_civ, opp_slug, scale) -> mean, sd, n, verdict, dedup_group`
  — `verdict` is `tossup` when `|mean| <= 10` or `SD > |mean|`, else `win`/`loss` by sign.
- `groups_done(dg, scale, n)` — resume checkpoint; re-running skips completed groups.

### Committed stub vs. external baseline (verified 2026-06-09)

| File | Size | Tables | Contents |
|---|---|---|---|
| `webapp/matchup_db.db` (committed) | 3.9 MB | `matchup_battles` only | **10,340 rows, my-side = Armenians only** (10 units × 517 opponents × 2 scales), single `sim_version`, `runs_count` 1 (10,146 rows) or 3 (194). A leftover snapshot from the per-civ batching era (commit `b9685ab` "snapshot matchup_db + derived_data after Armenian batch"). Nothing in the app reads it; derive scripts only hit it if you forget `--matchup-db`. |
| `D:/AI/matchup_baseline_177723.db` (local, NOT in git) | 276 MB | `matchup_battles`, `matchup_means`, `groups_done` | The build-177723 **baseline-of-record**: 491,384 rows in both battle and means tables, 67,654 dedup groups. Verdicts: 234,820 win / 234,820 loss (exactly symmetric) / 21,744 tossup (4.4%). Seed counts: 460,376 rows at n=8 escalating up to 1,726 at n=40. |

Practical consequence: **every derive command below must be pointed at the external
baseline** (`--matchup-db D:/AI/matchup_baseline_177723.db`). The flag is now **required**
(no default pointing at the stub), and both `derive_unit_rankings.py` and
`derive_pool_scores.py` run `matchup_db.preflight_derive_guard` before writing: a source DB
with <40 distinct `my_civ` values aborts (it looks like the Armenians-only stub; override
with `--allow-small-db`), and rows simmed under a non-current `sim_version` abort unless
`--allow-stale` (legitimate after scoped `--changed-units` re-sims — `patch_pipeline`
passes it). Guards live at the CLI layer only; the library functions stay unguarded for
tests. (`derive_advisor_recs.py`, which had no flag at all, is archived in `.old/webapp/`.)

## 2. The derive chain

| Script | Reads | Writes | Rerun command (from repo root) |
|---|---|---|---|
| `webapp/derive_unit_rankings.py` | `matchup_battles` (yardstick rows only) + `ref_units` | `derived_data.db` · `battle_scores` (land lines) | `python -m webapp.derive_unit_rankings --matchup-db D:/AI/matchup_baseline_177723.db --build 177723` |
| `webapp/derive_pool_scores.py` (+ `pool_scores_lib.py`) | `matchup_battles` (all rows) | `pool_scores.db` · `pool_scores` | `python -m webapp.derive_pool_scores --matchup-db D:/AI/matchup_baseline_177723.db --out webapp/pool_scores.db --build 177723` |
| `webapp/derive_advisor_recs.py` — **archived to `.old/webapp/`** (output read by nothing; no `--matchup-db` flag) | `webapp/matchup_db.db` (path not overridable) | `derived_data.db` · `advisor_recommendations` (rows kept, table DDL parked) | n/a — do not run |
| `webapp/derive_siege_scores.py` | `compute_battle_scores.compute_siege_antibuilding_scores()` (fresh sims, not matchup_db) | `derived_data.db` · `battle_scores` (siege lines) | `python -m webapp.derive_siege_scores --build 177723` |
| `webapp/best_units.py` `save_civ_power_units()` | `derived_data.db` + `pool_scores.db` + `ref_units` | `webapp/civ_power_units/<build>.json` | `python -c "import sys; sys.path.insert(0,'webapp'); import best_units; best_units.save_civ_power_units('177723')"` |
| `webapp/top_units.py` | `ref_units` only (no sim data) | `webapp/civ_top_units.json` | `python -m webapp.top_units` |

### `derive_unit_rankings.py` → `battle_scores`

Filters `matchup_battles` to rows whose **opponent is one of six yardstick units**: Vikings
Champion, Franks Paladin, Britons Arbalester, Britons Halberdier, Britons Imperial Elite
Skirmisher, Magyars Hussar. Each yardstick feeds one or two roles (`general_combat`,
`anti_cav`, `anti_archer`, `anti_trash`); per-role scores are the mean signed HP score
(`100 × (winner_hp% − loser_hp%)`, sign from my side) across yardsticks and scales,
then **min-max normalized to 0–100 within each pool** (infantry/ranged/stable). Composites:
`militia_value` (0.75 gc / 0.10 ac / 0.15 at), `ranged_effectiveness` (0.70 gc / 0.30 aa,
multiplied by speed × (range+1) before normalization), `stable_effectiveness`
(0.70 gc / 0.30 ac, multiplied by speed). Per-yardstick sub-scores are also written, both
normalized (`gc_30v30_vs_champ`) and raw (`..._raw`). Writes one `battle_scores` row per
(line, age, civ, unit, score_type, build), with `rank` and `median_delta` computed within
each (line, score_type), deleting that build's prior rows first (including rows for the
same unit under a different line classification).

`derived_data.db` current state: 51,187 `battle_scores` rows (24,187 @ build 170934,
27,000 @ 177723), 62 distinct `score_type`s, ages `imperial` and `castle`, 20 line_slugs.

### `derive_pool_scores.py` + `pool_scores_lib.py` → `pool_scores`

The rankings-page scoring engine. For every (civ, unit) in `matchup_battles` that maps into
one of three pools — `infantry` (Barracks), `stable` (Stable), `archer` (Archery Range,
plus the scorpion line via `LINE_POOL_OVERRIDE`) — it writes **6 rows: 3 axes × 2 scales**:

- **hp axis**: signed HP score with **loss aversion** (`apply_loss_aversion`: negatives
  multiplied by λ=2.0).
- **cost axis**: weighted resources (`0.8·wood + food + 1.5·gold`); win → my spent value;
  loss → λ × (my spent + opponent remaining); tie → no λ. Higher = worse.
- **speed axis**: `±100 × max(0, 1 − t/120s)`, loss side scaled by λ.

Per row, opponents are bucketed into roles per `POOL_ROLES` (an opponent line may count in
multiple roles), values are collapsed by `dedup_group` (first-wins), averaged per line, per
role, then combined with `POOL_WEIGHTS` (GC 0.70 everywhere; AC/AT/AA make up the rest).
Each row also carries distribution "shape" descriptors over raw HP scores (`win_rate`,
`decisive_win_rate`, `big_win_rate`, `catastrophic_loss_rate`, `n`, `mean`, `stddev`) and a
JSON `role_line_means` breakdown. Table: 21 columns, PK
`(civ_name, unit_slug, scale, axis, build_number)`. Current state: 5,844 rows
(2,754 @ 170934, 3,090 @ 177723).

**Percentile-within-line** is *not* stored in `pool_scores`; it is computed at
civ-power-units derive time by `best_units._load_pool_score_percentiles()`: average the
`hp`-axis `final_score` across both scales per unit, rank **within the unit's line** (not
the whole pool, so a strong cav-archer is not drowned by stacked arbalester variants), and
emit percentile 0–100. `_classify_strength()` then maps percentile to
signature (≥90) / strong (≥65) / average (≥35) / weak (≥15) / poor.

The webapp reads `pool_scores` via `webapp/pool_scores_query.py` `load_pool_scores()`
(attached to `/api/ref/unit-line/<line>` responses, filtered by current build).

### `derive_advisor_recs.py` → `advisor_recommendations`

For each (my_civ, opp_civ) pair, ranks my units by mean signed score against **all** of the
opponent civ's units across both scales, and writes the top 2 as `rec_type='top'`. The
table (in `derived_data.db`, 5,618 rows) has **no `build_number` column** and — verified by
grep — **nothing in `webapp/app.py` or any template reads it**; only
`tests/test_advisor_derive.py` exercises it. The live Matchup Advisor instead runs on-the-fly
sims (`best_units.get_matchup_recommendations` / `get_matchup_sims`, fed by
`civ_power_units/<build>.json`). Treat this table as parked output awaiting a consumer.

### `derive_siege_scores.py` → siege rows in `battle_scores`

Siege/anti-building scores cannot come from `matchup_battles` (no buildings there). This
script calls `compute_battle_scores.compute_siege_antibuilding_scores()` directly (fresh
sims vs. castle/building targets), deletes the target build's siege-line rows in
`derived_data.db`, inserts the aggregate `anti_building_score` **and** the per-castle
`ab_<castle>_<mode>_{ttk,dmg}` breakdown rows, then recomputes rank/median_delta. It exists
because carry-forward alone propagated only the aggregate, breaking the rankings hover
breakdown. Naval rows (`naval_effectiveness`, `vs_galleon`, …) have **no** equivalent
standing derive script into `derived_data.db` — they survive via carry-forward only.

### `best_units.py` → `civ_power_units/<build>.json`

`compute_civ_power_units()` joins `battle_scores` (per line/score_type/build) with pool-score
percentiles and ref stats into a per-civ, per-age "power units" payload (strength profile,
strategic summary, per-line entries). `save_civ_power_units(build)` writes
`webapp/civ_power_units/<build>.json` (~1.8 MB each; `170934.json` and `177723.json` are
committed). `load_civ_power_units()` resolves the current build via `patches.db` and loads
the per-build file **only** — the legacy flat `webapp/civ_power_units.json` (a frozen
170934 snapshot) and its silent fallback were removed; a missing per-build file now logs an
ERROR and returns None (the API surfaces a 500). Consumed by
`/api/civ-power-units/<civ>` and the Matchup Advisor sim helpers.

### `top_units.py` → `civ_top_units.json`

Not sim-derived (input is `ref_units` + `UNIT_LINES` only) but lives in this layer: resolves
each civ's actual highest Imperial tier per line (Koreans knight → Cavalier, Persians →
Savar). Read by `/api/top-units/<civ>` and `/api/top-unit/<civ>/<line>` via `load_top_units()`.

`webapp/unit_lines.py` is the single Python source of the `UNIT_LINES` registry that every
script above imports (a parallel JS copy exists in `webapp/static/js/rankings.js`).

## 3. Build-number versioning

| Table / artifact | Build column | Notes |
|---|---|---|
| `derived_data.db` · `battle_scores` | `build_number` (TEXT, default `'170934'`), part of the UNIQUE key | All app queries filter by current build when one resolves |
| `pool_scores.db` · `pool_scores` | `build_number`, part of the PK | Same |
| `civ_power_units/` | encoded in the **filename** `<build>.json` | Per-build file only — the legacy flat `civ_power_units.json` fallback was deleted |
| `derived_data.db` · `advisor_recommendations` | **none** | Not yet versioned |
| `matchup_battles` | none — versioned by `sim_version`, not build | The baseline file itself is named per build |

**`is_current`**: `patches.db` `patches` has one row per game build; exactly one row carries
`is_current=1`. `patches_db.get_current_build()` is the single resolver every consumer goes
through (app routes, all derive scripts default their `--build` to it, falling back to the
literal `'170934'` if `patches.db` is absent). `set_current_build()` zeroes the flag on all
rows then sets it on one; the resolver also falls back to the newest `release_date` row if
no flag is set.

**Carry-forward on a new patch**: `patch_pipeline.carry_forward_battle_scores(old, new)`
copies every old-build `battle_scores` row to the new build (INSERT OR REPLACE) **before**
re-derivation, so the new build is a complete snapshot — the land rows get overwritten by
`derive_unit_rankings`, while naval/siege rows (not produced by that script) survive.
Siege rows should then be properly regenerated with `derive_siege_scores.py`.

**`migrate_baseline.py`** was the one-time migration that introduced all of this: it rebuilt
`battle_scores` and `pool_scores` tables to add `build_number` (a full table rebuild, since
the PK changes), tagged existing rows `170934`, copied `civ_power_units.json` →
`civ_power_units/170934.json` (the flat file has since been deleted from the repo), and
seeded the first `patches` row with `is_current=1`.
It is idempotent and is still the documented bootstrap if `patches.db` is missing
(`patch_pipeline` exits with instructions to run it).

## 4. `patches.db` and the patch pipeline

Schema (`webapp/patches_db.py`):

| Table | Columns | Current rows |
|---|---|---|
| `patches` | `id, build_number (UNIQUE), release_date, title, summary_md, source_url, baseline_build, is_current, created_at` | 2 (170934; 177723 with `baseline_build=170934`, `is_current=1`) |
| `patch_unit_changes` | `patch_id, civ_name, unit_slug, field, old_value, new_value, note` | 19 |
| `patch_unit_ranking` | `patch_id, civ_name, unit_slug, score_type, old_score, new_score, old_rank, new_rank` | 0 |
| `patch_matchup_changes` | `patch_id, my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, old_winner, new_winner, old_score, new_score, swing` | 346 |

Read by the `/patches` page and `/patches/<build>/<civ>/<unit>` per-unit pages (stat deltas,
ranking moves, "now beats / now loses / shifted" matchup buckets, cross-patch timeline).

**`patch_pipeline.py`** — run once per patch
(`python -m webapp.patch_pipeline --build <b> --release-date <d> --source-url <u>
--summary-file <md> --pypy <pypy3> --matchup-db <path>`). Architecturally it chains six
phases:

- **Archive** — snapshot the previous extraction output and `aoe2_reference.db` as the
  untracked "before" copies.
- **Extract/rebuild** — re-run stages 1–3 on the new `.dat` and re-apply the surgical
  `analysis/patches/` scripts.
- **Diff** — `ref_diff.py` (stat deltas → `changed_units_<build>.json`) and
  `matchup_diff.snapshot()` (the "before" outcomes for changed slugs).
- **Re-sim** — incremental `run_matchup_battles --force --changed-units`, then
  `matchup_diff.diff_outcomes()` for winner flips / score swings.
- **Derive** — carry forward prior-build `battle_scores`, re-run rankings + pool scores at
  the new build, insert the `patches` row, flip `is_current`, regenerate
  `civ_power_units/<build>.json` (ordering matters: the power-units step reads the current
  build, so the patches row lands mid-phase).
- **Record** — `matchup_diff.diff_rankings()` → `patch_unit_ranking`; write all patch record
  sets into `patches.db` (idempotent — prior records for the patch are deleted first).

The verbatim operational checklist (exact commands, flags, manual head/tail steps) is
[runbooks.md](runbooks.md) §1, which stays canonical.

Note the pipeline does **not** run `derive_siege_scores.py` or `derive_advisor_recs.py`;
[docs/patch-workflow.md](../patch-workflow.md) is the authoritative checklist around it.

Two standalone verification tools (both PyPy-only) support patch analysis outside the
pipeline:

- **`patch_resim.py`** — stable multi-seed means for a small "my-units" set against the full
  opponent pool, into a separate `matchup_means` DB. Adaptive: 1 sim if seed 0 is a blowout
  (|score| > 50), else 5 seeds, escalating to `--seeds` (default 15) only if the 5 disagree
  on the winner. Run once per reference DB (old and new), then diff.
- **`verify_flips.py`** — adversarial re-check of candidate flips from two `patch_resim`
  outputs. Exists because the agreement-based stopping rule biases |mean| high on
  high-variance matchups, fabricating swings. It takes candidates with raw |swing| ≥ 10,
  drops same-line mirrors, dedups by (my unit, scale, old+new opponent fingerprints), and
  runs a **matched escalating sampler** on both reference DBs simultaneously (12-seed
  batches up to 72, stop when SE < 3.5) → `verified_means`.

## 5. Legacy artifacts (verified status)

| Artifact | Status |
|---|---|
| `webapp/battle_scores.json` | **Deleted** (2026-06-10) along with its `app.py` startup loader and the `-999`-sentinel `else` branch of `_attach_scores()` in `/api/ref/unit-line`. The branch was unreachable (every real line in `UNIT_LINES` is inside the infantry/archery/stable/siege/naval score sets), and `rankings.js` treats missing score keys the same as the old sentinels. Role scores come solely from `derived_data.db`. |
| `webapp/compute_battle_scores.py` (committed) | Dead as a pipeline, alive as a library. Its `main()` writes role scores to the `battle_scores` table in **`aoe2_reference.db`** — which currently has **0 rows** and is only read as a last-resort fallback when `derived_data.db` returns nothing — plus a `battle_scores.json` that nothing loads anymore. But `derive_siege_scores.py` imports `compute_siege_antibuilding_scores()` and `SIEGE_LINE_SLUGS` from it, so the module cannot be deleted without extracting those. Do **not** run its `main()` as part of any current workflow. |
| `webapp/battle_cache.json` (1 KB, gitignored) | Sim-result cache used only by `compute_battle_scores.main()`. Dead weight while that script is retired. |

## 6. Committed vs. local artifacts (git ls-files is ground truth)

The full committed inventory (every DB/JSON the deployed app ships with) lives in
[operations.md](operations.md) §2. Listed here are only the local-only artifacts specific to
this layer:

| Artifact | In git? | Role |
|---|---|---|
| `D:/AI/matchup_baseline_177723.db` (276 MB) | no | baseline-of-record; input to all derives |
| `webapp/aoe2_reference_prev.db`, `webapp/aoe2_reference_177723.db`, `webapp/aoe2_reference_170934_clean.db` | no (untracked) | before-snapshots for diffing |
| `webapp/derived_data.db.bak`, `webapp/pool_scores.db.bak` | no (untracked) | manual backups |

## Update triggers

| If this changes… | …update these sections |
|---|---|
| `matchup_db.py` schema or `sim_version.py` inputs | §1 (schema table, provenance) |
| Sampler constants in `run_matchup_battles.py` / `rebuild_matchup_baseline.py` | §1 (seed rules, verdict thresholds) and [docs/matchup-baseline.md](../matchup-baseline.md) |
| A new full baseline is built (new build or sim change) | §1 committed-vs-baseline table, §6, and the verified row counts throughout |
| Yardsticks, roles, or composite weights in `derive_unit_rankings.py` | §2 rankings subsection |
| `pool_scores_lib.py` axes, λ, pools, or role weights | §2 pool-scores subsection |
| `advisor_recommendations` gains a consumer or a `build_number` column | §2 advisor subsection, §3 table |
| `patch_pipeline.py` steps or new supporting modules | §4 |
| A script starts/stops reading `battle_scores.json` or `compute_battle_scores.py` | §5 |
| Files added to / removed from git in `webapp/` (`git ls-files webapp/`) | §6 |
| A new `patches` row / `is_current` flip | §3, §4 current-rows column |
