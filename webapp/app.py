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

    # Units to exclude from simulations (low accuracy units like Trebuchets and Rams)
    EXCLUDED_UNITS = {"trebuchet", "packed-trebuchet", "ram", "siege_ram"}

    # Only compare Castle and Imperial ages (feudal units are not very useful)
    MATCHUP_AGES = {k: v for k, v in AGES.items() if k != "feudal"}

    for age_slug, age_data in MATCHUP_AGES.items():
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

        # Resource cost formula varies by age
        # Castle age: wood + 2*food + gold
        # Imperial age: wood + 2*food + 3*gold
        is_imperial = age_slug == "imperial"

        def calc_resource_cost(unit):
            food = unit["cost_food"] or 0
            wood = unit["cost_wood"] or 0
            gold = unit["cost_gold"] or 0
            if is_imperial:
                cost = wood + 2 * food + 3 * gold
            else:
                cost = wood + 2 * food + gold
            return cost if cost > 0 else 100

        # Paired units: different modes of the same unit (e.g., Ratha melee/ranged)
        # Group them together so we can test all modes and use the best result
        PAIRED_UNIT_PATTERNS = [
            ("ratha_(melee)", "ratha_(ranged)", "Ratha"),
            ("elite_ratha_(melee)", "elite_ratha_(ranged)", "Elite Ratha"),
        ]

        def get_paired_unit(slug):
            """Return the paired unit slug if this unit has a pair, else None."""
            for mode1, mode2, _ in PAIRED_UNIT_PATTERNS:
                if mode1 in slug:
                    return slug.replace(mode1, mode2)
                if mode2 in slug:
                    return slug.replace(mode2, mode1)
            return None

        def get_display_name_for_paired(slug):
            """Return display name for paired units."""
            for mode1, mode2, display in PAIRED_UNIT_PATTERNS:
                if mode1 in slug or mode2 in slug:
                    return display
            return None

        # Build lookup dict for units by slug
        civ1_unit_lookup = {u["slug"]: u for u in civ1_units}
        civ2_unit_lookup = {u["slug"]: u for u in civ2_units}

        # Filter out paired units - only keep one mode per pair (we'll test both in simulation)
        def filter_paired_units(units):
            """Keep only one representative per paired unit group."""
            seen_pairs = set()
            filtered = []
            for u in units:
                slug = u["slug"]
                paired = get_paired_unit(slug)
                if paired:
                    # This is a paired unit - check if we already have its pair
                    pair_key = tuple(sorted([slug, paired]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        filtered.append(u)
                else:
                    filtered.append(u)
            return filtered

        civ1_units_filtered = filter_paired_units(civ1_units)
        civ2_units_filtered = filter_paired_units(civ2_units)

        for u1 in civ1_units_filtered:
            u1_wins = 0
            u1_total = 0
            u1_cost = calc_resource_cost(u1)

            # Get all modes for u1 (for paired units like Ratha)
            u1_modes = [u1]
            u1_paired_slug = get_paired_unit(u1["slug"])
            if u1_paired_slug and u1_paired_slug in civ1_unit_lookup:
                u1_modes.append(civ1_unit_lookup[u1_paired_slug])

            for u2 in civ2_units_filtered:
                # Get all modes for u2 (for paired units like Ratha)
                u2_modes = [u2]
                u2_paired_slug = get_paired_unit(u2["slug"])
                if u2_paired_slug and u2_paired_slug in civ2_unit_lookup:
                    u2_modes.append(civ2_unit_lookup[u2_paired_slug])

                # Test all combinations of modes and find the best outcome for each side
                # For paired units: unit wins if ANY of its modes wins against ANY of opponent's modes
                u1_won_any = False
                u2_won_any = False

                # Track best outcome across all mode combinations
                # We want to find if any mode combo results in winning BOTH simulations
                u1_won_both_any = False  # u1 won both sims in at least one mode combo
                u2_won_both_any = False  # u2 won both sims in at least one mode combo
                u1_won_any = False  # u1 won at least one sim in any mode combo
                u2_won_any = False  # u2 won at least one sim in any mode combo

                for u1_mode in u1_modes:
                    u1_mode_cost = calc_resource_cost(u1_mode)
                    for u2_mode in u2_modes:
                        u2_mode_cost = calc_resource_cost(u2_mode)

                        # Run two simulations:
                        # 1. Resource-based: 3000 resources
                        # 2. Count-based: 30 units each
                        winner_resources, _, _ = simulate_battle(
                            u1_mode,
                            u1_mode_cost,
                            u2_mode,
                            u2_mode_cost,
                            3000,
                            civ1,
                            civ2,
                        )
                        winner_count, _, _ = simulate_battle(
                            u1_mode,
                            u1_mode_cost,
                            u2_mode,
                            u2_mode_cost,
                            0,  # resources ignored when fixed_count is set
                            civ1,
                            civ2,
                            fixed_count=30,
                        )

                        # Track if this mode combo won both simulations
                        if winner_resources == 1 and winner_count == 1:
                            u1_won_both_any = True
                        if winner_resources == 2 and winner_count == 2:
                            u2_won_both_any = True

                        # Track if won at least one
                        if winner_resources == 1 or winner_count == 1:
                            u1_won_any = True
                        if winner_resources == 2 or winner_count == 2:
                            u2_won_any = True

                # Determine winner and score:
                # - If a unit won BOTH simulations in any mode combo: 3 points (clear win)
                # - If results are split (each won at least one): 1 point each (draw)
                # - If neither won anything: 0 points (true draw, shouldn't happen often)
                if u1_won_both_any and not u2_won_both_any:
                    winner = 1
                    u1_score_add = 3
                    u2_score_add = 0
                elif u2_won_both_any and not u1_won_both_any:
                    winner = 2
                    u1_score_add = 0
                    u2_score_add = 3
                elif u1_won_any and u2_won_any:
                    # Split results - draw, 1 point each
                    winner = 0
                    u1_score_add = 1
                    u2_score_add = 1
                elif u1_won_both_any and u2_won_both_any:
                    # Both have mode combos that won both - draw
                    winner = 0
                    u1_score_add = 1
                    u2_score_add = 1
                else:
                    # True draw - neither won anything
                    winner = 0
                    u1_score_add = 1
                    u2_score_add = 1

                u1_total += 1
                if winner == 1:
                    u1_wins += 1

                # Track for civ2 scoring - use primary slug for paired units
                u2_key = u2["slug"]
                if u2_key not in civ2_scores:
                    # Use display name for paired units
                    display_name = get_display_name_for_paired(u2["slug"])
                    civ2_scores[u2_key] = {
                        "wins": 0,
                        "total": 0,
                        "unit": u2,
                        "display_name": display_name,
                    }
                civ2_scores[u2_key]["total"] += 1
                if winner == 2:
                    civ2_scores[u2_key]["wins"] += 1

                # Use display name for paired units in matchup results
                u1_display = get_display_name_for_paired(u1["slug"]) or u1["unit_name"]
                u2_display = get_display_name_for_paired(u2["slug"]) or u2["unit_name"]

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

            # Use display name for paired units
            u1_display_name = get_display_name_for_paired(u1["slug"])
            civ1_scores[u1["slug"]] = {
                "wins": u1_wins,
                "total": u1_total,
                "unit": u1,
                "display_name": u1_display_name,
            }

        # Define trash and siege units for scoring
        # Trash units: no score, just show counters
        TRASH_SLUGS = {
            "spearman",
            "pikeman",
            "halberdier",
            "skirmisher",
            "elite_skirm",
            "scout",
            "light_cav",
            "hussar",
        }
        # Siege units: no score, just show counters
        SIEGE_SLUGS = {
            "ram",
            "mangonel",
            "scorpion",
            "siege_ram",
            "siege_onager",
            "heavy_scorpion",
            "bombard_cannon",
            "trebuchet",
        }

        def get_base_slug(slug):
            """Remove civ suffix from slug to get base unit slug."""
            # First check if the full slug is already a known unit type
            if slug in TRASH_SLUGS or slug in SIEGE_SLUGS:
                return slug
            # Slugs are like 'elite_longbowman_britons' or 'siege_onager_britons'
            # We need to remove the civ suffix (last part)
            parts = slug.rsplit("_", 1)
            if len(parts) == 2 and len(parts[1]) > 3:
                # Likely a civ suffix (civ names are longer than 3 chars)
                return parts[0]
            return slug

        def is_trash_or_siege(slug):
            """Check if unit slug (with civ suffix) is trash or siege."""
            base = get_base_slug(slug)
            return base in TRASH_SLUGS or base in SIEGE_SLUGS

        def get_unit_type(slug):
            """Return 'trash', 'siege', or 'combat' for a unit slug."""
            base = get_base_slug(slug)
            if base in TRASH_SLUGS:
                return "trash"
            if base in SIEGE_SLUGS:
                return "siege"
            return "combat"

        # Build matchup lookup and track details
        matchup_results = {}
        civ1_matchup_details = {}
        civ2_matchup_details = {}
        for m in all_matchups:
            key = (m["civ1_slug"], m["civ2_slug"])
            matchup_results[key] = m["winner"]

            # Determine result for each side: "win", "draw", or "loss"
            if m["winner"] == 1:
                civ1_result = "win"
                civ2_result = "loss"
            elif m["winner"] == 2:
                civ1_result = "loss"
                civ2_result = "win"
            else:
                civ1_result = "draw"
                civ2_result = "draw"

            # Track details for civ1 unit
            if m["civ1_slug"] not in civ1_matchup_details:
                civ1_matchup_details[m["civ1_slug"]] = []
            civ1_matchup_details[m["civ1_slug"]].append(
                {
                    "opponent": m["civ2_unit"],
                    "opponent_slug": m["civ2_slug"],
                    "result": civ1_result,
                    "score": m["u1_score"],
                }
            )

            # Track details for civ2 unit
            if m["civ2_slug"] not in civ2_matchup_details:
                civ2_matchup_details[m["civ2_slug"]] = []
            civ2_matchup_details[m["civ2_slug"]].append(
                {
                    "opponent": m["civ1_unit"],
                    "opponent_slug": m["civ1_slug"],
                    "result": civ2_result,
                    "score": m["u2_score"],
                }
            )

        # Calculate scores for each unit
        # Scoring: 3 for winning both sims, 1 each for draw (split results)
        # No score for beating trash or siege units
        for key in civ1_scores:
            s = civ1_scores[key]
            s["win_rate"] = s["wins"] / s["total"] if s["total"] > 0 else 0
            # Calculate score based on matchup details
            score = 0
            for matchup in civ1_matchup_details.get(key, []):
                opp_slug = matchup["opponent_slug"]
                is_trash = opp_slug in TRASH_SLUGS
                is_siege = opp_slug in SIEGE_SLUGS
                # Only score for significant units (not trash, not siege)
                if not is_trash and not is_siege:
                    score += matchup["score"]
            s["score"] = score

        for key in civ2_scores:
            s = civ2_scores[key]
            s["win_rate"] = s["wins"] / s["total"] if s["total"] > 0 else 0
            # Calculate score based on matchup details
            score = 0
            for matchup in civ2_matchup_details.get(key, []):
                opp_slug = matchup["opponent_slug"]
                is_trash = opp_slug in TRASH_SLUGS
                is_siege = opp_slug in SIEGE_SLUGS
                # Only score for significant units (not trash, not siege)
                if not is_trash and not is_siege:
                    score += matchup["score"]
            s["score"] = score

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
                    if m["winner"] == 1:
                        civ1_beats_best.add(m["civ1_slug"])
                # Check if civ2 unit beats civ1's best
                if m["civ1_slug"] == civ1_best_slug:
                    if m["winner"] == 2:
                        civ2_beats_best.add(m["civ2_slug"])

        def format_unit(slug, data, beats_opponent_best, matchup_details):
            # Sort matchups by result: wins, draws, losses
            details = matchup_details.get(slug, [])
            wins = [d for d in details if d["result"] == "win"]
            draws = [d for d in details if d["result"] == "draw"]
            losses = [d for d in details if d["result"] == "loss"]
            # Use display_name for paired units (like Ratha), otherwise use unit_name
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

        def format_counter_unit(slug, data, matchup_details):
            """Format trash/siege unit showing only what it counters (no score)."""
            details = matchup_details.get(slug, [])
            wins = [d for d in details if d["result"] == "win"]
            draws = [d for d in details if d["result"] == "draw"]
            display_name = data.get("display_name") or data["unit"]["unit_name"]
            return {
                "slug": slug,
                "name": display_name,
                "counters": [d["opponent"] for d in wins],
                "draws": [d["opponent"] for d in draws],
            }

        # Separate combat units from trash/siege
        civ1_combat = {k: v for k, v in civ1_scores.items() if not is_trash_or_siege(k)}
        civ1_trash = {
            k: v for k, v in civ1_scores.items() if get_unit_type(k) == "trash"
        }
        civ1_siege = {
            k: v for k, v in civ1_scores.items() if get_unit_type(k) == "siege"
        }

        civ2_combat = {k: v for k, v in civ2_scores.items() if not is_trash_or_siege(k)}
        civ2_trash = {
            k: v for k, v in civ2_scores.items() if get_unit_type(k) == "trash"
        }
        civ2_siege = {
            k: v for k, v in civ2_scores.items() if get_unit_type(k) == "siege"
        }

        # Find best unit only among combat units
        civ1_combat_best = (
            max(civ1_combat.items(), key=lambda x: x[1]["score"])
            if civ1_combat
            else None
        )
        civ2_combat_best = (
            max(civ2_combat.items(), key=lambda x: x[1]["score"])
            if civ2_combat
            else None
        )

        results[age_slug] = {
            "age_name": age_data["name"],
            "civ1_best": format_unit(
                civ1_combat_best[0],
                civ1_combat_best[1],
                civ1_beats_best,
                civ1_matchup_details,
            )
            if civ1_combat_best
            else None,
            "civ2_best": format_unit(
                civ2_combat_best[0],
                civ2_combat_best[1],
                civ2_beats_best,
                civ2_matchup_details,
            )
            if civ2_combat_best
            else None,
            "civ1_all": [
                format_unit(k, v, civ1_beats_best, civ1_matchup_details)
                for k, v in sorted(civ1_combat.items(), key=lambda x: -x[1]["score"])
            ],
            "civ2_all": [
                format_unit(k, v, civ2_beats_best, civ2_matchup_details)
                for k, v in sorted(civ2_combat.items(), key=lambda x: -x[1]["score"])
            ],
            "civ1_trash": [
                format_counter_unit(k, v, civ1_matchup_details)
                for k, v in civ1_trash.items()
            ],
            "civ1_siege": [
                format_counter_unit(k, v, civ1_matchup_details)
                for k, v in civ1_siege.items()
            ],
            "civ2_trash": [
                format_counter_unit(k, v, civ2_matchup_details)
                for k, v in civ2_trash.items()
            ],
            "civ2_siege": [
                format_counter_unit(k, v, civ2_matchup_details)
                for k, v in civ2_siege.items()
            ],
        }

    conn.close()
    return jsonify({"civ1": civ1, "civ2": civ2, "ages": results})


def simulate_battle(
    unit1,
    cost1,
    unit2,
    cost2,
    resources,
    civ1_name=None,
    civ2_name=None,
    fixed_count=None,
):
    """
    Tick-based battle simulation with kiting support and siege projectile mechanics.

    Siege units (mangonels, siege onagers) fire ground-targeted projectiles that
    travel at light cavalry speed. They struggle against fast melee units but
    do well against slower ranged units.

    Args:
        fixed_count: If provided, use this fixed unit count for both sides
                     instead of calculating from resources.

    Returns: (winner, unit1_remaining, unit2_remaining)
        winner: 1 if unit1 wins, 2 if unit2 wins, 0 if draw
    """
    import json

    # Calculate army sizes
    if fixed_count is not None:
        count1 = fixed_count
        count2 = fixed_count
    else:
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
    move_speed1 = unit1["movement_speed"] or 1.0
    move_speed2 = unit2["movement_speed"] or 1.0

    is_ranged1 = range1 >= 1.0
    is_ranged2 = range2 >= 1.0

    # Siege units fire ground-targeted projectiles (mangonel, siege_onager)
    SIEGE_UNITS = {"mangonel", "siege_onager"}
    # Scorpions have minimum range but fire direct projectiles (no splash)
    SCORPION_UNITS = {"scorpion", "heavy_scorpion"}
    # Skirmishers have minimum range of 1
    SKIRMISHER_UNITS = {"skirm", "elite_skirm"}
    # Units that ignore armor (Composite Bowman ignores pierce, Leitis ignores melee)
    IGNORE_PIERCE_ARMOR = {"composite_bowman", "elite_composite_bowman"}
    IGNORE_MELEE_ARMOR = {"leitis", "elite_leitis"}

    # Units with trample damage (melee splash)
    # Format: base_slug -> (trample_percent, trample_radius, flat_damage)
    TRAMPLE_UNITS = {
        "ratha_(melee)": (0.5, 0.5, 0),  # 50% damage, 0.5 tile radius
        "elite_ratha_(melee)": (0.5, 0.5, 0),
        "elephant": (0.5, 0.5, 0),  # Battle Elephant
        "elite_elephant": (0.5, 0.5, 0),
        "cataphract": (0.5, 0.5, 0),
        "elite_cataphract": (0.5, 0.5, 0),
        "war_elephant": (0.5, 0.5, 0),
        "elite_war_elephant": (0.5, 0.5, 0),
    }
    # Slavic infantry with Druzhina - flat 5 damage trample
    DRUZHINA_CIVS = {"Slavs"}
    DRUZHINA_INFANTRY = {"champion", "halberdier", "swordsmen"}
    DRUZHINA_TRAMPLE = (0, 0.5, 5)  # 0%, 0.5 radius, 5 flat damage

    def get_trample_info(slug, civ_name):
        """Return (trample_percent, radius, flat_damage) or None."""
        # Check base slug (remove civ suffix like _bengalis, _byzantines)
        base_slug = slug
        # Try removing last part after underscore to get base slug
        if "_" in slug:
            parts = slug.rsplit("_", 1)
            # Only remove if the last part looks like a civ name (not part of unit name)
            if len(parts[1]) > 3:  # Civ names are longer than 3 chars
                base_slug = parts[0]

        # Check direct trample units
        if base_slug in TRAMPLE_UNITS:
            return TRAMPLE_UNITS[base_slug]

        # Also check full slug in case base_slug stripping was wrong
        if slug in TRAMPLE_UNITS:
            return TRAMPLE_UNITS[slug]

        # Check Druzhina for Slavic infantry (Imperial age only)
        if civ_name in DRUZHINA_CIVS and base_slug in DRUZHINA_INFANTRY:
            return DRUZHINA_TRAMPLE

        return None

    slug1 = unit1["slug"] if "slug" in unit1.keys() else ""
    slug2 = unit2["slug"] if "slug" in unit2.keys() else ""
    is_siege1 = slug1 in SIEGE_UNITS
    is_siege2 = slug2 in SIEGE_UNITS
    is_scorpion1 = slug1 in SCORPION_UNITS
    is_scorpion2 = slug2 in SCORPION_UNITS
    is_skirmisher1 = slug1 in SKIRMISHER_UNITS
    is_skirmisher2 = slug2 in SKIRMISHER_UNITS
    # Check if units ignore armor (match base slug without civ suffix)
    slug1_base = slug1.rsplit("_", 1)[0] if "_" in slug1 else slug1
    slug2_base = slug2.rsplit("_", 1)[0] if "_" in slug2 else slug2
    ignores_pierce1 = slug1_base in IGNORE_PIERCE_ARMOR
    ignores_pierce2 = slug2_base in IGNORE_PIERCE_ARMOR
    ignores_melee1 = slug1_base in IGNORE_MELEE_ARMOR
    ignores_melee2 = slug2_base in IGNORE_MELEE_ARMOR

    # Get trample info for both units
    trample1 = get_trample_info(slug1, civ1_name)
    trample2 = get_trample_info(slug2, civ2_name)

    # Projectile speed for siege units - roughly same as light cavalry (1.65 tiles/sec)
    # This allows fast melee units to dodge by moving out of the impact zone
    PROJECTILE_SPEED = 1.7
    # Hit radius - projectile hits if target is within this distance of impact point
    HIT_RADIUS = 1.0
    # Splash radius - siege projectiles deal damage to all units in this radius
    SPLASH_RADIUS = 1.5
    # Minimum attack range for siege units - they can't fire at close range
    # In AoE2, mangonels have minimum range of 3, scorpions have minimum range of 2
    # Skirmishers have minimum range of 1
    MIN_SIEGE_RANGE = 3.0
    MIN_SCORPION_RANGE = 2.0
    MIN_SKIRMISHER_RANGE = 1.0

    # Bengali civ bonus: elephant units take 25% less bonus damage
    BENGALI_BONUS_REDUCTION = 0.25
    BENGALI_ELEPHANT_SLUGS = {
        "elephant",
        "elite_elephant",
        "elephant_archer",
        "elite_ele_archer",
        "ratha_(melee)",
        "elite_ratha_(melee)",
        "ratha_(ranged)",
        "elite_ratha_(ranged)",
    }

    def is_bengali_elephant(slug, civ_name):
        """Check if unit is a Bengali elephant unit that gets bonus damage reduction."""
        if civ_name != "Bengalis":
            return False
        base_slug = (
            slug.rsplit("_", 1)[0]
            if "_" in slug and len(slug.rsplit("_", 1)[1]) > 3
            else slug
        )
        return base_slug in BENGALI_ELEPHANT_SLUGS or slug in BENGALI_ELEPHANT_SLUGS

    # Calculate damage per hit (use pierce for ranged, melee for melee)
    def calc_damage(
        attacker_attacks,
        attacker_attack,
        defender_armors,
        defender_melee_armor,
        defender_pierce_armor,
        is_ranged,
        ignores_pierce=False,
        ignores_melee=False,
        bonus_damage_reduction=0,
    ):
        if is_ranged:
            base_damage = attacker_attacks.get(
                3, attacker_attacks.get(4, attacker_attack)
            )
            # Composite Bowman ignores pierce armor
            target_armor = (
                0 if ignores_pierce else defender_armors.get(3, defender_pierce_armor)
            )
        else:
            base_damage = attacker_attacks.get(4, attacker_attack)
            # Leitis ignores melee armor
            target_armor = (
                0 if ignores_melee else defender_armors.get(4, defender_melee_armor)
            )

        bonus_damage = 0
        for armor_class, armor_value in defender_armors.items():
            if armor_class in attacker_attacks and armor_class not in (3, 4):
                attack_bonus = attacker_attacks[armor_class]
                if attack_bonus > 0:
                    effective_bonus = max(0, attack_bonus - armor_value)
                    bonus_damage += effective_bonus

        # Apply bonus damage reduction (e.g., Bengali elephants take 25% less)
        if bonus_damage_reduction > 0:
            bonus_damage = int(bonus_damage * (1 - bonus_damage_reduction))

        return max(1, base_damage + bonus_damage - target_armor)

    # Check for Bengali elephant bonus damage reduction
    bonus_reduction1 = (
        BENGALI_BONUS_REDUCTION if is_bengali_elephant(slug1, civ1_name) else 0
    )
    bonus_reduction2 = (
        BENGALI_BONUS_REDUCTION if is_bengali_elephant(slug2, civ2_name) else 0
    )

    dmg1 = calc_damage(
        attacks1,
        unit1["attack"],
        armors2,
        unit2["melee_armor"],
        unit2["pierce_armor"],
        is_ranged1,
        ignores_pierce=ignores_pierce1,
        ignores_melee=ignores_melee1,
        bonus_damage_reduction=bonus_reduction2,  # Defender's reduction
    )
    dmg2 = calc_damage(
        attacks2,
        unit2["attack"],
        armors1,
        unit1["melee_armor"],
        unit1["pierce_armor"],
        is_ranged2,
        ignores_pierce=ignores_pierce2,
        ignores_melee=ignores_melee2,
        bonus_damage_reduction=bonus_reduction1,  # Defender's reduction
    )

    # Get attack speeds (reload time)
    speed1 = unit1["attack_speed"] or 0.5
    speed2 = unit2["attack_speed"] or 0.5
    reload1 = 1.0 / speed1 if speed1 > 0 else 2.0
    reload2 = 1.0 / speed2 if speed2 > 0 else 2.0

    # Create armies with positions
    # Team 1 starts at position 0 (left), Team 2 at position 100 (right)
    hp1 = [float(unit1["hp"])] * count1
    hp2 = [float(unit2["hp"])] * count2
    pos1 = [i * 0.5 for i in range(count1)]
    pos2 = [100 - i * 0.5 for i in range(count2)]
    cooldown1 = [0.0] * count1
    cooldown2 = [0.0] * count2

    # Simulate with tick limit for speed
    dt = 0.1  # 100ms time step
    max_ticks = 1000
    melee_range = 0.5
    ticks = 0
    start_hp1 = sum(hp1)
    start_hp2 = sum(hp2)

    # Map boundaries - units can't kite forever
    MAP_MIN = 0
    MAP_MAX = 100

    # Track siege projectiles in flight
    # Each projectile: (target_team, impact_pos, current_pos, damage, target_positions_at_fire)
    # target_positions_at_fire is a dict of {unit_idx: position} for splash damage calculation
    projectiles = []

    while ticks < max_ticks:
        ticks += 1
        alive1 = [i for i, h in enumerate(hp1) if h > 0]
        alive2 = [i for i, h in enumerate(hp2) if h > 0]

        if not alive1 or not alive2:
            break

        # Early termination: if one side lost >50% units and other has >60% left
        alive1_pct = len(alive1) / count1
        alive2_pct = len(alive2) / count2
        if alive1_pct < 0.5 and alive2_pct > 0.6:
            # Team 2 wins decisively
            return (2, len(alive1), len(alive2))
        if alive2_pct < 0.5 and alive1_pct > 0.6:
            # Team 1 wins decisively
            return (1, len(alive1), len(alive2))

        # Update cooldowns
        for i in alive1:
            cooldown1[i] = max(0, cooldown1[i] - dt)
        for i in alive2:
            cooldown2[i] = max(0, cooldown2[i] - dt)

        # Update siege projectiles in flight
        new_projectiles = []
        for proj in projectiles:
            target_team, impact_pos, proj_pos, damage, positions_at_fire = proj
            # Move projectile toward impact position
            if proj_pos < impact_pos:
                proj_pos += PROJECTILE_SPEED * dt
                arrived = proj_pos >= impact_pos
            else:
                proj_pos -= PROJECTILE_SPEED * dt
                arrived = proj_pos <= impact_pos

            if arrived:
                # Projectile arrived - apply splash damage to units that were near impact
                # AND haven't moved much (dodge check)
                if target_team == 1:
                    for idx in alive1:
                        if idx in positions_at_fire:
                            pos_at_fire = positions_at_fire[idx]
                            # Was unit near impact point when fired?
                            if abs(pos_at_fire - impact_pos) <= SPLASH_RADIUS:
                                # Has unit moved significantly? (dodge check)
                                dist_moved = abs(pos1[idx] - pos_at_fire)
                                if dist_moved <= HIT_RADIUS:
                                    hp1[idx] -= damage
                else:
                    for idx in alive2:
                        if idx in positions_at_fire:
                            pos_at_fire = positions_at_fire[idx]
                            # Was unit near impact point when fired?
                            if abs(pos_at_fire - impact_pos) <= SPLASH_RADIUS:
                                # Has unit moved significantly? (dodge check)
                                dist_moved = abs(pos2[idx] - pos_at_fire)
                                if dist_moved <= HIT_RADIUS:
                                    hp2[idx] -= damage
            else:
                new_projectiles.append(
                    (target_team, impact_pos, proj_pos, damage, positions_at_fire)
                )
        projectiles = new_projectiles

        # Collect attacks (simultaneous)
        pending_damage = []

        # Ranged units kite (move away while reloading)
        # But only if they're faster than the enemy, or if enemy is also ranged
        # This prevents unrealistic perfect kiting where slower ranged beats faster melee
        should_kite1 = is_ranged1 and (is_ranged2 or move_speed1 > move_speed2)
        should_kite2 = is_ranged2 and (is_ranged1 or move_speed2 > move_speed1)

        # Team 1 units (move right toward team 2)
        for i in alive1:
            closest = min(alive2, key=lambda j: abs(pos2[j] - pos1[i]))
            distance = abs(pos2[closest] - pos1[i])
            attack_range = range1 if is_ranged1 else melee_range

            if is_ranged1:
                # Check minimum range for siege units and scorpions
                can_fire = distance <= attack_range
                if is_siege1 and distance < MIN_SIEGE_RANGE:
                    can_fire = False  # Too close, siege can't fire
                if is_scorpion1 and distance < MIN_SCORPION_RANGE:
                    can_fire = False  # Too close, scorpion can't fire
                if is_skirmisher1 and distance < MIN_SKIRMISHER_RANGE:
                    can_fire = False  # Too close, skirmisher can't fire

                if cooldown1[i] <= 0 and can_fire:
                    if is_siege1:
                        # Siege unit fires ground-targeted projectile with splash
                        # Store positions of all enemy units at fire time for dodge calculation
                        target_pos = pos2[closest]
                        enemy_positions = {idx: pos2[idx] for idx in alive2}
                        projectiles.append(
                            (2, target_pos, pos1[i], dmg1, enemy_positions)
                        )
                    else:
                        pending_damage.append((2, closest, dmg1, i, pos1[i]))
                    cooldown1[i] = reload1
                elif cooldown1[i] > 0 and should_kite1:
                    # Kite (move away while reloading), respect map boundary
                    pos1[i] = max(MAP_MIN, pos1[i] - move_speed1 * dt)
                elif distance > attack_range:
                    pos1[i] += move_speed1 * dt
                # Siege units inside minimum range can't do anything - they're helpless
            else:
                if distance <= attack_range:
                    if cooldown1[i] <= 0:
                        pending_damage.append((2, closest, dmg1, i, pos1[i]))
                        cooldown1[i] = reload1
                else:
                    pos1[i] += move_speed1 * dt

        # Team 2 units (move left toward team 1)
        for i in alive2:
            closest = min(alive1, key=lambda j: abs(pos1[j] - pos2[i]))
            distance = abs(pos1[closest] - pos2[i])
            attack_range = range2 if is_ranged2 else melee_range

            if is_ranged2:
                # Check minimum range for siege units and scorpions
                can_fire = distance <= attack_range
                if is_siege2 and distance < MIN_SIEGE_RANGE:
                    can_fire = False  # Too close, siege can't fire
                if is_scorpion2 and distance < MIN_SCORPION_RANGE:
                    can_fire = False  # Too close, scorpion can't fire
                if is_skirmisher2 and distance < MIN_SKIRMISHER_RANGE:
                    can_fire = False  # Too close, skirmisher can't fire

                if cooldown2[i] <= 0 and can_fire:
                    if is_siege2:
                        # Siege unit fires ground-targeted projectile with splash
                        # Store positions of all enemy units at fire time for dodge calculation
                        target_pos = pos1[closest]
                        enemy_positions = {idx: pos1[idx] for idx in alive1}
                        projectiles.append(
                            (1, target_pos, pos2[i], dmg2, enemy_positions)
                        )
                    else:
                        pending_damage.append((1, closest, dmg2, i, pos2[i]))
                    cooldown2[i] = reload2
                elif cooldown2[i] > 0 and should_kite2:
                    # Kite (move away while reloading), respect map boundary
                    pos2[i] = min(MAP_MAX, pos2[i] + move_speed2 * dt)
                elif distance > attack_range:
                    pos2[i] -= move_speed2 * dt
                # Siege units inside minimum range can't do anything - they're helpless
            else:
                if distance <= attack_range:
                    if cooldown2[i] <= 0:
                        pending_damage.append((1, closest, dmg2, i, pos2[i]))
                        cooldown2[i] = reload2
                else:
                    pos2[i] -= move_speed2 * dt

        # Apply damage (including trample)
        for team, target, damage, attacker_idx, attacker_pos in pending_damage:
            if team == 1:
                hp1[target] -= damage
                # Apply trample damage from unit2 to nearby unit1s
                if trample2 and not is_ranged2:
                    trample_pct, trample_radius, flat_dmg = trample2
                    trample_dmg = int(damage * trample_pct) + flat_dmg
                    if trample_dmg > 0:
                        for idx in alive1:
                            if idx != target:  # Skip primary target
                                dist = abs(pos1[idx] - attacker_pos)
                                if dist <= trample_radius:
                                    hp1[idx] -= trample_dmg
            else:
                hp2[target] -= damage
                # Apply trample damage from unit1 to nearby unit2s
                if trample1 and not is_ranged1:
                    trample_pct, trample_radius, flat_dmg = trample1
                    trample_dmg = int(damage * trample_pct) + flat_dmg
                    if trample_dmg > 0:
                        for idx in alive2:
                            if idx != target:  # Skip primary target
                                dist = abs(pos2[idx] - attacker_pos)
                                if dist <= trample_radius:
                                    hp2[idx] -= trample_dmg

    remaining1 = len([h for h in hp1 if h > 0])
    remaining2 = len([h for h in hp2 if h > 0])
    total_hp1 = sum(max(0, h) for h in hp1)
    total_hp2 = sum(max(0, h) for h in hp2)

    # Determine winner
    if remaining1 > 0 and remaining2 == 0:
        return (1, remaining1, 0)
    elif remaining2 > 0 and remaining1 == 0:
        return (2, 0, remaining2)
    else:
        # Compare units lost from start
        lost1 = count1 - remaining1
        lost2 = count2 - remaining2
        if lost1 > lost2:
            # Team 1 lost more units, Team 2 wins
            return (2, remaining1, remaining2)
        elif lost2 > lost1:
            # Team 2 lost more units, Team 1 wins
            return (1, remaining1, remaining2)
        else:
            # Same units lost - compare HP percentage lost
            hp_lost_pct1 = (start_hp1 - total_hp1) / start_hp1 if start_hp1 > 0 else 0
            hp_lost_pct2 = (start_hp2 - total_hp2) / start_hp2 if start_hp2 > 0 else 0
            if hp_lost_pct1 > hp_lost_pct2:
                # Team 1 lost more HP %, Team 2 wins
                return (2, remaining1, remaining2)
            elif hp_lost_pct2 > hp_lost_pct1:
                # Team 2 lost more HP %, Team 1 wins
                return (1, remaining1, remaining2)
            else:
                return (0, remaining1, remaining2)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
