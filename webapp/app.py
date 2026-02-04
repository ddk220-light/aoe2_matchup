import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, render_template, request

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
            us.unit_name, c.name as civ_name
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

    return jsonify(
        {
            "id": row["id"],
            "name": row["unit_name"],
            "civ": row["civ_name"],
            "hp": row["hp"],
            "attack": row["attack"],
            "attack_range": row["attack_range"] or 0,
            "attack_speed": row["attack_speed"],
            "melee_armor": row["melee_armor"],
            "pierce_armor": row["pierce_armor"],
            "movement_speed": row["movement_speed"],
            "attacks_json": row["attacks_json"],
            "armors_json": row["armors_json"],
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
