"""Filesystem contract for the project-local calibration workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ZIP_NAME = "aoe2_golden_STANDARD_UNITS_FINAL.zip"


@dataclass(frozen=True)
class CalibrationPaths:
    root: Path
    source_dir: Path
    source_zip: Path
    source_lock: Path
    tapes_dir: Path
    fixtures_dir: Path
    manifest: Path
    truth_dir: Path
    spawns: Path
    combat_dicts: Path
    matchups: Path
    fight_sets: Path
    runs_dir: Path
    reports_dir: Path
    docs_dir: Path
    scratch_dir: Path


def workspace_paths(root: Path | None = None) -> CalibrationPaths:
    """Return every calibration path closed over one explicit workspace."""
    base = (root or REPO_ROOT / "calibration").resolve()
    source = base / "source"
    fixtures = base / "fixtures"
    scratch = (
        base / ".scratch"
        if root is not None
        else REPO_ROOT / ".scratch" / "calibration"
    )
    return CalibrationPaths(
        root=base,
        source_dir=source,
        source_zip=source / SOURCE_ZIP_NAME,
        source_lock=source / "source_of_truth.json",
        tapes_dir=base / "tapes",
        fixtures_dir=fixtures,
        manifest=fixtures / "manifest.json",
        truth_dir=fixtures / "truth",
        spawns=fixtures / "spawns.json",
        combat_dicts=fixtures / "combat_dicts.json",
        matchups=fixtures / "matchups.json",
        fight_sets=fixtures / "fight_sets.json",
        runs_dir=base / "runs",
        reports_dir=base / "reports",
        docs_dir=base / "docs",
        scratch_dir=scratch,
    )
