# tests/test_matchup_diff.py
import os, sqlite3, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
import matchup_diff


def _mk_matchup(path, rows):
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE matchup_battles (my_civ TEXT, my_unit_slug TEXT,
        opp_civ TEXT, opp_unit_slug TEXT, scale TEXT, winner INTEGER,
        team1_hp_pct REAL, team2_hp_pct REAL)""")
    c.executemany("INSERT INTO matchup_battles VALUES (?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()


def test_row_score():
    assert matchup_diff.row_score({"winner": 1, "team1_hp_pct": 0.8, "team2_hp_pct": 0.0}) == 80.0
    assert matchup_diff.row_score({"winner": 2, "team1_hp_pct": 0.0, "team2_hp_pct": 0.5}) == -50.0
    assert matchup_diff.row_score({"winner": 0, "team1_hp_pct": 0.0, "team2_hp_pct": 0.0}) == 0.0


def test_snapshot_and_diff_flip(tmp_path):
    before = str(tmp_path / "before.db")
    after = str(tmp_path / "after.db")
    # BEFORE: Tiger Cav (my) beats Knight (opp), winner=1 score +60
    _mk_matchup(before, [("Wei", "tiger_cavalry_wei", "Franks", "knight", "30v30", 1, 0.6, 0.0)])
    # AFTER: nerfed -> now loses, winner=2 score -20
    _mk_matchup(after, [("Wei", "tiger_cavalry_wei", "Franks", "knight", "30v30", 2, 0.0, 0.2)])
    snap = matchup_diff.snapshot(before, {"tiger_cavalry_wei"})
    changes = matchup_diff.diff_outcomes(snap, after, {"tiger_cavalry_wei"})
    assert len(changes) == 1
    ch = changes[0]
    assert ch["old_winner"] == 1 and ch["new_winner"] == 2
    assert ch["old_score"] == 60.0 and ch["new_score"] == -20.0
    assert ch["swing"] == -80.0
