# Ease of Creation Integration into Matchup Advisor

## Goal

Integrate `unit_creation_ease` data into the matchup advisor's combo cards to provide context-dependent statements about how easy/hard a combo is to mass relative to the opponent, and to sort zero-gap combos by ease.

## Approach: Enrich at Pre-Compute Time, Compare in Frontend (Approach C)

Bake ease sub-scores into `civ_power_units.json` via `_build_unit_entry`. All comparison logic stays in the frontend JS alongside existing combo logic.

## Data Shape

Each unit entry in `civ_power_units.json` gains:

```json
"ease": {
    "score": 0.83,
    "is_castle_unit": false,
    "creation_time": 21,
    "total_upgrade_cost": 1150,
    "needs_castle_ut": false,
    "sub_scores": {
        "not_castle": 1.0,
        "creation_time": 0.64,
        "upgrade_cost": 0.81,
        "no_castle_ut": 1.0,
        "speed": 0.68
    }
}
```

## Combo Statements

Each combo card gets a statements section below the summary, built from two sources.

### Combat Context (from gap categories)

| Gap makeup | Statement |
|-----------|-----------|
| All gaps `pop` type | "Loses on pop efficiency, but trades better on eco" |
| All gaps `eco` type | "Less eco-efficient, but more pop-efficient" |
| Mixed `pop` + `eco` | "Mixed results — pop-efficient vs some, eco-efficient vs others" |
| All gaps `loss` type | No combat qualifier, just ease statement |

### Ease Statements (compared to opponent's best combo)

Factors with ≥0.15 delta on sub-scores, up to 2-3:

| Factor | Higher | Lower |
|--------|--------|-------|
| not_castle | (skip) | "Needs a Castle" |
| creation_time | "Trains faster" | "Slower to train" |
| upgrade_cost | "Cheaper upgrades" | "Costlier upgrades" |
| no_castle_ut | (skip if same) | "Needs a Castle unique tech" |
| speed | "Faster on the field" | "Slower on the field" |

Castle is always included if one combo has a castle unit and the opponent doesn't.

### Scenario Behavior

- **Zero-gap:** No statement. Sort by ease (easiest first).
- **Has gaps, easier to mass:** "Combat context. Easier to mass — factors."
- **Has gaps, harder:** "Combat context. Also harder to get going — factors."

### Combined Examples

- "Loses on pop efficiency, but trades better on eco. Easier to mass — trains faster and cheaper upgrades."
- "Less eco-efficient, but more pop-efficient. Also harder to get going — needs a Castle."
- "Doesn't win outright. Easier to mass — cheaper upgrades."
- "Doesn't win outright and harder to get going — costlier upgrades and slower to train."

## Sort Order

Zero-gap combos sorted by average ease_score (top unit + partner), descending. Non-zero-gap cards sorted by gap size first, then ease as tiebreaker.

## Files Changed

| File | Change |
|------|--------|
| `webapp/best_units.py` | `_build_unit_entry()` — add ease dict. Batch-load ease data per civ. Include in `_strip_siege_entries()`. |
| `webapp/static/js/matchup_advisor.js` | `_buildComboCard()` — add statements div. `_buildTopColumn()` — sort by ease. New helpers: `_computeEaseStatements()`, `_computeCombatContext()`, `_avgEase()`. |
| `webapp/static/css/matchup_advisor.css` | Styles for `ma-ease-statement`, `ma-ease-upside`, `ma-ease-downside`. |

## Build Step

Re-run `save_civ_power_units()` to regenerate `civ_power_units.json` with ease data.

## Not in Scope

- No changes to per-unit comparison grid
- No changes to sim overlay icons
- No new API endpoints
