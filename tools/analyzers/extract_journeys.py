#!/usr/bin/env python3
"""
AoE2 Unit Journey Extractor
Creates a CSV with one row per unit/building, showing their complete action history.

Each row contains:
- Player name
- Unit/building name (e.g., villager_ddk220_1, archer_TiShi_3)
- Unit type (villager, military, building)
- First seen timestamp
- Last seen timestamp
- Whether the unit likely died (military only, 5 min idle before game end)
- Complete action journey as a formatted string
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import mgz
import mgz.model

# Death threshold for military units (5 minutes)
DEATH_THRESHOLD_SECONDS = 5 * 60


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
        pass
    return {}


def format_timestamp(td):
    """Format timedelta as HH:MM:SS."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def extract_journeys(file_path, output_file):
    """Extract unit journeys from a replay file."""

    print(f"Processing: {file_path}")

    object_names = load_object_names()

    with open(file_path, "rb") as f:
        match = mgz.model.parse_match(f)

        match_duration = match.duration.total_seconds()

        # =====================================================================
        # Build unit owner map (unit instance ID -> owner player)
        # =====================================================================
        unit_owner_map = {}  # {instance_id: player_name}

        # Starting units belong to their player
        for player in match.players:
            if player.objects:
                for obj in player.objects:
                    unit_owner_map[obj.instance_id] = player.name

        # For other units, the owner is the player who first commands them
        for action in match.actions:
            if not action.player:
                continue
            payload = action.payload or {}
            if "object_ids" in payload:
                for obj_id in payload["object_ids"]:
                    if obj_id not in unit_owner_map:
                        unit_owner_map[obj_id] = action.player.name

        # =====================================================================
        # Collect all actions per unit instance ID
        # =====================================================================
        unit_actions = defaultdict(list)  # {instance_id: [action_data, ...]}

        # Track training events to determine unit types
        training_events = []

        for action in match.actions:
            if not action.player:
                continue

            action_type = str(action.type).replace("Action.", "")
            payload = action.payload or {}
            pos = action.position if hasattr(action, "position") else None

            # Track training events
            if action_type == "DE_QUEUE" and payload:
                unit_type_name = payload.get("unit", "unit")
                training_events.append(
                    {
                        "timestamp": action.timestamp.total_seconds(),
                        "player": action.player.name,
                        "unit_type": unit_type_name.lower().replace(" ", ""),
                    }
                )

            # Record actions for each unit involved
            if "object_ids" in payload:
                for obj_id in payload["object_ids"]:
                    unit_actions[obj_id].append(
                        {
                            "timestamp": action.timestamp,
                            "timestamp_seconds": action.timestamp.total_seconds(),
                            "type": action_type,
                            "payload": payload,
                            "position": pos,
                            "player_issuing": action.player.name,
                        }
                    )

        # =====================================================================
        # Build unit names and classify units
        # =====================================================================
        unit_name_map = {}  # {instance_id: "villager_ddk220_1"}
        unit_type_map = {}  # {instance_id: "villager" | "military" | "other"}
        unit_counters = defaultdict(lambda: defaultdict(int))

        # Name starting units
        for player in match.players:
            player_name = player.name
            if player.objects:
                for obj in player.objects:
                    unit_type = (
                        obj.name.lower().replace(" ", "") if obj.name else "unit"
                    )
                    unit_counters[player_name][unit_type] += 1
                    count = unit_counters[player_name][unit_type]
                    unit_name_map[obj.instance_id] = (
                        f"{unit_type}_{player_name}_{count}"
                    )

                    # Classify
                    if "villager" in unit_type.lower():
                        unit_type_map[obj.instance_id] = "villager"
                    elif "scout" in unit_type.lower():
                        unit_type_map[obj.instance_id] = "military"
                    else:
                        unit_type_map[obj.instance_id] = "other"

        # Name and classify units as they appear in actions
        for obj_id in unit_actions.keys():
            if obj_id in unit_name_map:
                continue

            owner = unit_owner_map.get(obj_id, "unknown")
            actions = unit_actions[obj_id]

            # Check if this unit does BUILD actions (villager)
            is_villager = any(a["type"] == "BUILD" for a in actions)

            if is_villager:
                unit_type = "villager"
                unit_type_map[obj_id] = "villager"
            else:
                # Try to match with a training event
                first_seen = actions[0]["timestamp_seconds"] if actions else None
                unit_type = "unit"

                if first_seen:
                    for te in reversed(training_events):
                        if te["player"] == owner and te["timestamp"] < first_seen:
                            unit_type = te["unit_type"]
                            break

                unit_type_map[obj_id] = "military"

            unit_counters[owner][unit_type] += 1
            count = unit_counters[owner][unit_type]
            unit_name_map[obj_id] = f"{unit_type}_{owner}_{count}"

        # =====================================================================
        # Track buildings separately
        # =====================================================================
        buildings = {}  # {(player, pos_key): {"name": ..., "type": ..., "built_at": ..., "actions": [...]}}
        building_counters = defaultdict(lambda: defaultdict(int))

        for action in match.actions:
            if not action.player:
                continue

            action_type = str(action.type).replace("Action.", "")
            payload = action.payload or {}
            pos = action.position if hasattr(action, "position") else None

            if action_type == "BUILD" and pos:
                player_name = action.player.name
                building_id = payload.get("building_id", payload.get("building", ""))
                building_type = object_names.get(
                    str(building_id), f"building{building_id}"
                )
                building_type_clean = building_type.lower().replace(" ", "")

                pos_key = f"{int(pos.x)}_{int(pos.y)}"
                key = (player_name, pos_key)

                if key not in buildings:
                    building_counters[player_name][building_type_clean] += 1
                    count = building_counters[player_name][building_type_clean]

                    buildings[key] = {
                        "name": f"{building_type_clean}_{player_name}_{count}",
                        "type": building_type_clean,
                        "owner": player_name,
                        "built_at": action.timestamp,
                        "built_at_seconds": action.timestamp.total_seconds(),
                        "position": (pos.x, pos.y),
                        "actions": [
                            {
                                "timestamp": action.timestamp,
                                "type": "BUILD_STARTED",
                                "position": (pos.x, pos.y),
                            }
                        ],
                    }

        # =====================================================================
        # Write journey CSV
        # =====================================================================
        print(f"Writing to: {output_file}")

        with open(output_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player",
                    "unit_name",
                    "unit_category",  # villager, military, building, other
                    "first_seen",
                    "first_seen_seconds",
                    "last_seen",
                    "last_seen_seconds",
                    "active_duration_seconds",
                    "total_actions",
                    "likely_died",
                    "estimated_death_time",
                    "journey",
                ]
            )

            # Group units by player
            player_units = defaultdict(
                list
            )  # {player: [(instance_id, name, category), ...]}

            for obj_id, name in unit_name_map.items():
                owner = unit_owner_map.get(obj_id, "unknown")
                category = unit_type_map.get(obj_id, "other")
                player_units[owner].append((obj_id, name, category))

            # Add buildings
            for key, building in buildings.items():
                player_units[building["owner"]].append(
                    (key, building["name"], "building")
                )

            # Process each player's units
            for player in match.players:
                player_name = player.name
                units = player_units.get(player_name, [])

                # Sort by first seen time
                def get_first_seen(item):
                    obj_id, name, category = item
                    if category == "building":
                        return buildings[obj_id]["built_at_seconds"]
                    else:
                        actions = unit_actions.get(obj_id, [])
                        return actions[0]["timestamp_seconds"] if actions else 0

                units.sort(key=get_first_seen)

                for obj_id, name, category in units:
                    if category == "building":
                        # Building journey
                        building = buildings[obj_id]
                        first_seen = building["built_at"]
                        first_seen_seconds = building["built_at_seconds"]
                        last_seen = first_seen
                        last_seen_seconds = first_seen_seconds

                        journey_parts = [
                            f"[{format_timestamp(first_seen)}] BUILD_STARTED at ({building['position'][0]:.1f}, {building['position'][1]:.1f})"
                        ]

                        writer.writerow(
                            [
                                player_name,
                                name,
                                "building",
                                format_timestamp(first_seen),
                                f"{first_seen_seconds:.1f}",
                                format_timestamp(last_seen),
                                f"{last_seen_seconds:.1f}",
                                "0",
                                "1",
                                "",  # Buildings don't die in this tracking
                                "",
                                " -> ".join(journey_parts),
                            ]
                        )
                    else:
                        # Unit journey
                        actions = unit_actions.get(obj_id, [])
                        if not actions:
                            continue

                        first_action = actions[0]
                        last_action = actions[-1]

                        first_seen = first_action["timestamp"]
                        first_seen_seconds = first_action["timestamp_seconds"]
                        last_seen = last_action["timestamp"]
                        last_seen_seconds = last_action["timestamp_seconds"]
                        active_duration = last_seen_seconds - first_seen_seconds

                        # Check if likely died (military only, 5 min idle before game end)
                        time_since_last = match_duration - last_seen_seconds
                        likely_died = (
                            category == "military"
                            and time_since_last > DEATH_THRESHOLD_SECONDS
                        )
                        estimated_death = ""
                        if likely_died:
                            death_seconds = last_seen_seconds + DEATH_THRESHOLD_SECONDS
                            death_td = last_action["timestamp"] + __import__(
                                "datetime"
                            ).timedelta(seconds=DEATH_THRESHOLD_SECONDS)
                            estimated_death = format_timestamp(death_td)

                        # Build journey string
                        journey_parts = []
                        prev_pos = None

                        for action in actions:
                            ts = format_timestamp(action["timestamp"])
                            action_type = action["type"]
                            pos = action["position"]
                            payload = action["payload"]

                            # Format action
                            if action_type == "MOVE":
                                if pos:
                                    journey_parts.append(
                                        f"[{ts}] MOVE to ({pos.x:.1f}, {pos.y:.1f})"
                                    )
                                else:
                                    journey_parts.append(f"[{ts}] MOVE")

                            elif action_type == "BUILD":
                                building_id = payload.get(
                                    "building_id", payload.get("building", "")
                                )
                                building_type = object_names.get(
                                    str(building_id), f"building{building_id}"
                                )
                                if pos:
                                    journey_parts.append(
                                        f"[{ts}] BUILD {building_type} at ({pos.x:.1f}, {pos.y:.1f})"
                                    )
                                else:
                                    journey_parts.append(
                                        f"[{ts}] BUILD {building_type}"
                                    )

                            elif action_type == "ORDER":
                                target_id = payload.get("target_id", "")
                                if pos:
                                    journey_parts.append(
                                        f"[{ts}] ORDER at ({pos.x:.1f}, {pos.y:.1f})"
                                    )
                                elif target_id:
                                    target_name = unit_name_map.get(
                                        target_id, f"target_{target_id}"
                                    )
                                    journey_parts.append(
                                        f"[{ts}] ORDER target={target_name}"
                                    )
                                else:
                                    journey_parts.append(f"[{ts}] ORDER")

                            elif action_type == "PATROL":
                                if pos:
                                    journey_parts.append(
                                        f"[{ts}] PATROL to ({pos.x:.1f}, {pos.y:.1f})"
                                    )
                                else:
                                    journey_parts.append(f"[{ts}] PATROL")

                            elif action_type == "STANCE":
                                stance = payload.get("stance", "")
                                stance_names = {
                                    0: "aggressive",
                                    1: "defensive",
                                    2: "standground",
                                    3: "noattack",
                                }
                                stance_name = stance_names.get(stance, str(stance))
                                journey_parts.append(f"[{ts}] STANCE {stance_name}")

                            elif action_type == "FORMATION":
                                formation = payload.get("formation", "")
                                formation_names = {
                                    0: "line",
                                    1: "staggered",
                                    2: "box",
                                    3: "flank",
                                }
                                formation_name = formation_names.get(
                                    formation, str(formation)
                                )
                                journey_parts.append(
                                    f"[{ts}] FORMATION {formation_name}"
                                )

                            elif action_type == "STOP":
                                journey_parts.append(f"[{ts}] STOP")

                            elif action_type == "GARRISON":
                                journey_parts.append(f"[{ts}] GARRISON")

                            elif action_type == "UNGARRISON":
                                journey_parts.append(f"[{ts}] UNGARRISON")

                            elif action_type == "DELETE":
                                journey_parts.append(f"[{ts}] DELETED")

                            elif action_type == "GATHER":
                                if pos:
                                    journey_parts.append(
                                        f"[{ts}] GATHER at ({pos.x:.1f}, {pos.y:.1f})"
                                    )
                                else:
                                    journey_parts.append(f"[{ts}] GATHER")

                            else:
                                # Generic action
                                if pos:
                                    journey_parts.append(
                                        f"[{ts}] {action_type} at ({pos.x:.1f}, {pos.y:.1f})"
                                    )
                                else:
                                    journey_parts.append(f"[{ts}] {action_type}")

                        # Add death marker if applicable
                        if likely_died:
                            journey_parts.append(
                                f"[{estimated_death}] LIKELY_DIED (5 min idle)"
                            )

                        writer.writerow(
                            [
                                player_name,
                                name,
                                category,
                                format_timestamp(first_seen),
                                f"{first_seen_seconds:.1f}",
                                format_timestamp(last_seen),
                                f"{last_seen_seconds:.1f}",
                                f"{active_duration:.1f}",
                                len(actions),
                                "yes" if likely_died else "no",
                                estimated_death,
                                " -> ".join(journey_parts),
                            ]
                        )

        # Count summary
        total_units = sum(1 for obj_id in unit_name_map if unit_actions.get(obj_id))
        total_buildings = len(buildings)

        print(f"\nJourney extraction complete!")
        print(f"  Total units tracked: {total_units}")
        print(f"  Total buildings tracked: {total_buildings}")
        print(f"  Output: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract unit journeys from an AoE2 replay to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output format:
  Each row represents one unit or building with its complete action history.
  Units are grouped by player and sorted by first seen time.

  The journey column contains a timeline like:
    [0:15] MOVE to (150.0, 75.0) -> [0:30] BUILD House at (145.0, 80.0) -> ...

Examples:
  python extract_journeys.py game.aoe2record
  python extract_journeys.py game.aoe2record --output journeys.csv
        """,
    )

    parser.add_argument("file", help="Path to .aoe2record file")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output CSV file (default: <filename>_journeys.csv)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: File does not exist: {args.file}")
        sys.exit(1)

    # Default output file
    if args.output is None:
        base_name = os.path.splitext(os.path.basename(args.file))[0]
        args.output = os.path.join(
            os.path.dirname(args.file), f"{base_name}_journeys.csv"
        )

    extract_journeys(args.file, args.output)


if __name__ == "__main__":
    main()
