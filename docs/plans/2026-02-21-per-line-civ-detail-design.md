# Per-Line Civ Detail Page Redesign

**Date:** 2026-02-21
**Status:** Approved

## Summary

Restructure the civilization detail page to show individual unit lines with per-line normalization and percentile ranking, replacing the current role-based grouping (cavalry/ranged/infantry + anti-cav/anti-archer sub-sections).

## Goals

1. Show unit lines individually within 4 columns (Cavalry, Ranged, Infantry, Siege)
2. Normalize and rank within each unit line (knights vs knights, camels vs camels, etc.)
3. Remove cross-pool categories (anti_cavalry, anti_archer, anti_cav_infantry)
4. Clean up dead code from old category system

## Design Decisions

| Decision | Choice |
|----------|--------|
| Composite score formula | Keep existing per-pool formulas (militia_value 50/30/20, stable_effectiveness 70/30, ranged_effectiveness = general_combat) |
| Normalization scope | Per-line everywhere (stable and infantry switch from pool to per-line; archery already per-line) |
| Anti-cav pool | Remove entirely — spears ranked among spears, camels among camels |
| Strategic narratives | Keep hero paragraph but simplify to use per-line strength data |
| Approach | Modify both compute_battle_scores.py and best_units.py |

## Column Layout

```
Cavalry          Ranged           Infantry         Siege
├─ Light Cav     ├─ Skirmisher    ├─ Militia Line   ├─ Rams
├─ Knight Line   ├─ Archer Line   ├─ Spear Line     ├─ Bombard Cannon
├─ Camel Line    ├─ Cav Archer    └─ Shock Infantry └─ Trebuchet
├─ Steppe Lancer ├─ Gunpowder
└─ Elephant      └─ Scorpion
```

Each line shows one unit per civ (the final upgrade) or "not available" if the civ lacks that line.

## File Changes

### 1. `compute_battle_scores.py`

#### Stable scoring (`compute_stable_role_scores`)
- Build `line_groups` dict mapping line_slug -> list of unit keys
- Change min-max normalization from pool-wide (lines 1488-1494) to per-line (same pattern as archery lines 1290-1301)
- Change speed weighting from `scope="pool"` to `scope="per_line"` with `line_groups`
- Composite formula unchanged: `stable_effectiveness = 0.70 * general_combat + 0.30 * anti_cav`

#### Infantry scoring (`compute_infantry_role_scores`)
- Build `line_groups` dict (already has `sk_to_line`)
- Change min-max normalization from pool-wide (lines 1129-1135) to per-line
- Change speed weighting from `scope="pool"` to `scope="per_line"` with `line_groups`
- Composite formula unchanged: `militia_value = 50% gc + 30% anti_cav + 20% raid_building`

#### Anti-cav pool removal
- Remove `compute_anti_cav_scores()` function
- Remove `anti_cav_combined` and `anti_cav_value` score types from infantry
- Remove `anti_cav_pool` line_slug from DB writes
- Update `INFANTRY_SCORE_TYPES` to remove `anti_cav_combined`, `anti_cav_value`

#### No changes to
- Archery scoring (already per-line)
- Siege scoring (already per-line)
- DB table schema

### 2. `best_units.py`

#### New data definitions
```python
COLUMN_DEFS = {
    "cavalry": ["light_cav", "knight", "camel", "steppe_lancer", "elephant"],
    "ranged": ["skirmisher", "archer", "cav_archer", "gunpowder", "scorpion"],
    "infantry": ["militia", "spear", "shock_infantry"],
    "siege": ["ram", "bombard_cannon", "trebuchet"],
}

LINE_SCORE_TYPE = {
    "light_cav": "stable_effectiveness",
    "knight": "stable_effectiveness",
    "camel": "stable_effectiveness",
    "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
    "skirmisher": "ranged_effectiveness",
    "archer": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness",
    "gunpowder": "ranged_effectiveness",
    "scorpion": "ranged_effectiveness",
    "militia": "militia_value",
    "spear": "militia_value",
    "shock_infantry": "militia_value",
    "ram": "anti_building_score",
    "bombard_cannon": "anti_building_score",
    "trebuchet": "anti_building_score",
}
```

#### New output structure
```json
{
  "power_units": {
    "cavalry": {
      "light_cav": { "unit_slug", "unit_name", "percentile", "strength", ... },
      "knight": { ... },
      "camel": null,
      "steppe_lancer": null,
      "elephant": null
    },
    "ranged": { ... },
    "infantry": { ... },
    "siege": { ... }
  },
  "strength_profile": {
    "light_cav": "strong",
    "knight": "signature",
    "camel": null,
    ...
  },
  "strategic_summary": { "strong_areas": [...], ... },
  "strategic_description": "..."
}
```

#### Removed code
- `ROLE_DEFS` → replaced by `COLUMN_DEFS` + `LINE_SCORE_TYPE`
- `_build_role_dict()` — no more role-level aggregation
- `_determine_narrative_key()` — no more role-level narratives
- Anti-cav cavalry/infantry split logic (lines 695-730)
- `_ROLE_NAMES` dict
- Old `strength_profile` per-role logic

#### Strategic description
`_generate_strategic_description()` rewritten to check per-line strengths:
- "cavalry is strong" = any cavalry line ≥ "strong"
- "ranged is strong" = any ranged line ≥ "strong"
- Same 3-part structure (playstyle, defense, push strategy)

#### Matchup recommendations (Phase B)
- `COUNTER_MAP` updated to remove `anti_cav_pool` references
- Query `anti_cav` from `stable` and `spear` lines directly instead of `anti_cav_combined` from `anti_cav_pool`

### 3. Frontend (`matchup.js` + `matchup.css`)

#### matchup.js
- Remove `COLUMN_LAYOUT` (old main+sub structure)
- Add `COLUMN_DEFS` and `LINE_NAMES` matching backend
- Render loop: for each column, iterate line slugs, show unit badge or "not available"
- Remove sub-section rendering (anti_cavalry, anti_archer, anti_cav_infantry)
- Remove `getNarrative()` (role-level narratives)
- Keep tooltip rendering unchanged

#### matchup.css
- Remove `.role-sub-section` styling
- Add `.line-section` styling for individual line entries
- Add `.line-unavailable` dimmed state
- Column grid stays 4-column responsive

### 4. `app.py` API

The `/api/civ-power-units/<civ>` endpoint loads from `civ_power_units.json` — no code change needed, just the JSON structure changes. Frontend adapts to the new structure.

## Migration

1. Modify `compute_battle_scores.py` (per-line normalization)
2. Rerun: `cd webapp && python3 compute_battle_scores.py --full`
3. Modify `best_units.py` (per-line structure)
4. Rerun: `cd webapp && python3 best_units.py`
5. Update `matchup.js` + `matchup.css`
6. Verify all 50 civs render correctly
