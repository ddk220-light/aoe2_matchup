"""Patch data checks: real extraction/analyzer behavior, no simulations."""
import json
import hashlib
import sqlite3
import pytest
from pathlib import Path

from aoe2x.extract import extract_effects
from aoe2x.dbgen.unit_analyzer import UnitAnalyzer, UnitStats


def test_resolved_tree_excludes_disabled_unit_and_upgrade_tech():
    civ = {"name": "Vikings", "disabled_techs": [], "disabled_units": []}
    tree = {"civ_techs_units": [
        {"Use Type": "Unit", "Node ID": 2700, "Name": "Mounted Crossbowman",
         "Node Status": "ResearchedCompleted"},
        {"Use Type": "Unit", "Node ID": 2701, "Name": "Heavy Mounted Crossbowman",
         "Node Status": "NotAvailable", "Trigger Tech ID": 1451},
        {"Use Type": "Unit", "Node ID": 39, "Name": "Cavalry Archer",
         "Node Status": "NotAvailable"},
        {"Use Type": "Tech", "Node ID": 875, "Name": "Gambesons",
         "Node Status": "NotAvailable"},
    ]}
    extract_effects.apply_resolved_tech_tree(civ, tree)
    assert civ["resolved_units"]["2700"]["available"] is True
    assert civ["resolved_units"]["39"]["available"] is False
    assert {t["id"] for t in civ["disabled_techs"]} == {1451, 875}


def make_analyzer(tmp_path):
    units = [{"id": uid, "name": name, "hit_points": 50, "class": 36,
              "speed": 1, "attacks": [{"class": 3, "amount": 6}],
              "armors": [], "cost": {"wood": 45, "gold": 60}}
             for uid, name in [(39, "Cavalry Archer"), (2700, "Mounted Crossbowman"),
                               (2701, "Heavy Mounted Crossbowman")]]
    values = {
        "units": units, "technologies": [], "effects": [], "tech_effects": [],
        "civilizations": [{"name": "Vikings", "id": 11}],
        "civ_tech_trees": [{"name": "Vikings", "disabled_techs": [],
            "resolved_units": {"39": {"available": False},
                "2700": {"available": True}, "2701": {"available": False}}}],
    }
    for name, value in values.items():
        (tmp_path / (name + ".json")).write_text(json.dumps(value))
    return UnitAnalyzer(tmp_path)


def test_replaced_cavalry_archer_is_not_available(tmp_path):
    analyzer = make_analyzer(tmp_path)
    result = analyzer.calculate_unit_stats_for_civ("Vikings", {
        "base_id": 39, "display_name": "Cavalry Archer", "unit_class": 36,
        "availability_tech": None, "upgrades": []}, 4)
    assert result["has_unit"] is False


def test_regional_unit_keeps_base_tier_when_heavy_is_missing(tmp_path):
    analyzer = make_analyzer(tmp_path)
    result = analyzer.calculate_unit_stats_for_civ("Vikings", {
        "base_id": 2700, "display_name": "Mounted Crossbowman", "unit_class": 36,
        "availability_tech": None, "upgrades": [(1451, 2701, "Heavy Mounted Crossbowman")]}, 4)
    assert result["has_unit"] is True
    assert result["unit_id"] == 2700


def test_northmens_fury_multiplies_building_attack_by_positive_140_percent():
    analyzer = UnitAnalyzer.__new__(UnitAnalyzer)
    stats = UnitStats(attacks={11: 50})
    analyzer._multiply_attribute(stats, 9, 11 * 256 + 140)
    assert stats.attacks[11] == 70


def test_main_db_can_be_generated_at_explicit_candidate_path(tmp_path):
    from aoe2x.dbgen.generate_main_db import generate_main_database
    source = Path(__file__).parents[1] / "data/golden/aoe2_reference.db"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    candidate = tmp_path / "candidate.db"
    generate_main_database(reference_db=source, output_db=candidate)
    with sqlite3.connect(candidate) as conn, sqlite3.connect(source) as ref:
        assert conn.execute("select count(*) from unit_stats where has_unit=1").fetchone() == ref.execute("select count(*) from ref_units").fetchone()
        assert conn.execute("select count(*) from armor_classes").fetchone()[0] > 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_melee_forging_does_not_raise_pierce_weapon_displayed_attack():
    analyzer = UnitAnalyzer.__new__(UnitAnalyzer)
    stats = UnitStats(attack=8, attacks={3: 8})
    analyzer._add_attribute(stats, 9, 4 * 256 + 1)
    assert stats.attack == 8
    assert stats.attacks == {3: 8}


@pytest.fixture
def patch_analyzer():
    extracted = Path(__file__).parents[1] / "data/local/generated/patch-185872/extracted"
    if not (extracted / "units.json").is_file():
        pytest.skip("requires local build185872 extraction")
    return UnitAnalyzer(extracted)


def test_war_chariot_uses_playable_master_and_patch_cost(patch_analyzer):
    from aoe2x.dbgen.config_units import UNIQUE_UNITS
    config = next(c for c in UNIQUE_UNITS["Shu"] if c["display_name"] == "War Chariot")
    result = patch_analyzer.calculate_unit_stats_for_civ("Shu", config, 4)
    assert result["stats"].cost_food == 75
    assert result["stats"].cost_gold == 90
    assert patch_analyzer.get_unit(result["unit_id"])["train_time"] == 32
    assert result["stats"].attack == 9


def test_teutonic_knight_bonus_reassignment_has_no_net_armor_change(patch_analyzer):
    stats = patch_analyzer.calculate_form_stats("Teutons", 554, 4)
    assert patch_analyzer.get_base_stats(patch_analyzer.get_unit(554)).melee_armor == 8
    assert stats.melee_armor == 13


def test_vietnamese_hp_bonus_no_longer_applies_to_mounted_archers(patch_analyzer):
    assert patch_analyzer.calculate_form_stats("Vietnamese", 474, 4).hp == 80
    assert patch_analyzer.calculate_form_stats("Vietnamese", 1131, 4).hp == 48


def test_rocket_cart_replacement_survives_mangonel_tree_exclusion(patch_analyzer):
    from aoe2x.dbgen.config_units import IMPERIAL_UNITS
    result = patch_analyzer.calculate_unit_stats_for_civ("Chinese", IMPERIAL_UNITS["siege_onager"], 4)
    assert result["has_unit"] is True
    assert result["unit_name"] == "Heavy Rocket Cart"


def test_new_civ_self_team_bonuses_are_applied(patch_analyzer):
    from aoe2x.dbgen.config_units import IMPERIAL_UNITS
    dane = patch_analyzer.calculate_unit_stats_for_civ("Danes", IMPERIAL_UNITS["siege_onager"], 4)
    varangian = patch_analyzer.calculate_unit_stats_for_civ("Varangians", IMPERIAL_UNITS["paladin"], 4)
    assert dane["stats"].los == 14
    assert varangian["stats"].attacks[1] == 1


def test_resource_selector_unique_techs_are_not_lost_from_upgrade_audit(patch_analyzer):
    danes = patch_analyzer.get_unique_techs_for_unit("Danes", 2712, 6, 4)
    saxons = patch_analyzer.get_unique_techs_for_unit("Saxons", 2706, 6, 4)
    assert any(t["tech_id"] == 1484 and t.get("conditional_description") for t in danes)
    assert any(t["tech_id"] == 1464 and t.get("conditional_description") for t in saxons)
    assert not any(t["tech_id"] == 1484 for t in patch_analyzer.get_unique_techs_for_unit("Danes", 283, 12, 4))


def test_patch_diff_separates_reassigned_bonus_from_actual_change(tmp_path):
    from aoe2x.dbgen.prepare_patch185872 import compare_references
    paths = [tmp_path / "old.db", tmp_path / "new.db"]
    for path, base, final in [(paths[0], 10, 13), (paths[1], 8, 13)]:
        with sqlite3.connect(path) as conn:
            conn.execute("create table ref_units(id integer, civ_name text, unit_slug text, age text, base_melee_armor real, final_melee_armor real)")
            conn.execute("insert into ref_units values(1,'Teutons','elite_teutonic_knight_teutons','Imperial',?,?)", (base, final))
    result = compare_references(*paths)
    assert result["added"] == []
    assert result["removed"] == []
    assert result["changed"][0]["changes"] == {"base_melee_armor": {"before": 10, "after": 8}}
    assert result["changed"][0]["unchanged_final_stats"] == ["melee_armor"]


def test_extraction_reads_tech_research_time_from_research_location():
    from types import SimpleNamespace
    from aoe2x.extract.extract_techs import extract_tech_data
    tech = SimpleNamespace(name="Shield Wall", research_locations=[
        SimpleNamespace(location_id=82, research_time=80)], resource_costs=[])
    assert extract_tech_data(tech)["research_time"] == 80
