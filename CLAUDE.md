# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Flask web app that extracts Age of Empires II:DE unit data from the game's binary `.dat` file, computes fully-upgraded stats for 50 civilizations, and serves matchup/simulation tools. Deployed on Railway.

## Build Pipeline (run in order when game data or configs change)

```bash
python3 -m extraction.run                      # ~10s — empires2_x2_p1.dat -> extraction/extracted_data/*.json
python3 -m analysis.generate_reference         # ~30s -> webapp/aoe2_reference.db (full audit trail)
python3 -m analysis.generate_main_db           # ~2s  -> webapp/aoe2_units.db   (flat unit_stats table)
cd webapp && python3 compute_battle_scores.py  # ~20s -> webapp/battle_scores.json (round-robin rankings)
```

The `.dat` file is not in the repo. Copy it from a local AoE2:DE install into `extraction/` (see README).

## Run / Test

```bash
PORT=5002 python3 webapp/app.py                # local dev server
pytest                                         # full test suite (testpaths=tests)
pytest tests/test_simulations.py               # single file
pytest tests/test_infantry_scoring.py::test_name -v
```

Production start (Railway): `cd webapp && gunicorn app:app` — see `railway.json`, `webapp/Procfile`.

Top-level `requirements.txt` has only `flask` + `gunicorn`; `webapp/requirements.txt` is what Railway installs. `genieutils-py` is required for extraction but is not in either requirements file (install manually when rebuilding DBs).

## Architecture — The Four Stages

The whole project is a 4-stage pipeline. Each stage produces artifacts the next stage reads; webapp reads only stage-4 outputs.

1. **`extraction/`** — parses `empires2_x2_p1.dat` via `genieutils-py` into 8 JSON files (units, techs, effects, civs, armor classes, constants). Entry: `extraction/run.py`.
2. **`analysis/generate_reference.py`** — applies tech effects per civ to build `aoe2_reference.db` with a full audit trail (which tech/bonus produced which stat change).
3. **`analysis/generate_main_db.py`** — flattens the reference DB into `aoe2_units.db`'s `unit_stats` table (80+ columns, one row per civ×unit×age), which is what the webapp SQL queries hit.
4. **`webapp/`** — Flask + inline-JS templates + `simulation.py` tick-based battle sim. `compute_battle_scores.py` is an offline batch job that pre-runs round-robin matchups into `battle_scores.json`.

### Config override priority (later wins)

```
extracted .dat data  →  COMBAT_PROPERTIES  →  UNIQUE_COMBAT_PROPERTIES  →  CIV_COMBAT_PROPERTIES
```

All three `*_PROPERTIES` dicts live in `analysis/config*.py`. Use these to hardcode combat properties that can't be read from the dat file (charge, trample, bleed, dodge, projectile_count, etc.).

### Combat-unit data flow (most common debugging path)

```
analysis/config*.py
 → analysis/generate_reference.py → aoe2_reference.db
  → analysis/generate_main_db.py → aoe2_units.db (unit_stats)
   → app.py /api/combat-unit/<civ>/<slug>
    → simulate.html JS fetch → simulation.py prepare_combat_unit() → simulate_battle()
```

### Webapp internals

- `webapp/app.py` — 37 routes, all DB queries, matchup analysis helpers (`_run_matchup_analysis`, `_run_army_sims`).
- `webapp/simulation.py` — pure Python, no Flask/DB deps. `prepare_combat_unit()` parses a DB row dict; `simulate_battle()` runs the 1v1 tick loop; `simulate_mixed_battle()` runs army fights. ~1.3ms/sim.
- `webapp/templates/*.html` — CSS and JS are **inlined per template**; there is no shared stylesheet. `simulate.html` carries its own JS canvas simulation (`BattleUnit` class) that mirrors but is separate from the backend sim.
- Databases in `webapp/`: `aoe2_units.db` (main), `aoe2_reference.db` (audit), `matchup_combos.db`, plus `app_data.db` for comments/verifications.

## Cross-File Sync Rules (forget one → bug)

These constants are duplicated across files. Any change must be applied everywhere:

1. **`UNIT_LINES` dict** — in both `webapp/app.py` and `webapp/compute_battle_scores.py`.
2. **`NAME_TO_ICON`** — in 4 templates: `index.html`, `simulate.html`, `civ_detail.html`, `matchup_advisor.html`.
3. **`UNIQUE_BUILDING`** — in `simulate.html` and `civ_detail.html` (maps non-Castle unique units to their buildings).
4. **`ENABLED_CIVS`** — in `index.html` and `simulate.html`; must match `ORIGINAL_13_CIVS` in `app.py` (authoritative).
5. **New `unit_stats` column** — touches `analysis/generate_main_db.py` (schema + `build_combat_dict_from_ref`), `webapp/app.py` `api_combat_unit()` SELECT, `webapp/simulation.py` `prepare_combat_unit()`, and possibly `simulate.html` `BattleUnit`.
6. **Battle scores go stale** after any simulation logic or stat change — rerun `compute_battle_scores.py`.

## Conventions

- **Civ names** are title-case strings (`"Franks"`, `"Byzantines"`). **Unit slugs** are lowercase; standard units use the plain name (`"knight"`, `"halberdier"`), unique units carry the civ suffix (`"huskarl_goths"`, `"cataphract_byzantines"`). For non-elite uniques that exist in both Castle and Imperial ages, filter by `us.age = 'Imperial'`.
- Simulations are **deterministic** — run each scenario once, not in a loop.
- When comparing units, run **both** equal-count and equal-resources sims; they test different things (raw strength vs. cost-efficiency).

## Project-specific skills and agents

Prefer these over ad-hoc exploration:

- Skills in `.claude/skills/`: `webapp-architecture`, `running-simulations`, `researching-game-data`, `aoe2onlinereference`.
- Agents in `.claude/agents/`: `unit-stats-analyzer` (full stat/tech breakdown for a unit×civ), `webapp-test-runner` (spins up local server + runs validations).

## Git workflow — branches and Railway environments

Two long-lived branches, each tied to a Railway environment:

| Branch    | Railway env  | Role                                                              |
|-----------|--------------|-------------------------------------------------------------------|
| `main`    | production   | **Frozen.** Only updated by promoting `staging`. Auto-deploys to prod. |
| `staging` | staging      | Where new work lands. Auto-deploys to the staging URL on every push.   |

**Rules:**

1. **Never commit directly to `main`.** All work goes on `staging` (or short-lived feature branches off `staging` that merge back into it).
2. **Never `git push origin main` from a Claude session unless explicitly asked.** A push to `main` ships to production. If a fix needs to ship, push to `staging`, ask the user to verify on the staging URL, then ask before promoting.
3. **Promotion is fast-forward only:**
   ```bash
   git checkout main
   git merge --ff-only staging
   git push origin main
   ```
   `--ff-only` refuses if `main` has diverged — that's a feature, not a bug. If it errors, stop and ask the user.
4. **Default working branch is `staging`.** When starting a new task, check out `staging` first (`git checkout staging && git pull`). If a session lands on `main` and starts committing, fix it before pushing.
5. **If local `main` is ever ahead of `origin/main`** (e.g. accidental commits): the safe recovery is `git reset --hard origin/main`, but only after confirming the work is preserved on `staging` — ask the user.
6. **Don't commit `webapp/matchup_db.db`** (200+ MB sim cache, modified locally during sim batches). It's already gitignored where possible; treat any "modified" status on it as noise.
7. **Sim-data files (`webapp/aoe2_reference.db`, `webapp/derived_data.db`, `webapp/civ_power_units.json`, `webapp/pool_scores.db`) ARE committed.** They're how the deployed app gets its data — both environments deploy whatever's on their branch. Regenerate → commit on `staging` → smoke-test → promote.
8. **`.golden/baseline.json` is sim-output golden data.** When sim behavior changes, regenerate via `python .golden/capture_baseline.py` and commit on `staging` like any other source file.
