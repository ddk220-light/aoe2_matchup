# Matchup Advisor Redesign

Replace the 4-phase simulation-heavy matchup advisor with a fast, pre-computed power-units approach.

## Approach

Enrich `civ_power_units.json` at build time (Approach 1). No new endpoints. Frontend reads pre-computed JSON for instant render; Phase B recommendations load asynchronously.

## Data Layer

Extend `best_units.py` `compute_civ_power_units()` to join `ref_units` and include summary stats in each power unit entry:

```json
{
  "unit_slug": "paladin",
  "unit_name": "Paladin",
  "line_slug": "stable",
  "score": 27.0,
  "rank": 89,
  "median_delta": -6.3,
  "is_signature": false,
  "strength": "average",
  "stats": {
    "hp": 180,
    "attack": 18,
    "melee_armor": 5,
    "pierce_armor": 5,
    "speed": 1.35,
    "range": 0,
    "cost_food": 60,
    "cost_wood": 0,
    "cost_gold": 75
  }
}
```

Fields added: `unit_name` (display name), `stats` (final post-tech values from `ref_units`).

Build pipeline unchanged: `python3 best_units.py` produces richer JSON.

## API

Existing endpoints, no changes:
- `GET /api/civ-power-units/<civ_name>` — Phase A (enriched power units)
- `GET /api/matchup-recommendations/<civ_a>/<civ_b>` — Phase B (counter compositions)

## Frontend

### Page flow
1. User picks two civs (existing civ-grid selector, unchanged)
2. On "Analyze Matchup" click: fetch both civs' power units (two parallel calls to `/api/civ-power-units/<civ>`)
3. Render side-by-side power units grid immediately
4. Fire Phase B (`/api/matchup-recommendations/<civ_a>/<civ_b>`) in background
5. When Phase B completes, slide in "Recommended Compositions" section below the grid

### Power units grid layout

Side-by-side table, one row per role (cavalry, ranged, infantry, anti_cavalry, trash, siege):

Each unit cell contains:
- Unit icon + name, linked to rankings page (`/?line=<line_slug>&age=Imperial`)
- Strength badge: colored chip (signature=gold, strong=green, average=neutral, weak=red)
- Rank indicator: e.g. "#4 / 98"

### Hover tooltip (CSS-only, no API call)
- HP, Attack, Melee/Pierce Armor, Speed, Range
- Cost (food/wood/gold)
- Score and median delta ("12.5 above median")

### Phase B slide-in
Once matchup-recommendations returns, a section fades in below the grid:
- 1-2 compositions per civ: gold unit + trash unit with reasoning text
- Resource/pop efficiency scores

### Age support
Imperial only. Castle age data not pre-computed.

## Backend Cleanup

### Delete from `app.py`:
- `_run_matchup_analysis()` and all internal helpers:
  - `_categorize_units()`
  - `_find_clear_winner_and_scores()`
  - `_find_best_counter()`
  - `_build_combos_for_civ()`
  - `_run_army_sims()`
  - `_ADVISOR_EXCLUDED`
- `/api/matchup-advisor/analysis/<civ1>/<civ2>` endpoint
- `/api/matchup-advisor/army/<civ1>/<civ2>` endpoint
- `AGES` dict if only used by matchup advisor (audit first)

### Keep in `app.py`:
- `_build_combat_dict_from_ref()` — used by `/api/ref/combat-unit`
- `/matchup-advisor` route (template changes, route stays)
- `/api/civ-power-units/<civ_name>` endpoint
- `/api/matchup-recommendations/<civ_a>/<civ_b>` endpoint

### Keep in `best_units.py`:
- All existing code (extended, not replaced)
- `ROLE_DEFS`, `COUNTER_MAP`, `TRASH_PAIRING` unchanged

## Frontend files changed
- `webapp/templates/matchup_advisor.html` — minimal template changes
- `webapp/static/js/matchup.js` — full rewrite (old 4-phase render logic replaced)
- `webapp/static/css/matchup.css` — updated styles for grid layout, tooltips, badges
