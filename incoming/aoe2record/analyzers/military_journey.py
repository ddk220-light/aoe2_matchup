#!/usr/bin/env python3
"""
AoE2 Military Unit Journey Analyzer
Tracks the complete journey of military units throughout a game,
narrating their actions like a story and detecting likely deaths.
"""

import argparse
import json
import os
import sys
from datetime import timedelta

import mgz
import mgz.model

# Time threshold for assuming unit death (5 minutes of inactivity)
DEATH_THRESHOLD_SECONDS = 5 * 60  # 5 minutes


def load_unit_data():
    """Load unit stats data from cache."""
    cache_file = os.path.join(os.path.dirname(__file__), ".unit_data_cache.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
                return cache.get("units", {})
        except (json.JSONDecodeError, IOError):
            pass

    return {}


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


def get_action_description(action, object_names):
    """Convert an action into a human-readable description."""

    action_type = str(action["type"]).replace("Action.", "")
    payload = action.get("payload", {})
    position = action.get("position")

    if action_type == "MOVE":
        if position:
            return f"Moved to position ({position.x:.0f}, {position.y:.0f})"
        return "Moved to a new position"

    elif action_type == "MOVE_SEQUENCE":
        return format_move_sequence(action)

    elif action_type == "ORDER":
        target_id = payload.get("target_id")
        if target_id:
            return f"Ordered to engage/interact with target #{target_id}"
        return "Received an order"

    elif action_type == "PATROL":
        if position:
            return f"Started patrolling towards ({position.x:.0f}, {position.y:.0f})"
        return "Started patrolling"

    elif action_type == "STANCE":
        stance_names = {
            0: "Aggressive",
            1: "Defensive",
            2: "Stand Ground",
            3: "No Attack",
        }
        stance = payload.get("stance", 0)
        return f"Changed stance to {stance_names.get(stance, f'stance {stance}')}"

    elif action_type == "FORMATION":
        formation_names = {0: "Line", 1: "Staggered", 2: "Box", 3: "Flank"}
        formation = payload.get("formation", 0)
        return f"Changed formation to {formation_names.get(formation, f'formation {formation}')}"

    elif action_type == "ATTACK":
        target_id = payload.get("target_id")
        if target_id:
            return f"Attacked target #{target_id}"
        if position:
            return f"Attack-moved to ({position.x:.0f}, {position.y:.0f})"
        return "Engaged in combat"

    elif action_type == "DELETE":
        return "Was deleted by the player"

    elif action_type == "UNGARRISON":
        return "Exited from a building/transport"

    elif action_type == "SPECIAL":
        return "Used special ability"

    elif action_type == "FLARE":
        return "Flare signal sent"

    return f"Performed {action_type} action"


def format_move_sequence(action):
    """Format a consolidated move sequence."""
    count = action["move_count"]
    start = action.get("start_pos")
    end = action.get("end_pos")
    duration = action.get("duration", timedelta(0))

    if start and end:
        dx = end.x - start.x
        dy = end.y - start.y
        distance = (dx**2 + dy**2) ** 0.5

        return (
            f"Marched from ({start.x:.0f}, {start.y:.0f}) to ({end.x:.0f}, {end.y:.0f}) "
            f"(~{distance:.0f} tiles over {duration})"
        )

    return f"Made {count} movement commands over {duration}"


def simplify_journey(actions):
    """Simplify a sequence of actions by consolidating repeated moves."""
    simplified = []
    consecutive_moves = []

    for action in actions:
        action_type = str(action["type"]).replace("Action.", "")

        if action_type == "MOVE":
            consecutive_moves.append(action)
        else:
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
                consecutive_moves = []

            simplified.append(action)

    # Handle trailing moves
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


def determine_unit_fate(last_action_time, match_duration, game_end_time):
    """Determine if a unit likely died or survived."""

    last_ts = last_action_time.total_seconds()
    end_ts = game_end_time.total_seconds()

    time_since_last_action = end_ts - last_ts

    if time_since_last_action > DEATH_THRESHOLD_SECONDS:
        return "LIKELY DIED", last_action_time + timedelta(
            seconds=DEATH_THRESHOLD_SECONDS
        )
    else:
        return "SURVIVED", None


def guess_unit_type(unit_id, first_seen_time, military_queue_times):
    """Try to guess what type of unit this is based on training times."""

    first_ts = first_seen_time.total_seconds()

    # Find the most recent queue that could have produced this unit
    best_match = None
    best_diff = float("inf")

    for queue_info in military_queue_times:
        queue_ts = queue_info["timestamp"].total_seconds()
        train_time = queue_info.get("train_time", 35)  # Default archer train time

        # Unit would appear after queue_ts + train_time
        expected_appear = queue_ts + train_time

        # Allow some tolerance (unit could be commanded shortly after spawning)
        diff = first_ts - expected_appear

        if -10 <= diff <= 60:  # Within reasonable window
            if abs(diff) < best_diff:
                best_diff = abs(diff)
                best_match = queue_info

    if best_match:
        return best_match["unit_name"], best_match["unit_id"]

    return "Unknown Unit", None


def analyze_military_journeys(file_path, player_name, unit_count=5):
    """Analyze and narrate the journey of military units."""

    print("=" * 90)
    print("AoE2 MILITARY UNIT JOURNEY ANALYZER")
    print("=" * 90)
    print(f"\nFile: {file_path}")
    print(f"Player: {player_name}")
    print(f"Units to track: {unit_count}")
    print(f"Death threshold: {DEATH_THRESHOLD_SECONDS // 60} minutes of inactivity")
    print()

    # Load data
    unit_data = load_unit_data()
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
            print(f"Match duration: {match.duration}")

            starting_ids = {obj.instance_id for obj in target_player.objects}

            # Collect military unit training queue
            military_queue = []
            train_times = {
                4: 35,  # Archer
                93: 22,  # Spearman
                440: 25,  # Petard
                280: 46,  # Mangonel
                1968: 17,  # Fire Archer
            }

            for action in match.actions:
                if action.player and action.player.name == target_player.name:
                    if "QUEUE" in str(action.type) and action.payload:
                        unit_name = action.payload.get("unit", "")
                        unit_type_id = action.payload.get("unit_id")

                        if "Villager" not in unit_name and unit_name:
                            military_queue.append(
                                {
                                    "timestamp": action.timestamp,
                                    "unit_name": unit_name,
                                    "unit_id": unit_type_id,
                                    "train_time": train_times.get(unit_type_id, 35),
                                }
                            )

            print(f"Military units queued: {len(military_queue)}")

            # Get first military queue time
            if military_queue:
                first_military_time = military_queue[0]["timestamp"].total_seconds()
            else:
                print("No military units found.")
                return

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

            # Find military units
            military_units = []

            for obj_id, actions in unit_actions.items():
                if obj_id in starting_ids:
                    continue

                first_ts = actions[0]["timestamp"].total_seconds()

                # Must appear after first military training + some train time
                if first_ts < first_military_time + 20:
                    continue

                # Military units don't BUILD
                has_build = any("BUILD" in a["type"] for a in actions)
                if has_build:
                    continue

                # Need some activity
                move_count = sum(1 for a in actions if "MOVE" in a["type"])
                has_patrol = any("PATROL" in a["type"] for a in actions)
                has_stance = any("STANCE" in a["type"] for a in actions)
                has_formation = any("FORMATION" in a["type"] for a in actions)
                order_count = sum(1 for a in actions if "ORDER" in a["type"])

                # Filter for military-like behavior
                if (
                    move_count >= 2
                    or has_patrol
                    or has_stance
                    or has_formation
                    or order_count >= 1
                ):
                    # Guess unit type
                    unit_type_name, unit_type_id = guess_unit_type(
                        obj_id, actions[0]["timestamp"], military_queue
                    )

                    military_units.append(
                        {
                            "id": obj_id,
                            "first_seen": actions[0]["timestamp"],
                            "last_seen": actions[-1]["timestamp"],
                            "actions": actions,
                            "action_count": len(actions),
                            "move_count": move_count,
                            "order_count": order_count,
                            "has_patrol": has_patrol,
                            "has_stance": has_stance,
                            "unit_type_name": unit_type_name,
                            "unit_type_id": unit_type_id,
                        }
                    )

            # Sort by first appearance
            military_units.sort(key=lambda x: x["first_seen"])
            units_to_track = military_units[:unit_count]

            if not units_to_track:
                print("\nNo military units found to track.")
                return

            print(f"\nTracking {len(units_to_track)} military units:")
            for u in units_to_track:
                fate, death_time = determine_unit_fate(
                    u["last_seen"], match.duration, match.duration
                )
                fate_str = f" [{fate}]" if fate == "LIKELY DIED" else " [SURVIVED]"
                print(
                    f"  - {u['unit_type_name']} #{u['id']}: First seen {u['first_seen']}, "
                    f"{u['action_count']} actions{fate_str}"
                )

            # Narrate each unit's journey
            for i, unit_info in enumerate(units_to_track, 1):
                print("\n" + "=" * 90)
                print(f"THE STORY OF {unit_info['unit_type_name'].upper()} #{i}")
                print(f"(Unit ID: {unit_info['id']})")
                print("=" * 90)

                # Calculate stats
                first_action_time = unit_info["actions"][0]["timestamp"]
                last_action_time = unit_info["actions"][-1]["timestamp"]
                active_duration = last_action_time - first_action_time

                # Determine fate
                fate, estimated_death_time = determine_unit_fate(
                    last_action_time, match.duration, match.duration
                )

                # Get unit stats if available
                unit_stats = None
                if (
                    unit_info["unit_type_id"]
                    and str(unit_info["unit_type_id"]) in unit_data
                ):
                    unit_stats = unit_data[str(unit_info["unit_type_id"])]

                print(f"\nUnit Type: {unit_info['unit_type_name']}")
                if unit_stats:
                    print(
                        f"Base Stats: HP={unit_stats.get('HP', '?')}, "
                        f"Attack={unit_stats.get('Attack', '?')}, "
                        f"Armor={unit_stats.get('MeleeArmor', '?')}/{unit_stats.get('PierceArmor', '?')}, "
                        f"Speed={unit_stats.get('Speed', '?')}"
                    )

                print(f"\nBorn: {first_action_time}")
                print(f"Last commanded: {last_action_time}")
                print(f"Active service: {active_duration}")

                if fate == "LIKELY DIED":
                    print(f"\nFATE: {fate}")
                    print(f"Estimated time of death: ~{estimated_death_time}")
                    print(
                        "(No commands received for 5+ minutes - presumed killed in action)"
                    )
                else:
                    print(f"\nFATE: {fate} until end of match")

                print()
                print("-" * 90)
                print("BATTLE TIMELINE")
                print("-" * 90)

                # Simplify journey
                simplified_actions = simplify_journey(unit_info["actions"])

                for action in simplified_actions:
                    timestamp = action["timestamp"]
                    description = get_action_description(action, object_names)

                    print(f"\n[{timestamp}]")
                    print(f"  {description}")

                # If likely died, add death marker
                if fate == "LIKELY DIED" and estimated_death_time:
                    print(f"\n[~{estimated_death_time}]")
                    print(f"  *** PRESUMED KILLED IN ACTION ***")
                    print(f"  (No further commands - likely fell in battle)")

                print()
                print("-" * 90)
                print("COMBAT STATISTICS")
                print("-" * 90)
                print(f"  Total move commands:    {unit_info['move_count']}")
                print(f"  Attack/task orders:     {unit_info['order_count']}")
                print(
                    f"  Used patrol:            {'Yes' if unit_info['has_patrol'] else 'No'}"
                )
                print(
                    f"  Changed stance:         {'Yes' if unit_info['has_stance'] else 'No'}"
                )

            # Summary
            print("\n" + "=" * 90)
            print("MILITARY SUMMARY")
            print("=" * 90)

            survived = sum(
                1
                for u in units_to_track
                if determine_unit_fate(u["last_seen"], match.duration, match.duration)[
                    0
                ]
                == "SURVIVED"
            )
            died = len(units_to_track) - survived

            print(f"\nOf the {len(units_to_track)} units tracked:")
            print(f"  Survived:     {survived}")
            print(f"  Likely died:  {died}")

            print("\n" + "=" * 90)
            print("END OF MILITARY ANALYSIS")
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
        description="Track the journey of military units in an AoE2 replay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python military_journey.py game.aoe2record --player "ddk220"
  python military_journey.py game.aoe2record --player "ddk" --units 10
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

    analyze_military_journeys(args.file, args.player, args.units)


if __name__ == "__main__":
    main()
