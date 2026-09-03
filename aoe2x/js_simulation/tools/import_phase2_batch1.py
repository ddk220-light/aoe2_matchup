"""Import Batch 1 truth from the authorized Phase 2 golden archive.

The importer reads only the project-local, SHA-256-locked archive.  It keeps
the exact starting roster and source members for every selected recording and
does not inspect simulation output.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile


ARCHIVE_NAME = "aoe2_golden_phase2_WITH_TAPES.zip"
REQUIRED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6"
ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_ARCHIVE = ROOT / "calibration" / "source" / ARCHIVE_NAME
SOURCE_MANIFEST = ROOT / "calibration" / "source" / "phase2_source.json"
OUTPUT_TRUTH = ROOT / "calibration" / "fixtures" / "phase2" / "batch1_truth.json"
DECODED_ROOT = "phase2/decoded/"
RAW_ROOT = "phase2/raw recordings/"
SUMMARY_SUFFIX = ".summary.json"
UNITS_SUFFIX = ".units.jsonl.gz"
FRAMES_SUFFIX = ".frames.bin"
REPEAT_SUFFIX = re.compile(r"_r(?P<repeat>\d+)$")

BATCH1_UNITS = (
    ("elite_longbowman_britons", "elite_longbowman", 530),
    ("elite_throwing_axeman_franks", "elite_throwing_axeman", 531),
    ("elite_woad_raider_celts", "elite_woad_raider", 534),
    ("elite_shotel_warrior_ethiopians", "elite_shotel_warrior", 1018),
    ("elite_gbeto_malians", "elite_gbeto", 1015),
    ("elite_huskarl_goths", "elite_huskarl", 555),
    ("elite_teutonic_knight_teutons", "elite_teutonic_knight", 554),
    ("elite_boyar_slavs", "elite_boyar", 878),
    ("elite_tarkan_huns", "elite_tarkan", 757),
    ("elite_genoese_crossbowman_italians", "elite_genoese_crossbowman", 868),
    ("elite_plumed_archer_mayans", "elite_plumed_archer", 765),
    ("elite_mangudai_mongols", "elite_mangudai", 561),
    ("elite_rattan_archer_vietnamese", "elite_rattan_archer", 1131),
    ("elite_janissary_turks", "elite_janissary", 557),
    ("elite_conquistador_spanish", "elite_conquistador", 773),
    ("elite_war_wagon_koreans", "elite_war_wagon", 829),
    ("elite_magyar_huszar_magyars", "elite_magyar_huszar", 871),
    ("elite_keshik_tatars", "elite_keshik", 1230),
    ("elite_karambit_warrior_malay", "elite_karambit_warrior", 1125),
    ("warrior_priest_armenians", "warrior_priest", 1811),
)
STANDARD_OPPONENTS = (
    ("arbalester", "arbalester", 492),
    ("champion", "champion", 567),
    ("elite_elephant", "elite_elephant", 1134),
    ("heavy_cav_archer", "heavy_cav_archer", 474),
    ("heavy_scorpion", "heavy_scorpion", 542),
    ("paladin", "paladin", 569),
)
EXPECTED_ROWS = 120
EXPECTED_RECORDINGS = 288


def import_archive(archive: Path = AUTHORIZED_ARCHIVE) -> dict[str, Any]:
    archive = Path(archive)
    _verify_authorized_archive(archive)
    batch_by_key = {key: (slug, master) for key, slug, master in BATCH1_UNITS}
    opponent_by_key = {key: (slug, master) for key, slug, master in STANDARD_OPPONENTS}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    row_sides: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    with ZipFile(archive) as source:
        names = set(source.namelist())
        summaries = sorted(
            name for name in names
            if name.startswith(DECODED_ROOT) and name.endswith(SUMMARY_SUFFIX)
        )
        for summary_member in summaries:
            tag = summary_member[len(DECODED_ROOT):-len(SUMMARY_SUFFIX)]
            stem, repeat = _stem_and_repeat(tag)
            pieces = stem.split("__vs__")
            if len(pieces) != 2 or pieces[0] not in batch_by_key:
                continue
            unit_key, opponent_key = pieces
            if opponent_key not in opponent_by_key:
                raise ValueError(f"unexpected Batch 1 opponent: {tag}")
            unit_slug, unit_master = batch_by_key[unit_key]
            opponent_slug, opponent_master = opponent_by_key[opponent_key]
            units_member = DECODED_ROOT + tag + UNITS_SUFFIX
            frames_member = RAW_ROOT + tag + FRAMES_SUFFIX
            for member in (units_member, frames_member):
                if member not in names:
                    raise ValueError(f"missing source member for {tag}: {member}")

            summary = json.loads(source.read(summary_member))
            slug_by_master = {
                unit_master: unit_slug,
                opponent_master: opponent_slug,
            }
            side2 = _side(summary, "side2", 2, slug_by_master, tag)
            side3 = _side(summary, "side3", 3, slug_by_master, tag)
            if {side2["master"], side3["master"]} != {unit_master, opponent_master}:
                raise ValueError(f"tape sides do not contain the named matchup: {tag}")
            starting_units = _starting_units(
                source,
                units_member,
                side2["count"] + side3["count"],
                tag,
            )
            _validate_starting_roster(starting_units, side2, side3, tag)
            starting_hp = _starting_hp_by_owner(starting_units)
            for side in (side2, side3):
                if abs(starting_hp[side["owner"]] - side["hp_start"]) > 1e-6:
                    raise ValueError(f"starting HP differs from unit stream: {tag}")

            outcome = summary.get("outcome")
            if outcome not in ("side2", "side3"):
                raise ValueError(f"unsupported Batch 1 outcome {outcome!r}: {tag}")
            winner_owner = 2 if outcome == "side2" else 3
            winner_side = side2 if winner_owner == 2 else side3
            winner_hp = winner_side["hp_remaining"]
            signed_score = 100.0 * winner_hp / winner_side["hp_start"]
            if winner_owner == 2:
                signed_score = -signed_score

            row_id = f"{unit_slug}_vs_{opponent_slug}"
            row_identity = (
                {key: value for key, value in side2.items() if key not in ("hp_start", "hp_remaining", "survivors")},
                {key: value for key, value in side3.items() if key not in ("hp_start", "hp_remaining", "survivors")},
            )
            if row_id in row_sides and row_sides[row_id] != row_identity:
                raise ValueError(f"inconsistent row identity: {row_id}")
            row_sides[row_id] = row_identity
            grouped[row_id].append({
                "tag": tag,
                "repeat": repeat,
                "archive_key": stem,
                "source_members": {
                    "frames": frames_member,
                    "summary": summary_member,
                    "units": units_member,
                },
                "starting_units": starting_units,
                "starting_units_hash": _canonical_hash(starting_units),
                "starting_hp_by_owner": {"2": side2["hp_start"], "3": side3["hp_start"]},
                "status": "scored",
                "winner_owner": winner_owner,
                "winner_hp": winner_hp,
                "survivors": winner_side["survivors"],
                "signed_score": signed_score,
            })

    unit_order = {slug: index for index, (_, slug, _) in enumerate(BATCH1_UNITS)}
    opponent_order = {slug: index for index, (_, slug, _) in enumerate(STANDARD_OPPONENTS)}
    rows = []
    for row_id, runs in grouped.items():
        side2, side3 = row_sides[row_id]
        runs.sort(key=lambda run: run["repeat"])
        if [run["repeat"] for run in runs] != list(range(1, len(runs) + 1)):
            raise ValueError(f"non-contiguous repeats: {row_id}")
        if len({run["starting_units_hash"] for run in runs}) != 1:
            raise ValueError(f"multiple starting geometries: {row_id}")
        rows.append({
            "id": row_id,
            "subject_slug": row_id.rsplit("_vs_", 1)[0],
            "opponent_slug": row_id.rsplit("_vs_", 1)[1],
            "matchup": f"{side2['unit']} vs {side3['unit']}",
            "side2": side2,
            "side3": side3,
            "runs": runs,
        })
    rows.sort(key=lambda row: (
        unit_order[row["subject_slug"]],
        opponent_order[row["opponent_slug"]],
    ))
    _validate_corpus(rows)
    return {
        "schema_version": 1,
        "archive": {
            "name": ARCHIVE_NAME,
            "path": "aoe2x/js_simulation/calibration/source/" + ARCHIVE_NAME,
            "zip_sha256": REQUIRED_SHA256,
        },
        "batch": 1,
        "unit_slugs": [slug for _, slug, _ in BATCH1_UNITS],
        "opponent_slugs": [slug for _, slug, _ in STANDARD_OPPONENTS],
        "rows": rows,
    }


def write_truth_fixture(
    archive: Path = AUTHORIZED_ARCHIVE,
    output: Path = OUTPUT_TRUTH,
) -> dict[str, Any]:
    truth = import_archive(archive)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return truth


def _verify_authorized_archive(archive: Path) -> None:
    if archive.resolve() != AUTHORIZED_ARCHIVE.resolve():
        raise ValueError("archive must be the project-local authorized Phase 2 source")
    if archive.name != ARCHIVE_NAME or not archive.is_file():
        raise FileNotFoundError(archive)
    lock = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    if not lock.get("authorized"):
        raise ValueError("Phase 2 source manifest is not authorized")
    if lock.get("archive") != ARCHIVE_NAME or lock.get("zip_sha256") != REQUIRED_SHA256:
        raise ValueError("Phase 2 source manifest does not match the authorized archive")
    if _sha256(archive) != REQUIRED_SHA256:
        raise ValueError("authorized Phase 2 archive SHA-256 mismatch")


def _stem_and_repeat(tag: str) -> tuple[str, int]:
    match = REPEAT_SUFFIX.search(tag)
    if match is None:
        return tag, 1
    repeat = int(match.group("repeat"))
    if repeat < 2:
        raise ValueError(f"invalid repeat suffix: {tag}")
    return tag[:match.start()], repeat


def _side(
    summary: dict[str, Any],
    key: str,
    owner: int,
    slug_by_master: dict[int, str],
    tag: str,
) -> dict[str, Any]:
    side = summary.get("sides", {}).get(key)
    if not isinstance(side, dict) or side.get("owner") != owner:
        raise ValueError(f"unexpected {key} identity: {tag}")
    master = side.get("master")
    slug = slug_by_master.get(master)
    if slug is None:
        raise ValueError(f"unexpected {key} master {master}: {tag}")
    required = ("unit", "start_count", "hp_start", "hp_remaining", "survivors")
    if any(field not in side for field in required):
        raise ValueError(f"incomplete {key}: {tag}")
    return {
        "owner": owner,
        "slug": slug,
        "unit": side["unit"],
        "master": master,
        "count": side["start_count"],
        "hp_start": float(side["hp_start"]),
        "hp_remaining": float(side["hp_remaining"]),
        "survivors": side["survivors"],
    }


def _starting_units(
    source: ZipFile,
    member: str,
    expected_count: int,
    tag: str,
) -> list[dict[str, Any]]:
    first_by_id: dict[int, dict[str, Any]] = {}
    with source.open(member) as compressed:
        with gzip.GzipFile(fileobj=compressed) as lines:
            for raw_line in lines:
                sample = json.loads(raw_line)
                unit_id = sample.get("id")
                if not isinstance(unit_id, int):
                    raise ValueError(f"unit sample has no numeric id: {tag}")
                first_by_id.setdefault(unit_id, sample)
                if len(first_by_id) == expected_count:
                    break
    if len(first_by_id) != expected_count:
        raise ValueError(f"expected {expected_count} starting units, found {len(first_by_id)}: {tag}")
    units = []
    for sample in sorted(first_by_id.values(), key=lambda value: value["id"]):
        if any(field not in sample for field in ("owner", "master", "x", "y", "hp")):
            raise ValueError(f"incomplete starting unit: {tag}")
        units.append({
            "id": sample["id"],
            "owner": sample["owner"],
            "master": sample["master"],
            "x": sample["x"],
            "y": sample["y"],
            "hp": sample["hp"],
        })
    return units


def _validate_starting_roster(
    units: list[dict[str, Any]],
    side2: dict[str, Any],
    side3: dict[str, Any],
    tag: str,
) -> None:
    for side in (side2, side3):
        roster = [unit for unit in units if unit["owner"] == side["owner"]]
        if len(roster) != side["count"] or {unit["master"] for unit in roster} != {side["master"]}:
            raise ValueError(f"starting roster differs from summary: {tag} owner {side['owner']}")


def _starting_hp_by_owner(units: list[dict[str, Any]]) -> dict[int, float]:
    totals = {2: 0.0, 3: 0.0}
    for unit in units:
        totals[unit["owner"]] += float(unit["hp"])
    return totals


def _validate_corpus(rows: list[dict[str, Any]]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} Batch 1 rows, found {len(rows)}")
    recordings = [run for row in rows for run in row["runs"]]
    if len(recordings) != EXPECTED_RECORDINGS:
        raise ValueError(f"expected {EXPECTED_RECORDINGS} Batch 1 recordings, found {len(recordings)}")
    expected_opponents = {slug for _, slug, _ in STANDARD_OPPONENTS}
    for _, slug, _ in BATCH1_UNITS:
        actual = {
            row["opponent_slug"]
            for row in rows
            if row["subject_slug"] == slug
        }
        if actual != expected_opponents:
            raise ValueError(f"incomplete opponent coverage for {slug}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def main() -> None:
    truth = write_truth_fixture()
    recordings = sum(len(row["runs"]) for row in truth["rows"])
    print(
        f"archive={truth['archive']['name']} "
        f"sha256={truth['archive']['zip_sha256']} "
        f"rows={len(truth['rows'])} recordings={recordings}"
    )


if __name__ == "__main__":
    main()
