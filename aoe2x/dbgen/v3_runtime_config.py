"""Canonical non-scalar configuration for V3 unit mechanics.

Most mechanics are extracted from the Genie DAT or the fully-upgraded
``ref_units`` row.  A small number are command/mode semantics or compound
technology effects that cannot be represented by one DAT scalar.  They live
here so reference-database generation, fixture export, the web API, and tests
all consume the same declarations.

Nothing in this module depends on an opponent, winner, survivor HP, or battle
outcome.  Live-capture references describe mechanics evidence only.
"""

from __future__ import annotations


# Effects merged into the runtime ``effects`` object after the ordinary
# registry-backed ref_units columns have been read.
RUNTIME_EFFECTS_BY_SLUG = {
    # Official updates 83607 and 95810; see the dated unit audit for URLs.
    "elite_centurion_romans": {
        "speed_attack_aura_group": "militia",
        "speed_attack_aura_radius_tiles": 12.0,
        "aura_move_multiplier": 1.15,
        "aura_attack_rate_multiplier": 1.2,
    },
    # Task151: work rate * civilization resource, paid during attack animation.
    # Published direct DAT/recording analysis and stored 185872 tasks:
    # https://www.reddit.com/r/aoe2/comments/gq309z/how_does_keshik_gold_generation_ability_work_an/
    # https://www.reddit.com/r/aoe2/comments/1wpq9yi/reasoning_for_the_weird_numbers_behind_the/
    # Exact gold tick timing remains uncalibrated; do not apply tooltip +50%
    # again on top of the animation/reload and resource multiplier.
    "elite_keshik_tatars": {"combat_gold_per_animation_second": 0.01 * 50},
    "elite_varangian_guard": {
        "combat_gold_per_animation_second": 0.015908999368548393 * 50,
    },
    # reference/units/unique/Monaspa.md: seven OTHER own Knights/Monaspas,
    # within 15 tiles, one attack per tier and at most four tiers.
    "elite_monaspa_georgians": {
        "nearby_attack_step": 7,
        "nearby_attack_radius_tiles": 15.0,
    },
    # The old registry's block_first_melee flag identifies this ability, but
    # its once-per-life description is incomplete. Iron_Pagoda.md documents
    # a 30-second recharge for the elite unit (40 seconds for the base unit).
    "elite_iron_pagoda_jurchens": {
        "melee_block_recharge_seconds": 30.0,
        "friendly_fire_damage_multiplier": 0.5,
    },
    "elite_guecha_warrior_muisca": {
        "ally_death_heal_radius_tiles": 6.0,
        "ally_death_heal_group": "guecha",
    },
    "elite_leitis_lithuanians": {
        "melee_armor_bypass_non_siege_land_only": True,
    },
    "elite_tiger_cavalry_wei": {
        "hp_per_kill_increases_maximum": True,
    },
    "elite_liao_dao_khitans": {
        "bleed_target_filter": "non_mechanical_land",
    },
    "elite_blackwood_archer_tupi": {
        "death_resource_refund_fraction": 0.15,
    },
    "elite_ibirapema_warrior_tupi": {
        "death_resource_refund_fraction": 0.15,
    },
    "jian_swordsman_wu": {
        "hp_transform_reversible": True,
    },
    "elite_white_feather_guard_shu": {
        "on_hit_slow_percent": 0.15,
        "on_hit_slow_duration_seconds": 10.0,
        "on_hit_slow_excludes_siege": True,
        "hp_nearby_radius_tiles": 15.0,
    },
    "mounted_trebuchet_khitans": {
        "impact_hazard_radius_tiles": 0.7,
        "impact_hazard_duration_seconds": 10.0,
        "impact_hazard_damage_per_second": 2.0,
        "impact_hazard_stacks": False,
    },
    "elite_samurai_japanese": {
        "charged_speed_multiplier": 1.25,
        "charged_speed_min_target_distance_tiles": 2.0,
        "charged_speed_max_target_distance_tiles": 7.0,
    },
}


# Fully researched civilization technologies whose runtime behavior is a
# compound event rather than a single unit attribute.
RUNTIME_EFFECTS_BY_CIV_SLUG = {
    ("Varangians", "elite_varangian_guard"): {
        # Patch185872 task151 and tech1488, preserved in ref_special_effects.
        "combat_gold_per_animation_second": 0.015908999368548393 * 50 * 1.333299994468689,
        # Owner-specified independent slots. Existing fully-upgraded reload
        # supplies the rapid 1.6-second throw interval; exact live cadence open.
        "independent_charge_recharge_seconds": 30.0,
    },
    ("Jurchens", "grenadier_jurchens"): {
        "delayed_impact_melee_attack": 4.0,
        "delayed_impact_radius_tiles": 0.65,
        "delayed_impact_delay_seconds": 1.5,
        "delayed_impact_repeat_count": 3,
        "delayed_impact_repeat_interval_seconds": 1.5,
        "death_explosion_melee_attack": 15.0,
        "death_explosion_radius_tiles": 0.75,
    },
    ("Jurchens", "mangonel"): {
        "delayed_impact_melee_attack": 4.0,
        "delayed_impact_radius_tiles": 1.25,
        "delayed_impact_delay_seconds": 2.0,
        "delayed_impact_repeat_count": 1,
        "delayed_impact_repeat_interval_seconds": 2.0,
        "death_explosion_melee_attack": 15.0,
        "death_explosion_radius_tiles": 1.0,
    },
    ("Jurchens", "siege_onager"): {
        "delayed_impact_melee_attack": 4.0,
        "delayed_impact_radius_tiles": 1.25,
        "delayed_impact_delay_seconds": 2.0,
        "delayed_impact_repeat_count": 1,
        "delayed_impact_repeat_interval_seconds": 2.0,
        "death_explosion_melee_attack": 15.0,
        "death_explosion_radius_tiles": 1.0,
    },
    ("Jurchens", "lou_chuan_jurchens"): {
        "delayed_impact_weapon_mode": "trebuchet",
        "delayed_impact_melee_attack": 20.0,
        "delayed_impact_radius_tiles": 2.0,
        "delayed_impact_delay_seconds": 2.0,
        "delayed_impact_repeat_count": 1,
        "delayed_impact_repeat_interval_seconds": 2.0,
        "death_explosion_melee_attack": 45.0,
        "death_explosion_radius_tiles": 2.0,
    },
}


# Options that select or annotate a concrete weapon form.  They are consumed
# by the shared mechanics builder; fixture scripts no longer own them.
EXPORT_OPTIONS_BY_CIV_SLUG = {
    ("Shu", "war_chariot_shu"): {
        "concrete_form": True,
        "extra_projectile_count": 6,
        "volley_release_interval_seconds": 1 / 3,
        "volley_release_size": 1,
        "volley_release_source": (
            "war_chariot_shu_vs_arbalester run_001 frames.bin: complete "
            "seven-bolt Focus Fire volleys release at 0.334 s median intervals"
        ),
        "weapon_mode": "focus_fire",
    },
    ("Chinese", "elite_chu_ko_nu_chinese"): {
        "volley_release_interval_seconds": 0.27,
        "volley_release_size": 1,
        "volley_double_release_percent": 34.0,
        "volley_release_source": (
            "elite_chu_ko_nu_chinese_vs_arbalester run_001 frames.bin: "
            "source-attributed arrows release in groups of one or two at "
            "roughly 0.28 s intervals; 91 of 269 complete-volley release "
            "groups contain two arrows"
        ),
        "weapon_mode": "repeating_volley",
    },
}


# Additional selectable modes sharing one public reference-database row.
ADDITIONAL_MODES_BY_CIV_SLUG = {
    ("Shu", "war_chariot_shu"): (
        {
            "mode": "barrage",
            "master": 1980,
            "options": {
                "concrete_form": True,
                "extra_projectile_count": 10,
                "volley_release_interval_seconds": 1 / 3,
                "volley_release_size": 1,
                "volley_release_source": (
                    "mechanics hypothesis inherited from sibling Focus Fire "
                    "form sharing attack graphic 12976; no live Barrage tape "
                    "is preserved"
                ),
                "weapon_mode": "barrage",
            },
        },
    ),
}


# Alternate bodies that must carry a complete mechanics block.
DISMOUNT_FORM_BY_CIV_SLUG = {
    ("Bulgarians", "elite_konnik_bulgarians"): 1253,
}


# Unit behavior classification is normally derived from ranged-ness and the
# DAT unit class.  These mobile-looking siege bodies are the small set whose
# gameplay role is not conveyed by class 13 alone.
BEHAVIOR_CLASS_BY_CIV_SLUG = {
    ("Shu", "war_chariot_shu"): "siege_ranged",
    ("Bohemians", "elite_hussite_wagon_bohemians"): "siege_ranged",
    ("Khitans", "mounted_trebuchet_khitans"): "siege_ranged",
    ("Khmer", "elite_ballista_elephant_khmer"): "siege_ranged",
}


# Scenario-owned actors are not user-selectable ref_units rows, but their
# mechanics must still be generated and stored so production never reaches
# into calibration fixtures.  Player 4 uses the authored Scout Cavalry body
# with the fully-upgraded Spanish Hussar stat chain, matching the golden run.
AUXILIARY_PROFILE_SPECS = {
    "scout_cavalry": {
        "civilization": "Spanish",
        "reference_slug": "hussar",
        "unit_name": "Scout Cavalry",
        "master": 448,
        "mode": "default",
    },
}


def default_mode(civilization: str, unit_slug: str) -> str:
    options = EXPORT_OPTIONS_BY_CIV_SLUG.get((civilization, unit_slug), {})
    return options.get("weapon_mode", "default")
