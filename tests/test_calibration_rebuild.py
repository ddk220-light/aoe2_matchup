import json
import shutil
from pathlib import Path

import pytest

from aoe2x.calibration.paths import workspace_paths
from aoe2x.calibration.rebuild import _publish_staged_workspace, rebuild_final
from aoe2x.calibration.source import CalibrationSourceError, FINAL_SHA256


LOCAL_FINAL = workspace_paths().source_zip
LOCAL_LOCK = workspace_paths().source_lock


def test_publish_staged_workspace_replaces_instead_of_appending(tmp_path):
    """Catch stale truth/tape files surviving a supposedly clean rebuild."""
    target = workspace_paths(tmp_path / "target")
    staged = workspace_paths(tmp_path / "staged")
    target.truth_dir.mkdir(parents=True)
    staged.truth_dir.mkdir(parents=True)
    target.tapes_dir.mkdir(parents=True)
    staged.tapes_dir.mkdir(parents=True)
    (target.truth_dir / "stale_old_tape.json").write_text("{}", encoding="utf-8")
    (staged.truth_dir / "final.json").write_text("{}", encoding="utf-8")
    (staged.tapes_dir / "final.stream").write_text("final", encoding="utf-8")

    _publish_staged_workspace(staged, target)

    assert not (target.truth_dir / "stale_old_tape.json").exists()
    assert (target.truth_dir / "final.json").exists()
    assert (target.tapes_dir / "final.stream").read_text(encoding="utf-8") == "final"


def test_rebuild_verifies_source_before_mutating(tmp_path):
    """Catch a missing-source rebuild deleting the last valid fixture set."""
    paths = workspace_paths(tmp_path / "calibration")
    paths.fixtures_dir.mkdir(parents=True)
    marker = paths.fixtures_dir / "must-survive.txt"
    marker.write_text("unchanged", encoding="utf-8")

    with pytest.raises(CalibrationSourceError):
        rebuild_final(paths)

    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_publish_rolls_back_when_second_directory_move_fails(tmp_path, monkeypatch):
    """Catch publication leaving new tapes paired with old/missing fixtures."""
    target = workspace_paths(tmp_path / "target")
    staged = workspace_paths(tmp_path / "staged")
    target.tapes_dir.mkdir(parents=True)
    target.fixtures_dir.mkdir(parents=True)
    staged.tapes_dir.mkdir(parents=True)
    staged.fixtures_dir.mkdir(parents=True)
    (target.tapes_dir / "old.txt").write_text("old tapes", encoding="utf-8")
    (target.fixtures_dir / "old.txt").write_text("old fixtures", encoding="utf-8")
    (staged.tapes_dir / "new.txt").write_text("new tapes", encoding="utf-8")
    (staged.fixtures_dir / "new.txt").write_text("new fixtures", encoding="utf-8")

    original_replace = Path.replace

    def fail_new_fixtures(self, target_path):
        if self == staged.fixtures_dir:
            raise OSError("injected fixture publication failure")
        return original_replace(self, target_path)

    monkeypatch.setattr(Path, "replace", fail_new_fixtures)

    with pytest.raises(OSError, match="injected fixture publication failure"):
        _publish_staged_workspace(staged, target)

    assert (target.tapes_dir / "old.txt").read_text(encoding="utf-8") == "old tapes"
    assert (target.fixtures_dir / "old.txt").read_text(encoding="utf-8") == "old fixtures"


@pytest.mark.skipif(not LOCAL_FINAL.exists(), reason="ignored FINAL archive is not installed")
def test_rebuild_final_publishes_complete_final_corpus(tmp_path):
    """Catch incomplete, appended, or non-FINAL publication end to end."""
    paths = workspace_paths(tmp_path / "calibration")
    paths.source_dir.mkdir(parents=True)
    shutil.copy2(LOCAL_FINAL, paths.source_zip)
    shutil.copy2(LOCAL_LOCK, paths.source_lock)
    paths.truth_dir.mkdir(parents=True)
    (paths.truth_dir / "stale_old_tape.json").write_text("{}", encoding="utf-8")
    paths.fight_sets.write_text(
        json.dumps({"melee": ["project_policy"]}), encoding="utf-8"
    )

    summary = rebuild_final(paths)

    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))["fights"]
    assert summary == {
        "recordings": 339,
        "truth_cards": 339,
        "unordered_matchups": 91,
    }
    assert len(manifest) == 339
    assert len(list(paths.truth_dir.glob("*.json"))) == 339
    assert not (paths.truth_dir / "stale_old_tape.json").exists()
    assert json.loads(paths.fight_sets.read_text(encoding="utf-8")) == {
        "melee": ["project_policy"]
    }
    assert {row["zip_sha256"].upper() for row in manifest} == {FINAL_SHA256}
    assert {row["source_archive"] for row in manifest} == {paths.source_zip.name}
    assert len({row["matchup"] for row in manifest}) == 91
    assert len(
        {
            side["slug"]
            for row in manifest
            for side in (row["side1"], row["side2"])
        }
    ) == 14
