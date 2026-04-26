import os
import tempfile

from webapp.battle_outcome import BattleOutcome
from webapp.yardstick_db import (
    create_db, insert_outcome, fetch_all_rows, has_row,
)
from webapp.derive_scores_from_yardsticks import (
    YARDSTICK_TO_ROLE, aggregate_role_scores,
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
                       outcome=o, runs_count=1, score_stddev=None,
                       dedup_group="test")
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
        insert_outcome(conn, outcome=o1, runs_count=1, score_stddev=None, dedup_group="test", **kw)
        insert_outcome(conn, outcome=o2, runs_count=3, score_stddev=2.5, dedup_group="test", **kw)
        rows = fetch_all_rows(conn)
        assert len(rows) == 1
        assert rows[0]["winner"] == 2  # second insert replaced first
        assert rows[0]["runs_count"] == 3
        conn.close()


def test_yardstick_role_mapping_is_complete():
    expected = {
        "champion":        ["general_combat"],
        "paladin":         ["general_combat", "anti_cav"],
        "arbalester":      ["general_combat", "anti_archer"],
        "halberdier":      ["anti_trash"],
        "imp_elite_skirm": ["anti_trash"],
        "hussar":          ["anti_trash"],
    }
    assert YARDSTICK_TO_ROLE == expected


def test_aggregate_role_scores_basic():
    # 4 rows for one (civ, unit): champ + paladin + arb + halb across 2 scales each
    # Make halb +50 both scales -> anti_trash should average to 50
    rows = [
        # (yardstick, scale, signed_score)
        ("champion", "30v30", 80),
        ("champion", "3k",    60),
        ("paladin",  "30v30", -30),
        ("paladin",  "3k",    -10),
        ("arbalester", "30v30", 70),
        ("arbalester", "3k",    50),
        ("halberdier", "30v30", 50),
        ("halberdier", "3k",    50),
    ]
    out = aggregate_role_scores(rows)
    # general_combat pools champion (80,60) + paladin (-30,-10) + arbalester (70,50)
    # sum = 80+60-30-10+70+50 = 220, avg = 220/6 = 36.666... -> rounds to 36.7
    assert out["general_combat"] == 36.7   # avg of all 6 (champ + paladin + arb)
    assert out["anti_cav"] == -20.0        # avg of paladin
    assert out["anti_archer"] == 60.0      # avg of arbalester
    assert out["anti_trash"] == 50.0       # avg of halberdier (skirm/hussar absent here)


from webapp.derive_scores_from_yardsticks import _normalize_pool


def test_normalize_pool_to_0_100():
    units = {
        "a": {"v": 50.0},
        "b": {"v": 100.0},
        "c": {"v": 0.0},
    }
    _normalize_pool(units, "v")
    assert units["a"]["v"] == 50.0
    assert units["b"]["v"] == 100.0
    assert units["c"]["v"] == 0.0


def test_normalize_pool_handles_all_equal():
    units = {"a": {"v": 5.0}, "b": {"v": 5.0}}
    _normalize_pool(units, "v")
    assert units["a"]["v"] == 0.0  # all-equal collapses to 0
    assert units["b"]["v"] == 0.0
