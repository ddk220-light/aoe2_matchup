#!/usr/bin/env python3
"""Populate versioned V3 runtime mechanics in ``aoe2_reference.db``.

The game DAT is needed only while regenerating golden data.  The deployed web
application reads the resulting SQLite rows and never needs a game install.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from aoe2x.js_simulation.tools.export_unit_mechanics import export_unit_mechanics

from .v3_mechanics import (
    MECHANICS_SCHEMA_VERSION,
    build_runtime_profile,
    canonical_json,
    mechanics_hash,
)
from .v3_runtime_config import (
    ADDITIONAL_MODES_BY_CIV_SLUG,
    AUXILIARY_PROFILE_SPECS,
    DISMOUNT_FORM_BY_CIV_SLUG,
    EXPORT_OPTIONS_BY_CIV_SLUG,
    default_mode,
)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().lower()


def _attach_dismount_form(
    exported: dict[str, Any],
    *,
    reference_db: Path,
    dat_path: Path,
    row: dict[str, Any],
) -> None:
    master = DISMOUNT_FORM_BY_CIV_SLUG.get((row["civ_name"], row["unit_slug"]))
    if master is None:
        return
    dismount = export_unit_mechanics(
        reference_db,
        dat_path,
        row["unit_slug"],
        row["civ_name"],
        master,
        concrete_form=True,
    )
    death_animation = exported.get("death_animation")
    if not death_animation:
        raise ValueError(f"{row['unit_slug']} needs a death animation for dismount timing")
    dismount["spawn_delay_seconds"] = round(float(death_animation["seconds"]), 6)
    exported["dismount_form"] = dismount


def _profile_specs(row: dict[str, Any]):
    key = (row["civ_name"], row["unit_slug"])
    yield {
        "mode": default_mode(*key),
        "master": int(row["unit_master"]),
        "options": dict(EXPORT_OPTIONS_BY_CIV_SLUG.get(key, {})),
        "is_default": 1,
    }
    for specification in ADDITIONAL_MODES_BY_CIV_SLUG.get(key, ()):
        yield {**specification, "is_default": 0}


def build_profiles_for_row(
    reference_db: Path,
    dat_path: Path,
    row: dict[str, Any],
):
    for specification in _profile_specs(row):
        exported = export_unit_mechanics(
            reference_db,
            dat_path,
            row["unit_slug"],
            row["civ_name"],
            int(specification["master"]),
            **specification["options"],
        )
        if specification["is_default"]:
            _attach_dismount_form(
                exported,
                reference_db=reference_db,
                dat_path=dat_path,
                row=row,
            )
        profile = build_runtime_profile(exported, row, mode=specification["mode"])
        yield specification["mode"], specification["is_default"], profile


def populate_v3_mechanics(reference_db: Path, dat_path: Path) -> dict[str, int | str]:
    reference_db = Path(reference_db).resolve()
    dat_path = Path(dat_path).resolve()
    if not reference_db.is_file():
        raise FileNotFoundError(reference_db)
    if not dat_path.is_file():
        raise FileNotFoundError(dat_path)

    connection = sqlite3.connect(reference_db)
    connection.row_factory = sqlite3.Row
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(ref_units)")}
        if "unit_master" not in columns:
            raise RuntimeError(
                "ref_units has no unit_master column; regenerate it with the current "
                "aoe2x.dbgen.generate_reference first"
            )
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM ref_units ORDER BY id"
            ).fetchall()
        ]
        if not rows:
            raise RuntimeError("ref_units is empty")

        # Build every payload before touching the published table.  One bad
        # unit therefore cannot leave a partially migrated golden database.
        generated = []
        for index, row in enumerate(rows, 1):
            try:
                for mode, is_default, profile in build_profiles_for_row(
                    reference_db, dat_path, row
                ):
                    generated.append(
                        (
                            row["id"],
                            mode,
                            is_default,
                            MECHANICS_SCHEMA_VERSION,
                            canonical_json(profile),
                            mechanics_hash(profile),
                        )
                    )
            except Exception as exc:
                raise RuntimeError(
                    f"failed V3 mechanics for ref_unit_id={row['id']} "
                    f"{row['civ_name']} {row['unit_slug']}: {exc}"
                ) from exc
            if index % 100 == 0:
                print(f"  built {index}/{len(rows)} unit rows")

        auxiliary = []
        for actor_slug, specification in AUXILIARY_PROFILE_SPECS.items():
            reference = next(
                (
                    row for row in rows
                    if row["civ_name"] == specification["civilization"]
                    and row["unit_slug"] == specification["reference_slug"]
                    and row["age"] == "Imperial"
                ),
                None,
            )
            if reference is None:
                raise RuntimeError(f"missing reference row for auxiliary actor {actor_slug}")
            exported = export_unit_mechanics(
                reference_db,
                dat_path,
                reference["unit_slug"],
                reference["civ_name"],
                specification["master"],
            )
            identity = {
                **reference,
                "unit_slug": actor_slug,
                "unit_name": specification["unit_name"],
            }
            profile = build_runtime_profile(
                exported, identity, mode=specification["mode"]
            )
            auxiliary.append(
                (
                    actor_slug,
                    specification["mode"],
                    MECHANICS_SCHEMA_VERSION,
                    canonical_json(profile),
                    mechanics_hash(profile),
                )
            )

        source_build = _file_hash(dat_path)
        with connection:
            connection.execute("DROP TABLE IF EXISTS ref_unit_mechanics_new")
            connection.execute(
                """
                CREATE TABLE ref_unit_mechanics_new (
                    ref_unit_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    is_default INTEGER NOT NULL CHECK (is_default IN (0, 1)),
                    schema_version INTEGER NOT NULL,
                    mechanics_json TEXT NOT NULL,
                    mechanics_hash TEXT NOT NULL,
                    source_build TEXT NOT NULL,
                    PRIMARY KEY (ref_unit_id, mode),
                    FOREIGN KEY (ref_unit_id) REFERENCES ref_units(id)
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO ref_unit_mechanics_new
                    (ref_unit_id, mode, is_default, schema_version,
                     mechanics_json, mechanics_hash, source_build)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [(*row, source_build) for row in generated],
            )
            bad_defaults = connection.execute(
                """
                SELECT ref_unit_id, SUM(is_default)
                FROM ref_unit_mechanics_new
                GROUP BY ref_unit_id
                HAVING SUM(is_default) != 1
                """
            ).fetchall()
            if bad_defaults:
                raise RuntimeError(f"unit rows without exactly one default mode: {bad_defaults[:5]}")
            connection.execute("DROP TABLE IF EXISTS ref_unit_mechanics")
            connection.execute(
                "ALTER TABLE ref_unit_mechanics_new RENAME TO ref_unit_mechanics"
            )
            connection.execute(
                "CREATE INDEX idx_ref_unit_mechanics_hash "
                "ON ref_unit_mechanics(mechanics_hash)"
            )
            connection.execute("DROP TABLE IF EXISTS ref_auxiliary_mechanics_new")
            connection.execute(
                """
                CREATE TABLE ref_auxiliary_mechanics_new (
                    actor_slug TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    mechanics_json TEXT NOT NULL,
                    mechanics_hash TEXT NOT NULL,
                    source_build TEXT NOT NULL,
                    PRIMARY KEY (actor_slug, mode)
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO ref_auxiliary_mechanics_new
                    (actor_slug, mode, schema_version, mechanics_json,
                     mechanics_hash, source_build)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(*row, source_build) for row in auxiliary],
            )
            connection.execute("DROP TABLE IF EXISTS ref_auxiliary_mechanics")
            connection.execute(
                "ALTER TABLE ref_auxiliary_mechanics_new "
                "RENAME TO ref_auxiliary_mechanics"
            )
    finally:
        connection.close()

    return {
        "unit_rows": len(rows),
        "mechanics_rows": len(generated),
        "auxiliary_rows": len(auxiliary),
        "schema_version": MECHANICS_SCHEMA_VERSION,
        "source_build": source_build,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-db", type=Path, required=True)
    parser.add_argument("--dat", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = populate_v3_mechanics(args.reference_db, args.dat)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
