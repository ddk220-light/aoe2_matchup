# tests/test_versioning.py
import importlib
import os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
from aoe2x.rank import derived_db


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


from aoe2x.rank import pool_scores_db


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
    from aoe2x.advisor import best_units
    importlib.reload(best_units)
    monkeypatch.setattr(best_units, "POWER_UNITS_DIR", str(tmp_path / "cpu"))
    p = best_units.power_units_path("177723")
    assert p.endswith(os.path.join("cpu", "177723.json"))


def test_load_civ_power_units_per_build_only(monkeypatch, tmp_path):
    """Per-build file or nothing — the legacy flat-file fallback was removed."""
    import json
    from aoe2x.advisor import best_units
    importlib.reload(best_units)
    cpu_dir = str(tmp_path / "cpu")
    monkeypatch.setattr(best_units, "POWER_UNITS_DIR", cpu_dir)
    # per-build file missing -> None (no silent fallback to stale data)
    assert best_units.load_civ_power_units(build_number="177723") is None
    # the legacy flat-file hook is gone entirely
    assert not hasattr(best_units, "POWER_UNITS_PATH")
    # per-build present -> loaded
    os.makedirs(cpu_dir, exist_ok=True)
    with open(best_units.power_units_path("177723"), "w") as f:
        json.dump({"src": "perbuild"}, f)
    assert best_units.load_civ_power_units(build_number="177723") == {"src": "perbuild"}


def test_migrate_baseline_tags_and_rebuilds(tmp_path, monkeypatch):
    # Build OLD-schema derived_data.db (no build_number, old UNIQUE)
    import sqlite3, json
    dd = str(tmp_path / "derived_data.db")
    c = sqlite3.connect(dd)
    c.executescript("""
        CREATE TABLE battle_scores (id INTEGER PRIMARY KEY, line_slug TEXT, age TEXT,
          civ_name TEXT, unit_slug TEXT, score_type TEXT, score_value REAL,
          rank INTEGER, median_delta REAL,
          UNIQUE(line_slug,age,civ_name,unit_slug,score_type));
    """)
    c.execute("INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,score_type,"
              "score_value,rank,median_delta) VALUES "
              "('naval','imperial','Britons','galleon','naval_effectiveness',70,1,2)")
    c.commit(); c.close()

    ps = str(tmp_path / "pool_scores.db")
    c = sqlite3.connect(ps)
    c.executescript("""
        CREATE TABLE pool_scores (civ_name TEXT, unit_slug TEXT, pool TEXT, scale TEXT,
          axis TEXT, final_score REAL, gc REAL, ac REAL, at REAL, aa REAL, n INTEGER,
          mean REAL, stddev REAL, win_rate REAL, decisive_win_rate REAL,
          big_win_rate REAL, catastrophic_loss_rate REAL, sim_version TEXT,
          derived_at TEXT, role_line_means TEXT,
          PRIMARY KEY (civ_name,unit_slug,scale,axis));
    """)
    c.execute("INSERT INTO pool_scores VALUES ('Franks','knight','stable','30v30','hp',"
              "90,1,1,1,1,10,90,1,0.5,0.3,0.2,0.1,'x','2026','{}')")
    c.commit(); c.close()

    cpu_json = str(tmp_path / "civ_power_units.json")
    with open(cpu_json, "w") as f:
        json.dump({"Franks": {"imperial": {}}}, f)
    cpu_dir = str(tmp_path / "civ_power_units")
    patches = str(tmp_path / "patches.db")

    from aoe2x.batch import migrate_baseline
    migrate_baseline.run(derived_db=dd, pool_db=ps, cpu_json=cpu_json,
                         cpu_dir=cpu_dir, patches_db=patches,
                         baseline_build="170934", release_date="2026-04-01",
                         source_url="http://x", summary_md="baseline")

    bc = sqlite3.connect(dd)
    cols = {r[1] for r in bc.execute("PRAGMA table_info(battle_scores)")}
    assert "build_number" in cols
    assert bc.execute("SELECT build_number FROM battle_scores").fetchone()[0] == "170934"
    bc.close()
    assert os.path.exists(os.path.join(cpu_dir, "170934.json"))
    from aoe2x.batch import patches_db
    assert patches_db.get_current_build(patches_db_path=patches) == "170934"

    # Idempotent: second run does not raise and keeps one row
    migrate_baseline.run(derived_db=dd, pool_db=ps, cpu_json=cpu_json,
                         cpu_dir=cpu_dir, patches_db=patches,
                         baseline_build="170934", release_date="2026-04-01",
                         source_url="http://x", summary_md="baseline")
    bc = sqlite3.connect(dd)
    assert bc.execute("SELECT COUNT(*) FROM battle_scores").fetchone()[0] == 1
    bc.close()


def test_force_marks_all_pending():
    from aoe2x.batch import run_matchup_battles as r  # importable under CPython once the PyPy
    # guard is moved into main() (see Step 3).
    members = [("A", "x", 0, "B", "y", 0)]
    # has_row=True everywhere; without force -> skip; with force -> pending
    assert r._group_pending(lambda *a: True, members, "30v30", "ver", force=False) is False
    assert r._group_pending(lambda *a: True, members, "30v30", "ver", force=True) is True


def test_carry_forward_battle_scores(tmp_path):
    import sqlite3
    from aoe2x.rank import derived_db
    from aoe2x.batch import patch_pipeline
    dd = str(tmp_path / "d.db")
    conn = derived_db.create_db(dd)
    # naval row only exists at old build; must be carried to new build
    conn.execute("INSERT INTO battle_scores (line_slug,age,civ_name,unit_slug,"
                 "score_type,score_value,rank,median_delta,build_number) VALUES "
                 "('naval','imperial','Britons','galleon','naval_effectiveness',70,1,2,'170934')")
    conn.commit(); conn.close()
    patch_pipeline.carry_forward_battle_scores(dd, "170934", "177723")
    conn = sqlite3.connect(dd)
    n = conn.execute("SELECT COUNT(*) FROM battle_scores WHERE build_number='177723' "
                     "AND unit_slug='galleon'").fetchone()[0]
    conn.close()
    assert n == 1


def test_write_patch_records(tmp_path):
    from aoe2x.batch import patches_db, patch_pipeline
    pdb = str(tmp_path / "p.db")
    conn = patches_db.create_db(pdb)
    pid = patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
        title="Update 177723", summary_md="x", source_url="u",
        baseline_build="170934", is_current=0)
    conn.commit()
    patch_pipeline.write_patch_records(conn, pid,
        unit_changes=[{"civ_name":"Wei","unit_slug":"tiger_cavalry_wei",
                       "field":"base_hp","old_value":115,"new_value":110}],
        ranking_changes=[{"civ_name":"Wei","unit_slug":"tiger_cavalry_wei",
                       "score_type":"stable_effectiveness","old_score":90,"new_score":85,
                       "old_rank":1,"new_rank":4}],
        matchup_changes=[{"my_civ":"Wei","my_unit_slug":"tiger_cavalry_wei",
                       "opp_civ":"Franks","opp_unit_slug":"knight","scale":"30v30",
                       "old_winner":1,"new_winner":2,"old_score":60,"new_score":-20,"swing":-80}])
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM patch_unit_changes WHERE patch_id=?", (pid,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM patch_unit_ranking WHERE patch_id=?", (pid,)).fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM patch_matchup_changes WHERE patch_id=?", (pid,)).fetchone()[0] == 1
    conn.close()
