"""Read yardstick_battles.db, derive ranking scores, write to battle_scores.

Score model:
  signed_score(outcome) = 100 * (winner_hp% - loser_hp%) (negated if team2 won)

Role aggregation (averaged across the 2 scales):
  general_combat = avg over (champion, paladin, arbalester)
  anti_cav       = avg over (paladin)
  anti_archer    = avg over (arbalester)
  anti_trash     = avg over (halberdier, imp_elite_skirm, hussar)

Composites + pool normalization mirror compute_battle_scores.py /
derive_battle_scores_from_matchups.py.
"""

import argparse
import json
import os
import sqlite3
import time
from collections import defaultdict

from webapp.unit_lines import UNIT_LINES, CIV_MISSING_UNITS

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
YARDSTICK_DB_PATH = os.path.join(os.path.dirname(__file__), "yardstick_battles.db")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

YARDSTICK_TO_ROLE = {
    "champion":        ["general_combat"],
    "paladin":         ["general_combat", "anti_cav"],
    "arbalester":      ["general_combat", "anti_archer"],
    "halberdier":      ["anti_trash"],
    "imp_elite_skirm": ["anti_trash"],
    "hussar":          ["anti_trash"],
}

# Maps each role to the key prefix used in per-benchmark sub-scores.
ROLE_PREFIX = {
    "general_combat": "gc",
    "anti_cav":       "ac",
    "anti_archer":    "aa",
    "anti_trash":     "at",
}

# Maps yardstick_slug to short label used in sub-score keys.
YARDSTICK_LABEL = {
    "champion":        "champ",
    "paladin":         "paladin",
    "arbalester":      "arb",
    "halberdier":      "halb",
    "imp_elite_skirm": "elite_skirm",
    "hussar":          "hussar",
}

ROLE_SCORE_TYPES = ("general_combat", "anti_archer", "anti_cav", "anti_trash")


def sub_score_keys(role, yardstick_slug, scale):
    """Yield (norm_key, raw_key) for each (role, yardstick, scale) combo
    that the JS rankings tooltips look up."""
    prefix = ROLE_PREFIX[role]
    label = YARDSTICK_LABEL[yardstick_slug]
    base = f"{prefix}_{scale}_vs_{label}"
    return base, f"{base}_raw"

COMPOSITE_WEIGHTS = {
    "militia_value":         {"general_combat": 0.75, "anti_cav": 0.10, "anti_trash": 0.15},
    "ranged_effectiveness":  {"general_combat": 0.70, "anti_archer": 0.30},
    "stable_effectiveness":  {"general_combat": 0.70, "anti_cav": 0.30},
}

LINE_COMPOSITE = {
    "militia": "militia_value", "spear": "militia_value", "shock_infantry": "militia_value",
    "skirmisher": "ranged_effectiveness", "archer": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness", "gunpowder": "ranged_effectiveness",
    "scorpion": "ranged_effectiveness",
    "light_cav": "stable_effectiveness", "knight": "stable_effectiveness",
    "camel": "stable_effectiveness", "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
}

POOL_OF_LINE = {
    "militia": "infantry", "spear": "infantry", "shock_infantry": "infantry",
    "skirmisher": "ranged", "archer": "ranged", "cav_archer": "ranged",
    "gunpowder": "ranged", "scorpion": "ranged",
    "light_cav": "stable", "knight": "stable", "camel": "stable",
    "steppe_lancer": "stable", "elephant": "stable",
}

SPEED_WEIGHTED_COMPOSITES = {
    "ranged_effectiveness": ("_speed", "_range"),
    "stable_effectiveness": ("_speed",),
}

def _all_sub_score_types():
    keys = []
    for ys, roles in YARDSTICK_TO_ROLE.items():
        for role in roles:
            for scale in ("30v30", "3k"):
                norm_key, raw_key = sub_score_keys(role, ys, scale)
                keys.append(norm_key)
                keys.append(raw_key)
    return tuple(keys)


TARGET_SCORE_TYPES = ROLE_SCORE_TYPES + tuple(COMPOSITE_WEIGHTS) + _all_sub_score_types()


def _signed_score_from_row(row):
    """row is a sqlite3.Row from yardstick_battles."""
    if row["winner"] == 0:
        return 0.0
    if row["winner"] == 1:
        return 100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"])
    return -100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"])


def aggregate_role_scores(rows):
    """rows = [(yardstick_slug, scale, signed_score), ...] for ONE (civ, unit).
    Returns dict {role_score_type: float}."""
    by_role = defaultdict(list)
    for ys, _scale, sc in rows:
        for role in YARDSTICK_TO_ROLE.get(ys, ()):
            by_role[role].append(sc)
    out = {}
    for role in ROLE_SCORE_TYPES:
        vals = by_role.get(role, [])
        if vals:
            out[role] = round(sum(vals) / len(vals), 1)
    return out


def _normalize_pool(units_dict, key):
    """Map units_dict[k][key] to 0..100 across the pool (linear)."""
    if not units_dict:
        return
    raw = [v[key] for v in units_dict.values()]
    lo, hi = min(raw), max(raw)
    span = hi - lo if hi != lo else 0
    for v in units_dict.values():
        if span == 0:
            v[key] = 0.0
        else:
            v[key] = round((v[key] - lo) / span * 100, 1)


def build_slug_to_line():
    out = {}
    for line_slug, info in UNIT_LINES.items():
        for k in ("castle_slug", "imperial_slug"):
            if info.get(k):
                out[info[k]] = line_slug
        for k in ("castle_slugs", "imperial_slugs",
                  "extra_castle_slugs", "extra_imperial_slugs"):
            for s in (info.get(k) or []):
                if s:
                    out[s] = line_slug
        for civ_slugs in (info.get("unique_units") or {}).values():
            if isinstance(civ_slugs, list):
                for tup in civ_slugs:
                    for s in tup:
                        if s:
                            out[s] = line_slug
            else:
                for s in civ_slugs:
                    if s:
                        out[s] = line_slug
    return out


def compute_scores(yardstick_conn, ref_units_by_civ_slug, slug_to_line):
    """Returns {(line_slug, civ, unit): {score_type: 0..100, ...}}."""

    rows = yardstick_conn.execute(
        """SELECT civ, my_unit_slug, yardstick_slug, scale,
                  winner, team1_hp_pct, team2_hp_pct
           FROM yardstick_battles"""
    ).fetchall()

    by_unit = defaultdict(list)  # (civ, slug) -> [(ys, scale, signed_score)]
    for r in rows:
        # Skip phantom rows — units present in ref_units but not actually in
        # the civ's tech tree (e.g. Mapuche/Tupi/Muisca/Incas champion).
        if (r["civ"], r["my_unit_slug"]) in CIV_MISSING_UNITS:
            continue
        by_unit[(r["civ"], r["my_unit_slug"])].append(
            (r["yardstick_slug"], r["scale"], _signed_score_from_row(r))
        )

    # Track raw per-benchmark signed scores keyed by (civ, slug) -> {sub_key: raw}
    raw_subs = defaultdict(dict)
    for (civ, slug), pair_rows in by_unit.items():
        for ys, scale, sc in pair_rows:
            for role in YARDSTICK_TO_ROLE.get(ys, ()):
                norm_key, raw_key = sub_score_keys(role, ys, scale)
                raw_subs[(civ, slug)][raw_key] = round(sc, 1)
                # store norm under norm_key for now; will be overwritten with normalized value
                raw_subs[(civ, slug)][norm_key] = sc

    by_pool = defaultdict(dict)
    for (civ, slug), pair_rows in by_unit.items():
        line = slug_to_line.get(slug)
        if line is None:
            continue
        pool = POOL_OF_LINE.get(line)
        if pool is None:
            continue
        ref = ref_units_by_civ_slug.get((civ, slug))
        if ref is None:
            continue
        roles = aggregate_role_scores(pair_rows)
        if not roles:
            continue
        entry = dict(roles)
        entry["_speed"] = ref["final_speed"] or 1.0
        entry["_range"] = (ref["final_range"] or 0) + 1.0
        by_pool[pool][(line, civ, slug)] = entry

    out = defaultdict(dict)

    # Pool-normalize per-benchmark sub-scores. Done across the same pool that
    # the role uses, so a unit's normalized vs-Paladin score is comparable to
    # the pool-normalized anti_cav role score.
    for pool, units in by_pool.items():
        sub_keys_in_pool = set()
        for (line, civ, slug) in units:
            for k in raw_subs[(civ, slug)]:
                if not k.endswith("_raw"):
                    sub_keys_in_pool.add(k)
        for sub_key in sub_keys_in_pool:
            tmp = {}
            for k in units:
                _, civ, slug = k
                v = raw_subs[(civ, slug)].get(sub_key, 0)
                tmp[k] = {"v": v}
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[k][sub_key] = v["v"]
        # raw values: passthrough, no normalization
        for k in units:
            _, civ, slug = k
            for rkey, rval in raw_subs[(civ, slug)].items():
                if rkey.endswith("_raw"):
                    out[k][rkey] = rval

    for pool, units in by_pool.items():
        for role in ROLE_SCORE_TYPES:
            tmp = {k: {"v": v.get(role, 0)} for k, v in units.items()}
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[k][role] = v["v"]

        sample_line = next(iter(units))[0]
        comp_name = LINE_COMPOSITE.get(sample_line)
        if not comp_name:
            continue
        weights = COMPOSITE_WEIGHTS[comp_name]
        tmp = {}
        for k in units:
            row = out[k]
            val = sum(weights[c] * row.get(c, 0) for c in weights)
            tmp[k] = {"v": val}
        mult_keys = SPEED_WEIGHTED_COMPOSITES.get(comp_name)
        if mult_keys:
            for k, v in tmp.items():
                mult = 1.0
                for mk in mult_keys:
                    mult *= units[k][mk]
                v["v"] *= mult
        _normalize_pool(tmp, "v")
        for k, v in tmp.items():
            out[k][comp_name] = v["v"]

    return out


def load_ref_units(conn, age="Imperial"):
    rows = conn.execute(
        "SELECT civ_name, unit_slug, final_speed, final_range "
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
    age_lower = age.lower()
    cur = conn.cursor()

    by_line_type = defaultdict(list)
    for (line, civ, slug), st_map in scores.items():
        for st, val in st_map.items():
            by_line_type[(line, st)].append((civ, slug, val))

    deleted = 0
    for (line, st), entries in by_line_type.items():
        for civ, slug, _ in entries:
            cur.execute(
                "DELETE FROM battle_scores WHERE line_slug=? AND age=? "
                "AND civ_name=? AND unit_slug=? AND score_type=?",
                (line, age_lower, civ, slug, st),
            )
            deleted += cur.rowcount

    inserts = 0
    for (line, st), entries in by_line_type.items():
        entries.sort(key=lambda e: -e[2])
        sorted_vals = sorted(e[2] for e in entries)
        median_val = sorted_vals[len(sorted_vals) // 2] if sorted_vals else 0
        for rank_idx, (civ, slug, val) in enumerate(entries, start=1):
            cur.execute("""
                INSERT INTO battle_scores
                (line_slug, age, civ_name, unit_slug, score_type, score_value,
                 rank, median_delta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (line, age_lower, civ, slug, st, round(val, 1),
                  rank_idx, round(val - median_val, 1)))
            inserts += 1

    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return deleted, inserts


def restore_backup(conn, backup_path):
    with open(backup_path) as f:
        rows = json.load(f)
    cur = conn.cursor()
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--age", default="imperial")
    parser.add_argument("--restore", metavar="BACKUP.json")
    args = parser.parse_args()

    if not os.path.exists(YARDSTICK_DB_PATH):
        print(f"ERROR: {YARDSTICK_DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if args.restore:
        n = restore_backup(conn, args.restore)
        print(f"Restored {n} rows from {args.restore}")
        return

    age_proper = args.age.capitalize()
    yconn = sqlite3.connect(YARDSTICK_DB_PATH)
    yconn.row_factory = sqlite3.Row

    slug_to_line = build_slug_to_line()
    ref_units = load_ref_units(conn, age_proper)
    scores = compute_scores(yconn, ref_units, slug_to_line)
    print(f"Computed scores for {len(scores)} (line, civ, unit) entries")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"battle_scores_pre_yardstick_{ts}.json")
    backup = backup_existing(conn, args.age, TARGET_SCORE_TYPES)
    with open(backup_path, "w") as f:
        json.dump(backup, f)
    print(f"Backed up {len(backup)} rows to {backup_path}")

    deleted, inserted = write_scores(conn, scores, age_proper, dry_run=args.dry_run)
    print(f"Deleted: {deleted}  Inserted: {inserted}")
    if args.dry_run:
        print("(dry run — no changes committed)")

    yconn.close()
    conn.close()


if __name__ == "__main__":
    main()
