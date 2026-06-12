"""
Compute "Ease of Creation" score for every civ-unit combo.

Criteria (weighted):
  1. Not created at Castle         (0.3) - binary
  2. Low creation time             (0.2) - normalized inverse
  3. Low total upgrade cost        (0.3) - normalized inverse
  4. No castle unique tech needed  (0.1) - binary
  5. Fast movement speed           (0.1) - normalized

Output: unit_creation_ease table in aoe2_reference.db
"""

import sqlite3
import os

from aoe2x.paths import GOLDEN_DIR as _GOLDEN_DIR
DB_PATH = os.path.join(str(_GOLDEN_DIR), "aoe2_reference.db")

# Building ID 82 = Castle
CASTLE_BUILDING_ID = 82

# Unit class -> building ID (from config.py)
UNIT_CLASS_TO_BUILDING = {
    6: 12,    # Infantry -> Barracks
    0: 87,    # Archer -> Archery Range
    12: 101,  # Cavalry -> Stable
    36: 87,   # Cavalry Archer -> Archery Range
    13: 49,   # Siege -> Siege Workshop
    44: 87,   # Gunpowder (Hand Cannoneer) -> Archery Range
    55: 49,   # Scorpion/Ballista -> Siege Workshop
    54: 82,   # Trebuchet -> Castle
}


def get_training_building(unit_type, unit_class):
    """Determine training building ID for a unit."""
    if unit_type == "unique":
        return CASTLE_BUILDING_ID
    return UNIT_CLASS_TO_BUILDING.get(unit_class, None)


def compute():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Gather all civ-unit rows from ref_units
    cur.execute("""
        SELECT id, civ_name, unit_name, unit_slug, unit_type, unit_class,
               final_train_time, final_speed,
               upgrade_cost_food, upgrade_cost_wood, upgrade_cost_gold
        FROM ref_units
    """)
    rows = [dict(r) for r in cur.fetchall()]

    # 2. Find which ref_unit IDs have a castle unique tech applied
    cur.execute("""
        SELECT DISTINCT ref_unit_id
        FROM ref_techs_applied
        WHERE tech_type = 'unique_tech' AND building = 'Castle'
    """)
    needs_castle_ut_ids = {r[0] for r in cur.fetchall()}

    # 3. Compute raw values for each row
    records = []
    for r in rows:
        building_id = get_training_building(r["unit_type"], r["unit_class"])
        is_castle = building_id == CASTLE_BUILDING_ID
        total_upgrade_cost = (
            (r["upgrade_cost_food"] or 0)
            + (r["upgrade_cost_wood"] or 0)
            + (r["upgrade_cost_gold"] or 0)
        )
        needs_castle_ut = r["id"] in needs_castle_ut_ids
        creation_time = r["final_train_time"] or 0
        speed = r["final_speed"] or 0

        records.append({
            "civ_name": r["civ_name"],
            "unit_name": r["unit_name"],
            "unit_slug": r["unit_slug"],
            "is_castle_unit": is_castle,
            "creation_time": creation_time,
            "total_upgrade_cost": total_upgrade_cost,
            "needs_castle_ut": needs_castle_ut,
            "movement_speed": speed,
        })

    # 4. Compute min/max for normalization
    creation_times = [r["creation_time"] for r in records if r["creation_time"] > 0]
    upgrade_costs = [r["total_upgrade_cost"] for r in records]
    speeds = [r["movement_speed"] for r in records]

    ct_min, ct_max = min(creation_times), max(creation_times)
    uc_min, uc_max = min(upgrade_costs), max(upgrade_costs)
    sp_min, sp_max = min(speeds), max(speeds)

    # 5. Score each record
    for r in records:
        # Criterion 1: Not castle (binary)
        r["score_not_castle"] = 0.0 if r["is_castle_unit"] else 1.0

        # Criterion 2: Low creation time (inverse normalized)
        if ct_max > ct_min and r["creation_time"] > 0:
            r["score_creation_time"] = 1.0 - (r["creation_time"] - ct_min) / (ct_max - ct_min)
        else:
            r["score_creation_time"] = 0.5  # default for 0 train time edge cases

        # Criterion 3: Low upgrade cost (inverse normalized)
        if uc_max > uc_min:
            r["score_upgrade_cost"] = 1.0 - (r["total_upgrade_cost"] - uc_min) / (uc_max - uc_min)
        else:
            r["score_upgrade_cost"] = 1.0

        # Criterion 4: No castle unique tech (binary)
        r["score_no_castle_ut"] = 0.0 if r["needs_castle_ut"] else 1.0

        # Criterion 5: Fast movement speed (normalized)
        if sp_max > sp_min:
            r["score_speed"] = (r["movement_speed"] - sp_min) / (sp_max - sp_min)
        else:
            r["score_speed"] = 0.5

        # Weighted total
        r["ease_score"] = round(
            0.3 * r["score_not_castle"]
            + 0.2 * r["score_creation_time"]
            + 0.3 * r["score_upgrade_cost"]
            + 0.1 * r["score_no_castle_ut"]
            + 0.1 * r["score_speed"],
            4,
        )

    # 6. Write to DB
    cur.execute("DROP TABLE IF EXISTS unit_creation_ease")
    cur.execute("""
        CREATE TABLE unit_creation_ease (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ_name TEXT NOT NULL,
            unit_name TEXT NOT NULL,
            unit_slug TEXT,
            is_castle_unit INTEGER NOT NULL,
            creation_time REAL,
            total_upgrade_cost INTEGER,
            needs_castle_ut INTEGER NOT NULL,
            movement_speed REAL,
            score_not_castle REAL,
            score_creation_time REAL,
            score_upgrade_cost REAL,
            score_no_castle_ut REAL,
            score_speed REAL,
            ease_score REAL NOT NULL
        )
    """)

    cur.executemany(
        """INSERT INTO unit_creation_ease
           (civ_name, unit_name, unit_slug, is_castle_unit, creation_time,
            total_upgrade_cost, needs_castle_ut, movement_speed,
            score_not_castle, score_creation_time, score_upgrade_cost,
            score_no_castle_ut, score_speed, ease_score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                r["civ_name"], r["unit_name"], r["unit_slug"],
                int(r["is_castle_unit"]), r["creation_time"],
                r["total_upgrade_cost"], int(r["needs_castle_ut"]),
                r["movement_speed"],
                round(r["score_not_castle"], 4),
                round(r["score_creation_time"], 4),
                round(r["score_upgrade_cost"], 4),
                round(r["score_no_castle_ut"], 4),
                round(r["score_speed"], 4),
                r["ease_score"],
            )
            for r in records
        ],
    )

    conn.commit()
    print(f"Wrote {len(records)} rows to unit_creation_ease table")

    # 7. Show stats
    print(f"\nNormalization ranges:")
    print(f"  Creation time: {ct_min} - {ct_max}")
    print(f"  Upgrade cost:  {uc_min} - {uc_max}")
    print(f"  Speed:         {sp_min} - {sp_max}")

    # 8. Show 10 samples spanning the range
    cur.execute("""
        SELECT civ_name, unit_name, is_castle_unit, creation_time,
               total_upgrade_cost, needs_castle_ut, movement_speed, ease_score
        FROM unit_creation_ease
        ORDER BY ease_score DESC
    """)
    all_rows = cur.fetchall()
    total = len(all_rows)

    # Pick 5 easiest, 5 hardest
    samples = all_rows[:5] + all_rows[-5:]

    print(f"\n{'Civ':<16} {'Unit':<28} {'Castle?':>7} {'Time':>6} {'UpgCost':>8} {'CUT?':>5} {'Speed':>6} {'Ease':>6}")
    print("-" * 100)
    for i, s in enumerate(samples):
        if i == 5:
            print("  " + "·" * 96)
        civ, unit, castle, ct, uc, cut, spd, ease = s
        print(f"{civ:<16} {unit:<28} {'Yes' if castle else 'No':>7} {ct:>6.0f} {uc:>8} {'Yes' if cut else 'No':>5} {spd:>6.2f} {ease:>6.4f}")

    conn.close()


if __name__ == "__main__":
    compute()
