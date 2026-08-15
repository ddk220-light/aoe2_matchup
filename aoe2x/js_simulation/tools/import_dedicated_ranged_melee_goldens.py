"""Import all authorized dedicated ranged-versus-melee golden archives.

The importer reads only project-local archives locked by the active manifest.
It records every tape ratio, every repeat, exact starting positions, outcomes,
and raw frames.bin provenance without consulting simulation output.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "calibration" / "source"
MANIFEST = SOURCE_DIR / "dedicated_ranged_melee_sources.json"
OUTPUT = (
    ROOT
    / "calibration"
    / "fixtures"
    / "dedicated_ranged_melee"
    / "dedicated_ranged_melee_truth.json"
)
RATIOS = ("5v10", "10v5", "15v20", "20v15", "20v20")
RUN_PATTERN = re.compile(
    r"^(?P<stem>.+)__(?P<ratio>5v10|10v5|15v20|20v15|20v20)"
    r"(?:_r(?P<repeat>[2-5]))?$"
)
EXPECTED = (
    ("arbalester", "champion", "aoe2_golden_kiting_arbalestervschampion_2026-08-06.zip", 492, 567, "arbalester_vs_champion_kiting_basics.json"),
    ("arbalester", "elite_elephant", "aoe2_golden_kiting_arbalestervselephant_2026-08-06.zip", 492, 1134, "arbalester_vs_elephant_kiting_basics.json"),
    ("arbalester", "elite_fire_lancer", "aoe2_golden_kiting_arbalestervsfirelancer_2026-08-06.zip", 492, 1903, "arbalester_vs_firelancer_kiting_basics.json"),
    ("arbalester", "paladin", "aoe2_golden_kiting_arbalestervspaladin_2026-08-06.zip", 492, 569, "arbalester_vs_paladin_kiting_basics.json"),
    ("arbalester", "elite_steppe", "aoe2_golden_kiting_arbalestervssteppe_2026-08-06.zip", 492, 1372, "arbalester_vs_steppe_kiting_basics.json"),
    ("imp_elite_skirm", "champion", "aoe2_golden_kiting_eliteskirmvschampion_2026-08-06.zip", 6, 567, "eliteskirm_vs_champion_kiting_basics.json"),
    ("imp_elite_skirm", "elite_elephant", "aoe2_golden_kiting_eliteskirmvselephant_2026-08-06.zip", 6, 1134, "eliteskirm_vs_elephant_kiting_basics.json"),
    ("imp_elite_skirm", "elite_fire_lancer", "aoe2_golden_kiting_eliteskirmvsfirelancer_2026-08-06.zip", 6, 1903, None),
    ("imp_elite_skirm", "paladin", "aoe2_golden_kiting_eliteskirmvspaladin_2026-08-06.zip", 6, 569, "eliteskirm_vs_paladin_kiting_basics.json"),
    ("imp_elite_skirm", "elite_steppe", "aoe2_golden_kiting_eliteskirmvssteppe_2026-08-06.zip", 6, 1372, "eliteskirm_vs_steppe_kiting_basics.json"),
    ("hand_cannoneer", "champion", "aoe2_golden_kiting_hcvschampion_2026-08-14.zip", 5, 567, None),
    ("hand_cannoneer", "paladin", "aoe2_golden_kiting_hcvspaladin_2026-08-14.zip", 5, 569, None),
    ("heavy_cav_archer", "champion", "aoe2_golden_kiting_hcavarchervschampion_2026-08-06.zip", 474, 567, "hcavarcher_vs_champion_kiting_basics.json"),
    ("heavy_cav_archer", "elite_elephant", "aoe2_golden_kiting_hcavarchervselephant_2026-08-06.zip", 474, 1134, "hcavarcher_vs_elephant_kiting_basics.json"),
    ("heavy_cav_archer", "elite_fire_lancer", "aoe2_golden_kiting_hcavarchervsfirelancer_2026-08-06.zip", 474, 1903, None),
    ("heavy_cav_archer", "paladin", "aoe2_golden_kiting_hcavarchervspaladin_2026-08-06.zip", 474, 569, "hcavarcher_vs_paladin_kiting_basics.json"),
    ("heavy_cav_archer", "elite_steppe", "aoe2_golden_kiting_hcavarchervssteppe_2026-08-06.zip", 474, 1372, "hcavarcher_vs_steppe_kiting_basics.json"),
    ("heavy_scorpion", "champion", "aoe2_golden_ranged_scorpionvschampion_2026-08-05.zip", 542, 567, "scorpion_vs_champion_basics.json"),
    ("heavy_scorpion", "paladin", "aoe2_golden_ranged_scorpionvspaladin_2026-08-05.zip", 542, 569, "scorpion_vs_paladin_basics.json"),
)


def import_corpus(selected_archives: set[str] | None = None) -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    locks = {entry["archive"]: entry for entry in manifest["archives"]}
    expected_names = {entry[2] for entry in EXPECTED}
    if set(locks) != expected_names:
        raise ValueError("dedicated manifest archive set differs from the authorized corpus")
    if selected_archives is not None and not selected_archives <= expected_names:
        unknown = sorted(selected_archives - expected_names)
        raise ValueError(f"unknown selected archive(s): {', '.join(unknown)}")
    existing_by_id: dict[str, dict[str, Any]] = {}
    if selected_archives is not None and OUTPUT.exists():
        existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        existing_by_id = {matchup["id"]: matchup for matchup in existing["matchups"]}

    matchups = []
    for index, expected in enumerate(EXPECTED, start=1):
        ranged_slug, melee_slug, archive_name, ranged_master, melee_master, legacy = expected
        lock = locks[archive_name]
        matchup_id = f"{ranged_slug}_vs_{melee_slug}"
        if selected_archives is not None and archive_name not in selected_archives:
            matchup = existing_by_id.get(matchup_id)
            if matchup is None:
                raise ValueError(f"existing truth is missing unselected matchup: {matchup_id}")
            if (
                matchup["archive"] != archive_name
                or matchup["zip_sha256"] != lock["zip_sha256"]
            ):
                raise ValueError(f"existing truth provenance differs: {matchup_id}")
            matchups.append(matchup)
            print(
                f"[{index}/{len(EXPECTED)}] retained verified truth for {archive_name}",
                flush=True,
            )
            continue
        archive = SOURCE_DIR / archive_name
        print(f"[{index}/{len(EXPECTED)}] verifying {archive_name}", flush=True)
        actual_hash = _sha256(archive)
        if actual_hash != lock["zip_sha256"]:
            raise ValueError(f"project-local archive SHA-256 mismatch: {archive_name}")
        matchup = _read_matchup(
            archive,
            ranged_slug=ranged_slug,
            melee_slug=melee_slug,
            ranged_master=ranged_master,
            melee_master=melee_master,
            zip_sha256=actual_hash,
        )
        if legacy:
            _validate_legacy_fixture(matchup, ROOT / "calibration" / "fixtures" / legacy)
        matchups.append(matchup)
        print(f"[{index}/{len(EXPECTED)}] imported 5 ratios / 25 runs", flush=True)

    return {
        "schema_version": 1,
        "manifest": "aoe2x/js_simulation/calibration/source/dedicated_ranged_melee_sources.json",
        "matchup_count": len(matchups),
        "ratio_count": sum(len(matchup["ratios"]) for matchup in matchups),
        "tape_run_count": sum(
            len(row["runs"])
            for matchup in matchups
            for row in matchup["ratios"]
        ),
        "matchups": matchups,
    }


def _read_matchup(
    archive: Path,
    *,
    ranged_slug: str,
    melee_slug: str,
    ranged_master: int,
    melee_master: int,
    zip_sha256: str,
) -> dict[str, Any]:
    with ZipFile(archive) as source:
        names = set(source.namelist())
        summaries = sorted(
            name for name in names
            if "/decoded/" in name and name.endswith(".summary.json")
        )
        if len(summaries) != 25:
            raise ValueError(f"expected 25 decoded summaries in {archive.name}, found {len(summaries)}")
        grouped = {ratio: [] for ratio in RATIOS}
        for summary_member in summaries:
            run_name = summary_member.rsplit("/", 1)[1][:-len(".summary.json")]
            match = RUN_PATTERN.fullmatch(run_name)
            if match is None:
                raise ValueError(f"unexpected run name: {summary_member}")
            ratio = match.group("ratio")
            repeat = int(match.group("repeat") or 1)
            prefix = summary_member[:-len(".summary.json")]
            units_member = prefix + ".units.jsonl.gz"
            raw_root = summary_member.split("/decoded/", 1)[0] + "/raw recordings/"
            frames_member = raw_root + run_name + ".frames.bin"
            if units_member not in names or frames_member not in names:
                raise ValueError(f"run is missing units or frames provenance: {run_name}")
            summary = json.loads(source.read(summary_member))
            side2 = _side(summary, "side2", 2, ranged_master, run_name)
            side3 = _side(summary, "side3", 3, melee_master, run_name)
            starting_units = _starting_units(
                source,
                units_member,
                side2["count"] + side3["count"],
                run_name,
            )
            _validate_starting_roster(starting_units, side2, side3, run_name)
            winner_key = summary["outcome"]
            if winner_key not in ("side2", "side3"):
                raise ValueError(f"dedicated run has unsupported outcome {winner_key!r}: {run_name}")
            winner_owner = 2 if winner_key == "side2" else 3
            winner_side = side2 if winner_owner == 2 else side3
            winner_hp = winner_side["hp_remaining"]
            signed_score = 100 * winner_hp / winner_side["hp_start"]
            if winner_owner == 2:
                signed_score = -signed_score
            grouped[ratio].append({
                "tag": ratio if repeat == 1 else f"{ratio}_r{repeat}",
                "repeat": repeat,
                "source_members": {
                    "frames": frames_member,
                    "summary": summary_member,
                    "units": units_member,
                },
                "starting_units": starting_units,
                "starting_hp_by_owner": {
                    "2": side2["hp_start"],
                    "3": side3["hp_start"],
                },
                "winner_owner": winner_owner,
                "winner_hp": winner_hp,
                "survivors": winner_side["survivors"],
                "signed_score": signed_score,
            })

    rows = []
    for ratio in RATIOS:
        runs = sorted(grouped[ratio], key=lambda run: run["repeat"])
        if [run["repeat"] for run in runs] != [1, 2, 3, 4, 5]:
            raise ValueError(f"ratio does not contain repeats 1-5: {archive.name} {ratio}")
        rows.append({"ratio": ratio, "runs": runs})
    first = rows[0]["runs"][0]
    first_side2 = [unit for unit in first["starting_units"] if unit["owner"] == 2]
    first_side3 = [unit for unit in first["starting_units"] if unit["owner"] == 3]
    return {
        "id": f"{ranged_slug}_vs_{melee_slug}",
        "ranged_slug": ranged_slug,
        "melee_slug": melee_slug,
        "archive": archive.name,
        "zip_sha256": zip_sha256,
        "side2": {"owner": 2, "master": ranged_master, "unit": side2["unit"]},
        "side3": {"owner": 3, "master": melee_master, "unit": side3["unit"]},
        "first_roster_masters": sorted({unit["master"] for unit in first_side2 + first_side3}),
        "ratios": rows,
    }


def _side(
    summary: dict[str, Any],
    key: str,
    owner: int,
    master: int,
    run_name: str,
) -> dict[str, Any]:
    side = summary.get("sides", {}).get(key)
    if not isinstance(side, dict) or side.get("owner") != owner or side.get("master") != master:
        raise ValueError(f"unexpected {key} identity: {run_name}")
    return {
        "owner": owner,
        "master": master,
        "unit": side["unit"],
        "count": side["start_count"],
        "hp_start": side["hp_start"],
        "hp_remaining": side["hp_remaining"],
        "survivors": side["survivors"],
    }


def _starting_units(
    source: ZipFile,
    member: str,
    expected_count: int,
    run_name: str,
) -> list[dict[str, Any]]:
    first_by_id: dict[int, dict[str, Any]] = {}
    with source.open(member) as compressed:
        with gzip.GzipFile(fileobj=compressed) as lines:
            for raw_line in lines:
                sample = json.loads(raw_line)
                first_by_id.setdefault(sample["id"], sample)
                if len(first_by_id) == expected_count:
                    break
    if len(first_by_id) != expected_count:
        raise ValueError(f"expected {expected_count} starting units, found {len(first_by_id)}: {run_name}")
    return [
        {
            "id": sample["id"],
            "owner": sample["owner"],
            "master": sample["master"],
            "x": sample["x"],
            "y": sample["y"],
            "hp": sample["hp"],
        }
        for sample in sorted(first_by_id.values(), key=lambda value: value["id"])
    ]


def _validate_starting_roster(
    units: list[dict[str, Any]],
    side2: dict[str, Any],
    side3: dict[str, Any],
    run_name: str,
) -> None:
    for side in (side2, side3):
        roster = [unit for unit in units if unit["owner"] == side["owner"]]
        if len(roster) != side["count"] or {unit["master"] for unit in roster} != {side["master"]}:
            raise ValueError(f"starting roster differs from summary: {run_name} owner {side['owner']}")


def _validate_legacy_fixture(matchup: dict[str, Any], path: Path) -> None:
    legacy = json.loads(path.read_text(encoding="utf-8"))
    if legacy["archive"] != matchup["archive"] or legacy["zip_sha256"] != matchup["zip_sha256"]:
        raise ValueError(f"legacy fixture provenance differs: {path.name}")
    for row in matchup["ratios"]:
        old_runs = legacy["ratios"][row["ratio"]]["runs"]
        for current, old in zip(row["runs"], old_runs, strict=True):
            projected = [
                [unit["id"], unit["owner"], unit["master"], unit["x"], unit["y"]]
                for unit in current["starting_units"]
            ]
            if (
                current["tag"] != old["tag"]
                or current["winner_owner"] != old["winnerOwner"]
                or current["winner_hp"] != old["winnerHp"]
                or current["survivors"] != old["survivors"]
                or projected != old["startingUnits"]
            ):
                raise ValueError(f"legacy fixture does not reproduce from raw archive: {path.name} {current['tag']}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> None:
    selected_archives = set(sys.argv[1:]) or None
    truth = import_corpus(selected_archives)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
