import sqlite3
import pytest

from battle_outcome import BattleOutcome
from matchup_db import create_db as create_matchup_db, insert_outcome
from derived_db import create_db as create_derived_db
from derive_advisor_recs import compute_and_write_recs


def _outcome(winner=1, hp1=0.8, hp2=0.0):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=10.0,
        team1_hp_pct=hp1, team2_hp_pct=hp2,
        team1_survivors=24, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=4500,
        team1_start_count=30, team2_start_count=30,
    )


def test_recommends_unit_with_highest_mean_score(tmp_path):
    matchup_path = tmp_path / "m.db"
    derived_path = tmp_path / "d.db"
    ref_path = tmp_path / "ref.db"

    # Minimal ref DB so unit_name lookup works
    rc = sqlite3.connect(str(ref_path))
    rc.executescript("""
      CREATE TABLE ref_units (id INTEGER PRIMARY KEY, civ_name TEXT, unit_slug TEXT,
        unit_name TEXT, age TEXT);
      INSERT INTO ref_units (civ_name, unit_slug, unit_name, age)
        VALUES ('Aztecs', 'elite_eagle', 'Elite Eagle Warrior', 'Imperial'),
               ('Aztecs', 'champion', 'Champion', 'Imperial');
    """)
    rc.commit(); rc.close()

    mc = create_matchup_db(str(matchup_path))
    # Aztecs has 2 candidate top units; Eagle wins big, Champion barely wins.
    for opp in ["arbalester", "halberdier", "champion"]:
        insert_outcome(mc, my_civ="Aztecs", my_unit_slug="elite_eagle",
            opp_civ="Britons", opp_unit_slug=opp, scale="30v30",
            my_count=30, opp_count=30,
            outcome=_outcome(winner=1, hp1=0.9, hp2=0.0),
            runs_count=1, score_stddev=None, dedup_group="x", sim_version="v1")
        insert_outcome(mc, my_civ="Aztecs", my_unit_slug="champion",
            opp_civ="Britons", opp_unit_slug=opp, scale="30v30",
            my_count=30, opp_count=30,
            outcome=_outcome(winner=1, hp1=0.2, hp2=0.0),
            runs_count=1, score_stddev=None, dedup_group="y", sim_version="v1")
    mc.close()

    create_derived_db(str(derived_path)).close()
    n = compute_and_write_recs(
        matchup_db_path=str(matchup_path),
        derived_db_path=str(derived_path),
        ref_db_path=str(ref_path),
    )
    assert n >= 2

    rows = sqlite3.connect(str(derived_path)).execute(
        "SELECT rec_rank, unit_slug, score FROM advisor_recommendations "
        "WHERE civ='Aztecs' AND opponent='Britons' AND rec_type='top' ORDER BY rec_rank"
    ).fetchall()
    assert rows[0][1] == "elite_eagle"   # rank 1 should be Eagle
    assert rows[1][1] == "champion"
