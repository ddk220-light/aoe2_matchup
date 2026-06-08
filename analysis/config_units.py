"""Unit definitions, stat overrides, and building mappings for AoE2 analysis.

Contains all unit line definitions (FEUDAL_UNITS, CASTLE_UNITS, IMPERIAL_UNITS,
UNIQUE_UNITS), base stat overrides, building-related mappings, and the derived
UNITS_BY_AGE / AGE_NAMES / _PREVIOUS_AGE_NAMES lookups.

Imports age constants from config_constants so this module is self-contained.
"""

from .config_constants import FEUDAL_AGE, CASTLE_AGE, IMPERIAL_AGE

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

# Civ team bonuses that multiply building work_rate (applied to self)
# Format: civ_name → {building_id: multiplier, ...}
CIV_TEAM_BONUS_WORK_RATE = {
    "Britons": {87: 1.10, 10: 1.10, 14: 1.10},  # Archery Ranges work 10% faster
    "Goths": {12: 1.20, 498: 1.20, 132: 1.20, 20: 1.20},  # Barracks work 20% faster
    "Celts": {49: 1.20, 150: 1.20},  # Siege Workshops work 20% faster
}

# Civ team bonuses that add attack vs armor class (applied to self)
# Format: civ_name → [(unit_id, attack_class, amount), ...]
# unit_id=-1 means class-based (uses class_id from command)
CIV_TEAM_BONUS_ATTACK = {
    # Knights +2 attack vs Archers (class 15)
    "Persians": [
        (38, 15, 2),  # Knight
        (283, 15, 2),  # Cavalier
        (569, 15, 2),  # Paladin
        (1813, 15, 2),  # Savar
    ],
    # Foot archers +3 attack vs Standard Buildings (class 21)
    "Saracens": [
        (-1, 21, 3, 0),  # class_id=0 (Archer class), -1 = all units of class
    ],
}

# Unique units that can also be created in Barracks (after specific tech)
# Format: (civ_name, base_slug) → barracks_building_id
UNIQUE_UNITS_IN_BARRACKS = {
    ("Goths", "huskarl"): 12,  # After Anarchy tech
    ("Goths", "elite_huskarl"): 12,
}

# Base stat overrides for units where the dat file has incorrect values.
# Keyed by unit ID. Applied after get_base_stats() before tech calculations.
UNIT_STAT_OVERRIDES = {
    # Elite Woad Raider (534): dat file has speed=1.17 (same as base), but elite should
    # be faster. 1.4 (wiki final speed) / 1.15 (Celts infantry speed bonus) ≈ 1.217
    534: {"speed": 1.2174},  # Elite Woad Raider
    # War Chariot (2150): dat extracts as melee, but is actually ranged siege unit
    # with scorpion-like pass-through bolts. Override base stats to match game data.
    2150: {  # War Chariot
        "hp": 65,
        "attack": 8,
        "range": 6,
        "reload_time": 7.5,
        "accuracy": 100,
        "melee_armor": 0,
        "pierce_armor": 5,
        "speed": 0.9,
        "cost_food": 65,
        "cost_wood": 0,
        "cost_gold": 90,
        "los": 8,
        "attacks": {3: 8, 1: 2},  # Pierce 8, +2 buildings
    },
    # Fire Archer (1968) / Elite Fire Archer (1970): dat exposes the
    # anti-BUILDING primary attack (range 9 / 10). For unit-vs-unit combat
    # the in-game logic auto-switches to the anti-UNIT charge attack
    # (range 5 / 6, 3 projectiles, 0.25 blast). extra_projectiles=2 is
    # already extracted from the secondary mode; only range needs override.
    # Tech bonuses (Fletching/Bodkin/Bracer) then yield 7 castle / 9 imperial
    # post-tech, matching the Chu Ko Nu pattern.
    # Sources: Fandom Fire_Archer page, SiegeEngineers data.json (charge_type=6).
    1968: {"range": 5},
    1970: {"range": 6},
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
    "champi_warrior": {
        "base_id": 2552,
        "display_name": "Champi Warrior",
        "unit_class": 6,
        "availability_tech": 1351,  # Champi Warrior (make avail)
        "upgrades": [],
    },
    "light_cav": {
        "base_id": 448,  # Scout Cavalry (upgrades to Light Cav)
        "display_name": "Light Cavalry",
        "unit_class": 12,
        "availability_tech": 204,  # Scout (make avail) - Aztecs/Mayans don't have this
        "upgrades": [
            (254, 546, "Light Cavalry"),  # Light Cavalry upgrade
        ],
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
            (100, 24, "Crossbowman"),  # Crossbow tech (researched at Archery Range)
        ],
    },
    "elite_skirm": {
        "base_id": 7,  # Skirmisher
        "display_name": "Elite Skirmisher",
        "unit_class": 0,
        "availability_tech": None,
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
            "unit_class": 12,  # Cavalry/elephant class — gets blacksmith barding, Bloodlines, Husbandry
        },
    },
    "mangonel": {
        "base_id": 280,
        "display_name": "Mangonel",
        "unit_class": 13,
        "availability_tech": None,
        "upgrades": [],
        # Rocket Cart replaces Mangonel for Chinese/Koreans
        "civ_upgrades": {
            "Chinese": [(979, 1904, "Rocket Cart")],
            "Koreans": [(979, 1904, "Rocket Cart")],
            "Jurchens": [(979, 1904, "Rocket Cart")],
            "Khitans": [(979, 1904, "Rocket Cart")],
        },
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
    "slinger": {
        "base_id": 185,
        "display_name": "Slinger",
        "unit_class": 0,  # Archer class (Archery Range)
        "availability_tech": 528,  # Slinger (make avail) - Incas only
        "upgrades": [],
    },
    "genitour": {
        "base_id": 1010,
        "display_name": "Genitour",
        "unit_class": 36,  # Cavalry Archer
        "availability_tech": 427,  # Genitour (make avail)
        "upgrades": [],
        "civ_only": [
            "Berbers"
        ],  # Team unit: all civs can train with Berber ally, but restrict to owner
    },
}

IMPERIAL_UNITS = {
    "champion": {
        "base_id": 75,  # Man-at-Arms
        "display_name": "Champion",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [
            (207, 77, "Long Swordsman"),
            (217, 473, "Two-Handed Swordsman"),
            (264, 567, "Champion"),
        ],
        # Legionary replaces Champion for Romans
        "civ_upgrades": {
            "Romans": [
                (207, 77, "Long Swordsman"),
                (217, 473, "Two-Handed Swordsman"),
                (885, 1793, "Legionary"),
            ],
        },
    },
    "halberdier": {
        "base_id": 93,  # Spearman
        "display_name": "Halberdier",
        "unit_class": 6,
        "availability_tech": None,
        "upgrades": [
            (197, 358, "Pikeman"),
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
    "elite_champi_warrior": {
        "base_id": 2552,
        "display_name": "Elite Champi Warrior",
        "unit_class": 6,
        "availability_tech": 1351,
        "upgrades": [
            (1352, 2554, "Elite Champi Warrior"),
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
        "base_id": 448,  # Scout Cavalry (upgrades through Light Cav → Hussar)
        "display_name": "Hussar",
        "unit_class": 12,
        "availability_tech": 204,  # Scout (make avail) - Aztecs/Mayans don't have this
        "upgrades": [
            (254, 546, "Light Cavalry"),
            (428, 441, "Hussar"),
        ],
        # Winged Hussar replaces Hussar for Lithuanians and Poles
        "civ_upgrades": {
            "Lithuanians": [
                (254, 546, "Light Cavalry"),
                (786, 1707, "Winged Hussar"),
            ],
            "Poles": [
                (254, 546, "Light Cavalry"),
                (786, 1707, "Winged Hussar"),
            ],
        },
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
        "base_id": 4,  # Archer
        "display_name": "Arbalester",
        "unit_class": 0,
        "availability_tech": None,
        "upgrades": [
            (100, 24, "Crossbowman"),
            (237, 492, "Arbalester"),
        ],
    },
    "imp_elite_skirm": {
        "base_id": 7,  # Skirmisher
        "display_name": "Elite Skirmisher",
        "unit_class": 0,
        "availability_tech": None,
        "upgrades": [
            (98, 6, "Elite Skirmisher"),
        ],
        # Imperial Skirmisher replaces Elite Skirmisher for Vietnamese (+ allies)
        "civ_upgrades": {
            "Vietnamese": [
                (98, 6, "Elite Skirmisher"),
                (655, 1155, "Imperial Skirmisher"),
            ],
        },
    },
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
            "unit_class": 12,  # Cavalry/elephant class — gets blacksmith barding, Bloodlines, Husbandry
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
        # Heavy Rocket Cart replaces Onager/Siege Onager for Chinese/Koreans
        "civ_upgrades": {
            "Chinese": [
                (979, 1904, "Rocket Cart"),
                (980, 1907, "Heavy Rocket Cart"),
            ],
            "Koreans": [
                (979, 1904, "Rocket Cart"),
                (980, 1907, "Heavy Rocket Cart"),
            ],
            "Jurchens": [
                (979, 1904, "Rocket Cart"),
                (980, 1907, "Heavy Rocket Cart"),
            ],
            "Khitans": [
                (979, 1904, "Rocket Cart"),
                (980, 1907, "Heavy Rocket Cart"),
            ],
        },
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
        # Houfnice (Bohemian Imperial UT, tech 787) upgrades the Bombard Cannon
        # in place to unit 1709 "Houfnice" (+10 HP, +10 attack, +50 vs buildings,
        # +1 pierce armor). Same UPGRADE_UNIT pattern as Persian Savar.
        "civ_upgrades": {
            "Bohemians": [
                (787, 1709, "Houfnice"),
            ],
        },
    },
    "trebuchet": {
        "base_id": 42,
        "display_name": "Trebuchet",
        "unit_class": 54,
        "availability_tech": None,
        "upgrades": [],
    },
    "traction_trebuchet": {
        "base_id": 1942,
        "display_name": "Traction Trebuchet",
        "unit_class": 13,
        "availability_tech": 1025,  # Shadow tech, auto-researches at Imperial Age
        "upgrades": [],
        "civ_only": ["Shu", "Wu", "Wei"],
    },
    "condottiero": {
        "base_id": 882,
        "display_name": "Condottiero",
        "unit_class": 6,  # Infantry
        "availability_tech": 522,  # Condottiero (make avail)
        "upgrades": [],
        "civ_only": [
            "Italians"
        ],  # Team unit: all civs can train with Italian ally, but restrict to owner for now
    },
    "imp_slinger": {
        "base_id": 185,
        "display_name": "Slinger",
        "unit_class": 0,  # Archer class
        "availability_tech": 528,  # Slinger (make avail) - Incas only
        "upgrades": [],
    },
    "elite_genitour": {
        "base_id": 1010,
        "display_name": "Elite Genitour",
        "unit_class": 36,  # Cavalry Archer
        "availability_tech": 427,  # Genitour (make avail)
        "upgrades": [
            (430, 1012, "Elite Genitour"),
        ],
        "civ_only": [
            "Berbers"
        ],  # Team unit: all civs can train with Berber ally, but restrict to owner
    },
    "flemish_militia": {
        "base_id": 1699,
        "display_name": "Flemish Militia",
        "unit_class": 6,  # Infantry
        "availability_tech": 773,  # Flemish Militia (make avail)
        "upgrades": [],
        "civ_only": ["Burgundians"],
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
# NAVAL UNIT CONFIGURATIONS
# =============================================================================
# One config per naval line. Both Castle and Imperial runs use the same config;
# calculate_unit_stats_for_civ() applies only techs available by the given max_age.
#
# Tech 34 (War Galley) upgrades Galley→War Galley, Fire Galley→Fire Ship, AND
# Hulk→War Hulk simultaneously — all three share that Castle-age tier gate.
NAVAL_LINE_CONFIGS = {
    "galleon": {
        "base_id": 539,           # Galley (always available)
        "display_name": "Galley",
        "unit_class": 22,         # Ship class
        "availability_tech": None,
        "upgrades": [
            (34, 21, "War Galley"),    # Castle Age
            (911, 442, "Galleon"),     # Imperial Age
        ],
    },
    "fire": {
        "base_id": 1103,          # Fire Galley (always available)
        "display_name": "Fire Galley",
        "unit_class": 22,
        "availability_tech": None,
        "upgrades": [
            (34, 529, "Fire Ship"),        # Castle Age
            (246, 532, "Fast Fire Ship"),  # Imperial Age
        ],
    },
    "hulk": {
        "base_id": 2626,          # Hulk (requires tech 903)
        "display_name": "Hulk",
        "unit_class": 22,
        "availability_tech": 903,
        "upgrades": [
            (34, 2627, "War Hulk"),    # Castle Age
            (904, 2628, "Carrack"),    # Imperial Age
        ],
    },
    "demo": {
        "base_id": 1104,          # Demo Raft (always available)
        "display_name": "Demo Raft",
        "unit_class": 22,
        "availability_tech": None,
        "upgrades": [
            (905, 527, "Demo Ship"),          # Castle Age
            (244, 528, "Heavy Demo Ship"),    # Imperial Age
        ],
    },
    "cannon_galleon": {
        "base_id": 420,           # Cannon Galleon (requires tech 37)
        "display_name": "Cannon Galleon",
        "unit_class": 22,
        "availability_tech": 37,
        "upgrades": [
            (376, 691, "Elite Cannon Galleon"),  # Imperial Age
        ],
    },
}

# Unique naval units keyed by civ. Structure mirrors UNIQUE_UNITS.
# "line" field identifies which standard line slot this unit replaces.
NAVAL_UNIQUE_UNITS = {
    "Vikings": [
        {
            "base_id": 250,
            "display_name": "Longboat",
            "unit_class": 22,
            "availability_tech": 272,
            "elite_tech": 372,
            "elite_id": 533,
            "elite_name": "Elite Longboat",
            "line": "galleon",
        }
    ],
    "Koreans": [
        {
            "base_id": 831,
            "display_name": "Turtle Ship",
            "unit_class": 22,
            "availability_tech": 447,
            "elite_tech": 448,
            "elite_id": 832,
            "elite_name": "Elite Turtle Ship",
            "line": "hulk",
        }
    ],
    "Portuguese": [
        {
            "base_id": 1004,
            "display_name": "Caravel",
            "unit_class": 22,
            "availability_tech": 596,
            "elite_tech": 597,
            "elite_id": 1006,
            "elite_name": "Elite Caravel",
            "line": "galleon",
        }
    ],
    "Dravidians": [
        {
            "base_id": 1750,
            "display_name": "Thirisadai",
            "unit_class": 22,
            "availability_tech": 841,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "galleon",
        }
    ],
    "Berbers": [
        {
            "base_id": 1631,
            "display_name": "Xebec",
            "unit_class": 22,
            "availability_tech": None,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "galleon",
        }
    ],
    # Dromon (1795) is enabled for Byzantines, Romans, Armenians, Goths, Huns
    # (tech 886 = "Dromon make avail" is active for all five civs in the dat).
    "Byzantines": [
        {
            "base_id": 1795,
            "display_name": "Dromon",
            "unit_class": 22,
            "availability_tech": 886,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Romans": [
        {
            "base_id": 1795,
            "display_name": "Dromon",
            "unit_class": 22,
            "availability_tech": 886,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Armenians": [
        {
            "base_id": 1795,
            "display_name": "Dromon",
            "unit_class": 22,
            "availability_tech": 886,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Goths": [
        {
            "base_id": 1795,
            "display_name": "Dromon",
            "unit_class": 22,
            "availability_tech": 886,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Huns": [
        {
            "base_id": 1795,
            "display_name": "Dromon",
            "unit_class": 22,
            "availability_tech": 886,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    # Catapult Galleon (2633): South American civs — tech 913 enabled for all three
    "Mapuche": [
        {
            "base_id": 2633,
            "display_name": "Catapult Galleon",
            "unit_class": 22,
            "availability_tech": 913,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Tupi": [
        {
            "base_id": 2633,
            "display_name": "Catapult Galleon",
            "unit_class": 22,
            "availability_tech": 913,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Muisca": [
        {
            "base_id": 2633,
            "display_name": "Catapult Galleon",
            "unit_class": 22,
            "availability_tech": 913,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    # Lou Chuan (1948) — tech 1034 "Lou Chuan make avail" is active for
    # Chinese, Jurchens, and all Three Kingdoms civs (Wu/Shu/Wei).
    "Chinese": [
        {
            "base_id": 1948,
            "display_name": "Lou Chuan",
            "unit_class": 22,
            "availability_tech": 1034,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Jurchens": [
        {
            "base_id": 1948,
            "display_name": "Lou Chuan",
            "unit_class": 22,
            "availability_tech": 1034,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Wu": [
        {
            "base_id": 1948,
            "display_name": "Lou Chuan",
            "unit_class": 22,
            "availability_tech": 1034,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Shu": [
        {
            "base_id": 1948,
            "display_name": "Lou Chuan",
            "unit_class": 22,
            "availability_tech": 1034,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
    "Wei": [
        {
            "base_id": 1948,
            "display_name": "Lou Chuan",
            "unit_class": 22,
            "availability_tech": 1034,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
            "line": "cannon_galleon",
        }
    ],
}

# Build mapping: unit_id -> display name from previous age configs
# Used to get correct names when a config's upgrades don't apply
# (e.g., "Pikeman" config falls back to "Spearman" for Turks)
_PREVIOUS_AGE_NAMES = {}
for _cfg in FEUDAL_UNITS.values():
    if _cfg.get("upgrades"):
        _last = _cfg["upgrades"][-1]
        _PREVIOUS_AGE_NAMES[_last[1]] = _last[2]
    else:
        _PREVIOUS_AGE_NAMES[_cfg["base_id"]] = _cfg["display_name"]
for _cfg in CASTLE_UNITS.values():
    if _cfg.get("upgrades"):
        _last = _cfg["upgrades"][-1]
        _PREVIOUS_AGE_NAMES[_last[1]] = _last[2]
    else:
        _PREVIOUS_AGE_NAMES[_cfg["base_id"]] = _cfg["display_name"]

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
            # dat unit class is 23 ("Conquistador" class). Must NOT be 36
            # (Cavalry Archer): 36 wrongly grants Fletching/Bodkin/Bracer/
            # Chemistry/Thumb Ring, none of which the Conquistador receives.
            "unit_class": 23,
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
            "extra_unit_classes": [
                12
            ],  # Also gets cavalry techs (Husbandry, Bloodlines, etc.)
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
            # dat unit class is 23 ("Conquistador" class), same as Conquistador.
            # Must NOT be 36 (Cavalry Archer): 36 wrongly grants Fletching/
            # Bodkin/Bracer/Thumb Ring. Chemistry & Parthian Tactics still apply
            # because the dat targets the Arambai by unit id (1126/1128).
            "unit_class": 23,
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
            "availability_tech": 750,
            "elite_tech": 751,
            "elite_id": 1657,
            "elite_name": "Elite Coustillier",
        },
    ],
    "Sicilians": [
        {
            "base_id": 1658,
            "display_name": "Serjeant",
            "unit_class": 6,
            "availability_tech": 752,
            "elite_tech": 753,
            "elite_id": 1659,
            "elite_name": "Elite Serjeant",
        },
    ],
    "Poles": [
        {
            "base_id": 1701,
            "display_name": "Obuch",
            "unit_class": 6,
            "availability_tech": 778,
            "elite_tech": 779,
            "elite_id": 1703,
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
            # Melee form's true dat class is 12 (Cavalry). Must NOT be 36
            # (Cavalry Archer): 36 drops the melee blacksmith line (Forging/
            # Iron Casting/Blast Furnace) and adds inert Chemistry/Thumb Ring.
            # The Ranged form below is genuinely class 36 — leave it.
            "unit_class": 12,
            "availability_tech": 831,
            "elite_tech": 828,
            "elite_id": 1740,
            "elite_name": "Elite Ratha (Melee)",
        },
        {
            "base_id": 1759,
            "display_name": "Ratha (Ranged)",
            "unit_class": 36,
            "availability_tech": 831,
            "elite_tech": 828,
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
            # The Centurion is mounted — true dat class is 12 (Cavalry). Must NOT
            # be 6 (Infantry): 6 grants infantry Mail Armor/Squires/Arson and drops
            # the cavalry upgrades the game gives it (Bloodlines, Husbandry, Barding).
            "unit_class": 12,
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
            "unit_class": 6,  # Infantry class
            "extra_unit_classes": [18],  # Also gets Monastery techs (Sanctity, etc.)
            "excluded_tech_ids": [
                230,  # Block Printing: +3 range is monk conversion range, not attack range
                233,  # Illumination: +1.4 reload is monk recovery, not attack speed
            ],
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
            "display_name": "Mounted Trebuchet",
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
            "display_name": "White Feather Guard",
            "unit_class": 6,
            "availability_tech": 1063,
            "elite_tech": 1064,
            "elite_id": 1961,
            "elite_name": "Elite White Feather Guard",
        },
        {
            "base_id": 2150,
            "display_name": "War Chariot",
            "unit_class": 12,
            "availability_tech": 1065,
            "elite_tech": None,
            "elite_id": None,
            "elite_name": None,
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
    "Muisca": [
        {
            "base_id": 2562,
            "display_name": "Guecha Warrior",
            "unit_class": 0,  # Archer
            "availability_tech": 1363,
            "elite_tech": 1364,
            "elite_id": 2564,
            "elite_name": "Elite Guecha Warrior",
        },
        {
            "base_id": 2586,
            "display_name": "Temple Guard",
            "unit_class": 6,  # Infantry
            "availability_tech": 1400,
            "elite_tech": 1401,
            "elite_id": 2587,
            "elite_name": "Elite Temple Guard",
        },
    ],
    "Mapuche": [
        {
            "base_id": 2566,
            "display_name": "Kona",
            "unit_class": 12,  # Cavalry
            "availability_tech": 1375,
            "elite_tech": 1376,
            "elite_id": 2568,
            "elite_name": "Elite Kona",
        },
        {
            "base_id": 2569,
            "display_name": "Bolas Rider",
            "unit_class": 36,  # Cavalry Archer
            "availability_tech": 1377,
            "elite_tech": 1378,
            "elite_id": 2571,
            "elite_name": "Elite Bolas Rider",
        },
    ],
    "Tupi": [
        {
            "base_id": 2579,
            "display_name": "Blackwood Archer",
            "unit_class": 0,  # Archer
            "availability_tech": 1388,
            "elite_tech": 1389,
            "elite_id": 2581,
            "elite_name": "Elite Blackwood Archer",
        },
        {
            "base_id": 2582,
            "display_name": "Ibirapema Warrior",
            "unit_class": 6,  # Infantry
            "availability_tech": 1390,
            "elite_tech": 1391,
            "elite_id": 2584,
            "elite_name": "Elite Ibirapema Warrior",
        },
    ],
}


# ---------------------------------------------------------------------------
# Authoritative per-civ availability overrides (phantom-unit fix)
# ---------------------------------------------------------------------------
# unit_analyzer's availability model is a BLOCKLIST: a civ trains a unit unless
# the unit's "make-avail" tech is in that civ's disabled_techs (extracted from
# type-102 DISABLE_TECH commands in the civ's tech-tree effect). That is correct
# for default-roster units (e.g. Knight is explicitly disabled for non-knight
# civs).
#
# The lines below are ALLOWLIST units instead: in empires2_x2_p1.dat they are
# NOT disabled for the civs that lack them; the game auto-enables them per civ
# through tech-tree resolution (prerequisites / auto-research) that this
# pipeline does not replicate. With no disable signal, the blocklist lets EVERY
# civ train them -> ~776 phantom rows (each line attached to ~48 civs), incl.
# wrong upgrade tiers (Cumans Heavy Camel, Dravidians Elite Battle Elephant).
#
# Fix: pin each affected slug to its authoritative civ list. Source of truth =
# SiegeEngineers/aoe2techtree data.json per-civ Unit lists (resolved tech-tree
# availability), verified per UPGRADE TIER via the exact genie unit id and
# cross-checked against the clean build-170934 reference. paladin = knight line
# (unit 38) plus the Three Kingdoms Hei-Kuang Cavalry alternate (unit 1944).
#
# The CASTLE_UNITS / IMPERIAL_UNITS loops in generate_reference already honor
# "civ_only", so this needs no code change. NOTE: per these sources the Eagle
# line is Aztecs/Mayans only (Incas is excluded) -- matches the clean baseline.
_AVAILABILITY_OVERRIDES = {
    "eagle_warrior": ["Aztecs", "Mayans"],
    "elite_eagle": ["Aztecs", "Mayans"],
    "camel": ["Berbers", "Byzantines", "Cumans", "Ethiopians", "Gurjaras", "Hindustanis", "Khitans", "Malians", "Mongols", "Persians", "Saracens", "Tatars", "Turks"],
    "heavy_camel": ["Berbers", "Byzantines", "Ethiopians", "Gurjaras", "Hindustanis", "Khitans", "Malians", "Mongols", "Persians", "Saracens", "Tatars", "Turks"],
    "elephant": ["Bengalis", "Burmese", "Dravidians", "Khmer", "Malay", "Vietnamese"],
    "elite_elephant": ["Bengalis", "Burmese", "Khmer", "Malay", "Vietnamese"],
    "elephant_archer": ["Bengalis", "Dravidians", "Gurjaras"],
    "elite_ele_archer": ["Bengalis", "Dravidians", "Gurjaras"],
    "slinger": ["Incas", "Mapuche", "Muisca", "Tupi"],
    "imp_slinger": ["Incas", "Mapuche", "Muisca", "Tupi"],
    "champi_warrior": ["Incas", "Mapuche", "Muisca", "Tupi"],
    "elite_champi_warrior": ["Incas", "Mapuche", "Muisca", "Tupi"],
    "steppe_lancer": ["Cumans", "Jurchens", "Khitans", "Mongols", "Tatars"],
    "elite_steppe": ["Cumans", "Jurchens", "Khitans", "Mongols", "Tatars"],
    "fire_lancer": ["Chinese", "Jurchens", "Khitans", "Koreans", "Vietnamese"],
    "elite_fire_lancer": ["Chinese", "Jurchens", "Khitans", "Koreans", "Vietnamese"],
    "paladin": ["Armenians", "Berbers", "Bohemians", "Britons", "Bulgarians", "Burgundians", "Burmese", "Byzantines", "Celts", "Chinese", "Cumans", "Ethiopians", "Franks", "Georgians", "Goths", "Huns", "Italians", "Japanese", "Khmer", "Koreans", "Lithuanians", "Magyars", "Malay", "Malians", "Mongols", "Persians", "Poles", "Portuguese", "Romans", "Saracens", "Shu", "Sicilians", "Slavs", "Spanish", "Tatars", "Teutons", "Turks", "Vietnamese", "Vikings", "Wei", "Wu"],
}

_missing_override_slugs = []
for _avail_dict in (CASTLE_UNITS, IMPERIAL_UNITS):
    for _slug, _civs in _AVAILABILITY_OVERRIDES.items():
        if _slug in _avail_dict:
            _avail_dict[_slug]["civ_only"] = list(_civs)
# Any override slug not found in either dict is a config drift bug -> surface it.
_found = set(CASTLE_UNITS) | set(IMPERIAL_UNITS)
_missing_override_slugs = [s for s in _AVAILABILITY_OVERRIDES if s not in _found]
if _missing_override_slugs:
    import warnings as _warnings
    _warnings.warn(
        "phantom-fix availability overrides reference unknown slugs: "
        + ", ".join(_missing_override_slugs)
    )
