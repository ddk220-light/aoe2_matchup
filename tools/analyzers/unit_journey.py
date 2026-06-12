#!/usr/bin/env python3
"""
AoE2 Unit Journey Analyzer
Tracks the complete journey of specific units throughout a game,
narrating their actions like a story.
"""

import argparse
import json
import os
import sys
from datetime import timedelta

import mgz
import mgz.model


# Load object reference data for building/resource names
def load_object_names():
    """Load object ID to name mappings."""
    cache_file = os.path.join(os.path.dirname(__file__), ".unit_data_cache.json")

    # Try to load from aocref
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


def get_action_description(action, object_names, all_unit_actions):
    """Convert an action into a human-readable description."""

    action_type = str(action["type"]).replace("Action.", "")
    payload = action.get("payload", {})
    position = action.get("position")

    descriptions = {
        "MOVE": lambda: describe_move(position),
        "BUILD": lambda: describe_build(payload, position, object_names),
        "ORDER": lambda: describe_order(payload, object_names),
        "GATHER_POINT": lambda: describe_gather_point(payload, position, object_names),
        "RESEARCH": lambda: describe_research(payload),
        "DE_QUEUE": lambda: describe_queue(payload),
        "ATTACK": lambda: describe_attack(payload, position),
        "STANCE": lambda: describe_stance(payload),
        "FORMATION": lambda: describe_formation(payload),
        "PATROL": lambda: describe_patrol(position),
        "DELETE": lambda: "Was deleted by the player",
        "UNGARRISON": lambda: "Exited from a building/transport",
        "SPECIAL": lambda: describe_special(payload),
        "WALL": lambda: describe_wall(position),
        "SELL": lambda: describe_market(payload, "sell"),
        "BUY": lambda: describe_market(payload, "buy"),
        "FLARE": lambda: f"Sent a flare signal at ({position.x:.0f}, {position.y:.0f})"
        if position
        else "Sent a flare signal",
        "DE_TRANSFORM": lambda: "Transformed/packed up",
    }

    if action_type in descriptions:
        return descriptions[action_type]()

    return f"Performed {action_type} action"


def describe_move(position):
    """Describe a move action."""
    if position:
        return f"Moved to position ({position.x:.0f}, {position.y:.0f})"
    return "Moved to a new position"


def describe_build(payload, position, object_names):
    """Describe a build action."""
    building_id = payload.get("building_id", payload.get("building", "unknown"))
    building_name = object_names.get(str(building_id), f"building #{building_id}")

    if position:
        return f"Started constructing a {building_name} at ({position.x:.0f}, {position.y:.0f})"
    return f"Started constructing a {building_name}"


def describe_order(payload, object_names):
    """Describe an order action (usually tasking to a resource or building)."""
    target_id = payload.get("target_id")

    if target_id:
        # Common resource/building IDs
        # In AoE2, resources have specific object types
        return f"Was tasked to target #{target_id}"

    return "Received a task order"


def describe_gather_point(payload, position, object_names):
    """Describe setting a gather point."""
    target_id = payload.get("target_id")
    if target_id:
        return f"Set gather point to target #{target_id}"
    if position:
        return f"Set gather point to ({position.x:.0f}, {position.y:.0f})"
    return "Set a gather point"


def describe_research(payload):
    """Describe a research action."""
    tech = payload.get("technology", payload.get("tech_id", "unknown technology"))
    return f"Started researching {tech}"


def describe_queue(payload):
    """Describe a queue action."""
    unit = payload.get("unit", "unit")
    amount = payload.get("amount", 1)
    return f"Queued {amount}x {unit} for training"


def describe_attack(payload, position):
    """Describe an attack action."""
    target_id = payload.get("target_id")
    if target_id:
        return f"Attacked target #{target_id}"
    if position:
        return f"Attack-moved to ({position.x:.0f}, {position.y:.0f})"
    return "Engaged in combat"


def describe_stance(payload):
    """Describe a stance change."""
    stance_names = {0: "Aggressive", 1: "Defensive", 2: "Stand Ground", 3: "No Attack"}
    stance = payload.get("stance", 0)
    return f"Changed stance to {stance_names.get(stance, f'stance {stance}')}"


def describe_formation(payload):
    """Describe a formation change."""
    formation_names = {0: "Line", 1: "Staggered", 2: "Box", 3: "Flank"}
    formation = payload.get("formation", 0)
    return f"Changed formation to {formation_names.get(formation, f'formation {formation}')}"


def describe_patrol(position):
    """Describe a patrol action."""
    if position:
        return f"Started patrolling towards ({position.x:.0f}, {position.y:.0f})"
    return "Started patrolling"


def describe_special(payload):
    """Describe a special action."""
    return "Performed a special action (ability/auto-task)"


def describe_wall(position):
    """Describe wall building."""
    if position:
        return f"Built wall segment at ({position.x:.0f}, {position.y:.0f})"
    return "Built a wall segment"


def describe_market(payload, action_type):
    """Describe market transactions."""
    resource = payload.get("resource", "resource")
    amount = payload.get("amount", 100)
    return f"{'Sold' if action_type == 'sell' else 'Bought'} {amount} {resource} at the market"


def simplify_journey(actions):
    """Simplify a sequence of actions by consolidating repeated moves."""
    simplified = []
    consecutive_moves = []

    for action in actions:
        action_type = str(action["type"]).replace("Action.", "")

        if action_type == "MOVE":
            consecutive_moves.append(action)
        else:
            # Flush consecutive moves
            if consecutive_moves:
                if len(consecutive_moves) == 1:
                    simplified.append(consecutive_moves[0])
                else:
                    # Summarize multiple moves
                    first_pos = consecutive_moves[0].get("position")
                    last_pos = consecutive_moves[-1].get("position")
                    first_time = consecutive_moves[0]["timestamp"]
                    last_time = consecutive_moves[-1]["timestamp"]

                    summary_action = {
                        "timestamp": first_time,
                        "type": "MOVE_SEQUENCE",
                        "move_count": len(consecutive_moves),
                        "start_pos": first_pos,
                        "end_pos": last_pos,
                        "duration": last_time - first_time,
                        "payload": {},
                    }
                    simplified.append(summary_action)
                consecutive_moves = []

            simplified.append(action)

    # Don't forget trailing moves
    if consecutive_moves:
        if len(consecutive_moves) == 1:
            simplified.append(consecutive_moves[0])
        else:
            first_pos = consecutive_moves[0].get("position")
            last_pos = consecutive_moves[-1].get("position")
            first_time = consecutive_moves[0]["timestamp"]
            last_time = consecutive_moves[-1]["timestamp"]

            summary_action = {
                "timestamp": first_time,
                "type": "MOVE_SEQUENCE",
                "move_count": len(consecutive_moves),
                "start_pos": first_pos,
                "end_pos": last_pos,
                "duration": last_time - first_time,
                "payload": {},
            }
            simplified.append(summary_action)

    return simplified


def format_move_sequence(action):
    """Format a consolidated move sequence."""
    count = action["move_count"]
    start = action.get("start_pos")
    end = action.get("end_pos")
    duration = action.get("duration", timedelta(0))

    if start and end:
        # Calculate approximate distance
        dx = end.x - start.x
        dy = end.y - start.y
        distance = (dx**2 + dy**2) ** 0.5

        return (
            f"Traveled from ({start.x:.0f}, {start.y:.0f}) to ({end.x:.0f}, {end.y:.0f}) "
            f"({count} move commands, ~{distance:.0f} tiles, over {duration})"
        )

    return f"Made {count} movement commands over {duration}"


def analyze_unit_journeys(file_path, player_name, unit_count=5):
    """Analyze and narrate the journey of units created by a player."""

    print("=" * 90)
    print("AoE2 UNIT JOURNEY ANALYZER")
    print("=" * 90)
    print(f"\nFile: {file_path}")
    print(f"Player: {player_name}")
    print(f"Units to track: {unit_count}")
    print()

    # Load object names
    object_names = load_object_names()

    try:
        with open(file_path, "rb") as f:
            match = mgz.model.parse_match(f)

            # Find target player
            target_player = None
            for p in match.players:
                if player_name.lower() in p.name.lower():
                    target_player = p
                    break

            if not target_player:
                print(f"ERROR: Player '{player_name}' not found.")
                return

            print(f"Found player: {target_player.name}")

            # Get starting unit IDs
            starting_ids = {obj.instance_id for obj in target_player.objects}
            print(f"Starting units: {len(starting_ids)} (IDs: {sorted(starting_ids)})")

            # Collect all actions by unit ID
            unit_actions = {}

            for action in match.actions:
                if action.player and action.player.name == target_player.name:
                    if action.payload and "object_ids" in action.payload:
                        for obj_id in action.payload["object_ids"]:
                            if obj_id not in unit_actions:
                                unit_actions[obj_id] = []
                            unit_actions[obj_id].append(
                                {
                                    "timestamp": action.timestamp,
                                    "type": str(action.type),
                                    "payload": action.payload,
                                    "position": action.position
                                    if hasattr(action, "position")
                                    else None,
                                }
                            )

            # Find the first villagers queued
            queue_times = []
            for action in match.actions:
                if action.player and action.player.name == target_player.name:
                    if "QUEUE" in str(action.type) and action.payload:
                        if action.payload.get("unit") == "Villager":
                            queue_times.append(action.timestamp)
                            if len(queue_times) >= 10:
                                break

            if queue_times:
                first_queue_time = queue_times[0].total_seconds()
                print(f"First villager queued at: {queue_times[0]}")
            else:
                first_queue_time = 0

            # Find newly created villagers (must have BUILD actions - confirmed villagers)
            new_units = []

            for obj_id, actions in unit_actions.items():
                if obj_id in starting_ids:
                    continue

                # Check for BUILD actions - this confirms it's a villager
                has_build = any("BUILD" in a["type"] for a in actions)

                # Only track confirmed villagers (those with build commands)
                if has_build:
                    build_count = sum(1 for a in actions if "BUILD" in a["type"])
                    new_units.append(
                        {
                            "id": obj_id,
                            "first_seen": actions[0]["timestamp"],
                            "actions": actions,
                            "has_build": has_build,
                            "action_count": len(actions),
                            "build_count": build_count,
                        }
                    )

            # Sort by first appearance and take the first N
            new_units.sort(key=lambda x: x["first_seen"])
            units_to_track = new_units[:unit_count]

            if not units_to_track:
                print("\nNo newly created units found to track.")
                return

            print(
                f"\nTracking {len(units_to_track)} confirmed villagers (units with BUILD actions):"
            )
            for u in units_to_track:
                print(
                    f"  - Villager #{u['id']}: First seen at {u['first_seen']}, "
                    f"{u['action_count']} actions, {u['build_count']} buildings constructed"
                )

            # Narrate each unit's journey
            for i, unit_info in enumerate(units_to_track, 1):
                print("\n" + "=" * 90)
                print(f"THE STORY OF VILLAGER #{i}")
                print(f"(Unit ID: {unit_info['id']})")
                print("=" * 90)

                # Simplify the journey
                simplified_actions = simplify_journey(unit_info["actions"])

                # Calculate stats
                total_moves = sum(
                    1 for a in unit_info["actions"] if "MOVE" in str(a["type"])
                )
                total_builds = sum(
                    1 for a in unit_info["actions"] if "BUILD" in str(a["type"])
                )
                total_orders = sum(
                    1 for a in unit_info["actions"] if "ORDER" in str(a["type"])
                )
                first_action_time = unit_info["actions"][0]["timestamp"]
                last_action_time = unit_info["actions"][-1]["timestamp"]
                active_duration = last_action_time - first_action_time

                # Get buildings constructed
                buildings_built = []
                for a in unit_info["actions"]:
                    if "BUILD" in str(a["type"]):
                        building_id = a["payload"].get(
                            "building_id", a["payload"].get("building", "unknown")
                        )
                        building_name = object_names.get(
                            str(building_id), f"Building #{building_id}"
                        )
                        buildings_built.append(building_name)

                print(f"\nBorn: {first_action_time}")
                print(f"Last seen: {last_action_time}")
                print(f"Career span: {active_duration}")
                print(
                    f"Buildings constructed: {', '.join(buildings_built) if buildings_built else 'None'}"
                )
                print()
                print("-" * 90)
                print("TIMELINE")
                print("-" * 90)

                for action in simplified_actions:
                    timestamp = action["timestamp"]
                    action_type = str(action["type"]).replace("Action.", "")

                    if action_type == "MOVE_SEQUENCE":
                        description = format_move_sequence(action)
                    else:
                        description = get_action_description(
                            action, object_names, unit_actions
                        )

                    print(f"\n[{timestamp}]")
                    print(f"  {description}")

                print()
                print("-" * 90)
                print("CAREER STATISTICS")
                print("-" * 90)
                print(f"  Total move commands:  {total_moves}")
                print(f"  Buildings constructed: {total_builds}")
                print(f"  Resource/task orders: {total_orders}")

            print("\n" + "=" * 90)
            print("END OF UNIT JOURNEYS")
            print("=" * 90)

    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Track the journey of units created by a player in an AoE2 replay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python unit_journey.py game.aoe2record --player "ddk220"
  python unit_journey.py game.aoe2record --player "ddk" --units 10
        """,
    )

    parser.add_argument("file", help="Path to .aoe2record file")
    parser.add_argument(
        "--player", "-p", required=True, help="Player name (or partial match)"
    )
    parser.add_argument(
        "--units",
        "-u",
        type=int,
        default=5,
        help="Number of units to track (default: 5)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: File does not exist: {args.file}")
        sys.exit(1)

    analyze_unit_journeys(args.file, args.player, args.units)


if __name__ == "__main__":
    main()
