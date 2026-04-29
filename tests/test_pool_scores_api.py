"""Integration tests for /api/ref/unit-line pool_scores attachment."""
import os
import pytest


@pytest.fixture(autouse=True)
def _require_real_dbs():
    """Skip if the live pool_scores.db isn't generated yet."""
    p = os.path.join(os.path.dirname(__file__), "..", "webapp", "pool_scores.db")
    if not os.path.exists(p):
        pytest.skip(f"{p} not present — run derive_pool_scores.py first")


def _find(rows, civ, slug):
    return next((u for u in rows if u["civ_name"] == civ and u["unit_slug"] == slug), None)


def test_pool_scores_attached_for_infantry_unit(client):
    resp = client.get("/api/ref/unit-line/militia")
    assert resp.status_code == 200
    data = resp.get_json()
    berserker = _find(data["imperial"], "Vikings", "elite_berserk_vikings")
    assert berserker is not None
    assert "pool_scores" in berserker
    ps = berserker["pool_scores"]
    assert ps["pool"] == "infantry"
    assert "30v30" in ps["scales"]
    assert "3k" in ps["scales"]
    pop_hp = ps["scales"]["30v30"]["hp"]
    assert pop_hp["final"] == pytest.approx(8.9, abs=0.5)
    assert pop_hp["at"] == pytest.approx(92.7, abs=0.5)


def test_pool_scores_attached_for_stable_unit(client):
    resp = client.get("/api/ref/unit-line/knight")
    assert resp.status_code == 200
    data = resp.get_json()
    paladin = _find(data["imperial"], "Franks", "paladin")
    assert paladin is not None
    assert "pool_scores" in paladin
    assert paladin["pool_scores"]["pool"] == "stable"


def test_pool_scores_attached_for_archer_unit(client):
    resp = client.get("/api/ref/unit-line/archer")
    assert resp.status_code == 200
    data = resp.get_json()
    arb = _find(data["imperial"], "Britons", "arbalester")
    assert arb is not None
    assert "pool_scores" in arb
    assert arb["pool_scores"]["pool"] == "archer"


def test_pool_scores_absent_for_siege_unit(client):
    """Trebuchet is in the trebuchet line — not covered by pool_scores."""
    resp = client.get("/api/ref/unit-line/trebuchet")
    assert resp.status_code == 200
    data = resp.get_json()
    treb = _find(data["imperial"], "Britons", "trebuchet")
    assert treb is not None
    assert "pool_scores" not in treb


def test_pool_scores_absent_for_naval_unit(client):
    resp = client.get("/api/ref/unit-line/galleon")
    assert resp.status_code == 200
    data = resp.get_json()
    galleon = _find(data["imperial"], "Britons", "galleon")
    assert galleon is not None
    assert "pool_scores" not in galleon


def test_pool_scores_shape_descriptors_present(client):
    resp = client.get("/api/ref/unit-line/militia")
    data = resp.get_json()
    berserker = _find(data["imperial"], "Vikings", "elite_berserk_vikings")
    shape = berserker["pool_scores"]["scales"]["30v30"]["shape"]
    assert shape["n"] >= 200
    assert "win_rate" in shape
    assert "catastrophic_loss_rate" in shape
    assert "stddev" in shape


def test_unit_row_includes_missing_techs(client):
    resp = client.get("/api/ref/unit-line/militia")
    assert resp.status_code == 200
    data = resp.get_json()
    aztec_champ = _find(data["imperial"], "Aztecs", "champion")
    assert aztec_champ is not None
    assert "missing_techs" in aztec_champ
    assert isinstance(aztec_champ["missing_techs"], list)


def test_unit_row_includes_role_line_means(client):
    resp = client.get("/api/ref/unit-line/militia")
    data = resp.get_json()
    berserker = _find(data["imperial"], "Vikings", "elite_berserk_vikings")
    pop_hp = berserker["pool_scores"]["scales"]["30v30"]["hp"]
    assert "role_line_means" in pop_hp
    rlm = pop_hp["role_line_means"]
    assert "GC" in rlm and set(rlm["GC"].keys()) == {"militia", "knight", "archer"}
    assert "AC" in rlm
    assert "AT" in rlm
