#!/usr/bin/env python3
"""
Generate SQLite database directly from AoE2 JSON data files.

This script reads the extracted game data (units.json, technologies.json, etc.)
and generates a SQLite database with fully upgraded unit stats for each civilization.

Database Schema:
- civilizations: List of all civilizations
- ages: Age definitions (Feudal, Castle, Imperial)
- units: List of all unit types with their age
- unit_stats: Stats for each civ/unit combination
- comments: User feedback on data cells
"""

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

# Paths
OUTPUT_DIR = Path(__file__).parent / "output"
DB_PATH = Path(__file__).parent / "webapp" / "aoe2_units.db"

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
}

# Original 13 civilizations
ORIGINAL_13_CIVS = [
    "Britons",
    "Byzantines",
    "Celts",
    "Chinese",
    "Franks",
    "Goths",
    "Japanese",
    "Mongols",
    "Persians",
    "Saracens",
    "Teutons",
    "Turks",
    "Vikings",
]

# =============================================================================
# SIMULATION CONFIGURATION
# =============================================================================
# Lithuanian relic count for cavalry attack bonus (0-4)
# Each relic gives +1 attack to Knights, Cavaliers, Paladins, and Leitis
LITHUANIAN_RELIC_COUNT = 2

# =============================================================================
# BUILDING WORK RATE (affects unit creation time)
# =============================================================================
# Unit class → primary creation building ID
UNIT_CLASS_TO_BUILDING = {
    6: 12,  # Infantry → Barracks
    0: 87,  # Archer → Archery Range
    12: 101,  # Cavalry → Stable
    36: 87,  # Cavalry Archer → Archery Range
    13: 49,  # Siege → Siege Workshop
    44: 87,  # Gunpowder (Hand Cannoneer) → Archery Range
    55: 49,  # Scorpion/Ballista → Siege Workshop
    54: 82,  # Trebuchet → Castle
}

# Unique units are created at Castle (82) by default
UNIQUE_UNIT_BUILDING = 82

# Techs that multiply building work_rate (attribute 13)
# Format: tech_id → (civ_id, {building_id: multiplier, ...})
# civ_id=-1 means available to all civs
BUILDING_WORK_RATE_TECHS = {
    315: (
        -1,
        {  # Conscription (Imperial, all civs)
            12: 1.33,
            20: 1.33,  # Barracks variants
            87: 1.33,
            10: 1.33,
            14: 1.33,  # Archery Range variants
            101: 1.33,
            86: 1.33,
            153: 1.33,  # Stable variants
            82: 1.33,  # Castle
            49: 1.33,  # Siege Workshop
            498: 1.33,
            132: 1.33,  # Other military buildings
            1251: 1.33,
            1665: 1.33,  # Krepost, Donjon
        },
    ),
    457: (
        3,
        {  # Perfusion (Goths Imperial UT, civ_id=3)
            12: 2.0,  # Barracks only
        },
    ),
    493: (
        2,
        {  # Chivalry (Franks Imperial UT, civ_id=2)
            101: 1.4,
            86: 1.4,
            153: 1.4,  # Stable variants
        },
    ),
}

# Civ bonuses that discount technology costs (applied to self)
# Format: civ_name → {age_name: discount_fraction, ...}
# Chinese: -10% Feudal, -15% Castle, -20% Imperial
CIV_TECH_COST_DISCOUNT = {
    "Chinese": {"Feudal": 0.10, "Castle": 0.15, "Imperial": 0.20},
}

# Civ team bonuses that multiply building work_rate (applied to self)
# Format: civ_name → {building_id: multiplier, ...}
CIV_TEAM_BONUS_WORK_RATE = {
    "Britons": {87: 1.10, 10: 1.10, 14: 1.10},  # Archery Ranges work 10% faster
    "Goths": {12: 1.20, 498: 1.20, 132: 1.20, 20: 1.20},  # Barracks work 20% faster
    "Celts": {49: 1.20, 150: 1.20},  # Siege Workshops work 20% faster
}

# Unique units that can also be created in Barracks (after specific tech)
# Format: (civ_name, base_slug) → barracks_building_id
UNIQUE_UNITS_IN_BARRACKS = {
    ("Goths", "huskarl"): 12,  # After Anarchy tech
    ("Goths", "elite_huskarl"): 12,
}

# =============================================================================
# COMBAT PROPERTIES (stored in DB so simulation needs zero hardcoded slug lookups)
# =============================================================================
# Standard units — keyed by unit slug
COMBAT_PROPERTIES = {
    # min_attack_range, is_siege_projectile, splash_radius, projectile_speed
    # are now data-driven from get_extracted_combat_properties()
    "mangonel": {"unit_category": "siege"},
    "siege_onager": {"unit_category": "siege"},
    "scorpion": {"unit_category": "siege"},
    "heavy_scorpion": {"unit_category": "siege"},
    "skirm": {"unit_category": "trash"},
    "elite_skirm": {"unit_category": "trash"},
    "spearman": {"unit_category": "trash"},
    "pikeman": {"unit_category": "trash"},
    "halberdier": {"unit_category": "trash"},
    "scout": {"unit_category": "trash"},
    "light_cav": {"unit_category": "trash"},
    "hussar": {"unit_category": "trash"},
    "ram": {"unit_category": "siege"},
    "siege_ram": {"unit_category": "siege"},
    "trebuchet": {"unit_category": "siege"},
    "bombard_cannon": {"unit_category": "siege"},
}

# Unique units — keyed by base slug (without civ suffix)
# Only ability flags and values NOT extractable from dat file belong here.
# Stats like extra_projectiles, trample, dodge shield are now data-driven
# via get_extracted_combat_properties().
UNIQUE_COMBAT_PROPERTIES = {
    "konnik": {"dismount_unit_id": 1252},
    "elite_konnik": {"dismount_unit_id": 1253},
    "leitis": {"ignores_melee_armor": 1},
    "elite_leitis": {"ignores_melee_armor": 1},
    "composite_bowman": {"ignores_pierce_armor": 1},
    "elite_composite_bowman": {"ignores_pierce_armor": 1},
    # Fire Lancer charge: 3 projectiles, range 4, ignores armor (except siege/ships/buildings)
    "fire_lancer": {"charge_attack_range": 4, "charge_ignores_armor": 1},
    "elite_fire_lancer": {"charge_attack_range": 4, "charge_ignores_armor": 1},
    # Organ Gun/Fire Archer extra projectiles are now data-driven
    # Bleed damage (ability flag + stat values not in dat)
    "liao_dao": {"bleed_dps": 2.0, "bleed_duration": 5.0},
    "elite_liao_dao": {"bleed_dps": 3.0, "bleed_duration": 5.0},
    # Block first melee hit (ability flag, not in dat)
    "iron_pagoda": {"block_first_melee": 1},
    "elite_iron_pagoda": {"block_first_melee": 1},
    # Kill bonus attack (ability flag, not in dat)
    "tiger_cavalry": {"attack_bonus_per_kill": 4},
    "elite_tiger_cavalry": {"attack_bonus_per_kill": 4},
    "jaguar_warrior": {"attack_bonus_per_kill": 4},
    "elite_jaguar_warrior": {"attack_bonus_per_kill": 4},
    # HP transformation (ability flag, not in dat)
    "jian_swordsman": {"hp_transform_threshold": 0.5, "transform_unit_id": 1976},
}

# Civ-conditional properties (applied on top of base/unique properties)
CIV_COMBAT_PROPERTIES = {
    # Logistica (Byzantine Castle UT) - Cataphracts deal 5 trample damage
    ("Byzantines", "cataphract"): {"trample_flat_damage": 5, "trample_radius": 0.5},
    ("Byzantines", "elite_cataphract"): {
        "trample_flat_damage": 5,
        "trample_radius": 0.5,
    },
    # Druzhina (Slavs Imperial UT) - infantry deal 5 trample damage
    ("Slavs", "champion"): {"trample_flat_damage": 5, "trample_radius": 0.5},
    ("Slavs", "halberdier"): {"trample_flat_damage": 5, "trample_radius": 0.5},
    ("Slavs", "swordsmen"): {"trample_flat_damage": 5, "trample_radius": 0.5},
    ("Bengalis", "elephant"): {"bonus_damage_reduction": 0.25},
    ("Bengalis", "elite_elephant"): {"bonus_damage_reduction": 0.25},
    ("Bengalis", "elephant_archer"): {"bonus_damage_reduction": 0.25},
    ("Bengalis", "elite_ele_archer"): {"bonus_damage_reduction": 0.25},
    ("Bengalis", "ratha_(melee)"): {"bonus_damage_reduction": 0.25},
    ("Bengalis", "ratha_(ranged)"): {"bonus_damage_reduction": 0.25},
    ("Bengalis", "elite_ratha_(melee)"): {"bonus_damage_reduction": 0.25},
    ("Bengalis", "elite_ratha_(ranged)"): {"bonus_damage_reduction": 0.25},
    # Wootz Steel (Dravidian Imperial UT) - melee attacks ignore armor
    ("Dravidians", "champion"): {"ignores_melee_armor": 1},
    ("Dravidians", "halberdier"): {"ignores_melee_armor": 1},
    ("Dravidians", "hussar"): {"ignores_melee_armor": 1},
    ("Dravidians", "elite_elephant"): {"ignores_melee_armor": 1},
    ("Dravidians", "elite_urumi_swordsman"): {"ignores_melee_armor": 1},
}

# Paired units mapping (for matchup mode switching)
PAIRED_UNITS = {
    "ratha_(melee)": "ratha_(ranged)",
    "ratha_(ranged)": "ratha_(melee)",
    "elite_ratha_(melee)": "elite_ratha_(ranged)",
    "elite_ratha_(ranged)": "elite_ratha_(melee)",
}

# =============================================================================
# UNIT DEFINITIONS
# =============================================================================
# Format: (base_unit_id, display_name, unit_class, availability_tech, upgrade_techs)
# - base_unit_id: The starting unit ID for this line
# - display_name: Display name for the table
# - unit_class: Unit class for tech effect filtering
# - availability_tech: Tech ID that makes this unit available (None if always available)
# - upgrade_techs: List of (tech_id, upgraded_unit_id, upgraded_name) in upgrade order

FEUDAL_UNITS = {
    "man_at_arms": {
        "base_id": 74,  # Militia (named "Spearman" in data, but it's actually Militia)
        "display_name": "Man-at-Arms",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [
            (222, 75, "Man-at-Arms"),  # Man-at-Arms upgrade: 74 -> 75
        ],
    },
    "spearman": {
        "base_id": 93,  # Spearman (named "Pikeman" in data, but has Spearman stats)
        "display_name": "Spearman",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [],  # No upgrades in Feudal Age
    },
    "archer": {
        "base_id": 4,
        "display_name": "Archer",
        "unit_class": 0,
        "availability_tech": None,
        "upgrades": [],
    },
    "skirmisher": {
        "base_id": 7,
        "display_name": "Skirmisher",
        "unit_class": 0,
        "availability_tech": None,
        "upgrades": [],
    },
    "scout": {
        "base_id": 448,
        "display_name": "Scout Cavalry",
        "unit_class": 12,
        "availability_tech": 204,  # Scout (make avail)
        "upgrades": [],
    },
}

CASTLE_UNITS = {
    "swordsmen": {
        "base_id": 75,  # Man-at-Arms
        "display_name": "Long Swordsman",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [
            (207, 77, "Long Swordsman"),  # Long Swordsman upgrade
        ],
    },
    "pikeman": {
        "base_id": 93,  # Spearman
        "display_name": "Pikeman",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [
            (197, 358, "Pikeman"),  # Pikeman upgrade: 93 -> 358
        ],
    },
    "eagle_warrior": {
        "base_id": 753,  # Correct ID per AoE2ScenarioParser (751 is Eagle Scout)
        "display_name": "Eagle Warrior",
        "unit_class": 6,
        "availability_tech": 433,  # Eagle Warrior (make avail)
        "upgrades": [],
    },
    "light_cav": {
        "base_id": 546,
        "display_name": "Light Cavalry",
        "unit_class": 12,
        "availability_tech": 254,  # Light Cavalry upgrade tech
        "upgrades": [],
    },
    "knight": {
        "base_id": 38,
        "display_name": "Knight",
        "unit_class": 12,
        "availability_tech": 166,  # Knight (make avail)
        "upgrades": [],
        # Special handling for Burgundians who get Cavalier in Castle Age
        "civ_upgrades": {
            "Burgundians": [(209, 283, "Cavalier")],  # Cavalier available in Castle Age
        },
    },
    "camel": {
        "base_id": 329,
        "display_name": "Camel Rider",
        "unit_class": 12,
        "availability_tech": 235,  # Camel Rider (make avail)
        "upgrades": [],
    },
    "elephant": {
        "base_id": 1132,  # Correct ID per AoE2ScenarioParser
        "display_name": "Battle Elephant",
        "unit_class": 12,
        "availability_tech": 630,  # Battle Elephant (make avail)
        "upgrades": [],
    },
    "steppe_lancer": {
        "base_id": 1370,
        "display_name": "Steppe Lancer",
        "unit_class": 12,
        "availability_tech": 714,  # Steppe Lancer (make avail)
        "upgrades": [],
    },
    "crossbow": {
        "base_id": 4,  # Archer
        "display_name": "Crossbowman",
        "unit_class": 0,
        "availability_tech": None,
        "upgrades": [
            (212, 24, "Crossbowman"),  # Crossbowman upgrade
        ],
    },
    "elite_skirm": {
        "base_id": 7,  # Skirmisher
        "display_name": "Elite Skirmisher",
        "unit_class": 0,
        "availability_tech": None,
        "required_upgrade": 98,  # Elite Skirmisher tech required
        "upgrades": [
            (98, 6, "Elite Skirmisher"),  # Elite Skirmisher upgrade
        ],
    },
    "cav_archer": {
        "base_id": 39,
        "display_name": "Cavalry Archer",
        "unit_class": 36,
        "availability_tech": 192,  # Cavalry Archer (make avail)
        "upgrades": [],
    },
    "elephant_archer": {
        "base_id": 873,  # Correct ID per AoE2ScenarioParser
        "display_name": "Elephant Archer",
        "unit_class": 36,
        "availability_tech": 480,  # Elephant Archer (make avail)
        "upgrades": [],
    },
    "ram": {
        "base_id": 35,
        "display_name": "Battering Ram",
        "unit_class": 13,
        "availability_tech": 162,  # Battering Ram (make avail)
        "upgrades": [],
        # Alternate unit for civs without rams
        "alternate": {
            "availability_tech": 837,  # Armored Elephant (make avail)
            "base_id": 1744,  # Correct ID for Armored Elephant
            "display_name": "Armored Elephant",
        },
    },
    "mangonel": {
        "base_id": 280,
        "display_name": "Mangonel",
        "unit_class": 13,
        "availability_tech": None,
        "upgrades": [],
    },
    "scorpion": {
        "base_id": 279,
        "display_name": "Scorpion",
        "unit_class": 55,
        "availability_tech": None,
        "upgrades": [],
    },
    "fire_lancer": {
        "base_id": 1901,
        "display_name": "Fire Lancer",
        "unit_class": 6,
        "availability_tech": 981,  # Fire Lancer (make avail)
        "upgrades": [],
    },
}

IMPERIAL_UNITS = {
    "champion": {
        "base_id": 77,  # Long Swordsman
        "display_name": "Champion",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [
            (217, 473, "Two-Handed Swordsman"),
            (264, 567, "Champion"),
        ],
    },
    "halberdier": {
        "base_id": 358,  # Pikeman
        "display_name": "Halberdier",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [
            (429, 359, "Halberdier"),
        ],
    },
    "elite_eagle": {
        "base_id": 751,
        "display_name": "Elite Eagle Warrior",
        "unit_class": 6,
        "availability_tech": 433,
        "upgrades": [
            (384, 752, "Elite Eagle Warrior"),
        ],
    },
    "elite_fire_lancer": {
        "base_id": 1901,  # Fire Lancer
        "display_name": "Elite Fire Lancer",
        "unit_class": 6,
        "availability_tech": 981,  # Fire Lancer (make avail)
        "upgrades": [
            (982, 1903, "Elite Fire Lancer"),
        ],
    },
    "hussar": {
        "base_id": 546,  # Light Cavalry
        "display_name": "Hussar",
        "unit_class": 12,
        "availability_tech": 254,
        "upgrades": [
            (428, 441, "Hussar"),
            (786, 1707, "Winged Hussar"),
        ],
    },
    "paladin": {
        "base_id": 38,  # Knight
        "display_name": "Paladin",
        "unit_class": 12,
        "availability_tech": 166,
        "upgrades": [
            (209, 283, "Cavalier"),
            (265, 569, "Paladin"),
        ],
        # Alternate for 3K civs
        "alternate": {
            "availability_tech": 1032,  # Hei-Kuang Cavalry (make avail)
            "base_id": 1944,
            "display_name": "Hei-Kuang Cavalry",
            "upgrades": [
                (1033, 1946, "Heavy Hei-Kuang Cavalry"),
            ],
        },
        # Savar replaces Paladin for Persians
        "civ_upgrades": {
            "Persians": [
                (209, 283, "Cavalier"),
                (526, 1813, "Savar"),
            ],
        },
    },
    "heavy_camel": {
        "base_id": 329,
        "display_name": "Heavy Camel Rider",
        "unit_class": 12,
        "availability_tech": 235,
        "upgrades": [
            (236, 330, "Heavy Camel Rider"),
        ],
        # Imperial Camel Rider is Hindustanis-only
        "civ_upgrades": {
            "Hindustanis": [
                (236, 330, "Heavy Camel Rider"),
                (521, 207, "Imperial Camel Rider"),
            ],
        },
    },
    "elite_elephant": {
        "base_id": 1132,  # Correct ID per AoE2ScenarioParser
        "display_name": "Elite Battle Elephant",
        "unit_class": 12,
        "availability_tech": 630,
        "upgrades": [
            (631, 1134, "Elite Battle Elephant"),  # Correct elite ID: 1134
        ],
    },
    "elite_steppe": {
        "base_id": 1370,
        "display_name": "Elite Steppe Lancer",
        "unit_class": 12,
        "availability_tech": 714,
        "upgrades": [
            (715, 1372, "Elite Steppe Lancer"),
        ],
    },
    "arbalester": {
        "base_id": 24,  # Crossbowman
        "display_name": "Arbalester",
        "unit_class": 0,
        "availability_tech": None,
        "upgrades": [
            (237, 492, "Arbalester"),
        ],
    },
    # Imperial Skirmisher removed - requires Vietnamese team bonus (not standard)
    "heavy_cav_archer": {
        "base_id": 39,
        "display_name": "Heavy Cavalry Archer",
        "unit_class": 36,
        "availability_tech": 192,
        "upgrades": [
            (218, 474, "Heavy Cavalry Archer"),
        ],
    },
    "elite_ele_archer": {
        "base_id": 873,  # Correct ID per AoE2ScenarioParser
        "display_name": "Elite Elephant Archer",
        "unit_class": 36,
        "availability_tech": 480,
        "upgrades": [
            (481, 875, "Elite Elephant Archer"),  # Correct elite ID: 875
        ],
    },
    "siege_ram": {
        "base_id": 35,  # Battering Ram
        "display_name": "Siege Ram",
        "unit_class": 13,
        "availability_tech": 162,
        "upgrades": [
            (96, 422, "Capped Ram"),
            (255, 548, "Siege Ram"),
        ],
        "alternate": {
            "availability_tech": 837,
            "base_id": 1744,  # Armored Elephant
            "display_name": "Siege Elephant",
            "upgrades": [
                (838, 1746, "Siege Elephant"),  # Correct ID for Siege Elephant
            ],
        },
    },
    "siege_onager": {
        "base_id": 280,
        "display_name": "Siege Onager",
        "unit_class": 13,
        "availability_tech": None,
        "upgrades": [
            (257, 550, "Onager"),
            (320, 588, "Siege Onager"),
        ],
    },
    "heavy_scorpion": {
        "base_id": 279,
        "display_name": "Heavy Scorpion",
        "unit_class": 55,
        "availability_tech": None,
        "upgrades": [
            (239, 542, "Heavy Scorpion"),
        ],
    },
    "hand_cannoneer": {
        "base_id": 5,
        "display_name": "Hand Cannoneer",
        "unit_class": 44,
        "availability_tech": 85,  # Hand Cannoneer (make avail)
        "upgrades": [],
    },
    "bombard_cannon": {
        "base_id": 36,
        "display_name": "Bombard Cannon",
        "unit_class": 13,
        "availability_tech": 188,  # Bombard Cannon (make avail)
        "upgrades": [],
    },
    "trebuchet": {
        "base_id": 42,
        "display_name": "Trebuchet",
        "unit_class": 54,
        "availability_tech": None,
        "upgrades": [],
    },
}

# All units by age
UNITS_BY_AGE = {
    FEUDAL_AGE: FEUDAL_UNITS,
    CASTLE_AGE: CASTLE_UNITS,
    IMPERIAL_AGE: IMPERIAL_UNITS,
}

AGE_NAMES = {
    FEUDAL_AGE: "Feudal Age",
    CASTLE_AGE: "Castle Age",
    IMPERIAL_AGE: "Imperial Age",
}

# =============================================================================
# UNIQUE UNITS
# =============================================================================
# Format: civ_name -> list of unique unit configs
# Each unique unit has: base_id, display_name, unit_class, availability_tech, elite_tech, elite_id
UNIQUE_UNITS = {
    "Britons": [
        {
            "base_id": 8,
            "display_name": "Longbowman",
            "unit_class": 0,
            "availability_tech": 263,
            "elite_tech": 360,
            "elite_id": 530,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Longbowman",
        },
    ],
    "Franks": [
        {
            "base_id": 281,  # Correct ID per AoE2ScenarioParser
            "display_name": "Throwing Axeman",
            "unit_class": 6,
            "availability_tech": 275,
            "elite_tech": 363,
            "elite_id": 531,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Throwing Axeman",
        },
    ],
    "Goths": [
        {
            "base_id": 41,
            "display_name": "Huskarl",
            "unit_class": 6,
            "availability_tech": 446,
            "elite_tech": 365,
            "elite_id": 555,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Huskarl",
        },
    ],
    "Teutons": [
        {
            "base_id": 25,
            "display_name": "Teutonic Knight",
            "unit_class": 6,
            "availability_tech": 276,
            "elite_tech": 364,
            "elite_id": 554,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Teutonic Knight",
        },
    ],
    "Japanese": [
        {
            "base_id": 291,
            "display_name": "Samurai",
            "unit_class": 6,
            "availability_tech": 262,
            "elite_tech": 366,
            "elite_id": 560,
            "elite_name": "Elite Samurai",
        },
    ],
    "Chinese": [
        {
            "base_id": 73,
            "display_name": "Chu Ko Nu",
            "unit_class": 0,
            "availability_tech": 268,
            "elite_tech": 362,
            "elite_id": 559,
            "elite_name": "Elite Chu Ko Nu",
        },
    ],
    "Byzantines": [
        {
            "base_id": 40,
            "display_name": "Cataphract",
            "unit_class": 12,
            "availability_tech": 267,
            "elite_tech": 361,
            "elite_id": 553,
            "elite_name": "Elite Cataphract",
        },
    ],
    "Persians": [
        {
            "base_id": 239,
            "display_name": "War Elephant",
            "unit_class": 12,
            "availability_tech": 274,
            "elite_tech": 367,
            "elite_id": 558,
            "elite_name": "Elite War Elephant",
        },
    ],
    "Saracens": [
        {
            "base_id": 282,  # Correct ID per AoE2ScenarioParser
            "display_name": "Mameluke",
            "unit_class": 12,
            "availability_tech": 269,
            "elite_tech": 368,
            "elite_id": 556,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Mameluke",
        },
    ],
    "Turks": [
        {
            "base_id": 46,
            "display_name": "Janissary",
            "unit_class": 44,
            "availability_tech": 271,
            "elite_tech": 369,
            "elite_id": 557,
            "elite_name": "Elite Janissary",
        },
    ],
    "Mongols": [
        {
            "base_id": 11,
            "display_name": "Mangudai",
            "unit_class": 36,
            "availability_tech": 273,
            "elite_tech": 371,
            "elite_id": 561,
            "elite_name": "Elite Mangudai",
        },
    ],
    "Celts": [
        {
            "base_id": 232,
            "display_name": "Woad Raider",
            "unit_class": 6,
            "availability_tech": 277,
            "elite_tech": 370,
            "elite_id": 534,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Woad Raider",
        },
    ],
    "Vikings": [
        {
            "base_id": 692,
            "display_name": "Berserk",
            "unit_class": 6,
            "availability_tech": 398,
            "elite_tech": 398,
            "elite_id": 694,
            "elite_name": "Elite Berserk",
        },
    ],
    "Aztecs": [
        {
            "base_id": 725,
            "display_name": "Jaguar Warrior",
            "unit_class": 6,
            "availability_tech": 431,
            "elite_tech": 432,
            "elite_id": 726,
            "elite_name": "Elite Jaguar Warrior",
        },
    ],
    "Mayans": [
        {
            "base_id": 763,
            "display_name": "Plumed Archer",
            "unit_class": 0,
            "availability_tech": 26,
            "elite_tech": 27,
            "elite_id": 765,
            "elite_name": "Elite Plumed Archer",
        },
    ],
    "Huns": [
        {
            "base_id": 755,
            "display_name": "Tarkan",
            "unit_class": 12,
            "availability_tech": 1,
            "elite_tech": 2,
            "elite_id": 757,
            "elite_name": "Elite Tarkan",
        },
    ],
    "Spanish": [
        {
            "base_id": 771,
            "display_name": "Conquistador",
            "unit_class": 36,
            "availability_tech": 58,
            "elite_tech": 60,
            "elite_id": 773,
            "elite_name": "Elite Conquistador",
        },
    ],
    "Koreans": [
        {
            "base_id": 827,
            "display_name": "War Wagon",
            "unit_class": 36,
            "availability_tech": 449,
            "elite_tech": 450,
            "elite_id": 829,
            "elite_name": "Elite War Wagon",
        },
    ],
    "Italians": [
        {
            "base_id": 866,  # Correct ID per AoE2ScenarioParser
            "display_name": "Genoese Crossbowman",
            "unit_class": 0,
            "availability_tech": 467,
            "elite_tech": 468,
            "elite_id": 868,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Genoese Crossbowman",
        },
    ],
    "Magyars": [
        {
            "base_id": 869,
            "display_name": "Magyar Huszar",
            "unit_class": 12,
            "availability_tech": 471,
            "elite_tech": 472,
            "elite_id": 871,
            "elite_name": "Elite Magyar Huszar",
        },
    ],
    "Slavs": [
        {
            "base_id": 876,
            "display_name": "Boyar",
            "unit_class": 12,
            "availability_tech": 503,
            "elite_tech": 504,
            "elite_id": 878,
            "elite_name": "Elite Boyar",
        },
    ],
    "Incas": [
        {
            "base_id": 879,
            "display_name": "Kamayuk",
            "unit_class": 6,
            "availability_tech": 508,
            "elite_tech": 509,
            "elite_id": 881,
            "elite_name": "Elite Kamayuk",
        },
    ],
    "Hindustanis": [
        {
            "base_id": 1747,
            "display_name": "Ghulam",
            "unit_class": 6,
            "availability_tech": 885,
            "elite_tech": 886,
            "elite_id": 1749,
            "elite_name": "Elite Ghulam",
        },
    ],
    "Portuguese": [
        {
            "base_id": 1001,  # Correct ID per AoE2ScenarioParser
            "display_name": "Organ Gun",
            "unit_class": 13,
            "availability_tech": 562,
            "elite_tech": 563,
            "elite_id": 1003,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Organ Gun",
        },
    ],
    "Berbers": [
        {
            "base_id": 1007,  # Correct ID per AoE2ScenarioParser
            "display_name": "Camel Archer",
            "unit_class": 36,
            "availability_tech": 564,
            "elite_tech": 565,
            "elite_id": 1009,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Camel Archer",
        },
    ],
    "Malians": [
        {
            "base_id": 1013,
            "display_name": "Gbeto",
            "unit_class": 6,
            "availability_tech": 566,
            "elite_tech": 567,
            "elite_id": 1015,
            "elite_name": "Elite Gbeto",
        },
    ],
    "Ethiopians": [
        {
            "base_id": 1016,
            "display_name": "Shotel Warrior",
            "unit_class": 6,
            "availability_tech": 568,
            "elite_tech": 569,
            "elite_id": 1018,
            "elite_name": "Elite Shotel Warrior",
        },
    ],
    "Khmer": [
        {
            "base_id": 1120,  # Correct ID per AoE2ScenarioParser
            "display_name": "Ballista Elephant",
            "unit_class": 55,
            "availability_tech": 614,
            "elite_tech": 615,
            "elite_id": 1122,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Ballista Elephant",
        },
    ],
    "Malay": [
        {
            "base_id": 1123,  # Correct ID per AoE2ScenarioParser
            "display_name": "Karambit Warrior",
            "unit_class": 6,
            "availability_tech": 616,
            "elite_tech": 617,
            "elite_id": 1125,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Karambit Warrior",
        },
    ],
    "Burmese": [
        {
            "base_id": 1126,  # Correct ID per AoE2ScenarioParser
            "display_name": "Arambai",
            "unit_class": 36,
            "availability_tech": 618,
            "elite_tech": 619,
            "elite_id": 1128,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Arambai",
        },
    ],
    "Vietnamese": [
        {
            "base_id": 1129,  # Correct ID per AoE2ScenarioParser
            "display_name": "Rattan Archer",
            "unit_class": 0,
            "availability_tech": 620,
            "elite_tech": 621,
            "elite_id": 1131,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Rattan Archer",
        },
    ],
    "Bulgarians": [
        {
            "base_id": 1225,  # Correct ID per AoE2ScenarioParser
            "display_name": "Konnik",
            "unit_class": 12,
            "availability_tech": 677,
            "elite_tech": 678,
            "elite_id": 1227,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Konnik",
        },
    ],
    "Tatars": [
        {
            "base_id": 1228,  # Correct ID per AoE2ScenarioParser
            "display_name": "Keshik",
            "unit_class": 12,
            "availability_tech": 679,
            "elite_tech": 680,
            "elite_id": 1230,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Keshik",
        },
    ],
    "Cumans": [
        {
            "base_id": 1231,  # Correct ID per AoE2ScenarioParser
            "display_name": "Kipchak",
            "unit_class": 36,
            "availability_tech": 681,
            "elite_tech": 682,
            "elite_id": 1233,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Kipchak",
        },
    ],
    "Lithuanians": [
        {
            "base_id": 1234,  # Correct ID per AoE2ScenarioParser
            "display_name": "Leitis",
            "unit_class": 12,
            "availability_tech": 683,
            "elite_tech": 684,
            "elite_id": 1236,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Leitis",
        },
    ],
    "Burgundians": [
        {
            "base_id": 1655,
            "display_name": "Coustillier",
            "unit_class": 12,
            "availability_tech": 754,
            "elite_tech": 755,
            "elite_id": 1657,
            "elite_name": "Elite Coustillier",
        },
    ],
    "Sicilians": [
        {
            "base_id": 1658,
            "display_name": "Serjeant",
            "unit_class": 6,
            "availability_tech": 756,
            "elite_tech": 757,
            "elite_id": 1659,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Serjeant",
        },
    ],
    "Poles": [
        {
            "base_id": 1701,  # Correct ID per AoE2ScenarioParser
            "display_name": "Obuch",
            "unit_class": 6,
            "availability_tech": 782,
            "elite_tech": 783,
            "elite_id": 1703,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Obuch",
        },
    ],
    "Bohemians": [
        {
            "base_id": 1704,  # Correct ID per AoE2ScenarioParser
            "display_name": "Hussite Wagon",
            "unit_class": 13,
            "availability_tech": 780,
            "elite_tech": 781,
            "elite_id": 1706,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Hussite Wagon",
        },
    ],
    "Dravidians": [
        {
            "base_id": 1735,
            "display_name": "Urumi Swordsman",
            "unit_class": 6,
            "availability_tech": 825,
            "elite_tech": 826,
            "elite_id": 1737,
            "elite_name": "Elite Urumi Swordsman",
        },
    ],
    "Bengalis": [
        {
            "base_id": 1738,
            "display_name": "Ratha (Melee)",
            "unit_class": 36,
            "availability_tech": 831,
            "elite_tech": 832,
            "elite_id": 1740,
            "elite_name": "Elite Ratha (Melee)",
        },
        {
            "base_id": 1759,
            "display_name": "Ratha (Ranged)",
            "unit_class": 36,
            "availability_tech": 831,
            "elite_tech": 832,
            "elite_id": 1761,
            "elite_name": "Elite Ratha (Ranged)",
        },
    ],
    "Gurjaras": [
        {
            "base_id": 1751,
            "display_name": "Shrivamsha Rider",
            "unit_class": 12,
            "availability_tech": 889,
            "elite_tech": 890,
            "elite_id": 1753,
            "elite_name": "Elite Shrivamsha Rider",
        },
        {
            "base_id": 1741,  # Correct ID per AoE2ScenarioParser
            "display_name": "Chakram Thrower",
            "unit_class": 6,
            "availability_tech": 893,
            "elite_tech": 894,
            "elite_id": 1743,  # Correct ID per AoE2ScenarioParser
            "elite_name": "Elite Chakram Thrower",
        },
    ],
    "Romans": [
        {
            "base_id": 1790,
            "display_name": "Centurion",
            "unit_class": 6,
            "availability_tech": 935,
            "elite_tech": 936,
            "elite_id": 1792,
            "elite_name": "Elite Centurion",
        },
    ],
    "Armenians": [
        {
            "base_id": 1800,
            "display_name": "Composite Bowman",
            "unit_class": 0,
            "availability_tech": 963,
            "elite_tech": 964,
            "elite_id": 1802,
            "elite_name": "Elite Composite Bowman",
        },
        {
            "base_id": 1811,
            "display_name": "Warrior Priest",
            "unit_class": 6,  # Infantry class (gets monk bonuses via unit-specific effects)
            "availability_tech": 948,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
        },
    ],
    "Georgians": [
        {
            "base_id": 1803,
            "display_name": "Monaspa",
            "unit_class": 12,
            "availability_tech": 973,
            "elite_tech": 974,
            "elite_id": 1805,
            "elite_name": "Elite Monaspa",
        },
    ],
    "Jurchens": [
        {
            "base_id": 1908,
            "display_name": "Iron Pagoda",
            "unit_class": 12,
            "availability_tech": 990,
            "elite_tech": 991,
            "elite_id": 1910,
            "elite_name": "Elite Iron Pagoda",
        },
        {
            "base_id": 1911,
            "display_name": "Grenadier",
            "unit_class": 44,
            "availability_tech": 992,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
        },
    ],
    "Khitans": [
        {
            "base_id": 1920,
            "display_name": "Liao Dao",
            "unit_class": 6,
            "availability_tech": 1001,
            "elite_tech": 1002,
            "elite_id": 1922,
            "elite_name": "Elite Liao Dao",
        },
        {
            "base_id": 1923,
            "display_name": "Siege Camel",
            "unit_class": 12,
            "availability_tech": 1005,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
        },
    ],
    "Shu": [
        {
            "base_id": 1959,
            "display_name": "White Feather Crossbowman",
            "unit_class": 6,
            "availability_tech": 1063,
            "elite_tech": 1064,
            "elite_id": 1961,
            "elite_name": "Elite White Feather Crossbowman",
        },
        {
            "base_id": 2150,
            "display_name": "War Chariot",
            "unit_class": 12,
            "availability_tech": 1065,
            "elite_tech": 1171,
            "elite_id": 2151,
            "elite_name": "Elite War Chariot",
        },
    ],
    "Wei": [
        {
            "base_id": 1949,
            "display_name": "Tiger Cavalry",
            "unit_class": 12,
            "availability_tech": 1035,
            "elite_tech": 1036,
            "elite_id": 1951,
            "elite_name": "Elite Tiger Cavalry",
        },
        {
            "base_id": 1952,
            "display_name": "Xianbei Raider",
            "unit_class": 36,
            "availability_tech": 1037,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
        },
    ],
    "Wu": [
        {
            "base_id": 1968,
            "display_name": "Fire Archer",
            "unit_class": 0,
            "availability_tech": 1073,
            "elite_tech": 1074,
            "elite_id": 1970,
            "elite_name": "Elite Fire Archer",
        },
        {
            "base_id": 1974,
            "display_name": "Jian Swordsman",
            "unit_class": 6,
            "availability_tech": 1075,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
        },
    ],
}


@dataclass
class UnitStats:
    """Mutable unit stats that can be modified by effects."""

    hp: float = 0
    attack: float = 0
    melee_armor: float = 0
    pierce_armor: float = 0
    speed: float = 0
    range: float = 0
    reload_time: float = 0
    attack_delay: float = 0
    accuracy: float = 0
    los: float = 0
    cost_food: float = 0
    cost_wood: float = 0
    cost_gold: float = 0
    cost_stone: float = 0
    train_time: float = 0
    upgrade_cost: float = 0
    attacks: dict = field(default_factory=dict)
    armors: dict = field(default_factory=dict)

    def copy(self):
        return UnitStats(
            hp=self.hp,
            attack=self.attack,
            melee_armor=self.melee_armor,
            pierce_armor=self.pierce_armor,
            speed=self.speed,
            range=self.range,
            reload_time=self.reload_time,
            attack_delay=self.attack_delay,
            accuracy=self.accuracy,
            los=self.los,
            cost_food=self.cost_food,
            cost_wood=self.cost_wood,
            cost_gold=self.cost_gold,
            cost_stone=self.cost_stone,
            train_time=self.train_time,
            upgrade_cost=self.upgrade_cost,
            attacks=self.attacks.copy(),
            armors=self.armors.copy(),
        )

    def attack_rate(self) -> float:
        """Calculate attacks per second from reload time."""
        if self.reload_time > 0:
            return 1.0 / self.reload_time
        return 0.0


class UnitAnalyzer:
    """Analyzes unit stats and calculates civ-specific values."""

    def __init__(self):
        self.load_data()
        self._tech_cache = {}

    def load_data(self):
        """Load all game data from JSON files."""
        self.units = {u["id"]: u for u in json.load(open(OUTPUT_DIR / "units.json"))}
        self.techs = {
            t["id"]: t for t in json.load(open(OUTPUT_DIR / "technologies.json"))
        }
        self.civs = json.load(open(OUTPUT_DIR / "civilizations.json"))
        self.civ_tech_trees = {
            c["name"]: c for c in json.load(open(OUTPUT_DIR / "civ_tech_trees.json"))
        }
        self.effects = {
            e["id"]: e for e in json.load(open(OUTPUT_DIR / "effects.json"))
        }
        self.tech_effects = json.load(open(OUTPUT_DIR / "tech_effects.json"))

        # Load tech ages
        tech_ages_file = OUTPUT_DIR / "tech_ages.json"
        if tech_ages_file.exists():
            tech_ages_data = json.load(open(tech_ages_file))
            self.tech_ages = tech_ages_data.get("techs", {})
        else:
            self.tech_ages = {}

        # Build tech effect lookup
        self.tech_effect_map = {te["tech_id"]: te for te in self.tech_effects}

        # Build civ bonus techs lookup
        self.civ_bonus_techs = {}
        for tech_id, tech in self.techs.items():
            civ_id = tech.get("civ", -1)
            if civ_id >= 0:
                if civ_id not in self.civ_bonus_techs:
                    self.civ_bonus_techs[civ_id] = []
                self.civ_bonus_techs[civ_id].append(tech_id)

        # Build civ name to ID mapping
        self.civ_name_to_id = {c["name"]: c["id"] for c in self.civs}

        # Build disabled tech lookup per civ
        self.civ_disabled_tech_ids = {}
        for civ_name, civ_data in self.civ_tech_trees.items():
            disabled = set()
            for t in civ_data.get("disabled_techs", []):
                if isinstance(t, dict):
                    disabled.add(t["id"])
            self.civ_disabled_tech_ids[civ_name] = disabled

    def get_disabled_techs(self, civ_name: str) -> set:
        """Get set of disabled tech IDs for a civilization."""
        return self.civ_disabled_tech_ids.get(civ_name, set())

    def get_building_work_rate(
        self, civ_name: str, building_id: int, max_age: int
    ) -> float:
        """Get combined work rate multiplier for a building from all available techs."""
        disabled_techs = self.get_disabled_techs(civ_name)
        civ_id = self.civ_name_to_id.get(civ_name, -1)
        multiplier = 1.0
        for tech_id, (
            tech_civ_id,
            building_multipliers,
        ) in BUILDING_WORK_RATE_TECHS.items():
            if building_id not in building_multipliers:
                continue
            if tech_id in disabled_techs:
                continue
            # Check civ restriction (-1 = all civs)
            if tech_civ_id != -1 and tech_civ_id != civ_id:
                continue
            # Check age requirement
            tech_age = self.get_tech_age_recursive(tech_id)
            if tech_age > max_age:
                continue
            multiplier *= building_multipliers[building_id]
        # Apply civ team bonus work rate (civs apply their own team bonus)
        team_bonus = CIV_TEAM_BONUS_WORK_RATE.get(civ_name, {})
        if building_id in team_bonus:
            multiplier *= team_bonus[building_id]
        return multiplier

    def has_tech(self, civ_name: str, tech_id: int) -> bool:
        """Check if a civ has access to a specific tech."""
        if tech_id is None:
            return True
        disabled_techs = self.get_disabled_techs(civ_name)
        return tech_id not in disabled_techs

    def get_unit(self, unit_id: int):
        """Get unit by ID."""
        return self.units.get(unit_id)

    def get_base_stats(self, unit: dict) -> UnitStats:
        """Extract base stats from unit data."""
        stats = UnitStats()
        stats.hp = unit.get("hit_points", 0)
        stats.speed = unit.get("speed", 0)
        stats.range = unit.get("range", 0)
        stats.reload_time = unit.get("reload_time", 0)
        stats.attack_delay = unit.get("attack_delay", 0)
        stats.accuracy = unit.get("accuracy", 0)
        stats.los = unit.get("line_of_sight", 0)
        stats.train_time = unit.get("train_time", 0)

        cost = unit.get("cost", {})
        stats.cost_food = cost.get("food", 0)
        stats.cost_wood = cost.get("wood", 0)
        stats.cost_gold = cost.get("gold", 0)
        stats.cost_stone = cost.get("stone", 0)

        stats.melee_armor = unit.get("displayed_melee_armor", 0)
        stats.pierce_armor = unit.get("displayed_pierce_armor", 0)
        stats.attack = unit.get("displayed_attack", 0)

        for atk in unit.get("attacks", []):
            stats.attacks[atk["class"]] = atk["amount"]
        for arm in unit.get("armors", []):
            stats.armors[arm["class"]] = arm["amount"]

        return stats

    def get_tech_age(self, tech_id: int) -> int:
        """Get the age when a tech becomes available."""
        tech_id_str = str(tech_id)
        if tech_id_str in self.tech_ages:
            return self.tech_ages[tech_id_str].get("age", 4)

        # Fallback: check required_techs
        tech_data = self.techs.get(tech_id, {})
        required = tech_data.get("required_techs", [])
        for req in required:
            if req in AGE_TECH_IDS:
                return AGE_TECH_IDS[req]
        return 1  # Dark Age default

    def find_techs_affecting_unit(
        self, unit_id: int, unit_class: int, max_age: int = 4
    ) -> set:
        """Find all techs up to a certain age that affect this unit."""
        cache_key = (unit_id, unit_class, max_age)
        if cache_key in self._tech_cache:
            return self._tech_cache[cache_key]

        relevant_techs = set()

        for te in self.tech_effects:
            tech_id = te["tech_id"]
            tech_data = self.techs.get(tech_id, {})

            # Skip civ-specific techs (handled separately)
            if tech_data.get("civ", -1) >= 0:
                continue

            # Skip DLC/campaign-specific techs (have non-standard requirements like Antiquity techs)
            # These are identified by having required_techs with IDs > 1000 that aren't standard
            required_techs = tech_data.get("required_techs", [])
            has_dlc_requirement = any(
                req > 1000 and req not in AGE_TECH_IDS
                for req in required_techs
                if req > 0
            )
            if has_dlc_requirement:
                continue

            affects_unit = False

            for cmd in te.get("commands", []):
                cmd_type = cmd.get("type", -1)
                a = cmd.get("a", -999)
                b = cmd.get("b", -999)

                if cmd_type in (
                    CMD_SET_ATTRIBUTE,
                    CMD_ADD_ATTRIBUTE,
                    CMD_MULTIPLY_ATTRIBUTE,
                ):
                    if a == unit_id or (a == -1 and b == unit_class):
                        affects_unit = True
                        break

            if affects_unit:
                tech_age = self.get_tech_age(tech_id)
                if tech_age <= max_age:
                    relevant_techs.add(tech_id)

        self._tech_cache[cache_key] = relevant_techs
        return relevant_techs

    def get_tech_age_recursive(self, tech_id: int, visited: set = None) -> int:
        """
        Get the effective age when a tech becomes available,
        considering the ages of required techs recursively.
        """
        if visited is None:
            visited = set()

        if tech_id in visited:
            return 1  # Prevent infinite loops
        visited.add(tech_id)

        # First check if it's an age tech itself
        if tech_id in AGE_TECH_IDS:
            return AGE_TECH_IDS[tech_id]

        # Check tech_ages.json
        tech_id_str = str(tech_id)
        if tech_id_str in self.tech_ages:
            return self.tech_ages[tech_id_str].get("age", 1)

        # Check required_techs and find the max age among them
        tech_data = self.techs.get(tech_id, {})
        required_techs = tech_data.get("required_techs", [])

        max_age = 1  # Dark Age default
        for req_tech in required_techs:
            req_age = self.get_tech_age_recursive(req_tech, visited.copy())
            max_age = max(max_age, req_age)

        return max_age

    def get_civ_bonus_techs_for_unit(
        self, civ_name: str, unit_id: int, unit_class: int, max_age: int = 4
    ) -> list:
        """Get civ-specific bonus techs that affect this unit."""
        civ_id = self.civ_name_to_id.get(civ_name, -1)
        if civ_id < 0:
            return []

        relevant = []
        tech_ids = self.civ_bonus_techs.get(civ_id, [])

        for tech_id in tech_ids:
            if tech_id not in self.tech_effect_map:
                continue

            te = self.tech_effect_map[tech_id]
            tech_data = self.techs.get(tech_id, {})
            tech_name = tech_data.get("name", "")

            # Skip unique techs (have cost and don't start with C-Bonus)
            if tech_data.get("cost") and not tech_name.startswith("C-Bonus"):
                continue

            # Handle relic-based bonuses (e.g., Lithuanian "Relic +1 cav attack")
            # Apply only the configured number of relic bonuses for Lithuanians
            if "Relic" in tech_name:
                if civ_name == "Lithuanians" and LITHUANIAN_RELIC_COUNT > 0:
                    # Extract relic number from tech name (e.g., "Relic +1 cav attack 1" -> 1)
                    relic_num = 0
                    for part in tech_name.split():
                        if part.isdigit():
                            relic_num = int(part)
                            break
                    # Only apply if this relic number is within our configured count
                    if relic_num > LITHUANIAN_RELIC_COUNT:
                        continue
                    # Fall through to apply this relic bonus
                else:
                    continue

            # Check if all required techs are available to this civ
            # This handles conditional bonuses like Mongol "+30% HP + BL" which requires Bloodlines
            required_techs = tech_data.get("required_techs", [])
            disabled_techs = self.get_disabled_techs(civ_name)
            has_non_age_requirement = False
            all_required_available = True
            for req_tech in required_techs:
                # Skip age tech IDs (they're not researchable techs)
                if req_tech in AGE_TECH_IDS:
                    continue
                has_non_age_requirement = True
                # Check if the required tech is disabled for this civ
                if req_tech in disabled_techs:
                    all_required_available = False
                    break

            if not all_required_available:
                continue

            # Skip non-conditional variants if civ has the conditional version available
            # E.g., if Mongols have Bloodlines, use "+30% HP + BL" version, not "+30% HP"
            # The "+BL" versions are designed to work WITH Bloodlines, non-BL versions are fallbacks
            if not has_non_age_requirement and "+ BL" not in tech_name:
                # This is a non-conditional version - check if a conditional version exists
                base_bonus_pattern = tech_name.replace("C-Bonus, ", "")
                skip_this = False
                for other_tech_id in tech_ids:
                    other_tech = self.techs.get(other_tech_id, {})
                    other_name = other_tech.get("name", "")
                    if "+ BL" in other_name and base_bonus_pattern in other_name:
                        # Found a "+BL" version - check if it's available
                        other_reqs = other_tech.get("required_techs", [])
                        other_available = True
                        for req in other_reqs:
                            if req not in AGE_TECH_IDS and req in disabled_techs:
                                other_available = False
                                break
                        if other_available:
                            skip_this = True
                            break
                if skip_this:
                    continue

            # Check age requirements recursively
            # This handles cases where a bonus requires another tech (e.g., Double Forging requires Forging)
            bonus_age = self.get_tech_age_recursive(tech_id)

            if bonus_age > max_age:
                continue

            for cmd in te.get("commands", []):
                if self.effect_applies_to_unit(cmd, unit_id, unit_class):
                    relevant.append(te)
                    break

        return relevant

    def get_unique_techs_for_unit(
        self, civ_name: str, unit_id: int, unit_class: int, max_age: int = 4
    ) -> list:
        """Get civ-specific unique techs (Castle/Imperial Age) that affect this unit."""
        civ_id = self.civ_name_to_id.get(civ_name, -1)
        if civ_id < 0:
            return []

        relevant = []

        # Find all techs for this civ that have a cost (unique techs)
        for tech_id, tech_data in self.techs.items():
            # Must be for this civ
            if tech_data.get("civ", -1) != civ_id:
                continue

            # Must have a cost (unique techs have research cost)
            if not tech_data.get("cost"):
                continue

            # Must not be a C-Bonus tech
            tech_name = tech_data.get("name", "")
            if tech_name.startswith("C-Bonus"):
                continue

            # Check age requirement
            tech_age = self.get_tech_age_recursive(tech_id)
            if tech_age > max_age:
                continue

            # Check if this tech affects our unit
            if tech_id not in self.tech_effect_map:
                continue

            te = self.tech_effect_map[tech_id]
            for cmd in te.get("commands", []):
                if self.effect_applies_to_unit(cmd, unit_id, unit_class):
                    te_with_name = dict(te)
                    te_with_name["tech_name"] = tech_name
                    relevant.append(te_with_name)
                    break

        return relevant

    def effect_applies_to_unit(self, cmd: dict, unit_id: int, unit_class: int) -> bool:
        """Check if an effect command applies to a specific unit."""
        a = cmd.get("a", -999)
        b = cmd.get("b", -999)
        if a == unit_id:
            return True
        if a == -1 and b == unit_class:
            return True
        return False

    def apply_effect_command(
        self, cmd: dict, stats: UnitStats, unit_id: int, unit_class: int
    ) -> bool:
        """Apply a single effect command to unit stats."""
        if not self.effect_applies_to_unit(cmd, unit_id, unit_class):
            return False

        cmd_type = cmd.get("type", 0)
        c = cmd.get("c", 0)
        d = cmd.get("d", 0)

        if cmd_type == CMD_SET_ATTRIBUTE:
            self._set_attribute(stats, c, d)
        elif cmd_type == CMD_ADD_ATTRIBUTE:
            self._add_attribute(stats, c, d)
        elif cmd_type == CMD_MULTIPLY_ATTRIBUTE:
            self._multiply_attribute(stats, c, d)
        else:
            return False
        return True

    def _decode_armor_attack_value(self, d: float) -> tuple:
        d_int = int(d)
        if d_int >= 0:
            armor_class = d_int // 256
            amount = d_int % 256
            if amount > 127:
                amount = amount - 256
        else:
            d_int = abs(d_int)
            armor_class = d_int // 256
            amount = -(d_int % 256)
        return armor_class, amount

    def _set_attribute(self, stats: UnitStats, attr: int, value: float):
        if attr == ATTR_HP:
            stats.hp = value
        elif attr == ATTR_SPEED:
            stats.speed = value
        elif attr == ATTR_RANGE:
            stats.range = value
        elif attr == ATTR_RELOAD_TIME:
            stats.reload_time = value

    def _add_attribute(self, stats: UnitStats, attr: int, value: float):
        if attr == ATTR_HP:
            stats.hp += value
        elif attr == ATTR_SPEED:
            stats.speed += value
        elif attr == ATTR_RANGE:
            stats.range += value
        elif attr == ATTR_RELOAD_TIME:
            stats.reload_time += value
        elif attr == ATTR_LOS:
            stats.los += value
        elif attr == ATTR_TRAIN_TIME:
            stats.train_time += value
        elif attr == ATTR_ATTACK:
            atk_class, amount = self._decode_armor_attack_value(value)
            if atk_class in stats.attacks:
                stats.attacks[atk_class] += amount
            if atk_class == 4:
                stats.attack += amount
        elif attr == ATTR_ARMOR:
            arm_class, amount = self._decode_armor_attack_value(value)
            if arm_class in stats.armors:
                stats.armors[arm_class] += amount
            if arm_class == 4:
                stats.melee_armor += amount
            elif arm_class == 3:
                stats.pierce_armor += amount

    def _multiply_attribute(self, stats: UnitStats, attr: int, value: float):
        if attr == ATTR_HP:
            stats.hp *= value
        elif attr == ATTR_SPEED:
            stats.speed *= value
        elif attr == ATTR_RANGE:
            stats.range *= value
        elif attr == ATTR_RELOAD_TIME:
            stats.reload_time *= value
        elif attr == ATTR_LOS:
            stats.los *= value
        elif attr == ATTR_TRAIN_TIME:
            stats.train_time *= value
        elif attr == ATTR_COST:
            stats.cost_food *= value
            stats.cost_wood *= value
            stats.cost_gold *= value
            stats.cost_stone *= value
        elif attr == ATTR_GOLD_COST:
            stats.cost_gold *= value
        elif attr == ATTR_FOOD_COST:
            stats.cost_food *= value
        elif attr == ATTR_WOOD_COST:
            stats.cost_wood *= value

    def calculate_upgrade_cost(
        self, civ_name: str, relevant_techs: set, disabled_techs: set
    ) -> int:
        """Calculate total upgrade cost for relevant techs (with civ discount)."""
        discount_map = CIV_TECH_COST_DISCOUNT.get(civ_name, {})
        total = 0
        for tech_id in relevant_techs:
            if tech_id in disabled_techs:
                continue
            tech_data = self.techs.get(tech_id, {})
            base_cost = tech_data.get("cost", {})
            tech_age = self.get_tech_age_recursive(tech_id)
            age_name = _tech_age_name(tech_age)
            discount = discount_map.get(age_name, 0)
            mult = 1.0 - discount
            for val in base_cost.values():
                total += round(val * mult)
        return total

    def calculate_unit_stats_for_civ(
        self, civ_name: str, unit_config: dict, max_age: int
    ) -> dict:
        """
        Calculate stats for a unit for a specific civ at a given age.

        Returns dict with:
        - unit_name: Final unit name after upgrades
        - stats: UnitStats object
        - has_unit: Whether the civ has this unit
        - applied_bonuses: List of applied civ bonuses
        """
        disabled_techs = self.get_disabled_techs(civ_name)

        # Check for alternate unit (e.g., Armored Elephant instead of Ram)
        alternate = unit_config.get("alternate")
        use_alternate = False

        if alternate:
            main_avail_tech = unit_config.get("availability_tech")
            alt_avail_tech = alternate.get("availability_tech")

            # Use alternate if main unit is disabled but alternate is available
            if main_avail_tech and main_avail_tech in disabled_techs:
                if alt_avail_tech and alt_avail_tech not in disabled_techs:
                    use_alternate = True

        # Track if we're using civ-specific upgrades (skip age check for these)
        using_civ_upgrades = False

        if use_alternate:
            base_id = alternate["base_id"]
            base_unit = self.get_unit(base_id)
            base_name = alternate["display_name"]
            upgrades = alternate.get("upgrades", [])
        else:
            base_id = unit_config["base_id"]
            base_unit = self.get_unit(base_id)
            base_name = unit_config["display_name"]
            upgrades = unit_config.get("upgrades", [])

            # Check for civ-specific upgrades (e.g., Burgundians Cavalier in Castle Age)
            civ_upgrades = unit_config.get("civ_upgrades", {})
            if civ_name in civ_upgrades:
                upgrades = civ_upgrades[civ_name]
                using_civ_upgrades = True  # Skip age check for civ-specific upgrades

        # Check if civ has access to this unit
        avail_tech = unit_config.get("availability_tech")
        if not use_alternate and avail_tech and avail_tech in disabled_techs:
            return {
                "unit_name": base_name,
                "stats": None,
                "has_unit": False,
                "applied_bonuses": [],
            }

        # For alternate units, check if they have access
        if use_alternate:
            alt_avail_tech = alternate.get("availability_tech")
            if alt_avail_tech and alt_avail_tech in disabled_techs:
                return {
                    "unit_name": base_name,
                    "stats": None,
                    "has_unit": False,
                    "applied_bonuses": [],
                }

        # Check required upgrade (e.g., Elite Skirmisher requires tech 98)
        required_upgrade = unit_config.get("required_upgrade")
        if required_upgrade and required_upgrade in disabled_techs:
            return {
                "unit_name": base_name,
                "stats": None,
                "has_unit": False,
                "applied_bonuses": [],
            }

        # Find highest available upgrade
        final_unit_id = base_id
        final_unit_name = base_name

        for tech_id, upgraded_id, upgraded_name in upgrades:
            if tech_id not in disabled_techs:
                # For civ-specific upgrades, skip age check (they're explicitly available)
                if using_civ_upgrades:
                    final_unit_id = upgraded_id
                    final_unit_name = upgraded_name
                else:
                    # Check if this upgrade is available at the current age
                    tech_age = self.get_tech_age(tech_id)
                    if tech_age <= max_age:
                        final_unit_id = upgraded_id
                        final_unit_name = upgraded_name

        # Get the unit data
        unit = self.get_unit(final_unit_id)
        if not unit:
            # Fallback to base unit
            unit = self.get_unit(base_id)
            final_unit_name = base_name

        if not unit:
            return {
                "unit_name": final_unit_name,
                "stats": None,
                "has_unit": False,
                "applied_bonuses": [],
            }

        # Calculate stats
        unit_class = unit_config["unit_class"]
        stats = self.get_base_stats(unit)
        applied_bonuses = []

        # Apply standard techs FIRST (e.g., Bloodlines adds HP before civ bonuses multiply)
        standard_techs = self.find_techs_affecting_unit(
            final_unit_id, unit_class, max_age
        )

        for tech_id in sorted(standard_techs):
            if tech_id in disabled_techs:
                continue

            if tech_id in self.tech_effect_map:
                te = self.tech_effect_map[tech_id]
                for cmd in te.get("commands", []):
                    self.apply_effect_command(cmd, stats, final_unit_id, unit_class)

        # Apply civ bonus techs AFTER standard techs
        # This ensures additive bonuses (like Bloodlines +20 HP) are applied before
        # multiplicative civ bonuses
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(
            civ_name, final_unit_id, unit_class, max_age
        )
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, final_unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply unique techs (Castle/Imperial Age civ-specific techs like Garland Wars)
        unique_techs = self.get_unique_techs_for_unit(
            civ_name, final_unit_id, unit_class, max_age
        )
        for te in unique_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, final_unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Calculate upgrade cost
        upgrade_cost = self.calculate_upgrade_cost(
            civ_name, standard_techs, disabled_techs
        )
        stats.upgrade_cost = upgrade_cost

        # Apply building work rate to creation time
        building_id = UNIT_CLASS_TO_BUILDING.get(unit_class)
        if building_id and stats.train_time > 0:
            work_rate = self.get_building_work_rate(civ_name, building_id, max_age)
            if work_rate > 1.0:
                stats.train_time = stats.train_time / work_rate
                civ_id = self.civ_name_to_id.get(civ_name, -1)
                for tech_id, (
                    tech_civ_id,
                    bldg_mults,
                ) in BUILDING_WORK_RATE_TECHS.items():
                    if building_id in bldg_mults:
                        if tech_id not in disabled_techs:
                            if tech_civ_id == -1 or tech_civ_id == civ_id:
                                tech_age = self.get_tech_age_recursive(tech_id)
                                if tech_age <= max_age:
                                    te = self.tech_effect_map.get(tech_id, {})
                                    tname = te.get("tech_name", f"Tech {tech_id}")
                                    if tname not in applied_bonuses:
                                        applied_bonuses.append(tname)

        # Round values
        stats.hp = round(stats.hp)
        stats.speed = round(stats.speed, 2)
        stats.attack = round(stats.attack)
        stats.melee_armor = round(stats.melee_armor)
        stats.pierce_armor = round(stats.pierce_armor)
        stats.cost_food = round(stats.cost_food)
        stats.cost_wood = round(stats.cost_wood)
        stats.cost_gold = round(stats.cost_gold)
        stats.train_time = round(stats.train_time)
        stats.upgrade_cost = round(stats.upgrade_cost)
        stats.reload_time = round(stats.reload_time, 3)
        stats.range = round(stats.range, 1)

        return {
            "unit_name": final_unit_name,
            "unit_id": final_unit_id,
            "stats": stats,
            "has_unit": True,
            "applied_bonuses": applied_bonuses,
        }

    def calculate_unique_unit_stats(
        self, civ_name: str, uu_config: dict, max_age: int, elite: bool = False
    ) -> dict:
        """
        Calculate stats for a unique unit for its civilization.

        Args:
            civ_name: The civilization name
            uu_config: Unique unit configuration dict
            max_age: Maximum age (CASTLE_AGE or IMPERIAL_AGE)
            elite: Whether to calculate elite version stats

        Returns dict with:
        - stats: UnitStats object
        - has_unit: Whether the civ has this unit
        - applied_bonuses: List of applied civ bonuses
        """
        # Get the unit ID based on elite status
        if elite:
            unit_id = uu_config.get("elite_id", uu_config["base_id"])
            unit_name = uu_config.get(
                "elite_name", f"Elite {uu_config['display_name']}"
            )
        else:
            unit_id = uu_config["base_id"]
            unit_name = uu_config["display_name"]

        unit = self.get_unit(unit_id)
        if not unit:
            return {
                "unit_id": unit_id,
                "stats": None,
                "has_unit": False,
                "applied_bonuses": [],
            }

        unit_class = uu_config["unit_class"]
        stats = self.get_base_stats(unit)
        applied_bonuses = []

        # Apply standard techs (blacksmith upgrades, etc.)
        standard_techs = self.find_techs_affecting_unit(unit_id, unit_class, max_age)
        disabled_techs = self.get_disabled_techs(civ_name)

        for tech_id in sorted(standard_techs):
            if tech_id in disabled_techs:
                continue

            if tech_id in self.tech_effect_map:
                te = self.tech_effect_map[tech_id]
                for cmd in te.get("commands", []):
                    self.apply_effect_command(cmd, stats, unit_id, unit_class)

        # Apply civ bonus techs
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply unique techs (Castle/Imperial Age civ-specific techs like Garland Wars)
        unique_techs = self.get_unique_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in unique_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply building work rate to creation time
        # Unique units default to Castle; some can also be created in Barracks
        disabled_techs = self.get_disabled_techs(civ_name)
        if stats.train_time > 0:
            unit_slug = unit_name.lower().replace(" ", "_").replace("-", "_")
            castle_rate = self.get_building_work_rate(
                civ_name, UNIQUE_UNIT_BUILDING, max_age
            )
            # Check if this unit can also be created in Barracks
            barracks_key = (civ_name, unit_slug)
            if barracks_key in UNIQUE_UNITS_IN_BARRACKS:
                barracks_id = UNIQUE_UNITS_IN_BARRACKS[barracks_key]
                barracks_rate = self.get_building_work_rate(
                    civ_name, barracks_id, max_age
                )
                best_rate = max(castle_rate, barracks_rate)
            else:
                best_rate = castle_rate

            if best_rate > 1.0:
                stats.train_time = stats.train_time / best_rate
                # Determine which building gives best rate for bonus tracking
                best_building = UNIQUE_UNIT_BUILDING
                if barracks_key in UNIQUE_UNITS_IN_BARRACKS:
                    barracks_id = UNIQUE_UNITS_IN_BARRACKS[barracks_key]
                    if (
                        self.get_building_work_rate(civ_name, barracks_id, max_age)
                        > castle_rate
                    ):
                        best_building = barracks_id
                civ_id = self.civ_name_to_id.get(civ_name, -1)
                for tech_id, (
                    tech_civ_id,
                    bldg_mults,
                ) in BUILDING_WORK_RATE_TECHS.items():
                    if best_building in bldg_mults:
                        if tech_id not in disabled_techs:
                            if tech_civ_id == -1 or tech_civ_id == civ_id:
                                tech_age = self.get_tech_age_recursive(tech_id)
                                if tech_age <= max_age:
                                    te = self.tech_effect_map.get(tech_id, {})
                                    tname = te.get("tech_name", f"Tech {tech_id}")
                                    if tname not in applied_bonuses:
                                        applied_bonuses.append(tname)

        # Round values
        stats.hp = round(stats.hp)
        stats.speed = round(stats.speed, 2)
        stats.attack = round(stats.attack)
        stats.melee_armor = round(stats.melee_armor)
        stats.pierce_armor = round(stats.pierce_armor)
        stats.cost_food = round(stats.cost_food)
        stats.cost_wood = round(stats.cost_wood)
        stats.cost_gold = round(stats.cost_gold)
        stats.train_time = round(stats.train_time)
        stats.reload_time = round(stats.reload_time, 3)
        stats.range = round(stats.range, 1)

        return {
            "unit_id": unit_id,
            "stats": stats,
            "has_unit": True,
            "applied_bonuses": applied_bonuses,
        }


def create_database():
    """Create the SQLite database with the schema."""
    # Ensure parent directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
        -- Civilizations table
        CREATE TABLE civilizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        -- Ages table
        CREATE TABLE ages (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        -- Units table (unit types)
        CREATE TABLE units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            age_id INTEGER NOT NULL,
            unit_type TEXT DEFAULT 'standard',
            civ_id INTEGER,
            FOREIGN KEY (age_id) REFERENCES ages(id),
            FOREIGN KEY (civ_id) REFERENCES civilizations(id)
        );

        -- Unit stats table (stats for each civ/unit combination)
        CREATE TABLE unit_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL,
            unit_name TEXT NOT NULL,
            hp INTEGER,
            attack INTEGER,
            attack_range REAL,
            attack_speed REAL,
            attack_delay REAL,
            melee_armor INTEGER,
            pierce_armor INTEGER,
            movement_speed REAL,
            cost_food INTEGER,
            cost_wood INTEGER,
            cost_gold INTEGER,
            creation_time INTEGER,
            upgrade_cost INTEGER,
            civ_bonuses TEXT,
            has_unit INTEGER NOT NULL,
            attacks_json TEXT,
            armors_json TEXT,
            combat_wins INTEGER DEFAULT 0,
            combat_losses INTEGER DEFAULT 0,
            combat_draws INTEGER DEFAULT 0,
            combat_score REAL DEFAULT 0,
            -- Combat properties (data-driven simulation, no hardcoded slug lookups)
            min_attack_range REAL DEFAULT 0,
            is_siege_projectile INTEGER DEFAULT 0,
            splash_radius REAL DEFAULT 0,
            projectile_speed REAL DEFAULT 0,
            ignores_pierce_armor INTEGER DEFAULT 0,
            ignores_melee_armor INTEGER DEFAULT 0,
            trample_percent REAL DEFAULT 0,
            trample_radius REAL DEFAULT 0,
            trample_flat_damage INTEGER DEFAULT 0,
            bonus_damage_reduction REAL DEFAULT 0,
            unit_category TEXT DEFAULT 'military',
            paired_unit_slug TEXT,
            -- Unique unit mechanics
            extra_projectiles INTEGER DEFAULT 0,
            extra_projectile_attacks_json TEXT,
            charge_projectile_count INTEGER DEFAULT 0,
            charge_projectile_attacks_json TEXT,
            charge_projectile_speed REAL DEFAULT 0,
            charge_attack_range REAL DEFAULT 0,
            charge_ignores_armor INTEGER DEFAULT 0,
            splash_on_hit_radius REAL DEFAULT 0,
            dodge_shield_max INTEGER DEFAULT 0,
            dodge_shield_recharge REAL DEFAULT 0,
            bleed_dps REAL DEFAULT 0,
            bleed_duration REAL DEFAULT 0,
            block_first_melee INTEGER DEFAULT 0,
            attack_bonus_per_kill REAL DEFAULT 0,
            first_attack_extra_projectiles INTEGER DEFAULT 0,
            hp_transform_threshold REAL DEFAULT 0,
            -- HP transform alternate form (Jian Swordsman)
            transform_hp INTEGER,
            transform_attack INTEGER,
            transform_melee_armor INTEGER,
            transform_pierce_armor INTEGER,
            transform_attack_speed REAL,
            transform_attack_delay REAL,
            transform_movement_speed REAL,
            transform_attacks_json TEXT,
            transform_armors_json TEXT,
            -- Dismount on death (Konnik)
            dismount_hp INTEGER,
            dismount_attack INTEGER,
            dismount_melee_armor INTEGER,
            dismount_pierce_armor INTEGER,
            dismount_attack_speed REAL,
            dismount_attack_delay REAL,
            dismount_movement_speed REAL,
            dismount_attacks_json TEXT,
            dismount_armors_json TEXT,
            FOREIGN KEY (civ_id) REFERENCES civilizations(id),
            FOREIGN KEY (unit_id) REFERENCES units(id),
            UNIQUE(civ_id, unit_id)
        );

        -- Armor classes lookup table
        CREATE TABLE armor_classes (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        -- Combat simulation results table
        CREATE TABLE combat_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_stats_id_1 INTEGER NOT NULL,
            unit_stats_id_2 INTEGER NOT NULL,
            winner_id INTEGER,
            winner_hp_remaining INTEGER,
            combat_time REAL,
            hits_by_unit1 INTEGER,
            hits_by_unit2 INTEGER,
            FOREIGN KEY (unit_stats_id_1) REFERENCES unit_stats(id),
            FOREIGN KEY (unit_stats_id_2) REFERENCES unit_stats(id),
            FOREIGN KEY (winner_id) REFERENCES unit_stats(id)
        );

        -- Comments table for user feedback
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            civ_id INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            comment_text TEXT NOT NULL,
            author_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0,
            FOREIGN KEY (unit_id) REFERENCES units(id),
            FOREIGN KEY (civ_id) REFERENCES civilizations(id)
        );

        -- Create indexes
        CREATE INDEX idx_unit_stats_civ ON unit_stats(civ_id);
        CREATE INDEX idx_unit_stats_unit ON unit_stats(unit_id);
        CREATE INDEX idx_units_age ON units(age_id);
        CREATE INDEX idx_comments_unit ON comments(unit_id);
        CREATE INDEX idx_comments_civ ON comments(civ_id);
        CREATE INDEX idx_comments_resolved ON comments(resolved);
    """)

    conn.commit()
    return conn


def get_extracted_combat_properties(unit_id, units_data):
    """Read combat properties from extracted dat file data for a given game unit ID.

    Maps extracted fields to simulation combat property columns:
    - min_range → min_attack_range
    - projectile_speed (from projectile unit) → projectile_speed
    - class=13 + blast_width>0 + blast_damage≥1 → is_siege_projectile + splash_radius
    - total_projectiles → extra_projectiles (Chu Ko Nu, Kipchak, Organ Gun)
    - charge_type=6 + max_total_projectiles → extra_projectiles (Fire Archer)
    - charge_type=7 + max-total → first_attack_extra_projectiles (Xianbei)
    - secondary_projectile_attacks → extra_projectile_attacks_json
    - blast_width + blast_damage (0<dmg<1, level=2) → trample_percent + trample_radius
    - blast_width (level=11) → splash_on_hit_radius (Grenadier)
    - charge_type=4 → dodge_shield_max + dodge_shield_recharge (Shrivamsha)
    - bonus_damage_resistance → bonus_damage_reduction
    """
    if not unit_id or unit_id not in units_data:
        return {}

    unit = units_data[unit_id]
    props = {}

    # --- min_attack_range ---
    min_range = unit.get("min_range", 0) or 0
    if min_range > 0:
        props["min_attack_range"] = round(min_range, 2)

    # --- Projectile speed (from projectile unit's speed) ---
    proj_speed = unit.get("projectile_speed", 0) or 0
    if proj_speed > 0:
        props["projectile_speed"] = round(proj_speed, 2)

    # --- Siege projectile detection ---
    # Ranged siege units (class 13) with blast_width > 0 and blast_damage = 1.0 fire splash
    # projectiles (Mangonel, Siege Onager, Bombard Cannon).
    # Excludes melee siege (Rams, Siege Towers) and Organ Gun (blast_width=0).
    unit_class = unit.get("class", 0)
    blast_width = unit.get("blast_width", 0) or 0
    blast_damage = unit.get("blast_damage", 0) or 0
    blast_level = unit.get("blast_attack_level", 0) or 0
    unit_range = unit.get("range", 0) or 0

    if (
        unit_class == 13
        and blast_width > 0
        and blast_damage >= 1.0
        and unit_range >= 1.0
    ):
        props["is_siege_projectile"] = 1
        props["splash_radius"] = round(blast_width, 2)

    # --- Extra projectiles from total_projectiles ---
    # Units with total_projectiles > 1 fire extra arrows per attack.
    # Siege class (13) with blast_width > 0 fires stones (handled as splash above).
    # Organ Gun (class 13, blast_width=0) fires real extra projectiles like archers.
    total_proj = unit.get("total_projectiles", 1)
    is_siege_splash = unit_class == 13 and blast_width > 0 and blast_damage >= 1.0
    if total_proj and total_proj > 1 and not is_siege_splash:
        props["extra_projectiles"] = int(total_proj) - 1

    # --- Fire Archer extra projectiles from charge_type=6 ---
    # Fire Archer: total_proj=1, max_proj=3, charge_type=6 → 2 extra projectiles
    # Fire Lancer: total_proj=0 (melee), max_proj=3 → uses charge_projectile_count instead
    max_proj = unit.get("max_total_projectiles", 0)
    charge_type = unit.get("charge_type", 0)
    if (
        charge_type == 6
        and max_proj
        and max_proj > 1
        and total_proj
        and total_proj >= 1
    ):
        props["extra_projectiles"] = int(max_proj) - 1

    # --- First attack extra projectiles (burst) ---
    # Xianbei Raider (1952): total=1, max=6 → 5 extra on first attack
    if max_proj and total_proj and max_proj > total_proj:
        if charge_type == 7:
            props["first_attack_extra_projectiles"] = int(max_proj) - int(total_proj)

    # --- Secondary projectile attacks (different damage for extra projectiles) ---
    # Only relevant when unit actually fires extra projectiles (regular or burst)
    sec_attacks = unit.get("secondary_projectile_attacks")
    has_extra = (
        props.get("extra_projectiles", 0) > 0
        or props.get("first_attack_extra_projectiles", 0) > 0
    )
    if sec_attacks and has_extra:
        attacks_dict = {str(a["class"]): a["amount"] for a in sec_attacks}
        props["extra_projectile_attacks_json"] = json.dumps(attacks_dict)

    # --- Charge projectile attacks (Fire Lancer, Fire Archer, etc.) ---
    charge_proj_attacks = unit.get("charge_projectile_attacks")
    if charge_proj_attacks:
        attacks_dict = {str(a["class"]): a["amount"] for a in charge_proj_attacks}
        props["charge_projectile_attacks_json"] = json.dumps(attacks_dict)
    charge_proj_speed = unit.get("charge_projectile_speed", 0)
    if charge_proj_speed:
        props["charge_projectile_speed"] = charge_proj_speed
    charge_proj_count = 0
    if charge_type == 6 and max_proj and max_proj > 0:
        # Charge projectiles = max - base (melee units have total_proj=0)
        base_proj = int(total_proj) if total_proj else 0
        charge_proj_count = int(max_proj) - max(base_proj, 0)
    elif charge_type == 7 and max_proj and total_proj and max_proj > total_proj:
        charge_proj_count = int(max_proj) - int(total_proj)
    if charge_proj_count > 0:
        props["charge_projectile_count"] = charge_proj_count

    # --- Trample / splash from blast fields ---
    if blast_width > 0:
        if blast_level == 2 and 0 < blast_damage < 1.0:
            # Fractional trample: Battle Elephant (0.25), Ratha melee (0.2), War Elephant (0.5)
            props["trample_percent"] = round(blast_damage, 4)
            props["trample_radius"] = round(blast_width, 2)
        elif blast_level == 11:
            # Grenadier splash on hit (AoE around target)
            props["splash_on_hit_radius"] = round(blast_width, 2)

    # NOTE: blast_damage=-5.0 is standard for infantry/cavalry (means "no trample").
    # Cataphract trample comes from Logistica tech, not base unit stats - in CIV_COMBAT_PROPERTIES.

    # --- Dodge shield from charge_type=4 (Shrivamsha Rider) ---
    charge_attack = unit.get("charge_attack", 0)
    charge_recharge = unit.get("charge_recharge_rate", 0)

    if charge_type == 4 and charge_attack and charge_recharge:
        props["dodge_shield_max"] = int(charge_attack)
        props["dodge_shield_recharge"] = round(charge_attack / charge_recharge, 2)

    # --- Bonus damage reduction ---
    bonus_resist = unit.get("bonus_damage_resistance", 0)
    if bonus_resist and bonus_resist > 0:
        props["bonus_damage_reduction"] = round(bonus_resist, 4)

    return props


def get_combat_properties(unit_slug, civ_name=None, unit_id=None, units_data=None):
    """Look up combat properties for a unit slug, optionally with civ-specific overrides.

    For unique units, the slug has a civ suffix (e.g., 'leitis_lithuanians').
    We strip the suffix and look up in UNIQUE_COMBAT_PROPERTIES.

    Priority order (later overrides earlier):
    1. Defaults (all zeros)
    2. Extracted dat file data (data-driven stats like trample, extra projectiles)
    3. Hardcoded COMBAT_PROPERTIES / UNIQUE_COMBAT_PROPERTIES (ability flags, special cases)
    4. Civ-conditional CIV_COMBAT_PROPERTIES
    """
    props = {
        "min_attack_range": 0,
        "is_siege_projectile": 0,
        "splash_radius": 0,
        "projectile_speed": 0,
        "ignores_pierce_armor": 0,
        "ignores_melee_armor": 0,
        "trample_percent": 0,
        "trample_radius": 0,
        "trample_flat_damage": 0,
        "bonus_damage_reduction": 0,
        "unit_category": "military",
        "paired_unit_slug": None,
        "extra_projectiles": 0,
        "extra_projectile_attacks_json": None,
        "charge_projectile_count": 0,
        "charge_projectile_attacks_json": None,
        "charge_projectile_speed": 0,
        "charge_attack_range": 0,
        "charge_ignores_armor": 0,
        "splash_on_hit_radius": 0,
        "dodge_shield_max": 0,
        "dodge_shield_recharge": 0,
        "bleed_dps": 0,
        "bleed_duration": 0,
        "block_first_melee": 0,
        "attack_bonus_per_kill": 0,
        "first_attack_extra_projectiles": 0,
        "hp_transform_threshold": 0,
        "transform_unit_id": 0,
        "dismount_unit_id": 0,
    }

    # Apply extracted data from dat file (data-driven stats)
    if unit_id and units_data:
        extracted = get_extracted_combat_properties(unit_id, units_data)
        props.update(extracted)

    # Hardcoded overrides: standard combat properties (exact slug match)
    if unit_slug in COMBAT_PROPERTIES:
        props.update(COMBAT_PROPERTIES[unit_slug])

    # Hardcoded overrides: unique unit properties (strip civ suffix)
    for base_slug, unique_props in UNIQUE_COMBAT_PROPERTIES.items():
        if unit_slug == base_slug or unit_slug.startswith(base_slug + "_"):
            props.update(unique_props)
            break

    # Civ-conditional properties (e.g., Slavs champion gets Druzhina trample)
    if civ_name:
        # For standard units, key is (civ_name, unit_slug)
        civ_key = (civ_name, unit_slug)
        if civ_key in CIV_COMBAT_PROPERTIES:
            props.update(CIV_COMBAT_PROPERTIES[civ_key])

        # For unique units, try base slug (strip civ suffix) against CIV_COMBAT_PROPERTIES
        # Check all CIV_COMBAT_PROPERTIES keys for base slug matches
        for civ, base_slug in CIV_COMBAT_PROPERTIES:
            if civ == civ_name and base_slug != unit_slug:
                if unit_slug.startswith(base_slug + "_"):
                    props.update(CIV_COMBAT_PROPERTIES[(civ, base_slug)])
                    break

    # Check paired units
    for paired_slug, partner_slug in PAIRED_UNITS.items():
        if unit_slug == paired_slug or unit_slug.startswith(paired_slug + "_"):
            # Build the full partner slug with same civ suffix
            if unit_slug.startswith(paired_slug + "_"):
                suffix = unit_slug[len(paired_slug) :]
                props["paired_unit_slug"] = partner_slug + suffix
            else:
                props["paired_unit_slug"] = partner_slug
            break

    return props


def compute_dismount_stats(analyzer, dismount_unit_id, civ_name, max_age):
    """Compute stats for a dismounted unit (e.g., Konnik -> dismounted Konnik).

    Looks up the dismounted unit's base stats and applies relevant techs.
    Returns a dict with the dismounted unit's combat stats, or None.
    """
    if not dismount_unit_id:
        return None

    unit = analyzer.get_unit(dismount_unit_id)
    if not unit:
        return None

    stats = analyzer.get_base_stats(unit)
    unit_class = unit.get("class", 6)  # dismounted Konnik is infantry (class 6)

    # Apply standard techs (blacksmith upgrades, etc.)
    standard_techs = analyzer.find_techs_affecting_unit(
        dismount_unit_id, unit_class, max_age
    )
    disabled_techs = analyzer.get_disabled_techs(civ_name)

    for tech_id in sorted(standard_techs):
        if tech_id in disabled_techs:
            continue
        if tech_id in analyzer.tech_effect_map:
            te = analyzer.tech_effect_map[tech_id]
            for cmd in te.get("commands", []):
                analyzer.apply_effect_command(cmd, stats, dismount_unit_id, unit_class)

    # Apply civ bonus techs
    civ_bonus_techs = analyzer.get_civ_bonus_techs_for_unit(
        civ_name, dismount_unit_id, unit_class, max_age
    )
    for te in civ_bonus_techs:
        for cmd in te.get("commands", []):
            analyzer.apply_effect_command(cmd, stats, dismount_unit_id, unit_class)

    # Apply unique techs
    unique_techs = analyzer.get_unique_techs_for_unit(
        civ_name, dismount_unit_id, unit_class, max_age
    )
    for te in unique_techs:
        for cmd in te.get("commands", []):
            analyzer.apply_effect_command(cmd, stats, dismount_unit_id, unit_class)

    # Round values
    stats.hp = round(stats.hp)
    stats.attack = round(stats.attack)
    stats.melee_armor = round(stats.melee_armor)
    stats.pierce_armor = round(stats.pierce_armor)
    stats.speed = round(stats.speed, 2)
    stats.reload_time = round(stats.reload_time, 3)
    stats.attack_delay = round(stats.attack_delay, 3)

    return {
        "hp": int(stats.hp),
        "attack": int(stats.attack),
        "melee_armor": int(stats.melee_armor),
        "pierce_armor": int(stats.pierce_armor),
        "attack_speed": round(1.0 / stats.reload_time, 3)
        if stats.reload_time > 0
        else 0,
        "attack_delay": stats.attack_delay,
        "movement_speed": stats.speed,
        "attacks_json": json.dumps(stats.attacks) if stats.attacks else None,
        "armors_json": json.dumps(stats.armors) if stats.armors else None,
    }


def populate_database(conn, analyzer: UnitAnalyzer):
    """Populate the database with all unit stats."""
    cursor = conn.cursor()

    # Populate ages
    for age_id, age_name in AGE_NAMES.items():
        cursor.execute("INSERT INTO ages (id, name) VALUES (?, ?)", (age_id, age_name))

    # Populate civilizations (exclude Gaia)
    civ_names = sorted([c["name"] for c in analyzer.civs if c["name"] != "Gaia"])
    for civ_name in civ_names:
        cursor.execute("INSERT INTO civilizations (name) VALUES (?)", (civ_name,))

    # Get civ ID mapping
    cursor.execute("SELECT id, name FROM civilizations")
    civ_id_map = {row[1]: row[0] for row in cursor.fetchall()}

    # Populate armor classes from unit data
    armor_class_names = {}
    for unit in analyzer.units.values():
        for atk in unit.get("attacks", []):
            armor_class_names[atk["class"]] = atk.get(
                "class_name", f"Class {atk['class']}"
            )
        for arm in unit.get("armors", []):
            armor_class_names[arm["class"]] = arm.get(
                "class_name", f"Class {arm['class']}"
            )

    for class_id, class_name in sorted(armor_class_names.items()):
        cursor.execute(
            "INSERT OR IGNORE INTO armor_classes (id, name) VALUES (?, ?)",
            (class_id, class_name),
        )
    print(f"Populated {len(armor_class_names)} armor classes")

    # Populate units and stats
    for age_id, units in UNITS_BY_AGE.items():
        print(f"\nProcessing {AGE_NAMES[age_id]}...")

        for unit_slug, unit_config in units.items():
            display_name = unit_config["display_name"]
            print(f"  {display_name}...")

            # Insert unit (standard type)
            cursor.execute(
                "INSERT INTO units (slug, display_name, age_id, unit_type) VALUES (?, ?, ?, ?)",
                (unit_slug, display_name, age_id, "standard"),
            )
            db_unit_id = cursor.lastrowid

            # Calculate stats for each civ
            for civ_name in civ_names:
                result = analyzer.calculate_unit_stats_for_civ(
                    civ_name, unit_config, age_id
                )

                stats = result["stats"]
                has_unit = 1 if result["has_unit"] else 0

                # Format bonuses
                bonuses = result["applied_bonuses"]
                bonuses_str = None
                if bonuses:
                    bonuses_str = ", ".join(b.replace("C-Bonus, ", "") for b in bonuses)

                # Look up combat properties (extracted data + hardcoded overrides)
                game_unit_id = result.get("unit_id")
                combat_props = get_combat_properties(
                    unit_slug, civ_name, unit_id=game_unit_id, units_data=analyzer.units
                )

                if stats:
                    # Convert attacks and armors to JSON
                    attacks_json = json.dumps(stats.attacks) if stats.attacks else None
                    armors_json = json.dumps(stats.armors) if stats.armors else None

                    cursor.execute(
                        """
                        INSERT INTO unit_stats (
                            civ_id, unit_id, unit_name, hp, attack, attack_range,
                            attack_speed, attack_delay, melee_armor, pierce_armor, movement_speed,
                            cost_food, cost_wood, cost_gold, creation_time, upgrade_cost,
                            civ_bonuses, has_unit, attacks_json, armors_json,
                            min_attack_range, is_siege_projectile, splash_radius, projectile_speed,
                            ignores_pierce_armor, ignores_melee_armor, trample_percent,
                            trample_radius, trample_flat_damage, bonus_damage_reduction,
                            unit_category, paired_unit_slug,
                            extra_projectiles, extra_projectile_attacks_json,
                            charge_projectile_count, charge_projectile_attacks_json,
                            charge_projectile_speed,
                            charge_attack_range, charge_ignores_armor,
                            splash_on_hit_radius,
                            dodge_shield_max, dodge_shield_recharge,
                            bleed_dps, bleed_duration, block_first_melee,
                            attack_bonus_per_kill, first_attack_extra_projectiles,
                            hp_transform_threshold
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            civ_id_map[civ_name],
                            db_unit_id,
                            result["unit_name"],
                            int(stats.hp),
                            int(stats.attack),
                            float(stats.range) if stats.range > 0 else None,
                            round(stats.attack_rate(), 3),
                            round(stats.attack_delay, 3),
                            int(stats.melee_armor),
                            int(stats.pierce_armor),
                            stats.speed,
                            int(stats.cost_food),
                            int(stats.cost_wood),
                            int(stats.cost_gold),
                            int(stats.train_time),
                            int(stats.upgrade_cost),
                            bonuses_str,
                            has_unit,
                            attacks_json,
                            armors_json,
                            combat_props["min_attack_range"],
                            combat_props["is_siege_projectile"],
                            combat_props["splash_radius"],
                            combat_props["projectile_speed"],
                            combat_props["ignores_pierce_armor"],
                            combat_props["ignores_melee_armor"],
                            combat_props["trample_percent"],
                            combat_props["trample_radius"],
                            combat_props["trample_flat_damage"],
                            combat_props["bonus_damage_reduction"],
                            combat_props["unit_category"],
                            combat_props["paired_unit_slug"],
                            combat_props["extra_projectiles"],
                            combat_props["extra_projectile_attacks_json"],
                            combat_props["charge_projectile_count"],
                            combat_props["charge_projectile_attacks_json"],
                            combat_props["charge_projectile_speed"],
                            combat_props["charge_attack_range"],
                            combat_props["charge_ignores_armor"],
                            combat_props["splash_on_hit_radius"],
                            combat_props["dodge_shield_max"],
                            combat_props["dodge_shield_recharge"],
                            combat_props["bleed_dps"],
                            combat_props["bleed_duration"],
                            combat_props["block_first_melee"],
                            combat_props["attack_bonus_per_kill"],
                            combat_props["first_attack_extra_projectiles"],
                            combat_props["hp_transform_threshold"],
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO unit_stats (
                            civ_id, unit_id, unit_name, hp, attack, attack_range,
                            attack_speed, attack_delay, melee_armor, pierce_armor, movement_speed,
                            cost_food, cost_wood, cost_gold, creation_time, upgrade_cost,
                            civ_bonuses, has_unit, attacks_json, armors_json,
                            unit_category
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?)
                        """,
                        (
                            civ_id_map[civ_name],
                            db_unit_id,
                            result["unit_name"],
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            has_unit,
                            None,
                            None,
                            combat_props["unit_category"],
                        ),
                    )

    # Populate unique units
    print("\nProcessing Unique Units...")
    for civ_name, unique_units in UNIQUE_UNITS.items():
        if civ_name not in civ_id_map:
            continue

        db_civ_id = civ_id_map[civ_name]

        for uu_config in unique_units:
            display_name = uu_config["display_name"]
            elite_name = uu_config.get("elite_name")
            has_elite = uu_config.get("elite_id") is not None
            unit_slug = display_name.lower().replace(" ", "_").replace("-", "_")

            print(f"  {civ_name}: {display_name}...")

            # Insert unique unit (Castle Age - base version)
            cursor.execute(
                "INSERT INTO units (slug, display_name, age_id, unit_type, civ_id) VALUES (?, ?, ?, ?, ?)",
                (
                    f"{unit_slug}_{civ_name.lower()}",
                    display_name,
                    CASTLE_AGE,
                    "unique",
                    db_civ_id,
                ),
            )
            db_unit_id_castle = cursor.lastrowid

            db_unit_id_imperial = None
            if has_elite:
                # Insert elite version (Imperial Age)
                cursor.execute(
                    "INSERT INTO units (slug, display_name, age_id, unit_type, civ_id) VALUES (?, ?, ?, ?, ?)",
                    (
                        f"elite_{unit_slug}_{civ_name.lower()}",
                        elite_name or f"Elite {display_name}",
                        IMPERIAL_AGE,
                        "unique",
                        db_civ_id,
                    ),
                )
                db_unit_id_imperial = cursor.lastrowid

            # Calculate stats for the unique unit's civ only
            # Castle Age (base unit)
            result_castle = analyzer.calculate_unique_unit_stats(
                civ_name, uu_config, CASTLE_AGE, elite=False
            )

            # Build list of units to process
            units_to_process = [(db_unit_id_castle, result_castle, display_name)]

            if has_elite:
                # Imperial Age (elite unit)
                result_imperial = analyzer.calculate_unique_unit_stats(
                    civ_name, uu_config, IMPERIAL_AGE, elite=True
                )
                units_to_process.append(
                    (
                        db_unit_id_imperial,
                        result_imperial,
                        elite_name or f"Elite {display_name}",
                    )
                )
            else:
                # For units without elite version, also calculate Imperial Age stats
                # so they get Imperial Age unique techs (e.g., Warrior Priest + Fereters)
                result_imperial = analyzer.calculate_unique_unit_stats(
                    civ_name, uu_config, IMPERIAL_AGE, elite=False
                )
                # Insert Imperial Age version of the unit (with _imp suffix to avoid slug conflict)
                cursor.execute(
                    "INSERT INTO units (slug, display_name, age_id, unit_type, civ_id) VALUES (?, ?, ?, ?, ?)",
                    (
                        f"{unit_slug}_imp_{civ_name.lower()}",
                        display_name,
                        IMPERIAL_AGE,
                        "unique",
                        db_civ_id,
                    ),
                )
                db_unit_id_imperial = cursor.lastrowid
                units_to_process.append(
                    (db_unit_id_imperial, result_imperial, display_name)
                )

            # Build slug list matching units_to_process order
            castle_slug = f"{unit_slug}_{civ_name.lower()}"
            if has_elite:
                imperial_slug = f"elite_{unit_slug}_{civ_name.lower()}"
            else:
                imperial_slug = f"{unit_slug}_imp_{civ_name.lower()}"
            slugs_to_process = [castle_slug, imperial_slug]

            for idx, (db_unit_id, result, unit_name) in enumerate(units_to_process):
                stats = result["stats"]
                has_unit = 1 if result["has_unit"] else 0
                bonuses = result.get("applied_bonuses", [])
                bonuses_str = (
                    ", ".join(b.replace("C-Bonus, ", "") for b in bonuses)
                    if bonuses
                    else None
                )

                # Look up combat properties (extracted data + hardcoded overrides)
                uu_slug = slugs_to_process[idx]
                game_unit_id = result.get("unit_id")
                combat_props = get_combat_properties(
                    uu_slug, civ_name, unit_id=game_unit_id, units_data=analyzer.units
                )

                # Compute transform stats if applicable (e.g., Jian Swordsman)
                transform_id = combat_props.get("transform_unit_id", 0)
                ts = (
                    compute_dismount_stats(
                        analyzer,
                        transform_id,
                        civ_name,
                        CASTLE_AGE if idx == 0 else IMPERIAL_AGE,
                    )
                    if transform_id
                    else None
                )

                # Compute dismount stats if applicable (e.g., Konnik)
                dismount_id = combat_props.get("dismount_unit_id", 0)
                ds = (
                    compute_dismount_stats(
                        analyzer,
                        dismount_id,
                        civ_name,
                        CASTLE_AGE if idx == 0 else IMPERIAL_AGE,
                    )
                    if dismount_id
                    else None
                )

                if stats:
                    attacks_json = json.dumps(stats.attacks) if stats.attacks else None
                    armors_json = json.dumps(stats.armors) if stats.armors else None

                    cursor.execute(
                        """
                        INSERT INTO unit_stats (
                            civ_id, unit_id, unit_name, hp, attack, attack_range,
                            attack_speed, attack_delay, melee_armor, pierce_armor, movement_speed,
                            cost_food, cost_wood, cost_gold, creation_time, upgrade_cost,
                            civ_bonuses, has_unit, attacks_json, armors_json,
                            min_attack_range, is_siege_projectile, splash_radius, projectile_speed,
                            ignores_pierce_armor, ignores_melee_armor, trample_percent,
                            trample_radius, trample_flat_damage, bonus_damage_reduction,
                            unit_category, paired_unit_slug,
                            extra_projectiles, extra_projectile_attacks_json,
                            charge_projectile_count, charge_projectile_attacks_json,
                            charge_projectile_speed,
                            charge_attack_range, charge_ignores_armor,
                            splash_on_hit_radius,
                            dodge_shield_max, dodge_shield_recharge,
                            bleed_dps, bleed_duration, block_first_melee,
                            attack_bonus_per_kill, first_attack_extra_projectiles,
                            hp_transform_threshold,
                            transform_hp, transform_attack, transform_melee_armor,
                            transform_pierce_armor, transform_attack_speed,
                            transform_attack_delay, transform_movement_speed,
                            transform_attacks_json, transform_armors_json,
                            dismount_hp, dismount_attack, dismount_melee_armor,
                            dismount_pierce_armor, dismount_attack_speed,
                            dismount_attack_delay, dismount_movement_speed,
                            dismount_attacks_json, dismount_armors_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            db_civ_id,
                            db_unit_id,
                            unit_name,
                            int(stats.hp),
                            int(stats.attack),
                            float(stats.range) if stats.range > 0 else None,
                            round(stats.attack_rate(), 3),
                            round(stats.attack_delay, 3),
                            int(stats.melee_armor),
                            int(stats.pierce_armor),
                            stats.speed,
                            int(stats.cost_food),
                            int(stats.cost_wood),
                            int(stats.cost_gold),
                            int(stats.train_time),
                            int(stats.upgrade_cost) if stats.upgrade_cost else 0,
                            bonuses_str,
                            has_unit,
                            attacks_json,
                            armors_json,
                            combat_props["min_attack_range"],
                            combat_props["is_siege_projectile"],
                            combat_props["splash_radius"],
                            combat_props["projectile_speed"],
                            combat_props["ignores_pierce_armor"],
                            combat_props["ignores_melee_armor"],
                            combat_props["trample_percent"],
                            combat_props["trample_radius"],
                            combat_props["trample_flat_damage"],
                            combat_props["bonus_damage_reduction"],
                            combat_props["unit_category"],
                            combat_props["paired_unit_slug"],
                            combat_props["extra_projectiles"],
                            combat_props["extra_projectile_attacks_json"],
                            combat_props["charge_projectile_count"],
                            combat_props["charge_projectile_attacks_json"],
                            combat_props["charge_projectile_speed"],
                            combat_props["charge_attack_range"],
                            combat_props["charge_ignores_armor"],
                            combat_props["splash_on_hit_radius"],
                            combat_props["dodge_shield_max"],
                            combat_props["dodge_shield_recharge"],
                            combat_props["bleed_dps"],
                            combat_props["bleed_duration"],
                            combat_props["block_first_melee"],
                            combat_props["attack_bonus_per_kill"],
                            combat_props["first_attack_extra_projectiles"],
                            combat_props["hp_transform_threshold"],
                            ts["hp"] if ts else None,
                            ts["attack"] if ts else None,
                            ts["melee_armor"] if ts else None,
                            ts["pierce_armor"] if ts else None,
                            ts["attack_speed"] if ts else None,
                            ts["attack_delay"] if ts else None,
                            ts["movement_speed"] if ts else None,
                            ts["attacks_json"] if ts else None,
                            ts["armors_json"] if ts else None,
                            ds["hp"] if ds else None,
                            ds["attack"] if ds else None,
                            ds["melee_armor"] if ds else None,
                            ds["pierce_armor"] if ds else None,
                            ds["attack_speed"] if ds else None,
                            ds["attack_delay"] if ds else None,
                            ds["movement_speed"] if ds else None,
                            ds["attacks_json"] if ds else None,
                            ds["armors_json"] if ds else None,
                        ),
                    )

    conn.commit()


def print_stats(conn):
    """Print database statistics."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM civilizations")
    civ_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM units")
    unit_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM unit_stats")
    stats_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM unit_stats WHERE has_unit = 1")
    available_count = cursor.fetchone()[0]

    print(f"\nDatabase created at: {DB_PATH}")
    print(f"  Civilizations: {civ_count}")
    print(f"  Unit types: {unit_count}")
    print(f"  Unit stats records: {stats_count}")
    print(f"  Available unit/civ combinations: {available_count}")

    # Show units by age
    print("\nUnits by age:")
    for age_id, age_name in AGE_NAMES.items():
        cursor.execute("SELECT COUNT(*) FROM units WHERE age_id = ?", (age_id,))
        count = cursor.fetchone()[0]
        print(f"  {age_name}: {count} units")


# =============================================================================
# REFERENCE / AUDIT DATABASE
# =============================================================================


def _describe_effect_cmd(cmd, armor_class_names):
    """Generate a human-readable description of a single effect command."""
    cmd_type = cmd.get("type", 0)
    c = cmd.get("c", 0)
    d = cmd.get("d", 0)

    if cmd_type == CMD_SET_ATTRIBUTE:
        attr_name = ATTR_DISPLAY_NAMES.get(c, f"attr_{c}")
        if c == ATTR_ACCURACY:
            return f"set {attr_name}={d:.0f}%"
        return f"set {attr_name}={d:.3g}"
    elif cmd_type == CMD_ADD_ATTRIBUTE:
        if c == ATTR_ATTACK:
            d_int = int(d)
            if d_int >= 0:
                atk_class = d_int // 256
                amount = d_int % 256
                if amount > 127:
                    amount -= 256
            else:
                d_int_abs = abs(d_int)
                atk_class = d_int_abs // 256
                amount = -(d_int_abs % 256)
            cls_name = armor_class_names.get(atk_class, f"class {atk_class}")
            sign = "+" if amount >= 0 else ""
            return f"{sign}{amount} attack ({cls_name})"
        elif c == ATTR_ARMOR:
            d_int = int(d)
            if d_int >= 0:
                arm_class = d_int // 256
                amount = d_int % 256
                if amount > 127:
                    amount -= 256
            else:
                d_int_abs = abs(d_int)
                arm_class = d_int_abs // 256
                amount = -(d_int_abs % 256)
            cls_name = armor_class_names.get(arm_class, f"class {arm_class}")
            sign = "+" if amount >= 0 else ""
            return f"{sign}{amount} armor ({cls_name})"
        else:
            attr_name = ATTR_DISPLAY_NAMES.get(c, f"attr_{c}")
            sign = "+" if d >= 0 else ""
            return f"{sign}{d:.3g} {attr_name}"
    elif cmd_type == CMD_MULTIPLY_ATTRIBUTE:
        attr_name = ATTR_DISPLAY_NAMES.get(c, f"attr_{c}")
        return f"x{d:.3g} {attr_name}"
    return f"cmd_{cmd_type} attr_{c}={d}"


def _get_tech_building(tech_data):
    """Get building name for a tech from its research_location."""
    rl = tech_data.get("research_location", -1)
    if rl >= 0:
        return BUILDING_NAMES.get(rl, f"Building_{rl}")
    return "N/A"


def _tech_age_name(age_num):
    """Convert age number to name."""
    return {1: "Dark", 2: "Feudal", 3: "Castle", 4: "Imperial"}.get(
        age_num, f"Age {age_num}"
    )


def _snapshot_stats(stats):
    """Capture a snapshot of current stats as a dict."""
    return {
        "hp": stats.hp,
        "attack": stats.attack,
        "melee_armor": stats.melee_armor,
        "pierce_armor": stats.pierce_armor,
        "speed": stats.speed,
        "range": stats.range,
        "reload_time": stats.reload_time,
        "accuracy": stats.accuracy,
        "los": stats.los,
        "train_time": stats.train_time,
        "cost_food": stats.cost_food,
        "cost_wood": stats.cost_wood,
        "cost_gold": stats.cost_gold,
        "attacks": dict(stats.attacks),
        "armors": dict(stats.armors),
    }


def _diff_stats(before, after, armor_class_names):
    """Describe what changed between two stat snapshots."""
    changes = []
    for key, label in [
        ("hp", "HP"),
        ("attack", "Attack"),
        ("melee_armor", "MA"),
        ("pierce_armor", "PA"),
        ("speed", "Speed"),
        ("range", "Range"),
        ("reload_time", "Reload"),
        ("accuracy", "Accuracy"),
        ("los", "LOS"),
        ("train_time", "Train Time"),
    ]:
        old_val = before[key]
        new_val = after[key]
        if abs(new_val - old_val) > 0.001:
            diff = new_val - old_val
            # Check if multiplicative (ratio-based)
            if (
                old_val != 0
                and abs(diff / old_val) > 0.01
                and key in ("reload_time", "speed", "hp")
            ):
                ratio = new_val / old_val
                if abs(ratio - round(ratio)) > 0.001:  # Not a clean additive
                    changes.append(f"x{ratio:.3g} {label}")
                    continue
            sign = "+" if diff > 0 else ""
            changes.append(f"{sign}{diff:.3g} {label}")

    # Cost changes
    for key, label in [
        ("cost_food", "food"),
        ("cost_wood", "wood"),
        ("cost_gold", "gold"),
    ]:
        old_val = before[key]
        new_val = after[key]
        if abs(new_val - old_val) > 0.01:
            diff = new_val - old_val
            if old_val != 0:
                ratio = new_val / old_val
                if abs(ratio - round(ratio)) > 0.001:
                    changes.append(f"x{ratio:.3g} {label}")
                    continue
            sign = "+" if diff > 0 else ""
            changes.append(f"{sign}{diff:.3g} {label}")

    # Attack class changes
    for cls_id in sorted(
        set(list(before["attacks"].keys()) + list(after["attacks"].keys()))
    ):
        old_val = before["attacks"].get(cls_id, 0)
        new_val = after["attacks"].get(cls_id, 0)
        if abs(new_val - old_val) > 0.001:
            cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
            sign = "+" if (new_val - old_val) > 0 else ""
            changes.append(f"{sign}{new_val - old_val:.0f} atk ({cls_name})")

    # Armor class changes
    for cls_id in sorted(
        set(list(before["armors"].keys()) + list(after["armors"].keys()))
    ):
        old_val = before["armors"].get(cls_id, 0)
        new_val = after["armors"].get(cls_id, 0)
        if abs(new_val - old_val) > 0.001:
            cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
            sign = "+" if (new_val - old_val) > 0 else ""
            changes.append(f"{sign}{new_val - old_val:.0f} armor ({cls_name})")

    return ", ".join(changes) if changes else "(no change)"


def generate_reference_database(analyzer):
    """Generate the reference/audit database with detailed stat breakdowns."""
    ref_db_path = Path(__file__).parent / "webapp" / "aoe2_reference.db"
    if ref_db_path.exists():
        ref_db_path.unlink()

    conn = sqlite3.connect(str(ref_db_path))
    cursor = conn.cursor()

    # Load armor class names
    armor_class_names = {}
    ac_file = OUTPUT_DIR / "armor_classes.json"
    if ac_file.exists():
        for ac in json.load(open(ac_file)):
            armor_class_names[ac["id"]] = ac["name"]

    # Create tables
    cursor.executescript("""
        CREATE TABLE ref_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ_name TEXT NOT NULL,
            unit_name TEXT NOT NULL,
            unit_slug TEXT NOT NULL,
            unit_type TEXT NOT NULL,
            age TEXT NOT NULL,
            unit_class INTEGER,
            unit_class_name TEXT,
            is_ranged INTEGER DEFAULT 0,
            base_hp REAL, base_attack REAL, base_melee_armor REAL, base_pierce_armor REAL,
            base_speed REAL, base_range REAL, base_reload_time REAL, base_attack_delay REAL,
            base_accuracy REAL, base_los REAL,
            base_cost_food REAL, base_cost_wood REAL, base_cost_gold REAL,
            base_attacks_json TEXT, base_armors_json TEXT,
            final_hp REAL, final_attack REAL, final_melee_armor REAL, final_pierce_armor REAL,
            final_speed REAL, final_range REAL, final_reload_time REAL, final_attack_delay REAL,
            final_accuracy REAL, final_los REAL,
            final_cost_food REAL, final_cost_wood REAL, final_cost_gold REAL,
            final_attacks_json TEXT, final_armors_json TEXT,
            base_train_time REAL, final_train_time REAL,
            total_projectiles REAL, projectile_speed REAL, min_range REAL,
            applied_bonuses_summary TEXT,
            upgrade_cost_food INTEGER DEFAULT 0,
            upgrade_cost_wood INTEGER DEFAULT 0,
            upgrade_cost_gold INTEGER DEFAULT 0
        );
        CREATE TABLE ref_techs_applied (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            tech_id INTEGER,
            tech_name TEXT NOT NULL,
            tech_type TEXT NOT NULL,
            building TEXT,
            age_available TEXT,
            effect_description TEXT,
            cost_food INTEGER DEFAULT 0,
            cost_wood INTEGER DEFAULT 0,
            cost_gold INTEGER DEFAULT 0,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
        CREATE TABLE ref_stat_chain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            tech_name TEXT NOT NULL,
            tech_type TEXT NOT NULL,
            hp REAL, attack REAL, melee_armor REAL, pierce_armor REAL,
            speed REAL, range_val REAL, reload_time REAL,
            accuracy REAL, los REAL, train_time REAL,
            cost_food REAL, cost_wood REAL, cost_gold REAL,
            attacks_json TEXT, armors_json TEXT,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
        CREATE TABLE ref_special_effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            property_name TEXT NOT NULL,
            property_value TEXT,
            source TEXT,
            description TEXT,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
        CREATE TABLE ref_projectiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            projectile_type TEXT NOT NULL,
            projectile_count INTEGER,
            projectile_speed REAL,
            attacks_json TEXT,
            blast_radius REAL,
            is_siege_projectile INTEGER DEFAULT 0,
            FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
        );
    """)

    # Class names from unit data
    class_names = {}
    for uid, u in analyzer.units.items():
        cls_id = u.get("class", -1)
        cls_name = u.get("class_name", "")
        if cls_id >= 0 and cls_name:
            class_names[cls_id] = cls_name

    def _insert_stat_chain_row(ref_unit_id, step, tech_name, tech_type, snap):
        cursor.execute(
            """INSERT INTO ref_stat_chain
               (ref_unit_id, step_order, tech_name, tech_type,
                hp, attack, melee_armor, pierce_armor,
                speed, range_val, reload_time, accuracy, los, train_time,
                cost_food, cost_wood, cost_gold,
                attacks_json, armors_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ref_unit_id,
                step,
                tech_name,
                tech_type,
                snap["hp"],
                snap["attack"],
                snap["melee_armor"],
                snap["pierce_armor"],
                snap["speed"],
                snap["range"],
                snap["reload_time"],
                snap["accuracy"],
                snap["los"],
                snap["train_time"],
                snap["cost_food"],
                snap["cost_wood"],
                snap["cost_gold"],
                json.dumps(snap["attacks"]),
                json.dumps(snap["armors"]),
            ),
        )

    def _insert_tech_applied(
        ref_unit_id,
        tech_id,
        tech_name,
        tech_type,
        building,
        age_available,
        effect_desc,
        cost,
    ):
        cursor.execute(
            """INSERT INTO ref_techs_applied
               (ref_unit_id, tech_id, tech_name, tech_type, building,
                age_available, effect_description, cost_food, cost_wood, cost_gold)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                ref_unit_id,
                tech_id,
                tech_name,
                tech_type,
                building,
                age_available,
                effect_desc,
                cost.get("food", 0),
                cost.get("wood", 0),
                cost.get("gold", 0),
            ),
        )

    def process_unit_audited(
        civ_name,
        unit_id,
        unit_class,
        unit_name,
        unit_slug,
        unit_type,
        age_label,
        max_age,
        unit_data,
    ):
        """Process one unit with full audit trail. Returns ref_unit_id or None."""
        stats = analyzer.get_base_stats(unit_data)
        base_snap = _snapshot_stats(stats)
        is_ranged = 1 if unit_data.get("range", 0) > 1 else 0

        # Insert ref_units row (will fill final stats later)
        cursor.execute(
            """INSERT INTO ref_units
               (civ_name, unit_name, unit_slug, unit_type, age,
                unit_class, unit_class_name, is_ranged,
                base_hp, base_attack, base_melee_armor, base_pierce_armor,
                base_speed, base_range, base_reload_time, base_attack_delay,
                base_accuracy, base_los,
                base_cost_food, base_cost_wood, base_cost_gold,
                base_attacks_json, base_armors_json,
                base_train_time,
                total_projectiles, projectile_speed, min_range)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                civ_name,
                unit_name,
                unit_slug,
                unit_type,
                age_label,
                unit_class,
                class_names.get(unit_class, ""),
                is_ranged,
                base_snap["hp"],
                base_snap["attack"],
                base_snap["melee_armor"],
                base_snap["pierce_armor"],
                base_snap["speed"],
                base_snap["range"],
                base_snap["reload_time"],
                unit_data.get("attack_delay", 0),
                base_snap["accuracy"],
                base_snap["los"],
                base_snap["cost_food"],
                base_snap["cost_wood"],
                base_snap["cost_gold"],
                json.dumps(base_snap["attacks"]),
                json.dumps(base_snap["armors"]),
                base_snap["train_time"],
                unit_data.get("total_projectiles", 1),
                unit_data.get("projectile_speed", 0),
                unit_data.get("min_range", 0),
            ),
        )
        ref_unit_id = cursor.lastrowid

        # Step 0: base stats
        step = 0
        _insert_stat_chain_row(ref_unit_id, step, "Base Stats", "base", base_snap)
        step += 1

        disabled_techs = analyzer.get_disabled_techs(civ_name)
        all_tech_names = []

        # Phase 1: Standard techs
        standard_techs = analyzer.find_techs_affecting_unit(
            unit_id, unit_class, max_age
        )
        for tech_id in sorted(standard_techs):
            if tech_id in disabled_techs:
                continue
            if tech_id not in analyzer.tech_effect_map:
                continue

            te = analyzer.tech_effect_map[tech_id]
            tech_data = analyzer.techs.get(tech_id, {})
            tech_name = tech_data.get("name", f"Tech {tech_id}")
            building = _get_tech_building(tech_data)
            tech_age = analyzer.get_tech_age(tech_id)
            cost = tech_data.get("cost", {})

            before = _snapshot_stats(stats)
            applied = False
            effects = []
            for cmd in te.get("commands", []):
                if analyzer.apply_effect_command(cmd, stats, unit_id, unit_class):
                    applied = True
                    effects.append(_describe_effect_cmd(cmd, armor_class_names))

            if applied:
                after = _snapshot_stats(stats)
                effect_desc = "; ".join(effects)
                _insert_tech_applied(
                    ref_unit_id,
                    tech_id,
                    tech_name,
                    "standard",
                    building,
                    _tech_age_name(tech_age),
                    effect_desc,
                    cost,
                )
                _insert_stat_chain_row(ref_unit_id, step, tech_name, "standard", after)
                step += 1
                all_tech_names.append(tech_name)

        # Phase 2: Civ bonus techs
        civ_bonus_techs = analyzer.get_civ_bonus_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in civ_bonus_techs:
            tech_id = te.get("tech_id", 0)
            tech_data = analyzer.techs.get(tech_id, {})
            tech_name = tech_data.get("name", f"Tech {tech_id}")
            if tech_name in ("None", "", None):
                tech_name = f"C-Bonus (Tech {tech_id})"
            tech_age = analyzer.get_tech_age_recursive(tech_id)
            cost = tech_data.get("cost", {})

            before = _snapshot_stats(stats)
            applied = False
            effects = []
            for cmd in te.get("commands", []):
                if analyzer.apply_effect_command(cmd, stats, unit_id, unit_class):
                    applied = True
                    effects.append(_describe_effect_cmd(cmd, armor_class_names))

            if applied:
                after = _snapshot_stats(stats)
                effect_desc = "; ".join(effects)
                _insert_tech_applied(
                    ref_unit_id,
                    tech_id,
                    tech_name,
                    "civ_bonus",
                    "N/A",
                    _tech_age_name(tech_age),
                    effect_desc,
                    cost,
                )
                _insert_stat_chain_row(ref_unit_id, step, tech_name, "civ_bonus", after)
                step += 1
                all_tech_names.append(tech_name)

        # Phase 3: Unique techs
        unique_techs = analyzer.get_unique_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in unique_techs:
            tech_id = te.get("tech_id", 0)
            tech_data = analyzer.techs.get(tech_id, {})
            tech_name = te.get("tech_name", tech_data.get("name", f"Tech {tech_id}"))
            building = _get_tech_building(tech_data)
            tech_age = analyzer.get_tech_age_recursive(tech_id)
            cost = tech_data.get("cost", {})

            before = _snapshot_stats(stats)
            applied = False
            effects = []
            for cmd in te.get("commands", []):
                if analyzer.apply_effect_command(cmd, stats, unit_id, unit_class):
                    applied = True
                    effects.append(_describe_effect_cmd(cmd, armor_class_names))

            if applied:
                after = _snapshot_stats(stats)
                effect_desc = "; ".join(effects)
                _insert_tech_applied(
                    ref_unit_id,
                    tech_id,
                    tech_name,
                    "unique_tech",
                    building,
                    _tech_age_name(tech_age),
                    effect_desc,
                    cost,
                )
                _insert_stat_chain_row(
                    ref_unit_id, step, tech_name, "unique_tech", after
                )
                step += 1
                all_tech_names.append(tech_name)

        # Final stats
        final_snap = _snapshot_stats(stats)

        # Apply building work rate to creation time
        if final_snap["train_time"] > 0:
            if unit_type == "unique":
                bld_id = UNIQUE_UNIT_BUILDING
                # Strip civ suffix from slug for lookup (e.g. elite_huskarl_goths → elite_huskarl)
                unit_slug_key = unit_slug
                civ_suffix = "_" + civ_name.lower()
                if unit_slug_key.endswith(civ_suffix):
                    unit_slug_key = unit_slug_key[: -len(civ_suffix)]
                barracks_key = (civ_name, unit_slug_key)
                castle_rate = analyzer.get_building_work_rate(
                    civ_name, UNIQUE_UNIT_BUILDING, max_age
                )
                if barracks_key in UNIQUE_UNITS_IN_BARRACKS:
                    barracks_id = UNIQUE_UNITS_IN_BARRACKS[barracks_key]
                    barracks_rate = analyzer.get_building_work_rate(
                        civ_name, barracks_id, max_age
                    )
                    best_rate = max(castle_rate, barracks_rate)
                    if barracks_rate > castle_rate:
                        bld_id = barracks_id
                else:
                    best_rate = castle_rate
            else:
                bld_id = UNIT_CLASS_TO_BUILDING.get(unit_class)
                best_rate = (
                    analyzer.get_building_work_rate(civ_name, bld_id, max_age)
                    if bld_id
                    else 1.0
                )

            if best_rate > 1.0:
                final_snap["train_time"] = final_snap["train_time"] / best_rate
                # Add stat chain step and tech applied entries for work rate techs
                disabled_techs = analyzer.get_disabled_techs(civ_name)
                civ_id = analyzer.civ_name_to_id.get(civ_name, -1)
                work_rate_techs = []
                for tech_id, (
                    tech_civ_id,
                    bldg_mults,
                ) in BUILDING_WORK_RATE_TECHS.items():
                    if bld_id not in bldg_mults:
                        continue
                    if tech_id in disabled_techs:
                        continue
                    if tech_civ_id != -1 and tech_civ_id != civ_id:
                        continue
                    tech_age = analyzer.get_tech_age_recursive(tech_id)
                    if tech_age > max_age:
                        continue
                    te = analyzer.tech_effect_map.get(tech_id, {})
                    tname = te.get("tech_name", f"Tech {tech_id}")
                    work_rate_techs.append(tname)
                    # Add tech applied entry
                    building = te.get("building", "")
                    cost = te.get("cost", {})
                    mult = bldg_mults[bld_id]
                    effect_desc = f"Building work rate ×{mult} (train time ÷{mult})"
                    _insert_tech_applied(
                        ref_unit_id,
                        tech_id,
                        tname,
                        "work_rate",
                        building,
                        _tech_age_name(tech_age),
                        effect_desc,
                        cost,
                    )
                    all_tech_names.append(tname)
                # Add team bonus work rate if applicable
                team_bonus = CIV_TEAM_BONUS_WORK_RATE.get(civ_name, {})
                if bld_id in team_bonus:
                    tb_mult = team_bonus[bld_id]
                    tb_name = f"{civ_name} Team Bonus"
                    work_rate_techs.append(tb_name)
                    effect_desc = (
                        f"Building work rate ×{tb_mult} (train time ÷{tb_mult})"
                    )
                    _insert_tech_applied(
                        ref_unit_id,
                        -1,
                        tb_name,
                        "civ_bonus",
                        "N/A",
                        "Dark",
                        effect_desc,
                        {},
                    )
                    all_tech_names.append(tb_name)
                # Add stat chain step showing the work rate effect
                work_rate_snap = dict(final_snap)
                _insert_stat_chain_row(
                    ref_unit_id,
                    step,
                    "Building Work Rate (" + ", ".join(work_rate_techs) + ")",
                    "work_rate",
                    work_rate_snap,
                )
                step += 1

        cursor.execute(
            """UPDATE ref_units SET
               final_hp=?, final_attack=?, final_melee_armor=?, final_pierce_armor=?,
               final_speed=?, final_range=?, final_reload_time=?, final_attack_delay=?,
               final_accuracy=?, final_los=?,
               final_cost_food=?, final_cost_wood=?, final_cost_gold=?,
               final_attacks_json=?, final_armors_json=?,
               final_train_time=?,
               applied_bonuses_summary=?
               WHERE id=?""",
            (
                round(final_snap["hp"]),
                round(final_snap["attack"]),
                round(final_snap["melee_armor"]),
                round(final_snap["pierce_armor"]),
                round(final_snap["speed"], 2),
                round(final_snap["range"], 1),
                round(final_snap["reload_time"], 3),
                unit_data.get("attack_delay", 0),
                round(final_snap["accuracy"]),
                round(final_snap["los"], 1),
                round(final_snap["cost_food"]),
                round(final_snap["cost_wood"]),
                round(final_snap["cost_gold"]),
                json.dumps(
                    {str(k): round(v) for k, v in final_snap["attacks"].items()}
                ),
                json.dumps({str(k): round(v) for k, v in final_snap["armors"].items()}),
                round(final_snap["train_time"]),
                ", ".join(all_tech_names),
                ref_unit_id,
            ),
        )

        # Compute total upgrade cost (sum of all tech costs, with civ discount)
        tech_costs = cursor.execute(
            """SELECT cost_food, cost_wood, cost_gold, age_available
               FROM ref_techs_applied WHERE ref_unit_id=?""",
            (ref_unit_id,),
        ).fetchall()
        discount_map = CIV_TECH_COST_DISCOUNT.get(civ_name, {})
        total_food, total_wood, total_gold = 0, 0, 0
        for tc_food, tc_wood, tc_gold, tc_age in tech_costs:
            discount = discount_map.get(tc_age, 0)
            mult = 1.0 - discount
            total_food += round(tc_food * mult)
            total_wood += round(tc_wood * mult)
            total_gold += round(tc_gold * mult)
        cursor.execute(
            """UPDATE ref_units SET upgrade_cost_food=?, upgrade_cost_wood=?, upgrade_cost_gold=?
               WHERE id=?""",
            (total_food, total_wood, total_gold, ref_unit_id),
        )

        # Special effects (combat properties)
        combat_props = get_combat_properties(
            unit_slug, civ_name=civ_name, unit_id=unit_id, units_data=analyzer.units
        )
        special_props = [
            ("ignores_melee_armor", "Unit ignores melee armor"),
            ("ignores_pierce_armor", "Unit ignores pierce armor"),
            ("trample_percent", "Trample damage percent"),
            ("trample_radius", "Trample damage radius"),
            ("trample_flat_damage", "Flat trample damage"),
            ("bonus_damage_reduction", "Reduces bonus damage taken"),
            ("splash_radius", "Splash damage radius"),
            ("splash_on_hit_radius", "Splash on hit radius"),
            ("dodge_shield_max", "Dodge shield charges"),
            ("dodge_shield_recharge", "Dodge shield recharge time"),
            ("bleed_dps", "Bleed damage per second"),
            ("bleed_duration", "Bleed duration"),
            ("block_first_melee", "Blocks first melee hit"),
            ("attack_bonus_per_kill", "Attack bonus per kill"),
            ("charge_attack_range", "Charge attack range"),
            ("charge_ignores_armor", "Charge attack ignores armor"),
            ("hp_transform_threshold", "HP threshold for form change"),
            ("dismount_unit_id", "Dismounts to unit on death"),
        ]
        for prop_name, desc in special_props:
            val = combat_props.get(prop_name, 0)
            if val and val != 0:
                # Determine source
                source = "extracted_data"
                base_slug = unit_slug
                for bs in UNIQUE_COMBAT_PROPERTIES:
                    if unit_slug == bs or unit_slug.startswith(bs + "_"):
                        if prop_name in UNIQUE_COMBAT_PROPERTIES[bs]:
                            source = "UNIQUE_COMBAT_PROPERTIES"
                        base_slug = bs
                        break
                civ_key = (civ_name, unit_slug)
                if (
                    civ_key in CIV_COMBAT_PROPERTIES
                    and prop_name in CIV_COMBAT_PROPERTIES[civ_key]
                ):
                    source = "CIV_COMBAT_PROPERTIES"
                else:
                    # For unique units with civ suffix, try base slug matching
                    for civ, civ_base_slug in CIV_COMBAT_PROPERTIES:
                        if civ == civ_name and unit_slug.startswith(
                            civ_base_slug + "_"
                        ):
                            if prop_name in CIV_COMBAT_PROPERTIES[(civ, civ_base_slug)]:
                                source = "CIV_COMBAT_PROPERTIES"
                            break
                cursor.execute(
                    "INSERT INTO ref_special_effects (ref_unit_id, property_name, property_value, source, description) VALUES (?,?,?,?,?)",
                    (ref_unit_id, prop_name, str(val), source, desc),
                )

        # Projectile data
        extra_proj = combat_props.get("extra_projectiles", 0)
        proj_speed = combat_props.get("projectile_speed", 0)
        splash = combat_props.get("splash_radius", 0)
        is_siege = combat_props.get("is_siege_projectile", 0)
        total_proj = unit_data.get("total_projectiles", 1)

        if total_proj > 0 or proj_speed > 0:
            cursor.execute(
                "INSERT INTO ref_projectiles (ref_unit_id, projectile_type, projectile_count, projectile_speed, blast_radius, is_siege_projectile) VALUES (?,?,?,?,?,?)",
                (ref_unit_id, "primary", int(total_proj), proj_speed, splash, is_siege),
            )
        if extra_proj > 0:
            extra_atk_json = combat_props.get("extra_projectile_attacks_json")
            cursor.execute(
                "INSERT INTO ref_projectiles (ref_unit_id, projectile_type, projectile_count, projectile_speed, attacks_json, blast_radius, is_siege_projectile) VALUES (?,?,?,?,?,?,?)",
                (
                    ref_unit_id,
                    "extra",
                    int(extra_proj),
                    proj_speed,
                    extra_atk_json,
                    splash,
                    is_siege,
                ),
            )

        # Charge projectile data (Fire Lancer, Fire Archer, etc.)
        charge_proj_count = combat_props.get("charge_projectile_count", 0)
        charge_proj_atk_json = combat_props.get("charge_projectile_attacks_json")
        charge_proj_speed = combat_props.get("charge_projectile_speed", 0)
        if charge_proj_count > 0 and charge_proj_atk_json:
            cursor.execute(
                "INSERT INTO ref_projectiles (ref_unit_id, projectile_type, projectile_count, projectile_speed, attacks_json, blast_radius, is_siege_projectile) VALUES (?,?,?,?,?,?,?)",
                (
                    ref_unit_id,
                    "charge",
                    int(charge_proj_count),
                    charge_proj_speed,
                    charge_proj_atk_json,
                    0,
                    0,
                ),
            )

        return ref_unit_id

    # Process all units for all 13 civs
    print("\nGenerating reference database...")
    for civ_name in ORIGINAL_13_CIVS:
        print(f"  {civ_name}...")
        disabled_techs = analyzer.get_disabled_techs(civ_name)

        # Castle Age units
        for slug, config in CASTLE_UNITS.items():
            result = analyzer.calculate_unit_stats_for_civ(civ_name, config, CASTLE_AGE)
            if not result["has_unit"]:
                continue
            final_unit_id = result.get("unit_id", config["base_id"])
            unit_data = analyzer.get_unit(final_unit_id)
            if not unit_data:
                continue
            process_unit_audited(
                civ_name,
                final_unit_id,
                config["unit_class"],
                result["unit_name"],
                slug,
                "standard",
                "Castle",
                CASTLE_AGE,
                unit_data,
            )

        # Imperial Age units
        for slug, config in IMPERIAL_UNITS.items():
            result = analyzer.calculate_unit_stats_for_civ(
                civ_name, config, IMPERIAL_AGE
            )
            if not result["has_unit"]:
                continue
            final_unit_id = result.get("unit_id", config["base_id"])
            unit_data = analyzer.get_unit(final_unit_id)
            if not unit_data:
                continue
            process_unit_audited(
                civ_name,
                final_unit_id,
                config["unit_class"],
                result["unit_name"],
                slug,
                "standard",
                "Imperial",
                IMPERIAL_AGE,
                unit_data,
            )

        # Unique units
        if civ_name in UNIQUE_UNITS:
            for uu_config in UNIQUE_UNITS[civ_name]:
                # Castle Age (base version)
                base_id = uu_config["base_id"]
                unit_data = analyzer.get_unit(base_id)
                if unit_data:
                    slug = (
                        uu_config["display_name"]
                        .lower()
                        .replace(" ", "_")
                        .replace("-", "_")
                    )
                    process_unit_audited(
                        civ_name,
                        base_id,
                        uu_config["unit_class"],
                        uu_config["display_name"],
                        f"{slug}_{civ_name.lower()}",
                        "unique",
                        "Castle",
                        CASTLE_AGE,
                        unit_data,
                    )

                # Imperial Age (elite version)
                elite_id = uu_config.get("elite_id")
                if elite_id:
                    elite_data = analyzer.get_unit(elite_id)
                    if elite_data:
                        elite_name = uu_config.get(
                            "elite_name", f"Elite {uu_config['display_name']}"
                        )
                        elite_slug = f"elite_{slug}_{civ_name.lower()}"
                        process_unit_audited(
                            civ_name,
                            elite_id,
                            uu_config["unit_class"],
                            elite_name,
                            elite_slug,
                            "unique",
                            "Imperial",
                            IMPERIAL_AGE,
                            elite_data,
                        )

    conn.commit()

    # Count records
    cursor.execute("SELECT COUNT(*) FROM ref_units")
    unit_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ref_techs_applied")
    tech_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ref_stat_chain")
    chain_count = cursor.fetchone()[0]

    print(f"\n  Reference DB created at: {ref_db_path}")
    print(f"  Units: {unit_count}")
    print(f"  Techs applied: {tech_count}")
    print(f"  Stat chain steps: {chain_count}")

    # Print detailed display
    print_reference_display(conn, armor_class_names)

    conn.close()


def print_reference_display(conn, armor_class_names):
    """Print the detailed per-stat breakdown for all units."""
    cursor = conn.cursor()

    for civ_name in ORIGINAL_13_CIVS:
        print(f"\n{'=' * 80}")
        print(f"=== {civ_name} ===")
        print(f"{'=' * 80}")

        cursor.execute(
            "SELECT * FROM ref_units WHERE civ_name=? ORDER BY age, unit_type, unit_name",
            (civ_name,),
        )
        columns = [desc[0] for desc in cursor.description]
        units = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for unit in units:
            ref_id = unit["id"]

            # Get techs applied for this unit
            cursor.execute(
                """SELECT tech_name, tech_type, building, effect_description, age_available
                   FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id""",
                (ref_id,),
            )
            techs = cursor.fetchall()

            # Get stat chain
            cursor.execute(
                """SELECT tech_name, tech_type, hp, attack, melee_armor, pierce_armor,
                          speed, range_val, reload_time, accuracy, los, train_time,
                          cost_food, cost_wood, cost_gold, attacks_json, armors_json
                   FROM ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order""",
                (ref_id,),
            )
            chain = cursor.fetchall()

            # Get special effects
            cursor.execute(
                "SELECT property_name, property_value, source FROM ref_special_effects WHERE ref_unit_id=?",
                (ref_id,),
            )
            specials = cursor.fetchall()

            # Get projectiles
            cursor.execute(
                "SELECT projectile_type, projectile_count, projectile_speed, blast_radius, is_siege_projectile, attacks_json FROM ref_projectiles WHERE ref_unit_id=?",
                (ref_id,),
            )
            projectiles = cursor.fetchall()

            # Determine main attack class
            main_atk_class = 3 if unit["is_ranged"] else 4

            # Build upgrade descriptions per stat
            stat_upgrades = _build_stat_upgrade_descriptions(
                chain, techs, armor_class_names, main_atk_class
            )

            print(
                f"\nUnit: {unit['unit_name']} | Age: {unit['age']} | Class: {unit.get('unit_class_name', '')} ({unit.get('unit_class', '')})"
            )

            # HP
            _print_stat_line(
                "HP", unit["base_hp"], unit["final_hp"], stat_upgrades.get("hp", [])
            )

            # Attack (main class) - use attacks_json for correct ranged/melee tracking
            base_attacks = (
                json.loads(unit["base_attacks_json"])
                if unit["base_attacks_json"]
                else {}
            )
            final_attacks = (
                json.loads(unit["final_attacks_json"])
                if unit["final_attacks_json"]
                else {}
            )
            base_main_atk = base_attacks.get(str(main_atk_class), 0)
            final_main_atk = final_attacks.get(str(main_atk_class), 0)
            main_cls_name = armor_class_names.get(
                main_atk_class, f"class {main_atk_class}"
            )
            atk_label = f"Attack (class {main_atk_class}: {main_cls_name})"
            _print_stat_line(
                atk_label,
                base_main_atk,
                final_main_atk,
                stat_upgrades.get("attack", []),
            )

            # Bonus attack classes (base_attacks/final_attacks already parsed above)
            bonus_atk_parts = []
            for cls_id_str in sorted(
                set(list(base_attacks.keys()) + list(final_attacks.keys()))
            ):
                cls_id = int(cls_id_str)
                if cls_id == main_atk_class:
                    continue  # Skip main attack class
                cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
                base_val = base_attacks.get(
                    cls_id_str, base_attacks.get(str(cls_id), 0)
                )
                final_val = final_attacks.get(
                    cls_id_str, final_attacks.get(str(cls_id), 0)
                )
                if base_val != 0 or final_val != 0:
                    bonus_atk_parts.append(
                        f"class {cls_id} {cls_name}: base={base_val}, final={final_val}"
                    )
            if bonus_atk_parts:
                print(f"  Bonus Atk: {' | '.join(bonus_atk_parts)}")

            # MA
            _print_stat_line(
                "MA",
                unit["base_melee_armor"],
                unit["final_melee_armor"],
                stat_upgrades.get("melee_armor", []),
            )

            # PA
            _print_stat_line(
                "PA",
                unit["base_pierce_armor"],
                unit["final_pierce_armor"],
                stat_upgrades.get("pierce_armor", []),
            )

            # All armor classes
            base_armors = (
                json.loads(unit["base_armors_json"]) if unit["base_armors_json"] else {}
            )
            final_armors = (
                json.loads(unit["final_armors_json"])
                if unit["final_armors_json"]
                else {}
            )
            armor_parts = []
            for cls_id_str in sorted(final_armors.keys(), key=lambda x: int(x)):
                cls_id = int(cls_id_str)
                cls_name = armor_class_names.get(cls_id, f"class {cls_id}")
                val = final_armors[cls_id_str]
                armor_parts.append(f"class {cls_id} {cls_name}: {val}")
            if armor_parts:
                print(f"  All Armor: {' | '.join(armor_parts)}")

            # Range
            _print_stat_line(
                "Range",
                unit["base_range"],
                unit["final_range"],
                stat_upgrades.get("range", []),
            )

            # Speed
            _print_stat_line(
                "Speed",
                unit["base_speed"],
                unit["final_speed"],
                stat_upgrades.get("speed", []),
            )

            # Reload
            _print_stat_line(
                "Reload",
                unit["base_reload_time"],
                unit["final_reload_time"],
                stat_upgrades.get("reload_time", []),
            )

            # Accuracy
            _print_stat_line(
                "Accuracy",
                unit["base_accuracy"],
                unit["final_accuracy"],
                stat_upgrades.get("accuracy", []),
            )

            # LOS
            _print_stat_line(
                "LOS", unit["base_los"], unit["final_los"], stat_upgrades.get("los", [])
            )

            # Attack delay (not upgradeable)
            print(f"  Atk Delay: {unit.get('base_attack_delay', 0)}")

            # Projectile
            for p in projectiles:
                p_type, p_count, p_speed, p_blast, p_siege, p_atk_json = p
                parts = [f"type={p_type}", f"count={p_count}", f"speed={p_speed}"]
                if p_blast:
                    parts.append(f"blast={p_blast}")
                if p_siege:
                    parts.append("siege=yes")
                if p_atk_json:
                    # Show attack classes with names
                    atk_dict = json.loads(p_atk_json)
                    atk_parts = []
                    for cls_id_str, amount in sorted(
                        atk_dict.items(), key=lambda x: x[1], reverse=True
                    ):
                        cls_name = armor_class_names.get(
                            int(cls_id_str), f"class {cls_id_str}"
                        )
                        atk_parts.append(f"{cls_name}={amount}")
                    parts.append(f"attacks=[{', '.join(atk_parts)}]")
                print(f"  Projectile: {', '.join(parts)}")

            # Train time
            _print_stat_line(
                "Train Time",
                unit["base_train_time"],
                unit["final_train_time"],
                stat_upgrades.get("train_time", []),
            )

            # Cost
            base_cost = _format_cost(
                unit["base_cost_food"], unit["base_cost_wood"], unit["base_cost_gold"]
            )
            final_cost = _format_cost(
                unit.get("final_cost_food", unit["base_cost_food"]),
                unit.get("final_cost_wood", unit["base_cost_wood"]),
                unit.get("final_cost_gold", unit["base_cost_gold"]),
            )
            cost_upgrades = stat_upgrades.get("cost", [])
            if cost_upgrades:
                print(
                    f"  Cost:      Base={base_cost} | Upgrades: {', '.join(cost_upgrades)} | Final={final_cost}"
                )
            else:
                print(
                    f"  Cost:      Base={base_cost} | Upgrades: (none) | Final={final_cost}"
                )

            # Special effects
            if specials:
                special_strs = [f"{name}={val} ({src})" for name, val, src in specials]
                print(f"  Special:   {', '.join(special_strs)}")

            # Unique tech effects (from techs_applied with type unique_tech)
            ut_list = [t for t in techs if t[1] == "unique_tech"]
            if ut_list:
                ut_strs = [f"{t[0]} ({t[3]})" for t in ut_list]
                print(f"  Unique Techs: {'; '.join(ut_strs)}")


def _build_stat_upgrade_descriptions(chain, techs, armor_class_names, main_atk_class=4):
    """Build per-stat upgrade descriptions by comparing consecutive chain entries.

    main_atk_class: 3 for ranged (Base Pierce), 4 for melee (Base Melee).
    """
    upgrades = {}  # stat_name -> [change_str, ...]

    if len(chain) < 2:
        return upgrades

    # chain columns: tech_name, tech_type, hp, attack, ma, pa, speed, range, reload,
    #                accuracy, los, train_time, cost_food, cost_wood, cost_gold, attacks_json, armors_json
    stat_indices = {
        "hp": 2,
        "melee_armor": 4,
        "pierce_armor": 5,
        "speed": 6,
        "range": 7,
        "reload_time": 8,
        "accuracy": 9,
        "los": 10,
        "train_time": 11,
    }

    # Match chain entries to techs for building info
    tech_buildings = {}
    for t in techs:
        tech_buildings[t[0]] = t[2]  # tech_name -> building

    for i in range(1, len(chain)):
        prev = chain[i - 1]
        curr = chain[i]
        tech_name = curr[0]
        tech_type = curr[1]
        building = tech_buildings.get(tech_name, "N/A")

        # Track main attack class from attacks_json (column index 15)
        prev_attacks = json.loads(prev[15]) if prev[15] else {}
        curr_attacks = json.loads(curr[15]) if curr[15] else {}
        prev_main_atk = prev_attacks.get(
            str(main_atk_class), prev_attacks.get(main_atk_class, 0)
        )
        curr_main_atk = curr_attacks.get(
            str(main_atk_class), curr_attacks.get(main_atk_class, 0)
        )
        if abs(curr_main_atk - prev_main_atk) > 0.001:
            diff = curr_main_atk - prev_main_atk
            sign = "+" if diff > 0 else ""
            change = f"{sign}{diff:.3g} {building} ({tech_name})"
            upgrades.setdefault("attack", []).append(change)

        for stat_name, idx in stat_indices.items():
            old_val = prev[idx] or 0
            new_val = curr[idx] or 0
            if abs(new_val - old_val) > 0.001:
                diff = new_val - old_val
                # Multiplicative check
                if old_val != 0 and stat_name in (
                    "reload_time",
                    "speed",
                    "hp",
                    "train_time",
                ):
                    ratio = new_val / old_val
                    if (
                        abs(ratio - round(ratio)) > 0.001
                        and abs(diff - round(diff)) > 0.01
                    ):
                        change = f"x{ratio:.3g} {building} ({tech_name})"
                        upgrades.setdefault(stat_name, []).append(change)
                        continue

                sign = "+" if diff > 0 else ""
                change = f"{sign}{diff:.3g} {building} ({tech_name})"
                upgrades.setdefault(stat_name, []).append(change)

        # Cost changes
        cost_changed = False
        cost_parts = []
        for ci, cname in [(12, "food"), (13, "wood"), (14, "gold")]:
            old_val = prev[ci] or 0
            new_val = curr[ci] or 0
            if abs(new_val - old_val) > 0.01:
                cost_changed = True
                diff = new_val - old_val
                if old_val != 0:
                    ratio = new_val / old_val
                    if abs(ratio - round(ratio)) > 0.001:
                        cost_parts.append(f"x{ratio:.3g} {cname}")
                        continue
                sign = "+" if diff > 0 else ""
                cost_parts.append(f"{sign}{diff:.3g} {cname}")
        if cost_changed:
            change = f"{', '.join(cost_parts)} {building} ({tech_name})"
            upgrades.setdefault("cost", []).append(change)

    return upgrades


def _print_stat_line(label, base_val, final_val, upgrade_list):
    """Print a single stat line in Base | Upgrades | Final format."""
    label_padded = f"{label}:".ljust(12)
    if base_val is None:
        base_val = 0
    if final_val is None:
        final_val = base_val

    # Format values
    if isinstance(base_val, float) and base_val == int(base_val):
        base_str = str(int(base_val))
    else:
        base_str = f"{base_val:.3g}" if isinstance(base_val, float) else str(base_val)

    if isinstance(final_val, float) and final_val == int(final_val):
        final_str = str(int(final_val))
    else:
        final_str = (
            f"{final_val:.3g}" if isinstance(final_val, float) else str(final_val)
        )

    if upgrade_list:
        upgrades_str = ", ".join(upgrade_list)
        print(
            f"  {label_padded} Base={base_str} | Upgrades: {upgrades_str} | Final={final_str}"
        )
    else:
        print(
            f"  {label_padded} Base={base_str} | Upgrades: (none) | Final={final_str}"
        )


def _format_cost(food, wood, gold):
    """Format cost as string like '25W 45G'."""
    parts = []
    if food and food > 0:
        parts.append(f"{int(food)}F")
    if wood and wood > 0:
        parts.append(f"{int(wood)}W")
    if gold and gold > 0:
        parts.append(f"{int(gold)}G")
    return " ".join(parts) if parts else "Free"


def main():
    print("AoE2 Unit Database Generator")
    print("=" * 60)
    print("Reading data directly from JSON files...")

    # Load analyzer
    analyzer = UnitAnalyzer()
    print(f"  Loaded {len(analyzer.units)} units")
    print(f"  Loaded {len(analyzer.civs)} civilizations")
    print(f"  Loaded {len(analyzer.techs)} technologies")

    # Create database
    print("\nCreating database...")
    conn = create_database()

    # Populate database
    print("\nPopulating database...")
    populate_database(conn, analyzer)

    # Print stats
    print_stats(conn)

    conn.close()
    print("\nDatabase generation complete!")

    # Generate reference/audit database
    generate_reference_database(analyzer)


if __name__ == "__main__":
    main()
