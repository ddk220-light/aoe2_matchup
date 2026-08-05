from types import SimpleNamespace

import pytest

from tools.simjs.collision_dat_audit import extract_unit_fields, resolve_standard_unit_ids


def test_standard_unit_ids_are_resolved_from_project_configuration():
    assert resolve_standard_unit_ids() == {
        "champion": 567,
        "halberdier": 359,
        "elite_fire_lancer": 1903,
        "hussar": 441,
        "paladin": 569,
        "heavy_camel": 330,
        "elite_elephant": 1134,
        "elite_steppe": 1372,
        "arbalester": 492,
        "imp_elite_skirm": 6,
        "heavy_cav_archer": 474,
        "siege_onager": 588,
        "heavy_scorpion": 542,
        "hand_cannoneer": 5,
    }


def test_extract_unit_fields_keeps_raw_collision_and_obstruction_values():
    unit = SimpleNamespace(
        name="HCANR",
        unit_class=44,
        speed=0.96,
        collision_size_x=0.2,
        collision_size_y=0.2,
        collision_size_z=2.0,
        clearance_size=(0.2, 0.2),
        outline_size_x=0.2,
        outline_size_y=0.2,
        outline_size_z=2.0,
        obstruction_type=5,
        obstruction_class=2,
        dead_fish=SimpleNamespace(
            min_collision_size_multiplier=0.8,
            old_size_class=0,
            old_move_algorithm=0,
            tracking_unit=-1,
            tracking_unit_mode=0,
            tracking_unit_density=0.0,
            turn_radius=0.0,
        ),
    )

    record = extract_unit_fields(5, unit)

    assert record["unit_id"] == 5
    assert record["collision_size_tiles"] == {"x": 0.2, "y": 0.2, "z": 2.0}
    assert record["min_collision_size_multiplier"] == 0.8
    assert record["nominal_collision_diameter_tiles"] == pytest.approx(0.4)
    assert record["multiplied_collision_diameter_tiles"] == pytest.approx(0.32)
    assert record["obstruction"] == {"type": 5, "class": 2}
