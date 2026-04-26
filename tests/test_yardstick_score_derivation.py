import os
import tempfile

from webapp.battle_outcome import BattleOutcome
from webapp.yardstick_db import (
    create_db, insert_outcome, fetch_all_rows, has_row,
)


def _outcome(winner=1, hp1=0.6, hp2=0.0):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=24.5,
        team1_hp_pct=hp1, team2_hp_pct=hp2,
        team1_survivors=18 if winner == 1 else 0,
        team2_survivors=18 if winner == 2 else 0,
        team1_resources_lost=900, team2_resources_lost=2400,
        team1_start_count=30, team2_start_count=30,
    )


def test_create_and_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "y.db")
        conn = create_db(path)
        o = _outcome()
        insert_outcome(conn, civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
                       yardstick_slug="halberdier", scale="30v30",
                       my_count=30, opp_count=30,
                       outcome=o, runs_count=1, score_stddev=None)
        rows = fetch_all_rows(conn)
        assert len(rows) == 1
        r = rows[0]
        assert r["civ"] == "Aztecs"
        assert r["winner"] == 1
        assert r["team1_hp_pct"] == 0.6
        assert r["runs_count"] == 1
        assert has_row(conn, "Aztecs", "elite_jaguar_warrior_aztecs", "halberdier", "30v30")
        assert not has_row(conn, "Aztecs", "elite_jaguar_warrior_aztecs", "halberdier", "3k")
        conn.close()


def test_insert_idempotent_on_unique_key():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "y.db")
        conn = create_db(path)
        o1 = _outcome(winner=1, hp1=0.6)
        o2 = _outcome(winner=2, hp1=0.0, hp2=0.7)
        kw = dict(
            civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
            yardstick_slug="halberdier", scale="30v30",
            my_count=30, opp_count=30,
        )
        insert_outcome(conn, outcome=o1, runs_count=1, score_stddev=None, **kw)
        insert_outcome(conn, outcome=o2, runs_count=3, score_stddev=2.5, **kw)
        rows = fetch_all_rows(conn)
        assert len(rows) == 1
        assert rows[0]["winner"] == 2  # second insert replaced first
        assert rows[0]["runs_count"] == 3
        conn.close()
