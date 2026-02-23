"""
Batch-generate matchup advisor combos for every civ pair.

Runs get_matchup_sims() for each unique civ pair, then ports the frontend
top-unit / sidekick / gold-combo ranking logic to Python, storing results
in a SQLite database for easy querying.

Usage:
    cd webapp && python3 generate_matchup_db.py

Output:
    webapp/matchup_combos.db
"""

import itertools
import json
import os
import sqlite3
import sys
import time

from best_units import get_matchup_sims, load_civ_power_units

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "matchup_combos.db")

# All 50 civs — authoritative list from app.py ORIGINAL_13_CIVS
CIVS = [
    "Armenians", "Aztecs", "Bengalis", "Berbers", "Bohemians",
    "Britons", "Bulgarians", "Burgundians", "Burmese", "Byzantines",
    "Celts", "Chinese", "Cumans", "Dravidians", "Ethiopians",
    "Franks", "Georgians", "Goths", "Gurjaras", "Hindustanis",
    "Huns", "Incas", "Italians", "Japanese", "Jurchens",
    "Khitans", "Khmer", "Koreans", "Lithuanians", "Magyars",
    "Malay", "Malians", "Mayans", "Mongols", "Persians",
    "Poles", "Portuguese", "Romans", "Saracens", "Shu",
    "Sicilians", "Slavs", "Spanish", "Tatars", "Teutons",
    "Turks", "Vietnamese", "Vikings", "Wei", "Wu",
]

SIEGE_LINES = {"ram", "bombard_cannon", "trebuchet"}

# ---------------------------------------------------------------------------
# Port of JS ranking logic to Python
# ---------------------------------------------------------------------------


def _collect_all_units(power_units):
    """Collect all non-siege unit entries from power_units structure."""
    units = []
    for col_key in ("cavalry", "ranged", "infantry"):
        col_data = power_units.get(col_key, {})
        for _line_slug, entries in col_data.items():
            if not entries:
                continue
            for entry in entries:
                units.append(entry)
    return units


def _get_gold_slugs(units):
    """Return set of unit_slugs that cost gold > 0."""
    gold = set()
    for u in units:
        stats = u.get("stats")
        if stats and stats.get("cost_gold", 0) > 0:
            gold.add(u["unit_slug"])
    return gold


def _compute_top_units(side_key, units_by_slug, opp_gold_slugs, opp_side_key,
                       my_gold_slugs, sim_data):
    """Rank units by weighted score. Port of JS _computeTopUnits."""
    side_data = sim_data.get(side_key, {})
    opp_data = sim_data.get(opp_side_key, {})
    if not side_data or not opp_data:
        return []

    # Step 1: Opponent strength — how many of MY gold units each opp unit beats
    opp_strength = {}
    for opp_slug in opp_gold_slugs:
        od = opp_data.get(opp_slug, {})
        opp_wins = od.get("wins", [])
        opp_strength[opp_slug] = len([w for w in opp_wins if w in my_gold_slugs])

    # Step 2: Score each of my units
    ranked = []
    for slug, d in side_data.items():
        entry = units_by_slug.get(slug)
        if not entry:
            continue

        wins = d.get("wins", [])
        pop_wins = d.get("pop_wins", [])
        eco_wins = d.get("eco_wins", [])

        gold_wins = [w for w in wins if w in opp_gold_slugs]
        gold_pop_wins = [w for w in pop_wins if w in opp_gold_slugs]
        gold_eco_wins = [w for w in eco_wins if w in opp_gold_slugs]

        score = 0
        for w in gold_wins:
            score += 3 * opp_strength.get(w, 0)
        for w in gold_pop_wins:
            score += 1 * opp_strength.get(w, 0)
        for w in gold_eco_wins:
            score += 1 * opp_strength.get(w, 0)

        if score == 0 and len(gold_wins) == 0:
            continue

        ranked.append({
            "slug": slug,
            "entry": entry,
            "goldWins": gold_wins,
            "goldPopWins": gold_pop_wins,
            "goldEcoWins": gold_eco_wins,
            "percentile": entry.get("percentile", 0),
            "losses": d.get("losses", []),
            "score": score,
        })

    ranked.sort(key=lambda x: (-x["score"], -x["percentile"]))
    return ranked[:2]


def _compute_sidekicks(top_item, side_key, units_by_slug, opp_gold_slugs, sim_data):
    """Find top 2 complementary trash sidekicks. Port of JS _computeSidekicks."""
    side_data = sim_data.get(side_key, {})
    if not side_data:
        return []

    top_stats = top_item["entry"].get("stats", {})
    top_is_gold = bool(top_stats and top_stats.get("cost_gold", 0) > 0)

    top_losses = set(l for l in top_item.get("losses", []) if l in opp_gold_slugs)
    top_draws = set(top_item.get("goldPopWins", [])) | set(top_item.get("goldEcoWins", []))
    all_weaknesses = top_losses | top_draws

    if not all_weaknesses:
        return []

    ranked = []
    for slug, d in side_data.items():
        entry = units_by_slug.get(slug)
        if not entry or slug == top_item["slug"]:
            continue

        sk_stats = entry.get("stats", {})
        is_gold = bool(sk_stats and sk_stats.get("cost_gold", 0) > 0)
        if is_gold == top_is_gold:
            continue  # Must be opposite resource type

        sk_wins = set(d.get("wins", []))
        sk_draws = set(d.get("pop_wins", [])) | set(d.get("eco_wins", []))

        score = 0
        covered = []

        for opp in top_losses:
            if opp in sk_wins:
                score += 3; covered.append(opp)
            elif opp in sk_draws:
                score += 2; covered.append(opp)

        for opp in top_draws:
            if opp in sk_wins:
                score += 2; covered.append(opp)
            elif opp in sk_draws:
                score += 1; covered.append(opp)

        if score == 0:
            continue

        covered_set = set(covered)
        gap = [s for s in all_weaknesses if s not in covered_set]

        ranked.append({
            "slug": slug,
            "entry": entry,
            "score": score,
            "percentile": entry.get("percentile", 0),
            "covered": covered,
            "gap": gap,
            "totalWeaknesses": len(all_weaknesses),
        })

    ranked.sort(key=lambda x: (-x["score"], -x["percentile"]))
    return ranked[:2]


def _compute_gold_combo(top_item, side_key, units_by_slug, opp_gold_slugs, sim_data):
    """Find best gold unit partner. Port of JS _computeGoldCombo."""
    side_data = sim_data.get(side_key, {})
    if not side_data:
        return None

    top_losses = set(l for l in top_item.get("losses", []) if l in opp_gold_slugs)
    top_draws = set(top_item.get("goldPopWins", [])) | set(top_item.get("goldEcoWins", []))
    all_weaknesses = top_losses | top_draws

    if not all_weaknesses:
        return None

    ranked = []
    for slug, d in side_data.items():
        entry = units_by_slug.get(slug)
        if not entry or slug == top_item["slug"]:
            continue

        p_stats = entry.get("stats", {})
        is_gold = bool(p_stats and p_stats.get("cost_gold", 0) > 0)
        if not is_gold:
            continue  # Partner must be gold

        p_wins = set(d.get("wins", []))
        p_draws = set(d.get("pop_wins", [])) | set(d.get("eco_wins", []))

        score = 0
        covered = []

        for opp in top_losses:
            if opp in p_wins:
                score += 3; covered.append(opp)
            elif opp in p_draws:
                score += 2; covered.append(opp)

        for opp in top_draws:
            if opp in p_wins:
                score += 2; covered.append(opp)
            elif opp in p_draws:
                score += 1; covered.append(opp)

        if score == 0:
            continue

        covered_set = set(covered)
        gap = [s for s in all_weaknesses if s not in covered_set]

        ranked.append({
            "slug": slug,
            "entry": entry,
            "score": score,
            "percentile": entry.get("percentile", 0),
            "covered": covered,
            "gap": gap,
            "totalWeaknesses": len(all_weaknesses),
        })

    ranked.sort(key=lambda x: (-x["score"], -x["percentile"]))
    return ranked[0] if ranked else None


def _is_perfect(item, sidekicks, opp_gold_slugs):
    """Check if a top unit + sidekick combo is perfect (no gap)."""
    if not sidekicks:
        # No sidekick = unit beats everything solo. Verify.
        gold_losses = [l for l in item.get("losses", []) if l in opp_gold_slugs]
        gold_pop_wins = item.get("goldPopWins", [])
        gold_eco_wins = item.get("goldEcoWins", [])
        return (len(gold_losses) == 0 and len(gold_pop_wins) == 0
                and len(gold_eco_wins) == 0)
    return sidekicks[0]["gap"] == [] or len(sidekicks[0]["gap"]) == 0


def analyze_matchup_side(side_key, opp_side_key, units_by_slug, opp_gold_slugs,
                         my_gold_slugs, sim_data, name_map):
    """
    Compute top combos for one side of a matchup.

    Returns a list of combo dicts, each with:
        combo_type: 'top_sidekick' or 'gold_gold'
        combo_rank: 1-based rank
        is_perfect: whether gap is empty
        top_unit_slug, top_unit_name
        partner_slug, partner_name (sidekick or gold partner)
        partner_type: 'trash_sidekick' or 'gold_partner'
        gap: list of uncovered opponent slugs
        gap_names: list of uncovered opponent display names
        top_unit_score: ranking score of the top unit
        partner_score: scoring of the sidekick/partner
    """
    top_units = _compute_top_units(
        side_key, units_by_slug, opp_gold_slugs, opp_side_key,
        my_gold_slugs, sim_data
    )

    if not top_units:
        return []

    # Compute sidekicks for each top unit
    top_with_sidekicks = []
    for item in top_units:
        sidekicks = _compute_sidekicks(item, side_key, units_by_slug,
                                        opp_gold_slugs, sim_data)
        top_with_sidekicks.append({"item": item, "sidekicks": sidekicks})

    # Filter sidekicks: if best sidekick has no gap, drop alt with gap
    for tw in top_with_sidekicks:
        sks = tw["sidekicks"]
        if len(sks) >= 2 and len(sks[0]["gap"]) == 0 and len(sks[1]["gap"]) > 0:
            tw["sidekicks"] = [sks[0]]

    # Filter top units: if any combo is perfect, keep only perfects
    any_perfect = any(
        _is_perfect(tw["item"], tw["sidekicks"], opp_gold_slugs)
        for tw in top_with_sidekicks
    )
    if any_perfect:
        filtered = [tw for tw in top_with_sidekicks
                    if _is_perfect(tw["item"], tw["sidekicks"], opp_gold_slugs)]
    else:
        filtered = top_with_sidekicks

    # Check if all combos have gaps (need gold combo)
    all_have_gaps = all(
        (not tw["sidekicks"]) or len(tw["sidekicks"][0]["gap"]) > 0
        for tw in filtered
    )
    # But if no sidekicks AND unit is perfect solo, that's NOT a gap
    if all_have_gaps:
        # Recheck: a unit with no sidekicks that beats everything is fine
        truly_gapped = all(
            not _is_perfect(tw["item"], tw["sidekicks"], opp_gold_slugs)
            for tw in filtered
        )
        all_have_gaps = truly_gapped

    combos = []

    # Gold combo card (shown first if all have gaps)
    if all_have_gaps:
        gold_combo = _compute_gold_combo(
            top_units[0], side_key, units_by_slug, opp_gold_slugs, sim_data
        )
        if gold_combo:
            combos.append({
                "combo_type": "gold_gold",
                "combo_rank": 1,
                "is_perfect": len(gold_combo["gap"]) == 0,
                "top_unit_slug": top_units[0]["slug"],
                "top_unit_name": name_map.get(top_units[0]["slug"], top_units[0]["slug"]),
                "partner_slug": gold_combo["slug"],
                "partner_name": name_map.get(gold_combo["slug"], gold_combo["slug"]),
                "partner_type": "gold_partner",
                "gap": gold_combo["gap"],
                "gap_names": [name_map.get(g, g) for g in gold_combo["gap"]],
                "top_unit_score": top_units[0]["score"],
                "partner_score": gold_combo["score"],
            })

    # Top unit + sidekick cards
    for rank_idx, tw in enumerate(filtered):
        item = tw["item"]
        sidekicks = tw["sidekicks"]

        for sk_idx, sk in enumerate(sidekicks):
            combos.append({
                "combo_type": "top_sidekick",
                "combo_rank": rank_idx + 1,
                "sidekick_rank": sk_idx + 1,
                "is_perfect": len(sk["gap"]) == 0,
                "top_unit_slug": item["slug"],
                "top_unit_name": name_map.get(item["slug"], item["slug"]),
                "partner_slug": sk["slug"],
                "partner_name": name_map.get(sk["slug"], sk["slug"]),
                "partner_type": "trash_sidekick",
                "gap": sk["gap"],
                "gap_names": [name_map.get(g, g) for g in sk["gap"]],
                "top_unit_score": item["score"],
                "partner_score": sk["score"],
            })

        # Unit with no sidekicks (beats everything solo or has no trash that helps)
        if not sidekicks:
            perfect = _is_perfect(item, sidekicks, opp_gold_slugs)
            combos.append({
                "combo_type": "top_sidekick",
                "combo_rank": rank_idx + 1,
                "sidekick_rank": 0,
                "is_perfect": perfect,
                "top_unit_slug": item["slug"],
                "top_unit_name": name_map.get(item["slug"], item["slug"]),
                "partner_slug": None,
                "partner_name": None,
                "partner_type": "none",
                "gap": [],
                "gap_names": [],
                "top_unit_score": item["score"],
                "partner_score": 0,
            })

    return combos


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def create_db():
    """Create the matchup_combos database."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        DROP TABLE IF EXISTS matchup_combos;

        CREATE TABLE matchup_combos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            civ TEXT NOT NULL,
            opponent TEXT NOT NULL,
            combo_type TEXT NOT NULL,        -- 'top_sidekick' or 'gold_gold'
            combo_rank INTEGER NOT NULL,     -- rank of the top unit (1 or 2)
            sidekick_rank INTEGER DEFAULT 0, -- rank of the sidekick (1 or 2, 0 if gold_gold or solo)
            is_perfect INTEGER NOT NULL DEFAULT 0,
            top_unit_slug TEXT NOT NULL,
            top_unit_name TEXT NOT NULL,
            partner_slug TEXT,               -- sidekick or gold partner
            partner_name TEXT,
            partner_type TEXT NOT NULL,       -- 'trash_sidekick', 'gold_partner', 'none'
            gap TEXT,                        -- JSON array of uncovered opponent slugs
            gap_names TEXT,                  -- JSON array of uncovered opponent names
            gap_count INTEGER NOT NULL DEFAULT 0,
            top_unit_score REAL NOT NULL DEFAULT 0,
            partner_score REAL NOT NULL DEFAULT 0
        );

        CREATE INDEX idx_civ ON matchup_combos(civ);
        CREATE INDEX idx_opponent ON matchup_combos(opponent);
        CREATE INDEX idx_civ_opponent ON matchup_combos(civ, opponent);
        CREATE INDEX idx_top_unit ON matchup_combos(top_unit_slug);
        CREATE INDEX idx_partner ON matchup_combos(partner_slug);
        CREATE INDEX idx_combo_type ON matchup_combos(combo_type);
        CREATE INDEX idx_perfect ON matchup_combos(is_perfect);
    """)
    conn.commit()
    return conn


def insert_combos(conn, civ, opponent, combos):
    """Insert combo results for one civ/opponent pair."""
    for c in combos:
        conn.execute("""
            INSERT INTO matchup_combos
            (civ, opponent, combo_type, combo_rank, sidekick_rank, is_perfect,
             top_unit_slug, top_unit_name, partner_slug, partner_name,
             partner_type, gap, gap_names, gap_count,
             top_unit_score, partner_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            civ, opponent,
            c["combo_type"], c["combo_rank"], c.get("sidekick_rank", 0),
            1 if c["is_perfect"] else 0,
            c["top_unit_slug"], c["top_unit_name"],
            c.get("partner_slug"), c.get("partner_name"),
            c["partner_type"],
            json.dumps(c["gap"]), json.dumps(c["gap_names"]),
            len(c["gap"]),
            c["top_unit_score"], c["partner_score"],
        ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("Loading civ power units...")
    power_data = load_civ_power_units()
    if not power_data:
        print("ERROR: civ_power_units.json not found. Run: python3 best_units.py")
        sys.exit(1)

    # Validate civs
    available = [c for c in CIVS if c in power_data]
    missing = [c for c in CIVS if c not in power_data]
    if missing:
        print(f"WARNING: {len(missing)} civs not in power data: {missing}")
    print(f"Processing {len(available)} civs ({len(available) * (len(available) - 1) // 2} unique pairs)")

    conn = create_db()
    total_pairs = len(available) * (len(available) - 1) // 2
    done = 0
    start = time.time()

    for civ_a, civ_b in itertools.combinations(available, 2):
        # Run simulations (returns data for both sides)
        sim_result = get_matchup_sims(civ_a, civ_b, age="imperial")
        if "error" in sim_result:
            print(f"  SKIP {civ_a} vs {civ_b}: {sim_result['error']}")
            continue

        sim_data = {
            "left": sim_result["left"],
            "right": sim_result["right"],
        }
        name_map = sim_result.get("name_map", {})

        # Get power_units for each side
        pu_left = power_data[civ_a].get("imperial", {}).get("power_units", {})
        pu_right = power_data[civ_b].get("imperial", {}).get("power_units", {})

        left_units = _collect_all_units(pu_left)
        right_units = _collect_all_units(pu_right)

        left_gold_slugs = _get_gold_slugs(left_units)
        right_gold_slugs = _get_gold_slugs(right_units)

        left_by_slug = {u["unit_slug"]: u for u in left_units}
        right_by_slug = {u["unit_slug"]: u for u in right_units}

        # Analyze left side (civ_a's combos vs civ_b)
        left_combos = analyze_matchup_side(
            "left", "right", left_by_slug, right_gold_slugs,
            left_gold_slugs, sim_data, name_map
        )
        insert_combos(conn, civ_a, civ_b, left_combos)

        # Analyze right side (civ_b's combos vs civ_a)
        right_combos = analyze_matchup_side(
            "right", "left", right_by_slug, left_gold_slugs,
            right_gold_slugs, sim_data, name_map
        )
        insert_combos(conn, civ_b, civ_a, right_combos)

        done += 1
        if done % 50 == 0 or done == total_pairs:
            elapsed = time.time() - start
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total_pairs - done) / rate if rate > 0 else 0
            print(f"  {done}/{total_pairs} pairs ({elapsed:.0f}s, ~{eta:.0f}s remaining)")
            conn.commit()

    conn.commit()

    # Print summary stats
    cur = conn.cursor()
    total_rows = cur.execute("SELECT COUNT(*) FROM matchup_combos").fetchone()[0]
    perfect = cur.execute("SELECT COUNT(*) FROM matchup_combos WHERE is_perfect=1").fetchone()[0]
    gold_gold = cur.execute("SELECT COUNT(*) FROM matchup_combos WHERE combo_type='gold_gold'").fetchone()[0]
    top_sk = cur.execute("SELECT COUNT(*) FROM matchup_combos WHERE combo_type='top_sidekick'").fetchone()[0]

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Wrote {DB_PATH}")
    print(f"  {total_rows} total rows")
    print(f"  {top_sk} top+sidekick combos ({perfect} perfect)")
    print(f"  {gold_gold} gold+gold combos")

    # Top 10 most common top units across all matchups
    print("\nMost common top units (all civs):")
    rows = cur.execute("""
        SELECT top_unit_name, COUNT(*) as cnt, COUNT(DISTINCT civ) as civ_cnt
        FROM matchup_combos
        WHERE combo_rank = 1 AND combo_type = 'top_sidekick'
        GROUP BY top_unit_slug
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0]}: {r[1]} matchups across {r[2]} civs")

    conn.close()


if __name__ == "__main__":
    main()
