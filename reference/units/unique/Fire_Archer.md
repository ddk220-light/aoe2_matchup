# Fire Archer

**Type:** Unique  
**Available to:** Wu  
**Sources:** SiegeEngineers/aoe2techtree, Fandom wiki  
**Generated:** 2026-04-13

## Stats

| Stat | Castle | Imperial |
|------|---------|-------|
| HP | 35.0 | 40.0 |
| Attack | 5.0 | 6.0 |
| Melee Armor | 0.0 | 0.0 |
| Pierce Armor | 0.0 | 0.0 |
| Speed | 0.96 | 0.96 |
| Range | 9.0 | 10.0 |
| Reload Time | 3.5 | 3.5 |
| Cost Food | 0.0 | 0.0 |
| Cost Wood | 45.0 | 45.0 |
| Cost Gold | 45.0 | 45.0 |
| Pop Space | 1.0 | 1.0 |

## Special Effects

- **pass_through_count:** 1.0

## DB Comparison

| Field | External | Our DB (Castle) | Match |
|-------|----------|-----------------|-------|
| HP | 35.0 | 35.0 | ✅ |
| Attack | 4.0 | 5.0 | ❌ |
| Melee Armor | 0.0 | 0.0 | ✅ |
| Pierce Armor | 0.0 | 0.0 | ✅ |
| Speed | 0.96 | 0.96 | ✅ |
| Range | ⚠️ | 9.0 | ⚠️ |
| Reload Time | 3.5 | 3.5 | ✅ |
| Cost Food | 800 | 0.0 | ❌ |
| Cost Wood | 45 | 45.0 | ✅ |
| Cost Gold | 45 | 45.0 | ✅ |

**⚠️ 2 mismatch(es) found — investigate.**

## Attack Bonuses

| Bonus | Armor Class |
|-------|-------------|
| +4 | Standard Buildings |
| +3 | Ships & Saboteurs |
| +2 | Spearmen |
| +1 | Siege Weapons |

## Armor Classes (Vulnerability)

_Units with attack bonuses against these classes deal extra damage to this unit._

| Armor Class | Armor Value |
|-------------|-------------|
| Archers | 0 |
| Unique Units | 0 |
| Leitis | 0 |

## Strengths & Weaknesses

**Strong vs:** building, ship
**Weak vs:** Elite Skirmisher, Huskarl, Eagle Warrior

## Ability

_Automatically switches to a long range attack mode vs buildings and ships_

The anti-unit attack of the Fire Archer is programmed as a "ranged charge attack" (charge type 6 in Genie Editor):
* Charge event: -4 (range of charge attack is 4 less than regular attack)
* Recharge rate: Infinite (always available)
* Charge target: Infantry, cavalry, foot archers, mounted archers, Monks, civilians (Villagers and Trade Carts), and siege weapons. This specifically excludes ships and buildings.
* It fires multiple arrows which are released one after the other (like a Chu Ko Nu) rather than concurrently (which would be like a Kipchak).

Against buildings, it uses the regular attack attributes defined in the data file, firing one projectile at a longer range.

## Technologies

| Stat | Technology (Effect) |
|------|---------------------|
| Attack | Fletching (+1) |
| Attack | Bodkin Arrow (+1) |
| Attack | Bracer (+1) |
| Attack | Chemistry (+1) |
| Attack | Red Cliffs Tactics (+5 over 5 seconds, anti-building mode) |
| Armor | Padded Archer Armor (+1/+1) |
| Armor | Leather Archer Armor (+1/+1) |
| Conversion | Devotion (+1 min, +1 max) |
| Conversion | Faith (+4 min, +4 max) |
| Creation | Conscription (+33%) |
