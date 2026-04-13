def test_naval_aggregate_returns_units(client):
    """Naval aggregate slug returns galleon/fire/hulk units."""
    resp = client.get("/api/ref/unit-line/naval")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert "imperial" in data
    assert len(data["imperial"]) > 0
    unit_names = {u["unit_name"] for u in data["imperial"]}
    assert "Galleon" in unit_names


def test_naval_galleon_subline(client):
    """Galleon sub-line slug returns galleon units and unique units."""
    resp = client.get("/api/ref/unit-line/galleon")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["imperial"]) > 0
    # Vikings unique should be present
    viking_names = [u["unit_name"] for u in data["imperial"] if u["civ_name"] == "Vikings"]
    assert any("Longboat" in n for n in viking_names)


def test_cannon_galleon_in_siege(client):
    """Siege aggregate now includes cannon_galleon sub-line in Imperial Age."""
    resp = client.get("/api/ref/unit-line/siege")
    assert resp.status_code == 200
    data = resp.get_json()
    line_slugs = {u["line_slug"] for u in data["imperial"]}
    assert "cannon_galleon" in line_slugs


def test_naval_no_score_columns(client):
    """Naval units have no land battle score fields (no scoring yet)."""
    resp = client.get("/api/ref/unit-line/naval")
    data = resp.get_json()
    for unit in data["imperial"]:
        assert "militia_value" not in unit
        assert "ranged_effectiveness" not in unit
        assert "anti_building_score" not in unit
