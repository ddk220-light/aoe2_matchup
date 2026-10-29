"""Patch-specific unit changes, including upgrade preservation and atomicity."""
import json
from pathlib import Path
import shutil
import sqlite3
import pytest
from aoe2x.dbgen.patch188329_stats import patch_base_unit, migrate
from aoe2x.dbgen.unit_analyzer import UnitAnalyzer

GOLDEN = Path(__file__).parents[1] / "data/golden"
FILES = ("aoe2_reference_simulation.db", "aoe2_reference.db", "aoe2_units.db")


def test_raw_overlay_precedes_upgrades_and_leaves_elite_bolas_unchanged():
    analyzer = UnitAnalyzer.__new__(UnitAnalyzer)
    for master, old, new in [(873, 230, 220), (875, 280, 270)]:
        raw = {"id": master, "hit_points": old, "cost": {"food": 60, "gold": 80}}
        stats = analyzer.get_base_stats(raw)
        assert (stats.hp, stats.cost_food, stats.cost_gold) == (new, 70, 80)
        assert raw["hit_points"] == old
        assert patch_base_unit(patch_base_unit(raw)) == patch_base_unit(raw)
    assert analyzer.get_base_stats({"id": 2569, "speed": 1.5}).speed == 1.45
    assert analyzer.get_base_stats({"id": 2571, "speed": 1.5}).speed == 1.5


def test_shipped_stats_profiles_and_flat_table_match():
    for filename in FILES[:2]:
        with sqlite3.connect(GOLDEN / filename) as c:
            rows = c.execute("SELECT u.civ_name,u.final_hp,u.final_cost_food,m.mechanics_json "
                "FROM ref_units u JOIN ref_unit_mechanics m ON m.ref_unit_id=u.id WHERE u.unit_master=875").fetchall()
            assert len(rows) == 3
            for civ, hp, food, encoded in rows:
                assert hp == (270 if civ == "Dravidians" else 290)
                assert food == (52 if civ == "Gurjaras" else 70)
                p = json.loads(encoded)
                assert (p["hp"], p["cost"]["food"], p["cost"]["gold"]) == (hp, food, 80)
                assert p["balance_overrides"][0]["build"] == 188329
            assert c.execute("SELECT final_speed FROM ref_units WHERE unit_master=2571").fetchone()[0] == 1.5
    with sqlite3.connect(GOLDEN / FILES[2]) as c:
        assert c.execute("SELECT hp,cost_food FROM unit_stats WHERE unit_name='Elite Elephant Archer' AND has_unit=1 ORDER BY hp,cost_food").fetchall() == [(270, 70), (290, 52), (290, 70)]


def test_migration_is_idempotent_and_rolls_back_all_attached_databases(tmp_path):
    from aoe2x.dbgen.v3_mechanics import canonical_json, mechanics_hash
    for filename in FILES:
        shutil.copyfile(GOLDEN / filename, tmp_path / filename)
    assert migrate(tmp_path) == []
    with sqlite3.connect(tmp_path / FILES[0]) as c:
        ref_id = c.execute("SELECT id FROM ref_units WHERE civ_name='Bengalis' AND unit_master=875").fetchone()[0]
        c.execute("UPDATE ref_units SET base_hp=280,final_hp=300,base_cost_food=60,final_cost_food=60 WHERE id=?", (ref_id,))
        c.execute("UPDATE ref_stat_chain SET hp=hp+10,cost_food=60 WHERE ref_unit_id=?", (ref_id,))
        mode, encoded = c.execute("SELECT mode,mechanics_json FROM ref_unit_mechanics WHERE ref_unit_id=?", (ref_id,)).fetchone()
        p = json.loads(encoded); p['hp'] = 300; p['cost']['food'] = 60
        c.execute("UPDATE ref_unit_mechanics SET mechanics_json=?,mechanics_hash=? WHERE ref_unit_id=? AND mode=?",
                  (canonical_json(p), mechanics_hash(p), ref_id, mode))
    with sqlite3.connect(tmp_path / FILES[1]) as c:
        c.execute("UPDATE ref_units SET base_hp=279,base_cost_food=60 WHERE civ_name='Bengalis' AND unit_master=875")
    before = [(tmp_path / name).read_bytes() for name in FILES]
    with pytest.raises(ValueError, match="baseline"):
        migrate(tmp_path)
    assert [(tmp_path / name).read_bytes() for name in FILES] == before


def test_sim_api_serves_updated_elephant_archer(client):
    response = client.get('/api/ref/combat-unit/Bengalis/elite_ele_archer')
    assert response.status_code == 200
    assert response.json['mechanics']['hp'] == 290
    assert response.json['mechanics']['cost']['food'] == 70
