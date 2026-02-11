#!/usr/bin/env python3
"""Generate the main webapp database (aoe2_units.db) from the reference database (aoe2_reference.db).

Reads all unit data from aoe2_reference.db (ref_units, ref_special_effects, ref_projectiles)
and creates the main DB with civilizations, ages, units, and unit_stats tables.

Usage:
    python3 -m database_creation.generate_main_db
    # or from project root:
    python3 database_creation/generate_main_db.py
"""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
REF_DB_PATH = PROJECT_ROOT / "webapp" / "aoe2_reference.db"
MAIN_DB_PATH = PROJECT_ROOT / "webapp" / "aoe2_units.db"

# Import config for COMBAT_PROPERTIES, PAIRED_UNITS, etc.
# When run as module, use relative import; when run as script, add parent to path
try:
    from .config import COMBAT_PROPERTIES, PAIRED_UNITS
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from database_creation.config import COMBAT_PROPERTIES, PAIRED_UNITS

# Age mapping: ref DB uses "Castle"/"Imperial" strings, main DB uses integer IDs
AGE_MAP = {
    "Feudal": 2,
    "Castle": 3,
    "Imperial": 4,
}

AGE_NAMES = {
    2: "Feudal Age",
    3: "Castle Age",
    4: "Imperial Age",
}

# Units without elite that exist in both Castle and Imperial ages.
# These get an "_imp" suffix slug for the Imperial version.
# Format: base_castle_slug -> imperial_slug
# (Units with elite_tech=None in UNIQUE_UNITS config)
NO_ELITE_UNITS = {
    "grenadier": "grenadier_imp",
    "warrior_priest": "warrior_priest_imp",
    "jian_swordsman": "jian_swordsman_imp",
    "siege_camel": "siege_camel_imp",
    "xianbei_raider": "xianbei_raider_imp",
}


def _get_unit_category(unit_slug):
    """Determine unit_category from COMBAT_PROPERTIES config.

    Returns 'siege', 'trash', or 'military'.
    """
    if unit_slug in COMBAT_PROPERTIES:
        return COMBAT_PROPERTIES[unit_slug].get("unit_category", "military")
    return "military"


def _get_paired_unit_slug(unit_slug):
    """Get the paired unit slug (for Ratha melee/ranged switching).

    For unique units with civ suffix, builds the full partner slug.
    """
    for paired_slug, partner_slug in PAIRED_UNITS.items():
        if unit_slug == paired_slug or unit_slug.startswith(paired_slug + "_"):
            if unit_slug.startswith(paired_slug + "_"):
                suffix = unit_slug[len(paired_slug) :]
                return partner_slug + suffix
            return partner_slug
    return None


def build_combat_dict_from_ref(rc, row):
    """Build a combat properties dict from a ref_units row + related tables.

    This mirrors _build_combat_dict_from_ref in webapp/app.py.

    Args:
        rc: sqlite3 cursor on the reference DB
        row: sqlite3.Row from ref_units table

    Returns:
        dict with all combat property fields for unit_stats table
    """
    uid = row["id"]

    # Get special effects as flat dict
    rc.execute(
        "SELECT property_name, property_value FROM ref_special_effects WHERE ref_unit_id=?",
        (uid,),
    )
    special = {}
    for s in rc.fetchall():
        try:
            special[s["property_name"]] = float(s["property_value"])
        except (ValueError, TypeError):
            special[s["property_name"]] = s["property_value"]

    # Get projectile data
    rc.execute(
        """SELECT projectile_type, projectile_count, projectile_speed,
                  attacks_json, blast_radius, is_siege_projectile
           FROM ref_projectiles WHERE ref_unit_id=?""",
        (uid,),
    )
    primary_proj = None
    extra_proj = None
    charge_proj = None
    for p in rc.fetchall():
        pdict = dict(p)
        if pdict["projectile_type"] == "primary":
            primary_proj = pdict
        elif pdict["projectile_type"] == "extra":
            extra_proj = pdict
        elif pdict["projectile_type"] == "charge":
            charge_proj = pdict

    return {
        # From projectiles
        "projectile_speed": (
            primary_proj["projectile_speed"]
            if primary_proj and primary_proj["projectile_speed"]
            else row["projectile_speed"] or 0
        ),
        "is_siege_projectile": (
            primary_proj["is_siege_projectile"] if primary_proj else 0
        ),
        "splash_radius": special.get("splash_radius", 0),
        "extra_projectiles": extra_proj["projectile_count"] if extra_proj else 0,
        "extra_projectile_attacks_json": (
            extra_proj["attacks_json"] if extra_proj else None
        ),
        "charge_projectile_count": (
            charge_proj["projectile_count"] if charge_proj else 0
        ),
        "charge_projectile_speed": (
            charge_proj["projectile_speed"] if charge_proj else 0
        ),
        "charge_projectile_attacks_json": (
            charge_proj["attacks_json"] if charge_proj else None
        ),
        # Special combat properties from ref_special_effects
        "trample_percent": special.get("trample_percent", 0),
        "trample_radius": special.get("trample_radius", 0),
        "trample_flat_damage": special.get("trample_flat_damage", 0),
        "hp_regen": special.get("hp_regen", 0),
        "charge_attack_range": float(special.get("charge_attack_range", 0)),
        "charge_ignores_armor": int(special.get("charge_ignores_armor", 0)),
        "ignores_pierce_armor": int(special.get("ignores_pierce_armor", 0)),
        "ignores_melee_armor": int(special.get("ignores_melee_armor", 0)),
        "bonus_damage_reduction": special.get("bonus_damage_reduction", 0),
        "splash_on_hit_radius": special.get("splash_on_hit_radius", 0),
        "dodge_shield_max": int(special.get("dodge_shield_max", 0)),
        "dodge_shield_recharge": special.get("dodge_shield_recharge", 0),
        "bleed_dps": special.get("bleed_dps", 0),
        "bleed_duration": special.get("bleed_duration", 0),
        "block_first_melee": int(special.get("block_first_melee", 0)),
        "attack_bonus_per_kill": int(special.get("attack_bonus_per_kill", 0)),
        "first_attack_extra_projectiles": int(
            special.get("first_attack_extra_projectiles", 0)
        ),
        "hp_transform_threshold": special.get("hp_transform_threshold", 0),
        "pass_through_percent": special.get("pass_through_percent", 0),
        "pop_space": special.get("pop_space", 1.0),
    }


def generate_main_database():
    """Generate aoe2_units.db from aoe2_reference.db."""

    if not REF_DB_PATH.exists():
        print(f"ERROR: Reference database not found at {REF_DB_PATH}")
        print("Run 'python3 -m database_creation.run' first to generate it.")
        sys.exit(1)

    # Connect to reference DB
    ref_conn = sqlite3.connect(str(REF_DB_PATH))
    ref_conn.row_factory = sqlite3.Row
    rc = ref_conn.cursor()

    # Load all ref_units
    rc.execute(
        """SELECT * FROM ref_units ORDER BY civ_name, age, unit_type, unit_slug"""
    )
    all_ref_units = rc.fetchall()

    if not all_ref_units:
        print("ERROR: No units found in reference database.")
        sys.exit(1)

    # Collect distinct civs and their units
    civ_names = sorted(set(row["civ_name"] for row in all_ref_units))
    print(f"Found {len(all_ref_units)} unit entries for {len(civ_names)} civilizations")

    # Collect distinct unit slugs per age+type for the units table
    # A "unit" in the main DB is a (slug, age, type) combination
    # Standard units: same slug across civs, no civ_id
    # Unique units: slug includes civ suffix, has civ_id
    unit_definitions = {}  # (slug, age_id) -> {display_name, unit_type, civ_id}

    for row in all_ref_units:
        slug = row["unit_slug"]
        age_id = AGE_MAP[row["age"]]
        unit_type = row["unit_type"]
        civ_name = row["civ_name"]

        key = (slug, age_id)
        if key not in unit_definitions:
            civ_id = None  # Will be set below for unique units
            unit_definitions[key] = {
                "display_name": row["unit_name"],
                "unit_type": unit_type,
                "civ_name": civ_name if unit_type == "unique" else None,
            }

    # --- Check for no-elite unique units ---
    # These are Castle-age unique units that also appear in Imperial without an elite version.
    # In the ref DB, they appear as Castle-age entries only (no elite in Imperial).
    # We need to check if the ref DB has them in Imperial too (it should, generated by
    # generate_reference.py if they have imperial techs applied).
    # If not, we still only output what the ref DB has.

    # --- Create main database ---
    if MAIN_DB_PATH.exists():
        # Preserve any user data (comments, verifications) before recreating
        old_conn = sqlite3.connect(str(MAIN_DB_PATH))
        old_conn.row_factory = sqlite3.Row
        old_c = old_conn.cursor()

        # Check for user-generated data to preserve
        preserved_data = {
            "simulation_comments": [],
            "unit_verifications": [],
            "comments": [],
        }
        for table_name in preserved_data:
            try:
                old_c.execute(f"SELECT * FROM {table_name}")
                rows = old_c.fetchall()
                if rows:
                    cols = [desc[0] for desc in old_c.description]
                    preserved_data[table_name] = [dict(zip(cols, r)) for r in rows]
                    print(f"  Preserving {len(rows)} rows from {table_name}")
            except sqlite3.OperationalError:
                pass  # Table doesn't exist

        old_conn.close()
        MAIN_DB_PATH.unlink()

    else:
        preserved_data = {
            "simulation_comments": [],
            "unit_verifications": [],
            "comments": [],
        }

    # Create fresh database
    conn = sqlite3.connect(str(MAIN_DB_PATH))
    cursor = conn.cursor()

    # --- Create schema ---
    cursor.executescript("""
        CREATE TABLE civilizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE ages (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            display_name TEXT NOT NULL,
            age_id INTEGER NOT NULL,
            unit_type TEXT DEFAULT 'standard',
            civ_id INTEGER,
            FOREIGN KEY (age_id) REFERENCES ages(id),
            FOREIGN KEY (civ_id) REFERENCES civilizations(id)
        );

        CREATE TABLE unit_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL,
            unit_name TEXT NOT NULL,
            hp INTEGER,
            attack INTEGER,
            attack_range REAL,
            attack_speed REAL,
            attack_delay REAL,
            melee_armor INTEGER,
            pierce_armor INTEGER,
            movement_speed REAL,
            cost_food INTEGER,
            cost_wood INTEGER,
            cost_gold INTEGER,
            creation_time INTEGER,
            upgrade_cost INTEGER,
            civ_bonuses TEXT,
            has_unit INTEGER NOT NULL,
            attacks_json TEXT,
            armors_json TEXT,
            combat_wins INTEGER DEFAULT 0,
            combat_losses INTEGER DEFAULT 0,
            combat_draws INTEGER DEFAULT 0,
            combat_score REAL DEFAULT 0,
            min_attack_range REAL DEFAULT 0,
            is_siege_projectile INTEGER DEFAULT 0,
            splash_radius REAL DEFAULT 0,
            projectile_speed REAL DEFAULT 0,
            ignores_pierce_armor INTEGER DEFAULT 0,
            ignores_melee_armor INTEGER DEFAULT 0,
            trample_percent REAL DEFAULT 0,
            trample_radius REAL DEFAULT 0,
            trample_flat_damage INTEGER DEFAULT 0,
            bonus_damage_reduction REAL DEFAULT 0,
            unit_category TEXT DEFAULT 'military',
            paired_unit_slug TEXT DEFAULT NULL,
            extra_projectiles INTEGER DEFAULT 0,
            extra_projectile_attacks_json TEXT DEFAULT NULL,
            charge_projectile_count INTEGER DEFAULT 0,
            charge_projectile_attacks_json TEXT DEFAULT NULL,
            charge_projectile_speed REAL DEFAULT 0,
            charge_attack_range REAL DEFAULT 0,
            charge_ignores_armor INTEGER DEFAULT 0,
            splash_on_hit_radius REAL DEFAULT 0,
            dodge_shield_max INTEGER DEFAULT 0,
            dodge_shield_recharge REAL DEFAULT 0,
            bleed_dps REAL DEFAULT 0,
            bleed_duration REAL DEFAULT 0,
            block_first_melee INTEGER DEFAULT 0,
            attack_bonus_per_kill REAL DEFAULT 0,
            first_attack_extra_projectiles INTEGER DEFAULT 0,
            hp_regen REAL DEFAULT 0,
            pass_through_percent REAL DEFAULT 0,
            hp_transform_threshold REAL DEFAULT 0,
            pop_space REAL DEFAULT 1.0,
            transform_hp INTEGER DEFAULT NULL,
            transform_attack INTEGER DEFAULT NULL,
            transform_melee_armor INTEGER DEFAULT NULL,
            transform_pierce_armor INTEGER DEFAULT NULL,
            transform_attack_speed REAL DEFAULT NULL,
            transform_attack_delay REAL DEFAULT NULL,
            transform_movement_speed REAL DEFAULT NULL,
            transform_attacks_json TEXT DEFAULT NULL,
            transform_armors_json TEXT DEFAULT NULL,
            dismount_hp INTEGER DEFAULT NULL,
            dismount_attack INTEGER DEFAULT NULL,
            dismount_melee_armor INTEGER DEFAULT NULL,
            dismount_pierce_armor INTEGER DEFAULT NULL,
            dismount_attack_speed REAL DEFAULT NULL,
            dismount_attack_delay REAL DEFAULT NULL,
            dismount_movement_speed REAL DEFAULT NULL,
            dismount_attacks_json TEXT DEFAULT NULL,
            dismount_armors_json TEXT DEFAULT NULL,
            FOREIGN KEY (civ_id) REFERENCES civilizations(id),
            FOREIGN KEY (unit_id) REFERENCES units(id)
        );

        CREATE TABLE armor_classes (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE combat_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_stats_id_1 INTEGER NOT NULL,
            unit_stats_id_2 INTEGER NOT NULL,
            winner_id INTEGER,
            winner_hp_remaining INTEGER,
            combat_time REAL,
            hits_by_unit1 INTEGER,
            hits_by_unit2 INTEGER,
            FOREIGN KEY (unit_stats_id_1) REFERENCES unit_stats(id),
            FOREIGN KEY (unit_stats_id_2) REFERENCES unit_stats(id)
        );

        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            civ_id INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            comment_text TEXT NOT NULL,
            author_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved INTEGER DEFAULT 0
        );

        CREATE TABLE simulation_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team1_civ TEXT NOT NULL,
            team1_unit TEXT NOT NULL,
            team1_count INTEGER NOT NULL,
            team2_civ TEXT NOT NULL,
            team2_unit TEXT NOT NULL,
            team2_count INTEGER NOT NULL,
            winner INTEGER,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE unit_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # --- Populate ages ---
    for age_id, age_name in sorted(AGE_NAMES.items()):
        cursor.execute("INSERT INTO ages (id, name) VALUES (?, ?)", (age_id, age_name))

    # --- Populate civilizations (alphabetical order) ---
    civ_id_map = {}  # civ_name -> civ_id
    for civ_name in sorted(civ_names):
        cursor.execute("INSERT INTO civilizations (name) VALUES (?)", (civ_name,))
        civ_id_map[civ_name] = cursor.lastrowid

    print(f"  Inserted {len(civ_id_map)} civilizations")

    # --- Populate armor_classes from reference DB extracted data ---
    armor_classes_file = Path(__file__).parent / "extracted_data" / "armor_classes.json"
    if armor_classes_file.exists():
        armor_classes = json.load(open(armor_classes_file))
        for ac in armor_classes:
            cursor.execute(
                "INSERT OR REPLACE INTO armor_classes (id, name) VALUES (?, ?)",
                (ac["id"], ac["name"]),
            )
        print(f"  Inserted {len(armor_classes)} armor classes")

    # --- Populate units table ---
    # Build the units table from distinct (slug, age_id) pairs
    unit_id_map = {}  # (slug, age_id) -> unit_id

    # Sort: standard units first (by age, then slug), then unique units
    sorted_unit_defs = sorted(
        unit_definitions.items(),
        key=lambda x: (
            x[0][1],  # age_id
            0 if x[1]["unit_type"] == "standard" else 1,  # standard first
            x[0][0],  # slug
        ),
    )

    for (slug, age_id), defn in sorted_unit_defs:
        civ_id = None
        if defn["unit_type"] == "unique" and defn["civ_name"]:
            civ_id = civ_id_map.get(defn["civ_name"])

        cursor.execute(
            """INSERT INTO units (slug, display_name, age_id, unit_type, civ_id)
               VALUES (?, ?, ?, ?, ?)""",
            (slug, defn["display_name"], age_id, defn["unit_type"], civ_id),
        )
        unit_id_map[(slug, age_id)] = cursor.lastrowid

    print(f"  Inserted {len(unit_id_map)} unit definitions")

    # --- Build index of which (civ, slug, age) combos exist in ref DB ---
    ref_unit_index = {}  # (civ_name, slug, age) -> ref_unit row id
    for row in all_ref_units:
        key = (row["civ_name"], row["unit_slug"], row["age"])
        ref_unit_index[key] = row["id"]

    # --- Populate unit_stats ---
    # For each unit definition, create a row for EVERY civ.
    # If a civ has the unit in ref DB: has_unit=1, fill stats
    # If a civ doesn't have it: has_unit=0, minimal data
    stats_count = 0
    has_unit_count = 0

    for (slug, age_id), defn in sorted_unit_defs:
        db_unit_id = unit_id_map[(slug, age_id)]
        age_str = {3: "Castle", 4: "Imperial"}.get(age_id)

        if age_str is None:
            # Skip feudal (not in ref DB)
            continue

        for civ_name in sorted(civ_names):
            db_civ_id = civ_id_map[civ_name]

            # Look up this unit for this civ in ref DB
            ref_key = (civ_name, slug, age_str)
            ref_id = ref_unit_index.get(ref_key)

            if ref_id is not None:
                # Civ has this unit - get full data from ref DB
                rc.execute("SELECT * FROM ref_units WHERE id=?", (ref_id,))
                ref_row = rc.fetchone()

                if ref_row is None:
                    # Shouldn't happen, but handle gracefully
                    _insert_empty_unit_stats(
                        cursor, db_civ_id, db_unit_id, defn["display_name"], slug
                    )
                    stats_count += 1
                    continue

                # Build combat properties from special effects and projectiles
                combat = build_combat_dict_from_ref(rc, ref_row)

                # Determine attack_range: None for melee, value for ranged
                attack_range = None
                if ref_row["is_ranged"]:
                    attack_range = ref_row["final_range"]

                # Calculate attack_speed from reload_time
                reload_time = ref_row["final_reload_time"] or 2.0
                attack_speed = round(1.0 / reload_time, 3) if reload_time > 0 else 0.5

                # Unit category from COMBAT_PROPERTIES config
                unit_category = _get_unit_category(slug)

                # Paired unit slug
                paired = _get_paired_unit_slug(slug)

                # Upgrade cost (sum of food + wood + gold)
                upgrade_cost = (
                    (ref_row["upgrade_cost_food"] or 0)
                    + (ref_row["upgrade_cost_wood"] or 0)
                    + (ref_row["upgrade_cost_gold"] or 0)
                )

                # Civ bonuses summary
                civ_bonuses = ref_row["applied_bonuses_summary"] or None
                # Filter out generic tech names that aren't really "civ bonuses"
                # Keep the full applied_bonuses_summary as-is for now

                # min_attack_range
                min_attack_range = ref_row["min_range"] or 0

                cursor.execute(
                    """INSERT INTO unit_stats (
                        civ_id, unit_id, unit_name,
                        hp, attack, attack_range, attack_speed, attack_delay,
                        melee_armor, pierce_armor, movement_speed,
                        cost_food, cost_wood, cost_gold,
                        creation_time, upgrade_cost, civ_bonuses, has_unit,
                        attacks_json, armors_json,
                        combat_wins, combat_losses, combat_draws, combat_score,
                        min_attack_range, is_siege_projectile, splash_radius,
                        projectile_speed, ignores_pierce_armor, ignores_melee_armor,
                        trample_percent, trample_radius, trample_flat_damage,
                        bonus_damage_reduction, unit_category, paired_unit_slug,
                        extra_projectiles, extra_projectile_attacks_json,
                        charge_projectile_count, charge_projectile_attacks_json,
                        charge_projectile_speed, charge_attack_range, charge_ignores_armor,
                        splash_on_hit_radius,
                        dodge_shield_max, dodge_shield_recharge,
                        bleed_dps, bleed_duration, block_first_melee,
                        attack_bonus_per_kill, first_attack_extra_projectiles,
                        hp_regen, pass_through_percent, hp_transform_threshold,
                        pop_space,
                        transform_hp, transform_attack, transform_melee_armor,
                        transform_pierce_armor, transform_attack_speed,
                        transform_attack_delay, transform_movement_speed,
                        transform_attacks_json, transform_armors_json,
                        dismount_hp, dismount_attack, dismount_melee_armor,
                        dismount_pierce_armor, dismount_attack_speed,
                        dismount_attack_delay, dismount_movement_speed,
                        dismount_attacks_json, dismount_armors_json
                    ) VALUES (
                        ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?,
                        0, 0, 0, 0.0,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?,
                        NULL, NULL, NULL,
                        NULL, NULL,
                        NULL, NULL,
                        NULL, NULL,
                        NULL, NULL, NULL,
                        NULL, NULL,
                        NULL, NULL,
                        NULL, NULL
                    )""",
                    (
                        db_civ_id,
                        db_unit_id,
                        ref_row["unit_name"],
                        # Core stats
                        int(ref_row["final_hp"]),
                        int(ref_row["final_attack"]),
                        attack_range,
                        attack_speed,
                        ref_row["final_attack_delay"] or 0,
                        int(ref_row["final_melee_armor"]),
                        int(ref_row["final_pierce_armor"]),
                        round(ref_row["final_speed"], 2),
                        # Costs
                        int(ref_row["final_cost_food"] or 0),
                        int(ref_row["final_cost_wood"] or 0),
                        int(ref_row["final_cost_gold"] or 0),
                        # Creation time and upgrade cost
                        int(ref_row["final_train_time"] or 0),
                        upgrade_cost,
                        civ_bonuses,
                        1,  # has_unit = True
                        # Attack/armor JSON
                        ref_row["final_attacks_json"],
                        ref_row["final_armors_json"],
                        # Combat properties
                        min_attack_range,
                        combat["is_siege_projectile"],
                        combat["splash_radius"],
                        combat["projectile_speed"],
                        combat["ignores_pierce_armor"],
                        combat["ignores_melee_armor"],
                        combat["trample_percent"],
                        combat["trample_radius"],
                        combat["trample_flat_damage"],
                        combat["bonus_damage_reduction"],
                        unit_category,
                        paired,
                        combat["extra_projectiles"],
                        combat["extra_projectile_attacks_json"],
                        combat["charge_projectile_count"],
                        combat["charge_projectile_attacks_json"],
                        combat["charge_projectile_speed"],
                        combat["charge_attack_range"],
                        combat["charge_ignores_armor"],
                        combat["splash_on_hit_radius"],
                        combat["dodge_shield_max"],
                        combat["dodge_shield_recharge"],
                        combat["bleed_dps"],
                        combat["bleed_duration"],
                        combat["block_first_melee"],
                        combat["attack_bonus_per_kill"],
                        combat["first_attack_extra_projectiles"],
                        combat["hp_regen"],
                        combat["pass_through_percent"],
                        combat["hp_transform_threshold"],
                        combat["pop_space"],
                    ),
                )
                has_unit_count += 1
            else:
                # Civ doesn't have this unit
                _insert_empty_unit_stats(
                    cursor, db_civ_id, db_unit_id, defn["display_name"], slug
                )

            stats_count += 1

    conn.commit()

    # --- Restore preserved user data ---
    _restore_preserved_data(cursor, conn, preserved_data)

    # --- Print summary ---
    cursor.execute("SELECT COUNT(*) FROM civilizations")
    n_civs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM units")
    n_units = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM unit_stats")
    n_stats = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM unit_stats WHERE has_unit=1")
    n_has = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM unit_stats WHERE has_unit=0")
    n_missing = cursor.fetchone()[0]

    print(f"\n  Main DB created at: {MAIN_DB_PATH}")
    print(f"  Civilizations: {n_civs}")
    print(f"  Unit definitions: {n_units}")
    print(f"  Unit stats rows: {n_stats} ({n_has} has_unit=1, {n_missing} has_unit=0)")

    # Sanity checks
    _run_sanity_checks(cursor, rc)

    conn.close()
    ref_conn.close()

    print("\nDone!")


def _insert_empty_unit_stats(cursor, civ_id, unit_id, display_name, slug):
    """Insert a unit_stats row for a civ that doesn't have this unit (has_unit=0)."""
    unit_category = _get_unit_category(slug)
    cursor.execute(
        """INSERT INTO unit_stats (
            civ_id, unit_id, unit_name,
            hp, attack, attack_range, attack_speed, attack_delay,
            melee_armor, pierce_armor, movement_speed,
            cost_food, cost_wood, cost_gold,
            creation_time, upgrade_cost, civ_bonuses, has_unit,
            attacks_json, armors_json,
            unit_category
        ) VALUES (
            ?, ?, ?,
            0, 0, NULL, 0, 0,
            0, 0, 0,
            0, 0, 0,
            0, 0, NULL, 0,
            NULL, NULL,
            ?
        )""",
        (civ_id, unit_id, display_name, unit_category),
    )


def _restore_preserved_data(cursor, conn, preserved_data):
    """Restore previously preserved user data (comments, verifications)."""
    for table_name, rows in preserved_data.items():
        if not rows:
            continue

        cols = list(rows[0].keys())
        # Skip 'id' column (auto-increment)
        cols_no_id = [c for c in cols if c != "id"]
        placeholders = ", ".join(["?"] * len(cols_no_id))
        col_names = ", ".join(cols_no_id)

        for row in rows:
            values = [row[c] for c in cols_no_id]
            try:
                cursor.execute(
                    f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                    values,
                )
            except sqlite3.Error as e:
                print(f"  Warning: Could not restore {table_name} row: {e}")

        conn.commit()
        print(f"  Restored {len(rows)} rows to {table_name}")


def _run_sanity_checks(cursor, rc):
    """Run basic sanity checks comparing main DB to reference DB."""
    print("\n  Sanity checks:")

    # Check a known unit: Byzantines Knight (Castle)
    cursor.execute(
        """SELECT us.hp, us.attack, us.melee_armor, us.pierce_armor, us.has_unit
           FROM unit_stats us
           JOIN units u ON us.unit_id = u.id
           JOIN civilizations c ON us.civ_id = c.id
           WHERE c.name='Byzantines' AND u.slug='knight' AND u.age_id=3"""
    )
    row = cursor.fetchone()
    if row:
        hp, atk, ma, pa, has = row
        rc.execute(
            "SELECT final_hp, final_attack, final_melee_armor, final_pierce_armor FROM ref_units WHERE civ_name='Byzantines' AND unit_slug='knight'"
        )
        ref = rc.fetchone()
        if ref:
            ok = (
                hp == int(ref["final_hp"])
                and atk == int(ref["final_attack"])
                and ma == int(ref["final_melee_armor"])
                and pa == int(ref["final_pierce_armor"])
                and has == 1
            )
            status = "PASS" if ok else "FAIL"
            print(
                f"    {status}: Byzantines Knight HP={hp}/{int(ref['final_hp'])}, "
                f"Atk={atk}/{int(ref['final_attack'])}, "
                f"MA={ma}/{int(ref['final_melee_armor'])}, "
                f"PA={pa}/{int(ref['final_pierce_armor'])}"
            )

    # Check a unit that some civs don't have (Eagle Warrior - only Aztecs, Mayans)
    cursor.execute(
        """SELECT c.name, us.has_unit
           FROM unit_stats us
           JOIN units u ON us.unit_id = u.id
           JOIN civilizations c ON us.civ_id = c.id
           WHERE u.slug='eagle_warrior' AND u.age_id=3
           ORDER BY c.name"""
    )
    eagle_rows = cursor.fetchall()
    if eagle_rows:
        has_eagle = [r[0] for r in eagle_rows if r[1] == 1]
        no_eagle = [r[0] for r in eagle_rows if r[1] == 0]
        print(
            f"    Eagle Warrior: has_unit=1 for {has_eagle}, has_unit=0 for {len(no_eagle)} civs"
        )

    # Check combat properties: Cataphract trample
    cursor.execute(
        """SELECT us.trample_flat_damage, us.trample_radius
           FROM unit_stats us
           JOIN units u ON us.unit_id = u.id
           JOIN civilizations c ON us.civ_id = c.id
           WHERE c.name='Byzantines' AND u.slug='cataphract_byzantines'"""
    )
    cat_row = cursor.fetchone()
    if cat_row:
        ok = cat_row[0] == 5 and cat_row[1] == 0.5
        status = "PASS" if ok else "FAIL"
        print(
            f"    {status}: Cataphract trample_flat_damage={cat_row[0]}, "
            f"trample_radius={cat_row[1]}"
        )

    # Check Chu Ko Nu extra projectiles
    cursor.execute(
        """SELECT us.extra_projectiles, us.extra_projectile_attacks_json
           FROM unit_stats us
           JOIN units u ON us.unit_id = u.id
           JOIN civilizations c ON us.civ_id = c.id
           WHERE c.name='Chinese' AND u.slug='chu_ko_nu_chinese'"""
    )
    cku_row = cursor.fetchone()
    if cku_row:
        ok = cku_row[0] == 2
        status = "PASS" if ok else "FAIL"
        print(
            f"    {status}: Chu Ko Nu extra_projectiles={cku_row[0]}, "
            f"attacks_json={cku_row[1]}"
        )

    # Check Fire Lancer charge projectiles
    cursor.execute(
        """SELECT us.charge_projectile_count, us.charge_projectile_attacks_json,
                  us.charge_attack_range, us.charge_ignores_armor
           FROM unit_stats us
           JOIN units u ON us.unit_id = u.id
           JOIN civilizations c ON us.civ_id = c.id
           WHERE c.name='Chinese' AND u.slug='fire_lancer'"""
    )
    fl_row = cursor.fetchone()
    if fl_row:
        ok = fl_row[0] == 3 and fl_row[2] == 4.0 and fl_row[3] == 1
        status = "PASS" if ok else "FAIL"
        print(
            f"    {status}: Fire Lancer charge_count={fl_row[0]}, "
            f"charge_range={fl_row[2]}, charge_ignores={fl_row[3]}"
        )

    # Check Berserk HP regen
    cursor.execute(
        """SELECT us.hp_regen
           FROM unit_stats us
           JOIN units u ON us.unit_id = u.id
           JOIN civilizations c ON us.civ_id = c.id
           WHERE c.name='Vikings' AND u.slug='berserk_vikings'"""
    )
    ber_row = cursor.fetchone()
    if ber_row:
        ok = ber_row[0] == 40.0
        status = "PASS" if ok else "FAIL"
        print(f"    {status}: Berserk hp_regen={ber_row[0]} (expected 40.0)")


def main():
    print("=" * 60)
    print("Generating main database from reference database")
    print("=" * 60)
    print(f"  Source: {REF_DB_PATH}")
    print(f"  Target: {MAIN_DB_PATH}")
    print()
    generate_main_database()


if __name__ == "__main__":
    main()
