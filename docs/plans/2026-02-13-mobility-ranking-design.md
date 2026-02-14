# Mobility Ranking for Ranged Units

## Overview

Add a new "Mobility Ranking" section for all ranged units (archer, skirmisher, cav_archer lines), displayed alongside the existing Ranged Power Rankings. The score captures how effective a ranged unit is when leveraging movement — combining hit-and-run DPS potential with durability.

## Formula

```
mobility_score = (normalized(speed * dps) + normalized(pierce_armor) + normalized(hp)) / 3
```

- **speed * dps**: `movement_speed * (attack / reload_time)` — hit-and-run effectiveness
- **pierce_armor**: `final_pierce_armor` — resistance to incoming ranged fire
- **hp**: `final_hp` — raw survivability

Each component is normalized 0–100 across all units in the archery pool (min→0, max→100). The three normalized values are averaged equally (33.3% each).

## Architecture

### Backend (`compute_battle_scores.py`)

Computed inside `compute_archery_role_scores()`, after the existing benchmark simulations:

1. First pass: collect raw values for each unit
   - `speed_dps = movement_speed * (attack / attack_speed)` where attack_speed is already 1/reload_time from `prepare_combat_unit()`
   - `pierce_armor` from combat unit dict
   - `hp` from combat unit dict
2. Normalize each to 0–100 across the full archery pool
3. Composite: average of 3 normalized values
4. Store sub-scores (`mobility_speed_dps`, `mobility_pierce_armor`, `mobility_hp`) for UI breakdown

New score types added to `ARCHERY_ROLE_SCORE_TYPES`:
- `mobility_score` — the composite
- `mobility_speed_dps` — normalized speed*dps component
- `mobility_pierce_armor` — normalized pierce armor component
- `mobility_hp` — normalized hp component

### Frontend (`index.html`)

1. New ranking tab `"mobility"` in the archery section, with name "Mobility Rankings"
2. `mobilityColumns` array mirroring the archery columns pattern:
   - Civ, Unit, Line, Score (mobility_score), Speed*DPS, Pierce Armor, HP, then stat columns
3. Score breakdown popover for `mobility_score` showing the 3 sub-components with equal 33.3% weights
4. Default sort by `mobility_score` descending
5. Add `mobility_score` and sub-scores to numeric formatting and `ARCHERY_SLUGS` sort sets

### No changes needed

- **app.py**: Already loads all `battle_scores` rows for archery lines via `_attach_scores()`
- **Database schema**: Uses existing `battle_scores` table
- **Build pipeline**: Runs as part of existing `compute_battle_scores.py`
