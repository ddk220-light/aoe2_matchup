#!/usr/bin/env python3
"""
Extract unique unit stats from both extracted JSON data and the SQLite database
for wiki verification purposes.

Outputs: docs/unique_unit_verification_data.json

Data sources:
  1. database_creation/extracted_data/units.json  (base game stats from dat file)
  2. webapp/aoe2_units.db                         (computed combat properties)
"""

import json
import os
import sqlite3
import sys

# Paths relative to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED_UNITS_PATH = os.path.join(PROJECT_ROOT, "database_creation", "extracted_data", "units.json")
DB_PATH = os.path.join(PROJECT_ROOT, "webapp", "aoe2_units.db")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "docs", "unique_unit_verification_data.json")

# Combat property columns to extract from DB (only include non-zero/non-null values)
COMBAT_PROPERTY_COLS = [
    "extra_projectiles",
    "extra_projectile_attacks_json",
    "splash_radius",
    "splash_on_hit_radius",
    "splash_on_hit_fraction",
    "trample_percent",
    "trample_radius",
    "trample_flat_damage",
    "charge_projectile_count",
    "charge_projectile_attacks_json",
    "charge_projectile_speed",
    "charge_attack_range",
    "charge_ignores_armor",
    "charge_attack_melee",
    "charge_recharge_time",
    "dodge_shield_max",
    "dodge_shield_recharge",
    "ignores_pierce_armor",
    "ignores_melee_armor",
    "bleed_dps",
    "bleed_duration",
    "block_first_melee",
    "attack_bonus_per_kill",
    "first_attack_extra_projectiles",
    "hp_regen",
    "pass_through_percent",
    "hp_transform_threshold",
    "bonus_damage_reduction",
    "armor_strip_per_hit",
    "min_attack_range",
    "projectile_speed",
    "is_siege_projectile",
]

# Wiki URL special cases where the page name differs from the unit name
WIKI_NAME_OVERRIDES = {
    "Ratha (Melee)": "Ratha",
    "Ratha (Ranged)": "Ratha",
}


def build_wiki_url(base_name):
    """Build the fandom wiki URL for a unit."""
    wiki_name = WIKI_NAME_OVERRIDES.get(base_name, base_name)
    # Replace spaces with underscores for URL
    slug = wiki_name.replace(" ", "_")
    return f"https://ageofempires.fandom.com/wiki/{slug}_(Age_of_Empires_II)"


def extract_base_stats(unit):
    """Extract relevant base stats from an extracted units.json entry."""
    return {
        "unit_id": unit["id"],
        "hp": unit["hit_points"],
        "attack": unit.get("displayed_attack", unit.get("base_attack")),
        "range": unit.get("range"),
        "accuracy": unit.get("accuracy"),
        "reload_time": unit.get("reload_time"),
        "attack_delay": unit.get("attack_delay"),
        "melee_armor": unit.get("displayed_melee_armor", unit.get("melee_armor")),
        "pierce_armor": unit.get("displayed_pierce_armor", unit.get("pierce_armor")),
        "speed": unit.get("speed"),
        "line_of_sight": unit.get("line_of_sight"),
        "cost": unit.get("cost"),
        "train_time": unit.get("train_time"),
        "attacks": unit.get("attacks"),
        "armors": unit.get("armors"),
        "class_name": unit.get("class_name"),
        "max_total_projectiles": unit.get("max_total_projectiles"),
    }


def get_db_combat_properties(cursor, unit_name, age_id):
    """
    Get combat properties from the DB for a unique unit.

    Since unit_stats has one row per civ, we pick the row where has_unit=1
    (the civ that actually has this unit). For non-elite uniques that appear
    in both ages (e.g. Grenadier), we filter by age_id.
    """
    # Build the SELECT with all combat columns plus always-include columns
    always_cols = ["upgrade_cost", "attacks_json", "armors_json"]
    all_cols = always_cols + COMBAT_PROPERTY_COLS

    cols_str = ", ".join(f"us.{c}" for c in all_cols)

    query = f"""
        SELECT {cols_str}
        FROM unit_stats us
        JOIN units u ON u.display_name = us.unit_name AND u.unit_type = 'unique'
        WHERE us.unit_name = ? AND us.has_unit = 1 AND u.age_id = ?
        LIMIT 1
    """
    cursor.execute(query, (unit_name, age_id))
    row = cursor.fetchone()

    if row is None:
        return None

    result = {}

    # Always include these
    for i, col in enumerate(always_cols):
        val = row[i]
        if val is not None:
            # Parse JSON strings
            if col.endswith("_json") and isinstance(val, str):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            result[col] = val

    # Only include non-zero/non-null combat properties
    for j, col in enumerate(COMBAT_PROPERTY_COLS):
        val = row[len(always_cols) + j]
        if val is not None and val != 0 and val != 0.0:
            # Parse JSON strings
            if col.endswith("_json") and isinstance(val, str):
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            result[col] = val

    return result if result else None


def get_base_name(unit_name):
    """Strip 'Elite ' prefix to get the base unit name."""
    if unit_name.startswith("Elite "):
        return unit_name[6:]
    return unit_name


def main():
    # Load extracted unit data
    print(f"Loading extracted units from {EXTRACTED_UNITS_PATH}...")
    with open(EXTRACTED_UNITS_PATH) as f:
        all_units = json.load(f)

    # Filter to type=70 (combat units) and index by name
    type70 = [u for u in all_units if u.get("type") == 70]
    extracted_by_name = {}
    for u in type70:
        name = u["name"]
        # Some names may appear multiple times (e.g. with different IDs due to
        # scrambled names). Keep only the first occurrence per name.
        if name not in extracted_by_name:
            extracted_by_name[name] = u

    print(f"  Found {len(type70)} type=70 units, {len(extracted_by_name)} unique names")

    # Connect to DB and get all unique unit names + age info
    print(f"Connecting to database {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get distinct unique unit names with their age_id
    cursor.execute("""
        SELECT DISTINCT us.unit_name, u.age_id
        FROM unit_stats us
        JOIN units u ON u.display_name = us.unit_name AND u.unit_type = 'unique'
        ORDER BY us.unit_name, u.age_id
    """)
    db_unique_entries = cursor.fetchall()
    print(f"  Found {len(db_unique_entries)} unique unit entries in DB")

    # Build a set of all DB unique unit names
    db_unique_names = set(row[0] for row in db_unique_entries)

    # Also build a mapping: (unit_name, age_id) for DB lookups
    db_age_map = {}
    for name, age_id in db_unique_entries:
        if name not in db_age_map:
            db_age_map[name] = []
        db_age_map[name].append(age_id)

    # Identify which extracted units are unique (match DB unique names)
    unique_extracted = {
        name: unit for name, unit in extracted_by_name.items()
        if name in db_unique_names
    }
    print(f"  Matched {len(unique_extracted)} extracted units to DB unique names")

    # Non-elite unique units that have both castle and imperial entries (no "Elite" variant)
    # These are: Warrior Priest, Jian Swordsman, Grenadier, Xianbei Raider, Mounted Trebuchet
    non_elite_with_imperial = set()
    for name, ages in db_age_map.items():
        if not name.startswith("Elite ") and 4 in ages:
            non_elite_with_imperial.add(name)

    # Group base + elite under same wiki page name
    # For standard units: "Foo" (base) + "Elite Foo" (elite) -> wiki page "Foo"
    # For non-elite-with-imperial: "Foo" age=3 (base) + "Foo" age=4 (elite equivalent)

    output = {}

    # Process all base (non-Elite) unique units
    for name in sorted(db_unique_names):
        if name.startswith("Elite "):
            continue  # Process elites together with their base

        base_name = name
        elite_name = f"Elite {name}"

        # Determine if this is a non-elite-with-imperial unit
        is_non_elite_imperial = name in non_elite_with_imperial
        has_elite = elite_name in db_unique_names

        # Extract base stats from units.json
        base_extracted = unique_extracted.get(name)
        base_stats = extract_base_stats(base_extracted) if base_extracted else None

        # Extract elite stats from units.json
        elite_stats = None
        if has_elite:
            elite_extracted = unique_extracted.get(elite_name)
            if elite_extracted:
                elite_stats = extract_base_stats(elite_extracted)
        elif is_non_elite_imperial:
            # For non-elite-with-imperial, the "elite" is the same name at age=4
            # The extracted data has only one entry per name, so base stats
            # serve for both. The DB has different stats per age.
            # We still use the same extracted entry (dat file doesn't distinguish).
            elite_stats = None  # Same extracted data; distinction is in DB combat props

        # Get DB combat properties for base (age=3 Castle Age)
        base_db_combat = get_db_combat_properties(cursor, name, 3)

        # Get DB combat properties for elite
        elite_db_combat = None
        if has_elite:
            elite_db_combat = get_db_combat_properties(cursor, elite_name, 4)
        elif is_non_elite_imperial:
            elite_db_combat = get_db_combat_properties(cursor, name, 4)

        entry = {
            "wiki_url": build_wiki_url(base_name),
            "base": base_stats,
            "elite": elite_stats,
            "base_db_combat": base_db_combat,
            "elite_db_combat": elite_db_combat,
        }

        # For non-elite-with-imperial units, note the variant type
        if is_non_elite_imperial:
            entry["note"] = "Non-elite unique: Castle Age base, Imperial Age upgraded (no 'Elite' prefix)"

        output[base_name] = entry

    conn.close()

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    print(f"\nWriting output to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary stats
    total = len(output)
    with_elite = sum(1 for v in output.values() if v["elite"] is not None)
    with_base_combat = sum(1 for v in output.values() if v["base_db_combat"] is not None)
    with_elite_combat = sum(1 for v in output.values() if v["elite_db_combat"] is not None)
    non_elite_imp = sum(1 for v in output.values() if "note" in v)

    print(f"\nSummary:")
    print(f"  Total unique units (wiki pages): {total}")
    print(f"  With elite variant stats:        {with_elite}")
    print(f"  Non-elite with imperial upgrade:  {non_elite_imp}")
    print(f"  With base DB combat props:        {with_base_combat}")
    print(f"  With elite DB combat props:       {with_elite_combat}")
    print(f"\nDone!")


if __name__ == "__main__":
    main()
