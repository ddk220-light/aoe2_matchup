"""Import the locked Champion-versus-Champion clean-room truth corpus."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path
from statistics import median
from zipfile import ZipFile


ARCHIVE_NAME = "aoe2_golden_basics_championvschampion_2026-08-04.zip"
REQUIRED_SHA256 = "33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE"
AUTHORIZED_ARCHIVE = (
    Path(__file__).resolve().parents[1]
    / "calibration"
    / "source"
    / ARCHIVE_NAME
)
RATIOS = ("1v1", "2v1", "2v3", "5v3", "6v3")
MEMBER_ROOT = "basics_championpluspaladin/decoded/"
MEMBER_KINDS = {
    "commands": ".commands.jsonl",
    "damage": ".damage.jsonl.gz",
    "metadata": ".meta.json",
    "missiles": ".missiles.jsonl.gz",
    "summary": ".summary.json",
    "units": ".units.jsonl.gz",
}
RUN_NAME = re.compile(
    r"^champion_vs_champion__(?P<ratio>1v1|2v1|2v3|5v3|6v3)(?P<repeat>_r[23])?$"
)


def import_archive(archive: Path) -> tuple[dict, dict]:
    """Return a manifest and complete, reproducible truth fixture from *archive*."""
    archive = Path(archive)
    _verify_archive(archive)

    with ZipFile(archive) as source:
        members = _collect_members(source.namelist())
        manifest_runs = []
        grouped_runs = {ratio: [] for ratio in RATIOS}
        for ratio in RATIOS:
            for tag in _expected_tags(ratio):
                source_members = members[(ratio, tag)]
                run = _read_run(source, ratio, tag, source_members)
                grouped_runs[ratio].append(run)
                manifest_runs.append(
                    {
                        "ratio": ratio,
                        "tag": tag,
                        "zip_sha256": REQUIRED_SHA256,
                        "source_members": source_members,
                    }
                )

    truth_ratios = {}
    for ratio in RATIOS:
        runs = grouped_runs[ratio]
        winner_hp_percentages = [
            _winner_hp_percent(run["winner"], run["aggregate_hp"])
            for run in runs
        ]
        truth_ratios[ratio] = {
            "runs": runs,
            "median_winner_hp_pct": median(winner_hp_percentages),
        }

    manifest = {
        "archive": ARCHIVE_NAME,
        "zip_sha256": REQUIRED_SHA256,
        "runs": manifest_runs,
    }
    truth = {
        "archive": ARCHIVE_NAME,
        "zip_sha256": REQUIRED_SHA256,
        "ratios": truth_ratios,
    }
    return manifest, truth


def _verify_archive(archive: Path) -> None:
    if archive.resolve() != AUTHORIZED_ARCHIVE:
        raise ValueError("archive must be the project-local authorized source")
    if archive.name != ARCHIVE_NAME:
        raise ValueError(f"unauthorized archive name: {archive.name}")
    if not archive.is_file():
        raise FileNotFoundError(archive)

    digest = hashlib.sha256()
    with archive.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest().upper() != REQUIRED_SHA256:
        raise ValueError("authorized Champion archive SHA-256 mismatch")


def _collect_members(names: list[str]) -> dict[tuple[str, str], dict[str, str]]:
    members: dict[tuple[str, str], dict[str, str]] = {}
    for name in names:
        if not name.startswith(MEMBER_ROOT):
            continue
        for kind, suffix in MEMBER_KINDS.items():
            if not name.endswith(suffix):
                continue
            run_name = name[len(MEMBER_ROOT) : -len(suffix)]
            match = RUN_NAME.fullmatch(run_name)
            if match is None:
                raise ValueError(f"unexpected decoded member: {name}")
            ratio = match.group("ratio")
            tag = run_name[len("champion_vs_champion__") :]
            key = (ratio, tag)
            if key not in members:
                members[key] = {}
            if kind in members[key]:
                raise ValueError(f"duplicate {kind} member for {tag}")
            members[key][kind] = name

    expected_keys = {
        (ratio, tag) for ratio in RATIOS for tag in _expected_tags(ratio)
    }
    if set(members) != expected_keys:
        raise ValueError("archive must contain exactly three runs for every authorized ratio")
    for key, run_members in members.items():
        if set(run_members) != set(MEMBER_KINDS):
            raise ValueError(f"incomplete decoded recording: {key[1]}")
    return members


def _expected_tags(ratio: str) -> tuple[str, str, str]:
    return ratio, f"{ratio}_r2", f"{ratio}_r3"


def _read_run(
    source: ZipFile, ratio: str, tag: str, source_members: dict[str, str]
) -> dict:
    metadata = _read_json(source, source_members["metadata"])
    summary = _read_json(source, source_members["summary"])
    unit_samples = _read_json_lines(source, source_members["units"], compressed=True)
    damage_events = _read_json_lines(source, source_members["damage"], compressed=True)
    missile_events = _read_json_lines(source, source_members["missiles"], compressed=True)
    command_stream = _read_json_lines(source, source_members["commands"], compressed=False)

    if not unit_samples or not damage_events or not command_stream:
        raise ValueError(f"decoded recording is empty: {tag}")

    winner = summary["outcome"]
    if winner not in summary["sides"]:
        raise ValueError(f"summary winner is not a side: {tag}")
    aggregate_hp = {
        side: {
            "starting": values["hp_start"],
            "remaining": values["hp_remaining"],
            "survivors": values["survivors"],
        }
        for side, values in summary["sides"].items()
    }
    return {
        "ratio": ratio,
        "tag": tag,
        "composition": metadata["composition"],
        "metadata": metadata,
        "summary": summary,
        "starting_units": _starting_units(unit_samples),
        "unit_samples": unit_samples,
        "damage_events": damage_events,
        "missile_events": missile_events,
        "command_stream": command_stream,
        "winner": winner,
        "aggregate_hp": aggregate_hp,
        "first_damage": damage_events[0],
        "final_kill": _final_kill(damage_events),
        "source_members": source_members,
    }


def _read_json(source: ZipFile, member: str) -> dict:
    return json.loads(source.read(member))


def _read_json_lines(source: ZipFile, member: str, *, compressed: bool) -> list[dict]:
    payload = source.read(member)
    if compressed:
        payload = gzip.decompress(payload)
    return [json.loads(line) for line in payload.decode("utf-8").splitlines()]


def _starting_units(unit_samples: list[dict]) -> list[dict]:
    first_samples: dict[int, dict] = {}
    for sample in unit_samples:
        first_samples.setdefault(sample["id"], sample)
    return [
        {
            "id": sample["id"],
            "owner": sample["owner"],
            "master": sample["master"],
            "x": sample["x"],
            "y": sample["y"],
        }
        for sample in sorted(first_samples.values(), key=lambda item: item["id"])
    ]


def _final_kill(damage_events: list[dict]) -> dict:
    kills = [event for event in damage_events if event["kill"]]
    if not kills:
        raise ValueError("recording has no final kill")
    return kills[-1]


def _winner_hp_percent(winner: str, aggregate_hp: dict[str, dict]) -> float:
    side = aggregate_hp[winner]
    return 100.0 * side["remaining"] / side["starting"]
