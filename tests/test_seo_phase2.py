# tests/test_seo_phase2.py
import json


def test_unit_line_api_parity(client):
    resp = client.get("/api/ref/unit-line/infantry")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(["line_name", "building", "imperial"]).issubset(data.keys())
    assert isinstance(data["imperial"], list) and data["imperial"]
    assert client.get("/api/ref/unit-line/not_a_line").status_code == 404


def test_get_unit_line_data_matches_api(client):
    import app
    api = client.get("/api/ref/unit-line/infantry").get_json()
    helper = app.get_unit_line_data("infantry")
    assert helper == api


def test_rankings_overview_shape(client):
    import app
    data = app.get_rankings_overview_data(top_n=8)
    labels = [g["label"] for g in data]
    assert labels == ["Infantry", "Archers & Gunpowder", "Cavalry", "Siege", "Naval"]
    for g in data:
        assert g["units"], f"{g['label']} has no ranked units"
        assert len(g["units"]) <= 8
        scores = [u["score"] for u in g["units"]]
        assert scores == sorted(scores, reverse=True)
        u = g["units"][0]
        assert set(u.keys()) == {"civ", "name", "slug", "score"}
        assert isinstance(u["score"], (int, float))
