"""Export the exact 27v27 formation from the current melee golden scenario."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import AoE2ScenarioParser
from AoE2ScenarioParser import settings
from AoE2ScenarioParser.datasets.effects import EffectId
from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


settings.PRINT_STATUS_UPDATES = False

EXPECTED_SOURCE_SHA256 = (
    "31f3bed38ce0512b484124d89d5aa4e97318b3ea55c398bb8dad27242c769f4e"
)
FOREST_TERRAIN_IDS = frozenset({10, 56, 128})
RETAINED_PER_SIDE = 27


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_names() -> dict[int, str]:
    names: dict[int, str] = {}
    for dataset in (UnitInfo, OtherInfo):
        for item in dataset:
            names.setdefault(int(item.value[0]), item.name)
    return names


def _cell(x: float, y: float) -> tuple[int, int]:
    return math.floor(x), math.floor(y)


def extract_formation(path: Path) -> dict:
    """Return the literal first 27 P2/P3 records and their placement audit."""
    path = Path(path).resolve()
    source_hash = _sha256(path)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            "golden melee scenario hash mismatch: "
            f"expected {EXPECTED_SOURCE_SHA256}, got {source_hash}"
        )

    scenario = AoE2DEScenario.from_file(str(path))
    names = _object_names()
    sides: dict[str, list[dict]] = {}
    for player_id in (2, 3):
        units = list(scenario.unit_manager.get_player_units(player_id))
        retained = units[:RETAINED_PER_SIDE]
        if len(retained) != RETAINED_PER_SIDE:
            raise ValueError(
                f"player {player_id} has fewer than {RETAINED_PER_SIDE} source units"
            )
        sides[str(player_id)] = [
            {
                "reference_id": int(unit.reference_id),
                "player_id": player_id,
                "unit_const": int(unit.unit_const),
                "name": names.get(int(unit.unit_const), f"UNKNOWN_{int(unit.unit_const)}"),
                "position": {
                    "x": float(unit.x),
                    "y": float(unit.y),
                    "z": float(unit.z),
                },
                "rotation": float(unit.rotation),
            }
            for unit in retained
        ]

    patrol_effect = int(EffectId.PATROL)
    opening_patrol_by_owner: dict[str, dict] = {}
    for trigger_index, trigger in enumerate(scenario.trigger_manager.triggers):
        if not bool(trigger.enabled):
            continue
        for effect_index, effect in enumerate(trigger.effects):
            if int(effect.effect_type) != patrol_effect:
                continue
            owner = int(effect.source_player)
            if owner not in (2, 3):
                continue
            owner_key = str(owner)
            if owner_key in opening_patrol_by_owner:
                raise ValueError(f"multiple opening patrol effects for player {owner}")
            x = int(effect.location_x)
            y = int(effect.location_y)
            if not (0 <= x < scenario.map_manager.map_width
                    and 0 <= y < scenario.map_manager.map_height):
                raise ValueError(f"player {owner} patrol destination is outside the map")
            opening_patrol_by_owner[owner_key] = {
                "x": x,
                "y": y,
                "trigger_index": trigger_index,
                "effect_index": effect_index,
                "area": {
                    "x1": int(effect.area_x1),
                    "y1": int(effect.area_y1),
                    "x2": int(effect.area_x2),
                    "y2": int(effect.area_y2),
                },
            }
    if set(opening_patrol_by_owner) != {"2", "3"}:
        raise ValueError("golden melee scenario must contain one opening patrol per side")

    gaia_cells = {
        _cell(float(unit.x), float(unit.y))
        for unit in scenario.unit_manager.get_player_units(0)
    }
    forest_cells = {
        (int(tile.x), int(tile.y))
        for tile in scenario.map_manager.terrain
        if int(tile.terrain_id) in FOREST_TERRAIN_IDS
    }
    conflicts: list[dict] = []
    occupied: dict[tuple[int, int], int] = {}
    for units in sides.values():
        for unit in units:
            x = unit["position"]["x"]
            y = unit["position"]["y"]
            cell = _cell(x, y)
            if cell in forest_cells:
                conflicts.append({"code": "forest", "reference_id": unit["reference_id"], "cell": list(cell)})
            if cell in gaia_cells:
                conflicts.append({"code": "gaia", "reference_id": unit["reference_id"], "cell": list(cell)})
            if cell in occupied:
                conflicts.append({
                    "code": "duplicate_cell",
                    "reference_id": unit["reference_id"],
                    "other_reference_id": occupied[cell],
                    "cell": list(cell),
                })
            occupied[cell] = unit["reference_id"]

    return {
        "schema_version": 1,
        "source": {
            "filename": path.name,
            "sha256": source_hash,
            "scenario_version": float(scenario.scenario_version),
            "parser": "AoE2ScenarioParser",
            "parser_version": str(AoE2ScenarioParser.__version__),
            "selection_rule": "first_27_units_in_player_order",
        },
        "map": {
            "width": int(scenario.map_manager.map_width),
            "height": int(scenario.map_manager.map_height),
        },
        "opening_patrol": {
            "effect_id": patrol_effect,
            "by_owner": opening_patrol_by_owner,
        },
        "sides": sides,
        "validation": {"valid": not conflicts, "conflicts": conflicts},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = extract_formation(args.scenario)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} "
        f"({RETAINED_PER_SIDE} P2 units, {RETAINED_PER_SIDE} P3 units)"
    )


if __name__ == "__main__":
    main()
