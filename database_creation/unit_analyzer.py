"""UnitStats dataclass and UnitAnalyzer class for computing civ-specific unit stats."""

import json
from dataclasses import dataclass, field

from .config import (
    OUTPUT_DIR,
    AGE_TECH_IDS,
    ATTR_HP, ATTR_LOS, ATTR_SPEED, ATTR_ARMOR, ATTR_ATTACK,
    ATTR_RELOAD_TIME, ATTR_ACCURACY, ATTR_RANGE, ATTR_TRAIN_TIME,
    ATTR_COST, ATTR_FOOD_COST, ATTR_WOOD_COST, ATTR_GOLD_COST,
    CMD_SET_ATTRIBUTE, CMD_ADD_ATTRIBUTE, CMD_MULTIPLY_ATTRIBUTE,
    BUILDING_WORK_RATE_TECHS, CIV_TECH_COST_DISCOUNT,
    CIV_TEAM_BONUS_WORK_RATE, CIV_TEAM_BONUS_ATTACK,
    UNIQUE_UNITS_IN_BARRACKS, REMOVED_TECHS, LITHUANIAN_RELIC_COUNT,
    UNIT_CLASS_TO_BUILDING, UNIQUE_UNIT_BUILDING,
    _PREVIOUS_AGE_NAMES,
    _tech_age_name,
)

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
    attack_delay: float = 0
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
            attack_delay=self.attack_delay,
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
    """Analyzes unit stats and calculates civ-specific values."""

    def __init__(self):
        self.load_data()
        self._tech_cache = {}

    def load_data(self):
        """Load all game data from JSON files."""
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

        # Load tech ages
        tech_ages_file = OUTPUT_DIR / "tech_ages.json"
        if tech_ages_file.exists():
            tech_ages_data = json.load(open(tech_ages_file))
            self.tech_ages = tech_ages_data.get("techs", {})
        else:
            self.tech_ages = {}

        # Build tech effect lookup
        self.tech_effect_map = {te["tech_id"]: te for te in self.tech_effects}

        # Build civ bonus techs lookup
        self.civ_bonus_techs = {}
        for tech_id, tech in self.techs.items():
            civ_id = tech.get("civ", -1)
            if civ_id >= 0:
                if civ_id not in self.civ_bonus_techs:
                    self.civ_bonus_techs[civ_id] = []
                self.civ_bonus_techs[civ_id].append(tech_id)

        # Build civ name to ID mapping
        self.civ_name_to_id = {c["name"]: c["id"] for c in self.civs}

        # Build disabled tech lookup per civ
        self.civ_disabled_tech_ids = {}
        for civ_name, civ_data in self.civ_tech_trees.items():
            disabled = set()
            for t in civ_data.get("disabled_techs", []):
                if isinstance(t, dict):
                    disabled.add(t["id"])
            self.civ_disabled_tech_ids[civ_name] = disabled

    def get_disabled_techs(self, civ_name: str) -> set:
        """Get set of disabled tech IDs for a civilization."""
        return self.civ_disabled_tech_ids.get(civ_name, set())

    def get_building_work_rate(
        self, civ_name: str, building_id: int, max_age: int
    ) -> float:
        """Get combined work rate multiplier for a building from all available techs."""
        disabled_techs = self.get_disabled_techs(civ_name)
        civ_id = self.civ_name_to_id.get(civ_name, -1)
        multiplier = 1.0
        for tech_id, (
            tech_civ_id,
            building_multipliers,
        ) in BUILDING_WORK_RATE_TECHS.items():
            if building_id not in building_multipliers:
                continue
            if tech_id in disabled_techs:
                continue
            # Check civ restriction (-1 = all civs)
            if tech_civ_id != -1 and tech_civ_id != civ_id:
                continue
            # Check age requirement
            tech_age = self.get_tech_age_recursive(tech_id)
            if tech_age > max_age:
                continue
            multiplier *= building_multipliers[building_id]
        # Apply civ team bonus work rate (civs apply their own team bonus)
        team_bonus = CIV_TEAM_BONUS_WORK_RATE.get(civ_name, {})
        if building_id in team_bonus:
            multiplier *= team_bonus[building_id]
        return multiplier

    def has_tech(self, civ_name: str, tech_id: int) -> bool:
        """Check if a civ has access to a specific tech."""
        if tech_id is None:
            return True
        disabled_techs = self.get_disabled_techs(civ_name)
        return tech_id not in disabled_techs

    def get_unit(self, unit_id: int):
        """Get unit by ID."""
        return self.units.get(unit_id)

    def get_base_stats(self, unit: dict) -> UnitStats:
        """Extract base stats from unit data."""
        stats = UnitStats()
        stats.hp = unit.get("hit_points", 0)
        stats.speed = unit.get("speed", 0)
        stats.range = unit.get("range", 0)
        stats.reload_time = unit.get("reload_time", 0)
        stats.attack_delay = unit.get("attack_delay", 0)
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

    def get_tech_age(self, tech_id: int) -> int:
        """Get the age when a tech becomes available."""
        tech_id_str = str(tech_id)
        if tech_id_str in self.tech_ages:
            return self.tech_ages[tech_id_str].get("age", 4)

        # Fallback: check required_techs
        tech_data = self.techs.get(tech_id, {})
        required = tech_data.get("required_techs", [])
        for req in required:
            if req in AGE_TECH_IDS:
                return AGE_TECH_IDS[req]
        return 1  # Dark Age default

    def find_techs_affecting_unit(
        self, unit_id: int, unit_class: int, max_age: int = 4
    ) -> set:
        """Find all techs up to a certain age that affect this unit."""
        cache_key = (unit_id, unit_class, max_age)
        if cache_key in self._tech_cache:
            return self._tech_cache[cache_key]

        relevant_techs = set()

        for te in self.tech_effects:
            tech_id = te["tech_id"]
            tech_data = self.techs.get(tech_id, {})

            # Skip civ-specific techs (handled separately)
            if tech_data.get("civ", -1) >= 0:
                continue

            # Skip DLC/campaign-specific techs (have non-standard requirements like Antiquity techs)
            # These are identified by having required_techs with IDs > 1000 that aren't standard
            required_techs = tech_data.get("required_techs", [])
            has_dlc_requirement = any(
                req > 1000 and req not in AGE_TECH_IDS
                for req in required_techs
                if req > 0
            )
            if has_dlc_requirement:
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
                tech_age = self.get_tech_age(tech_id)
                if tech_age <= max_age:
                    relevant_techs.add(tech_id)

        self._tech_cache[cache_key] = relevant_techs
        return relevant_techs

    def get_tech_age_recursive(self, tech_id: int, visited: set = None) -> int:
        """
        Get the effective age when a tech becomes available,
        considering the ages of required techs recursively.
        """
        if visited is None:
            visited = set()

        if tech_id in visited:
            return 1  # Prevent infinite loops
        visited.add(tech_id)

        # First check if it's an age tech itself
        if tech_id in AGE_TECH_IDS:
            return AGE_TECH_IDS[tech_id]

        # Check tech_ages.json
        tech_id_str = str(tech_id)
        if tech_id_str in self.tech_ages:
            return self.tech_ages[tech_id_str].get("age", 1)

        # Check required_techs and find the max age among them
        tech_data = self.techs.get(tech_id, {})
        required_techs = tech_data.get("required_techs", [])

        max_age = 1  # Dark Age default
        for req_tech in required_techs:
            req_age = self.get_tech_age_recursive(req_tech, visited.copy())
            max_age = max(max_age, req_age)

        return max_age

    def get_civ_bonus_techs_for_unit(
        self, civ_name: str, unit_id: int, unit_class: int, max_age: int = 4
    ) -> list:
        """Get civ-specific bonus techs that affect this unit."""
        civ_id = self.civ_name_to_id.get(civ_name, -1)
        if civ_id < 0:
            return []

        relevant = []
        tech_ids = self.civ_bonus_techs.get(civ_id, [])

        for tech_id in tech_ids:
            if tech_id in REMOVED_TECHS:
                continue
            if tech_id not in self.tech_effect_map:
                continue

            te = self.tech_effect_map[tech_id]
            tech_data = self.techs.get(tech_id, {})
            tech_name = tech_data.get("name", "")

            # Skip unique techs (have cost and don't start with C-Bonus)
            if tech_data.get("cost") and not tech_name.startswith("C-Bonus"):
                continue

            # Handle relic-based bonuses (e.g., Lithuanian "Relic +1 cav attack")
            # Apply only the configured number of relic bonuses for Lithuanians
            if "Relic" in tech_name:
                if civ_name == "Lithuanians" and LITHUANIAN_RELIC_COUNT > 0:
                    # Extract relic number from tech name (e.g., "Relic +1 cav attack 1" -> 1)
                    relic_num = 0
                    for part in tech_name.split():
                        if part.isdigit():
                            relic_num = int(part)
                            break
                    # Only apply if this relic number is within our configured count
                    if relic_num > LITHUANIAN_RELIC_COUNT:
                        continue
                    # Fall through to apply this relic bonus
                else:
                    continue

            # Check if all required techs are available to this civ
            # This handles conditional bonuses like Mongol "+30% HP + BL" which requires Bloodlines
            required_techs = tech_data.get("required_techs", [])
            disabled_techs = self.get_disabled_techs(civ_name)
            has_non_age_requirement = False
            all_required_available = True
            for req_tech in required_techs:
                # Skip age tech IDs (they're not researchable techs)
                if req_tech in AGE_TECH_IDS:
                    continue
                has_non_age_requirement = True
                # Check if the required tech is disabled for this civ
                if req_tech in disabled_techs:
                    all_required_available = False
                    break

            if not all_required_available:
                continue

            # Skip non-conditional variants if civ has the conditional version available
            # E.g., if Mongols have Bloodlines, use "+30% HP + BL" version, not "+30% HP"
            # The "+BL" versions are designed to work WITH Bloodlines, non-BL versions are fallbacks
            if not has_non_age_requirement and "+ BL" not in tech_name:
                # This is a non-conditional version - check if a conditional version exists
                base_bonus_pattern = tech_name.replace("C-Bonus, ", "")
                skip_this = False
                for other_tech_id in tech_ids:
                    other_tech = self.techs.get(other_tech_id, {})
                    other_name = other_tech.get("name", "")
                    if "+ BL" in other_name and base_bonus_pattern in other_name:
                        # Found a "+BL" version - check if it's available
                        other_reqs = other_tech.get("required_techs", [])
                        other_available = True
                        for req in other_reqs:
                            if req not in AGE_TECH_IDS and req in disabled_techs:
                                other_available = False
                                break
                        if other_available:
                            skip_this = True
                            break
                if skip_this:
                    continue

            # Check age requirements recursively
            # This handles cases where a bonus requires another tech (e.g., Double Forging requires Forging)
            bonus_age = self.get_tech_age_recursive(tech_id)

            if bonus_age > max_age:
                continue

            for cmd in te.get("commands", []):
                if self.effect_applies_to_unit(cmd, unit_id, unit_class):
                    relevant.append(te)
                    break

        return relevant

    def get_unique_techs_for_unit(
        self, civ_name: str, unit_id: int, unit_class: int, max_age: int = 4
    ) -> list:
        """Get civ-specific unique techs (Castle/Imperial Age) that affect this unit."""
        civ_id = self.civ_name_to_id.get(civ_name, -1)
        if civ_id < 0:
            return []

        relevant = []

        # Find all techs for this civ that have a cost (unique techs)
        for tech_id, tech_data in self.techs.items():
            if tech_id in REMOVED_TECHS:
                continue
            # Must be for this civ
            if tech_data.get("civ", -1) != civ_id:
                continue

            # Must have a cost (unique techs have research cost)
            if not tech_data.get("cost"):
                continue

            # Must not be a C-Bonus tech
            tech_name = tech_data.get("name", "")
            if tech_name.startswith("C-Bonus"):
                continue

            # Check age requirement
            tech_age = self.get_tech_age_recursive(tech_id)
            if tech_age > max_age:
                continue

            # Check if this tech affects our unit
            if tech_id not in self.tech_effect_map:
                continue

            te = self.tech_effect_map[tech_id]
            for cmd in te.get("commands", []):
                if self.effect_applies_to_unit(cmd, unit_id, unit_class):
                    te_with_name = dict(te)
                    te_with_name["tech_name"] = tech_name
                    relevant.append(te_with_name)
                    break

        return relevant

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

    def calculate_upgrade_cost(
        self, civ_name: str, relevant_techs: set, disabled_techs: set
    ) -> int:
        """Calculate total upgrade cost for relevant techs (with civ discount)."""
        discount_map = CIV_TECH_COST_DISCOUNT.get(civ_name, {})
        total = 0
        for tech_id in relevant_techs:
            if tech_id in disabled_techs:
                continue
            tech_data = self.techs.get(tech_id, {})
            base_cost = tech_data.get("cost", {})
            tech_age = self.get_tech_age_recursive(tech_id)
            age_name = _tech_age_name(tech_age)
            discount = discount_map.get(age_name, 0)
            mult = 1.0 - discount
            for val in base_cost.values():
                total += round(val * mult)
        return total

    def calculate_unit_stats_for_civ(
        self, civ_name: str, unit_config: dict, max_age: int
    ) -> dict:
        """
        Calculate stats for a unit for a specific civ at a given age.

        Returns dict with:
        - unit_name: Final unit name after upgrades
        - stats: UnitStats object
        - has_unit: Whether the civ has this unit
        - applied_bonuses: List of applied civ bonuses
        """
        disabled_techs = self.get_disabled_techs(civ_name)

        # Check for alternate unit (e.g., Armored Elephant instead of Ram)
        alternate = unit_config.get("alternate")
        use_alternate = False

        if alternate:
            main_avail_tech = unit_config.get("availability_tech")
            alt_avail_tech = alternate.get("availability_tech")

            # Use alternate if main unit is disabled but alternate is available
            if main_avail_tech and main_avail_tech in disabled_techs:
                if alt_avail_tech and alt_avail_tech not in disabled_techs:
                    use_alternate = True

        # Track if we're using civ-specific upgrades (skip age check for these)
        using_civ_upgrades = False

        if use_alternate:
            base_id = alternate["base_id"]
            base_unit = self.get_unit(base_id)
            base_name = alternate["display_name"]
            upgrades = alternate.get("upgrades", [])
        else:
            base_id = unit_config["base_id"]
            base_unit = self.get_unit(base_id)
            base_name = unit_config["display_name"]
            upgrades = unit_config.get("upgrades", [])

            # Check for civ-specific upgrades (e.g., Burgundians Cavalier in Castle Age)
            civ_upgrades = unit_config.get("civ_upgrades", {})
            if civ_name in civ_upgrades:
                upgrades = civ_upgrades[civ_name]
                using_civ_upgrades = True  # Skip age check for civ-specific upgrades

        # Check if civ has access to this unit
        avail_tech = unit_config.get("availability_tech")
        if not use_alternate and avail_tech and avail_tech in disabled_techs:
            return {
                "unit_name": base_name,
                "stats": None,
                "has_unit": False,
                "applied_bonuses": [],
            }

        # For alternate units, check if they have access
        if use_alternate:
            alt_avail_tech = alternate.get("availability_tech")
            if alt_avail_tech and alt_avail_tech in disabled_techs:
                return {
                    "unit_name": base_name,
                    "stats": None,
                    "has_unit": False,
                    "applied_bonuses": [],
                }

        # Find highest available upgrade
        final_unit_id = base_id
        final_unit_name = base_name

        for tech_id, upgraded_id, upgraded_name in upgrades:
            if tech_id not in disabled_techs:
                # For civ-specific upgrades, skip age check (they're explicitly available)
                if using_civ_upgrades:
                    final_unit_id = upgraded_id
                    final_unit_name = upgraded_name
                else:
                    # Check if this upgrade is available at the current age
                    tech_age = self.get_tech_age(tech_id)
                    if tech_age <= max_age:
                        final_unit_id = upgraded_id
                        final_unit_name = upgraded_name

        # If no upgrades were applied, use the Castle-age name for the base unit
        # (e.g., "Pikeman" instead of config display_name "Halberdier")
        if final_unit_id == base_id and base_id in _PREVIOUS_AGE_NAMES:
            final_unit_name = _PREVIOUS_AGE_NAMES[base_id]

        # Get the unit data
        unit = self.get_unit(final_unit_id)
        if not unit:
            # Fallback to base unit
            unit = self.get_unit(base_id)
            final_unit_name = base_name

        if not unit:
            return {
                "unit_name": final_unit_name,
                "stats": None,
                "has_unit": False,
                "applied_bonuses": [],
            }

        # Calculate stats
        unit_class = unit_config["unit_class"]
        stats = self.get_base_stats(unit)
        applied_bonuses = []

        # Apply standard techs FIRST (e.g., Bloodlines adds HP before civ bonuses multiply)
        standard_techs = self.find_techs_affecting_unit(
            final_unit_id, unit_class, max_age
        )

        for tech_id in sorted(standard_techs):
            if tech_id in disabled_techs:
                continue

            if tech_id in self.tech_effect_map:
                te = self.tech_effect_map[tech_id]
                for cmd in te.get("commands", []):
                    self.apply_effect_command(cmd, stats, final_unit_id, unit_class)

        # Apply civ bonus techs AFTER standard techs
        # This ensures additive bonuses (like Bloodlines +20 HP) are applied before
        # multiplicative civ bonuses
        civ_bonus_techs = self.get_civ_bonus_techs_for_unit(
            civ_name, final_unit_id, unit_class, max_age
        )
        for te in civ_bonus_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, final_unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply team bonus attack bonuses (e.g., Persians Knights +2 vs Archers)
        team_atk_bonuses = CIV_TEAM_BONUS_ATTACK.get(civ_name, [])
        for bonus in team_atk_bonuses:
            if len(bonus) == 3:
                b_unit_id, atk_class, amount = bonus
                if b_unit_id == final_unit_id:
                    if atk_class in stats.attacks:
                        stats.attacks[atk_class] += amount
                    else:
                        stats.attacks[atk_class] = amount
                    applied_bonuses.append(f"{civ_name} Team Bonus")
            elif len(bonus) == 4:
                b_unit_id, atk_class, amount, b_class_id = bonus
                if b_unit_id == -1 and b_class_id == unit_class:
                    if atk_class in stats.attacks:
                        stats.attacks[atk_class] += amount
                    else:
                        stats.attacks[atk_class] = amount
                    applied_bonuses.append(f"{civ_name} Team Bonus")

        # Apply unique techs (Castle/Imperial Age civ-specific techs like Garland Wars)
        unique_techs = self.get_unique_techs_for_unit(
            civ_name, final_unit_id, unit_class, max_age
        )
        for te in unique_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, final_unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Calculate upgrade cost
        upgrade_cost = self.calculate_upgrade_cost(
            civ_name, standard_techs, disabled_techs
        )
        stats.upgrade_cost = upgrade_cost

        # Apply building work rate to creation time
        building_id = UNIT_CLASS_TO_BUILDING.get(unit_class)
        if building_id and stats.train_time > 0:
            work_rate = self.get_building_work_rate(civ_name, building_id, max_age)
            if work_rate > 1.0:
                stats.train_time = stats.train_time / work_rate
                civ_id = self.civ_name_to_id.get(civ_name, -1)
                for tech_id, (
                    tech_civ_id,
                    bldg_mults,
                ) in BUILDING_WORK_RATE_TECHS.items():
                    if building_id in bldg_mults:
                        if tech_id not in disabled_techs:
                            if tech_civ_id == -1 or tech_civ_id == civ_id:
                                tech_age = self.get_tech_age_recursive(tech_id)
                                if tech_age <= max_age:
                                    te = self.tech_effect_map.get(tech_id, {})
                                    tname = te.get("tech_name", f"Tech {tech_id}")
                                    if tname not in applied_bonuses:
                                        applied_bonuses.append(tname)

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
            "unit_name": final_unit_name,
            "unit_id": final_unit_id,
            "stats": stats,
            "has_unit": True,
            "applied_bonuses": applied_bonuses,
        }

    def calculate_unique_unit_stats(
        self, civ_name: str, uu_config: dict, max_age: int, elite: bool = False
    ) -> dict:
        """
        Calculate stats for a unique unit for its civilization.

        Args:
            civ_name: The civilization name
            uu_config: Unique unit configuration dict
            max_age: Maximum age (CASTLE_AGE or IMPERIAL_AGE)
            elite: Whether to calculate elite version stats

        Returns dict with:
        - stats: UnitStats object
        - has_unit: Whether the civ has this unit
        - applied_bonuses: List of applied civ bonuses
        """
        # Get the unit ID based on elite status
        if elite:
            unit_id = uu_config.get("elite_id", uu_config["base_id"])
            unit_name = uu_config.get(
                "elite_name", f"Elite {uu_config['display_name']}"
            )
        else:
            unit_id = uu_config["base_id"]
            unit_name = uu_config["display_name"]

        unit = self.get_unit(unit_id)
        if not unit:
            return {
                "unit_id": unit_id,
                "stats": None,
                "has_unit": False,
                "applied_bonuses": [],
            }

        unit_class = uu_config["unit_class"]
        stats = self.get_base_stats(unit)
        applied_bonuses = []

        # Apply standard techs (blacksmith upgrades, etc.)
        standard_techs = self.find_techs_affecting_unit(unit_id, unit_class, max_age)
        disabled_techs = self.get_disabled_techs(civ_name)

        for tech_id in sorted(standard_techs):
            if tech_id in disabled_techs:
                continue

            if tech_id in self.tech_effect_map:
                te = self.tech_effect_map[tech_id]
                for cmd in te.get("commands", []):
                    self.apply_effect_command(cmd, stats, unit_id, unit_class)

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

        # Apply team bonus attack bonuses
        team_atk_bonuses = CIV_TEAM_BONUS_ATTACK.get(civ_name, [])
        for bonus in team_atk_bonuses:
            if len(bonus) == 3:
                b_unit_id, atk_class, amount = bonus
                if b_unit_id == unit_id:
                    if atk_class in stats.attacks:
                        stats.attacks[atk_class] += amount
                    else:
                        stats.attacks[atk_class] = amount
                    applied_bonuses.append(f"{civ_name} Team Bonus")
            elif len(bonus) == 4:
                b_unit_id, atk_class, amount, b_class_id = bonus
                if b_unit_id == -1 and b_class_id == unit_class:
                    if atk_class in stats.attacks:
                        stats.attacks[atk_class] += amount
                    else:
                        stats.attacks[atk_class] = amount
                    applied_bonuses.append(f"{civ_name} Team Bonus")

        # Apply unique techs (Castle/Imperial Age civ-specific techs like Garland Wars)
        unique_techs = self.get_unique_techs_for_unit(
            civ_name, unit_id, unit_class, max_age
        )
        for te in unique_techs:
            tech_name = te.get("tech_name", f"Tech {te['tech_id']}")
            for cmd in te.get("commands", []):
                if self.apply_effect_command(cmd, stats, unit_id, unit_class):
                    if tech_name not in applied_bonuses:
                        applied_bonuses.append(tech_name)

        # Apply building work rate to creation time
        # Unique units default to Castle; some can also be created in Barracks
        disabled_techs = self.get_disabled_techs(civ_name)
        if stats.train_time > 0:
            unit_slug = unit_name.lower().replace(" ", "_").replace("-", "_")
            castle_rate = self.get_building_work_rate(
                civ_name, UNIQUE_UNIT_BUILDING, max_age
            )
            # Check if this unit can also be created in Barracks
            barracks_key = (civ_name, unit_slug)
            if barracks_key in UNIQUE_UNITS_IN_BARRACKS:
                barracks_id = UNIQUE_UNITS_IN_BARRACKS[barracks_key]
                barracks_rate = self.get_building_work_rate(
                    civ_name, barracks_id, max_age
                )
                best_rate = max(castle_rate, barracks_rate)
            else:
                best_rate = castle_rate

            if best_rate > 1.0:
                stats.train_time = stats.train_time / best_rate
                # Determine which building gives best rate for bonus tracking
                best_building = UNIQUE_UNIT_BUILDING
                if barracks_key in UNIQUE_UNITS_IN_BARRACKS:
                    barracks_id = UNIQUE_UNITS_IN_BARRACKS[barracks_key]
                    if (
                        self.get_building_work_rate(civ_name, barracks_id, max_age)
                        > castle_rate
                    ):
                        best_building = barracks_id
                civ_id = self.civ_name_to_id.get(civ_name, -1)
                for tech_id, (
                    tech_civ_id,
                    bldg_mults,
                ) in BUILDING_WORK_RATE_TECHS.items():
                    if best_building in bldg_mults:
                        if tech_id not in disabled_techs:
                            if tech_civ_id == -1 or tech_civ_id == civ_id:
                                tech_age = self.get_tech_age_recursive(tech_id)
                                if tech_age <= max_age:
                                    te = self.tech_effect_map.get(tech_id, {})
                                    tname = te.get("tech_name", f"Tech {tech_id}")
                                    if tname not in applied_bonuses:
                                        applied_bonuses.append(tname)

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
        stats.reload_time = round(stats.reload_time, 3)
        stats.range = round(stats.range, 1)

        return {
            "unit_id": unit_id,
            "stats": stats,
            "has_unit": True,
            "applied_bonuses": applied_bonuses,
        }


