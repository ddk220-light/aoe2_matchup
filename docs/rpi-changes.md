# RPI Changes Log

## 2026-02-12: Fix hp_regen not applied from civ bonus techs (attr 109)

### Bug

Wu infantry HP regeneration civ bonus was not being applied to the simulation.
Wu has 3 cumulative civ bonus techs that each add +10 to attribute 109 (hp_regen):

- Tech 1085: `C-Bonus, inf regen Feudal` → +10 HP/min
- Tech 1086: `C-Bonus, inf regen Castle` → +10 HP/min
- Tech 1087: `C-Bonus, inf regen Imp` → +10 HP/min

By Imperial age, Wu infantry should have **30 HP/min regen**. The bonus text was
recorded in the `civ_bonuses` string and the `ref_techs_applied` table, but the
numeric `hp_regen` field remained 0 because `unit_analyzer.py` did not handle
attribute 109.

This also affects any future civilization that receives hp_regen through tech
effect commands rather than base unit data or hardcoded config overrides.

### Root Cause

The `_add_attribute()` and `_set_attribute()` methods in `unit_analyzer.py` only
handled attributes 0-105 (HP, speed, armor, attack, costs, etc.). Attribute 109
(hp_regen) was defined in `extract_effects.py` for naming purposes but had no
corresponding `ATTR_HP_REGEN` constant or handler in the stat computation engine.

The existing hp_regen path only worked for:
- Units with regen baked into the dat file base data (e.g. Berserk = 40 HP/min)
- Units with manual overrides in `CIV_COMBAT_OVERRIDES` in config.py (e.g. Khitans cavalry = 20 HP/min)

### Fix

**Files changed:**

1. `analysis/config.py`
   - Added `ATTR_HP_REGEN = 109` constant
   - Added `ATTR_HP_REGEN` to `ATTR_DISPLAY_NAMES`

2. `analysis/unit_analyzer.py`
   - Added `hp_regen: float = 0` field to `UnitStats` dataclass
   - Added `hp_regen` to `UnitStats.copy()`
   - Imported `ATTR_HP_REGEN` from config
   - Added `ATTR_HP_REGEN` handling in `_set_attribute()` and `_add_attribute()`
   - Added `stats.hp_regen = round(stats.hp_regen, 1)` to final rounding

3. `analysis/generate_reference.py`
   - After `get_combat_properties()`, merge analyzer's `stats.hp_regen` into
     `combat_props` if it's higher than the existing value
   - Added `hp_regen` to the `ref_units` UPDATE statement so the reference DB
     stores the correct value

### Impact

- Wu Champion: `hp_regen` changes from 0 → 30.0 HP/min
- Wu Man-at-Arms / Long Swordsman / Two-Handed Swordsman: gain age-appropriate regen
- Wu Spearman / Pikeman / Halberdier: gain age-appropriate regen
- All other Wu infantry units: gain cumulative regen per age
- Any future civ with tech-applied hp_regen will now work automatically

### Runtime Patching (temporary)

The databases (`aoe2_units.db`, `aoe2_reference.db`) cannot be rebuilt without
the `.dat` game file, which is only available on the dev machine. Until the next
full rebuild, Wu infantry hp_regen values in the shipped databases remain 0.

To verify the fix and run rankings, a runtime patching approach was used: after
loading unit data from the existing DB, Wu infantry units are patched in-memory
with `hp_regen = 30.0` before running simulations. This hack is used only for
local testing/ranking scripts — the pipeline fix above is the real solution and
will take effect on the next `python3 -m extraction.run && python3 -m analysis.generate_reference` rebuild.

### Verification

After rebuilding databases (`python3 -m extraction.run && python3 -m analysis.generate_reference`), Wu Champion
should show `hp_regen = 30.0` in both `aoe2_reference.db` and `aoe2_units.db`.

Simulation test: 10 Wu Champions vs 10 Chinese Champions (identical stats except
regen) — Wu wins 10-0 with 4 HP remaining per unit. Without the fix, this was a
draw.

### Infantry Rankings (with runtime patch)

Round-robin results across 3 scenarios (30v30, 3000 res, 5000 res):

**Militia line** — Wu Champion ranks **#24** out of 24 (regen helps survival but
Wu lacks Blast Furnace, so base attack is lower than most civs).

**Spear line** — Wu Halberdier ranks **#6** out of 19 (regen is more impactful
on spear units due to longer fights; Wu also gets full spear upgrades).

## 2026-02-12: Fix Jian Swordsman HP Transform Mechanic

### Bug

The Jian Swordsman (Wu unique unit) has an HP-transform mechanic: when HP drops
below 45, it switches to an unshielded form with +3 attack, -2 melee armor,
-3 pierce armor, and +10% speed. Three bugs existed:

1. **Transform stats were un-upgraded base values** — the DB stored raw base stats
   (ATK=11, MA=0, PA=2) instead of fully upgraded stats. The pipeline never applied
   tech upgrades (Forging/Iron Casting/Blast Furnace, Scale/Chain/Plate armor) to
   the transform fields.

2. **HP threshold was wrong** — config had `0.5` (35 HP) but the game uses 45 HP
   (45/70 = 0.6429).

3. **No revert mechanic** — the simulation only transformed one-way; the game
   reverts stats when HP heals back above the threshold (e.g. via Wu's 30 HP/min
   infantry regen).

### Root Cause

`config.py` stores the Jian Swordsman's transform stats as hardcoded base values
from the dat file. `generate_reference.py` wrote these raw values directly into the
DB without applying the tech upgrade deltas that the normal form receives.

The simulation in `simulation.py` only checked for the forward transform (HP drops
below threshold) but never checked for the revert condition (HP heals above threshold).

### Fix

**Files changed:**

1. `analysis/config.py`
   - Changed `hp_transform_threshold` from `0.5` to `45.0 / 70.0` (~0.6429)

2. `analysis/generate_reference.py`
   - After computing `final_snap` (fully upgraded normal stats) and before writing
     special props, apply tech deltas to transform stats:
     `transform_final = normal_final + (transform_base - normal_base)`
   - This upgrades `transform_attack`, `transform_melee_armor`,
     `transform_pierce_armor`, `transform_movement_speed`, `transform_attacks_json`,
     and `transform_armors_json`

3. `webapp/simulation.py`
   - Added revert mechanic: when a transformed unit's HP heals back above the
     threshold, `transformed[idx]` is set back to `False`, restoring normal form stats

### Expected Values (Imperial, Wu)

| Stat | Normal | Transform (base, old) | Transform (upgraded, fixed) |
|------|--------|-----------------------|-----------------------------|
| ATK  | 14     | 11                    | 17                          |
| MA   | 5      | 0                     | 3                           |
| PA   | 9      | 2                     | 6                           |
| SPD  | 1.10   | 1.10                  | 1.21                        |

### Impact

- Transform stats now properly reflect full Imperial age upgrades
- HP threshold matches the in-game 45 HP value
- Units with regen (Wu infantry) can now oscillate between forms as HP fluctuates
  around the threshold, matching in-game behavior
- DB rebuild (`python3 -m extraction.run && python3 -m analysis.generate_reference`) required for pipeline fix to take effect
