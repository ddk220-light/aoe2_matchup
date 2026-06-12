#!/usr/bin/env python3
"""
AoE2 Unit Analyzer
Analyzes units created by a specific player in an Age of Empires 2 recorded game.
Shows detailed stats for each unit including attack, armor, speed, HP, etc.
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import timedelta

import mgz
import mgz.model

# URL for unit stats data
UNIT_DATA_URL = "https://raw.githubusercontent.com/SiegeEngineers/aoe2techtree/master/data/data.json"

# Cache file for unit data
CACHE_FILE = os.path.join(os.path.dirname(__file__), ".unit_data_cache.json")


def load_unit_data():
    """Load unit stats data from cache or fetch from URL."""

    # Try to load from cache first
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
                if "units" in cache:
                    return cache["units"]
        except (json.JSONDecodeError, IOError):
            pass

    # Fetch from URL
    print("Fetching unit data from aoe2techtree...")
    try:
        with urllib.request.urlopen(UNIT_DATA_URL, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            units = data.get("data", {}).get("units", {})

            # Cache the data
            try:
                with open(CACHE_FILE, "w") as f:
                    json.dump({"units": units}, f)
            except IOError:
                pass

            return units
    except Exception as e:
        print(f"Warning: Could not fetch unit data: {e}")
        return {}


def get_armor_class_name(class_id):
    """Convert armor class ID to human-readable name."""
    armor_classes = {
        1: "Infantry",
        2: "Turtle Ships",
        3: "Base Pierce",
        4: "Base Melee",
        5: "War Elephants",
        8: "Cavalry",
        11: "All Buildings",
        13: "Stone Defense",
        15: "Archers",
        16: "Ships",
        17: "Rams",
        19: "Trees",
        20: "Unique Units",
        21: "Siege Weapons",
        22: "Standard Buildings",
        23: "Walls & Gates",
        24: "Boars",
        25: "Monks",
        26: "Castle",
        27: "Spearmen",
        28: "Cavalry Archers",
        29: "Eagle Warriors",
        30: "Camels",
        31: "Leitis",
        32: "Condottieri",
        34: "Fishing Ships",
        35: "Mamelukes",
        36: "Heroes",
        37: "Hussite Wagons",
        38: "Elephants",
        39: "Obuch",
    }
    return armor_classes.get(class_id, f"Class {class_id}")


def format_attacks(attacks):
    """Format attack bonuses into readable string."""
    if not attacks:
        return "None"

    bonus_attacks = []
    base_attack = 0

    for attack in attacks:
        amount = attack.get("Amount", 0)
        class_id = attack.get("Class", 0)
        class_name = get_armor_class_name(class_id)

        # Class 3 (Base Pierce) and 4 (Base Melee) are the main attack values
        if class_id in (3, 4):
            if amount > 0:
                base_attack = max(base_attack, amount)
        elif amount != 0:
            bonus_attacks.append(f"+{amount} vs {class_name}")

    if bonus_attacks:
        return ", ".join(bonus_attacks[:5])  # Limit to 5 most relevant
    return "None"


def format_armors(armors):
    """Format armor values into readable string."""
    if not armors:
        return "None"

    melee = 0
    pierce = 0
    bonus_armors = []

    for armor in armors:
        amount = armor.get("Amount", 0)
        class_id = armor.get("Class", 0)

        if class_id == 4:  # Base Melee
            melee = amount
        elif class_id == 3:  # Base Pierce
            pierce = amount
        elif amount != 0:
            class_name = get_armor_class_name(class_id)
            bonus_armors.append(f"{amount} ({class_name})")

    result = f"Melee: {melee}, Pierce: {pierce}"
    if bonus_armors:
        result += f" | Bonus: {', '.join(bonus_armors[:3])}"
    return result


def format_cost(cost):
    """Format resource cost into readable string."""
    if not cost:
        return "Free"

    parts = []
    if "Food" in cost:
        parts.append(f"{cost['Food']}F")
    if "Wood" in cost:
        parts.append(f"{cost['Wood']}W")
    if "Gold" in cost:
        parts.append(f"{cost['Gold']}G")
    if "Stone" in cost:
        parts.append(f"{cost['Stone']}S")

    return " ".join(parts) if parts else "Free"


def analyze_player_units(file_path, player_name, limit=10):
    """Analyze units created by a specific player."""

    print("=" * 90)
    print("AoE2 UNIT ANALYZER")
    print("=" * 90)
    print(f"\nFile: {file_path}")
    print(f"Target Player: {player_name}")
    print(f"Unit Limit: {limit}")
    print()

    # Load unit stats data
    unit_data = load_unit_data()
    if not unit_data:
        print("Warning: Unit stats data not available. Only basic info will be shown.")

    try:
        with open(file_path, "rb") as f:
            match = mgz.model.parse_match(f)

            # Find the target player
            target_player = None
            for p in match.players:
                if player_name.lower() in p.name.lower():
                    target_player = p
                    break

            if not target_player:
                print(f"ERROR: Player '{player_name}' not found.")
                print("Available players:")
                for p in match.players:
                    print(f"  - {p.name}")
                return

            print(f"Found player: {target_player.name}")
            print(f"Civilization ID: {target_player.civilization_id}")
            print()

            # Find all unit creation actions (DE_QUEUE)
            unit_creations = []
            for action in match.actions:
                if action.player and action.player.name == target_player.name:
                    if "QUEUE" in str(action.type) and action.payload:
                        unit_id = action.payload.get("unit_id")
                        unit_name = action.payload.get("unit", "Unknown")
                        amount = action.payload.get("amount", 1)

                        if unit_id:
                            unit_creations.append(
                                {
                                    "timestamp": action.timestamp,
                                    "unit_id": unit_id,
                                    "unit_name": unit_name,
                                    "amount": amount,
                                    "building_ids": action.payload.get(
                                        "object_ids", []
                                    ),
                                }
                            )

            print(f"Total unit training commands: {len(unit_creations)}")
            print()

            # Display units with stats
            print("=" * 90)
            print("UNITS CREATED (with stats)")
            print("=" * 90)
            print()

            displayed = 0
            for creation in unit_creations:
                if displayed >= limit:
                    break

                unit_id = str(creation["unit_id"])
                unit_name = creation["unit_name"]
                timestamp = creation["timestamp"]
                amount = creation["amount"]

                print(f"[{timestamp}] {unit_name} (ID: {unit_id}) x{amount}")
                print("-" * 60)

                # Get stats from unit data
                if unit_id in unit_data:
                    stats = unit_data[unit_id]

                    # Basic stats
                    print(f"  HP:              {stats.get('HP', 'N/A')}")
                    print(f"  Attack:          {stats.get('Attack', 'N/A')}")
                    print(f"  Melee Armor:     {stats.get('MeleeArmor', 'N/A')}")
                    print(f"  Pierce Armor:    {stats.get('PierceArmor', 'N/A')}")
                    print(f"  Speed:           {stats.get('Speed', 'N/A')}")
                    print(f"  Range:           {stats.get('Range', 'N/A')}")
                    print(f"  Line of Sight:   {stats.get('LineOfSight', 'N/A')}")
                    print(f"  Reload Time:     {stats.get('ReloadTime', 'N/A')}s")
                    print(f"  Train Time:      {stats.get('TrainTime', 'N/A')}s")
                    print(f"  Accuracy:        {stats.get('AccuracyPercent', 'N/A')}%")
                    print(f"  Cost:            {format_cost(stats.get('Cost', {}))}")

                    # Attack bonuses
                    attacks = stats.get("Attacks", [])
                    if attacks:
                        print(f"  Attack Bonuses:  {format_attacks(attacks)}")

                    # Armor classes
                    armors = stats.get("Armours", [])
                    if armors:
                        print(f"  Armor Classes:   {format_armors(armors)}")

                    # Internal name
                    if "internal_name" in stats:
                        print(f"  Internal Name:   {stats['internal_name']}")
                else:
                    print("  (Stats not available for this unit)")

                print()
                displayed += 1

            if len(unit_creations) > limit:
                print(
                    f"... and {len(unit_creations) - limit} more unit training commands"
                )

            # Summary statistics
            print("=" * 90)
            print("SUMMARY")
            print("=" * 90)

            # Count by unit type
            unit_counts = {}
            for creation in unit_creations:
                name = creation["unit_name"]
                amount = creation["amount"]
                unit_counts[name] = unit_counts.get(name, 0) + amount

            print("\nUnits trained by type:")
            for name, count in sorted(unit_counts.items(), key=lambda x: -x[1]):
                print(f"  {name}: {count}")

            print(f"\nTotal units trained: {sum(unit_counts.values())}")

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
        description="Analyze units created by a player in an AoE2 replay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python unit_analyzer.py game.aoe2record --player "ddk220"
  python unit_analyzer.py game.aoe2record --player "ddk" --limit 20
        """,
    )

    parser.add_argument("file", help="Path to .aoe2record file")
    parser.add_argument(
        "--player", "-p", required=True, help="Player name (or partial match)"
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Maximum number of units to display (default: 10)",
    )

    args = parser.parse_args()

    # Validate file exists
    if not os.path.exists(args.file):
        print(f"ERROR: File does not exist: {args.file}")
        sys.exit(1)

    analyze_player_units(args.file, args.player, args.limit)


if __name__ == "__main__":
    main()
