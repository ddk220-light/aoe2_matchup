import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "validation" / "tape_runs.db"


def test_list_shows_engine_and_max_seconds():
    out = subprocess.run(
        [sys.executable, "-m", "aoe2x.validation.report", "--list"],
        cwd=str(REPO), check=True, capture_output=True).stdout.decode()
    assert "simulation_real.py" in out, "engine column must be printed"
    assert "max_s=" in out, "max_seconds must be printed"


def test_diff_warns_across_engines_or_caps():
    db = sqlite3.connect(str(DB))
    tags = {}
    for tag, engine, max_s in db.execute(
            "SELECT run_tag, engine, max_seconds FROM tape_runs ORDER BY started_utc"):
        tags.setdefault((engine, max_s), tag)
    pairs = list(tags.values())
    if len(pairs) < 2:
        return  # nothing to compare yet
    out = subprocess.run(
        [sys.executable, "-m", "aoe2x.validation.report", "--diff", pairs[0], pairs[-1]],
        cwd=str(REPO), check=True, capture_output=True).stdout.decode(errors='replace')
    assert "WARNING" in out
