# Architecture Overview

> Historical architecture (June 2026). Start with [Current website architecture](CURRENT.md)
> for the active V3 runtime, module ownership, crawler configuration and release gates.
> The engine/frontend ownership below describes the earlier implementation. Since
> 2026-11 the site is the Astro app `apps/web` plus the Flask API `apps/backend`
> on Vercel; the old `apps/website` Flask site is deleted and its browser client
> lives on as research code in `legacy/client/` (see [webapp.md](webapp.md)).

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This is the entry point for the architecture doc set. It gives the system map, the
master "single source of truth" table, and the invariants that hold everything
together. Each subsystem has its own deep-dive doc (index below), and
[runbooks.md](runbooks.md) is the operational companion: **when X changes, update Y**.

## What this is

A data-engineering pipeline disguised as a website ([aoe2matchup.com](https://aoe2matchup.com)).
Offline stages turn the game's binary `.dat` file into fully-upgraded per-civ unit
stats (56 civilizations in the simulation/rankings reference DBs; 53 in the older
`aoe2_reference.db`), two custom battle-sim engines turn those stats into
hundreds of thousands of pre-computed matchup outcomes, and an Astro site backed
by a Flask JSON API serves the results as five tools: battle simulator, unit
rankings, civ pages, matchup advisor and patch tracker (the replay analyzer is no
longer mounted). All serving data is committed SQLite/JSON —
**committing regenerated artifacts on a branch IS the deployment mechanism**
(Vercel builds `staging` → preview deployment, `main` → production).

## System diagram

```
                     empires2_x2_p1.dat  (game install; not in repo)
                              │  python -m aoe2x.extract.run        (genieutils-py)
                              ▼
              data/inputs/extracted_data/*.json  (8 files: units, technologies,
                              │   tech_ages, civilizations, armor_classes,
                              │   effects, tech_effects, civ_tech_trees)
                              │  python -m aoe2x.dbgen.generate_reference
                              │   (applies techs/civ bonuses/unique techs per civ;
                              │    + hardcoded layers in aoe2x/dbgen/config_combat.py)
                              ▼
   ┌────────────── data/golden/aoe2_reference.db  (ref_units + audit tables; committed)
   │                          │
   │ python -m analysis.      │  combat_unit_loader.build_combat_dict_from_ref()
   │   generate_main_db       │
   ▼                          ├────────────────────────────┐
data/golden/aoe2_units.db          │                            │
(unit_stats; legacy,          ▼                            ▼
 no app route reads it)   Flask API               batch sim runners (PyPy)
                          aoe2_api/web.py         run_matchup_battles.py
                          /api/ref/* routes
                              │                   rebuild_matchup_baseline.py
                              │                       │ engine: simulation_real.py
                              │                       │ (multi-seed, sim_version-stamped)
                              │                       ▼
                              │            D:/AI/matchup_baseline_<build>.db
                              │            (~494k matchups; local, NOT committed)
                              │                       │
                              │     ┌─────────────────┼──────────────────────┐
                              │     ▼                 ▼                      ▼
                              │  derive_unit_     derive_pool_         best_units.py
                              │  rankings.py      scores.py            save_civ_power_units
                              │     ▼                 ▼                      ▼
                              │  derived_data.db  pool_scores.db   civ_power_units/<build>.json
                              │     └─────────────────┴──────────────────────┘
                              │                  (committed, build-versioned)
                              ▼
            scripts/migration/prepare_release.py (build-time exports + page metadata)
              → Astro apps/web (pages, styles, src/features/*)
            (interactive battle sim runs CLIENT-SIDE in aoe2x/js_simulation/src/, V3)

  Side systems:
  • patches.db ← patch_pipeline.py (per-patch stat diffs, ranking deltas, matchup swings)
  • replay tooling is not mounted by aoe2matchup.com (legacy viewer code remains under aoe2x/replay)
  • apps/video/ (validates sims against the real game), graphics/ (sprites + FLUX.2 art)
```

### Retired frontend battle-sim engine (extracted 2026-07-28; now `legacy/client/`)

The live Battle Sim page runs the V3 engine `aoe2x/js_simulation/src/` in the
worker `apps/web/static/js/v3_sim_worker.js` (see [CURRENT.md](CURRENT.md)).
The earlier client engine is kept, unpublished, for parity, calibration and research:

| Path | One-liner |
|---|---|
| `legacy/client/js/engine/` | The retired frontend engine: pure ESM, DOM-free, deterministic — `rng.js` (seeded mulberry32), `constants.js`, `projectile.js`, `melee_effect.js`, `battle_unit.js`, `sim.js` (`Simulation` + `stateHash` + combat counters), `scenario.js` (`createSimulation`), `index.js` (public API). Runs unchanged under node. |
| `legacy/client/js/sim_renderer.js`, `legacy/client/js/simulate.js` | The old canvas renderer and Battle Sim page shell (no longer served). |
| `legacy/client/lab/sim_harness.html` + `.js` + `sim_worker.js` | The old diagnostic harness (presets, count modes, seed control, overlays, multi-seed scoreboard). No longer served by the site. |
| `tools/simjs/` | Engine tooling: `golden/` (205-fight parity panel + `panel.meta.json` provenance), `parity_check.mjs` (**the gate** — bit-exact replay, exit 0/1/2), `headless.mjs` (node engine runner), `parity_capture.mjs` + `legacy_harness.cjs` (one-off pre-extraction capture), `audit_panel.mjs`, `ability_coverage.py`, `dump_combat_dicts.py` (dumps the ref-DB combat dicts the runners feed the engine). |
| `tests/js/engine/*.test.mjs` | Node unit tests — `node --test tests/js/engine/`. |

**Standing rule:** any edit under `legacy/client/js/engine/` must re-run `node tools/simjs/parity_check.mjs`.
A behavior change is *supposed* to fail it — re-capture the golden panel and say why.

## Document index

| Doc | Covers |
|---|---|
| [data-pipeline.md](data-pipeline.md) | Stages 1–3: dat extraction, tech-effect application, armor/attack derivation, unit availability per civ, config override layers, DB schemas |
| [simulation-engines.md](simulation-engines.md) | The three sim implementations (abstract tick, position-based, frontend JS), damage formula, special abilities, who uses which engine |
| [derived-data.md](derived-data.md) | Matchup baseline, rankings/pool-scores/advisor derive chain, build-number versioning, patches.db |
| [webapp.md](webapp.md) | Astro frontend, Flask API routes, build-time exports, central registries, env vars, live sync rules |
| [replay.md](replay.md) | Replay analyzer: mgz parsing, unit classifier, playback SPA, clip export |
| [operations.md](operations.md) | Deployment (now Vercel — see [../vercel-deployment.md](../vercel-deployment.md)), git/data-shipping workflow, tests + golden baseline, scenario builder, graphics, reference corpus |
| [runbooks.md](runbooks.md) | **When X changes, update Y** — step-by-step checklists with exact commands |
| [data-model-review.md](data-model-review.md) | Deep critique of the stage 1–3 data model: derive-vs-store verdicts, availability resolver, ability registry, multi-form tech gap, migration plan |
| [../../simulation_v2/CHANGELIST.md](../../simulation_v2/CHANGELIST.md) | **Staged, not live:** the V2 engine — every fix/model change vs the engines that produced current data, affected units, and the full-rerun protocol |

Procedure deep-dives that predate this set and remain canonical:
[../patch-workflow.md](../patch-workflow.md) (end-to-end patch procedure) and
[../matchup-baseline.md](../matchup-baseline.md) (how the ~494k-matchup baseline was built).

## Single sources of truth

Where to look (and what to edit) for each kind of fact:

| Fact | Source of truth | Notes |
|---|---|---|
| Civ list (pipeline) | `CIV_NAMES` in `extraction/extract_constants.py` | 60 dat slots → 53 playable civs (Gaia + 6 Chronicles slots skipped) |
| Civ list (frontend) | `ENABLED_CIVS` in `apps/web/static/js/constants.js` ← `window.SITE_CATALOG.civilizations` | 56 entries from `site_catalog()` (`apps/backend/aoe2_api/services/catalog.py`) over `aoe2_reference_simulation.db`; server-side validation also derives from the reference DBs (`_valid_civs()` / `_sim_civs()` in `apps/backend/aoe2_api/web.py`) |
| Extractable units | `UNIT_NAMES` in `extraction/extract_units.py` | 256 dat unit ids; absent here = never enters the pipeline |
| Unit rosters & upgrade chains | `CASTLE_UNITS` / `IMPERIAL_UNITS` / `UNIQUE_UNITS` / `NAVAL_*` in `aoe2x/dbgen/config_units.py` | Slugs, base ids, availability techs, alternates, civ upgrades |
| Per-civ availability fixes | `_AVAILABILITY_OVERRIDES` in `aoe2x/dbgen/config_units.py` | Allowlist pinning 17 auto-enabled lines to explicit civ lists |
| Hardcoded combat properties | `COMBAT_PROPERTIES` / `UNIQUE_COMBAT_PROPERTIES` / `CIV_COMBAT_PROPERTIES` in `aoe2x/dbgen/config_combat.py` | 30/52/89 entries; later layer wins; hashed into `sim_version` |
| Base-stat dat corrections | `UNIT_STAT_OVERRIDES` in `aoe2x/dbgen/config_units.py` | 4 entries |
| Armor/attack classes | `ARMOR_CLASSES` in `extraction/extract_constants.py` | 40 classes; used by every per-class attack/armor list |
| Unit lines (Python) | `UNIT_LINES` + `CIV_MISSING_UNITS` in `aoe2x/sim/unit_lines.py` | Imported by 12 modules. ⚠ The live JS copy lives in `apps/web/src/features/rankings/render.mjs` — update both |
| Unit icons | `icon_names` (230) in `aoe2x/assets/presentation.json` → `NAME_TO_ICON` + `getIconUrl()` in `apps/web/static/js/constants.js` | Authoring PNGs in `data/media/img/units/` (served from Blob) |
| Unique-unit buildings | `unique_buildings` (13) in `aoe2x/assets/presentation.json` → `UNIQUE_BUILDING` in `apps/web/static/js/constants.js` | |
| Civ emblems | `CIV_EMBLEM_BASE` in `apps/web/static/js/constants.js` | aoe2companion CDN |
| Unit display names | `ref_units.unit_name` in `data/golden/aoe2_reference.db` | Per civ×slug×age (e.g. Koreans `paladin` → "Cavalier"); resolved by `_ref_unit_name()` |
| Combat-dict mapping | `build_combat_dict_from_ref()` in `aoe2x/sim/combat_unit_loader.py` | Shared by `aoe2_api/web.py`, best_units, batch runners; `aoe2x/dbgen/generate_main_db.py` has a same-named sibling that must stay in sync |
| Current build number | `patches_db.get_current_build()` (`data/golden/patches.db`, `is_current=1`) | Every build-versioned artifact keys off this |
| Sim cache key | `compute_sim_version()` in `aoe2x/sim/sim_version.py` | Hashes `simulation_real.py` + `aoe2x/dbgen/config_combat.py` — **not** `simulation.py` |
| Pool scoring spec | constants in `aoe2x/rank/pool_scores_lib.py` | λ=2 loss aversion, pool roles/weights |
| Battle scoring | `aoe2x/sim/battle_outcome.py` | `BattleOutcome`, `signed_score` (−100…+100), multi-seed aggregation |
| Resource cost weights | `weighted_cost` in `aoe2x/sim/simulation_real.py` | ⚠ duplicated in `compute_battle_scores.calc_weighted_cost`; `best_units._calc_weighted_cost` delegates to it (int floor on top); `pool_scores_lib.weighted_cost` intentionally frozen at wood ×0.8 (matches committed pool_scores.db) |
| Replay sprites | `aoe2x/replay/public/assets/sprites/sprites.json` | Shared by renderer.js and clip_export.py |
| Train times (classifier) | `aoe2x/replay/train_times.json` | Used by the replay unit classifier |

## Key invariants

1. **The app serves combat data from `aoe2_reference.db`**, not `aoe2_units.db`.
   `/api/ref/combat-unit/<civ>/<slug>` reads `ref_units` through
   `combat_unit_loader.build_combat_dict_from_ref()`. No route queries `unit_stats`.
2. **The interactive battle sim is client-side.** The page at `/` posts the
   selection to `/api/v3/battle-config` and runs the fight in the V3 engine
   (`aoe2x/js_simulation/src/`) inside a Web Worker. The Python engines never run
   during page sims.
3. **Three engines, three jobs.** `simulation.py` (abstract tick) backs
   `/api/matchup-sims`; `simulation_real.py` (position-based) backs all batch
   matchup data; the V3 JS engine backs the interactive page and node batch runs
   (the retired `legacy/client/js/engine/` backs only the parity panel and
   headless research tools). A mechanic change is
   incomplete until all three (plus `.golden/baseline.json`) agree — see
   [runbooks.md](runbooks.md) §2. Editing the legacy JS engine additionally requires the
   parity gate (`node tools/simjs/parity_check.mjs`).
4. **`sim_version` self-heals the matchup data.** Any edit to `simulation_real.py`
   or `aoe2x/dbgen/config_combat.py` changes the hash; stale rows are re-simmed on
   the next batch run.
5. **Everything user-visible is build-versioned.** Rankings, pool scores, and
   civ power units are keyed by `build_number`; `patches.db` decides which build
   is current.
6. **Determinism by seed.** Batch sims use explicit multi-seed sampling
   (escalating 8→40 seeds); golden tests pin `GOLDEN_SEED=20260411`.
7. **Committed data = deployed data.** Regenerate → commit on `staging` →
   smoke-test → fast-forward promote to `main`.

## When something changes

Go to [runbooks.md](runbooks.md). It has checklists for: a new game patch
(build numbers, re-extraction, re-sim, re-derive), sim logic changes, new combat
columns/abilities, new units/civs, new icons/art, frontend constant changes, and
surgical single-unit stat fixes.

## Update triggers

| If this changes | Update |
|---|---|
| Pipeline stage added/removed or artifact renamed | System diagram + document index |
| A registry moves files (e.g. constants split again) | Single-sources-of-truth table |
| Engine responsibilities shift (e.g. matchup-sims switches engine) | Key invariants §3 + [simulation-engines.md](simulation-engines.md) |
| New deployment mechanism | "What this is" + invariant §7 + [operations.md](operations.md) |
