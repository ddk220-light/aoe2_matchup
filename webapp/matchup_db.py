"""Schema + I/O for matchup_db.db.

One row per (my_civ, my_unit, opp_civ, opp_unit, scale).  Stores raw
1v1 simulation outcomes including per-resource losses, gains, and
HP-weighted value_lost.

dedup_group is a stable 16-char hex string tagging every row sharing
the same sim result (identical fingerprint pair + scale).

sim_version is a hash of simulation source files; rows whose value
differs from current are re-simulated on the next run.
"""

import hashlib
import os
import sqlite3

from battle_outcome import BattleOutcome

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "matchup_db.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS matchup_battles (
    id INTEGER PRIMARY KEY,

    my_civ TEXT NOT NULL,
    my_unit_slug TEXT NOT NULL,
    opp_civ TEXT NOT NULL,
    opp_unit_slug TEXT NOT NULL,
    scale TEXT NOT NULL,
    my_count INTEGER NOT NULL,
    opp_count INTEGER NOT NULL,

    my_cost_food REAL NOT NULL,
    my_cost_wood REAL NOT NULL,
    my_cost_gold REAL NOT NULL,
    opp_cost_food REAL NOT NULL,
    opp_cost_wood REAL NOT NULL,
    opp_cost_gold REAL NOT NULL,

    winner INTEGER NOT NULL,
    end_reason TEXT NOT NULL,
    game_time_s REAL NOT NULL,

    team1_hp_pct REAL NOT NULL,
    team1_survivors INTEGER NOT NULL,
    team1_food_lost REAL NOT NULL,
    team1_wood_lost REAL NOT NULL,
    team1_gold_lost REAL NOT NULL,
    team1_food_gained REAL NOT NULL,
    team1_wood_gained REAL NOT NULL,
    team1_gold_gained REAL NOT NULL,
    team1_value_lost REAL NOT NULL,

    team2_hp_pct REAL NOT NULL,
    team2_survivors INTEGER NOT NULL,
    team2_food_lost REAL NOT NULL,
    team2_wood_lost REAL NOT NULL,
    team2_gold_lost REAL NOT NULL,
    team2_food_gained REAL NOT NULL,
    team2_wood_gained REAL NOT NULL,
    team2_gold_gained REAL NOT NULL,
    team2_value_lost REAL NOT NULL,

    team1_start_count INTEGER NOT NULL,
    team2_start_count INTEGER NOT NULL,

    runs_count INTEGER NOT NULL,
    score_stddev REAL,
    dedup_group TEXT NOT NULL,
    sim_version TEXT NOT NULL,

    UNIQUE(my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale)
);
CREATE INDEX IF NOT EXISTS idx_my  ON matchup_battles(my_civ, my_unit_slug);
CREATE INDEX IF NOT EXISTS idx_opp ON matchup_battles(opp_civ, opp_unit_slug);
CREATE INDEX IF NOT EXISTS idx_dedup ON matchup_battles(dedup_group);
CREATE INDEX IF NOT EXISTS idx_simver ON matchup_battles(sim_version);
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


def insert_outcome(conn, *, my_civ, my_unit_slug, opp_civ, opp_unit_slug,
                   scale, my_count, opp_count,
                   outcome: BattleOutcome,
                   runs_count, score_stddev, dedup_group, sim_version):
    conn.execute("""
        INSERT INTO matchup_battles (
            my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
            my_count, opp_count,
            my_cost_food, my_cost_wood, my_cost_gold,
            opp_cost_food, opp_cost_wood, opp_cost_gold,
            winner, end_reason, game_time_s,
            team1_hp_pct, team1_survivors,
            team1_food_lost, team1_wood_lost, team1_gold_lost,
            team1_food_gained, team1_wood_gained, team1_gold_gained,
            team1_value_lost,
            team2_hp_pct, team2_survivors,
            team2_food_lost, team2_wood_lost, team2_gold_lost,
            team2_food_gained, team2_wood_gained, team2_gold_gained,
            team2_value_lost,
            team1_start_count, team2_start_count,
            runs_count, score_stddev, dedup_group, sim_version
        ) VALUES (
            ?,?,?,?,?,
            ?,?,
            ?,?,?,
            ?,?,?,
            ?,?,?,
            ?,?,
            ?,?,?,
            ?,?,?,
            ?,
            ?,?,
            ?,?,?,
            ?,?,?,
            ?,
            ?,?,
            ?,?,?,?
        )
        ON CONFLICT(my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale) DO UPDATE SET
            my_count=excluded.my_count, opp_count=excluded.opp_count,
            my_cost_food=excluded.my_cost_food, my_cost_wood=excluded.my_cost_wood, my_cost_gold=excluded.my_cost_gold,
            opp_cost_food=excluded.opp_cost_food, opp_cost_wood=excluded.opp_cost_wood, opp_cost_gold=excluded.opp_cost_gold,
            winner=excluded.winner, end_reason=excluded.end_reason, game_time_s=excluded.game_time_s,
            team1_hp_pct=excluded.team1_hp_pct, team1_survivors=excluded.team1_survivors,
            team1_food_lost=excluded.team1_food_lost, team1_wood_lost=excluded.team1_wood_lost, team1_gold_lost=excluded.team1_gold_lost,
            team1_food_gained=excluded.team1_food_gained, team1_wood_gained=excluded.team1_wood_gained, team1_gold_gained=excluded.team1_gold_gained,
            team1_value_lost=excluded.team1_value_lost,
            team2_hp_pct=excluded.team2_hp_pct, team2_survivors=excluded.team2_survivors,
            team2_food_lost=excluded.team2_food_lost, team2_wood_lost=excluded.team2_wood_lost, team2_gold_lost=excluded.team2_gold_lost,
            team2_food_gained=excluded.team2_food_gained, team2_wood_gained=excluded.team2_wood_gained, team2_gold_gained=excluded.team2_gold_gained,
            team2_value_lost=excluded.team2_value_lost,
            team1_start_count=excluded.team1_start_count, team2_start_count=excluded.team2_start_count,
            runs_count=excluded.runs_count, score_stddev=excluded.score_stddev,
            dedup_group=excluded.dedup_group, sim_version=excluded.sim_version
    """, (
        my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
        my_count, opp_count,
        outcome.my_cost_food, outcome.my_cost_wood, outcome.my_cost_gold,
        outcome.opp_cost_food, outcome.opp_cost_wood, outcome.opp_cost_gold,
        outcome.winner, outcome.end_reason, outcome.game_time_s,
        outcome.team1_hp_pct, outcome.team1_survivors,
        outcome.team1_food_lost, outcome.team1_wood_lost, outcome.team1_gold_lost,
        outcome.team1_food_gained, outcome.team1_wood_gained, outcome.team1_gold_gained,
        outcome.team1_value_lost,
        outcome.team2_hp_pct, outcome.team2_survivors,
        outcome.team2_food_lost, outcome.team2_wood_lost, outcome.team2_gold_lost,
        outcome.team2_food_gained, outcome.team2_wood_gained, outcome.team2_gold_gained,
        outcome.team2_value_lost,
        outcome.team1_start_count, outcome.team2_start_count,
        runs_count, score_stddev, dedup_group, sim_version,
    ))
    conn.commit()


def fetch_all_rows(conn):
    return conn.execute("SELECT * FROM matchup_battles").fetchall()


def has_row_with_version(conn, my_civ, my_unit_slug, opp_civ, opp_unit_slug,
                         scale, sim_version):
    r = conn.execute(
        """SELECT 1 FROM matchup_battles
           WHERE my_civ=? AND my_unit_slug=? AND opp_civ=? AND opp_unit_slug=?
             AND scale=? AND sim_version=?""",
        (my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, sim_version),
    ).fetchone()
    return r is not None
