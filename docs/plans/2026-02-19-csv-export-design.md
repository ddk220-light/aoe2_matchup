# CSV Export for Unit Rankings

## Overview
Add a per-category "Export CSV" button to the unit rankings page that exports all unit scores including raw (pre-normalization) sub-scores, normalized sub-scores, composite scores, and rank.

## Approach: Client-Side Export
The CSV is built in JavaScript from `currentEnriched[]` data already loaded via the API. Raw scores are persisted during battle score computation and served alongside normalized scores.

## Data Flow
```
compute_battle_scores.py stores raw + normalized scores in battle_scores DB table
  → app.py serves both via /api/ref/unit-line/<slug> response
  → rankings.js enriches data client-side (DPS, PES, RES, etc.)
  → Export button builds CSV from currentEnriched[]
  → Browser downloads <line>_<age>_rankings.csv
```

## CSV Columns by Category

### All categories include
Rank, Civ, Unit, Line (if composite category)

### Infantry
- Composites: militia_value, general_combat, anti_cav, raid_building
- GC sub-scores (raw + normalized): gc_30v30_vs_paladin, gc_30v30_vs_arb, gc_30v30_vs_champ, gc_3k_vs_paladin, gc_3k_vs_arb, gc_3k_vs_champ
- AC sub-scores (raw + normalized): gc_30v30_vs_paladin (shared), ac_30v30_vs_elephant, ac_30v30_vs_hussar, gc_3k_vs_paladin (shared), ac_3k_vs_elephant, ac_3k_vs_hussar
- Raid sub-scores: raid_vs_tc_nmin, raid_vs_castle_nmin
- Stats: DPS, HP, Atk, M.Arm, P.Arm, Speed, Cost, Upg Cost

### Archery
- Composites: ranged_effectiveness, general_combat, anti_archer
- GC sub-scores (raw + normalized): gc_30v30_vs_paladin, gc_30v30_vs_arb, gc_30v30_vs_champ, gc_3k_vs_paladin, gc_3k_vs_arb, gc_3k_vs_champ
- AA sub-scores (raw + normalized): aa_30v30_vs_arb, aa_30v30_vs_ca, aa_30v30_vs_ele_archer, aa_3k_vs_arb, aa_3k_vs_ca, aa_3k_vs_ele_archer
- Stats: DPS, HP, Atk, M.Arm, P.Arm, Speed, Range, Cost, Upg Cost

### Stable
- Composites: stable_effectiveness, general_combat, anti_cav
- GC sub-scores (raw + normalized): gc_30v30_vs_paladin, gc_30v30_vs_arb, gc_30v30_vs_champ, gc_3k_vs_paladin, gc_3k_vs_arb, gc_3k_vs_champ
- AC sub-scores (raw + normalized): gc_30v30_vs_paladin (shared), ac_30v30_vs_heavy_camel, ac_30v30_vs_elephant, gc_3k_vs_paladin (shared), ac_3k_vs_heavy_camel, ac_3k_vs_elephant
- Stats: DPS, HP, Atk, M.Arm, P.Arm, Speed, Cost, Upg Cost

### Siege
- Scores: anti_building_score, time_to_kill
- Stats: DPS, HP, Atk, M.Arm, P.Arm, Speed, Range, Cost, Upg Cost

## Changes Required

### 1. compute_battle_scores.py
Before min-max normalization steps, save raw scores with `_raw` suffix. Both raw and normalized values get written to `battle_scores` table.

### 2. app.py
Include `_raw` score types in the unit-line API response (they come through the same `battle_scores` query automatically).

### 3. rankings.js
- Add `exportCSV()` function that builds CSV from `currentEnriched[]`
- Rank = row position when sorted by the category's primary composite score descending
- Export button placed next to civ filter input
- File named `{line}_{age}_rankings.csv`

### 4. rankings.css
Style export button to match medieval theme.

## UI
Export button sits next to the civ filter, small and unobtrusive. Downloads immediately on click.
