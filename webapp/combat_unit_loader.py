"""
Shared combat-unit dict builder for ref_units rows.

All three callers (app.py, best_units.py, compute_battle_scores.py) previously
duplicated the same 85-line field mapping.  This module provides a single
canonical version that all of them import.
"""


def build_combat_dict_from_ref(row):
    """Build a combat-unit dict from a ref_units row.

    Compatible with prepare_combat_unit() from simulation.py.
    Both app.py and best_units.py use this to avoid duplicating
    the 85-line field mapping.
    """
    reload_time = row["final_reload_time"] or 2.0
    attack_speed = 1.0 / reload_time if reload_time > 0 else 0.5

    return {
        "slug": row["unit_slug"],
        "unit_name": row["unit_name"],
        "unit_category": "military",
        "paired_unit_slug": None,
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "attack_range": row["final_range"] if row["is_ranged"] else 0,
        "attack_speed": attack_speed,
        "attack_delay": row["final_attack_delay"] or 0,
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "movement_speed": row["final_speed"],
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
        "upgrade_cost_food": row["upgrade_cost_food"] or 0,
        "upgrade_cost_wood": row["upgrade_cost_wood"] or 0,
        "upgrade_cost_gold": row["upgrade_cost_gold"] or 0,
        "attacks_json": row["final_attacks_json"],
        "armors_json": row["final_armors_json"],
        "accuracy": row["final_accuracy"] or 100,
        # Base accuracy (pre-Thumb Ring) is the per-arrow rate for SECONDARY
        # projectiles — Thumb Ring boosts only the primary arrow. Used by
        # simulation.py to roll extra-projectile hits at the unit's natural
        # accuracy (e.g. 85% for Chu Ko Nu) rather than a flat 50% heuristic.
        "base_accuracy": row["base_accuracy"] or 100,
        "min_attack_range": row["min_range"] or 0,
        "projectile_speed": row["projectile_speed"] or 0,
        "is_siege_projectile": row["is_siege_projectile"] or 0,
        "splash_radius": row["splash_radius"] or 0,
        "extra_projectiles": row["extra_projectiles"] or 0,
        "extra_projectile_attacks_json": row["extra_projectile_attacks_json"],
        "trample_percent": row["trample_percent"] or 0,
        "trample_radius": row["trample_radius"] or 0,
        "trample_flat_damage": row["trample_flat_damage"] or 0,
        "hp_regen": row["hp_regen"] or 0,
        "hp_regen_in_combat": row["hp_regen_in_combat"] or 0,
        "food_per_kill": row["food_per_kill"] or 0,
        "wood_per_kill": row["wood_per_kill"] or 0,
        "gold_per_kill": row["gold_per_kill"] or 0,
        "charge_projectile_count": row["charge_projectile_count"] or 0,
        "charge_projectile_speed": row["charge_projectile_speed"] or 0,
        "charge_projectile_attacks_json": row["charge_projectile_attacks_json"],
        "charge_attack_range": float(row["charge_attack_range"] or 0),
        "charge_ignores_armor": int(row["charge_ignores_armor"] or 0),
        "ignores_pierce_armor": int(row["ignores_pierce_armor"] or 0),
        "ignores_melee_armor": int(row["ignores_melee_armor"] or 0),
        "bonus_damage_reduction": row["bonus_damage_reduction"] or 0,
        "splash_on_hit_radius": row["splash_on_hit_radius"] or 0,
        "splash_on_hit_fraction": row["splash_on_hit_fraction"] or 1.0,
        "dodge_shield_max": int(row["dodge_shield_max"] or 0),
        "dodge_shield_recharge": row["dodge_shield_recharge"] or 0,
        "bleed_dps": row["bleed_dps"] or 0,
        "bleed_duration": row["bleed_duration"] or 0,
        "block_first_melee": int(row["block_first_melee"] or 0),
        "attack_bonus_per_kill": int(row["attack_bonus_per_kill"] or 0),
        "first_attack_extra_projectiles": int(
            row["first_attack_extra_projectiles"] or 0
        ),
        "pass_through_percent": row["pass_through_percent"] or 0,
        "pass_through_count": row["pass_through_count"] or 1,
        "extra_proj_scatter": row["extra_proj_scatter"] or 0,
        "miss_damage_percent": row["miss_damage_percent"] or 0,
        "hp_per_kill": int(row["hp_per_kill"] or 0),
        "hp_per_kill_max": int(row["hp_per_kill_max"] or 0),
        "hp_transform_threshold": row["hp_transform_threshold"] or 0,
        "pop_space": row["pop_space"] or 1.0,
        "armor_strip_per_hit": int(row["armor_strip_per_hit"] or 0),
        "charge_attack_melee": int(row["charge_attack_melee"] or 0),
        "charge_recharge_time": row["charge_recharge_time"] or 0,
        "attack_bonus_nearby": row["attack_bonus_nearby"] or 0,
        "nearby_bonus_count": int(row["nearby_bonus_count"] or 0),
        "damage_reflect_percent": row["damage_reflect_percent"] or 0,
        "hp_nearby_percent_per_unit": row["hp_nearby_percent_per_unit"] or 0,
        "hp_nearby_max_units": int(row["hp_nearby_max_units"] or 0),
        "charge_slow_percent": row["charge_slow_percent"] or 0,
        "charge_slow_duration": row["charge_slow_duration"] or 0,
        # Attack speed ramp (Temple Guard)
        "attack_speed_ramp": row["attack_speed_ramp"] or 0,
        "attack_speed_min": row["attack_speed_min"] or 0,
        # Execute damage (Kona)
        "execute_damage_per_step": row["execute_damage_per_step"] or 0,
        "execute_hp_step": row["execute_hp_step"] or 0,
        # Ally death heal (Guecha)
        "ally_death_heal": row["ally_death_heal"] or 0,
        "ally_death_heal_duration": row["ally_death_heal_duration"] or 0,
        # Dismount on death (Konnik)
        "dismount_hp": row["dismount_hp"],
        "dismount_attack": row["dismount_attack"],
        "dismount_melee_armor": row["dismount_melee_armor"],
        "dismount_pierce_armor": row["dismount_pierce_armor"],
        "dismount_attack_speed": row["dismount_attack_speed"],
        "dismount_attack_delay": row["dismount_attack_delay"],
        "dismount_movement_speed": row["dismount_movement_speed"],
        "dismount_attacks_json": row["dismount_attacks_json"],
        "dismount_armors_json": row["dismount_armors_json"],
        # Transform on HP threshold (Jian Swordsman)
        "transform_hp": row["transform_hp"],
        "transform_attack": row["transform_attack"],
        "transform_melee_armor": row["transform_melee_armor"],
        "transform_pierce_armor": row["transform_pierce_armor"],
        "transform_attack_speed": row["transform_attack_speed"],
        "transform_attack_delay": row["transform_attack_delay"],
        "transform_movement_speed": row["transform_movement_speed"],
        "transform_attacks_json": row["transform_attacks_json"],
        "transform_armors_json": row["transform_armors_json"],
        # Outline size — used by the position-aware sim (simulation_real.py)
        # to compute unit radius for collision/range calculations.  Not used
        # by the abstract tick-based sim in simulation.py.
        "outline_size": row["outline_size_x"] or 0.2,
    }
