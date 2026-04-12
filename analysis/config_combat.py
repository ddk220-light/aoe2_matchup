"""Combat properties for AoE2 unit simulation.

Contains three dicts:
  - COMBAT_PROPERTIES: standard unit combat flags (keyed by unit slug)
  - UNIQUE_COMBAT_PROPERTIES: unique unit ability flags not extractable from dat
  - CIV_COMBAT_PROPERTIES: civ-conditional overrides applied on top of base/unique props

No dependencies on other config sub-modules.
"""

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
    "traction_trebuchet": {"unit_category": "siege"},
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
    "chakram_thrower": {"pass_through_percent": 1.0, "pass_through_count": 3},
    "elite_chakram_thrower": {"pass_through_percent": 1.0, "pass_through_count": 3},
    # Ghulam has blast_damage=0.5 in dat but small melee splash radius —
    # not modeled (position-less sim over-amplifies melee splash on cheap swarm units).
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
    # Ibirapema Warrior: blast_width=1.0 in dat = area/splash melee damage
    # blast_attack_level=162 — treat as trample (similar to Druzhina infantry splash)
    "ibirapema_warrior": {"trample_flat_damage": 5, "trample_radius": 0.5},
    "elite_ibirapema_warrior": {"trample_flat_damage": 5, "trample_radius": 0.5},
    "temple_guard": {"attack_speed_ramp": 0.2, "attack_speed_min": 1.0},
    "elite_temple_guard": {"attack_speed_ramp": 0.2, "attack_speed_min": 1.0},
    # Guecha Warrior: regen on nearby ally Guecha death (+5 HP over 3s, refreshes)
    "guecha_warrior": {"ally_death_heal": 5.0, "ally_death_heal_duration": 3.0},
    "elite_guecha_warrior": {"ally_death_heal": 5.0, "ally_death_heal_duration": 3.0},
    # Kona execute damage: +1 attack per 15% missing HP on the target
    "kona": {"execute_damage_per_step": 1, "execute_hp_step": 0.15},
    "elite_kona": {"execute_damage_per_step": 1, "execute_hp_step": 0.15},
    # Bolas Rider: charge extra projectile (charge_type=6 in dat)
    # max_total_projectiles=1 so extraction sets charge_projectile_count=0;
    # override to 1 because the one projectile IS stronger on charge.
    # charge_recharge_rate=0.0333 in dat → recharge_time = 1/0.0333 ≈ 30s.
    "bolas_rider": {"charge_projectile_count": 1, "charge_recharge_time": 30.0, "charge_slow_percent": 0.15, "charge_slow_duration": 10.0},
    "elite_bolas_rider": {"charge_projectile_count": 1, "charge_recharge_time": 30.0, "charge_slow_percent": 0.15, "charge_slow_duration": 10.0},
    # War Dog: dodge shield (charge_type=4 in dat) + hp_regen (15/min); data-driven
    # Blackwood Archer: 0.5 pop space (trained in pairs like Karambit Warrior)
    # Poison via Curare tech modeled as CIV_COMBAT_PROPERTIES below
    "blackwood_archer": {"pop_space": 0.5},
    "elite_blackwood_archer": {"pop_space": 0.5},
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
    # Mapuche Malon (Castle UT) — Bolas Riders, Slingers, Skirmishers deal 30% pass-through damage
    ("Mapuche", "bolas_rider"): {"pass_through_percent": 0.30, "pass_through_count": 1},
    ("Mapuche", "elite_bolas_rider"): {"pass_through_percent": 0.30, "pass_through_count": 1},
    ("Mapuche", "slinger"): {"pass_through_percent": 0.30, "pass_through_count": 1},
    ("Mapuche", "imp_slinger"): {"pass_through_percent": 0.30, "pass_through_count": 1},
    ("Mapuche", "elite_skirm"): {"pass_through_percent": 0.30, "pass_through_count": 1},
    ("Mapuche", "imp_elite_skirm"): {"pass_through_percent": 0.30, "pass_through_count": 1},
    # Tupi Curare (Imp UT) — arrow projectiles apply poison (2 DPS for 15 seconds)
    # Imperial-age only: Curare is an Imperial UT, so Castle-age archers don't get it.
    ("Tupi", "arbalester"): {"bleed_dps": 2.0, "bleed_duration": 15.0},
    ("Tupi", "elite_blackwood_archer"): {"bleed_dps": 2.0, "bleed_duration": 15.0},
}
