#!/usr/bin/env python3
"""
AoE2 Data Explorer
Interactive script to query and explore extracted game data.

Usage:
    python explore.py                    # Interactive mode
    python explore.py search knight      # Search for units by name
    python explore.py unit 38            # Get unit by ID
    python explore.py compare 38 93      # Compare two units
    python explore.py counters 38        # Find counters for a unit
"""

import json
import sys
from pathlib import Path


class AoE2Data:
    def __init__(self, data_dir: Path = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / "output"

        self.units = self._load_json(data_dir / "units.json")
        self.techs = self._load_json(data_dir / "technologies.json")
        self.civs = self._load_json(data_dir / "civilizations.json")
        self.armor_classes = self._load_json(data_dir / "armor_classes.json")

        # Build indexes
        self.units_by_id = {u["id"]: u for u in self.units}
        self.units_by_name = {}
        for u in self.units:
            name_lower = u["name"].lower()
            if name_lower not in self.units_by_name:
                self.units_by_name[name_lower] = []
            self.units_by_name[name_lower].append(u)

    def _load_json(self, path: Path) -> list:
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return []

    def search_units(self, query: str) -> list:
        """Search units by name (partial match)."""
        query = query.lower()
        results = []
        for u in self.units:
            if query in u["name"].lower() or query in u["internal_name"].lower():
                results.append(u)
        return results

    def get_unit(self, unit_id: int) -> dict:
        """Get unit by ID."""
        return self.units_by_id.get(unit_id)

    def get_unit_by_name(self, name: str) -> dict:
        """Get unit by exact name match."""
        matches = self.units_by_name.get(name.lower(), [])
        return matches[0] if matches else None

    def format_unit(self, unit: dict, verbose: bool = True) -> str:
        """Format unit data for display."""
        lines = []
        lines.append(f"\n{'='*50}")
        lines.append(f"{unit['name']} (ID: {unit['id']})")
        lines.append(f"{'='*50}")
        lines.append(f"Class: {unit['class_name']} | Type: {'Combat' if unit['type'] == 70 else 'Building'}")
        lines.append(f"HP: {unit['hit_points']} | Speed: {unit['speed']}")

        if unit.get("cost"):
            cost_parts = [f"{v} {k}" for k, v in unit["cost"].items()]
            lines.append(f"Cost: {', '.join(cost_parts)}")

        if unit.get("train_time"):
            lines.append(f"Train Time: {unit['train_time']}s")

        # Combat stats
        if unit.get("range", 0) > 0:
            range_str = f"Range: {unit['range']}"
            if unit.get("min_range", 0) > 0:
                range_str += f" (min: {unit['min_range']})"
            lines.append(range_str)

        if unit.get("reload_time"):
            lines.append(f"Reload Time: {unit['reload_time']}s | Accuracy: {unit.get('accuracy', 100)}%")

        if unit.get("blast_width", 0) > 0:
            lines.append(f"Blast Width: {unit['blast_width']}")

        # Attacks
        if verbose and unit.get("attacks"):
            lines.append("\nAttacks:")
            for atk in unit["attacks"]:
                if atk["amount"] != 0:
                    lines.append(f"  +{atk['amount']} vs {atk['class_name']}")

        # Armors
        if verbose and unit.get("armors"):
            melee = next((a["amount"] for a in unit["armors"] if a["class"] == 4), 0)
            pierce = next((a["amount"] for a in unit["armors"] if a["class"] == 3), 0)
            lines.append(f"\nArmor: {melee}/{pierce} (melee/pierce)")

            # Show bonus armors
            for arm in unit["armors"]:
                if arm["class"] not in [3, 4] and arm["amount"] != 0:
                    lines.append(f"  {arm['amount']} {arm['class_name']} armor")

        return "\n".join(lines)

    def compare_units(self, unit1: dict, unit2: dict) -> str:
        """Compare two units side by side."""
        lines = []
        lines.append(f"\n{'='*60}")
        lines.append(f"{'UNIT COMPARISON':^60}")
        lines.append(f"{'='*60}")

        # Header
        n1, n2 = unit1["name"][:25], unit2["name"][:25]
        lines.append(f"{'Stat':<15} {n1:<22} {n2:<22}")
        lines.append("-" * 60)

        # Stats comparison
        stats = [
            ("HP", "hit_points"),
            ("Speed", "speed"),
            ("Range", "range"),
            ("Reload", "reload_time"),
            ("Accuracy", "accuracy"),
        ]

        for label, key in stats:
            v1 = unit1.get(key, "-")
            v2 = unit2.get(key, "-")
            lines.append(f"{label:<15} {str(v1):<22} {str(v2):<22}")

        # Cost
        c1 = ", ".join(f"{v}{k[0]}" for k, v in unit1.get("cost", {}).items())
        c2 = ", ".join(f"{v}{k[0]}" for k, v in unit2.get("cost", {}).items())
        lines.append(f"{'Cost':<15} {c1 or '-':<22} {c2 or '-':<22}")

        # Armor
        def get_armor(u):
            armors = u.get("armors", [])
            m = next((a["amount"] for a in armors if a["class"] == 4), 0)
            p = next((a["amount"] for a in armors if a["class"] == 3), 0)
            return f"{m}/{p}"

        lines.append(f"{'Armor (m/p)':<15} {get_armor(unit1):<22} {get_armor(unit2):<22}")

        # Main attack
        def get_attack(u):
            attacks = u.get("attacks", [])
            if attacks:
                main = attacks[0]
                return f"{main['amount']} ({main['class_name'][:10]})"
            return "-"

        lines.append(f"{'Main Attack':<15} {get_attack(unit1):<22} {get_attack(unit2):<22}")

        return "\n".join(lines)

    def find_counters(self, unit: dict) -> dict:
        """Find units that counter or are countered by this unit."""
        # Get armor classes this unit has
        armor_classes = set(a["class"] for a in unit.get("armors", []))

        # Find units with bonus damage against these armor classes
        counters = []
        countered_by = []

        for other in self.units:
            if other["id"] == unit["id"]:
                continue
            if other["class"] in [3, 11, 15, 7, 8, 9, 10, 29, 38]:  # Skip buildings, resources, etc.
                continue

            # Check if other unit has bonus vs this unit's armor classes
            for atk in other.get("attacks", []):
                if atk["class"] in armor_classes and atk["amount"] > 0 and atk["class"] not in [3, 4]:
                    countered_by.append({
                        "unit": other,
                        "bonus": atk["amount"],
                        "class": atk["class_name"]
                    })
                    break

            # Check if this unit has bonus vs other unit's armor classes
            other_armors = set(a["class"] for a in other.get("armors", []))
            for atk in unit.get("attacks", []):
                if atk["class"] in other_armors and atk["amount"] > 0 and atk["class"] not in [3, 4]:
                    counters.append({
                        "unit": other,
                        "bonus": atk["amount"],
                        "class": atk["class_name"]
                    })
                    break

        return {
            "counters": sorted(counters, key=lambda x: x["bonus"], reverse=True)[:10],
            "countered_by": sorted(countered_by, key=lambda x: x["bonus"], reverse=True)[:10]
        }

    def list_by_class(self, class_name: str) -> list:
        """List all units of a specific class."""
        class_name = class_name.lower()
        return [u for u in self.units if class_name in u["class_name"].lower()]


def main():
    data = AoE2Data()

    if len(sys.argv) < 2:
        # Interactive mode
        print("\nAoE2 Data Explorer")
        print("==================")
        print(f"Loaded {len(data.units)} units, {len(data.techs)} technologies, {len(data.civs)} civilizations")
        print("\nCommands:")
        print("  search <query>     - Search units by name")
        print("  unit <id>          - Get unit by ID")
        print("  compare <id1> <id2> - Compare two units")
        print("  counters <id>      - Find counters for a unit")
        print("  class <name>       - List units by class (e.g., cavalry, infantry)")
        print("  quit               - Exit")

        while True:
            try:
                cmd = input("\n> ").strip().split()
                if not cmd:
                    continue

                action = cmd[0].lower()

                if action in ["quit", "exit", "q"]:
                    break
                elif action == "search" and len(cmd) > 1:
                    query = " ".join(cmd[1:])
                    results = data.search_units(query)
                    if results:
                        print(f"\nFound {len(results)} units:")
                        for u in results[:20]:
                            print(f"  [{u['id']:4d}] {u['name']:<25} HP:{u['hit_points']:3d} Class:{u['class_name']}")
                    else:
                        print("No units found.")
                elif action == "unit" and len(cmd) > 1:
                    try:
                        unit_id = int(cmd[1])
                        unit = data.get_unit(unit_id)
                        if unit:
                            print(data.format_unit(unit))
                        else:
                            print(f"Unit ID {unit_id} not found.")
                    except ValueError:
                        # Try by name
                        name = " ".join(cmd[1:])
                        results = data.search_units(name)
                        if results:
                            print(data.format_unit(results[0]))
                        else:
                            print(f"Unit '{name}' not found.")
                elif action == "compare" and len(cmd) > 2:
                    try:
                        id1, id2 = int(cmd[1]), int(cmd[2])
                        u1, u2 = data.get_unit(id1), data.get_unit(id2)
                        if u1 and u2:
                            print(data.compare_units(u1, u2))
                        else:
                            print("One or both units not found.")
                    except ValueError:
                        print("Usage: compare <id1> <id2>")
                elif action == "counters" and len(cmd) > 1:
                    try:
                        unit_id = int(cmd[1])
                        unit = data.get_unit(unit_id)
                        if unit:
                            result = data.find_counters(unit)
                            print(f"\n{unit['name']} counters:")
                            for c in result["counters"][:10]:
                                print(f"  {c['unit']['name']:<25} (+{c['bonus']} vs {c['class']})")
                            print(f"\n{unit['name']} is countered by:")
                            for c in result["countered_by"][:10]:
                                print(f"  {c['unit']['name']:<25} (+{c['bonus']} vs {c['class']})")
                        else:
                            print(f"Unit ID {unit_id} not found.")
                    except ValueError:
                        print("Usage: counters <id>")
                elif action == "class" and len(cmd) > 1:
                    class_name = " ".join(cmd[1:])
                    results = data.list_by_class(class_name)
                    if results:
                        print(f"\n{len(results)} {class_name} units:")
                        for u in results[:30]:
                            print(f"  [{u['id']:4d}] {u['name']:<25} HP:{u['hit_points']:3d}")
                    else:
                        print(f"No units found for class '{class_name}'.")
                else:
                    print("Unknown command. Type 'quit' to exit.")

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

    else:
        # Command line mode
        action = sys.argv[1].lower()

        if action == "search" and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
            results = data.search_units(query)
            for u in results[:20]:
                print(f"[{u['id']:4d}] {u['name']:<25} HP:{u['hit_points']:3d} Class:{u['class_name']}")

        elif action == "unit" and len(sys.argv) > 2:
            try:
                unit_id = int(sys.argv[2])
                unit = data.get_unit(unit_id)
                if unit:
                    print(data.format_unit(unit))
            except ValueError:
                name = " ".join(sys.argv[2:])
                results = data.search_units(name)
                if results:
                    print(data.format_unit(results[0]))

        elif action == "compare" and len(sys.argv) > 3:
            id1, id2 = int(sys.argv[2]), int(sys.argv[3])
            u1, u2 = data.get_unit(id1), data.get_unit(id2)
            if u1 and u2:
                print(data.compare_units(u1, u2))

        elif action == "counters" and len(sys.argv) > 2:
            unit_id = int(sys.argv[2])
            unit = data.get_unit(unit_id)
            if unit:
                result = data.find_counters(unit)
                print(f"\n{unit['name']} counters:")
                for c in result["counters"][:10]:
                    print(f"  {c['unit']['name']:<25} (+{c['bonus']} vs {c['class']})")
                print(f"\n{unit['name']} is countered by:")
                for c in result["countered_by"][:10]:
                    print(f"  {c['unit']['name']:<25} (+{c['bonus']} vs {c['class']})")


if __name__ == "__main__":
    main()
