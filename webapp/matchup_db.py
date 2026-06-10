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


def preflight_derive_guard(db_path, *, allow_small_db=False, allow_stale=False,
                           min_civs=40):
    """CLI pre-flight for the derive scripts (derive_unit_rankings,
    derive_pool_scores): sanity-check a matchup DB before deriving published
    data from it. Aborts via SystemExit when:

      * the DB covers fewer than `min_civs` distinct `my_civ` values — this
        catches the committed Armenians-only stub `webapp/matchup_db.db`
        (the real baseline lives at D:/AI/matchup_baseline_<build>.db).
        Override with --allow-small-db.
      * any rows carry a sim_version other than the current
        `sim_version.compute_sim_version()` — the engine changed since those
        rows were simmed. Override with --allow-stale (legitimately needed
        after a scoped `run_matchup_battles --force --changed-units` re-sim,
        which leaves the baseline at mixed versions; patch_pipeline passes it).

    Guards live at the CLI layer only — library functions
    (compute_and_write_rankings, derive_unit_scores, ...) stay unguarded so
    tests can feed them small synthetic DBs.
    """
    import sys

    from sim_version import compute_sim_version

    if not os.path.exists(db_path):
        raise SystemExit(f"ERROR: matchup DB not found: {db_path}")
    conn = sqlite3.connect(db_path)
    try:
        try:
            n_civs = conn.execute(
                "SELECT COUNT(DISTINCT my_civ) FROM matchup_battles"
            ).fetchone()[0]
        except sqlite3.OperationalError as e:
            raise SystemExit(
                f"ERROR: {db_path} has no matchup_battles table ({e}) — "
                "not a matchup DB?")
        if n_civs < min_civs and not allow_small_db:
            raise SystemExit(
                f"ERROR: {db_path} has rows for only {n_civs} distinct civ(s) "
                f"(expected >= {min_civs}). This looks like the committed "
                "Armenians-only stub (webapp/matchup_db.db), not the real "
                "baseline (D:/AI/matchup_baseline_<build>.db). Deriving from "
                "it would publish partial/stale data. Pass --allow-small-db "
                "to proceed anyway.")
        current = compute_sim_version()
        n_stale = conn.execute(
            "SELECT COUNT(*) FROM matchup_battles "
            "WHERE sim_version IS NULL OR sim_version != ?", (current,)
        ).fetchone()[0]
        if n_stale:
            print(
                "=" * 72 + "\n"
                f"WARNING: {n_stale} row(s) in {db_path} were simmed under a "
                f"sim_version other than the current {current!r}.\n"
                "The sim engine (simulation_real.py / config_combat.py) changed "
                "since those rows were generated — derived output would mix "
                "engine versions.\n" + "=" * 72,
                file=sys.stderr)
            if not allow_stale:
                raise SystemExit(
                    "ERROR: refusing to derive from stale sim rows. Re-sim the "
                    "DB, or pass --allow-stale if the mix is intentional (e.g. "
                    "after a scoped --changed-units re-sim).")
    finally:
        conn.close()


def create_db(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_outcome(conn, *, my_civ, my_unit_slug, opp_civ, opp_unit_slug,
                   scale, my_count, opp_count,
                   outcome: BattleOutcome,
                   runs_count, score_stddev, dedup_group, sim_version,
                   commit=True):
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
    if commit:
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
