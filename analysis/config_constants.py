"""Magic IDs, paths, age constants, and attribute constants for AoE2 analysis.

This module contains primitive/scalar configuration that other config modules
and analysis modules depend on. It has no dependencies on other config sub-modules.
"""

from pathlib import Path

from extraction.extract_constants import CIV_NAMES

# Paths - relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = Path(__file__).parent.parent / "extraction" / "extracted_data"
REF_DB_PATH = PROJECT_ROOT / "webapp" / "aoe2_reference.db"

# Age constants
FEUDAL_AGE = 2
CASTLE_AGE = 3
IMPERIAL_AGE = 4

# Age tech IDs (required_techs values that indicate age)
AGE_TECH_IDS = {101: FEUDAL_AGE, 102: CASTLE_AGE, 103: IMPERIAL_AGE}

# Attribute IDs used in effects
ATTR_HP = 0
ATTR_LOS = 1
ATTR_SPEED = 5
ATTR_ARMOR = 8
ATTR_ATTACK = 9
ATTR_RELOAD_TIME = 10
ATTR_ACCURACY = 11
ATTR_RANGE = 12
ATTR_TRAIN_TIME = 101
ATTR_COST = 100
ATTR_FOOD_COST = 103
ATTR_WOOD_COST = 104
ATTR_GOLD_COST = 105
ATTR_HP_REGEN = 109

# Effect command types
CMD_SET_ATTRIBUTE = 0
CMD_ENABLE_DISABLE_UNIT = 2
CMD_UPGRADE_UNIT = 3
CMD_ADD_ATTRIBUTE = 4
CMD_MULTIPLY_ATTRIBUTE = 5

# Building ID to name mapping (from dat file research_locations)
BUILDING_NAMES = {
    0: "N/A",  # OLD-ACADEMY (auto-upgrade techs)
    103: "Blacksmith",
    101: "Stable",
    87: "Archery Range",
    12: "Barracks",
    209: "University",
    104: "Monastery",
    82: "Castle",
    109: "Town Center",
    49: "Siege Workshop",
    45: "Dock",
    84: "Market",
    68: "Mill",
}

# Attribute ID to human-readable name
ATTR_DISPLAY_NAMES = {
    ATTR_HP: "HP",
    ATTR_LOS: "LOS",
    ATTR_SPEED: "Speed",
    ATTR_ARMOR: "Armor",
    ATTR_ATTACK: "Attack",
    ATTR_RELOAD_TIME: "Reload",
    ATTR_ACCURACY: "Accuracy",
    ATTR_RANGE: "Range",
    ATTR_TRAIN_TIME: "Train Time",
    ATTR_COST: "Cost (all)",
    ATTR_FOOD_COST: "Cost (food)",
    ATTR_WOOD_COST: "Cost (wood)",
    ATTR_GOLD_COST: "Cost (gold)",
    ATTR_HP_REGEN: "HP Regen",
}

# All playable civilizations (53), alphabetical — derived from the dat civ-slot
# list so a new DLC civ added to CIV_NAMES flows through automatically.
# CIV_NAMES[0] is "Gaia" (not playable); None entries are unused dat slots.
# Name is historical ("original 13" from the first prototype); rename deferred.
ORIGINAL_13_CIVS = sorted(c for c in CIV_NAMES[1:] if c)

# =============================================================================
# SIMULATION CONFIGURATION
# =============================================================================
# Lithuanian relic count for cavalry attack bonus (0-4)
# Each relic gives +1 attack to Knights, Cavaliers, Paladins, and Leitis
LITHUANIAN_RELIC_COUNT = 4

# =============================================================================
# ALLOWED SHADOW TECHS
# =============================================================================
# Shadow techs have research_location=-1 and are normally filtered out in
# find_techs_affecting_unit() to prevent spurious tech application. This
# allow-list names the specific shadow tech IDs that must bypass that filter
# because they carry real stat upgrades or unit-enable effects that belong in
# the analysis pipeline.
ALLOWED_SHADOW_TECHS = {
    774,   # Flemish Militia Age3: +10 HP, +3 attack, +anti-cav bonuses
    797,   # Flemish Militia Age4: +5 HP, +3 attack, +anti-cav bonuses
    1025,  # Traction Trebuchet (make avail): enables unit 1942 at Imperial Age
}

# Techs that exist in the dat file but have been removed/replaced in-game
# These are skipped during unique tech and civ bonus application
REMOVED_TECHS = {
    9,  # Saracen Zealotry (replaced by Bimaristan + Counterweights)
}


def _tech_age_name(age_num):
    """Convert age number to name."""
    return {1: "Dark", 2: "Feudal", 3: "Castle", 4: "Imperial"}.get(
        age_num, f"Age {age_num}"
    )
