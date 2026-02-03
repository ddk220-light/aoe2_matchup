#!/usr/bin/env python3
"""
Flexible Unit Comparison Tool

Dynamically analyzes any unit across all civilizations by:
1. Loading the unit's base stats
2. Finding all techs that affect this unit (by ID or class) from tech_effects.json
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
from collections import defaultdict

OUTPUT_DIR = Path(__file__).parent.parent / "output"

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

# Resource type mapping for tech costs
RESOURCE_FOOD = 0
RESOURCE_WOOD = 1
RESOURCE_STONE = 2
RESOURCE_GOLD = 3

# Effect command types
CMD_SET_ATTRIBUTE = 0
CMD_ADD_ATTRIBUTE = 4
CMD_MULTIPLY_ATTRIBUTE = 5
CMD_UPGRADE_UNIT = 3
CMD_ENABLE_UNIT = 2
CMD_TECH_COST_SET = 101
CMD_DISABLE_TECH = 102

# Building ID to readable name mapping
BUILDING_NAMES = {
    101: "Stable", 86: "Stable", 153: "Stable",
    87: "Archery Range", 10: "Archery Range", 104: "Archery Range",
    12: "Barracks", 498: "Barracks", 234: "Barracks",
    49: "Siege Workshop", 150: "Siege Workshop",
    209: "University", 210: "University",
    82: "Castle", 137: "Castle",
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

    def to_tuple(self):
        """Return a tuple for comparison (to group identical civs)."""
        return (
            round(self.hp), round(self.attack),
            round(self.melee_armor), round(self.pierce_armor),
            round(self.speed, 2), round(self.cost_food), round(self.cost_wood),
            round(self.cost_gold), round(self.train_time), round(self.upgrade_cost)
        )


class UnitAnalyzer:
    def __init__(self):
        self.load_data()
        self._tech_cache = {}  # Cache for techs affecting units
        self._building_cache = {}  # Cache for production buildings

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

        # Build civ name to ID mapping dynamically
        self.civ_name_to_id = {c["name"]: c["id"] for c in self.civs}
        self.civ_id_to_name = {c["id"]: c["name"] for c in self.civs}

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

    def find_techs_affecting_unit(self, unit_id: int, unit_class: int, max_age: str) -> set:
        """Dynamically find all standard techs that affect this unit.

        Excludes civ-specific techs (C-Bonus) and unique techs.
        Only includes blacksmith, stable, archery range, university type techs.
        """
        cache_key = (unit_id, unit_class, max_age)
        if cache_key in self._tech_cache:
            return self._tech_cache[cache_key]

        relevant_techs = set()

        # Known standard tech categories (by tech ID ranges and names)
        # These are techs that are universally available (if not disabled)
        standard_tech_names = {
            # Blacksmith attack
            "forging", "iron casting", "blast furnace",
            # Blacksmith cavalry armor
            "scale barding armor", "chain barding armor", "plate barding armor",
            # Blacksmith infantry armor
            "scale mail armor", "chain mail armor", "plate mail armor",
            # Blacksmith archer armor
            "padded archer armor", "leather archer armor", "ring archer armor",
            # Archery range
            "fletching", "bodkin arrow", "bracer", "thumb ring",
            # Stable
            "bloodlines", "husbandry",
            # Unit upgrades
            "cavalier", "paladin", "elite skirmisher", "arbalester",
            "heavy cavalry archer", "elite eagle warrior",
            "long swordsman", "two-handed swordsman", "champion",
            "pikeman", "halberdier", "elite battle elephant",
        }

        for te in self.tech_effects:
            tech_id = te["tech_id"]
            tech_data = self.techs.get(tech_id, {})
            tech_name = tech_data.get("name", "").lower()

            # Skip civ-specific techs
            if tech_data.get("civ", -1) >= 0:
                continue

            # Check if this tech affects our unit
            affects_unit = False
            is_upgrade_tech = False

            for cmd in te.get("commands", []):
                cmd_type = cmd.get("type", -1)
                a = cmd.get("a", -999)
                b = cmd.get("b", -999)

                # Check for unit upgrade (type 3)
                if cmd_type == CMD_UPGRADE_UNIT:
                    if a == unit_id:  # Upgrades FROM this unit
                        is_upgrade_tech = True
                        affects_unit = True
                        break

                # Check for stat modifications (types 0, 4, 5)
                if cmd_type in (CMD_SET_ATTRIBUTE, CMD_ADD_ATTRIBUTE, CMD_MULTIPLY_ATTRIBUTE):
                    # Direct unit match or class match
                    if a == unit_id or (a == -1 and b == unit_class):
                        affects_unit = True
                        break

            if affects_unit:
                # Filter to only standard techs (not unique techs)
                # Standard techs either have a recognized name or no cost (auto-applied)
                is_standard = False

                # Check by name
                for std_name in standard_tech_names:
                    if std_name in tech_name:
                        is_standard = True
                        break

                # Also include if it's a no-cost tech that affects stats (like age-up bonuses)
                tech_cost = tech_data.get("cost", {})
                total_cost = sum(tech_cost.values()) if tech_cost else 0

                if is_standard or (total_cost > 0 and is_upgrade_tech):
                    relevant_techs.add(tech_id)

        # Filter by age using exact tech names
        # Imperial-only techs (not available in Castle Age)
        imperial_only_tech_names = {
            "iron casting", "blast furnace",
            "plate barding armor", "plate mail armor",
            "ring archer armor", "bracer",
            "paladin", "cavalier", "arbalest", "arbalester",
            "champion", "halberdier", "two-handed swordsman",
            "heavy cavalry archer",
        }

        if max_age == "castle":
            filtered = set()
            for tech_id in relevant_techs:
                tech_name = self.techs.get(tech_id, {}).get("name", "").lower()
                # Check exact match against imperial tech names
                if tech_name not in imperial_only_tech_names:
                    # Also check for "elite" prefix (elite unit upgrades are imperial)
                    if not tech_name.startswith("elite "):
                        filtered.add(tech_id)
            relevant_techs = filtered

        self._tech_cache[cache_key] = relevant_techs
        return relevant_techs

    def find_production_buildings(self, unit_id: int, unit_class: int) -> set:
        """Find buildings that produce this unit by looking at enable/disable commands."""
        cache_key = (unit_id, unit_class)
        if cache_key in self._building_cache:
            return self._building_cache[cache_key]

        # Look for "make avail" techs that enable this unit
        # These techs have ENABLE_UNIT commands
        building_ids = set()

        # Common building IDs by unit class (as fallback)
        class_to_buildings = {
            12: {101, 86, 153},  # Cavalry -> Stable variants
            0: {87, 10, 104},    # Archer -> Archery Range variants
            6: {12, 87, 234},    # Infantry -> Barracks variants
        }

        # Try to find from tech effects
        for te in self.tech_effects:
            tech_name = te.get("tech_name", "").lower()

            # Look for "make avail" techs for this unit
            for cmd in te.get("commands", []):
                if cmd.get("type") == CMD_ENABLE_UNIT:
                    enabled_unit = cmd.get("a", -1)
                    if enabled_unit == unit_id:
                        # This tech enables our unit - look for building work rate effects
                        # in team bonuses to identify the building
                        pass

        # Use class-based fallback
        if unit_class in class_to_buildings:
            building_ids = class_to_buildings[unit_class]

        self._building_cache[cache_key] = building_ids
        return building_ids

    def find_unit_upgrade_chain(self, unit_id: int) -> dict:
        """Find units that this unit upgrades to (and their tech IDs)."""
        upgrades = {}  # to_unit_id -> tech_id

        for te in self.tech_effects:
            for cmd in te.get("commands", []):
                if cmd.get("type") == CMD_UPGRADE_UNIT:
                    if cmd.get("a") == unit_id:  # from_unit
                        to_unit = cmd.get("b")
                        tech_id = te["tech_id"]
                        upgrades[to_unit] = tech_id

        return upgrades

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

    def get_tech_cost_modifiers(self, civ_name: str) -> dict:
        """Get tech cost modifiers for a civilization."""
        civ_data = self.civ_tech_trees.get(civ_name, {})
        effect_id = civ_data.get("tech_tree_effect_id")

        modifiers = {}

        if effect_id and effect_id in self.effects:
            effect = self.effects[effect_id]
            for cmd in effect.get("commands", []):
                if cmd.get("type") == CMD_TECH_COST_SET:
                    tech_id = cmd.get("a")
                    resource_type = cmd.get("b")
                    value = cmd.get("d", 0)

                    if tech_id not in modifiers:
                        modifiers[tech_id] = {}
                    modifiers[tech_id][resource_type] = value

        return modifiers

    def calculate_upgrade_cost(self, civ_name: str, relevant_techs: set, disabled_techs: set) -> tuple:
        """Calculate total upgrade cost for relevant techs."""
        tech_cost_mods = self.get_tech_cost_modifiers(civ_name)

        total_food = 0
        total_wood = 0
        total_gold = 0
        total_stone = 0
        breakdown = {}

        for tech_id in relevant_techs:
            if tech_id in disabled_techs:
                breakdown[tech_id] = {"name": self.techs.get(tech_id, {}).get("name", f"Tech {tech_id}"), "cost": 0, "disabled": True}
                continue

            tech_data = self.techs.get(tech_id, {})
            tech_name = tech_data.get("name", f"Tech {tech_id}")
            base_cost = tech_data.get("cost", {})

            food = base_cost.get("food", 0)
            wood = base_cost.get("wood", 0)
            gold = base_cost.get("gold", 0)
            stone = base_cost.get("stone", 0)

            # Apply civ-specific modifiers
            if tech_id in tech_cost_mods:
                mods = tech_cost_mods[tech_id]
                for res_type, mod_val in mods.items():
                    if res_type == RESOURCE_FOOD:
                        food = 0 if mod_val == 0 else max(0, food + mod_val) if mod_val < 0 else food
                    elif res_type == RESOURCE_WOOD:
                        wood = 0 if mod_val == 0 else max(0, wood + mod_val) if mod_val < 0 else wood
                    elif res_type == RESOURCE_GOLD:
                        gold = 0 if mod_val == 0 else max(0, gold + mod_val) if mod_val < 0 else gold
                    elif res_type == RESOURCE_STONE:
                        stone = 0 if mod_val == 0 else max(0, stone + mod_val) if mod_val < 0 else stone

            tech_total = food + wood + gold + stone
            breakdown[tech_id] = {"name": tech_name, "cost": tech_total, "food": food, "wood": wood, "gold": gold, "stone": stone, "disabled": False}

            total_food += food
            total_wood += wood
            total_gold += gold
            total_stone += stone

        total = total_food + total_wood + total_gold + total_stone
        return total, breakdown

    def is_unit_disabled(self, civ_name: str, unit_name: str) -> bool:
        """Check if a unit is disabled for a civilization."""
        civ_data = self.civ_tech_trees.get(civ_name, {})
        disabled = civ_data.get("disabled_techs", [])
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
        """Decode armor/attack value."""
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

    def get_special_upgrade_civs(self, unit_id: int, max_age: str) -> dict:
        """Find civs that can research unit upgrades in earlier ages.

        Returns: {civ_name: {"upgrade_unit_id": id, "upgrade_tech_id": id}}
        """
        special_civs = {}

        # Find upgrade techs for this unit
        upgrades = self.find_unit_upgrade_chain(unit_id)

        for to_unit_id, tech_id in upgrades.items():
            tech_data = self.techs.get(tech_id, {})
            tech_name = tech_data.get("name", "").lower()

            # Check each civ's tech tree effects for age modifications
            for civ_name, civ_data in self.civ_tech_trees.items():
                effect_id = civ_data.get("tech_tree_effect_id")
                if not effect_id or effect_id not in self.effects:
                    continue

                effect = self.effects[effect_id]
                for cmd in effect.get("commands", []):
                    # Look for tech age modifications or special enables
                    # Burgundians have stable techs available one age earlier
                    pass

        # Hardcode known special cases for now (can be made dynamic later)
        if unit_id == 38 and max_age == "castle":  # Knight
            # Burgundians can research Cavalier in Castle Age
            special_civs["Burgundians"] = {"upgrade_unit_id": 283, "upgrade_tech_id": 209}

        return special_civs

    def calculate_civ_stats(self, unit: dict, civ_name: str, max_age: str = "imperial") -> dict:
        """Calculate unit stats for a specific civilization."""
        unit_id = unit["id"]
        unit_class = unit["class"]
        unit_name = unit["name"]

        # Check for special upgrade availability (e.g., Burgundians Cavalier in Castle)
        special_upgrades = self.get_special_upgrade_civs(unit_id, max_age)
        effective_unit = unit
        uses_upgrade = False
        upgrade_name = None

        if civ_name in special_upgrades:
            upgrade_info = special_upgrades[civ_name]
            upgraded_unit = self.units.get(upgrade_info["upgrade_unit_id"])
            if upgraded_unit:
                effective_unit = upgraded_unit
                unit_id = upgraded_unit["id"]
                unit_name = upgraded_unit["name"]
                uses_upgrade = True
                upgrade_name = upgraded_unit["name"]

        # Check if this unit is disabled for this civ
        unit_disabled = self.is_unit_disabled(civ_name, unit["name"])  # Check original unit name
        if unit_disabled:
            return {
                "civ": civ_name,
                "stats": None,
                "base_stats": None,
                "applied_techs": [],
                "applied_bonuses": [],
                "unit_disabled": True,
            }

        stats = self.get_base_stats(effective_unit)
        base_stats = stats.copy()

        disabled_techs = self.get_disabled_techs(civ_name)
        applied_techs = []
        applied_bonuses = []

        if uses_upgrade:
            applied_bonuses.append(f"{upgrade_name} in Castle Age")

        # 1. Apply civ-specific bonus techs (C-Bonus techs)
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(civ_name, unit_id, unit_class)
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            tech_data = self.techs.get(te["tech_id"], {})
            if tech_data.get("cost") and not tech_name.startswith("C-Bonus"):
                continue

            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # 1b. Apply team bonus for production building work rate
        civ_data = self.civ_tech_trees.get(civ_name, {})
        team_bonus_effect_id = civ_data.get("team_bonus_effect_id")
        if team_bonus_effect_id and team_bonus_effect_id in self.effects:
            effect = self.effects[team_bonus_effect_id]
            production_buildings = self.find_production_buildings(unit_id, unit_class)

            building_bonus_applied = False
            for cmd in effect.get("commands", []):
                building_id = cmd.get("a", -1)
                if building_id in production_buildings and cmd.get("c") == ATTR_WORK_RATE and not building_bonus_applied:
                    work_rate_mult = cmd.get("d", 1.0)
                    if work_rate_mult > 0 and work_rate_mult != 1.0:
                        stats.train_time = stats.train_time / work_rate_mult
                        # Get building name from mapping
                        building_name = BUILDING_NAMES.get(building_id, f"Building {building_id}")
                        bonus_pct = int((work_rate_mult - 1) * 100)
                        bonus_name = f"Team Bonus: {building_name} +{bonus_pct}% work rate"
                        if bonus_name not in applied_bonuses:
                            applied_bonuses.append(bonus_name)
                        building_bonus_applied = True

        # 2. Apply standard techs dynamically discovered
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

        # 3. Calculate upgrade cost
        relevant_upgrade_techs = self.find_techs_affecting_unit(unit_id, unit_class, max_age)

        # Add special upgrade tech cost if applicable
        if civ_name in special_upgrades:
            upgrade_tech_id = special_upgrades[civ_name]["upgrade_tech_id"]
            relevant_upgrade_techs = relevant_upgrade_techs | {upgrade_tech_id}

        upgrade_cost, upgrade_breakdown = self.calculate_upgrade_cost(
            civ_name, relevant_upgrade_techs, disabled_techs
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

        return {
            "civ": civ_name,
            "stats": stats,
            "base_stats": base_stats,
            "applied_techs": applied_techs,
            "applied_bonuses": applied_bonuses,
            "upgrade_breakdown": upgrade_breakdown,
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
        """Print formatted comparison table with grouped identical civs."""
        enabled = [r for r in results if not r.get("unit_disabled", False)]
        disabled = [r for r in results if r.get("unit_disabled", False)]

        # Group civs with identical stats
        stat_groups = defaultdict(list)
        for r in enabled:
            s = r["stats"]
            # Create a key from stats + bonuses for grouping
            bonuses_key = tuple(sorted(r["applied_bonuses"]))
            stat_key = (s.to_tuple(), bonuses_key)
            stat_groups[stat_key].append(r)

        # Find the most common stats (generic/baseline)
        largest_group_key = max(stat_groups.keys(), key=lambda k: len(stat_groups[k]))
        generic_civs = [r["civ"] for r in stat_groups[largest_group_key]]

        # Sort groups by power score
        def power_score(stat_key):
            stats_tuple = stat_key[0]
            hp, attack = stats_tuple[0], stats_tuple[1]
            return hp * attack

        sorted_groups = sorted(stat_groups.keys(), key=power_score, reverse=True)

        print("\n" + "=" * 145)
        print(f"{'Civilization(s)':<40} {'HP':>4} {'Atk':>4} {'M.Arm':>5} {'P.Arm':>5} {'Speed':>5} {'Cost':>11} {'Train':>5} {'Upgr':>6} {'Civ Bonuses':<30}")
        print("-" * 145)

        for stat_key in sorted_groups:
            group = stat_groups[stat_key]
            s = group[0]["stats"]

            # Get civ names for this group
            civ_names = sorted([r["civ"] for r in group])

            # If this is the generic group, label it
            if stat_key == largest_group_key and len(civ_names) > 3:
                civ_str = f"Generic ({len(civ_names)} civs)"
            elif len(civ_names) > 3:
                civ_str = f"{civ_names[0]}, +{len(civ_names)-1} more"
            else:
                civ_str = ", ".join(civ_names)

            # Truncate if too long
            if len(civ_str) > 38:
                civ_str = civ_str[:35] + "..."

            # Build cost string
            cost_parts = []
            if s.cost_food > 0:
                cost_parts.append(f"{int(s.cost_food)}F")
            if s.cost_wood > 0:
                cost_parts.append(f"{int(s.cost_wood)}W")
            if s.cost_gold > 0:
                cost_parts.append(f"{int(s.cost_gold)}G")
            cost = "/".join(cost_parts) if cost_parts else "0"

            # Get bonuses (should be same for all in group)
            bonuses = group[0]["applied_bonuses"]
            bonus_str = ", ".join(b.replace("C-Bonus, ", "") for b in bonuses)[:30] if bonuses else "-"

            print(f"{civ_str:<40} {s.hp:>4.0f} {s.attack:>4.0f} {s.melee_armor:>5.0f} {s.pierce_armor:>5.0f} {s.speed:>5.2f} {cost:>11} {s.train_time:>4.0f}s {s.upgrade_cost:>6.0f} {bonus_str:<30}")

        # Print disabled civs
        if disabled:
            print("-" * 145)
            disabled_names = sorted([r["civ"] for r in disabled])
            print(f"{'NO UNIT: ' + ', '.join(disabled_names):<145}")

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
