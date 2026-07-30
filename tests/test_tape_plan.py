import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "data" / "validation" / "tape_plan.json"
DICTS = REPO / "data" / "validation" / "tape_combat_dicts.json"


def test_dump_tape_dicts_produces_plan_and_dicts():
    subprocess.run([sys.executable, "tools/simjs/dump_tape_dicts.py"],
                   cwd=str(REPO), check=True, capture_output=True)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    dicts = json.loads(DICTS.read_text(encoding="utf-8"))

    assert len(plan["rows"]) == 38
    # every unit referenced by the plan has a combat dict
    for r in plan["rows"]:
        assert f'{r["subject_civ"]}|{r["subject_slug"]}' in dicts
        assert f'{r["opp_civ"]}|{r["opp_slug"]}' in dicts
    # the recorder's own cost rule must reproduce the recorded counts exactly
    for r in plan["rows"]:
        assert r["counts"]["equal_resource"] == r["counts"]["tape"], r["plan_id"]
    # equal_count is N v N at the subject count
    for r in plan["rows"]:
        n1, _ = r["counts"]["tape"]
        assert r["counts"]["equal_count"] == [n1, n1]
