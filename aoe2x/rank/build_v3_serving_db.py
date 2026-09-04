"""Build the serving database for the staged Simulation V3 rankings cutover."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from aoe2x.rank.derived_db import create_db as create_derived_db


BUILD_NUMBER = "177723"
EXPECTED_SOURCE_SUMMARY = {
    "failures": 0,
    "matchups": 4530,
    "runs": 22650,
    "scores": 15855,
}
EXPECTED_V3_LAND_VARIANTS = 522
EXPECTED_V3_LAND_SCORE_ROWS = 10962
EXPECTED_RETAIL_ROWS_BY_LINE = {
    "ram": 1378,
    "trebuchet": 650,
    "bombard_cannon": 364,
    "cannon_galleon": 637,
    "galleon": 1120,
    "fire": 1060,
    "hulk": 1080,
}
EXPECTED_PUBLISHED_ROWS = 17251

V3_STAGES = ("infantry", "archery", "cavalry")
V3_FINAL_SCORE_BY_STAGE = {
    "infantry": "militia_value",
    "archery": "ranged_effectiveness",
    "cavalry": "stable_effectiveness",
}
V3_COMMON_SCORE_TYPES = {
    "general_combat",
    "anti_cav",
    "anti_archer",
    "anti_trash",
    "aa_v3_27_vs_arb",
    "aa_v3_27_vs_arb_raw",
    "ac_v3_27_vs_paladin",
    "ac_v3_27_vs_paladin_raw",
    "at_v3_27_vs_elite_skirm",
    "at_v3_27_vs_elite_skirm_raw",
    "at_v3_27_vs_halb",
    "at_v3_27_vs_halb_raw",
    "at_v3_27_vs_hussar",
    "at_v3_27_vs_hussar_raw",
    "gc_v3_27_vs_arb",
    "gc_v3_27_vs_arb_raw",
    "gc_v3_27_vs_champ",
    "gc_v3_27_vs_champ_raw",
    "gc_v3_27_vs_paladin",
    "gc_v3_27_vs_paladin_raw",
}

SIEGE_LINES = {"ram", "trebuchet", "bombard_cannon", "cannon_galleon"}
SIEGE_SCORE_TYPES = {"anti_building_score"} | {
    f"ab_{target}_{mode}_{measure}"
    for target in ("persian", "teuton", "byzantine")
    for mode in ("5k", "5u")
    for measure in ("dmg", "ttk")
}
NAVAL_LINES = {"galleon", "fire", "hulk"}
NAVAL_SCORE_TYPES = {
    "naval_effectiveness",
    "vs_fire",
    "vs_fire_30v30",
    "vs_fire_3k",
    "vs_galleon",
    "vs_galleon_30v30",
    "vs_galleon_3k",
    "vs_hulk",
    "vs_hulk_30v30",
    "vs_hulk_3k",
}


def _load_campaign_metadata(conn: sqlite3.Connection) -> dict[str, object]:
    return {
        row["key"]: json.loads(row["value_json"])
        for row in conn.execute("SELECT key, value_json FROM campaign_metadata")
    }


def _validate_v3_source(
    conn: sqlite3.Connection,
    expected_summary: dict[str, int],
) -> dict[str, object]:
    metadata = _load_campaign_metadata(conn)
    failure_count = conn.execute("SELECT COUNT(*) FROM campaign_failures").fetchone()[0]
    if failure_count:
        raise ValueError(f"campaign failures must be zero; found {failure_count}")
    if metadata.get("last_summary") != expected_summary:
        raise ValueError(f"campaign summary mismatch: {metadata.get('last_summary')!r}")
    if metadata.get("seed_count") != 5:
        raise ValueError("seed_count must be 5")
    if metadata.get("resource_weights") != {"food": 1, "wood": 1, "gold": 1}:
        raise ValueError("resource_weights must be 1:1:1")
    if metadata.get("unit_cap") != 27:
        raise ValueError("unit_cap must be 27")

    actual_summary = {
        "failures": failure_count,
        "matchups": conn.execute("SELECT COUNT(*) FROM ranking_matchups").fetchone()[0],
        "runs": conn.execute("SELECT COUNT(*) FROM ranking_runs").fetchone()[0],
        "scores": conn.execute("SELECT COUNT(*) FROM battle_scores").fetchone()[0],
    }
    if actual_summary != expected_summary:
        raise ValueError(f"campaign table counts mismatch: {actual_summary!r}")

    incomplete = conn.execute(
        "SELECT COUNT(*) FROM ranking_matchups WHERE resolved_seeds != 5 OR failed_seeds != 0"
    ).fetchone()[0]
    if incomplete:
        raise ValueError(f"every matchup must have five resolved seeds; found {incomplete} incomplete")

    placeholders = ",".join("?" for _ in V3_STAGES)
    wrong_yardstick_count = conn.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT civ_name, unit_slug, line_slug, stage_name
            FROM ranking_matchups
            WHERE stage_name IN ({placeholders})
            GROUP BY civ_name, unit_slug, line_slug, stage_name
            HAVING COUNT(DISTINCT opponent_civ || ':' || opponent_slug) != 6
        )
        """,
        V3_STAGES,
    ).fetchone()[0]
    if wrong_yardstick_count:
        raise ValueError(f"each V3 land variant must have six yardsticks; found {wrong_yardstick_count} invalid")

    score_types_by_variant: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for row in conn.execute(
        f"""
        SELECT line_slug, stage_name, civ_name, unit_slug, score_type
        FROM battle_scores
        WHERE stage_name IN ({placeholders})
        """,
        V3_STAGES,
    ):
        key = (row["line_slug"], row["stage_name"], row["civ_name"], row["unit_slug"])
        score_types_by_variant[key].add(row["score_type"])
    invalid_score_sets = 0
    for (_line, stage, _civ, _slug), score_types in score_types_by_variant.items():
        expected_types = V3_COMMON_SCORE_TYPES | {V3_FINAL_SCORE_BY_STAGE[stage]}
        if score_types != expected_types:
            invalid_score_sets += 1
    if invalid_score_sets:
        raise ValueError(f"V3 land score-type set mismatch for {invalid_score_sets} variants")

    if expected_summary == EXPECTED_SOURCE_SUMMARY:
        if len(score_types_by_variant) != EXPECTED_V3_LAND_VARIANTS:
            raise ValueError(
                f"expected {EXPECTED_V3_LAND_VARIANTS} V3 land variants; "
                f"found {len(score_types_by_variant)}"
            )
        land_score_count = sum(len(value) for value in score_types_by_variant.values())
        if land_score_count != EXPECTED_V3_LAND_SCORE_ROWS:
            raise ValueError(
                f"expected {EXPECTED_V3_LAND_SCORE_ROWS} V3 land scores; found {land_score_count}"
            )
    return metadata


def _select_v3_rows(conn: sqlite3.Connection, build_number: str) -> list[dict[str, object]]:
    placeholders = ",".join("?" for _ in V3_STAGES)
    rows = conn.execute(
        f"""
        SELECT line_slug, age, civ_name, unit_slug, score_type, score_value
        FROM battle_scores
        WHERE stage_name IN ({placeholders})
        ORDER BY line_slug, age, civ_name, unit_slug, score_type
        """,
        V3_STAGES,
    ).fetchall()
    return [
        {
            "line_slug": row["line_slug"],
            "age": row["age"].lower(),
            "civ_name": row["civ_name"],
            "unit_slug": row["unit_slug"],
            "score_type": row["score_type"],
            "score_value": row["score_value"],
            "build_number": build_number,
        }
        for row in rows
    ]


def _select_retail_rows(
    conn: sqlite3.Connection,
    build_number: str,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT line_slug, age, civ_name, unit_slug, score_type, score_value
        FROM battle_scores
        WHERE build_number = ?
        ORDER BY line_slug, age, civ_name, unit_slug, score_type
        """,
        (build_number,),
    ).fetchall()
    selected = []
    for row in rows:
        keep_siege = row["line_slug"] in SIEGE_LINES and row["score_type"] in SIEGE_SCORE_TYPES
        keep_naval = row["line_slug"] in NAVAL_LINES and row["score_type"] in NAVAL_SCORE_TYPES
        if keep_siege or keep_naval:
            selected.append(
                {
                    "line_slug": row["line_slug"],
                    "age": row["age"].lower(),
                    "civ_name": row["civ_name"],
                    "unit_slug": row["unit_slug"],
                    "score_type": row["score_type"],
                    "score_value": row["score_value"],
                    "build_number": build_number,
                }
            )
    return selected


def _rank_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["line_slug"]),
            str(row["age"]),
            str(row["score_type"]),
            str(row["build_number"]),
        )
        groups[key].append(row)

    ranked = []
    for key in sorted(groups):
        entries = groups[key]
        values = sorted(float(row["score_value"]) for row in entries)
        median = values[len(values) // 2]
        entries.sort(
            key=lambda row: (
                -float(row["score_value"]),
                str(row["civ_name"]),
                str(row["unit_slug"]),
            )
        )
        for rank, row in enumerate(entries, 1):
            ranked.append(
                {
                    **row,
                    "rank": rank,
                    "median_delta": round(float(row["score_value"]) - median, 1),
                }
            )
    return ranked


def _validate_published_rows(
    rows: list[dict[str, object]],
    *,
    build_number: str,
    production_snapshot: bool,
) -> None:
    keys = [
        (
            row["line_slug"],
            row["age"],
            row["civ_name"],
            row["unit_slug"],
            row["score_type"],
            row["build_number"],
        )
        for row in rows
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("published battle-score keys must be unique")
    if any(row["build_number"] != build_number for row in rows):
        raise ValueError("published rows contain the wrong game build")
    if any(row["line_slug"] == "mangonel" for row in rows):
        raise ValueError("mangonel must remain stat-only")
    if any(row["score_type"] == "v3_combat_effectiveness" for row in rows):
        raise ValueError("V3 Siege scores must not be published")

    ranks_by_partition: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for row in rows:
        partition = (
            str(row["line_slug"]),
            str(row["age"]),
            str(row["score_type"]),
            str(row["build_number"]),
        )
        ranks_by_partition[partition].append(int(row["rank"]))
    for partition, ranks in ranks_by_partition.items():
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError(f"non-contiguous ranks in partition {partition!r}")

    if production_snapshot:
        counts_by_line: dict[str, int] = defaultdict(int)
        for row in rows:
            if row["line_slug"] in EXPECTED_RETAIL_ROWS_BY_LINE:
                counts_by_line[str(row["line_slug"])] += 1
        if dict(counts_by_line) != EXPECTED_RETAIL_ROWS_BY_LINE:
            raise ValueError(f"retained retail row counts mismatch: {dict(counts_by_line)!r}")
        if len(rows) != EXPECTED_PUBLISHED_ROWS:
            raise ValueError(f"expected {EXPECTED_PUBLISHED_ROWS} published rows; found {len(rows)}")


def _write_database(path: Path, rows: list[dict[str, object]]) -> None:
    conn = create_derived_db(str(path))
    try:
        conn.executemany(
            """
            INSERT INTO battle_scores
                (line_slug, age, civ_name, unit_slug, score_type, score_value,
                 rank, median_delta, build_number)
            VALUES
                (:line_slug, :age, :civ_name, :unit_slug, :score_type, :score_value,
                 :rank, :median_delta, :build_number)
            """,
            rows,
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM battle_scores").fetchone()[0]
        if count != len(rows):
            raise ValueError(f"output database row mismatch: expected {len(rows)}, found {count}")
        if conn.execute("SELECT COUNT(*) FROM advisor_recommendations").fetchone()[0] != 0:
            raise ValueError("output advisor_recommendations must be empty")
    finally:
        conn.close()


def build_serving_db(
    v3_db_path: str,
    retail_db_path: str,
    output_db_path: str,
    metadata_path: str,
    build_number: str = BUILD_NUMBER,
    expected_summary: dict[str, int] | None = None,
) -> dict[str, object]:
    expected_summary = expected_summary or EXPECTED_SOURCE_SUMMARY
    production_snapshot = expected_summary == EXPECTED_SOURCE_SUMMARY

    v3_conn = sqlite3.connect(v3_db_path)
    v3_conn.row_factory = sqlite3.Row
    retail_conn = sqlite3.connect(retail_db_path)
    retail_conn.row_factory = sqlite3.Row
    try:
        metadata = _validate_v3_source(v3_conn, expected_summary)
        v3_rows = _select_v3_rows(v3_conn, build_number)
        retail_rows = _select_retail_rows(retail_conn, build_number)
    finally:
        v3_conn.close()
        retail_conn.close()

    ranked_rows = _rank_rows(v3_rows + retail_rows)
    _validate_published_rows(
        ranked_rows,
        build_number=build_number,
        production_snapshot=production_snapshot,
    )

    manifest = {
        "schema_version": 1,
        "game_build": build_number,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "v3_source": str(Path(v3_db_path).resolve()),
        "retail_source": str(Path(retail_db_path).resolve()),
        "engine_revision": metadata["engine_revision"],
        "mechanics_build": metadata["source_mechanics_build"],
        "seed_count": metadata["seed_count"],
        "resource_weights": metadata["resource_weights"],
        "unit_cap": metadata["unit_cap"],
        "source_summary": metadata["last_summary"],
        "published_stages": list(V3_STAGES),
        "retained_retail_lines": sorted(SIEGE_LINES | NAVAL_LINES),
        "published_rows": len(ranked_rows),
    }

    output_path = Path(output_db_path)
    metadata_output_path = Path(metadata_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent, delete=False
    ) as temp_db_file:
        temp_db_path = Path(temp_db_file.name)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{metadata_output_path.name}.",
        suffix=".tmp",
        dir=metadata_output_path.parent,
        delete=False,
    ) as temp_metadata_file:
        temp_metadata_path = Path(temp_metadata_file.name)
        json.dump(manifest, temp_metadata_file, indent=2, sort_keys=True)
        temp_metadata_file.write("\n")

    try:
        _write_database(temp_db_path, ranked_rows)
        os.replace(temp_db_path, output_path)
        os.replace(temp_metadata_path, metadata_output_path)
    finally:
        temp_db_path.unlink(missing_ok=True)
        temp_metadata_path.unlink(missing_ok=True)
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v3-db", required=True)
    parser.add_argument("--retail-db", required=True)
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--build-number", default=BUILD_NUMBER)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build_serving_db(
        args.v3_db,
        args.retail_db,
        args.output_db,
        args.metadata,
        build_number=args.build_number,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
