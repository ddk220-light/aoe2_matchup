"""The patch audit must target the right rows without changing combat values."""

from dataclasses import dataclass
import json
import sqlite3
from types import SimpleNamespace as NS


@dataclass
class Command:
    type: int
    a: int
    b: int
    c: int
    d: float


@dataclass
class Task:
    action_type: int = 151
    resource_multiplier: int = 297
    resource_out: int = 3
    work_value_1: float = 0.015909
    class_id: int = 6


@dataclass
class ProjectileCombat:
    attacks: tuple = ()


@dataclass
class Projectile:
    smart_mode: int = 9


@dataclass
class ResearchCost:
    type: int
    amount: int
    flag: int


@dataclass
class ResearchLocation:
    location_id: int = 82
    research_time: int = 60
    button_id: int = 7
    hot_key_id: int = 0


def fixture_dat():
    techs = [NS(civ=-1, effect_id=-1, required_techs=[]) for _ in range(1500)]
    effects = [NS(name="", effect_commands=[]) for _ in range(1500)]
    for tid, civ, age, name, commands in [
        (1464, 60, 103, "Shield Wall", [Command(1, 33, 0, -1, 31)]),
        (1469, 60, None, "Foot Soldiers Discount", [Command(0, 82, -1, 66, 2716)]),
        (1484, 62, 102, "Hamask", [Command(1, 33, 0, -1, 30)]),
        (1488, 61, None, "VG gold", [Command(6, 297, -1, -1, 1.3333)]),
        (1483, 62, 103, "Northmen's Fury", [Command(5, -1, 13, 9, 2956)]),
        (1474, 61, 103, "Gothikon", [Command(0, 2704, -1, 125, 2710)]),
    ]:
        techs[tid] = NS(civ=civ, name=name, effect_id=tid,
                        required_techs=[age] if age else [],
                        resource_costs=(ResearchCost(0, 250, 1), ResearchCost(3, 450, 1),
                                        ResearchCost(-1, 0, 0)),
                        research_locations=[ResearchLocation()])
        effects[tid] = NS(name=name, effect_commands=commands)
    units = [None] * 2721
    units[2704] = NS(
        id=2704, name="Elite Varangian Guard", class_=6,
        creatable=NS(max_charge=0.0, recharge_rate=0.0, charge_event=0,
                     charge_type=0, charge_target=127, charge_projectile_unit=-1,
                     total_projectiles=0, max_total_projectiles=1),
        bird=NS(tasks=[Task()]), type_50=NS(projectile_unit_id=-1),
    )
    units[2710] = NS(name="Projectile Gothikon", speed=7,
                     type_50=ProjectileCombat(), projectile=Projectile())
    resources = [0.0] * 552
    resources[297] = 50.0
    civs = [NS(name="Unused", units=units, resources=resources,
               team_bonus_id=-1, tech_tree_id=-1) for _ in range(63)]
    for cid, name in [(60, "Saxons"), (61, "Varangians"), (62, "Danes")]:
        civs[cid] = NS(name=name, units=units, resources=resources,
                      team_bonus_id=-1, tech_tree_id=-1)
    return NS(version="VER 8.8", techs=techs, effects=effects, civs=civs)


def reference_db(tmp_path):
    path = tmp_path / "reference.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE ref_units (id INTEGER PRIMARY KEY, civ_name TEXT,
                unit_master INTEGER, unit_slug TEXT, unit_class INTEGER,
                age TEXT, final_attack REAL, final_cost_gold REAL);
            CREATE TABLE ref_special_effects (ref_unit_id INTEGER,
                property_name TEXT, property_value TEXT, source TEXT, description TEXT);
            CREATE TABLE ref_techs_applied (ref_unit_id INTEGER, tech_id INTEGER);
        """)
        db.executemany("INSERT INTO ref_units VALUES (?,?,?,?,?,?,?,?)", [
            (1, "Danes", 2704, "elite_varangian_guard", 6, "Imperial", 17, 45),
            (2, "Saxons", 2704, "elite_varangian_guard", 6, "Imperial", 17, 45),
            (3, "Saxons", 2703, "varangian_guard", 6, "Castle", 13, 45),
            (4, "Saxons", 2701, "heavy_mounted_crossbowman", 36, "Imperial", 8, 65),
            (5, "Varangians", 2704, "elite_varangian_guard", 6, "Imperial", 17, 45),
            (6, "Danes", 588, "siege_onager", 13, "Imperial", 75, 135),
        ])
        db.execute("INSERT INTO ref_special_effects VALUES (1,'hp_regen','0','existing','keep')")
    return path


def test_conditional_effects_match_civ_class_and_age_without_mutating_stats(tmp_path, monkeypatch):
    # Catches resource-only effects being omitted or attached to cavalry/wrong ages.
    from aoe2x.dbgen import patch185872_effects as recorder

    path = reference_db(tmp_path)
    monkeypatch.setattr(recorder, "_parsed_dat", lambda _: fixture_dat())
    summary = recorder.record_patch_effects(path, tmp_path / "source.dat")
    with sqlite3.connect(path) as db:
        def ids(property_name):
            return [row[0] for row in db.execute(
                "SELECT ref_unit_id FROM ref_special_effects WHERE property_name=? ORDER BY 1",
                (property_name,))]
        assert ids("patch185872:Hamask_json") == [1]
        assert ids("patch185872:Shield Wall_json") == [2]
        assert ids("patch185872:Foot soldier discount_json") == [2, 3]
        assert db.execute("SELECT final_attack,final_cost_gold FROM ref_units WHERE id=2").fetchone() == (17, 45)
        assert ids("hp_regen") == [1]
    assert summary["stat_policy"]["saxon_controlled_town_centers"] is None
    assert summary["stat_policy"]["saxon_controlled_castles"] is None
    assert {m["tech_id"] for m in summary["mechanics"]} >= {1464, 1469, 1484}
    json.dumps(summary)


def test_raw_gold_and_unsigned_multiplier_evidence_survives_recording(tmp_path, monkeypatch):
    # Catches flattening unresolved evidence into a scalar or multiplying a signed byte.
    from aoe2x.dbgen import patch185872_effects as recorder

    path = reference_db(tmp_path)
    monkeypatch.setattr(recorder, "_parsed_dat", lambda _: fixture_dat())
    summary = recorder.record_patch_effects(path, tmp_path / "source.dat")
    hamask = next(m for m in summary["mechanics"] if m["tech_id"] == 1484)
    assert hamask["resource_costs"] == [
        {"type": 0, "amount": 250, "flag": 1},
        {"type": 3, "amount": 450, "flag": 1},
        {"type": -1, "amount": 0, "flag": 0},
    ]
    assert hamask["research_time"] == 60
    assert hamask["research_locations"] == [
        {"location_id": 82, "research_time": 60, "button_id": 7, "hot_key_id": 0},
    ]
    gold = next(m for m in summary["mechanics"] if m["tech_id"] == 1488)
    assert gold["commands"][0]["d"] == 1.3333
    assert gold["resource_evidence"]["297"] == 50
    assert gold["discrepancy"]["tooltip_multiplier"] == 1.5
    fury = next(m for m in summary["mechanics"] if m["tech_id"] == 1483)
    assert fury["attack_multipliers"] == [{"armor_class": 11, "percent": 140, "multiplier": 1.4}]
    gothikon = next(m for m in summary["mechanics"] if m["tech_id"] == 1474)
    assert gothikon["projectile_evidence"][0]["unit_id"] == 2710
    assert gothikon["projectile_evidence"][0]["projectile"]["smart_mode"] == 9
    with sqlite3.connect(path) as db:
        payload = json.loads(db.execute("""SELECT property_value FROM ref_special_effects
            WHERE ref_unit_id=5 AND property_name='patch185872:unit-mechanics_json'""").fetchone()[0])
        assert payload["charge"]["charge_target"] == 127
        assert payload["tasks"][0]["resource_multiplier"] == 297
        assert payload["runtime_status"] == "validation_pending"
        before = db.execute("SELECT count(*) FROM ref_special_effects").fetchone()[0]
    recorder.record_patch_effects(path, tmp_path / "source.dat")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM ref_special_effects").fetchone()[0] == before
