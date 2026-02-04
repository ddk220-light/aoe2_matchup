#!/usr/bin/env python3
"""
Generate SQLite database from unit CSV files.

Database Schema:
- civilizations: List of all civilizations
- units: List of all unit types with their age
- unit_stats: Stats for each civ/unit combination

This allows queries like:
- Get all civs for a unit: SELECT * FROM unit_stats WHERE unit_id = ?
- Get all units for a civ: SELECT * FROM unit_stats WHERE civ_id = ?
- Get units by age: SELECT * FROM unit_stats JOIN units ON unit_stats.unit_id = units.id WHERE units.age = ?
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd

# Database file location
DB_PATH = Path(__file__).parent / "webapp" / "aoe2_units.db"
UNIT_OUTPUT_DIR = Path(__file__).parent / "unit_output"

# Age definitions
AGES = {
    "feudal": {"id": 2, "name": "Feudal Age"},
    "castle": {"id": 3, "name": "Castle Age"},
    "imperial": {"id": 4, "name": "Imperial Age"},
}

# Unit display names (for better readability)
UNIT_DISPLAY_NAMES = {
    # Feudal
    "archer": "Archer",
    "man_at_arms": "Man-at-Arms",
    "scout": "Scout Cavalry",
    "skirmisher": "Skirmisher",
    "spearman": "Spearman",
    # Castle
    "camel": "Camel Rider",
    "cav_archer": "Cavalry Archer",
    "crossbow": "Crossbowman",
    "eagle_warrior": "Eagle Warrior",
    "elephant": "Battle Elephant",
    "elephant_archer": "Elephant Archer",
    "elite_skirm": "Elite Skirmisher",
    "fire_archer": "Fire Archer",
    "knight": "Knight",
    "light_cav": "Light Cavalry",
    "mangonel": "Mangonel",
    "pikeman": "Pikeman",
    "ram": "Battering Ram",
    "scorpion": "Scorpion",
    "steppe_lancer": "Steppe Lancer",
    "swordsmen": "Long Swordsman",
    # Imperial
    "arbalester": "Arbalester",
    "bombard_cannon": "Bombard Cannon",
    "champion": "Champion",
    "elite_eagle": "Elite Eagle Warrior",
    "elite_ele_archer": "Elite Elephant Archer",
    "elite_elephant": "Elite Battle Elephant",
    "elite_steppe": "Elite Steppe Lancer",
    "halberdier": "Halberdier",
    "hand_cannoneer": "Hand Cannoneer",
    "heavy_camel": "Heavy Camel Rider",
    "heavy_cav_archer": "Heavy Cavalry Archer",
    "heavy_scorpion": "Heavy Scorpion",
    "hussar": "Hussar",
    "imp_skirm": "Imperial Skirmisher",
    "paladin": "Paladin",
    "siege_onager": "Siege Onager",
    "siege_ram": "Siege Ram",
    "trebuchet": "Trebuchet",
}


def create_database():
    """Create the SQLite database with the schema."""
    # Remove existing database
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
        -- Civilizations table
        CREATE TABLE civilizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );

        -- Ages table
        CREATE TABLE ages (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        -- Units table (unit types)
        CREATE TABLE units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            age_id INTEGER NOT NULL,
            FOREIGN KEY (age_id) REFERENCES ages(id)
        );

        -- Unit stats table (stats for each civ/unit combination)
        CREATE TABLE unit_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL,
            unit_name TEXT NOT NULL,  -- Actual unit name (e.g., "Paladin", "Cavalier", "Hei-Kuang Cavalry")
            hp INTEGER,
            attack INTEGER,
            attack_range REAL,
            attack_speed REAL,
            melee_armor INTEGER,
            pierce_armor INTEGER,
            movement_speed REAL,
            cost_food INTEGER,
            cost_wood INTEGER,
            cost_gold INTEGER,
            creation_time INTEGER,
            upgrade_cost INTEGER,
            civ_bonuses TEXT,
            has_unit INTEGER NOT NULL,  -- 1 = has unit, 0 = doesn't have unit
            FOREIGN KEY (civ_id) REFERENCES civilizations(id),
            FOREIGN KEY (unit_id) REFERENCES units(id),
            UNIQUE(civ_id, unit_id)
        );

        -- Comments table for user feedback on specific cells
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            civ_id INTEGER NOT NULL,
            column_name TEXT NOT NULL,  -- e.g., "HP", "Attack", "Attack_Speed"
            comment_text TEXT NOT NULL,
            author_name TEXT,  -- optional author name
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0,  -- 0 = open, 1 = resolved
            FOREIGN KEY (unit_id) REFERENCES units(id),
            FOREIGN KEY (civ_id) REFERENCES civilizations(id)
        );

        -- Create indexes for efficient queries
        CREATE INDEX idx_unit_stats_civ ON unit_stats(civ_id);
        CREATE INDEX idx_unit_stats_unit ON unit_stats(unit_id);
        CREATE INDEX idx_units_age ON units(age_id);
        CREATE INDEX idx_comments_unit ON comments(unit_id);
        CREATE INDEX idx_comments_civ ON comments(civ_id);
        CREATE INDEX idx_comments_resolved ON comments(resolved);
    """)

    conn.commit()
    return conn


def populate_ages(conn):
    """Populate the ages table."""
    cursor = conn.cursor()
    for age_slug, age_data in AGES.items():
        cursor.execute(
            "INSERT INTO ages (id, name) VALUES (?, ?)",
            (age_data["id"], age_data["name"]),
        )
    conn.commit()


def get_all_civs_from_csvs():
    """Extract all unique civilization names from all CSV files."""
    civs = set()
    for age_dir in UNIT_OUTPUT_DIR.iterdir():
        if age_dir.is_dir():
            for csv_file in age_dir.glob("*.csv"):
                df = pd.read_csv(csv_file)
                civs.update(df["Civilization"].unique())
    return sorted(civs)


def populate_civilizations(conn, civs):
    """Populate the civilizations table."""
    cursor = conn.cursor()
    for civ in civs:
        cursor.execute("INSERT INTO civilizations (name) VALUES (?)", (civ,))
    conn.commit()

    # Return a mapping of civ name to id
    cursor.execute("SELECT id, name FROM civilizations")
    return {row[1]: row[0] for row in cursor.fetchall()}


def populate_units(conn):
    """Populate the units table from CSV files."""
    cursor = conn.cursor()

    for age_slug, age_data in AGES.items():
        age_dir = UNIT_OUTPUT_DIR / age_slug
        if not age_dir.exists():
            continue

        for csv_file in sorted(age_dir.glob("*.csv")):
            unit_slug = csv_file.stem
            display_name = UNIT_DISPLAY_NAMES.get(
                unit_slug, unit_slug.replace("_", " ").title()
            )

            cursor.execute(
                "INSERT INTO units (slug, display_name, age_id) VALUES (?, ?, ?)",
                (unit_slug, display_name, age_data["id"]),
            )

    conn.commit()

    # Return a mapping of unit slug to id
    cursor.execute("SELECT id, slug FROM units")
    return {row[1]: row[0] for row in cursor.fetchall()}


def populate_unit_stats(conn, civ_map, unit_map):
    """Populate the unit_stats table from CSV files."""
    cursor = conn.cursor()

    for age_slug in AGES.keys():
        age_dir = UNIT_OUTPUT_DIR / age_slug
        if not age_dir.exists():
            continue

        for csv_file in sorted(age_dir.glob("*.csv")):
            unit_slug = csv_file.stem
            unit_id = unit_map[unit_slug]

            df = pd.read_csv(csv_file)

            for _, row in df.iterrows():
                civ_name = row["Civilization"]
                civ_id = civ_map[civ_name]

                # Handle optional Range column (some units don't have it)
                attack_range = row.get("Range", None)
                if pd.isna(attack_range):
                    attack_range = None

                # Convert Has_Unit to integer
                has_unit = 1 if row["Has_Unit"] == "Yes" else 0

                # Handle civ bonuses
                civ_bonuses = row.get("Civ_Bonuses", "-")
                if pd.isna(civ_bonuses) or civ_bonuses == "-":
                    civ_bonuses = None

                cursor.execute(
                    """
                    INSERT INTO unit_stats (
                        civ_id, unit_id, unit_name, hp, attack, attack_range,
                        attack_speed, melee_armor, pierce_armor, movement_speed,
                        cost_food, cost_wood, cost_gold, creation_time, upgrade_cost,
                        civ_bonuses, has_unit
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        civ_id,
                        unit_id,
                        row["Unit"],
                        int(row["HP"]) if not pd.isna(row["HP"]) else None,
                        int(row["Attack"]) if not pd.isna(row["Attack"]) else None,
                        float(attack_range) if attack_range is not None else None,
                        float(row["Attack_Speed"])
                        if not pd.isna(row["Attack_Speed"])
                        else None,
                        int(row["Melee_Armor"])
                        if not pd.isna(row["Melee_Armor"])
                        else None,
                        int(row["Pierce_Armor"])
                        if not pd.isna(row["Pierce_Armor"])
                        else None,
                        float(row["Movement_Speed"])
                        if not pd.isna(row["Movement_Speed"])
                        else None,
                        int(row["Cost_Food"])
                        if not pd.isna(row["Cost_Food"])
                        else None,
                        int(row["Cost_Wood"])
                        if not pd.isna(row["Cost_Wood"])
                        else None,
                        int(row["Cost_Gold"])
                        if not pd.isna(row["Cost_Gold"])
                        else None,
                        int(row["Creation_Time"])
                        if not pd.isna(row["Creation_Time"])
                        else None,
                        int(row["Upgrade_Cost"])
                        if not pd.isna(row["Upgrade_Cost"])
                        else None,
                        civ_bonuses,
                        has_unit,
                    ),
                )

    conn.commit()


def print_stats(conn):
    """Print database statistics."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM civilizations")
    civ_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM units")
    unit_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM unit_stats")
    stats_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM unit_stats WHERE has_unit = 1")
    available_count = cursor.fetchone()[0]

    print(f"\nDatabase created at: {DB_PATH}")
    print(f"  Civilizations: {civ_count}")
    print(f"  Unit types: {unit_count}")
    print(f"  Unit stats records: {stats_count}")
    print(f"  Available unit/civ combinations: {available_count}")

    # Show units by age
    print("\nUnits by age:")
    for age_id, age_name in [(2, "Feudal"), (3, "Castle"), (4, "Imperial")]:
        cursor.execute("SELECT COUNT(*) FROM units WHERE age_id = ?", (age_id,))
        count = cursor.fetchone()[0]
        print(f"  {age_name}: {count} units")


def example_queries(conn):
    """Show example queries that can be run against the database."""
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("Example Queries:")
    print("=" * 60)

    # Query 1: Get all civs for a specific unit
    print("\n1. All civs with Paladin (has_unit=1):")
    cursor.execute("""
        SELECT c.name, us.unit_name, us.hp, us.attack
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        WHERE u.slug = 'paladin' AND us.has_unit = 1
        ORDER BY us.hp DESC
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]} - HP: {row[2]}, Attack: {row[3]}")

    # Query 2: Get all units for a specific civ
    print("\n2. All Imperial age units for Franks:")
    cursor.execute("""
        SELECT u.display_name, us.unit_name, us.hp, us.attack, us.has_unit
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        JOIN ages a ON u.age_id = a.id
        WHERE c.name = 'Franks' AND a.id = 4
        ORDER BY u.display_name
    """)
    for row in cursor.fetchall():
        status = "Yes" if row[4] else "No"
        print(f"    {row[0]}: {row[1]} - HP: {row[2]}, Attack: {row[3]}, Has: {status}")

    # Query 3: Find civs with unique bonuses for a unit
    print("\n3. Civs with bonuses for Knight:")
    cursor.execute("""
        SELECT c.name, us.civ_bonuses
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        WHERE u.slug = 'knight' AND us.civ_bonuses IS NOT NULL
        ORDER BY c.name
    """)
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")


def main():
    print("Creating AoE2 Units Database...")

    # Create database and schema
    conn = create_database()

    # Populate ages
    populate_ages(conn)

    # Get all civs and populate
    civs = get_all_civs_from_csvs()
    civ_map = populate_civilizations(conn, civs)
    print(f"Found {len(civs)} civilizations")

    # Populate units
    unit_map = populate_units(conn)
    print(f"Found {len(unit_map)} unit types")

    # Populate unit stats
    populate_unit_stats(conn, civ_map, unit_map)

    # Print stats
    print_stats(conn)

    # Show example queries
    example_queries(conn)

    conn.close()
    print("\nDatabase generation complete!")


if __name__ == "__main__":
    main()
