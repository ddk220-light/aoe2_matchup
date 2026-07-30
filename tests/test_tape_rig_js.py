import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_tape_rig_js_records_a_js_run(tmp_path):
    db_path = tmp_path / "t.db"
    subprocess.run(
        [sys.executable, "-m", "aoe2x.validation.tape_rig_js",
         "--label", "unit-test", "--seeds", "1", "--scales", "tape",
         "--out", str(db_path)],
        cwd=str(REPO), check=True, capture_output=True)

    db = sqlite3.connect(str(db_path))
    runs = list(db.execute(
        "SELECT run_tag, engine, python_impl, max_seconds, seeds, n_fights FROM tape_runs"))
    assert len(runs) == 1
    run_tag, engine, impl, max_s, seeds, n_fights = runs[0]
    assert engine == "js apps/website/static/js/engine"
    assert impl.startswith("Node ")
    assert max_s == 600.0
    assert seeds == 1
    assert n_fights == 38

    battles = list(db.execute(
        "SELECT winner, end_reason, sim_outcome, agrees, tape_outcome,"
        " team1_hp_pct, my_count, opp_count FROM tape_battles WHERE run_tag=?",
        (run_tag,)))
    assert len(battles) == 38
    for w, er, so, ag, tape, hp1, n1, n2 in battles:
        assert w in (0, 1, 2)
        assert er in ("eliminated", "time_cap")
        assert so in ("win", "loss")
        assert ag in (0, 1)
        assert so == ("win" if w == 1 else "loss")
        assert 0.0 <= hp1 <= 1.0
        assert n1 >= 1 and n2 >= 1


def test_js_sim_version_differs_from_python():
    from aoe2x.validation.tape_rig_js import js_sim_version
    from aoe2x.sim.sim_version import compute_sim_version
    assert js_sim_version() != compute_sim_version()
    assert len(js_sim_version()) == 16
