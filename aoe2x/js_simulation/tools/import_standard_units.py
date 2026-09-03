"""Import the authorized standard-units clean-room truth corpus.

This importer reads only the project-local golden archive named in the active
source manifest.  It records raw source-member paths, tape starting rosters,
and summary outcomes; it does not use simulator mechanics to construct tape
truth.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile


ARCHIVE_NAME = "aoe2_golden_STANDARD_UNITS_WITH_TAPES.zip"
REQUIRED_SHA256 = "38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D"
ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_ARCHIVE = ROOT / "calibration" / "source" / ARCHIVE_NAME
SOURCE_MANIFEST = ROOT / "calibration" / "source" / "standard_units_source.json"
OUTPUT_TRUTH = ROOT / "calibration" / "fixtures" / "standard_units" / "standard_units_truth.json"
DECODED_MEMBER_ROOT = "standard_units/decoded/"
RAW_FRAME_ROOT = "standard_units/raw recordings/"
DECODED_MEMBER_SUFFIXES = {
    "summary": ".summary.json",
    "units": ".units.jsonl.gz",
}
FRAME_SUFFIX = ".frames.bin"
REPEAT_SUFFIX = re.compile(r"_r\d+$")
EXPECTED_ROWS = 101
EXPECTED_RECORDINGS = 339
EXPECTED_SCORED_RECORDINGS = 338
EXPECTED_TIMEOUTS = 1
EXPECTED_UNITS = 14


def import_archive(archive: Path) -> dict[str, Any]:
    """Return complete tape-derived truth from the verified *archive*."""
    archive = Path(archive)
    _verify_authorized_archive(archive)

    with ZipFile(archive) as source:
        members = _collect_members(source.namelist())
        recordings = [
            _read_recording(source, tag, source_members)
            for tag, source_members in sorted(members.items())
        ]

    rows = _group_rows(recordings)
    _validate_corpus(rows)
    return {
        "schema_version": 1,
        "archive": {
            "name": ARCHIVE_NAME,
            "path": "aoe2x/js_simulation/calibration/source/" + ARCHIVE_NAME,
            "zip_sha256": REQUIRED_SHA256,
        },
        "rows": rows,
    }


def write_truth_fixture(archive: Path = AUTHORIZED_ARCHIVE, output: Path = OUTPUT_TRUTH) -> dict[str, Any]:
    """Import *archive*, serialize it canonically, and return the truth object."""
    truth = import_archive(archive)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return truth


def _verify_authorized_archive(archive: Path) -> None:
    if archive.resolve() != AUTHORIZED_ARCHIVE.resolve():
        raise ValueError("archive must be the project-local authorized source")
    if archive.name != ARCHIVE_NAME:
        raise ValueError(f"unauthorized archive name: {archive.name}")
    if not archive.is_file():
        raise FileNotFoundError(archive)
    if not SOURCE_MANIFEST.is_file():
        raise FileNotFoundError(SOURCE_MANIFEST)

    source_lock = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    if source_lock.get("archive") != ARCHIVE_NAME:
        raise ValueError("active source manifest names a different archive")
    if source_lock.get("zip_sha256") != REQUIRED_SHA256:
        raise ValueError("active source manifest SHA-256 does not match the authorized archive")
    if _sha256(archive) != REQUIRED_SHA256:
        raise ValueError("authorized standard-units archive SHA-256 mismatch")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _collect_members(names: list[str]) -> dict[str, dict[str, str]]:
    recordings: dict[str, dict[str, str]] = {}
    for name in names:
        if name.startswith(DECODED_MEMBER_ROOT):
            for kind, suffix in DECODED_MEMBER_SUFFIXES.items():
                if not name.endswith(suffix):
                    continue
                tag = name[len(DECODED_MEMBER_ROOT) : -len(suffix)]
                _add_member(recordings, tag, kind, name)
        elif name.startswith(RAW_FRAME_ROOT) and name.endswith(FRAME_SUFFIX):
            tag = name[len(RAW_FRAME_ROOT) : -len(FRAME_SUFFIX)]
            _add_member(recordings, tag, "frames", name)

    for tag, recording in recordings.items():
        if set(recording) != {"frames", *DECODED_MEMBER_SUFFIXES}:
            raise ValueError(f"incomplete decoded recording: {tag}")
    if len(recordings) != EXPECTED_RECORDINGS:
        raise ValueError(f"expected {EXPECTED_RECORDINGS} recordings, found {len(recordings)}")
    return recordings


def _add_member(
    recordings: dict[str, dict[str, str]], tag: str, kind: str, name: str
) -> None:
    if not tag:
        raise ValueError(f"empty recording tag: {name}")
    recording = recordings.setdefault(tag, {})
    if kind in recording:
        raise ValueError(f"duplicate {kind} member for {tag}")
    recording[kind] = name


def _read_recording(source: ZipFile, tag: str, members: dict[str, str]) -> dict[str, Any]:
    summary = json.loads(source.read(members["summary"]))
    sides = summary.get("sides")
    if not isinstance(sides, dict):
        raise ValueError(f"summary has no sides: {tag}")
    side2 = _read_side(sides.get("side2"), expected_owner=2, tag=tag)
    side3 = _read_side(sides.get("side3"), expected_owner=3, tag=tag)
    starting_units = _starting_units(source, members["units"], tag)
    starting_hp = _starting_hp_by_owner(starting_units, tag)
    _validate_starting_units(side2, side3, starting_units, tag)

    summary_start_hp = {
        2: side2.get("hp_start"),
        3: side3.get("hp_start"),
    }
    starting_hp_by_owner: dict[str, float] = {}
    hp_source_by_owner: dict[str, str] = {}
    for owner, declared in summary_start_hp.items():
        if isinstance(declared, (int, float)) and declared > 0:
            starting_hp_by_owner[str(owner)] = float(declared)
            hp_source_by_owner[str(owner)] = "summary"
        else:
            starting_hp_by_owner[str(owner)] = starting_hp[owner]
            hp_source_by_owner[str(owner)] = "unit_samples"

    outcome = summary.get("outcome")
    winners = {"side2": 2, "side3": 3}
    if outcome in winners:
        winner_owner = winners[outcome]
        winner_hp = float(sides[outcome]["hp_remaining"])
        score = 100.0 * winner_hp / starting_hp_by_owner[str(winner_owner)]
        signed_score = -score if winner_owner == 2 else score
        status = "scored"
    elif outcome == "timeout":
        winner_owner = None
        winner_hp = None
        signed_score = None
        status = "timeout"
    else:
        raise ValueError(f"unknown outcome {outcome!r}: {tag}")

    return {
        "tag": tag,
        "archive_key": REPEAT_SUFFIX.sub("", tag),
        "source_members": members,
        "side2": {
            "owner": 2,
            "unit": side2["unit"],
            "master": side2["master"],
            "count": side2["start_count"],
        },
        "side3": {
            "owner": 3,
            "unit": side3["unit"],
            "master": side3["master"],
            "count": side3["start_count"],
        },
        "starting_units": starting_units,
        "starting_units_hash": _canonical_hash(starting_units),
        "starting_hp_by_owner": starting_hp_by_owner,
        "starting_hp_source_by_owner": hp_source_by_owner,
        "status": status,
        "winner_owner": winner_owner,
        "winner_hp": winner_hp,
        "winner_starting_hp_source": (
            hp_source_by_owner[str(winner_owner)] if winner_owner is not None else None
        ),
        "signed_score": signed_score,
    }


def _read_side(value: Any, *, expected_owner: int, tag: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"missing side {expected_owner}: {tag}")
    if value.get("owner") != expected_owner:
        raise ValueError(f"unexpected owner for side {expected_owner}: {tag}")
    if not isinstance(value.get("master"), int) or not isinstance(value.get("unit"), str):
        raise ValueError(f"missing unit identity for side {expected_owner}: {tag}")
    if not isinstance(value.get("start_count"), int) or value["start_count"] < 1:
        raise ValueError(f"invalid start_count for side {expected_owner}: {tag}")
    if not isinstance(value.get("hp_remaining"), (int, float)):
        raise ValueError(f"missing remaining HP for side {expected_owner}: {tag}")
    return value


def _starting_units(source: ZipFile, member: str, tag: str) -> list[dict[str, Any]]:
    payload = gzip.decompress(source.read(member)).decode("utf-8")
    first: dict[int, dict[str, Any]] = {}
    for line in payload.splitlines():
        sample = json.loads(line)
        unit_id = sample.get("id")
        if not isinstance(unit_id, int):
            raise ValueError(f"unit sample has no numeric id: {tag}")
        first.setdefault(unit_id, sample)
    if not first:
        raise ValueError(f"empty unit stream: {tag}")
    units = []
    for sample in sorted(first.values(), key=lambda item: item["id"]):
        required = ("id", "owner", "master", "x", "y", "hp")
        if any(key not in sample for key in required):
            raise ValueError(f"incomplete initial unit sample: {tag}")
        units.append({
            "id": sample["id"],
            "owner": sample["owner"],
            "master": sample["master"],
            "x": sample["x"],
            "y": sample["y"],
            "hp": sample["hp"],
        })
    return units


def _starting_hp_by_owner(units: list[dict[str, Any]], tag: str) -> dict[int, float]:
    totals = {2: 0.0, 3: 0.0}
    for unit in units:
        owner = unit["owner"]
        if owner not in totals:
            raise ValueError(f"unexpected unit owner {owner}: {tag}")
        if not isinstance(unit["hp"], (int, float)) or unit["hp"] <= 0:
            raise ValueError(f"invalid initial HP: {tag}")
        totals[owner] += float(unit["hp"])
    if not totals[2] or not totals[3]:
        raise ValueError(f"missing side in initial unit samples: {tag}")
    return totals


def _validate_starting_units(
    side2: dict[str, Any], side3: dict[str, Any], units: list[dict[str, Any]], tag: str
) -> None:
    for side in (side2, side3):
        owner = side["owner"]
        side_units = [unit for unit in units if unit["owner"] == owner]
        if len(side_units) != side["start_count"]:
            raise ValueError(f"starting unit count does not match summary: {tag}")
        if any(unit["master"] != side["master"] for unit in side_units):
            raise ValueError(f"starting unit master does not match summary: {tag}")


def _group_rows(recordings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for recording in recordings:
        key = (
            recording["side2"]["master"],
            recording["side2"]["count"],
            recording["side3"]["master"],
            recording["side3"]["count"],
        )
        grouped[key].append(recording)

    rows = []
    for key, runs in sorted(grouped.items()):
        runs.sort(key=lambda run: run["tag"])
        side2 = runs[0]["side2"]
        side3 = runs[0]["side3"]
        if any(run["side2"] != side2 or run["side3"] != side3 for run in runs):
            raise ValueError(f"inconsistent row grouping for {key}")
        if len({run["starting_units_hash"] for run in runs}) != 1:
            raise ValueError(f"multiple start geometries for {side2['unit']} vs {side3['unit']}")
        rows.append({
            "id": f"{side2['master']}-{side2['count']}_vs_{side3['master']}-{side3['count']}",
            "matchup": f"{side2['unit']} vs {side3['unit']}",
            "side2": side2,
            "side3": side3,
            "archive_keys": sorted({run["archive_key"] for run in runs}),
            "runs": runs,
        })
    return rows


def _validate_corpus(rows: list[dict[str, Any]]) -> None:
    runs = [run for row in rows for run in row["runs"]]
    masters = {
        row[side]["master"]
        for row in rows
        for side in ("side2", "side3")
    }
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} comparison rows, found {len(rows)}")
    if len(runs) != EXPECTED_RECORDINGS:
        raise ValueError(f"expected {EXPECTED_RECORDINGS} recordings, found {len(runs)}")
    if len(masters) != EXPECTED_UNITS:
        raise ValueError(f"expected {EXPECTED_UNITS} unit masters, found {len(masters)}")
    if sum(run["status"] == "scored" for run in runs) != EXPECTED_SCORED_RECORDINGS:
        raise ValueError("unexpected scored-recording count")
    if sum(run["status"] == "timeout" for run in runs) != EXPECTED_TIMEOUTS:
        raise ValueError("unexpected timeout count")


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=AUTHORIZED_ARCHIVE)
    parser.add_argument("--output", type=Path, default=OUTPUT_TRUTH)
    args = parser.parse_args(argv)
    truth = write_truth_fixture(args.archive, args.output)
    runs = [run for row in truth["rows"] for run in row["runs"]]
    print(
        " ".join((
            f"archive={truth['archive']['name']}",
            f"sha256={truth['archive']['zip_sha256']}",
            f"rows={len(truth['rows'])}",
            f"recordings={len(runs)}",
            f"scored={sum(run['status'] == 'scored' for run in runs)}",
            f"timeouts={sum(run['status'] == 'timeout' for run in runs)}",
        ))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
