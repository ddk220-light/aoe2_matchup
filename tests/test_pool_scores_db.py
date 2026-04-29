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
