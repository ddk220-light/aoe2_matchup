"""Tests for webapp/pool_scores_db.py."""
import sqlite3
from pool_scores_db import create_db, insert_score


def test_create_db_has_pool_scores_table(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    assert "pool_scores" in tables
    conn.close()


def test_pool_scores_columns_match_spec(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(pool_scores)")
    cols = {r[1]: r[2] for r in cur.fetchall()}
    expected = {
        "civ_name": "TEXT", "unit_slug": "TEXT", "pool": "TEXT",
        "scale": "TEXT", "axis": "TEXT",
        "final_score": "REAL", "gc": "REAL", "ac": "REAL",
        "at": "REAL", "aa": "REAL",
        "n": "INTEGER", "mean": "REAL", "stddev": "REAL",
        "win_rate": "REAL", "decisive_win_rate": "REAL",
        "big_win_rate": "REAL", "catastrophic_loss_rate": "REAL",
        "sim_version": "TEXT", "derived_at": "TEXT",
        "role_line_means": "TEXT",
    }
    for col, ctype in expected.items():
        assert col in cols, f"missing column: {col}"
        assert cols[col] == ctype, f"{col}: expected {ctype}, got {cols[col]}"
    conn.close()


def test_insert_and_read_back(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, {
        "civ_name": "Vikings", "unit_slug": "elite_berserk_vikings",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 8.9, "gc": -6.8, "ac": -1.6, "at": 92.7, "aa": None,
        "n": 238, "mean": 35.2, "stddev": 59.5,
        "win_rate": 72.3, "decisive_win_rate": 64.3,
        "big_win_rate": 55.9, "catastrophic_loss_rate": 13.0,
        "sim_version": "ba893a3", "derived_at": "2026-04-28T00:00:00",
        "role_line_means": None,
    })
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT final_score, gc, n FROM pool_scores WHERE unit_slug='elite_berserk_vikings'")
    row = cur.fetchone()
    assert row == (8.9, -6.8, 238)
    conn.close()


def test_insert_replaces_on_duplicate_key(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    payload = {
        "civ_name": "Vikings", "unit_slug": "elite_berserk_vikings",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 1.0, "gc": 0, "ac": 0, "at": 0, "aa": None,
        "n": 1, "mean": 0, "stddev": 0,
        "win_rate": 0, "decisive_win_rate": 0,
        "big_win_rate": 0, "catastrophic_loss_rate": 0,
        "sim_version": "v1", "derived_at": "t1",
        "role_line_means": None,
    }
    insert_score(conn, payload)
    payload["final_score"] = 99.0
    insert_score(conn, payload)
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(final_score) FROM pool_scores")
    n, total = cur.fetchone()
    assert n == 1
    assert total == 99.0
    conn.close()


def test_insert_writes_role_line_means_json(tmp_path):
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
        "role_line_means": '{"GC":{"militia":-10.2,"knight":-5.5,"archer":-4.6}}',
    })
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT role_line_means FROM pool_scores WHERE unit_slug='elite_berserk_vikings'")
    (got,) = cur.fetchone()
    assert got == '{"GC":{"militia":-10.2,"knight":-5.5,"archer":-4.6}}'
    conn.close()


import json
import sqlite3
from derive_pool_scores import main as derive_main


def test_orchestrator_writes_json_role_line_means(tmp_path):
    """End-to-end: derive on a tiny synthetic matchup DB and verify the JSON column."""
    matchup_path = tmp_path / "matchup.db"
    out_path = tmp_path / "pool.db"

    mc = sqlite3.connect(matchup_path)
    mc.executescript("""
        CREATE TABLE matchup_battles (
            my_civ TEXT, my_unit_slug TEXT, opp_unit_slug TEXT,
            scale TEXT, winner INTEGER,
            team1_hp_pct REAL, team2_hp_pct REAL,
            my_count INTEGER, my_cost_food REAL, my_cost_wood REAL, my_cost_gold REAL,
            opp_count INTEGER, opp_cost_food REAL, opp_cost_wood REAL, opp_cost_gold REAL,
            game_time_s REAL, dedup_group TEXT, sim_version TEXT
        );
    """)
    mc.execute("""
        INSERT INTO matchup_battles VALUES
        ('Vikings','champion','paladin','30v30',2,0.0,0.5,30,60,0,20,30,60,0,80,40.0,'g1','vTEST')
    """)
    mc.commit()
    mc.close()

    rc = derive_main(["--matchup-db", str(matchup_path), "--out", str(out_path)])
    assert rc == 0

    conn = sqlite3.connect(out_path)
    cur = conn.execute(
        "SELECT axis, role_line_means FROM pool_scores WHERE unit_slug='champion' AND scale='30v30'"
    )
    rows = dict(cur.fetchall())
    conn.close()

    assert "hp" in rows
    rlm = json.loads(rows["hp"])
    assert rlm["GC"]["knight"] is not None
    assert rlm["GC"]["militia"] is None
    assert rlm["GC"]["archer"] is None


def test_orchestrator_migrates_existing_db_without_column(tmp_path):
    """Old pool_scores.db (no role_line_means column) gets ALTER TABLE on next run."""
    out_path = tmp_path / "pool.db"

    legacy = sqlite3.connect(out_path)
    legacy.executescript("""
        CREATE TABLE pool_scores (
            civ_name TEXT, unit_slug TEXT, pool TEXT, scale TEXT, axis TEXT,
            final_score REAL, gc REAL, ac REAL, at REAL, aa REAL,
            n INTEGER, mean REAL, stddev REAL,
            win_rate REAL, decisive_win_rate REAL, big_win_rate REAL,
            catastrophic_loss_rate REAL,
            sim_version TEXT, derived_at TEXT,
            PRIMARY KEY (civ_name, unit_slug, scale, axis)
        );
    """)
    legacy.commit()
    legacy.close()

    matchup_path = tmp_path / "matchup.db"
    mc = sqlite3.connect(matchup_path)
    mc.executescript("""
        CREATE TABLE matchup_battles (
            my_civ TEXT, my_unit_slug TEXT, opp_unit_slug TEXT,
            scale TEXT, winner INTEGER,
            team1_hp_pct REAL, team2_hp_pct REAL,
            my_count INTEGER, my_cost_food REAL, my_cost_wood REAL, my_cost_gold REAL,
            opp_count INTEGER, opp_cost_food REAL, opp_cost_wood REAL, opp_cost_gold REAL,
            game_time_s REAL, dedup_group TEXT, sim_version TEXT
        );
    """)
    mc.commit()
    mc.close()

    derive_main(["--matchup-db", str(matchup_path), "--out", str(out_path)])

    conn = sqlite3.connect(out_path)
    cur = conn.execute("PRAGMA table_info(pool_scores)")
    cols = {r[1] for r in cur.fetchall()}
    conn.close()
    assert "role_line_means" in cols
