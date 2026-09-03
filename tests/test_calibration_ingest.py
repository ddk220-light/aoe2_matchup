import json

import pytest

from aoe2x.calibration.paths import workspace_paths


def test_hp_cross_validation_rejects_wrong_civ():
    from aoe2x.calibration.ingest import validate_unit

    validate_unit("Burmese", "elite_elephant", observed_hp=320.0)
    with pytest.raises(Exception):
        validate_unit("Bengalis", "elite_elephant", observed_hp=999.0)


def test_attack_floor_clamps_to_minimum_one_damage():
    from aoe2x.calibration.ingest import _expected_hit_damage, validate_unit

    skirm_attacks = {
        "final_attacks_json": '{"27": 4, "15": 4, "3": 7, "28": 2, "35": 2, "21": 0, "17": 0}'
    }
    elephant_armors = {
        "final_armors_json": '{"5": 0, "4": 6, "8": 0, "3": 9, "31": 0}'
    }
    paladin_armors = {
        "final_armors_json": '{"4": 5, "8": 0, "3": 7, "31": 0}'
    }
    assert _expected_hit_damage(skirm_attacks, elephant_armors) == 1.0
    assert _expected_hit_damage(skirm_attacks, paladin_armors) == 1.0
    validate_unit(
        "Chinese",
        "imp_elite_skirm",
        observed_hp=35.0,
        opponent_civ="Burmese",
        opponent_slug="elite_elephant",
        modal_hit_damage=1.0,
    )
    validate_unit(
        "Chinese",
        "imp_elite_skirm",
        observed_hp=35.0,
        opponent_civ="Spanish",
        opponent_slug="paladin",
        modal_hit_damage=1.0,
    )


def test_trample_skips_naive_primary_hit_check():
    from aoe2x.calibration.ingest import validate_unit

    validate_unit(
        "Burmese",
        "elite_elephant",
        observed_hp=320.0,
        opponent_civ="Persians",
        opponent_slug="heavy_camel",
        modal_hit_damage=3.75,
    )


def test_find_decoded_dir_accepts_final_nested_layout(tmp_path):
    from aoe2x.calibration.ingest import _find_decoded_dir

    decoded = tmp_path / "standard_units" / "decoded"
    decoded.mkdir(parents=True)
    (decoded / "champion__vs__hussar.meta.json").touch()

    assert _find_decoded_dir(tmp_path) == decoded


def test_roster_builds_matchup_authority_without_old_fixture(tmp_path):
    from aoe2x.calibration.ingest import _load_roster_authority

    roster = tmp_path / "standard_units" / "ROSTER.txt"
    roster.parent.mkdir(parents=True)
    roster.write_text(
        "3 standard units\n\n"
        "  Champion                 Chinese/champion             melee\n"
        "  Heavy Cav Archer         Saracens/heavy_cav_archer    ranged\n"
        "  Paladin                  Spanish/paladin              melee\n",
        encoding="utf-8",
    )

    assert _load_roster_authority(tmp_path) == [
        {
            "civ1": "Chinese",
            "slug1": "champion",
            "label1": "Champion",
            "civ2": "Saracens",
            "slug2": "heavy_cav_archer",
            "label2": "Heavy Cav Archer",
        },
        {
            "civ1": "Chinese",
            "slug1": "champion",
            "label1": "Champion",
            "civ2": "Spanish",
            "slug2": "paladin",
            "label2": "Paladin",
        },
        {
            "civ1": "Saracens",
            "slug1": "heavy_cav_archer",
            "label1": "Heavy Cav Archer",
            "civ2": "Spanish",
            "slug2": "paladin",
            "label2": "Paladin",
        },
    ]


def test_matchup_identity_uses_authority_order_not_recording_direction():
    from aoe2x.calibration.ingest import _canonical_matchup_for_composition

    authority = [
        {
            "label1": "Champion",
            "civ1": "Chinese",
            "slug1": "champion",
            "label2": "Arbalester",
            "civ2": "Chinese",
            "slug2": "arbalester",
        }
    ]
    reverse_recording = {
        "side2": {"Arbalester": 30},
        "side1": {"Champion": 30},
    }

    assert (
        _canonical_matchup_for_composition(reverse_recording, authority)
        == "champion__vs__arbalester"
    )


def test_manifest_helpers_write_only_to_explicit_workspace(tmp_path):
    from aoe2x.calibration.ingest import _load_manifest, _save_manifest

    paths = workspace_paths(tmp_path / "calibration")
    expected = {"fights": [{"run_id": "synthetic"}]}

    _save_manifest(expected, paths)

    assert _load_manifest(paths) == expected
    assert json.loads(paths.manifest.read_text(encoding="utf-8")) == expected
