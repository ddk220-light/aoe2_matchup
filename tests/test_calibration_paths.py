import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

import aoe2x.calibration.source as source_mod
from aoe2x.calibration.paths import workspace_paths
from aoe2x.calibration.source import CalibrationSourceError, verify_source_archive


REPO = Path(__file__).resolve().parents[1]


def test_default_workspace_is_inside_repo():
    """Catch a regression that sends calibration data outside this checkout."""
    paths = workspace_paths()

    assert paths.root == REPO / "calibration"
    assert paths.source_zip == (
        paths.root / "source" / "aoe2_golden_STANDARD_UNITS_FINAL.zip"
    )
    assert paths.manifest == paths.root / "fixtures" / "manifest.json"
    assert paths.runs_dir == paths.root / "runs"
    assert paths.scratch_dir == REPO / ".scratch" / "calibration"


def test_explicit_workspace_override_keeps_every_write_under_test_root(tmp_path):
    """Catch a partial override that still writes one artifact to the real repo."""
    paths = workspace_paths(tmp_path / "workspace")

    assert paths.root == (tmp_path / "workspace").resolve()
    for child in (
        paths.source_dir,
        paths.tapes_dir,
        paths.fixtures_dir,
        paths.truth_dir,
        paths.runs_dir,
        paths.reports_dir,
        paths.docs_dir,
        paths.scratch_dir,
    ):
        assert child.is_relative_to(paths.root)


def _write_lock(paths, sha256, **overrides):
    payload = {
        "archive": paths.source_zip.name,
        "sha256": sha256,
        "recordings": 339,
        "unordered_matchups": 91,
        "standard_units": 14,
    }
    payload.update(overrides)
    paths.source_lock.write_text(json.dumps(payload), encoding="utf-8")


def _make_locked_test_archive(tmp_path):
    paths = workspace_paths(tmp_path / "calibration")
    paths.source_dir.mkdir(parents=True)
    with ZipFile(paths.source_zip, "w") as zf:
        zf.writestr("standard_units/decoded/f.meta.json", "{}")
    digest = hashlib.sha256(paths.source_zip.read_bytes()).hexdigest().upper()
    _write_lock(paths, digest)
    return paths, digest


def test_verify_source_archive_accepts_exact_locked_zip(tmp_path, monkeypatch):
    """Catch rejection of the one archive matching both code and source lock."""
    paths, digest = _make_locked_test_archive(tmp_path)
    monkeypatch.setattr(source_mod, "FINAL_SHA256", digest)

    lock = verify_source_archive(paths)

    assert lock["sha256"] == digest
    assert lock["recordings"] == 339


@pytest.mark.parametrize(
    ("condition", "message"),
    [
        ("missing", "missing"),
        ("wrong_hash", "SHA-256"),
        ("wrong_name", "archive"),
        ("wrong_counts", "recordings"),
    ],
)
def test_verify_source_archive_fails_closed(tmp_path, condition, message):
    """Catch any fallback that accepts absent, renamed, or non-FINAL evidence."""
    paths = workspace_paths(tmp_path / "calibration")
    paths.source_dir.mkdir(parents=True)
    if condition != "missing":
        with ZipFile(paths.source_zip, "w") as zf:
            zf.writestr("standard_units/decoded/f.meta.json", "{}")
    overrides = {}
    if condition == "wrong_name":
        overrides["archive"] = "old.zip"
    if condition == "wrong_counts":
        overrides["recordings"] = 338
    lock_hash = source_mod.FINAL_SHA256 if condition == "wrong_counts" else "0" * 64
    _write_lock(paths, lock_hash, **overrides)

    with pytest.raises(CalibrationSourceError, match=message):
        verify_source_archive(paths)


def test_source_cli_reports_verified_contract(tmp_path, capsys, monkeypatch):
    """Catch a CLI that succeeds without reporting the corpus it verified."""
    paths, digest = _make_locked_test_archive(tmp_path)
    monkeypatch.setattr(source_mod, "FINAL_SHA256", digest)

    assert source_mod.main(["--workspace-root", str(paths.root)]) == 0

    out = capsys.readouterr().out
    assert paths.source_zip.name in out
    assert f"sha256={digest}" in out
    assert "recordings=339" in out
    assert "unordered_matchups=91" in out
    assert "standard_units=14" in out
