"""Build-185872 registrations exercised through reference generation."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from aoe2x.dbgen.config_constants import ORIGINAL_13_CIVS
from aoe2x.dbgen.generate_reference import generate_reference_database
from aoe2x.dbgen.unit_analyzer import UnitAnalyzer
from aoe2x.extract.extract_constants import CIV_NAMES
from aoe2x.extract.extract_units import extract_unit_data


@pytest.fixture(scope="module")
def roster_db(tmp_path_factory):
    """Real registrations and writer; only Bearded Axe adds a stat effect."""
    directory = tmp_path_factory.mktemp("patch185872-roster")
    units = [
        {"id": unit_id, "name": name, "class": unit_class,
         "hit_points": hp, "range": range_value, "attacks": [], "armors": []}
        for unit_id, name, unit_class, hp, range_value in [
            (38, "Knight", 12, 100, 0),
            (283, "Cavalier", 12, 120, 0),
            (569, "Paladin", 12, 160, 0),
            (250, "Longship", 22, 130, 6),
            (533, "Elite Longship", 22, 160, 7),
            (2633, "Catapult Galleon", 22, 150, 13),
            (281, "Throwing Axeman", 6, 60, 3),
            (531, "Elite Throwing Axeman", 6, 70, 4),
            (2700, "Mounted Crossbowman", 36, 45, 4),
            (2701, "Heavy Mounted Crossbowman", 36, 55, 4),
            (2703, "Varangian Guard", 6, 70, 0),
            (2704, "Elite Varangian Guard", 6, 80, 0),
            (2705, "Hearth Troop", 6, 75, 0),
            (2706, "Elite Hearth Troop", 6, 85, 0),
            (2708, "Jarl", 12, 65, 0),
            (2709, "Elite Jarl", 12, 75, 0),
            (2711, "Jomsviking", 6, 70, 0),
            (2712, "Elite Jomsviking", 6, 75, 0),
        ]
    ]
    techs = [
        {"id": tech_id, "name": f"Upgrade {tech_id}", "civ": -1,
         "required_techs": [103], "research_location": 82, "cost": {"food": 100}}
        for tech_id in (209, 265, 372, 531, 1451, 1454, 1462, 1472, 1482)
    ]
    techs += [
        {"id": tech_id, "name": name, "civ": 2, "required_techs": [103],
         "research_location": 82, "cost": {"food": 100}}
        for tech_id, name in [(83, "Bearded Axe (removed)"), (1496, "Bearded Axe")]
    ]
    payloads = {
        "units": units,
        "technologies": techs,
        "civilizations": [{"id": i, "name": name} for i, name in enumerate(CIV_NAMES) if name],
        "civ_tech_trees": [{"name": name, "disabled_techs": []} for name in ORIGINAL_13_CIVS],
        "effects": [],
        "tech_effects": [
            {"tech_id": tech_id, "commands": [{"type": 4, "a": 531, "b": -1, "c": 12, "d": 1}]}
            for tech_id in (83, 1496)
        ],
    }
    for filename, payload in payloads.items():
        (directory / f"{filename}.json").write_text(json.dumps(payload), encoding="utf-8")
    path = directory / "roster.db"
    generate_reference_database(UnitAnalyzer(directory), ref_db_path=path)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def test_mounted_crossbowmen_emit_only_source_civilizations_and_upgrade_tiers(roster_db):
    rows = roster_db.execute(
        "SELECT civ_name, unit_master FROM ref_units WHERE unit_slug = 'heavy_mounted_crossbowman'"
    ).fetchall()
    assert {row["civ_name"]: row["unit_master"] for row in rows} == {
        "Bohemians": 2700, "Britons": 2701, "Burgundians": 2700,
        "Celts": 2701, "Danes": 2701, "Franks": 2701, "Italians": 2700,
        "Poles": 2701, "Portuguese": 2700, "Saxons": 2701,
        "Sicilians": 2701, "Spanish": 2701, "Teutons": 2701,
        "Varangians": 2701, "Vikings": 2700,
    }


def test_varangian_guards_emit_for_all_five_source_civilizations(roster_db):
    rows = roster_db.execute(
        "SELECT civ_name, unit_master, unit_class FROM ref_units WHERE unit_slug = 'elite_varangian_guard'"
    ).fetchall()
    assert {(row["civ_name"], row["unit_master"], row["unit_class"]) for row in rows} == {
        ("Byzantines", 2704, 6), ("Danes", 2704, 6), ("Saxons", 2704, 6),
        ("Varangians", 2704, 6), ("Vikings", 2704, 6),
    }


@pytest.mark.parametrize("civ,slug,unit_id,unit_class,hp", [
    ("Saxons", "elite_hearth_troop_saxons", 2706, 6, 85),
    ("Varangians", "elite_jarl_varangians", 2709, 12, 75),
    ("Danes", "elite_jomsviking_danes", 2712, 6, 75),
])
def test_new_unique_units_use_the_source_elite_form(roster_db, civ, slug, unit_id, unit_class, hp):
    row = roster_db.execute(
        "SELECT unit_master, unit_class, base_hp FROM ref_units WHERE civ_name = ? AND unit_slug = ?",
        (civ, slug),
    ).fetchone()
    assert row is not None
    assert tuple(row) == (unit_id, unit_class, hp)


def test_new_civilizations_keep_the_knight_line(roster_db):
    rows = roster_db.execute(
        "SELECT civ_name FROM ref_units WHERE unit_slug = 'paladin' AND civ_name IN ('Danes', 'Saxons', 'Varangians')"
    ).fetchall()
    assert {row[0] for row in rows} == {"Danes", "Saxons", "Varangians"}


def test_longships_emit_for_four_civilizations_without_renaming_vikings_identity(roster_db):
    rows = roster_db.execute(
        "SELECT civ_name, unit_slug, unit_name FROM ref_units WHERE unit_master = 533"
    ).fetchall()
    assert {tuple(row) for row in rows} == {
        ("Vikings", "elite_longboat_vikings", "Elite Longship"),
        ("Danes", "elite_longship_danes", "Elite Longship"),
        ("Saxons", "elite_longship_saxons", "Elite Longship"),
        ("Varangians", "elite_longship_varangians", "Elite Longship"),
    }


def test_catapult_galleons_emit_for_the_source_roster(roster_db):
    rows = roster_db.execute("SELECT civ_name FROM ref_units WHERE unit_master = 2633").fetchall()
    assert {row[0] for row in rows} == {
        "Aztecs", "Cumans", "Danes", "Incas", "Mapuche", "Mayans", "Muisca",
        "Saxons", "Tupi", "Varangians", "Vikings",
    }


def test_replaced_bearded_axe_does_not_double_axeman_range(roster_db):
    row = roster_db.execute(
        "SELECT final_range FROM ref_units WHERE unit_slug = 'elite_throwing_axeman_franks'"
    ).fetchone()
    assert row[0] == 5


@pytest.mark.parametrize("unit_id,name", [(250, "Longship"), (533, "Elite Longship")])
def test_extraction_uses_current_longship_names(unit_id, name):
    unit = SimpleNamespace(id=unit_id, type=70, class_=22, name="LONGSHIP")
    assert extract_unit_data(unit)["name"] == name
