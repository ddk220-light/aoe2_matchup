# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Flask web app ([aoe2matchup.com](https://aoe2matchup.com)) that extracts Age of Empires II:DE unit data from the game's binary `.dat` file, computes fully-upgraded stats for **53 civilizations**, pre-simulates ~500k unit matchups, and serves battle-sim / rankings / matchup-advisor / patch-tracker / replay-analyzer tools. Deployed on Railway.

**Architecture docs live in `docs/architecture/`** — start at `README.md` (system map + single-sources-of-truth table). **Before any structural change, read the matching checklist in `docs/architecture/runbooks.md`** ("when X changes, update Y": new game patch, sim logic change, new combat column, new unit/civ, new icon, frontend constants, surgical stat fix).

## Build Pipeline (stats)

```bash
python -m aoe2x.extract.run               # ~10s — data/inputs/empires2_x2_p1.dat -> data/inputs/extracted_data/*.json (needs genieutils-py)
python -m aoe2x.dbgen.generate_reference   # ~30s -> data/golden/aoe2_reference.db (audit trail; THE DB the app serves)
python -m aoe2x.dbgen.generate_main_db     # ~2s  -> data/golden/aoe2_units.db (flat unit_stats; /units page + unit_verifications read it)
```

The `.dat` file is not in the repo — copy it from a local AoE2:DE install into `data/inputs/`. `genieutils-py` is in neither requirements file (use the conda python, which has it).

Rankings/matchup data is **not** produced by the above. It comes from the sim-data chain (PyPy + `simulation_real.py`): batch matchup sims → `derive_unit_rankings.py` / `derive_pool_scores.py` / `best_units.py` → `derived_data.db` / `pool_scores.db` / `civ_power_units/<build>.json`. Exact commands: `docs/architecture/runbooks.md` §1. (`compute_battle_scores.py` is **retired** — don't run it; its `battle_scores.json` output and the `app.py` loader were deleted, scores live in `derived_data.db`.)

## Run / Test

```bash
PORT=5002 python webapp/app.py                 # local dev server
pytest                                         # full test suite (testpaths=tests)
pytest tests/test_simulations.py               # single file (golden-baseline regression)
pytest tests/test_infantry_scoring.py::test_name -v
```

Production start (Railway): `railway.json` runs `gunicorn app:app --workers 2 --timeout 300` from `webapp/` (the Procfile is a fallback). Railway installs `webapp/requirements.txt` (Flask, numpy, Pillow, imageio-ffmpeg, pinned `aoc-mgz` fork); top-level `requirements.txt` is minimal.

## Architecture — quick map

Full detail: `docs/architecture/README.md`. The short version:

1. **`extraction/`** — parses the dat via genieutils-py into 8 JSONs (units, technologies, tech_ages, civilizations, armor_classes, effects, tech_effects, civ_tech_trees).
2. **`analysis/generate_reference.py`** — applies tech effects/civ bonuses per civ into `aoe2_reference.db` with a full audit trail (`ref_stat_chain` records every step). Hardcoded combat properties layer on top from `analysis/config_combat.py` (later wins): `extracted dat → COMBAT_PROPERTIES → UNIQUE_COMBAT_PROPERTIES → CIV_COMBAT_PROPERTIES`.
3. **`analysis/generate_main_db.py`** — flattens into `aoe2_units.db` `unit_stats` (100 columns). Legacy: the app reads `aoe2_reference.db` instead.
4. **`webapp/`** — Flask (`app.py`, 24 routes + 7-route replay blueprint) + shared static assets (`static/js/*.js`, `static/css/*.css` — **not** inlined in templates anymore).

### Three sim engines — know which one you're touching

| Engine | File | Used by |
|---|---|---|
| Abstract tick (no positions) | `webapp/simulation.py` | `/api/matchup-sims` overlay (via `best_units.get_matchup_sims`) |
| Position-based 2D | `webapp/simulation_real.py` | ALL batch matchup data (`run_matchup_battles.py`, `rebuild_matchup_baseline.py`, `patch_resim.py`) |
| Frontend canvas (`BattleUnit`) | `webapp/static/js/simulate.js` | The interactive Battle Sim page at `/` — runs entirely client-side |

`webapp/sim_version.py` hashes `simulation_real.py` + `analysis/config_combat.py` into the matchup-row cache key: editing either auto-stales matchup data (re-simmed on next batch run). Editing `simulation.py` does **not** bump it.

### Combat-unit data flow (most common debugging path)

```
analysis/config_combat.py (+ config_units.py)
 → analysis/generate_reference.py → aoe2_reference.db (ref_units)
  → webapp/combat_unit_loader.py build_combat_dict_from_ref()
   → app.py /api/ref/combat-unit/<civ>/<slug>  (JSON)
    → static/js/simulate.js BattleUnit (interactive page)
    → simulation.py / simulation_real.py prepare_combat_unit() (backend callers)
```

## Cross-File Sync Rules (forget one → bug)

1. **New combat column/ability** = registry entry (`analysis/ability_registry.py`) + `config_combat.py` value + one handler per engine (`simulation.py` / `simulation_real.py` / `static/js/simulate.js`) — the ref-DB schema/writer/audit and `combat_unit_loader.py` are GENERATED from the registry; only legacy `generate_main_db.py` still needs hand edits. Checklist: runbooks §3.
2. **`UNIT_LINES`** — Python source is `webapp/unit_lines.py` (imported by 8 modules); a JS copy lives in `static/js/rankings.js`. Update both.
3. **Resource cost weights** — `simulation_real.py weighted_cost` ↔ `compute_battle_scores.calc_weighted_cost` (explicit keep-in-lockstep comment).
4. **`PLAYER_COLORS`** — `replay_core.py` ↔ `clip_export.py` (intentionally different palettes; change together).
5. **Sim behavior changes** → regenerate `.golden/baseline.json` (`python .golden/capture_baseline.py`) and re-sim/re-derive matchup data (runbooks §2).
6. **Frontend constants** (`ENABLED_CIVS`, `NAME_TO_ICON` 218 entries, `UNIQUE_BUILDING`) live ONLY in `webapp/static/js/constants.js` — the old per-template copies are gone. (Server-side civ validation derives from the reference DB; the pipeline civ list `ORIGINAL_13_CIVS` in `analysis/config_constants.py` is derived from `extraction.extract_constants.CIV_NAMES`.)

## Conventions

- **Civ names** are title-case strings (`"Franks"`). **Unit slugs** are lowercase; standard units use the plain name (`"knight"`), unique units carry the civ suffix (`"huskarl_goths"`). **The data model is Imperial-only** (2026-06-11): every `ref_units`/`unit_stats` row is age `Imperial`; `age=castle` API requests get a clean 400. Castle-age techs still apply *inside* the Imperial stat chain.
- **Determinism:** single sims are deterministic given a seed — run each scenario once, not in a loop. Batch matchup data uses explicit multi-seed sampling (8→40 escalating); golden tests pin `GOLDEN_SEED=20260411`.
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
6. **Matchup DBs live OUTSIDE the repo** (`D:/AI/matchup_baseline_<build>.db`, 200+ MB) — never commit them. (The old 3.9 MB Armenians-only `webapp/matchup_db.db` stub was removed 2026-06-11; derive scripts take `--matchup-db` and pre-flight-reject partial DBs.)
7. **Committed data artifacts ARE the deployment mechanism** — both environments serve whatever's on their branch: `webapp/aoe2_reference.db`, `aoe2_units.db`, `derived_data.db`, `pool_scores.db`, `patches.db`, `civ_power_units/*.json`, `civ_top_units.json`, `train_times.json`. Regenerate → commit on `staging` → smoke-test → promote.
8. **`.golden/baseline.json` is sim-output golden data.** When sim behavior changes, regenerate via `python .golden/capture_baseline.py` and commit on `staging` like any other source file.
