# tests/test_seo_phase1.py — the civilization overview data behind the published /civilizations pages.
# The page head, ItemList and per-civ links are covered in tests/test_site_builders.py.
PAGE_ONLY_CIVS = ["Danes", "Saxons", "Varangians"]


def test_get_civ_overview_data_shape(client):
    import aoe2_api.web as app
    data = app.get_civ_overview_data()
    # Page-only additions do not expand the simulation reference catalog.
    civs = sorted(app._get_ref_civs() + PAGE_ONLY_CIVS)
    assert len(data) == len(civs)
    assert [c["name"] for c in data] == civs  # same order (alphabetical)
    # Every entry has the SSR fields.
    for c in data:
        assert set(c.keys()) == {"name", "slug", "description", "emblem_url", "roles"}
        assert c["slug"] == c["name"].lower()
        assert isinstance(c["roles"], list)
    # At least one civ has a non-empty description and at least one unit.
    rich = [c for c in data if c["description"] and c["roles"]]
    assert rich, "expected some civ with description + roles"
    unit = rich[0]["roles"][0]["units"][0]
    assert set(unit.keys()) == {"name", "slug", "tier", "is_unique"}
    assert unit["name"]

