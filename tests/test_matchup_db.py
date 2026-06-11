import os
import tempfile
import pytest
from aoe2x.sim.battle_outcome import BattleOutcome
from aoe2x.batch.matchup_db import (
    create_db, insert_outcome, has_row_with_version, fetch_all_rows, _short_hash,
)


def _outcome(**kw):
    base = dict(
        winner=1, end_reason="eliminated", game_time_s=10.0,
        team1_hp_pct=1.0, team2_hp_pct=0.0,
        team1_survivors=30, team2_survivors=0,
        team1_resources_lost=0, team2_resources_lost=4500,
        team1_start_count=30, team2_start_count=30,
    )
    base.update(kw)
    return BattleOutcome(**base)


def test_create_db_makes_table(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert any(r[0] == 'matchup_battles' for r in rows)


def test_insert_and_fetch(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    insert_outcome(
        conn,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Britons", opp_unit_slug="halberdier",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(),
        runs_count=1, score_stddev=None,
        dedup_group="abc1234567890def",
        sim_version="cafef00ddeadbeef",
    )
    rows = fetch_all_rows(conn)
    assert len(rows) == 1
    assert rows[0]["my_civ"] == "Aztecs"
    assert rows[0]["sim_version"] == "cafef00ddeadbeef"


def test_upsert_overwrites(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    args = dict(
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Britons", opp_unit_slug="halberdier",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(winner=1),
        runs_count=1, score_stddev=None, dedup_group="abc", sim_version="v1",
    )
    insert_outcome(conn, **args)
    args["outcome"] = _outcome(winner=2)
    args["sim_version"] = "v2"
    insert_outcome(conn, **args)
    rows = fetch_all_rows(conn)
    assert len(rows) == 1
    assert rows[0]["winner"] == 2
    assert rows[0]["sim_version"] == "v2"


def test_has_row_with_version(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    insert_outcome(
        conn,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Britons", opp_unit_slug="halberdier",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(),
        runs_count=1, score_stddev=None, dedup_group="abc", sim_version="v1",
    )
    assert has_row_with_version(conn, "Aztecs", "elite_jaguar_warrior_aztecs",
                                 "Britons", "halberdier", "30v30", "v1")
    assert not has_row_with_version(conn, "Aztecs", "elite_jaguar_warrior_aztecs",
                                     "Britons", "halberdier", "30v30", "v2")
