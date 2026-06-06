# tests/test_patches_db.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import patches_db


def test_create_and_current_build(tmp_path):
    db = str(tmp_path / "patches.db")
    conn = patches_db.create_db(db)
    patches_db.insert_patch(conn, build_number="170934", release_date="2026-04-01",
                            title="Update 170934", summary_md="base", source_url="http://x",
                            baseline_build=None, is_current=1)
    patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
                            title="Update 177723", summary_md="notes", source_url="http://y",
                            baseline_build="170934", is_current=0)
    conn.commit()
    assert patches_db.get_current_build(patches_db_path=db) == "170934"
    patches_db.set_current_build(conn, "177723"); conn.commit()
    assert patches_db.get_current_build(patches_db_path=db) == "177723"
    # exactly one current
    n = conn.execute("SELECT COUNT(*) FROM patches WHERE is_current=1").fetchone()[0]
    assert n == 1
    conn.close()


def test_get_current_build_missing_db(tmp_path):
    assert patches_db.get_current_build(patches_db_path=str(tmp_path / "nope.db")) is None
