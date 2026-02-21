import json
import os
import sqlite3

from flask import Flask, jsonify, redirect, render_template, request
from best_units import load_civ_power_units, get_matchup_recommendations, CIVS_WITHOUT_TREBUCHET


app = Flask(__name__)
app.json.sort_keys = False

# Database paths
DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_units.db")
REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")

# Age definitions
AGES = {
    "feudal": {"id": 2, "name": "Feudal Age"},
    "castle": {"id": 3, "name": "Castle Age"},
    "imperial": {"id": 4, "name": "Imperial Age"},
}


def get_db():
    """Get a database connection with row factory (legacy, for non-migrated endpoints)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_ref_db():
    """Get a connection to the reference/audit database."""
    conn = sqlite3.connect(REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_units_by_age():
    """Get list of available unit types organized by age."""
    conn = get_db()
    cursor = conn.cursor()

    units_by_age = {}
    for age_slug, age_data in AGES.items():
        cursor.execute(
            """
            SELECT slug, display_name
            FROM units
            WHERE age_id = ? AND unit_type = 'standard'
            ORDER BY display_name
            """,
            (age_data["id"],),
        )
        units = [
            {"id": row["slug"], "name": row["display_name"], "age": age_slug}
            for row in cursor.fetchall()
        ]
        units_by_age[age_slug] = {"name": age_data["name"], "units": units}

    conn.close()
    return units_by_age


@app.route("/")
def home():
    """Battle Sim is the homepage."""
    return render_template("simulate.html", active_nav="simulate")


@app.route("/units")
def units():
    units_by_age = get_units_by_age()
    ages = {k: v["name"] for k, v in AGES.items()}
    return render_template("index.html", units_by_age=units_by_age, ages=ages, active_nav="rankings")


@app.route("/civilizations")
def civ_view():
    """Civilization analysis page — shows power units, strengths, and strategic identity."""
    civs = _get_ref_civs()
    return render_template("civ_detail.html", civs=civs, active_nav="civ_select")


@app.route("/civilizations/<civ_name>")
def civ_detail(civ_name):
    """Civilization unit detail page."""
    if civ_name not in ORIGINAL_13_CIVS:
        return redirect("/civilizations")
    return render_template("deprecated-civ.html", civ_name=civ_name, active_nav="civ_detail")


@app.route("/civ")
def civ_redirect():
    """Backward compat redirect."""
    return redirect("/civilizations", code=301)


@app.route("/civ/<civ_name>")
def civ_detail_redirect(civ_name):
    """Backward compat redirect."""
    return redirect(f"/civilizations/{civ_name}", code=301)


@app.route("/simulate")
def simulate_redirect():
    """Redirect old /simulate URL to homepage."""
    return redirect("/", code=301)


@app.route("/api/armor-classes")
def api_armor_classes():
    """Get all armor class names."""
    conn = get_ref_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM armor_classes ORDER BY id")
    classes = {str(row["id"]): row["name"] for row in cursor.fetchall()}
    conn.close()
    return jsonify(classes)


ORIGINAL_13_CIVS = [
    "Armenians",
    "Aztecs",
    "Bengalis",
    "Berbers",
    "Bohemians",
    "Britons",
    "Bulgarians",
    "Burgundians",
    "Burmese",
    "Byzantines",
    "Celts",
    "Chinese",
    "Cumans",
    "Dravidians",
    "Ethiopians",
    "Franks",
    "Georgians",
    "Goths",
    "Gurjaras",
    "Hindustanis",
    "Huns",
    "Incas",
    "Italians",
    "Japanese",
    "Jurchens",
    "Khitans",
    "Khmer",
    "Koreans",
    "Lithuanians",
    "Magyars",
    "Malay",
    "Malians",
    "Mayans",
    "Mongols",
    "Persians",
    "Poles",
    "Portuguese",
    "Romans",
    "Saracens",
    "Shu",
    "Sicilians",
    "Slavs",
    "Spanish",
    "Tatars",
    "Teutons",
    "Turks",
    "Vietnamese",
    "Vikings",
    "Wei",
    "Wu",
]

_TREBUCHET_SLUGS = {"trebuchet", "traction_trebuchet"}


@app.route("/api/ref/civ/<civ_name>")
def api_ref_civ(civ_name):
    """Get all reference data for a civilization."""
    if civ_name not in ORIGINAL_13_CIVS:
        return jsonify({"error": "Civilization not in original 13"}), 404

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Get all units for this civ
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? ORDER BY age DESC, unit_name",
        (civ_name,),
    )
    units_rows = rc.fetchall()

    # Filter out trebuchets for civs that don't have them
    if civ_name in CIVS_WITHOUT_TREBUCHET:
        units_rows = [r for r in units_rows if r["unit_slug"] not in _TREBUCHET_SLUGS]

    # Get verifications
    main_conn = get_db()
    mc = main_conn.cursor()
    mc.execute("SELECT ref_unit_id FROM unit_verifications")
    verified_ids = {row["ref_unit_id"] for row in mc.fetchall()}
    main_conn.close()

    # Get armor class names
    rc.execute("SELECT id, name FROM armor_classes ORDER BY id")
    ac_names = {str(row["id"]): row["name"] for row in rc.fetchall()}

    units = []
    for row in units_rows:
        uid = row["id"]

        # Get techs applied
        rc.execute(
            """SELECT tech_name, tech_type, building, age_available, effect_description
               FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id""",
            (uid,),
        )
        techs = [dict(t) for t in rc.fetchall()]

        # Get stat chain
        rc.execute(
            """SELECT step_order, tech_name, tech_type,
                      hp, attack, melee_armor, pierce_armor,
                      speed, range_val, reload_time, accuracy, los,
                      train_time, cost_food, cost_wood, cost_gold,
                      attacks_json, armors_json
               FROM ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order""",
            (uid,),
        )
        stat_chain = [dict(s) for s in rc.fetchall()]

        # Get special effects
        rc.execute(
            """SELECT property_name, property_value, source, description
               FROM ref_special_effects WHERE ref_unit_id=?""",
            (uid,),
        )
        special = [dict(s) for s in rc.fetchall()]

        # Convert class IDs to names in attack/armor JSONs
        def convert_classes(json_str):
            if not json_str:
                return {}
            raw = json.loads(json_str)
            return {ac_names.get(k, f"class_{k}"): v for k, v in raw.items()}

        # Get projectiles
        rc.execute(
            """SELECT projectile_type, projectile_count, projectile_speed,
                      attacks_json, blast_radius, is_siege_projectile
               FROM ref_projectiles WHERE ref_unit_id=?""",
            (uid,),
        )
        projectiles_raw = rc.fetchall()
        projectiles = []
        for p in projectiles_raw:
            pd = dict(p)
            if pd.get("attacks_json"):
                pd["attacks"] = convert_classes(pd["attacks_json"])
            projectiles.append(pd)

        unit = {
            "id": uid,
            "unit_name": row["unit_name"],
            "unit_slug": row["unit_slug"],
            "unit_type": row["unit_type"],
            "age": row["age"],
            "unit_class_name": row["unit_class_name"],
            "is_ranged": bool(row["is_ranged"]),
            "verified": uid in verified_ids,
            "base_stats": {
                "hp": row["base_hp"],
                "attack": row["base_attack"],
                "melee_armor": row["base_melee_armor"],
                "pierce_armor": row["base_pierce_armor"],
                "range": row["base_range"],
                "speed": row["base_speed"],
                "reload_time": row["base_reload_time"],
                "attack_delay": row["base_attack_delay"],
                "accuracy": row["base_accuracy"],
                "los": row["base_los"],
                "cost_food": row["base_cost_food"],
                "cost_wood": row["base_cost_wood"],
                "cost_gold": row["base_cost_gold"],
                "train_time": row["base_train_time"],
            },
            "final_stats": {
                "hp": row["final_hp"],
                "attack": row["final_attack"],
                "melee_armor": row["final_melee_armor"],
                "pierce_armor": row["final_pierce_armor"],
                "range": row["final_range"],
                "speed": row["final_speed"],
                "reload_time": row["final_reload_time"],
                "attack_delay": row["final_attack_delay"],
                "accuracy": row["final_accuracy"],
                "los": row["final_los"],
                "cost_food": row["final_cost_food"],
                "cost_wood": row["final_cost_wood"],
                "cost_gold": row["final_cost_gold"],
                "train_time": row["final_train_time"],
            },
            "base_attacks": convert_classes(row["base_attacks_json"]),
            "final_attacks": convert_classes(row["final_attacks_json"]),
            "base_armors": convert_classes(row["base_armors_json"]),
            "final_armors": convert_classes(row["final_armors_json"]),
            "total_projectiles": row["total_projectiles"],
            "projectile_speed": row["projectile_speed"],
            "min_range": row["min_range"],
            "upgrade_cost": {
                "food": row["upgrade_cost_food"] or 0,
                "wood": row["upgrade_cost_wood"] or 0,
                "gold": row["upgrade_cost_gold"] or 0,
            },
            "techs_applied": techs,
            "stat_chain": stat_chain,
            "special_effects": special,
            "projectiles": projectiles,
        }
        units.append(unit)

    ref_conn.close()

    # Group by age
    by_age = {"Castle": [], "Imperial": []}
    for u in units:
        if u["age"] in by_age:
            by_age[u["age"]].append(u)

    return jsonify(
        {
            "civ_name": civ_name,
            "units_by_age": by_age,
            "total_units": len(units),
            "verified_count": sum(1 for u in units if u["verified"]),
        }
    )


# ===== Combat unit building from reference DB =====


def _build_combat_dict_from_ref(rc, row):
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
        "attack_range": row["final_range"] if row["is_ranged"] else 0,
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
        "dismount_hp": row["dismount_hp"],
        "dismount_attack": row["dismount_attack"],
        "dismount_melee_armor": row["dismount_melee_armor"],
        "dismount_pierce_armor": row["dismount_pierce_armor"],
        "dismount_attack_speed": row["dismount_attack_speed"],
        "dismount_attack_delay": row["dismount_attack_delay"],
        "dismount_movement_speed": row["dismount_movement_speed"],
        "dismount_attacks_json": row["dismount_attacks_json"],
        "dismount_armors_json": row["dismount_armors_json"],
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


@app.route("/api/ref/stat-chain/<int:ref_unit_id>")
def api_ref_stat_chain(ref_unit_id):
    """Get stat chain and techs applied for a single ref unit (for hover cards)."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute(
        """SELECT step_order, tech_name, tech_type,
                  hp, attack, melee_armor, pierce_armor,
                  speed, range_val, reload_time,
                  cost_food, cost_wood, cost_gold
           FROM ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order""",
        (ref_unit_id,),
    )
    chain = [dict(row) for row in rc.fetchall()]
    rc.execute(
        """SELECT tech_name, tech_type, building, age_available,
                  effect_description
           FROM ref_techs_applied WHERE ref_unit_id=? ORDER BY id""",
        (ref_unit_id,),
    )
    techs = [dict(row) for row in rc.fetchall()]
    ref_conn.close()
    return jsonify({"stat_chain": chain, "techs_applied": techs})


@app.route("/api/ref/combat-unit/<civ_name>/<unit_slug>")
def api_ref_combat_unit(civ_name, unit_slug):
    """Get combat-ready stats for a unit from reference DB (for battle simulator)."""
    if civ_name not in ORIGINAL_13_CIVS:
        return jsonify({"error": "Civilization not in original 13"}), 404

    age = request.args.get("age", "Imperial")

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Prefer requested age; fall back to any age if not found
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        rc.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?",
            (civ_name, unit_slug),
        )
        row = rc.fetchone()
    if not row:
        ref_conn.close()
        return jsonify({"error": f"Unit {unit_slug} not found for {civ_name}"}), 404

    result = _build_combat_dict_from_ref(rc, row)

    # Add stat chain for debug breakdown (HTTP endpoint only)
    rc.execute(
        """SELECT step_order, tech_name, tech_type, attack, melee_armor, pierce_armor,
                  attacks_json, armors_json
           FROM ref_stat_chain WHERE ref_unit_id=? ORDER BY step_order""",
        (row["id"],),
    )
    result["stat_chain"] = [
        {
            "step": sc["step_order"],
            "tech": sc["tech_name"],
            "type": sc["tech_type"],
            "attacks_json": sc["attacks_json"],
            "armors_json": sc["armors_json"],
        }
        for sc in rc.fetchall()
    ]

    # Extra fields for HTTP response
    result["name"] = row["unit_name"]
    result["civ"] = civ_name
    result["total_cost"] = (
        (row["final_cost_food"] or 0)
        + (row["final_cost_wood"] or 0)
        + (row["final_cost_gold"] or 0)
    )
    result["outline_size"] = row["outline_size_x"] or 0.2

    ref_conn.close()
    return jsonify(result)


# ===== Unit Lines config for rankings page =====
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
    "archery": {
        "name": "Ranged Effectiveness",
        "building": "Archery Range",
        "sub_lines": ["archer", "cav_archer", "skirmisher", "scorpion", "gunpowder"],
    },
    "infantry": {
        "name": "Infantry Effectiveness",
        "building": "Barracks",
        "sub_lines": ["militia", "spear", "shock_infantry"],
    },
    "stable": {
        "name": "Stable Units",
        "building": "Stable",
        "sub_lines": ["knight", "light_cav", "camel", "steppe_lancer", "elephant"],
    },
    "siege": {
        "name": "Anti-Building Effectiveness",
        "building": "Siege Workshop",
        "sub_lines": ["ram", "trebuchet", "bombard_cannon"],
    },
}

INFANTRY_LINE_SLUGS = {"militia", "spear", "shock_infantry"}
ARCHERY_LINE_SLUGS = {"archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"}
STABLE_LINE_SLUGS = {"knight", "light_cav", "camel", "steppe_lancer", "elephant"}
SIEGE_LINE_SLUGS = {"ram", "mangonel", "trebuchet", "bombard_cannon"}

# Stage-to-query mapping for team analysis
# Each stage has line_slugs (list of DB line_slug values to query) and tabs
# (ordered dict of sub-category breakdowns, each mapping to a score_type).
TEAM_ANALYSIS_STAGES = {
    "cavalry": {
        "line_slugs": ["knight", "light_cav", "camel", "steppe_lancer", "elephant"],
        "tabs": {
            "overall":        {"score_type": "stable_effectiveness", "label": "Overall"},
            "general_combat": {"score_type": "general_combat",       "label": "General Combat"},
            "anti_cav":       {"score_type": "anti_cav",             "label": "Anti-Cav"},
        },
    },
    "infantry": {
        "line_slugs": ["militia", "spear", "shock_infantry"],
        "tabs": {
            "overall":        {"score_type": "militia_value",    "label": "Overall"},
            "general_combat": {"score_type": "general_combat",   "label": "General Combat"},
            "anti_cav":       {"score_type": "anti_cav",         "label": "Anti-Cav"},
            "raiding":        {"score_type": "raiding_value",    "label": "Raiding"},
        },
    },
    "ranged": {
        "line_slugs": ["archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"],
        "tabs": {
            "overall":        {"score_type": "ranged_effectiveness", "label": "Overall"},
            "general_combat": {"score_type": "general_combat",       "label": "General Combat"},
            "anti_archer":    {"score_type": "anti_archer",          "label": "Anti-Archer"},
            "mobility":       {"score_type": "mobility_score",       "label": "Mobility"},
        },
    },
    "siege": {
        "line_slugs": ["ram", "trebuchet", "bombard_cannon"],
        "tabs": {
            "overall":      {"score_type": "anti_building_score", "label": "Overall"},
            "time_to_kill": {"score_type": "time_to_kill",        "label": "Time to Kill"},
        },
    },
}


# ===== Pre-computed battle scores (loaded from battle_scores.json) =====
# Generated by: cd webapp && python3 compute_battle_scores.py
# Militia role scores are in aoe2_reference.db battle_scores table (not JSON).

BATTLE_SCORES_PATH = os.path.join(os.path.dirname(__file__), "battle_scores.json")

_ROUND_ROBIN = {}
_BENCHMARKS = {}

if os.path.exists(BATTLE_SCORES_PATH):
    with open(BATTLE_SCORES_PATH) as _f:
        _scores_data = json.load(_f)
        _ROUND_ROBIN = _scores_data.get("round_robin", {})
        _BENCHMARKS = _scores_data.get("benchmarks", {})
    print(
        f"Battle scores loaded: {len(_ROUND_ROBIN)} round-robin, {len(_BENCHMARKS)} benchmark line-ages"
    )
else:
    print(
        f"WARNING: {BATTLE_SCORES_PATH} not found. Run: cd webapp && python3 compute_battle_scores.py"
    )


@app.route("/api/ref/unit-line/<line_slug>")
def api_ref_unit_line(line_slug):
    """Get comparison data for a unit line across all civs."""
    if line_slug not in UNIT_LINES:
        return jsonify({"error": "Unknown unit line"}), 404

    line = UNIT_LINES[line_slug]
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    stat_cols = """id, civ_name, unit_name, unit_slug, unit_type, age,
        final_hp, final_attack, final_melee_armor, final_pierce_armor,
        final_speed, final_range, final_reload_time,
        final_cost_food, final_cost_wood, final_cost_gold,
        upgrade_cost_food, upgrade_cost_wood, upgrade_cost_gold,
        applied_bonuses_summary"""

    # Determine which sub-lines to fetch (virtual "infantry" or single line)
    sub_lines = line.get("sub_lines", [line_slug])

    result = {
        "line_name": line["name"],
        "building": line["building"],
        "castle": [],
        "imperial": [],
    }

    # Load role scores from DB (keyed by "age|civ_name|unit_slug")
    _db_role_scores = {}
    _score_line_slugs = [s for s in sub_lines if s in INFANTRY_LINE_SLUGS or s in ARCHERY_LINE_SLUGS]
    # Stable and siege scores are stored per sub-line in DB
    if line_slug == "stable":
        _score_line_slugs = list(STABLE_LINE_SLUGS)
    elif line_slug == "siege":
        _score_line_slugs = ["ram", "trebuchet", "bombard_cannon"]
    if _score_line_slugs:
        placeholders = ",".join("?" for _ in _score_line_slugs)
        rc.execute(
            f"SELECT age, civ_name, unit_slug, score_type, score_value FROM battle_scores WHERE line_slug IN ({placeholders})",
            _score_line_slugs,
        )
        for bs_row in rc.fetchall():
            uk = f"{bs_row['age'].lower()}|{bs_row['civ_name']}|{bs_row['unit_slug']}"
            _db_role_scores.setdefault(uk, {})[bs_row["score_type"]] = bs_row[
                "score_value"
            ]

    def _attach_scores(entry, age_key, sub_slug):
        """Attach battle scores: DB role scores for infantry/archery/stable/siege, JSON for other lines."""
        unit_key = f"{age_key}|{entry['civ_name']}|{entry['unit_slug']}"
        if (sub_slug in INFANTRY_LINE_SLUGS or sub_slug in ARCHERY_LINE_SLUGS or sub_slug in STABLE_LINE_SLUGS or sub_slug in SIEGE_LINE_SLUGS) and _db_role_scores:
            rs = _db_role_scores.get(unit_key, {})
            for rk, rv in rs.items():
                entry[rk] = rv
        else:
            # Other lines: round-robin + benchmark from JSON
            line_key = f"{sub_slug}|{age_key}"
            rr = _ROUND_ROBIN.get(line_key, {}).get(unit_key, {})
            entry["score_30v30"] = rr.get("score_30v30", -999)
            entry["score_3k"] = rr.get("score_3k", -999)
            entry["score_5k"] = rr.get("score_5k", -999)
            bm = _BENCHMARKS.get(line_key, {}).get(unit_key, {})
            entry["vs_champ"] = bm.get("vs_champ", -999)
            entry["vs_paladin"] = bm.get("vs_paladin", -999)
            entry["vs_arb"] = bm.get("vs_arb", -999)
            entry["pop_vs_champ"] = bm.get("pop_vs_champ", -999)
            entry["pop_vs_paladin"] = bm.get("pop_vs_paladin", -999)
            entry["pop_vs_arb"] = bm.get("pop_vs_arb", -999)

    _ABILITY_LABELS = {
        "ignores_melee_armor": "Ignores melee armor",
        "ignores_pierce_armor": "Ignores pierce armor",
        "trample_percent": "Trample {v:.0%}",
        "trample_flat_damage": "Trample +{v:.0f} dmg",
        "trample_radius": None,
        "bonus_damage_reduction": "{v:.0%} bonus dmg reduction",
        "damage_reflect_percent": "Reflects {v:.0%} melee dmg",
        "hp_regen": "{v:.0f} HP/min regen",
        "attack_bonus_per_kill": "+{v:.0f} atk per kill",
        "pop_space": "{v} pop space",
        "armor_strip_per_hit": "Strips {v:.0f} armor/hit",
        "bleed_dps": "Bleed {v:.0f} dps",
        "bleed_duration": None,
        "pass_through_percent": "Pass-through dmg",
        "pass_through_count": None,
        "extra_proj_scatter": "Projectiles scatter",
        "miss_damage_percent": "Missed shots deal {v:.0%} dmg",
        "hp_per_kill": "+{v:.0f} HP per kill",
        "hp_per_kill_max": None,
        "charge_attack_melee": "Charge +{v:.0f} melee",
        "charge_recharge_time": None,
        "block_first_melee": "Blocks first melee hit",
        "hp_transform_threshold": "Transforms at {v:.0%} HP",
        "dodge_shield_max": "Dodge shield ({v:.0f} charges)",
        "dodge_shield_recharge": None,
    }

    def _attach_special(entry):
        rc.execute(
            "SELECT property_name, property_value FROM ref_special_effects WHERE ref_unit_id=?",
            (entry["id"],),
        )
        parts = []
        for pname, pval in rc.fetchall():
            label = _ABILITY_LABELS.get(pname)
            if label is None:
                continue
            try:
                v = float(pval)
            except (ValueError, TypeError):
                continue
            if v == 0:
                continue
            parts.append(label.format(v=v))
        entry["special_abilities"] = "; ".join(parts) if parts else ""

    # Fetch units for each sub-line
    for sub_slug in sub_lines:
        sub_line = UNIT_LINES[sub_slug]

        # Standard units for each age
        for age_key, slug_key, slugs_key, db_age in [
            ("castle", "castle_slug", "castle_slugs", "Castle"),
            ("imperial", "imperial_slug", "imperial_slugs", "Imperial"),
        ]:
            slugs = sub_line.get(
                slugs_key, [sub_line.get(slug_key)] if sub_line.get(slug_key) else []
            )
            for slug in slugs:
                rc.execute(
                    f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
                    (slug, db_age),
                )
                for row in rc.fetchall():
                    entry = dict(row)
                    entry["is_unique"] = False
                    entry["line_slug"] = sub_slug
                    _attach_scores(entry, age_key, sub_slug)
                    _attach_special(entry)
                    result[age_key].append(entry)

        # Extra standard units
        for extra_slug in sub_line.get("extra_castle_slugs", []):
            rc.execute(
                f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
                (extra_slug, "Castle"),
            )
            for row in rc.fetchall():
                entry = dict(row)
                entry["is_unique"] = False
                entry["line_slug"] = sub_slug
                _attach_scores(entry, "castle", sub_slug)
                _attach_special(entry)
                result["castle"].append(entry)

        for extra_slug in sub_line.get("extra_imperial_slugs", []):
            rc.execute(
                f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND age=? ORDER BY civ_name",
                (extra_slug, "Imperial"),
            )
            for row in rc.fetchall():
                entry = dict(row)
                entry["is_unique"] = False
                entry["line_slug"] = sub_slug
                _attach_scores(entry, "imperial", sub_slug)
                _attach_special(entry)
                result["imperial"].append(entry)

        # Unique units
        for civ_name, (castle_uu, imperial_uu) in sub_line.get(
            "unique_units", {}
        ).items():
            for uu_slug, age_key, db_age in [
                (castle_uu, "castle", "Castle"),
                (imperial_uu, "imperial", "Imperial"),
            ]:
                if not uu_slug:
                    continue
                rc.execute(
                    f"SELECT {stat_cols} FROM ref_units WHERE unit_slug=? AND civ_name=? AND age=?",
                    (uu_slug, civ_name, db_age),
                )
                row = rc.fetchone()
                if row:
                    entry = dict(row)
                    entry["is_unique"] = True
                    entry["line_slug"] = sub_slug
                    _attach_scores(entry, age_key, sub_slug)
                    _attach_special(entry)
                    result[age_key].append(entry)

    # Exclude Elephant Archers from stable (ranged, already in archery rankings)
    if line_slug == "stable":
        result["castle"] = [u for u in result["castle"] if "ele_archer" not in u["unit_slug"]]
        result["imperial"] = [u for u in result["imperial"] if "ele_archer" not in u["unit_slug"]]

    ref_conn.close()
    return jsonify(result)


# ============== Civ Matchup ==============


def _get_ref_civs():
    """Get list of civilizations from the reference DB."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute("SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name")
    civs = [row["civ_name"] for row in rc.fetchall()]
    ref_conn.close()
    return civs


@app.route("/matchup-advisor")
def matchup_advisor():
    """Matchup Advisor page — WIP."""
    return render_template("matchup_wip.html", active_nav="matchup")


@app.route("/team-analysis")
def team_analysis():
    """Team Analysis page."""
    civs = _get_ref_civs()
    return render_template("team_analysis.html", civs=civs, active_nav="team_analysis")


@app.route("/api/team-analysis")
def api_team_analysis():
    """Team analysis: compare two teams' strength in a given stage/tab."""
    team1_raw = request.args.get("team1", "")
    team2_raw = request.args.get("team2", "")
    stage = request.args.get("stage", "cavalry")
    tab = request.args.get("tab", "overall")
    age = request.args.get("age", "imperial").lower()

    if stage not in TEAM_ANALYSIS_STAGES:
        return jsonify({"error": f"Unknown stage: {stage}"}), 400

    stage_cfg = TEAM_ANALYSIS_STAGES[stage]
    tabs = stage_cfg["tabs"]

    if tab not in tabs:
        return jsonify({"error": f"Unknown tab '{tab}' for stage '{stage}'"}), 400

    team1_civs = [c.strip() for c in team1_raw.split(",") if c.strip()]
    team2_civs = [c.strip() for c in team2_raw.split(",") if c.strip()]

    if len(team1_civs) != 4 or len(team2_civs) != 4:
        return jsonify({"error": "Each team must have exactly 4 civs"}), 400

    line_slugs = stage_cfg["line_slugs"]
    score_type = tabs[tab]["score_type"]

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Build line_slug IN clause
    ls_placeholders = ",".join("?" for _ in line_slugs)

    # Get median for this group
    rc.execute(
        f"SELECT score_value, median_delta FROM battle_scores WHERE line_slug IN ({ls_placeholders}) AND age=? AND score_type=? LIMIT 1",
        line_slugs + [age, score_type],
    )
    sample = rc.fetchone()
    if not sample:
        ref_conn.close()
        return jsonify({"error": "No scores found for this stage/tab/age"}), 404
    median = round(sample["score_value"] - sample["median_delta"], 4)

    def get_team_data(civs):
        civ_placeholders = ",".join("?" for _ in civs)
        rc.execute(
            f"""SELECT bs.civ_name, bs.unit_slug, bs.score_value, bs.rank, bs.median_delta,
                       ru.unit_name
                FROM battle_scores bs
                JOIN ref_units ru ON bs.civ_name = ru.civ_name
                  AND bs.unit_slug = ru.unit_slug AND LOWER(ru.age) = bs.age
                WHERE bs.line_slug IN ({ls_placeholders}) AND bs.age=? AND bs.score_type=?
                  AND bs.civ_name IN ({civ_placeholders})
                  AND bs.median_delta > 0
                ORDER BY bs.score_value DESC""",
            line_slugs + [age, score_type] + civs,
        )
        above = [
            {
                "civ": row["civ_name"],
                "unit_slug": row["unit_slug"],
                "unit_name": row["unit_name"],
                "score": round(row["score_value"], 1),
                "rank": row["rank"],
                "median_delta": round(row["median_delta"], 1),
            }
            for row in rc.fetchall()
        ]
        total_delta = round(sum(u["median_delta"] for u in above), 1)
        return {"civs": civs, "above_median_units": above, "total_delta": total_delta}

    t1 = get_team_data(team1_civs)
    t2 = get_team_data(team2_civs)
    ref_conn.close()

    if t1["total_delta"] > t2["total_delta"]:
        advantage = "team1"
    elif t2["total_delta"] > t1["total_delta"]:
        advantage = "team2"
    else:
        advantage = "even"

    return jsonify({
        "stage": stage,
        "tab": tab,
        "tab_label": tabs[tab]["label"],
        "available_tabs": [{"key": k, "label": v["label"]} for k, v in tabs.items()],
        "age": age,
        "score_type": score_type,
        "median": round(median, 1),
        "team1": t1,
        "team2": t2,
        "advantage": advantage,
        "advantage_margin": round(abs(t1["total_delta"] - t2["total_delta"]), 1),
    })


@app.route("/api/civ-power-units/<civ_name>")
def api_civ_power_units(civ_name):
    """Get pre-computed power units for a civilization."""
    age = request.args.get("age", "imperial").lower()
    data = load_civ_power_units()
    if not data:
        return jsonify({"error": "civ_power_units.json not found"}), 500
    civ_data = data.get(civ_name)
    if not civ_data:
        return jsonify({"error": f"Civilization '{civ_name}' not found"}), 404
    age_data = civ_data.get(age)
    if not age_data:
        return jsonify({"error": f"No {age} data for {civ_name}"}), 404
    return jsonify({"civ_name": civ_name, "age": age, **age_data})


@app.route("/api/matchup-recommendations/<civ_a>/<civ_b>")
def api_matchup_recommendations(civ_a, civ_b):
    """Get recommended units and compositions for civ_a vs civ_b."""
    age = request.args.get("age", "imperial").lower()
    result = get_matchup_recommendations(civ_a, civ_b, age)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
