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

1. `database_creation/config.py`
   - Added `ATTR_HP_REGEN = 109` constant
   - Added `ATTR_HP_REGEN` to `ATTR_DISPLAY_NAMES`

2. `database_creation/unit_analyzer.py`
   - Added `hp_regen: float = 0` field to `UnitStats` dataclass
   - Added `hp_regen` to `UnitStats.copy()`
   - Imported `ATTR_HP_REGEN` from config
   - Added `ATTR_HP_REGEN` handling in `_set_attribute()` and `_add_attribute()`
   - Added `stats.hp_regen = round(stats.hp_regen, 1)` to final rounding

3. `database_creation/generate_reference.py`
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
will take effect on the next `python3 -m database_creation.run` rebuild.

### Verification

After rebuilding databases (`python3 -m database_creation.run`), Wu Champion
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
