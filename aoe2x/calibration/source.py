"""Verify the sole allowed standard-unit tape archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence
from zipfile import BadZipFile, ZipFile

from .paths import CalibrationPaths, SOURCE_ZIP_NAME, workspace_paths


FINAL_SHA256 = "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9"
EXPECTED_COUNTS = {
    "recordings": 339,
    "unordered_matchups": 91,
    "standard_units": 14,
}
LOCK_FIELDS = {"archive", "sha256", *EXPECTED_COUNTS}


class CalibrationSourceError(RuntimeError):
    """The configured calibration evidence is absent or not exactly FINAL."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_source_lock(paths: CalibrationPaths) -> dict[str, object]:
    if not paths.source_lock.is_file():
        raise CalibrationSourceError(f"source lock is missing: {paths.source_lock}")
    try:
        lock = json.loads(paths.source_lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalibrationSourceError(f"invalid source lock: {paths.source_lock}") from exc
    if not isinstance(lock, dict):
        raise CalibrationSourceError("source lock must be a JSON object")
    fields = set(lock)
    if fields != LOCK_FIELDS:
        raise CalibrationSourceError(
            f"source lock fields differ: missing={sorted(LOCK_FIELDS - fields)} "
            f"unexpected={sorted(fields - LOCK_FIELDS)}"
        )
    return lock


def verify_source_archive(paths: CalibrationPaths | None = None) -> dict[str, object]:
    paths = paths or workspace_paths()
    lock = load_source_lock(paths)
    if not paths.source_zip.is_file():
        raise CalibrationSourceError(f"FINAL archive is missing: {paths.source_zip}")
    if lock["archive"] != SOURCE_ZIP_NAME:
        raise CalibrationSourceError(
            f"source archive must be {SOURCE_ZIP_NAME}, got {lock['archive']!r}"
        )
    lock_sha = str(lock["sha256"]).upper()
    if lock_sha != FINAL_SHA256:
        raise CalibrationSourceError(
            f"source lock SHA-256 must be {FINAL_SHA256}, got {lock_sha}"
        )
    for field, expected in EXPECTED_COUNTS.items():
        if lock[field] != expected:
            raise CalibrationSourceError(
                f"source lock {field} must be {expected}, got {lock[field]!r}"
            )
    actual_sha = _sha256(paths.source_zip)
    if actual_sha != FINAL_SHA256:
        raise CalibrationSourceError(
            f"archive SHA-256 must be {FINAL_SHA256}, got {actual_sha}"
        )
    try:
        with ZipFile(paths.source_zip) as archive:
            corrupt = archive.testzip()
    except (BadZipFile, OSError) as exc:
        raise CalibrationSourceError(f"invalid FINAL archive: {paths.source_zip}") from exc
    if corrupt is not None:
        raise CalibrationSourceError(f"corrupt FINAL archive member: {corrupt}")
    return {
        "archive": SOURCE_ZIP_NAME,
        "sha256": actual_sha,
        **EXPECTED_COUNTS,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path)
    args = parser.parse_args(argv)
    lock = verify_source_archive(workspace_paths(args.workspace_root))
    print(
        f"archive={lock['archive']} sha256={lock['sha256']} "
        f"recordings={lock['recordings']} "
        f"unordered_matchups={lock['unordered_matchups']} "
        f"standard_units={lock['standard_units']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
