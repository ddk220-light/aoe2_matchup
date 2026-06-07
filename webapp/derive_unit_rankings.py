"""Read matchup_db.matchup_battles, write battle_scores to derived_data.db.

Score model: signed_score(outcome) = 100 * (winner_hp% - loser_hp%) (negated
if team2 won). Role aggregation, composites, pool normalization mirror the
prior derive_scores_from_yardsticks.py.
"""

import argparse
import os
import sqlite3
import sys
from collections import defaultdict

# Allow `python -m webapp.derive_unit_rankings` from the repo root: make this
# directory (webapp/) importable for the bare sibling imports below.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from derived_db import create_db as create_derived_db
from matchup_db import DEFAULT_DB_PATH as MATCHUP_DB_PATH
from unit_lines import UNIT_LINES, CIV_MISSING_UNITS
from patches_db import get_current_build  # resolves the build to tag rows with

REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
DERIVED_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")

YARDSTICKS = [
    ("Vikings", "champion"),
    ("Franks",  "paladin"),
    ("Britons", "arbalester"),
    ("Britons", "halberdier"),
    ("Britons", "imp_elite_skirm"),
    ("Magyars", "hussar"),
]

YARDSTICK_TO_ROLE = {
    "champion":        ["general_combat"],
    "paladin":         ["general_combat", "anti_cav"],
    "arbalester":      ["general_combat", "anti_archer"],
    "halberdier":      ["anti_trash"],
    "imp_elite_skirm": ["anti_trash"],
    "hussar":          ["anti_trash"],
}

ROLE_PREFIX = {"general_combat": "gc", "anti_cav": "ac",
               "anti_archer": "aa", "anti_trash": "at"}

YARDSTICK_LABEL = {
    "champion":        "champ",
    "paladin":         "paladin",
    "arbalester":      "arb",
    "halberdier":      "halb",
    "imp_elite_skirm": "elite_skirm",
    "hussar":          "hussar",
}

ROLE_SCORE_TYPES = ("general_combat", "anti_archer", "anti_cav", "anti_trash")

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


def sub_score_keys(role, ys_slug, scale):
    prefix = ROLE_PREFIX[role]
    label = YARDSTICK_LABEL[ys_slug]
    base = f"{prefix}_{scale}_vs_{label}"
    return base, f"{base}_raw"


def _signed_score(row):
    if row["winner"] == 0:
        return 0.0
    if row["winner"] == 1:
        return 100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"])
    return -100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"])


def _normalize_pool(units_dict, key):
    if not units_dict:
        return
    raw = [v[key] for v in units_dict.values()]
    lo, hi = min(raw), max(raw)
    span = hi - lo if hi != lo else 0
    for v in units_dict.values():
        v[key] = 0.0 if span == 0 else round((v[key] - lo) / span * 100, 1)


def build_slug_to_line():
    """Build {unit_slug -> line_slug} for ranking classification.

    First-write-wins: when a slug is listed under multiple lines (e.g.
    elite_ele_archer is in both cav_archer and elephant), the line that
    appears earlier in UNIT_LINES wins. This is intentional — the elephant
    archer is conceptually a ranged unit, and cav_archer is defined before
    elephant in unit_lines.py, so it's correctly scored as ranged_effectiveness
    rather than getting overwritten to stable_effectiveness.
    """
    out = {}
    for line_slug, info in UNIT_LINES.items():
        for k in ("castle_slug", "imperial_slug"):
            if info.get(k):
                out.setdefault(info[k], line_slug)
        for k in ("castle_slugs", "imperial_slugs",
                  "extra_castle_slugs", "extra_imperial_slugs"):
            for s in (info.get(k) or []):
                if s:
                    out.setdefault(s, line_slug)
        for civ_slugs in (info.get("unique_units") or {}).values():
            if isinstance(civ_slugs, list):
                for tup in civ_slugs:
                    for s in tup:
                        if s:
                            out.setdefault(s, line_slug)
            else:
                for s in civ_slugs:
                    if s:
                        out.setdefault(s, line_slug)
    return out


def compute_and_write_rankings(matchup_db_path=MATCHUP_DB_PATH,
                               ref_db_path=REF_DB_PATH,
                               derived_db_path=DERIVED_DB_PATH,
                               age="Imperial",
                               build_number=None):
    """Returns count of rows inserted into battle_scores. Rows are tagged with
    build_number (defaults to the current build from patches.db, then '170934')."""
    if build_number is None:
        # patches.db lives at a fixed webapp location; no path needed here.
        build_number = get_current_build() or "170934"
    mconn = sqlite3.connect(matchup_db_path)
    mconn.row_factory = sqlite3.Row
    rconn = sqlite3.connect(ref_db_path)
    rconn.row_factory = sqlite3.Row

    slug_to_line = build_slug_to_line()
    ref_units = {(r["civ_name"], r["unit_slug"]): r
                 for r in rconn.execute(
                     "SELECT civ_name, unit_slug, final_speed, final_range "
                     "FROM ref_units WHERE age=?", (age,)).fetchall()}

    # Pull only rows where opponent is a yardstick
    yardstick_civ_units = set(YARDSTICKS)
    rows = mconn.execute("""
        SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
               winner, team1_hp_pct, team2_hp_pct
        FROM matchup_battles
    """).fetchall()
    rows = [r for r in rows
            if (r["opp_civ"], r["opp_unit_slug"]) in yardstick_civ_units]

    # by_unit -> [(yardstick_slug, scale, signed_score)]
    by_unit = defaultdict(list)
    raw_subs = defaultdict(dict)  # (civ, slug) -> {sub_key: value}
    for r in rows:
        if (r["my_civ"], r["my_unit_slug"]) in CIV_MISSING_UNITS:
            continue
        sc = _signed_score(r)
        for role in YARDSTICK_TO_ROLE.get(r["opp_unit_slug"], ()):
            norm_key, raw_key = sub_score_keys(role, r["opp_unit_slug"], r["scale"])
            raw_subs[(r["my_civ"], r["my_unit_slug"])][raw_key] = round(sc, 1)
            raw_subs[(r["my_civ"], r["my_unit_slug"])][norm_key] = sc
        by_unit[(r["my_civ"], r["my_unit_slug"])].append(
            (r["opp_unit_slug"], r["scale"], sc)
        )

    # Aggregate roles per unit, classify by line/pool
    by_pool = defaultdict(dict)
    for (civ, slug), pair_rows in by_unit.items():
        line = slug_to_line.get(slug)
        if line is None:
            continue
        pool = POOL_OF_LINE.get(line)
        if pool is None:
            continue
        ref = ref_units.get((civ, slug))
        if ref is None:
            continue
        from collections import defaultdict as dd
        by_role = dd(list)
        for ys, _scale, sc in pair_rows:
            for role in YARDSTICK_TO_ROLE.get(ys, ()):
                by_role[role].append(sc)
        roles = {r: round(sum(v) / len(v), 1) for r, v in by_role.items() if v}
        if not roles:
            continue
        entry = dict(roles)
        entry["_speed"] = ref["final_speed"] or 1.0
        entry["_range"] = (ref["final_range"] or 0) + 1.0
        by_pool[pool][(line, civ, slug)] = entry

    # Build output dict
    out = defaultdict(dict)

    # Per-benchmark sub-scores: pool-normalize within each pool
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
                tmp[k] = {"v": raw_subs[(civ, slug)].get(sub_key, 0)}
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[k][sub_key] = v["v"]
        for k in units:
            _, civ, slug = k
            for rkey, rval in raw_subs[(civ, slug)].items():
                if rkey.endswith("_raw"):
                    out[k][rkey] = rval

    # Role + composite scores
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

    # Write to derived_db.battle_scores
    dconn = sqlite3.connect(derived_db_path)
    age_lower = age.lower()
    by_line_type = defaultdict(list)
    for (line, civ, slug), st_map in out.items():
        for st, val in st_map.items():
            by_line_type[(line, st)].append((civ, slug, val))

    cur = dconn.cursor()
    # Aggressive cleanup: for every (civ, slug) we're about to write, also
    # delete any rows for that pair under DIFFERENT line_slugs at this age.
    # This prevents stale rows from a previous classification (e.g. an older
    # last-write-wins build_slug_to_line that put elite_ele_archer under
    # `elephant`) from sticking around when the classification changes.
    # Scope: only land-line score_types (we own those); naval/siege rows
    # written by other pipelines are untouched.
    LAND_SCORE_TYPES = ROLE_SCORE_TYPES + tuple(COMPOSITE_WEIGHTS.keys())
    land_score_phs = ",".join("?" for _ in LAND_SCORE_TYPES)
    for (line, civ, slug), _st_map in out.items():
        cur.execute(
            f"DELETE FROM battle_scores WHERE age=? AND civ_name=? "
            f"AND unit_slug=? AND line_slug != ? AND build_number=? "
            f"AND score_type IN ({land_score_phs})",
            (age_lower, civ, slug, line, build_number) + LAND_SCORE_TYPES,
        )

    inserts = 0
    for (line, st), entries in by_line_type.items():
        for civ, slug, _ in entries:
            cur.execute(
                "DELETE FROM battle_scores WHERE line_slug=? AND age=? "
                "AND civ_name=? AND unit_slug=? AND score_type=? AND build_number=?",
                (line, age_lower, civ, slug, st, build_number),
            )
        entries.sort(key=lambda e: -e[2])
        sorted_vals = sorted(e[2] for e in entries)
        median_val = sorted_vals[len(sorted_vals) // 2] if sorted_vals else 0
        for rank_idx, (civ, slug, val) in enumerate(entries, start=1):
            cur.execute("""
                INSERT INTO battle_scores
                (line_slug, age, civ_name, unit_slug, score_type, score_value,
                 rank, median_delta, build_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (line, age_lower, civ, slug, st, round(val, 1),
                  rank_idx, round(val - median_val, 1), build_number))
            inserts += 1

    dconn.commit()
    mconn.close(); rconn.close(); dconn.close()
    return inserts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--age", default="imperial")
    parser.add_argument("--matchup-db", dest="matchup_db", default=MATCHUP_DB_PATH,
                        help="Path to the matchup DB to derive from "
                             "(default: webapp/matchup_db.db).")
    parser.add_argument("--build", dest="build", default=None,
                        help="Build number to tag rows with (default: current).")
    args = parser.parse_args()
    n = compute_and_write_rankings(matchup_db_path=args.matchup_db,
                                   age=args.age.capitalize(),
                                   build_number=args.build)
    print(f"Inserted {n} rows into derived_data.battle_scores")


if __name__ == "__main__":
    main()
