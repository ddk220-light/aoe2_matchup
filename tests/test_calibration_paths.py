from pathlib import Path

from aoe2x.calibration.paths import workspace_paths


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
