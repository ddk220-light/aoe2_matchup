"""Unit tests for webapp/pool_scores_query.py."""
import json
import os
import sqlite3
import pytest

from pool_scores_db import create_db, insert_score
from pool_scores_query import load_pool_scores


def _make_row(civ, slug, scale, axis, **overrides):
    base = {
        "civ_name": civ, "unit_slug": slug,
        "pool": "infantry", "scale": scale, "axis": axis,
        "final_score": 0.0, "gc": 0.0, "ac": 0.0, "at": 0.0, "aa": None,
        "n": 1, "mean": 0.0, "stddev": 0.0,
        "win_rate": 0.0, "decisive_win_rate": 0.0,
        "big_win_rate": 0.0, "catastrophic_loss_rate": 0.0,
        "sim_version": "v1", "derived_at": "t1",
        "role_line_means": None,
        "build_number": "170934",
    }
    base.update(overrides)
    return base


def test_load_returns_empty_when_no_rows(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    conn.close()
    result = load_pool_scores(str(db_path), [("Vikings", "elite_berserk_vikings")])
    assert result == {}


def test_load_returns_payload_for_known_unit(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    # Two scales × three axes = 6 rows
    for scale in ("30v30", "3k"):
        for axis in ("hp", "cost", "speed"):
            insert_score(conn, _make_row(
                "Vikings", "elite_berserk_vikings", scale, axis,
                final_score=10.0, gc=5.0, ac=3.0, at=90.0,
                n=200, win_rate=70.0, catastrophic_loss_rate=10.0,
                stddev=50.0, mean=20.0,
                decisive_win_rate=60.0, big_win_rate=50.0,
            ))
    conn.commit()
    conn.close()

    result = load_pool_scores(str(db_path),
                              [("Vikings", "elite_berserk_vikings")])
    payload = result[("Vikings", "elite_berserk_vikings")]
    assert payload["pool"] == "infantry"
    assert set(payload["scales"]) == {"30v30", "3k"}
    pop_hp = payload["scales"]["30v30"]["hp"]
    assert pop_hp["final"] == 10.0
    assert pop_hp["gc"] == 5.0
    assert pop_hp["ac"] == 3.0
    assert pop_hp["at"] == 90.0
    assert pop_hp["aa"] is None
    shape = payload["scales"]["30v30"]["shape"]
    assert shape["n"] == 200
    assert shape["win_rate"] == 70.0
    assert shape["catastrophic_loss_rate"] == 10.0


def test_load_skips_units_not_in_db(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "30v30", "hp"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "30v30", "cost"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "30v30", "speed"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "3k", "hp"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "3k", "cost"))
    insert_score(conn, _make_row("Vikings", "elite_berserk_vikings", "3k", "speed"))
    conn.commit()
    conn.close()

    result = load_pool_scores(str(db_path), [
        ("Vikings", "elite_berserk_vikings"),
        ("Britons", "trebuchet"),  # not in db
    ])
    assert ("Vikings", "elite_berserk_vikings") in result
    assert ("Britons", "trebuchet") not in result
    assert len(result) == 1


def test_load_returns_empty_dict_for_empty_input(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    conn.close()
    assert load_pool_scores(str(db_path), []) == {}


def test_load_partial_scales_handled_gracefully(tmp_path):
    """If a unit only has 30v30 rows but no 3k, still return what's available."""
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    for axis in ("hp", "cost", "speed"):
        insert_score(conn, _make_row(
            "Vikings", "elite_berserk_vikings", "30v30", axis, final_score=5.0))
    conn.commit()
    conn.close()

    result = load_pool_scores(str(db_path), [("Vikings", "elite_berserk_vikings")])
    payload = result[("Vikings", "elite_berserk_vikings")]
    assert "30v30" in payload["scales"]
    # Missing 3k means no entry for that scale.
    assert "3k" not in payload["scales"]


def test_load_decodes_role_line_means(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, {
        "civ_name": "Vikings", "unit_slug": "elite_berserk_vikings",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 8.9, "gc": -6.8, "ac": -1.6, "at": 92.7, "aa": None,
        "n": 269, "mean": 35.2, "stddev": 59.5,
        "win_rate": 61.7, "decisive_win_rate": 53.4,
        "big_win_rate": 47.1, "catastrophic_loss_rate": 27.1,
        "sim_version": "v", "derived_at": "t",
        "role_line_means": json.dumps({
            "GC": {"militia": -10.2, "knight": -5.5, "archer": -4.6},
            "AC": {"knight": -2.1, "camel": 0.0, "steppe_lancer": None, "elephant": -2.8},
            "AT": {"spear": 92.7, "skirmisher": 91.4, "light_cav": 94.0},
        }),
        "build_number": "170934",
    })
    conn.commit()
    conn.close()

    payload = load_pool_scores(str(db_path), [("Vikings", "elite_berserk_vikings")])
    unit = payload[("Vikings", "elite_berserk_vikings")]
    hp = unit["scales"]["30v30"]["hp"]
    assert "role_line_means" in hp
    assert hp["role_line_means"]["GC"]["militia"] == pytest.approx(-10.2)
    assert hp["role_line_means"]["AC"]["steppe_lancer"] is None


def test_load_missing_role_line_means_yields_empty_dict(tmp_path):
    """Old rows where role_line_means is NULL should still load (return {})."""
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, {
        "civ_name": "Vikings", "unit_slug": "champion",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 0, "gc": 0, "ac": 0, "at": 0, "aa": None,
        "n": 1, "mean": 0, "stddev": 0,
        "win_rate": 0, "decisive_win_rate": 0,
        "big_win_rate": 0, "catastrophic_loss_rate": 0,
        "sim_version": "v", "derived_at": "t",
        "role_line_means": None,
        "build_number": "170934",
    })
    conn.commit()
    conn.close()

    payload = load_pool_scores(str(db_path), [("Vikings", "champion")])
    hp = payload[("Vikings", "champion")]["scales"]["30v30"]["hp"]
    assert hp["role_line_means"] == {}
