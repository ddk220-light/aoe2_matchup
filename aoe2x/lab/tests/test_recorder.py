from __future__ import annotations

import contextlib
import io
import json

import pytest

from aoe2x.lab.cli import build_parser
from aoe2x.lab.config import load_config
from aoe2x.lab.errors import LiveCaptureError
from aoe2x.lab.live import _camera_configuration, _load_stack, _validate_scenario, golden_path, run_live
from aoe2x.lab.planner import make_request, plan_matchup
from aoe2x.lab.recording import recorder_retention, validate_recording_bundle, write_recording_bundle


def test_recorder_cli_keeps_raw_and_rejects_destructive_policy():
    args = build_parser().parse_args(["record", "--side2", "champion", "--side3", "paladin"])
    assert recorder_retention(args.mode, args.retention) == "raw"
    assert build_parser().parse_args(["batch", "queue.toml", "--phase", "recorder"]).phase == "recorder"
    for mode in ("archive", "stats"):
        with pytest.raises(ValueError, match="expanded raw"):
            recorder_retention("recorder", mode)


@pytest.mark.parametrize("sides", [
    ("elite_tiger_cavalry_wei", "paladin"),
    ("arbalester", "arbalester"),
    ("arbalester", "paladin"),
    ("paladin", "arbalester"),
])
def test_unequal_rosters_preserve_default1_camera_and_golden(sides, tmp_path):
    config = load_config()
    plan = plan_matchup(config, make_request(side2=sides[0], side3=sides[1], balance="explicit", n2=11, n3=23))
    stack = _load_stack(config)
    generated = tmp_path / "matchup.aoe2scenario"
    with contextlib.redirect_stdout(io.StringIO()):
        stack["build_run"](
            stack["resolve_side"](plan["side2"]["civ"], sides[0]),
            stack["resolve_side"](plan["side3"]["civ"], sides[1]), generated,
            counts=(11, 23), template=golden_path(config, plan["scenario"]["family"]),
            ranged=(plan["side2"]["ranged"], plan["side3"]["ranged"]),
        )
        assert _validate_scenario(config, plan, generated, stack)["cameraMatchesGolden"]
        scenario = stack["AoE2DEScenario"].from_file(str(generated))
        assert _camera_configuration(scenario) == ((0, 1, 8, 7, -1, 1),)
        scenario.trigger_manager.triggers[0].effects[0].location_x = 2
        tampered = tmp_path / "tampered.aoe2scenario"
        scenario.write_to_file(str(tampered))
        with pytest.raises(LiveCaptureError, match="camera"):
            _validate_scenario(config, plan, tampered, stack)


def test_recording_inventory_detects_missing_or_changed_video(tmp_path, monkeypatch):
    raw = tmp_path / "raw recordings"
    raw.mkdir()
    for suffix in (".mov", ".frames.bin", ".meta.json", ".END"):
        (raw / f"fight{suffix}").write_bytes(b"capture fixture")
    (raw / "fight.hp.json").write_text(json.dumps({"clock": "video", "game_speed": 1.7}))
    (tmp_path / "fight.aoe2scenario").write_bytes(b"scenario fixture")
    plan = {"matchupId": "fight", "jobId": "job", "planHash": "hash", "side2": {"slug": "a"}, "side3": {"slug": "b"}}
    monkeypatch.setattr("aoe2x.lab.recording.probe_video", lambda _: {"durationSeconds": 20})
    result = write_recording_bundle(tmp_path, plan, {"artifacts": {"video": "raw recordings/fight.mov"}})
    assert result["sides"]["side1"]["player"] == 2
    assert result["overlayApplied"] is False
    assert not list(tmp_path.rglob("*.zip"))
    validate_recording_bundle(tmp_path, plan)
    (raw / "fight.mov").write_bytes(b"tampered fixture")
    with pytest.raises(LiveCaptureError, match="missing or changed"):
        validate_recording_bundle(tmp_path, plan)


def test_recorder_resume_needs_no_game_and_default_live_cannot_delete_it(tmp_path, monkeypatch):
    from aoe2x.lab.artifacts import create_job
    from aoe2x.lab.io import read_json, write_json

    plan = {"matchupId": "fight", "jobId": "job", "planHash": "hash",
            "side2": {"count": 2}, "side3": {"count": 2}}
    job = create_job(tmp_path, "job")
    job.initialize({}, plan)
    run = job.live_directory / "run_001"
    raw = run / "raw recordings"
    raw.mkdir(parents=True)
    for suffix in (".mov", ".frames.bin", ".meta.json", ".END"):
        (raw / f"fight{suffix}").write_bytes(b"fixture")
    hp = {"clock": "video", "rows": [
        {"game_s": 0, "side1": {"count": 2, "hp": 200}, "side2": {"count": 2, "hp": 200}},
        {"game_s": 10, "side1": {"count": 1, "hp": 80}, "side2": {"count": 0, "hp": 0}},
    ]}
    write_json(raw / "fight.hp.json", hp)
    (run / "fight.aoe2scenario").write_bytes(b"scenario")
    capture = {"artifacts": {"video": "raw recordings/fight.mov", "sidecar": "raw recordings/fight.hp.json"},
               "startCounts": [2, 2], "winnerOwner": 2, "signedRemainingHpPercent": 40}
    monkeypatch.setattr("aoe2x.lab.recording.probe_video", lambda _: {"durationSeconds": 20})
    write_recording_bundle(run, plan, capture)
    write_json(run / "manifest.json", {"capture": capture, "mode": "recorder", "retention": {"mode": "raw"}})
    monkeypatch.setattr("aoe2x.lab.live._load_stack", lambda _: {})
    def no_game(*args, **kwargs):
        pytest.fail("a completed recorder resume must not inspect or operate the game")
    monkeypatch.setattr("aoe2x.lab.live.preflight_live", no_game)
    for mode in ("recorder", "statistics"):
        summary = run_live(load_config(), job, repeats=1, mode=mode)
        assert summary["repeatCount"] == 1
        assert read_json(run / "manifest.json")["retention"]["mode"] == "raw"
        assert (raw / "fight.mov").exists()
