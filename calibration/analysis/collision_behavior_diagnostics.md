# Standard-unit collision and compression diagnostics

## Bottom line

The current Genie data has both a base collision radius and a per-unit `min_collision_size_multiplier`. That multiplier is the closest thing to the “overlap radius” remembered from Advanced Genie Editor. It is not a second radius: it scales the collision size under engine-selected circumstances.

It is important, but it is **not the direct explanation for Hand Cannoneer compression**:

- Hand Cannoneer has collision radius **0.20 tile**, nominal same-unit diameter **0.40 tile**, and multiplier **1.0**.
- In the locked FINAL tape, its same-owner nearest-neighbor spacing is p10 **0.084**, median **0.308**, and p90 **0.540** tile.
- **72.5%** of HC observations are below the nominal 0.40-tile diameter despite the multiplier being 1.0.
- Against melee, HC median spacing is only **0.223–0.309 tile**; against ranged/siege it is generally **0.466–0.824 tile**.

So the missing behavior is not “load HC’s `.dat` multiplier.” It is a runtime formation/movement/contact rule that permits same-team ranged bodies to interpenetrate in particular combat contexts. The current FINAL command capture is too lossy to name that rule exactly.

## Locked evidence

Only these inputs were used:

- Tape: `calibration/source/aoe2_golden_STANDARD_UNITS_FINAL.zip`
- Tape SHA-256: `31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9`
- Tape population: **339 recordings**, all game version **180059**, all position streams **10 Hz**
- Current installed data: `D:\SteamLibrary\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat`
- `.dat` SHA-256: `CE3530DF36CF0B333A9751CB0FF94460FE904F811FEECEC8AE9794701622B4CF`
- Parser: `genieutils-py 0.1.2`

The audit is reproducible in:

- `tools/simjs/collision_dat_audit.py`
- `tools/simjs/collision_tape_audit.py`
- `calibration/analysis/current_genie_collision_fields.json`
- `calibration/analysis/final_tape_collision_spacing.json`

## What the current `.dat` contains

`collision_size_x/y` is the base physics radius. `outline_size_x/y` is a distinct visual/selection-sized field. `dead_fish.min_collision_size_multiplier` is the unit-specific collision multiplier. All 14 standard units have obstruction type **5** and obstruction class **2**, so obstruction type does not distinguish them.

| Standard unit | Collision radius | Nominal diameter | Min multiplier | Multiplied diameter | Outline X |
|---|---:|---:|---:|---:|---:|
| Champion | 0.20 | 0.40 | 0.80 | 0.32 | 0.20 |
| Halberdier | 0.20 | 0.40 | 0.80 | 0.32 | 0.20 |
| Elite Fire Lancer | 0.20 | 0.40 | 0.80 | 0.32 | 0.20 |
| Hussar | 0.25 | 0.50 | 0.50 | 0.25 | 0.40 |
| Paladin | 0.25 | 0.50 | 0.50 | 0.25 | 0.40 |
| Heavy Camel | 0.25 | 0.50 | 0.50 | 0.25 | 0.40 |
| Elite Battle Elephant | 0.25 | 0.50 | 0.50 | 0.25 | 0.50 |
| Elite Steppe Lancer | 0.25 | 0.50 | 1.00 | 0.50 | 0.40 |
| Arbalester | 0.20 | 0.40 | 1.00 | 0.40 | 0.20 |
| Elite Skirmisher (Chinese, ID 6) | 0.20 | 0.40 | 1.00 | 0.40 | 0.20 |
| Heavy Cavalry Archer | 0.25 | 0.50 | 1.00 | 0.50 | 0.40 |
| Siege Onager | 0.50 | 1.00 | 1.00 | 1.00 | 0.50 |
| Heavy Scorpion | 0.50 | 1.00 | 1.00 | 1.00 | 0.50 |
| Hand Cannoneer | 0.20 | 0.40 | 1.00 | 0.40 | 0.20 |

The multiplied diameter column is arithmetic, not a claim that the game always enforces that floor. Official balance notes establish the direction of the behavior: raising the Steppe Lancer collision modifier from 0.5 to 1 made it harder to stack, while lowering the Trade Cart/Cog multiplier reduced bumping. The exact runtime conditions that activate the minimum multiplier are not publicly specified.

## What the FINAL tape measures

For every sampled frame, the audit takes each living unit’s Euclidean center distance to the nearest living unit with the same owner and master unit ID.

| Unit | p10 | Median | p90 | Below nominal | Below multiplied floor |
|---|---:|---:|---:|---:|---:|
| Champion | 0.392 | 0.481 | 0.916 | 12.9% | 1.3% |
| Halberdier | 0.390 | 0.500 | 1.000 | 12.7% | 1.3% |
| Elite Fire Lancer | 0.397 | 0.487 | 1.000 | 11.2% | 1.2% |
| Hussar | 0.433 | 0.538 | 0.873 | 28.4% | 0.4% |
| Paladin | 0.456 | 0.570 | 1.098 | 20.3% | 0.4% |
| Heavy Camel | 0.455 | 0.572 | 1.281 | 19.9% | 0.3% |
| Elite Battle Elephant | 0.443 | 0.563 | 1.000 | 23.3% | 0.6% |
| Elite Steppe Lancer | 0.500 | 0.614 | 1.195 | 7.3% | 7.3% |
| Arbalester | 0.135 | 0.389 | 0.795 | 55.9% | 55.9% |
| Elite Skirmisher | 0.110 | 0.359 | 0.642 | 61.9% | 61.9% |
| Heavy Cavalry Archer | 0.172 | 0.517 | 0.767 | 44.6% | 44.6% |
| Siege Onager | 1.000 | 1.151 | 2.000 | 4.2% | 4.2% |
| Heavy Scorpion | 1.000 | 1.012 | 1.524 | 5.4% | 5.4% |
| Hand Cannoneer | **0.084** | **0.308** | **0.540** | **72.5%** | **72.5%** |

This validates the multiplier as a meaningful lower scale for ordinary melee movement: infantry and cavalry frequently dip below nominal diameter but almost never below their multiplied diameter. Steppe Lancer at multiplier 1.0 is much harder to compress. Ranged units are different: they can be far inside nominal diameter even when their multiplier is 1.0.

## HC is context-dependent, not just “small”

Canonical matchup aggregation combines repeats recorded with either tag order.

| HC matchup context | HC median spacing | HC p10 | Below 0.40 tile | Patrol events captured |
|---|---:|---:|---:|---:|
| Champion | 0.223 | 0.068 | 84.2% | 0 |
| Elite Fire Lancer | 0.228 | 0.074 | 85.0% | 0 |
| Heavy Camel | 0.259 | 0.054 | 81.8% | 0 |
| Elite Steppe Lancer | 0.289 | 0.083 | 75.0% | 0 |
| Paladin | 0.295 | 0.087 | 77.3% | 0 |
| Elite Battle Elephant | 0.300 | 0.086 | 79.7% | 0 |
| Halberdier | 0.306 | 0.114 | 73.3% | 0 |
| Hussar | 0.309 | 0.102 | 74.1% | 0 |
| Heavy Cavalry Archer | 0.466 | 0.276 | 21.9% | 8 |
| Heavy Scorpion | 0.475 | 0.349 | 19.9% | 6 |
| Siege Onager | 0.485 | 0.319 | 21.7% | 6 |
| Arbalester | 0.506 | 0.384 | 11.9% | 6 |
| Elite Skirmisher | 0.824 | 0.374 | 13.1% | 4 |

This makes a fixed HC radius reduction the wrong model. The same HC body is extremely compressed against melee and usually uncompressed against ranged/siege.

## Movement and command-state evidence

HC is moving in **70.1%** of classifiable nearest-neighbor samples. Its moving median is **0.304 tile** and stationary median is **0.320 tile**. Movement increases compression, but stationary HC is still well below its nominal 0.40-tile diameter. All recorded HC rows expose the same opaque raw unit state value (`2`), so that field cannot separate attacking, kiting, regrouping, or formation movement.

The FINAL command stream contains only timestamp and command-kind names:

- `formFormation`: 12,230 events across 203 recordings
- `interact`: 22,444 events across 218 recordings
- `patrol`: 72 events across only 24 recordings

Every captured patrol event is in a ranged-vs-ranged/siege family. There are **zero patrol events** in the HC-vs-melee families where compression is strongest. Therefore:

- Patrol may change compression in ranged-vs-ranged behavior.
- Patrol is **not supported as the cause of HC compression against Paladin, Steppe Lancer, Camel, Elephant, Champion, Halberdier, or Hussar**.
- `formFormation` and `interact` are present in those fights, but the capture omits unit IDs, formation ID, destinations, command payloads, and attack-move details. Correlation cannot identify the exact state transition.

## Comparison with the current simulation

The current simulation uses the `.dat` collision radius but not the per-unit multiplier. Its collision pass enforces:

`minimum center distance = radius A + radius B + 1 px`

with `COMBAT_PACK_FACTOR = 1.0`, so the combat-pack path does not shrink that floor. For two HC units this is **13 px = 0.433 tile**, slightly larger than even their nominal 0.40-tile diameter. That construction cannot produce the FINAL HC-vs-Paladin median of 0.295 tile or p10 of 0.087 tile.

Always applying the `.dat` multiplier is also wrong:

- It changes infantry/cavalry but leaves HC unchanged at multiplier 1.0.
- Melee tape spacing generally remains around nominal diameter; the multiplied value behaves more like a state-dependent lower bound than the ordinary target spacing.
- A permanent 0.5 cavalry factor would overcompress Paladins, Hussars, Camels, and Elephants.

## Hypotheses and decisions

### H-A: The `.dat` minimum multiplier is the missing HC mechanism

**Decision: reject as the HC fix; keep as a future engine input.** It is a real field and should eventually be carried through extraction, but HC is 1.0. It may improve state-dependent melee bumping, not the HC-vs-melee gap.

### H-B: Patrol applies a tighter ranged formation

**Decision: plausible generally, rejected for the current HC-vs-melee failure.** The FINAL tape has no patrol events in those families. Test it separately for ranged-vs-ranged.

### H-C: Formation/regroup/contact state temporarily relaxes same-team ranged collision

**Decision: strongest surviving hypothesis.** It explains why multiplier-1 ranged units violate nominal diameter, why HC changes dramatically by opponent class, and why simple radius changes fail. The present command stream cannot distinguish the exact trigger.

### H-D: Tape coordinates are not unit centers

**Decision: weak.** A fixed anchor offset would not make the same HC unit measure 0.22–0.31 against melee and 0.47–0.82 against ranged. Siege and melee distributions also align with their declared geometry.

### H-E: The melee attack-swing plant indirectly creates HC compression

**Decision: compatible but not sufficient by itself.** The melee plant can stall the front rank while HC continues moving/regrouping, increasing backline pile-up. It explains the opponent-class split, but the simulation still needs a runtime rule that permits HC bodies to occupy the observed spacing once they pile up.

## Smallest decisive follow-up tests

1. **Command-state isolation in game.** Record the same 21 HC units with no enemy under idle, move, patrol, attack-move, formation change, and repeated focus-interact commands. Capture full command payloads and 60 Hz positions. This identifies which command first permits spacing below 0.40.
2. **Opponent-contact isolation.** Repeat with stationary non-attacking melee dummies, then attacking melee units, then ranged dummies. This separates own-formation compression from enemy-contact/swing effects.
3. **Formation isolation.** Repeat line, staggered, box, flank, and no-formation movement using the same path. Measure transition timing into and out of compressed spacing.
4. **Simulation diagnostic flag.** Add a calibration-only, state-gated ranged same-team floor—never a permanent HC radius change. Sweep trigger definitions (moving-to-formation slot, active interact/regroup, nearby melee contact) against all FINAL standard matchups and reject any trigger that compresses HC-vs-ranged the way HC-vs-melee compresses.
5. **Carry raw multiplier separately.** Add `min_collision_size_multiplier` to the extracted combat dictionary, but keep it inactive until a tape-supported runtime trigger is found. This avoids hard-coding class guesses while preventing premature global compression.

## Primary/official references

- [`genieutils-py` supports reading current AoE2 DE `.dat` files](https://pypi.org/project/genieutils-py/).
- [Official Update Preview 125283: lowering Trade Cart/Cog collision multiplier reduces bumping](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-preview-125283/).
- [Forgotten Empires balance changelog: raising Steppe Lancer modifier 0.5 → 1 makes stacking harder](https://www.forgottenempires.net/age-of-empires-ii-definitive-edition/balance-changelog).
- [Official Update 42848: Elephant collision multiplier changed to match cavalry/ranged](https://staging.ageofempires.com/news/aoe2de-update-42848/).
- [Official Update 81058: straight-line formation pathing, bump retargeting, collision/stutter, and obstruction fixes](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-81058/).
- [Official obstruction-type notes distinguish collision size, selection radius, and hard obstruction](https://www.ageofempires.com/news/a-sneak-peek-at-new-content-coming-to-age-of-empires-ii-definitive-edition/).
