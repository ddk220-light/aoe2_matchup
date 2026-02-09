import json
import os
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache

from flask import Flask, jsonify, redirect, render_template, request
from simulation import prepare_combat_unit, simulate_battle, simulate_mixed_battle

app = Flask(__name__)

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
            us.hp_regen, us.hp_transform_threshold
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
    "Britons",
    "Byzantines",
    "Celts",
    "Chinese",
    "Franks",
    "Goths",
    "Japanese",
    "Mongols",
    "Persians",
    "Saracens",
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
        # Defaults for properties not in ref DB (not needed for original 13)
        "ignores_pierce_armor": 0,
        "ignores_melee_armor": 0,
        "bonus_damage_reduction": 0,
        "splash_on_hit_radius": 0,
        "dodge_shield_max": 0,
        "dodge_shield_recharge": 0,
        "bleed_dps": 0,
        "bleed_duration": 0,
        "block_first_melee": 0,
        "attack_bonus_per_kill": 0,
        "first_attack_extra_projectiles": 0,
        "hp_regen": special.get("hp_regen", 0),
        "hp_transform_threshold": 0,
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
        "unique_units": {},
    },
    "archer": {
        "name": "Archer Line",
        "building": "Archery Range",
        "castle_slug": "crossbow",
        "imperial_slug": "arbalester",
        "unique_units": {
            "Britons": ("longbowman_britons", "elite_longbowman_britons"),
            "Chinese": ("chu_ko_nu_chinese", "elite_chu_ko_nu_chinese"),
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
        },
    },
    "hand_cannoneer": {
        "name": "Hand Cannoneer",
        "building": "Archery Range",
        "castle_slug": None,
        "imperial_slug": "hand_cannoneer",
        "unique_units": {
            "Turks": ("janissary_turks", "elite_janissary_turks"),
            "Franks": ("throwing_axeman_franks", "elite_throwing_axeman_franks"),
        },
    },
    "knight": {
        "name": "Knight Line",
        "building": "Stable",
        "castle_slug": "knight",
        "imperial_slug": "paladin",
        "unique_units": {
            "Byzantines": ("cataphract_byzantines", "elite_cataphract_byzantines"),
        },
    },
    "light_cav": {
        "name": "Light Cavalry Line",
        "building": "Stable",
        "castle_slug": "light_cav",
        "imperial_slug": "hussar",
        "unique_units": {},
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

    # Fetch standard units for each age
    for age_key, slug_key, db_age in [
        ("castle", "castle_slug", "Castle"),
        ("imperial", "imperial_slug", "Imperial"),
    ]:
        slug = line[slug_key]
        if not slug:
            continue
        rc.execute(
            f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
            (slug, db_age),
        )
        for row in rc.fetchall():
            entry = dict(row)
            entry["is_unique"] = False
            _attach_scores(entry, age_key)
            result[age_key].append(entry)

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


# ============== 1v1 Civ Matchup ==============

# Units to exclude from matchup simulations
_MATCHUP_EXCLUDED = {"trebuchet", "ram", "siege_ram"}


def _get_ref_civs():
    """Get list of civilizations from the reference DB."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute("SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name")
    civs = [row["civ_name"] for row in rc.fetchall()]
    ref_conn.close()
    return civs


@app.route("/matchup")
def matchup():
    """1v1 Civilization matchup page."""
    civs = _get_ref_civs()
    ages = {k: v["name"] for k, v in AGES.items()}
    return render_template("matchup.html", civs=civs, ages=ages)


@app.route("/api/matchup/<civ1>/<civ2>")
def api_matchup(civ1, civ2):
    """
    Calculate best unit recommendations for a 1v1 matchup between two civs.
    Uses the reference DB and the same simulation engine as unit rankings.
    """
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Verify both civs exist
    rc.execute("SELECT DISTINCT civ_name FROM ref_units WHERE civ_name=?", (civ1,))
    if not rc.fetchone():
        ref_conn.close()
        return jsonify({"error": f"Civilization '{civ1}' not found"}), 404
    rc.execute("SELECT DISTINCT civ_name FROM ref_units WHERE civ_name=?", (civ2,))
    if not rc.fetchone():
        ref_conn.close()
        return jsonify({"error": f"Civilization '{civ2}' not found"}), 404

    # Only compare Castle and Imperial ages
    MATCHUP_AGES = {k: v for k, v in AGES.items() if k != "feudal"}
    results = {}

    for age_slug, age_data in MATCHUP_AGES.items():
        db_age = "Castle" if age_slug == "castle" else "Imperial"
        is_imperial = age_slug == "imperial"

        # Fetch all units for each civ in this age
        def fetch_civ_units(civ_name):
            rc.execute(
                "SELECT * FROM ref_units WHERE civ_name=? AND age=?",
                (civ_name, db_age),
            )
            units = {}
            for row in rc.fetchall():
                slug = row["unit_slug"]
                if slug in _MATCHUP_EXCLUDED:
                    continue
                combat_dict = _build_combat_dict_from_ref(rc, row)
                cu = prepare_combat_unit(combat_dict)
                cu["_display_name"] = row["unit_name"]
                cu["_slug"] = slug
                cu["_unit_type"] = row["unit_type"]
                units[slug] = cu
            return units

        civ1_units = fetch_civ_units(civ1)
        civ2_units = fetch_civ_units(civ2)

        if not civ1_units or not civ2_units:
            results[age_slug] = {
                "age_name": age_data["name"],
                "civ1_best": None,
                "civ2_best": None,
                "civ1_all": [],
                "civ2_all": [],
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

        # Round-robin: every civ1 unit vs every civ2 unit
        civ1_scores = {}
        civ2_scores = {}
        all_matchups = []

        civ1_list = list(civ1_units.values())
        civ2_list = list(civ2_units.values())

        for u1 in civ1_list:
            u1_slug = u1["_slug"]
            u1_wins = 0
            u1_total = 0

            for u2 in civ2_list:
                u2_slug = u2["_slug"]

                c1 = calc_cost(u1)
                c2 = calc_cost(u2)

                # Resource-based (3000) and count-based (30v30)
                w_res, _, _ = simulate_battle(
                    u1, u2, 3000, cost1_override=c1, cost2_override=c2
                )
                w_cnt, _, _ = simulate_battle(u1, u2, 0, fixed_count=30)

                u1_won_both = w_res == 1 and w_cnt == 1
                u2_won_both = w_res == 2 and w_cnt == 2
                u1_won_any = w_res == 1 or w_cnt == 1
                u2_won_any = w_res == 2 or w_cnt == 2

                # Scoring: 3 for winning both, 0 for losing both, 1 each otherwise
                if u1_won_both and not u2_won_both:
                    winner = 1
                    u1_add, u2_add = 3, 0
                elif u2_won_both and not u1_won_both:
                    winner = 2
                    u1_add, u2_add = 0, 3
                else:
                    winner = 0
                    u1_add, u2_add = 1, 1

                u1_total += 1
                if winner == 1:
                    u1_wins += 1

                if u2_slug not in civ2_scores:
                    civ2_scores[u2_slug] = {"wins": 0, "total": 0, "unit": u2}
                civ2_scores[u2_slug]["total"] += 1
                if winner == 2:
                    civ2_scores[u2_slug]["wins"] += 1

                all_matchups.append(
                    {
                        "civ1_slug": u1_slug,
                        "civ1_unit": u1["_display_name"],
                        "civ2_slug": u2_slug,
                        "civ2_unit": u2["_display_name"],
                        "winner": winner,
                        "u1_score": u1_add,
                        "u2_score": u2_add,
                    }
                )

            civ1_scores[u1_slug] = {"wins": u1_wins, "total": u1_total, "unit": u1}

        # Build matchup details for tooltips
        civ1_details = {}
        civ2_details = {}
        for m in all_matchups:
            c1r = (
                "win" if m["winner"] == 1 else ("loss" if m["winner"] == 2 else "draw")
            )
            c2r = (
                "win" if m["winner"] == 2 else ("loss" if m["winner"] == 1 else "draw")
            )
            civ1_details.setdefault(m["civ1_slug"], []).append(
                {
                    "opponent": m["civ2_unit"],
                    "opponent_slug": m["civ2_slug"],
                    "result": c1r,
                    "score": m["u1_score"],
                }
            )
            civ2_details.setdefault(m["civ2_slug"], []).append(
                {
                    "opponent": m["civ1_unit"],
                    "opponent_slug": m["civ1_slug"],
                    "result": c2r,
                    "score": m["u2_score"],
                }
            )

        # Calculate final scores (sum of points)
        for key, s in civ1_scores.items():
            s["win_rate"] = s["wins"] / s["total"] if s["total"] > 0 else 0
            s["score"] = sum(d["score"] for d in civ1_details.get(key, []))
        for key, s in civ2_scores.items():
            s["win_rate"] = s["wins"] / s["total"] if s["total"] > 0 else 0
            s["score"] = sum(d["score"] for d in civ2_details.get(key, []))

        # Find best unit for each civ
        civ1_best = (
            max(civ1_scores.items(), key=lambda x: x[1]["score"])
            if civ1_scores
            else None
        )
        civ2_best = (
            max(civ2_scores.items(), key=lambda x: x[1]["score"])
            if civ2_scores
            else None
        )

        # Find which units beat the opponent's best
        civ1_beats_best = set()
        civ2_beats_best = set()
        if civ1_best and civ2_best:
            for m in all_matchups:
                if m["civ2_slug"] == civ2_best[0] and m["winner"] == 1:
                    civ1_beats_best.add(m["civ1_slug"])
                if m["civ1_slug"] == civ1_best[0] and m["winner"] == 2:
                    civ2_beats_best.add(m["civ2_slug"])

        def format_unit(slug, data, beats_best, details):
            d = details.get(slug, [])
            wins_list = [x for x in d if x["result"] == "win"]
            draws_list = [x for x in d if x["result"] == "draw"]
            losses_list = [x for x in d if x["result"] == "loss"]
            return {
                "slug": slug,
                "name": data["unit"]["_display_name"],
                "score": data["score"],
                "wins": data["wins"],
                "total": data["total"],
                "win_rate": round(data["win_rate"] * 100, 1),
                "beats_opponent_best": slug in beats_best,
                "matchups": {
                    "wins": [x["opponent"] for x in wins_list],
                    "draws": [x["opponent"] for x in draws_list],
                    "losses": [x["opponent"] for x in losses_list],
                },
            }

        results[age_slug] = {
            "age_name": age_data["name"],
            "civ1_best": format_unit(
                civ1_best[0], civ1_best[1], civ1_beats_best, civ1_details
            )
            if civ1_best
            else None,
            "civ2_best": format_unit(
                civ2_best[0], civ2_best[1], civ2_beats_best, civ2_details
            )
            if civ2_best
            else None,
            "civ1_all": [
                format_unit(k, v, civ1_beats_best, civ1_details)
                for k, v in sorted(civ1_scores.items(), key=lambda x: -x[1]["score"])
            ],
            "civ2_all": [
                format_unit(k, v, civ2_beats_best, civ2_details)
                for k, v in sorted(civ2_scores.items(), key=lambda x: -x[1]["score"])
            ],
        }

    ref_conn.close()
    return jsonify({"civ1": civ1, "civ2": civ2, "ages": results})


# ============== Matchup Advisor ==============

_MOBILE_SPEED_THRESHOLD = 1.4
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
        if rng >= 1.0 and gold > 0 and cls not in _SIEGE_CLASSES:
            ranged_gold[slug] = cu
        if cls in _SIEGE_CLASSES:
            siege[slug] = cu

    return {
        "mobile": mobile,
        "ranged_gold": ranged_gold,
        "siege": siege,
        "all": units_dict,
    }


def _run_pair(u1, u2, calc_cost, is_imperial):
    """Run 30v30 + 3000-resource sim. Returns (winner, score1, score2).
    3 pts for winning both, 1 each for split, 0 for losing both."""
    c1 = calc_cost(u1)
    c2 = calc_cost(u2)
    w_res, _, _ = simulate_battle(u1, u2, 3000, cost1_override=c1, cost2_override=c2)
    w_cnt, _, _ = simulate_battle(u1, u2, 0, fixed_count=30)

    u1_won_both = w_res == 1 and w_cnt == 1
    u2_won_both = w_res == 2 and w_cnt == 2

    if u1_won_both and not u2_won_both:
        return (1, 3, 0)
    elif u2_won_both and not u1_won_both:
        return (2, 0, 3)
    else:
        return (0, 1, 1)


def _find_clear_winner_and_scores(my_units, opp_units, calc_cost, is_imperial):
    """Run all pairs between my_units and opp_units.
    Returns (clear_winner_slug_or_None, scores_dict, grid).
    A clear winner wins or draws ALL opponents."""
    scores = {}
    grid = []
    for my_slug, my_cu in my_units.items():
        total_score = 0
        all_win_or_draw = True
        for opp_slug, opp_cu in opp_units.items():
            winner, s1, s2 = _run_pair(my_cu, opp_cu, calc_cost, is_imperial)
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
    counter_pool, target_units, calc_cost, is_imperial, exclude=None
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
            _, s1, _ = _run_pair(cu, opp_cu, calc_cost, is_imperial)
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
):
    """Build up to 4 combo options for a civ. Each combo = (primary, secondary, reasoning)."""
    combos = []
    used = set()
    all_units = civ_cats["all"]
    mobile = civ_cats["mobile"]
    ranged_gold = civ_cats["ranged_gold"]
    siege = civ_cats["siege"]
    opp_mobile = opp_cats["mobile"]

    def _add(primary_slug, secondary_slug, reasoning):
        key = (primary_slug, secondary_slug)
        if key in used or primary_slug == secondary_slug:
            return False
        if primary_slug not in all_units or secondary_slug not in all_units:
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

    if is_mobile_dominant and dominant_slug:
        # Mobile dominant civ: pair dominant unit with support
        dom = dominant_slug
        # Combo 1: dominant + best support vs opponent's counter to dominant
        support, _ = _find_best_counter(
            all_units, opp_cats["all"], calc_cost, is_imperial, exclude={dom}
        )
        if support:
            _add(dom, support, f"Dominant mobile + best support")

        # Combo 2: dominant + best ranged support
        ranged_support, _ = _find_best_counter(
            ranged_gold, opp_cats["all"], calc_cost, is_imperial, exclude={dom}
        )
        if ranged_support:
            _add(dom, ranged_support, f"Dominant mobile + ranged support")

        # Combo 3: second-best mobile + best support
        second_mobile = None
        best_score = -1
        for s, cu in mobile.items():
            if s == dom:
                continue
            total = 0
            for _, opp in opp_mobile.items():
                _, s1, _ = _run_pair(cu, opp, calc_cost, is_imperial)
                total += s1
            if total > best_score:
                best_score = total
                second_mobile = s
        if second_mobile and support:
            _add(second_mobile, support, f"Alt mobile + best support")

        # Combo 4: dominant + trash (no gold cost)
        trash, _ = _find_best_counter(
            {s: cu for s, cu in all_units.items() if cu["cost_gold"] == 0},
            opp_mobile if opp_mobile else opp_cats["all"],
            calc_cost,
            is_imperial,
            exclude={dom},
        )
        if trash:
            _add(dom, trash, f"Dominant mobile + trash (eco-friendly)")

    else:
        # Weaker mobile civ: lead with ranged, support with counter
        rng = ranged_slug
        if rng and opp_mobile:
            # Combo 1: ranged + best trash counter to opponent's mobile
            trash_counter, _ = _find_best_counter(
                {s: cu for s, cu in all_units.items() if cu["cost_gold"] == 0},
                opp_mobile,
                calc_cost,
                is_imperial,
                exclude={rng} if rng else set(),
            )
            if trash_counter:
                _add(rng, trash_counter, f"Ranged advantage + trash counter")

            # Combo 2: ranged + best gold counter
            gold_counter, _ = _find_best_counter(
                {s: cu for s, cu in all_units.items() if cu["cost_gold"] > 0},
                opp_mobile,
                calc_cost,
                is_imperial,
                exclude={rng} if rng else set(),
            )
            if gold_counter:
                _add(rng, gold_counter, f"Ranged advantage + gold counter")

        # Combo 3: best ranged (may differ) + best counter
        if ranged_gold:
            alt_ranged = max(
                ranged_gold.keys(),
                key=lambda s: sum(
                    _run_pair(ranged_gold[s], opp, calc_cost, is_imperial)[1]
                    for _, opp in opp_cats["all"].items()
                ),
                default=None,
            )
            if alt_ranged:
                counter, _ = _find_best_counter(
                    all_units,
                    opp_mobile if opp_mobile else opp_cats["all"],
                    calc_cost,
                    is_imperial,
                    exclude={alt_ranged},
                )
                if counter:
                    _add(alt_ranged, counter, f"Best ranged + counter")

        # Combo 4: best siege + counter
        if siege:
            best_siege = max(
                siege.keys(), key=lambda s: siege[s].get("attack", 0), default=None
            )
            if best_siege:
                counter, _ = _find_best_counter(
                    all_units,
                    opp_mobile if opp_mobile else opp_cats["all"],
                    calc_cost,
                    is_imperial,
                    exclude={best_siege},
                )
                if counter:
                    _add(best_siege, counter, f"Siege + counter")

    # Fill remaining slots with fallback combos
    if len(combos) < 4 and all_units:
        sorted_units = sorted(
            all_units.keys(),
            key=lambda s: sum(
                _run_pair(all_units[s], opp, calc_cost, is_imperial)[1]
                for _, opp in opp_cats["all"].items()
            ),
            reverse=True,
        )
        for i, s1 in enumerate(sorted_units[:3]):
            for s2 in sorted_units[i + 1 :]:
                if len(combos) >= 4:
                    break
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


@app.route("/api/matchup-advisor/<civ1>/<civ2>")
def api_matchup_advisor(civ1, civ2):
    """Strategic army composition analysis for two civs."""
    if civ1 == civ2:
        return jsonify({"error": "Please select two different civilizations"}), 400

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Verify civs
    for civ in (civ1, civ2):
        rc.execute("SELECT DISTINCT civ_name FROM ref_units WHERE civ_name=?", (civ,))
        if not rc.fetchone():
            ref_conn.close()
            return jsonify({"error": f"Civilization '{civ}' not found"}), 404

    MATCHUP_AGES = {"castle": AGES["castle"], "imperial": AGES["imperial"]}
    results = {}

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
                    c1_mobile, c2_mobile, calc_cost, is_imperial
                )
            )
            c2_clear, c2_best_mob, c2_mob_scores, c2_grid = (
                _find_clear_winner_and_scores(
                    c2_mobile, c1_mobile, calc_cost, is_imperial
                )
            )

            # Determine dominant civ
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
                # Compare aggregate scores
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
            # Merge grids (c1 attacking c2)
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

        # --- Phase 2: Ranged Advantage (for weaker mobile civ) ---
        weaker_civ = "civ2" if phase1["dominant_civ"] == "civ1" else "civ1"
        phase2 = {
            "analyzed_for": weaker_civ,
            "advantage_unit": None,
            "has_clear_advantage": False,
            "grid": [],
        }

        weaker_ranged = (
            civ1_cats["ranged_gold"]
            if weaker_civ == "civ1"
            else civ2_cats["ranged_gold"]
        )
        dom_ranged = (
            civ2_cats["ranged_gold"]
            if weaker_civ == "civ1"
            else civ1_cats["ranged_gold"]
        )

        ranged_advantage_slug = None
        if weaker_ranged and dom_ranged:
            r_clear, r_best, r_scores, r_grid = _find_clear_winner_and_scores(
                weaker_ranged, dom_ranged, calc_cost, is_imperial
            )
            phase2["grid"] = r_grid
            if r_clear:
                phase2["has_clear_advantage"] = True
                ranged_advantage_slug = r_clear
            else:
                ranged_advantage_slug = r_best
            weaker_units = civ1_units if weaker_civ == "civ1" else civ2_units
            if ranged_advantage_slug and ranged_advantage_slug in weaker_units:
                phase2["advantage_unit"] = {
                    "slug": ranged_advantage_slug,
                    "name": weaker_units[ranged_advantage_slug]["_display_name"],
                }
        elif weaker_ranged:
            ranged_advantage_slug = max(
                weaker_ranged.keys(),
                key=lambda s: weaker_ranged[s].get("attack", 0),
                default=None,
            )
            weaker_units = civ1_units if weaker_civ == "civ1" else civ2_units
            if ranged_advantage_slug:
                phase2["advantage_unit"] = {
                    "slug": ranged_advantage_slug,
                    "name": weaker_units[ranged_advantage_slug]["_display_name"],
                }

        # --- Phase 3: Build Combos ---
        dominant_slug = (
            phase1["dominant_unit"]["slug"] if phase1["dominant_unit"] else None
        )

        # Determine which civ is dominant and weaker
        if phase1["dominant_civ"] == "civ1":
            c1_combos = _build_combos_for_civ(
                civ1_cats,
                civ2_cats,
                True,
                dominant_slug,
                None,
                calc_cost,
                is_imperial,
                civ1_units,
            )
            c2_combos = _build_combos_for_civ(
                civ2_cats,
                civ1_cats,
                False,
                None,
                ranged_advantage_slug,
                calc_cost,
                is_imperial,
                civ2_units,
            )
        else:
            c1_combos = _build_combos_for_civ(
                civ1_cats,
                civ2_cats,
                False,
                None,
                ranged_advantage_slug,
                calc_cost,
                is_imperial,
                civ1_units,
            )
            c2_combos = _build_combos_for_civ(
                civ2_cats,
                civ1_cats,
                True,
                dominant_slug,
                None,
                calc_cost,
                is_imperial,
                civ2_units,
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

        # --- Phase 4: Army Combo Simulation ---
        combo_grid = []
        if c1_combos and c2_combos:
            combo_grid = _run_army_sims(
                c1_combos, c2_combos, civ1_units, civ2_units, calc_cost, is_imperial
            )

            # Update army scores on combos: best margin for each combo across all opponents
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

        results[age_slug] = {
            "age_name": age_data["name"],
            "phase1_mobile": phase1,
            "phase2_ranged": phase2,
            "phase3_combos": {
                "civ1": phase3_civ1,
                "civ2": phase3_civ2,
            },
            "phase4_army": {
                "combo_grid": combo_grid,
            },
        }

    # Build all_units list for custom combo dropdowns
    all_units_out = {"civ1": [], "civ2": []}
    for age_slug in ("castle", "imperial"):
        db_age = "Castle" if age_slug == "castle" else "Imperial"
        for civ_key, civ_name in (("civ1", civ1), ("civ2", civ2)):
            rc.execute(
                "SELECT unit_slug, unit_name FROM ref_units WHERE civ_name=? AND age=? ORDER BY unit_name",
                (civ_name, db_age),
            )
            for row in rc.fetchall():
                if row["unit_slug"] not in _ADVISOR_EXCLUDED:
                    all_units_out[civ_key].append(
                        {
                            "slug": row["unit_slug"],
                            "name": row["unit_name"],
                            "age": age_slug,
                        }
                    )

    ref_conn.close()
    return jsonify(
        {
            "civ1": civ1,
            "civ2": civ2,
            "all_units": all_units_out,
            "ages": results,
        }
    )


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
