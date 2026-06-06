# tests/test_versioning.py
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
