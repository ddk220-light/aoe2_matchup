"""Bounded storage policies for validated live captures.

The default ``stats`` policy keeps the small decoded HP timeline, run manifest,
scenario, and diagnostic log. Large recordings and raw gRPC/reseed streams are
deleted only after the run has been validated and its summary has been written.
"""

from __future__ import annotations

import zipfile
import json
from pathlib import Path
from typing import Any

from .io import sha256


RETENTION_MODES = frozenset({"stats", "archive", "raw"})
RAW_SUFFIXES = (
    ".mov",
    ".mp4",
    ".frames.bin",
    ".seed_snap.bin",
    ".reseed.bin",
    ".live_seed.bin",
    ".meta.json",
    ".END",
)


def normalize_retention(value: str | None, default: str = "stats") -> str:
    selected = (value or default).strip().lower()
    if selected not in RETENTION_MODES:
        raise ValueError("retention must be stats, archive, or raw")
    return selected


def _is_raw_capture(path: Path) -> bool:
    name = path.name
    return any(name.endswith(suffix) for suffix in RAW_SUFFIXES)


def raw_capture_files(run_directory: Path) -> list[Path]:
    return sorted(
        (
            path for path in run_directory.rglob("*")
            if path.is_file() and _is_raw_capture(path)
        ),
        key=lambda path: str(path).lower(),
    )


def apply_run_retention(run_directory: Path, mode: str) -> dict[str, Any]:
    """Apply retention after validation; never removes decoded HP statistics."""
    selected = normalize_retention(mode)
    raw_files = raw_capture_files(run_directory)
    total_bytes = sum(path.stat().st_size for path in raw_files)
    result: dict[str, Any] = {
        "mode": selected,
        "rawFileCount": len(raw_files),
        "rawBytes": total_bytes,
        "deletedRawBytes": 0,
        "recordingsRetained": selected in {"archive", "raw"},
    }
    if selected == "raw" or not raw_files:
        return result

    if selected == "archive":
        archive = run_directory / "recordings.zip"
        temporary = archive.with_suffix(".zip.partial")
        temporary.unlink(missing_ok=True)
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as bundle:
            for path in raw_files:
                bundle.write(path, path.relative_to(run_directory))
        temporary.replace(archive)
        result.update({
            "archive": str(archive.relative_to(run_directory)).replace("\\", "/"),
            "archiveBytes": archive.stat().st_size,
            "archiveSha256": sha256(archive),
        })

    for path in raw_files:
        path.unlink(missing_ok=True)
    result["deletedRawBytes"] = total_bytes
    return result


def validate_retained_statistics(
    run_directory: Path,
    run_manifest: dict[str, Any],
    expected_counts: tuple[int, int],
) -> dict[str, Any]:
    """Validate a resumed stats-only/archive checkpoint without requiring raw tape."""
    capture = run_manifest.get("capture") or {}
    if tuple(capture.get("startCounts") or capture.get("start_counts") or ()) != expected_counts:
        raise ValueError("retained capture starting counts do not match the matchup")
    artifacts = capture.get("artifacts") or {}
    sidecar_value = artifacts.get("sidecar")
    if sidecar_value:
        sidecar = run_directory / sidecar_value
    else:
        candidates = list(run_directory.rglob("*.hp.json"))
        if len(candidates) != 1:
            raise ValueError("retained capture must contain exactly one HP sidecar")
        sidecar = candidates[0]
    if not sidecar.exists() or sidecar.stat().st_size == 0:
        raise ValueError("retained capture HP sidecar is missing or empty")
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    rows = sidecar_payload.get("rows") or []
    if not rows:
        raise ValueError("retained capture HP sidecar has no decoded rows")
    first, final = rows[0], rows[-1]
    observed_start = (first["side1"]["count"], first["side2"]["count"])
    if observed_start != expected_counts:
        raise ValueError("retained HP sidecar starting counts do not match the matchup")
    end = (final["side1"]["count"], final["side2"]["count"])
    if (end[0] == 0) == (end[1] == 0):
        raise ValueError("retained HP sidecar does not contain exactly one defeated army")
    winner_index = 0 if end[0] > 0 else 1
    winner_key = f"side{winner_index + 1}"
    winner_hp = float(final[winner_key]["hp"])
    starting_hp = float(first[winner_key]["hp"])
    remaining_percent = winner_hp / starting_hp * 100
    if "startCounts" in capture:
        capture.setdefault("winnerStartingHp", starting_hp)
        capture.setdefault("winnerRemainingHpPercent", remaining_percent)
        capture.setdefault(
            "signedRemainingHpPercent",
            remaining_percent if winner_index == 0 else -remaining_percent,
        )
    else:
        capture.setdefault("winner_starting_hp", starting_hp)
        capture.setdefault("winner_remaining_hp_percent", remaining_percent)
        capture.setdefault(
            "signed_remaining_hp_percent",
            remaining_percent if winner_index == 0 else -remaining_percent,
        )
    retention = run_manifest.get("retention") or {}
    mode = normalize_retention(retention.get("mode"), default="raw")
    if mode == "archive":
        archive = run_directory / str(retention.get("archive", "recordings.zip"))
        if not archive.exists() or archive.stat().st_size == 0:
            raise ValueError("retained capture archive is missing or empty")
        expected_sha = retention.get("archiveSha256")
        if expected_sha and sha256(archive) != expected_sha:
            raise ValueError("retained capture archive checksum changed")
    return capture
