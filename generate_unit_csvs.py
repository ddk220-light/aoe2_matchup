#!/usr/bin/env python3
"""
Generate CSV files for each unit line across all civilizations.

Outputs fully upgraded stats for each age (Feudal, Castle, Imperial),
showing which civs have access to each unit and their civ-specific bonuses.

Usage:
    python generate_unit_csvs.py
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

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
UNIT_AVAILABILITY_TECHS = {
    235: "Camel Rider",
    166: "Knight",
    175: "Paladin",
    192: "Cavalry Archer",
    433: "Eagle Warrior",
    480: "Elephant Archer",
    630: "Battle Elephant",
    714: "Steppe Lancer",
    837: "Armored Elephant",
    162: "Battering Ram",
    981: "Fire Lancer",
    979: "Rocket Cart",
    1032: "Hei-Kuang Cavalry",
    85: "Hand Cannoneer",
    188: "Bombard Cannon",
}

# Upgrade techs that may be disabled
UPGRADE_TECHS = {
    # Tech ID -> (unit it upgrades TO, base unit name)
    222: ("Man-at-Arms", "Militia"),
    207: ("Long Swordsman", "Man-at-Arms"),
    217: ("Two-Handed Swordsman", "Long Swordsman"),
    264: ("Champion", "Two-Handed Swordsman"),
    215: ("Pikeman", "Spearman"),
    429: ("Halberdier", "Pikeman"),
    384: ("Elite Eagle Warrior", "Eagle Warrior"),
    98: ("Elite Skirmisher", "Skirmisher"),
    655: ("Imperial Skirmisher", "Elite Skirmisher"),
    428: ("Hussar", "Light Cavalry"),
    786: ("Winged Hussar", "Hussar"),
    209: ("Cavalier", "Knight"),
    265: ("Paladin", "Cavalier"),
    1033: ("Heavy Hei-Kuang Cavalry", "Hei-Kuang Cavalry"),
    236: ("Heavy Camel Rider", "Camel Rider"),
    521: ("Imperial Camel Rider", "Heavy Camel Rider"),
    631: ("Elite Battle Elephant", "Battle Elephant"),
    715: ("Elite Steppe Lancer", "Steppe Lancer"),
    212: ("Crossbowman", "Archer"),
    237: ("Arbalester", "Crossbowman"),
    218: ("Heavy Cavalry Archer", "Cavalry Archer"),
    481: ("Elite Elephant Archer", "Elephant Archer"),
    96: ("Capped Ram", "Battering Ram"),
    255: ("Siege Ram", "Capped Ram"),
    838: ("Siege Elephant", "Armored Elephant"),
    257: ("Onager", "Mangonel"),
    320: ("Siege Onager", "Onager"),
    239: ("Heavy Scorpion", "Scorpion"),
}

# Age constants
FEUDAL_AGE = 2
CASTLE_AGE = 3
IMPERIAL_AGE = 4

# =============================================================================
# UNIT DEFINITIONS BY AGE
# =============================================================================

# Feudal Age units (unit_id, display_name, unit_class)
FEUDAL_AGE_UNITS = {
    "man_at_arms": (93, "Man-at-Arms", 6),
    "spearman": (93, "Spearman", 6),  # Will use ID 93 and check upgrade
    "archer": (4, "Archer", 0),
    "skirmisher": (7, "Skirmisher", 0),
    "scout": (448, "Scout Cavalry", 12),
}

# Castle Age units
CASTLE_AGE_UNITS = {
    "swordsmen": (76, "Long Swordsman", 6),
    "pikeman": (358, "Pikeman", 6),
    "eagle_warrior": (751, "Eagle Warrior", 6),
    "light_cav": (546, "Light Cavalry", 12),
    "knight": (38, "Knight", 12),
    "camel": (329, "Camel Rider", 12),
    "elephant": (1132, "Battle Elephant", 12),
    "steppe_lancer": (1370, "Steppe Lancer", 12),
    "crossbow": (24, "Crossbowman", 0),
    "elite_skirm": (6, "Elite Skirmisher", 0),
    "cav_archer": (39, "Cavalry Archer", 36),
    "elephant_archer": (873, "Elephant Archer", 36),
    "ram": (35, "Battering Ram", 13),
    "mangonel": (280, "Mangonel", 13),
    "scorpion": (279, "Scorpion", 55),
}

# Imperial Age units - these use merged upgrade lines
# Format: (base_unit_id, display_name, unit_class, upgrade_chain)
# upgrade_chain is list of (tech_id, upgraded_unit_id, upgraded_name) from lowest to highest
IMPERIAL_AGE_UNITS = {
    "champion": {
        "base_id": 76,
        "base_name": "Long Swordsman",
        "display_name": "Champion",
        "unit_class": 6,
        "upgrades": [
            (217, 473, "Two-Handed Swordsman"),
            (264, 567, "Champion"),
        ],
    },
    "halberdier": {
        "base_id": 358,
        "base_name": "Pikeman",
        "display_name": "Halberdier",
        "unit_class": 6,
        "upgrades": [
            (429, 359, "Halberdier"),
        ],
    },
    "elite_eagle": {
        "base_id": 751,
        "base_name": "Eagle Warrior",
        "display_name": "Elite Eagle Warrior",
        "unit_class": 6,
        "upgrades": [
            (384, 752, "Elite Eagle Warrior"),
        ],
    },
    "hussar": {
        "base_id": 546,
        "base_name": "Light Cavalry",
        "display_name": "Hussar",
        "unit_class": 12,
        "upgrades": [
            (428, 441, "Hussar"),
            (786, 1707, "Winged Hussar"),
        ],
    },
    "paladin": {
        "base_id": 38,
        "base_name": "Knight",
        "display_name": "Paladin",
        "unit_class": 12,
        "upgrades": [
            (209, 283, "Cavalier"),
            (265, 569, "Paladin"),
        ],
        # Special: Hei-Kuang Cavalry for 3K civs
        "alternates": {
            "base_tech": 1032,  # Hei-Kuang Cavalry (make avail)
            "base_id": 1944,
            "base_name": "Hei-Kuang Cavalry",
            "upgrades": [
                (1033, 1946, "Heavy Hei-Kuang Cavalry"),
            ],
        },
    },
    "heavy_camel": {
        "base_id": 329,
        "base_name": "Camel Rider",
        "display_name": "Heavy Camel Rider",
        "unit_class": 12,
        "upgrades": [
            (236, 330, "Heavy Camel Rider"),
            (521, 207, "Imperial Camel Rider"),
        ],
    },
    "elite_elephant": {
        "base_id": 1132,
        "base_name": "Battle Elephant",
        "display_name": "Elite Battle Elephant",
        "unit_class": 12,
        "upgrades": [
            (631, 1134, "Elite Battle Elephant"),
        ],
    },
    "elite_steppe": {
        "base_id": 1370,
        "base_name": "Steppe Lancer",
        "display_name": "Elite Steppe Lancer",
        "unit_class": 12,
        "upgrades": [
            (715, 1372, "Elite Steppe Lancer"),
        ],
    },
    "arbalester": {
        "base_id": 24,
        "base_name": "Crossbowman",
        "display_name": "Arbalester",
        "unit_class": 0,
        "upgrades": [
            (237, 492, "Arbalester"),
        ],
    },
    "imp_skirm": {
        "base_id": 6,
        "base_name": "Elite Skirmisher",
        "display_name": "Imperial Skirmisher",
        "unit_class": 0,
        "upgrades": [
            (655, 1155, "Imperial Skirmisher"),
        ],
    },
    "heavy_cav_archer": {
        "base_id": 39,
        "base_name": "Cavalry Archer",
        "display_name": "Heavy Cavalry Archer",
        "unit_class": 36,
        "upgrades": [
            (218, 474, "Heavy Cavalry Archer"),
        ],
    },
    "elite_ele_archer": {
        "base_id": 873,
        "base_name": "Elephant Archer",
        "display_name": "Elite Elephant Archer",
        "unit_class": 36,
        "upgrades": [
            (481, 875, "Elite Elephant Archer"),
        ],
    },
    "siege_ram": {
        "base_id": 35,
        "base_name": "Battering Ram",
        "display_name": "Siege Ram",
        "unit_class": 13,
        "upgrades": [
            (96, 422, "Capped Ram"),
            (255, 548, "Siege Ram"),
        ],
        # Special: Armored/Siege Elephant for Indian civs
        "alternates": {
            "base_tech": 837,  # Armored Elephant (make avail)
            "base_id": 1733,
            "base_name": "Armored Elephant",
            "upgrades": [
                (838, 1735, "Siege Elephant"),
            ],
        },
    },
    "siege_onager": {
        "base_id": 280,
        "base_name": "Mangonel",
        "display_name": "Siege Onager",
        "unit_class": 13,
        "upgrades": [
            (257, 550, "Onager"),
            (320, 588, "Siege Onager"),
        ],
    },
    "heavy_scorpion": {
        "base_id": 279,
        "base_name": "Scorpion",
        "display_name": "Heavy Scorpion",
        "unit_class": 55,
        "upgrades": [
            (239, 542, "Heavy Scorpion"),
        ],
    },
    "hand_cannoneer": {
        "base_id": 5,
        "base_name": "Hand Cannoneer",
        "display_name": "Hand Cannoneer",
        "unit_class": 44,
        "upgrades": [],
    },
    "bombard_cannon": {
        "base_id": 36,
        "base_name": "Bombard Cannon",
        "display_name": "Bombard Cannon",
        "unit_class": 13,
        "upgrades": [],
    },
    "trebuchet": {
        "base_id": 42,
        "base_name": "Trebuchet",
        "display_name": "Trebuchet",
        "unit_class": 54,
        "upgrades": [],
    },
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
            hp=self.hp,
            attack=self.attack,
            melee_armor=self.melee_armor,
            pierce_armor=self.pierce_armor,
            speed=self.speed,
            range=self.range,
            reload_time=self.reload_time,
            accuracy=self.accuracy,
            los=self.los,
            cost_food=self.cost_food,
            cost_wood=self.cost_wood,
            cost_gold=self.cost_gold,
            cost_stone=self.cost_stone,
            train_time=self.train_time,
            upgrade_cost=self.upgrade_cost,
            attacks=self.attacks.copy(),
            armors=self.armors.copy(),
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
        self.techs = {
            t["id"]: t for t in json.load(open(OUTPUT_DIR / "technologies.json"))
        }
        self.civs = json.load(open(OUTPUT_DIR / "civilizations.json"))
        self.civ_tech_trees = {
            c["name"]: c for c in json.load(open(OUTPUT_DIR / "civ_tech_trees.json"))
        }
        self.effects = {
            e["id"]: e for e in json.load(open(OUTPUT_DIR / "effects.json"))
        }
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

        # Special cases for unit lines
        unit_lower = unit_name.lower()

        # Camel line
        if any(
            x in unit_lower for x in ["camel rider", "heavy camel", "imperial camel"]
        ):
            if 235 in disabled_techs:
                return False

        # Knight line
        if any(x in unit_lower for x in ["knight", "cavalier", "paladin"]):
            if 166 in disabled_techs:
                return False

        # Cavalry Archer line
        if any(x in unit_lower for x in ["cavalry archer", "heavy cavalry archer"]):
            if 192 in disabled_techs:
                return False

        # Elephant Archer line
        if any(x in unit_lower for x in ["elephant archer"]):
            if 480 in disabled_techs:
                return False

        # Battle Elephant line
        if any(x in unit_lower for x in ["battle elephant", "elite battle elephant"]):
            if 630 in disabled_techs:
                return False

        # Steppe Lancer line
        if any(x in unit_lower for x in ["steppe lancer", "elite steppe lancer"]):
            if 714 in disabled_techs:
                return False

        # Eagle Warrior line
        if any(
            x in unit_lower
            for x in ["eagle warrior", "elite eagle warrior", "eagle scout"]
        ):
            if 433 in disabled_techs:
                return False

        # Ram line
        if any(x in unit_lower for x in ["battering ram", "capped ram", "siege ram"]):
            if 162 in disabled_techs:
                return False

        # Armored Elephant line
        if any(x in unit_lower for x in ["armored elephant", "siege elephant"]):
            if 837 in disabled_techs:
                return False

        # Hei-Kuang Cavalry line
        if any(x in unit_lower for x in ["hei-kuang", "hei kuang"]):
            if 1032 in disabled_techs:
                return False

        # Hand Cannoneer
        if "hand cannoneer" in unit_lower:
            if 85 in disabled_techs:
                return False

        # Bombard Cannon
        if "bombard cannon" in unit_lower:
            if 188 in disabled_techs:
                return False

        # Trebuchet
        if "trebuchet" in unit_lower:
            if 194 in disabled_techs:
                return False

        return True

    def has_upgrade(self, civ_name: str, tech_id: int) -> bool:
        """Check if a civ has access to a specific upgrade tech."""
        disabled_techs = self.civ_disabled_tech_ids.get(civ_name, set())
        return tech_id not in disabled_techs

    def get_unit(self, unit_id: int):
        """Get unit by ID."""
        return self.units.get(unit_id)

    def find_techs_affecting_unit(
        self, unit_id: int, unit_class: int, max_age: int = 3
    ) -> set:
        """Find all techs up to a certain age that affect this unit."""
        cache_key = (unit_id, unit_class, max_age)
        if cache_key in self._tech_cache:
            return self._tech_cache[cache_key]

        relevant_techs = set()

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

                if cmd_type in (
                    CMD_SET_ATTRIBUTE,
                    CMD_ADD_ATTRIBUTE,
                    CMD_MULTIPLY_ATTRIBUTE,
                ):
                    if a == unit_id or (a == -1 and b == unit_class):
                        affects_unit = True
                        break

            if affects_unit:
                tech_id_str = str(tech_id)
                if tech_id_str in self.tech_ages:
                    tech_age_data = self.tech_ages[tech_id_str]
                    tech_age = tech_age_data.get("age", 4)
                    if tech_age <= max_age:
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

    def apply_effect_command(
        self, cmd: dict, stats: UnitStats, unit_id: int, unit_class: int
    ) -> bool:
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

    def get_civ_bonus_techs_for_unit(
        self, civ_name: str, unit_id: int, unit_class: int, max_age: int = 3
    ) -> list:
        """Get civ-specific bonus techs that affect this unit."""
        civ_id = self.civ_name_to_id.get(civ_name, -1)
        if civ_id < 0:
            return []

        relevant = []
        tech_ids = self.civ_bonus_techs.get(civ_id, [])

        age_tech_ids = {101: 2, 102: 3, 103: 4}

        for tech_id in tech_ids:
            if tech_id not in self.tech_effect_map:
                continue

            te = self.tech_effect_map[tech_id]
            tech_data = self.techs.get(tech_id, {})
            tech_name = tech_data.get("name", "")

            # Skip unique techs (have cost and don't start with C-Bonus)
            if tech_data.get("cost") and not tech_name.startswith("C-Bonus"):
                continue

            # Check age requirements
            required_techs = tech_data.get("required_techs", [])
            bonus_age = 1
            for req_tech in required_techs:
                if req_tech in age_tech_ids:
                    bonus_age = max(bonus_age, age_tech_ids[req_tech])

            if bonus_age > max_age:
                continue

            for cmd in te.get("commands", []):
                if self.effect_applies_to_unit(cmd, unit_id, unit_class):
                    relevant.append(te)
                    break

        return relevant

    def calculate_upgrade_cost(
        self, civ_name: str, relevant_techs: set, disabled_techs: set
    ) -> int:
        """Calculate total upgrade cost for relevant techs."""
        total = 0
        for tech_id in relevant_techs:
            if tech_id in disabled_techs:
                continue
            tech_data = self.techs.get(tech_id, {})
            base_cost = tech_data.get("cost", {})
            total += sum(base_cost.values())
        return total

    def calculate_civ_stats(
        self, unit: dict, civ_name: str, unit_display_name: str, max_age: int = 3
    ) -> dict:
        """Calculate fully upgraded stats for a unit for a specific civ up to a certain age."""
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
                "final_unit_name": unit_display_name,
            }

        stats = self.get_base_stats(unit)
        disabled_techs = self.get_disabled_techs(civ_name)
        applied_techs = []
        applied_bonuses = []

        # Apply civ bonus techs
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")

            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply standard techs for this age
        standard_techs = self.find_techs_affecting_unit(unit_id, unit_class, max_age)

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
        upgrade_cost = self.calculate_upgrade_cost(
            civ_name, standard_techs, disabled_techs
        )
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
            "final_unit_name": unit_display_name,
        }

    def calculate_imperial_civ_stats(self, civ_name: str, unit_config: dict) -> dict:
        """
        Calculate Imperial Age stats for a merged unit line.
        Returns the highest upgrade available to this civ.
        """
        base_id = unit_config["base_id"]
        base_name = unit_config["base_name"]
        unit_class = unit_config["unit_class"]
        upgrades = unit_config.get("upgrades", [])
        alternates = unit_config.get("alternates")

        disabled_techs = self.get_disabled_techs(civ_name)

        # Check for alternate unit (e.g., Hei-Kuang for 3K civs, Armored Elephant for Indian civs)
        use_alternate = False
        if alternates:
            alt_tech = alternates["base_tech"]
            # Civ uses alternate if they have alt_tech available but NOT the main unit
            main_unit_tech = None
            if base_name == "Knight":
                main_unit_tech = 166
            elif base_name == "Battering Ram":
                main_unit_tech = 162

            if (
                main_unit_tech
                and main_unit_tech in disabled_techs
                and alt_tech not in disabled_techs
            ):
                use_alternate = True
                base_id = alternates["base_id"]
                base_name = alternates["base_name"]
                upgrades = alternates.get("upgrades", [])

        # Check if civ has access to base unit
        if not self.has_unit_access(civ_name, base_name):
            return {
                "civ": civ_name,
                "stats": None,
                "applied_techs": [],
                "applied_bonuses": [],
                "unit_disabled": True,
                "final_unit_name": base_name,
            }

        # Find highest available upgrade
        final_unit_id = base_id
        final_unit_name = base_name

        for tech_id, upgraded_id, upgraded_name in upgrades:
            if self.has_upgrade(civ_name, tech_id):
                final_unit_id = upgraded_id
                final_unit_name = upgraded_name

        # Get the final unit
        unit = self.get_unit(final_unit_id)
        if not unit:
            # Fallback to base unit
            unit = self.get_unit(base_id)
            final_unit_name = base_name

        if not unit:
            return {
                "civ": civ_name,
                "stats": None,
                "applied_techs": [],
                "applied_bonuses": [],
                "unit_disabled": True,
                "final_unit_name": final_unit_name,
            }

        # Calculate stats with Imperial Age techs
        stats = self.get_base_stats(unit)
        applied_techs = []
        applied_bonuses = []

        # Apply civ bonus techs (Imperial Age)
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(
            civ_name, final_unit_id, unit_class, IMPERIAL_AGE
        )
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, final_unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply standard Imperial Age techs
        standard_techs = self.find_techs_affecting_unit(
            final_unit_id, unit_class, IMPERIAL_AGE
        )

        for tech_id in sorted(standard_techs):
            tech_name = self.techs.get(tech_id, {}).get("name", f"Tech {tech_id}")

            if tech_id in disabled_techs:
                continue

            if tech_id in self.tech_effect_map:
                te = self.tech_effect_map[tech_id]
                for cmd in te.get("commands", []):
                    if self.apply_effect_command(cmd, stats, final_unit_id, unit_class):
                        if tech_name not in applied_techs:
                            applied_techs.append(tech_name)

        # Calculate upgrade cost
        upgrade_cost = self.calculate_upgrade_cost(
            civ_name, standard_techs, disabled_techs
        )
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
            "final_unit_name": final_unit_name,
        }


def generate_csv_for_unit(
    analyzer: UnitAnalyzer,
    output_dir: Path,
    line_name: str,
    unit_id: int,
    unit_display_name: str,
    unit_class: int,
    max_age: int = CASTLE_AGE,
):
    """Generate a CSV file for a unit across all civs."""
    csv_path = output_dir / f"{line_name}.csv"

    unit = analyzer.get_unit(unit_id)
    if not unit:
        print(f"  ERROR: Unit ID {unit_id} not found!")
        return None

    # Determine if ranged unit
    is_ranged = unit.get("range", 0) > 0

    # Build header
    if is_ranged:
        fieldnames = [
            "Civilization",
            "Unit",
            "HP",
            "Attack",
            "Range",
            "Attack_Speed",
            "Melee_Armor",
            "Pierce_Armor",
            "Movement_Speed",
            "Cost_Food",
            "Cost_Wood",
            "Cost_Gold",
            "Creation_Time",
            "Upgrade_Cost",
            "Civ_Bonuses",
            "Has_Unit",
        ]
    else:
        fieldnames = [
            "Civilization",
            "Unit",
            "HP",
            "Attack",
            "Attack_Speed",
            "Melee_Armor",
            "Pierce_Armor",
            "Movement_Speed",
            "Cost_Food",
            "Cost_Wood",
            "Cost_Gold",
            "Creation_Time",
            "Upgrade_Cost",
            "Civ_Bonuses",
            "Has_Unit",
        ]

    rows = []

    for civ in analyzer.civs:
        civ_name = civ["name"]
        if civ_name == "Gaia":
            continue

        result = analyzer.calculate_civ_stats(
            unit, civ_name, unit_display_name, max_age
        )

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
            bonuses = ", ".join(
                b.replace("C-Bonus, ", "") for b in result["applied_bonuses"]
            )

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

    has_unit = sum(1 for r in rows if r["Has_Unit"] == "Yes")
    no_unit = sum(1 for r in rows if r["Has_Unit"] == "No")

    print(f"  Generated {csv_path.name} ({has_unit} civs have it, {no_unit} don't)")
    return csv_path


def generate_imperial_csv(
    analyzer: UnitAnalyzer, output_dir: Path, line_name: str, unit_config: dict
):
    """Generate a CSV file for an Imperial Age merged unit line."""
    csv_path = output_dir / f"{line_name}.csv"

    # Get base unit to determine if ranged
    base_unit = analyzer.get_unit(unit_config["base_id"])
    is_ranged = base_unit and base_unit.get("range", 0) > 0

    # Build header
    if is_ranged:
        fieldnames = [
            "Civilization",
            "Unit",
            "HP",
            "Attack",
            "Range",
            "Attack_Speed",
            "Melee_Armor",
            "Pierce_Armor",
            "Movement_Speed",
            "Cost_Food",
            "Cost_Wood",
            "Cost_Gold",
            "Creation_Time",
            "Upgrade_Cost",
            "Civ_Bonuses",
            "Has_Unit",
        ]
    else:
        fieldnames = [
            "Civilization",
            "Unit",
            "HP",
            "Attack",
            "Attack_Speed",
            "Melee_Armor",
            "Pierce_Armor",
            "Movement_Speed",
            "Cost_Food",
            "Cost_Wood",
            "Cost_Gold",
            "Creation_Time",
            "Upgrade_Cost",
            "Civ_Bonuses",
            "Has_Unit",
        ]

    rows = []

    for civ in analyzer.civs:
        civ_name = civ["name"]
        if civ_name == "Gaia":
            continue

        result = analyzer.calculate_imperial_civ_stats(civ_name, unit_config)

        if result["unit_disabled"]:
            row = {
                "Civilization": civ_name,
                "Unit": result["final_unit_name"],
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
            bonuses = ", ".join(
                b.replace("C-Bonus, ", "") for b in result["applied_bonuses"]
            )

            row = {
                "Civilization": civ_name,
                "Unit": result["final_unit_name"],
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

    has_unit = sum(1 for r in rows if r["Has_Unit"] == "Yes")
    no_unit = sum(1 for r in rows if r["Has_Unit"] == "No")

    # Count unique unit names
    unit_names = set(r["Unit"] for r in rows if r["Has_Unit"] == "Yes")
    print(f"  Generated {csv_path.name} ({has_unit} civs, variants: {unit_names})")
    return csv_path


def main():
    print("AoE2 Unit CSV Generator - All Ages")
    print("=" * 60)

    # Create output directories
    feudal_dir = CSV_OUTPUT_DIR / "feudal"
    castle_dir = CSV_OUTPUT_DIR / "castle"
    imperial_dir = CSV_OUTPUT_DIR / "imperial"

    feudal_dir.mkdir(parents=True, exist_ok=True)
    castle_dir.mkdir(parents=True, exist_ok=True)
    imperial_dir.mkdir(parents=True, exist_ok=True)

    print("\nLoading game data...")
    analyzer = UnitAnalyzer()
    print(f"  Loaded {len(analyzer.units)} units")
    print(f"  Loaded {len(analyzer.civs)} civilizations")
    print(f"  Loaded {len(analyzer.techs)} technologies")

    # Generate Feudal Age CSVs
    print("\n" + "=" * 60)
    print("FEUDAL AGE UNITS")
    print("=" * 60)

    feudal_units = {
        "man_at_arms": (93, "Man-at-Arms", 6),
        "spearman": (93, "Spearman", 6),
        "archer": (4, "Archer", 0),
        "skirmisher": (7, "Skirmisher", 0),
        "scout": (448, "Scout Cavalry", 12),
    }

    for line_name, (unit_id, unit_display_name, unit_class) in feudal_units.items():
        print(f"\n{line_name} ({unit_display_name}):")
        generate_csv_for_unit(
            analyzer,
            feudal_dir,
            line_name,
            unit_id,
            unit_display_name,
            unit_class,
            max_age=FEUDAL_AGE,
        )

    # Generate Castle Age CSVs (regenerate to ensure consistency)
    print("\n" + "=" * 60)
    print("CASTLE AGE UNITS")
    print("=" * 60)

    for line_name, (unit_id, unit_display_name, unit_class) in CASTLE_AGE_UNITS.items():
        print(f"\n{line_name} ({unit_display_name}):")
        generate_csv_for_unit(
            analyzer,
            castle_dir,
            line_name,
            unit_id,
            unit_display_name,
            unit_class,
            max_age=CASTLE_AGE,
        )

    # Generate Imperial Age CSVs
    print("\n" + "=" * 60)
    print("IMPERIAL AGE UNITS")
    print("=" * 60)

    for line_name, unit_config in IMPERIAL_AGE_UNITS.items():
        print(f"\n{line_name} ({unit_config['display_name']}):")
        generate_imperial_csv(analyzer, imperial_dir, line_name, unit_config)

    print("\n" + "=" * 60)
    print(f"Done! CSV files written to: {CSV_OUTPUT_DIR}")
    print(f"  Feudal: {feudal_dir}")
    print(f"  Castle: {castle_dir}")
    print(f"  Imperial: {imperial_dir}")


if __name__ == "__main__":
    main()
