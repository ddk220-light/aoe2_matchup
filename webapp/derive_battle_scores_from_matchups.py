"""
Derive unit ranking scores from matchup_combos_real.db.

This is a pure-data transform — it runs ZERO simulations.  Every score is
aggregated from the rank-1 recommendations already stored in the matchup DB
(produced by generate_matchup_db_real.py).  When the matchup DB is regenerated
(after sim changes), re-running this script propagates the new data into the
unit rankings.

Score types updated (imperial age only — that's what the matchup DB covers):
    general_combat
    anti_archer
    anti_cav
    anti_trash
    militia_value          (composite: 0.75 GC + 0.10 AC + 0.15 AT)
    ranged_effectiveness   (composite: 0.70 GC + 0.30 AA, then range/speed weight)
    stable_effectiveness   (composite: 0.70 GC + 0.30 AC, then speed weight)

Score types LEFT UNTOUCHED (no matchup-DB equivalent):
    anti_building_score, mobility_*, raiding_*, naval_effectiveness,
    vs_fire / vs_galleon / vs_hulk, all "_raw" sub-scores, all per-benchmark
    gc_/aa_/ac_/at_ scenario scores.

A backup of the rows being overwritten is dumped to a JSON file before
the UPDATE so the previous fast-sim values can be restored if needed.

Usage:
    cd webapp && python3 derive_battle_scores_from_matchups.py
    cd webapp && python3 derive_battle_scores_from_matchups.py --dry-run
    cd webapp && python3 derive_battle_scores_from_matchups.py --restore <backup.json>
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict

from unit_lines import UNIT_LINES

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
MATCHUP_DB_PATH = os.path.join(os.path.dirname(__file__), "matchup_combos_real.db")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

# Score types we will overwrite.  Pre-cleared before INSERT.
TARGET_SCORE_TYPES = (
    "general_combat",
    "anti_archer",
    "anti_cav",
    "anti_trash",
    "militia_value",
    "ranged_effectiveness",
    "stable_effectiveness",
)

# Map opponent's rank-1 top-unit's line_slug to the role bucket on OUR side
# (which categorical score increments).
OPPONENT_LINE_TO_ROLE = {
    # Archery / gunpowder roles → my anti_archer
    "archer": "anti_archer",
    "gunpowder": "anti_archer",
    "cav_archer": "anti_archer",
    # Cavalry / camel / elephant → my anti_cav
    "knight": "anti_cav",
    "camel": "anti_cav",
    "light_cav": "anti_cav",
    "steppe_lancer": "anti_cav",
    "elephant": "anti_cav",
    # Trash / spear / skirm → my anti_trash
    "spear": "anti_trash",
    "skirmisher": "anti_trash",
    # Other (militia/shock_infantry/siege/naval) → not in our anti_X bucket
    # set; still counted toward general_combat via N_top.
}

# Composite weights (mirror compute_battle_scores.py)
COMPOSITE_WEIGHTS = {
    "militia_value":         {"general_combat": 0.75, "anti_cav": 0.10, "anti_trash": 0.15},
    "ranged_effectiveness":  {"general_combat": 0.70, "anti_archer": 0.30},
    "stable_effectiveness":  {"general_combat": 0.70, "anti_cav": 0.30},
}

# Which composite belongs to which line (mirror best_units.LINE_SCORE_TYPE).
# A line only gets ONE composite written into battle_scores.
LINE_COMPOSITE = {
    "militia":        "militia_value",
    "spear":          "militia_value",
    "shock_infantry": "militia_value",
    "skirmisher":     "ranged_effectiveness",
    "archer":         "ranged_effectiveness",
    "cav_archer":     "ranged_effectiveness",
    "gunpowder":      "ranged_effectiveness",
    "scorpion":       "ranged_effectiveness",
    "light_cav":      "stable_effectiveness",
    "knight":         "stable_effectiveness",
    "camel":          "stable_effectiveness",
    "steppe_lancer":  "stable_effectiveness",
    "elephant":       "stable_effectiveness",
}

# Lines that get speed/range weighting on their composite.
SPEED_WEIGHTED_COMPOSITES = {
    "ranged_effectiveness": ("_speed", "_range"),
    "stable_effectiveness": ("_speed",),
    # militia_value is NOT speed-weighted in current scoring
}


# ---------------------------------------------------------------------------
# Slug → line_slug mapping
# ---------------------------------------------------------------------------


def build_slug_to_line():
    """Return {unit_slug: line_slug} based on UNIT_LINES.

    Includes castle/imperial standard slugs, extra slugs, and unique units
    (both castle and imperial / elite variants).
    """
    out = {}
    for line_slug, info in UNIT_LINES.items():
        for k in ("castle_slug", "imperial_slug"):
            v = info.get(k)
            if v:
                out[v] = line_slug
        for k in ("castle_slugs", "imperial_slugs", "extra_castle_slugs", "extra_imperial_slugs"):
            v = info.get(k) or []
            for s in v:
                if s:
                    out[s] = line_slug
        unique = info.get("unique_units", {}) or {}
        for civ, slugs in unique.items():
            # Some entries are list-of-tuples (e.g. Incas multi-uniques).
            if isinstance(slugs, list):
                for tup in slugs:
                    for s in tup:
                        if s:
                            out[s] = line_slug
            else:
                for s in slugs:
                    if s:
                        out[s] = line_slug
    return out


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def fetch_rank1_recommendations(matchup_db):
    """For every (civ, opponent) pair, return the rank-1 top recommendation.

    Picks the row with combo_rank=1 and the LOWER sidekick_rank (i.e. the
    actually-displayed top: sidekick_rank=1 if a sidekick exists, else
    sidekick_rank=0 for solo units).  For gold_gold combos (which have
    sidekick_rank=0), still rank-1 is the chosen recommendation.
    """
    conn = sqlite3.connect(matchup_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT civ, opponent, top_unit_slug, partner_slug,
               combo_type, is_perfect, gap_count, top_unit_score,
               sidekick_rank
        FROM matchup_combos
        WHERE combo_rank = 1
        ORDER BY civ, opponent, sidekick_rank ASC
    """).fetchall()
    out = {}
    for r in rows:
        key = (r["civ"], r["opponent"])
        # First row per key wins (sidekick_rank ASC: 0 first then 1).
        # Prefer the displayed top: sidekick_rank=1 (if any) over =0.
        # Trick: overwrite, so the LAST sidekick_rank value wins.  Since we
        # ORDER BY sidekick_rank ASC, the highest (most relevant) lands last.
        out[key] = dict(r)
    conn.close()
    return out


def classify_role(opponent_top_slug, slug_to_line):
    """Return role bucket name (anti_archer/anti_cav/anti_trash) or None."""
    line = slug_to_line.get(opponent_top_slug)
    if line is None:
        return None
    return OPPONENT_LINE_TO_ROLE.get(line)


def aggregate_recommendations(rank1_by_pair, slug_to_line):
    """Build per-unit recommendation counts.

    Returns {(civ, my_unit_slug): {n_top, n_perfect_top,
                                   n_anti_archer, n_anti_cav, n_anti_trash}}
    """
    counts = defaultdict(lambda: {
        "n_top": 0,
        "n_perfect_top": 0,
        "n_anti_archer": 0,
        "n_anti_cav": 0,
        "n_anti_trash": 0,
    })

    for (civ, opp), my_rec in rank1_by_pair.items():
        my_slug = my_rec["top_unit_slug"]
        bucket = counts[(civ, my_slug)]
        bucket["n_top"] += 1
        if my_rec["is_perfect"]:
            bucket["n_perfect_top"] += 1

        # Look up opponent's rank-1 top to classify role.
        opp_rec = rank1_by_pair.get((opp, civ))
        if opp_rec is None:
            continue
        role = classify_role(opp_rec["top_unit_slug"], slug_to_line)
        if role:
            bucket[f"n_{role}"] += 1

    return counts


# ---------------------------------------------------------------------------
# Score computation (per-line × age pool normalization)
# ---------------------------------------------------------------------------


def _normalize_pool(values, key):
    """Map values[*][key] to 0..100 across the pool (linear)."""
    if not values:
        return
    raw = [v[key] for v in values.values()]
    lo, hi = min(raw), max(raw)
    span = hi - lo if hi != lo else 1
    for v in values.values():
        v[key] = round((v[key] - lo) / span * 100, 1)


def compute_scores(counts, ref_units_by_civ_slug, slug_to_line, age="Imperial"):
    """Convert recommendation counts into 0-100 ranking scores per (civ, unit).

    Returns {(line_slug, civ_name, unit_slug): {score_type: value, ...}}.
    """
    # Group units by line_slug for pool normalization.
    by_line = defaultdict(dict)  # {line_slug: {(civ, slug): {raw_metrics, _speed, _range}}}

    for (civ, slug), c in counts.items():
        line_slug = slug_to_line.get(slug)
        if line_slug is None:
            # Unmapped unit (probably a unique unit our slug map missed)
            continue
        # Lookup speed/range from ref_units for later weighting.
        ref = ref_units_by_civ_slug.get((civ, slug))
        if ref is None:
            continue
        by_line[line_slug][(civ, slug)] = {
            "_n_top": c["n_top"],
            "_n_perfect": c["n_perfect_top"],
            "_n_aa": c["n_anti_archer"],
            "_n_ac": c["n_anti_cav"],
            "_n_at": c["n_anti_trash"],
            "_speed": ref["final_speed"] or 1.0,
            "_range": (ref["final_range"] or 0) + 1.0,  # +1 so melee != 0
        }

    # Pool-normalize raw counts into 0-100 scores within each line × age.
    out = defaultdict(dict)
    for line_slug, units in by_line.items():
        if not units:
            continue
        # Convert the raw counts into normalized scores.
        for metric, target_key in (
            ("_n_top",     "general_combat"),
            ("_n_aa",      "anti_archer"),
            ("_n_ac",      "anti_cav"),
            ("_n_at",      "anti_trash"),
        ):
            tmp = {k: {"v": v[metric]} for k, v in units.items()}
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[(line_slug, k[0], k[1])][target_key] = v["v"]

        # Each line gets ONE composite (mirroring LINE_COMPOSITE).
        comp_name = LINE_COMPOSITE.get(line_slug)
        if comp_name:
            weights = COMPOSITE_WEIGHTS[comp_name]
            tmp = {}
            for ck, _ in units.items():
                row = out[(line_slug, ck[0], ck[1])]
                val = sum(weights[c] * row.get(c, 0) for c in weights)
                tmp[ck] = {"v": val}
            mult_keys = SPEED_WEIGHTED_COMPOSITES.get(comp_name)
            if mult_keys:
                for k, v in tmp.items():
                    mult = 1.0
                    for mk in mult_keys:
                        mult *= units[k][mk]
                    v["v"] *= mult
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[(line_slug, k[0], k[1])][comp_name] = v["v"]

    return out


# ---------------------------------------------------------------------------
# DB read/write
# ---------------------------------------------------------------------------


def load_ref_units(conn, age="Imperial"):
    rows = conn.execute(
        "SELECT civ_name, unit_slug, final_speed, final_range, final_attack "
        "FROM ref_units WHERE age=?",
        (age,),
    ).fetchall()
    return {(r["civ_name"], r["unit_slug"]): r for r in rows}


def backup_existing(conn, age, score_types):
    rows = conn.execute(
        f"""SELECT id, line_slug, age, civ_name, unit_slug, score_type,
                   score_value, rank, median_delta
            FROM battle_scores
            WHERE age=? AND score_type IN ({','.join('?' * len(score_types))})""",
        (age, *score_types),
    ).fetchall()
    return [dict(r) for r in rows]


def write_scores(conn, scores, age, dry_run=False):
    """Replace battle_scores rows for our target score_types at this age,
    but ONLY for (civ, unit) pairs we have new data for.  Existing rows
    for non-power units (units that don't appear in civ_power_units.json
    and therefore have no matchup-DB entries) stay untouched.
    """
    age_lower = age.lower()
    cur = conn.cursor()

    # Build per-line × score_type rank tables for ranking.
    by_line_type = defaultdict(list)  # (line, st) -> [(civ, slug, val)]
    for (line_slug, civ, slug), st_map in scores.items():
        for st, val in st_map.items():
            by_line_type[(line_slug, st)].append((civ, slug, val))

    # Targeted DELETE: only the (line, civ, unit, score_type) rows we will
    # immediately re-insert.  Non-power units keep their fast-sim values.
    deleted = 0
    for (line_slug, st), entries in by_line_type.items():
        for civ, slug, _ in entries:
            cur.execute(
                "DELETE FROM battle_scores WHERE line_slug=? AND age=? "
                "AND civ_name=? AND unit_slug=? AND score_type=?",
                (line_slug, age_lower, civ, slug, st),
            )
            deleted += cur.rowcount

    inserts = 0
    for (line_slug, st), entries in by_line_type.items():
        # Rank within line (descending score)
        entries.sort(key=lambda e: -e[2])
        sorted_vals = sorted(e[2] for e in entries)
        median_val = sorted_vals[len(sorted_vals) // 2] if sorted_vals else 0
        for rank_idx, (civ, slug, val) in enumerate(entries, start=1):
            cur.execute("""
                INSERT INTO battle_scores
                (line_slug, age, civ_name, unit_slug, score_type, score_value,
                 rank, median_delta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (line_slug, age_lower, civ, slug, st, round(val, 1),
                  rank_idx, round(val - median_val, 1)))
            inserts += 1

    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return deleted, inserts


def restore_backup(conn, backup_path):
    with open(backup_path, "r") as f:
        rows = json.load(f)
    cur = conn.cursor()
    # Wipe whatever we last wrote, then re-insert backup data verbatim.
    age = rows[0]["age"] if rows else None
    score_types = sorted(set(r["score_type"] for r in rows))
    placeholders = ",".join("?" * len(score_types))
    cur.execute(
        f"DELETE FROM battle_scores WHERE age=? AND score_type IN ({placeholders})",
        (age, *score_types),
    )
    for r in rows:
        cur.execute("""
            INSERT INTO battle_scores
            (id, line_slug, age, civ_name, unit_slug, score_type, score_value,
             rank, median_delta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (r["id"], r["line_slug"], r["age"], r["civ_name"], r["unit_slug"],
              r["score_type"], r["score_value"], r["rank"], r["median_delta"]))
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--age", default="imperial", choices=("imperial", "castle"),
        help="Age to update.  Matchup DB is currently imperial-only."
    )
    parser.add_argument(
        "--restore", metavar="BACKUP.json",
        help="Restore from a backup JSON file (overwrites current rows)."
    )
    args = parser.parse_args()

    if not os.path.exists(MATCHUP_DB_PATH):
        print(f"ERROR: {MATCHUP_DB_PATH} not found.")
        sys.exit(1)
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        sys.exit(1)

    age_proper = args.age.capitalize()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.restore:
        n = restore_backup(conn, args.restore)
        conn.close()
        print(f"Restored {n} rows from {args.restore}")
        return

    print(f"Loading slug -> line mapping...")
    slug_to_line = build_slug_to_line()
    print(f"  {len(slug_to_line)} slugs mapped")

    print(f"Loading ref_units ({age_proper})...")
    ref_units = load_ref_units(conn, age_proper)
    print(f"  {len(ref_units)} (civ, unit) entries")

    print(f"Reading {MATCHUP_DB_PATH}...")
    rank1 = fetch_rank1_recommendations(MATCHUP_DB_PATH)
    print(f"  {len(rank1)} (civ, opponent) directional pairs")

    print("Aggregating per-unit recommendation counts...")
    counts = aggregate_recommendations(rank1, slug_to_line)
    print(f"  {len(counts)} (civ, unit) entries")

    print("Computing normalized scores...")
    scores = compute_scores(counts, ref_units, slug_to_line, age_proper)
    print(f"  {len(scores)} (line, civ, unit) score rows")

    # Backup existing rows
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(
        BACKUP_DIR, f"battle_scores_pre_matchup_{ts}.json"
    )
    backup = backup_existing(conn, args.age, TARGET_SCORE_TYPES)
    with open(backup_path, "w") as f:
        json.dump(backup, f)
    print(f"Backed up {len(backup)} rows to {backup_path}")

    print(f"{'(DRY RUN) ' if args.dry_run else ''}Writing battle_scores...")
    deleted, inserted = write_scores(conn, scores, age_proper, dry_run=args.dry_run)
    print(f"  Deleted: {deleted}  Inserted: {inserted}")

    if args.dry_run:
        print("(dry run — no changes committed)")

    # Quick sanity print: top-3 in a few lines
    print("\nTop 3 by general_combat in each major line:")
    cur = conn.cursor()
    for line in ("militia", "archer", "knight", "scorpion", "skirmisher",
                 "spear", "cav_archer", "camel"):
        rows = cur.execute("""
            SELECT civ_name, unit_slug, score_value
            FROM battle_scores
            WHERE line_slug=? AND age=? AND score_type='general_combat'
            ORDER BY score_value DESC LIMIT 3
        """, (line, args.age)).fetchall()
        if rows:
            top = ", ".join(f"{r[0]} {r[1]} ({r[2]})" for r in rows)
            print(f"  {line:<14}: {top}")

    conn.close()


if __name__ == "__main__":
    main()
