"""Regression coverage for the three Thunderclap Bombs unit families."""

from aoe2x.js_simulation.tools.export_unit_mechanics import (
    CURATED_CIV_RUNTIME_EFFECTS,
)


def test_thunderclap_bombs_covers_only_the_affected_jurchen_families():
    assert set(CURATED_CIV_RUNTIME_EFFECTS) == {
        ("Jurchens", "grenadier_jurchens"),
        ("Jurchens", "mangonel"),
        ("Jurchens", "siege_onager"),
        ("Jurchens", "lou_chuan_jurchens"),
    }


def test_thunderclap_bombs_family_payloads_are_not_interchangeable():
    grenadier = CURATED_CIV_RUNTIME_EFFECTS[("Jurchens", "grenadier_jurchens")]
    rocket_cart = CURATED_CIV_RUNTIME_EFFECTS[("Jurchens", "mangonel")]
    heavy_rocket_cart = CURATED_CIV_RUNTIME_EFFECTS[("Jurchens", "siege_onager")]
    lou_chuan = CURATED_CIV_RUNTIME_EFFECTS[("Jurchens", "lou_chuan_jurchens")]

    assert grenadier == {
        "delayed_impact_melee_attack": 4.0,
        "delayed_impact_radius_tiles": 0.65,
        "delayed_impact_delay_seconds": 1.5,
        "delayed_impact_repeat_count": 3,
        "delayed_impact_repeat_interval_seconds": 1.5,
        "death_explosion_melee_attack": 15.0,
        "death_explosion_radius_tiles": 0.75,
    }
    expected_rocket_cart = {
        "delayed_impact_melee_attack": 4.0,
        "delayed_impact_radius_tiles": 1.25,
        "delayed_impact_delay_seconds": 2.0,
        "delayed_impact_repeat_count": 1,
        "delayed_impact_repeat_interval_seconds": 2.0,
        "death_explosion_melee_attack": 15.0,
        "death_explosion_radius_tiles": 1.0,
    }
    assert rocket_cart == expected_rocket_cart
    assert heavy_rocket_cart == expected_rocket_cart
    assert lou_chuan == {
        "delayed_impact_weapon_mode": "trebuchet",
        "delayed_impact_melee_attack": 20.0,
        "delayed_impact_radius_tiles": 2.0,
        "delayed_impact_delay_seconds": 2.0,
        "delayed_impact_repeat_count": 1,
        "delayed_impact_repeat_interval_seconds": 2.0,
        "death_explosion_melee_attack": 45.0,
        "death_explosion_radius_tiles": 2.0,
    }
