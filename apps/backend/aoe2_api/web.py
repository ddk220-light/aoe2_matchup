"""Role: serving — the Flask JSON API behind aoe2matchup.com.

Only /api/* routes live here; every page is prerendered by the Astro app in
apps/web (build-side page data comes from scripts/migration/site). Serves the
committed data artifacts — aoe2_reference.db, derived_data.db,
derived_data_v3.db, patches.db, civ_power_units/<build>.json — and only
simulates at serve time for the live Matchup Advisor endpoints
(best_units.get_matchup_sims / get_matchup_recommendations).

Importers put the repo root (or the packaged apps/backend/runtime, which
mirrors it) and its apps/backend directory on sys.path, then import
``aoe2_api.web``.
"""
import json
import os
import sqlite3
from collections import defaultdict
from functools import lru_cache

from flask import Flask, jsonify, redirect, request
from aoe2x.advisor.best_units import (
    get_matchup_recommendations,
    get_matchup_sims,
    CIVS_WITHOUT_TREBUCHET,
)
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
from aoe2x.advisor.top_units import load_top_units, compute_top_units
from aoe2x.sim.unit_lines import TREBUCHET_SLUGS
from aoe2x.batch.patches_db import get_current_build
from aoe2x.assets import config as _assets_cfg
from aoe2x.assets import catalog as _assets_catalog
from aoe2x.paths import REPO_ROOT


from .services.catalog import site_catalog
from .services.release import release_metadata
from .services.seo import indexing_enabled
from .services.civilizations import (civilization_analysis, civilization_overview,
    civilization_page_names, load_civilization_supplement)
from .services.database import connect_readonly
from .services.mechanics import _find_ref_unit, _load_v3_mechanics
from .services.rankings import get_unit_line_data as ranking_data
from .services.rankings import LAND_LINES as RANKING_LAND_LINES
from .routes.civilizations import create_blueprint as civilization_blueprint
from .routes.battles import create_blueprint as battle_blueprint

# The repo root, or apps/backend/runtime in the packaged backend (aoe2x.paths
# resolves it from the aoe2x package that is imported).
_REPO_ROOT = str(REPO_ROOT)

# JSON API only: no templates and no implicit /static route.
app = Flask(__name__, static_folder=None, template_folder=None)
app.json.sort_keys = False
app.config['SEARCH_INDEXING'] = os.environ.get('SEARCH_INDEXING')

def allow_indexing():
    return indexing_enabled(app.config, request.host, SITE_URL, os.environ.get('RAILWAY_ENVIRONMENT_NAME', ''))

@app.after_request
def crawler_headers(response):
    if not allow_indexing():
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


# Reject unexpectedly large request bodies before Flask buffers them.
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

# Public site URL — decides the crawler policy and the www -> apex redirect.
# Override with SITE_URL env var if you ever change domains (the page builders
# in scripts/migration/site read the same variable).
SITE_URL = os.environ.get("SITE_URL", "https://aoe2matchup.com").rstrip("/")


# Database paths — committed golden artifacts (see aoe2x/paths.py)
from aoe2x.paths import GOLDEN_DIR as _GOLDEN_DIR

DB_PATH = os.path.join(str(_GOLDEN_DIR), "aoe2_units.db")
REF_DB_PATH = os.path.join(str(_GOLDEN_DIR), "aoe2_reference.db")
SIM_REF_DB_PATH = os.path.join(str(_GOLDEN_DIR), "aoe2_reference_simulation.db")
RANKINGS_REF_DB_PATH = os.path.join(str(_GOLDEN_DIR), "aoe2_reference_rankings.db")
RANKINGS_DERIVED_DB_PATH = os.path.join(str(_GOLDEN_DIR), "derived_data_v3.db")
PATCHES_DB_PATH = os.path.join(str(_GOLDEN_DIR), "patches.db")


def get_db():
    """Get a database connection with row factory (legacy, for non-migrated endpoints)."""
    conn = connect_readonly(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_ref_db():
    """Get a connection to the reference/audit database."""
    conn = connect_readonly(REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_sim_ref_db():
    conn = connect_readonly(SIM_REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_rankings_derived_db():
    """Get the staged V3 rankings database, including retained siege/naval rows."""
    conn = connect_readonly(RANKINGS_DERIVED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_rankings_ref_db():
    conn = connect_readonly(RANKINGS_REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def current_build():
    """Resolve the live build once per call (None if patches.db absent)."""
    return get_current_build(patches_db_path=PATCHES_DB_PATH)


# =====================================================================
# SEO: canonical redirects (robots.txt and sitemap.xml are prerendered by
# the Astro app from scripts/migration/site)
# =====================================================================

@app.before_request
def _seo_canonical_redirects():
    """301 duplicate-URL variants to the canonical URL (one URL per page).

    - www.aoe2matchup.com -> apex (takes effect once the www DNS record exists;
      local/staging hosts are untouched because we match the www host exactly).
    - Trailing-slash variants (/api/x/ -> /api/x), which would otherwise
      404 and drop the link equity of external links written with a slash.
    """
    qs = request.query_string.decode()
    suffix = f"?{qs}" if qs else ""
    www_host = "www." + SITE_URL.split("://", 1)[-1]
    if request.host.partition(":")[0] == www_host:
        return redirect(f"{SITE_URL}{request.path}{suffix}", code=301)
    if request.path != "/" and request.path.endswith("/"):
        return redirect(request.path.rstrip("/") + suffix, code=301)



@app.route("/api/armor-classes")
def api_armor_classes():
    """Get all armor class names."""
    conn = get_ref_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM armor_classes ORDER BY id")
    classes = {str(row["id"]): row["name"] for row in cursor.fetchall()}
    conn.close()
    return jsonify(classes)


@lru_cache(maxsize=1)
def _catalog_payload():
    """Built once per process. With a catalog DB, reads Postgres (URLs already
    stored); else synthesizes from the in-repo manifest, pointing media at the
    /assets prefix when the bucket is configured, otherwise /static.
    Restart/redeploy refreshes it (catalog changes only at publish time).
    The deployed backend (apps/backend/app.py) replaces it with the frozen
    public catalog."""
    try:
        build = get_current_build() or "local"
    except Exception:
        build = "local"
    if _assets_cfg.database_url():
        from aoe2x.assets import catalog_pg
        return catalog_pg.load_catalog(build, "")
    base = _assets_cfg.ASSET_ROUTE_PREFIX if _assets_cfg.assets_enabled() else ""
    return _assets_catalog.synthesize_local(asset_base=base, build=str(build))


@app.get('/api/release')
def api_release():
    return jsonify(release_metadata(_REPO_ROOT, _GOLDEN_DIR))


@app.route("/api/assets/catalog")
def assets_catalog():
    return jsonify(_catalog_payload())


@app.route("/api/ref/civ/<civ_name>")
def api_ref_civ(civ_name):
    """Get all reference data for a civilization."""
    err = _validate_sim_civ_name(civ_name)
    if err:
        return err

    ref_conn = get_sim_ref_db()
    rc = ref_conn.cursor()

    # Get all units for this civ
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? ORDER BY age DESC, unit_name",
        (civ_name,),
    )
    units_rows = rc.fetchall()

    # Filter out trebuchets for civs that don't have them
    if civ_name in CIVS_WITHOUT_TREBUCHET:
        units_rows = [r for r in units_rows if r["unit_slug"] not in TREBUCHET_SLUGS]

    # Get verifications
    main_conn = get_db()
    mc = main_conn.cursor()
    mc.execute("SELECT ref_unit_id FROM unit_verifications")
    verified_ids = {row["ref_unit_id"] for row in mc.fetchall()}
    main_conn.close()

    # Get armor class names
    rc.execute("SELECT id, name FROM armor_classes ORDER BY id")
    ac_names = {str(row["id"]): row["name"] for row in rc.fetchall()}

    # Batch-load related data for all units (avoids N+1 per-unit queries)
    all_uids = [row["id"] for row in units_rows]
    placeholders = ",".join("?" * len(all_uids))

    # Techs applied — grouped by ref_unit_id
    techs_by_uid = defaultdict(list)
    if all_uids:
        rc.execute(
            f"""SELECT ref_unit_id, tech_name, tech_type, building, age_available, effect_description
                FROM ref_techs_applied WHERE ref_unit_id IN ({placeholders}) ORDER BY id""",
            all_uids,
        )
        for t in rc.fetchall():
            d = dict(t)
            uid_key = d.pop("ref_unit_id")
            techs_by_uid[uid_key].append(d)

    # Stat chain — grouped by ref_unit_id
    stat_chain_by_uid = defaultdict(list)
    if all_uids:
        rc.execute(
            f"""SELECT ref_unit_id, step_order, tech_name, tech_type,
                       hp, attack, melee_armor, pierce_armor,
                       speed, range_val, reload_time, accuracy, los,
                       train_time, cost_food, cost_wood, cost_gold,
                       attacks_json, armors_json
                FROM ref_stat_chain WHERE ref_unit_id IN ({placeholders}) ORDER BY step_order""",
            all_uids,
        )
        for s in rc.fetchall():
            d = dict(s)
            uid_key = d.pop("ref_unit_id")
            stat_chain_by_uid[uid_key].append(d)

    # Special effects — grouped by ref_unit_id
    special_by_uid = defaultdict(list)
    if all_uids:
        rc.execute(
            f"""SELECT ref_unit_id, property_name, property_value, source, description
                FROM ref_special_effects WHERE ref_unit_id IN ({placeholders})""",
            all_uids,
        )
        for s in rc.fetchall():
            d = dict(s)
            uid_key = d.pop("ref_unit_id")
            special_by_uid[uid_key].append(d)

    # Projectiles — grouped by ref_unit_id
    projectiles_by_uid = defaultdict(list)
    if all_uids:
        rc.execute(
            f"""SELECT ref_unit_id, projectile_type, projectile_count, projectile_speed,
                       attacks_json, blast_radius, is_siege_projectile
                FROM ref_projectiles WHERE ref_unit_id IN ({placeholders})""",
            all_uids,
        )
        for p in rc.fetchall():
            d = dict(p)
            uid_key = d.pop("ref_unit_id")
            projectiles_by_uid[uid_key].append(d)

    # Convert class IDs to names in attack/armor JSONs
    def convert_classes(json_str):
        if not json_str:
            return {}
        raw = json.loads(json_str)
        return {ac_names.get(k, f"class_{k}"): v for k, v in raw.items()}

    units = []
    for row in units_rows:
        uid = row["id"]

        techs = techs_by_uid[uid]
        stat_chain = stat_chain_by_uid[uid]
        special = special_by_uid[uid]

        projectiles = []
        for pd in projectiles_by_uid[uid]:
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

    # Group by age (Imperial-only data model)
    by_age = {"Imperial": []}
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
# build_combat_dict_from_ref() is imported from combat_unit_loader


def _combat_response(rc, row, requested_mode=None, include_stat_chain=True):
    result = build_combat_dict_from_ref(row)
    if include_stat_chain:
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
    result["name"] = row["unit_name"]
    result["civ"] = row["civ_name"]
    result["total_cost"] = (
        (row["final_cost_food"] or 0)
        + (row["final_cost_wood"] or 0)
        + (row["final_cost_gold"] or 0)
    )
    result["outline_size"] = row["outline_size_x"] or 0.2
    result.update(_load_v3_mechanics(rc, row["id"], requested_mode))
    return result


@app.route("/api/ref/stat-chain/<int:ref_unit_id>")
def api_ref_stat_chain(ref_unit_id):
    """Get stat chain and techs applied for a single ref unit (for hover cards)."""
    ref_conn = get_rankings_ref_db() if request.args.get('source') == 'rankings' else get_ref_db()
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
    err = _validate_sim_civ_name(civ_name)
    if err:
        return err

    age = request.args.get("age", "Imperial")
    err = _validate_age(age)
    if err:
        return err

    ref_conn = get_sim_ref_db()
    rc = ref_conn.cursor()

    row = _find_ref_unit(rc, civ_name, unit_slug, age)
    if not row:
        ref_conn.close()
        return jsonify({"error": f"Unit {unit_slug} not found for {civ_name}"}), 404
    try:
        result = _combat_response(rc, row, request.args.get("mode"))
    except ValueError as exc:
        ref_conn.close()
        return jsonify({"error": str(exc)}), 400
    except (LookupError, RuntimeError, sqlite3.DatabaseError) as exc:
        ref_conn.close()
        app.logger.error("V3 mechanics unavailable: %s", exc)
        return jsonify({"error": "V3 mechanics unavailable", "detail": str(exc)}), 503
    ref_conn.close()
    response = jsonify(result)
    response.set_etag(result["mechanics_hash"])
    response.cache_control.private = True
    response.cache_control.max_age = 3600
    return response.make_conditional(request)


def get_unit_line_data(line_slug):
    reference = get_rankings_ref_db if line_slug in RANKING_LAND_LINES else get_ref_db
    return ranking_data(line_slug, get_ref_db=reference, get_rankings_derived_db=get_rankings_derived_db, current_build=current_build)


@app.route("/api/ref/unit-line/<line_slug>")
def api_ref_unit_line(line_slug):
    """Get comparison data for a unit line across all civs."""
    data = get_unit_line_data(line_slug)
    if data is None:
        return jsonify({"error": "Unknown unit line"}), 404
    return jsonify(data)



def get_civ_overview_data():
    return civilization_overview(_get_page_civs(), build_number=current_build())



def _get_ref_civs():
    """Get list of civilizations from the reference DB."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute("SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name")
    civs = [row["civ_name"] for row in rc.fetchall()]
    ref_conn.close()
    return civs


def _get_page_civs():
    return civilization_page_names(_get_ref_civs(), load_civilization_supplement())


@lru_cache(maxsize=1)
def _unit_search_index():
    """Compact search index for the Battle Sim picker search box: every civ's
    Imperial-age unique units (display name + slug + civ). Lets a search jump
    straight to a unique unit, which selects its civ + that unit. Standard units
    stay reachable via the civ -> unit grid. Cached for the process lifetime
    (restart Flask if the unit roster changes)."""
    ref_conn = get_sim_ref_db()
    rc = ref_conn.cursor()
    rc.execute(
        "SELECT civ_name, unit_name, unit_slug FROM ref_units "
        "WHERE unit_type = 'unique' AND age = 'Imperial' "
        "AND unit_class_name != 'Unknown' "
        "AND lower(unit_slug) NOT LIKE '%trebuchet%' "
        "ORDER BY civ_name, unit_name"
    )
    out = [
        {"civ": row["civ_name"], "name": row["unit_name"], "slug": row["unit_slug"]}
        for row in rc.fetchall()
    ]
    ref_conn.close()
    return out


# ============== Input validation ==============

_VALID_AGES = frozenset({"imperial"})


@lru_cache(maxsize=1)
def _valid_civs():
    """Cached frozenset of canonical civ names from the reference DB.
    Cached for the lifetime of the process — restart Flask if civs are added
    to the DB. Used for fast O(1) membership checks in input validators."""
    return frozenset(_get_ref_civs())


def _sim_civs():
    return frozenset(site_catalog(SIM_REF_DB_PATH)["civilizations"])


def _validate_sim_civ_name(name):
    if not isinstance(name, str) or name not in _sim_civs():
        return jsonify({"error": f"Unknown civilization: {name!r}"}), 400
    return None


app.register_blueprint(battle_blueprint(lambda: get_sim_ref_db(), lambda: _sim_civs()))
app.register_blueprint(civilization_blueprint(_get_page_civs, current_build))


def _validate_civ_name(name):
    """Return None if `name` is a known civilization, else a Flask 400
    response. Compare is case-sensitive — call sites must pass the
    canonical capitalised form (e.g. 'Britons')."""
    if not isinstance(name, str) or name not in _valid_civs():
        return jsonify({"error": f"Unknown civilization: {name!r}"}), 400
    return None


def _validate_age(age):
    """Return None if `age` is a valid age string, else a Flask 400
    response. Compares case-insensitively — caller is free to keep its
    original case after this call returns None."""
    if not isinstance(age, str) or age.lower() not in _VALID_AGES:
        return (
            jsonify({"error": f"Invalid age: {age!r}. Must be 'imperial'."}),
            400,
        )
    return None


@app.get('/api/advisor-catalog')
def api_advisor_catalog():
    from .services.advisor import advisor_catalog
    return jsonify(advisor_catalog())


@app.get('/api/advisor-matchups/<civilization>')
def api_advisor_matchups(civilization):
    from .services.advisor import advisor_matchups
    try:
        return jsonify(advisor_matchups(civilization))
    except LookupError:
        return jsonify(error='Unknown civilization'), 404


@app.get('/api/advisor-evidence/<int:identifier>')
def api_advisor_evidence(identifier):
    from .services.advisor import advisor_evidence
    try:
        return jsonify(advisor_evidence(identifier))
    except LookupError:
        return jsonify(error='Unknown matchup'), 404


@app.get('/api/economy')
def api_economy_metadata():
    from .services.economy import economy_metadata
    return app.response_class(economy_metadata(), mimetype='application/json')


@app.get('/api/economy/<civilization>')
def api_economy(civilization):
    from .services.economy import economy_civilization
    try:
        return app.response_class(economy_civilization(civilization), mimetype='application/json')
    except LookupError:
        return jsonify(error='Unknown civilization'), 404


@app.route("/api/civ-power-units/<civ_name>")
def api_civ_power_units(civ_name):
    """Get pre-computed power units for a civilization."""
    err = _validate_civ_name(civ_name)
    if err:
        return err
    age = request.args.get("age", "imperial").lower()
    err = _validate_age(age)
    if err:
        return err
    try:
        return jsonify(civilization_analysis(civ_name, age, build_number=current_build()))
    except FileNotFoundError as exc:
        return jsonify(error=str(exc)), 500
    except LookupError as exc:
        return jsonify(error=str(exc)), 404



def _top_units_data():
    """Per-civ top units per line (Imperial). Prefers committed JSON; falls back
    to on-the-fly derivation from ref_units."""
    return load_top_units() or compute_top_units()


@app.route("/api/top-units/<civ_name>")
def api_top_units(civ_name):
    """Each line's highest-tier unit this civ fields at Imperial age
    (e.g. Koreans knight -> Cavalier, Cumans camel -> Camel Rider)."""
    err = _validate_civ_name(civ_name)
    if err:
        return err
    data = _top_units_data()
    civ_data = data.get(civ_name)
    if civ_data is None:
        return jsonify({"error": f"Civilization '{civ_name}' not found"}), 404
    return jsonify({"civ_name": civ_name, "lines": civ_data})


@app.route("/api/top-unit/<civ_name>/<line>")
def api_top_unit(civ_name, line):
    """The highest-tier unit(s) a civ fields in one line at Imperial age."""
    err = _validate_civ_name(civ_name)
    if err:
        return err
    civ_data = _top_units_data().get(civ_name)
    if civ_data is None:
        return jsonify({"error": f"Civilization '{civ_name}' not found"}), 404
    line_data = civ_data.get(line)
    if line_data is None:
        return jsonify({"error": f"{civ_name} has no '{line}' line"}), 404
    return jsonify({"civ_name": civ_name, "line": line, **line_data})


@app.route("/api/matchup-recommendations/<civ_a>/<civ_b>")
def api_matchup_recommendations(civ_a, civ_b):
    """Get recommended units and compositions for civ_a vs civ_b."""
    for civ in (civ_a, civ_b):
        err = _validate_civ_name(civ)
        if err:
            return err
    age = request.args.get("age", "imperial").lower()
    err = _validate_age(age)
    if err:
        return err
    result = get_matchup_recommendations(civ_a, civ_b, age)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/matchup-sims", methods=["POST"])
def api_matchup_sims():
    """Run cross-matchup simulations between two civs' power units."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    civ_left = data.get("civ_left", "")
    civ_right = data.get("civ_right", "")
    age = data.get("age", "imperial").lower()

    if not civ_left or not civ_right:
        return jsonify({"error": "civ_left and civ_right required"}), 400

    for civ in (civ_left, civ_right):
        err = _validate_civ_name(civ)
        if err:
            return err
    err = _validate_age(age)
    if err:
        return err

    result = get_matchup_sims(civ_left, civ_right, age)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)
