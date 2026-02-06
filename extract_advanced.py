#!/usr/bin/env python3
"""
Advanced AoE2:DE Data Extractor
Extracts:
- Effects and their commands (civ bonuses, tech effects)
- Disabled units/techs per civilization
- Team bonuses
- Technology effects
"""

import json
from pathlib import Path

from genieutils.datfile import DatFile

# Effect command type definitions
EFFECT_COMMAND_TYPES = {
    0: "SET_ATTRIBUTE",  # Set unit attribute to value
    1: "ADD_RESOURCE",  # Add to resource
    2: "ENABLE_DISABLE_UNIT",  # Enable/disable unit
    3: "UPGRADE_UNIT",  # Upgrade unit A to unit B
    4: "ADD_ATTRIBUTE",  # Add value to unit attribute
    5: "MULTIPLY_ATTRIBUTE",  # Multiply unit attribute by value
    6: "MULTIPLY_RESOURCE",  # Multiply resource by value
    7: "SPAWN_UNIT",  # Spawn unit at location
    8: "RESEARCH_COST_MOD",  # Modify tech cost
    10: "TEAM_ATTRIBUTE",  # Team-wide attribute modifier
    12: "ENABLE_TECH",  # Enable tech
    15: "TEAM_MULTIPLY_ATTR",  # Team multiply attribute
    18: "TECH_COST_ABS",  # Set tech cost absolute
    26: "MODIFY_TECH",  # Modify tech
    40: "RENAME_UNIT",  # Rename unit
    101: "TECH_COST_SET",  # Set technology cost
    102: "DISABLE_TECH",  # Disable technology
    103: "DISABLE_UNIT",  # Disable unit
    200: "ADD_ATTACK",  # Add attack class
    201: "ADD_ARMOR",  # Add armor class
    202: "MODIFY_ARMOR",  # Modify armor value
    204: "SET_ATTACK_ARMOR",  # Set attack/armor
    255: "NO_EFFECT",  # No effect / placeholder
}

# Unit attribute IDs
UNIT_ATTRIBUTES = {
    0: "hit_points",
    1: "line_of_sight",
    2: "garrison_capacity",
    3: "unit_size_x",
    4: "unit_size_y",
    5: "movement_speed",
    6: "rotation_speed",
    8: "armor",  # Add to armor class
    9: "attack",  # Add to attack class
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
}

# Civilization names
CIV_NAMES = [
    "Gaia",  # 0
    "Britons",
    "Franks",
    "Goths",
    "Teutons",
    "Japanese",
    "Chinese",
    "Byzantines",
    "Persians",
    "Saracens",
    "Turks",  # 10
    "Vikings",
    "Mongols",
    "Celts",
    "Spanish",
    "Aztecs",
    "Mayans",
    "Huns",
    "Koreans",
    "Italians",
    "Indians",  # 20 (was Hindustanis)
    "Incas",
    "Magyars",
    "Slavs",
    "Portuguese",
    "Ethiopians",
    "Malians",
    "Berbers",
    "Khmer",
    "Malay",
    "Burmese",  # 30
    "Vietnamese",
    "Bulgarians",
    "Tatars",
    "Cumans",
    "Lithuanians",
    "Burgundians",
    "Sicilians",
    "Poles",
    "Bohemians",
    "Dravidians",  # 40
    "Bengalis",
    "Gurjaras",
    "Romans",
    "Armenians",
    "Georgians",  # 45
    # Chronicles DLC - Age of Antiquity (not in ranked play)
    None,  # 46 Achaemenids - skip
    None,  # 47 Athenians - skip
    None,  # 48 Spartans - skip
    # Three Kingdoms DLC (in ranked play)
    "Shu",  # 49
    "Wu",  # 50
    "Wei",  # 51
    "Jurchens",  # 52
    "Khitans",  # 53
    # Chronicles DLC - Alexander (not in ranked play)
    None,  # 54 Macedonians - skip
    None,  # 55 Thracians - skip
    None,  # 56 Puru - skip
]


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

    # Add human-readable interpretation based on type
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
        # Decode the 'd' value for attack/armor
        # Packing: d = class * 256 + amount (negative d means negative amount)
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
    """Extract all effects with their commands."""
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


def extract_civ_tech_trees(df, effects, techs_by_id, units_by_id):
    """Extract tech tree (disabled units/techs) for each civilization."""
    civ_data = []

    for civ_id, civ in enumerate(df.civs):
        if civ_id == 0 or civ_id >= len(CIV_NAMES):
            continue

        civ_name = CIV_NAMES[civ_id]
        if civ_name is None:
            continue  # Skip non-ranked play civs
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


def extract_tech_effects(df, techs):
    """Extract effect details for each technology."""
    tech_effects = []

    for tech in techs:
        if "effect_id" not in tech:
            continue

        effect_id = tech.get("effect_id", -1)
        if effect_id < 0 or effect_id >= len(df.effects):
            continue

        effect = df.effects[effect_id]
        if not effect.effect_commands:
            continue

        tech_effect = {
            "tech_id": tech["id"],
            "tech_name": tech["name"],
            "effect_id": effect_id,
            "effect_name": effect.name,
            "commands": [parse_effect_command(cmd) for cmd in effect.effect_commands],
        }
        tech_effects.append(tech_effect)

    return tech_effects


def find_unit_affecting_effects(df, unit_id, units_by_id):
    """Find all effects that modify a specific unit."""
    affecting_effects = []

    for i, effect in enumerate(df.effects):
        relevant_commands = []
        for cmd in effect.effect_commands:
            # Check if this command affects the unit
            if cmd.a == unit_id:
                relevant_commands.append(parse_effect_command(cmd))
            # Also check for class-based effects (b=-1 means all units)
            elif cmd.a == -1 and cmd.type in [4, 5]:
                # This affects all units, might apply to our unit
                relevant_commands.append(parse_effect_command(cmd))

        if relevant_commands:
            affecting_effects.append(
                {
                    "effect_id": i,
                    "effect_name": effect.name,
                    "commands": relevant_commands,
                }
            )

    return affecting_effects


def main():
    dat_path = Path(__file__).parent / "empires2_x2_p1.dat"
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"Loading {dat_path}...")
    df = DatFile.parse(dat_path)
    print(f"Loaded successfully!")

    # Load existing unit and tech data for name lookups
    print("\nLoading existing data for name lookups...")
    with open(output_dir / "units.json") as f:
        units = json.load(f)
    units_by_id = {u["id"]: u for u in units}

    with open(output_dir / "technologies.json") as f:
        techs = json.load(f)
    techs_by_id = {t["id"]: t for t in techs}

    # Extract effects
    print("\nExtracting effects...")
    effects = extract_effects(df)
    print(f"  Extracted {len(effects)} effects with commands")

    with open(output_dir / "effects.json", "w") as f:
        json.dump(effects, f, indent=2)
    print(f"  Saved to output/effects.json")

    # Extract civ tech trees and bonuses
    print("\nExtracting civilization tech trees and bonuses...")
    civ_tech_trees = extract_civ_tech_trees(df, effects, techs_by_id, units_by_id)
    print(f"  Extracted data for {len(civ_tech_trees)} civilizations")

    with open(output_dir / "civ_tech_trees.json", "w") as f:
        json.dump(civ_tech_trees, f, indent=2)
    print(f"  Saved to output/civ_tech_trees.json")

    # Extract tech effects (what each tech does)
    print("\nExtracting technology effects...")
    # First, get effect_id for each tech
    techs_with_effects = []
    for i, tech in enumerate(df.techs):
        if tech is None:
            continue
        name = getattr(tech, "name", "").strip()
        if not name or name.startswith("YOURITEMHERE"):
            continue

        effect_id = getattr(tech, "effect_id", -1)
        techs_with_effects.append({"id": i, "name": name, "effect_id": effect_id})

    tech_effects = extract_tech_effects(df, techs_with_effects)
    print(f"  Extracted effects for {len(tech_effects)} technologies")

    with open(output_dir / "tech_effects.json", "w") as f:
        json.dump(tech_effects, f, indent=2)
    print(f"  Saved to output/tech_effects.json")

    # Example: Find all effects affecting Knight (ID 38)
    print("\n" + "=" * 70)
    print("EXAMPLE: Effects affecting Knight (ID: 38)")
    print("=" * 70)

    knight_effects = find_unit_affecting_effects(df, 38, units_by_id)
    print(f"\nFound {len(knight_effects)} effects that modify Knight:")
    for eff in knight_effects[:15]:
        print(f"\n  {eff['effect_name']} (Effect ID: {eff['effect_id']}):")
        for cmd in eff["commands"][:3]:
            if "description" in cmd:
                print(f"    - {cmd['description']}")

    # Summary of disabled units for meso civs
    print("\n" + "=" * 70)
    print("DISABLED UNITS BY CIVILIZATION (sample)")
    print("=" * 70)

    for civ in civ_tech_trees:
        if civ["disabled_units"]:
            print(f"\n{civ['name']}:")
            for unit in civ["disabled_units"][:10]:
                print(f"  - {unit['name']} (ID: {unit['id']})")

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"\nNew files created in {output_dir}/:")
    print(f"  - effects.json         ({len(effects)} effects)")
    print(f"  - civ_tech_trees.json  ({len(civ_tech_trees)} civilizations)")
    print(f"  - tech_effects.json    ({len(tech_effects)} tech effects)")


if __name__ == "__main__":
    main()
