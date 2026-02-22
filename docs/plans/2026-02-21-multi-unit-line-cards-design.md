# Multi-Unit Line Cards Design

**Date:** 2026-02-21
**Status:** Approved

## Summary

Show all units in a line card when a civ has multiple units sharing the same unit line (e.g., Paladin + Elite Leitis for Lithuanians in the knight line). Currently only the highest-scoring unit is shown (`LIMIT 1`).

## Scope

~41 civ/line combinations have 2 units in the same line:
- 11 knight line (Paladin + unique cavalry)
- 15 militia line (Champion + unique infantry)
- 7 archer line (Arbalester + unique archer)
- 8 cav_archer line (Heavy CA + unique mounted ranged)

## Design Decisions

| Decision | Choice |
|----------|--------|
| Data structure | Array per line (single entry becomes `[entry1, entry2]`, null stays null) |
| Scoring | Both units scored independently with own percentile |
| Line strength | Best unit (first in array) determines strength_profile |
| Icon display | Side-by-side, equal size |
| Sort order | Descending by score_value |

## Data Changes

### `best_units.py`

Remove `LIMIT 1` from the per-line query in `compute_civ_power_units()`. Fetch all units, build an array per line sorted by score descending. Change line entry from single object to array.

Before:
```json
"knight": { "unit_name": "Elite Leitis", "percentile": 98, ... }
```

After:
```json
"knight": [
  { "unit_name": "Elite Leitis", "percentile": 98, "strength": "signature", ... },
  { "unit_name": "Paladin", "percentile": 75, "strength": "strong", ... }
]
```

Unavailable lines remain `null` (not empty array).

`strength_profile` uses `entries[0]["strength"]` (best unit).

All downstream consumers of `power_units` that read individual line entries must be updated to handle arrays: `_generate_strategic_description()`, `get_matchup_recommendations()`.

### `matchup.js`

Update `renderAnalysis()` to iterate the array. Each unit renders as a full badge via `renderUnitBadge()`.

Icon layout: both icons side-by-side at equal size within the line card.

### `matchup.css`

Add horizontal icon row layout within `.line-section` for multi-unit lines.

### No changes to

- `compute_battle_scores.py` (scoring pipeline unchanged)
- `app.py` (serves JSON as-is)
- DB schema
