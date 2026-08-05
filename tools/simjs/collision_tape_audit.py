"""Audit same-owner unit spacing in the one locked FINAL standard-unit tape.

The archive hash is validated before any member is read. This tool deliberately
has no directory fallback and no archive discovery logic: callers must provide
``aoe2_golden_STANDARD_UNITS_FINAL.zip`` with the locked SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import zipfile
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FINAL_ARCHIVE_NAME = "aoe2_golden_STANDARD_UNITS_FINAL.zip"
FINAL_ARCHIVE_SHA256 = "31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9"
DECODED_PREFIX = "standard_units/decoded/"


def matchup_family(tag: str) -> str:
    return re.sub(r"_r\d+$", "", tag)


def canonical_matchup_family(tag: str) -> str:
    oriented = matchup_family(tag)
    sides = oriented.split("__vs__", 1)
    return "__vs__".join(sorted(sides)) if len(sides) == 2 else oriented


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_final_archive(path: Path) -> str:
    path = Path(path).resolve()
    if path.name != FINAL_ARCHIVE_NAME:
        raise RuntimeError(f"refusing non-FINAL tape archive: {path.name}")
    digest = _sha256(path)
    if digest != FINAL_ARCHIVE_SHA256:
        raise RuntimeError(f"FINAL tape SHA-256 mismatch: {digest}")
    return digest


def nearest_neighbors_for_frame(frame: list[dict[str, Any]]) -> dict[int, float]:
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for row in frame:
        if float(row.get("hp") or 0) <= 0:
            continue
        groups[(row.get("owner"), row.get("master"))].append(row)

    distances: dict[int, float] = {}
    for rows in groups.values():
        if len(rows) < 2:
            continue
        for index, row in enumerate(rows):
            nearest = min(
                math.hypot(float(row["x"]) - float(other["x"]), float(row["y"]) - float(other["y"]))
                for other_index, other in enumerate(rows)
                if other_index != index
            )
            distances[int(row["id"])] = nearest
    return distances


def _quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires at least one value")
    if len(sorted_values) == 1:
        return sorted_values[0]
    location = (len(sorted_values) - 1) * probability
    lower = math.floor(location)
    upper = math.ceil(location)
    if lower == upper:
        return sorted_values[lower]
    fraction = location - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def summarize(values: Iterable[float], nominal: float, multiplied: float) -> dict[str, Any]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"samples": 0}
    return {
        "samples": len(ordered),
        "p10_tiles": round(_quantile(ordered, 0.10), 6),
        "median_tiles": round(_quantile(ordered, 0.50), 6),
        "p90_tiles": round(_quantile(ordered, 0.90), 6),
        "minimum_tiles": round(ordered[0], 6),
        "share_below_nominal_pct": round(
            100 * sum(value < nominal for value in ordered) / len(ordered), 3
        ),
        "share_below_multiplied_pct": round(
            100 * sum(value < multiplied for value in ordered) / len(ordered), 3
        ),
    }


def _frames(zipped: zipfile.ZipFile, member: str):
    with zipped.open(member) as compressed:
        with gzip.GzipFile(fileobj=compressed) as uncompressed:
            with io.TextIOWrapper(uncompressed, encoding="utf-8") as text:
                current_t = None
                rows: list[dict[str, Any]] = []
                for line in text:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    timestamp = row["t"]
                    if current_t is not None and timestamp != current_t:
                        yield current_t, rows
                        rows = []
                    current_t = timestamp
                    rows.append(row)
                if rows:
                    yield current_t, rows


def _json_member(zipped: zipfile.ZipFile, member: str) -> Any:
    return json.loads(zipped.read(member).decode("utf-8"))


def build_report(
    archive_path: Path,
    dat_audit_path: Path,
    extracted_at: str | None = None,
) -> dict[str, Any]:
    archive_path = Path(archive_path).resolve()
    digest = validate_final_archive(archive_path)
    dat_audit = json.loads(Path(dat_audit_path).read_text(encoding="utf-8"))
    units = dat_audit["units"]
    master_to_slug = {int(record["unit_id"]): slug for slug, record in units.items()}
    thresholds = {
        slug: (
            float(record["nominal_collision_diameter_tiles"]),
            float(record["multiplied_collision_diameter_tiles"]),
        )
        for slug, record in units.items()
    }

    overall: dict[str, array] = defaultdict(lambda: array("f"))
    by_matchup: dict[tuple[str, str], array] = defaultdict(lambda: array("f"))
    by_canonical_matchup: dict[tuple[str, str], array] = defaultdict(lambda: array("f"))
    by_activity: dict[tuple[str, str], array] = defaultdict(lambda: array("f"))
    state_counts: dict[str, Counter] = defaultdict(Counter)
    command_totals = Counter()
    recordings_with_command = Counter()
    command_by_matchup: dict[str, Counter] = defaultdict(Counter)
    command_by_canonical_matchup: dict[str, Counter] = defaultdict(Counter)
    game_versions = Counter()
    position_sample_rates = Counter()
    recording_metrics: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with zipfile.ZipFile(archive_path) as zipped:
        with zipped.open("standard_units/INDEX.csv") as raw_index:
            index_rows = list(csv.DictReader(io.TextIOWrapper(raw_index, encoding="utf-8-sig")))
        tags = [row["tag"] for row in index_rows]
        if len(tags) != 339 or len(set(tags)) != 339:
            raise RuntimeError(f"expected 339 unique FINAL recordings, found {len(tags)}")

        unknown_masters = Counter()
        for tag in tags:
            family = matchup_family(tag)
            canonical_family = canonical_matchup_family(tag)
            meta = _json_member(zipped, f"{DECODED_PREFIX}{tag}.meta.json")
            game_versions[str(meta.get("recorder_meta", {}).get("game_version"))] += 1
            position_sample_rates[str(meta.get("position_sample_hz"))] += 1

            commands = Counter()
            command_member = f"{DECODED_PREFIX}{tag}.commands.jsonl"
            for line in zipped.read(command_member).decode("utf-8").splitlines():
                if line.strip():
                    commands[json.loads(line).get("kind", "<missing>")] += 1
            command_totals.update(commands)
            command_by_matchup[family].update(commands)
            command_by_canonical_matchup[canonical_family].update(commands)
            recordings_with_command.update(commands.keys())

            previous_position: dict[int, tuple[float, float]] = {}
            per_recording: dict[str, array] = defaultdict(lambda: array("f"))
            unit_member = f"{DECODED_PREFIX}{tag}.units.jsonl.gz"
            for _, frame in _frames(zipped, unit_member):
                nearest = nearest_neighbors_for_frame(frame)
                alive_positions: dict[int, tuple[float, float]] = {}
                for row in frame:
                    if float(row.get("hp") or 0) <= 0:
                        continue
                    unit_id = int(row["id"])
                    alive_positions[unit_id] = (float(row["x"]), float(row["y"]))
                    if unit_id not in nearest:
                        continue
                    master = int(row["master"])
                    slug = master_to_slug.get(master)
                    if slug is None:
                        unknown_masters[master] += 1
                        continue
                    distance = nearest[unit_id]
                    overall[slug].append(distance)
                    by_matchup[(family, slug)].append(distance)
                    by_canonical_matchup[(canonical_family, slug)].append(distance)
                    per_recording[slug].append(distance)
                    state_counts[slug][str(row.get("state"))] += 1
                    previous = previous_position.get(unit_id)
                    if previous is not None:
                        displacement = math.hypot(alive_positions[unit_id][0] - previous[0], alive_positions[unit_id][1] - previous[1])
                        activity = "moving" if displacement > 0.0005 else "stationary"
                        by_activity[(slug, activity)].append(distance)
                previous_position.update(alive_positions)

            for slug, values in per_recording.items():
                nominal, multiplied = thresholds[slug]
                recording_metrics[slug].append(
                    {
                        "tag": tag,
                        "matchup": family,
                        "canonical_matchup": canonical_family,
                        **summarize(values, nominal, multiplied),
                    }
                )

        if unknown_masters:
            raise RuntimeError(f"unmapped FINAL tape unit master IDs: {dict(unknown_masters)}")

    unit_report = {}
    for slug in units:
        nominal, multiplied = thresholds[slug]
        moving = by_activity[(slug, "moving")]
        stationary = by_activity[(slug, "stationary")]
        activity_samples = len(moving) + len(stationary)
        unit_report[slug] = {
            "master_unit_id": units[slug]["unit_id"],
            "collision_radius_tiles": units[slug]["collision_size_tiles"]["x"],
            "min_collision_size_multiplier": units[slug]["min_collision_size_multiplier"],
            "nominal_collision_diameter_tiles": nominal,
            "multiplied_collision_diameter_tiles": multiplied,
            "overall": summarize(overall[slug], nominal, multiplied),
            "activity": {
                "definition": "moving means position changed by >0.0005 tile since the preceding 10 Hz sample",
                "moving_sample_pct": round(100 * len(moving) / activity_samples, 3) if activity_samples else None,
                "moving": summarize(moving, nominal, multiplied),
                "stationary": summarize(stationary, nominal, multiplied),
            },
            "raw_unit_state_counts": dict(sorted(state_counts[slug].items())),
            "recordings": recording_metrics[slug],
        }

    matchup_report: dict[str, dict[str, Any]] = defaultdict(dict)
    for (family, slug), values in sorted(by_matchup.items()):
        nominal, multiplied = thresholds[slug]
        matchup_report[family][slug] = summarize(values, nominal, multiplied)

    canonical_matchup_report: dict[str, dict[str, Any]] = defaultdict(dict)
    for (family, slug), values in sorted(by_canonical_matchup.items()):
        nominal, multiplied = thresholds[slug]
        canonical_matchup_report[family][slug] = summarize(values, nominal, multiplied)

    return {
        "schema": 1,
        "extracted_at_utc": extracted_at or datetime.now(timezone.utc).isoformat(),
        "source": {
            "archive": archive_path.name,
            "path": str(archive_path),
            "sha256": digest,
            "recordings": 339,
            "game_versions": dict(sorted(game_versions.items())),
            "position_sample_hz": dict(sorted(position_sample_rates.items())),
            "dat_collision_audit": str(Path(dat_audit_path).resolve()),
            "dat_sha256": dat_audit["source"]["sha256"],
        },
        "method": {
            "spacing": "Euclidean center distance to the nearest living unit with the same owner and master ID at each sampled frame",
            "thresholds": "strictly less than the nominal or multiplier-adjusted same-unit diameter",
            "activity": "derived from successive recorded positions; it is not an interpretation of the opaque unit state code",
        },
        "units": unit_report,
        "oriented_matchups": dict(matchup_report),
        "canonical_matchups": dict(canonical_matchup_report),
        "command_stream": {
            "limitation": "FINAL commands.jsonl retains only t and kind; it has no unit IDs, destination, or patrol/attack-move opcode details",
            "total_kind_counts": dict(command_totals.most_common()),
            "recordings_with_kind": dict(recordings_with_command.most_common()),
            "by_matchup": {
                family: dict(counts.most_common()) for family, counts in sorted(command_by_matchup.items())
            },
            "by_canonical_matchup": {
                family: dict(counts.most_common())
                for family, counts in sorted(command_by_canonical_matchup.items())
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--dat-audit", required=True, type=Path)
    parser.add_argument("--json", required=True, type=Path)
    parser.add_argument("--extracted-at", help="Override timestamp for deterministic regeneration")
    args = parser.parse_args()

    report = build_report(args.archive, args.dat_audit, args.extracted_at)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
