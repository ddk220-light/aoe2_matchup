#!/usr/bin/env python3
"""
AoE2 Record Stats Extractor
Extracts all useful statistics from an AoE2 replay and outputs to CSV files.

Outputs:
- match_info.csv: General match information
- players.csv: Player information and final stats
- units.csv: All units trained by each player with their stats
- buildings.csv: All buildings constructed by each player
- technologies.csv: All technologies researched by each player
- actions_summary.csv: Action counts per player per minute
- unit_summary.csv: Summary stats per unit (one row per unit)
- all_actions.csv: Every single action as a separate row with full details
- actions_readable.csv: Human-readable actions with named units (villager_ddk220_1, etc.)
- player_totals.csv: Aggregate stats per player
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import timedelta

import mgz
import mgz.model

# Death threshold for military units (5 minutes)
DEATH_THRESHOLD_SECONDS = 5 * 60


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


def extract_stats(file_path, output_dir):
    """Extract all stats from a replay file and output to CSV files."""

    print(f"Processing: {file_path}")
    print(f"Output directory: {output_dir}")

    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)

    # Load reference data
    unit_data = load_unit_data()
    object_names = load_object_names()

    with open(file_path, "rb") as f:
        match = mgz.model.parse_match(f)

        match_duration = match.duration.total_seconds()

        # =====================================================================
        # 1. MATCH INFO
        # =====================================================================
        match_info_file = os.path.join(output_dir, "match_info.csv")
        with open(match_info_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["field", "value"])
            writer.writerow(["file", os.path.basename(file_path)])
            writer.writerow(["duration_seconds", match_duration])
            writer.writerow(["duration_formatted", str(match.duration)])
            writer.writerow(
                [
                    "map",
                    match.map.name if hasattr(match.map, "name") else str(match.map),
                ]
            )
            writer.writerow(["num_players", len(match.players)])
            writer.writerow(
                [
                    "game_version",
                    str(match.game_version) if hasattr(match, "game_version") else "",
                ]
            )
            writer.writerow(
                ["speed", str(match.speed) if hasattr(match, "speed") else ""]
            )
        print(f"  Created: {match_info_file}")

        # =====================================================================
        # 2. PLAYERS
        # =====================================================================
        players_file = os.path.join(output_dir, "players.csv")
        with open(players_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player_number",
                    "name",
                    "civilization",
                    "civilization_id",
                    "color_id",
                    "team_id",
                    "winner",
                    "starting_units",
                ]
            )

            for i, p in enumerate(match.players, 1):
                writer.writerow(
                    [
                        i,
                        p.name,
                        p.civilization if hasattr(p, "civilization") else "",
                        p.civilization_id,
                        p.color_id,
                        str(p.team_id) if p.team_id else "",
                        p.winner,
                        len(p.objects) if p.objects else 0,
                    ]
                )
        print(f"  Created: {players_file}")

        # =====================================================================
        # Collect all actions per player
        # =====================================================================
        player_actions = {p.name: [] for p in match.players}
        player_unit_actions = {p.name: defaultdict(list) for p in match.players}

        for action in match.actions:
            if action.player and action.player.name in player_actions:
                player_name = action.player.name

                action_data = {
                    "timestamp": action.timestamp,
                    "timestamp_seconds": action.timestamp.total_seconds(),
                    "type": str(action.type).replace("Action.", ""),
                    "payload": action.payload,
                    "position": action.position
                    if hasattr(action, "position")
                    else None,
                }
                player_actions[player_name].append(action_data)

                # Track per-unit actions
                if action.payload and "object_ids" in action.payload:
                    for obj_id in action.payload["object_ids"]:
                        player_unit_actions[player_name][obj_id].append(action_data)

        # =====================================================================
        # 3. UNITS (training commands)
        # =====================================================================
        units_file = os.path.join(output_dir, "units.csv")
        with open(units_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player",
                    "unit_name",
                    "unit_type_id",
                    "queue_time_seconds",
                    "queue_time_formatted",
                    "training_building_id",
                    "amount",
                    "is_villager",
                    "hp",
                    "attack",
                    "melee_armor",
                    "pierce_armor",
                    "speed",
                    "range",
                    "train_time",
                    "food_cost",
                    "wood_cost",
                    "gold_cost",
                    "stone_cost",
                ]
            )

            for player_name, actions in player_actions.items():
                for action in actions:
                    if action["type"] == "DE_QUEUE" and action["payload"]:
                        unit_name = action["payload"].get("unit", "")
                        unit_id = action["payload"].get("unit_id")
                        amount = action["payload"].get("amount", 1)
                        building_ids = action["payload"].get("object_ids", [])

                        # Get unit stats
                        stats = unit_data.get(str(unit_id), {}) if unit_id else {}
                        cost = stats.get("Cost", {})

                        writer.writerow(
                            [
                                player_name,
                                unit_name,
                                unit_id,
                                action["timestamp_seconds"],
                                str(action["timestamp"]),
                                building_ids[0] if building_ids else "",
                                amount,
                                1 if "Villager" in unit_name else 0,
                                stats.get("HP", ""),
                                stats.get("Attack", ""),
                                stats.get("MeleeArmor", ""),
                                stats.get("PierceArmor", ""),
                                stats.get("Speed", ""),
                                stats.get("Range", ""),
                                stats.get("TrainTime", ""),
                                cost.get("Food", ""),
                                cost.get("Wood", ""),
                                cost.get("Gold", ""),
                                cost.get("Stone", ""),
                            ]
                        )
        print(f"  Created: {units_file}")

        # =====================================================================
        # 4. BUILDINGS
        # =====================================================================
        buildings_file = os.path.join(output_dir, "buildings.csv")
        with open(buildings_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player",
                    "building_name",
                    "building_id",
                    "build_time_seconds",
                    "build_time_formatted",
                    "position_x",
                    "position_y",
                    "builder_ids",
                ]
            )

            for player_name, actions in player_actions.items():
                for action in actions:
                    if action["type"] == "BUILD" and action["payload"]:
                        building_id = action["payload"].get(
                            "building_id", action["payload"].get("building", "")
                        )
                        building_name = object_names.get(
                            str(building_id), f"Building_{building_id}"
                        )
                        builder_ids = action["payload"].get("object_ids", [])
                        pos = action["position"]

                        writer.writerow(
                            [
                                player_name,
                                building_name,
                                building_id,
                                action["timestamp_seconds"],
                                str(action["timestamp"]),
                                pos.x if pos else "",
                                pos.y if pos else "",
                                ",".join(map(str, builder_ids)),
                            ]
                        )
        print(f"  Created: {buildings_file}")

        # =====================================================================
        # 5. TECHNOLOGIES
        # =====================================================================
        tech_file = os.path.join(output_dir, "technologies.csv")
        with open(tech_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player",
                    "technology",
                    "research_time_seconds",
                    "research_time_formatted",
                    "building_id",
                ]
            )

            for player_name, actions in player_actions.items():
                for action in actions:
                    if action["type"] == "RESEARCH" and action["payload"]:
                        tech = action["payload"].get(
                            "technology", action["payload"].get("tech_id", "Unknown")
                        )
                        building_ids = action["payload"].get("object_ids", [])

                        writer.writerow(
                            [
                                player_name,
                                tech,
                                action["timestamp_seconds"],
                                str(action["timestamp"]),
                                building_ids[0] if building_ids else "",
                            ]
                        )
        print(f"  Created: {tech_file}")

        # =====================================================================
        # 6. ACTIONS SUMMARY (per player per minute)
        # =====================================================================
        actions_summary_file = os.path.join(output_dir, "actions_summary.csv")
        with open(actions_summary_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player",
                    "minute",
                    "total_actions",
                    "move_actions",
                    "order_actions",
                    "build_actions",
                    "queue_actions",
                    "research_actions",
                    "other_actions",
                ]
            )

            for player_name, actions in player_actions.items():
                # Group by minute
                actions_by_minute = defaultdict(
                    lambda: {
                        "total": 0,
                        "move": 0,
                        "order": 0,
                        "build": 0,
                        "queue": 0,
                        "research": 0,
                        "other": 0,
                    }
                )

                for action in actions:
                    minute = int(action["timestamp_seconds"] // 60)
                    action_type = action["type"]

                    actions_by_minute[minute]["total"] += 1

                    if action_type == "MOVE":
                        actions_by_minute[minute]["move"] += 1
                    elif action_type == "ORDER":
                        actions_by_minute[minute]["order"] += 1
                    elif action_type == "BUILD":
                        actions_by_minute[minute]["build"] += 1
                    elif action_type == "DE_QUEUE":
                        actions_by_minute[minute]["queue"] += 1
                    elif action_type == "RESEARCH":
                        actions_by_minute[minute]["research"] += 1
                    else:
                        actions_by_minute[minute]["other"] += 1

                for minute in sorted(actions_by_minute.keys()):
                    counts = actions_by_minute[minute]
                    writer.writerow(
                        [
                            player_name,
                            minute,
                            counts["total"],
                            counts["move"],
                            counts["order"],
                            counts["build"],
                            counts["queue"],
                            counts["research"],
                            counts["other"],
                        ]
                    )
        print(f"  Created: {actions_summary_file}")

        # =====================================================================
        # 7. UNIT SUMMARY (one row per unit with aggregate stats)
        # =====================================================================
        unit_summary_file = os.path.join(output_dir, "unit_summary.csv")
        with open(unit_summary_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player",
                    "unit_instance_id",
                    "is_starting_unit",
                    "is_villager",
                    "first_seen_seconds",
                    "first_seen_formatted",
                    "last_seen_seconds",
                    "last_seen_formatted",
                    "active_duration_seconds",
                    "total_actions",
                    "move_count",
                    "order_count",
                    "build_count",
                    "stance_changes",
                    "patrol_count",
                    "likely_died",
                    "estimated_death_seconds",
                    "first_pos_x",
                    "first_pos_y",
                    "last_pos_x",
                    "last_pos_y",
                ]
            )

            for player in match.players:
                player_name = player.name
                starting_ids = (
                    {obj.instance_id for obj in player.objects}
                    if player.objects
                    else set()
                )

                for unit_id, actions in player_unit_actions[player_name].items():
                    if not actions:
                        continue

                    # Calculate stats
                    first_action = actions[0]
                    last_action = actions[-1]

                    first_ts = first_action["timestamp_seconds"]
                    last_ts = last_action["timestamp_seconds"]
                    active_duration = last_ts - first_ts

                    move_count = sum(1 for a in actions if a["type"] == "MOVE")
                    order_count = sum(1 for a in actions if a["type"] == "ORDER")
                    build_count = sum(1 for a in actions if a["type"] == "BUILD")
                    stance_count = sum(1 for a in actions if a["type"] == "STANCE")
                    patrol_count = sum(1 for a in actions if a["type"] == "PATROL")

                    is_starting = unit_id in starting_ids
                    is_villager = build_count > 0  # Villagers can build

                    # Determine if likely died (military only)
                    time_since_last = match_duration - last_ts
                    likely_died = (
                        not is_villager
                        and time_since_last > DEATH_THRESHOLD_SECONDS
                        and not is_starting
                    )
                    estimated_death = (
                        last_ts + DEATH_THRESHOLD_SECONDS if likely_died else ""
                    )

                    # Get positions
                    first_pos = first_action.get("position")
                    last_pos = last_action.get("position")

                    writer.writerow(
                        [
                            player_name,
                            unit_id,
                            1 if is_starting else 0,
                            1 if is_villager else 0,
                            first_ts,
                            str(first_action["timestamp"]),
                            last_ts,
                            str(last_action["timestamp"]),
                            active_duration,
                            len(actions),
                            move_count,
                            order_count,
                            build_count,
                            stance_count,
                            patrol_count,
                            1 if likely_died else 0,
                            estimated_death,
                            first_pos.x if first_pos else "",
                            first_pos.y if first_pos else "",
                            last_pos.x if last_pos else "",
                            last_pos.y if last_pos else "",
                        ]
                    )
        print(f"  Created: {unit_summary_file}")

        # =====================================================================
        # 8. ALL ACTIONS (every single action as a separate row)
        # =====================================================================
        all_actions_file = os.path.join(output_dir, "all_actions.csv")
        with open(all_actions_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "action_id",
                    "timestamp_seconds",
                    "timestamp_formatted",
                    "player",
                    "action_type",
                    "unit_ids",
                    "unit_ids_count",
                    "target_id",
                    "position_x",
                    "position_y",
                    "building_id",
                    "building_name",
                    "unit_type_id",
                    "unit_type_name",
                    "technology",
                    "amount",
                    "stance",
                    "formation",
                    "other_payload",
                ]
            )

            action_id = 0
            for action in match.actions:
                if not action.player:
                    continue

                action_id += 1
                player_name = action.player.name
                action_type = str(action.type).replace("Action.", "")
                payload = action.payload or {}
                pos = action.position if hasattr(action, "position") else None

                # Extract common fields from payload
                unit_ids = payload.get("object_ids", [])
                target_id = payload.get("target_id", "")
                building_id = payload.get("building_id", payload.get("building", ""))
                building_name = (
                    object_names.get(str(building_id), "") if building_id else ""
                )
                unit_type_id = payload.get("unit_id", "")
                unit_type_name = payload.get("unit", "")
                technology = payload.get("technology", payload.get("tech_id", ""))
                amount = payload.get("amount", "")
                stance = payload.get("stance", "")
                formation = payload.get("formation", "")

                # Collect remaining payload fields
                known_keys = {
                    "object_ids",
                    "target_id",
                    "building_id",
                    "building",
                    "unit_id",
                    "unit",
                    "technology",
                    "tech_id",
                    "amount",
                    "stance",
                    "formation",
                    "sequence",
                }
                other_payload = {
                    k: v for k, v in payload.items() if k not in known_keys
                }
                other_payload_str = str(other_payload) if other_payload else ""

                writer.writerow(
                    [
                        action_id,
                        action.timestamp.total_seconds(),
                        str(action.timestamp),
                        player_name,
                        action_type,
                        ",".join(map(str, unit_ids)) if unit_ids else "",
                        len(unit_ids) if unit_ids else 0,
                        target_id,
                        pos.x if pos else "",
                        pos.y if pos else "",
                        building_id,
                        building_name,
                        unit_type_id,
                        unit_type_name,
                        technology,
                        amount,
                        stance,
                        formation,
                        other_payload_str,
                    ]
                )
        print(f"  Created: {all_actions_file}")

        # =====================================================================
        # 9. ACTIONS READABLE (formatted with human-readable unit names)
        # =====================================================================
        actions_readable_file = os.path.join(output_dir, "actions_readable.csv")

        # First pass: assign names to all unit instance IDs
        # Track unit creation order per player per unit type
        unit_name_map = {}  # {instance_id: "villager_ddk220_1"}
        building_name_map = {}  # {instance_id: "towncenter_ddk220_1"}
        tech_name_map = {}  # {(player, tech): "loom_ddk220"}

        # Counters per player per type
        unit_counters = defaultdict(
            lambda: defaultdict(int)
        )  # {player: {unit_type: count}}
        building_counters = defaultdict(
            lambda: defaultdict(int)
        )  # {player: {building_type: count}}
        tech_counters = defaultdict(lambda: defaultdict(int))  # {player: {tech: count}}

        # First, name all starting units
        for player in match.players:
            player_name = player.name
            if player.objects:
                for obj in player.objects:
                    # Starting units are typically villagers
                    unit_type = (
                        obj.name.lower().replace(" ", "") if obj.name else "unit"
                    )
                    unit_counters[player_name][unit_type] += 1
                    count = unit_counters[player_name][unit_type]
                    unit_name_map[obj.instance_id] = (
                        f"{unit_type}_{player_name}_{count}"
                    )

        # Second pass: go through all actions to name units as they appear
        for action in match.actions:
            if not action.player:
                continue

            player_name = action.player.name
            action_type = str(action.type).replace("Action.", "")
            payload = action.payload or {}

            # Name units when they're trained (DE_QUEUE)
            if action_type == "DE_QUEUE":
                unit_type_name = payload.get("unit", "unit").lower().replace(" ", "")
                building_id = payload.get("object_ids", [None])[0]
                amount = payload.get("amount", 1)

                # We don't know the exact instance ID of the created unit from DE_QUEUE
                # But we can track training building to estimate
                # For now, just count for naming purposes

            # Name buildings when they're built
            if action_type == "BUILD":
                building_type_id = payload.get(
                    "building_id", payload.get("building", "")
                )
                building_type_name = object_names.get(
                    str(building_type_id), f"building{building_type_id}"
                )
                building_type_name = building_type_name.lower().replace(" ", "")

                # The building gets an instance ID but we don't have it directly
                # We'll name it based on position for uniqueness
                pos = (
                    action.position
                    if hasattr(action, "position") and action.position
                    else None
                )
                if pos:
                    pos_key = f"{int(pos.x)}_{int(pos.y)}"
                    building_counters[player_name][building_type_name] += 1
                    count = building_counters[player_name][building_type_name]
                    building_name_map[(player_name, pos_key)] = (
                        f"{building_type_name}_{player_name}_{count}"
                    )

            # Track unit instance IDs as they appear in actions
            if "object_ids" in payload:
                for obj_id in payload["object_ids"]:
                    if obj_id not in unit_name_map:
                        # Try to figure out what type of unit this is
                        # Check if this unit does BUILD actions (villager)
                        is_villager = False
                        for p_actions in player_unit_actions[player_name].get(
                            obj_id, []
                        ):
                            if p_actions["type"] == "BUILD":
                                is_villager = True
                                break

                        if is_villager:
                            unit_type = "villager"
                        else:
                            # Could be military, sheep, or other
                            unit_type = "unit"

                        unit_counters[player_name][unit_type] += 1
                        count = unit_counters[player_name][unit_type]
                        unit_name_map[obj_id] = f"{unit_type}_{player_name}_{count}"

        # Better approach: identify unit types by analyzing training commands and timing
        # Re-process to assign better names based on training queue
        training_events = []  # List of (timestamp, player, unit_type_name, building_id)

        for action in match.actions:
            if not action.player:
                continue
            action_type = str(action.type).replace("Action.", "")
            if action_type == "DE_QUEUE" and action.payload:
                unit_type_name = action.payload.get("unit", "unit")
                training_events.append(
                    {
                        "timestamp": action.timestamp.total_seconds(),
                        "player": action.player.name,
                        "unit_type": unit_type_name.lower().replace(" ", ""),
                        "unit_type_display": unit_type_name,
                    }
                )

        # Build a map of unit instance ID -> owner player
        # Owner is determined by: 1) starting units belong to player, 2) first player to command a unit
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

        # Reset and rebuild unit names with proper types
        unit_name_map = {}
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

        # For non-starting units, we'll name them when they first appear
        # and try to match with training events based on timing

        with open(actions_readable_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "action_id",
                    "timestamp_formatted",
                    "player",
                    "action_type",
                    "subject_name",
                    "target_name",
                    "position_x",
                    "position_y",
                    "details",
                ]
            )

            action_id = 0
            for action in match.actions:
                if not action.player:
                    continue

                action_id += 1
                player_name = action.player.name
                action_type = str(action.type).replace("Action.", "")
                payload = action.payload or {}
                pos = action.position if hasattr(action, "position") else None

                # Build subject name (the unit(s) performing the action)
                subject_names = []
                unit_ids = payload.get("object_ids", [])

                for obj_id in unit_ids:
                    if obj_id not in unit_name_map:
                        # Get the owner of this unit (first player to command it)
                        owner = unit_owner_map.get(obj_id, player_name)

                        # Determine unit type by checking if this unit does BUILD actions
                        is_villager = any(
                            a["type"] == "BUILD"
                            for a in player_unit_actions[owner].get(obj_id, [])
                        )

                        if is_villager:
                            unit_type = "villager"
                        else:
                            # Try to match with a training event
                            first_seen = None
                            for a in player_unit_actions[owner].get(obj_id, []):
                                first_seen = a["timestamp_seconds"]
                                break

                            # Find most recent training event before this unit appeared
                            unit_type = "unit"
                            if first_seen:
                                for te in reversed(training_events):
                                    if (
                                        te["player"] == owner
                                        and te["timestamp"] < first_seen
                                    ):
                                        # Possible match - use this unit type
                                        unit_type = te["unit_type"]
                                        break

                        unit_counters[owner][unit_type] += 1
                        count = unit_counters[owner][unit_type]
                        unit_name_map[obj_id] = f"{unit_type}_{owner}_{count}"

                    subject_names.append(unit_name_map[obj_id])

                subject_name = ", ".join(subject_names) if subject_names else ""

                # Build target name
                target_name = ""
                target_id = payload.get("target_id")
                if target_id:
                    if target_id in unit_name_map:
                        target_name = unit_name_map[target_id]
                    else:
                        target_name = f"target_{target_id}"

                # Handle special cases for different action types
                if action_type == "BUILD":
                    building_id = payload.get(
                        "building_id", payload.get("building", "")
                    )
                    building_type = object_names.get(
                        str(building_id), f"building{building_id}"
                    )
                    building_type_clean = building_type.lower().replace(" ", "")

                    if pos:
                        pos_key = f"{int(pos.x)}_{int(pos.y)}"
                        if (player_name, pos_key) not in building_name_map:
                            building_counters[player_name][building_type_clean] += 1
                            count = building_counters[player_name][building_type_clean]
                            building_name_map[(player_name, pos_key)] = (
                                f"{building_type_clean}_{player_name}_{count}"
                            )
                        target_name = building_name_map[(player_name, pos_key)]
                    else:
                        building_counters[player_name][building_type_clean] += 1
                        count = building_counters[player_name][building_type_clean]
                        target_name = f"{building_type_clean}_{player_name}_{count}"

                elif action_type == "DE_QUEUE":
                    unit_type = payload.get("unit", "unit")
                    amount = payload.get("amount", 1)
                    target_name = f"training_{unit_type.lower().replace(' ', '')}"

                elif action_type == "RESEARCH":
                    tech = payload.get("technology", payload.get("tech_id", "unknown"))
                    tech_clean = str(tech).lower().replace(" ", "")
                    tech_counters[player_name][tech_clean] += 1
                    count = tech_counters[player_name][tech_clean]
                    if count == 1:
                        target_name = f"{tech_clean}_{player_name}"
                    else:
                        target_name = f"{tech_clean}_{player_name}_{count}"

                # Build details string
                details_parts = []
                if action_type == "DE_QUEUE":
                    amount = payload.get("amount", 1)
                    if amount > 1:
                        details_parts.append(f"amount={amount}")
                if action_type == "STANCE":
                    stance = payload.get("stance", "")
                    stance_names = {
                        0: "aggressive",
                        1: "defensive",
                        2: "standground",
                        3: "noattack",
                    }
                    details_parts.append(f"stance={stance_names.get(stance, stance)}")
                if action_type == "FORMATION":
                    formation = payload.get("formation", "")
                    formation_names = {0: "line", 1: "staggered", 2: "box", 3: "flank"}
                    details_parts.append(
                        f"formation={formation_names.get(formation, formation)}"
                    )
                if action_type == "GAME":
                    cmd = payload.get("command", "")
                    if cmd:
                        details_parts.append(f"command={cmd}")

                # Add any other payload items
                known_keys = {
                    "object_ids",
                    "target_id",
                    "building_id",
                    "building",
                    "unit_id",
                    "unit",
                    "technology",
                    "tech_id",
                    "amount",
                    "stance",
                    "formation",
                    "sequence",
                    "command",
                    "command_id",
                }
                for k, v in payload.items():
                    if k not in known_keys:
                        details_parts.append(f"{k}={v}")

                details = "; ".join(details_parts) if details_parts else ""

                writer.writerow(
                    [
                        action_id,
                        str(action.timestamp),
                        player_name,
                        action_type,
                        subject_name,
                        target_name,
                        f"{pos.x:.1f}" if pos else "",
                        f"{pos.y:.1f}" if pos else "",
                        details,
                    ]
                )

        print(f"  Created: {actions_readable_file}")

        # =====================================================================
        # 10. PLAYER TOTALS (summary stats per player)
        # =====================================================================
        player_totals_file = os.path.join(output_dir, "player_totals.csv")
        with open(player_totals_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "player",
                    "winner",
                    "civilization",
                    "total_actions",
                    "total_villagers_trained",
                    "total_military_trained",
                    "total_buildings",
                    "total_technologies",
                    "unique_unit_types",
                    "unique_building_types",
                    "units_likely_died",
                    "villagers_with_builds",
                ]
            )

            for player in match.players:
                player_name = player.name
                actions = player_actions[player_name]
                starting_ids = (
                    {obj.instance_id for obj in player.objects}
                    if player.objects
                    else set()
                )

                # Count units trained
                villagers_trained = 0
                military_trained = 0
                unit_types = set()

                for action in actions:
                    if action["type"] == "DE_QUEUE" and action["payload"]:
                        unit_name = action["payload"].get("unit", "")
                        amount = action["payload"].get("amount", 1)
                        unit_types.add(unit_name)

                        if "Villager" in unit_name:
                            villagers_trained += amount
                        else:
                            military_trained += amount

                # Count buildings
                building_types = set()
                total_buildings = 0
                for action in actions:
                    if action["type"] == "BUILD" and action["payload"]:
                        building_id = action["payload"].get(
                            "building_id", action["payload"].get("building", "")
                        )
                        building_types.add(building_id)
                        total_buildings += 1

                # Count technologies
                total_techs = sum(1 for a in actions if a["type"] == "RESEARCH")

                # Count deaths and villagers
                units_died = 0
                villagers_with_builds = 0

                for unit_id, unit_actions in player_unit_actions[player_name].items():
                    if not unit_actions or unit_id in starting_ids:
                        continue

                    build_count = sum(1 for a in unit_actions if a["type"] == "BUILD")
                    is_villager = build_count > 0

                    if is_villager:
                        villagers_with_builds += 1
                    else:
                        last_ts = unit_actions[-1]["timestamp_seconds"]
                        if match_duration - last_ts > DEATH_THRESHOLD_SECONDS:
                            units_died += 1

                writer.writerow(
                    [
                        player_name,
                        1 if player.winner else 0,
                        player.civilization if hasattr(player, "civilization") else "",
                        len(actions),
                        villagers_trained,
                        military_trained,
                        total_buildings,
                        total_techs,
                        len(unit_types),
                        len(building_types),
                        units_died,
                        villagers_with_builds,
                    ]
                )
        print(f"  Created: {player_totals_file}")

        print(f"\nExtraction complete! 10 CSV files created in {output_dir}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract stats from an AoE2 replay to CSV files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output files created:
  match_info.csv      - General match information
  players.csv         - Player information
  units.csv           - All units trained (one row per training command)
  buildings.csv       - All buildings constructed
  technologies.csv    - All technologies researched
  actions_summary.csv - Action counts per player per minute
  unit_summary.csv    - Summary stats per unit (one row per unit)
  all_actions.csv     - Every action as a separate row with full details
  player_totals.csv   - Aggregate stats per player

Examples:
  python extract_stats.py game.aoe2record
  python extract_stats.py game.aoe2record --output ./stats_output
        """,
    )

    parser.add_argument("file", help="Path to .aoe2record file")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output directory (default: <filename>_stats)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: File does not exist: {args.file}")
        sys.exit(1)

    # Default output directory
    if args.output is None:
        base_name = os.path.splitext(os.path.basename(args.file))[0]
        args.output = os.path.join(os.path.dirname(args.file), f"{base_name}_stats")

    extract_stats(args.file, args.output)


if __name__ == "__main__":
    main()
