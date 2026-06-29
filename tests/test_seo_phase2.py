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
