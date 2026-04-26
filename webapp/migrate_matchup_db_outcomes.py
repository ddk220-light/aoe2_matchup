"""Add nullable BattleOutcome columns to matchup_combos_real.db.

Idempotent: skips columns that already exist.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "matchup_combos_real.db")

NEW_COLUMNS = [
    ("end_reason", "TEXT"),
    ("game_time_s", "REAL"),
    ("team1_hp_pct", "REAL"),
    ("team2_hp_pct", "REAL"),
    ("team1_survivors", "INTEGER"),
    ("team2_survivors", "INTEGER"),
    ("team1_resources_lost", "INTEGER"),
    ("team2_resources_lost", "INTEGER"),
    ("runs_count", "INTEGER"),
    ("score_stddev", "REAL"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(matchup_combos)")
    existing = {r[1] for r in cur.fetchall()}
    added = 0
    for name, type_ in NEW_COLUMNS:
        if name in existing:
            continue
        cur.execute(f"ALTER TABLE matchup_combos ADD COLUMN {name} {type_}")
        added += 1
        print(f"  + {name} {type_}")
    conn.commit()
    conn.close()
    print(f"Added {added} columns.")


if __name__ == "__main__":
    main()
