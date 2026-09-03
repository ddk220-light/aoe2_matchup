"""Export the website's Imperial unit catalogue for the local JS viewer.

The output is display metadata only. Clean-room simulation availability still
comes exclusively from ``src/unit-registry.js`` at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path


def _key_part(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def export_catalogue(database: Path, output: Path) -> dict:
    database = Path(database).resolve()
    output = Path(output).resolve()
    if not database.is_file():
        raise FileNotFoundError(database)

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, civ_name, unit_name, unit_slug, unit_type,
                   unit_class_name
            FROM ref_units
            WHERE age = 'Imperial'
            ORDER BY civ_name COLLATE NOCASE, unit_name COLLATE NOCASE, id
            """
        ).fetchall()

    civilizations: list[dict] = []
    by_civ: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        identity = (row["civ_name"], row["unit_name"])
        if identity in seen:
            raise ValueError(
                f"duplicate Imperial catalogue entry {identity[0]} / {identity[1]}"
            )
        seen.add(identity)
        by_civ.setdefault(row["civ_name"], []).append(
            {
                "catalogueKey": (
                    f"{_key_part(row['civ_name'])}:"
                    f"{_key_part(row['unit_name'])}:{row['id']}"
                ),
                "name": row["unit_name"],
                "slug": row["unit_slug"],
                "type": row["unit_type"],
                "className": row["unit_class_name"] or "Unknown",
            }
        )

    for name, units in by_civ.items():
        civilizations.append({"name": name, "units": units})

    payload = {
        "schemaVersion": 1,
        "source": {
            "filename": database.name,
            "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        },
        "civilizations": civilizations,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(body, encoding="utf-8", newline="\n")
    temporary.replace(output)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = export_catalogue(args.database, args.output)
    unit_count = sum(len(civ["units"]) for civ in payload["civilizations"])
    print(
        f"Exported {unit_count} Imperial rows across "
        f"{len(payload['civilizations'])} civilizations to {args.output}"
    )


if __name__ == "__main__":
    main()
