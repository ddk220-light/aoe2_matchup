# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Absolute tape source of truth

For calibration and simulation-vs-tape work, use only the ignored project-local
archive named by `calibration/source/source_of_truth.json`. Verify it before
analysis and require every `calibration/fixtures/manifest.json` row to carry the
locked hash. Never search the historical external workspace or substitute
another corpus. If verification fails, stop and ask. Full policy:
`calibration/docs/TAPE_SOURCE_OF_TRUTH.md`.

## Project

Astro site + Flask API ([aoe2matchup.com](https://aoe2matchup.com)) that extracts Age of Empires II:DE unit data from the game's binary `.dat` file, computes fully-upgraded stats for **56 civilizations** (the simulation/rankings reference DBs; the older `aoe2_reference.db` still holds 53), pre-simulates ~500k unit matchups, and serves battle-sim / rankings / civilization / matchup-advisor / patch-tracker tools (the replay analyzer is no longer mounted; `/replay` 301-redirects to `/`). Deployed on Vercel.

**Architecture docs live in `docs/architecture/`** — start at `README.md` (system map + single-sources-of-truth table). **Before any structural change, read the matching checklist in `docs/architecture/runbooks.md`** ("when X changes, update Y": new game patch, sim logic change, new combat column, new unit/civ, new icon, frontend constants, surgical stat fix).

## Website frontend: one source of truth (2026-11-11)

Production is Vercel (see `docs/vercel-deployment.md`); Railway is retired and the
old Flask website (`apps/website`) is deleted. All visitor-facing presentation
lives in the Astro app `apps/web` (header/footer in `src/components/site/`, shared
styles in `src/styles/`, page code in `src/features/` and `src/pages/`, live
public files in `static/{img,js}/`). Flask (`apps/backend`) only serves `/api/*`.
Page titles/meta/JSON-LD, the sitemap and the exported page data are built at
build time by `scripts/migration/prepare_release.py` (`export_*.py` plus the
builders in `scripts/migration/site/`; the only Jinja left is the verbatim
snippets in `scripts/migration/site/templates/`) into `apps/web/src/generated/`,
`apps/web/public/` and `apps/backend/runtime/`. After editing `apps/web`, run
`python scripts/migration/prepare_release.py` before `npm run build --prefix apps/web`
(the build refuses sources changed after sealing), then `git checkout vercel.json`
unless the data itself changed.

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
pytest                                         # full test suite (testpaths=tests); API tests use the `client` fixture (tests/conftest.py imports aoe2_api.web)
pytest tests/test_simulations.py               # single file (golden-baseline regression)
pytest tests/test_infantry_scoring.py::test_name -v
python scripts/migration/prepare_release.py    # seal generated data: apps/web/src/generated, apps/web/public, apps/backend/runtime
npm run dev --prefix apps/web                  # Astro dev server (Node 24) on 127.0.0.1; needs prepare_release first
(cd apps/backend && flask --app app run --port 5002)   # packaged API from the sealed runtime/ (Python 3.13)
python scripts/migration/verify_build.py       # smoke the packaged API + release identity
npm run build --prefix apps/web                # production Astro build (checks the seal first)
```

There is no single local server for site + API: the Astro dev server does not
proxy `/api/*` to Flask, so pages that call the API (simulator, rankings,
advisor) only work end-to-end on a Vercel preview. CI (`.github/workflows/ci.yml`)
runs the `test` job (pytest with an ignore list, node engine/V3/frontend tests)
and the `vercel-build` job (`prepare_release.py`, `check_release.mjs frontend`/`backend`,
`verify_build.py` and the Astro build, from a clean checkout).

Production (Vercel): root `vercel.json` defines two services, `frontend`
(`apps/web`, Astro) and `backend` (`apps/backend`, Flask entrypoint `app:app`);
each runs `scripts/migration/build_service.sh <service>`. The backend installs
`apps/backend/requirements.txt` (Flask, boto3, psycopg); the CI test job uses
`requirements-ci.txt`; top-level `requirements.txt` is minimal.

## Architecture — quick map

Full detail: `docs/architecture/README.md`. The short version:

1. **`aoe2x/extract/`** — parses the dat via genieutils-py into 8 JSONs (units, technologies, tech_ages, civilizations, armor_classes, effects, tech_effects, civ_tech_trees).
2. **`aoe2x/dbgen/generate_reference.py`** — applies tech effects/civ bonuses per civ into `aoe2_reference.db` with a full audit trail (`ref_stat_chain` records every step). Hardcoded combat properties layer on top from `aoe2x/dbgen/config_combat.py` (later wins): `extracted dat → COMBAT_PROPERTIES → UNIQUE_COMBAT_PROPERTIES → CIV_COMBAT_PROPERTIES`.
3. **`aoe2x/dbgen/generate_main_db.py`** — flattens into `aoe2_units.db` `unit_stats` (100 columns). Legacy: the app reads `aoe2_reference.db` instead.
4. **`apps/backend/`** — Flask API only. `app.py` is the Vercel entrypoint: it imports the sealed copy of the package from `runtime/`, adds release headers, `/_internal/release` and `/api/cached-advisor/...`, and 404s every non-API path. The package `aoe2_api/` holds `web.py` (15 `/api/*` routes), `routes/` (battle + civilization blueprints), `services/` and `data/` (civilization JSONs).
5. **`apps/web/`** — Astro frontend: every page, the header/footer and styles, plus the live public scripts `static/js/{constants,api_client,v3_sim_worker}.js`. Build-time page data comes from `scripts/migration/` (see above).

### Three sim engines (plus a retired one) — know which one you're touching

| Engine | File | Used by |
|---|---|---|
| Abstract tick (no positions) | `aoe2x/sim/simulation.py` | `/api/matchup-sims` overlay (via `best_units.get_matchup_sims`) |
| Position-based 2D | `aoe2x/sim/simulation_real.py` | ALL batch matchup data (`run_matchup_battles.py`, `rebuild_matchup_baseline.py`, `patch_resim.py`) |
| V3 JS engine (active) | `aoe2x/js_simulation/src/` | The interactive Battle Sim page at `/`: the browser worker `apps/web/static/js/v3_sim_worker.js` runs it from the sealed `/v3-runtime/` copy against `POST /api/v3/battle-config`; also runs under node |
| Legacy client engine (retired) | `legacy/client/js/engine/` (old page shell `legacy/client/js/simulate.js`, renderer `sim_renderer.js`, lab harness `legacy/client/lab/`) | Research/parity/calibration only — never published. Parity gate `tools/simjs/parity_check.mjs`, headless runner `tools/simjs/headless.mjs`, `tests/js/engine/` |

`aoe2x/sim/sim_version.py` hashes `simulation_real.py` + `aoe2x/dbgen/config_combat.py` into the matchup-row cache key: editing either auto-stales matchup data (re-simmed on next batch run). Editing `simulation.py` does **not** bump it.

### Combat-unit data flow (most common debugging path)

```
aoe2x/dbgen/config_combat.py (+ config_units.py)
 → aoe2x/dbgen/generate_reference.py → aoe2_reference.db (ref_units)
  → aoe2x/sim/combat_unit_loader.py build_combat_dict_from_ref()
   → apps/backend/aoe2_api/web.py /api/ref/combat-unit/<civ>/<slug>  (JSON)
    → legacy/client/js/engine/battle_unit.js BattleUnit (lab harness + headless + parity tools)
    → simulation.py / simulation_real.py prepare_combat_unit() (backend callers)
```

The live simulator instead goes reference DB (`aoe2_reference_simulation.db`)
→ `aoe2_api/services/{mechanics,battles}.py` → `POST /api/v3/battle-config`
(`aoe2_api/routes/battles.py`) → `aoe2x/js_simulation/src/` in the browser worker.

## Cross-File Sync Rules (forget one → bug)

1. **New combat column/ability** = registry entry (`aoe2x/dbgen/ability_registry.py`) + `config_combat.py` value + one handler per engine (`simulation.py` / `simulation_real.py` / `legacy/client/js/engine/battle_unit.js`) — the ref-DB schema/writer/audit and `combat_unit_loader.py` are GENERATED from the registry; only legacy `generate_main_db.py` still needs hand edits. Checklist: runbooks §3.
   - **Parity gate — any edit under `legacy/client/js/engine/` must re-run `node tools/simjs/parity_check.mjs`** (bit-exact replay of 205 golden fights; exit 0 = OK). A deliberate behavior change *will* fail it: that is the signal to re-capture the golden panel and record why in the commit. Also run `node --test tests/js/engine/`.
2. **`UNIT_LINES`** — Python source is `aoe2x/sim/unit_lines.py` (imported by 12 modules); the live JS copy lives in `apps/web/src/features/rankings/render.mjs` (the retired `legacy/client/js/rankings.js` has another). Update the live copies together.
3. **Resource cost weights** — `simulation_real.py weighted_cost` ↔ `compute_battle_scores.calc_weighted_cost` (explicit keep-in-lockstep comment).
4. **`PLAYER_COLORS`** — `replay_core.py` ↔ `clip_export.py` (intentionally different palettes; change together).
5. **Sim behavior changes** → regenerate `.golden/baseline.json` (`python .golden/capture_baseline.py`) and re-sim/re-derive matchup data (runbooks §2).
6. **Frontend constants** (`ENABLED_CIVS`, `NAME_TO_ICON`, `UNIQUE_BUILDING`) are declared ONLY in `apps/web/static/js/constants.js`, which reads them from `window.SITE_CATALOG` — built by `site_catalog()` in `apps/backend/aoe2_api/services/catalog.py` from the civ roster in `aoe2_reference_simulation.db` plus `aoe2x/assets/presentation.json` (`icon_names` 230, `unique_buildings` 13). Edit the JSON/DB, not the JS. (Server-side civ validation derives from the reference DBs; the pipeline civ list `ORIGINAL_13_CIVS` in `aoe2x/dbgen/config_constants.py` is derived from `aoe2x.extract.extract_constants.CIV_NAMES`.)

## Conventions

- **Civ names** are title-case strings (`"Franks"`). **Unit slugs** are lowercase; standard units use the plain name (`"knight"`), unique units carry the civ suffix (`"huskarl_goths"`). **The data model is Imperial-only** (2026-06-11): every `ref_units`/`unit_stats` row is age `Imperial`; `age=castle` API requests get a clean 400. Castle-age techs still apply *inside* the Imperial stat chain.
- **Determinism:** single sims are deterministic given a seed — run each scenario once, not in a loop. Batch matchup data uses explicit multi-seed sampling (8→40 escalating); golden tests pin `GOLDEN_SEED=20260411`.
- When comparing units, run **both** equal-count and equal-resources sims; they test different things (raw strength vs. cost-efficiency).

## Project-specific skills and agents

Prefer these over ad-hoc exploration:

- Skills in `.claude/skills/`: `webapp-architecture`, `running-simulations`, `researching-game-data`, `aoe2onlinereference`.
- Agents in `.claude/agents/`: `unit-stats-analyzer` (full stat/tech breakdown for a unit×civ), `webapp-test-runner` (seals a release, runs the API/build checks and validations).

## Git workflow — branches and Vercel deployments

Two long-lived branches, each tied to a Vercel deployment (project and release checks: `docs/vercel-deployment.md`):

| Branch    | Vercel       | Role                                                              |
|-----------|--------------|-------------------------------------------------------------------|
| `main`    | production   | **Frozen.** Only updated by promoting `staging`. Auto-deploys to prod (aoe2matchup.com). |
| `staging` | preview      | Where new work lands. Every push builds a protected preview deployment. |

**Rules:**

1. **Never commit directly to `main`.** All work goes on `staging` (or short-lived feature branches off `staging` that merge back into it).
2. **Never `git push origin main` from a Claude session unless explicitly asked.** A push to `main` ships to production. If a fix needs to ship, push to `staging`, ask the user to verify on the staging preview deployment, then ask before promoting.
3. **Promotion is fast-forward only:**
   ```bash
   git checkout main
   git merge --ff-only staging
   git push origin main
   ```
   `--ff-only` refuses if `main` has diverged — that's a feature, not a bug. If it errors, stop and ask the user.
4. **Default working branch is `staging`.** When starting a new task, check out `staging` first (`git checkout staging && git pull`). If a session lands on `main` and starts committing, fix it before pushing.
5. **If local `main` is ever ahead of `origin/main`** (e.g. accidental commits): the safe recovery is `git reset --hard origin/main`, but only after confirming the work is preserved on `staging` — ask the user.
6. **Matchup DBs live OUTSIDE the repo** (`D:/AI/matchup_baseline_<build>.db`, 200+ MB) — never commit them. (The old 3.9 MB Armenians-only `matchup_db.db` stub in the former Flask website folder was removed 2026-06-11; derive scripts take `--matchup-db` and pre-flight-reject partial DBs.)
7. **Committed data artifacts ARE the deployment mechanism** — every Vercel deployment rebuilds from whatever's on its branch (`scripts/migration/build_service.sh`): `data/golden/aoe2_reference.db`, `aoe2_reference_simulation.db`, `aoe2_reference_rankings.db`, `aoe2_units.db`, `derived_data.db`, `pool_scores.db`, `patches.db`, `civ_power_units/*.json`, `civ_top_units.json`, `train_times.json`. Regenerate → commit on `staging` → smoke-test → promote.
8. **`.golden/baseline.json` is sim-output golden data.** When sim behavior changes, regenerate via `python .golden/capture_baseline.py` and commit on `staging` like any other source file.
