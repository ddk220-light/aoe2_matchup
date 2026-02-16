"""
Best units logic: civ power units (pre-computed) + matchup recommendations (on-the-fly).
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
POWER_UNITS_PATH = os.path.join(os.path.dirname(__file__), "civ_power_units.json")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Role definitions: (role_key, line_slugs, score_type)
ROLE_DEFS = [
    ("cavalry", ["stable"], "stable_effectiveness"),
    ("ranged", ["archer", "cav_archer", "scorpion", "gunpowder"], "ranged_effectiveness"),
    ("infantry", ["militia", "shock_infantry"], "militia_value"),
    ("anti_cavalry", ["spear", "militia"], "anti_cav_value"),
    ("siege", ["siege"], "anti_building_score"),
]

# Trash role handled separately (needs gold cost filter)
TRASH_LINES = ["stable", "militia", "spear", "shock_infantry", "archer", "cav_archer",
               "scorpion", "gunpowder", "skirmisher"]


def _classify_strength(rank, median_delta):
    """Classify a unit's strength tier based on rank and median_delta."""
    if rank is not None and rank <= 5 and median_delta is not None and median_delta > 20:
        return "signature"
    if median_delta is not None and median_delta > 10:
        return "strong"
    if median_delta is not None and median_delta < -10:
        return "weak"
    return "average"


def compute_civ_power_units():
    """Pre-compute power units for all civs. Returns dict keyed by civ_name."""
    conn = _get_db()
    rc = conn.cursor()

    # Get all civ names
    rc.execute("SELECT DISTINCT civ_name FROM battle_scores ORDER BY civ_name")
    all_civs = [row["civ_name"] for row in rc.fetchall()]

    # Get trash unit slugs (gold cost = 0) from ref_units
    rc.execute(
        "SELECT DISTINCT civ_name, unit_slug FROM ref_units WHERE final_cost_gold = 0 AND age = 'Imperial'"
    )
    trash_by_civ = {}
    for row in rc.fetchall():
        trash_by_civ.setdefault(row["civ_name"], set()).add(row["unit_slug"])

    result = {}

    for civ in all_civs:
        civ_data = {"imperial": None, "castle": None}

        for age_key in ["imperial"]:  # Start with imperial only
            power_units = {}

            for role_key, line_slugs, score_type in ROLE_DEFS:
                placeholders = ",".join("?" for _ in line_slugs)
                rc.execute(
                    f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                        FROM battle_scores
                        WHERE civ_name = ?
                          AND LOWER(age) = ?
                          AND score_type = ?
                          AND line_slug IN ({placeholders})
                        ORDER BY median_delta DESC
                        LIMIT 1""",
                    [civ, age_key, score_type] + line_slugs,
                )
                row = rc.fetchone()
                if row:
                    strength = _classify_strength(row["rank"], row["median_delta"])
                    power_units[role_key] = {
                        "unit_slug": row["unit_slug"],
                        "line_slug": row["line_slug"],
                        "score": round(row["score_value"], 1),
                        "rank": row["rank"],
                        "median_delta": round(row["median_delta"], 1),
                        "is_signature": strength == "signature",
                        "strength": strength,
                    }
                else:
                    power_units[role_key] = None

            # Trash: best general_combat among zero-gold units
            civ_trash = trash_by_civ.get(civ, set())
            if civ_trash:
                trash_placeholders = ",".join("?" for _ in civ_trash)
                line_placeholders = ",".join("?" for _ in TRASH_LINES)
                rc.execute(
                    f"""SELECT unit_slug, line_slug, score_value, rank, median_delta
                        FROM battle_scores
                        WHERE civ_name = ?
                          AND LOWER(age) = ?
                          AND score_type = 'general_combat'
                          AND line_slug IN ({line_placeholders})
                          AND unit_slug IN ({trash_placeholders})
                        ORDER BY median_delta DESC
                        LIMIT 1""",
                    [civ, age_key] + TRASH_LINES + list(civ_trash),
                )
                row = rc.fetchone()
                if row:
                    strength = _classify_strength(row["rank"], row["median_delta"])
                    power_units["trash"] = {
                        "unit_slug": row["unit_slug"],
                        "line_slug": row["line_slug"],
                        "score": round(row["score_value"], 1),
                        "rank": row["rank"],
                        "median_delta": round(row["median_delta"], 1),
                        "is_signature": strength == "signature",
                        "strength": strength,
                    }
                else:
                    power_units["trash"] = None
            else:
                power_units["trash"] = None

            # Build strength profile
            strength_profile = {}
            for role_key in ["cavalry", "ranged", "infantry", "anti_cavalry", "trash", "siege"]:
                entry = power_units.get(role_key)
                strength_profile[role_key] = entry["strength"] if entry else "weak"

            civ_data[age_key] = {
                "power_units": power_units,
                "strength_profile": strength_profile,
            }

        result[civ] = civ_data

    conn.close()
    return result


def save_civ_power_units():
    """Compute and write civ_power_units.json."""
    data = compute_civ_power_units()
    with open(POWER_UNITS_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote {POWER_UNITS_PATH} ({len(data)} civs)")
    return data


def load_civ_power_units():
    """Load pre-computed civ power units. Returns dict or None if file missing."""
    if not os.path.exists(POWER_UNITS_PATH):
        return None
    with open(POWER_UNITS_PATH, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    save_civ_power_units()
