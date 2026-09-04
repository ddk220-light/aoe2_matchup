"""Serializable golden-scenario contract for the V3 web backend.

The JavaScript engine owns combat behavior.  This module only packages the
same checked-in golden map, formation, orders, diplomacy and trigger facts for
delivery to a browser worker.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parent
_GOLDEN_HASHES = {
    "melee_vs_melee": "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e",
    "ranged_vs_ranged": "f44097ef86e6b123c6dfeb4989842e548af91f0d492e69caf6de87148f040883",
    "ranged_vs_melee": "13c41485a00943ef525cab848d835d1379259fc8fff38b83d4ec510bc8824783",
    "melee_vs_ranged": "faf8d616ac9bb4601c4582deccec0984e997617d8c121bc44d698c7963f038a8",
}


@lru_cache(maxsize=1)
def _map_fixture() -> dict[str, Any]:
    return json.loads((_ROOT / "fixtures" / "golden_map.json").read_text("utf-8"))


@lru_cache(maxsize=1)
def _melee_fixture() -> dict[str, Any]:
    return json.loads(
        (_ROOT / "fixtures" / "golden_formation_27v27.json").read_text("utf-8")
    )


@lru_cache(maxsize=1)
def _ranged_fixture() -> dict[str, Any]:
    return json.loads(
        (_ROOT / "fixtures" / "current_ranged_golden_formations.json").read_text(
            "utf-8"
        )
    )


def _cells(rows: list[dict[str, Any]], owner: int, expected: int) -> list[dict[str, float]]:
    if len(rows) != expected:
        raise RuntimeError(f"golden Player {owner} has {len(rows)} cells, expected {expected}")
    cells = []
    for row in rows:
        position = row.get("position", {})
        if row.get("player_id", owner) != owner or not all(
            isinstance(position.get(axis), (int, float)) for axis in ("x", "y")
        ):
            raise RuntimeError(f"golden Player {owner} contains an invalid cell")
        cells.append({"x": float(position["x"]), "y": float(position["y"])})
    return cells


def _direct_teams() -> list[dict[str, Any]]:
    return [
        {"winnerOwner": 2, "owners": [2]},
        {"winnerOwner": 3, "owners": [3]},
    ]


def build_arena_preview_payload() -> dict[str, Any]:
    """Return the map and authored formation slots used by the unit picker.

    The picker deliberately receives no units.  It draws the empty arena first
    and fills these slots client-side only after the corresponding team has a
    selected unit.
    """
    fixture = _melee_fixture()
    return {
        "map": _map_fixture()["map"],
        "placementByOwner": {
            owner: [
                {
                    "x": float(row["position"]["x"]),
                    "y": float(row["position"]["y"]),
                    "rotation": float(row.get("rotation", 0)),
                }
                for row in fixture["sides"][owner]
            ]
            for owner in ("2", "3")
        },
    }


def build_scenario_payload(
    family: str,
    *,
    engine_family: str,
    include_buffer: bool,
) -> dict[str, Any]:
    """Return JSON-safe scenario inputs sourced from the golden fixtures."""
    if family not in _GOLDEN_HASHES:
        raise ValueError(f"unknown golden scenario family {family!r}")
    result: dict[str, Any] = {
        "version": "golden-v1",
        "family": family,
        "engineFamily": engine_family,
        "mapFixture": _map_fixture(),
        "preserveOwnerOrientation": family != "melee_vs_melee",
        "hasRangedBuffer": False,
    }
    if family == "melee_vs_melee":
        fixture = _melee_fixture()
        if fixture.get("source", {}).get("sha256") != _GOLDEN_HASHES[family]:
            raise RuntimeError("melee golden source hash does not match")
        result.update(
            {
                "goldenSha256": _GOLDEN_HASHES[family],
                "placementByOwner": {
                    "2": _cells(fixture["sides"]["2"], 2, 27),
                    "3": _cells(fixture["sides"]["3"], 3, 27),
                },
                "openingPatrolByOwner": {
                    owner: {
                        "x": float(fixture["opening_patrol"]["by_owner"][owner]["x"]),
                        "y": float(fixture["opening_patrol"]["by_owner"][owner]["y"]),
                    }
                    for owner in ("2", "3")
                },
                "victoryTeams": _direct_teams(),
            }
        )
        return result

    document = _ranged_fixture()
    if document.get("schema_version") != 1:
        raise RuntimeError("ranged golden schema is incompatible")
    fixture = document.get("families", {}).get(family)
    if fixture is None or fixture.get("source", {}).get("sha256") != _GOLDEN_HASHES[family]:
        raise RuntimeError(f"{family} golden source hash does not match")
    mixed = family in {"ranged_vs_melee", "melee_vs_ranged"}
    if include_buffer and not mixed:
        raise ValueError("ranged buffer requires a mixed ranged/melee family")
    result.update(
        {
            "goldenSha256": _GOLDEN_HASHES[family],
            "placementByOwner": {
                "2": _cells(fixture["sides"]["2"], 2, 27),
                "3": _cells(fixture["sides"]["3"], 3, 27),
            },
        }
    )
    if include_buffer:
        buffer_cells = _cells(fixture["sides"]["4"], 4, 9)
        if any(row.get("unit_const") != 448 for row in fixture["sides"]["4"]):
            raise RuntimeError(f"{family} golden contains a non-scout buffer unit")
        result.update(
            {
                "hasRangedBuffer": True,
                "auxiliaryArmiesByOwner": {
                    "4": {
                        "slug": "scout_cavalry",
                        "unit_slug": "scout_cavalry",
                        "civilization": "Spanish",
                        "cells": buffer_cells,
                    }
                },
                "diplomacyByOwner": fixture["initial_diplomacy"],
                "triggers": fixture["triggers"],
                "victoryTeams": [
                    {"winnerOwner": 2, "owners": [2, 4]},
                    {"winnerOwner": 3, "owners": [3]},
                ]
                if family == "ranged_vs_melee"
                else [
                    {"winnerOwner": 2, "owners": [2]},
                    {"winnerOwner": 3, "owners": [3, 4]},
                ],
            }
        )
    else:
        result.update(
            {
                "diplomacyByOwner": {"2": {"3": 3}, "3": {"2": 3}},
                "triggers": [
                    {
                        **fixture["triggers"][0],
                        "effects": [
                            effect
                            for effect in fixture["triggers"][0]["effects"]
                            if effect.get("owner") != 4
                        ],
                    }
                ],
                "victoryTeams": _direct_teams(),
            }
        )
    return result
