# tests/test_patches_db.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
from aoe2x.batch import patches_db


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


def test_patch_id_for(tmp_path):
    db = str(tmp_path / "patches.db")
    conn = patches_db.create_db(db)
    pid = patches_db.insert_patch(conn, build_number="170934", release_date="2026-04-01",
                                  title="Update 170934", summary_md="b", source_url="u",
                                  baseline_build=None, is_current=1)
    conn.commit()
    assert patches_db.patch_id_for(conn, "170934") == pid
    assert patches_db.patch_id_for(conn, "999999") is None
    conn.close()


def test_set_current_build_unknown_raises(tmp_path):
    import pytest
    db = str(tmp_path / "patches.db")
    conn = patches_db.create_db(db)
    patches_db.insert_patch(conn, build_number="170934", release_date="2026-04-01",
                            title="t", summary_md="b", source_url="u",
                            baseline_build=None, is_current=1)
    conn.commit()
    with pytest.raises(ValueError):
        patches_db.set_current_build(conn, "does_not_exist")
    conn.close()


# Moved from tests/test_patch_routes.py (its route tests are covered by tests/test_site_builders.py).
def test_committed_patches_have_ranking_rows():
    """Guard against the 177723 regression: every patch in the COMMITTED
    patches.db that records unit changes must also carry ranking-diff rows
    (patch_unit_ranking sat empty for build 177723 because the data was
    written by an ad-hoc finalize script that skipped pipeline step 8)."""
    db = os.path.join(os.path.dirname(__file__), "..", "data", "golden", "patches.db")
    if not os.path.exists(db):
        import pytest
        pytest.skip("committed patches.db not present")
    import sqlite3
    conn = sqlite3.connect(db)
    missing = conn.execute(
        "SELECT p.build_number FROM patches p "
        "WHERE EXISTS (SELECT 1 FROM patch_unit_changes c WHERE c.patch_id=p.id) "
        "AND NOT EXISTS (SELECT 1 FROM patch_unit_ranking r WHERE r.patch_id=p.id)"
    ).fetchall()
    conn.close()
    assert not missing, f"patches with unit changes but no ranking rows: {missing}"
