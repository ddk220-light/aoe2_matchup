# Anti Archer Ranking — Design

## Overview

New ranking section for all ranged units measuring effectiveness against archer-class opponents. Appears as a separate tab alongside the existing "Ranged Power Rankings" in the Archery Range section.

## Scoring Formula

`anti_archer = 0.5 * eco_score + 0.3 * pop_score + 0.2 * power`

### Benchmarks (8 simulations per unit)

| Key | Opponent | Mode | Details |
|-----|----------|------|---------|
| `aa_eco_vs_arb` | Chinese Arbalester | `res` (3000) | HP% remaining |
| `aa_eco_vs_ca` | Chinese Heavy Cav Archer | `res` (3000) | HP% remaining |
| `aa_eco_vs_hc` | Spanish Hand Cannoneer | `res` (3000) | HP% remaining |
| `aa_pop_vs_arb` | Chinese Arbalester | `fixed_hp` (30,30) | HP% remaining |
| `aa_pop_vs_ca` | Chinese Heavy Cav Archer | `fixed_hp` (30,30) | HP% remaining |
| `aa_pop_vs_hc` | Spanish Hand Cannoneer | `fixed_hp` (30,30) | HP% remaining |
| `aa_power_vs_hussar` | Spanish Hussar | `res` (3000) | HP% remaining |
| `aa_power_vs_champ` | Chinese Champion | `res` (3000) | HP% remaining |

### Derived Scores

- `aa_eco_score` = avg(aa_eco_vs_arb, aa_eco_vs_ca, aa_eco_vs_hc)
- `aa_pop_score` = avg(aa_pop_vs_arb, aa_pop_vs_ca, aa_pop_vs_hc)
- `aa_power` = avg(aa_power_vs_hussar, aa_power_vs_champ)
- `anti_archer` = 0.5 * aa_eco_score + 0.3 * aa_pop_score + 0.2 * aa_power

All keys prefixed with `aa_` to avoid collisions with existing `ranged_power` scores.

## Approach: Parallel Role Score System

Separate `compute_anti_archer_scores()` function in `compute_battle_scores.py`, following the same pattern as `compute_archery_role_scores()`.

## Data Storage

Same `battle_scores` table in `aoe2_reference.db`. 12 score types per unit (8 benchmarks + 3 derived + 1 composite).

**Critical constraint:** `write_role_scores_to_db()` deletes ALL rows for a line_slug before inserting. Since anti-archer uses the same line slugs (archer, skirmisher, cav_archer), both archery and anti-archer score dicts must be **merged before writing** to avoid one overwriting the other.

Score types stored:
```
anti_archer, aa_eco_score, aa_pop_score, aa_power,
aa_eco_vs_arb, aa_eco_vs_ca, aa_eco_vs_hc,
aa_pop_vs_arb, aa_pop_vs_ca, aa_pop_vs_hc,
aa_power_vs_hussar, aa_power_vs_champ
```

## API

No new endpoint. Existing `/api/ref/unit-line/<line_slug>` loads all `battle_scores` rows for sub_lines. The `aa_*` scores attach automatically via `_attach_scores()`.

## Frontend

### Line Definition (app.py)

```python
"anti_archer": {
    "name": "Anti Archer Rankings",
    "building": "Archery Range",
    "sub_lines": ["archer", "cav_archer", "skirmisher"],
}
```

### Tab (index.html)

New entry in `UNIT_LINES` JS object. Added to `ARCHERY_SLUGS` set. Default sort: `anti_archer` descending.

### Table Columns

| Key | Label | Tooltip |
|-----|-------|---------|
| `civ_name` | Civ | — |
| `unit_name` | Unit | — |
| `line_slug` | Line | (meta-line only) |
| `anti_archer` | **Score** | "Weighted: 50% Eco + 30% Pop + 20% Power" |
| `aa_eco_score` | Eco | "Avg HP% after 3K resource fights vs Chinese Arb, Chinese Cav Archer, Spanish HC" |
| `aa_pop_score` | Pop | "Avg HP% after 30v30 vs Chinese Arb, Chinese Cav Archer, Spanish HC" |
| `aa_power` | Power | "Avg HP% after 3K resource fights vs Spanish Hussar, Chinese Champion" |
| `dps` | DPS | — |
| `final_hp` | HP | — |
| `final_attack` | Atk | — |
| `final_melee_armor` | M.Arm | — |
| `final_pierce_armor` | P.Arm | — |
| `final_speed` | Speed | — |
| `final_range` | Range | — |
| `total_cost` | Cost | — |
| `total_upgrade_cost` | Upg Cost | — |
| `special_abilities` | Special | — |

### Stat Cols for Median Coloring

```
anti_archer, aa_eco_score, aa_pop_score, aa_power,
dps, final_hp, final_attack, final_melee_armor,
final_pierce_armor, final_speed, final_range
```
