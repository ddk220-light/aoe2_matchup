# Raiding Score Redesign: Attrition-Based Building Destruction

## Problem

The current raiding building score uses a pure DPS formula that ignores:
- Buildings fighting back (arrows killing infantry)
- Multiple arrows from castles and garrisoned TCs
- University tech upgrades (Masonry/Architecture) on building armor
- Building armor class 21 negating Arson bonus
- Unit survivability (HP, pierce armor) under fire

## Solution

Replace the DPS formula with **minimum units to destroy the building** (`N_min`), computed via an O(1) attrition formula that models focus-fire sequential kills.

## Attrition Formula

The building focus-fires one unit at a time. Each unit takes `h/f` seconds to die. As units die, army DPS decreases.

**Phase-by-phase damage:**

| Phase | Units alive | Damage dealt |
|---|---|---|
| 0 | N | N * d * h/f |
| 1 | N-1 | (N-1) * d * h/f |
| ... | ... | ... |
| N-1 | 1 | 1 * d * h/f |

Total damage = `(d*h/f) * N*(N+1)/2` (triangular sum)

**Solve for minimum N where total damage >= building HP:**

```
N*(N+1) >= 2*B*f / (d*h)

Let C = 2*B*f / (d*h)
N_min = ceil((-1 + sqrt(1 + 4*C)) / 2)
```

Where:
- `d` = unit anti-building DPS = `max(1, (melee_atk - building_melee_armor) + (bonus_vs_buildings - building_armor_class_21)) / unit_reload`
- `f` = building DPS vs unit = `num_arrows * max(1, arrow_attack - unit_pierce_armor) / building_reload`
- `h` = unit HP
- `B` = building HP

## Building Definitions

Fully upgraded Spanish buildings. Blacksmith (Fletching/Bodkin/Bracer) + Chemistry always applied. Masonry/Architecture toggled to create two variants per building; scores averaged.

### Castle (empty, 5 base arrows, Hoardings always on)

| Stat | WITH Masonry+Arch | WITHOUT |
|---|---|---|
| HP | 7028 | 5808 |
| Melee armor | 10 | 8 |
| Building armor (class 21) | 6 | 0 |
| Arrows | 5 | 5 |
| Attack per arrow | 15 | 15 |
| Reload | 2.0s | 2.0s |

HP derivation: 4800 * 1.1 (Masonry) * 1.1 (Architecture) * 1.21 (Hoardings) = 7028
Attack derivation: 11 base + 1 Fletching + 1 Bodkin + 1 Bracer + 1 Chemistry = 15

### Town Center (15 garrisoned villagers)

| Stat | WITH Masonry+Arch | WITHOUT |
|---|---|---|
| HP | 2904 | 2400 |
| Melee armor | 5 | 3 |
| Building armor (class 21) | 6 | 0 |
| Arrows | 15 | 15 |
| Attack per arrow | 9 | 9 |
| Reload | 2.0s | 2.0s |

HP derivation: 2400 * 1.1 * 1.1 = 2904
Attack derivation: 5 base + 1 + 1 + 1 + 1 = 9

## Scoring Flow

```
For each infantry unit:
  1. Compute N_min for all 4 building variants (castle+uni, castle-uni, tc+uni, tc-uni)
  2. raid_vs_castle_raw = (N_castle_with + N_castle_without) / 2
  3. raid_vs_tc_raw = (N_tc_with + N_tc_without) / 2
  4. Normalize each 0-100 (inverted: lower N_min = higher score)
  5. raid_building = (raid_vs_castle_norm + raid_vs_tc_norm) / 2
```

## Damage Formula Fix

The unit-vs-building damage must separately handle melee armor and building armor class:

```python
# OLD (incorrect - treats building armor as 0)
damage = max(1, melee_atk + bonus_vs_buildings - building_melee_armor)

# NEW (correct - separate armor classes)
melee_contribution = melee_atk - building_melee_armor
building_contribution = bonus_vs_buildings - building_armor_class_21
damage = max(1, melee_contribution + building_contribution)
```

## Composite Weights

| Component | Old | New |
|---|---|---|
| Movement speed | 30% | **25%** |
| Villager kill speed | 30% | **25%** |
| Building destruction (N_min) | 40% | **50%** |

Building score now encodes both offensive DPS AND defensive survivability, justifying higher weight.

## Validation Example: Champion

```
Champion: 70 HP, melee=13, Arson=+2, pierce_armor=4, reload=2.0

Castle WITH:    d=0.5  f=27.5  N=105
Castle WITHOUT: d=3.5  f=27.5  N=36
avg castle = 70.5

TC WITH:        d=2.0  f=37.5  N=39
TC WITHOUT:     d=6.0  f=37.5  N=21
avg TC = 30
```

## Files to Modify

- `webapp/compute_battle_scores.py`: Replace `BUILDING_TARGETS` and `compute_raiding_scores()` building section
- No simulation.py changes needed (formula is O(1), not tick-based)
- No frontend changes needed (score names unchanged)
