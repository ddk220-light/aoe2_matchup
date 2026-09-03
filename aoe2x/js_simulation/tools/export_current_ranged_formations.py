"""Export the two SHA-pinned current ranged golden formations.

This is deliberately separate from the melee formation exporter: ranged-vs-
melee also carries the nine-unit Player-4 diplomacy gate, which is part of the
scenario mechanics and must not be flattened into an ordinary two-army start.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import AoE2ScenarioParser
from AoE2ScenarioParser import settings
from AoE2ScenarioParser.datasets.conditions import ConditionId
from AoE2ScenarioParser.datasets.effects import EffectId
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


settings.PRINT_STATUS_UPDATES = False
ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "current_ranged_goldens_2026-08-29" / "source"
)
SOURCES = {
    "ranged_vs_ranged": (
        "rangedvsranged.aoe2scenario",
        "f44097ef86e6b123c6dfeb4989842e548af91f0d492e69caf6de87148f040883",
    ),
    "ranged_vs_melee": (
        "rangedvsmelee.aoe2scenario",
        "13c41485a00943ef525cab848d835d1379259fc8fff38b83d4ec510bc8824783",
    ),
    "melee_vs_ranged": (
        "meleevsranged.aoe2scenario",
        "faf8d616ac9bb4601c4582deccec0984e997617d8c121bc44d698c7963f038a8",
    ),
}
OUTPUT = ROOT / "fixtures" / "current_ranged_golden_formations.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unit_row(unit, player_id: int) -> dict:
    return {
        "reference_id": int(unit.reference_id),
        "player_id": player_id,
        "unit_const": int(unit.unit_const),
        "position": {
            "x": float(unit.x),
            "y": float(unit.y),
            "z": float(unit.z),
        },
        "rotation": float(unit.rotation),
    }


def extract_family(family: str, filename: str, expected_hash: str) -> dict:
    path = SOURCE_ROOT / filename
    actual_hash = sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"{family} source hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    scenario = AoE2DEScenario.from_file(str(path))
    sides = {
        str(owner): [unit_row(unit, owner) for unit in scenario.unit_manager.get_player_units(owner)]
        for owner in (2, 3, 4)
    }
    if len(sides["2"]) != 27 or len(sides["3"]) != 27:
        raise ValueError(f"{family} must expose exactly 27 ordered slots per testing side")

    player_ids = (2, 3, 4)
    player_metadata = {}
    initial_diplomacy = {}
    for owner in player_ids:
        player = scenario.player_manager.players[owner]
        player_metadata[str(owner)] = {
            "active": bool(player.active),
            "color": int(player.color),
            "civilization": player.civilization.name,
        }
        initial_diplomacy[str(owner)] = {
            str(target): int(player.diplomacy[target - 1])
            for target in player_ids
            if target != owner
        }

    triggers = []
    for trigger_index, trigger in enumerate(scenario.trigger_manager.triggers):
        if not bool(trigger.enabled):
            continue
        conditions = []
        for condition_index, condition in enumerate(trigger.conditions):
            condition_type = int(condition.condition_type)
            if condition_type != int(ConditionId.PLAYER_DEFEATED):
                raise ValueError(
                    f"{family} trigger {trigger_index} contains unsupported condition "
                    f"type {condition_type}"
                )
            conditions.append({
                "type": "player_defeated",
                "source_player": int(condition.source_player),
                "condition_index": condition_index,
            })
        effects = []
        for effect_index, effect in enumerate(trigger.effects):
            effect_type = int(effect.effect_type)
            if effect_type == int(EffectId.PATROL):
                effects.append({
                    "type": "patrol",
                    "owner": int(effect.source_player),
                    "x": int(effect.location_x),
                    "y": int(effect.location_y),
                    "area": {
                        "x1": int(effect.area_x1),
                        "y1": int(effect.area_y1),
                        "x2": int(effect.area_x2),
                        "y2": int(effect.area_y2),
                    },
                    "effect_index": effect_index,
                })
            elif effect_type == int(EffectId.CHANGE_DIPLOMACY):
                effects.append({
                    "type": "change_diplomacy",
                    "source_player": int(effect.source_player),
                    "target_player": int(effect.target_player),
                    "diplomacy": int(effect.diplomacy),
                    "mutual": bool(effect.mutual_diplomacy),
                    "effect_index": effect_index,
                })
            elif effect_index != 0 or conditions:
                raise ValueError(
                    f"{family} trigger {trigger_index} contains unsupported effect "
                    f"type {effect_type}"
                )
        triggers.append({
            "trigger_index": trigger_index,
            "name": trigger.name,
            "looping": bool(trigger.looping),
            "conditions": conditions,
            "effects": effects,
        })
    return {
        "source": {
            "filename": filename,
            "sha256": actual_hash,
            "scenario_version": float(scenario.scenario_version),
            "parser": "AoE2ScenarioParser",
            "parser_version": str(AoE2ScenarioParser.__version__),
            "selection_rule": "first_n_units_in_player_order",
        },
        "map": {
            "width": int(scenario.map_manager.map_width),
            "height": int(scenario.map_manager.map_height),
        },
        "players": player_metadata,
        "initial_diplomacy": initial_diplomacy,
        "sides": sides,
        "triggers": triggers,
    }


def main() -> None:
    payload = {
        "schema_version": 1,
        "families": {
            family: extract_family(family, filename, expected_hash)
            for family, (filename, expected_hash) in SOURCES.items()
        },
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
