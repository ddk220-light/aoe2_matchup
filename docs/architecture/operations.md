# Operations: Deployment, Testing, and Offline Tooling

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This document covers how the webapp ships to Railway, how the repo is tested, and the offline tooling that lives alongside the webapp (scenario recording, sprite/art extraction, the reference corpus, and marketing). For what the webapp itself does see [webapp.md](webapp.md); for how the databases it serves are built see [data-pipeline.md](data-pipeline.md) and [derived-data.md](derived-data.md).

## 1. Deployment (Railway)

The app is a Flask + gunicorn service deployed on Railway behind `aoe2matchup.com`. All deployment configuration in the repo lives in two files.

### `railway.json`

| Key | Value |
|-----|-------|
| `build.buildCommand` | `pip install -r webapp/requirements.txt` |
| `build.watchPatterns` | `["webapp/**"]` — pushes that touch only files outside `webapp/` do **not** trigger a redeploy |
| `deploy.startCommand` | `cd webapp && gunicorn app:app --workers 2 --timeout 300 --graceful-timeout 300` |
| `deploy.restartPolicyType` | `ON_FAILURE`, max 10 retries |

The long timeouts exist because some API endpoints run batches of battle simulations synchronously. Note the `watchPatterns` consequence: changes to `analysis/`, `extraction/`, `tests/`, or `docs/` alone will not redeploy — the deployed app only changes when something under `webapp/` changes (which includes the committed databases, see below).

### `webapp/Procfile`

Contains a single line, `web: gunicorn app:app`. Railway's `startCommand` in `railway.json` takes precedence, so the Procfile is a fallback/legacy artifact (no `--workers`/`--timeout` flags). If you change gunicorn flags, change them in `railway.json`; the Procfile is not what production runs.

### Requirements files

There are two requirements files with different purposes:

| File | Contents | Used by |
|------|----------|---------|
| `requirements.txt` (root) | `flask==3.0.0`, `gunicorn==21.2.0` | Minimal local install; **not** what Railway installs |
| `webapp/requirements.txt` | `flask==3.0.0`, `gunicorn==21.2.0`, `numpy`, `requests>=2.31.0`, `flask-cors>=4.0.0`, `mgz` (pinned fork, see below), `Pillow>=10.0.0`, `imageio-ffmpeg>=0.4.9` | Railway build (`railway.json` buildCommand) |

The `mgz` dependency is pinned to a fork tarball, not PyPI: `mgz @ https://github.com/sanduckhan/aoc-mgz/archive/a1683d8eeca67796ced0d0c05b145420c97d862d.tar.gz`. The fork adds AoE2:DE save-version 67.x support (current game builds) that is not yet upstream (aoc-mgz PR #141). It powers the replay analyzer feature — see [replay.md](replay.md). `Pillow` + `imageio-ffmpeg` support server-side WebM clip export (the imageio-ffmpeg wheel bundles an ffmpeg binary, so the slim Railway image needs no `apt install`).

Notably absent from both files: `genieutils-py` (needed only for stage-1 extraction, never on the server — see Local prerequisites) and `pytest`.

### Environments and branch mapping

Two long-lived branches map to two Railway environments. The mapping itself is Railway dashboard configuration, not in the repo:

| Branch | Railway environment | Role |
|--------|--------------------|------|
| `main` | production (`aoe2matchup.com`) | Frozen; only updated by fast-forward promotion from `staging`. Auto-deploys on push. |
| `staging` | staging URL | Default working branch; auto-deploys on every push. |

### How data ships

There is no database server. All data the app serves is **SQLite files and JSON committed to git inside `webapp/`** — each environment deploys whatever data files are on its branch. Shipping new data means: regenerate locally → commit on `staging` → smoke-test on the staging URL → promote. Because of `watchPatterns`, committing a regenerated `webapp/*.db` is itself enough to trigger a redeploy.

### Environment variables

All optional, read in `webapp/app.py`: `PORT` (dev server; Railway injects its own — local convention `PORT=5002 python webapp/app.py`), `SITE_URL`, `CONTACT_FORM_ENDPOINT`, and the `SOCIAL_*` footer links (behavior covered by `tests/test_footer.py`). The full table with `app.py` line numbers is in [webapp.md](webapp.md), "Environment variables and config".

## 2. Git workflow and committed artifacts

Rules (full rationale in `CLAUDE.md`, verified still accurate except where noted):

1. **All work lands on `staging`** (or short-lived feature branches off it). Never commit directly to `main`.
2. **Promotion is fast-forward only**: `git checkout main && git merge --ff-only staging && git push origin main`. If `--ff-only` refuses, `main` has diverged — stop and investigate, do not force.
3. A push to `main` is a production deploy. Never push `main` without explicit confirmation.

### Committed data artifacts (ground truth from `git ls-files`)

These binary/data files are committed **on purpose** — they are how the deployed app gets its data:

| File | Size | What it is |
|------|------|------------|
| `webapp/aoe2_units.db` | 2.0 MB | Main flat `unit_stats` DB (stage 3 output) |
| `webapp/aoe2_reference.db` | 4.5 MB | Audit-trail reference DB (stage 2 output) |
| `webapp/derived_data.db` | 14.5 MB | Derived rankings/advisor recommendations (battle scores live here now) |
| `webapp/matchup_db.db` | 3.9 MB | Raw 1v1 matchup outcomes (multi-seed baseline) |
| `webapp/pool_scores.db` | 4.4 MB | Pool-score data |
| `webapp/patches.db` | 6.3 MB | Patch/build history for the patches pages |
| `webapp/civ_power_units.json` + `webapp/civ_power_units/{170934,177723}.json` | ~1.8 MB each | Per-build civ power-unit data |
| `webapp/civ_top_units.json`, `webapp/train_times.json` | small | Misc serving data (`battle_scores.json` was deleted — scores moved into `derived_data.db`) |
| `.golden/baseline.json` | 208 KB | Golden sim regression baseline (section 3) |
| `tests/fixtures/berserker_matchups.db` | test fixture | |
| `scenario_builder/auto/unique_units.json`, `marketing/responded-threads.json` | small | Tooling state |

**Stale-doc warning:** `CLAUDE.md` rule 6 says "Don't commit `webapp/matchup_db.db` (200+ MB sim cache)". That described an older incarnation; the current `webapp/matchup_db.db` **is committed** (3.9 MB) and is required serving data. Treat the file like the other committed DBs.

Deliberately **not** committed (`.gitignore`): `extraction/empires2_x2_p1.dat` and `extraction/extracted_data/`, `graphics/game_raw_files/` (19 GB raw sprite dump), `webapp/battle_cache.json`, `webapp/battle_scores.db`, `webapp/matchup_votes.jsonl`, patch-pipeline intermediates (`webapp/aoe2_reference_*.db`, `webapp/changed_units_*.json`, `webapp/*.db.bak`, `extraction/extracted_data_prev/`), and scratch dirs (`.scratch/`, `tmp/`, `.old/`).

## 3. Testing

### pytest

Config is `pytest.ini`: `testpaths = tests`, `python_files = test_*.py`. `tests/conftest.py` prepends `webapp/` to `sys.path` (tests import webapp modules bare, e.g. `from best_units import ...`) and provides a Flask test `client` fixture. Run with `pytest` from the repo root. There are 25 Python test files plus 2 Node.js test files:

| File | Covers |
|------|--------|
| `test_simulations.py` | Golden regression: `get_matchup_sims()` vs `.golden/baseline.json` (see below) |
| `test_position_sim_abilities.py` | Special abilities in the position-based engine `webapp/simulation_real.py` |
| `test_battle_outcome.py` | `BattleOutcome` contract: `signed_score`, `average_outcomes`, `simulate_real_battle` return shape |
| `test_resource_per_kill.py` | Per-resource kill-bonus accounting in `simulation_real.py` |
| `test_value_lost.py` | HP-weighted value-lost computation in `simulation_real.py` |
| `test_sim_outcome_cache.py` | Outcome cache + unit fingerprinting (`webapp/sim_outcome_cache.py`) |
| `test_sim_version.py` | `compute_sim_version()` hash changes when sim source changes |
| `test_matchup_db.py` | `webapp/matchup_db.py` schema/insert/upsert/version checks |
| `test_matchup_diff.py` | `matchup_diff` snapshot/diff detects verdict flips between builds |
| `test_ref_diff.py` | `ref_diff` detects changed unit fields between reference DBs |
| `test_unit_ranking_derive.py` | `derive_unit_rankings` writes role/composite scores to `derived_data.db` |
| `test_advisor_derive.py` | `derive_advisor_recs` recommends the highest-mean-score unit |
| `test_naval_rankings.py` | Battle-score queries against `derived_data.db` (naval columns) |
| `test_versioning.py` | Build-number versioning of derived artifacts, fallback chains, migrations |
| `test_pool_scores_db.py` / `_lib.py` / `_query.py` | Unit tests for the three pool-score modules |
| `test_pool_scores_api.py` | `/api/ref/unit-line` pool-score attachment (skips if `pool_scores.db` missing) |
| `test_pool_scores_integration.py` | End-to-end derived-score regression (Viking Elite Berserk) |
| `test_infantry_scoring.py` | Militia-line role benchmarks in `webapp/compute_battle_scores.py` |
| `test_siege_scoring.py` | Siege-vs-castle scoring helpers (`_simulate_siege_vs_castle`, TTK math, castle target table) |
| `test_patches_db.py` / `test_patch_routes.py` | `patches_db` helpers and the `/patches` pages |
| `test_reference_builder.py` | Pure functions of `scripts/build_reference_docs.py` (section 6) |
| `test_footer.py` | Env-driven footer/contact/social rendering (section 1 env vars) |

### Golden baseline (`.golden/`)

`.golden/capture_baseline.py` snapshots `get_matchup_sims()` (from `webapp/best_units.py`) for 10 fixed civ pairs × 2 ages = **20 entries** into `.golden/baseline.json` (committed). Determinism comes from `random.seed(GOLDEN_SEED)` — `GOLDEN_SEED = 20260411`, re-seeded before *each* matchup so entries are insensitive to iteration order. A `_normalize` pass drops non-deterministic keys (`elapsed_ms`, `timing`, `generated_at`) and rounds floats to 6 decimal places. `tests/test_simulations.py` re-runs each entry with the same seed and asserts byte-equality with the baseline.

**Regenerate** (`python .golden/capture_baseline.py`, ~30 s, CPython is fine) whenever simulation behavior changes *intentionally* — any sim-logic, stat, or config change makes `test_golden_regression` fail until you do. Commit the regenerated `baseline.json` on `staging` like source. (The script docstring still mentions a direct `simulate_battle()` section; `main()` only captures `matchup_sims` — the docstring is stale.)

### JavaScript tests (frontend parity)

Not collected by pytest; run manually with Node (v20 available locally):

- `node tests/test_frontend_projectile_miss.js` — brace-matches the **live** `BattleUnit` class out of `webapp/static/js/simulate.js` (no hand-copied snapshot) and exercises `fireProjectile` under mocked browser globals, asserting the frontend canvas sim mirrors the backend miss/graze model in `webapp/simulation_real.py`.
- `node tests/test_sim_params.js` — URL-parameter parsing in `webapp/static/js/sim_params.js` (deep-link autorun).

## 4. `scenario_builder/` — validating the sim against the real game

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
| `overlay/` | Video composition: `overlay_data.py` (stats from `webapp/aoe2_reference.db`), `render_card.py` (HTML → headless Chrome → PNG intro/outro cards), `hud.py` (Pillow live HUD), `results.py` (sim-predicted timeline), `video_extract.py` (OCR survivor counts from footage), `compose.py` (ffmpeg assembly), `make_real_video.py` (one recording → titled video) |
| `recorder/` | `sck_record.swift` — macOS ScreenCaptureKit recorder (video + system audio, 1920×1248@60) with `build.sh`/`record.sh` |

**Status:** past the original de-risk spike (the Fire Archer vs Jian spike scenarios are still committed at the top level, plus `spike_runs/` outputs). Per `scenario_builder/auto/README.md` the hands-off pipeline is verified: a 2-matchup batch produced both titled videos with no human interaction, ~4 min each. The composition is now template-based and OCR-free for results (OCR is only used for screen-state detection).

**Platform constraints:** the automation half is **macOS-only** — it depends on `cliclick` (Homebrew), `screencapture`, ScreenCaptureKit, and the Mac-native AoE2:DE install. The launching Terminal needs **both** Screen Recording and Accessibility permission (System Settings → Privacy & Security); Screen Recording alone does not allow input injection. The game's scenario folder is dedicated to staged runs (exactly one file at a time, so UI navigation needs no search). The game launches via Steam app id 813780. Scenario *generation* (`make_scenario.py`, `build_run.py`) is cross-platform Python. Setup/handoff notes: `scenario_builder/MAC_SETUP.md`.

## 5. `graphics/` — sprites, upscaling, and FLUX.2 art

### Sprite extraction: `graphics/sld_decode.py`

A from-scratch decoder for AoE2:DE's **SLD v4** sprite format (BC1/DXT1-compressed, used since ~build 66692), implemented from the openage spec because no headless decoder was installable. It decodes the MAIN graphics layer (RGB + transparency from skipped blocks and BC1 1-bit alpha) and **skips** the shadow, damage, and player-color layers — player-color areas render in their baked-in default tint, which is fine for portraits/reference. Flags: `--frame N`, `--all`, `--max M`, `--angle-stride S` (one image per facing), `--crop`, `--margin N`. Prefer `_x2.sld` variants for double resolution. Raw `.sld` inputs live in `graphics/game_raw_files/` (gitignored, ~19 GB local dump); to find a unit's `.sld` and frame layout, read the dat's graphic entries via genieutils (recipe in the module docstring — conda `python`, see section 8). Decoded PNGs land in `graphics/extracted/<slug>/`. The small original sprites (~3.4 MB) are git-tracked; the regenerable `_lanczos4x`/`_esrgan4x` upscale variants were untracked + gitignored on 2026-06-10 (kept on disk; older versions remain in git history).

### Upscaling: `graphics/upscale_sprites.py`

Halo-free 4× upscaler for the extracted sprites: edge-bleeds opaque RGB into transparent pixels, upscales RGB via Lanczos and Real-ESRGAN (`realesrgan-ncnn-vulkan`, expected at `.scratch/tools/re/`), upscales the original alpha separately, then recombines. Writes `_lanczos4x.png` / `_esrgan4x.png` siblings next to each original under `graphics/extracted/`.

### FLUX.2 hybrid art

`docs/flux2-unit-art-workflow.md` is the full, battle-tested recipe for generating pose-faithful character renders of unique units with FLUX.2-dev (4-bit): dir05 sprite frame (pose anchor) + the in-game icon (color/identity) as the only two references, a researched-then-critiqued short prompt, a self-critique loop, then rembg background removal. Outputs land in `graphics/art/flux2_hybrid/` as three files per unit (`<slug>_idle_dir05_{bg,nobg,icon}.png`; 195 files at last count, 65 units). As of 2026-06-10 this directory is **untracked + gitignored** (kept on disk; pre-2026-06-10 versions remain in git history) to stop repo growth. **These renders are not yet wired into the webapp** — they are an art asset pipeline awaiting a consumer; when units get wired in, copy the chosen PNGs into `webapp/static/img/` and commit them there.

### How a new unit icon reaches the site

The icons the site actually serves are a separate, simpler chain (documented in `docs/superpowers/specs/2026-04-13-navy-column-design.md`, "Icons" section):

In short: look up the unit's `icon_id` in the dat, fetch the PNG from aoe2techtree.net, save it under `webapp/static/img/units/`, and register it in `NAME_TO_ICON` — the step-by-step checklist is [runbooks.md](runbooks.md) §5. Environment note the runbook glosses over: the dat lookup needs `genieutils-py`, which on this machine lives only in the conda base `python` (not the git-bash Python) — see section 8.

Both `CLAUDE.md` and `.claude/skills/webapp-architecture/SKILL.md` still claim `NAME_TO_ICON` is duplicated across four HTML templates — that is obsolete; the templates contain no copy of it.

## 6. `reference/` corpus and `scripts/build_reference_docs.py`

`scripts/build_reference_docs.py` generates a markdown **validation corpus** under `reference/`: 189 `.md` files (53 civ files under `reference/civs/`, unit files under `reference/units/{generic,naval,unique}/`, plus `armor-classes.md` and `README.md`). Each file embeds a **DB Comparison table** cross-checking `webapp/aoe2_reference.db` against two external sources: the SiegeEngineers `aoe2techtree` `data.json` (stats) and the Fandom wiki API (civ bonuses, unique techs), with ✅/❌/⚠️ markers per field. Its purpose is auditing — spotting where the local pipeline disagrees with authoritative external data after a patch.

Flags: no args = generate missing files only; `--force` = regenerate all; `--civ <Name>` / `--unit "<Name>"` = single target; `--dry-run` = report only. Wiki calls are rate-limited (0.5 s delay). Regenerate after a dat-file patch, new civs, or new combat mechanics. Pure helper functions are covered by `tests/test_reference_builder.py`.

## 7. `marketing/`

`marketing/` holds the promotion workflow for aoe2matchup.com: `launch-plan.md` (strategy), `reply-playbook.md` (reply templates and tone rules), `responded-threads.json` (dedup list of threads already answered — read it before drafting), `reports/` (biweekly deep-dive posts), and `replies/` (drafted replies per scouted batch). The end-to-end scout-and-reply process — Reddit JSON API scouting, forum browsing, dedup, simulation-driven drafting — is codified in the globally installed **`aoe2matchup-marketing-scout`** skill (`~/.claude/skills/aoe2matchup-marketing-scout/SKILL.md`); see `marketing/README.md` for the index.

## 8. Local prerequisites (not needed on the server)

| Tool | Needed for | Notes |
|------|-----------|-------|
| `empires2_x2_p1.dat` | Stage-1 extraction | Not in the repo (gitignored). Copy from a local AoE2:DE install: Windows Steam `C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat` → `extraction/` (macOS path in `README.md`) |
| `genieutils-py` | Parsing the dat (extraction, icon lookups, sprite lookups) | In **neither** requirements file — install manually. On this machine it lives in the conda base `python`, not the git-bash Python |
| PyPy 3 | Matchup batch sims: `webapp/run_matchup_battles.py` (hard `_require_pypy()` guard) and `webapp/rebuild_matchup_baseline.py` | CPython is ~10× too slow for the 491k-matchup baseline. The `.golden` capture does **not** need PyPy |
| Node.js | The two JS tests (section 3) | v20 verified locally |
| ffmpeg | `scenario_builder/overlay/compose.py` video assembly | `brew install ffmpeg` on the Mac; the *server* needs none (imageio-ffmpeg wheel bundles one) |
| Real-ESRGAN ncnn-vulkan | `graphics/upscale_sprites.py` | Local exe under `.scratch/tools/re/` |
| FLUX.2 diffusion env | FLUX.2 art workflow | Separate conda env (`visomaster`), RTX-class GPU; see `docs/flux2-unit-art-workflow.md` |
| AoE2ScenarioParser, rapidocr, cliclick, headless Chrome | `scenario_builder/` automation | macOS; see `scenario_builder/MAC_SETUP.md` |

## Update triggers

| If this changes | Update these sections |
|-----------------|----------------------|
| `railway.json` (build/start command, watchPatterns) | §1 Deployment |
| `webapp/requirements.txt` (esp. the mgz fork pin) | §1 Requirements files |
| New committed DB/JSON under `webapp/`, or one removed | §2 Committed artifacts table |
| Branch strategy / Railway env mapping | §1 Environments, §2 Git workflow |
| Files added/removed in `tests/` | §3 test table |
| Sim behavior change (any engine/config/stat) | §3 Golden baseline — regenerate `.golden/baseline.json` |
| `capture_baseline.py` matchup list or seed | §3 Golden baseline |
| `scenario_builder/auto/` pipeline changes or new platform | §4 module map + status |
| Icon pipeline or `NAME_TO_ICON` location | §5 icon chain |
| FLUX.2 renders get wired into the webapp | §5 FLUX.2 (remove the "not yet wired" caveat) |
| `scripts/build_reference_docs.py` sources/flags or corpus size | §6 |
| New local-only tool requirement (PyPy, genieutils, etc.) | §8 |
