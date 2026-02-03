#!/usr/bin/env python3
"""
Generate CSV files for each unit line across all civilizations.

Outputs fully upgraded Castle Age stats for each unit, showing which civs
have access to each unit and their civ-specific bonuses.

Usage:
    python generate_unit_csvs.py
"""

import json
import csv
from pathlib import Path
from dataclasses import dataclass, field

OUTPUT_DIR = Path(__file__).parent / "output"
CSV_OUTPUT_DIR = Path(__file__).parent / "unit_output"

# Attribute IDs used in effects
ATTR_HP = 0
ATTR_LOS = 1
ATTR_SPEED = 5
ATTR_ARMOR = 8
ATTR_ATTACK = 9
ATTR_RELOAD_TIME = 10
ATTR_ACCURACY = 11
ATTR_RANGE = 12
ATTR_WORK_RATE = 13
ATTR_TRAIN_TIME = 101
ATTR_COST = 100
ATTR_FOOD_COST = 103
ATTR_WOOD_COST = 104
ATTR_GOLD_COST = 105

# Effect command types
CMD_SET_ATTRIBUTE = 0
CMD_ADD_ATTRIBUTE = 4
CMD_MULTIPLY_ATTRIBUTE = 5
CMD_UPGRADE_UNIT = 3

# Unit availability tech IDs - these techs enable units when NOT disabled
# If a civ has these in disabled_techs, they don't have access to the unit
UNIT_AVAILABILITY_TECHS = {
    # Tech ID -> unit display name it enables
    235: "Camel Rider",  # Make Camels Available
    166: "Knight",  # Knight (make avail)
    175: "Paladin",  # Paladin (make avail)
    192: "Cavalry Archer",  # Cav Archer (make avail)
    433: "Eagle Warrior",  # Eagle Warrior (make avail)
    480: "Elephant Archer",  # Elephant Archer (make avail)
    630: "Battle Elephant",  # Battle Elephant (make avail)
    714: "Steppe Lancer",  # Steppe Lancer (make avail)
    837: "Armored Elephant",  # Armored Elephant (make avail)
    162: "Battering Ram",  # Bat Ram (make avail)
    981: "Fire Lancer",  # Fire Lancer (make avail)
    979: "Rocket Cart",  # Rocket Cart (make avail)
    1032: "Hei-Kuang Cavalry",  # Hei-Kuang Cavalry (make avail)
}

# Upgrade techs that may be disabled (preventing access to upgraded units)
UPGRADE_TECHS = {
    # Tech ID -> (unit it upgrades TO, base unit name)
    236: ("Heavy Camel Rider", "Camel Rider"),
    218: ("Heavy Cavalry Archer", "Cavalry Archer"),
    237: ("Arbalester", "Crossbowman"),
    265: ("Paladin", "Cavalier"),
    209: ("Cavalier", "Knight"),
    428: ("Hussar", "Light Cavalry"),
    786: ("Winged Hussar", "Hussar"),
    631: ("Elite Battle Elephant", "Battle Elephant"),
    715: ("Elite Steppe Lancer", "Steppe Lancer"),
    481: ("Elite Elephant Archer", "Elephant Archer"),
    320: ("Siege Onager", "Onager"),
    255: ("Siege Ram", "Capped Ram"),
    384: ("Elite Eagle Warrior", "Eagle Warrior"),
}

# Castle Age units to analyze (unit_id, display_name, unit_class)
# These are the main Castle Age military units
CASTLE_AGE_UNITS = {
    "swordsmen": (76, "Long Swordsman", 6),  # HVSWD - Castle Age militia line
    "pikeman": (358, "Pikeman", 6),  # ISPKM - Castle Age spear line
    "light_cav": (546, "Light Cavalry", 12),  # LTCAV - Castle Age scout line
    "knight": (38, "Knight", 12),  # KNGHT - Castle Age knight
    "camel": (329, "Camel Rider", 12),  # CVLRY - Castle Age camel
    "elephant": (1132, "Battle Elephant", 12),  # BATELE - Castle Age elephant
    "steppe_lancer": (1370, "Steppe Lancer", 12),  # SLANCER - Castle Age steppe lancer
    "crossbow": (24, "Crossbowman", 0),  # CARCH - Castle Age archer line
    "elite_skirm": (6, "Elite Skirmisher", 0),  # HXBOW - Castle Age skirm
    "cav_archer": (39, "Cavalry Archer", 36),  # CVRCH - Castle Age cav archer
    "elephant_archer": (873, "Elephant Archer", 36),  # ELEAR - Castle Age elephant archer
    "ram": (35, "Battering Ram", 13),  # BTRAM - Castle Age ram
    "mangonel": (280, "Mangonel", 13),  # MANGO - Castle Age mangonel
    "scorpion": (279, "Scorpion", 55),  # SCBAL - Castle Age scorpion
    "fire_archer": (1968, "Fire Archer", 0),  # FIREARCHER - Castle Age fire archer (3K DLC)
}


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
    upgrade_cost: float = 0
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
            upgrade_cost=self.upgrade_cost,
            attacks=self.attacks.copy(), armors=self.armors.copy(),
        )

    def attack_rate(self) -> float:
        """Calculate attacks per second from reload time."""
        if self.reload_time > 0:
            return 1.0 / self.reload_time
        return 0.0


class UnitAnalyzer:
    def __init__(self):
        self.load_data()
        self._tech_cache = {}

    def load_data(self):
        """Load all game data."""
        self.units = {u["id"]: u for u in json.load(open(OUTPUT_DIR / "units.json"))}
        self.techs = {t["id"]: t for t in json.load(open(OUTPUT_DIR / "technologies.json"))}
        self.civs = json.load(open(OUTPUT_DIR / "civilizations.json"))
        self.civ_tech_trees = {c["name"]: c for c in json.load(open(OUTPUT_DIR / "civ_tech_trees.json"))}
        self.effects = {e["id"]: e for e in json.load(open(OUTPUT_DIR / "effects.json"))}
        self.tech_effects = json.load(open(OUTPUT_DIR / "tech_effects.json"))

        tech_ages_file = OUTPUT_DIR / "tech_ages.json"
        if tech_ages_file.exists():
            tech_ages_data = json.load(open(tech_ages_file))
            self.tech_ages = tech_ages_data.get("techs", {})
        else:
            self.tech_ages = {}

        self.tech_effect_map = {te["tech_id"]: te for te in self.tech_effects}

        self.civ_bonus_techs = {}
        for tech_id, tech in self.techs.items():
            civ_id = tech.get("civ", -1)
            if civ_id >= 0:
                if civ_id not in self.civ_bonus_techs:
                    self.civ_bonus_techs[civ_id] = []
                self.civ_bonus_techs[civ_id].append(tech_id)

        self.civ_name_to_id = {c["name"]: c["id"] for c in self.civs}

        # Build disabled tech lookup per civ
        self.civ_disabled_tech_ids = {}
        for civ_name, civ_data in self.civ_tech_trees.items():
            disabled = set()
            for t in civ_data.get("disabled_techs", []):
                if isinstance(t, dict):
                    disabled.add(t["id"])
            self.civ_disabled_tech_ids[civ_name] = disabled

    def has_unit_access(self, civ_name: str, unit_name: str) -> bool:
        """Check if a civilization has access to a unit."""
        disabled_techs = self.civ_disabled_tech_ids.get(civ_name, set())

        # Check if the unit's availability tech is disabled
        for tech_id, enabled_unit in UNIT_AVAILABILITY_TECHS.items():
            if enabled_unit.lower() == unit_name.lower():
                if tech_id in disabled_techs:
                    return False

        # Special cases for units that share availability with others
        # Camel line
        if unit_name in ["Camel Rider", "Heavy Camel Rider"]:
            if 235 in disabled_techs:  # Make Camels Available
                return False

        # Knight line
        if unit_name in ["Knight", "Cavalier", "Paladin"]:
            if 166 in disabled_techs:  # Knight (make avail)
                return False

        # Cavalry Archer line
        if unit_name in ["Cavalry Archer", "Heavy Cavalry Archer"]:
            if 192 in disabled_techs:  # Cav Archer (make avail)
                return False

        # Elephant Archer line
        if unit_name in ["Elephant Archer", "Elite Elephant Archer"]:
            if 480 in disabled_techs:  # Elephant Archer (make avail)
                return False

        # Battle Elephant line
        if unit_name in ["Battle Elephant", "Elite Battle Elephant"]:
            if 630 in disabled_techs:  # Battle Elephant (make avail)
                return False

        # Steppe Lancer line
        if unit_name in ["Steppe Lancer", "Elite Steppe Lancer"]:
            if 714 in disabled_techs:  # Steppe Lancer (make avail)
                return False

        # Ram line - most civs have rams
        if unit_name in ["Battering Ram", "Capped Ram", "Siege Ram"]:
            if 162 in disabled_techs:  # Bat Ram (make avail)
                return False

        return True

    def get_unit(self, unit_id: int):
        """Get unit by ID."""
        return self.units.get(unit_id)

    def find_techs_affecting_unit(self, unit_id: int, unit_class: int) -> set:
        """Find all Castle Age techs that affect this unit."""
        cache_key = (unit_id, unit_class)
        if cache_key in self._tech_cache:
            return self._tech_cache[cache_key]

        relevant_techs = set()
        max_age_num = 3  # Castle Age

        for te in self.tech_effects:
            tech_id = te["tech_id"]
            tech_data = self.techs.get(tech_id, {})

            # Skip civ-specific techs
            if tech_data.get("civ", -1) >= 0:
                continue

            affects_unit = False

            for cmd in te.get("commands", []):
                cmd_type = cmd.get("type", -1)
                a = cmd.get("a", -999)
                b = cmd.get("b", -999)

                if cmd_type in (CMD_SET_ATTRIBUTE, CMD_ADD_ATTRIBUTE, CMD_MULTIPLY_ATTRIBUTE):
                    if a == unit_id or (a == -1 and b == unit_class):
                        affects_unit = True
                        break

            if affects_unit:
                tech_id_str = str(tech_id)
                if tech_id_str in self.tech_ages:
                    tech_age_data = self.tech_ages[tech_id_str]
                    tech_age = tech_age_data.get("age", 4)
                    if tech_age <= max_age_num:
                        relevant_techs.add(tech_id)

        self._tech_cache[cache_key] = relevant_techs
        return relevant_techs

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
        return self.civ_disabled_tech_ids.get(civ_name, set())

    def effect_applies_to_unit(self, cmd: dict, unit_id: int, unit_class: int) -> bool:
        """Check if an effect command applies to a specific unit."""
        a = cmd.get("a", -999)
        b = cmd.get("b", -999)
        if a == unit_id:
            return True
        if a == -1 and b == unit_class:
            return True
        return False

    def apply_effect_command(self, cmd: dict, stats: UnitStats, unit_id: int, unit_class: int) -> bool:
        """Apply a single effect command to unit stats."""
        if not self.effect_applies_to_unit(cmd, unit_id, unit_class):
            return False

        cmd_type = cmd.get("type", 0)
        c = cmd.get("c", 0)
        d = cmd.get("d", 0)

        if cmd_type == CMD_SET_ATTRIBUTE:
            self._set_attribute(stats, c, d)
        elif cmd_type == CMD_ADD_ATTRIBUTE:
            self._add_attribute(stats, c, d)
        elif cmd_type == CMD_MULTIPLY_ATTRIBUTE:
            self._multiply_attribute(stats, c, d)
        else:
            return False
        return True

    def _decode_armor_attack_value(self, d: float) -> tuple:
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
            if atk_class == 4:
                stats.attack += amount
        elif attr == ATTR_ARMOR:
            arm_class, amount = self._decode_armor_attack_value(value)
            if arm_class in stats.armors:
                stats.armors[arm_class] += amount
            if arm_class == 4:
                stats.melee_armor += amount
            elif arm_class == 3:
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
        civ_id = self.civ_name_to_id.get(civ_name, -1)
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

    def calculate_upgrade_cost(self, civ_name: str, relevant_techs: set, disabled_techs: set) -> int:
        """Calculate total upgrade cost for relevant techs."""
        total = 0
        for tech_id in relevant_techs:
            if tech_id in disabled_techs:
                continue
            tech_data = self.techs.get(tech_id, {})
            base_cost = tech_data.get("cost", {})
            total += sum(base_cost.values())
        return total

    def calculate_civ_stats(self, unit: dict, civ_name: str, unit_display_name: str) -> dict:
        """Calculate fully upgraded Castle Age stats for a unit for a specific civ."""
        unit_id = unit["id"]
        unit_class = unit["class"]

        # Check if civ has access to this unit
        has_access = self.has_unit_access(civ_name, unit_display_name)
        if not has_access:
            return {
                "civ": civ_name,
                "stats": None,
                "applied_techs": [],
                "applied_bonuses": [],
                "unit_disabled": True,
            }

        stats = self.get_base_stats(unit)
        disabled_techs = self.get_disabled_techs(civ_name)
        applied_techs = []
        applied_bonuses = []

        # Age gating for civ bonuses
        age_tech_ids = {101: 2, 102: 3, 103: 4}
        max_age_num = 3  # Castle Age

        # Apply civ bonus techs
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(civ_name, unit_id, unit_class)
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            tech_data = self.techs.get(te["tech_id"], {})

            # Skip unique techs (have cost and don't start with C-Bonus)
            if tech_data.get("cost") and not tech_name.startswith("C-Bonus"):
                continue

            # Check age requirements
            required_techs = tech_data.get("required_techs", [])
            bonus_age = 1
            for req_tech in required_techs:
                if req_tech in age_tech_ids:
                    bonus_age = max(bonus_age, age_tech_ids[req_tech])

            if bonus_age > max_age_num:
                continue

            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply standard Castle Age techs
        standard_techs = self.find_techs_affecting_unit(unit_id, unit_class)

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

        # Calculate upgrade cost
        upgrade_cost = self.calculate_upgrade_cost(civ_name, standard_techs, disabled_techs)
        stats.upgrade_cost = upgrade_cost

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
        stats.upgrade_cost = round(stats.upgrade_cost)
        stats.reload_time = round(stats.reload_time, 3)
        stats.range = round(stats.range, 1)

        return {
            "civ": civ_name,
            "stats": stats,
            "applied_techs": applied_techs,
            "applied_bonuses": applied_bonuses,
            "unit_disabled": False,
        }


def generate_csv_for_unit(analyzer: UnitAnalyzer, line_name: str, unit_id: int,
                          unit_display_name: str, unit_class: int):
    """Generate a CSV file for a Castle Age unit across all civs."""
    csv_path = CSV_OUTPUT_DIR / f"{line_name}.csv"

    unit = analyzer.get_unit(unit_id)
    if not unit:
        print(f"  ERROR: Unit ID {unit_id} not found!")
        return None

    # Determine if ranged unit
    is_ranged = unit.get("range", 0) > 0

    # Build header
    if is_ranged:
        fieldnames = [
            "Civilization", "Unit", "HP", "Attack", "Range", "Attack_Speed",
            "Melee_Armor", "Pierce_Armor", "Movement_Speed", "Cost_Food", "Cost_Wood",
            "Cost_Gold", "Creation_Time", "Upgrade_Cost", "Civ_Bonuses", "Has_Unit"
        ]
    else:
        fieldnames = [
            "Civilization", "Unit", "HP", "Attack", "Attack_Speed",
            "Melee_Armor", "Pierce_Armor", "Movement_Speed", "Cost_Food", "Cost_Wood",
            "Cost_Gold", "Creation_Time", "Upgrade_Cost", "Civ_Bonuses", "Has_Unit"
        ]

    rows = []

    for civ in analyzer.civs:
        civ_name = civ["name"]
        result = analyzer.calculate_civ_stats(unit, civ_name, unit_display_name)

        if result["unit_disabled"]:
            row = {
                "Civilization": civ_name,
                "Unit": unit_display_name,
                "HP": "",
                "Attack": "",
                "Attack_Speed": "",
                "Melee_Armor": "",
                "Pierce_Armor": "",
                "Movement_Speed": "",
                "Cost_Food": "",
                "Cost_Wood": "",
                "Cost_Gold": "",
                "Creation_Time": "",
                "Upgrade_Cost": "",
                "Civ_Bonuses": "",
                "Has_Unit": "No",
            }
            if is_ranged:
                row["Range"] = ""
        else:
            stats = result["stats"]
            bonuses = ", ".join(b.replace("C-Bonus, ", "") for b in result["applied_bonuses"])

            row = {
                "Civilization": civ_name,
                "Unit": unit_display_name,
                "HP": int(stats.hp),
                "Attack": int(stats.attack),
                "Attack_Speed": round(stats.attack_rate(), 3),
                "Melee_Armor": int(stats.melee_armor),
                "Pierce_Armor": int(stats.pierce_armor),
                "Movement_Speed": stats.speed,
                "Cost_Food": int(stats.cost_food),
                "Cost_Wood": int(stats.cost_wood),
                "Cost_Gold": int(stats.cost_gold),
                "Creation_Time": int(stats.train_time),
                "Upgrade_Cost": int(stats.upgrade_cost),
                "Civ_Bonuses": bonuses if bonuses else "-",
                "Has_Unit": "Yes",
            }
            if is_ranged:
                row["Range"] = stats.range

        rows.append(row)

    # Write CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Count civs with and without the unit
    has_unit = sum(1 for r in rows if r["Has_Unit"] == "Yes")
    no_unit = sum(1 for r in rows if r["Has_Unit"] == "No")

    print(f"  Generated {csv_path.name} ({has_unit} civs have it, {no_unit} don't)")
    return csv_path


def main():
    print("AoE2 Unit CSV Generator - Castle Age Fully Upgraded")
    print("=" * 60)

    CSV_OUTPUT_DIR.mkdir(exist_ok=True)

    print("\nLoading game data...")
    analyzer = UnitAnalyzer()
    print(f"  Loaded {len(analyzer.units)} units")
    print(f"  Loaded {len(analyzer.civs)} civilizations")
    print(f"  Loaded {len(analyzer.techs)} technologies")

    print("\nGenerating CSV files for Castle Age units...")
    for line_name, (unit_id, unit_display_name, unit_class) in CASTLE_AGE_UNITS.items():
        print(f"\n{line_name} ({unit_display_name}):")
        generate_csv_for_unit(analyzer, line_name, unit_id, unit_display_name, unit_class)

    print("\n" + "=" * 60)
    print(f"Done! CSV files written to: {CSV_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
