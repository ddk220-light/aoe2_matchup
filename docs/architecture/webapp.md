# Webapp: Flask app and frontend

*Last verified: 2026-06-09 · game build 177723 · branch `staging`*

This document covers the Flask application in `apps/website/app.py`, its routes, the templates, the shared static assets, and the central registries the frontend depends on. The replay subsystem is only summarized here — see [replay.md](replay.md). Simulation engine internals (`aoe2x/sim/simulation.py`, `aoe2x/sim/simulation_real.py`) are covered in [simulation-engines.md](simulation-engines.md), the offline scoring jobs that produce `derived_data.db` / `pool_scores.db` in [derived-data.md](derived-data.md), and the DB-building pipeline in [data-pipeline.md](data-pipeline.md).

## Overview

`apps/website/app.py` (1,516 lines) defines **24 routes**: 8 HTML pages, 3 permanent redirects, 3 SEO endpoints, and 10 JSON APIs. The replay blueprint (`aoe2x/replay/blueprint.py`, registered at import time when its optional dependencies are available) adds 7 more routes under `/replay/api/*`, for 31 total in a fully-enabled deployment. There is no login, no sessions, and no write path except the replay upload API — every core route is a read against committed SQLite databases and JSON artifacts.

The frontend is plain JavaScript, no framework and no build step. Shared CSS/JS lives in `apps/website/static/css/` and `apps/website/static/js/` and is loaded with ordinary `<link>`/`<script>` tags. (Older docs claim all CSS/JS is inlined per template — that has not been true since the assets were extracted to `static/`.)

## Route inventory

### Pages (8)

| Route | View function | Template | Data read |
|---|---|---|---|
| `/` | `home` | `simulate.html` | none server-side (JS calls APIs) |
| `/units` | `units` | `rankings.html` | `aoe2_units.db` (`units` table, unit list per age) |
| `/civilizations` | `civ_view` | `civ_overview.html` | `aoe2_reference.db` (civ list) |
| `/civilizations/<civ_name>` | `civ_detail` | `civ_detail.html` | `aoe2_reference.db` (civ validation) |
| `/matchup-advisor` | `matchup_advisor` | `matchup_advisor.html` | `aoe2_reference.db` (civ list) |
| `/replay` | `replay` | `replay.html` | none (iframe shell, see [replay.md](replay.md)) |
| `/patches` | `patches_page` | `patches.html` | `patches.db` + `aoe2_reference.db` (unit names) |
| `/patches/<build>/<civ>/<path:unit>` | `patch_unit_page` | `patch_unit.html` | `patches.db` + `aoe2_reference.db` |

Template names match what they render (since the 2026-06-10 rename): `rankings.html` is the `/units` rankings page, `civ_overview.html` is the civilization overview/selector, and `civ_detail.html` is the live per-civ detail page (formerly `deprecated-civ.html` — the old names were inverted).

### Redirects (3)

`/civ` → `/civilizations`, `/civ/<civ_name>` → `/civilizations/<civ_name>`, and `/simulate` → `/` — all HTTP 301, kept for old inbound links.

### SEO (3)

| Route | Behavior |
|---|---|
| `/robots.txt` | Allows everything, disallows `/api/`, points to the sitemap. |
| `/sitemap.xml` | Core pages + every `/civilizations/<civ>` + one `/vs/...` URL per unique-unit pair. Pairs come from `_matchup_seed_pairs()`: one Imperial unique unit per civ (Elite preferred) from `aoe2_reference.db`, crossed pairwise. |
| `/vs/<civ_a>/<unit_a>/<civ_b>/<unit_b>` | `matchup_landing.html` — server-rendered stat comparison from `ref_units` rows with a deep-link CTA into the Battle Sim. 404s on unknown civs/units. |

All three use `SITE_URL` for absolute URLs.

### JSON APIs (10, all under `/api/`)

| Route | Method | Data read | Consumed by |
|---|---|---|---|
| `/api/armor-classes` | GET | `aoe2_reference.db` | `simulate.js` |
| `/api/ref/civ/<civ_name>` | GET | `aoe2_reference.db` + `aoe2_units.db` (`unit_verifications`) | `simulate.js`, `civ-detail.js` |
| `/api/ref/stat-chain/<int:ref_unit_id>` | GET | `aoe2_reference.db` | `rankings.js` (hover cards) |
| `/api/ref/combat-unit/<civ_name>/<unit_slug>` | GET | `aoe2_reference.db` (`ref_units` via `combat_unit_loader.build_combat_dict_from_ref`) | `simulate.js` (the JS battle sim's unit loader) |
| `/api/ref/unit-line/<line_slug>` | GET | `aoe2_reference.db` + `derived_data.db` (`battle_scores`) + `pool_scores.db` + `patches.db` (current build) | `rankings.js` |
| `/api/civ-power-units/<civ_name>` | GET | `civ_power_units/<build>.json` + `patches.db` | `matchup.js`, `matchup_advisor.js` |
| `/api/top-units/<civ_name>` | GET | `civ_top_units.json`, falling back to live derivation from `aoe2_reference.db` | external/diagnostic |
| `/api/top-unit/<civ_name>/<line>` | GET | same as above | external/diagnostic |
| `/api/matchup-recommendations/<civ_a>/<civ_b>` | GET | `best_units.py` (reads `aoe2_reference.db`, `derived_data.db`, `pool_scores.db`) + on-the-fly sims | `matchup_advisor.js` |
| `/api/matchup-sims` | POST | same as above; runs live `simulate_battle()` cross-sims | `matchup_advisor.js` |

Input validation: `_validate_civ_name()` checks against `_valid_civs()` — an `lru_cache`d frozenset of `DISTINCT civ_name` from `aoe2_reference.db` (53 civs at build 177723). `_validate_age()` accepts only `imperial` (Imperial-only data model since 2026-06-11; `age=castle` is a clean 400). Civ names are case-sensitive title-case.

### Replay blueprint (7)

`aoe2x/replay/blueprint.py` registers `/replay/api/upload` (POST), `/replay/api/matches`, `/replay/api/matches/<player_name>`, `/replay/api/players`, `/replay/api/player/<int:profile_id>/matches`, `/replay/api/load-match` (POST), and `/replay/api/clip`. The `/replay` page embeds the static SPA at `aoe2x/replay/public/index.html` in an iframe. If the blueprint's heavy deps (`mgz`, Pillow, etc.) fail to import, registration is skipped and the rest of the site still boots. Details in [replay.md](replay.md).

## Central registries

These are the single-source-of-truth files. Each was previously duplicated across templates/modules; the copies have been consolidated.

| Registry | Lives in | Contents | Consumers | If you forget to update it |
|---|---|---|---|---|
| `UNIT_LINES` | `aoe2x/sim/unit_lines.py` | 26 keys: 21 unit lines (with per-civ `unique_units` slug pairs) + 5 aggregate pseudo-lines (`archery`, `infantry`, `stable`, `siege`, `naval`) | 8 modules: `app.py`, `best_units.py`, `compute_battle_scores.py`, `derive_pool_scores.py`, `derive_unit_rankings.py`, `pool_scores_lib.py`, `run_matchup_battles.py`, `top_units.py` | New unit never appears in rankings, matchup advisor, top-units, or any derived score |
| `CIV_MISSING_UNITS` | `aoe2x/sim/unit_lines.py` | 14 `(civ, slug)` pairs the extraction pipeline emits but the civ cannot actually build | `app.py` (`/api/ref/unit-line`), `compute_battle_scores.py`, `derive_unit_rankings.py`, `run_matchup_battles.py` | Phantom units (e.g. Inca Champion) show up in rankings and get sim-scored |
| `NAVAL_UNIT_LINES`, `CANNON_GALLEON_LINE`, `TREBUCHET_SLUGS` | `aoe2x/sim/unit_lines.py` | Navy-column mappings and treb exclusion set | `best_units.py` | Navy column in the advisor misses/mis-maps a civ's ship |
| `ENABLED_CIVS` | `apps/website/static/js/constants.js` | 53 civ names shown in frontend pickers | `simulate.js`, `rankings.js` | New civ invisible in the Battle Sim civ dropdown even though APIs serve it |
| `NAME_TO_ICON` | `apps/website/static/js/constants.js` | 218 display-name → icon-filename entries | `simulate.js`, `rankings.js`, `matchup.js`, `matchup_advisor.js`, `civ-detail.js` (all via `getIconUrl()`) | Unit renders without an icon everywhere |
| `UNIQUE_BUILDING` | `apps/website/static/js/constants.js` | 13 overrides mapping non-Castle unique units to their building | same JS files | Unit grouped under Castle instead of its real building |
| Civ emblems | `apps/website/static/js/constants.js` (`CIV_EMBLEM_BASE`) | External CDN: `https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/` | `matchup.js`, `matchup_advisor.js`, `rankings.js` | n/a (third-party hosted; a new civ missing from the CDN shows a broken emblem) |
| Unit display names | `aoe2_reference.db` `ref_units.unit_name` (generated by the analysis stage) | The actual unit a civ fields per slug/age (Koreans `paladin` → "Cavalier") | `_ref_unit_name()` in `app.py`, all API payloads; the `/units` page list uses `aoe2_units.db` `units.display_name` | Wrong/stale names; fix in the pipeline, not here — see [data-pipeline.md](data-pipeline.md) |
| Server-side civ list | `aoe2_reference.db` via `_valid_civs()` in `app.py` | Authoritative civ set for validation and the sitemap | every validated route | n/a — derived from the DB. The pipeline civ list (`ORIGINAL_13_CIVS` in `aoe2x/dbgen/config_constants.py`) is derived from `extraction.extract_constants.CIV_NAMES`; the old dead copy in `app.py` was deleted |

`ENABLED_CIVS` and the DB civ set must agree (both 53 today). There is no automated check; a civ added to the DB but not to `constants.js` is simply unselectable in the frontend.

### Slug conventions

- Slugs are lowercase with underscores. Standard line units use plain names: `knight`, `halberdier`, `heavy_cav_archer`.
- Civ-locked unique units carry the civ as a **suffix**: `huskarl_goths`, `cataphract_byzantines`. Multi-word civ names keep underscores in the suffix.
- Regional uniques shared by several civs carry **no** suffix: `champi_warrior`, `slinger`, `eagle_warrior`, `genitour`.
- Elite tiers use the `elite_` **prefix** (`elite_huskarl_goths`); synthetic Imperial-age entries for units with no upgrade use the `imp_` **prefix** (`imp_elite_skirm`, `imp_slinger`) — it is a prefix, not a `_imp` suffix (see `_token_of_slug()` in `app.py`, which strips `imp_elite_`, `elite_`, `imp_`).
- Two slugs contain parentheses: `ratha_(melee)_bengalis`, `ratha_(ranged)_bengalis`.

## Templates

All templates extend `apps/website/templates/base.html` except the included `_footer.html` fragment.

| Template | Route(s) | Page CSS | Page JS |
|---|---|---|---|
| `base.html` | (layout) | `css/base.css` | `js/constants.js`, `js/api_client.js`, inline theme toggle |
| `_footer.html` | (include) | — | inline contact-modal script when `CONTACT_FORM_ENDPOINT` is set |
| `simulate.html` | `/` | `css/simulate.css` | `js/sim_params.js`, `js/simulate.js` |
| `rankings.html` | `/units` | `css/rankings.css` | `js/rankings.js` |
| `civ_overview.html` | `/civilizations` | `css/matchup.css` | `js/matchup.js` (+ inline `CIVS` constant) |
| `civ_detail.html` | `/civilizations/<civ>` | `css/civ-detail.css` | `js/civ-detail.js` (+ inline `CIV_NAME`) |
| `matchup_advisor.html` | `/matchup-advisor` | `css/matchup_advisor.css` | `js/matchup_advisor.js` (re-loads `constants.js`, harmless duplicate) |
| `matchup_landing.html` | `/vs/...` | inline `<style>` | none; overrides the JSON-LD block with `FAQPage` schema |
| `patches.html` | `/patches` | inline `<style>` | none (server-rendered accordions) |
| `patch_unit.html` | `/patches/<build>/<civ>/<unit>` | inline `<style>` | none |
| `replay.html` | `/replay` | inline | inline iframe-sizing script; iframe src `/static/replay/index.html` |

`base.html` provides, for every page: Google Analytics (gtag, ID `G-MYNEW08LBR`, hardcoded), title/meta-description/robots/canonical blocks, Open Graph + Twitter Card tags, a default `WebApplication` JSON-LD block (overridable via `{% block structured_data %}`), Google Fonts, a pre-paint theme script (reads `localStorage['aoe2-theme']` to avoid flash), the six-tab site nav driven by the `active_nav` template variable, and the dark/light theme toggle. Canonical URLs default to `site_url + request.path` unless the view passes `canonical_url` (only `/vs/...` does).

Known issue: `base.html` references `/static/img/favicon.png` and `/static/img/og-default.png`, but `apps/website/static/img/` contains only the `units/` directory — both files are missing from the repo, so the favicon and default OG image 404.

## Static assets

| File | Lines | Role |
|---|---|---|
| `static/js/constants.js` | 360 | Central registries (see above) + `getIconUrl()`, `escapeHtml()`, building maps |
| `static/js/api_client.js` | 101 | `apiGet`/`apiPost`/`apiRequest` fetch wrappers with 10s timeout and `ApiError` |
| `static/js/simulate.js` | 2,643 | Battle Sim page: civ/unit pickers, deep-link autorun, and the full **canvas battle simulation** (`BattleUnit`, `BattleSimulation`, `Projectile`, `MeleeEffect` classes). This JS engine mirrors but is separate from the Python engines — see [simulation-engines.md](simulation-engines.md) |
| `static/js/sim_params.js` | 21 | Pure deep-link query-param parser (`readSimParams`), shared with tests via CommonJS export |
| `static/js/rankings.js` | 2,013 | Rankings tables for `/units`, fetches `/api/ref/unit-line` and `/api/ref/stat-chain` |
| `static/js/matchup.js` | 320 | Civilization overview grid + power-unit cards (`/api/civ-power-units`) |
| `static/js/matchup_advisor.js` | 1,270 | Advisor UI: power units, recommendations, live cross-sims |
| `static/js/civ-detail.js` | 417 | Per-civ unit table on the deprecated detail page (`/api/ref/civ`) |
| `static/css/*.css` | 6 files | `base.css` (theme variables, nav, footer) + one per page, matching the template table above |
| `static/img/units/` | 213 PNGs | Unit icons, filenames matching `NAME_TO_ICON` values. New icons are added by the icon/art pipeline — see [operations.md](operations.md) |
| `static/replay/` | SPA | Self-contained replay visualizer — see [replay.md](replay.md) |

## Database access

All connections are short-lived `sqlite3.connect()` calls with `Row` factory; there is no pooling and no ORM.

| Helper | DB file | Tables read by routes |
|---|---|---|
| `get_db()` (`app.py`) | `data/golden/aoe2_units.db` | `units` (the `/units` page list), `unit_verifications` (verified badges in `/api/ref/civ`) |
| `get_ref_db()` (`app.py`) | `data/golden/aoe2_reference.db` | `ref_units`, `ref_techs_applied`, `ref_stat_chain`, `ref_special_effects`, `ref_projectiles`, `armor_classes` — the workhorse runtime DB |
| `get_derived_db()` (`app.py`) | `data/golden/derived_data.db` | `battle_scores` (rankings role scores; see [derived-data.md](derived-data.md)) |
| `_patches_conn()` / `patches_db.get_current_build()` | `data/golden/patches.db` | `patches`, `patch_unit_changes`, `patch_unit_ranking`, `patch_matchup_changes`. `get_current_build()` is the single build resolver every score lookup goes through |
| `pool_scores_query.load_pool_scores()` | `data/golden/pool_scores.db` | `pool_scores` (per-unit pool payloads on the rankings page) |
| `best_units.py` module paths | `aoe2_reference.db`, `derived_data.db`, `pool_scores.db` | advisor recommendations and percentiles |

JSON artifacts read at runtime: `civ_power_units/<build>.json` (per-build only — the legacy flat `civ_power_units.json` fallback was removed) and `civ_top_units.json`. (`battle_scores.json` and its `app.py` loader were deleted — role scores come from `derived_data.db`.) Matchup DBs live outside the repo at `D:/AI/` (the committed 3.9 MB stub was removed 2026-06-11); they and `battle_cache.json` are **not** read by any route — they feed the offline derive jobs only.

There is **no `app_data.db`** — older docs mention it, but the file does not exist; `unit_verifications` plus dormant `comments`/`simulation_comments`/`combat_results` tables live inside `aoe2_units.db`, and no comment routes exist anymore. The `unit_stats` table in `aoe2_units.db` is likewise not queried by any route — combat stats come from `ref_units`.

## Environment variables and config

| Variable | Read in | Default / effect |
|---|---|---|
| `SITE_URL` | `app.py:31` | `https://aoe2matchup.com`; canonical URLs, sitemap, OG tags |
| `CONTACT_FORM_ENDPOINT` | `app.py:45` | unset → contact button hidden; set → footer contact modal POSTs to it |
| `SOCIAL_DISCORD_URL`, `SOCIAL_YOUTUBE_URL`, `SOCIAL_INSTAGRAM_URL` | `app.py:47-49` | unset → footer icon hidden; also feed the JSON-LD `sameAs` array |
| `PORT` | `app.py:1515` | dev server only (default 5000); production port handling is gunicorn's |

Production start (Railway): `cd apps/website && gunicorn app:app --workers 2 --timeout 300 --graceful-timeout 300` per `railway.json`; `apps/website/Procfile` has the plain `gunicorn app:app` variant. Deployment/branch mechanics are in [operations.md](operations.md). The Google Analytics ID is hardcoded in `base.html`, not env-driven.

## Cross-file sync rules (verified 2026-06-09)

The six sync rules in `CLAUDE.md` were written before several consolidations. Current status:

| Old rule | Status now |
|---|---|
| `UNIT_LINES` duplicated in `app.py` + `compute_battle_scores.py` | **Retired** — single source `aoe2x/sim/unit_lines.py`. Residual drift: the supplementary `*_LINE_SLUGS` sets are still defined separately in `app.py` and `compute_battle_scores.py` (585+), and disagree on mangonel (`SIEGE_LINE_SLUGS` vs `HIDDEN_LINE_SLUGS`) — documented as a TODO in `unit_lines.py` |
| `NAME_TO_ICON` in 4 templates | **Retired** — single source `static/js/constants.js`. New unit still needs both the dict entry and a PNG in `static/img/units/` |
| `UNIQUE_BUILDING` in 2 templates | **Retired** — single source `static/js/constants.js` |
| `ENABLED_CIVS` in 2 templates matching `ORIGINAL_13_CIVS` | **Changed** — one copy in `constants.js`; must match the civ set in `aoe2_reference.db` (the server validates against the DB, not any Python list). The dead `ORIGINAL_13_CIVS` copy in `app.py` was deleted |
| New `unit_stats` column touches 4 files | **Changed** — new combat property now flows `ref_units` column (analysis stage) → `aoe2x/sim/combat_unit_loader.py` `build_combat_dict_from_ref()` → `simulation.py` `prepare_combat_unit()` (and `simulation_real.py`) → `simulate.js` `BattleUnit` if the canvas sim needs it. `unit_stats` is out of the loop |
| Battle scores stale after sim changes | **Still true, different artifacts** — regenerate `derived_data.db`, `pool_scores.db`, `civ_power_units/` via the patch pipeline ([derived-data.md](derived-data.md)); `battle_scores.json` no longer exists |

Sync rules that are live today:

1. **Deep-link contract**: `battle_sim_deep_link()` in `app.py` builds `?civ1=&unit1=&civ2=&unit2=&age1=&age2=&mode=&count1=&count2=&resources=&autorun=1`; `static/js/sim_params.js` `readSimParams()` parses the same keys. Change one → change the other.
2. **JS sim parity**: behavior changes in the Python engines usually need a mirrored change in `simulate.js`'s canvas classes ([simulation-engines.md](simulation-engines.md)).
3. **New unique unit**: `UNIT_LINES` entry (`unit_lines.py`) + `NAME_TO_ICON` entry + icon PNG + `UNIQUE_BUILDING` if not Castle-trained.
4. **New civ**: appears automatically server-side once in the DBs, but needs `ENABLED_CIVS` in `constants.js` to be selectable.
5. **`*_LINE_SLUGS` drift** between `app.py` and `compute_battle_scores.py` — touch role-scoring categories in both places until they are consolidated.

## Update triggers

| If this changes | Update these sections |
|---|---|
| Routes added/removed in `app.py` | Route inventory (recount the totals) |
| Templates or `static/js`/`static/css` files added | Templates table, Static assets |
| `unit_lines.py` keys or `constants.js` registries | Central registries (recount entries) |
| A new DB file or JSON artifact read by a route | Database access |
| New `os.environ` reads in `app.py` | Environment variables |
| `*_LINE_SLUGS` consolidation into `unit_lines.py` lands | Cross-file sync rules |
| Comments/verification features revived or removed | Database access (aoe2_units.db tables) |
| `favicon.png` / `og-default.png` added | Templates (remove the known issue) |
