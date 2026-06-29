# tests/test_seo_phase1.py
def test_get_civ_overview_data_shape(client):
    import app
    data = app.get_civ_overview_data()
    # One entry per civ in the reference DB.
    civs = app._get_ref_civs()
    assert len(data) == len(civs)
    assert [c["name"] for c in data] == civs  # same order (alphabetical)
    # Every entry has the SSR fields.
    for c in data:
        assert set(c.keys()) == {"name", "slug", "description", "roles"}
        assert c["slug"] == c["name"].lower()
        assert isinstance(c["roles"], list)
    # At least one civ has a non-empty description and at least one unit.
    rich = [c for c in data if c["description"] and c["roles"]]
    assert rich, "expected some civ with description + roles"
    unit = rich[0]["roles"][0]["units"][0]
    assert set(unit.keys()) == {"name", "slug", "tier", "is_unique"}
    assert unit["name"]
