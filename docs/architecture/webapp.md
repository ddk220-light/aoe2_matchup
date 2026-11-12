# Webapp: Astro frontend and Flask API

*Last verified: 2026-11-12 · branch `chore/remove-flask-site` (after the `apps/website` deletion)*

This document covers the public website: the Astro frontend in `apps/web`, the Flask JSON API in `apps/backend`, and the build step that joins them (`scripts/migration/`). The old Flask website (`apps/website`: Jinja templates, page scripts, `static/`) has been deleted; its browser client survives only as research code in `legacy/client/`. Deployment is covered in [../vercel-deployment.md](../vercel-deployment.md), the active V3 runtime and module ownership in [CURRENT.md](CURRENT.md), and the simulation engines in [simulation-engines.md](simulation-engines.md).

## Overview

| Piece | Path | Role |
|---|---|---|
| Frontend | `apps/web/` (Astro 7, Node 24) | Every visitor-facing page. Layout `src/layouts/BaseLayout.astro`, header/footer `src/components/site/`, shared styles `src/styles/`, page code `src/features/<page>/`, routes `src/pages/`. Live public files (favicon, OG image, `constants.js`, `api_client.js`, `v3_sim_worker.js`) are in `static/{img,js}/` and published under `/static/...`. |
| API | `apps/backend/` (Flask 3, Python 3.13) | `app.py` is the Vercel entrypoint: it imports the sealed copy of `aoe2_api` from `runtime/`, adds `X-AoE2-*` release headers, rejects stale simulator versions with 409, serves `/_internal/release` and `/api/cached-advisor/<revision>/...`, and 404s every non-`/api/` path. The package `aoe2_api/` holds `web.py` (app + API routes), `routes/` (`battles.py`, `civilizations.py` blueprints), `services/` (battles, mechanics, rankings, civilizations, catalog, advisor, economy, database, release, seo) and `data/` (civilization JSONs). |
| Build | `scripts/migration/` | `build_service.sh` → `prepare_release.py`, which runs `export_data.py`, `export_civilization_pages.py`, `export_ranking_pages.py`, `export_simulator_page.py`, `export_remaining_pages.py` and the page/metadata/sitemap builders in `site/` (verbatim Jinja snippets in `site/templates/`), then seals `apps/web/src/generated/*.json`, `apps/web/public/` and `apps/backend/runtime/` and rewrites `vercel.json`. |

Page titles, meta, canonical links, JSON-LD, the about/ranking/simulator HTML fragments and the sitemap are computed at build time, not per request. There is no login, no session and no write path.

## Route inventory

### Pages (Astro, `apps/web/src/pages/`)

| Route | Source | Page code / data |
|---|---|---|
| `/` | `index.astro` | Battle Sim — `src/features/simulator/` (`enhance.js`, `selection.js`, `api.mjs`, `worker-session.js`, `playback.js`, `statistics.js`); data `generated/simulator-page.json` |
| `/units`, `/units/<line>` | `units/index.astro`, `units/[slug].astro` | Rankings — `src/features/rankings/` (`enhance.js`, `render.mjs`, `model.mjs`, `page-data.mjs`); data `generated/ranking-pages.json` |
| `/civilizations`, `/civilizations/<civ>` | `civilizations/index.astro`, `civilizations/[slug].astro` | `src/features/civilizations/`; data `generated/civilization-pages.json` (56 civs) |
| `/matchup-advisor` | `matchup-advisor.astro` | `src/features/advisor/` |
| `/matchups`, `/vs/<civ_a>/<unit_a>/<civ_b>/<unit_b>` | `matchups.astro`, `vs/[...path].astro` | `src/features/remaining/`; data `generated/remaining-pages.json` |
| `/patches`, `/patches/<build>`, `/patches/<build>/<civ>/<unit>` | `patches/index.astro`, `patches/[build].astro`, `patches/[...path].astro` | `generated/remaining-pages.json` |
| `/about` | `about.astro` | `generated/about.json` |
| `/robots.txt`, `/sitemap.xml` | `robots.txt.ts`, `sitemap.xml.ts` | sitemap built by `scripts/migration/site/sitemap.py` |

### Redirects and dynamic handlers

`/simulate` and `/replay` 301 to `/` (query preserved); `/civ`, `/civ/<civ>` and case variants of `/civilizations/<civ>` and `/units/<line>` 301 to the canonical URL. `/assets/...` and `/static/...` misses redirect to the Blob media store (`src/lib/media-redirect.ts`); unknown `/data/<ver>/...` and `/releases/...` files return a no-store 404 ("Reload the page"). `src/middleware.ts` answers non-GET/HEAD requests to page routes with 405 and adds `X-Robots-Tag: noindex, nofollow` off the public host.

### JSON APIs (`apps/backend/aoe2_api/web.py`)

| Route | Method | Data read | Consumed by |
|---|---|---|---|
| `/api/armor-classes` | GET | `aoe2_reference.db` | legacy client / external |
| `/api/ref/civ/<civ_name>` | GET | `aoe2_reference.db` + `aoe2_units.db` (`unit_verifications`) | snapshotted per simulator civ by `export_data.py` into `/data/<ver>/` |
| `/api/ref/stat-chain/<int:ref_unit_id>` | GET | `aoe2_reference.db` | `apps/web/src/features/rankings/enhance.js` (hover cards) |
| `/api/ref/combat-unit/<civ_name>/<unit_slug>` | GET | `aoe2_reference.db` (`ref_units` via `combat_unit_loader.build_combat_dict_from_ref`) | legacy client engine, lab/parity tooling |
| `/api/ref/unit-line/<line_slug>` | GET | `aoe2_reference.db` / `aoe2_reference_rankings.db` + `derived_data_v3.db` + `patches.db` (current build), via `get_unit_line_data()` | snapshotted per line by `export_data.py`; ranking pages call `get_unit_line_data()` at build time (`scripts/migration/site/sources.py`) |
| `/api/civ-power-units/<civ_name>` | GET | `civ_power_units/<build>.json` + `patches.db` | external/diagnostic |
| `/api/top-units/<civ_name>` | GET | `civ_top_units.json`, falling back to live derivation from `aoe2_reference.db` | external/diagnostic |
| `/api/top-unit/<civ_name>/<line>` | GET | same as above | external/diagnostic |
| `/api/matchup-recommendations/<civ_a>/<civ_b>` | GET | `best_units.py` (reads `aoe2_reference.db`, `derived_data.db`, `pool_scores.db`) + on-the-fly sims | advisor (`apps/backend/app.py` wraps both in `/api/cached-advisor/...`) |
| `/api/matchup-sims` | POST | same as above; runs live `simulate_battle()` cross-sims | advisor (`apps/backend/app.py` wraps both in `/api/cached-advisor/...`) |
| `/api/release` | GET | release identity | simulator (`src/features/simulator/api.mjs`) |
| `/api/assets/catalog` | GET | frozen public catalog | `apps/web/static/js/api_client.js` |
| `/api/advisor-catalog`, `/api/advisor-matchups/<civ>`, `/api/advisor-evidence/<id>` | GET | `civ_matchups_first_pass.db` | advisor (`src/features/advisor/view.js`; catalog/matchups also snapshotted by `export_data.py`) |
| `/api/economy`, `/api/economy/<civ>` | GET | `data/army_economics/army_context.jsonl.gz` via `services/economy.py` (canonical bytes; unknown civ → 404 `{"error":"Unknown civilization"}`) | not read by any page yet; snapshotted by `export_data.py` (economy component) for `src/features/economy/loader.mjs` |
| `/api/civilizations/<civ>` | GET | civilization analysis service | snapshotted per civ by `export_data.py` (`aoe2_api/routes/civilizations.py`) |
| `/api/v3/arena-preview`, `/api/v3/battle-config` | GET / POST | `aoe2_reference_simulation.db` via `services/battles.py` + `services/mechanics.py` | simulator (`src/features/simulator/enhance.js`) → `v3_sim_worker.js` |

Input validation: `_validate_civ_name()` (`aoe2_api/web.py`) checks against `_valid_civs()` — an `lru_cache`d frozenset of `DISTINCT civ_name` from `aoe2_reference.db` (53 civs; the simulator and rankings validate against the 56-civ `_sim_civs()` roster). `_validate_age()` accepts only `imperial` (Imperial-only data model since 2026-06-11; `age=castle` is a clean 400). Civ names are case-sensitive title-case.

The replay blueprint (`aoe2x/replay/blueprint.py`) is not mounted; see [replay.md](replay.md).

## Central registries

| Registry | Lives in | Contents | Consumers | If you forget to update it |
|---|---|---|---|---|
| `UNIT_LINES` | `aoe2x/sim/unit_lines.py` | 26 keys: 21 unit lines (with per-civ `unique_units` slug pairs) + 5 aggregate pseudo-lines | 12 modules, incl. `aoe2_api/web.py`, `aoe2_api/services/rankings.py`, `scripts/migration/export_data.py`, `scripts/migration/site/sources.py`, `aoe2x/advisor/best_units.py`, `aoe2x/rank/*`, `aoe2x/batch/run_matchup_battles.py` | New unit never appears in rankings, matchup advisor, top-units, or any derived score |
| `UNIT_LINES` (JS) | `apps/web/src/features/rankings/render.mjs` | Live rankings-page copy (names, buildings, sub-lines) | `rankings/enhance.js`, the SSR ranking tables | Line missing or mislabeled on `/units` |
| `CIV_MISSING_UNITS` | `aoe2x/sim/unit_lines.py` | `(civ, slug)` pairs the extraction pipeline emits but the civ cannot actually build | `/api/ref/unit-line`, `derive_unit_rankings.py`, `run_matchup_battles.py` | Phantom units show up in rankings and get sim-scored |
| Site catalog (`ENABLED_CIVS`, `NAME_TO_ICON`, `UNIQUE_BUILDING`) | `site_catalog()` in `aoe2_api/services/catalog.py` = civ roster of `aoe2_reference_simulation.db` (56) + `aoe2x/assets/presentation.json` (`icon_names` 230, `unique_buildings` 13); injected as `window.SITE_CATALOG` and read by `apps/web/static/js/constants.js` | Picker civs, icon names, non-Castle unique buildings | simulator, rankings, civilization pages (via `getIconUrl()`) | Unit without icon / grouped under Castle; civ unselectable |
| Civ emblems | `CIV_EMBLEM_BASE` in `apps/web/static/js/constants.js` | aoe2companion CDN | civilization and rankings pages | n/a (third-party hosted) |
| Unit display names | `aoe2_reference*.db` `ref_units.unit_name` | The actual unit a civ fields per slug/age | all API payloads and exports | Fix in the pipeline — see [data-pipeline.md](data-pipeline.md) |
| Server-side civ list | `_valid_civs()` / `_sim_civs()` in `aoe2_api/web.py` | Authoritative civ sets for validation and the sitemap | every validated route | n/a — derived from the DBs. The pipeline list `ORIGINAL_13_CIVS` (`aoe2x/dbgen/config_constants.py`) derives from `aoe2x.extract.extract_constants.CIV_NAMES` |

### Slug conventions

- Slugs are lowercase with underscores. Standard line units use plain names: `knight`, `halberdier`, `heavy_cav_archer`.
- Civ-locked unique units carry the civ as a **suffix**: `huskarl_goths`, `cataphract_byzantines`. Multi-word civ names keep underscores in the suffix.
- Regional uniques shared by several civs carry **no** suffix: `champi_warrior`, `slinger`, `eagle_warrior`, `genitour`.
- Elite tiers use the `elite_` **prefix** (`elite_huskarl_goths`); synthetic Imperial-age entries for units with no upgrade use the `imp_` **prefix** (`imp_elite_skirm`, `imp_slinger`) — it is a prefix, not a `_imp` suffix (see `_token_of_slug()` in `scripts/migration/site/patches.py`, which strips `imp_elite_`, `elite_`, `imp_`).
- Two slugs contain parentheses: `ratha_(melee)_bengalis`, `ratha_(ranged)_bengalis`.

## Build-time page data

`prepare_release.py` imports `aoe2_api.web` and the builders in `scripts/migration/site/` (`config.py` env policy, `metadata.py` head/JSON-LD, `pages.py` page bodies, `patches.py` patch pages and the Battle Sim deep link, `sitemap.py`, `sources.py`, `content.py`, `templating.py`) and writes `apps/web/src/generated/` (`about.json`, `civilization-pages.json`, `ranking-pages.json`, `simulator-page.json`, `remaining-pages.json`, `release.json`, `public-catalog.json`, `data-manifest.json`, `media-manifest.json`, `gallery.json`). Astro pages read only these JSON files; changing a page title or JSON-LD means editing the builder (or its verbatim snippet in `scripts/migration/site/templates/`), not an Astro page.

## How site data is published (standard for new data components)

Data that pages load at run time is published twice from the same bytes, and a
new data component should follow this pattern (the Matchup Advisor and army
economics are the examples):

1. **API route** in `aoe2_api/web.py` backed by a service in
   `aoe2_api/services/` that reads a committed artefact from the packaged
   runtime (`data/golden/civ_matchups_first_pass.db` for the advisor,
   `data/army_economics/army_context.jsonl.gz` for economy; a file outside
   `data/golden` must be added to `backend_sources` in `prepare_release.py`).
   One document per civilization (`/api/advisor-matchups/<Civ>`,
   `/api/economy/<Civ>`) plus a shared one (`/api/advisor-catalog`,
   `/api/economy`). Civ names are case-sensitive; unknown → 404
   `{"error": "Unknown civilization"}`. API responses are `Cache-Control: no-store`
   (set by `apps/backend/app.py`).
2. **Static files**: `scripts/migration/export_data.py` calls those routes with
   the test client and writes canonical JSON (sorted keys, compact, UTF-8) to
   `/data/<version>/<name>.json`, where `<name>` is the lower-case civ name or the
   shared file's name and `<version>` is the SHA-256 of the component's file
   hashes. Economy responses are already canonical, so the static file and the API
   body are byte-identical (asserted by the export and `verify_build.py`).
3. **Release registration**: the component (files with url/sha256/bytes/gzip_bytes,
   roster, version) lands in `apps/web/src/generated/data-manifest.json`,
   `release.json` and `/data/release.json`; `validate_exports.mjs` checks every
   file against `$defs/<component>` in `scripts/migration/schemas/projections.json`;
   `check_release.mjs` checks the seal (including every component file's hash);
   `prepare_release.py` gives every `/data/<version>/` path a one-year immutable
   `Cache-Control` in the generated `vercel.json` headers.
4. **Browser loader**: the page passes `data.components.<component>.files` into
   its config and fetches `files[civ.toLowerCase()].url`, falling back to the API
   URL; one cached promise per document, dropped on failure so it can be retried
   (`src/features/advisor/view.js`, `src/features/economy/loader.mjs`).

Keep each component's inputs separate: a component's version hashes only its own
files, so adding or changing one never moves another's `/data/<version>/` URLs
(economics deliberately lives outside `data/golden/` and `aoe2x/js_simulation/`,
which the simulator and engine versions hash). Where the browser computes from
the data (economy), the Python code stays the reference and a committed fixture
pins the JS port to it (`tests/economy/matchup-parity.test.mjs`).

## Static and media assets

| Path | Role |
|---|---|
| `apps/web/static/js/constants.js` | Shared constants over `window.SITE_CATALOG` + `getIconUrl()` and helpers |
| `apps/web/static/js/api_client.js` | `apiGet`/`apiPost`/`apiRequest` fetch wrappers with timeout and `ApiError` |
| `apps/web/static/js/v3_sim_worker.js` | Simulator Web Worker: runs `aoe2x/js_simulation/src/` from the sealed `/releases/engine/<version>/v3-runtime/` copy |
| `apps/web/static/img/` | `favicon.png`, `og-default.png` |
| `/static/js/unit_sprites.js` | Written by `prepare_release.py` from the public catalog (no source file) |
| `data/media/{img,anim,data}` | Authoring copy of unit icons, sprites, animations and the `unit_sprites.json` / `unit_anims.json` / `anim_sheets.json` manifests (`aoe2x.paths.MEDIA_DIR`); served to visitors from Blob, verified by SHA-256 manifests |
| `legacy/client/{js,css,lab}` | The retired client (engine, page scripts, CSS, lab harness; `aoe2x.paths.LEGACY_CLIENT_DIR`) — tests, parity and calibration only, never published |

## Database access

All connections are short-lived read-only SQLite connections (`connect_readonly()` in `aoe2_api/services/database.py`, `mode=ro` + `query_only`) with `Row` factory; there is no pooling and no ORM. On Vercel the databases are read from the sealed `apps/backend/runtime/data/golden/` copy.

| Helper | DB file | Tables read by routes |
|---|---|---|
| `get_db()` (`aoe2_api/web.py`) | `data/golden/aoe2_units.db` | `unit_verifications` (verified badges in `/api/ref/civ`) |
| `get_ref_db()` (`aoe2_api/web.py`) | `data/golden/aoe2_reference.db` | `ref_units`, `ref_techs_applied`, `ref_stat_chain`, `ref_special_effects`, `ref_projectiles`, `armor_classes` |
| `get_sim_ref_db()` / `get_rankings_ref_db()` (`aoe2_api/web.py`) | `data/golden/aoe2_reference_simulation.db` / `aoe2_reference_rankings.db` | 56-civ rosters for the V3 battle config, site catalog and rankings |
| `get_rankings_derived_db()` (`aoe2_api/web.py`) | `data/golden/derived_data_v3.db` | published ranking scores (see [derived-data.md](derived-data.md)) |
| `patches_db.get_current_build()` | `data/golden/patches.db` | `patches` etc. `get_current_build()` is the single build resolver every score lookup goes through; patch pages are built at build time by `scripts/migration/site/patches.py` |
| advisor service (`aoe2_api/services/advisor.py`) | `data/golden/civ_matchups_first_pass.db` | `/api/advisor-*` |
| economy service (`aoe2_api/services/economy.py`) | `data/army_economics/army_context.jsonl.gz` (gzip JSON Lines, not SQLite; `aoe2x/economy/artefact.py`) | `/api/economy*` |
| `best_units.py` module paths | `aoe2_reference.db`, `derived_data.db`, `pool_scores.db` | advisor recommendations and percentiles |

JSON artifacts read at runtime: `civ_power_units/<build>.json` (per-build only — the legacy flat `civ_power_units.json` fallback was removed) and `civ_top_units.json`. (`battle_scores.json` and its old Flask loader were deleted — role scores come from `derived_data.db`.) Matchup DBs live outside the repo at `D:/AI/` (the committed 3.9 MB stub was removed 2026-06-11); they and `battle_cache.json` are **not** read by any route — they feed the offline derive jobs only.

There is **no `app_data.db`** — older docs mention it, but the file does not exist; `unit_verifications` plus dormant `comments`/`simulation_comments`/`combat_results` tables live inside `aoe2_units.db`, and no comment routes exist anymore. The `unit_stats` table in `aoe2_units.db` is likewise not queried by any route — combat stats come from `ref_units`.

## Environment variables and config

| Variable | Read in | Default / effect |
|---|---|---|
| `SITE_URL` | `scripts/migration/site/config.py`, `aoe2_api/web.py` | `https://aoe2matchup.com`; canonical URLs, sitemap, OG tags |
| `SEARCH_INDEXING` | same | indexing policy (`apps/backend/app.py` forces `false` for the API) |
| `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION` | `scripts/migration/site/config.py` | verification `<meta>` tags when set |
| `SOCIAL_DISCORD_URL`, `SOCIAL_YOUTUBE_URL`, `SOCIAL_INSTAGRAM_URL` | `scripts/migration/site/config.py` | footer links and JSON-LD `sameAs` (YouTube has a default) |

These are read when the release is built, so a change needs a new deployment. `RAILWAY_ENVIRONMENT_NAME` (a Railway-era input) is still consulted by the indexing policy for compatibility.

## Cross-file sync rules

1. **Deep-link contract**: `battle_sim_deep_link()` in `scripts/migration/site/patches.py` builds `?civ1=&unit1=&civ2=&unit2=&...&autorun=1`; `readSimParams()` in `apps/web/src/features/simulator/params.mjs` parses the same keys. Change one → change the other.
2. **Engine parity**: behavior changes in the Python engines usually need a mirrored change in the V3 engine (`aoe2x/js_simulation/src/`); edits to the retired `legacy/client/js/engine/` must re-run `node tools/simjs/parity_check.mjs`.
3. **New unique unit**: `UNIT_LINES` entry (`unit_lines.py`, and `render.mjs` if it changes a line) + `icon_names` / `unique_buildings` in `aoe2x/assets/presentation.json` + icon in `data/media/img/units/` (published to Blob).
4. **New civ**: appears automatically once in the reference DBs (the catalog is derived); civilization page copy lives in `apps/backend/aoe2_api/data/`.
5. **`*_LINE_SLUGS` drift** between `aoe2_api/services/rankings.py` and `aoe2x/rank/compute_battle_scores.py` (retired) — touch role-scoring categories in both places until they are consolidated.
6. **Presentation changes go only in `apps/web`**; after editing, rerun `python scripts/migration/prepare_release.py` before `npm run build --prefix apps/web`.

## Update triggers

| If this changes | Update these sections |
|---|---|
| API routes added/removed in `aoe2_api/web.py`, `routes/` or `apps/backend/app.py` | Route inventory |
| Astro pages or `src/features/*` added | Pages table |
| `unit_lines.py`, `render.mjs` or `presentation.json` registries | Central registries |
| A new DB file or JSON artifact read by the API or the exports | Database access, Build-time page data |
| New `os.environ` reads in the API or `scripts/migration/site/config.py` | Environment variables |
