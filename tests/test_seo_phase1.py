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


def test_civ_overview_ssr_renders_all_civs(client):
    import app
    civs = app._get_ref_civs()
    body = client.get("/civilizations").data.decode()
    for civ in civs:
        assert civ in body, f"{civ} missing from civ SSR"
    assert 'id="civ-ssr"' in body


def test_civ_overview_ssr_has_descriptions_and_units(client):
    import app
    data = app.get_civ_overview_data()
    body = client.get("/civilizations").data.decode()
    # At least one strategic description rendered (they begin "This civ ...").
    assert "This civ" in body
    # A power-unit name renders as crawlable text.
    sample = next(c for c in data if c["roles"])
    assert sample["roles"][0]["units"][0]["name"] in body


def test_civ_overview_itemlist_jsonld(client):
    import app
    n = len(app._get_ref_civs())
    body = client.get("/civilizations").data.decode()
    assert '"@type": "ItemList"' in body
    assert f'"numberOfItems": {n}' in body
