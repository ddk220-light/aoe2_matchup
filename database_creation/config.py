"""Configuration constants and unit definitions for AoE2 reference database generation."""

from dataclasses import dataclass, field
from pathlib import Path

# Paths - relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = Path(__file__).parent / "extracted_data"
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

# Original 13 civilizations
ORIGINAL_13_CIVS = [
    "Armenians",
    "Aztecs",
    "Bengalis",
    "Berbers",
    "Bohemians",
    "Britons",
    "Bulgarians",
    "Burgundians",
    "Burmese",
    "Byzantines",
    "Celts",
    "Chinese",
    "Cumans",
    "Dravidians",
    "Ethiopians",
    "Franks",
    "Georgians",
    "Goths",
    "Gurjaras",
    "Hindustanis",
    "Huns",
    "Incas",
    "Italians",
    "Japanese",
    "Jurchens",
    "Khitans",
    "Khmer",
    "Koreans",
    "Lithuanians",
    "Magyars",
    "Malay",
    "Malians",
    "Mayans",
    "Mongols",
    "Persians",
    "Poles",
    "Portuguese",
    "Romans",
    "Saracens",
    "Shu",
    "Sicilians",
    "Slavs",
    "Spanish",
    "Tatars",
    "Teutons",
    "Turks",
    "Vietnamese",
    "Vikings",
    "Wei",
    "Wu",
]

# =============================================================================
# SIMULATION CONFIGURATION
# =============================================================================
# Lithuanian relic count for cavalry attack bonus (0-4)
# Each relic gives +1 attack to Knights, Cavaliers, Paladins, and Leitis
LITHUANIAN_RELIC_COUNT = 4

# =============================================================================
# ALLOWED SHADOW TECHS — shadow techs (research_location=-1) that should NOT be
# filtered out. These are age-based stat upgrade techs for specific units.
# =============================================================================
ALLOWED_SHADOW_TECHS = {
    774,  # Flemish Militia Age3: +10 HP, +3 attack, +anti-cav bonuses
    797,  # Flemish Militia Age4: +5 HP, +3 attack, +anti-cav bonuses
}

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

# Techs that exist in the dat file but have been removed/replaced in-game
# These are skipped during unique tech and civ bonus application
REMOVED_TECHS = {
    9,  # Saracen Zealotry (replaced by Bimaristan + Counterweights)
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
    "scorpion": {"unit_category": "siege", "pass_through_count": 3},
    "heavy_scorpion": {"unit_category": "siege", "pass_through_count": 3},
    "skirm": {"unit_category": "trash"},
    "elite_skirm": {"unit_category": "trash"},
    "imp_elite_skirm": {"unit_category": "trash"},
    "spearman": {"unit_category": "trash"},
    "pikeman": {"unit_category": "trash"},
    "halberdier": {"unit_category": "trash"},
    "scout": {"unit_category": "trash"},
    "light_cav": {"unit_category": "trash"},
    "hussar": {"unit_category": "trash"},
    "winged_hussar": {"unit_category": "trash"},
    "ram": {"unit_category": "siege"},
    "siege_ram": {"unit_category": "siege"},
    "trebuchet": {"unit_category": "siege"},
    "bombard_cannon": {"unit_category": "siege"},
    "organ_gun": {"unit_category": "siege"},
    "elite_organ_gun": {"unit_category": "siege"},
    "hussite_wagon": {"unit_category": "siege"},
    "elite_hussite_wagon": {"unit_category": "siege"},
    "chakram_thrower": {"unit_category": "infantry"},
    "elite_chakram_thrower": {"unit_category": "infantry"},
    "warrior_priest": {"unit_category": "infantry"},
    "grenadier": {"unit_category": "siege"},
    "war_chariot": {"unit_category": "siege"},
    "mounted_trebuchet": {"unit_category": "siege"},
    "jian_swordsman": {"unit_category": "infantry"},
}

# Base stat overrides for units where the dat file has incorrect values.
# Keyed by unit ID. Applied after get_base_stats() before tech calculations.
UNIT_STAT_OVERRIDES = {
    # Elite Woad Raider: dat file has speed=1.17 (same as base), but elite should
    # be faster. 1.4 (wiki final speed) / 1.15 (Celts infantry speed bonus) ≈ 1.217
    534: {"speed": 1.2174},
    # War Chariot (2150): dat extracts as melee, but is actually ranged siege unit
    # with scorpion-like pass-through bolts. Override base stats to match game data.
    2150: {
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
}

# Unique units — keyed by base slug (without civ suffix)
# Only ability flags and values NOT extractable from dat file belong here.
# Stats like extra_projectiles, trample, dodge shield are now data-driven
# via get_extracted_combat_properties().
UNIQUE_COMBAT_PROPERTIES = {
    "konnik": {
        "dismount_unit_id": 1252,
        "dismount_hp": 45,
        "dismount_attack": 12,
        "dismount_melee_armor": 1,
        "dismount_pierce_armor": 1,
        "dismount_attack_speed": 2.4,
        "dismount_attack_delay": 0,
        "dismount_movement_speed": 0.9,
        "dismount_attacks_json": '{"4": 12, "1": 0, "19": 0, "31": 0}',
        "dismount_armors_json": '{"1": 0, "3": 1, "4": 1, "19": 0, "31": 0}',
    },
    "elite_konnik": {
        "dismount_unit_id": 1253,
        "dismount_hp": 50,
        "dismount_attack": 13,
        "dismount_melee_armor": 2,
        "dismount_pierce_armor": 2,
        "dismount_attack_speed": 2.4,
        "dismount_attack_delay": 0,
        "dismount_movement_speed": 0.9,
        "dismount_attacks_json": '{"4": 13, "1": 0, "19": 0, "31": 0}',
        "dismount_armors_json": '{"1": 0, "3": 2, "4": 2, "19": 0, "31": 0}',
    },
    "leitis": {"ignores_melee_armor": 1},
    "elite_leitis": {"ignores_melee_armor": 1},
    "composite_bowman": {"ignores_pierce_armor": 1},
    "elite_composite_bowman": {"ignores_pierce_armor": 1},
    # Fire Lancer charge: 3 projectiles, range 4, ignores armor (except siege/ships/buildings)
    "fire_lancer": {"charge_attack_range": 4, "charge_ignores_armor": 1},
    "elite_fire_lancer": {"charge_attack_range": 4, "charge_ignores_armor": 1},
    # Berserk HP regen is now data-driven from rear_attack_modifier in dat (40 HP/min)
    # Organ Gun/Fire Archer extra projectiles are now data-driven
    # Bleed damage (ability flag + stat values not in dat)
    "liao_dao": {"bleed_dps": 2.0, "bleed_duration": 5.0},
    "elite_liao_dao": {"bleed_dps": 3.0, "bleed_duration": 5.0},
    # Block first melee hit (ability flag, not in dat)
    "iron_pagoda": {"block_first_melee": 1},
    "elite_iron_pagoda": {"block_first_melee": 1},
    # Grenadier splash: data-driven from dat (blast_level=11, blast_width=0.65)
    # Kill bonus attack + HP regen per kill (ability flags, not in dat)
    # Tiger Cavalry: +4 attack and +10 HP per kill, max +40 HP gained
    "tiger_cavalry": {"attack_bonus_per_kill": 4, "hp_per_kill": 10, "hp_per_kill_max": 40},
    "elite_tiger_cavalry": {"attack_bonus_per_kill": 4, "hp_per_kill": 10, "hp_per_kill_max": 40},
    "jaguar_warrior": {"attack_bonus_per_kill": 4},
    "elite_jaguar_warrior": {"attack_bonus_per_kill": 4},
    # HP transformation (ability flag, not in dat)
    "jian_swordsman": {
        "hp_transform_threshold": 45.0 / 70.0,
        "transform_unit_id": 1976,
        "transform_hp": 70,
        "transform_attack": 11,
        "transform_melee_armor": 0,
        "transform_pierce_armor": 2,
        "transform_attack_speed": 0.5,
        "transform_attack_delay": 0.0,
        "transform_movement_speed": 1.1,
        "transform_attacks_json": '{"4": 11, "15": 4, "21": 2, "8": 0, "30": 0}',
        "transform_armors_json": '{"1": 0, "4": 0, "3": 2, "31": 0, "29": 0, "19": 0}',
    },
    # Karambit Warrior takes 0.5 pop space (Malay unique tech Forced Levy is separate)
    "karambit_warrior": {"pop_space": 0.5},
    "elite_karambit_warrior": {"pop_space": 0.5},
    # Obuch strips 1 melee + 1 pierce armor per hit (not in dat)
    "obuch": {"armor_strip_per_hit": 1},
    "elite_obuch": {"armor_strip_per_hit": 1},
    # Coustillier melee charge attack (charge_type=1 in dat, data-driven fields extracted)
    "coustillier": {"charge_attack_melee": 20, "charge_recharge_time": 40.0},
    "elite_coustillier": {"charge_attack_melee": 25, "charge_recharge_time": 40.0},
    # Chakram Thrower pass-through (chakrams hit multiple units in a line)
    # blast_damage=1.0 in dat = pass-through, not splash
    "chakram_thrower": {"pass_through_percent": 1.0},
    "elite_chakram_thrower": {"pass_through_percent": 1.0},
    # Ghulam pass-through (blast_attack_level=130, blast_damage=0.5 in dat)
    # Thrusting attack penetrates to unit behind target for 50% damage.
    # In group fights (which sim always models), there's usually a unit behind the target.
    "ghulam": {"pass_through_percent": 0.5},
    "elite_ghulam": {"pass_through_percent": 0.5},
    # Ballista Elephant bolts pass through 3 additional enemies (like scorpions)
    "ballista_elephant": {"pass_through_count": 3},
    "elite_ballista_elephant": {"pass_through_count": 3},
    # Organ Gun fires 5/6 projectiles that scatter to different targets
    "organ_gun": {"extra_proj_scatter": 1},
    "elite_organ_gun": {"extra_proj_scatter": 1},
    # War Chariot: ranged pass-through (like scorpion), 5 total projectiles in focus fire
    "war_chariot": {
        "pass_through_percent": 0.5,
        "pass_through_count": 3,
        "extra_projectiles": 4,
        "min_attack_range": 1,
    },
    # Arambai: missed shots deal full damage to random nearby enemy.
    # With 20/30% accuracy, most shots miss but hit other units in group fights.
    "arambai": {"miss_damage_percent": 1.0},
    "elite_arambai": {"miss_damage_percent": 1.0},
    # Monaspa nearby ally attack bonus (+2 per nearby cavalry, max 4 nearby)
    "monaspa": {"attack_bonus_nearby": 2, "nearby_bonus_count": 4},
    "elite_monaspa": {"attack_bonus_nearby": 2, "nearby_bonus_count": 4},
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
    # Hul'che Javelineers (Mayan Castle UT) - skirmishers fire extra projectile
    ("Mayans", "elite_skirm"): {
        "extra_projectiles": 1,
        "extra_projectile_attacks_json": '{"3": 1}',
    },
    ("Mayans", "imp_elite_skirm"): {
        "extra_projectiles": 1,
        "extra_projectile_attacks_json": '{"3": 1}',
    },
    # Pirotecnia (Italian Imperial UT) - gunpowder units get 15% pass-through damage
    ("Italians", "hand_cannoneer"): {"pass_through_percent": 0.15},
    # Sicilian civ bonus - all military units receive 40% less bonus damage
    ("Sicilians", "swordsmen"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "champion"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "pikeman"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "halberdier"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "knight"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "paladin"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "light_cav"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "hussar"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "crossbow"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "arbalester"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "cav_archer"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "heavy_cav_archer"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "elite_skirm"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "imp_elite_skirm"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "heavy_camel"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "hand_cannoneer"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "serjeant"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "elite_serjeant"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "scorpion"): {"bonus_damage_reduction": 0.4},
    ("Sicilians", "heavy_scorpion"): {"bonus_damage_reduction": 0.4},
    # Lechitic Legacy (Poles Imperial UT) - light cavalry get 50% trample
    ("Poles", "hussar"): {"trample_percent": 0.5, "trample_radius": 0.5},
    ("Poles", "winged_hussar"): {"trample_percent": 0.5, "trample_radius": 0.5},
    # Comitatenses (Romans Imperial UT, Tech 884) - charge attack for knights, militia, centurion
    # charge_recharge_rate=0.25 in dat → recharge_time = 1/0.25 = 4.0 seconds
    ("Romans", "champion"): {"charge_attack_melee": 5, "charge_recharge_time": 4.0},
    ("Romans", "legionary"): {"charge_attack_melee": 5, "charge_recharge_time": 4.0},
    ("Romans", "paladin"): {"charge_attack_melee": 5, "charge_recharge_time": 4.0},
    ("Romans", "centurion"): {"charge_attack_melee": 5, "charge_recharge_time": 4.0},
    ("Romans", "elite_centurion"): {
        "charge_attack_melee": 5,
        "charge_recharge_time": 4.0,
    },
    # Khitan Lamellar Armor (Imp UT) — infantry + skirmishers reflect 25% melee damage
    ("Khitans", "champion"): {"damage_reflect_percent": 0.25},
    ("Khitans", "halberdier"): {"damage_reflect_percent": 0.25},
    ("Khitans", "pikeman"): {"damage_reflect_percent": 0.25},
    ("Khitans", "swordsmen"): {"damage_reflect_percent": 0.25},
    ("Khitans", "elite_skirm"): {"damage_reflect_percent": 0.25},
    ("Khitans", "imp_elite_skirm"): {"damage_reflect_percent": 0.25},
    ("Khitans", "liao_dao"): {"damage_reflect_percent": 0.25},
    ("Khitans", "elite_liao_dao"): {"damage_reflect_percent": 0.25},
    # Khitan Ordo Cavalry — cavalry HP regen in combat (20 HP/min)
    ("Khitans", "heavy_cav_archer"): {"hp_regen": 20},
    ("Khitans", "cav_archer"): {"hp_regen": 20},
    ("Khitans", "hussar"): {"hp_regen": 20},
    ("Khitans", "light_cav"): {"hp_regen": 20},
    ("Khitans", "steppe_lancer"): {"hp_regen": 20},
    ("Khitans", "elite_steppe"): {"hp_regen": 20},
    ("Khitans", "camel"): {"hp_regen": 20},
    ("Khitans", "heavy_camel"): {"hp_regen": 20},
    ("Khitans", "fire_lancer"): {"hp_regen": 20},
    ("Khitans", "elite_fire_lancer"): {"hp_regen": 20},
    ("Khitans", "mounted_trebuchet"): {"hp_regen": 20},
    # Shu Coiled Serpent Array (Castle UT) — spear-line + White Feather gain %HP near each other
    # +0.5% HP per nearby qualifying unit, capped at 30 units = +15% HP max
    ("Shu", "halberdier"): {"hp_nearby_percent_per_unit": 0.5, "hp_nearby_max_units": 30},
    ("Shu", "pikeman"): {"hp_nearby_percent_per_unit": 0.5, "hp_nearby_max_units": 30},
    ("Shu", "white_feather_guard"): {
        "hp_nearby_percent_per_unit": 0.5,
        "hp_nearby_max_units": 30,
    },
    ("Shu", "elite_white_feather_guard"): {
        "hp_nearby_percent_per_unit": 0.5,
        "hp_nearby_max_units": 30,
    },
    # Shu Bolt Magazine (Imp UT) — archer-line + War Chariots fire additional projectiles
    ("Shu", "arbalester"): {
        "extra_projectiles": 1,
        "extra_projectile_attacks_json": '{"3": 1}',
    },
    ("Shu", "crossbow"): {
        "extra_projectiles": 1,
        "extra_projectile_attacks_json": '{"3": 1}',
    },
    ("Shu", "war_chariot"): {"extra_projectiles": 6},
    # Jurchens Thunderclap Bombs (Imp UT) — additional projectiles for Rocket Carts, Grenadiers
    ("Jurchens", "mangonel"): {"extra_projectiles": 1},
    ("Jurchens", "siege_onager"): {"extra_projectiles": 1},
    ("Jurchens", "grenadier"): {"extra_projectiles": 1},
}

# Paired units mapping (for matchup mode switching)
PAIRED_UNITS = {
    "ratha_(melee)": "ratha_(ranged)",
    "ratha_(ranged)": "ratha_(melee)",
    "elite_ratha_(melee)": "elite_ratha_(ranged)",
    "elite_ratha_(ranged)": "elite_ratha_(melee)",
}

# =============================================================================
# ALLY (TEAM) UNITS
# =============================================================================
# Units that become available to ALL civs when a specific civ is on the team.
# Key: source civ name. Value: list of unit slugs from CASTLE_UNITS/IMPERIAL_UNITS.
# These units must have "civ_only" set in their unit config to restrict solo generation.
# Not yet used in any feature — reserved for future team game support.
ALLY_UNITS = {
    "Italians": ["condottiero"],
    "Berbers": ["genitour", "elite_genitour"],
    "Vietnamese": ["imperial_skirmisher"],
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
    },
    "trebuchet": {
        "base_id": 42,
        "display_name": "Trebuchet",
        "unit_class": 54,
        "availability_tech": None,
        "upgrades": [],
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
            "unit_class": 36,
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
}


def _tech_age_name(age_num):
    """Convert age number to name."""
    return {1: "Dark", 2: "Feudal", 3: "Castle", 4: "Imperial"}.get(
        age_num, f"Age {age_num}"
    )
