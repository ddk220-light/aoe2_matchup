# tests/test_patch_routes.py
import os, sys, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))


def _seed_patches(path):
    from aoe2x.batch import patches_db
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


def _seed_unit_detail(path):
    from aoe2x.batch import patches_db
    conn = patches_db.create_db(path)
    pid = patches_db.insert_patch(conn, build_number="177723", release_date="2026-06-02",
        title="Update 177723", summary_md="x", source_url="u",
        baseline_build="170934", is_current=1)
    conn.execute("INSERT INTO patch_unit_changes VALUES (?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","base_hp",130,125,None))
    conn.execute("INSERT INTO patch_unit_ranking VALUES (?,?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","stable_effectiveness",90,85,1,4))
    conn.execute("INSERT INTO patch_matchup_changes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (pid,"Wei","tiger_cavalry_wei","Franks","knight","30v30",1,2,60,-20,-80))
    conn.commit(); conn.close()


def test_patch_unit_page(tmp_path, monkeypatch):
    import app
    db = str(tmp_path / "patches.db")
    _seed_unit_detail(db)
    monkeypatch.setattr(app, "PATCHES_DB_PATH", db)
    client = app.app.test_client()
    r = client.get("/patches/177723/Wei/tiger_cavalry_wei")
    assert r.status_code == 200
    assert b"tiger" in r.data.lower()
    # deep link to the flipped matchup
    assert b"civ1=Wei" in r.data and b"unit2=knight" in r.data and b"autorun=1" in r.data


def test_committed_patches_have_ranking_rows():
    """Guard against the 177723 regression: every patch in the COMMITTED
    patches.db that records unit changes must also carry ranking-diff rows
    (patch_unit_ranking sat empty for build 177723 because the data was
    written by an ad-hoc finalize script that skipped pipeline step 8)."""
    db = os.path.join(os.path.dirname(__file__), "..", "data", "golden", "patches.db")
    if not os.path.exists(db):
        import pytest
        pytest.skip("committed patches.db not present")
    conn = sqlite3.connect(db)
    missing = conn.execute(
        "SELECT p.build_number FROM patches p "
        "WHERE EXISTS (SELECT 1 FROM patch_unit_changes c WHERE c.patch_id=p.id) "
        "AND NOT EXISTS (SELECT 1 FROM patch_unit_ranking r WHERE r.patch_id=p.id)"
    ).fetchall()
    conn.close()
    assert not missing, f"patches with unit changes but no ranking rows: {missing}"


def test_deep_link_builder():
    import app
    url = app.battle_sim_deep_link("Wei", "tiger_cavalry_wei", "Franks", "knight", "30v30")
    assert url.startswith("/?")
    assert "civ1=Wei" in url and "unit1=tiger_cavalry_wei" in url
    assert "civ2=Franks" in url and "unit2=knight" in url
    assert "mode=count" in url and "autorun=1" in url
    url3k = app.battle_sim_deep_link("Wei", "tiger_cavalry_wei", "Franks", "knight", "3k")
    assert "mode=resources" in url3k and "resources=3000" in url3k
