import os
import sqlite3
import pytest

from battle_outcome import BattleOutcome
from matchup_db import create_db as create_matchup_db, insert_outcome
from derived_db import create_db as create_derived_db
from derive_unit_rankings import compute_and_write_rankings


def _outcome(winner=1, hp1=0.8, hp2=0.0):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=10.0,
        team1_hp_pct=hp1, team2_hp_pct=hp2,
        team1_survivors=24, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=4500,
        team1_start_count=30, team2_start_count=30,
    )


def test_derive_writes_role_and_composite_scores(tmp_path):
    matchup_path = tmp_path / "matchup.db"
    derived_path = tmp_path / "derived.db"
    ref_path = tmp_path / "ref.db"

    # Build a minimal ref DB with one civ + one unit
    rc = sqlite3.connect(str(ref_path))
    rc.executescript("""
      CREATE TABLE ref_units (id INTEGER PRIMARY KEY, civ_name TEXT, unit_slug TEXT,
        age TEXT, final_speed REAL, final_range REAL);
      INSERT INTO ref_units (civ_name, unit_slug, age, final_speed, final_range)
        VALUES ('Aztecs', 'elite_jaguar_warrior_aztecs', 'Imperial', 1.0, 0);
    """)
    rc.commit(); rc.close()

    mc = create_matchup_db(str(matchup_path))
    # Insert one row vs the Vikings champion yardstick
    insert_outcome(mc,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Vikings", opp_unit_slug="champion",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(winner=1, hp1=0.8, hp2=0.0),
        runs_count=1, score_stddev=None,
        dedup_group="abc", sim_version="v1",
    )
    insert_outcome(mc,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Vikings", opp_unit_slug="champion",
        scale="3k", my_count=30, opp_count=30,
        outcome=_outcome(winner=1, hp1=0.7, hp2=0.0),
        runs_count=1, score_stddev=None,
        dedup_group="abc", sim_version="v1",
    )
    mc.close()

    dc = create_derived_db(str(derived_path))

    n = compute_and_write_rankings(
        matchup_db_path=str(matchup_path),
        ref_db_path=str(ref_path),
        derived_db_path=str(derived_path),
        age="Imperial",
    )
    assert n > 0

    rows = sqlite3.connect(str(derived_path)).execute(
        "SELECT score_type, score_value FROM battle_scores WHERE civ_name='Aztecs'"
    ).fetchall()
    score_types = {r[0] for r in rows}
    # Champion is part of general_combat aggregation
    assert "general_combat" in score_types
    # militia line gets militia_value composite
    assert "militia_value" in score_types
