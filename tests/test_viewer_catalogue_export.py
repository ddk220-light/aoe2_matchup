"""Regression tests for the local Battle Simulation display catalogue."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "aoe2x" / "js_simulation" / "tools"
sys.path.insert(0, str(TOOLS))

from export_viewer_catalogue import export_catalogue  # noqa: E402


def _reference_db(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE ref_units (
                id INTEGER PRIMARY KEY,
                civ_name TEXT NOT NULL,
                unit_name TEXT NOT NULL,
                unit_slug TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                age TEXT NOT NULL,
                unit_class_name TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO ref_units VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (4, "Chinese", "Champion", "militia", "standard", "Imperial", "Infantry"),
                (2, "Bohemians", "Hand Cannoneer", "gunpowder", "standard", "Imperial", "Archer"),
                (1, "Bohemians", "Houfnice", "houfnice", "unique", "Imperial", "Siege Weapon"),
                (3, "Chinese", "Long Swordsman", "militia", "standard", "Castle", "Infantry"),
            ],
        )


def test_export_catalogue_is_stable_imperial_display_data(tmp_path):
    """Catch unstable ordering, non-Imperial leakage, and untraceable display data."""
    database = tmp_path / "reference.db"
    output = tmp_path / "catalogue.json"
    _reference_db(database)

    payload = export_catalogue(database, output)

    assert payload == {
        "schemaVersion": 1,
        "source": {
            "filename": "reference.db",
            "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        },
        "civilizations": [
            {
                "name": "Bohemians",
                "units": [
                    {
                        "catalogueKey": "bohemians:hand-cannoneer:2",
                        "name": "Hand Cannoneer",
                        "slug": "gunpowder",
                        "type": "standard",
                        "className": "Archer",
                    },
                    {
                        "catalogueKey": "bohemians:houfnice:1",
                        "name": "Houfnice",
                        "slug": "houfnice",
                        "type": "unique",
                        "className": "Siege Weapon",
                    },
                ],
            },
            {
                "name": "Chinese",
                "units": [
                    {
                        "catalogueKey": "chinese:champion:4",
                        "name": "Champion",
                        "slug": "militia",
                        "type": "standard",
                        "className": "Infantry",
                    }
                ],
            },
        ],
    }
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert output.read_bytes().endswith(b"\n")


def test_export_catalogue_rejects_duplicate_display_rows(tmp_path):
    """Catch an ambiguous civ/name mapping that could enable the wrong engine unit."""
    database = tmp_path / "reference.db"
    output = tmp_path / "catalogue.json"
    _reference_db(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO ref_units VALUES (?, ?, ?, ?, ?, ?, ?)",
            (9, "Chinese", "Champion", "other-line", "standard", "Imperial", "Infantry"),
        )

    try:
        export_catalogue(database, output)
    except ValueError as error:
        assert "duplicate Imperial catalogue entry Chinese / Champion" in str(error)
    else:
        raise AssertionError("duplicate catalogue row was accepted")
