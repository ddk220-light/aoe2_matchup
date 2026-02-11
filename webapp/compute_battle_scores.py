"""
Standalone script to pre-compute battle ranking scores for the unit rankings page.

Run this after regenerating aoe2_reference.db to produce battle_scores.json.
The Flask server loads this file at startup (no simulations at serve time).

Usage:
    cd webapp && python3 compute_battle_scores.py            # incremental (cached)
    cd webapp && python3 compute_battle_scores.py --full      # force full recompute
"""

import argparse
import copy
import hashlib
import json
import os
import sqlite3
import time

from simulation import prepare_combat_unit, simulate_battle

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "battle_cache.json")
EXTRACTED_UNITS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "database_creation", "extracted_data", "units.json"
)
CACHE_VERSION = 10

# Load extracted units data for dismount resolution
_EXTRACTED_UNITS = {}
if os.path.exists(EXTRACTED_UNITS_PATH):
    with open(EXTRACTED_UNITS_PATH) as f:
        for u in json.load(f):
            _EXTRACTED_UNITS[u["id"]] = u


def _resolve_dismount(unit_id):
    """Look up dismount unit stats from extracted data. Returns dict or None."""
    u = _EXTRACTED_UNITS.get(int(unit_id))
    if not u:
        return None
    creatable = u.get("creatable", {})
    attacks = {}
    armors = {}
    for entry in creatable.get("attacks", []):
        attacks[str(entry["class"])] = entry["amount"]
    for entry in creatable.get("armours", []):
        armors[str(entry["class"])] = entry["amount"]
    reload_time = creatable.get("reload_time", 2.0)
    attack_speed = round(1.0 / reload_time, 3) if reload_time else 0.5
    frame_delay = creatable.get("frame_delay", 0)
    max_frame = max(1, creatable.get("max_frame", 10))
    attack_delay = frame_delay * reload_time / max_frame if frame_delay else 0
    return {
        "hp": int(u.get("hit_points", 0)),
        "attack": int(creatable.get("displayed_attack", 0)),
        "melee_armor": int(creatable.get("displayed_melee_armour", 0)),
        "pierce_armor": int(creatable.get("displayed_range_armour", 0)),
        "attack_speed": attack_speed,
        "attack_delay": attack_delay,
        "movement_speed": u.get("speed", 0.9),
        "attacks_json": json.dumps(attacks) if attacks else None,
        "armors_json": json.dumps(armors) if armors else None,
    }


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
            "Malay": ("karambit_warrior_malay", "elite_karambit_warrior_malay"),
            "Burgundians": ("flemish_militia_burgundians", None),
            "Sicilians": ("serjeant_sicilians", "elite_serjeant_sicilians"),
            "Poles": ("obuch_poles", "elite_obuch_poles"),
            "Dravidians": (
                "urumi_swordsman_dravidians",
                "elite_urumi_swordsman_dravidians",
            ),
            "Hindustanis": ("ghulam_hindustanis", "elite_ghulam_hindustanis"),
            "Gurjaras": (
                "chakram_thrower_gurjaras",
                "elite_chakram_thrower_gurjaras",
            ),
            "Armenians": ("warrior_priest_armenians", "warrior_priest_armenians"),
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
        },
    },
    "archer": {
        "name": "Archers & Gunpowder",
        "building": "Archery Range",
        "castle_slug": "crossbow",
        "imperial_slug": "arbalester",
        "extra_imperial_slugs": ["hand_cannoneer"],
        "unique_units": {
            "Britons": ("longbowman_britons", "elite_longbowman_britons"),
            "Chinese": ("chu_ko_nu_chinese", "elite_chu_ko_nu_chinese"),
            "Mayans": ("plumed_archer_mayans", "elite_plumed_archer_mayans"),
            "Italians": (
                "genoese_crossbowman_italians",
                "elite_genoese_crossbowman_italians",
            ),
            "Turks": ("janissary_turks", "elite_janissary_turks"),
            "Franks": ("throwing_axeman_franks", "elite_throwing_axeman_franks"),
            "Incas": ("slinger", "imp_slinger"),
            "Vietnamese": (
                "rattan_archer_vietnamese",
                "elite_rattan_archer_vietnamese",
            ),
            "Malians": ("gbeto_malians", "elite_gbeto_malians"),
            "Armenians": (
                "composite_bowman_armenians",
                "elite_composite_bowman_armenians",
            ),
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
        "unique_units": {
            "Mongols": ("mangudai_mongols", "elite_mangudai_mongols"),
            "Saracens": ("mameluke_saracens", "elite_mameluke_saracens"),
            "Koreans": ("war_wagon_koreans", "elite_war_wagon_koreans"),
            "Spanish": ("conquistador_spanish", "elite_conquistador_spanish"),
            "Berbers": ("camel_archer_berbers", "elite_camel_archer_berbers"),
            "Burmese": ("arambai_burmese", "elite_arambai_burmese"),
            "Cumans": ("kipchak_cumans", "elite_kipchak_cumans"),
            "Bengalis": (
                "ratha_(ranged)_bengalis",
                "elite_ratha_(ranged)_bengalis",
            ),
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
        "unique_units": {
            "Portuguese": ("organ_gun_portuguese", "elite_organ_gun_portuguese"),
            "Bohemians": ("hussite_wagon_bohemians", "elite_hussite_wagon_bohemians"),
        },
    },
    "scorpion": {
        "name": "Scorpion Line",
        "building": "Siege Workshop",
        "castle_slug": "scorpion",
        "imperial_slug": "heavy_scorpion",
        "unique_units": {
            "Khmer": ("ballista_elephant_khmer", "elite_ballista_elephant_khmer"),
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
        "unique_units": {},
    },
    "all_cavalry": {
        "name": "All Cavalry (Gold)",
        "building": "Stable",
        "castle_slug": None,
        "imperial_slug": None,
        "castle_slugs": ["knight", "camel", "steppe_lancer", "elephant"],
        "imperial_slugs": ["paladin", "heavy_camel", "elite_steppe", "elite_elephant"],
        "unique_units": {
            "Byzantines": ("cataphract_byzantines", "elite_cataphract_byzantines"),
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
            "Slavs": ("boyar_slavs", "elite_boyar_slavs"),
            "Persians": ("war_elephant_persians", "elite_war_elephant_persians"),
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
        },
    },
    "all_ranged": {
        "name": "All Ranged (Gold)",
        "building": "Archery Range",
        "castle_slug": None,
        "imperial_slug": None,
        "castle_slugs": ["crossbow", "cav_archer"],
        "imperial_slugs": ["arbalester", "heavy_cav_archer", "hand_cannoneer"],
        "unique_units": {
            "Britons": ("longbowman_britons", "elite_longbowman_britons"),
            "Chinese": ("chu_ko_nu_chinese", "elite_chu_ko_nu_chinese"),
            "Mayans": ("plumed_archer_mayans", "elite_plumed_archer_mayans"),
            "Italians": (
                "genoese_crossbowman_italians",
                "elite_genoese_crossbowman_italians",
            ),
            "Turks": ("janissary_turks", "elite_janissary_turks"),
            "Franks": ("throwing_axeman_franks", "elite_throwing_axeman_franks"),
            "Incas": ("slinger", "imp_slinger"),
            "Mongols": ("mangudai_mongols", "elite_mangudai_mongols"),
            "Saracens": ("mameluke_saracens", "elite_mameluke_saracens"),
            "Koreans": ("war_wagon_koreans", "elite_war_wagon_koreans"),
            "Spanish": ("conquistador_spanish", "elite_conquistador_spanish"),
            "Berbers": ("camel_archer_berbers", "elite_camel_archer_berbers"),
            "Burmese": ("arambai_burmese", "elite_arambai_burmese"),
            "Vietnamese": (
                "rattan_archer_vietnamese",
                "elite_rattan_archer_vietnamese",
            ),
            "Malians": ("gbeto_malians", "elite_gbeto_malians"),
            "Cumans": ("kipchak_cumans", "elite_kipchak_cumans"),
            "Bengalis": (
                "ratha_(ranged)_bengalis",
                "elite_ratha_(ranged)_bengalis",
            ),
            "Armenians": (
                "composite_bowman_armenians",
                "elite_composite_bowman_armenians",
            ),
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
    """Build a dict from a ref_units row, compatible with prepare_combat_unit()."""
    uid = row["id"]

    rc.execute(
        "SELECT property_name, property_value FROM ref_special_effects WHERE ref_unit_id=?",
        (uid,),
    )
    special = {}
    for s in rc.fetchall():
        try:
            special[s["property_name"]] = float(s["property_value"])
        except (ValueError, TypeError):
            special[s["property_name"]] = s["property_value"]

    rc.execute(
        """SELECT projectile_type, projectile_count, projectile_speed,
                  attacks_json, blast_radius, is_siege_projectile
           FROM ref_projectiles WHERE ref_unit_id=?""",
        (uid,),
    )
    primary_proj = None
    extra_proj = None
    charge_proj = None
    for p in rc.fetchall():
        if p["projectile_type"] == "primary":
            primary_proj = dict(p)
        elif p["projectile_type"] == "extra":
            extra_proj = dict(p)
        elif p["projectile_type"] == "charge":
            charge_proj = dict(p)

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
        "projectile_speed": (
            primary_proj["projectile_speed"]
            if primary_proj and primary_proj["projectile_speed"]
            else row["projectile_speed"] or 0
        ),
        "is_siege_projectile": (
            primary_proj["is_siege_projectile"] if primary_proj else 0
        ),
        "splash_radius": special.get("splash_radius", 0),
        "extra_projectiles": extra_proj["projectile_count"] if extra_proj else 0,
        "extra_projectile_attacks_json": (
            extra_proj["attacks_json"] if extra_proj else None
        ),
        "trample_percent": special.get("trample_percent", 0),
        "trample_radius": special.get("trample_radius", 0),
        "trample_flat_damage": special.get("trample_flat_damage", 0),
        "hp_regen": special.get("hp_regen", 0),
        "charge_projectile_count": (
            charge_proj["projectile_count"] if charge_proj else 0
        ),
        "charge_projectile_speed": (
            charge_proj["projectile_speed"] if charge_proj else 0
        ),
        "charge_projectile_attacks_json": (
            charge_proj["attacks_json"] if charge_proj else None
        ),
        "charge_attack_range": float(special.get("charge_attack_range", 0)),
        "charge_ignores_armor": int(special.get("charge_ignores_armor", 0)),
        "ignores_pierce_armor": int(special.get("ignores_pierce_armor", 0)),
        "ignores_melee_armor": int(special.get("ignores_melee_armor", 0)),
        "bonus_damage_reduction": special.get("bonus_damage_reduction", 0),
        "splash_on_hit_radius": special.get("splash_on_hit_radius", 0),
        "dodge_shield_max": int(special.get("dodge_shield_max", 0)),
        "dodge_shield_recharge": special.get("dodge_shield_recharge", 0),
        "bleed_dps": special.get("bleed_dps", 0),
        "bleed_duration": special.get("bleed_duration", 0),
        "block_first_melee": int(special.get("block_first_melee", 0)),
        "attack_bonus_per_kill": int(special.get("attack_bonus_per_kill", 0)),
        "first_attack_extra_projectiles": int(
            special.get("first_attack_extra_projectiles", 0)
        ),
        "pass_through_percent": special.get("pass_through_percent", 0),
        "hp_transform_threshold": special.get("hp_transform_threshold", 0),
        "pop_space": special.get("pop_space", 1.0),
        "armor_strip_per_hit": int(special.get("armor_strip_per_hit", 0)),
        "charge_attack_melee": int(special.get("charge_attack_melee", 0)),
        "charge_recharge_time": special.get("charge_recharge_time", 0),
        "attack_bonus_nearby": int(special.get("attack_bonus_nearby", 0)),
        "nearby_bonus_count": int(special.get("nearby_bonus_count", 0)),
        # Dismount on death (Konnik): from hardcoded config via special effects
        "dismount_hp": (
            int(special["dismount_hp"]) if "dismount_hp" in special else None
        ),
        "dismount_attack": (
            int(special["dismount_attack"]) if "dismount_attack" in special else None
        ),
        "dismount_melee_armor": (
            int(special["dismount_melee_armor"])
            if "dismount_melee_armor" in special
            else None
        ),
        "dismount_pierce_armor": (
            int(special["dismount_pierce_armor"])
            if "dismount_pierce_armor" in special
            else None
        ),
        "dismount_attack_speed": special.get("dismount_attack_speed"),
        "dismount_attack_delay": special.get("dismount_attack_delay"),
        "dismount_movement_speed": special.get("dismount_movement_speed"),
        "dismount_attacks_json": special.get("dismount_attacks_json"),
        "dismount_armors_json": special.get("dismount_armors_json"),
    }


def calc_weighted_cost(food, wood, gold, is_imperial):
    if is_imperial:
        cost = (wood or 0) + (food or 0) + (gold or 0)
    else:
        cost = (wood or 0) + 1.5 * (food or 0) + (gold or 0)
    return int(cost) if cost > 0 else 100


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
            "SELECT * FROM ref_units WHERE unit_slug=? AND civ_name=?",
            (uu_slug, civ_name),
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


def main():
    parser = argparse.ArgumentParser(description="Compute battle ranking scores")
    parser.add_argument(
        "--full", action="store_true", help="Force full recomputation (ignore cache)"
    )
    args = parser.parse_args()

    start = time.time()

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

    # Build all units and compute fingerprints
    current_fps = {}
    for line_slug, config in UNIT_LINES.items():
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

    # Write output
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
