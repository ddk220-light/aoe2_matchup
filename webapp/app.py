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
            us.unit_name, c.name as civ_name,
            us.cost_food, us.cost_wood, us.cost_gold
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
            "hp": row["hp"],
            "attack": row["attack"],
            "attack_range": row["attack_range"] or 0,
            "attack_speed": row["attack_speed"],
            "melee_armor": row["melee_armor"],
            "pierce_armor": row["pierce_armor"],
            "movement_speed": row["movement_speed"],
            "attacks_json": row["attacks_json"],
            "armors_json": row["armors_json"],
            "cost_food": cost_food,
            "cost_wood": cost_wood,
            "cost_gold": cost_gold,
            "total_cost": total_cost,
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
    the most matchups against all of the opponent's units (using 1000 resources).
    """
    import json

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

    # Units to exclude from simulations (low accuracy units like Trebuchets)
    EXCLUDED_UNITS = {"trebuchet", "packed-trebuchet"}

    for age_slug, age_data in AGES.items():
        age_id = age_data["id"]

        # Get all units for civ1 in this age (excluding trebuchets)
        cursor.execute(
            """
            SELECT u.slug, us.unit_name, us.hp, us.attack, us.attack_speed,
                   us.attack_range, us.movement_speed,
                   us.melee_armor, us.pierce_armor, us.attacks_json, us.armors_json,
                   us.cost_food, us.cost_wood, us.cost_gold
            FROM unit_stats us
            JOIN units u ON us.unit_id = u.id
            JOIN civilizations c ON us.civ_id = c.id
            WHERE c.name = ? AND u.age_id = ? AND us.has_unit = 1
        """,
            (civ1, age_id),
        )
        civ1_units = [u for u in cursor.fetchall() if u["slug"] not in EXCLUDED_UNITS]

        # Get all units for civ2 in this age (excluding trebuchets)
        cursor.execute(
            """
            SELECT u.slug, us.unit_name, us.hp, us.attack, us.attack_speed,
                   us.attack_range, us.movement_speed,
                   us.melee_armor, us.pierce_armor, us.attacks_json, us.armors_json,
                   us.cost_food, us.cost_wood, us.cost_gold
            FROM unit_stats us
            JOIN units u ON us.unit_id = u.id
            JOIN civilizations c ON us.civ_id = c.id
            WHERE c.name = ? AND u.age_id = ? AND us.has_unit = 1
        """,
            (civ2, age_id),
        )
        civ2_units = [u for u in cursor.fetchall() if u["slug"] not in EXCLUDED_UNITS]

        if not civ1_units or not civ2_units:
            results[age_slug] = {
                "age_name": age_data["name"],
                "civ1_best": None,
                "civ2_best": None,
                "matchups": [],
            }
            continue

        # Calculate win rates for each civ1 unit against all civ2 units
        # Run TWO simulations: resource-based (1000 res) and count-based (30 units)
        civ1_scores = {}
        civ2_scores = {}
        all_matchups = []

        for u1 in civ1_units:
            u1_res_wins = 0
            u1_count_wins = 0
            u1_total = 0
            u1_cost = (
                (u1["cost_food"] or 0) + (u1["cost_wood"] or 0) + (u1["cost_gold"] or 0)
            )
            if u1_cost == 0:
                u1_cost = 100

            for u2 in civ2_units:
                u2_cost = (
                    (u2["cost_food"] or 0)
                    + (u2["cost_wood"] or 0)
                    + (u2["cost_gold"] or 0)
                )
                if u2_cost == 0:
                    u2_cost = 100

                # Simulation 1: Resource-based (1000 resources per team)
                res_winner, u1_res_remaining, u2_res_remaining = simulate_battle(
                    u1, u1_cost, u2, u2_cost, 1000
                )

                # Simulation 2: Count-based (30 units each, use unit cost * 30 as resources)
                count_resources = max(u1_cost, u2_cost) * 30
                count_winner, u1_count_remaining, u2_count_remaining = simulate_battle(
                    u1, u1_cost, u2, u2_cost, count_resources
                )

                u1_total += 1
                if res_winner == 1:
                    u1_res_wins += 1
                if count_winner == 1:
                    u1_count_wins += 1

                # Track for civ2 scoring
                u2_key = u2["slug"]
                if u2_key not in civ2_scores:
                    civ2_scores[u2_key] = {
                        "res_wins": 0,
                        "count_wins": 0,
                        "total": 0,
                        "unit": u2,
                    }
                civ2_scores[u2_key]["total"] += 1
                if res_winner == 2:
                    civ2_scores[u2_key]["res_wins"] += 1
                if count_winner == 2:
                    civ2_scores[u2_key]["count_wins"] += 1

                all_matchups.append(
                    {
                        "civ1_unit": u1["unit_name"],
                        "civ1_slug": u1["slug"],
                        "civ2_unit": u2["unit_name"],
                        "civ2_slug": u2["slug"],
                        "res_winner": res_winner,
                        "count_winner": count_winner,
                    }
                )

            civ1_scores[u1["slug"]] = {
                "res_wins": u1_res_wins,
                "count_wins": u1_count_wins,
                "total": u1_total,
                "unit": u1,
            }

        # Calculate scores for each unit
        # 3 points if win both resource and count, 1 point if win only one
        def calc_score(res_wins, count_wins, total):
            # For each matchup, determine points
            # We need to look at individual matchups, but we only have aggregates
            # So we approximate: if both win rates > 50%, likely winning both often
            if total == 0:
                return 0
            res_rate = res_wins / total
            count_rate = count_wins / total
            # Score = 3 * (wins in both) + 1 * (wins in one only)
            # Approximate: min of the two is "wins both", difference is "wins one"
            both_wins = min(res_wins, count_wins)
            only_res = res_wins - both_wins
            only_count = count_wins - both_wins
            return (both_wins * 3) + (only_res * 1) + (only_count * 1)

        for key in civ1_scores:
            s = civ1_scores[key]
            s["score"] = calc_score(s["res_wins"], s["count_wins"], s["total"])
            s["res_win_rate"] = s["res_wins"] / s["total"] if s["total"] > 0 else 0
            s["count_win_rate"] = s["count_wins"] / s["total"] if s["total"] > 0 else 0

        for key in civ2_scores:
            s = civ2_scores[key]
            s["score"] = calc_score(s["res_wins"], s["count_wins"], s["total"])
            s["res_win_rate"] = s["res_wins"] / s["total"] if s["total"] > 0 else 0
            s["count_win_rate"] = s["count_wins"] / s["total"] if s["total"] > 0 else 0

        # Find best unit for each civ (by score)
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

        # Find which civ1 units beat civ2's best unit (and vice versa)
        civ1_beats_best = set()
        civ2_beats_best = set()
        if civ1_best and civ2_best:
            civ2_best_slug = civ2_best[0]
            civ1_best_slug = civ1_best[0]
            for m in all_matchups:
                # Check if civ1 unit beats civ2's best
                if m["civ2_slug"] == civ2_best_slug:
                    if m["res_winner"] == 1 or m["count_winner"] == 1:
                        civ1_beats_best.add(m["civ1_slug"])
                # Check if civ2 unit beats civ1's best
                if m["civ1_slug"] == civ1_best_slug:
                    if m["res_winner"] == 2 or m["count_winner"] == 2:
                        civ2_beats_best.add(m["civ2_slug"])

        def format_unit(slug, data, beats_opponent_best):
            return {
                "slug": slug,
                "name": data["unit"]["unit_name"],
                "score": data["score"],
                "res_wins": data["res_wins"],
                "count_wins": data["count_wins"],
                "total": data["total"],
                "res_win_rate": round(data["res_win_rate"] * 100, 1),
                "count_win_rate": round(data["count_win_rate"] * 100, 1),
                "beats_opponent_best": slug in beats_opponent_best,
            }

        results[age_slug] = {
            "age_name": age_data["name"],
            "civ1_best": format_unit(civ1_best[0], civ1_best[1], civ1_beats_best)
            if civ1_best
            else None,
            "civ2_best": format_unit(civ2_best[0], civ2_best[1], civ2_beats_best)
            if civ2_best
            else None,
            "civ1_all": [
                format_unit(k, v, civ1_beats_best)
                for k, v in sorted(civ1_scores.items(), key=lambda x: -x[1]["score"])
            ],
            "civ2_all": [
                format_unit(k, v, civ2_beats_best)
                for k, v in sorted(civ2_scores.items(), key=lambda x: -x[1]["score"])
            ],
        }

    conn.close()
    return jsonify({"civ1": civ1, "civ2": civ2, "ages": results})


def simulate_battle(unit1, cost1, unit2, cost2, resources):
    """
    Fast analytical battle simulation for matchup comparisons.
    Uses DPS-based calculations instead of tick-by-tick simulation.

    Returns: (winner, unit1_remaining, unit2_remaining)
        winner: 1 if unit1 wins, 2 if unit2 wins, 0 if draw
    """
    import json
    import math

    # Calculate army sizes
    count1 = max(1, resources // cost1)
    count2 = max(1, resources // cost2)

    # Parse attacks and armors
    attacks1 = json.loads(unit1["attacks_json"]) if unit1["attacks_json"] else {}
    armors1 = json.loads(unit1["armors_json"]) if unit1["armors_json"] else {}
    attacks2 = json.loads(unit2["attacks_json"]) if unit2["attacks_json"] else {}
    armors2 = json.loads(unit2["armors_json"]) if unit2["armors_json"] else {}

    # Convert keys to int
    attacks1 = {int(k): v for k, v in attacks1.items()}
    armors1 = {int(k): v for k, v in armors1.items()}
    attacks2 = {int(k): v for k, v in attacks2.items()}
    armors2 = {int(k): v for k, v in armors2.items()}

    # Get attack range (0 = melee) and movement speed
    range1 = unit1["attack_range"] or 0.0
    range2 = unit2["attack_range"] or 0.0

    is_ranged1 = range1 >= 1.0
    is_ranged2 = range2 >= 1.0

    # Calculate damage per hit (use pierce for ranged, melee for melee)
    def calc_damage(
        attacker_attacks,
        attacker_attack,
        defender_armors,
        defender_melee_armor,
        defender_pierce_armor,
        is_ranged,
    ):
        if is_ranged:
            base_damage = attacker_attacks.get(
                3, attacker_attacks.get(4, attacker_attack)
            )
            target_armor = defender_armors.get(3, defender_pierce_armor)
        else:
            base_damage = attacker_attacks.get(4, attacker_attack)
            target_armor = defender_armors.get(4, defender_melee_armor)

        bonus_damage = 0
        for armor_class, armor_value in defender_armors.items():
            if armor_class in attacker_attacks and armor_class not in (3, 4):
                attack_bonus = attacker_attacks[armor_class]
                if attack_bonus > 0:
                    effective_bonus = max(0, attack_bonus - armor_value)
                    bonus_damage += effective_bonus
        return max(1, base_damage + bonus_damage - target_armor)

    dmg1 = calc_damage(
        attacks1,
        unit1["attack"],
        armors2,
        unit2["melee_armor"],
        unit2["pierce_armor"],
        is_ranged1,
    )
    dmg2 = calc_damage(
        attacks2,
        unit2["attack"],
        armors1,
        unit1["melee_armor"],
        unit1["pierce_armor"],
        is_ranged2,
    )

    # Get attack speeds
    speed1 = unit1["attack_speed"] or 0.5
    speed2 = unit2["attack_speed"] or 0.5
    reload1 = 1.0 / speed1 if speed1 > 0 else 2.0
    reload2 = 1.0 / speed2 if speed2 > 0 else 2.0

    # Calculate DPS (damage per second)
    dps1 = dmg1 / reload1  # Damage unit1 does to unit2 per second
    dps2 = dmg2 / reload2  # Damage unit2 does to unit1 per second

    # HP pools
    hp1 = unit1["hp"]
    hp2 = unit2["hp"]

    # Total army HP
    total_hp1 = hp1 * count1
    total_hp2 = hp2 * count2

    # Total army DPS (all units attacking)
    total_dps1 = dps1 * count1
    total_dps2 = dps2 * count2

    # Kiting advantage for ranged vs melee
    # If ranged vs melee, ranged gets more effective attacks before melee closes
    kiting_factor1 = 1.0
    kiting_factor2 = 1.0

    if is_ranged1 and not is_ranged2:
        # Unit1 is ranged, unit2 is melee - unit1 gets kiting advantage
        # More range = more kiting time
        kiting_factor1 = 1.0 + (range1 * 0.1)  # 10% bonus per range tile
    elif is_ranged2 and not is_ranged1:
        # Unit2 is ranged, unit1 is melee - unit2 gets kiting advantage
        kiting_factor2 = 1.0 + (range2 * 0.1)

    # Adjusted DPS with kiting
    effective_dps1 = total_dps1 * kiting_factor1
    effective_dps2 = total_dps2 * kiting_factor2

    # Time to kill each army
    time_to_kill2 = total_hp2 / effective_dps1 if effective_dps1 > 0 else float("inf")
    time_to_kill1 = total_hp1 / effective_dps2 if effective_dps2 > 0 else float("inf")

    # Determine winner based on who dies first
    if time_to_kill2 < time_to_kill1:
        # Team 1 kills team 2 first
        # Calculate how much HP team 1 has left
        damage_taken = effective_dps2 * time_to_kill2
        hp_remaining = total_hp1 - damage_taken
        units_remaining = max(1, math.ceil(hp_remaining / hp1))
        return (1, min(units_remaining, count1), 0)
    elif time_to_kill1 < time_to_kill2:
        # Team 2 kills team 1 first
        damage_taken = effective_dps1 * time_to_kill1
        hp_remaining = total_hp2 - damage_taken
        units_remaining = max(1, math.ceil(hp_remaining / hp2))
        return (2, 0, min(units_remaining, count2))
    else:
        # Draw - both die at the same time
        return (0, 0, 0)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
