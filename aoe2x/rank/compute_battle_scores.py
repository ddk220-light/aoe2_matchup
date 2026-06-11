"""Role: legacy — RETIRED as a pipeline; survives as a scoring LIBRARY.

Do NOT run this as a script. The battle_scores.json chain it used to produce
is retired: rankings are served from derived_data.db (built by the derive_*
scripts from the matchup baseline), and webapp/battle_scores.json is a
342-byte stub.

Still imported as a library:
  - derive_siege_scores.py uses compute_siege_antibuilding_scores()
  - tests/test_infantry_scoring.py, test_naval_rankings.py and
    test_siege_scoring.py exercise the infantry/naval/siege scoring helpers.

Phase-3 plan (docs/architecture/improvements.md): extract the scoring
functions into a lib and archive the rest.
"""

import argparse
import hashlib
import json
import math
import os
import sqlite3
import time

from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
from aoe2x.sim.simulation import prepare_combat_unit, simulate_battle
from aoe2x.sim.unit_lines import UNIT_LINES, CIV_MISSING_UNITS

from aoe2x.paths import WEBAPP_DIR as _DATA_DIR

DB_PATH = os.path.join(str(_DATA_DIR), "aoe2_reference.db")
CACHE_PATH = os.path.join(str(_DATA_DIR), "battle_cache.json")
CACHE_VERSION = 11

BENCHMARKS = [
    # Resource-based (3000 res) — used for RES
    ("vs_champ", "Chinese", "champion", "Imperial"),
    ("vs_paladin", "Franks", "paladin", "Imperial"),
    ("vs_arb", "Chinese", "arbalester", "Imperial"),
    # Pop-based (30v30 fixed count) — used for PES
    ("pop_vs_champ", "Chinese", "champion", "Imperial"),
    ("pop_vs_paladin", "Franks", "paladin", "Imperial"),
    ("pop_vs_arb", "Chinese", "arbalester", "Imperial"),
]

# Fields excluded from fingerprint (display-only, not affecting simulation)
_DISPLAY_FIELDS = {"slug", "unit_name", "unit_category", "paired_unit_slug"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _unit_fingerprint(combat_unit):
    """MD5 hash of simulation-relevant fields in a combat_unit dict. 12 hex chars."""
    d = {k: v for k, v in combat_unit.items() if k not in _DISPLAY_FIELDS}
    raw = json.dumps(d, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _sim_engine_hash():
    """MD5 hash of simulation.py file contents. 12 hex chars."""
    sim_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "sim", "simulation.py")
    with open(sim_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:12]


def load_cache():
    """Load battle_cache.json. Returns None if missing, corrupt, or version mismatch."""
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r") as f:
            cache = json.load(f)
        if cache.get("version") != CACHE_VERSION:
            return None
        return cache
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(cache, current_fps):
    """Write cache with garbage collection (only keep entries referencing live fingerprints)."""
    live_fps = set(current_fps.values())

    # GC pairwise: keep only entries where both hashes are still live
    clean_pairwise = {}
    for key, val in cache.get("pairwise", {}).items():
        parts = key.split(":")
        if len(parts) == 3 and parts[0] in live_fps and parts[1] in live_fps:
            clean_pairwise[key] = val
    cache["pairwise"] = clean_pairwise

    # GC benchmarks: keep only entries where unit hash is still live
    clean_bench = {}
    for key, val in cache.get("benchmarks", {}).items():
        parts = key.split(":")
        if len(parts) >= 2 and parts[0] in live_fps:
            clean_bench[key] = val
    cache["benchmarks"] = clean_bench

    cache["unit_hashes"] = current_fps
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Simulation helpers (extracted from round-robin/benchmark loops)
# ---------------------------------------------------------------------------


def _simulate_pair(unit_i, unit_j, is_imperial):
    """Run 3-scenario battle between two units. Returns [score_30v30, score_3k, score_5k]
    from unit_i's perspective (-100..+100)."""
    ci = calc_weighted_cost(
        unit_i["cost_food"], unit_i["cost_wood"], unit_i["cost_gold"], is_imperial
    )
    cj = calc_weighted_cost(
        unit_j["cost_food"], unit_j["cost_wood"], unit_j["cost_gold"], is_imperial
    )

    # Scenario 1: 30v30
    w1, _, _, hp1_1, hp2_1 = simulate_battle(
        unit_i, unit_j, 0, fixed_count=30, return_hp=True
    )

    # Scenario 2: 3000 resources
    w2, _, _, hp1_2, hp2_2 = simulate_battle(
        unit_i, unit_j, 3000, cost1_override=ci, cost2_override=cj, return_hp=True
    )

    # Scenario 3: 5000 resources with upgrades
    upg_i = calc_weighted_cost(
        unit_i["upgrade_cost_food"],
        unit_i["upgrade_cost_wood"],
        unit_i["upgrade_cost_gold"],
        is_imperial,
    )
    upg_j = calc_weighted_cost(
        unit_j["upgrade_cost_food"],
        unit_j["upgrade_cost_wood"],
        unit_j["upgrade_cost_gold"],
        is_imperial,
    )
    budget_i = max(ci, 5000 - upg_i)
    budget_j = max(cj, 5000 - upg_j)
    adj_cj = max(1, int(budget_i * cj / budget_j)) if budget_j > 0 else cj
    w3, _, _, hp1_3, hp2_3 = simulate_battle(
        unit_i,
        unit_j,
        budget_i,
        cost1_override=ci,
        cost2_override=adj_cj,
        return_hp=True,
    )

    scores = []
    for w, h1, h2 in [(w1, hp1_1, hp2_1), (w2, hp1_2, hp2_2), (w3, hp1_3, hp2_3)]:
        scores.append(_hp_score(w, h1, h2))
    return scores


def _simulate_benchmark(unit, bench_unit, is_imperial):
    """Run one benchmark battle. Returns float score (-100..+100) from unit's perspective."""
    unit_cost = calc_weighted_cost(
        unit["cost_food"], unit["cost_wood"], unit["cost_gold"], is_imperial
    )
    bench_cost = calc_weighted_cost(
        bench_unit["cost_food"], bench_unit["cost_wood"], bench_unit["cost_gold"], True
    )
    winner, _, _, hp_pct1, hp_pct2 = simulate_battle(
        unit,
        bench_unit,
        3000,
        cost1_override=unit_cost,
        cost2_override=bench_cost,
        return_hp=True,
    )
    if winner == 1:
        return round(hp_pct1 * 100, 1)
    elif winner == 2:
        return round(-hp_pct2 * 100, 1)
    return 0.0


def _simulate_pop_benchmark(unit, bench_unit, is_imperial):
    """Run one 30v30 fixed-count benchmark battle. Returns -100..+100 from unit's perspective."""
    winner, _, _, hp_pct1, hp_pct2 = simulate_battle(
        unit, bench_unit, 0, fixed_count=30, return_hp=True
    )
    return round(_hp_score(winner, hp_pct1, hp_pct2), 1)


# ---------------------------------------------------------------------------
# DB / combat dict building
# ---------------------------------------------------------------------------
# build_combat_dict_from_ref() is imported from combat_unit_loader


def build_combat_dict(rc, row):
    """Thin wrapper kept for call-site compatibility; delegates to shared loader."""
    return build_combat_dict_from_ref(row)


def calc_weighted_cost(food, wood, gold, is_imperial):
    # Keep in lockstep with simulation_real.weighted_cost — gold is the
    # scarcest resource, wood the most abundant.
    cost = 0.7 * (wood or 0) + (food or 0) + 1.5 * (gold or 0)
    return int(cost) if cost > 0 else 100


def _apply_speed_weighting(
    all_scores,
    score_keys,
    scope="pool",
    line_groups=None,
    multiplier_keys=("_speed",),
):
    """Multiply composite scores by one or more stat multipliers, then re-normalize to 0-100.

    Args:
        all_scores: dict {sk: {score_key: value, "_speed": float, ...}}
        score_keys: list of score keys to apply weighting to
        scope: "pool" = normalize across all units; "per_line" = normalize per line group
        line_groups: dict {line_slug: [sk, ...]} — required when scope="per_line"
        multiplier_keys: tuple of stat keys (e.g. "_speed", "_range") to multiply
            into each score before re-normalization. Default = ("_speed",).
    """

    def _multiplier(scores):
        m = 1.0
        for mk in multiplier_keys:
            m *= scores.get(mk, 1.0)
        return m

    if scope == "per_line" and line_groups:
        for key in score_keys:
            for line, sks in line_groups.items():
                weighted = {sk: all_scores[sk][key] * _multiplier(all_scores[sk]) for sk in sks}
                vals = list(weighted.values())
                lo, hi = min(vals), max(vals)
                span = hi - lo if hi != lo else 1
                for sk in sks:
                    all_scores[sk][key] = round((weighted[sk] - lo) / span * 100, 1)
    else:
        for key in score_keys:
            weighted = {sk: scores[key] * _multiplier(scores) for sk, scores in all_scores.items()}
            vals = list(weighted.values())
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1
            for sk in all_scores:
                all_scores[sk][key] = round((weighted[sk] - lo) / span * 100, 1)


def build_line_units(line_slug, age):
    """Build combat-ready units for a line + age."""
    line = UNIT_LINES[line_slug]
    is_castle = age == "castle"
    db_age = "Castle" if is_castle else "Imperial"

    # Support multi-slug lines (castle_slugs/imperial_slugs) or single slug
    if is_castle:
        std_slugs = line.get(
            "castle_slugs", [line["castle_slug"]] if line["castle_slug"] else []
        )
    else:
        std_slugs = line.get(
            "imperial_slugs", [line["imperial_slug"]] if line["imperial_slug"] else []
        )

    conn = get_db()
    rc = conn.cursor()
    units = []

    for std_slug in std_slugs:
        rc.execute(
            "SELECT * FROM ref_units WHERE unit_slug=? AND age=?", (std_slug, db_age)
        )
        for row in rc.fetchall():
            if (row["civ_name"], std_slug) in CIV_MISSING_UNITS:
                continue
            cd = build_combat_dict(rc, row)
            cu = prepare_combat_unit(cd)
            cu["upgrade_cost_food"] = row["upgrade_cost_food"] or 0
            cu["upgrade_cost_wood"] = row["upgrade_cost_wood"] or 0
            cu["upgrade_cost_gold"] = row["upgrade_cost_gold"] or 0
            units.append(
                {
                    "civ_name": row["civ_name"],
                    "unit_slug": row["unit_slug"],
                    "combat_unit": cu,
                }
            )

    # Fetch extra standard units (e.g. Elephant Archer in elephant line, Hand Cannoneer in archer line)
    if is_castle:
        for extra_slug in line.get("extra_castle_slugs", []):
            rc.execute(
                "SELECT * FROM ref_units WHERE unit_slug=? AND age=?",
                (extra_slug, "Castle"),
            )
            for row in rc.fetchall():
                if (row["civ_name"], extra_slug) in CIV_MISSING_UNITS:
                    continue
                cd = build_combat_dict(rc, row)
                cu = prepare_combat_unit(cd)
                cu["upgrade_cost_food"] = row["upgrade_cost_food"] or 0
                cu["upgrade_cost_wood"] = row["upgrade_cost_wood"] or 0
                cu["upgrade_cost_gold"] = row["upgrade_cost_gold"] or 0
                units.append(
                    {
                        "civ_name": row["civ_name"],
                        "unit_slug": row["unit_slug"],
                        "combat_unit": cu,
                    }
                )
    else:
        for extra_slug in line.get("extra_imperial_slugs", []):
            rc.execute(
                "SELECT * FROM ref_units WHERE unit_slug=? AND age=?",
                (extra_slug, "Imperial"),
            )
            for row in rc.fetchall():
                if (row["civ_name"], extra_slug) in CIV_MISSING_UNITS:
                    continue
                cd = build_combat_dict(rc, row)
                cu = prepare_combat_unit(cd)
                cu["upgrade_cost_food"] = row["upgrade_cost_food"] or 0
                cu["upgrade_cost_wood"] = row["upgrade_cost_wood"] or 0
                cu["upgrade_cost_gold"] = row["upgrade_cost_gold"] or 0
                units.append(
                    {
                        "civ_name": row["civ_name"],
                        "unit_slug": row["unit_slug"],
                        "combat_unit": cu,
                    }
                )

    for civ_name, entries in line.get("unique_units", {}).items():
        entries = entries if isinstance(entries, list) else [entries]
        for castle_uu, imperial_uu in entries:
            uu_slug = castle_uu if is_castle else imperial_uu
            if not uu_slug:
                continue
            rc.execute(
                "SELECT * FROM ref_units WHERE unit_slug=? AND civ_name=? AND age=?",
                (uu_slug, civ_name, db_age),
            )
            row = rc.fetchone()
            if row:
                cd = build_combat_dict(rc, row)
                cu = prepare_combat_unit(cd)
                cu["upgrade_cost_food"] = row["upgrade_cost_food"] or 0
                cu["upgrade_cost_wood"] = row["upgrade_cost_wood"] or 0
                cu["upgrade_cost_gold"] = row["upgrade_cost_gold"] or 0
                units.append(
                    {"civ_name": civ_name, "unit_slug": uu_slug, "combat_unit": cu}
                )

    conn.close()
    return units


def _hp_score(winner, hp_pct1, hp_pct2):
    """Convert battle result to -100..+100 HP score for unit 1.
    +100 = unit1 won with 100% HP; -100 = unit2 won with 100% HP; 0 = draw."""
    if winner == 1:
        return hp_pct1 * 100
    elif winner == 2:
        return -hp_pct2 * 100
    return 0.0


def compute_round_robin(line_slug, age, pairwise_cache, unit_fps):
    """Round-robin battles with caching. Returns (scores_dict, hits, misses).
    Scores are -100..+100 (average HP% across all opponents)."""
    is_imperial = age == "imperial"
    units = build_line_units(line_slug, age)
    n = len(units)
    if n < 2:
        return {}, 0, 0

    keys = [(u["civ_name"], u["unit_slug"]) for u in units]
    fps = []
    for u in units:
        fp_key = f"{u['civ_name']}|{u['unit_slug']}|{age}"
        fps.append(unit_fps.get(fp_key, "unknown"))

    hp_totals = {k: [0.0, 0.0, 0.0] for k in keys}
    hits = 0
    misses = 0

    for i in range(n):
        for j in range(i + 1, n):
            fp_i, fp_j = fps[i], fps[j]
            # Build sorted cache key so A:B == B:A
            if fp_i <= fp_j:
                cache_key = f"{fp_i}:{fp_j}:{age}"
                swapped = False
            else:
                cache_key = f"{fp_j}:{fp_i}:{age}"
                swapped = True

            if cache_key in pairwise_cache:
                pair_scores = pairwise_cache[cache_key]
                hits += 1
            else:
                pair_scores = _simulate_pair(
                    units[i]["combat_unit"], units[j]["combat_unit"], is_imperial
                )
                # Cache stores scores from fp_first's perspective.
                # Simulation returns scores from units[i]'s perspective.
                # If swapped (fp_j < fp_i), negate before caching.
                if swapped:
                    pair_scores = [-s for s in pair_scores]
                pairwise_cache[cache_key] = pair_scores
                misses += 1

            # pair_scores are from fp_first's perspective.
            # If swapped, fp_first is fp_j (= units[j]), so negate for units[i].
            for idx in range(3):
                s = pair_scores[idx]
                if swapped:
                    s = -s
                hp_totals[keys[i]][idx] += s
                hp_totals[keys[j]][idx] -= s

    opponents = n - 1
    scores = {}
    for k in keys:
        sk = f"{k[0]}|{k[1]}"
        scores[sk] = {
            "score_30v30": round(hp_totals[k][0] / opponents, 1),
            "score_3k": round(hp_totals[k][1] / opponents, 1),
            "score_5k": round(hp_totals[k][2] / opponents, 1),
        }
    return scores, hits, misses


def compute_benchmarks(bench_units, bench_fps, benchmark_cache, unit_fps):
    """Pit every unit against benchmark opponents with caching.
    Returns (all_scores, hits, misses)."""
    all_scores = {}
    total_hits = 0
    total_misses = 0

    for line_slug, config in UNIT_LINES.items():
        if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS or line_slug in STABLE_LINE_SLUGS or line_slug in SIEGE_LINE_SLUGS or line_slug in HIDDEN_LINE_SLUGS or line_slug in NAVAL_LINE_SLUGS:
            continue  # infantry/archery/stable uses role-based scores from battle_scores table
        for age_key in ["castle", "imperial"]:
            std_slug = config.get(f"{age_key}_slug")
            multi_slugs = config.get(f"{age_key}_slugs", [])
            has_unique = bool(config.get("unique_units"))
            if not std_slug and not multi_slugs and not has_unique:
                continue

            units = build_line_units(line_slug, age_key)
            if not units:
                continue

            is_imperial = age_key == "imperial"
            line_key = f"{line_slug}|{age_key}"
            line_scores = {}

            for u in units:
                cu = u["combat_unit"]
                fp_key = f"{u['civ_name']}|{u['unit_slug']}|{age_key}"
                u_fp = unit_fps.get(fp_key, "unknown")
                scores = {}

                for bkey, bciv, bslug, bage in BENCHMARKS:
                    if bkey not in bench_units:
                        scores[bkey] = -1
                        continue

                    b_fp = bench_fps.get(bkey, "unknown")
                    cache_key = f"{u_fp}:{b_fp}:{bkey}:{age_key}"

                    if cache_key in benchmark_cache:
                        scores[bkey] = benchmark_cache[cache_key]
                        total_hits += 1
                    else:
                        if bkey.startswith("pop_"):
                            val = _simulate_pop_benchmark(
                                cu, bench_units[bkey], is_imperial
                            )
                        else:
                            val = _simulate_benchmark(
                                cu, bench_units[bkey], is_imperial
                            )
                        scores[bkey] = val
                        benchmark_cache[cache_key] = val
                        total_misses += 1

                sk = f"{u['civ_name']}|{u['unit_slug']}"
                line_scores[sk] = scores

            all_scores[line_key] = line_scores

    return all_scores, total_hits, total_misses


# ---------------------------------------------------------------------------
# Militia role-based scoring
# ---------------------------------------------------------------------------

MILITIA_ROLE_BENCHMARKS = {
    "imperial": [
        # (key, civ, slug, age, mode, param)
        # General Combat — 30v30 fixed count (pop-adjusted)
        ("gc_30v30_vs_paladin", "Spanish", "paladin", "Imperial", "pop", 30),
        ("gc_30v30_vs_arb", "Chinese", "arbalester", "Imperial", "pop", 30),
        ("gc_30v30_vs_champ", "Chinese", "champion", "Imperial", "pop", 30),
        # General Combat — 3K resources each
        ("gc_3k_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
        ("gc_3k_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
        ("gc_3k_vs_champ", "Chinese", "champion", "Imperial", "res", 3000),
        # Anti-Cav — 30v30 fixed count (pop-adjusted)
        ("ac_30v30_vs_battle_elephant", "Khmer", "elite_elephant", "Imperial", "pop", 30),
        ("ac_30v30_vs_heavy_camel", "Turks", "heavy_camel", "Imperial", "pop", 30),
        ("ac_30v30_vs_steppe_lancer", "Mongols", "elite_steppe", "Imperial", "pop", 30),
        # Anti-Cav — 3K resources each
        ("ac_3k_vs_battle_elephant", "Khmer", "elite_elephant", "Imperial", "res", 3000),
        ("ac_3k_vs_heavy_camel", "Turks", "heavy_camel", "Imperial", "res", 3000),
        ("ac_3k_vs_steppe_lancer", "Mongols", "elite_steppe", "Imperial", "res", 3000),
        # Anti-Trash — 30v30 fixed count (pop-adjusted)
        ("at_30v30_vs_halb", "Spanish", "halberdier", "Imperial", "pop", 30),
        ("at_30v30_vs_hussar", "Spanish", "hussar", "Imperial", "pop", 30),
        ("at_30v30_vs_elite_skirm", "Spanish", "imp_elite_skirm", "Imperial", "pop", 30),
        # Anti-Trash — 3K resources each
        ("at_3k_vs_halb", "Spanish", "halberdier", "Imperial", "res", 3000),
        ("at_3k_vs_hussar", "Spanish", "hussar", "Imperial", "res", 3000),
        ("at_3k_vs_elite_skirm", "Spanish", "imp_elite_skirm", "Imperial", "res", 3000),
    ],
    "castle": [
        # General Combat — 30v30 fixed count (pop-adjusted)
        ("gc_30v30_vs_paladin", "Spanish", "knight", "Castle", "pop", 30),
        ("gc_30v30_vs_arb", "Chinese", "crossbow", "Castle", "pop", 30),
        ("gc_30v30_vs_champ", "Chinese", "swordsmen", "Castle", "pop", 30),
        # General Combat — 3K resources each
        ("gc_3k_vs_paladin", "Spanish", "knight", "Castle", "res", 3000),
        ("gc_3k_vs_arb", "Chinese", "crossbow", "Castle", "res", 3000),
        ("gc_3k_vs_champ", "Chinese", "swordsmen", "Castle", "res", 3000),
        # Anti-Cav — 30v30 fixed count (pop-adjusted)
        ("ac_30v30_vs_battle_elephant", "Khmer", "elephant", "Castle", "pop", 30),
        ("ac_30v30_vs_heavy_camel", "Turks", "camel", "Castle", "pop", 30),
        ("ac_30v30_vs_steppe_lancer", "Mongols", "steppe_lancer", "Castle", "pop", 30),
        # Anti-Cav — 3K resources each
        ("ac_3k_vs_battle_elephant", "Khmer", "elephant", "Castle", "res", 3000),
        ("ac_3k_vs_heavy_camel", "Turks", "camel", "Castle", "res", 3000),
        ("ac_3k_vs_steppe_lancer", "Mongols", "steppe_lancer", "Castle", "res", 3000),
        # Anti-Trash — 30v30 fixed count (pop-adjusted)
        ("at_30v30_vs_halb", "Spanish", "pikeman", "Castle", "pop", 30),
        ("at_30v30_vs_hussar", "Spanish", "light_cav", "Castle", "pop", 30),
        ("at_30v30_vs_elite_skirm", "Spanish", "elite_skirm", "Castle", "pop", 30),
        # Anti-Trash — 3K resources each
        ("at_3k_vs_halb", "Spanish", "pikeman", "Castle", "res", 3000),
        ("at_3k_vs_hussar", "Spanish", "light_cav", "Castle", "res", 3000),
        ("at_3k_vs_elite_skirm", "Spanish", "elite_skirm", "Castle", "res", 3000),
    ],
}

DT = 0.1  # must match simulation.py DT
MAX_BATTLE_TIME = 250.0  # MAX_TICKS * DT


def _load_benchmark_unit(civ, slug, age):
    """Load a single benchmark unit from the reference DB."""
    conn = get_db()
    rc = conn.cursor()
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ, slug, age),
    )
    row = rc.fetchone()
    if not row:
        conn.close()
        return None
    cd = build_combat_dict(rc, row)
    cu = prepare_combat_unit(cd)
    conn.close()
    return cu


INFANTRY_LINE_SLUGS = ["militia", "spear", "shock_infantry"]

ARCHERY_LINE_SLUGS = ["archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"]

ARCHERY_ROLE_BENCHMARKS = {
    "imperial": [
        # General Combat — 30v30 fixed count (HP% scoring)
        ("gc_30v30_vs_paladin", "Spanish", "paladin", "Imperial", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_arb", "Chinese", "arbalester", "Imperial", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_champ", "Chinese", "champion", "Imperial", "fixed_hp", (30, 30)),
        # General Combat — 3K resource (HP% scoring)
        ("gc_3k_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
        ("gc_3k_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
        ("gc_3k_vs_champ", "Chinese", "champion", "Imperial", "res", 3000),
        # Anti-Archer — 30v30 fixed count (HP% scoring)
        ("aa_30v30_vs_arb", "Chinese", "arbalester", "Imperial", "fixed_hp", (30, 30)),
        ("aa_30v30_vs_ca", "Chinese", "heavy_cav_archer", "Imperial", "fixed_hp", (30, 30)),
        ("aa_30v30_vs_ele_archer", "Gurjaras", "elite_ele_archer", "Imperial", "fixed_hp", (30, 30)),
        # Anti-Archer — 3K resource (HP% scoring)
        ("aa_3k_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
        ("aa_3k_vs_ca", "Chinese", "heavy_cav_archer", "Imperial", "res", 3000),
        ("aa_3k_vs_ele_archer", "Gurjaras", "elite_ele_archer", "Imperial", "res", 3000),
    ],
    "castle": [
        # General Combat — 30v30 fixed count (HP% scoring)
        ("gc_30v30_vs_paladin", "Spanish", "knight", "Castle", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_arb", "Chinese", "crossbow", "Castle", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_champ", "Chinese", "swordsmen", "Castle", "fixed_hp", (30, 30)),
        # General Combat — 3K resource (HP% scoring)
        ("gc_3k_vs_paladin", "Spanish", "knight", "Castle", "res", 3000),
        ("gc_3k_vs_arb", "Chinese", "crossbow", "Castle", "res", 3000),
        ("gc_3k_vs_champ", "Chinese", "swordsmen", "Castle", "res", 3000),
        # Anti-Archer — 30v30 fixed count (HP% scoring)
        ("aa_30v30_vs_arb", "Chinese", "crossbow", "Castle", "fixed_hp", (30, 30)),
        ("aa_30v30_vs_ca", "Chinese", "cav_archer", "Castle", "fixed_hp", (30, 30)),
        ("aa_30v30_vs_ele_archer", "Gurjaras", "elephant_archer", "Castle", "fixed_hp", (30, 30)),
        # Anti-Archer — 3K resource (HP% scoring)
        ("aa_3k_vs_arb", "Chinese", "crossbow", "Castle", "res", 3000),
        ("aa_3k_vs_ca", "Chinese", "cav_archer", "Castle", "res", 3000),
        ("aa_3k_vs_ele_archer", "Gurjaras", "elephant_archer", "Castle", "res", 3000),
    ],
}

ARCHERY_ROLE_SCORE_TYPES = [
    "ranged_effectiveness",
    "general_combat",
    "anti_archer",
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "aa_30v30_vs_arb",
    "aa_30v30_vs_ca",
    "aa_30v30_vs_ele_archer",
    "aa_3k_vs_arb",
    "aa_3k_vs_ca",
    "aa_3k_vs_ele_archer",
    # Raw (pre-normalization) scores
    "gc_30v30_vs_paladin_raw",
    "gc_30v30_vs_arb_raw",
    "gc_30v30_vs_champ_raw",
    "gc_3k_vs_paladin_raw",
    "gc_3k_vs_arb_raw",
    "gc_3k_vs_champ_raw",
    "aa_30v30_vs_arb_raw",
    "aa_30v30_vs_ca_raw",
    "aa_30v30_vs_ele_archer_raw",
    "aa_3k_vs_arb_raw",
    "aa_3k_vs_ca_raw",
    "aa_3k_vs_ele_archer_raw",
    # Mobility ranking scores
    "mobility_score",
    "mobility_speed_dps",
    "mobility_pierce_armor",
    "mobility_hp",
]

# ===== Stable unit scoring =====
STABLE_LINE_SLUGS = ["knight", "light_cav", "camel", "steppe_lancer", "elephant"]

NAVAL_LINE_SLUGS = ["galleon", "fire", "hulk"]

SIEGE_LINE_SLUGS = ["ram", "trebuchet", "bombard_cannon", "cannon_galleon"]

# Lines not displayed in any ranking category (skipped from all computation)
HIDDEN_LINE_SLUGS = ["mangonel"]

STABLE_BENCHMARKS = {
    "imperial": [
        # General Combat — 30v30 fixed count (HP% scoring)
        ("gc_30v30_vs_paladin", "Spanish", "paladin", "Imperial", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_arb", "Chinese", "arbalester", "Imperial", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_champ", "Chinese", "champion", "Imperial", "fixed_hp", (30, 30)),
        # General Combat — 3K resource (HP% scoring)
        ("gc_3k_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
        ("gc_3k_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
        ("gc_3k_vs_champ", "Chinese", "champion", "Imperial", "res", 3000),
        # Anti-Cav — 30v30 fixed count (HP% scoring) — gc_vs_paladin reused from above
        ("ac_30v30_vs_heavy_camel", "Turks", "heavy_camel", "Imperial", "fixed_hp", (30, 30)),
        ("ac_30v30_vs_elephant", "Vietnamese", "elite_elephant", "Imperial", "fixed_hp", (30, 30)),
        # Anti-Cav — 3K resource (HP% scoring)
        ("ac_3k_vs_heavy_camel", "Turks", "heavy_camel", "Imperial", "res", 3000),
        ("ac_3k_vs_elephant", "Vietnamese", "elite_elephant", "Imperial", "res", 3000),
    ],
    "castle": [
        # General Combat — 30v30 fixed count (HP% scoring)
        ("gc_30v30_vs_paladin", "Spanish", "knight", "Castle", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_arb", "Chinese", "crossbow", "Castle", "fixed_hp", (30, 30)),
        ("gc_30v30_vs_champ", "Chinese", "swordsmen", "Castle", "fixed_hp", (30, 30)),
        # General Combat — 3K resource (HP% scoring)
        ("gc_3k_vs_paladin", "Spanish", "knight", "Castle", "res", 3000),
        ("gc_3k_vs_arb", "Chinese", "crossbow", "Castle", "res", 3000),
        ("gc_3k_vs_champ", "Chinese", "swordsmen", "Castle", "res", 3000),
        # Anti-Cav — 30v30 fixed count (HP% scoring)
        ("ac_30v30_vs_heavy_camel", "Turks", "camel", "Castle", "fixed_hp", (30, 30)),
        ("ac_30v30_vs_elephant", "Vietnamese", "elephant", "Castle", "fixed_hp", (30, 30)),
        # Anti-Cav — 3K resource (HP% scoring)
        ("ac_3k_vs_heavy_camel", "Turks", "camel", "Castle", "res", 3000),
        ("ac_3k_vs_elephant", "Vietnamese", "elephant", "Castle", "res", 3000),
    ],
}

STABLE_SCORE_TYPES = [
    "stable_effectiveness",
    "general_combat",
    "anti_cav",
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "ac_30v30_vs_heavy_camel",
    "ac_30v30_vs_elephant",
    "ac_3k_vs_heavy_camel",
    "ac_3k_vs_elephant",
    # Raw (pre-normalization) scores
    "gc_30v30_vs_paladin_raw",
    "gc_30v30_vs_arb_raw",
    "gc_30v30_vs_champ_raw",
    "gc_3k_vs_paladin_raw",
    "gc_3k_vs_arb_raw",
    "gc_3k_vs_champ_raw",
    "ac_30v30_vs_heavy_camel_raw",
    "ac_30v30_vs_elephant_raw",
    "ac_3k_vs_heavy_camel_raw",
    "ac_3k_vs_elephant_raw",
]

NAVAL_ROLE_BENCHMARKS = {
    "imperial": [
        ("vs_galleon_30v30", "Britons",   "galleon", "Imperial", "fixed_hp", (30, 30)),
        ("vs_galleon_3k",    "Britons",   "galleon", "Imperial", "res",      3000),
        ("vs_fire_30v30",    "Britons",   "fire",    "Imperial", "fixed_hp", (30, 30)),
        ("vs_fire_3k",       "Britons",   "fire",    "Imperial", "res",      3000),
        ("vs_hulk_30v30",    "Sicilians", "hulk",    "Imperial", "fixed_hp", (30, 30)),
        ("vs_hulk_3k",       "Sicilians", "hulk",    "Imperial", "res",      3000),
    ],
    "castle": [
        ("vs_galleon_30v30", "Britons",   "galleon", "Castle",   "fixed_hp", (30, 30)),
        ("vs_galleon_3k",    "Britons",   "galleon", "Castle",   "res",      3000),
        ("vs_fire_30v30",    "Britons",   "fire",    "Castle",   "fixed_hp", (30, 30)),
        ("vs_fire_3k",       "Britons",   "fire",    "Castle",   "res",      3000),
        ("vs_hulk_30v30",    "Sicilians", "hulk",    "Castle",   "fixed_hp", (30, 30)),
        ("vs_hulk_3k",       "Sicilians", "hulk",    "Castle",   "res",      3000),
    ],
}

NAVAL_SCORE_TYPES = [
    "naval_effectiveness",
    "vs_galleon",
    "vs_fire",
    "vs_hulk",
    "vs_galleon_30v30",
    "vs_galleon_3k",
    "vs_fire_30v30",
    "vs_fire_3k",
    "vs_hulk_30v30",
    "vs_hulk_3k",
    # Raw (pre-normalization) scores
    "vs_galleon_30v30_raw",
    "vs_galleon_3k_raw",
    "vs_fire_30v30_raw",
    "vs_fire_3k_raw",
    "vs_hulk_30v30_raw",
    "vs_hulk_3k_raw",
]


def compute_infantry_role_scores(age="imperial"):
    """Compute role-based scores for infantry units at the given age.
    Returns dict: {"militia|<age>": {...}, "spear|<age>": {...}, ...}"""

    is_imperial = age == "imperial"
    benchmarks = MILITIA_ROLE_BENCHMARKS[age]

    # Load benchmark opponents (once, shared across all lines)
    bench_cache = {}
    for key, civ, slug, bench_age, mode, param in benchmarks:
        cache_key = (civ, slug, bench_age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, bench_age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: benchmark {civ}/{slug}/{bench_age} not found")

    # Pool all infantry units across all lines, simulate benchmarks
    all_scores = {}  # sk -> scores dict
    sk_to_line = {}  # sk -> line_slug

    for line_slug in INFANTRY_LINE_SLUGS:
        units = build_line_units(line_slug, age)
        if not units:
            continue

        for u in units:
            cu = u["combat_unit"]
            unit_cost = calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
            )
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            scores = {}

            for key, civ, slug, bench_age, mode, param in benchmarks:
                bench = bench_cache[(civ, slug, bench_age)]
                if bench is None:
                    scores[key] = 0.0
                    continue

                if mode == "pop":
                    # Pop-adjusted 30v30: fixed_count respects pop_space
                    # (e.g. Karambit Warrior at 0.5 pop gets 60 units)
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        param,
                        fixed_count=param,
                        return_hp=True,
                    )
                else:
                    # Resource-based: weighted cost determines army size
                    bench_cost = calc_weighted_cost(
                        bench["cost_food"], bench["cost_wood"], bench["cost_gold"], is_imperial
                    )
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        param,
                        cost1_override=unit_cost,
                        cost2_override=bench_cost,
                        return_hp=True,
                    )

                if winner == 1:
                    scores[key] = round(hp1 * 100, 1)
                elif winner == 2:
                    scores[key] = round(-hp2 * 100, 1)
                else:
                    scores[key] = 0.0

            scores["_combat_unit"] = cu  # temp ref for anti-cav scoring
            scores["_speed"] = cu["movement_speed"]
            all_scores[sk] = scores
            sk_to_line[sk] = line_slug

    # Save raw scores before normalization
    bench_keys = [k for k, _, _, _, _, _ in benchmarks]
    for key in bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Build line_groups for per-line normalization
    line_groups = {}
    for sk in all_scores:
        line = sk_to_line[sk]
        line_groups.setdefault(line, []).append(sk)

    # Normalize each benchmark score to 0–100 globally across all infantry lines
    for key in bench_keys:
        vals = [all_scores[sk][key] for sk in all_scores]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for sk in all_scores:
            all_scores[sk][key] = round((all_scores[sk][key] - lo) / span * 100, 1)

    # Compute general_combat, anti_cav, anti_trash composites from normalized scores
    gc_keys = [k for k, *_ in benchmarks if k.startswith("gc_")]
    ac_keys = [
        "ac_30v30_vs_battle_elephant", "ac_30v30_vs_heavy_camel", "ac_30v30_vs_steppe_lancer",
        "ac_3k_vs_battle_elephant",   "ac_3k_vs_heavy_camel",   "ac_3k_vs_steppe_lancer",
    ]
    at_keys = [
        "at_30v30_vs_halb", "at_30v30_vs_hussar", "at_30v30_vs_elite_skirm",
        "at_3k_vs_halb",   "at_3k_vs_hussar",   "at_3k_vs_elite_skirm",
    ]
    for sk, scores in all_scores.items():
        scores["general_combat"] = round(
            sum(scores[k] for k in gc_keys) / len(gc_keys), 1
        )
        scores["anti_cav"] = round(
            sum(scores[k] for k in ac_keys) / len(ac_keys), 1
        )
        scores["anti_trash"] = round(
            sum(scores[k] for k in at_keys) / len(at_keys), 1
        )

    # Compute raiding ranking scores (uses _combat_unit refs)
    compute_raiding_scores(all_scores, sk_to_line, age)

    # Compute militia_value from general_combat, anti_cav, and anti_trash
    for sk, scores in all_scores.items():
        scores["militia_value"] = round(
            0.75 * scores["general_combat"]
            + 0.10 * scores["anti_cav"]
            + 0.15 * scores["anti_trash"],
            1,
        )

    # Apply speed weighting: multiply composites by speed, re-normalize globally
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "anti_trash", "militia_value", "raid_building"],
        scope="pool",
    )

    # Clean up temp combat unit refs
    for s in all_scores.values():
        s.pop("_combat_unit", None)
        s.pop("_speed", None)

    # Regroup by line for DB storage
    all_role_scores = {}
    for sk, scores in all_scores.items():
        line_slug = sk_to_line[sk]
        line_key = f"{line_slug}|{age}"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores

    return all_role_scores


def compute_archery_role_scores(age="imperial"):
    """Compute role-based scores for archery units at the given age.

    Uses a unified set of benchmarks for both general combat and anti-archer.
    Each raw benchmark score (-100 to +100) is min-max normalized per unit line
    (0-100) before averaging into sub-scores.  This means archer scores are
    normalized among archers, skirmisher scores among skirmishers, etc.

    Final: ranged_effectiveness = general_combat

    Returns dict: {"archer|<age>": {...}, "cav_archer|<age>": {...}, ...}"""

    is_imperial = age == "imperial"
    benchmarks = ARCHERY_ROLE_BENCHMARKS[age]

    bench_cache = {}
    for key, civ, slug, bench_age, mode, param in benchmarks:
        cache_key = (civ, slug, bench_age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, bench_age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: archery benchmark {civ}/{slug}/{bench_age} not found")

    all_scores = {}
    sk_to_line = {}

    for line_slug in ARCHERY_LINE_SLUGS:
        units = build_line_units(line_slug, age)
        if not units:
            continue

        for u in units:
            cu = u["combat_unit"]
            unit_cost = calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
            )
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            scores = {}

            for key, civ, slug, bench_age, mode, param in benchmarks:
                bench = bench_cache[(civ, slug, bench_age)]
                if bench is None:
                    scores[key] = 0.0
                    continue

                if mode == "res":
                    bench_cost = calc_weighted_cost(
                        bench["cost_food"],
                        bench["cost_wood"],
                        bench["cost_gold"],
                        is_imperial,
                    )
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        param,
                        cost1_override=unit_cost,
                        cost2_override=bench_cost,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

                elif mode == "fixed_hp":
                    m_count, o_count = param
                    # Use fixed_count so simulate_battle honors pop_space.
                    # Half-pop units (Blackwood Archer, Karambit Warrior) get
                    # 2x unit count for the same pop slots, e.g. 30 pop = 60 units.
                    # Assumes m_count == o_count (true for all current benchmarks).
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        resources=0,
                        fixed_count=m_count,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

            scores["_speed"] = cu["movement_speed"]
            scores["_range"] = cu["attack_range"] or 1.0
            all_scores[sk] = scores
            sk_to_line[sk] = line_slug

    # Save raw scores before normalization
    gc_keys = [k for k, *_ in benchmarks if k.startswith("gc_")]
    aa_keys = [k for k, *_ in benchmarks if k.startswith("aa_")]
    all_bench_keys = gc_keys + aa_keys

    for key in all_bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Group by line (kept for downstream DB-write step that splits by line)
    line_groups = {}
    for sk, scores in all_scores.items():
        line = sk_to_line[sk]
        line_groups.setdefault(line, []).append(sk)

    # Min-max normalize each benchmark score 0-100 globally across all ranged
    # units (archer + skirmisher + cav_archer + scorpion + gunpowder pooled
    # together), so scores are directly comparable across sub-lines.
    for bk in all_bench_keys:
        vals = [all_scores[sk][bk] for sk in all_scores]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for sk in all_scores:
            all_scores[sk][bk] = round((all_scores[sk][bk] - lo) / span * 100, 1)

    # Compute composites from normalized benchmark values.
    for sk, scores in all_scores.items():
        scores["general_combat"] = round(
            sum(scores[k] for k in gc_keys) / len(gc_keys), 1
        )
        scores["anti_archer"] = round(
            sum(scores[k] for k in aa_keys) / len(aa_keys), 1
        )

    # Speed-weight the component scores globally (multiply by speed, re-normalize 0-100).
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_archer"],
        scope="pool",
    )

    # Ranged effectiveness combines both components (70% general / 30% anti-archer)
    # over the speed-weighted values, then is further weighted by attack range
    # (longer-range units gain a kiting/positioning premium). Range-weighting
    # is also globally pooled so the resulting score is comparable across all
    # ranged sub-lines.
    for sk, scores in all_scores.items():
        scores["ranged_effectiveness"] = round(
            0.7 * scores["general_combat"] + 0.3 * scores["anti_archer"], 1
        )
    _apply_speed_weighting(
        all_scores,
        ["ranged_effectiveness"],
        scope="pool",
        multiplier_keys=("_range",),
    )

    # Clean up temp speed/range refs
    for s in all_scores.values():
        s.pop("_speed", None)
        s.pop("_range", None)

    # Compute mobility ranking scores
    # Step 1: Collect raw values from combat units
    mobility_raw = {}
    for line_slug in ARCHERY_LINE_SLUGS:
        units = build_line_units(line_slug, age)
        for u in units:
            cu = u["combat_unit"]
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            if sk not in all_scores:
                continue
            attack = cu["attack"]
            attack_speed = cu["attack_speed"]  # already 1/reload from prepare_combat_unit
            reload_time = 1.0 / attack_speed if attack_speed > 0 else 2.0
            dps = attack / reload_time
            mobility_raw[sk] = {
                "speed_dps": cu["movement_speed"] * dps,
                "pierce_armor": cu["pierce_armor"],
                "hp": cu["hp"],
            }

    # Step 2: Normalize each component 0-100 per unit line
    if mobility_raw:
        mob_line_groups = {}
        for sk in mobility_raw:
            line = sk_to_line[sk]
            mob_line_groups.setdefault(line, []).append(sk)

        for component in ["speed_dps", "pierce_armor", "hp"]:
            for line, sks in mob_line_groups.items():
                vals = [mobility_raw[sk][component] for sk in sks]
                lo, hi = min(vals), max(vals)
                span = hi - lo if hi != lo else 1
                for sk in sks:
                    mobility_raw[sk][f"norm_{component}"] = round(
                        (mobility_raw[sk][component] - lo) / span * 100, 1
                    )

        # Step 3: Compute composite and store
        for sk, raw in mobility_raw.items():
            scores = all_scores[sk]
            scores["mobility_speed_dps"] = raw["norm_speed_dps"]
            scores["mobility_pierce_armor"] = raw["norm_pierce_armor"]
            scores["mobility_hp"] = raw["norm_hp"]
            scores["mobility_score"] = round(
                (raw["norm_speed_dps"] + raw["norm_pierce_armor"] + raw["norm_hp"]) / 3,
                1,
            )

    # Regroup by line for DB storage
    all_role_scores = {}
    for sk, scores in all_scores.items():
        line_slug = sk_to_line[sk]
        line_key = f"{line_slug}|{age}"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores

    return all_role_scores


def compute_stable_role_scores(age="imperial"):
    """Compute benchmark-based scores for stable units at the given age.

    Uses the same pattern as archery: simulate benchmarks, min-max normalize
    each one 0-100 per unit line, then average into composites.

    Final: stable_effectiveness = 0.7 * general_combat + 0.3 * anti_cav

    Returns dict: {"knight|<age>": {...}, "light_cav|<age>": {...}, ...}"""

    is_imperial = age == "imperial"
    benchmarks = STABLE_BENCHMARKS[age]

    # Load benchmark units
    bench_cache = {}
    for key, civ, slug, bench_age, mode, param in benchmarks:
        cache_key = (civ, slug, bench_age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, bench_age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: stable benchmark {civ}/{slug}/{bench_age} not found")

    all_scores = {}
    sk_to_line = {}  # sk -> line_slug

    for line_slug in STABLE_LINE_SLUGS:
        units = build_line_units(line_slug, age)
        if not units:
            continue

        # Exclude Elephant Archers (ranged units already scored in archery rankings)
        units = [u for u in units if "ele_archer" not in u["unit_slug"]]

        for u in units:
            cu = u["combat_unit"]
            unit_cost = calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
            )
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            scores = {}

            for key, civ, slug, bench_age, mode, param in benchmarks:
                bench = bench_cache[(civ, slug, bench_age)]
                if bench is None:
                    scores[key] = 0.0
                    continue

                if mode == "res":
                    bench_cost = calc_weighted_cost(
                        bench["cost_food"],
                        bench["cost_wood"],
                        bench["cost_gold"],
                        is_imperial,
                    )
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        param,
                        cost1_override=unit_cost,
                        cost2_override=bench_cost,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

                elif mode == "fixed_hp":
                    m_count, o_count = param
                    # Use fixed_count so simulate_battle honors pop_space.
                    # Half-pop units (Blackwood Archer, Karambit Warrior) get
                    # 2x unit count for the same pop slots, e.g. 30 pop = 60 units.
                    # Assumes m_count == o_count (true for all current benchmarks).
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        resources=0,
                        fixed_count=m_count,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

            scores["_speed"] = cu["movement_speed"]
            all_scores[sk] = scores
            sk_to_line[sk] = line_slug

    if not all_scores:
        return {}

    # Save raw scores before normalization
    gc_keys = [k for k, *_ in benchmarks if k.startswith("gc_")]
    ac_only_keys = [k for k, *_ in benchmarks if k.startswith("ac_")]
    all_bench_keys = gc_keys + ac_only_keys

    for key in all_bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Group by line (kept for downstream DB-write step that splits by line)
    line_groups = {}
    for sk in all_scores:
        line = sk_to_line[sk]
        line_groups.setdefault(line, []).append(sk)

    # Min-max normalize each benchmark score 0-100 globally across all stable
    # units (knight + light_cav + camel + steppe_lancer + elephant pooled
    # together), so scores are directly comparable across sub-lines —
    # mirrors the infantry and ranged scoring approach.
    for bk in all_bench_keys:
        vals = [all_scores[sk][bk] for sk in all_scores]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for sk in all_scores:
            all_scores[sk][bk] = round((all_scores[sk][bk] - lo) / span * 100, 1)

    # Compute derived scores from normalized values
    # Anti-cav reuses gc paladin benchmarks (30v30 + 3K)
    ac_keys = ["gc_30v30_vs_paladin", "gc_3k_vs_paladin"] + ac_only_keys
    for sk, scores in all_scores.items():
        scores["general_combat"] = round(
            sum(scores[k] for k in gc_keys) / len(gc_keys), 1
        )
        scores["anti_cav"] = round(
            sum(scores[k] for k in ac_keys) / len(ac_keys), 1
        )
        scores["stable_effectiveness"] = round(
            0.70 * scores["general_combat"] + 0.30 * scores["anti_cav"],
            1,
        )

    # Apply speed weighting globally (multiply composites by speed, re-normalize 0-100).
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "stable_effectiveness"],
        scope="pool",
    )

    # Clean up temp speed refs
    for s in all_scores.values():
        s.pop("_speed", None)

    # Regroup by line for DB storage
    all_role_scores = {}
    for sk, scores in all_scores.items():
        line_slug = sk_to_line[sk]
        line_key = f"{line_slug}|{age}"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores
    return all_role_scores


def compute_naval_role_scores(age="imperial"):
    """Compute role-based scores for naval units at the given age.

    Simulates each naval unit against three benchmark opponents:
    Britons Galleon, Britons Fast Fire Ship, Sicilians Carrack (hulk).
    Each sub-score = avg of 30v30 fixed-count and 3K resource battles,
    normalized 0-100 per sub-line, then speed-weighted.

    Final: naval_effectiveness = (vs_galleon + vs_fire + vs_hulk) / 3

    Returns dict: {"galleon|<age>": {...}, "fire|<age>": {...}, "hulk|<age>": {...}}
    """
    is_imperial = age == "imperial"
    benchmarks = NAVAL_ROLE_BENCHMARKS[age]

    bench_cache = {}
    for key, civ, slug, bench_age, mode, param in benchmarks:
        cache_key = (civ, slug, bench_age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, bench_age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: naval benchmark {civ}/{slug}/{bench_age} not found")

    all_scores = {}
    sk_to_line = {}

    for line_slug in NAVAL_LINE_SLUGS:
        units = build_line_units(line_slug, age)
        if not units:
            continue

        for u in units:
            cu = u["combat_unit"]
            unit_cost = calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
            )
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            scores = {}

            for key, civ, slug, bench_age, mode, param in benchmarks:
                bench = bench_cache[(civ, slug, bench_age)]
                if bench is None:
                    scores[key] = 0.0
                    continue

                if mode == "res":
                    bench_cost = calc_weighted_cost(
                        bench["cost_food"],
                        bench["cost_wood"],
                        bench["cost_gold"],
                        is_imperial,
                    )
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu, bench, param,
                        cost1_override=unit_cost,
                        cost2_override=bench_cost,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

                elif mode == "fixed_hp":
                    m_count, o_count = param
                    fake_res = m_count * o_count
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu, bench, fake_res,
                        cost1_override=fake_res // m_count,
                        cost2_override=fake_res // o_count,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

            scores["_speed"] = cu["movement_speed"]
            all_scores[sk] = scores
            sk_to_line[sk] = line_slug

    if not all_scores:
        return {}

    all_bench_keys = [k for k, *_ in benchmarks]
    for key in all_bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    line_groups = {}
    for sk in all_scores:
        line = sk_to_line[sk]
        line_groups.setdefault(line, []).append(sk)

    for bk in all_bench_keys:
        for line, sks in line_groups.items():
            vals = [all_scores[sk][bk] for sk in sks]
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1
            for sk in sks:
                all_scores[sk][bk] = round(
                    (all_scores[sk][bk] - lo) / span * 100, 1
                )

    for sk, scores in all_scores.items():
        scores["vs_galleon"] = round(
            (scores["vs_galleon_30v30"] + scores["vs_galleon_3k"]) / 2, 1
        )
        scores["vs_fire"] = round(
            (scores["vs_fire_30v30"] + scores["vs_fire_3k"]) / 2, 1
        )
        scores["vs_hulk"] = round(
            (scores["vs_hulk_30v30"] + scores["vs_hulk_3k"]) / 2, 1
        )
        scores["naval_effectiveness"] = round(
            (scores["vs_galleon"] + scores["vs_fire"] + scores["vs_hulk"]) / 3, 1
        )

    _apply_speed_weighting(
        all_scores,
        ["vs_galleon", "vs_fire", "vs_hulk", "naval_effectiveness"],
        scope="per_line",
        line_groups=line_groups,
    )

    for s in all_scores.values():
        s.pop("_speed", None)

    all_role_scores = {}
    for sk, scores in all_scores.items():
        line_slug = sk_to_line[sk]
        line_key = f"{line_slug}|{age}"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores

    return all_role_scores


# ===== Siege anti-building scoring =====

# Three fully-upgraded Imperial-age castle targets (one per civ config).
# Each entry represents a specific civ's castle with all available techs researched.
# Used in Task 5 for the 6-simulation loop (3 castles × 2 resource modes).
CASTLE_TARGETS = [
    {
        "name": "persian",
        # Hoardings(×1.21) × Masonry(×1.10) × Architecture(×1.10) = 4800 × 1.4641 ≈ 7027
        # Citadels (unique tech): +4 pierce attack, +3 bonus vs Rams (class 17), +3 bonus vs Infantry (class 1)
        # Stronghold is Celts-only (NOT universal) — reload stays 2.0s
        "hp": 7027,
        "armor": {
            3:  13,   # pierce: 11 + 1(Masonry) + 1(Architecture)
            4:  10,   # melee:  8 + 1 + 1
            11: 14,   # std_building: 8 + 3(Masonry) + 3(Architecture)
            21: 0,
        },
        "arrows": 5,
        "arrow_attack": 18,   # 11 + 1(Fletching) + 1(Bodkin) + 1(Chemistry) + 4(Citadels); no Bracer
        "arrow_range": 10,    # 8 + 1(Fletching) + 1(Bodkin); no Bracer
        "reload": 2.0,        # No Stronghold (Celts-only)
        "arrow_bonus_attacks": {17: 3, 1: 3},   # Citadels: +3 vs Rams (class 17), +3 vs Infantry (class 1)
    },
    {
        "name": "teuton",
        # Hoardings(×1.21) × Masonry(×1.10) = 4800 × 1.331 ≈ 6388; NO Architecture (disabled)
        # Civ bonus "+2 melee armor" applies only to infantry/cavalry units, NOT castle
        # Crenellations (unique tech): +3 range
        # No Bracer (disabled). No Stronghold.
        "hp": 6388,
        "armor": {
            3:  12,   # pierce: 11 + 1(Masonry); no Architecture, no Bracer
            4:   9,   # melee:  8 + 1(Masonry); no Architecture, no civ bonus (castle unit 82)
            11: 11,   # std_building: 8 + 3(Masonry); no Architecture
            21: 0,
        },
        "arrows": 5,
        "arrow_attack": 14,   # 11 + 1(Fletching) + 1(Bodkin) + 1(Chemistry); no Bracer
        "arrow_range": 13,    # 8 + 1(Fletching) + 1(Bodkin) + 3(Crenellations); no Bracer
        "reload": 2.0,
        "arrow_bonus_attacks": {},
    },
    {
        "name": "byzantine",
        # Hoardings(×1.21) only (Masonry + Architecture disabled).
        # Byzantine civ bonus: +10% HP/age (×1.40 at Imperial) → 4800 × 1.21 × 1.40 ≈ 8127
        # Has Bracer (+1 pierce armor, +1 attack, +1 range). No Heated Shot. No Stronghold.
        "hp": 8127,
        "armor": {
            3:  12,   # pierce: 11 + 1(Bracer); no Masonry/Architecture
            4:   8,   # melee: 8 base; no Masonry/Architecture
            11:  8,   # std_building: 8 base; no Masonry/Architecture
            21: 0,
        },
        "arrows": 5,
        "arrow_attack": 15,   # 11 + 1(Fletching) + 1(Bodkin) + 1(Bracer) + 1(Chemistry)
        "arrow_range": 11,    # 8 + 1(Fletching) + 1(Bodkin) + 1(Bracer)
        "reload": 2.0,
        "arrow_bonus_attacks": {},
    },
]


SIEGE_SCORE_TYPES = [
    "anti_building_score",
    # Sub-score TTKs (effective TTK in seconds, stored for hover card)
    # "5u" = fixed-count mode (5 units by default; 30 for tarkan/fire_archer_wu)
    # "5k" = 5000-resource mode (n = max(1, 5000 // weighted_unit_cost))
    "ab_persian_5u_ttk",   "ab_persian_5k_ttk",
    "ab_teuton_5u_ttk",    "ab_teuton_5k_ttk",
    "ab_byzantine_5u_ttk", "ab_byzantine_5k_ttk",
    # Damage fraction (0.0–1.0; 1.0 = castle destroyed, <1.0 = unit died first)
    "ab_persian_5u_dmg",   "ab_persian_5k_dmg",
    "ab_teuton_5u_dmg",    "ab_teuton_5k_dmg",
    "ab_byzantine_5u_dmg", "ab_byzantine_5k_dmg",
]


def _calc_building_damage(attacks, castle_armor):
    """Calculate per-hit damage of a unit against a building.

    Only counts attack classes that match known building armor classes (3=pierce,
    4=melee, 11=standard buildings). Other attack classes (anti-cavalry, anti-ship,
    etc.) are ignored because buildings have very high hidden armor for those.
    """
    total = 0
    for ac, dv in castle_armor.items():
        av = attacks.get(ac, 0)
        total += max(0, av - dv)
    return max(1, total)


def _simulate_siege_vs_castle(n_units, unit_hp, unit_dps, castle_hp,
                               castle_dps, unit_speed, unit_range, castle_range):
    """Tick-based attrition sim: units attack a castle that fires back.

    Returns (time_seconds, damage_fraction) where:
      - time_seconds: actual TTK if castle destroyed, else 600.0
      - damage_fraction: castle HP destroyed / castle_hp (1.0 = win)
    """
    DT = 0.1
    MAX_TIME = 600.0

    remaining_hp = float(castle_hp)
    units_alive = n_units
    focused_unit_hp = float(unit_hp)
    time = 0.0

    # Fast path: unit strictly outranges castle — castle arrows can't reach, no attrition.
    # Equal range means both fire simultaneously (handled below in combat phase).
    if unit_range > castle_range:
        total_dps = n_units * unit_dps
        if total_dps <= 0:
            return MAX_TIME, 0.0
        ttk = castle_hp / total_dps
        if ttk <= MAX_TIME:
            return round(ttk, 1), 1.0
        dmg = min(1.0, total_dps * MAX_TIME / castle_hp)
        return MAX_TIME, round(dmg, 4)

    # All siege units pre-position at their final attack spot — no closing phase.
    # Ranged units (BC, trebuchet) start at their attack range.
    # Melee units (rams) start at range 0, already adjacent to the castle.
    # Rams have 180 pierce armor so the castle barely damages them during approach
    # anyway (1 dmg/arrow = 2.5 DPS), making closing time a negligible noise source
    # that inflates faster civs' scores without reflecting real DPS differences.

    # Combat phase: both fire simultaneously
    while remaining_hp > 0 and units_alive > 0 and time < MAX_TIME:
        focused_unit_hp -= castle_dps * DT
        if focused_unit_hp <= 0:
            units_alive -= 1
            if units_alive > 0:
                focused_unit_hp = float(unit_hp)

        remaining_hp -= units_alive * unit_dps * DT
        time += DT

    dmg_fraction = min(1.0, round((castle_hp - max(0.0, remaining_hp)) / castle_hp, 4))

    if remaining_hp <= 0:
        return round(time, 1), 1.0
    return MAX_TIME, dmg_fraction


def _get_siege_fixed_count(slug):
    """Return the fixed unit count for siege anti-building simulations."""
    if "fire_archer_wu" in slug or "tarkan" in slug:
        return 30
    if slug == "ram":
        return 3
    return 5


def _effective_ttk(ttk, dmg_fraction, max_winner_ttk):
    """
    Compute effective TTK for scoring.

    Winners (dmg_fraction == 1.0): return actual TTK.
    Losers (dmg_fraction < 1.0):  return (max_winner_ttk + 200) / dmg_fraction.
    Edge case (max_winner_ttk is None, no unit in group won):  return 600.

    Args:
        ttk: actual simulation TTK (seconds)
        dmg_fraction: 0.0–1.0; 1.0 means castle was destroyed
        max_winner_ttk: slowest actual TTK among winners in the same group,
                        or None if no unit in the group won
    Returns:
        float: effective TTK in seconds (higher = worse)
    """
    if dmg_fraction >= 1.0:
        return ttk
    if max_winner_ttk is None:
        return 600.0
    if dmg_fraction <= 0:
        return 600.0
    return (max_winner_ttk + 200) / dmg_fraction


def compute_siege_antibuilding_scores():
    """Compute anti-building scores for all siege units (Castle + Imperial).

    Each unit is simulated against 3 castle types (persian, teuton, byzantine)
    in 2 modes (fixed-count, 5k-resource) for 6 total simulations per unit.
    Results are averaged into a single anti_building_score (0-100).

    Returns dict in write_role_scores_to_db format.
    """
    from statistics import mean

    # Phase 1 — Collect raw results
    raw_results = {}    # sk -> {(castle_name, mode): (ttk, dmg)}
    unit_groups = {}    # sk -> (line_slug, age)

    for age in ["castle", "imperial"]:
        is_imperial = age == "imperial"

        for line_slug in SIEGE_LINE_SLUGS:
            units = build_line_units(line_slug, age)
            if not units:
                continue

            for u in units:
                cu = u["combat_unit"]
                sk = f"{u['civ_name']}|{u['unit_slug']}"
                unit_groups[sk] = (line_slug, age)
                raw_results.setdefault(sk, {})

                attacks = cu.get("attacks", {})
                reload_time = 1.0 / cu["attack_speed"] if cu["attack_speed"] > 0 else 2.0

                for castle in CASTLE_TARGETS:
                    castle_name = castle["name"]

                    # Compute unit_dps (castle-specific due to armor differences)
                    damage_per_hit = _calc_building_damage(attacks, castle["armor"])
                    if "dromon" in u["unit_slug"]:
                        extra_proj = cu.get("extra_projectiles", 0) or 0
                        if extra_proj > 0:
                            damage_per_hit *= (1 + extra_proj)
                    unit_dps = damage_per_hit / reload_time
                    if "fire_archer_wu" in u["unit_slug"]:
                        unit_dps += 1.0

                    # Compute castle_dps
                    dmg_per_arrow = max(1, castle["arrow_attack"] - cu["pierce_armor"])
                    castle_dps = castle["arrows"] * dmg_per_arrow / castle["reload"]
                    # Persian bonus attacks vs specific armor classes
                    for bonus_class, bonus_attack in castle.get("arrow_bonus_attacks", {}).items():
                        if bonus_class in cu.get("armors", {}):
                            extra_dmg = max(0, bonus_attack - cu["armors"][bonus_class])
                            castle_dps += castle["arrows"] * extra_dmg / castle["reload"]

                    # Fixed-count mode
                    n_fixed = _get_siege_fixed_count(u["unit_slug"])
                    ttk_5u, dmg_5u = _simulate_siege_vs_castle(
                        n_fixed, cu["hp"], unit_dps, castle["hp"], castle_dps,
                        cu["movement_speed"], cu["attack_range"], castle["arrow_range"],
                    )
                    raw_results[sk][(castle_name, "5u")] = (ttk_5u, dmg_5u)

                    # 5K-resource mode
                    unit_cost = calc_weighted_cost(
                        cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
                    )
                    n_5k = max(1, 5000 // unit_cost)
                    ttk_5k, dmg_5k = _simulate_siege_vs_castle(
                        n_5k, cu["hp"], unit_dps, castle["hp"], castle_dps,
                        cu["movement_speed"], cu["attack_range"], castle["arrow_range"],
                    )
                    raw_results[sk][(castle_name, "5k")] = (ttk_5k, dmg_5k)

    # Phase 2 — Compute effective TTKs
    # Group units by (line_slug, age)
    groups = {}  # (line_slug, age) -> [sk, ...]
    for sk, (ls, ag) in unit_groups.items():
        groups.setdefault((ls, ag), []).append(sk)

    eff_ttks = {}  # sk -> {(castle_name, mode): eff_ttk}
    raw_dmgs = {}  # sk -> {(castle_name, mode): dmg}

    combos = [(c["name"], m) for c in CASTLE_TARGETS for m in ("5u", "5k")]

    for (ls, ag), sks in groups.items():
        for combo in combos:
            # Find max_winner_ttk for this group + combo
            winner_ttks = []
            for sk in sks:
                ttk, dmg = raw_results[sk][combo]
                if dmg >= 1.0:
                    winner_ttks.append(ttk)
            max_winner_ttk = max(winner_ttks) if winner_ttks else None

            for sk in sks:
                ttk, dmg = raw_results[sk][combo]
                eff = _effective_ttk(ttk, dmg, max_winner_ttk)
                eff_ttks.setdefault(sk, {})[combo] = eff
                raw_dmgs.setdefault(sk, {})[combo] = dmg

    # Phase 3 — Weighted average effective TTK + normalize
    # Castle weights: Persian 40%, Byzantine 40%, Teuton 20%.
    # Each castle has 2 modes (5u + 5k) that split the castle's weight equally.
    _CASTLE_WEIGHTS = {
        ("persian",   "5u"): 0.20,
        ("persian",   "5k"): 0.20,
        ("byzantine", "5u"): 0.20,
        ("byzantine", "5k"): 0.20,
        ("teuton",    "5u"): 0.10,
        ("teuton",    "5k"): 0.10,
    }
    avg_eff = {}  # sk -> float
    for sk in eff_ttks:
        avg_eff[sk] = sum(
            eff_ttks[sk][combo] * _CASTLE_WEIGHTS[combo]
            for combo in _CASTLE_WEIGHTS
        )

    # Global bounds per age: used for single-unit groups (e.g. tarkan) so they
    # get a meaningful score relative to the full siege pool, not just themselves.
    global_bounds = {}
    for ag in ("castle", "imperial"):
        age_avgs = [avg_eff[sk] for sk in avg_eff if unit_groups[sk][1] == ag]
        if age_avgs:
            global_bounds[ag] = (min(age_avgs), max(age_avgs))

    all_scores = {}  # (line_slug, age) -> {sk: score_dict}

    for (ls, ag), sks in groups.items():
        # Normalize across ALL siege units of the same age (not per-line).
        # This gives a single cross-line leaderboard: best unit overall = 100.
        lo, hi = global_bounds.get(ag, (0, 1))
        span = hi - lo if hi != lo else 1

        group_scores = {}
        for sk in sks:
            score = round((hi - avg_eff[sk]) / span * 100, 1)
            d = {"anti_building_score": score}
            # Store sub-score keys
            for castle_name, mode in combos:
                prefix = f"ab_{castle_name}_{mode}"
                d[f"{prefix}_ttk"] = round(eff_ttks[sk][(castle_name, mode)], 1)
                d[f"{prefix}_dmg"] = round(raw_dmgs[sk][(castle_name, mode)], 4)
            group_scores[sk] = d

        all_scores[(ls, ag)] = group_scores

    # Phase 4 — No speed weighting for siege.
    # Ranged units pre-position at attack range (no closing phase), so speed has
    # no effect on their simulation outcome. Rams have 180 pierce armor so the
    # castle barely damages them during approach. Speed weighting is removed entirely
    # to avoid inflating scores for faster civs (e.g. Mongols) without real DPS benefit.

    # Phase 5 — Assemble result
    result = {}
    for (line_slug, age), scores in all_scores.items():
        result[f"{line_slug}|{age}"] = scores
    return result


INFANTRY_ROLE_SCORE_TYPES = [
    "militia_value",
    "general_combat",
    "anti_cav",
    "anti_trash",
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "ac_30v30_vs_battle_elephant",
    "ac_30v30_vs_heavy_camel",
    "ac_30v30_vs_steppe_lancer",
    "ac_3k_vs_battle_elephant",
    "ac_3k_vs_heavy_camel",
    "ac_3k_vs_steppe_lancer",
    "at_30v30_vs_halb",
    "at_30v30_vs_hussar",
    "at_30v30_vs_elite_skirm",
    "at_3k_vs_halb",
    "at_3k_vs_hussar",
    "at_3k_vs_elite_skirm",
    # Raw (pre-normalization) scores
    "gc_30v30_vs_paladin_raw",
    "gc_30v30_vs_arb_raw",
    "gc_30v30_vs_champ_raw",
    "gc_3k_vs_paladin_raw",
    "gc_3k_vs_arb_raw",
    "gc_3k_vs_champ_raw",
    "ac_30v30_vs_battle_elephant_raw",
    "ac_30v30_vs_heavy_camel_raw",
    "ac_30v30_vs_steppe_lancer_raw",
    "ac_3k_vs_battle_elephant_raw",
    "ac_3k_vs_heavy_camel_raw",
    "ac_3k_vs_steppe_lancer_raw",
    "at_30v30_vs_halb_raw",
    "at_30v30_vs_hussar_raw",
    "at_30v30_vs_elite_skirm_raw",
    "at_3k_vs_halb_raw",
    "at_3k_vs_hussar_raw",
    "at_3k_vs_elite_skirm_raw",
    # Raiding ranking scores
    "raid_speed",
    "raid_vill_kill",
    "raid_building",
    "raiding_value",
    "raid_vs_tc_nmin",
    "raid_vs_castle_nmin",
]


# ---------------------------------------------------------------------------
# Raiding ranking
# ---------------------------------------------------------------------------

# Fully upgraded Spanish buildings (Fletching/Bodkin/Bracer/Chemistry always applied).
# Two variants per building: with and without Masonry+Architecture.
BUILDING_TARGETS = {
    "castle_uni": {
        "name": "Castle (Masonry+Arch)",
        "hp": 7028,           # 4800 * 1.1 * 1.1 * 1.21 (Hoardings)
        "melee_armor": 10,    # 8 + 1 + 1
        "building_armor": 6,  # 0 + 3 + 3
        "arrows": 5,          # base (no garrison)
        "arrow_attack": 15,   # 11 + 1 + 1 + 1 + 1 (Chemistry)
        "reload": 2.0,
    },
    "castle_no_uni": {
        "name": "Castle (no uni)",
        "hp": 5808,           # 4800 * 1.21 (Hoardings only)
        "melee_armor": 8,
        "building_armor": 0,
        "arrows": 5,
        "arrow_attack": 15,
        "reload": 2.0,
    },
    "tc_uni": {
        "name": "TC (Masonry+Arch, 15 vills)",
        "hp": 2904,           # 2400 * 1.1 * 1.1
        "melee_armor": 5,     # 3 + 1 + 1
        "building_armor": 6,  # 0 + 3 + 3
        "arrows": 15,         # 1 per garrisoned villager
        "arrow_attack": 9,    # 5 + 1 + 1 + 1 + 1
        "reload": 2.0,
    },
    "tc_no_uni": {
        "name": "TC (no uni, 15 vills)",
        "hp": 2400,
        "melee_armor": 3,
        "building_armor": 0,
        "arrows": 15,
        "arrow_attack": 9,
        "reload": 2.0,
    },
}


def compute_raiding_scores(all_scores, sk_to_line, age="imperial"):
    """Compute raiding ranking scores for all infantry units (in-place).

    Adds raid_speed, raid_vill_kill, raid_building, raiding_value and raw sub-scores.
    Uses _combat_unit refs from all_scores.
    """
    # Load Jurchen Man-at-Arms as villager proxy
    vill_proxy = _load_benchmark_unit("Jurchens", "swordsmen", "Castle")
    if vill_proxy is None:
        print(
            "  WARNING: Jurchen swordsmen (villager proxy) not found, skipping raiding scores"
        )
        return

    # 1. Movement speed
    for sk, scores in all_scores.items():
        cu = scores["_combat_unit"]
        scores["raid_speed"] = cu["movement_speed"]

    # 2. Villager killing speed (30v30 vs Jurchen MaA, fewer ticks = better)
    for sk, scores in all_scores.items():
        cu = scores["_combat_unit"]
        winner, _, _, hp1, hp2, ticks = simulate_battle(
            cu,
            vill_proxy,
            0,
            fixed_count=30,
            return_ticks=True,
        )
        # Lower ticks = faster kill = better score.
        # Store raw ticks; we'll invert during normalization.
        scores["raid_vill_kill_ticks"] = ticks

    # 3. Anti-building N_min calculation (attrition model with focus fire)
    # Each arrow individually does max(1, arrow_attack - pierce_armor) damage.
    # Building focus-fires one unit at a time; army DPS drops as units die.
    # N_min = ceil((-1 + sqrt(1 + 4*C)) / 2) where C = 2*B*f / (d*h)
    for sk, scores in all_scores.items():
        cu = scores["_combat_unit"]
        attacks = cu.get("attacks", {})
        base_melee = attacks.get(4, 0)  # class 4 = melee
        bonus_vs_buildings = attacks.get(21, 0)  # class 21 = Standard Buildings
        reload_time = 1.0 / cu["attack_speed"] if cu["attack_speed"] > 0 else 2.0
        unit_hp = cu["hp"]
        unit_pierce_armor = cu["pierce_armor"]

        for bkey, bstats in BUILDING_TARGETS.items():
            # Unit DPS vs building (separate armor classes)
            melee_dmg = base_melee - bstats["melee_armor"]
            building_dmg = bonus_vs_buildings - bstats["building_armor"]
            damage_per_hit = max(1, melee_dmg + building_dmg)
            d = damage_per_hit / reload_time  # unit anti-building DPS

            # Building DPS vs unit (each arrow reduced by pierce armor individually)
            dmg_per_arrow = max(1, bstats["arrow_attack"] - unit_pierce_armor)
            f = bstats["arrows"] * dmg_per_arrow / bstats["reload"]  # building DPS

            # Attrition formula: N*(N+1) >= 2*B*f / (d*h)
            B = bstats["hp"]
            C = 2.0 * B * f / (d * unit_hp)
            n_min = math.ceil((-1.0 + math.sqrt(1.0 + 4.0 * C)) / 2.0)
            scores[f"raid_vs_{bkey}_nmin"] = n_min

    # Normalize movement speed 0–100 (higher = better)
    speed_vals = [s["raid_speed"] for s in all_scores.values()]
    lo, hi = min(speed_vals), max(speed_vals)
    span = hi - lo if hi != lo else 1
    for s in all_scores.values():
        s["raid_speed"] = round((s["raid_speed"] - lo) / span * 100, 1)

    # Normalize vill kill: invert ticks (fewer = better → higher score)
    tick_vals = [s["raid_vill_kill_ticks"] for s in all_scores.values()]
    lo_t, hi_t = min(tick_vals), max(tick_vals)
    span_t = hi_t - lo_t if hi_t != lo_t else 1
    for s in all_scores.values():
        # Invert: lowest ticks → 100, highest ticks → 0
        s["raid_vill_kill"] = round(
            (hi_t - s["raid_vill_kill_ticks"]) / span_t * 100, 1
        )
        del s["raid_vill_kill_ticks"]  # clean up raw ticks

    # Normalize N_min sub-scores: average the two variants per building type
    # Then normalize 0-100 (inverted: lower N = higher score)
    for sk, scores in all_scores.items():
        scores["raid_vs_castle_nmin"] = (
            scores.pop("raid_vs_castle_uni_nmin") + scores.pop("raid_vs_castle_no_uni_nmin")
        ) / 2.0
        scores["raid_vs_tc_nmin"] = (
            scores.pop("raid_vs_tc_uni_nmin") + scores.pop("raid_vs_tc_no_uni_nmin")
        ) / 2.0

    for bkey in ("castle", "tc"):
        nmin_key = f"raid_vs_{bkey}_nmin"
        vals = [s[nmin_key] for s in all_scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for s in all_scores.values():
            # Invert: lowest N_min → 100 (best raider), highest → 0
            s[nmin_key] = round((hi - s[nmin_key]) / span * 100, 1)

    # Compute building composite (average of TC and Castle N_min scores)
    for sk, scores in all_scores.items():
        scores["raid_building"] = round(
            (scores["raid_vs_tc_nmin"] + scores["raid_vs_castle_nmin"]) / 2, 1
        )

    # Compute weighted composite (25% speed, 25% vill kill, 50% building)
    for sk, scores in all_scores.items():
        scores["raiding_value"] = round(
            0.25 * scores["raid_speed"]
            + 0.25 * scores["raid_vill_kill"]
            + 0.50 * scores["raid_building"],
            1,
        )


def write_role_scores_to_db(role_scores_dict, line_slugs, score_types):
    """Write role scores into the battle_scores table in aoe2_reference.db.

    Writes all score types for the given lines.
    Clears existing scores for those lines/ages before inserting.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Extract ages from the role_scores_dict keys to only delete matching ages
    ages = set()
    for line_age_key in role_scores_dict:
        _, age = line_age_key.split("|")
        ages.add(age)
    for slug in line_slugs:
        for age in ages:
            c.execute("DELETE FROM battle_scores WHERE line_slug=? AND age=?", (slug, age))

    rows = []
    for line_age_key, unit_scores in role_scores_dict.items():
        line_slug, age = line_age_key.split("|")
        for unit_key, scores in unit_scores.items():
            civ_name, unit_slug = unit_key.split("|")
            for score_type in score_types:
                if score_type in scores:
                    rows.append(
                        (
                            line_slug,
                            age,
                            civ_name,
                            unit_slug,
                            score_type,
                            scores[score_type],
                        )
                    )

    c.executemany(
        "INSERT INTO battle_scores (line_slug, age, civ_name, unit_slug, score_type, score_value) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"  Wrote {len(rows)} battle_scores rows to DB")


def _cleanup_stale_siege_entries():
    """Remove stale pooled 'siege' line_slug entries from battle_scores.

    Siege scores are stored per sub-line (ram, trebuchet, bombard_cannon).
    Any entries with line_slug='siege' are stale from an older format.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM battle_scores WHERE line_slug='siege'")
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"  Cleaned up {deleted} stale pooled 'siege' entries")


def _cleanup_stale_stable_entries():
    """Remove stale pooled 'stable' line_slug entries from battle_scores.

    Stable scores are now stored per sub-line (knight, light_cav, camel, etc.).
    Any entries with line_slug='stable' are stale from an older format.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM battle_scores WHERE line_slug='stable'")
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"  Cleaned up {deleted} stale pooled 'stable' entries")


def _cleanup_stale_anti_cav_pool():
    """Remove stale anti_cav_pool entries from battle_scores."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM battle_scores WHERE line_slug='anti_cav_pool'")
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"  Cleaned up {deleted} stale anti_cav_pool entries")


def _cleanup_stale_infantry_scores():
    """Remove old infantry benchmark score_type rows replaced by the redesign."""
    stale_keys = [
        "ac_30v30_vs_elephant", "ac_30v30_vs_hussar",
        "ac_3k_vs_elephant",   "ac_3k_vs_hussar",
        "ac_30v30_vs_elephant_raw", "ac_30v30_vs_hussar_raw",
        "ac_3k_vs_elephant_raw",   "ac_3k_vs_hussar_raw",
    ]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    placeholders = ",".join("?" * len(stale_keys))
    c.execute(
        f"DELETE FROM battle_scores WHERE line_slug IN ('militia','spear','shock_infantry')"
        f" AND score_type IN ({placeholders})",
        stale_keys,
    )
    deleted = c.rowcount
    conn.commit()
    conn.close()
    if deleted:
        print(f"  Cleaned up {deleted} stale infantry benchmark rows")


def compute_rankings():
    """Compute rank and median_delta for every (line_slug, age, score_type) group.

    For each group:
    - median = numpy.median(score_values)
    - rank = position sorted by score_value desc (1 = highest)
    - median_delta = score_value - median
    """
    import numpy as np

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all distinct groups
    c.execute("SELECT DISTINCT line_slug, age, score_type FROM battle_scores")
    groups = c.fetchall()

    total_updated = 0
    for line_slug, age, score_type in groups:
        # Fetch all rows in this group
        c.execute(
            "SELECT id, score_value FROM battle_scores WHERE line_slug=? AND age=? AND score_type=?",
            (line_slug, age, score_type),
        )
        rows = c.fetchall()
        if not rows:
            continue

        values = [r[1] for r in rows]
        median = float(np.median(values))

        # Sort by score_value desc for ranking
        ranked = sorted(rows, key=lambda r: r[1], reverse=True)

        for rank, (row_id, score_value) in enumerate(ranked, start=1):
            delta = round(score_value - median, 4)
            c.execute(
                "UPDATE battle_scores SET rank=?, median_delta=? WHERE id=?",
                (rank, delta, row_id),
            )
            total_updated += 1

    conn.commit()
    conn.close()
    print(f"Rankings: updated {total_updated} rows across {len(groups)} groups")


def main():
    parser = argparse.ArgumentParser(description="Compute battle ranking scores")
    parser.add_argument(
        "--full", action="store_true", help="Force full recomputation (ignore cache)"
    )
    parser.add_argument(
        "--roles-only",
        action="store_true",
        help="Only compute role scores (skip round-robin/benchmarks)",
    )
    args = parser.parse_args()

    start = time.time()

    if args.roles_only:
        for role_age in ["imperial", "castle"]:
            age_start = time.time()
            print(f"\n=== {role_age.upper()} AGE ===")

            role_scores = compute_infantry_role_scores(age=role_age)
            _cleanup_stale_infantry_scores()
            write_role_scores_to_db(role_scores, INFANTRY_LINE_SLUGS, INFANTRY_ROLE_SCORE_TYPES)
            total = sum(len(v) for v in role_scores.values())
            print(
                f"Infantry roles: {total} units across {len(role_scores)} lines in {time.time() - age_start:.1f}s"
            )

            archery_start = time.time()
            archery_scores = compute_archery_role_scores(age=role_age)
            write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
            total_archery = sum(len(v) for v in archery_scores.values())
            print(
                f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {time.time() - archery_start:.1f}s"
            )

            stable_start = time.time()
            stable_scores = compute_stable_role_scores(age=role_age)
            write_role_scores_to_db(stable_scores, STABLE_LINE_SLUGS, STABLE_SCORE_TYPES)
            total_stable = sum(len(v) for v in stable_scores.values())
            print(
                f"Stable roles: {total_stable} units across {len(stable_scores)} lines in {time.time() - stable_start:.1f}s"
            )

        # Siege anti-building scores (already handles both ages internally)
        siege_start = time.time()
        siege_scores = compute_siege_antibuilding_scores()
        write_role_scores_to_db(siege_scores, SIEGE_LINE_SLUGS, SIEGE_SCORE_TYPES)
        # Clean up stale pooled entries (scores are now per sub-line)
        _cleanup_stale_siege_entries()
        _cleanup_stale_stable_entries()
        _cleanup_stale_anti_cav_pool()
        total_siege = sum(len(v) for v in siege_scores.values())
        print(
            f"Siege anti-building: {total_siege} units in {time.time() - siege_start:.1f}s"
        )

        # Naval role scores
        naval_start = time.time()
        naval_scores_all = {}
        for naval_age in ["imperial", "castle"]:
            naval_scores = compute_naval_role_scores(age=naval_age)
            naval_scores_all.update(naval_scores)
            total_naval = sum(len(v) for v in naval_scores.values())
            print(
                f"Naval roles ({naval_age}): {total_naval} units in {time.time() - naval_start:.1f}s"
            )
        write_role_scores_to_db(naval_scores_all, NAVAL_LINE_SLUGS, NAVAL_SCORE_TYPES)
        total_naval_all = sum(len(v) for v in naval_scores_all.values())
        print(f"Naval roles total: {total_naval_all} units in {time.time() - naval_start:.1f}s")

        # Compute rankings for all scores
        ranking_start = time.time()
        compute_rankings()
        print(f"Rankings: {time.time() - ranking_start:.1f}s")
        return

    # Compute simulation engine hash
    engine_hash = _sim_engine_hash()

    # Load cache (if not --full)
    cache = None if args.full else load_cache()
    if cache and cache.get("sim_engine_hash") != engine_hash:
        print("Simulation engine changed — full recompute")
        cache = None
    if cache is None:
        cache = {
            "version": CACHE_VERSION,
            "sim_engine_hash": engine_hash,
            "unit_hashes": {},
            "benchmark_hashes": {},
            "pairwise": {},
            "benchmarks": {},
        }
        if args.full:
            print("Full recompute requested")
    else:
        print("Loaded cache")

    old_fps = cache.get("unit_hashes", {})
    old_bench_fps = cache.get("benchmark_hashes", {})
    pairwise_cache = cache.get("pairwise", {})
    benchmark_cache = cache.get("benchmarks", {})

    # Build all units and compute fingerprints (infantry/archery excluded — uses DB scores)
    current_fps = {}
    for line_slug, config in UNIT_LINES.items():
        if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS or line_slug in STABLE_LINE_SLUGS or line_slug in SIEGE_LINE_SLUGS or line_slug in HIDDEN_LINE_SLUGS or line_slug in NAVAL_LINE_SLUGS:
            continue
        for age_key in ["castle", "imperial"]:
            std_slug = config.get(f"{age_key}_slug")
            multi_slugs = config.get(f"{age_key}_slugs", [])
            has_unique = bool(config.get("unique_units"))
            if not std_slug and not multi_slugs and not has_unique:
                continue
            units = build_line_units(line_slug, age_key)
            for u in units:
                fp_key = f"{u['civ_name']}|{u['unit_slug']}|{age_key}"
                current_fps[fp_key] = _unit_fingerprint(u["combat_unit"])

    # Detect changed units — invalidate their cached pairwise entries
    changed_fps = set()
    for fp_key, fp_val in current_fps.items():
        if old_fps.get(fp_key) != fp_val:
            changed_fps.add(fp_val)

    # If any units changed, remove pairwise entries involving changed fingerprints
    if changed_fps:
        before = len(pairwise_cache)
        pairwise_cache = {
            k: v
            for k, v in pairwise_cache.items()
            if not any(part in changed_fps for part in k.split(":")[:2])
        }
        evicted = before - len(pairwise_cache)
        if evicted:
            print(f"Evicted {evicted} stale pairwise entries")

    # Benchmark units and fingerprints
    conn = get_db()
    rc = conn.cursor()
    bench_units = {}
    bench_fps = {}
    for key, civ, slug, age in BENCHMARKS:
        rc.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
            (civ, slug, age),
        )
        row = rc.fetchone()
        if row:
            cd = build_combat_dict(rc, row)
            cu = prepare_combat_unit(cd)
            bench_units[key] = cu
            bench_fps[key] = _unit_fingerprint(cu)
    conn.close()

    # Invalidate benchmark cache if benchmark units changed
    bench_changed = set()
    for bkey, bfp in bench_fps.items():
        if old_bench_fps.get(bkey) != bfp:
            bench_changed.add(bkey)
    if bench_changed:
        before = len(benchmark_cache)
        benchmark_cache = {
            k: v
            for k, v in benchmark_cache.items()
            if not any(bk in k for bk in bench_changed)
        }
        evicted = before - len(benchmark_cache)
        if evicted:
            print(f"Evicted {evicted} stale benchmark entries")
    if changed_fps:
        # Also invalidate benchmarks for changed units
        before = len(benchmark_cache)
        benchmark_cache = {
            k: v
            for k, v in benchmark_cache.items()
            if k.split(":")[0] not in changed_fps
        }
        evicted_u = before - len(benchmark_cache)
        if evicted_u:
            print(f"Evicted {evicted_u} benchmark entries for changed units")

    # Round-robin scores
    output = {"round_robin": {}, "benchmarks": {}}
    rr_count = 0
    rr_hits_total = 0
    rr_misses_total = 0

    for line_slug, config in UNIT_LINES.items():
        if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS or line_slug in STABLE_LINE_SLUGS or line_slug in SIEGE_LINE_SLUGS or line_slug in HIDDEN_LINE_SLUGS or line_slug in NAVAL_LINE_SLUGS:
            continue  # infantry/archery/stable uses role-based scores from battle_scores table
        for age_key in ["castle", "imperial"]:
            slug = config.get(f"{age_key}_slug")
            multi_slugs = config.get(f"{age_key}_slugs", [])
            has_unique = bool(config.get("unique_units"))
            if not slug and not multi_slugs and not has_unique:
                continue
            scores, hits, misses = compute_round_robin(
                line_slug, age_key, pairwise_cache, current_fps
            )
            if scores:
                output["round_robin"][f"{line_slug}|{age_key}"] = scores
                rr_count += 1
                rr_hits_total += hits
                rr_misses_total += misses

    rr_time = time.time() - start
    print(
        f"Round-robin: {rr_count} line-ages in {rr_time:.1f}s "
        f"({rr_misses_total} simulated, {rr_hits_total} cached)"
    )

    # Benchmark scores
    bench_start = time.time()
    output["benchmarks"], b_hits, b_misses = compute_benchmarks(
        bench_units, bench_fps, benchmark_cache, current_fps
    )
    bench_time = time.time() - bench_start
    print(f"Benchmarks: {bench_time:.1f}s ({b_misses} simulated, {b_hits} cached)")

    # Role scores for both ages (written to DB only, not JSON)
    for role_age in ["imperial", "castle"]:
        age_start = time.time()
        print(f"\n=== {role_age.upper()} AGE ===")

        role_scores = compute_infantry_role_scores(age=role_age)
        _cleanup_stale_infantry_scores()
        write_role_scores_to_db(role_scores, INFANTRY_LINE_SLUGS, INFANTRY_ROLE_SCORE_TYPES)
        total_infantry = sum(len(v) for v in role_scores.values())
        print(
            f"Infantry roles: {total_infantry} units across {len(role_scores)} lines in {time.time() - age_start:.1f}s"
        )

        archery_start = time.time()
        archery_scores = compute_archery_role_scores(age=role_age)
        write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
        total_archery = sum(len(v) for v in archery_scores.values())
        print(
            f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {time.time() - archery_start:.1f}s"
        )

        stable_start = time.time()
        stable_scores = compute_stable_role_scores(age=role_age)
        write_role_scores_to_db(stable_scores, STABLE_LINE_SLUGS, STABLE_SCORE_TYPES)
        total_stable = sum(len(v) for v in stable_scores.values())
        print(
            f"Stable roles: {total_stable} units across {len(stable_scores)} lines in {time.time() - stable_start:.1f}s"
        )

    # Siege anti-building scores (already handles both ages internally)
    siege_start = time.time()
    siege_scores = compute_siege_antibuilding_scores()
    write_role_scores_to_db(siege_scores, SIEGE_LINE_SLUGS, SIEGE_SCORE_TYPES)
    # Clean up stale pooled entries (scores are now per sub-line)
    _cleanup_stale_siege_entries()
    _cleanup_stale_stable_entries()
    _cleanup_stale_anti_cav_pool()
    total_siege = sum(len(v) for v in siege_scores.values())
    print(
        f"Siege anti-building: {total_siege} units in {time.time() - siege_start:.1f}s"
    )

    # Naval role scores
    naval_start = time.time()
    naval_scores_all = {}
    for naval_age in ["imperial", "castle"]:
        naval_scores = compute_naval_role_scores(age=naval_age)
        naval_scores_all.update(naval_scores)
    write_role_scores_to_db(naval_scores_all, NAVAL_LINE_SLUGS, NAVAL_SCORE_TYPES)
    total_naval = sum(len(v) for v in naval_scores_all.values())
    print(f"Naval roles: {total_naval} units in {time.time() - naval_start:.1f}s")

    # Compute rankings for all DB scores (rank + median_delta)
    ranking_start = time.time()
    compute_rankings()
    ranking_time = time.time() - ranking_start
    print(f"Rankings: {ranking_time:.1f}s")

    # Write output (round-robin + benchmarks only, no militia)
    out_path = os.path.join(str(_DATA_DIR), "battle_scores.json")
    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    # Save cache
    cache["sim_engine_hash"] = engine_hash
    cache["benchmark_hashes"] = bench_fps
    cache["pairwise"] = pairwise_cache
    cache["benchmarks"] = benchmark_cache
    save_cache(cache, current_fps)

    total = time.time() - start
    print(f"Total: {total:.1f}s -> {out_path}")


if __name__ == "__main__":
    main()
