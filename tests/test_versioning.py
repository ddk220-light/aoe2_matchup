# tests/test_versioning.py
import importlib
import os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import derived_db


def test_battle_scores_schema_has_build_number(tmp_path):
    db = str(tmp_path / "derived.db")
    conn = derived_db.create_db(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(battle_scores)")}
    assert "build_number" in cols
    # UNIQUE must include build_number so two builds can coexist for one unit
    conn.execute(
        "INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,score_type,"
        "score_value,rank,median_delta,build_number) VALUES "
        "('knight','imperial','Franks','knight','stable_effectiveness',90.0,1,5.0,'170934')"
    )
    conn.execute(
        "INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,score_type,"
        "score_value,rank,median_delta,build_number) VALUES "
        "('knight','imperial','Franks','knight','stable_effectiveness',88.0,2,3.0,'177723')"
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM battle_scores WHERE civ_name='Franks' "
                     "AND unit_slug='knight'").fetchone()[0]
    assert n == 2
    conn.close()


import pool_scores_db


def _pool_row(civ, build, score):
    return dict(civ_name=civ, unit_slug="knight", pool="stable", scale="30v30",
                axis="hp", final_score=score, gc=None, ac=None, at=None, aa=None,
                n=10, mean=score, stddev=1.0, win_rate=0.5, decisive_win_rate=0.3,
                big_win_rate=0.2, catastrophic_loss_rate=0.1, sim_version="x",
                derived_at="2026-06-06", role_line_means=None, build_number=build)


def test_pool_scores_build_number(tmp_path):
    db = str(tmp_path / "pool.db")
    conn = pool_scores_db.create_db(db)
    pool_scores_db.insert_score(conn, _pool_row("Franks", "170934", 90.0))
    pool_scores_db.insert_score(conn, _pool_row("Franks", "177723", 85.0))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM pool_scores WHERE civ_name='Franks' "
                     "AND unit_slug='knight' AND scale='30v30' AND axis='hp'").fetchone()[0]
    assert n == 2
    conn.close()


def test_power_units_path_for_build(monkeypatch, tmp_path):
    import best_units
    importlib.reload(best_units)
    monkeypatch.setattr(best_units, "POWER_UNITS_DIR", str(tmp_path / "cpu"))
    p = best_units.power_units_path("177723")
    assert p.endswith(os.path.join("cpu", "177723.json"))


def test_load_civ_power_units_fallback_chain(monkeypatch, tmp_path):
    import json
    import best_units
    importlib.reload(best_units)
    cpu_dir = str(tmp_path / "cpu")
    legacy = str(tmp_path / "legacy.json")
    monkeypatch.setattr(best_units, "POWER_UNITS_DIR", cpu_dir)
    monkeypatch.setattr(best_units, "POWER_UNITS_PATH", legacy)
    # neither present -> None
    assert best_units.load_civ_power_units(build_number="177723") is None
    # only legacy present -> legacy
    with open(legacy, "w") as f:
        json.dump({"src": "legacy"}, f)
    assert best_units.load_civ_power_units(build_number="177723") == {"src": "legacy"}
    # per-build present -> per-build wins over legacy
    os.makedirs(cpu_dir, exist_ok=True)
    with open(best_units.power_units_path("177723"), "w") as f:
        json.dump({"src": "perbuild"}, f)
    assert best_units.load_civ_power_units(build_number="177723") == {"src": "perbuild"}
