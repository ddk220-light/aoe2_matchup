"""
Standalone script to pre-compute battle ranking scores for the unit rankings page.

Run this after regenerating aoe2_reference.db to produce battle_scores.json.
The Flask server loads this file at startup (no simulations at serve time).

Usage:
    cd webapp && python3 compute_battle_scores.py            # incremental (cached)
    cd webapp && python3 compute_battle_scores.py --full      # force full recompute
"""

import argparse
import hashlib
import json
import math
import os
import sqlite3
import time

from simulation import prepare_combat_unit, simulate_battle

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "battle_cache.json")
CACHE_VERSION = 11


# Unit lines config (must match app.py UNIT_LINES)
UNIT_LINES = {
    "militia": {
        "name": "Militia Line",
        "building": "Barracks",
        "castle_slug": "swordsmen",
        "imperial_slug": "champion",
        "unique_units": {
            "Goths": ("huskarl_goths", "elite_huskarl_goths"),
            "Celts": ("woad_raider_celts", "elite_woad_raider_celts"),
            "Vikings": ("berserk_vikings", "elite_berserk_vikings"),
            "Japanese": ("samurai_japanese", "elite_samurai_japanese"),
            "Teutons": ("teutonic_knight_teutons", "elite_teutonic_knight_teutons"),
            "Aztecs": ("jaguar_warrior_aztecs", "elite_jaguar_warrior_aztecs"),
            "Incas": ("kamayuk_incas", "elite_kamayuk_incas"),
            "Italians": (None, "condottiero"),
            "Ethiopians": (
                "shotel_warrior_ethiopians",
                "elite_shotel_warrior_ethiopians",
            ),
            "Burgundians": (None, "flemish_militia"),
            "Sicilians": ("serjeant_sicilians", "elite_serjeant_sicilians"),
            "Poles": ("obuch_poles", "elite_obuch_poles"),
            "Dravidians": (
                "urumi_swordsman_dravidians",
                "elite_urumi_swordsman_dravidians",
            ),
            "Hindustanis": ("ghulam_hindustanis", "elite_ghulam_hindustanis"),
            "Armenians": ("warrior_priest_armenians", "warrior_priest_armenians"),
            "Khitans": ("liao_dao_khitans", "elite_liao_dao_khitans"),
            "Wu": ("jian_swordsman_wu", "jian_swordsman_wu"),
            "Shu": (
                "white_feather_guard_shu",
                "elite_white_feather_guard_shu",
            ),
        },
    },
    "spear": {
        "name": "Spear Line",
        "building": "Barracks",
        "castle_slug": "pikeman",
        "imperial_slug": "halberdier",
        "unique_units": {},
    },
    "shock_infantry": {
        "name": "Shock Infantry",
        "building": "Barracks",
        "castle_slug": "fire_lancer",
        "imperial_slug": "elite_fire_lancer",
        "unique_units": {
            "Aztecs": ("eagle_warrior", "elite_eagle"),
            "Incas": ("eagle_warrior", "elite_eagle"),
            "Mayans": ("eagle_warrior", "elite_eagle"),
            "Malay": ("karambit_warrior_malay", "elite_karambit_warrior_malay"),
        },
    },
    "archer": {
        "name": "Archers & Gunpowder",
        "building": "Archery Range",
        "castle_slug": "crossbow",
        "imperial_slug": "arbalester",
        "unique_units": {
            "Britons": ("longbowman_britons", "elite_longbowman_britons"),
            "Chinese": ("chu_ko_nu_chinese", "elite_chu_ko_nu_chinese"),
            "Mayans": ("plumed_archer_mayans", "elite_plumed_archer_mayans"),
            "Italians": (
                "genoese_crossbowman_italians",
                "elite_genoese_crossbowman_italians",
            ),
            "Vietnamese": (
                "rattan_archer_vietnamese",
                "elite_rattan_archer_vietnamese",
            ),
            "Armenians": (
                "composite_bowman_armenians",
                "elite_composite_bowman_armenians",
            ),
            "Wu": ("fire_archer_wu", "elite_fire_archer_wu"),
        },
    },
    "skirmisher": {
        "name": "Skirmisher Line",
        "building": "Archery Range",
        "castle_slug": "elite_skirm",
        "imperial_slug": "imp_elite_skirm",
        "unique_units": {
            "Berbers": ("genitour", "elite_genitour"),
        },
    },
    "cav_archer": {
        "name": "Cavalry Archer Line",
        "building": "Archery Range",
        "castle_slug": "cav_archer",
        "imperial_slug": "heavy_cav_archer",
        "extra_castle_slugs": ["elephant_archer"],
        "extra_imperial_slugs": ["elite_ele_archer"],
        "unique_units": {
            "Mongols": ("mangudai_mongols", "elite_mangudai_mongols"),
            "Saracens": ("mameluke_saracens", "elite_mameluke_saracens"),
            "Berbers": ("camel_archer_berbers", "elite_camel_archer_berbers"),
            "Burmese": ("arambai_burmese", "elite_arambai_burmese"),
            "Cumans": ("kipchak_cumans", "elite_kipchak_cumans"),
            "Bengalis": (
                "ratha_(ranged)_bengalis",
                "elite_ratha_(ranged)_bengalis",
            ),
            "Wei": ("xianbei_raider_wei", "xianbei_raider_wei"),
            "Spanish": ("conquistador_spanish", "elite_conquistador_spanish"),
            "Koreans": ("war_wagon_koreans", "elite_war_wagon_koreans"),
        },
    },
    "knight": {
        "name": "Knight Line",
        "building": "Stable",
        "castle_slug": "knight",
        "imperial_slug": "paladin",
        "unique_units": {
            "Byzantines": ("cataphract_byzantines", "elite_cataphract_byzantines"),
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
            "Slavs": ("boyar_slavs", "elite_boyar_slavs"),
            "Bulgarians": ("konnik_bulgarians", "elite_konnik_bulgarians"),
            "Lithuanians": ("leitis_lithuanians", "elite_leitis_lithuanians"),
            "Tatars": ("keshik_tatars", "elite_keshik_tatars"),
            "Burgundians": ("coustillier_burgundians", "elite_coustillier_burgundians"),
            "Bengalis": (
                "ratha_(melee)_bengalis",
                "elite_ratha_(melee)_bengalis",
            ),
            "Gurjaras": (
                "shrivamsha_rider_gurjaras",
                "elite_shrivamsha_rider_gurjaras",
            ),
            "Romans": ("centurion_romans", "elite_centurion_romans"),
            "Georgians": ("monaspa_georgians", "elite_monaspa_georgians"),
            "Jurchens": ("iron_pagoda_jurchens", "elite_iron_pagoda_jurchens"),
            "Wei": ("tiger_cavalry_wei", "elite_tiger_cavalry_wei"),
        },
    },
    "light_cav": {
        "name": "Light Cavalry Line",
        "building": "Stable",
        "castle_slug": "light_cav",
        "imperial_slug": "hussar",
        "unique_units": {
            "Magyars": ("magyar_huszar_magyars", "elite_magyar_huszar_magyars"),
        },
    },
    "camel": {
        "name": "Camel Line",
        "building": "Stable",
        "castle_slug": "camel",
        "imperial_slug": "heavy_camel",
        "unique_units": {},
    },
    "steppe_lancer": {
        "name": "Steppe Lancer",
        "building": "Stable",
        "castle_slug": "steppe_lancer",
        "imperial_slug": "elite_steppe",
        "unique_units": {},
    },
    "elephant": {
        "name": "Elephant Line",
        "building": "Stable",
        "castle_slug": "elephant",
        "imperial_slug": "elite_elephant",
        "extra_castle_slugs": ["elephant_archer"],
        "extra_imperial_slugs": ["elite_ele_archer"],
        "unique_units": {
            "Persians": ("war_elephant_persians", "elite_war_elephant_persians"),
        },
    },
    "ram": {
        "name": "Ram Line",
        "building": "Siege Workshop",
        "castle_slug": "ram",
        "imperial_slug": "siege_ram",
        "unique_units": {},
    },
    "mangonel": {
        "name": "Mangonel Line",
        "building": "Siege Workshop",
        "castle_slug": "mangonel",
        "imperial_slug": "siege_onager",
        "unique_units": {},
    },
    "gunpowder": {
        "name": "Gunpowder",
        "building": "Archery Range",
        "castle_slug": None,
        "imperial_slug": "hand_cannoneer",
        "unique_units": {
            "Turks": ("janissary_turks", "elite_janissary_turks"),
            "Portuguese": ("organ_gun_portuguese", "elite_organ_gun_portuguese"),
            "Jurchens": ("grenadier_jurchens", "grenadier_jurchens"),
            "Incas": ("slinger", "imp_slinger"),
            "Bohemians": ("hussite_wagon_bohemians", "elite_hussite_wagon_bohemians"),
            "Franks": ("throwing_axeman_franks", "elite_throwing_axeman_franks"),
            "Malians": ("gbeto_malians", "elite_gbeto_malians"),
            "Gurjaras": (
                "chakram_thrower_gurjaras",
                "elite_chakram_thrower_gurjaras",
            ),
        },
    },
    "scorpion": {
        "name": "Scorpion Line",
        "building": "Siege Workshop",
        "castle_slug": "scorpion",
        "imperial_slug": "heavy_scorpion",
        "unique_units": {
            "Khmer": ("ballista_elephant_khmer", "elite_ballista_elephant_khmer"),
            "Shu": ("war_chariot_shu", "elite_war_chariot_shu"),
            "Khitans": ("mounted_trebuchet_khitans", "mounted_trebuchet_khitans"),
        },
    },
    "trebuchet": {
        "name": "Trebuchet",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "trebuchet",
        "unique_units": {},
    },
    "bombard_cannon": {
        "name": "Bombard Cannon",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "bombard_cannon",
        "extra_imperial_slugs": ["traction_trebuchet"],
        "unique_units": {
            "Wu": (None, "elite_fire_archer_wu"),
        },
    },
}

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
    sim_path = os.path.join(os.path.dirname(__file__), "simulation.py")
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


def build_combat_dict(rc, row):
    """Build a dict from a ref_units row, compatible with prepare_combat_unit().

    All combat properties are now inline on ref_units — no extra queries needed.
    """
    reload_time = row["final_reload_time"] or 2.0
    attack_speed = 1.0 / reload_time if reload_time > 0 else 0.5

    return {
        "slug": row["unit_slug"],
        "unit_name": row["unit_name"],
        "unit_category": "military",
        "paired_unit_slug": None,
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "attack_range": row["final_range"],
        "attack_speed": attack_speed,
        "attack_delay": row["final_attack_delay"] or 0,
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "movement_speed": row["final_speed"],
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
        "upgrade_cost_food": row["upgrade_cost_food"] or 0,
        "upgrade_cost_wood": row["upgrade_cost_wood"] or 0,
        "upgrade_cost_gold": row["upgrade_cost_gold"] or 0,
        "attacks_json": row["final_attacks_json"],
        "armors_json": row["final_armors_json"],
        "accuracy": row["final_accuracy"] or 100,
        "min_attack_range": row["min_range"] or 0,
        "projectile_speed": row["projectile_speed"] or 0,
        "is_siege_projectile": row["is_siege_projectile"] or 0,
        "splash_radius": row["splash_radius"] or 0,
        "extra_projectiles": row["extra_projectiles"] or 0,
        "extra_projectile_attacks_json": row["extra_projectile_attacks_json"],
        "trample_percent": row["trample_percent"] or 0,
        "trample_radius": row["trample_radius"] or 0,
        "trample_flat_damage": row["trample_flat_damage"] or 0,
        "hp_regen": row["hp_regen"] or 0,
        "charge_projectile_count": row["charge_projectile_count"] or 0,
        "charge_projectile_speed": row["charge_projectile_speed"] or 0,
        "charge_projectile_attacks_json": row["charge_projectile_attacks_json"],
        "charge_attack_range": float(row["charge_attack_range"] or 0),
        "charge_ignores_armor": int(row["charge_ignores_armor"] or 0),
        "ignores_pierce_armor": int(row["ignores_pierce_armor"] or 0),
        "ignores_melee_armor": int(row["ignores_melee_armor"] or 0),
        "bonus_damage_reduction": row["bonus_damage_reduction"] or 0,
        "splash_on_hit_radius": row["splash_on_hit_radius"] or 0,
        "splash_on_hit_fraction": row["splash_on_hit_fraction"] or 1.0,
        "dodge_shield_max": int(row["dodge_shield_max"] or 0),
        "dodge_shield_recharge": row["dodge_shield_recharge"] or 0,
        "bleed_dps": row["bleed_dps"] or 0,
        "bleed_duration": row["bleed_duration"] or 0,
        "block_first_melee": int(row["block_first_melee"] or 0),
        "attack_bonus_per_kill": int(row["attack_bonus_per_kill"] or 0),
        "first_attack_extra_projectiles": int(
            row["first_attack_extra_projectiles"] or 0
        ),
        "pass_through_percent": row["pass_through_percent"] or 0,
        "pass_through_count": row["pass_through_count"] or 1,
        "extra_proj_scatter": row["extra_proj_scatter"] or 0,
        "miss_damage_percent": row["miss_damage_percent"] or 0,
        "hp_per_kill": int(row["hp_per_kill"] or 0),
        "hp_per_kill_max": int(row["hp_per_kill_max"] or 0),
        "hp_transform_threshold": row["hp_transform_threshold"] or 0,
        "pop_space": row["pop_space"] or 1.0,
        "armor_strip_per_hit": int(row["armor_strip_per_hit"] or 0),
        "charge_attack_melee": int(row["charge_attack_melee"] or 0),
        "charge_recharge_time": row["charge_recharge_time"] or 0,
        "attack_bonus_nearby": row["attack_bonus_nearby"] or 0,
        "nearby_bonus_count": int(row["nearby_bonus_count"] or 0),
        "damage_reflect_percent": row["damage_reflect_percent"] or 0,
        "hp_nearby_percent_per_unit": row["hp_nearby_percent_per_unit"] or 0,
        "hp_nearby_max_units": int(row["hp_nearby_max_units"] or 0),
        # Dismount on death (Konnik)
        "dismount_hp": row["dismount_hp"],
        "dismount_attack": row["dismount_attack"],
        "dismount_melee_armor": row["dismount_melee_armor"],
        "dismount_pierce_armor": row["dismount_pierce_armor"],
        "dismount_attack_speed": row["dismount_attack_speed"],
        "dismount_attack_delay": row["dismount_attack_delay"],
        "dismount_movement_speed": row["dismount_movement_speed"],
        "dismount_attacks_json": row["dismount_attacks_json"],
        "dismount_armors_json": row["dismount_armors_json"],
        # Transform on HP threshold (Jian Swordsman)
        "transform_hp": row["transform_hp"],
        "transform_attack": row["transform_attack"],
        "transform_melee_armor": row["transform_melee_armor"],
        "transform_pierce_armor": row["transform_pierce_armor"],
        "transform_attack_speed": row["transform_attack_speed"],
        "transform_attack_delay": row["transform_attack_delay"],
        "transform_movement_speed": row["transform_movement_speed"],
        "transform_attacks_json": row["transform_attacks_json"],
        "transform_armors_json": row["transform_armors_json"],
    }


def calc_weighted_cost(food, wood, gold, is_imperial):
    cost = 0.8 * (wood or 0) + (food or 0) + 1.5 * (gold or 0)
    return int(cost) if cost > 0 else 100


def _apply_speed_weighting(all_scores, score_keys, scope="pool", line_groups=None):
    """Multiply composite scores by movement speed, then re-normalize to 0-100.

    Args:
        all_scores: dict {sk: {score_key: value, "_speed": float, ...}}
        score_keys: list of score keys to apply speed weighting to
        scope: "pool" = normalize across all units; "per_line" = normalize per line group
        line_groups: dict {line_slug: [sk, ...]} — required when scope="per_line"
    """
    if scope == "per_line" and line_groups:
        for key in score_keys:
            for line, sks in line_groups.items():
                # Multiply by speed
                weighted = {}
                for sk in sks:
                    speed = all_scores[sk].get("_speed", 1.0)
                    weighted[sk] = all_scores[sk][key] * speed
                # Re-normalize 0-100
                vals = list(weighted.values())
                lo, hi = min(vals), max(vals)
                span = hi - lo if hi != lo else 1
                for sk in sks:
                    all_scores[sk][key] = round((weighted[sk] - lo) / span * 100, 1)
    else:
        for key in score_keys:
            # Multiply by speed
            weighted = {}
            for sk, scores in all_scores.items():
                speed = scores.get("_speed", 1.0)
                weighted[sk] = scores[key] * speed
            # Re-normalize 0-100
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

    for civ_name, (castle_uu, imperial_uu) in line.get("unique_units", {}).items():
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
        if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS or line_slug in STABLE_LINE_SLUGS or line_slug in SIEGE_LINE_SLUGS or line_slug in HIDDEN_LINE_SLUGS:
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

MILITIA_ROLE_BENCHMARKS = [
    # (key, civ, slug, age, mode, param)
    # General Combat — 30v30 fixed count (pop-adjusted: half-pop units get double)
    ("gc_30v30_vs_paladin", "Spanish", "paladin", "Imperial", "pop", 30),
    ("gc_30v30_vs_arb", "Chinese", "arbalester", "Imperial", "pop", 30),
    ("gc_30v30_vs_champ", "Chinese", "champion", "Imperial", "pop", 30),
    # General Combat — 3K resources each
    ("gc_3k_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
    ("gc_3k_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
    ("gc_3k_vs_champ", "Chinese", "champion", "Imperial", "res", 3000),
    # Anti-Cav — 30v30 fixed count (pop-adjusted)
    # gc_30v30_vs_paladin reused from above
    ("ac_30v30_vs_elephant", "Persians", "elite_war_elephant_persians", "Imperial", "pop", 30),
    ("ac_30v30_vs_hussar", "Spanish", "hussar", "Imperial", "pop", 30),
    # Anti-Cav — 3K resources each
    # gc_3k_vs_paladin reused from above
    ("ac_3k_vs_elephant", "Persians", "elite_war_elephant_persians", "Imperial", "res", 3000),
    ("ac_3k_vs_hussar", "Spanish", "hussar", "Imperial", "res", 3000),
]

ANTI_CAV_BENCHMARKS = [
    # (key, civ, slug, age, mode, param)
    ("ac_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
    ("ac_vs_hussar", "Spanish", "hussar", "Imperial", "res", 3000),
    ("ac_vs_heavy_camel", "Persians", "heavy_camel", "Imperial", "res", 3000),
    ("ac_vs_elephant", "Vietnamese", "elite_elephant", "Imperial", "res", 3000),
    ("ac_vs_halb", "Spanish", "halberdier", "Imperial", "res", 3000),
    ("ac_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
]

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

ARCHERY_ROLE_BENCHMARKS = [
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
]

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

SIEGE_LINE_SLUGS = ["ram", "trebuchet", "bombard_cannon"]

# Lines not displayed in any ranking category (skipped from all computation)
HIDDEN_LINE_SLUGS = ["mangonel"]

STABLE_BENCHMARKS = [
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
]

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


def compute_infantry_role_scores():
    """Compute role-based scores for all Imperial infantry units.
    Returns dict: {"militia|imperial": {...}, "spear|imperial": {...}, ...}"""

    # Load benchmark opponents (once, shared across all lines)
    bench_cache = {}
    for key, civ, slug, age, mode, param in MILITIA_ROLE_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: benchmark {civ}/{slug}/{age} not found")

    # Pool all infantry units across all lines, simulate benchmarks
    all_scores = {}  # sk -> scores dict
    sk_to_line = {}  # sk -> line_slug

    for line_slug in INFANTRY_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
        if not units:
            continue

        for u in units:
            cu = u["combat_unit"]
            unit_cost = calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"], True
            )
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            scores = {}

            for key, civ, slug, age, mode, param in MILITIA_ROLE_BENCHMARKS:
                bench = bench_cache[(civ, slug, age)]
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
                        bench["cost_food"], bench["cost_wood"], bench["cost_gold"], True
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
    bench_keys = [k for k, _, _, _, _, _ in MILITIA_ROLE_BENCHMARKS]
    for key in bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Normalize each benchmark score to 0–100 across ALL infantry units
    for key in bench_keys:
        vals = [s[key] for s in all_scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for s in all_scores.values():
            s[key] = round((s[key] - lo) / span * 100, 1)

    # Compute general_combat and anti_cav composites from normalized scores
    gc_keys = [k for k, *_ in MILITIA_ROLE_BENCHMARKS if k.startswith("gc_")]
    ac_keys_30v30 = ["gc_30v30_vs_paladin", "ac_30v30_vs_elephant", "ac_30v30_vs_hussar"]
    ac_keys_3k = ["gc_3k_vs_paladin", "ac_3k_vs_elephant", "ac_3k_vs_hussar"]
    ac_keys = ac_keys_30v30 + ac_keys_3k
    for sk, scores in all_scores.items():
        scores["general_combat"] = round(
            sum(scores[k] for k in gc_keys) / len(gc_keys), 1
        )
        scores["anti_cav"] = round(
            sum(scores[k] for k in ac_keys) / len(ac_keys), 1
        )

    # Compute anti-cav ranking scores (uses _combat_unit refs)
    compute_anti_cav_scores(all_scores, sk_to_line)

    # Compute raiding ranking scores (uses _combat_unit refs)
    compute_raiding_scores(all_scores, sk_to_line)

    # Compute militia_value from general_combat, anti_cav, and raid_building
    for sk, scores in all_scores.items():
        scores["militia_value"] = round(
            0.50 * scores["general_combat"]
            + 0.30 * scores["anti_cav"]
            + 0.20 * scores["raid_building"],
            1,
        )

    # Apply speed weighting: multiply composites by speed, re-normalize 0-100
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "militia_value", "raid_building", "anti_cav_value"],
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
        line_key = f"{line_slug}|imperial"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores

    return all_role_scores


def compute_archery_role_scores():
    """Compute role-based scores for all Imperial archery units.

    Uses a unified set of benchmarks for both general combat and anti-archer.
    Each raw benchmark score (-100 to +100) is min-max normalized per unit line
    (0-100) before averaging into sub-scores.  This means archer scores are
    normalized among archers, skirmisher scores among skirmishers, etc.

    Final: ranged_effectiveness = 0.7 * general_combat + 0.3 * anti_archer

    Returns dict: {"archer|imperial": {...}, "cav_archer|imperial": {...}, ...}"""

    bench_cache = {}
    for key, civ, slug, age, mode, param in ARCHERY_ROLE_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: archery benchmark {civ}/{slug}/{age} not found")

    all_scores = {}
    sk_to_line = {}

    for line_slug in ARCHERY_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
        if not units:
            continue

        for u in units:
            cu = u["combat_unit"]
            unit_cost = calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"], True
            )
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            scores = {}

            for key, civ, slug, age, mode, param in ARCHERY_ROLE_BENCHMARKS:
                bench = bench_cache[(civ, slug, age)]
                if bench is None:
                    scores[key] = 0.0
                    continue

                if mode == "res":
                    bench_cost = calc_weighted_cost(
                        bench["cost_food"],
                        bench["cost_wood"],
                        bench["cost_gold"],
                        True,
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
                    fake_res = m_count * o_count
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        fake_res,
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

    # Save raw scores before normalization
    gc_keys = [k for k, *_ in ARCHERY_ROLE_BENCHMARKS if k.startswith("gc_")]
    aa_keys = [k for k, *_ in ARCHERY_ROLE_BENCHMARKS if k.startswith("aa_")]
    all_bench_keys = gc_keys + aa_keys

    for key in all_bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Min-max normalize each benchmark score per unit line (0-100)
    # Each line (archer, skirmisher, cav_archer, etc.) is normalized independently
    # so scores reflect how good a unit is within its role, not across all ranged.
    line_groups = {}
    for sk, scores in all_scores.items():
        line = sk_to_line[sk]
        line_groups.setdefault(line, []).append(sk)

    for bk in all_bench_keys:
        for line, sks in line_groups.items():
            vals = [all_scores[sk][bk] for sk in sks]
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1
            for sk in sks:
                all_scores[sk][bk] = round((all_scores[sk][bk] - lo) / span * 100, 1)

    # Compute derived scores from normalized values
    for sk, scores in all_scores.items():
        scores["general_combat"] = round(
            sum(scores[k] for k in gc_keys) / len(gc_keys), 1
        )
        scores["anti_archer"] = round(
            sum(scores[k] for k in aa_keys) / len(aa_keys), 1
        )
        scores["ranged_effectiveness"] = round(
            0.70 * scores["general_combat"] + 0.30 * scores["anti_archer"],
            1,
        )

    # Apply speed weighting: multiply composites by speed, re-normalize per line
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_archer", "ranged_effectiveness"],
        scope="per_line",
        line_groups=line_groups,
    )

    # Clean up temp speed refs
    for s in all_scores.values():
        s.pop("_speed", None)

    # Compute mobility ranking scores
    # Step 1: Collect raw values from combat units
    mobility_raw = {}
    for line_slug in ARCHERY_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
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
        line_key = f"{line_slug}|imperial"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores

    return all_role_scores


def compute_stable_role_scores():
    """Compute benchmark-based scores for all Imperial stable units.

    Uses the same pattern as archery: simulate benchmarks, min-max normalize
    each one 0-100 across all stable units, then average into composites.

    Final: stable_effectiveness = 0.7 * general_combat + 0.3 * anti_cav

    Returns dict: {"stable|Imperial": {civ|slug: {score_type: value, ...}, ...}}"""

    # Load benchmark units
    bench_cache = {}
    for key, civ, slug, age, mode, param in STABLE_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: stable benchmark {civ}/{slug}/{age} not found")

    # Collect all Imperial stable units from all source lines
    all_units = []
    for line_slug in STABLE_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
        all_units.extend(units)

    # Exclude Elephant Archers (ranged units already scored in archery rankings)
    all_units = [u for u in all_units if "ele_archer" not in u["unit_slug"]]

    if not all_units:
        return {}

    all_scores = {}

    # Run each unit against all benchmarks
    for u in all_units:
        cu = u["combat_unit"]
        unit_cost = calc_weighted_cost(
            cu["cost_food"], cu["cost_wood"], cu["cost_gold"], True
        )
        sk = f"{u['civ_name']}|{u['unit_slug']}"
        scores = {}

        for key, civ, slug, age, mode, param in STABLE_BENCHMARKS:
            bench = bench_cache[(civ, slug, age)]
            if bench is None:
                scores[key] = 0.0
                continue

            if mode == "res":
                bench_cost = calc_weighted_cost(
                    bench["cost_food"],
                    bench["cost_wood"],
                    bench["cost_gold"],
                    True,
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
                fake_res = m_count * o_count
                winner, _, _, hp1, hp2 = simulate_battle(
                    cu,
                    bench,
                    fake_res,
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

    # Save raw scores before normalization
    gc_keys = [k for k, *_ in STABLE_BENCHMARKS if k.startswith("gc_")]
    ac_only_keys = [k for k, *_ in STABLE_BENCHMARKS if k.startswith("ac_")]
    all_bench_keys = gc_keys + ac_only_keys

    for key in all_bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Min-max normalize each benchmark score across all stable units (0-100)
    for bk in all_bench_keys:
        vals = [s[bk] for s in all_scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for s in all_scores.values():
            s[bk] = round((s[bk] - lo) / span * 100, 1)

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

    # Apply speed weighting: multiply composites by speed, re-normalize across all stable
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "stable_effectiveness"],
        scope="pool",
    )

    # Clean up temp speed refs
    for s in all_scores.values():
        s.pop("_speed", None)

    # Return in the format write_role_scores_to_db expects: {line_age_key: {unit_key: scores}}
    return {"stable|imperial": all_scores}


# ===== Siege anti-building scoring =====

# Fully upgraded Spanish Castle (Masonry + Architecture + Hoardings + all arrow techs)
SIEGE_CASTLE_TARGET = {
    "hp": 7028,           # 4800 * 1.1 * 1.1 * 1.21
    "armor": {
        3: 13,            # pierce: 11 + 1 + 1
        4: 10,            # melee: 8 + 1 + 1
        11: 6,            # standard building: 0 + 3 + 3
        21: 0,            # standard buildings class (no bonus armor)
    },
    "arrows": 5,          # base arrows (no garrison)
    "arrow_attack": 15,   # 11 + 1 + 1 + 1 + 1 (Fletching/Bodkin/Bracer/Chemistry)
    "arrow_range": 11,    # 8 + 1 + 1 + 1
    "reload": 2.0,
}

SIEGE_SCORE_TYPES = [
    "anti_building_score",
    "time_to_kill",
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

    Returns time in seconds to destroy the castle, or MAX_TIME if it survives.
    Castle focus-fires one unit at a time. Melee units need closing time.
    """
    DT = 0.1
    MAX_TIME = 600.0

    remaining_hp = float(castle_hp)
    units_alive = n_units
    focused_unit_hp = float(unit_hp)
    time = 0.0

    # Closing time for units that need to walk into range
    if unit_range < castle_range:
        closing_distance = castle_range - unit_range
        closing_time = closing_distance / unit_speed if unit_speed > 0 else MAX_TIME

        # During approach: castle fires but units can't attack yet
        while time < closing_time and units_alive > 0:
            focused_unit_hp -= castle_dps * DT
            if focused_unit_hp <= 0:
                units_alive -= 1
                if units_alive > 0:
                    focused_unit_hp = float(unit_hp)
            time += DT

    # Combat phase: units attack castle, castle fires back
    while remaining_hp > 0 and units_alive > 0 and time < MAX_TIME:
        focused_unit_hp -= castle_dps * DT
        if focused_unit_hp <= 0:
            units_alive -= 1
            if units_alive > 0:
                focused_unit_hp = float(unit_hp)

        remaining_hp -= units_alive * unit_dps * DT
        time += DT

    return time if remaining_hp <= 0 else MAX_TIME


def compute_siege_antibuilding_scores():
    """Compute anti-building scores for all siege units (Castle + Imperial).

    Each unit gets 1000 weighted resources. They attack a fully upgraded
    Spanish Castle. Ranked by time to destroy (faster = higher score).

    Returns dict in write_role_scores_to_db format.
    """
    castle = SIEGE_CASTLE_TARGET
    all_scores = {}  # (line_slug, age) -> {sk: scores}

    for age in ["castle", "imperial"]:
        is_imperial = age == "imperial"

        for line_slug in SIEGE_LINE_SLUGS:
            units = build_line_units(line_slug, age)
            if not units:
                continue

            for u in units:
                cu = u["combat_unit"]
                unit_cost = calc_weighted_cost(
                    cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
                )
                n_units = max(1, 1000 // unit_cost)

                # Damage per hit vs castle (full AoE2 damage model)
                attacks = cu.get("attacks", {})
                damage_per_hit = _calc_building_damage(attacks, castle["armor"])
                reload_time = 1.0 / cu["attack_speed"] if cu["attack_speed"] > 0 else 2.0
                unit_dps = damage_per_hit / reload_time

                # Fire Archer (Wu): Red Cliffs Tactics adds 5 fire damage over 5s
                # to buildings, ignoring armor, stacking per unit (= 1.0 DPS/unit)
                if "fire_archer_wu" in u["unit_slug"]:
                    unit_dps += 1.0

                # Does the unit outrange the castle?
                outranges = cu["attack_range"] > castle["arrow_range"]

                if outranges:
                    # No attrition — pure DPS
                    total_dps = n_units * unit_dps
                    ttk = castle["hp"] / total_dps if total_dps > 0 else 600.0
                else:
                    # Attrition: castle fires at units
                    dmg_per_arrow = max(1, castle["arrow_attack"] - cu["pierce_armor"])
                    castle_dps = castle["arrows"] * dmg_per_arrow / castle["reload"]

                    ttk = _simulate_siege_vs_castle(
                        n_units, cu["hp"], unit_dps, castle["hp"], castle_dps,
                        cu["movement_speed"], cu["attack_range"], castle["arrow_range"],
                    )

                sk = f"{u['civ_name']}|{u['unit_slug']}"
                all_scores.setdefault((line_slug, age), {})[sk] = {
                    "time_to_kill": round(min(ttk, 600.0), 1),
                    "_speed": cu["movement_speed"],
                }

    # Normalize per (line_slug, age): faster = higher score (0-100, inverted)
    for (line_slug, age), scores in all_scores.items():
        ttk_vals = [s["time_to_kill"] for s in scores.values()]
        lo, hi = min(ttk_vals), max(ttk_vals)
        span = hi - lo if hi != lo else 1
        for s in scores.values():
            s["anti_building_score"] = round((hi - s["time_to_kill"]) / span * 100, 1)

    # Apply speed weighting per line (exempt trebuchet — speed=0)
    for (line_slug, age), scores in all_scores.items():
        if line_slug == "trebuchet":
            continue
        weighted = {}
        for sk, s in scores.items():
            speed = s.get("_speed", 1.0)
            weighted[sk] = s["anti_building_score"] * speed
        vals = list(weighted.values())
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for sk in scores:
            scores[sk]["anti_building_score"] = round(
                (weighted[sk] - lo) / span * 100, 1
            )

    # Clean up temp speed refs
    for (line_slug, age), scores in all_scores.items():
        for s in scores.values():
            s.pop("_speed", None)

    # Format for write_role_scores_to_db (keyed per line_slug)
    result = {}
    for (line_slug, age), scores in all_scores.items():
        result[f"{line_slug}|{age}"] = scores
    return result


INFANTRY_ROLE_SCORE_TYPES = [
    "militia_value",
    "general_combat",
    "anti_cav",
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "ac_30v30_vs_elephant",
    "ac_30v30_vs_hussar",
    "ac_3k_vs_elephant",
    "ac_3k_vs_hussar",
    # Raw (pre-normalization) scores
    "gc_30v30_vs_paladin_raw",
    "gc_30v30_vs_arb_raw",
    "gc_30v30_vs_champ_raw",
    "gc_3k_vs_paladin_raw",
    "gc_3k_vs_arb_raw",
    "gc_3k_vs_champ_raw",
    "ac_30v30_vs_elephant_raw",
    "ac_30v30_vs_hussar_raw",
    "ac_3k_vs_elephant_raw",
    "ac_3k_vs_hussar_raw",
    # Anti-cav ranking scores
    "anti_cav_total",
    "frontline",
    "anti_cav_value",
    "ac_vs_paladin",
    "ac_vs_hussar",
    "ac_vs_heavy_camel",
    "ac_vs_elephant",
    "ac_vs_halb",
    "ac_vs_arb",
    # Raiding ranking scores
    "raid_speed",
    "raid_vill_kill",
    "raid_building",
    "raiding_value",
    "raid_vs_tc_nmin",
    "raid_vs_castle_nmin",
]


def compute_anti_cav_scores(all_scores, sk_to_line):
    """Compute anti-cav ranking scores for all infantry units (in-place).

    Uses the same pooled all_scores dict from compute_infantry_role_scores.
    Adds anti_cav_total, frontline, anti_cav_value and raw sub-scores.
    """
    # Load benchmark opponents
    bench_cache = {}
    for key, civ, slug, age, mode, param in ANTI_CAV_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
            if bench_cache[cache_key] is None:
                print(f"  WARNING: anti-cav benchmark {civ}/{slug}/{age} not found")

    # Simulate each infantry unit vs each anti-cav benchmark
    for sk, scores in all_scores.items():
        cu = scores["_combat_unit"]
        unit_cost = calc_weighted_cost(
            cu["cost_food"], cu["cost_wood"], cu["cost_gold"], True
        )

        for key, civ, slug, age, mode, param in ANTI_CAV_BENCHMARKS:
            bench = bench_cache.get((civ, slug, age))
            if bench is None:
                scores[key] = 0.0
                continue

            bench_cost = calc_weighted_cost(
                bench["cost_food"], bench["cost_wood"], bench["cost_gold"], True
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

    # Compute raw derived scores
    for sk, scores in all_scores.items():
        scores["anti_cav_total"] = (
            scores["ac_vs_paladin"]
            + scores["ac_vs_hussar"]
            + scores["ac_vs_heavy_camel"]
            + scores["ac_vs_elephant"]
        ) / 4
        scores["frontline"] = (scores["ac_vs_halb"] + scores["ac_vs_arb"]) / 2

    # Normalize to 0–100 across all infantry
    for key in ["anti_cav_total", "frontline"]:
        vals = [s[key] for s in all_scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for s in all_scores.values():
            s[key] = round((s[key] - lo) / span * 100, 1)

    # Compute weighted composite
    for sk, scores in all_scores.items():
        scores["anti_cav_value"] = round(
            0.90 * scores["anti_cav_total"] + 0.10 * scores["frontline"],
            1,
        )


# ---------------------------------------------------------------------------
# Combined anti-cav ranking (infantry + qualifying stable units)
# ---------------------------------------------------------------------------

# The 4 shared benchmarks used for cross-line anti-cav comparison (3K res each)
COMBINED_AC_BENCHMARKS = [
    ("ac_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
    ("ac_vs_hussar", "Spanish", "hussar", "Imperial", "res", 3000),
    ("ac_vs_heavy_camel", "Persians", "heavy_camel", "Imperial", "res", 3000),
    ("ac_vs_elephant", "Vietnamese", "elite_elephant", "Imperial", "res", 3000),
]

COMBINED_AC_KEYS = [k for k, *_ in COMBINED_AC_BENCHMARKS]


def compute_combined_anti_cav_scores(stable_role_scores):
    """Combine infantry and qualifying stable anti-cav scores into one pool.

    1. Build infantry units and simulate 4 shared benchmarks
    2. Filter stable units to above-median anti_cav specialists
    3. Simulate same 4 benchmarks against qualifying stable units
    4. Pool, min-max normalize 0-100, compute anti_cav_combined
    5. Return dict for write_role_scores_to_db: {"anti_cav_pool|imperial": {civ|slug: scores}}
    """
    bench_cache = {}
    for key, civ, slug, age, mode, param in COMBINED_AC_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
            if bench_cache[cache_key] is None:
                print(f"  WARNING: combined AC benchmark {civ}/{slug}/{age} not found")

    def _sim_unit_vs_benchmarks(cu):
        """Simulate a combat unit against the 4 shared AC benchmarks."""
        unit_cost = calc_weighted_cost(
            cu["cost_food"], cu["cost_wood"], cu["cost_gold"], True
        )
        raw = {}
        for key, civ, slug, age, mode, param in COMBINED_AC_BENCHMARKS:
            bench = bench_cache.get((civ, slug, age))
            if bench is None:
                raw[key] = 0.0
                continue
            bench_cost = calc_weighted_cost(
                bench["cost_food"], bench["cost_wood"], bench["cost_gold"], True
            )
            winner, _, _, hp1, hp2 = simulate_battle(
                cu, bench, param,
                cost1_override=unit_cost, cost2_override=bench_cost,
                return_hp=True,
            )
            if winner == 1:
                raw[key] = round(hp1 * 100, 1)
            elif winner == 2:
                raw[key] = round(-hp2 * 100, 1)
            else:
                raw[key] = 0.0
        return raw

    # --- Build and simulate infantry units ---
    pool = {}
    infantry_lines = ["militia", "spear", "shock_infantry"]
    for line_slug in infantry_lines:
        units = build_line_units(line_slug, "imperial")
        for u in units:
            cu = u["combat_unit"]
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            pool[sk] = _sim_unit_vs_benchmarks(cu)
            pool[sk]["_speed"] = cu["movement_speed"]

    infantry_count = len(pool)

    # --- Filter qualifying stable units (above-median anti_cav) ---
    stable_dict = stable_role_scores.get("stable|imperial", {})
    if stable_dict:
        ac_scores = [s.get("anti_cav", 0) for s in stable_dict.values()]
        ac_median = sorted(ac_scores)[len(ac_scores) // 2] if ac_scores else 0
    else:
        ac_median = 0

    # --- Simulate qualifying stable units ---
    stable_count = 0
    for line_slug in STABLE_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
        for u in units:
            if "ele_archer" in u["unit_slug"]:
                continue
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            # Check if this unit qualifies (above-median anti_cav)
            stable_scores = stable_dict.get(sk, {})
            if stable_scores.get("anti_cav", 0) < ac_median:
                continue
            cu = u["combat_unit"]
            pool[sk] = _sim_unit_vs_benchmarks(cu)
            pool[sk]["_speed"] = cu["movement_speed"]
            stable_count += 1

    print(f"  Combined anti-cav pool: {len(pool)} units ({infantry_count} infantry + {stable_count} stable)")

    if not pool:
        return {}

    # --- Min-max normalize each benchmark across the combined pool ---
    for key in COMBINED_AC_KEYS:
        vals = [p[key] for p in pool.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for p in pool.values():
            p[key] = round((p[key] - lo) / span * 100, 1)

    # --- Compute anti_cav_combined (average of 4 normalized scores) ---
    for sk, raw in pool.items():
        raw["anti_cav_combined"] = round(
            sum(raw[k] for k in COMBINED_AC_KEYS) / len(COMBINED_AC_KEYS), 1
        )

    # Apply speed weighting: multiply anti_cav_combined by speed, re-normalize
    _apply_speed_weighting(pool, ["anti_cav_combined"], scope="pool")

    # Clean up temp speed refs
    for p in pool.values():
        p.pop("_speed", None)

    # --- Format for write_role_scores_to_db ---
    result = {"anti_cav_pool|imperial": pool}
    return result


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


def compute_raiding_scores(all_scores, sk_to_line):
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
    Clears existing scores for those lines before inserting.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for slug in line_slugs:
        c.execute("DELETE FROM battle_scores WHERE line_slug=?", (slug,))

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
        role_scores = compute_infantry_role_scores()
        write_role_scores_to_db(role_scores, INFANTRY_LINE_SLUGS, INFANTRY_ROLE_SCORE_TYPES)
        total = sum(len(v) for v in role_scores.values())
        print(
            f"Infantry roles: {total} units across {len(role_scores)} lines in {time.time() - start:.1f}s"
        )

        archery_start = time.time()
        archery_scores = compute_archery_role_scores()
        write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
        total_archery = sum(len(v) for v in archery_scores.values())
        print(
            f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {time.time() - archery_start:.1f}s"
        )

        stable_start = time.time()
        stable_scores = compute_stable_role_scores()
        write_role_scores_to_db(stable_scores, ["stable"], STABLE_SCORE_TYPES)
        total_stable = sum(len(v) for v in stable_scores.values())
        print(
            f"Stable roles: {total_stable} units in {time.time() - stable_start:.1f}s"
        )

        siege_start = time.time()
        siege_scores = compute_siege_antibuilding_scores()
        write_role_scores_to_db(siege_scores, SIEGE_LINE_SLUGS, SIEGE_SCORE_TYPES)
        total_siege = sum(len(v) for v in siege_scores.values())
        print(
            f"Siege anti-building: {total_siege} units in {time.time() - siege_start:.1f}s"
        )

        # Combined anti-cav pool (infantry + qualifying stable)
        ac_start = time.time()
        combined_ac = compute_combined_anti_cav_scores(stable_scores)
        write_role_scores_to_db(combined_ac, ["anti_cav_pool"], ["anti_cav_combined"])
        print(f"Combined anti-cav: {time.time() - ac_start:.1f}s")

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
        if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS or line_slug in STABLE_LINE_SLUGS or line_slug in SIEGE_LINE_SLUGS or line_slug in HIDDEN_LINE_SLUGS:
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
        if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS or line_slug in STABLE_LINE_SLUGS or line_slug in SIEGE_LINE_SLUGS or line_slug in HIDDEN_LINE_SLUGS:
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

    # Infantry role scores (written to DB only, not JSON)
    role_start = time.time()
    role_scores = compute_infantry_role_scores()
    write_role_scores_to_db(role_scores, INFANTRY_LINE_SLUGS, INFANTRY_ROLE_SCORE_TYPES)
    role_time = time.time() - role_start
    total_infantry = sum(len(v) for v in role_scores.values())
    print(
        f"Infantry roles: {total_infantry} units across {len(role_scores)} lines in {role_time:.1f}s"
    )

    # Archery role scores (written to DB, not JSON)
    archery_start = time.time()
    archery_scores = compute_archery_role_scores()
    write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
    archery_time = time.time() - archery_start
    total_archery = sum(len(v) for v in archery_scores.values())
    print(
        f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {archery_time:.1f}s"
    )

    # Stable role scores (written to DB, not JSON)
    stable_start = time.time()
    stable_scores = compute_stable_role_scores()
    write_role_scores_to_db(stable_scores, ["stable"], STABLE_SCORE_TYPES)
    stable_time = time.time() - stable_start
    total_stable = sum(len(v) for v in stable_scores.values())
    print(
        f"Stable roles: {total_stable} units in {stable_time:.1f}s"
    )

    # Siege anti-building scores (written to DB, not JSON)
    siege_start = time.time()
    siege_scores = compute_siege_antibuilding_scores()
    write_role_scores_to_db(siege_scores, SIEGE_LINE_SLUGS, SIEGE_SCORE_TYPES)
    siege_time = time.time() - siege_start
    total_siege = sum(len(v) for v in siege_scores.values())
    print(
        f"Siege anti-building: {total_siege} units in {siege_time:.1f}s"
    )

    # Combined anti-cav pool (infantry + qualifying stable, written to DB)
    ac_start = time.time()
    combined_ac = compute_combined_anti_cav_scores(stable_scores)
    write_role_scores_to_db(combined_ac, ["anti_cav_pool"], ["anti_cav_combined"])
    ac_time = time.time() - ac_start
    print(f"Combined anti-cav: {ac_time:.1f}s")

    # Compute rankings for all DB scores (rank + median_delta)
    ranking_start = time.time()
    compute_rankings()
    ranking_time = time.time() - ranking_start
    print(f"Rankings: {ranking_time:.1f}s")

    # Write output (round-robin + benchmarks only, no militia)
    out_path = os.path.join(os.path.dirname(__file__), "battle_scores.json")
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
