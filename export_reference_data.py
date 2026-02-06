#!/usr/bin/env python3
"""Export reference database to a .md file with JSON data and verification instructions."""

import json
import sqlite3
from pathlib import Path

OUTPUT_DIR = Path("output")
REF_DB_PATH = Path("webapp/aoe2_reference.db")
EXPORT_PATH = Path("reference_data_export.md")


def load_armor_class_names():
    """Load armor class ID -> name mapping."""
    with open(OUTPUT_DIR / "armor_classes.json") as f:
        classes = json.load(f)
    return {str(ac["id"]): ac["name"] for ac in classes}


def export():
    ac_names = load_armor_class_names()
    conn = sqlite3.connect(REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Build data organized by civ
    data = {}
    c.execute(
        "SELECT * FROM ref_units ORDER BY civ_name, age DESC, unit_name"
    )  # Castle before Imperial
    for row in c.fetchall():
        civ = row["civ_name"]
        if civ not in data:
            data[civ] = []

        # Convert attack/armor JSON from numeric IDs to readable names
        def convert_classes(json_str):
            if not json_str:
                return {}
            raw = json.loads(json_str)
            return {ac_names.get(k, f"class_{k}"): v for k, v in raw.items()}

        # Get upgrades applied
        c2 = conn.cursor()
        c2.execute(
            """SELECT tech_name, tech_type, building, age_available, effect_description
               FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id""",
            (row["id"],),
        )
        upgrades = []
        for t in c2.fetchall():
            upgrades.append(
                {
                    "tech_name": t["tech_name"],
                    "type": t["tech_type"],
                    "building": t["building"],
                    "age": t["age_available"],
                    "effect": t["effect_description"],
                }
            )

        # Get special properties
        c2.execute(
            """SELECT property_name, property_value, source
               FROM ref_special_effects WHERE ref_unit_id=?""",
            (row["id"],),
        )
        special = {}
        for s in c2.fetchall():
            special[s["property_name"]] = {
                "value": s["property_value"],
                "source": s["source"],
            }

        unit = {
            "unit_name": row["unit_name"],
            "age": row["age"],
            "unit_class": row["unit_class_name"],
            "is_ranged": bool(row["is_ranged"]),
            "base_stats": {
                "hp": row["base_hp"],
                "attack": row["base_attack"],
                "melee_armor": row["base_melee_armor"],
                "pierce_armor": row["base_pierce_armor"],
                "range": row["base_range"],
                "speed": row["base_speed"],
                "reload_time": row["base_reload_time"],
                "attack_delay": row["base_attack_delay"],
                "accuracy": row["base_accuracy"],
                "los": row["base_los"],
                "cost": {
                    "food": row["base_cost_food"],
                    "wood": row["base_cost_wood"],
                    "gold": row["base_cost_gold"],
                },
            },
            "final_stats": {
                "hp": row["final_hp"],
                "attack": row["final_attack"],
                "melee_armor": row["final_melee_armor"],
                "pierce_armor": row["final_pierce_armor"],
                "range": row["final_range"],
                "speed": row["final_speed"],
                "reload_time": row["final_reload_time"],
                "accuracy": row["final_accuracy"],
                "los": row["final_los"],
            },
            "base_attack_classes": convert_classes(row["base_attacks_json"]),
            "final_attack_classes": convert_classes(row["final_attacks_json"]),
            "final_armor_classes": convert_classes(row["final_armors_json"]),
            "upgrades_applied": upgrades,
            "special_properties": special,
            "projectile_speed": row["projectile_speed"],
            "total_projectiles": row["total_projectiles"],
            "min_range": row["min_range"],
        }
        data[civ].append(unit)

    conn.close()

    # Write the .md file
    instructions = """# AoE2 Unit Stats Reference Data - Verification Request

## Instructions

You are given extracted unit stats data for Age of Empires II: Definitive Edition, covering 13 original civilizations. Your task is to verify this data against reliable online sources and produce a mismatch report.

### Scope
- 13 civilizations: Britons, Byzantines, Celts, Chinese, Franks, Goths, Japanese, Mongols, Persians, Saracens, Teutons, Turks, Vikings
- Castle Age and Imperial Age military units (fully upgraded for that age)
- Standard units and unique units

### What to verify

For each civilization's units, compare the following against the AoE2 wiki (https://ageofempires.fandom.com/wiki/Age_of_Empires_II) or other reliable AoE2:DE sources:

1. **Base stats** (before any techs): HP, attack, melee armor, pierce armor, range, speed, reload time, attack delay, accuracy, LOS, cost
2. **Upgrades available**: Which blacksmith, university, stable, archery range, barracks, monastery, and unique techs are available to each civ
3. **Final fully-upgraded stats**: The stats after all available techs for that civ and age are applied
4. **Attack classes**: Bonus damage values against unit classes (e.g., Pikeman bonus vs Cavalry)
5. **Armor classes**: Which armor classes the unit has and their values
6. **Special properties**: Trample damage, splash radius, ignore armor, etc.

### Important notes
- "attack" in base_stats refers to the unit's main attack class value (Base Pierce for ranged, Base Melee for melee). The full breakdown is in base_attack_classes/final_attack_classes.
- "final_stats.attack" stores the same main class value as base - check final_attack_classes for the actual upgraded value
- Reload time is in seconds (e.g., 2.0 = fires every 2 seconds)
- Speed is tiles per second
- Accuracy is a percentage (50 = 50%)
- Cost values of 0 mean that resource is not required

### Output format

Produce a document titled "AoE2 Reference Data Mismatch Report" with:

1. **Summary**: Total units checked, total mismatches found
2. **Mismatches by civilization**: For each civ with mismatches, list:
   - Unit name and age
   - Stat name
   - Our value vs. expected value (with source)
   - Whether the mismatch is in base stats, upgrades, or final stats
3. **Missing units**: Any units that should be available to a civ but are missing from our data
4. **Extra units**: Any units in our data that shouldn't be available to that civ
5. **Notes**: Any observations about systematic errors or patterns

Focus on **concrete numeric mismatches**. Minor floating-point differences (e.g., 0.96 vs 0.96) are not mismatches. Flag anything where the difference would affect gameplay calculations.

## Data

```json
"""

    closing = """
```
"""

    with open(EXPORT_PATH, "w") as f:
        f.write(instructions)
        f.write(json.dumps(data, indent=2))
        f.write(closing)

    # Print summary
    total_units = sum(len(units) for units in data.values())
    print(f"Exported {total_units} units across {len(data)} civs to {EXPORT_PATH}")
    for civ in sorted(data.keys()):
        print(f"  {civ}: {len(data[civ])} units")


if __name__ == "__main__":
    export()
