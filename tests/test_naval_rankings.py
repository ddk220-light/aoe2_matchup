import sqlite3
import os
from unittest.mock import patch

from patches_db import get_current_build


def _db_path():
    """Battle scores live in derived_data.db now (app.py reads from there)."""
    return os.path.join(os.path.dirname(__file__), "..", "webapp", "derived_data.db")


def _inject_naval_score(score_value):
    """Replace the Britons-galleon naval_effectiveness row for the CURRENT build
    with `score_value`, returning (build, original_value) for restoration.

    The /api/ref/unit-line route filters battle_scores by the current build
    (patches_db.get_current_build), so the injected row MUST carry that
    build_number or the route won't see it. battle_scores stores age lowercase.
    """
    build = get_current_build()
    conn = sqlite3.connect(_db_path())
    c = conn.cursor()
    c.execute(
        "SELECT score_value FROM battle_scores"
        " WHERE line_slug='galleon' AND age='imperial' AND civ_name='Britons'"
        " AND unit_slug='galleon' AND score_type='naval_effectiveness'"
        " AND build_number=?",
        (build,),
    )
    existing = c.fetchone()
    original_value = existing[0] if existing else None
    c.execute(
        "DELETE FROM battle_scores WHERE line_slug='galleon' AND age='imperial'"
        " AND civ_name='Britons' AND unit_slug='galleon' AND score_type='naval_effectiveness'"
        " AND build_number=?",
        (build,),
    )
    c.execute(
        "INSERT INTO battle_scores (line_slug, age, civ_name, unit_slug, score_type, score_value, build_number)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("galleon", "imperial", "Britons", "galleon", "naval_effectiveness", score_value, build),
    )
    conn.commit()
    conn.close()
    return build, original_value


def _restore_naval_score(build, original_value):
    conn = sqlite3.connect(_db_path())
    conn.execute(
        "DELETE FROM battle_scores WHERE line_slug='galleon' AND age='imperial'"
        " AND civ_name='Britons' AND unit_slug='galleon' AND score_type='naval_effectiveness'"
        " AND build_number=?",
        (build,),
    )
    if original_value is not None:
        conn.execute(
            "INSERT INTO battle_scores (line_slug, age, civ_name, unit_slug, score_type, score_value, build_number)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("galleon", "imperial", "Britons", "galleon", "naval_effectiveness", original_value, build),
        )
    conn.commit()
    conn.close()


def test_naval_score_attached_to_unit(client):
    """After inserting a battle_score row, /api/ref/unit-line/galleon returns it on the unit."""
    build, original_value = _inject_naval_score(77.5)
    try:
        resp = client.get("/api/ref/unit-line/galleon")
        assert resp.status_code == 200
        data = resp.get_json()
        britons = next(
            (u for u in data["imperial"]
             if u["civ_name"] == "Britons" and u["unit_slug"] == "galleon"),
            None,
        )
        assert britons is not None, "Britons galleon not found in imperial list"
        assert britons.get("naval_effectiveness") == 77.5, (
            f"expected 77.5, got {britons.get('naval_effectiveness')}"
        )
    finally:
        _restore_naval_score(build, original_value)


def test_naval_aggregate_score_attached(client):
    """GET /api/ref/unit-line/naval attaches naval_effectiveness scores to galleon units."""
    build, original_value = _inject_naval_score(65.0)
    try:
        resp = client.get("/api/ref/unit-line/naval")
        assert resp.status_code == 200
        data = resp.get_json()
        britons = next(
            (u for u in data["imperial"]
             if u["civ_name"] == "Britons" and u["unit_slug"] == "galleon"),
            None,
        )
        assert britons is not None
        assert britons.get("naval_effectiveness") == 65.0
    finally:
        _restore_naval_score(build, original_value)


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
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    for unit in data["imperial"]:
        assert "militia_value" not in unit
        assert "ranged_effectiveness" not in unit
        assert "anti_building_score" not in unit


def test_compute_naval_role_scores_structure():
    """compute_naval_role_scores returns galleon/fire/hulk sub-line dicts with required keys."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
    from compute_battle_scores import compute_naval_role_scores

    with patch("compute_battle_scores.simulate_battle") as mock_sim:
        mock_sim.return_value = (1, 100, 10.0, 0.5, 0.0)
        result = compute_naval_role_scores("imperial")

    assert "galleon|imperial" in result
    assert "fire|imperial" in result
    assert "hulk|imperial" in result

    for line_key in ["galleon|imperial", "fire|imperial", "hulk|imperial"]:
        assert len(result[line_key]) > 0, f"{line_key} is empty"
        for unit_key, scores in result[line_key].items():
            assert "naval_effectiveness" in scores, f"{unit_key} missing naval_effectiveness"
            assert "vs_galleon" in scores, f"{unit_key} missing vs_galleon"
            assert "vs_fire" in scores,    f"{unit_key} missing vs_fire"
            assert "vs_hulk" in scores,    f"{unit_key} missing vs_hulk"
            assert 0 <= scores["naval_effectiveness"] <= 100, \
                f"{unit_key} naval_effectiveness={scores['naval_effectiveness']} out of range"
