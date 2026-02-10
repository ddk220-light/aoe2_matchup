import json
import os
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache

from flask import Flask, jsonify, redirect, render_template, request
from simulation import prepare_combat_unit, simulate_battle, simulate_mixed_battle

app = Flask(__name__)
app.json.sort_keys = False

# Database paths
DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_units.db")
REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")

# Age definitions
AGES = {
    "feudal": {"id": 2, "name": "Feudal Age"},
    "castle": {"id": 3, "name": "Castle Age"},
    "imperial": {"id": 4, "name": "Imperial Age"},
}


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_ref_db():
    """Get a connection to the reference/audit database."""
    conn = sqlite3.connect(REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_units_by_age():
    """Get list of available unit types organized by age."""
    conn = get_db()
    cursor = conn.cursor()

    units_by_age = {}
    for age_slug, age_data in AGES.items():
        cursor.execute(
            """
            SELECT slug, display_name
            FROM units
            WHERE age_id = ? AND unit_type = 'standard'
            ORDER BY display_name
            """,
            (age_data["id"],),
        )
        units = [
            {"id": row["slug"], "name": row["display_name"], "age": age_slug}
            for row in cursor.fetchall()
        ]
        units_by_age[age_slug] = {"name": age_data["name"], "units": units}

    conn.close()
    return units_by_age


def get_unit_data(age_id, unit_id):
    """Load unit data from database and compute unique stats."""
    if age_id not in AGES:
        return None

    conn = get_db()
    cursor = conn.cursor()

    # Get unit info
    cursor.execute(
        "SELECT id FROM units WHERE slug = ? AND age_id = ?",
        (unit_id, AGES[age_id]["id"]),
    )
    unit_row = cursor.fetchone()
    if not unit_row:
        conn.close()
        return None

    db_unit_id = unit_row["id"]

    # Get all stats for this unit
    cursor.execute(
        """
        SELECT
            c.name as Civilization,
            us.unit_name as Unit,
            us.hp as HP,
            us.attack as Attack,
            us.attack_range as Range,
            us.attack_speed as Attack_Speed,
            us.melee_armor as Melee_Armor,
            us.pierce_armor as Pierce_Armor,
            us.movement_speed as Movement_Speed,
            COALESCE(us.cost_food, 0) + COALESCE(us.cost_wood, 0) + COALESCE(us.cost_gold, 0) as Cost,
            us.creation_time as Creation_Time,
            us.upgrade_cost as Upgrade_Cost,
            us.civ_bonuses as Civ_Bonuses,
            us.has_unit as Has_Unit,
            us.combat_score as Combat_Eff
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        WHERE us.unit_id = ?
        ORDER BY us.combat_score DESC, c.name
        """,
        (db_unit_id,),
    )

    all_rows = cursor.fetchall()
    conn.close()

    # Convert rows to dicts
    records_has_unit = []
    missing_civs = []

    for row in all_rows:
        row_dict = dict(row)
        # Convert Has_Unit to Yes/No for compatibility
        if row_dict["Has_Unit"] == 1:
            row_dict["Civ_Bonuses"] = row_dict["Civ_Bonuses"] or "-"
            records_has_unit.append(row_dict)
        else:
            missing_civs.append(row_dict["Civilization"])

    # Define columns
    columns = [
        "Civilization",
        "Unit",
        "Combat_Eff",
        "HP",
        "Attack",
        "Range",
        "Attack_Speed",
        "Melee_Armor",
        "Pierce_Armor",
        "Movement_Speed",
        "Cost",
        "Creation_Time",
        "Upgrade_Cost",
        "Civ_Bonuses",
    ]

    # Remove Range if all values are None
    has_range = any(r.get("Range") is not None for r in records_has_unit)
    if not has_range:
        columns = [c for c in columns if c != "Range"]

    # Identify numeric columns for uniqueness detection
    numeric_cols = [
        "Combat_Eff",
        "HP",
        "Attack",
        "Range",
        "Attack_Speed",
        "Melee_Armor",
        "Pierce_Armor",
        "Movement_Speed",
        "Cost",
        "Creation_Time",
        "Upgrade_Cost",
    ]

    existing_numeric_cols = [col for col in numeric_cols if col in columns]

    # Find unique values for each stat
    unique_stats = {}
    for col in existing_numeric_cols:
        values = [r[col] for r in records_has_unit if r.get(col) is not None]
        if len(values) > 0:
            # Find the most common value (baseline)
            from collections import Counter

            value_counts = Counter(values)
            baseline = value_counts.most_common(1)[0][0]
            # Mark values that differ from baseline as unique
            unique_stats[col] = {"baseline": baseline, "unique_civs": {}}
            for row in records_has_unit:
                val = row.get(col)
                if val is not None and val != baseline:
                    civ = row["Civilization"]
                    unique_stats[col]["unique_civs"][civ] = val

    return {
        "records": records_has_unit,
        "columns": columns,
        "unique_stats": unique_stats,
        "total_civs": len(records_has_unit),
        "missing_civs": sorted(missing_civs),
    }


def get_civ_data(civ_name):
    """Get all units for a specific civilization."""
    conn = get_db()
    cursor = conn.cursor()

    # Get civ id
    cursor.execute("SELECT id FROM civilizations WHERE name = ?", (civ_name,))
    civ_row = cursor.fetchone()
    if not civ_row:
        conn.close()
        return None

    civ_id = civ_row["id"]

    # Get all units for this civ organized by age
    cursor.execute(
        """
        SELECT
            a.name as age_name,
            a.id as age_id,
            u.display_name as unit_name,
            u.slug as unit_slug,
            us.unit_name as actual_unit,
            us.hp, us.attack, us.attack_range, us.attack_speed,
            us.melee_armor, us.pierce_armor, us.movement_speed,
            us.cost_food, us.cost_wood, us.cost_gold,
            us.creation_time, us.upgrade_cost, us.civ_bonuses,
            us.has_unit
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        JOIN ages a ON u.age_id = a.id
        WHERE us.civ_id = ?
        ORDER BY a.id, u.display_name
        """,
        (civ_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    # Organize by age
    units_by_age = {}
    for row in rows:
        age_name = row["age_name"]
        if age_name not in units_by_age:
            units_by_age[age_name] = []

        unit_data = {
            "unit_type": row["unit_name"],
            "unit_slug": row["unit_slug"],
            "actual_unit": row["actual_unit"],
            "has_unit": row["has_unit"] == 1,
            "stats": {
                "hp": row["hp"],
                "attack": row["attack"],
                "range": row["attack_range"],
                "attack_speed": row["attack_speed"],
                "melee_armor": row["melee_armor"],
                "pierce_armor": row["pierce_armor"],
                "movement_speed": row["movement_speed"],
                "cost_food": row["cost_food"],
                "cost_wood": row["cost_wood"],
                "cost_gold": row["cost_gold"],
                "creation_time": row["creation_time"],
                "upgrade_cost": row["upgrade_cost"],
            },
            "civ_bonuses": row["civ_bonuses"],
        }
        units_by_age[age_name].append(unit_data)

    return {"civilization": civ_name, "units_by_age": units_by_age}


def get_all_civs():
    """Get list of all civilizations."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM civilizations ORDER BY name")
    civs = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return civs


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/units")
def units():
    units_by_age = get_units_by_age()
    ages = {k: v["name"] for k, v in AGES.items()}
    return render_template("index.html", units_by_age=units_by_age, ages=ages)


@app.route("/api/debug")
def api_debug():
    """Debug endpoint to check database state."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name, us.hp
        FROM unit_stats us
        JOIN civilizations c ON us.civ_id = c.id
        JOIN units u ON us.unit_id = u.id
        WHERE u.slug = 'hussar' AND c.name = 'Mongols'
    """)
    row = cursor.fetchone()
    conn.close()
    import os

    return jsonify(
        {
            "mongol_hussar_hp": row["hp"] if row else None,
            "db_path": DB_PATH,
            "db_exists": os.path.exists(DB_PATH),
            "db_size": os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0,
            "version": "2024-02-04-v2",
        }
    )


@app.route("/api/units")
def api_units():
    return jsonify(get_units_by_age())


@app.route("/api/unit/<age_id>/<unit_id>")
def api_unit_data(age_id, unit_id):
    if age_id not in AGES:
        return jsonify({"error": "Invalid age"}), 404
    data = get_unit_data(age_id, unit_id)
    if data is None:
        return jsonify({"error": "Unit not found"}), 404
    return jsonify(data)


@app.route("/api/civs")
def api_civs():
    """Get list of all civilizations."""
    civs = get_all_civs()
    return jsonify(civs)


@app.route("/api/civ/<civ_name>")
def api_civ_data(civ_name):
    """Get all units for a specific civilization."""
    data = get_civ_data(civ_name)
    if data is None:
        return jsonify({"error": "Civilization not found"}), 404
    return jsonify(data)


# ============== Comment System ==============


def get_unit_and_civ_ids(unit_slug, civ_name):
    """Get unit_id and civ_id from their names."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM units WHERE slug = ?", (unit_slug,))
    unit_row = cursor.fetchone()

    cursor.execute("SELECT id FROM civilizations WHERE name = ?", (civ_name,))
    civ_row = cursor.fetchone()

    conn.close()

    if not unit_row or not civ_row:
        return None, None

    return unit_row["id"], civ_row["id"]


@app.route("/api/comments", methods=["POST"])
def add_comment():
    """Add a new comment to a specific cell."""
    data = request.get_json()

    unit_slug = data.get("unit_slug")
    civ_name = data.get("civ_name")
    column_name = data.get("column_name")
    comment_text = data.get("comment_text")
    author_name = data.get("author_name", "Anonymous")

    if not all([unit_slug, civ_name, column_name, comment_text]):
        return jsonify({"error": "Missing required fields"}), 400

    unit_id, civ_id = get_unit_and_civ_ids(unit_slug, civ_name)
    if not unit_id or not civ_id:
        return jsonify({"error": "Invalid unit or civilization"}), 404

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO comments (unit_id, civ_id, column_name, comment_text, author_name)
        VALUES (?, ?, ?, ?, ?)
        """,
        (unit_id, civ_id, column_name, comment_text, author_name),
    )

    comment_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"success": True, "comment_id": comment_id})


@app.route("/api/comments/<unit_slug>")
def get_comments_for_unit(unit_slug):
    """Get all comments for a specific unit."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM units WHERE slug = ?", (unit_slug,))
    unit_row = cursor.fetchone()
    if not unit_row:
        conn.close()
        return jsonify({"error": "Unit not found"}), 404

    unit_id = unit_row["id"]

    cursor.execute(
        """
        SELECT
            cm.id,
            c.name as civ_name,
            cm.column_name,
            cm.comment_text,
            cm.author_name,
            cm.created_at,
            cm.resolved
        FROM comments cm
        JOIN civilizations c ON cm.civ_id = c.id
        WHERE cm.unit_id = ?
        ORDER BY cm.created_at DESC
        """,
        (unit_id,),
    )

    comments = []
    for row in cursor.fetchall():
        comments.append(
            {
                "id": row["id"],
                "civ_name": row["civ_name"],
                "column_name": row["column_name"],
                "comment_text": row["comment_text"],
                "author_name": row["author_name"],
                "created_at": row["created_at"],
                "resolved": row["resolved"] == 1,
            }
        )

    conn.close()
    return jsonify(comments)


@app.route("/api/comments/all")
def get_all_comments():
    """Get all comments for review, optionally filtered by resolved status."""
    resolved_filter = request.args.get("resolved")

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT
            cm.id,
            u.slug as unit_slug,
            u.display_name as unit_name,
            a.name as age_name,
            c.name as civ_name,
            cm.column_name,
            cm.comment_text,
            cm.author_name,
            cm.created_at,
            cm.resolved
        FROM comments cm
        JOIN units u ON cm.unit_id = u.id
        JOIN ages a ON u.age_id = a.id
        JOIN civilizations c ON cm.civ_id = c.id
    """

    params = []
    if resolved_filter is not None:
        query += " WHERE cm.resolved = ?"
        params.append(1 if resolved_filter == "true" else 0)

    query += " ORDER BY cm.created_at DESC"

    cursor.execute(query, params)

    comments = []
    for row in cursor.fetchall():
        comments.append(
            {
                "id": row["id"],
                "unit_slug": row["unit_slug"],
                "unit_name": row["unit_name"],
                "age_name": row["age_name"],
                "civ_name": row["civ_name"],
                "column_name": row["column_name"],
                "comment_text": row["comment_text"],
                "author_name": row["author_name"],
                "created_at": row["created_at"],
                "resolved": row["resolved"] == 1,
            }
        )

    conn.close()
    return jsonify(comments)


@app.route("/api/comments/<int:comment_id>/resolve", methods=["POST"])
def resolve_comment(comment_id):
    """Mark a comment as resolved."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("UPDATE comments SET resolved = 1 WHERE id = ?", (comment_id,))

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Comment not found"}), 404

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/comments/<int:comment_id>", methods=["DELETE"])
def delete_comment(comment_id):
    """Delete a comment."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Comment not found"}), 404

    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/review")
def review_comments():
    """Page to review all comments."""
    return render_template("review.html")


@app.route("/civ")
def civ_view():
    """Civilization selection grid."""
    return render_template("civ_select.html")


@app.route("/civ/<civ_name>")
def civ_detail(civ_name):
    """Civilization unit detail page."""
    if civ_name not in ORIGINAL_13_CIVS:
        return redirect("/civ")
    return render_template("civ_detail.html", civ_name=civ_name)


# ============== Battle Simulation ==============


@app.route("/simulate")
def simulate():
    """Battle simulation page."""
    return render_template("simulate.html")


@app.route("/api/combat-unit/<civ_name>/<unit_slug>")
def api_combat_unit(civ_name, unit_slug):
    """Get combat stats for a specific civ/unit combination."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            us.id, us.hp, us.attack, us.attack_range, us.attack_speed,
            us.melee_armor, us.pierce_armor, us.movement_speed,
            us.attacks_json, us.armors_json,
            us.unit_name, c.name as civ_name, u.slug,
            us.cost_food, us.cost_wood, us.cost_gold, us.attack_delay,
            us.min_attack_range, us.is_siege_projectile, us.splash_radius,
            us.projectile_speed, us.ignores_pierce_armor, us.ignores_melee_armor,
            us.trample_percent, us.trample_radius, us.trample_flat_damage,
            us.bonus_damage_reduction, us.unit_category, us.paired_unit_slug,
            us.extra_projectiles, us.extra_projectile_attacks_json,
            us.splash_on_hit_radius,
            us.dodge_shield_max, us.dodge_shield_recharge,
            us.bleed_dps, us.bleed_duration, us.block_first_melee,
            us.attack_bonus_per_kill, us.first_attack_extra_projectiles,
            us.hp_regen, us.pass_through_percent, us.hp_transform_threshold
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        JOIN civilizations c ON us.civ_id = c.id
        WHERE c.name = ? AND u.slug = ? AND us.has_unit = 1
    """,
        (civ_name, unit_slug),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Unit not found"}), 404

    cost_food = row["cost_food"] or 0
    cost_wood = row["cost_wood"] or 0
    cost_gold = row["cost_gold"] or 0
    total_cost = cost_food + cost_wood + cost_gold

    return jsonify(
        {
            "id": row["id"],
            "name": row["unit_name"],
            "civ": row["civ_name"],
            "slug": row["slug"],
            "hp": row["hp"],
            "attack": row["attack"],
            "attack_range": row["attack_range"] or 0,
            "attack_speed": row["attack_speed"],
            "attack_delay": row["attack_delay"] or 0,
            "melee_armor": row["melee_armor"],
            "pierce_armor": row["pierce_armor"],
            "movement_speed": row["movement_speed"],
            "attacks_json": row["attacks_json"],
            "armors_json": row["armors_json"],
            "cost_food": cost_food,
            "cost_wood": cost_wood,
            "cost_gold": cost_gold,
            "total_cost": total_cost,
            # Combat properties for data-driven simulation
            "min_attack_range": row["min_attack_range"] or 0,
            "is_siege_projectile": row["is_siege_projectile"] or 0,
            "splash_radius": row["splash_radius"] or 0,
            "projectile_speed": row["projectile_speed"] or 0,
            "ignores_pierce_armor": row["ignores_pierce_armor"] or 0,
            "ignores_melee_armor": row["ignores_melee_armor"] or 0,
            "trample_percent": row["trample_percent"] or 0,
            "trample_radius": row["trample_radius"] or 0,
            "trample_flat_damage": row["trample_flat_damage"] or 0,
            "bonus_damage_reduction": row["bonus_damage_reduction"] or 0,
            "unit_category": row["unit_category"] or "military",
            "paired_unit_slug": row["paired_unit_slug"],
            "extra_projectiles": row["extra_projectiles"] or 0,
            "splash_on_hit_radius": row["splash_on_hit_radius"] or 0,
            "dodge_shield_max": row["dodge_shield_max"] or 0,
            "dodge_shield_recharge": row["dodge_shield_recharge"] or 0,
            "bleed_dps": row["bleed_dps"] or 0,
            "bleed_duration": row["bleed_duration"] or 0,
            "block_first_melee": row["block_first_melee"] or 0,
            "attack_bonus_per_kill": row["attack_bonus_per_kill"] or 0,
            "first_attack_extra_projectiles": row["first_attack_extra_projectiles"]
            or 0,
            "hp_regen": row["hp_regen"] or 0,
            "pass_through_percent": row["pass_through_percent"] or 0,
            "hp_transform_threshold": row["hp_transform_threshold"] or 0,
        }
    )


@app.route("/api/armor-classes")
def api_armor_classes():
    """Get all armor class names."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM armor_classes ORDER BY id")
    classes = {str(row["id"]): row["name"] for row in cursor.fetchall()}
    conn.close()
    return jsonify(classes)


@app.route("/api/civ-units/<civ_name>/<age_slug>")
def api_civ_units(civ_name, age_slug):
    """Get all units available for a civilization in a specific age."""
    if age_slug not in AGES:
        return jsonify({"error": "Invalid age"}), 404

    age_id = AGES[age_slug]["id"]

    conn = get_db()
    cursor = conn.cursor()

    # Get civ id
    cursor.execute("SELECT id FROM civilizations WHERE name = ?", (civ_name,))
    civ_row = cursor.fetchone()
    if not civ_row:
        conn.close()
        return jsonify({"error": "Civilization not found"}), 404

    civ_id = civ_row["id"]

    # Get all units this civ has in this age (both standard and unique)
    cursor.execute(
        """
        SELECT DISTINCT u.slug, us.unit_name, u.unit_type
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        WHERE us.civ_id = ? AND u.age_id = ? AND us.has_unit = 1
        ORDER BY u.unit_type DESC, us.unit_name
    """,
        (civ_id, age_id),
    )

    units = [
        {"slug": row["slug"], "name": row["unit_name"], "type": row["unit_type"]}
        for row in cursor.fetchall()
    ]

    conn.close()
    return jsonify(units)


def init_comments_table():
    """Create simulation_comments table if it doesn't exist."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_comments (
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
        )
    """
    )
    conn.commit()
    conn.close()


# Initialize comments table on startup
init_comments_table()


def init_verifications_table():
    """Create unit_verifications table if it doesn't exist."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS unit_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_unit_id INTEGER NOT NULL UNIQUE,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


init_verifications_table()

ORIGINAL_13_CIVS = [
    "Aztecs",
    "Britons",
    "Byzantines",
    "Celts",
    "Chinese",
    "Franks",
    "Goths",
    "Huns",
    "Incas",
    "Italians",
    "Japanese",
    "Koreans",
    "Magyars",
    "Mayans",
    "Mongols",
    "Persians",
    "Saracens",
    "Slavs",
    "Spanish",
    "Teutons",
    "Turks",
    "Vikings",
]


# ============== Unit Analysis ==============


@app.route("/analysis")
def analysis():
    """Unit analysis/verification page."""
    return render_template("analysis.html", civs=ORIGINAL_13_CIVS)


@app.route("/api/ref/armor-classes")
def api_ref_armor_classes():
    """Get armor class ID→name mapping from reference DB."""
    ref_conn = get_ref_db()
    # Use the main DB's armor_classes table
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM armor_classes ORDER BY id")
    classes = {str(row["id"]): row["name"] for row in cursor.fetchall()}
    conn.close()
    ref_conn.close()
    return jsonify(classes)


@app.route("/api/ref/civ/<civ_name>")
def api_ref_civ(civ_name):
    """Get all reference data for a civilization."""
    if civ_name not in ORIGINAL_13_CIVS:
        return jsonify({"error": "Civilization not in original 13"}), 404

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Get all units for this civ
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? ORDER BY age DESC, unit_name",
        (civ_name,),
    )
    units_rows = rc.fetchall()

    # Get verifications
    main_conn = get_db()
    mc = main_conn.cursor()
    mc.execute("SELECT ref_unit_id FROM unit_verifications")
    verified_ids = {row["ref_unit_id"] for row in mc.fetchall()}
    main_conn.close()

    # Get armor class names
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM armor_classes ORDER BY id")
    ac_names = {str(row["id"]): row["name"] for row in cursor.fetchall()}
    conn.close()

    units = []
    for row in units_rows:
        uid = row["id"]

        # Get techs applied
        rc.execute(
            """SELECT tech_name, tech_type, building, age_available, effect_description
               FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id""",
            (uid,),
        )
        techs = [dict(t) for t in rc.fetchall()]

        # Get stat chain
        rc.execute(
            """SELECT step_order, tech_name, tech_type,
                      hp, attack, melee_armor, pierce_armor,
                      speed, range_val, reload_time, accuracy, los,
                      train_time, cost_food, cost_wood, cost_gold,
                      attacks_json, armors_json
               FROM ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order""",
            (uid,),
        )
        stat_chain = [dict(s) for s in rc.fetchall()]

        # Get special effects
        rc.execute(
            """SELECT property_name, property_value, source, description
               FROM ref_special_effects WHERE ref_unit_id=?""",
            (uid,),
        )
        special = [dict(s) for s in rc.fetchall()]

        # Convert class IDs to names in attack/armor JSONs
        def convert_classes(json_str):
            if not json_str:
                return {}
            raw = json.loads(json_str)
            return {ac_names.get(k, f"class_{k}"): v for k, v in raw.items()}

        # Get projectiles
        rc.execute(
            """SELECT projectile_type, projectile_count, projectile_speed,
                      attacks_json, blast_radius, is_siege_projectile
               FROM ref_projectiles WHERE ref_unit_id=?""",
            (uid,),
        )
        projectiles_raw = rc.fetchall()
        projectiles = []
        for p in projectiles_raw:
            pd = dict(p)
            if pd.get("attacks_json"):
                pd["attacks"] = convert_classes(pd["attacks_json"])
            projectiles.append(pd)

        unit = {
            "id": uid,
            "unit_name": row["unit_name"],
            "unit_slug": row["unit_slug"],
            "unit_type": row["unit_type"],
            "age": row["age"],
            "unit_class_name": row["unit_class_name"],
            "is_ranged": bool(row["is_ranged"]),
            "verified": uid in verified_ids,
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
                "cost_food": row["base_cost_food"],
                "cost_wood": row["base_cost_wood"],
                "cost_gold": row["base_cost_gold"],
                "train_time": row["base_train_time"],
            },
            "final_stats": {
                "hp": row["final_hp"],
                "attack": row["final_attack"],
                "melee_armor": row["final_melee_armor"],
                "pierce_armor": row["final_pierce_armor"],
                "range": row["final_range"],
                "speed": row["final_speed"],
                "reload_time": row["final_reload_time"],
                "attack_delay": row["final_attack_delay"],
                "accuracy": row["final_accuracy"],
                "los": row["final_los"],
                "cost_food": row["final_cost_food"],
                "cost_wood": row["final_cost_wood"],
                "cost_gold": row["final_cost_gold"],
                "train_time": row["final_train_time"],
            },
            "base_attacks": convert_classes(row["base_attacks_json"]),
            "final_attacks": convert_classes(row["final_attacks_json"]),
            "base_armors": convert_classes(row["base_armors_json"]),
            "final_armors": convert_classes(row["final_armors_json"]),
            "total_projectiles": row["total_projectiles"],
            "projectile_speed": row["projectile_speed"],
            "min_range": row["min_range"],
            "upgrade_cost": {
                "food": row["upgrade_cost_food"] or 0,
                "wood": row["upgrade_cost_wood"] or 0,
                "gold": row["upgrade_cost_gold"] or 0,
            },
            "techs_applied": techs,
            "stat_chain": stat_chain,
            "special_effects": special,
            "projectiles": projectiles,
        }
        units.append(unit)

    ref_conn.close()

    # Group by age
    by_age = {"Castle": [], "Imperial": []}
    for u in units:
        if u["age"] in by_age:
            by_age[u["age"]].append(u)

    return jsonify(
        {
            "civ_name": civ_name,
            "units_by_age": by_age,
            "total_units": len(units),
            "verified_count": sum(1 for u in units if u["verified"]),
        }
    )


# ===== Combat unit building from reference DB =====


def _build_combat_dict_from_ref(rc, row):
    """Build a dict from a ref_units row + related tables, compatible with prepare_combat_unit().

    Args:
        rc: sqlite3 cursor on the reference DB
        row: sqlite3.Row from ref_units table

    Returns:
        dict with fields matching prepare_combat_unit() expectations
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
        if p["projectile_type"] == "primary":
            primary_proj = dict(p)
        elif p["projectile_type"] == "extra":
            extra_proj = dict(p)
        elif p["projectile_type"] == "charge":
            charge_proj = dict(p)

    reload_time = row["final_reload_time"] or 2.0
    attack_speed = 1.0 / reload_time if reload_time > 0 else 0.5

    return {
        "slug": row["unit_slug"],
        "unit_name": row["unit_name"],
        "unit_category": "military",
        "paired_unit_slug": None,
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "attack_range": row["final_range"],
        "attack_speed": attack_speed,
        "attack_delay": row["final_attack_delay"] or 0,
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "movement_speed": row["final_speed"],
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
        "upgrade_cost_food": row["upgrade_cost_food"] or 0,
        "upgrade_cost_wood": row["upgrade_cost_wood"] or 0,
        "upgrade_cost_gold": row["upgrade_cost_gold"] or 0,
        "attacks_json": row["final_attacks_json"],
        "armors_json": row["final_armors_json"],
        "min_attack_range": row["min_range"] or 0,
        # From projectiles
        "accuracy": row["final_accuracy"] or 100,
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
        "trample_percent": special.get("trample_percent", 0),
        "trample_radius": special.get("trample_radius", 0),
        "trample_flat_damage": special.get("trample_flat_damage", 0),
        "hp_regen": special.get("hp_regen", 0),
        "charge_projectile_count": charge_proj["projectile_count"]
        if charge_proj
        else 0,
        "charge_projectile_speed": charge_proj["projectile_speed"]
        if charge_proj
        else 0,
        "charge_projectile_attacks_json": charge_proj["attacks_json"]
        if charge_proj
        else None,
        "charge_attack_range": float(special.get("charge_attack_range", 0)),
        "charge_ignores_armor": int(special.get("charge_ignores_armor", 0)),
        # Special combat properties (from ref_special_effects or defaults)
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
        "hp_regen": special.get("hp_regen", 0),
        "pass_through_percent": special.get("pass_through_percent", 0),
        "hp_transform_threshold": special.get("hp_transform_threshold", 0),
        # No dismount/transform in original 13 ref DB
        "dismount_hp": None,
        "dismount_attack": None,
        "dismount_melee_armor": None,
        "dismount_pierce_armor": None,
        "dismount_attack_speed": None,
        "dismount_attack_delay": None,
        "dismount_movement_speed": None,
        "dismount_attacks_json": None,
        "dismount_armors_json": None,
        "transform_hp": None,
        "transform_attack": None,
        "transform_melee_armor": None,
        "transform_pierce_armor": None,
        "transform_attack_speed": None,
        "transform_attack_delay": None,
        "transform_movement_speed": None,
        "transform_attacks_json": None,
        "transform_armors_json": None,
    }


@app.route("/api/ref/combat-unit/<civ_name>/<unit_slug>")
def api_ref_combat_unit(civ_name, unit_slug):
    """Get combat-ready stats for a unit from reference DB (for battle simulator)."""
    if civ_name not in ORIGINAL_13_CIVS:
        return jsonify({"error": "Civilization not in original 13"}), 404

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?",
        (civ_name, unit_slug),
    )
    row = rc.fetchone()
    if not row:
        ref_conn.close()
        return jsonify({"error": f"Unit {unit_slug} not found for {civ_name}"}), 404

    result = _build_combat_dict_from_ref(rc, row)

    # Add stat chain for debug breakdown (HTTP endpoint only)
    rc.execute(
        """SELECT step_order, tech_name, tech_type, attack, melee_armor, pierce_armor,
                  attacks_json, armors_json
           FROM ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order""",
        (row["id"],),
    )
    result["stat_chain"] = [
        {
            "step": sc["step_order"],
            "tech": sc["tech_name"],
            "type": sc["tech_type"],
            "attacks_json": sc["attacks_json"],
            "armors_json": sc["armors_json"],
        }
        for sc in rc.fetchall()
    ]

    # Extra fields for HTTP response
    result["name"] = row["unit_name"]
    result["civ"] = civ_name
    result["total_cost"] = (
        (row["final_cost_food"] or 0)
        + (row["final_cost_wood"] or 0)
        + (row["final_cost_gold"] or 0)
    )
    result["outline_size"] = row["outline_size_x"] or 0.2

    ref_conn.close()
    return jsonify(result)


# ===== Unit Lines config for rankings page =====
UNIT_LINES = {
    "militia": {
        "name": "Militia Line",
        "building": "Barracks",
        "castle_slug": "swordsmen",
        "imperial_slug": "champion",
        "unique_units": {
            "Goths": ("huskarl_goths", "elite_huskarl_goths"),
            "Celts": ("woad_raider_celts", "elite_woad_raider_celts"),
            "Vikings": ("berserk_vikings", "elite_berserk_vikings"),
            "Japanese": ("samurai_japanese", "elite_samurai_japanese"),
            "Teutons": ("teutonic_knight_teutons", "elite_teutonic_knight_teutons"),
            "Aztecs": ("jaguar_warrior_aztecs", "elite_jaguar_warrior_aztecs"),
            "Incas": ("kamayuk_incas", "elite_kamayuk_incas"),
            "Italians": (None, "condottiero"),
        },
    },
    "spear": {
        "name": "Spear Line",
        "building": "Barracks",
        "castle_slug": "pikeman",
        "imperial_slug": "halberdier",
        "unique_units": {},
    },
    "shock_infantry": {
        "name": "Shock Infantry",
        "building": "Barracks",
        "castle_slug": "fire_lancer",
        "imperial_slug": "elite_fire_lancer",
        "unique_units": {
            "Aztecs": ("eagle_warrior", "elite_eagle"),
            "Incas": ("eagle_warrior", "elite_eagle"),
            "Mayans": ("eagle_warrior", "elite_eagle"),
        },
    },
    "archer": {
        "name": "Archers & Gunpowder",
        "building": "Archery Range",
        "castle_slug": "crossbow",
        "imperial_slug": "arbalester",
        "extra_imperial_slugs": ["hand_cannoneer"],
        "unique_units": {
            "Britons": ("longbowman_britons", "elite_longbowman_britons"),
            "Chinese": ("chu_ko_nu_chinese", "elite_chu_ko_nu_chinese"),
            "Mayans": ("plumed_archer_mayans", "elite_plumed_archer_mayans"),
            "Italians": (
                "genoese_crossbowman_italians",
                "elite_genoese_crossbowman_italians",
            ),
            "Turks": ("janissary_turks", "elite_janissary_turks"),
            "Franks": ("throwing_axeman_franks", "elite_throwing_axeman_franks"),
            "Incas": ("slinger", "imp_slinger"),
        },
    },
    "skirmisher": {
        "name": "Skirmisher Line",
        "building": "Archery Range",
        "castle_slug": "elite_skirm",
        "imperial_slug": "imp_elite_skirm",
        "unique_units": {},
    },
    "cav_archer": {
        "name": "Cavalry Archer Line",
        "building": "Archery Range",
        "castle_slug": "cav_archer",
        "imperial_slug": "heavy_cav_archer",
        "unique_units": {
            "Mongols": ("mangudai_mongols", "elite_mangudai_mongols"),
            "Saracens": ("mameluke_saracens", "elite_mameluke_saracens"),
            "Koreans": ("war_wagon_koreans", "elite_war_wagon_koreans"),
            "Spanish": ("conquistador_spanish", "elite_conquistador_spanish"),
        },
    },
    "knight": {
        "name": "Knight Line",
        "building": "Stable",
        "castle_slug": "knight",
        "imperial_slug": "paladin",
        "unique_units": {
            "Byzantines": ("cataphract_byzantines", "elite_cataphract_byzantines"),
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
            "Slavs": ("boyar_slavs", "elite_boyar_slavs"),
        },
    },
    "light_cav": {
        "name": "Light Cavalry Line",
        "building": "Stable",
        "castle_slug": "light_cav",
        "imperial_slug": "hussar",
        "unique_units": {
            "Magyars": ("magyar_huszar_magyars", "elite_magyar_huszar_magyars"),
        },
    },
    "camel": {
        "name": "Camel Line",
        "building": "Stable",
        "castle_slug": "camel",
        "imperial_slug": "heavy_camel",
        "unique_units": {},
    },
    "steppe_lancer": {
        "name": "Steppe Lancer",
        "building": "Stable",
        "castle_slug": "steppe_lancer",
        "imperial_slug": "elite_steppe",
        "unique_units": {},
    },
    "elephant": {
        "name": "Elephant Line",
        "building": "Stable",
        "castle_slug": None,
        "imperial_slug": None,
        "unique_units": {
            "Persians": ("war_elephant_persians", "elite_war_elephant_persians"),
        },
    },
    "ram": {
        "name": "Ram Line",
        "building": "Siege Workshop",
        "castle_slug": "ram",
        "imperial_slug": "siege_ram",
        "unique_units": {},
    },
    "mangonel": {
        "name": "Mangonel Line",
        "building": "Siege Workshop",
        "castle_slug": "mangonel",
        "imperial_slug": "siege_onager",
        "unique_units": {},
    },
    "scorpion": {
        "name": "Scorpion Line",
        "building": "Siege Workshop",
        "castle_slug": "scorpion",
        "imperial_slug": "heavy_scorpion",
        "unique_units": {},
    },
    "trebuchet": {
        "name": "Trebuchet",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "trebuchet",
        "unique_units": {},
    },
    "bombard_cannon": {
        "name": "Bombard Cannon",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "bombard_cannon",
        "unique_units": {},
    },
    "all_cavalry": {
        "name": "All Cavalry (Gold)",
        "building": "Stable",
        "castle_slug": None,
        "imperial_slug": None,
        "castle_slugs": ["knight", "camel", "steppe_lancer"],
        "imperial_slugs": ["paladin", "heavy_camel", "elite_steppe"],
        "unique_units": {
            "Byzantines": ("cataphract_byzantines", "elite_cataphract_byzantines"),
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
            "Slavs": ("boyar_slavs", "elite_boyar_slavs"),
        },
    },
    "all_ranged": {
        "name": "All Ranged (Gold)",
        "building": "Archery Range",
        "castle_slug": None,
        "imperial_slug": None,
        "castle_slugs": ["crossbow", "cav_archer"],
        "imperial_slugs": ["arbalester", "heavy_cav_archer", "hand_cannoneer"],
        "unique_units": {
            "Britons": ("longbowman_britons", "elite_longbowman_britons"),
            "Chinese": ("chu_ko_nu_chinese", "elite_chu_ko_nu_chinese"),
            "Mayans": ("plumed_archer_mayans", "elite_plumed_archer_mayans"),
            "Italians": (
                "genoese_crossbowman_italians",
                "elite_genoese_crossbowman_italians",
            ),
            "Turks": ("janissary_turks", "elite_janissary_turks"),
            "Franks": ("throwing_axeman_franks", "elite_throwing_axeman_franks"),
            "Incas": ("slinger", "imp_slinger"),
            "Mongols": ("mangudai_mongols", "elite_mangudai_mongols"),
            "Saracens": ("mameluke_saracens", "elite_mameluke_saracens"),
            "Koreans": ("war_wagon_koreans", "elite_war_wagon_koreans"),
            "Spanish": ("conquistador_spanish", "elite_conquistador_spanish"),
        },
    },
}


# ===== Pre-computed battle scores (loaded from battle_scores.json) =====
# Generated by: cd webapp && python3 compute_battle_scores.py

BATTLE_SCORES_PATH = os.path.join(os.path.dirname(__file__), "battle_scores.json")

_ROUND_ROBIN = {}
_BENCHMARKS = {}

if os.path.exists(BATTLE_SCORES_PATH):
    with open(BATTLE_SCORES_PATH) as _f:
        _scores_data = json.load(_f)
        _ROUND_ROBIN = _scores_data.get("round_robin", {})
        _BENCHMARKS = _scores_data.get("benchmarks", {})
    print(
        f"Battle scores loaded: {len(_ROUND_ROBIN)} round-robin, {len(_BENCHMARKS)} benchmark line-ages"
    )
else:
    print(
        f"WARNING: {BATTLE_SCORES_PATH} not found. Run: cd webapp && python3 compute_battle_scores.py"
    )


@app.route("/api/ref/unit-line/<line_slug>")
def api_ref_unit_line(line_slug):
    """Get comparison data for a unit line across all civs."""
    if line_slug not in UNIT_LINES:
        return jsonify({"error": "Unknown unit line"}), 404

    line = UNIT_LINES[line_slug]
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    stat_cols = """civ_name, unit_name, unit_slug, unit_type, age,
        final_hp, final_attack, final_melee_armor, final_pierce_armor,
        final_speed, final_range, final_reload_time,
        final_cost_food, final_cost_wood, final_cost_gold,
        upgrade_cost_food, upgrade_cost_wood, upgrade_cost_gold,
        applied_bonuses_summary"""

    result = {
        "line_name": line["name"],
        "building": line["building"],
        "castle": [],
        "imperial": [],
    }

    def _attach_scores(entry, age_key):
        """Attach battle scores and benchmark scores from pre-computed JSON."""
        line_key = f"{line_slug}|{age_key}"
        unit_key = f"{entry['civ_name']}|{entry['unit_slug']}"
        rr = _ROUND_ROBIN.get(line_key, {}).get(unit_key, {})
        entry["score_30v30"] = rr.get("score_30v30", -999)
        entry["score_3k"] = rr.get("score_3k", -999)
        entry["score_5k"] = rr.get("score_5k", -999)
        bm = _BENCHMARKS.get(line_key, {}).get(unit_key, {})
        entry["vs_champ"] = bm.get("vs_champ", -999)
        entry["vs_paladin"] = bm.get("vs_paladin", -999)
        entry["vs_arb"] = bm.get("vs_arb", -999)

    # Fetch standard units for each age (supports multi-slug lines)
    for age_key, slug_key, slugs_key, db_age in [
        ("castle", "castle_slug", "castle_slugs", "Castle"),
        ("imperial", "imperial_slug", "imperial_slugs", "Imperial"),
    ]:
        slugs = line.get(slugs_key, [line[slug_key]] if line[slug_key] else [])
        for slug in slugs:
            rc.execute(
                f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
                (slug, db_age),
            )
            for row in rc.fetchall():
                entry = dict(row)
                entry["is_unique"] = False
                _attach_scores(entry, age_key)
                result[age_key].append(entry)

    # Fetch extra standard units (e.g. Hand Cannoneer in archer line)
    for extra_slug in line.get("extra_imperial_slugs", []):
        rc.execute(
            f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
            (extra_slug, "Imperial"),
        )
        for row in rc.fetchall():
            entry = dict(row)
            entry["is_unique"] = False
            _attach_scores(entry, "imperial")
            result["imperial"].append(entry)

    # Fetch unique units
    for civ_name, (castle_uu, imperial_uu) in line.get("unique_units", {}).items():
        for uu_slug, age_key in [(castle_uu, "castle"), (imperial_uu, "imperial")]:
            if not uu_slug:
                continue
            rc.execute(
                f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND civ_name=?",
                (uu_slug, civ_name),
            )
            row = rc.fetchone()
            if row:
                entry = dict(row)
                entry["is_unique"] = True
                _attach_scores(entry, age_key)
                result[age_key].append(entry)

    ref_conn.close()
    return jsonify(result)


@app.route("/api/ref/verify/<int:ref_unit_id>", methods=["POST"])
def verify_unit(ref_unit_id):
    """Mark a unit as verified."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO unit_verifications (ref_unit_id) VALUES (?)",
        (ref_unit_id,),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/ref/verify/<int:ref_unit_id>", methods=["DELETE"])
def unverify_unit(ref_unit_id):
    """Unmark a unit verification."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM unit_verifications WHERE ref_unit_id=?", (ref_unit_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/ref/verify-all/<civ_name>", methods=["POST"])
def verify_all_civ(civ_name):
    """Mark all units for a civ as verified."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute("SELECT id FROM ref_units WHERE civ_name=?", (civ_name,))
    unit_ids = [row["id"] for row in rc.fetchall()]
    ref_conn.close()

    conn = get_db()
    cursor = conn.cursor()
    for uid in unit_ids:
        cursor.execute(
            "INSERT OR IGNORE INTO unit_verifications (ref_unit_id) VALUES (?)",
            (uid,),
        )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "count": len(unit_ids)})


@app.route("/api/ref/verify-all/<civ_name>", methods=["DELETE"])
def unverify_all_civ(civ_name):
    """Unmark all verifications for a civ."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute("SELECT id FROM ref_units WHERE civ_name=?", (civ_name,))
    unit_ids = [row["id"] for row in rc.fetchall()]
    ref_conn.close()

    conn = get_db()
    cursor = conn.cursor()
    for uid in unit_ids:
        cursor.execute("DELETE FROM unit_verifications WHERE ref_unit_id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/simulation-comments", methods=["POST"])
def save_simulation_comment():
    """Save a comment for a simulation."""
    data = request.get_json()

    required_fields = [
        "team1_civ",
        "team1_unit",
        "team1_count",
        "team2_civ",
        "team2_unit",
        "team2_count",
        "comment",
    ]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO simulation_comments
        (team1_civ, team1_unit, team1_count, team2_civ, team2_unit, team2_count, winner, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            data["team1_civ"],
            data["team1_unit"],
            data["team1_count"],
            data["team2_civ"],
            data["team2_unit"],
            data["team2_count"],
            data.get("winner"),
            data["comment"],
        ),
    )
    conn.commit()
    comment_id = cursor.lastrowid
    conn.close()

    return jsonify({"success": True, "id": comment_id})


@app.route("/api/simulation-comments", methods=["GET"])
def get_simulation_comments():
    """Get all simulation comments."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, team1_civ, team1_unit, team1_count, team2_civ, team2_unit, team2_count,
               winner, comment, created_at
        FROM simulation_comments
        ORDER BY created_at DESC
    """
    )
    comments = [
        {
            "id": row["id"],
            "team1_civ": row["team1_civ"],
            "team1_unit": row["team1_unit"],
            "team1_count": row["team1_count"],
            "team2_civ": row["team2_civ"],
            "team2_unit": row["team2_unit"],
            "team2_count": row["team2_count"],
            "winner": row["winner"],
            "comment": row["comment"],
            "created_at": row["created_at"],
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    return jsonify(comments)


@app.route("/api/simulation-comments/<int:comment_id>", methods=["DELETE"])
def delete_simulation_comment(comment_id):
    """Delete a simulation comment."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM simulation_comments WHERE id = ?", (comment_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return jsonify({"success": deleted})


@app.route("/simulation-notes")
def simulation_notes():
    """Page to review all simulation comments."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM civilizations ORDER BY name")
    civs = [row["name"] for row in cursor.fetchall()]
    conn.close()

    return render_template("simulation_notes.html", civs=civs)


# ============== Civ Matchup ==============


def _get_ref_civs():
    """Get list of civilizations from the reference DB."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute("SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name")
    civs = [row["civ_name"] for row in rc.fetchall()]
    ref_conn.close()
    return civs


# ============== Matchup Advisor ==============

_MOBILE_SPEED_THRESHOLD = 1.3
_SIEGE_CLASSES = {"Siege Weapon", "Ballista", "Unpacked Siege Unit"}
_ADVISOR_EXCLUDED = {"trebuchet", "ram", "siege_ram"}
VOTES_FILE = os.path.join(os.path.dirname(__file__), "matchup_votes.jsonl")


def _categorize_units(units_dict):
    """Split {slug: combat_unit} into strategic groups.
    A unit can appear in multiple categories."""
    mobile = {}
    ranged_gold = {}
    siege = {}
    for slug, cu in units_dict.items():
        cls = cu.get("_unit_class_name", "")
        speed = cu["movement_speed"]
        rng = cu["attack_range"]
        gold = cu["cost_gold"]

        if speed > _MOBILE_SPEED_THRESHOLD:
            mobile[slug] = cu
        if rng > 1.0 and gold > 0 and cls not in _SIEGE_CLASSES:
            ranged_gold[slug] = cu
        if cls in _SIEGE_CLASSES:
            siege[slug] = cu

    return {
        "mobile": mobile,
        "ranged_gold": ranged_gold,
        "siege": siege,
        "all": units_dict,
    }


def _unit_dps(u):
    """Estimate effective DPS for tiebreaking."""
    attack = u.get("attack", 0)
    accuracy = u.get("accuracy", 100) / 100.0
    attack_speed = u.get("attack_speed", 0.5)
    reload_time = 1.0 / attack_speed if attack_speed > 0 else 2.0
    return attack * accuracy / reload_time


def _run_pair(u1, u2, calc_cost, is_imperial, cache=None):
    """Run 30v30 + 3000-resource sim. Returns (winner, score1, score2).
    3 pts for winning both, 1 each for split, 0 for losing both.
    On split, higher DPS unit gets 2 pts vs 1.
    cache: optional dict keyed by (slug1, slug2) to avoid re-running same pair."""
    # Use object id to distinguish same-slug units from different civs
    key1 = id(u1)
    key2 = id(u2)
    if cache is not None:
        key = (key1, key2)
        if key in cache:
            return cache[key]

    c1 = calc_cost(u1)
    c2 = calc_cost(u2)
    w_res, _, _ = simulate_battle(u1, u2, 3000, cost1_override=c1, cost2_override=c2)
    w_cnt, _, _ = simulate_battle(u1, u2, 0, fixed_count=30)

    u1_won_both = w_res == 1 and w_cnt == 1
    u2_won_both = w_res == 2 and w_cnt == 2

    if u1_won_both and not u2_won_both:
        result = (1, 3, 0)
    elif u2_won_both and not u1_won_both:
        result = (2, 0, 3)
    else:
        dps1 = _unit_dps(u1)
        dps2 = _unit_dps(u2)
        if dps1 > dps2:
            result = (1, 2, 1)
        elif dps2 > dps1:
            result = (2, 1, 2)
        else:
            result = (0, 1, 1)

    if cache is not None:
        cache[key] = result
    return result


def _find_clear_winner_and_scores(
    my_units, opp_units, calc_cost, is_imperial, cache=None
):
    """Run all pairs between my_units and opp_units.
    Returns (clear_winner_slug_or_None, best_slug, scores_dict, grid).
    A clear winner wins or draws ALL opponents."""
    scores = {}
    grid = []
    for my_slug, my_cu in my_units.items():
        total_score = 0
        all_win_or_draw = True
        for opp_slug, opp_cu in opp_units.items():
            winner, s1, s2 = _run_pair(
                my_cu, opp_cu, calc_cost, is_imperial, cache=cache
            )
            total_score += s1
            if winner == 2:
                all_win_or_draw = False
            grid.append(
                {
                    "my_slug": my_slug,
                    "opp_slug": opp_slug,
                    "winner": winner,
                    "s1": s1,
                    "s2": s2,
                }
            )
        scores[my_slug] = {
            "total_score": total_score,
            "all_win_or_draw": all_win_or_draw,
        }

    # Find clear winner (wins/draws all)
    clear = None
    best_slug = None
    best_score = -1
    for slug, s in scores.items():
        if s["total_score"] > best_score:
            best_score = s["total_score"]
            best_slug = slug
        if s["all_win_or_draw"] and s["total_score"] > (
            scores.get(clear, {}).get("total_score", -1) if clear else -1
        ):
            clear = slug

    return clear, best_slug, scores, grid


def _find_best_counter(
    counter_pool, target_units, calc_cost, is_imperial, exclude=None, cache=None
):
    """Find the unit from counter_pool that scores best against target_units.
    Returns (best_slug, best_score)."""
    best_slug = None
    best_score = -1
    for slug, cu in counter_pool.items():
        if exclude and slug in exclude:
            continue
        total = 0
        for _, opp_cu in target_units.items():
            _, s1, _ = _run_pair(cu, opp_cu, calc_cost, is_imperial, cache=cache)
            total += s1
        if total > best_score:
            best_score = total
            best_slug = slug
    return best_slug, best_score


def _build_combos_for_civ(
    civ_cats,
    opp_cats,
    is_mobile_dominant,
    dominant_slug,
    ranged_slug,
    calc_cost,
    is_imperial,
    civ_units,
    has_clear_ranged_advantage=False,
    cache=None,
):
    """Build up to 4 combo options for a civ. Each combo = (primary, secondary, reasoning)."""
    combos = []
    used = set()
    all_units = civ_cats["all"]
    mobile = civ_cats["mobile"]
    ranged_gold = civ_cats["ranged_gold"]
    siege = civ_cats["siege"]
    opp_mobile = opp_cats["mobile"]

    def _is_ranged(slug):
        cu = all_units.get(slug)
        return cu and cu["attack_range"] > 1.0

    def _add(primary_slug, secondary_slug, reasoning):
        key = tuple(sorted([primary_slug, secondary_slug]))
        if key in used or primary_slug == secondary_slug:
            return False
        if primary_slug not in all_units or secondary_slug not in all_units:
            return False
        # Enforce: max one ranged unit per combo (ranged+melee or melee+melee)
        if _is_ranged(primary_slug) and _is_ranged(secondary_slug):
            return False
        used.add(key)
        combos.append(
            {
                "primary": primary_slug,
                "secondary": secondary_slug,
                "reasoning": reasoning,
            }
        )
        return True

    # Helper: find units already used as primary in combos so far
    def _used_primaries():
        return {c["primary"] for c in combos}

    if is_mobile_dominant and dominant_slug:
        dom = dominant_slug

        if has_clear_ranged_advantage and ranged_slug and ranged_slug != dom:
            # Dominant civ wins BOTH mobile and ranged: pair them
            _add(dom, ranged_slug, "Best mobile + best ranged")

            # Alt: dominant + 2nd-best ranged (vary the ranged unit)
            second_ranged, _ = _find_best_counter(
                ranged_gold,
                opp_cats["all"],
                calc_cost,
                is_imperial,
                exclude={dom, ranged_slug},
                cache=cache,
            )
            if second_ranged:
                _add(dom, second_ranged, "Best mobile + alt ranged")

            # Alt: different mobile + best ranged (vary primary)
            second_mobile = None
            best_score = -1
            for s, cu in mobile.items():
                if s == dom:
                    continue
                total = (
                    sum(
                        _run_pair(cu, opp, calc_cost, is_imperial, cache=cache)[1]
                        for _, opp in opp_mobile.items()
                    )
                    if opp_mobile
                    else 0
                )
                if total > best_score:
                    best_score = total
                    second_mobile = s
            if second_mobile:
                _add(second_mobile, ranged_slug, "Alt mobile + best ranged")

            # Alt: dominant + best melee support
            melee_support, _ = _find_best_counter(
                {
                    s: cu
                    for s, cu in all_units.items()
                    if cu["attack_range"] <= 1.0 and s != dom
                },
                opp_cats["all"],
                calc_cost,
                is_imperial,
                exclude={dom, ranged_slug},
                cache=cache,
            )
            if melee_support:
                _add(dom, melee_support, "Best mobile + melee support")
        else:
            # Dominant civ: mobile dominant but ranged contested
            # Combo 1: dominant + best support
            support, _ = _find_best_counter(
                all_units,
                opp_cats["all"],
                calc_cost,
                is_imperial,
                exclude={dom},
                cache=cache,
            )
            if support:
                _add(dom, support, "Best mobile + best support")

            # Combo 2: dominant + best ranged/siege support
            ranged_support, _ = _find_best_counter(
                {**ranged_gold, **siege},
                opp_cats["all"],
                calc_cost,
                is_imperial,
                exclude={dom},
                cache=cache,
            )
            if ranged_support:
                _add(dom, ranged_support, "Best mobile + ranged/siege support")

            # Combo 3: different mobile + support (vary primary)
            second_mobile = None
            best_score = -1
            for s, cu in mobile.items():
                if s == dom:
                    continue
                total = (
                    sum(
                        _run_pair(cu, opp, calc_cost, is_imperial, cache=cache)[1]
                        for _, opp in opp_mobile.items()
                    )
                    if opp_mobile
                    else 0
                )
                if total > best_score:
                    best_score = total
                    second_mobile = s
            if second_mobile and support:
                _add(second_mobile, support, "Alt mobile + best support")

            # Combo 4: dominant + trash
            trash, _ = _find_best_counter(
                {s: cu for s, cu in all_units.items() if cu["cost_gold"] == 0},
                opp_mobile if opp_mobile else opp_cats["all"],
                calc_cost,
                is_imperial,
                exclude={dom},
                cache=cache,
            )
            if trash:
                _add(dom, trash, "Best mobile + trash (eco-friendly)")

    else:
        # Weaker/non-dominant mobile civ
        melee_units = {
            s: cu for s, cu in all_units.items() if cu["attack_range"] <= 1.0
        }
        ranged_or_siege = {
            s: cu
            for s, cu in all_units.items()
            if cu["attack_range"] > 1.0
            or cu.get("_unit_class_name", "") in _SIEGE_CLASSES
        }

        if has_clear_ranged_advantage and ranged_slug and opp_mobile:
            # Path A: Has ranged advantage — lead with ranged unit
            trash_counter, _ = _find_best_counter(
                {s: cu for s, cu in melee_units.items() if cu["cost_gold"] == 0},
                opp_mobile,
                calc_cost,
                is_imperial,
                exclude={ranged_slug},
                cache=cache,
            )
            if trash_counter:
                _add(ranged_slug, trash_counter, "Ranged advantage + trash counter")

            gold_counter, _ = _find_best_counter(
                {s: cu for s, cu in melee_units.items() if cu["cost_gold"] > 0},
                opp_mobile,
                calc_cost,
                is_imperial,
                exclude={ranged_slug},
                cache=cache,
            )
            if gold_counter:
                _add(ranged_slug, gold_counter, "Ranged advantage + gold counter")

            # Alt: melee lead + ranged support (vary primary)
            best_melee, _ = _find_best_counter(
                melee_units,
                opp_cats["all"],
                calc_cost,
                is_imperial,
                cache=cache,
            )
            if best_melee:
                _add(best_melee, ranged_slug, "Best melee + ranged advantage")
        else:
            # Path B: No ranged advantage (opponent dominates both, or contested)
            # Lead with best melee, pair with siege/ranged support
            best_melee, _ = _find_best_counter(
                melee_units,
                opp_cats["all"],
                calc_cost,
                is_imperial,
                cache=cache,
            )
            if best_melee:
                best_support, _ = _find_best_counter(
                    ranged_or_siege,
                    opp_cats["all"],
                    calc_cost,
                    is_imperial,
                    exclude={best_melee},
                    cache=cache,
                )
                if best_support:
                    _add(best_melee, best_support, "Best melee + ranged/siege support")

                # Alt: best melee + siege specifically
                siege_sup, _ = _find_best_counter(
                    siege,
                    opp_cats["all"],
                    calc_cost,
                    is_imperial,
                    exclude={best_melee},
                    cache=cache,
                )
                if siege_sup:
                    _add(best_melee, siege_sup, "Best melee + siege support")

                # Alt: different melee + support (vary primary)
                second_melee, _ = _find_best_counter(
                    melee_units,
                    opp_cats["all"],
                    calc_cost,
                    is_imperial,
                    exclude={best_melee},
                    cache=cache,
                )
                if second_melee and best_support:
                    _add(second_melee, best_support, "Alt melee + ranged/siege support")

                # Alt: best melee + ranged specifically
                ranged_sup, _ = _find_best_counter(
                    ranged_gold,
                    opp_cats["all"],
                    calc_cost,
                    is_imperial,
                    exclude={best_melee},
                    cache=cache,
                )
                if ranged_sup:
                    _add(best_melee, ranged_sup, "Best melee + ranged support")

    # Fill remaining slots: pick top-scoring unit pairs with varied primaries
    if len(combos) < 4 and all_units:
        already_primary = _used_primaries()
        sorted_units = sorted(
            all_units.keys(),
            key=lambda s: sum(
                _run_pair(all_units[s], opp, calc_cost, is_imperial, cache=cache)[1]
                for _, opp in opp_cats["all"].items()
            ),
            reverse=True,
        )
        for s1 in sorted_units:
            if len(combos) >= 4:
                break
            # Prefer units not yet used as primary
            for s2 in sorted_units:
                if len(combos) >= 4:
                    break
                if s1 == s2:
                    continue
                # Prefer new primary over repeated primary
                if s1 in already_primary:
                    continue
                _add(s1, s2, "Top scoring units")
        # If still under 4, allow repeated primaries
        for s1 in sorted_units:
            if len(combos) >= 4:
                break
            for s2 in sorted_units:
                if len(combos) >= 4:
                    break
                if s1 == s2:
                    continue
                _add(s1, s2, "Top scoring units")

    return combos[:4]


def _run_army_sims(
    combos1,
    combos2,
    civ1_units,
    civ2_units,
    calc_cost,
    is_imperial,
    total_resources=5000,
):
    """Run mixed army sims for all combo pairs with various splits.
    Returns combo_grid with results."""
    SPLITS = [0.7, 0.6, 0.5, 0.4, 0.3]
    combo_grid = []

    for c1_idx, c1 in enumerate(combos1):
        u1a = civ1_units[c1["primary"]]
        u1b = civ1_units[c1["secondary"]]
        cost1a = calc_cost(u1a)
        cost1b = calc_cost(u1b)

        for c2_idx, c2 in enumerate(combos2):
            u2a = civ2_units[c2["primary"]]
            u2b = civ2_units[c2["secondary"]]
            cost2a = calc_cost(u2a)
            cost2b = calc_cost(u2b)

            best_result = None
            best_margin = -999

            for s1 in SPLITS:
                res1a = total_resources * s1
                res1b = total_resources * (1 - s1)
                cnt1a = max(1, int(res1a // cost1a))
                cnt1b = max(1, int(res1b // cost1b))

                for s2 in SPLITS:
                    res2a = total_resources * s2
                    res2b = total_resources * (1 - s2)
                    cnt2a = max(1, int(res2a // cost2a))
                    cnt2b = max(1, int(res2b // cost2b))

                    w, _, _, hp1, hp2 = simulate_mixed_battle(
                        [(u1a, cnt1a), (u1b, cnt1b)],
                        [(u2a, cnt2a), (u2b, cnt2b)],
                        return_hp=True,
                    )
                    margin = hp1 - hp2
                    if margin > best_margin:
                        best_margin = margin
                        best_result = {
                            "civ1_combo_id": c1_idx,
                            "civ2_combo_id": c2_idx,
                            "winner": "civ1"
                            if w == 1
                            else ("civ2" if w == 2 else "draw"),
                            "margin": round(best_margin, 3),
                            "best_split_civ1": [s1, round(1 - s1, 1)],
                            "best_split_civ2": [s2, round(1 - s2, 1)],
                            "counts_civ1": [cnt1a, cnt1b],
                            "counts_civ2": [cnt2a, cnt2b],
                        }

            if best_result:
                combo_grid.append(best_result)

    return combo_grid


@app.route("/matchup-advisor")
def matchup_advisor():
    """Matchup Advisor page."""
    civs = _get_ref_civs()
    return render_template("matchup_advisor.html", civs=civs)


def _run_matchup_analysis(civ1, civ2):
    """Run phases 1-3 of matchup analysis. Returns (results_by_age, raw_data) or raises ValueError."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    for civ in (civ1, civ2):
        rc.execute("SELECT DISTINCT civ_name FROM ref_units WHERE civ_name=?", (civ,))
        if not rc.fetchone():
            ref_conn.close()
            raise ValueError(f"Civilization '{civ}' not found")

    MATCHUP_AGES = {"imperial": AGES["imperial"], "castle": AGES["castle"]}
    results = {}
    raw_data = {}  # store internals for phase 4 reuse

    for age_slug, age_data in MATCHUP_AGES.items():
        db_age = "Castle" if age_slug == "castle" else "Imperial"
        is_imperial = age_slug == "imperial"

        def fetch_advisor_units(civ_name):
            rc.execute(
                "SELECT * FROM ref_units WHERE civ_name=? AND age=?",
                (civ_name, db_age),
            )
            units = {}
            for row in rc.fetchall():
                slug = row["unit_slug"]
                if slug in _ADVISOR_EXCLUDED:
                    continue
                combat_dict = _build_combat_dict_from_ref(rc, row)
                cu = prepare_combat_unit(combat_dict)
                cu["_display_name"] = row["unit_name"]
                cu["_slug"] = slug
                cu["_unit_type"] = row["unit_type"]
                cu["_unit_class_name"] = row["unit_class_name"] or ""
                units[slug] = cu
            return units

        civ1_units = fetch_advisor_units(civ1)
        civ2_units = fetch_advisor_units(civ2)

        if not civ1_units or not civ2_units:
            results[age_slug] = {
                "age_name": age_data["name"],
                "error": "No units found",
            }
            continue

        def calc_cost(unit):
            food = unit["cost_food"]
            wood = unit["cost_wood"]
            gold = unit["cost_gold"]
            if is_imperial:
                cost = wood + food + gold
            else:
                cost = wood + 1.5 * food + gold
            return int(cost) if cost > 0 else 100

        civ1_cats = _categorize_units(civ1_units)
        civ2_cats = _categorize_units(civ2_units)

        # Per-age simulation cache: avoids re-running same unit pair
        pair_cache = {}

        # --- Phase 1: Mobile Dominance ---
        c1_mobile = civ1_cats["mobile"]
        c2_mobile = civ2_cats["mobile"]

        phase1 = {
            "civ1_units": [],
            "civ2_units": [],
            "dominant_civ": None,
            "dominant_unit": None,
            "grid": [],
        }

        c1_clear, c1_best_mob, c1_mob_scores, c1_grid = None, None, {}, []
        c2_clear, c2_best_mob, c2_mob_scores, c2_grid = None, None, {}, []

        if c1_mobile and c2_mobile:
            c1_clear, c1_best_mob, c1_mob_scores, c1_grid = (
                _find_clear_winner_and_scores(
                    c1_mobile, c2_mobile, calc_cost, is_imperial, cache=pair_cache
                )
            )
            c2_clear, c2_best_mob, c2_mob_scores, c2_grid = (
                _find_clear_winner_and_scores(
                    c2_mobile, c1_mobile, calc_cost, is_imperial, cache=pair_cache
                )
            )

            if c1_clear and not c2_clear:
                phase1["dominant_civ"] = "civ1"
                phase1["dominant_unit"] = {
                    "slug": c1_clear,
                    "name": civ1_units[c1_clear]["_display_name"],
                }
            elif c2_clear and not c1_clear:
                phase1["dominant_civ"] = "civ2"
                phase1["dominant_unit"] = {
                    "slug": c2_clear,
                    "name": civ2_units[c2_clear]["_display_name"],
                }
            else:
                c1_total = sum(s["total_score"] for s in c1_mob_scores.values())
                c2_total = sum(s["total_score"] for s in c2_mob_scores.values())
                if c1_total > c2_total:
                    phase1["dominant_civ"] = "civ1"
                    phase1["dominant_unit"] = {
                        "slug": c1_best_mob,
                        "name": civ1_units[c1_best_mob]["_display_name"],
                    }
                elif c2_total > c1_total:
                    phase1["dominant_civ"] = "civ2"
                    phase1["dominant_unit"] = {
                        "slug": c2_best_mob,
                        "name": civ2_units[c2_best_mob]["_display_name"],
                    }
                else:
                    phase1["dominant_civ"] = "civ1"
                    phase1["dominant_unit"] = {
                        "slug": c1_best_mob,
                        "name": civ1_units[c1_best_mob]["_display_name"],
                    }

            phase1["civ1_units"] = [
                {
                    "slug": s,
                    "name": civ1_units[s]["_display_name"],
                    "speed": civ1_units[s]["movement_speed"],
                    "total_score": c1_mob_scores.get(s, {}).get("total_score", 0),
                }
                for s in c1_mobile
            ]
            phase1["civ2_units"] = [
                {
                    "slug": s,
                    "name": civ2_units[s]["_display_name"],
                    "speed": civ2_units[s]["movement_speed"],
                    "total_score": c2_mob_scores.get(s, {}).get("total_score", 0),
                }
                for s in c2_mobile
            ]
            phase1["grid"] = c1_grid

        elif c1_mobile and not c2_mobile:
            phase1["dominant_civ"] = "civ1"
            best = max(c1_mobile.keys(), key=lambda s: c1_mobile[s]["movement_speed"])
            phase1["dominant_unit"] = {
                "slug": best,
                "name": civ1_units[best]["_display_name"],
            }
            phase1["civ1_units"] = [
                {
                    "slug": s,
                    "name": civ1_units[s]["_display_name"],
                    "speed": civ1_units[s]["movement_speed"],
                    "total_score": 0,
                }
                for s in c1_mobile
            ]
        elif c2_mobile and not c1_mobile:
            phase1["dominant_civ"] = "civ2"
            best = max(c2_mobile.keys(), key=lambda s: c2_mobile[s]["movement_speed"])
            phase1["dominant_unit"] = {
                "slug": best,
                "name": civ2_units[best]["_display_name"],
            }
            phase1["civ2_units"] = [
                {
                    "slug": s,
                    "name": civ2_units[s]["_display_name"],
                    "speed": civ2_units[s]["movement_speed"],
                    "total_score": 0,
                }
                for s in c2_mobile
            ]

        # --- Phase 2: Ranged Advantage (both civs) ---
        c1_ranged = civ1_cats["ranged_gold"]
        c2_ranged = civ2_cats["ranged_gold"]

        # Find each civ's best ranged unit against the other's ranged
        c1_best_ranged_slug = None
        c2_best_ranged_slug = None
        c1_ranged_clear = False
        c2_ranged_clear = False
        ranged_grid = []

        if c1_ranged and c2_ranged:
            r1_clear, r1_best, _, r1_grid = _find_clear_winner_and_scores(
                c1_ranged, c2_ranged, calc_cost, is_imperial, cache=pair_cache
            )
            r2_clear, r2_best, _, _ = _find_clear_winner_and_scores(
                c2_ranged, c1_ranged, calc_cost, is_imperial, cache=pair_cache
            )
            ranged_grid = r1_grid
            c1_best_ranged_slug = r1_clear or r1_best
            c2_best_ranged_slug = r2_clear or r2_best
            c1_ranged_clear = bool(r1_clear)
            c2_ranged_clear = bool(r2_clear)
        elif c1_ranged:
            c1_best_ranged_slug = max(
                c1_ranged, key=lambda s: c1_ranged[s].get("attack", 0)
            )
            c1_ranged_clear = True
        elif c2_ranged:
            c2_best_ranged_slug = max(
                c2_ranged, key=lambda s: c2_ranged[s].get("attack", 0)
            )
            c2_ranged_clear = True

        # Determine overall ranged winner
        if c1_ranged_clear and not c2_ranged_clear:
            ranged_winner = "civ1"
        elif c2_ranged_clear and not c1_ranged_clear:
            ranged_winner = "civ2"
        else:
            ranged_winner = None  # contested or no ranged

        phase2 = {
            "civ1_best_ranged": {
                "slug": c1_best_ranged_slug,
                "name": civ1_units[c1_best_ranged_slug]["_display_name"],
                "clear": c1_ranged_clear,
            }
            if c1_best_ranged_slug
            else None,
            "civ2_best_ranged": {
                "slug": c2_best_ranged_slug,
                "name": civ2_units[c2_best_ranged_slug]["_display_name"],
                "clear": c2_ranged_clear,
            }
            if c2_best_ranged_slug
            else None,
            "ranged_winner": ranged_winner,
            "grid": ranged_grid,
        }

        # --- Best melee per civ ---
        melee1 = {s: cu for s, cu in civ1_units.items() if cu["attack_range"] <= 1.0}
        melee2 = {s: cu for s, cu in civ2_units.items() if cu["attack_range"] <= 1.0}
        best_melee1_slug, _ = (
            _find_best_counter(
                melee1, civ2_cats["all"], calc_cost, is_imperial, cache=pair_cache
            )
            if melee1
            else (None, 0)
        )
        best_melee2_slug, _ = (
            _find_best_counter(
                melee2, civ1_cats["all"], calc_cost, is_imperial, cache=pair_cache
            )
            if melee2
            else (None, 0)
        )

        # --- Best mobile per civ ---
        best_mob1 = (
            c1_best_mob
            if c1_best_mob
            else (
                max(c1_mobile.keys(), key=lambda s: c1_mobile[s]["movement_speed"])
                if c1_mobile
                else None
            )
        )
        best_mob2 = (
            c2_best_mob
            if c2_best_mob
            else (
                max(c2_mobile.keys(), key=lambda s: c2_mobile[s]["movement_speed"])
                if c2_mobile
                else None
            )
        )

        # --- Phase 3: Build Combos ---
        dominant_slug = (
            phase1["dominant_unit"]["slug"] if phase1["dominant_unit"] else None
        )
        dom_civ = phase1["dominant_civ"]

        # Determine ranged slugs per civ
        c1_ranged_slug = c1_best_ranged_slug
        c2_ranged_slug = c2_best_ranged_slug

        # Does the mobile-dominant civ also win ranged?
        dom_also_ranged = dom_civ and ranged_winner == dom_civ

        if dom_civ == "civ1":
            c1_combos = _build_combos_for_civ(
                civ1_cats,
                civ2_cats,
                True,
                dominant_slug,
                c1_ranged_slug,
                calc_cost,
                is_imperial,
                civ1_units,
                has_clear_ranged_advantage=dom_also_ranged,
                cache=pair_cache,
            )
            # Weaker civ: if opponent dominates both, no ranged advantage
            weaker_has_ranged = ranged_winner == "civ2"
            c2_combos = _build_combos_for_civ(
                civ2_cats,
                civ1_cats,
                False,
                None,
                c2_ranged_slug if weaker_has_ranged else None,
                calc_cost,
                is_imperial,
                civ2_units,
                has_clear_ranged_advantage=weaker_has_ranged,
                cache=pair_cache,
            )
        else:
            c2_combos = _build_combos_for_civ(
                civ2_cats,
                civ1_cats,
                True,
                dominant_slug,
                c2_ranged_slug,
                calc_cost,
                is_imperial,
                civ2_units,
                has_clear_ranged_advantage=dom_also_ranged,
                cache=pair_cache,
            )
            weaker_has_ranged = ranged_winner == "civ1"
            c1_combos = _build_combos_for_civ(
                civ1_cats,
                civ2_cats,
                False,
                None,
                c1_ranged_slug if weaker_has_ranged else None,
                calc_cost,
                is_imperial,
                civ1_units,
                has_clear_ranged_advantage=weaker_has_ranged,
                cache=pair_cache,
            )

        def _format_combos(combo_list, units_dict):
            out = []
            for i, c in enumerate(combo_list):
                out.append(
                    {
                        "id": i,
                        "primary": {
                            "slug": c["primary"],
                            "name": units_dict[c["primary"]]["_display_name"],
                        },
                        "secondary": {
                            "slug": c["secondary"],
                            "name": units_dict[c["secondary"]]["_display_name"],
                        },
                        "reasoning": c["reasoning"],
                        "is_recommended": i == 0,
                        "army_score": 0,
                        "best_split": [0.5, 0.5],
                    }
                )
            return out

        phase3_civ1 = _format_combos(c1_combos, civ1_units)
        phase3_civ2 = _format_combos(c2_combos, civ2_units)

        results[age_slug] = {
            "age_name": age_data["name"],
            "phase1_mobile": phase1,
            "phase2_ranged": phase2,
            "best_mobile": {
                "civ1": {
                    "slug": best_mob1,
                    "name": civ1_units[best_mob1]["_display_name"],
                    "speed": civ1_units[best_mob1]["movement_speed"],
                }
                if best_mob1
                else None,
                "civ2": {
                    "slug": best_mob2,
                    "name": civ2_units[best_mob2]["_display_name"],
                    "speed": civ2_units[best_mob2]["movement_speed"],
                }
                if best_mob2
                else None,
            },
            "best_melee": {
                "civ1": {
                    "slug": best_melee1_slug,
                    "name": civ1_units[best_melee1_slug]["_display_name"],
                }
                if best_melee1_slug
                else None,
                "civ2": {
                    "slug": best_melee2_slug,
                    "name": civ2_units[best_melee2_slug]["_display_name"],
                }
                if best_melee2_slug
                else None,
            },
            "phase3_combos": {
                "civ1": phase3_civ1,
                "civ2": phase3_civ2,
            },
        }

        # Store raw data for phase 4
        raw_data[age_slug] = {
            "c1_combos": c1_combos,
            "c2_combos": c2_combos,
            "civ1_units": civ1_units,
            "civ2_units": civ2_units,
            "calc_cost": calc_cost,
            "is_imperial": is_imperial,
        }

    ref_conn.close()
    return results, raw_data


@app.route("/api/matchup-advisor/analysis/<civ1>/<civ2>")
def api_matchup_advisor_analysis(civ1, civ2):
    """Fast endpoint: phases 1-3 of matchup analysis."""
    if civ1 == civ2:
        return jsonify({"error": "Please select two different civilizations"}), 400
    try:
        results, _ = _run_matchup_analysis(civ1, civ2)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    return jsonify({"civ1": civ1, "civ2": civ2, "ages": results})


@app.route("/api/matchup-advisor/army/<civ1>/<civ2>")
def api_matchup_advisor_army(civ1, civ2):
    """Slow endpoint: phase 4 army simulations with counter analysis."""
    if civ1 == civ2:
        return jsonify({"error": "Please select two different civilizations"}), 400
    try:
        results, raw_data = _run_matchup_analysis(civ1, civ2)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    army_results = {}
    for age_slug, age_data in results.items():
        if "error" in age_data:
            army_results[age_slug] = {"error": age_data["error"]}
            continue

        rd = raw_data[age_slug]
        c1_combos = rd["c1_combos"]
        c2_combos = rd["c2_combos"]
        civ1_units = rd["civ1_units"]
        civ2_units = rd["civ2_units"]
        calc_cost = rd["calc_cost"]
        is_imperial = rd["is_imperial"]

        combo_grid = []
        if c1_combos and c2_combos:
            combo_grid = _run_army_sims(
                c1_combos, c2_combos, civ1_units, civ2_units, calc_cost, is_imperial
            )

        # Format combos for reference
        phase3_civ1 = age_data["phase3_combos"]["civ1"]
        phase3_civ2 = age_data["phase3_combos"]["civ2"]

        # Update army scores
        for entry in combo_grid:
            c1_id = entry["civ1_combo_id"]
            c2_id = entry["civ2_combo_id"]
            margin = entry["margin"]
            if c1_id < len(phase3_civ1):
                if margin > phase3_civ1[c1_id]["army_score"]:
                    phase3_civ1[c1_id]["army_score"] = round(margin, 3)
                    phase3_civ1[c1_id]["best_split"] = entry["best_split_civ1"]
            if c2_id < len(phase3_civ2):
                neg_margin = -margin
                if neg_margin > phase3_civ2[c2_id]["army_score"]:
                    phase3_civ2[c2_id]["army_score"] = round(neg_margin, 3)
                    phase3_civ2[c2_id]["best_split"] = entry["best_split_civ2"]

        # Find best combo per civ and what counters it
        best_c1 = {"combo_id": 0, "wins": 0, "losses": 0, "draws": 0}
        best_c2 = {"combo_id": 0, "wins": 0, "losses": 0, "draws": 0}

        # Tally wins per combo
        c1_combo_wins = {}
        c2_combo_wins = {}
        for entry in combo_grid:
            c1_id = entry["civ1_combo_id"]
            c2_id = entry["civ2_combo_id"]
            if c1_id not in c1_combo_wins:
                c1_combo_wins[c1_id] = {"wins": 0, "losses": 0, "draws": 0}
            if c2_id not in c2_combo_wins:
                c2_combo_wins[c2_id] = {"wins": 0, "losses": 0, "draws": 0}
            if entry["winner"] == "civ1":
                c1_combo_wins[c1_id]["wins"] += 1
                c2_combo_wins[c2_id]["losses"] += 1
            elif entry["winner"] == "civ2":
                c1_combo_wins[c1_id]["losses"] += 1
                c2_combo_wins[c2_id]["wins"] += 1
            else:
                c1_combo_wins[c1_id]["draws"] += 1
                c2_combo_wins[c2_id]["draws"] += 1

        # Best combo = most wins
        if c1_combo_wins:
            best_c1_id = max(c1_combo_wins, key=lambda k: c1_combo_wins[k]["wins"])
            best_c1 = {"combo_id": best_c1_id, **c1_combo_wins[best_c1_id]}
        if c2_combo_wins:
            best_c2_id = max(c2_combo_wins, key=lambda k: c2_combo_wins[k]["wins"])
            best_c2 = {"combo_id": best_c2_id, **c2_combo_wins[best_c2_id]}

        # Counter analysis: for civ1's best combo, find civ2 combo that beats it most
        c1_countered_by = None
        c2_countered_by = None
        if combo_grid:
            # Find best civ2 combo vs civ1's best
            best_c1_id = best_c1["combo_id"]
            worst_margin_for_c1 = 999
            for entry in combo_grid:
                if (
                    entry["civ1_combo_id"] == best_c1_id
                    and entry["margin"] < worst_margin_for_c1
                ):
                    worst_margin_for_c1 = entry["margin"]
                    if entry["winner"] == "civ2" and entry["civ2_combo_id"] < len(
                        phase3_civ2
                    ):
                        c2_combo = phase3_civ2[entry["civ2_combo_id"]]
                        c1_countered_by = {
                            "combo_id": entry["civ2_combo_id"],
                            "primary": c2_combo["primary"]["name"],
                            "secondary": c2_combo["secondary"]["name"],
                        }

            # Find best civ1 combo vs civ2's best
            best_c2_id = best_c2["combo_id"]
            best_margin_for_c1 = -999
            for entry in combo_grid:
                if (
                    entry["civ2_combo_id"] == best_c2_id
                    and entry["margin"] > best_margin_for_c1
                ):
                    best_margin_for_c1 = entry["margin"]
                    if entry["winner"] == "civ1" and entry["civ1_combo_id"] < len(
                        phase3_civ1
                    ):
                        c1_combo = phase3_civ1[entry["civ1_combo_id"]]
                        c2_countered_by = {
                            "combo_id": entry["civ1_combo_id"],
                            "primary": c1_combo["primary"]["name"],
                            "secondary": c1_combo["secondary"]["name"],
                        }

        army_results[age_slug] = {
            "combo_grid": combo_grid,
            "combos": {
                "civ1": phase3_civ1,
                "civ2": phase3_civ2,
            },
            "best_combo": {"civ1": best_c1, "civ2": best_c2},
            "counters": {
                "civ1_countered_by": c1_countered_by,
                "civ2_countered_by": c2_countered_by,
            },
        }

    return jsonify({"civ1": civ1, "civ2": civ2, "ages": army_results})


@app.route("/api/matchup-advisor/<civ1>/<civ2>")
def api_matchup_advisor(civ1, civ2):
    """Legacy endpoint: all 4 phases at once."""
    if civ1 == civ2:
        return jsonify({"error": "Please select two different civilizations"}), 400
    try:
        results, raw_data = _run_matchup_analysis(civ1, civ2)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    for age_slug, age_data in results.items():
        if "error" in age_data:
            age_data["phase4_army"] = {"combo_grid": []}
            continue

        rd = raw_data[age_slug]
        combo_grid = []
        if rd["c1_combos"] and rd["c2_combos"]:
            combo_grid = _run_army_sims(
                rd["c1_combos"],
                rd["c2_combos"],
                rd["civ1_units"],
                rd["civ2_units"],
                rd["calc_cost"],
                rd["is_imperial"],
            )
            for entry in combo_grid:
                c1_id = entry["civ1_combo_id"]
                c2_id = entry["civ2_combo_id"]
                margin = entry["margin"]
                p3c1 = age_data["phase3_combos"]["civ1"]
                p3c2 = age_data["phase3_combos"]["civ2"]
                if c1_id < len(p3c1) and margin > p3c1[c1_id]["army_score"]:
                    p3c1[c1_id]["army_score"] = round(margin, 3)
                    p3c1[c1_id]["best_split"] = entry["best_split_civ1"]
                if c2_id < len(p3c2):
                    neg = -margin
                    if neg > p3c2[c2_id]["army_score"]:
                        p3c2[c2_id]["army_score"] = round(neg, 3)
                        p3c2[c2_id]["best_split"] = entry["best_split_civ2"]
        age_data["phase4_army"] = {"combo_grid": combo_grid}

    return jsonify({"civ1": civ1, "civ2": civ2, "ages": results})


@app.route("/api/matchup-advisor/vote", methods=["POST"])
def api_matchup_advisor_vote():
    """Record user's combo selection for later analysis."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    vote = {
        "civ1": data.get("civ1"),
        "civ2": data.get("civ2"),
        "age": data.get("age"),
        "selected_for": data.get("selected_for"),
        "selection_type": data.get("selection_type", "preset"),
        "combo_id": data.get("combo_id"),
        "combo_primary": data.get("combo_primary"),
        "combo_secondary": data.get("combo_secondary"),
        "recommended_combo_id": data.get("recommended_combo_id"),
        "recommended_primary": data.get("recommended_primary"),
        "recommended_secondary": data.get("recommended_secondary"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with open(VOTES_FILE, "a") as f:
            f.write(json.dumps(vote) + "\n")
    except OSError:
        return jsonify({"error": "Failed to record vote"}), 500

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
