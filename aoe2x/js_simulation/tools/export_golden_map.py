"""Export the literal map layer from an AoE2 DE scenario into JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import AoE2ScenarioParser
from AoE2ScenarioParser.datasets.other import OtherInfo
from AoE2ScenarioParser.datasets.terrains import TerrainId
from AoE2ScenarioParser.datasets.units import UnitInfo
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


REPOSITORY_SOURCE = (
    "aoe2x/js_simulation/calibration/live_observations/"
    "current_melee_golden_2026-08-28/source/meleevsmelee.aoe2scenario"
)


def _terrain_names() -> dict[int, str]:
    return {int(item.value): item.name for item in TerrainId}


def _object_names() -> dict[int, str]:
    names: dict[int, str] = {}
    for dataset in (UnitInfo, OtherInfo):
        for item in dataset:
            object_id = int(item.value[0])
            names.setdefault(object_id, item.name)
    return names


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_map(path: Path, repository_source: str = REPOSITORY_SOURCE) -> dict:
    """Return a stable, complete map fixture without inferred geometry."""
    path = Path(path).resolve()
    scenario = AoE2DEScenario.from_file(str(path))
    terrain_names = _terrain_names()
    object_names = _object_names()

    tiles = [
        {
            "x": int(tile.x),
            "y": int(tile.y),
            "terrain_id": int(tile.terrain_id),
            "terrain_name": terrain_names.get(
                int(tile.terrain_id), f"UNKNOWN_{int(tile.terrain_id)}"
            ),
            "elevation": int(tile.elevation),
            "layer": int(tile.layer),
        }
        for tile in scenario.map_manager.terrain
    ]
    tiles.sort(key=lambda tile: (tile["y"], tile["x"]))

    gaia_objects = [
        {
            "reference_id": int(unit.reference_id),
            "unit_const": int(unit.unit_const),
            "name": object_names.get(
                int(unit.unit_const), f"UNKNOWN_{int(unit.unit_const)}"
            ),
            "x": float(unit.x),
            "y": float(unit.y),
            "z": float(unit.z),
            "rotation": float(unit.rotation),
            "status": int(unit.status),
        }
        for unit in scenario.unit_manager.get_player_units(0)
    ]
    gaia_objects.sort(
        key=lambda unit: (unit["y"], unit["x"], unit["reference_id"])
    )

    terrain_counts = Counter(
        f'{tile["terrain_id"]}:{tile["terrain_name"]}' for tile in tiles
    )
    object_counts = Counter(
        f'{unit["unit_const"]}:{unit["name"]}' for unit in gaia_objects
    )

    return {
        "schema_version": 1,
        "source": {
            "filename": path.name,
            "sha256": _sha256(path),
            "repository_source": repository_source,
            "game_version": str(scenario.game_version),
            "scenario_version": float(scenario.scenario_version),
            "parser": "AoE2ScenarioParser",
            "parser_version": str(AoE2ScenarioParser.__version__),
        },
        "map": {
            "width": int(scenario.map_manager.map_width),
            "height": int(scenario.map_manager.map_height),
            "tiles": tiles,
            "gaia_objects": gaia_objects,
        },
        "terrain_counts": dict(sorted(terrain_counts.items())),
        "object_counts": dict(sorted(object_counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository-source", default=REPOSITORY_SOURCE)
    args = parser.parse_args()

    payload = extract_map(args.scenario, args.repository_source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} "
        f"({len(payload['map']['tiles'])} tiles, "
        f"{len(payload['map']['gaia_objects'])} Gaia objects)"
    )


if __name__ == "__main__":
    main()
