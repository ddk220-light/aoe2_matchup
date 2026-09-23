"""Focused exporter checks against the local, extracted patch candidate."""
from pathlib import Path

import pytest

from aoe2x.js_simulation.tools import export_unit_mechanics as exporter


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data/local/generated/patch-185872/aoe2_reference.db"
DAT = Path("D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat")


@pytest.mark.skipif(not REFERENCE.exists() or not DAT.exists(), reason="local patch source required")
def test_hearth_javelin_uses_charge_range_modifier():
    profile = exporter.export_unit_mechanics(REFERENCE, DAT, "elite_hearth_troop_saxons", "Saxons", 2706)
    assert profile["charge"]["attack_range_tiles"] == 9
    assert profile["charge"]["projectile_attacks"]["3"] == 11
    assert profile["charge"]["recharge_rate"] == pytest.approx(0.083)


@pytest.mark.skipif(not REFERENCE.exists() or not DAT.exists(), reason="local patch source required")
def test_jom_torch_preserves_building_ship_restriction():
    profile = exporter.export_unit_mechanics(REFERENCE, DAT, "elite_jomsviking_danes", "Danes", 2712)
    assert profile["charge"]["target_filter"] == "buildings_and_ships"
    assert profile["charge"]["attack_range_tiles"] == 3
    # Update185872 documents Smart Mode8: charge uses the carrier's own attack.
    assert profile["charge"]["projectile_attacks"] == profile["attack_classes"]
    assert profile["charge"].get("inherits_unit_attack") is True
    assert profile["unit_type"] == 70
    assert not profile["unit_traits"] & 2


def test_concrete_forms_use_the_candidate_extraction(tmp_path, monkeypatch):
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    calls = []

    class Analyzer:
        def calculate_form_stats(self, civ, master, age):
            calls.append((civ, master, age))
            return "candidate form stats"

    def factory(source):
        assert Path(source) == extracted
        return Analyzer()

    monkeypatch.setattr(exporter, "_unit_analyzer", factory)
    assert exporter._concrete_form_stats("Bulgarians", 1253, tmp_path / "candidate.db") == "candidate form stats"
    assert calls == [("Bulgarians", 1253, 4)]


@pytest.mark.skipif(not REFERENCE.exists() or not DAT.exists(), reason="local patch source required")
def test_vendel_legacy_activates_knight_flat_blast():
    import sqlite3
    with sqlite3.connect(REFERENCE) as connection:
        slug, master = connection.execute(
            "SELECT unit_slug,unit_master FROM ref_units WHERE civ_name='Varangians' "
            "AND unit_name='Cavalier' AND age='Imperial'"
        ).fetchone()
    profile = exporter.export_unit_mechanics(REFERENCE, DAT, slug, "Varangians", master)
    assert profile["blast"]["width_tiles"] == pytest.approx(0.5)
    assert profile["blast"]["damage_fraction"] == -5


@pytest.mark.skipif(not REFERENCE.exists() or not DAT.exists(), reason="local patch source required")
def test_hamask_exports_own_missing_health_attack_modifier():
    profile = exporter.export_unit_mechanics(REFERENCE, DAT, "elite_jomsviking_danes", "Danes", 2712)
    assert profile["effects"].get("missing_hp_attack_per_step") == 1
    assert profile["effects"].get("missing_hp_attack_step") == 0.1


@pytest.mark.skipif(not REFERENCE.exists() or not DAT.exists(), reason="local patch source required")
def test_shield_wall_exports_formation_rule():
    profile = exporter.export_unit_mechanics(REFERENCE, DAT, "elite_hearth_troop_saxons", "Saxons", 2706)
    assert profile.get("unit_class") == 6
    assert profile["effects"].get("nearby_infantry_armor_step") == 15
    assert profile["effects"].get("nearby_infantry_armor_max") == 3
    assert profile["effects"].get("nearby_infantry_armor_radius") == 7


@pytest.mark.skipif(not REFERENCE.exists() or not DAT.exists(), reason="local patch source required")
def test_gothikon_activates_researched_charge_with_two_separate_axes():
    profile = exporter.export_unit_mechanics(REFERENCE, DAT, "elite_varangian_guard", "Varangians", 2704)
    charge = profile["charge"]
    assert charge is not None
    assert charge["max_charge"] == 2
    assert charge["charge_cost"] == 1
    assert charge["recharge_rate"] == pytest.approx(1 / 30, abs=1e-7)
    assert charge["attack_range_tiles"] == 3
    assert charge["projectile_count"] == 1
    assert charge["inherits_unit_attack"] is True
    assert charge["projectile_attacks"] == profile["attack_classes"]
