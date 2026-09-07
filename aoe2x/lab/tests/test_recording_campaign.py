from pathlib import Path
from types import SimpleNamespace

from aoe2x.lab import recording_campaign as campaign
from aoe2x.lab.io import read_json


def setup_queue(monkeypatch, tmp_path, count, fail=False):
    monkeypatch.setattr(campaign, "load_config", lambda: None)
    monkeypatch.setattr(campaign, "_load_batch", lambda _: ({}, list(range(count))))
    monkeypatch.setattr(campaign, "_job", lambda _, i: (SimpleNamespace(
        job_id=f"job_{i}", live_directory=tmp_path / f"job_{i}",
        plan_path=Path("unused"), record_failure=lambda *a, **k: None), None))
    def capture(*args, **kwargs):
        assert kwargs["mode"] == "recorder" and kwargs["retention"] == "raw"
        if fail:
            raise RuntimeError("game unavailable")
    monkeypatch.setattr(campaign, "run_live", capture)
    monkeypatch.setattr(campaign, "read_json", lambda _: {})
    monkeypatch.setattr(campaign, "validate_recording_bundle", lambda *args: {
        "presentation": {"media": {"durationSeconds": 12}},
        "files": {"frames": {"bytes": 2000000}}})


def test_ten_match_report_and_final_remainder(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path, 13)
    assert campaign.run(Path("queue"), tmp_path) == 0
    assert read_json(tmp_path / "report_010.json")["completed"] == 10
    assert read_json(tmp_path / "report_013.json")["state"] == "COMPLETE"
    assert read_json(tmp_path / "status.json")["completed"] == 13


def test_repeated_failure_stops_and_reports_without_false_success(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path, 13, fail=True)
    assert campaign.run(Path("queue"), tmp_path) == 2
    state = read_json(tmp_path / "status.json")
    assert state["state"] == "STOPPED_AFTER_ERRORS"
    assert state["completed"] == 0 and state["failed"] == 3
    assert len(state["results"]) == 3
