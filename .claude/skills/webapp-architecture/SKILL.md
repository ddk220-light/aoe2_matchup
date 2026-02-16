---
name: webapp-architecture
description: Use when modifying the AoE2 unit analyzer webapp — adding simulation mechanics, changing UI, adding units or civs, creating API endpoints, or debugging data flow issues. Covers file locations, sync dependencies, and modification patterns.
---

# Webapp Architecture

## Overview

The webapp is a Flask app with a tick-based battle simulator. Four files do 95% of the work. All CSS/JS is inlined in templates (no shared static assets).

## Core Files

| File | Role |
|------|------|
| `webapp/app.py` | Flask routes (37 endpoints), DB queries, matchup analysis, API responses |
| `webapp/simulation.py` | Pure Python battle sim — `prepare_combat_unit()` parses DB rows, `simulate_battle()` runs tick loop, `simulate_mixed_battle()` for army fights. No Flask, no DB calls. |
| `webapp/compute_battle_scores.py` | Offline batch job: pairwise sims for all unit/civ combos → `battle_cache.json` + `battle_scores.json` |
| `webapp/templates/*.html` | 10 templates with inlined JS/CSS. `simulate.html` has its own JS canvas simulation (BattleUnit class) separate from backend sim. |

**Databases:** `aoe2_units.db` (main, `unit_stats` table with 80+ columns), `aoe2_reference.db` (audit), `app_data.db` (comments/verifications).

## Feature Map

| Feature | Backend | Frontend |
|---------|---------|----------|
| Unit Rankings | `app.py`: `/units`, `/api/units`, `/api/unit/<age>/<id>` | `index.html` (reads `battle_scores.json`) |
| Battle Simulation | `simulation.py` (all logic) | `simulate.html` (canvas + BattleUnit JS) |
| Civ Detail | `app.py`: `/civ/<name>`, `/api/civ/<name>` | `civ_detail.html` |
| Matchup Advisor | `app.py`: `_run_matchup_analysis()`, `_run_army_sims()` | `matchup_advisor.html` |
| Combat Unit API | `app.py`: `/api/combat-unit/<civ>/<slug>` (line 583) — direct SQL query on `unit_stats` | consumed by `simulate.html` and `matchup_advisor.html` |
| Comments | `app.py`: 6 endpoints | `review.html`, `analysis.html` |
| Verification | `app.py`: verify endpoints | `analysis.html` |
| Battle Scores | `compute_battle_scores.py` (offline) | consumed by `index.html` rankings |

## Sync Rules (MUST check before completing any task)

These files are duplicated or coupled. Missing one causes bugs:

1. **`UNIT_LINES` dict** — in BOTH `app.py` AND `compute_battle_scores.py`. Add/change unit lines in both.
2. **`NAME_TO_ICON` mapping** — in 4 templates: `index.html`, `simulate.html`, `civ_detail.html`, `matchup_advisor.html`. New unit type? Update all 4.
3. **`UNIQUE_BUILDING` mapping** — in `simulate.html` AND `civ_detail.html`. Maps non-Castle unique units to buildings.
4. **`ENABLED_CIVS` list** — in `index.html` AND `simulate.html`. Must match `ORIGINAL_13_CIVS` in `app.py` (authoritative source).
5. **Combat property columns** — adding a new column touches: DB schema (`generate_main_db.py`), API query (`app.py` line 589+), `simulation.py` (`prepare_combat_unit`), and optionally `simulate.html` JS.
6. **Battle scores** — stale after simulation logic changes. Rerun: `cd webapp && python3 compute_battle_scores.py`.

## Data Flow

**Combat unit data (most common path):**
```
analysis/config.py (COMBAT/UNIQUE/CIV_COMBAT_PROPERTIES)
  → analysis/generate_reference.py → aoe2_reference.db
    → analysis/generate_main_db.py → aoe2_units.db (unit_stats table)
      → app.py /api/combat-unit/<civ>/<slug> (SQL SELECT on unit_stats)
        → simulate.html JS fetches JSON → simulation.py prepare_combat_unit() → simulate_battle()
```

**Config override priority (later wins):**
```
defaults → extracted dat data → COMBAT_PROPERTIES → UNIQUE_COMBAT_PROPERTIES → CIV_COMBAT_PROPERTIES
```

**Build pipeline:** `python3 -m extraction.run` → `python3 -m analysis.generate_reference` → `python3 -m analysis.generate_main_db` → `cd webapp && python3 compute_battle_scores.py`

## Modification Recipes

### Add a new simulation mechanic
1. Add column to `unit_stats` CREATE TABLE in `analysis/generate_main_db.py`
2. Populate: data-driven in `analysis/generate_reference.py` OR hardcoded in `analysis/config.py` (COMBAT/UNIQUE/CIV_COMBAT_PROPERTIES)
3. Add to `build_combat_dict_from_ref()` in `analysis/generate_main_db.py`
4. Add to SELECT query in `app.py` `api_combat_unit()` (line 589+)
5. Add to `prepare_combat_unit()` in `simulation.py` (line 84)
6. Implement in `simulate_battle()` tick loop in `simulation.py`
7. If frontend needs it: update `simulate.html` BattleUnit class
8. Rebuild DBs, rerun battle scores (sync rule 6)

### Add a new unit or civ
1. Add to extraction config in `extraction/` and analysis config in `analysis/`
2. Run full build pipeline (see above)
3. Update `UNIT_LINES` in BOTH `app.py` AND `compute_battle_scores.py` (sync rule 1)
4. If unique unit: add to `UNIQUE_BUILDING` in `simulate.html` + `civ_detail.html` (sync rule 3)
5. Add icon to `NAME_TO_ICON` in all 4 templates (sync rule 2)
6. If new civ: add to `ORIGINAL_13_CIVS` in `app.py` + `ENABLED_CIVS` in 2 templates (sync rule 4)

### Add a new API endpoint
1. Add `@app.route()` in `app.py`
2. Query via `get_db()`, `get_ref_db()`, or `get_app_db()` as appropriate
3. Add fetch call in the consuming template JS

### Modify damage calculation
1. Per-hit damage: change `_calc_damage()` in `simulation.py`
2. Mechanic-level: modify tick loop in `simulate_battle()`
3. Rerun `compute_battle_scores.py` (sync rule 6)
4. Check if `simulate.html` BattleUnit JS needs matching changes

### Change frontend UI
1. Edit the specific template — all CSS/JS is inlined, no shared stylesheet
2. Check sync rules 2-4 for duplicated constants across templates
