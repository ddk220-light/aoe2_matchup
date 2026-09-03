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
