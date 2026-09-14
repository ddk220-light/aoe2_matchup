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
    monkeypatch.setattr(campaign, "finalize_recording", lambda _: {"durationSeconds": 12, "framesBytes": 2000000})
    monkeypatch.setattr(campaign, "read_json", lambda _: {})
    monkeypatch.setattr(campaign, "validate_recording_bundle", lambda *args: {
        "presentation": {"media": {"durationSeconds": 12}},
        "files": {"frames": {"bytes": 2000000}}})


def test_ten_match_report_and_final_remainder(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path, 13)
    assert campaign.run(Path("queue"), tmp_path) == 0
    assert len(read_json(tmp_path / "report_010.json")["results"]) == 10
    assert read_json(tmp_path / "report_013.json")["state"] == "COMPLETE"
    assert read_json(tmp_path / "status.json")["completed"] == 13


def test_repeated_failure_stops_and_reports_without_false_success(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path, 13, fail=True)
    assert campaign.run(Path("queue"), tmp_path) == 2
    state = read_json(tmp_path / "status.json")
    assert state["state"] == "STOPPED_AFTER_ERRORS"
    assert state["completed"] == 0 and state["failed"] == 3
    assert len(state["results"]) == 3


def test_next_capture_runs_before_previous_export_finishes(monkeypatch, tmp_path):
    from threading import Event
    setup_queue(monkeypatch, tmp_path, 2)
    second_capture = Event()
    first_finalizing = Event()
    def capture(config, job, **kwargs):
        assert kwargs["defer_clip"]
        if job.job_id == "job_1":
            assert first_finalizing.wait(2)
            assert read_json(tmp_path / "status.json")["completed"] == 0
            second_capture.set()
    def finalize(job):
        if job.job_id == "job_0":
            first_finalizing.set()
            assert second_capture.wait(2), "encoding blocked the next capture"
        return {"durationSeconds": 12, "framesBytes": 2000000}
    monkeypatch.setattr(campaign, "run_live", capture)
    monkeypatch.setattr(campaign, "finalize_recording", finalize)
    assert campaign.run(Path("queue"), tmp_path) == 0
    assert read_json(tmp_path / "status.json")["completed"] == 2


def test_failed_export_preserves_failure_and_continues_capture(monkeypatch, tmp_path):
    setup_queue(monkeypatch, tmp_path, 2)
    def finalize(job):
        if job.job_id == "job_0":
            raise RuntimeError("export failed; raw retained")
        return {"durationSeconds": 12, "framesBytes": 2000000}
    monkeypatch.setattr(campaign, "finalize_recording", finalize)
    assert campaign.run(Path("queue"), tmp_path) == 2
    state = read_json(tmp_path / "status.json")
    assert state["completed"] == 1 and state["failed"] == 1


def test_game_lock_released_before_final_export_finishes(monkeypatch, tmp_path):
    from threading import Event
    setup_queue(monkeypatch, tmp_path, 1)
    released = Event()

    def finalize(job):
        assert released.wait(2), "last export blocked release of the game"
        return {"durationSeconds": 12, "framesBytes": 2000000}

    monkeypatch.setattr(campaign, "finalize_recording", finalize)
    assert campaign.run(Path("queue"), tmp_path, release_capture=released.set) == 0
    assert read_json(tmp_path / "status.json")["captureReleased"] is True
