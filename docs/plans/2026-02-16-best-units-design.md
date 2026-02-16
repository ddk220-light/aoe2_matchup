# Best Units Logic — Design Document

**Date:** 2026-02-16
**Status:** Approved
**Approach:** Hybrid Scoring with Targeted Simulation

## Overview

Design logic to identify:
1. **Civ Power Units** — each civilization's best units by role (pre-computed)
2. **Matchup Recommendations** — best units and compositions for Civ A vs Civ B (on-the-fly)

## Data Assets

### Existing Data (no new computation needed for Phase A)

| Source | Contents | Size |
|--------|----------|------|
| `battle_scores` table | 10,220 rows: per-unit scores across 48 dimensions with rank + median_delta | Instant queries |
| `ref_units` table | ~3,000 rows: fully computed unit stats (HP, attack, armor, cost, special mechanics) | Instant queries |
| Simulation engine | `simulate_battle()` — tick-based combat sim, ~1.3ms/battle | On-demand |

### Key Score Types Available

| Line | Composite Scores | Role Scores |
|------|-----------------|-------------|
| `stable` | `stable_effectiveness` (70% general + 30% anti_cav) | `general_combat`, `anti_cav` |
| `archer`, `cav_archer`, `scorpion`, `gunpowder` | `ranged_effectiveness` (70% general + 30% anti_archer) | `general_combat`, `anti_archer`, `mobility_score` |
| `militia`, `spear`, `shock_infantry` | `militia_value` (50% general + 30% anti_cav + 20% raid) | `general_combat`, `anti_cav_value`, `raiding_value` |
| `siege` | `anti_building_score` | `time_to_kill` |

### Age Casing Note

The `battle_scores` table uses mixed age casing:
- `Imperial` (capitalized) for `stable` line
- `imperial` (lowercase) for all other lines
- `castle` (lowercase) for siege castle-age entries

Queries must handle this: use `LOWER(age)` or query both casings.

---

## Phase A: Civ Power Units (Pre-computed)

### Role Definitions

| Role | Lines Queried | Score Type | Selection Logic |
|------|--------------|------------|-----------------|
| **Power Cavalry** | `stable` | `stable_effectiveness` | Highest `median_delta` among civ's stable units |
| **Power Ranged** | `archer`, `cav_archer`, `scorpion`, `gunpowder` | `ranged_effectiveness` | Highest `median_delta` across all ranged lines |
| **Power Infantry** | `militia`, `shock_infantry` | `militia_value` | Highest `median_delta` among infantry |
| **Anti-Cavalry** | `spear`, `militia` | `anti_cav_value` | Best anti-cav specialist |
| **Best Trash** | all lines | `general_combat` | Best zero-gold unit (filtered by `cost_gold=0` from `ref_units`) |
| **Best Siege** | `siege` | `anti_building_score` | Best building destroyer |

### Algorithm

```
For each of 50 civilizations:
  For each role:
    1. Query battle_scores WHERE civ_name=? AND score_type=? AND line_slug IN (?)
    2. For "Best Trash": join with ref_units to filter cost_gold=0
    3. Select unit with highest median_delta
    4. Classify strength tier:
       - "signature": rank <= 5 AND median_delta > 20
       - "strong": median_delta > 10
       - "average": -10 <= median_delta <= 10
       - "weak": median_delta < -10
    5. Store result
```

### Output Schema

```json
{
  "civ_name": "Franks",
  "age": "imperial",
  "power_units": {
    "cavalry": {
      "unit_slug": "paladin",
      "line_slug": "stable",
      "score": 58.5,
      "rank": 20,
      "median_delta": 25.2,
      "is_signature": false,
      "strength": "strong"
    },
    "ranged": {
      "unit_slug": "elite_throwing_axeman_franks",
      "line_slug": "gunpowder",
      "score": 55.3,
      "rank": 4,
      "median_delta": 25.8,
      "is_signature": true,
      "strength": "signature"
    },
    "infantry": {
      "unit_slug": "champion",
      "line_slug": "militia",
      "score": 51.2,
      "rank": 32,
      "median_delta": 0.05,
      "is_signature": false,
      "strength": "average"
    },
    "anti_cavalry": {
      "unit_slug": "halberdier",
      "line_slug": "spear",
      "score": 83.8,
      "rank": 26,
      "median_delta": 0.0,
      "is_signature": false,
      "strength": "average"
    },
    "trash": {
      "unit_slug": "hussar",
      "line_slug": "stable",
      "score": 18.7,
      "rank": 111,
      "median_delta": -18.6,
      "is_signature": false,
      "strength": "weak"
    },
    "siege": {
      "unit_slug": "siege_ram",
      "line_slug": "siege",
      "score": 94.6,
      "rank": 37,
      "median_delta": 2.3,
      "is_signature": false,
      "strength": "average"
    }
  },
  "strength_profile": {
    "cavalry": "strong",
    "ranged": "signature",
    "infantry": "average",
    "anti_cavalry": "average",
    "trash": "weak",
    "siege": "average"
  }
}
```

### Strength Tier Thresholds

| Tier | Criteria | Meaning |
|------|----------|---------|
| `signature` | rank <= 5 AND median_delta > 20 | Top-tier, civ-defining unit |
| `strong` | median_delta > 10 | Clearly above average |
| `average` | -10 <= median_delta <= 10 | Around the median |
| `weak` | median_delta < -10 | Below average for this role |

### Storage

Pre-computed as a JSON file: `webapp/civ_power_units.json`

Structure: `{ "Franks": { "imperial": {...}, "castle": {...} }, "Britons": {...}, ... }`

Generated by adding a function to `compute_battle_scores.py` (or a separate script) that runs after battle_scores are computed.

---

## Phase B: Matchup Recommendations (On-the-fly)

### Input

- `civ_a`: player's civilization
- `civ_b`: opponent's civilization
- `age`: "imperial" (default) or "castle"

### Algorithm

#### Step 1: Load Power Units

Load pre-computed power units for both civs from `civ_power_units.json`.

#### Step 2: Identify Counter-Roles

For each of Civ B's power units that are "strong" or "signature", determine what Civ A needs:

| Opponent Strength | Counter Strategy | Civ A Score to Query |
|---|---|---|
| Strong cavalry | Anti-cavalry units | `anti_cav_value` in spear/militia; `anti_cav` in stable (camels) |
| Strong ranged | Close-distance units or anti-archer | `general_combat` in stable (cavalry closes); `anti_archer` in archery |
| Strong infantry | Ranged or cavalry | `general_combat` in archer/stable (both counter infantry) |
| Strong siege | Mobile snipe units | `general_combat` in stable (cavalry snipes siege) |

For each needed counter-role, query Civ A's top 3 units by `median_delta` in the relevant score type.

#### Step 3: Simulation Validation

For top 3 counter candidates per opponent power unit:

```
For each candidate:
  sim1 = simulate_battle(candidate, opponent_power_unit, 3000)  # cost efficiency
  sim2 = simulate_battle(candidate, opponent_power_unit, 0, fixed_count=30)  # pop efficiency
  counter_score = 0.6 * resource_score + 0.4 * pop_score
```

Total simulations: ~6 battles (~8ms)

#### Step 4: Composition Generation

For top 2 gold counter-units from Step 3, pair with best available trash:

| If gold unit is... | Pair with... | Rationale |
|---|---|---|
| Melee cavalry | Skirmisher | Skirm handles halbs that counter cavalry |
| Ranged unit | Hussar | Hussar tanks for ranged, raids, kills siege |
| Infantry | Hussar or Skirmisher | Depends on opponent composition |
| Camel | Skirmisher | Same as cavalry logic |

Simulate each composition vs opponent's likely army:
- Budget: 5000 resources
- Split: 70% gold unit, 30% trash unit
- Opponent: their power unit (70%) + their trash (30%)
- Run 2-4 additional simulations

#### Step 5: Reasoning Generation

For each recommended composition, generate a human-readable reason:

```python
reasons = []
if gold_unit.attack_range > 0 and opponent_unit.movement_speed < 1.0:
    reasons.append(f"{gold_unit.name} outranges slow {opponent_unit.name}")
if gold_unit.movement_speed > opponent_unit.movement_speed:
    reasons.append(f"{gold_unit.name} closes distance on {opponent_unit.name}")
if has_bonus_damage(gold_unit, opponent_unit):
    reasons.append(f"{gold_unit.name} has bonus damage vs {opponent_unit.armor_class}")
reasons.append(f"{trash_unit.name} handles {expected_counter_to_gold}")
```

### Output Schema

```json
{
  "civ_a": "Franks",
  "civ_b": "Britons",
  "age": "imperial",
  "opponent_strengths": [
    {
      "role": "ranged",
      "unit_slug": "elite_longbowman_britons",
      "strength": "signature",
      "median_delta": 45.2
    }
  ],
  "recommended_compositions": [
    {
      "rank": 1,
      "gold_unit": {
        "unit_slug": "paladin",
        "role": "cavalry",
        "line_slug": "stable"
      },
      "trash_unit": {
        "unit_slug": "imp_elite_skirm",
        "role": "trash",
        "line_slug": "skirmisher"
      },
      "resource_split": {"gold_pct": 70, "trash_pct": 30},
      "scores": {
        "resource_efficiency": 45.2,
        "pop_efficiency": 62.1,
        "composite": 51.9,
        "composition_win_margin": 38.5
      },
      "reasoning": "Paladin closes distance on Longbowman; Elite Skirmisher handles Halberdier support"
    },
    {
      "rank": 2,
      "gold_unit": {
        "unit_slug": "elite_throwing_axeman_franks",
        "role": "ranged",
        "line_slug": "gunpowder"
      },
      "trash_unit": {
        "unit_slug": "hussar",
        "role": "trash",
        "line_slug": "stable"
      },
      "resource_split": {"gold_pct": 70, "trash_pct": 30},
      "scores": {
        "resource_efficiency": 38.1,
        "pop_efficiency": 55.4,
        "composite": 45.0,
        "composition_win_margin": 22.3
      },
      "reasoning": "Throwing Axeman has high ranged damage vs archers; Hussar raids and tanks"
    }
  ],
  "individual_counters": [
    {
      "unit_slug": "paladin",
      "vs_unit": "elite_longbowman_britons",
      "resource_score": 45.2,
      "pop_score": 62.1,
      "composite": 51.9
    }
  ]
}
```

### Performance Budget

| Step | Time | Simulations |
|------|------|-------------|
| Load power units | ~1ms | 0 |
| Score lookups | ~5ms | 0 |
| Counter validation sims | ~8ms | 6 |
| Composition sims | ~5ms | 4 |
| **Total** | **~19ms** | **10** |

---

## Implementation Components

### New Files

1. **`webapp/compute_civ_power_units.py`** (or function in `compute_battle_scores.py`)
   - Reads `battle_scores` table
   - Computes power units for all 50 civs
   - Writes `civ_power_units.json`

2. **`webapp/best_units.py`** (module)
   - `get_civ_power_units(civ_name, age)` — reads pre-computed JSON
   - `get_matchup_recommendations(civ_a, civ_b, age)` — on-the-fly computation
   - Internal helpers for counter-role mapping, composition generation, reasoning

### New API Endpoints

1. **`GET /api/civ-power-units/<civ_name>`**
   - Returns pre-computed power units for a civ
   - Optional `?age=imperial` parameter

2. **`GET /api/matchup-recommendations/<civ_a>/<civ_b>`**
   - Returns matchup-specific unit and composition recommendations
   - Optional `?age=imperial` parameter

### Build Pipeline Addition

After `compute_battle_scores.py` runs:
```bash
python3 -m webapp.compute_civ_power_units  # or integrated into battle scores script
```

---

## Edge Cases

1. **Civ has no units in a role** (e.g., some civs lack cavalry): Return `null` for that role
2. **Opponent has no clear strengths** (all roles "average"): Recommend Civ A's own power units (play to your strengths)
3. **Both civs strong in same role**: Counter-role mapping still applies; both have strong cavalry → check whose is better
4. **Trash unit identification**: Join with `ref_units` to check `final_cost_gold = 0`. Hussar, Halberdier, Elite Skirmisher are the main trash units
5. **Age casing**: Normalize age to lowercase for all queries; special-case stable line (`Imperial` vs `imperial`)

## Non-Goals

- No frontend/UI design (separate task)
- No changes to existing scoring formulas/weights
- No pre-computation of all 2,450 civ pair matchups
- No micro/positional considerations (our sim doesn't model movement)
