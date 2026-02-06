import json
import os
import sqlite3
from datetime import datetime
from functools import lru_cache

from flask import Flask, jsonify, render_template, request
from simulation import prepare_combat_unit, simulate_battle

app = Flask(__name__)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_units.db")

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
def index():
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
    """Page to view units by civilization."""
    civs = get_all_civs()
    return render_template("civ_view.html", civs=civs)


# ============== Battle Simulation ==============


@app.route("/simulate")
def simulate():
    """Battle simulation page."""
    units_by_age = get_units_by_age()
    civs = get_all_civs()
    return render_template("simulate.html", units_by_age=units_by_age, civs=civs)


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
            us.hp_transform_threshold
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


@app.route("/matchup")
def matchup():
    """1v1 Civilization matchup page."""
    civs = get_all_civs()
    ages = {k: v["name"] for k, v in AGES.items()}
    return render_template("matchup.html", civs=civs, ages=ages)


@app.route("/api/matchup/<civ1>/<civ2>")
def api_matchup(civ1, civ2):
    """
    Calculate best unit recommendations for a 1v1 matchup between two civs.

    For each age, finds the best unit for each civ based on which unit wins
    the most matchups against all of the opponent's units.
    Uses data-driven simulation — no hardcoded slug lookups.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Verify both civs exist
    cursor.execute("SELECT id FROM civilizations WHERE name = ?", (civ1,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"error": f"Civilization '{civ1}' not found"}), 404

    cursor.execute("SELECT id FROM civilizations WHERE name = ?", (civ2,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"error": f"Civilization '{civ2}' not found"}), 404

    results = {}

    # Units to exclude from simulations (low accuracy units)
    EXCLUDED_UNITS = {"trebuchet", "packed-trebuchet", "ram", "siege_ram"}

    # Only compare Castle and Imperial ages
    MATCHUP_AGES = {k: v for k, v in AGES.items() if k != "feudal"}

    MATCHUP_QUERY = """
        SELECT u.slug, us.unit_name, us.hp, us.attack, us.attack_speed,
               us.attack_range, us.attack_delay, us.movement_speed,
               us.melee_armor, us.pierce_armor, us.attacks_json, us.armors_json,
               us.cost_food, us.cost_wood, us.cost_gold,
               us.min_attack_range, us.is_siege_projectile, us.splash_radius,
               us.projectile_speed, us.ignores_pierce_armor, us.ignores_melee_armor,
               us.trample_percent, us.trample_radius, us.trample_flat_damage,
               us.bonus_damage_reduction, us.unit_category, us.paired_unit_slug,
               us.extra_projectiles, us.extra_projectile_attacks_json,
               us.splash_on_hit_radius,
               us.dodge_shield_max, us.dodge_shield_recharge,
               us.bleed_dps, us.bleed_duration, us.block_first_melee,
               us.attack_bonus_per_kill, us.first_attack_extra_projectiles,
               us.hp_transform_threshold,
               us.transform_hp, us.transform_attack, us.transform_melee_armor,
               us.transform_pierce_armor, us.transform_attack_speed,
               us.transform_attack_delay, us.transform_movement_speed,
               us.transform_attacks_json, us.transform_armors_json,
               us.dismount_hp, us.dismount_attack, us.dismount_melee_armor,
               us.dismount_pierce_armor, us.dismount_attack_speed,
               us.dismount_attack_delay, us.dismount_movement_speed,
               us.dismount_attacks_json, us.dismount_armors_json
        FROM unit_stats us
        JOIN units u ON us.unit_id = u.id
        JOIN civilizations c ON us.civ_id = c.id
        WHERE c.name = ? AND u.age_id = ? AND us.has_unit = 1
    """

    for age_slug, age_data in MATCHUP_AGES.items():
        age_id = age_data["id"]

        cursor.execute(MATCHUP_QUERY, (civ1, age_id))
        civ1_rows = [u for u in cursor.fetchall() if u["slug"] not in EXCLUDED_UNITS]

        cursor.execute(MATCHUP_QUERY, (civ2, age_id))
        civ2_rows = [u for u in cursor.fetchall() if u["slug"] not in EXCLUDED_UNITS]

        if not civ1_rows or not civ2_rows:
            results[age_slug] = {
                "age_name": age_data["name"],
                "civ1_best": None,
                "civ2_best": None,
                "matchups": [],
            }
            continue

        # Pre-parse all units ONCE (not per simulation)
        civ1_units = {u["slug"]: prepare_combat_unit(u) for u in civ1_rows}
        civ2_units = {u["slug"]: prepare_combat_unit(u) for u in civ2_rows}

        # Resource cost formula varies by age
        is_imperial = age_slug == "imperial"

        def calc_resource_cost(unit):
            food = unit["cost_food"]
            wood = unit["cost_wood"]
            gold = unit["cost_gold"]
            if is_imperial:
                # Imperial: 1x wood, 1x food, 1x gold
                cost = wood + food + gold
            else:
                # Castle: 1x wood, 1.5x food, 1x gold
                cost = wood + 1.5 * food + gold
            return int(cost) if cost > 0 else 100

        # Filter: remove paired duplicates (keep one mode per pair)
        def filter_paired_units(units_dict):
            seen_pairs = set()
            filtered = []
            for slug, u in units_dict.items():
                paired = u.get("paired_unit_slug")
                if paired:
                    pair_key = tuple(sorted([slug, paired]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        filtered.append(u)
                else:
                    filtered.append(u)
            return filtered

        def get_display_name_for_paired(unit):
            """Return a clean display name for paired units (e.g., 'Ratha')."""
            if unit.get("paired_unit_slug"):
                name = unit["unit_name"]
                # Strip mode suffix like " (Melee)" or " (Ranged)"
                for suffix in [" (Melee)", " (Ranged)"]:
                    name = name.replace(suffix, "")
                # Strip "Elite " prefix check is not needed — keep as is
                return name
            return None

        # Filter units: remove paired duplicates and trash/siege (using DB category)
        civ1_filtered = [
            u
            for u in filter_paired_units(civ1_units)
            if u["unit_category"] == "military"
        ]
        civ2_filtered = [
            u
            for u in filter_paired_units(civ2_units)
            if u["unit_category"] == "military"
        ]

        civ1_scores = {}
        civ2_scores = {}
        all_matchups = []

        for u1 in civ1_filtered:
            u1_wins = 0
            u1_total = 0

            # Get all modes for u1 (for paired units like Ratha)
            u1_modes = [u1]
            u1_paired_slug = u1.get("paired_unit_slug")
            if u1_paired_slug and u1_paired_slug in civ1_units:
                u1_modes.append(civ1_units[u1_paired_slug])

            for u2 in civ2_filtered:
                u2_modes = [u2]
                u2_paired_slug = u2.get("paired_unit_slug")
                if u2_paired_slug and u2_paired_slug in civ2_units:
                    u2_modes.append(civ2_units[u2_paired_slug])

                u1_won_both_any = False
                u2_won_both_any = False
                u1_won_any = False
                u2_won_any = False

                for u1_mode in u1_modes:
                    for u2_mode in u2_modes:
                        # Run two simulations: resource-based and count-based
                        c1 = calc_resource_cost(u1_mode)
                        c2 = calc_resource_cost(u2_mode)
                        winner_res, _, _ = simulate_battle(
                            u1_mode, u2_mode, 3000, cost1_override=c1, cost2_override=c2
                        )
                        winner_cnt, _, _ = simulate_battle(
                            u1_mode, u2_mode, 0, fixed_count=30
                        )

                        if winner_res == 1 and winner_cnt == 1:
                            u1_won_both_any = True
                        if winner_res == 2 and winner_cnt == 2:
                            u2_won_both_any = True
                        if winner_res == 1 or winner_cnt == 1:
                            u1_won_any = True
                        if winner_res == 2 or winner_cnt == 2:
                            u2_won_any = True

                # Scoring
                if u1_won_both_any and not u2_won_both_any:
                    winner = 1
                    u1_score_add, u2_score_add = 3, 0
                elif u2_won_both_any and not u1_won_both_any:
                    winner = 2
                    u1_score_add, u2_score_add = 0, 3
                elif u1_won_both_any and u2_won_both_any:
                    winner = 0
                    u1_score_add, u2_score_add = 1, 1
                elif u1_won_any and u2_won_any:
                    winner = 0
                    u1_score_add, u2_score_add = 1, 1
                else:
                    winner = 0
                    u1_score_add, u2_score_add = 1, 1

                u1_total += 1
                if winner == 1:
                    u1_wins += 1

                u2_key = u2["slug"]
                if u2_key not in civ2_scores:
                    civ2_scores[u2_key] = {
                        "wins": 0,
                        "total": 0,
                        "unit": u2,
                        "display_name": get_display_name_for_paired(u2),
                    }
                civ2_scores[u2_key]["total"] += 1
                if winner == 2:
                    civ2_scores[u2_key]["wins"] += 1

                u1_display = get_display_name_for_paired(u1) or u1["unit_name"]
                u2_display = get_display_name_for_paired(u2) or u2["unit_name"]

                all_matchups.append(
                    {
                        "civ1_unit": u1_display,
                        "civ1_slug": u1["slug"],
                        "civ2_unit": u2_display,
                        "civ2_slug": u2["slug"],
                        "winner": winner,
                        "u1_score": u1_score_add,
                        "u2_score": u2_score_add,
                    }
                )

            civ1_scores[u1["slug"]] = {
                "wins": u1_wins,
                "total": u1_total,
                "unit": u1,
                "display_name": get_display_name_for_paired(u1),
            }

        # Build matchup details
        civ1_matchup_details = {}
        civ2_matchup_details = {}
        for m in all_matchups:
            if m["winner"] == 1:
                c1r, c2r = "win", "loss"
            elif m["winner"] == 2:
                c1r, c2r = "loss", "win"
            else:
                c1r, c2r = "draw", "draw"

            civ1_matchup_details.setdefault(m["civ1_slug"], []).append(
                {
                    "opponent": m["civ2_unit"],
                    "opponent_slug": m["civ2_slug"],
                    "result": c1r,
                    "score": m["u1_score"],
                }
            )
            civ2_matchup_details.setdefault(m["civ2_slug"], []).append(
                {
                    "opponent": m["civ1_unit"],
                    "opponent_slug": m["civ1_slug"],
                    "result": c2r,
                    "score": m["u2_score"],
                }
            )

        # Calculate scores — only count points against military units (not trash/siege)
        for key in civ1_scores:
            s = civ1_scores[key]
            s["win_rate"] = s["wins"] / s["total"] if s["total"] > 0 else 0
            score = 0
            for matchup in civ1_matchup_details.get(key, []):
                opp = civ2_units.get(matchup["opponent_slug"])
                if opp and opp["unit_category"] == "military":
                    score += matchup["score"]
            s["score"] = score

        for key in civ2_scores:
            s = civ2_scores[key]
            s["win_rate"] = s["wins"] / s["total"] if s["total"] > 0 else 0
            score = 0
            for matchup in civ2_matchup_details.get(key, []):
                opp = civ1_units.get(matchup["opponent_slug"])
                if opp and opp["unit_category"] == "military":
                    score += matchup["score"]
            s["score"] = score

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

        def format_unit(slug, data, beats_opponent_best, matchup_details):
            details = matchup_details.get(slug, [])
            wins = [d for d in details if d["result"] == "win"]
            draws = [d for d in details if d["result"] == "draw"]
            losses = [d for d in details if d["result"] == "loss"]
            display_name = data.get("display_name") or data["unit"]["unit_name"]
            return {
                "slug": slug,
                "name": display_name,
                "score": data["score"],
                "wins": data["wins"],
                "total": data["total"],
                "win_rate": round(data["win_rate"] * 100, 1),
                "beats_opponent_best": slug in beats_opponent_best,
                "matchups": {
                    "wins": [d["opponent"] for d in wins],
                    "draws": [d["opponent"] for d in draws],
                    "losses": [d["opponent"] for d in losses],
                },
            }

        results[age_slug] = {
            "age_name": age_data["name"],
            "civ1_best": format_unit(
                civ1_best[0], civ1_best[1], civ1_beats_best, civ1_matchup_details
            )
            if civ1_best
            else None,
            "civ2_best": format_unit(
                civ2_best[0], civ2_best[1], civ2_beats_best, civ2_matchup_details
            )
            if civ2_best
            else None,
            "civ1_all": [
                format_unit(k, v, civ1_beats_best, civ1_matchup_details)
                for k, v in sorted(civ1_scores.items(), key=lambda x: -x[1]["score"])
            ],
            "civ2_all": [
                format_unit(k, v, civ2_beats_best, civ2_matchup_details)
                for k, v in sorted(civ2_scores.items(), key=lambda x: -x[1]["score"])
            ],
        }

    conn.close()
    return jsonify({"civ1": civ1, "civ2": civ2, "ages": results})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
