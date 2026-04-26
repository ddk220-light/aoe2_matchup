"""Schema + I/O for yardstick_battles.db.

One row per (civ, my_unit_slug, yardstick_slug, scale).  Stores the averaged
BattleOutcome plus runs_count and score_stddev.

dedup_group is a stable 16-char hex string (MD5 prefix of the group key tuple)
that tags every row sharing the same sim result — i.e., all (civ, unit) pairs
whose unit fingerprint was identical for a given (yardstick, scale).  Query:
    SELECT * FROM yardstick_battles WHERE dedup_group = ?
"""

import hashlib
import os
import sqlite3

from webapp.battle_outcome import BattleOutcome

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "yardstick_battles.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS yardstick_battles (
    id INTEGER PRIMARY KEY,
    civ TEXT NOT NULL,
    my_unit_slug TEXT NOT NULL,
    yardstick_slug TEXT NOT NULL,
    scale TEXT NOT NULL,
    my_count INTEGER NOT NULL,
    opp_count INTEGER NOT NULL,
    winner INTEGER NOT NULL,
    end_reason TEXT NOT NULL,
    game_time_s REAL NOT NULL,
    team1_hp_pct REAL NOT NULL,
    team2_hp_pct REAL NOT NULL,
    team1_survivors INTEGER NOT NULL,
    team2_survivors INTEGER NOT NULL,
    team1_resources_lost INTEGER NOT NULL,
    team2_resources_lost INTEGER NOT NULL,
    team1_start_count INTEGER NOT NULL,
    team2_start_count INTEGER NOT NULL,
    runs_count INTEGER NOT NULL,
    score_stddev REAL,
    dedup_group TEXT,
    UNIQUE(civ, my_unit_slug, yardstick_slug, scale)
);
CREATE INDEX IF NOT EXISTS idx_civ_unit ON yardstick_battles(civ, my_unit_slug);
CREATE INDEX IF NOT EXISTS idx_dedup_group ON yardstick_battles(dedup_group);
"""


def _short_hash(t):
    """Stable 16-char hex prefix of a tuple — used as dedup_group label."""
    return hashlib.md5(repr(t).encode()).hexdigest()[:16]


def create_db(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_outcome(conn, *, civ, my_unit_slug, yardstick_slug, scale,
                   my_count, opp_count, outcome: BattleOutcome,
                   runs_count, score_stddev, dedup_group=None):
    conn.execute("""
        INSERT INTO yardstick_battles (
            civ, my_unit_slug, yardstick_slug, scale,
            my_count, opp_count,
            winner, end_reason, game_time_s,
            team1_hp_pct, team2_hp_pct,
            team1_survivors, team2_survivors,
            team1_resources_lost, team2_resources_lost,
            team1_start_count, team2_start_count,
            runs_count, score_stddev, dedup_group
        ) VALUES (?,?,?,?, ?,?, ?,?,?, ?,?, ?,?, ?,?, ?,?, ?,?,?)
        ON CONFLICT(civ, my_unit_slug, yardstick_slug, scale) DO UPDATE SET
            my_count=excluded.my_count,
            opp_count=excluded.opp_count,
            winner=excluded.winner,
            end_reason=excluded.end_reason,
            game_time_s=excluded.game_time_s,
            team1_hp_pct=excluded.team1_hp_pct,
            team2_hp_pct=excluded.team2_hp_pct,
            team1_survivors=excluded.team1_survivors,
            team2_survivors=excluded.team2_survivors,
            team1_resources_lost=excluded.team1_resources_lost,
            team2_resources_lost=excluded.team2_resources_lost,
            team1_start_count=excluded.team1_start_count,
            team2_start_count=excluded.team2_start_count,
            runs_count=excluded.runs_count,
            score_stddev=excluded.score_stddev,
            dedup_group=excluded.dedup_group
    """, (
        civ, my_unit_slug, yardstick_slug, scale,
        my_count, opp_count,
        outcome.winner, outcome.end_reason, outcome.game_time_s,
        outcome.team1_hp_pct, outcome.team2_hp_pct,
        outcome.team1_survivors, outcome.team2_survivors,
        outcome.team1_resources_lost, outcome.team2_resources_lost,
        outcome.team1_start_count, outcome.team2_start_count,
        runs_count, score_stddev, dedup_group,
    ))
    conn.commit()


def fetch_all_rows(conn):
    return conn.execute("SELECT * FROM yardstick_battles").fetchall()


def has_row(conn, civ, my_unit_slug, yardstick_slug, scale):
    r = conn.execute(
        """SELECT 1 FROM yardstick_battles
           WHERE civ=? AND my_unit_slug=? AND yardstick_slug=? AND scale=?""",
        (civ, my_unit_slug, yardstick_slug, scale),
    ).fetchone()
    return r is not None
