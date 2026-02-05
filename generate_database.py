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

# =============================================================================
# SIMULATION CONFIGURATION
# =============================================================================
# Lithuanian relic count for cavalry attack bonus (0-4)
# Each relic gives +1 attack to Knights, Cavaliers, Paladins, and Leitis
LITHUANIAN_RELIC_COUNT = 2

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
        """Calculate total upgrade cost for relevant techs."""
        total = 0
        for tech_id in relevant_techs:
            if tech_id in disabled_techs:
                continue
            tech_data = self.techs.get(tech_id, {})
            base_cost = tech_data.get("cost", {})
            total += sum(base_cost.values())
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
            base_name = (
                base_unit.get("name", alternate["display_name"])
                if base_unit
                else alternate["display_name"]
            )
            upgrades = alternate.get("upgrades", [])
        else:
            base_id = unit_config["base_id"]
            base_unit = self.get_unit(base_id)
            base_name = (
                base_unit.get("name", unit_config["display_name"])
                if base_unit
                else unit_config["display_name"]
            )
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

                if stats:
                    # Convert attacks and armors to JSON
                    attacks_json = json.dumps(stats.attacks) if stats.attacks else None
                    armors_json = json.dumps(stats.armors) if stats.armors else None

                    cursor.execute(
                        """
                        INSERT INTO unit_stats (
                            civ_id, unit_id, unit_name, hp, attack, attack_range,
                            attack_speed, melee_armor, pierce_armor, movement_speed,
                            cost_food, cost_wood, cost_gold, creation_time, upgrade_cost,
                            civ_bonuses, has_unit, attacks_json, armors_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            civ_id_map[civ_name],
                            db_unit_id,
                            result["unit_name"],
                            int(stats.hp),
                            int(stats.attack),
                            float(stats.range) if stats.range > 0 else None,
                            round(stats.attack_rate(), 3),
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
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO unit_stats (
                            civ_id, unit_id, unit_name, hp, attack, attack_range,
                            attack_speed, melee_armor, pierce_armor, movement_speed,
                            cost_food, cost_wood, cost_gold, creation_time, upgrade_cost,
                            civ_bonuses, has_unit, attacks_json, armors_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            has_unit,
                            None,
                            None,
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

            for db_unit_id, result, unit_name in units_to_process:
                stats = result["stats"]
                has_unit = 1 if result["has_unit"] else 0
                bonuses = result.get("applied_bonuses", [])
                bonuses_str = (
                    ", ".join(b.replace("C-Bonus, ", "") for b in bonuses)
                    if bonuses
                    else None
                )

                if stats:
                    attacks_json = json.dumps(stats.attacks) if stats.attacks else None
                    armors_json = json.dumps(stats.armors) if stats.armors else None

                    cursor.execute(
                        """
                        INSERT INTO unit_stats (
                            civ_id, unit_id, unit_name, hp, attack, attack_range,
                            attack_speed, melee_armor, pierce_armor, movement_speed,
                            cost_food, cost_wood, cost_gold, creation_time, upgrade_cost,
                            civ_bonuses, has_unit, attacks_json, armors_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            db_civ_id,
                            db_unit_id,
                            unit_name,
                            int(stats.hp),
                            int(stats.attack),
                            float(stats.range) if stats.range > 0 else None,
                            round(stats.attack_rate(), 3),
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


if __name__ == "__main__":
    main()
