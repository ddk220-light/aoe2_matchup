"""Read matchup_db, write advisor recommendations to derived_data.db.

For each (my_civ, opp_civ) pair, finds the (my_unit) with the highest
mean signed_score against all (opp_civ) opp_units across both scales.
Writes top-2 candidates per pair as `rec_type='top'`.
"""

import argparse
import os
import sqlite3
from collections import defaultdict

from matchup_db import DEFAULT_DB_PATH as MATCHUP_DB_PATH

DERIVED_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")
REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")


def _signed(row):
    if row["winner"] == 0: return 0.0
    if row["winner"] == 1: return 100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"])
    return -100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"])


def compute_and_write_recs(matchup_db_path=MATCHUP_DB_PATH,
                           derived_db_path=DERIVED_DB_PATH,
                           ref_db_path=REF_DB_PATH,
                           top_n=2):
    mconn = sqlite3.connect(matchup_db_path)
    mconn.row_factory = sqlite3.Row

    rows = mconn.execute("""
        SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
               winner, team1_hp_pct, team2_hp_pct
        FROM matchup_battles
    """).fetchall()

    # Aggregate: (my_civ, opp_civ, my_unit) -> list of signed scores
    bucket = defaultdict(list)
    for r in rows:
        bucket[(r["my_civ"], r["opp_civ"], r["my_unit_slug"])].append(_signed(r))

    # Per (my_civ, opp_civ): rank my_units by mean score
    by_pair = defaultdict(list)
    for (civ, opp, unit), scores in bucket.items():
        if not scores:
            continue
        by_pair[(civ, opp)].append((unit, sum(scores) / len(scores)))

    # Pull unit_name from ref DB
    rconn = sqlite3.connect(ref_db_path)
    rconn.row_factory = sqlite3.Row
    name_map = {}
    for r in rconn.execute(
        "SELECT civ_name, unit_slug, unit_name FROM ref_units WHERE age='Imperial'"
    ):
        name_map[(r["civ_name"], r["unit_slug"])] = r["unit_name"]
    rconn.close()
    mconn.close()

    dconn = sqlite3.connect(derived_db_path)
    cur = dconn.cursor()

    inserts = 0
    for (civ, opp), entries in by_pair.items():
        entries.sort(key=lambda e: -e[1])
        cur.execute("DELETE FROM advisor_recommendations WHERE civ=? AND opponent=? AND rec_type='top'",
                    (civ, opp))
        for rank, (unit_slug, score) in enumerate(entries[:top_n], start=1):
            unit_name = name_map.get((civ, unit_slug), unit_slug)
            cur.execute("""
                INSERT INTO advisor_recommendations
                (civ, opponent, rec_type, rec_rank, unit_slug, unit_name, score)
                VALUES (?, ?, 'top', ?, ?, ?, ?)
            """, (civ, opp, rank, unit_slug, unit_name, round(score, 2)))
            inserts += 1

    dconn.commit()
    dconn.close()
    return inserts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=2)
    args = parser.parse_args()
    n = compute_and_write_recs(top_n=args.top_n)
    print(f"Inserted {n} advisor recommendations")


if __name__ == "__main__":
    main()
