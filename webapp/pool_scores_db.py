"""SQLite schema + writer for the pool_scores derived database.

Single table: `pool_scores`, keyed by (civ_name, unit_slug, scale, axis).
Six rows per (civ, unit) — three axes × two scales.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS pool_scores (
    civ_name              TEXT NOT NULL,
    unit_slug             TEXT NOT NULL,
    pool                  TEXT NOT NULL,
    scale                 TEXT NOT NULL,
    axis                  TEXT NOT NULL,
    final_score           REAL NOT NULL,
    gc                    REAL,
    ac                    REAL,
    at                    REAL,
    aa                    REAL,
    n                     INTEGER NOT NULL,
    mean                  REAL NOT NULL,
    stddev                REAL NOT NULL,
    win_rate              REAL NOT NULL,
    decisive_win_rate     REAL NOT NULL,
    big_win_rate          REAL NOT NULL,
    catastrophic_loss_rate REAL NOT NULL,
    sim_version           TEXT,
    derived_at            TEXT NOT NULL,
    role_line_means       TEXT,
    build_number          TEXT NOT NULL DEFAULT '170934',
    PRIMARY KEY (civ_name, unit_slug, scale, axis, build_number)
);

CREATE INDEX IF NOT EXISTS idx_pool_scores_pool_axis_scale
    ON pool_scores (pool, axis, scale, build_number);
"""


def create_db(path: str) -> sqlite3.Connection:
    """Open the DB at `path`, create the schema if it doesn't exist."""
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


_INSERT_SQL = """
INSERT OR REPLACE INTO pool_scores (
    civ_name, unit_slug, pool, scale, axis,
    final_score, gc, ac, at, aa,
    n, mean, stddev,
    win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate,
    sim_version, derived_at, role_line_means, build_number
) VALUES (
    :civ_name, :unit_slug, :pool, :scale, :axis,
    :final_score, :gc, :ac, :at, :aa,
    :n, :mean, :stddev,
    :win_rate, :decisive_win_rate, :big_win_rate, :catastrophic_loss_rate,
    :sim_version, :derived_at, :role_line_means, :build_number
)
"""


def insert_score(conn: sqlite3.Connection, row: dict) -> None:
    """Upsert one row into pool_scores. Caller is responsible for commit."""
    conn.execute(_INSERT_SQL, row)
