# tests/test_seo_phase4.py
def test_get_patch_overview(client):
    import app
    data = app.get_patch_overview("177723")  # confirmed build with changes
    assert data is not None
    assert data["build_number"] == "177723"
    assert data["release_date"]
    assert data["title"]
    assert "<" in data["summary_html"]  # rendered HTML
    assert isinstance(data["unit_tables"], list) and data["unit_tables"]
    t = data["unit_tables"][0]
    assert {"civ", "slug", "title", "detail_url"}.issubset(t.keys())
    assert app.get_patch_overview("000000") is None
