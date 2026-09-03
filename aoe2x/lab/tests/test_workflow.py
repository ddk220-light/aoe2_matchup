from __future__ import annotations

import json
import zipfile

import pytest

from aoe2x.lab.artifacts import create_batch, create_job
from aoe2x.lab.compare import compare_job
from aoe2x.lab.errors import LabError
from aoe2x.lab.config import load_config
from aoe2x.lab.io import write_json
from aoe2x.lab.live import _load_stack, _validate_scenario, golden_path
from aoe2x.lab.planner import make_request, plan_matchup
from aoe2x.lab.retention import apply_run_retention, validate_retained_statistics
from aoe2x.lab.simulation import worker_count


def _plan(plan_hash: str = "plan-a") -> dict:
    return {
        "schemaVersion": 1,
        "jobId": "test_job",
        "matchupId": "arbalester_vs_paladin",
        "planHash": plan_hash,
    }


def test_job_resume_requires_the_identical_plan(tmp_path):
    job = create_job(tmp_path, "test_job")
    job.initialize({"schemaVersion": 1}, _plan())
    job.initialize({"schemaVersion": 1}, _plan())

    with pytest.raises(LabError, match="different plan"):
        job.initialize({"schemaVersion": 1}, _plan("plan-b"))


def test_comparison_uses_percentage_points_and_lists_every_wrong_seed(tmp_path):
    job = create_job(tmp_path, "test_job")
    job.initialize({"schemaVersion": 1}, _plan())
    write_json(job.live_directory / "summary.json", {
        "repeatCount": 1,
        "winnerOwners": [2],
        "meanSignedRemainingHpPercent": 22.0,
    })
    write_json(job.simulation_directory / "summary.json", {
        "seedCount": 2,
        "winnerOwners": [2, 3],
        "meanSignedRemainingHpPercent": 33.0,
        "seeds": [
            {"seed": 1, "winnerOwner": 2},
            {"seed": 2, "winnerOwner": 3},
        ],
    })

    report = compare_job(job, threshold_points=10.0)

    assert report["deltaPoints"] == 11.0
    assert report["absoluteDeltaPoints"] == 11.0
    assert report["wrongWinner"] is True
    assert report["wrongWinnerSeeds"] == [2]
    assert report["representativeSeed"] == 2
    assert report["viewerPath"].endswith("job=test_job&seed=2")
    assert job.manifest()["viewer"]["seed"] == 2
    assert report["accepted"] is False


def test_batch_identity_is_stable_and_manifest_is_durable(tmp_path):
    source = tmp_path / "queue.toml"
    source.write_text("schemaVersion = 1\n", encoding="utf-8")
    requests = [{"schemaVersion": 1, "side2": "a", "side3": "b"}]

    first = create_batch(tmp_path, source, requests)
    second = create_batch(tmp_path, source, requests)
    first.update_job("request_001", state="FAILED")

    assert first.batch_id == second.batch_id
    assert json.loads(first.manifest_path.read_text(encoding="utf-8"))["jobs"][
        "request_001"
    ]["state"] == "FAILED"


def test_worker_count_uses_available_compute_without_oversubscribing_tasks(monkeypatch):
    monkeypatch.setattr("aoe2x.lab.simulation.os.cpu_count", lambda: 16)
    assert worker_count(0, 5) == 5
    assert worker_count(3, 20) == 3


def test_mixed_live_build_preserves_p4_diplomacy_ai_and_trigger_structure(tmp_path):
    config = load_config()
    plan = plan_matchup(config, make_request(
        side2="arbalester",
        side3="paladin",
        civ2="Chinese",
        civ3="Spanish",
        balance="explicit",
        n2=1,
        n3=1,
    ))
    stack = _load_stack(config)
    generated = tmp_path / "mixed.aoe2scenario"
    side2 = stack["resolve_side"](plan["side2"]["civ"], plan["side2"]["slug"])
    side3 = stack["resolve_side"](plan["side3"]["civ"], plan["side3"]["slug"])
    stack["build_run"](
        side2,
        side3,
        generated,
        counts=(1, 1),
        ranged=(True, False),
        template=golden_path(config, "ranged_vs_melee"),
    )

    report = _validate_scenario(config, plan, generated, stack)

    assert report["player4Unchanged"] is True
    assert report["aiConfigurationMatchesGolden"] is True
    assert report["playerRuntimeConfigurationMatchesGolden"] is True
    assert report["triggerStructureMatchesGolden"] is True


def _retained_run(tmp_path):
    raw = tmp_path / "raw recordings"
    raw.mkdir()
    (raw / "fight.mov").write_bytes(b"video")
    (raw / "fight.frames.bin").write_bytes(b"frames")
    (raw / "fight.meta.json").write_text("{}", encoding="utf-8")
    (raw / "fight.END").write_text("done", encoding="utf-8")
    sidecar = {
        "rows": [
            {
                "side1": {"count": 2, "hp": 200},
                "side2": {"count": 2, "hp": 300},
            },
            {
                "side1": {"count": 1, "hp": 40},
                "side2": {"count": 0, "hp": 0},
            },
        ]
    }
    (raw / "fight.hp.json").write_text(json.dumps(sidecar), encoding="utf-8")
    (tmp_path / "capture.log").write_text("diagnostic", encoding="utf-8")
    manifest = {
        "capture": {
            "startCounts": [2, 2],
            "artifacts": {"sidecar": "raw recordings/fight.hp.json"},
        }
    }
    return raw, manifest


def test_stats_retention_deletes_raw_capture_but_keeps_hp_and_logs(tmp_path):
    raw, manifest = _retained_run(tmp_path)

    retention = apply_run_retention(tmp_path, "stats")
    manifest["retention"] = retention
    capture = validate_retained_statistics(tmp_path, manifest, (2, 2))

    assert not (raw / "fight.mov").exists()
    assert not (raw / "fight.frames.bin").exists()
    assert (raw / "fight.hp.json").exists()
    assert (tmp_path / "capture.log").exists()
    assert retention["recordingsRetained"] is False
    assert capture["winnerRemainingHpPercent"] == pytest.approx(20.0)


def test_archive_retention_zips_then_removes_expanded_raw_capture(tmp_path):
    raw, manifest = _retained_run(tmp_path)

    retention = apply_run_retention(tmp_path, "archive")
    manifest["retention"] = retention
    validate_retained_statistics(tmp_path, manifest, (2, 2))

    archive = tmp_path / "recordings.zip"
    assert archive.exists()
    assert not (raw / "fight.mov").exists()
    assert (raw / "fight.hp.json").exists()
    with zipfile.ZipFile(archive) as bundle:
        assert "raw recordings/fight.mov" in bundle.namelist()
        assert "raw recordings/fight.frames.bin" in bundle.namelist()


def test_default_lab_retention_is_stats():
    config = load_config()
    assert config.live_retention == "stats"
    assert config.live_min_free_bytes == 2 * 1024 ** 3
