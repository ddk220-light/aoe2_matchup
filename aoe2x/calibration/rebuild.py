"""Cleanly rebuild the active calibration workspace from FINAL."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from .paths import CalibrationPaths, workspace_paths
from .source import FINAL_SHA256, verify_source_archive


def _remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _publish_staged_workspace(
    staged: CalibrationPaths,
    target: CalibrationPaths,
) -> None:
    """Replace tapes and fixtures together, restoring both on any failure."""
    target.root.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    pairs = (
        (staged.tapes_dir, target.tapes_dir),
        (staged.fixtures_dir, target.fixtures_dir),
    )
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for _source, destination in pairs:
            if destination.exists():
                backup = destination.with_name(f".{destination.name}.backup-{token}")
                destination.replace(backup)
                backups[destination] = backup
        for source, destination in pairs:
            source.replace(destination)
            published.append(destination)
    except Exception:
        for destination in reversed(published):
            _remove_tree(destination)
        for destination, backup in backups.items():
            if backup.exists():
                backup.replace(destination)
        raise
    else:
        for backup in backups.values():
            _remove_tree(backup)


def rebuild_final(
    paths: CalibrationPaths | None = None,
) -> dict[str, int]:
    """Rebuild FINAL into staging and publish only after validation."""
    resolved = paths or workspace_paths()
    verify_source_archive(resolved)
    staging_root = resolved.scratch_dir / f"rebuild-{uuid4().hex}"
    staged = workspace_paths(staging_root)
    try:
        from .extract import write_truth_cards
        from .ingest import ingest_zip

        run_ids = ingest_zip(resolved.source_zip, paths=staged)
        written = write_truth_cards(paths=staged)
        manifest = json.loads(staged.manifest.read_text(encoding="utf-8"))["fights"]
        matchups = {row["matchup"] for row in manifest}
        unit_slugs = {
            side["slug"]
            for row in manifest
            for side in (row["side1"], row["side2"])
        }
        if len(run_ids) != 339 or len(manifest) != 339:
            raise RuntimeError(
                f"FINAL rebuild expected 339 recordings, got "
                f"run_ids={len(run_ids)} manifest={len(manifest)}"
            )
        if len(written) != 339 or len(list(staged.truth_dir.glob("*.json"))) != 339:
            raise RuntimeError("FINAL rebuild expected exactly 339 truth cards")
        if len(matchups) != 91:
            raise RuntimeError(f"FINAL rebuild expected 91 matchups, got {len(matchups)}")
        if len(unit_slugs) != 14:
            raise RuntimeError(f"FINAL rebuild expected 14 units, got {len(unit_slugs)}")
        if {str(row["zip_sha256"]).upper() for row in manifest} != {FINAL_SHA256}:
            raise RuntimeError("FINAL rebuild manifest contains a non-FINAL archive hash")
        if {row.get("source_archive") for row in manifest} != {resolved.source_zip.name}:
            raise RuntimeError("FINAL rebuild manifest contains an unexpected source archive")
        _publish_staged_workspace(staged, resolved)
        return {
            "recordings": len(manifest),
            "truth_cards": len(written),
            "unordered_matchups": len(matchups),
        }
    finally:
        scratch_root = resolved.scratch_dir.resolve()
        candidate = staging_root.resolve()
        if candidate.is_relative_to(scratch_root):
            shutil.rmtree(candidate, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild the project-local calibration workspace from FINAL."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Override the calibration workspace root (intended for tests).",
    )
    args = parser.parse_args(argv)
    paths = workspace_paths(args.workspace_root) if args.workspace_root else workspace_paths()
    print(json.dumps(rebuild_final(paths), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
