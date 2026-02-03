#!/usr/bin/env python3
"""
Flexible Unit Comparison Tool

Dynamically analyzes any unit across all civilizations by:
1. Loading the unit's base stats
2. Finding all techs that affect this unit (by ID or class)
3. Finding civ-specific bonuses (C-Bonus techs) that affect this unit
4. Calculating final stats for each civ
5. Comparing and ranking civs

Usage:
    python unit_comparison.py <unit_id_or_name> [--age castle|imperial]

Examples:
    python unit_comparison.py 38              # Knight by ID
    python unit_comparison.py "Knight"        # Knight by name
    python unit_comparison.py "Knight" --age castle
"""

import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Attribute IDs used in effects
ATTR_HP = 0
ATTR_LOS = 1
ATTR_GARRISON = 2
ATTR_RADIUS_1 = 3
ATTR_RADIUS_2 = 4
ATTR_SPEED = 5
ATTR_ROTATION = 6
ATTR_ARMOR = 8
ATTR_ATTACK = 9
ATTR_RELOAD_TIME = 10
ATTR_ACCURACY = 11
ATTR_RANGE = 12
ATTR_WORK_RATE = 13
ATTR_RESOURCE_CARRY = 14
ATTR_PROJECTILE_UNIT = 16
ATTR_ICON = 17
ATTR_PROJECTILE_COUNT = 19
ATTR_PROJECTILE_COUNT_CHANGE = 20
ATTR_MIN_RANGE = 23
ATTR_STORAGE = 32
ATTR_BLAST_LEVEL = 33
ATTR_HEALING_RATE = 37
ATTR_TRAIN_TIME = 101
ATTR_COST = 100
ATTR_GOLD_COST = 105  # Gold cost specifically (Portuguese bonus)
ATTR_FOOD_COST = 103  # Food cost specifically
ATTR_WOOD_COST = 104  # Wood cost specifically

# Standard blacksmith/stable techs by age
CASTLE_AGE_TECHS = {
    67,   # Forging
    81,   # Scale Barding Armor
    82,   # Chain Barding Armor
    435,  # Bloodlines
    39,   # Husbandry
    74,   # Scale Mail
    76,   # Chain Mail
    211,  # Padded Archer Armor
    212,  # Leather Archer Armor
}

IMPERIAL_AGE_TECHS = {
    68,   # Iron Casting
    75,   # Blast Furnace
    80,   # Plate Barding Armor
    77,   # Plate Mail Armor
    219,  # Ring Archer Armor
    209,  # Cavalier
    265,  # Paladin
}

# Civ ID to name mapping (from dat file)
CIV_ID_TO_NAME = {
    0: "Gaia", 1: "Britons", 2: "Franks", 3: "Goths", 4: "Teutons",
    5: "Japanese", 6: "Chinese", 7: "Byzantines", 8: "Persians", 9: "Saracens",
    10: "Turks", 11: "Vikings", 12: "Mongols", 13: "Celts", 14: "Spanish",
    15: "Aztecs", 16: "Mayans", 17: "Huns", 18: "Koreans", 19: "Italians",
    20: "Indians", 21: "Incas", 22: "Magyars", 23: "Slavs", 24: "Portuguese",
    25: "Ethiopians", 26: "Malians", 27: "Berbers", 28: "Khmer", 29: "Malay",
    30: "Burmese", 31: "Vietnamese", 32: "Bulgarians", 33: "Tatars", 34: "Cumans",
    35: "Lithuanians", 36: "Burgundians", 37: "Sicilians", 38: "Poles", 39: "Bohemians",
    40: "Dravidians", 41: "Bengalis", 42: "Gurjaras", 43: "Romans", 44: "Armenians",
    45: "Georgians",
}

# Reverse mapping
CIV_NAME_TO_ID = {v: k for k, v in CIV_ID_TO_NAME.items()}


@dataclass
class UnitStats:
    """Mutable unit stats that can be modified by effects."""
    hp: float = 0
    attack: float = 0
    melee_armor: float = 0
    pierce_armor: float = 0
    speed: float = 0
    range: float = 0
    reload_time: float = 0
    accuracy: float = 0
    los: float = 0
    cost_food: float = 0
    cost_wood: float = 0
    cost_gold: float = 0
    cost_stone: float = 0
    train_time: float = 0
    attacks: dict = field(default_factory=dict)
    armors: dict = field(default_factory=dict)

    def copy(self):
        return UnitStats(
            hp=self.hp, attack=self.attack,
            melee_armor=self.melee_armor, pierce_armor=self.pierce_armor,
            speed=self.speed, range=self.range,
            reload_time=self.reload_time, accuracy=self.accuracy,
            los=self.los, cost_food=self.cost_food,
            cost_wood=self.cost_wood, cost_gold=self.cost_gold,
            cost_stone=self.cost_stone, train_time=self.train_time,
            attacks=self.attacks.copy(), armors=self.armors.copy(),
        )


class UnitAnalyzer:
    def __init__(self):
        self.load_data()

    def load_data(self):
        """Load all game data."""
        self.units = {u["id"]: u for u in json.load(open(OUTPUT_DIR / "units.json"))}
        self.units_by_name = {u["name"].lower(): u for u in self.units.values()}
        self.techs = {t["id"]: t for t in json.load(open(OUTPUT_DIR / "technologies.json"))}
        self.civs = json.load(open(OUTPUT_DIR / "civilizations.json"))
        self.civ_tech_trees = {c["name"]: c for c in json.load(open(OUTPUT_DIR / "civ_tech_trees.json"))}
        self.effects = {e["id"]: e for e in json.load(open(OUTPUT_DIR / "effects.json"))}
        self.tech_effects = json.load(open(OUTPUT_DIR / "tech_effects.json"))

        # Index tech effects by tech_id
        self.tech_effect_map = {te["tech_id"]: te for te in self.tech_effects}

        # Index civ-specific techs (C-Bonus and others with civ != -1)
        self.civ_bonus_techs = {}  # civ_id -> list of tech_ids
        for tech_id, tech in self.techs.items():
            civ_id = tech.get("civ", -1)
            if civ_id >= 0:
                if civ_id not in self.civ_bonus_techs:
                    self.civ_bonus_techs[civ_id] = []
                self.civ_bonus_techs[civ_id].append(tech_id)

    def get_unit(self, unit_id_or_name) -> Optional[dict]:
        """Get unit by ID or name."""
        if isinstance(unit_id_or_name, int):
            return self.units.get(unit_id_or_name)
        name_lower = str(unit_id_or_name).lower()
        if name_lower in self.units_by_name:
            return self.units_by_name[name_lower]
        for name, unit in self.units_by_name.items():
            if name_lower in name:
                return unit
        return None

    def get_base_stats(self, unit: dict) -> UnitStats:
        """Extract base stats from unit data."""
        stats = UnitStats()
        stats.hp = unit.get("hit_points", 0)
        stats.speed = unit.get("speed", 0)
        stats.range = unit.get("range", 0)
        stats.reload_time = unit.get("reload_time", 0)
        stats.accuracy = unit.get("accuracy", 0)
        stats.los = unit.get("line_of_sight", 0)
        stats.train_time = unit.get("train_time", 0)

        cost = unit.get("cost", {})
        stats.cost_food = cost.get("food", 0)
        stats.cost_wood = cost.get("wood", 0)
        stats.cost_gold = cost.get("gold", 0)
        stats.cost_stone = cost.get("stone", 0)

        stats.melee_armor = unit.get("displayed_melee_armor", 0)
        stats.pierce_armor = unit.get("displayed_pierce_armor", 0)
        stats.attack = unit.get("displayed_attack", 0)

        for atk in unit.get("attacks", []):
            stats.attacks[atk["class"]] = atk["amount"]
        for arm in unit.get("armors", []):
            stats.armors[arm["class"]] = arm["amount"]

        return stats

    def get_disabled_techs(self, civ_name: str) -> set:
        """Get set of disabled tech IDs for a civilization."""
        civ_data = self.civ_tech_trees.get(civ_name, {})
        disabled = civ_data.get("disabled_techs", [])
        return set(t["id"] for t in disabled if isinstance(t, dict))

    def is_unit_disabled(self, civ_name: str, unit_name: str) -> bool:
        """Check if a unit is disabled for a civilization."""
        civ_data = self.civ_tech_trees.get(civ_name, {})
        disabled = civ_data.get("disabled_techs", [])
        # Check for "(make avail)" techs which indicate unit is disabled
        for t in disabled:
            if isinstance(t, dict):
                tech_name = t.get("name", "").lower()
                if unit_name.lower() in tech_name and "make avail" in tech_name:
                    return True
        return False

    def effect_applies_to_unit(self, cmd: dict, unit_id: int, unit_class: int) -> bool:
        """Check if an effect command applies to a specific unit."""
        a = cmd.get("a", -999)
        b = cmd.get("b", -999)

        # Direct unit match
        if a == unit_id:
            return True

        # Class match (a=-1 means use class in b)
        if a == -1 and b == unit_class:
            return True

        return False

    def apply_effect_command(self, cmd: dict, stats: UnitStats, unit_id: int, unit_class: int) -> bool:
        """Apply a single effect command to unit stats. Returns True if applied."""
        if not self.effect_applies_to_unit(cmd, unit_id, unit_class):
            return False

        cmd_type = cmd.get("type", 0)
        c = cmd.get("c", 0)
        d = cmd.get("d", 0)

        if cmd_type == 0:  # SET_ATTRIBUTE
            self._set_attribute(stats, c, d)
        elif cmd_type == 4:  # ADD_ATTRIBUTE
            self._add_attribute(stats, c, d)
        elif cmd_type == 5:  # MULTIPLY_ATTRIBUTE
            self._multiply_attribute(stats, c, d)
        else:
            return False
        return True

    def _decode_armor_attack_value(self, d: float) -> tuple:
        """Decode armor/attack value: class in high byte, amount in low byte."""
        d_int = int(d)
        if d_int >= 0:
            armor_class = d_int // 256
            amount = d_int % 256
            if amount > 127:
                amount = amount - 256
        else:
            d_int = abs(d_int)
            armor_class = d_int // 256
            amount = -(d_int % 256)
        return armor_class, amount

    def _set_attribute(self, stats: UnitStats, attr: int, value: float):
        if attr == ATTR_HP:
            stats.hp = value
        elif attr == ATTR_SPEED:
            stats.speed = value
        elif attr == ATTR_RANGE:
            stats.range = value
        elif attr == ATTR_RELOAD_TIME:
            stats.reload_time = value

    def _add_attribute(self, stats: UnitStats, attr: int, value: float):
        if attr == ATTR_HP:
            stats.hp += value
        elif attr == ATTR_SPEED:
            stats.speed += value
        elif attr == ATTR_RANGE:
            stats.range += value
        elif attr == ATTR_RELOAD_TIME:
            stats.reload_time += value
        elif attr == ATTR_LOS:
            stats.los += value
        elif attr == ATTR_TRAIN_TIME:
            stats.train_time += value
        elif attr == ATTR_ATTACK:
            atk_class, amount = self._decode_armor_attack_value(value)
            if atk_class in stats.attacks:
                stats.attacks[atk_class] += amount
            if atk_class == 4:  # Base melee
                stats.attack += amount
        elif attr == ATTR_ARMOR:
            arm_class, amount = self._decode_armor_attack_value(value)
            if arm_class in stats.armors:
                stats.armors[arm_class] += amount
            if arm_class == 4:  # Base melee
                stats.melee_armor += amount
            elif arm_class == 3:  # Base pierce
                stats.pierce_armor += amount

    def _multiply_attribute(self, stats: UnitStats, attr: int, value: float):
        if attr == ATTR_HP:
            stats.hp *= value
        elif attr == ATTR_SPEED:
            stats.speed *= value
        elif attr == ATTR_RANGE:
            stats.range *= value
        elif attr == ATTR_RELOAD_TIME:
            stats.reload_time *= value
        elif attr == ATTR_LOS:
            stats.los *= value
        elif attr == ATTR_TRAIN_TIME:
            stats.train_time *= value
        elif attr == ATTR_COST:
            # Multiply all costs
            stats.cost_food *= value
            stats.cost_wood *= value
            stats.cost_gold *= value
            stats.cost_stone *= value
        elif attr == ATTR_GOLD_COST:
            stats.cost_gold *= value
        elif attr == ATTR_FOOD_COST:
            stats.cost_food *= value
        elif attr == ATTR_WOOD_COST:
            stats.cost_wood *= value

    def get_civ_bonus_techs_for_unit(self, civ_name: str, unit_id: int, unit_class: int) -> list:
        """Get civ-specific bonus techs that affect this unit."""
        civ_id = CIV_NAME_TO_ID.get(civ_name, -1)
        if civ_id < 0:
            return []

        relevant = []
        tech_ids = self.civ_bonus_techs.get(civ_id, [])

        for tech_id in tech_ids:
            if tech_id not in self.tech_effect_map:
                continue

            te = self.tech_effect_map[tech_id]
            for cmd in te.get("commands", []):
                if self.effect_applies_to_unit(cmd, unit_id, unit_class):
                    relevant.append(te)
                    break

        return relevant

    def calculate_civ_stats(self, unit: dict, civ_name: str, max_age: str = "imperial") -> dict:
        """Calculate unit stats for a specific civilization."""
        unit_id = unit["id"]
        unit_class = unit["class"]
        unit_name = unit["name"]

        # Check if this unit is disabled for this civ
        unit_disabled = self.is_unit_disabled(civ_name, unit_name)
        if unit_disabled:
            return {
                "civ": civ_name,
                "stats": None,
                "base_stats": None,
                "applied_techs": [],
                "applied_bonuses": [],
                "unit_disabled": True,
            }

        stats = self.get_base_stats(unit)
        base_stats = stats.copy()

        disabled_techs = self.get_disabled_techs(civ_name)
        applied_techs = []
        applied_bonuses = []

        # 1. Apply civ-specific bonus techs (C-Bonus techs)
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(civ_name, unit_id, unit_class)
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")

            # Skip if it's a unique tech that needs research (has cost)
            tech_data = self.techs.get(te["tech_id"], {})
            if tech_data.get("cost") and not tech_name.startswith("C-Bonus"):
                continue

            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # 2. Apply standard techs (blacksmith, stable)
        standard_techs = CASTLE_AGE_TECHS if max_age == "castle" else (CASTLE_AGE_TECHS | IMPERIAL_AGE_TECHS)

        for tech_id in sorted(standard_techs):
            tech_name = self.techs.get(tech_id, {}).get("name", f"Tech {tech_id}")

            if tech_id in disabled_techs:
                applied_techs.append(f"{tech_name}: DISABLED")
                continue

            if tech_id in self.tech_effect_map:
                te = self.tech_effect_map[tech_id]
                tech_applied = False
                for cmd in te.get("commands", []):
                    if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                        tech_applied = True

                if tech_applied:
                    applied_techs.append(tech_name)

        # Round values
        stats.hp = round(stats.hp)
        stats.speed = round(stats.speed, 2)
        stats.attack = round(stats.attack)
        stats.melee_armor = round(stats.melee_armor)
        stats.pierce_armor = round(stats.pierce_armor)
        stats.cost_food = round(stats.cost_food)
        stats.cost_wood = round(stats.cost_wood)
        stats.cost_gold = round(stats.cost_gold)
        stats.train_time = round(stats.train_time)

        return {
            "civ": civ_name,
            "stats": stats,
            "base_stats": base_stats,
            "applied_techs": applied_techs,
            "applied_bonuses": applied_bonuses,
            "unit_disabled": False,
        }

    def compare_unit_across_civs(self, unit_id_or_name, max_age: str = "imperial"):
        """Compare a unit across all civilizations."""
        unit = self.get_unit(unit_id_or_name)
        if not unit:
            print(f"Unit not found: {unit_id_or_name}")
            return None

        print(f"\nAnalyzing: {unit['name']} (ID: {unit['id']}, Class: {unit['class_name']})")
        print(f"Age: {max_age.title()}")

        results = []
        for civ in self.civs:
            civ_name = civ["name"]
            result = self.calculate_civ_stats(unit, civ_name, max_age)
            results.append(result)

        return results

    def print_comparison(self, results: list, unit: dict):
        """Print formatted comparison table."""
        # Separate enabled and disabled civs
        enabled = [r for r in results if not r.get("unit_disabled", False)]
        disabled = [r for r in results if r.get("unit_disabled", False)]

        def power_score(r):
            s = r["stats"]
            if s is None:
                return 0
            return s.hp * s.attack

        results_sorted = sorted(enabled, key=power_score, reverse=True)

        print("\n" + "=" * 130)
        print(f"{'Civ':<15} {'HP':>5} {'Atk':>5} {'M.Arm':>6} {'P.Arm':>6} {'Speed':>6} {'Cost':>12} {'Train':>6} {'Civ Bonuses':<35}")
        print("-" * 130)

        for r in results_sorted:
            s = r["stats"]
            cost = f"{int(s.cost_food)}F/{int(s.cost_gold)}G"

            bonuses = r["applied_bonuses"]
            bonus_str = ", ".join(b.replace("C-Bonus, ", "") for b in bonuses)[:35] if bonuses else "-"

            print(f"{r['civ']:<15} {s.hp:>5.0f} {s.attack:>5.0f} {s.melee_armor:>6.0f} {s.pierce_armor:>6.0f} {s.speed:>6.2f} {cost:>12} {s.train_time:>5.0f}s {bonus_str:<35}")

        # Print disabled civs at the bottom
        if disabled:
            print("-" * 130)
            for r in sorted(disabled, key=lambda x: x["civ"]):
                print(f"{r['civ']:<15} {'--NO UNIT--':^60}")

    def print_detailed(self, result: dict):
        """Print detailed breakdown for one civ."""
        print(f"\n{result['civ']} Breakdown:")
        print("-" * 50)

        base = result["base_stats"]
        final = result["stats"]

        print(f"Base:  HP={base.hp:.0f}, Atk={base.attack:.0f}, Armor={base.melee_armor:.0f}/{base.pierce_armor:.0f}, Speed={base.speed:.2f}")

        if result["applied_bonuses"]:
            print("\nCiv Bonuses:")
            for bonus in result["applied_bonuses"]:
                print(f"  + {bonus}")

        if result["applied_techs"]:
            print("\nTechs:")
            for tech in result["applied_techs"]:
                print(f"  + {tech}")

        print(f"\nFinal: HP={final.hp:.0f}, Atk={final.attack:.0f}, Armor={final.melee_armor:.0f}/{final.pierce_armor:.0f}, Speed={final.speed:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Compare unit stats across civilizations")
    parser.add_argument("unit", help="Unit ID or name (e.g., 38 or 'Knight')")
    parser.add_argument("--age", choices=["castle", "imperial"], default="castle",
                        help="Maximum age for tech availability (default: castle)")
    parser.add_argument("--detail", nargs="*", help="Show detailed breakdown for specific civs")
    args = parser.parse_args()

    analyzer = UnitAnalyzer()

    try:
        unit_id = int(args.unit)
    except ValueError:
        unit_id = args.unit

    unit = analyzer.get_unit(unit_id)
    if not unit:
        print(f"Unit not found: {args.unit}")
        return

    results = analyzer.compare_unit_across_civs(unit_id, args.age)
    if results:
        analyzer.print_comparison(results, unit)

        if args.detail:
            for civ_name in args.detail:
                for r in results:
                    if r["civ"].lower() == civ_name.lower():
                        analyzer.print_detailed(r)
                        break


if __name__ == "__main__":
    main()
