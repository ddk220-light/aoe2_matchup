#!/usr/bin/env python3
"""
Generate JSON data for the AoE2 Replay Visualizer.
Exports match info, players, actions, and starting units.
"""

import json
import os
import sys
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mgz
import mgz.model

# AoE2 standard player colors
PLAYER_COLORS = {
    0: {"name": "Blue", "hex": "#0042FF"},
    1: {"name": "Red", "hex": "#FF0000"},
    2: {"name": "Green", "hex": "#00FF00"},
    3: {"name": "Yellow", "hex": "#FFFF00"},
    4: {"name": "Cyan", "hex": "#00FFFF"},
    5: {"name": "Purple", "hex": "#FF00FF"},
    6: {"name": "Grey", "hex": "#808080"},
    7: {"name": "Orange", "hex": "#FFA500"},
}

# Death threshold (5 minutes)
DEATH_THRESHOLD = 5 * 60


def load_object_names():
    """Load object ID to name mappings."""
    try:
        import aocref

        aocref_path = os.path.dirname(aocref.__file__)
        dataset_file = os.path.join(aocref_path, "data", "datasets", "100.json")
        with open(dataset_file, "r") as f:
            data = json.load(f)
            return data.get("objects", {})
    except:
        return {}


def generate_data(replay_file, output_file):
    """Generate JSON data from replay file."""

    print(f"Processing: {replay_file}")

    object_names = load_object_names()

    with open(replay_file, "rb") as f:
        match = mgz.model.parse_match(f)

        match_duration = match.duration.total_seconds()

        # Build unit owner map
        unit_owner_map = {}
        for player in match.players:
            if player.objects:
                for obj in player.objects:
                    unit_owner_map[obj.instance_id] = player.name

        for action in match.actions:
            if not action.player:
                continue
            payload = action.payload or {}
            if "object_ids" in payload:
                for obj_id in payload["object_ids"]:
                    if obj_id not in unit_owner_map:
                        unit_owner_map[obj_id] = action.player.name

        # Track actions per unit for villager detection and death detection
        unit_actions = defaultdict(list)
        for action in match.actions:
            if not action.player:
                continue
            payload = action.payload or {}
            if "object_ids" in payload:
                for obj_id in payload["object_ids"]:
                    unit_actions[obj_id].append(
                        {
                            "time": action.timestamp.total_seconds(),
                            "type": str(action.type).replace("Action.", ""),
                        }
                    )

        # Determine villagers (units that BUILD)
        villager_ids = set()
        for obj_id, actions in unit_actions.items():
            if any(a["type"] == "BUILD" for a in actions):
                villager_ids.add(obj_id)

        # Build unit names
        unit_name_map = {}
        unit_counters = defaultdict(lambda: defaultdict(int))

        # Training events for unit type detection
        training_events = []
        for action in match.actions:
            if not action.player:
                continue
            action_type = str(action.type).replace("Action.", "")
            if action_type == "DE_QUEUE" and action.payload:
                unit_type_name = action.payload.get("unit", "unit")
                training_events.append(
                    {
                        "time": action.timestamp.total_seconds(),
                        "player": action.player.name,
                        "unit_type": unit_type_name.lower().replace(" ", ""),
                    }
                )

        # Name starting units
        for player in match.players:
            if player.objects:
                for obj in player.objects:
                    unit_type = (
                        obj.name.lower().replace(" ", "") if obj.name else "unit"
                    )
                    unit_counters[player.name][unit_type] += 1
                    count = unit_counters[player.name][unit_type]
                    unit_name_map[obj.instance_id] = (
                        f"{unit_type}_{player.name}_{count}"
                    )

        # Build data structure
        data = {
            "match": {
                "map_name": match.map.name
                if hasattr(match.map, "name")
                else str(match.map),
                "map_size": 220,  # Large map
                "duration_seconds": match_duration,
                "duration_formatted": str(match.duration).split(".")[0],
            },
            "players": [],
            "starting_units": [],
            "actions": [],
            "unit_deaths": {},  # unit_name -> death_time
        }

        # Add players
        for player in match.players:
            color = PLAYER_COLORS.get(
                player.color_id, {"name": "Unknown", "hex": "#FFFFFF"}
            )
            data["players"].append(
                {
                    "name": player.name,
                    "color_id": player.color_id,
                    "color_hex": color["hex"],
                    "color_name": color["name"],
                    "civilization": player.civilization
                    if hasattr(player, "civilization")
                    else "",
                }
            )

        # Add starting units with positions
        for player in match.players:
            if player.objects:
                for obj in player.objects:
                    unit_name = unit_name_map.get(
                        obj.instance_id, f"unit_{obj.instance_id}"
                    )
                    unit_type = (
                        obj.name.lower().replace(" ", "") if obj.name else "unit"
                    )

                    # Get starting position from first action
                    start_x, start_y = None, None
                    for action in match.actions:
                        if not action.player:
                            continue
                        payload = action.payload or {}
                        if obj.instance_id in payload.get("object_ids", []):
                            if hasattr(action, "position") and action.position:
                                start_x = action.position.x
                                start_y = action.position.y
                                break

                    data["starting_units"].append(
                        {
                            "id": unit_name,
                            "instance_id": obj.instance_id,
                            "player": player.name,
                            "type": "villager"
                            if "villager" in unit_type
                            else "military",
                            "x": start_x,
                            "y": start_y,
                        }
                    )

        # Process actions
        action_id = 0
        for action in match.actions:
            if not action.player:
                continue

            action_id += 1
            action_type = str(action.type).replace("Action.", "")
            payload = action.payload or {}
            pos = action.position if hasattr(action, "position") else None

            # Get unit names for subjects
            unit_ids = payload.get("object_ids", [])
            subject_names = []

            for obj_id in unit_ids:
                if obj_id not in unit_name_map:
                    owner = unit_owner_map.get(obj_id, action.player.name)

                    # Determine unit type
                    if obj_id in villager_ids:
                        unit_type = "villager"
                    else:
                        # Try to match with training event
                        first_seen = None
                        for a in unit_actions.get(obj_id, []):
                            first_seen = a["time"]
                            break

                        unit_type = "unit"
                        if first_seen:
                            for te in reversed(training_events):
                                if te["player"] == owner and te["time"] < first_seen:
                                    unit_type = te["unit_type"]
                                    break

                    unit_counters[owner][unit_type] += 1
                    count = unit_counters[owner][unit_type]
                    unit_name_map[obj_id] = f"{unit_type}_{owner}_{count}"

                subject_names.append(unit_name_map[obj_id])

            # Build target name
            target_name = ""
            if action_type == "BUILD":
                building_id = payload.get("building_id", payload.get("building", ""))
                building_type = object_names.get(
                    str(building_id), f"building{building_id}"
                )
                target_name = building_type.lower().replace(" ", "")
            elif action_type == "DE_QUEUE":
                unit_type = payload.get("unit", "unit")
                target_name = unit_type.lower().replace(" ", "")
            elif action_type == "RESEARCH":
                tech = payload.get("technology", payload.get("tech_id", ""))
                target_name = str(tech).lower().replace(" ", "")

            # Add action
            data["actions"].append(
                {
                    "id": action_id,
                    "time": action.timestamp.total_seconds(),
                    "player": action.player.name,
                    "type": action_type,
                    "subjects": subject_names,
                    "target": target_name,
                    "x": pos.x if pos else None,
                    "y": pos.y if pos else None,
                    "amount": payload.get("amount"),
                }
            )

        # Calculate unit deaths (military units idle for 5+ min before game end)
        for obj_id, actions in unit_actions.items():
            if not actions:
                continue

            unit_name = unit_name_map.get(obj_id)
            if not unit_name:
                continue

            # Skip villagers and starting units
            if obj_id in villager_ids:
                continue
            if any(
                obj_id == su["instance_id"]
                for su in data["starting_units"]
                if "villager" in su["type"]
            ):
                continue

            last_time = actions[-1]["time"]
            if match_duration - last_time > DEATH_THRESHOLD:
                death_time = last_time + DEATH_THRESHOLD
                data["unit_deaths"][unit_name] = death_time

        # Write JSON
        print(f"Writing: {output_file}")
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"  Match duration: {data['match']['duration_formatted']}")
        print(f"  Players: {len(data['players'])}")
        print(f"  Starting units: {len(data['starting_units'])}")
        print(f"  Actions: {len(data['actions'])}")
        print(f"  Unit deaths tracked: {len(data['unit_deaths'])}")
        print("Done!")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)

    replay_file = os.path.join(parent_dir, "AgeIIDE_Replay_ddk_wu.aoe2record")
    output_file = os.path.join(script_dir, "replay_data.json")

    if not os.path.exists(replay_file):
        print(f"ERROR: Replay file not found: {replay_file}")
        sys.exit(1)

    generate_data(replay_file, output_file)


if __name__ == "__main__":
    main()
