---
name: webapp-architecture
description: Use when modifying the AoE2 unit analyzer webapp — adding simulation mechanics, changing UI, adding units or civs, creating API endpoints, or debugging data flow issues. Covers file locations, sync dependencies, and modification patterns.
---

# Webapp Architecture

## Overview

aoe2matchup.com is an Astro frontend (`apps/web`) plus a Flask JSON API (`apps/backend`), deployed on Vercel as two services from the root `vercel.json`. All serving data is committed SQLite/JSON (committing on a branch = deploying: `main` → production, `staging` → preview). Page titles/meta/JSON-LD, the sitemap and page data are generated at build time by `scripts/migration/prepare_release.py`. The old Flask website (`apps/website`, Jinja templates) is deleted; its browser client survives as research code in `legacy/client/`.

**Canonical docs:** `docs/architecture/CURRENT.md` (current module ownership), `docs/architecture/webapp.md` (routes, registries, build-time data), `docs/vercel-deployment.md` (deployment) and `docs/architecture/runbooks.md` (when-X-changes-update-Y checklists). This skill is the working summary; when in doubt, trust those docs.

## Core Files

| File | Role |
|------|------|
| `apps/backend/app.py` | Vercel entrypoint: imports the sealed `runtime/` copy of `aoe2_api`, release headers, `/_internal/release`, `/api/cached-advisor/...`; 404s non-API paths |
| `apps/backend/aoe2_api/web.py` | Flask app + 15 `/api/*` routes, DB helpers, validators |
| `apps/backend/aoe2_api/routes/`, `services/` | Battle/civilization blueprints; battles, mechanics, rankings, civilizations, catalog, advisor, release services |
| `apps/web/src/pages/`, `src/features/`, `src/components/site/`, `src/styles/` | Astro routes, page code, header/footer, shared styles |
| `apps/web/static/js/` | Live public scripts: `constants.js`, `api_client.js`, `v3_sim_worker.js` |
| `scripts/migration/prepare_release.py` (+ `export_*.py`, `site/`) | Build-time page data, metadata, sitemap; seals `apps/web/src/generated/`, `apps/web/public/`, `apps/backend/runtime/` |
| `aoe2x/js_simulation/src/` | Active V3 JS engine (browser worker + node) |
| `aoe2x/sim/simulation.py` | Abstract tick-based engine (no positions). Backs `/api/matchup-sims` via `best_units.get_matchup_sims` |
| `aoe2x/sim/simulation_real.py` | Position-based 2D engine. Backs ALL batch matchup data. Hashed into `sim_version` |
| `legacy/client/js/engine/` | Retired client engine (`BattleUnit`) — parity panel/research only, never published |
| `aoe2x/sim/combat_unit_loader.py` | `build_combat_dict_from_ref()` — canonical ref_units row → combat dict |
| `aoe2x/sim/unit_lines.py` | `UNIT_LINES` + `CIV_MISSING_UNITS` — Python source (live JS copy in `apps/web/src/features/rankings/render.mjs`) |
| `aoe2x/advisor/best_units.py` | Civ power units, matchup recommendations, live matchup sims |

**Databases the API reads:** `aoe2_reference.db`, `aoe2_reference_simulation.db` / `aoe2_reference_rankings.db` (56 civs), `derived_data_v3.db` (published rankings), `derived_data.db`, `pool_scores.db`, `patches.db`, `civ_matchups_first_pass.db` (advisor), plus `civ_power_units/<build>.json`. `aoe2_units.db` is read only for `unit_verifications`.

## Feature Map

| Feature | Backend | Frontend |
|---------|---------|----------|
| Battle Sim (page at `/`) | `POST /api/v3/battle-config` (`aoe2_api/routes/battles.py`) | `src/pages/index.astro` + `src/features/simulator/` → worker `static/js/v3_sim_worker.js` running `aoe2x/js_simulation/src/` |
| Unit Rankings (`/units[/<line>]`) | `get_unit_line_data()` / `/api/ref/unit-line/<line>`, `/api/ref/stat-chain/<id>` | `src/pages/units/` + `src/features/rankings/` |
| Civ pages (`/civilizations[/<name>]`) | `/api/civilizations/<civ>` (snapshotted at build) | `src/pages/civilizations/` + `src/features/civilizations/` |
| Matchup Advisor | `/api/advisor-*`, `/api/cached-advisor/...` | `src/pages/matchup-advisor.astro` + `src/features/advisor/` |
| Patches (`/patches[...]`) | `patches.db`, built by `scripts/migration/site/patches.py` | `src/pages/patches/` |
| SEO | `/vs/...`, `sitemap.xml`, `robots.txt`, metadata from `scripts/migration/site/` | `src/pages/vs/`, `sitemap.xml.ts`, `robots.txt.ts` |

The replay analyzer is not mounted (`/replay` 301s to `/`).

## Sync Rules (MUST check before completing any task)

1. **New combat column/ability** — registry entry in `aoe2x/dbgen/ability_registry.py` + `config_combat.py` value + one handler per engine (`simulation.py`, `simulation_real.py`, `legacy/client/js/engine/battle_unit.js`; V3 mechanics in `aoe2x/js_simulation/src/`). Legacy `generate_main_db.py` still needs hand edits. Run `node tools/simjs/parity_check.mjs` after any `legacy/client/js/engine/` edit. Full checklist: runbooks §3.
2. **`UNIT_LINES`** — `aoe2x/sim/unit_lines.py` (Python) ↔ JS copy in `apps/web/src/features/rankings/render.mjs`.
3. **Frontend constants** — `ENABLED_CIVS`, `NAME_TO_ICON`, `UNIQUE_BUILDING` are declared only in `apps/web/static/js/constants.js`, from `window.SITE_CATALOG` = `site_catalog()` (`aoe2_api/services/catalog.py`): civ roster of `aoe2_reference_simulation.db` + `aoe2x/assets/presentation.json` (`icon_names`, `unique_buildings`). Edit the JSON/DB, not the JS.
4. **Cost weights** — `simulation_real.py weighted_cost` ↔ `compute_battle_scores.calc_weighted_cost`.
5. **`PLAYER_COLORS`** — `replay_core.py` ↔ `clip_export.py`.
6. **Sim logic changed?** — editing `simulation_real.py`/`config_combat.py` bumps `sim_version` → matchup rows auto-stale (re-sim via batch runner, then re-derive rankings/pool scores). Editing `simulation.py` does NOT bump it. Always regenerate `.golden/baseline.json`. Checklist: runbooks §2.
7. **Presentation changes go only in `apps/web`**; then `python scripts/migration/prepare_release.py` before `npm run build --prefix apps/web`, and `git checkout vercel.json` unless the data changed.

## Data Flow

**Combat unit data (most common path):**
```
aoe2x/dbgen/config_combat.py (+ config_units.py)
  → aoe2x/dbgen/generate_reference.py → aoe2_reference*.db (ref_units)
    → combat_unit_loader.build_combat_dict_from_ref()
      → aoe2_api/web.py /api/ref/combat-unit/<civ>/<slug> → legacy/client/js/engine/ (parity/research)
      → simulation.py / simulation_real.py prepare_combat_unit()                    (backend callers)
    → aoe2_api/services/{mechanics,battles}.py → POST /api/v3/battle-config → aoe2x/js_simulation/src/ (live page)
```

**Rankings data:** batch sims (`simulation_real.py`, PyPy) → matchup DB → derive scripts → `derived_data*.db` / `pool_scores.db` / `civ_power_units/<build>.json` → `get_unit_line_data()` → build-time exports. All keyed by `patches_db.get_current_build()`.

**Config override priority (later wins):**
```
defaults → extracted dat data → COMBAT_PROPERTIES → UNIQUE_COMBAT_PROPERTIES → CIV_COMBAT_PROPERTIES
```

## Modification Recipes

Run the matching runbook in `docs/architecture/runbooks.md`:
- §1 new game patch (build numbers, re-extract, re-sim, re-derive, patches.db)
- §2 sim logic / mechanic change (engines + golden + re-derive)
- §3 new combat column / special ability
- §4 new unit or civ (CIV_NAMES, config_units, unit_lines, presentation.json, icons)
- §5 new unit icon / art
- §6 frontend constant change
- §7 surgical combat-prop fix for one unit (avoid full regen overwriting all rows)

### Add a new API endpoint
1. Add the route in `apps/backend/aoe2_api/web.py` (or a blueprint in `aoe2_api/routes/` with logic in `services/`); query through the read-only helpers there (`get_ref_db()`, `get_sim_ref_db()`, ...).
2. Call it from the consuming `apps/web/src/features/<page>/` module (or `static/js/api_client.js`). If the data is static per release, prefer a build-time snapshot via `scripts/migration/export_data.py`.
3. Test with the `client` fixture (`tests/conftest.py` imports `aoe2_api.web`).

### Change frontend UI
1. Page markup in `apps/web/src/pages/` / `src/components/`, page logic in `src/features/<page>/`, styling in the feature CSS + `src/styles/`.
2. Titles/meta/JSON-LD come from `scripts/migration/site/` builders, not the Astro page.
3. Check sync rule 3 for shared constants.

### Run locally
```bash
python scripts/migration/prepare_release.py           # required first
npm run dev --prefix apps/web                         # pages (Astro dev server, Node 24)
(cd apps/backend && flask --app app run --port 5002)  # API from the sealed runtime/
```
The Astro dev server does not proxy `/api/*`; check API-driven pages end to end on a Vercel preview.
