# Operations: Deployment, Testing, and Offline Tooling

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This document covers how the webapp ships to Vercel, how the repo is tested, and the offline tooling that lives alongside the webapp (scenario recording, sprite/art extraction, the reference corpus, and marketing). For what the webapp itself does see [webapp.md](webapp.md); for how the databases it serves are built see [data-pipeline.md](data-pipeline.md) and [derived-data.md](derived-data.md).

## 1. Deployment (Vercel)

*Updated 2026-11-12: Railway, `railway.json`, the Procfile and the `apps/website` Flask site are retired. Full release procedure: [../vercel-deployment.md](../vercel-deployment.md).*

The site is one Vercel project behind `aoe2matchup.com` with two services, both defined in the root `vercel.json` (which `scripts/migration/prepare_release.py` also rewrites with release headers/redirects):

| Service | Root | Framework / entry | Build command |
|-----|-------|-----|-----|
| `frontend` | `apps/web` | Astro (Node 24); bound to the backend via `BACKEND_INTERNAL_URL` | `bash ../../scripts/migration/build_service.sh frontend` |
| `backend` | `apps/backend` | Flask, entrypoint `app:app`, `maxDuration` 60 s | `bash ../../scripts/migration/build_service.sh backend` |

`build_service.sh` installs `scripts/migration` npm deps and `apps/backend/requirements.txt`, runs `prepare_release.py` (regenerating `apps/web/src/generated/`, `apps/web/public/` and the sealed `apps/backend/runtime/` from committed sources and databases) and `check_release.mjs <service>`, then for the frontend `npm run build --prefix apps/web`. Every push builds: there are no watch patterns, so any committed change (code, data or docs) produces a new deployment.

### Requirements files

| File | Contents | Used by |
|------|----------|---------|
| `requirements.txt` (root) | `flask==3.0.0`, `gunicorn==21.2.0` | Minimal local install; **not** what Vercel installs |
| `apps/backend/requirements.txt` (+ `pyproject.toml`, `uv.lock`) | `Flask==3.0.0`, `boto3`, `psycopg[binary]` (Python 3.13) | Vercel backend build and the CI `vercel-build` job |
| `requirements-ci.txt` | test dependencies | CI `test` job (Python 3.11) |

The replay analyzer's `mgz` fork, Pillow and imageio-ffmpeg are no longer server dependencies (the replay blueprint is not mounted); a separate replay host installs them from `apps/viewer/requirements.txt` — see [replay.md](replay.md). Notably absent from all of them: `genieutils-py` (needed only for stage-1 extraction — see Local prerequisites).

### Environments and branch mapping

Two long-lived branches; the mapping is Vercel project configuration, not in the repo:

| Branch | Vercel | Role |
|--------|--------------------|------|
| `main` | production (`aoe2matchup.com`) | Frozen; only updated by fast-forward promotion from `staging`. Auto-deploys on push. |
| `staging` | protected preview deployment | Default working branch; every push builds a preview. |

### How data ships

There is no database server for the core site. All data the site serves is **SQLite files and JSON committed to git** (mostly `data/golden/`, plus `apps/backend/aoe2_api/data/`) — each deployment is built from whatever data files are on its branch. Shipping new data means: regenerate locally → commit on `staging` → smoke-test on the preview deployment → promote. Media (unit art, animations) is served from Blob and verified against committed SHA-256 manifests; the authoring copy lives in `data/media/`.

### Environment variables

All optional and read when the release is built (`scripts/migration/site/config.py`, and `apps/backend/aoe2_api/web.py` for the API): `SITE_URL`, `SEARCH_INDEXING`, `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION`, and the `SOCIAL_*` footer links. The full table is in [webapp.md](webapp.md), "Environment variables and config".

## 2. Git workflow and committed artifacts

Rules (full rationale in `CLAUDE.md`, verified still accurate except where noted):

1. **All work lands on `staging`** (or short-lived feature branches off it). Never commit directly to `main`.
2. **Promotion is fast-forward only**: `git checkout main && git merge --ff-only staging && git push origin main`. If `--ff-only` refuses, `main` has diverged — stop and investigate, do not force.
3. A push to `main` is a production deploy. Never push `main` without explicit confirmation.

### Committed data artifacts (ground truth from `git ls-files`)

These binary/data files are committed **on purpose** — they are how the deployed app gets its data:

| File | Size | What it is |
|------|------|------------|
| `data/golden/aoe2_units.db` | 2.0 MB | Main flat `unit_stats` DB (stage 3 output) |
| `data/golden/aoe2_reference.db` | 4.5 MB | Audit-trail reference DB (stage 2 output) |
| `data/golden/aoe2_reference_simulation.db`, `aoe2_reference_rankings.db` | 11.1 MB each | 56-civ reference DBs for the V3 simulator and the published rankings |
| `data/golden/derived_data_v3.db` (+ `.metadata.json`) | 5.8 MB | Published V3 ranking scores and methodology |
| `data/golden/civ_matchups_first_pass.db` (+ metadata/validation JSON) | 99 MB | Matchup Advisor dataset (`/api/advisor-*`) |
| `apps/backend/aoe2_api/data/civilizations-185872.json`, `civilization-strategies.json` | small | Civilization page supplement and strategy copy |
| `data/golden/derived_data.db` | 14.5 MB | Derived rankings/advisor recommendations (battle scores live here now) |
| `data/golden/pool_scores.db` | 4.4 MB | Pool-score data |
| `data/golden/patches.db` | 6.3 MB | Patch/build history for the patches pages |
| `data/golden/civ_power_units/{170934,177723}.json` | ~1.8 MB each | Per-build civ power-unit data (the legacy flat `civ_power_units.json` was deleted — no fallback) |
| `data/golden/civ_top_units.json`, `aoe2x/replay/train_times.json` | small | Misc serving data (`battle_scores.json` was deleted — scores moved into `derived_data.db`) |
| `.golden/baseline.json` | 208 KB | Golden sim regression baseline (section 3) |
| `tests/fixtures/berserker_matchups.db` | test fixture | |
| `apps/video/auto/unique_units.json`, `marketing/responded-threads.json` | small | Tooling state |

**Note (2026-06-11):** the 3.9 MB Armenians-only in-repo `matchup_db.db` stub was removed from the repo — no route ever read it, and the derive scripts pre-flight-reject partial DBs. Matchup DBs are always local/external (`D:/AI/matchup_baseline_<build>.db`), passed via `--matchup-db`.

Deliberately **not** committed (`.gitignore`): `data/inputs/empires2_x2_p1.dat` and `data/inputs/extracted_data/`, `graphics/game_raw_files/` (19 GB raw sprite dump), everything under `data/local/` (sim caches such as `battle_cache.json`, local matchup DBs, patch-pipeline intermediates `aoe2_reference_prev.db`, `changed_units_*.json`, `extracted_data_prev/`), `data/golden/*.db.bak`, the generated build outputs (`apps/web/src/generated/`, `apps/web/public/`, `apps/backend/runtime/`), and scratch dirs (`.scratch/`, `tmp/`, `.old/`).

## 3. Testing

### pytest

Config is `pytest.ini`: `testpaths = tests`, `python_files = test_*.py`. `tests/conftest.py` prepends `apps/backend/` and the repo root to `sys.path`, imports the API as `aoe2_api.web` (never the deployed `apps/backend/app.py`, which needs the sealed `runtime/`), and provides a Flask test `client` fixture. Run with `pytest` from the repo root; CI runs it with an ignore list (see `.github/workflows/ci.yml`). There are 65 Python test files; a selection:

| File | Covers |
|------|--------|
| `test_simulations.py` | Golden regression: `get_matchup_sims()` vs `.golden/baseline.json` (see below) |
| `test_position_sim_abilities.py` | Special abilities in the position-based engine `aoe2x/sim/simulation_real.py` |
| `test_battle_outcome.py` | `BattleOutcome` contract: `signed_score`, `average_outcomes`, `simulate_real_battle` return shape |
| `test_resource_per_kill.py` | Per-resource kill-bonus accounting in `simulation_real.py` |
| `test_value_lost.py` | HP-weighted value-lost computation in `simulation_real.py` |
| `test_sim_outcome_cache.py` | Outcome cache + unit fingerprinting (`aoe2x/sim/sim_outcome_cache.py`) |
| `test_sim_version.py` | `compute_sim_version()` hash changes when sim source changes |
| `test_matchup_db.py` | `aoe2x/batch/matchup_db.py` schema/insert/upsert/version checks |
| `test_matchup_diff.py` | `matchup_diff` snapshot/diff detects verdict flips between builds |
| `test_ref_diff.py` | `ref_diff` detects changed unit fields between reference DBs |
| `test_unit_ranking_derive.py` | `derive_unit_rankings` writes role/composite scores to `derived_data.db` |
| `test_naval_rankings.py` | Battle-score queries against `derived_data.db` (naval columns) |
| `test_versioning.py` | Build-number versioning of derived artifacts, fallback chains, migrations |
| `test_pool_scores_db.py` / `_lib.py` / `_query.py` | Unit tests for the three pool-score modules |
| `test_pool_scores_integration.py` | End-to-end derived-score regression (Viking Elite Berserk) |
| `test_infantry_scoring.py` | Militia-line role benchmarks in `aoe2x/rank/compute_battle_scores.py` |
| `test_siege_scoring.py` | Siege-vs-castle scoring helpers (`_simulate_siege_vs_castle`, TTK math, castle target table) |
| `test_patches_db.py` | `patches_db` helpers and the build-time patch pages |
| `test_reference_builder.py` | Pure functions of `scripts/build_reference_docs.py` (section 6) |

### Golden baseline (`.golden/`)

`.golden/capture_baseline.py` snapshots `get_matchup_sims()` (from `aoe2x/advisor/best_units.py`) for 10 fixed civ pairs × 2 ages = **20 entries** into `.golden/baseline.json` (committed). Determinism comes from `random.seed(GOLDEN_SEED)` — `GOLDEN_SEED = 20260411`, re-seeded before *each* matchup so entries are insensitive to iteration order. A `_normalize` pass drops non-deterministic keys (`elapsed_ms`, `timing`, `generated_at`) and rounds floats to 6 decimal places. `tests/test_simulations.py` re-runs each entry with the same seed and asserts byte-equality with the baseline.

**Regenerate** (`python .golden/capture_baseline.py`, ~30 s, CPython is fine) whenever simulation behavior changes *intentionally* — any sim-logic, stat, or config change makes `test_golden_regression` fail until you do. Commit the regenerated `baseline.json` on `staging` like source. (The script docstring still mentions a direct `simulate_battle()` section; `main()` only captures `matchup_sims` — the docstring is stale.)

### JavaScript tests (frontend parity)

Not collected by pytest; run with Node (CI uses Node 22 for these):

- `node tests/test_frontend_projectile_miss.js` — dynamically `import()`s the **live** `BattleUnit` and `makeRng` out of the retired client engine `legacy/client/js/engine/` (7 tests). Since the 2026-07-28 engine extraction these are real ES modules, so the test imports them directly — no brace-matching, no `eval`, no hand-copied snapshot, and randomness is stubbed through `sim.rng` instead of `Math.random`. Asserts the frontend engine mirrors the backend miss/graze model in `aoe2x/sim/simulation_real.py`.
- `node --test tests/js/engine/` — 17 unit tests over the engine modules (RNG stream, projectile flight, `BattleUnit`, `Simulation`, DOM-purity).
- `node tools/simjs/parity_check.mjs` — **the parity gate.** Replays the 205-fight golden panel in `tools/simjs/golden/` against the engine and demands bit-exact state hashes (exit 0 = OK, 1 = divergence, 2 = harness/meta error). Mandatory after any edit under `legacy/client/js/engine/`; a deliberate behavior change is *supposed* to fail it, which calls for a re-captured golden panel and a note in the commit. See [simulation-engines.md](simulation-engines.md) §3.
- `node tests/test_sim_params.js` — URL-parameter parsing in `apps/web/src/features/simulator/params.mjs` (deep-link autorun).

## 4. `apps/video/` — validating the sim against the real game

Purpose: generate real `.aoe2scenario` files, run them in AoE2:DE as AI-vs-AI fights, record the screen, and compose titled matchup videos — both to **cross-check the simulator against the actual game** and to produce shareable video content. The sim engines being validated are described in [simulation-engines.md](simulation-engines.md).

| Module | Role |
|--------|------|
| `make_scenario.py` | Parameterized arena-scenario generator (walled arena, AI vs AI + spectator player, victory/countdown/force-engage triggers) via AoE2ScenarioParser |
| `make_showcase.py` | Decorated screenshot-friendly showcase arenas (peaceful by default, `--fight` to arm) |
| `prepare_template.py` | One-time cleanup of the golden jungle template (strips redundant tech-research effects) |
| `build_run.py` | Per-run scenario from the golden template: swaps civs + unit types, retargets triggers |
| `templates/template_landscape_jungle.aoe2scenario` | The committed hand-decorated golden template |
| `auto/orchestrate_matchup.py` | One-command macro: build → stage scenario as the sole file in the game folder → drive the Scenario Editor UI → record → detect fight end → compose → copy out |
| `auto/batch_matchups.py` | Queue of matchups back-to-back, hands-off; pre-flight slug/environment validation (`--dry-run`), per-matchup failure isolation |
| `auto/build_unique_list.py` → `auto/unique_units.json` | Ordered, validated list of all 62 land unique units for `--list`/`--slice` sweeps |
| `auto/input_driver.py` | Scripted mouse/keyboard via `cliclick` (`/opt/homebrew/bin/cliclick`); game-safe move→settle→down/up click pattern |
| `auto/vision.py` | `screencapture` + rapidocr OCR of fractional screen regions: "which screen is the game on / has the fight ended" |
| `auto/record_until_end.py` | Start recorder → watch for the end-of-game banner → stop → compose → copy |
| `overlay/` | Video composition: `overlay_data.py` (stats from `data/golden/aoe2_reference.db`), `render_card.py` (HTML → headless Chrome → PNG intro/outro cards), `hud.py` (Pillow live HUD), `results.py` (sim-predicted timeline), `video_extract.py` (OCR survivor counts from footage), `compose.py` (ffmpeg assembly), `make_real_video.py` (one recording → titled video) |
| `recorder/` | `sck_record.swift` — macOS ScreenCaptureKit recorder (video + system audio, 1920×1248@60) with `build.sh`/`record.sh` |

**Status:** past the original de-risk spike (the Fire Archer vs Jian spike scenarios are still committed at the top level, plus `spike_runs/` outputs). Per `apps/video/auto/README.md` the hands-off pipeline is verified: a 2-matchup batch produced both titled videos with no human interaction, ~4 min each. The composition is now template-based and OCR-free for results (OCR is only used for screen-state detection).

**Platform constraints:** the automation half is **macOS-only** — it depends on `cliclick` (Homebrew), `screencapture`, ScreenCaptureKit, and the Mac-native AoE2:DE install. The launching Terminal needs **both** Screen Recording and Accessibility permission (System Settings → Privacy & Security); Screen Recording alone does not allow input injection. The game's scenario folder is dedicated to staged runs (exactly one file at a time, so UI navigation needs no search). The game launches via Steam app id 813780. Scenario *generation* (`make_scenario.py`, `build_run.py`) is cross-platform Python. Setup/handoff notes: `apps/video/MAC_SETUP.md`.

## 5. `graphics/` — sprites, upscaling, and FLUX.2 art

### Sprite extraction: `graphics/sld_decode.py`

A from-scratch decoder for AoE2:DE's **SLD v4** sprite format (BC1/DXT1-compressed, used since ~build 66692), implemented from the openage spec because no headless decoder was installable. It decodes the MAIN graphics layer (RGB + transparency from skipped blocks and BC1 1-bit alpha) and **skips** the shadow, damage, and player-color layers — player-color areas render in their baked-in default tint, which is fine for portraits/reference. Flags: `--frame N`, `--all`, `--max M`, `--angle-stride S` (one image per facing), `--crop`, `--margin N`. Prefer `_x2.sld` variants for double resolution. Raw `.sld` inputs live in `graphics/game_raw_files/` (gitignored, ~19 GB local dump); to find a unit's `.sld` and frame layout, read the dat's graphic entries via genieutils (recipe in the module docstring — conda `python`, see section 8). Decoded PNGs land in `graphics/extracted/<slug>/`. All decoded sprites are git-tracked — originals and the `_lanczos4x`/`_esrgan4x` upscale variants (re-tracked 2026-06-11 by owner decision: the repo doubles as the backup for generated images).

### Upscaling: `graphics/upscale_sprites.py`

Halo-free 4× upscaler for the extracted sprites: edge-bleeds opaque RGB into transparent pixels, upscales RGB via Lanczos and Real-ESRGAN (`realesrgan-ncnn-vulkan`, expected at `.scratch/tools/re/`), upscales the original alpha separately, then recombines. Writes `_lanczos4x.png` / `_esrgan4x.png` siblings next to each original under `graphics/extracted/`.

### FLUX.2 hybrid art

`docs/flux2-unit-art-workflow.md` is the full, battle-tested recipe for generating pose-faithful character renders of unique units with FLUX.2-dev (4-bit): dir05 sprite frame (pose anchor) + the in-game icon (color/identity) as the only two references, a researched-then-critiqued short prompt, a self-critique loop, then rembg background removal. Outputs land in `graphics/art/flux2_hybrid/` as three files per unit (`<slug>_idle_dir05_{bg,nobg,icon}.png`; 195 files at last count, 65 units). This directory is **git-tracked** (briefly untracked on 2026-06-10 for repo size; re-tracked 2026-06-11 by owner decision — the repo doubles as the art backup). **These renders are not yet wired into the webapp** — they are an art asset pipeline awaiting a consumer; when units get wired in, copy the chosen PNGs into `data/media/img/` and publish them with the rest of the media.

### How a new unit icon reaches the site

The icons the site actually serves are a separate, simpler chain (documented in `docs/superpowers/specs/2026-04-13-navy-column-design.md`, "Icons" section):

In short: look up the unit's `icon_id` in the dat, fetch the PNG from aoe2techtree.net, save it under `data/media/img/units/`, and register it in `icon_names` in `aoe2x/assets/presentation.json` (exposed to pages as `NAME_TO_ICON`) — the step-by-step checklist is [runbooks.md](runbooks.md) §5. Environment note the runbook glosses over: the dat lookup needs `genieutils-py`, which on this machine lives only in the conda base `python` (not the git-bash Python) — see section 8.

`NAME_TO_ICON` is not duplicated anywhere: it is read from the site catalog by `apps/web/static/js/constants.js`.

## 6. `reference/` corpus and `scripts/build_reference_docs.py`

`scripts/build_reference_docs.py` generates a markdown **validation corpus** under `reference/`: 189 `.md` files (53 civ files under `reference/civs/`, unit files under `reference/units/{generic,naval,unique}/`, plus `armor-classes.md` and `README.md`). Each file embeds a **DB Comparison table** cross-checking `data/golden/aoe2_reference.db` against two external sources: the SiegeEngineers `aoe2techtree` `data.json` (stats) and the Fandom wiki API (civ bonuses, unique techs), with ✅/❌/⚠️ markers per field. Its purpose is auditing — spotting where the local pipeline disagrees with authoritative external data after a patch.

Flags: no args = generate missing files only; `--force` = regenerate all; `--civ <Name>` / `--unit "<Name>"` = single target; `--dry-run` = report only. Wiki calls are rate-limited (0.5 s delay). Regenerate after a dat-file patch, new civs, or new combat mechanics. Pure helper functions are covered by `tests/test_reference_builder.py`.

## 7. `marketing/`

`marketing/` holds the promotion workflow for aoe2matchup.com: `launch-plan.md` (strategy), `reply-playbook.md` (reply templates and tone rules), `responded-threads.json` (dedup list of threads already answered — read it before drafting), `reports/` (biweekly deep-dive posts), and `replies/` (drafted replies per scouted batch). The end-to-end scout-and-reply process — Reddit JSON API scouting, forum browsing, dedup, simulation-driven drafting — is codified in the globally installed **`aoe2matchup-marketing-scout`** skill (`~/.claude/skills/aoe2matchup-marketing-scout/SKILL.md`); see `marketing/README.md` for the index.

## 8. Local prerequisites (not needed on the server)

| Tool | Needed for | Notes |
|------|-----------|-------|
| `empires2_x2_p1.dat` | Stage-1 extraction | Not in the repo (gitignored). Copy from a local AoE2:DE install: Windows Steam `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat` → `aoe2x/extract/` (macOS path in `README.md`) |
| `genieutils-py` | Parsing the dat (extraction, icon lookups, sprite lookups) | In **neither** requirements file — install manually. On this machine it lives in the conda base `python`, not the git-bash Python |
| PyPy 3 | Matchup batch sims: `aoe2x/batch/run_matchup_battles.py` (hard `_require_pypy()` guard) and `aoe2x/batch/rebuild_matchup_baseline.py` | CPython is ~10× too slow for the 491k-matchup baseline. The `.golden` capture does **not** need PyPy |
| Node.js | JS tests (section 3) and the Astro build | Node 24 for `apps/web` (`engines`), CI tests on 22 |
| ffmpeg | `apps/video/overlay/compose.py` video assembly | `brew install ffmpeg` on the Mac; the server needs none |
| Real-ESRGAN ncnn-vulkan | `graphics/upscale_sprites.py` | Local exe under `.scratch/tools/re/` |
| FLUX.2 diffusion env | FLUX.2 art workflow | Separate conda env (`visomaster`), RTX-class GPU; see `docs/flux2-unit-art-workflow.md` |
| AoE2ScenarioParser, rapidocr, cliclick, headless Chrome | `apps/video/` automation | macOS; see `apps/video/MAC_SETUP.md` |

## Update triggers

| If this changes | Update these sections |
|-----------------|----------------------|
| `vercel.json` services or `scripts/migration/build_service.sh` | §1 Deployment |
| `apps/backend/requirements.txt` | §1 Requirements files |
| New committed DB/JSON under `data/golden/` or `apps/backend/aoe2_api/data/`, or one removed | §2 Committed artifacts table |
| Branch strategy / Vercel environment mapping | §1 Environments, §2 Git workflow |
| Files added/removed in `tests/` | §3 test table |
| Sim behavior change (any engine/config/stat) | §3 Golden baseline — regenerate `.golden/baseline.json` |
| `capture_baseline.py` matchup list or seed | §3 Golden baseline |
| `apps/video/auto/` pipeline changes or new platform | §4 module map + status |
| Icon pipeline or `NAME_TO_ICON` location | §5 icon chain |
| FLUX.2 renders get wired into the webapp | §5 FLUX.2 (remove the "not yet wired" caveat) |
| `scripts/build_reference_docs.py` sources/flags or corpus size | §6 |
| New local-only tool requirement (PyPy, genieutils, etc.) | §8 |
