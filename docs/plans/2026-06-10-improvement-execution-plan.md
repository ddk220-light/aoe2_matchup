# Improvement Execution Plan — 2026-06-10

Executes phases 1–2 of [docs/architecture/improvements.md](../architecture/improvements.md)
(owner-approved), under three owner constraints:

1. **Generated art is never deleted.** `graphics/art/` (FLUX.2 renders, future UI icons)
   and the sprite upscales are untracked from git but kept on disk.
2. **Nothing that requires re-simulating the matchup baseline.** No byte changes to
   `webapp/simulation_real.py` or `analysis/config_combat.py` (sim_version hash), no
   reference-DB regeneration, no batch sim runs. Items needing them are **deferred**
   (recorded below and in improvements.md).
3. **`scenario_builder/` is untouched** — `feat/matchup-video-automation` (active branch,
   touches only `scenario_builder/auto/**`) owns that tree. No path overlap with this plan,
   so it merges cleanly.

Baseline at start: 252 passed, **2 failed** (golden: Aztecs_vs_Armenians, Spanish_vs_Berbers
— 177723 data shipped without a baseline regen). The suite goes fully green at step W3.

## Steps (sequential, one commit each)

| # | Step | Files | Verification |
|---|------|-------|--------------|
| P1 | Untrack `graphics/art/` + 488 upscale PNGs; archive `derive_advisor_recs.py`, its test, `armenians_matchups.csv` → `.old/`; this plan doc | .gitignore, operations.md, .old/ | files on disk, `git ls-files` |
| W1 | Phase-2 deletions: `ORIGINAL_13_CIVS` (app.py dead copy; analysis copy derived from `CIV_NAMES`), `simulate_mixed_battle` (~860 lines), `NO_ELITE_UNITS` + `UNITS_BY_AGE`/`AGE_NAMES`, `battle_scores.json` stub + loader + `-999` branch | app.py, simulation.py, generate_main_db.py, config_units.py, config_constants.py, CLAUDE.md, docs | equality assert on civ list, grep zero refs, pytest (2 known golden fails only) |
| W2 | Template renames (`index→rankings`, `civ_detail→civ_overview`, `deprecated-civ→civ_detail`) + "all 50 civilizations"→53 SEO copy | templates/, app.py render_template lines, webapp.md, runbooks.md | grep, boot app, hit pages |
| W3 | Seed advisor RNG (`get_matchup_sims`/`get_matchup_recommendations`, seed 20260411); cost-weight fix (wood 0.8→0.7 via `simulation_real.weighted_cost`); regenerate `.golden/baseline.json` | best_units.py, .golden/baseline.json | **pytest fully green from here** |
| W4 | Derive-script guardrails: `--matchup-db` required + sim_version/sanity staleness check; remove legacy `civ_power_units.json` fallback | derive_unit_rankings.py, derive_pool_scores.py, derive_siege_scores.py, best_units.py | pytest, --help smoke |
| W5 | Backfill `patch_unit_ranking` for build 177723; VACUUM patches.db | patches.db (committed) | test_patch_routes, /patches page |
| W6 | Docstring + `Role:` tag pass (SKIP simulation_real.py/config_combat.py); stale-text fixes (CLASSIFIER_REWORK refs, clip 8x→4x, unit_lines 26 keys, capture_baseline, replay_core Blueprint, compute_battle_scores RETIRED banner); replay smalls: REPLAY_ENABLED nav gating, clip tmp-name collision, MAX_CONTENT_LENGTH | webapp/*.py docstrings, static/js headers, base.html, clip_export.py, app.py | pytest + node tests |
| W7 | Create `webapp/static/img/favicon.png` + `og-default.png` (referenced by base.html, currently 404) | static/img | local fetch 200 |
| P2 | CI: GitHub Actions (pytest + the two Node tests) — added once suite is green; mark done/deferred items in improvements.md | .github/workflows/ci.yml, improvements.md | CI run on push |

## Deferred — recorded, do later

**Completed 2026-06-10 (second pass — these only needed *missing rows*, not a full re-sim):**
Cumans Camel Rider / Dravidians Battle Elephant restored (`29a7525` config + surgical ref rows;
scoped baseline re-sim of 1,040 pending groups / 4,056 rows in 8.5 min via
`rebuild_matchup_baseline`'s `groups_done` resume — same escalating sampler as the baseline,
`sim_version` unchanged) and `pool_scores_lib` wood 0.7 alignment + full re-derive (`b9d2735`,
naval rows preserved byte-identically). Baseline now 495,440 rows / 517 units; pre-change
backup at `D:/AI/matchup_baseline_177723_pre_cumans.db`.

| Item | Why deferred |
|---|---|
| Engine renames (`sim_abstract`/`sim_position`) + `simulation_real.py` docstring | Any byte change re-stales 491k baseline rows — bundle with the next forced full re-sim (next game patch) |
| Port dismount (Konnik second life) to the position engine + simulate.js | Both lack the mechanic entirely (abstract-only today) — discovered 2026-06-10 during the form-stat fix; implementing it is a `simulation_real.py` change → full re-sim; bundle with the next window. Until then the matchup table undervalues Konnik |
| Delete the now-dead hand-copied dismount/transform values from `config_combat.py` | Values are overridden by generation-time derivation (commit `bcdbcbc`) but the file is sim_version-hashed — delete in the same bundled window |
| Naval rankings regeneration script | Baseline has no naval rows; needs naval sims |
| Incremental-resim noise (multi-seed degradation) | Sim-pipeline policy change; design alongside next patch run |
| `scenario_builder/overlay/results.py` port off `aoe2_units.db` (+ stage-3 retirement chain) | `scenario_builder/` owned by `feat/matchup-video-automation`; revisit after merge |
| `best_units.py` split, scoring-lib extraction from `compute_battle_scores.py`, `webapp/jobs/` subpackage | Phase 3 optional restructure |
| Emblem-CDN fallback, fallback-build '170934' centralization | Low value-for-risk right now |
