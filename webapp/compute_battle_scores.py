"""
Standalone script to pre-compute battle ranking scores for the unit rankings page.

Run this after regenerating aoe2_reference.db to produce battle_scores.json.
The Flask server loads this file at startup (no simulations at serve time).

Usage:
    cd webapp && python3 compute_battle_scores.py
"""

import json
import os
import sqlite3
import time

from simulation import prepare_combat_unit, simulate_battle

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")

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
        },
    },
    "skirmisher": {
        "name": "Skirmisher Line",
        "building": "Archery Range",
        "castle_slug": "elite_skirm",
        "imperial_slug": "imp_elite_skirm",
        "unique_units": {},
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
        "castle_slug": None,
        "imperial_slug": None,
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
    "scorpion": {
        "name": "Scorpion Line",
        "building": "Siege Workshop",
        "castle_slug": "scorpion",
        "imperial_slug": "heavy_scorpion",
        "unique_units": {},
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
        "castle_slugs": ["knight", "camel", "steppe_lancer"],
        "imperial_slugs": ["paladin", "heavy_camel", "elite_steppe"],
        "unique_units": {
            "Byzantines": ("cataphract_byzantines", "elite_cataphract_byzantines"),
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
            "Slavs": ("boyar_slavs", "elite_boyar_slavs"),
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
        },
    },
}

BENCHMARKS = [
    ("vs_champ", "Chinese", "champion", "Imperial"),
    ("vs_paladin", "Franks", "paladin", "Imperial"),
    ("vs_arb", "Chinese", "arbalester", "Imperial"),
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        "ignores_pierce_armor": 0,
        "ignores_melee_armor": 0,
        "bonus_damage_reduction": 0,
        "splash_on_hit_radius": 0,
        "dodge_shield_max": 0,
        "dodge_shield_recharge": 0,
        "bleed_dps": 0,
        "bleed_duration": 0,
        "block_first_melee": 0,
        "attack_bonus_per_kill": 0,
        "first_attack_extra_projectiles": 0,
        "pass_through_percent": special.get("pass_through_percent", 0),
        "hp_transform_threshold": 0,
        "dismount_hp": None,
        "dismount_attack": None,
        "dismount_melee_armor": None,
        "dismount_pierce_armor": None,
        "dismount_attack_speed": None,
        "dismount_attack_delay": None,
        "dismount_movement_speed": None,
        "dismount_attacks_json": None,
        "dismount_armors_json": None,
        "transform_hp": None,
        "transform_attack": None,
        "transform_melee_armor": None,
        "transform_pierce_armor": None,
        "transform_attack_speed": None,
        "transform_attack_delay": None,
        "transform_movement_speed": None,
        "transform_attacks_json": None,
        "transform_armors_json": None,
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

    # Fetch extra standard units (e.g. Hand Cannoneer in archer line)
    if not is_castle:
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


def compute_round_robin(line_slug, age):
    """Round-robin battles. Returns {civ_name|unit_slug: {score_30v30, score_3k, score_5k}}.
    Scores are -100..+100 (average HP% across all opponents)."""
    is_imperial = age == "imperial"
    units = build_line_units(line_slug, age)
    n = len(units)
    if n < 2:
        return {}

    keys = [(u["civ_name"], u["unit_slug"]) for u in units]
    # Accumulate HP scores per unit per scenario
    hp_totals = {k: [0.0, 0.0, 0.0] for k in keys}

    for i in range(n):
        for j in range(i + 1, n):
            ui = units[i]["combat_unit"]
            uj = units[j]["combat_unit"]
            ki, kj = keys[i], keys[j]

            ci = calc_weighted_cost(
                ui["cost_food"], ui["cost_wood"], ui["cost_gold"], is_imperial
            )
            cj = calc_weighted_cost(
                uj["cost_food"], uj["cost_wood"], uj["cost_gold"], is_imperial
            )

            # Scenario 1: 30v30
            w1, _, _, hp1_1, hp2_1 = simulate_battle(
                ui, uj, 0, fixed_count=30, return_hp=True
            )

            # Scenario 2: 3000 resources
            w2, _, _, hp1_2, hp2_2 = simulate_battle(
                ui, uj, 3000, cost1_override=ci, cost2_override=cj, return_hp=True
            )

            # Scenario 3: 5000 resources with upgrades
            upg_i = calc_weighted_cost(
                ui["upgrade_cost_food"],
                ui["upgrade_cost_wood"],
                ui["upgrade_cost_gold"],
                is_imperial,
            )
            upg_j = calc_weighted_cost(
                uj["upgrade_cost_food"],
                uj["upgrade_cost_wood"],
                uj["upgrade_cost_gold"],
                is_imperial,
            )
            budget_i = max(ci, 5000 - upg_i)
            budget_j = max(cj, 5000 - upg_j)
            adj_cj = max(1, int(budget_i * cj / budget_j)) if budget_j > 0 else cj
            w3, _, _, hp1_3, hp2_3 = simulate_battle(
                ui,
                uj,
                budget_i,
                cost1_override=ci,
                cost2_override=adj_cj,
                return_hp=True,
            )

            for idx, (w, h1, h2) in enumerate(
                [(w1, hp1_1, hp2_1), (w2, hp1_2, hp2_2), (w3, hp1_3, hp2_3)]
            ):
                s = _hp_score(w, h1, h2)
                hp_totals[ki][idx] += s
                hp_totals[kj][idx] -= s  # opposite sign for opponent

    opponents = n - 1
    scores = {}
    for k in keys:
        sk = f"{k[0]}|{k[1]}"
        scores[sk] = {
            "score_30v30": round(hp_totals[k][0] / opponents, 1),
            "score_3k": round(hp_totals[k][1] / opponents, 1),
            "score_5k": round(hp_totals[k][2] / opponents, 1),
        }
    return scores


def compute_benchmarks(bench_units):
    """Pit every unit against benchmark opponents. Returns nested dict."""
    all_scores = {}

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
                unit_cost = calc_weighted_cost(
                    cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
                )
                count_u = max(1, int(3000 // unit_cost))
                scores = {}

                for bkey, bciv, bslug, bage in BENCHMARKS:
                    if bkey not in bench_units:
                        scores[bkey] = -1
                        continue
                    bu = bench_units[bkey]
                    bench_cost = calc_weighted_cost(
                        bu["cost_food"], bu["cost_wood"], bu["cost_gold"], True
                    )
                    winner, _, _, hp_pct1, hp_pct2 = simulate_battle(
                        cu,
                        bu,
                        3000,
                        cost1_override=unit_cost,
                        cost2_override=bench_cost,
                        return_hp=True,
                    )
                    # Scale: +100 (unit won, lost 0% HP) to -100 (benchmark won, lost 0% HP)
                    if winner == 1:
                        scores[bkey] = round(hp_pct1 * 100, 1)
                    elif winner == 2:
                        scores[bkey] = round(-hp_pct2 * 100, 1)
                    else:
                        scores[bkey] = 0.0

                sk = f"{u['civ_name']}|{u['unit_slug']}"
                line_scores[sk] = scores

            all_scores[line_key] = line_scores

    return all_scores


def main():
    start = time.time()
    output = {"round_robin": {}, "benchmarks": {}}

    # Round-robin scores
    rr_count = 0
    for line_slug, config in UNIT_LINES.items():
        for age_key in ["castle", "imperial"]:
            slug = config.get(f"{age_key}_slug")
            multi_slugs = config.get(f"{age_key}_slugs", [])
            has_unique = bool(config.get("unique_units"))
            if not slug and not multi_slugs and not has_unique:
                continue
            scores = compute_round_robin(line_slug, age_key)
            if scores:
                output["round_robin"][f"{line_slug}|{age_key}"] = scores
                rr_count += 1

    rr_time = time.time() - start
    print(f"Round-robin: {rr_count} line-ages in {rr_time:.1f}s")

    # Benchmark scores
    bench_start = time.time()
    conn = get_db()
    rc = conn.cursor()
    bench_units = {}
    for key, civ, slug, age in BENCHMARKS:
        rc.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
            (civ, slug, age),
        )
        row = rc.fetchone()
        if row:
            cd = build_combat_dict(rc, row)
            bench_units[key] = prepare_combat_unit(cd)
    conn.close()

    output["benchmarks"] = compute_benchmarks(bench_units)
    bench_time = time.time() - bench_start
    print(f"Benchmarks: {bench_time:.1f}s")

    # Write output
    out_path = os.path.join(os.path.dirname(__file__), "battle_scores.json")
    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    total = time.time() - start
    print(f"Total: {total:.1f}s -> {out_path}")


if __name__ == "__main__":
    main()
