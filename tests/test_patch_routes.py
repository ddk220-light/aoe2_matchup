# tests/test_patch_routes.py
import os, sys, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))


def _seed_patches(path):
    import patches_db
    conn = patches_db.create_db(path)
    pid = patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
        title="Update 177723", summary_md="**Tiger Cavalry** HP 130 -> 125.",
        source_url="https://example.com/177723", baseline_build="170934", is_current=1)
    conn.execute("INSERT INTO patch_unit_changes (patch_id,civ_name,unit_slug,field,"
                 "old_value,new_value,note) VALUES (?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","base_hp",130,125,None))
    conn.commit(); conn.close()


def test_patches_page(tmp_path, monkeypatch):
    import app
    db = str(tmp_path / "patches.db")
    _seed_patches(db)
    monkeypatch.setattr(app, "PATCHES_DB_PATH", db)
    client = app.app.test_client()
    r = client.get("/patches")
    assert r.status_code == 200
    assert b"Update 177723" in r.data
    assert b"example.com/177723" in r.data


def test_render_markdown_basic():
    import app
    html = app.render_patch_summary("**bold** and [link](http://x)\n- one\n- two")
    assert "<strong>bold</strong>" in html
    assert '<a href="http://x"' in html
    assert "<li>one</li>" in html
