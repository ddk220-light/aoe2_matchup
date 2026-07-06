# apps/video/tests/test_queue_runner.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto.queue_runner import run_matchup_queue


def spec(i, **kw):
    d = {"civ1": "Muisca", "slug1": "elite_temple_guard_muisca",
         "civ2": "Aztecs", "slug2": f"opp_{i}", "name": f"clip_{i}",
         "label": f"Label {i}", "category": "expected_win", "why": "because"}
    d.update(kw)
    return d


def fake_runner_factory(fail_names=(), calls=None):
    def fake_run(s, out_dir):
        if calls is not None:
            calls.append(s["name"])
        if s["name"] in fail_names:
            raise RuntimeError("boom")
        p = Path(out_dir) / f"{s['name']}.mp4"
        p.write_bytes(b"fake")
        return p
    return fake_run


def test_writes_manifest_with_metadata(tmp_path):
    specs = [spec(1), spec(2)]
    res = run_matchup_queue(specs, tmp_path, run_one=fake_runner_factory())
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert [c["label"] for c in m["clips"]] == ["Label 1", "Label 2"]
    assert all(c["status"] == "done" and c["category"] == "expected_win"
               for c in m["clips"])
    assert len(res.done) == 2 and not res.failed


def test_resume_skips_existing(tmp_path):
    calls = []
    run_matchup_queue([spec(1)], tmp_path,
                      run_one=fake_runner_factory(calls=calls))
    run_matchup_queue([spec(1), spec(2)], tmp_path,
                      run_one=fake_runner_factory(calls=calls))
    assert calls == ["clip_1", "clip_2"]      # clip_1 not re-run


def test_failure_recorded_and_queue_continues(tmp_path):
    res = run_matchup_queue([spec(1), spec(2)], tmp_path,
                            run_one=fake_runner_factory(fail_names=("clip_1",)))
    m = json.loads((tmp_path / "manifest.json").read_text())
    st = {c["name"]: c["status"] for c in m["clips"]}
    assert st == {"clip_1": "failed", "clip_2": "done"}
    assert [s["name"] for s in res.failed] == ["clip_1"]
