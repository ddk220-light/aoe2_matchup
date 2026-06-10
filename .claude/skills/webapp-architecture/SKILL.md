---
name: webapp-architecture
description: Use when modifying the AoE2 unit analyzer webapp — adding simulation mechanics, changing UI, adding units or civs, creating API endpoints, or debugging data flow issues. Covers file locations, sync dependencies, and modification patterns.
---

# Webapp Architecture

## Overview

Flask app serving aoe2matchup.com. All serving data is committed SQLite/JSON (committing on a branch = deploying). Shared CSS/JS lives in `webapp/static/` — templates are thin Jinja shells over `base.html`.

**Canonical docs (verified 2026-06-09):** `docs/architecture/README.md` (system map + single-sources-of-truth table) and `docs/architecture/runbooks.md` (when-X-changes-update-Y checklists). This skill is the working summary; when in doubt, trust those docs.

## Core Files

| File | Role |
|------|------|
| `webapp/app.py` | Flask routes (24 + 7-route replay blueprint), DB queries, SEO endpoints |
| `webapp/simulation.py` | Abstract tick-based engine (no positions). Backs `/api/matchup-sims` via `best_units.get_matchup_sims` |
| `webapp/simulation_real.py` | Position-based 2D engine. Backs ALL batch matchup data (`run_matchup_battles.py`, `rebuild_matchup_baseline.py`, `patch_resim.py`). Hashed into `sim_version` |
| `webapp/static/js/simulate.js` | Frontend canvas engine (`BattleUnit`). The interactive Battle Sim page at `/` runs entirely client-side |
| `webapp/combat_unit_loader.py` | `build_combat_dict_from_ref()` — canonical ref_units row → combat dict, shared by all backend sim callers |
| `webapp/unit_lines.py` | `UNIT_LINES` + `CIV_MISSING_UNITS` — single Python source for unit lines (JS copy in `static/js/rankings.js`) |
| `webapp/best_units.py` | Civ power units, matchup recommendations, live matchup sims |
| `webapp/replay_core.py` | Replay analyzer blueprint (mgz parsing, gracefully disabled if deps missing) |

**Databases the app reads:** `aoe2_reference.db` (combat data — NOT `aoe2_units.db`), `derived_data.db` (rankings), `pool_scores.db`, `patches.db`, plus `civ_power_units/<build>.json`. `aoe2_units.db` `unit_stats` has no app route consumer (legacy).

## Feature Map

| Feature | Backend | Frontend |
|---------|---------|----------|
| Battle Sim (page at `/`) | `/api/ref/combat-unit/<civ>/<slug>` serves the combat dict | `simulate.html` + `static/js/simulate.js` (fight runs in JS) |
| Unit Rankings (`/units`) | `/api/ref/unit-line/<line>` reading `derived_data.db` + `pool_scores.db` | `index.html` + `static/js/rankings.js` |
| Civ pages (`/civilizations[/<name>]`) | `/api/civ-power-units/<civ>`, `/api/ref/civ/<civ>` | `civ_detail.html`, `deprecated-civ.html` + `static/js/civ-detail.js`, `matchup.js` |
| Matchup Advisor | `/api/matchup-recommendations/...`, `POST /api/matchup-sims` (live sims, `simulation.py`) | `matchup_advisor.html` + `static/js/matchup_advisor.js` |
| Patches (`/patches[...]`) | `patches.db` via `patches_db.py` | `patches.html`, `patch_unit.html` |
| Replay analyzer (`/replay`) | `replay_core.py` blueprint, `clip_export.py` | iframe SPA in `static/replay/` |
| SEO | `/vs/<civA>/<unitA>/<civB>/<unitB>`, `sitemap.xml`, `robots.txt` | `matchup_landing.html` |

## Sync Rules (MUST check before completing any task)

1. **New combat column/ability** — chain: `analysis/config_combat.py` (or `generate_reference.py` schema) → `analysis/generate_main_db.py` → `webapp/combat_unit_loader.py` → `simulation.py prepare_combat_unit()` → `simulation_real.py` → `static/js/simulate.js`. Full checklist: runbooks §3.
2. **`UNIT_LINES`** — `webapp/unit_lines.py` (Python) ↔ JS copy in `static/js/rankings.js`.
3. **Frontend constants** — `ENABLED_CIVS`, `NAME_TO_ICON` (218 entries), `UNIQUE_BUILDING` live ONLY in `static/js/constants.js`. No template copies. `ORIGINAL_13_CIVS` in `app.py` is dead code.
4. **Cost weights** — `simulation_real.py weighted_cost` ↔ `compute_battle_scores.calc_weighted_cost`.
5. **`PLAYER_COLORS`** — `replay_core.py` ↔ `clip_export.py`.
6. **Sim logic changed?** — editing `simulation_real.py`/`config_combat.py` bumps `sim_version` → matchup rows auto-stale (re-sim via batch runner, then re-derive rankings/pool scores). Editing `simulation.py` does NOT bump it. Always regenerate `.golden/baseline.json`. Checklist: runbooks §2.

## Data Flow

**Combat unit data (most common path):**
```
analysis/config_combat.py (+ config_units.py)
  → analysis/generate_reference.py → aoe2_reference.db (ref_units)
    → combat_unit_loader.build_combat_dict_from_ref()
      → app.py /api/ref/combat-unit/<civ>/<slug> → static/js/simulate.js  (interactive page)
      → simulation.py / simulation_real.py prepare_combat_unit()          (backend callers)
```

**Rankings data:** batch sims (`simulation_real.py`, PyPy) → matchup DB → `derive_unit_rankings.py` / `derive_pool_scores.py` / `best_units.py` → `derived_data.db` / `pool_scores.db` / `civ_power_units/<build>.json` → `/api/ref/unit-line` etc. All keyed by `patches_db.get_current_build()`.

**Config override priority (later wins):**
```
defaults → extracted dat data → COMBAT_PROPERTIES → UNIQUE_COMBAT_PROPERTIES → CIV_COMBAT_PROPERTIES
```

## Modification Recipes

Run the matching runbook in `docs/architecture/runbooks.md`:
- §1 new game patch (build numbers, re-extract, re-sim, re-derive, patches.db)
- §2 sim logic / mechanic change (three engines + golden + re-derive)
- §3 new combat column / special ability (6-file chain)
- §4 new unit or civ (CIV_NAMES, config_units, unit_lines, constants.js, icons)
- §5 new unit icon / art
- §6 frontend constant change
- §7 surgical combat-prop fix for one unit (avoid full regen overwriting all rows)

### Add a new API endpoint
1. Add `@app.route()` in `app.py`; query via the sqlite3 helpers there (per-DB `_connect`-style functions — there is no `get_app_db()`).
2. Add fetch call in the consuming `static/js/*.js` file (use `api_client.js` helpers).

### Change frontend UI
1. Templates are thin; page logic lives in `static/js/<page>.js`, styling in `static/css/<page>.css` + `base.css`.
2. Check sync rule 3 for shared constants.
