# Architecture Overview

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This is the entry point for the architecture doc set. It gives the system map, the
master "single source of truth" table, and the invariants that hold everything
together. Each subsystem has its own deep-dive doc (index below), and
[runbooks.md](runbooks.md) is the operational companion: **when X changes, update Y**.

## What this is

A data-engineering pipeline disguised as a website ([aoe2matchup.com](https://aoe2matchup.com)).
Offline stages turn the game's binary `.dat` file into fully-upgraded per-civ unit
stats (53 civilizations), two custom battle-sim engines turn those stats into
hundreds of thousands of pre-computed matchup outcomes, and a Flask app serves the
results as six tools: battle simulator, unit rankings, civ pages, matchup advisor,
patch tracker, and a replay analyzer. All serving data is committed SQLite/JSON —
**committing regenerated artifacts on a branch IS the deployment mechanism**
(Railway auto-deploys `staging` → staging env, `main` → production).

## System diagram

```
                     empires2_x2_p1.dat  (game install; not in repo)
                              │  python -m extraction.run        (genieutils-py)
                              ▼
              extraction/extracted_data/*.json  (8 files: units, technologies,
                              │   tech_ages, civilizations, armor_classes,
                              │   effects, tech_effects, civ_tech_trees)
                              │  python -m analysis.generate_reference
                              │   (applies techs/civ bonuses/unique techs per civ;
                              │    + hardcoded layers in analysis/config_combat.py)
                              ▼
   ┌────────────── webapp/aoe2_reference.db  (ref_units + audit tables; committed)
   │                          │
   │ python -m analysis.      │  combat_unit_loader.build_combat_dict_from_ref()
   │   generate_main_db       │
   ▼                          ├────────────────────────────┐
webapp/aoe2_units.db          │                            │
(unit_stats; legacy,          ▼                            ▼
 no app route reads it)   Flask app.py            batch sim runners (PyPy)
                          /api/ref/* routes       run_matchup_battles.py
                              │                   rebuild_matchup_baseline.py
                              │                       │ engine: simulation_real.py
                              │                       │ (multi-seed, sim_version-stamped)
                              │                       ▼
                              │            D:/AI/matchup_baseline_<build>.db
                              │            (~491k matchups; local, NOT committed)
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
            templates/*.html + static/js/*.js + static/css/*.css
            (interactive battle sim runs CLIENT-SIDE in static/js/simulate.js)

  Side systems:
  • patches.db ← patch_pipeline.py (per-patch stat diffs, ranking deltas, matchup swings)
  • /replay/* ← replay_core.py blueprint (mgz parsing, isometric playback SPA, WebM clips)
  • scenario_builder/ (validates sims against the real game), graphics/ (sprites + FLUX.2 art)
```

## Document index

| Doc | Covers |
|---|---|
| [data-pipeline.md](data-pipeline.md) | Stages 1–3: dat extraction, tech-effect application, armor/attack derivation, unit availability per civ, config override layers, DB schemas |
| [simulation-engines.md](simulation-engines.md) | The three sim implementations (abstract tick, position-based, frontend JS), damage formula, special abilities, who uses which engine |
| [derived-data.md](derived-data.md) | Matchup baseline, rankings/pool-scores/advisor derive chain, build-number versioning, patches.db |
| [webapp.md](webapp.md) | Flask routes, templates, static assets, central registries, env vars, live sync rules |
| [replay.md](replay.md) | Replay analyzer: mgz parsing, unit classifier, playback SPA, clip export |
| [operations.md](operations.md) | Railway deployment, git/data-shipping workflow, tests + golden baseline, scenario builder, graphics, reference corpus |
| [runbooks.md](runbooks.md) | **When X changes, update Y** — step-by-step checklists with exact commands |
| [data-model-review.md](data-model-review.md) | Deep critique of the stage 1–3 data model: derive-vs-store verdicts, availability resolver, ability registry, multi-form tech gap, migration plan |

Procedure deep-dives that predate this set and remain canonical:
[../patch-workflow.md](../patch-workflow.md) (end-to-end patch procedure) and
[../matchup-baseline.md](../matchup-baseline.md) (how the 491k-matchup baseline was built).

## Single sources of truth

Where to look (and what to edit) for each kind of fact:

| Fact | Source of truth | Notes |
|---|---|---|
| Civ list (pipeline) | `CIV_NAMES` in `extraction/extract_constants.py` | 60 dat slots → 53 playable civs (Gaia + 6 Chronicles slots skipped) |
| Civ list (frontend) | `ENABLED_CIVS` in `webapp/static/js/constants.js` | 53 entries; server-side validation derives from `aoe2_reference.db` via `_valid_civs()` in `app.py` |
| Extractable units | `UNIT_NAMES` in `extraction/extract_units.py` | 256 dat unit ids; absent here = never enters the pipeline |
| Unit rosters & upgrade chains | `CASTLE_UNITS` / `IMPERIAL_UNITS` / `UNIQUE_UNITS` / `NAVAL_*` in `analysis/config_units.py` | Slugs, base ids, availability techs, alternates, civ upgrades |
| Per-civ availability fixes | `_AVAILABILITY_OVERRIDES` in `analysis/config_units.py` | Allowlist pinning 17 auto-enabled lines to explicit civ lists |
| Hardcoded combat properties | `COMBAT_PROPERTIES` / `UNIQUE_COMBAT_PROPERTIES` / `CIV_COMBAT_PROPERTIES` in `analysis/config_combat.py` | 30/52/89 entries; later layer wins; hashed into `sim_version` |
| Base-stat dat corrections | `UNIT_STAT_OVERRIDES` in `analysis/config_units.py` | 4 entries |
| Armor/attack classes | `ARMOR_CLASSES` in `extraction/extract_constants.py` | 40 classes; used by every per-class attack/armor list |
| Unit lines (Python) | `UNIT_LINES` + `CIV_MISSING_UNITS` in `webapp/unit_lines.py` | Imported by 8 modules. ⚠ A JS copy lives in `static/js/rankings.js` — update both |
| Unit icons | `NAME_TO_ICON` (218) + `getIconUrl()` in `webapp/static/js/constants.js` | PNGs in `webapp/static/img/units/`; no template copies exist anymore |
| Unique-unit buildings | `UNIQUE_BUILDING` (13) in `webapp/static/js/constants.js` | |
| Civ emblems | `CIV_EMBLEM_BASE` in `webapp/static/js/constants.js` | aoe2companion CDN |
| Unit display names | `ref_units.unit_name` in `webapp/aoe2_reference.db` | Per civ×slug×age (e.g. Koreans `paladin` → "Cavalier"); resolved by `_ref_unit_name()` |
| Combat-dict mapping | `build_combat_dict_from_ref()` in `webapp/combat_unit_loader.py` | Shared by app.py, best_units, batch runners; `analysis/generate_main_db.py` has a same-named sibling that must stay in sync |
| Current build number | `patches_db.get_current_build()` (`webapp/patches.db`, `is_current=1`) | Every build-versioned artifact keys off this |
| Sim cache key | `compute_sim_version()` in `webapp/sim_version.py` | Hashes `simulation_real.py` + `analysis/config_combat.py` — **not** `simulation.py` |
| Pool scoring spec | constants in `webapp/pool_scores_lib.py` | λ=2 loss aversion, pool roles/weights |
| Battle scoring | `webapp/battle_outcome.py` | `BattleOutcome`, `signed_score` (−100…+100), multi-seed aggregation |
| Resource cost weights | `weighted_cost` in `webapp/simulation_real.py` | ⚠ duplicated in `compute_battle_scores.calc_weighted_cost`; `best_units._calc_weighted_cost` delegates to it (int floor on top); `pool_scores_lib.weighted_cost` intentionally frozen at wood ×0.8 (matches committed pool_scores.db) |
| Replay sprites | `webapp/static/replay/assets/sprites/sprites.json` | Shared by renderer.js and clip_export.py |
| Train times (classifier) | `webapp/train_times.json` | Used by the replay unit classifier |

## Key invariants

1. **The app serves combat data from `aoe2_reference.db`**, not `aoe2_units.db`.
   `/api/ref/combat-unit/<civ>/<slug>` reads `ref_units` through
   `combat_unit_loader.build_combat_dict_from_ref()`. No route queries `unit_stats`.
2. **The interactive battle sim is client-side.** The page at `/` fetches combat
   dicts as JSON and runs the fight in `static/js/simulate.js` (`BattleUnit`).
   The Python engines never run during page sims.
3. **Three engines, three jobs.** `simulation.py` (abstract tick) backs
   `/api/matchup-sims`; `simulation_real.py` (position-based) backs all batch
   matchup data; `simulate.js` backs the interactive page. A mechanic change is
   incomplete until all three (plus `.golden/baseline.json`) agree — see
   [runbooks.md](runbooks.md) §2.
4. **`sim_version` self-heals the matchup data.** Any edit to `simulation_real.py`
   or `analysis/config_combat.py` changes the hash; stale rows are re-simmed on
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
