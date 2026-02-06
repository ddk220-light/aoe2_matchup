"""Extract effects, civ tech trees, and tech effects from dat file."""

from .extract_constants import CIV_NAMES

# Effect command type definitions
EFFECT_COMMAND_TYPES = {
    0: "SET_ATTRIBUTE",
    1: "ADD_RESOURCE",
    2: "ENABLE_DISABLE_UNIT",
    3: "UPGRADE_UNIT",
    4: "ADD_ATTRIBUTE",
    5: "MULTIPLY_ATTRIBUTE",
    6: "MULTIPLY_RESOURCE",
    7: "SPAWN_UNIT",
    8: "RESEARCH_COST_MOD",
    10: "TEAM_ATTRIBUTE",
    12: "ENABLE_TECH",
    15: "TEAM_MULTIPLY_ATTR",
    18: "TECH_COST_ABS",
    26: "MODIFY_TECH",
    40: "RENAME_UNIT",
    101: "TECH_COST_SET",
    102: "DISABLE_TECH",
    103: "DISABLE_UNIT",
    200: "ADD_ATTACK",
    201: "ADD_ARMOR",
    202: "MODIFY_ARMOR",
    204: "SET_ATTACK_ARMOR",
    255: "NO_EFFECT",
}

# Unit attribute IDs used in effect commands
UNIT_ATTRIBUTES = {
    0: "hit_points",
    1: "line_of_sight",
    2: "garrison_capacity",
    3: "unit_size_x",
    4: "unit_size_y",
    5: "movement_speed",
    6: "rotation_speed",
    8: "armor",
    9: "attack",
    10: "attack_reload_time",
    11: "accuracy_percent",
    12: "max_range",
    13: "work_rate",
    14: "carry_capacity",
    15: "base_armor",
    16: "projectile_unit",
    17: "icon_graphics_angle",
    19: "train_time",
    20: "total_missiles",
    21: "food_cost",
    22: "wood_cost",
    23: "gold_cost",
    24: "stone_cost",
    25: "max_total_missiles",
    54: "search_radius",
    59: "charge_attack",
    60: "charge_recharge_rate",
    61: "charge_event",
    62: "charge_type",
    63: "attack_dispersion",
    100: "resource_cost",
    101: "train_time_mod",
    103: "food_cost_abs",
    105: "gold_cost_abs",
    108: "garrison_heal_rate",
    109: "hp_regen",
}


def parse_effect_command(cmd):
    """Parse an effect command into a readable dict."""
    cmd_type = EFFECT_COMMAND_TYPES.get(cmd.type, f"UNKNOWN_{cmd.type}")

    result = {
        "type": cmd.type,
        "type_name": cmd_type,
        "a": cmd.a,
        "b": cmd.b,
        "c": cmd.c,
        "d": cmd.d,
    }

    if cmd.type == 0:  # SET_ATTRIBUTE
        result["unit_id"] = cmd.a
        result["attribute"] = UNIT_ATTRIBUTES.get(cmd.c, f"attr_{cmd.c}")
        result["value"] = cmd.d
        result["description"] = f"Set unit {cmd.a} {result['attribute']} to {cmd.d}"
    elif cmd.type == 2:  # ENABLE_DISABLE_UNIT
        result["unit_id"] = cmd.a
        result["enable"] = cmd.b == 1
        result["description"] = f"{'Enable' if cmd.b == 1 else 'Disable'} unit {cmd.a}"
    elif cmd.type == 3:  # UPGRADE_UNIT
        result["from_unit"] = cmd.a
        result["to_unit"] = cmd.b
        result["description"] = f"Upgrade unit {cmd.a} to {cmd.b}"
    elif cmd.type == 4:  # ADD_ATTRIBUTE
        result["unit_id"] = cmd.a
        result["class_id"] = cmd.b
        result["attribute"] = UNIT_ATTRIBUTES.get(cmd.c, f"attr_{cmd.c}")
        result["amount"] = cmd.d
        if cmd.c in [8, 9]:  # armor or attack
            abs_d = abs(int(cmd.d))
            sign = 1 if cmd.d >= 0 else -1
            if abs_d >= 256:
                armor_class = abs_d // 256
                armor_amount = (abs_d % 256) * sign
                result["armor_class"] = armor_class
                result["armor_amount"] = armor_amount
                result["description"] = (
                    f"Add {armor_amount} to unit {cmd.a} {'armor' if cmd.c == 8 else 'attack'} class {armor_class}"
                )
            else:
                result["description"] = (
                    f"Add to unit {cmd.a} {result['attribute']}: {cmd.d}"
                )
        else:
            result["description"] = f"Add {cmd.d} to unit {cmd.a} {result['attribute']}"
    elif cmd.type == 5:  # MULTIPLY_ATTRIBUTE
        result["unit_id"] = cmd.a
        result["class_id"] = cmd.b
        result["attribute"] = UNIT_ATTRIBUTES.get(cmd.c, f"attr_{cmd.c}")
        result["multiplier"] = cmd.d
        result["description"] = (
            f"Multiply unit {cmd.a} {result['attribute']} by {cmd.d:.2f}"
        )
    elif cmd.type == 102:  # DISABLE_TECH
        result["tech_id"] = int(cmd.d)
        result["description"] = f"Disable tech {int(cmd.d)}"
    elif cmd.type == 103:  # DISABLE_UNIT
        result["unit_id"] = cmd.a
        result["description"] = f"Disable unit {cmd.a}"

    return result


def extract_effects(df):
    """Extract all effects with their commands.

    Args:
        df: Parsed DatFile object.
    Returns:
        List of effect dicts with id, name, and commands.
    """
    effects = []
    for i, effect in enumerate(df.effects):
        if not effect.effect_commands:
            continue

        effect_data = {
            "id": i,
            "name": effect.name if effect.name else f"Effect_{i}",
            "commands": [parse_effect_command(cmd) for cmd in effect.effect_commands],
        }
        effects.append(effect_data)

    return effects


def extract_civ_tech_trees(df, techs_by_id, units_by_id):
    """Extract tech tree (disabled units/techs) for each civilization.

    Args:
        df: Parsed DatFile object.
        techs_by_id: Dict of tech_id -> tech data dict (for name lookups).
        units_by_id: Dict of unit_id -> unit data dict (for name lookups).
    Returns:
        List of civ tech tree dicts.
    """
    civ_data = []

    for civ_id, civ in enumerate(df.civs):
        if civ_id == 0 or civ_id >= len(CIV_NAMES):
            continue

        civ_name = CIV_NAMES[civ_id]
        if civ_name is None:
            continue

        tech_tree_id = civ.tech_tree_id
        team_bonus_id = civ.team_bonus_id

        data = {
            "id": civ_id,
            "name": civ_name,
            "internal_name": civ.name,
            "tech_tree_effect_id": tech_tree_id,
            "team_bonus_effect_id": team_bonus_id,
            "disabled_techs": [],
            "disabled_units": [],
            "team_bonus": None,
            "civ_bonuses": [],
        }

        # Get disabled techs/units from tech tree effect
        if 0 <= tech_tree_id < len(df.effects):
            effect = df.effects[tech_tree_id]
            for cmd in effect.effect_commands:
                if cmd.type == 102:  # Disable tech
                    tech_id = int(cmd.d)
                    tech_name = techs_by_id.get(tech_id, {}).get(
                        "name", f"Tech_{tech_id}"
                    )
                    data["disabled_techs"].append({"id": tech_id, "name": tech_name})
                elif cmd.type == 103:  # Disable unit
                    unit_id = int(cmd.a)
                    unit_name = units_by_id.get(unit_id, {}).get(
                        "name", f"Unit_{unit_id}"
                    )
                    data["disabled_units"].append({"id": unit_id, "name": unit_name})

        # Get team bonus
        if 0 <= team_bonus_id < len(df.effects):
            effect = df.effects[team_bonus_id]
            data["team_bonus"] = {
                "effect_id": team_bonus_id,
                "name": effect.name,
                "commands": [
                    parse_effect_command(cmd) for cmd in effect.effect_commands
                ],
            }

        civ_data.append(data)

    return civ_data


def extract_tech_effects(df):
    """Extract effect details for each technology.

    Args:
        df: Parsed DatFile object.
    Returns:
        List of tech effect dicts.
    """
    tech_effects = []

    for i, tech in enumerate(df.techs):
        if tech is None:
            continue
        name = getattr(tech, "name", "").strip()
        if not name or name.startswith("YOURITEMHERE"):
            continue

        effect_id = getattr(tech, "effect_id", -1)
        if effect_id < 0 or effect_id >= len(df.effects):
            continue

        effect = df.effects[effect_id]
        if not effect.effect_commands:
            continue

        tech_effect = {
            "tech_id": i,
            "tech_name": name,
            "effect_id": effect_id,
            "effect_name": effect.name,
            "commands": [parse_effect_command(cmd) for cmd in effect.effect_commands],
        }
        tech_effects.append(tech_effect)

    return tech_effects
