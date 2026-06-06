import html as _html
import json
import os
import re as _re
import sqlite3
from collections import defaultdict
from functools import lru_cache

from flask import Flask, Response, abort, jsonify, redirect, render_template, request
from best_units import (
    load_civ_power_units,
    get_matchup_recommendations,
    get_matchup_sims,
    CIVS_WITHOUT_TREBUCHET,
    _compute_missing_techs as compute_missing_techs,
    _parse_techs_and_bonuses as parse_techs_and_bonuses,
)
from combat_unit_loader import build_combat_dict_from_ref
from unit_lines import UNIT_LINES, TREBUCHET_SLUGS, CIV_MISSING_UNITS
from pool_scores_query import load_pool_scores
from patches_db import get_current_build


app = Flask(__name__)
app.json.sort_keys = False

# Public site URL — used for canonical URLs, sitemap, OG tags.
# Override with SITE_URL env var if you ever change domains.
SITE_URL = os.environ.get("SITE_URL", "https://aoe2matchup.com").rstrip("/")


@app.context_processor
def inject_site_url():
    """Make site_url and canonical_url available in every template."""
    return {"site_url": SITE_URL, "canonical_url": None}


@app.context_processor
def inject_footer_config():
    """Footer-related config from env vars. Unset vars resolve to None so
    templates can hide the corresponding link/button cleanly."""
    return {
        "contact_form_endpoint": os.environ.get("CONTACT_FORM_ENDPOINT") or None,
        "social_links": {
            "discord":   os.environ.get("SOCIAL_DISCORD_URL")   or None,
            "youtube":   os.environ.get("SOCIAL_YOUTUBE_URL")   or None,
            "instagram": os.environ.get("SOCIAL_INSTAGRAM_URL") or None,
        },
    }


# ---- Replay Analyzer (ported from the standalone visualizer) -----------------
# Mounts the AoE2 replay browser/visualizer + WebM clip exporter under /replay/*.
# It pulls heavy optional deps (mgz, Pillow, imageio-ffmpeg, requests); if any
# are missing we skip registration so the core simulator site still boots.
try:
    from replay_core import replay_bp
    app.register_blueprint(replay_bp)
    REPLAY_ENABLED = True
except Exception as _replay_err:  # pragma: no cover
    import logging
    logging.getLogger(__name__).warning(
        "Replay Analyzer disabled (import failed): %s", _replay_err
    )
    REPLAY_ENABLED = False


# Database paths
DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_units.db")
REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
DERIVED_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")
PATCHES_DB_PATH = os.path.join(os.path.dirname(__file__), "patches.db")

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


def get_derived_db():
    """Get a connection to the derived-data database (battle_scores produced
    by webapp/derive_unit_rankings.py from matchup_db.db raw battles).
    """
    conn = sqlite3.connect(DERIVED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def current_build():
    """Resolve the live build once per call (None if patches.db absent)."""
    return get_current_build(patches_db_path=PATCHES_DB_PATH)


def render_patch_summary(md):
    """Minimal, safe markdown -> HTML for user-pasted patch notes.

    Supports: escaping, **bold**, [text](url), `- ` bullet lists, blank-line
    paragraphs. Everything else is escaped plain text."""
    if not md:
        return ""
    md = _html.escape(md)
    out, in_list = [], False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{line[2:].strip()}</li>")
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        if not line:
            out.append("")
        else:
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    txt = "\n".join(out)
    txt = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt)
    txt = _re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                  r'<a href="\2" target="_blank" rel="noopener">\1</a>', txt)
    return txt


def _patches_conn():
    conn = sqlite3.connect(PATCHES_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/patches")
def patches_page():
    if not os.path.exists(PATCHES_DB_PATH):
        return render_template("patches.html", patches=[], active_nav="patches")
    conn = _patches_conn()
    rows = conn.execute("SELECT * FROM patches ORDER BY release_date DESC").fetchall()
    patches = []
    for p in rows:
        chips = conn.execute(
            "SELECT DISTINCT civ_name, unit_slug FROM patch_unit_changes "
            "WHERE patch_id=? ORDER BY civ_name, unit_slug", (p["id"],)).fetchall()
        patches.append({
            "build_number": p["build_number"], "title": p["title"],
            "release_date": p["release_date"], "source_url": p["source_url"],
            "summary_html": render_patch_summary(p["summary_md"]),
            "units": [dict(c) for c in chips],
        })
    conn.close()
    return render_template("patches.html", patches=patches, active_nav="patches")


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


@app.route("/replay")
def replay():
    """Replay Analyzer tab. Embeds the full-screen visualizer in an isolated
    iframe so the analyzer nav + theme stay on top with no CSS conflicts.
    Forwards deep-link params (?match=&profile=&t=) into the iframe so shared
    links auto-load a replay (and optionally jump to a timestamp)."""
    from urllib.parse import urlencode
    allowed = {k: request.args[k] for k in ("match", "profile", "t")
               if request.args.get(k)}
    replay_qs = ("?" + urlencode(allowed)) if allowed else ""
    return render_template("replay.html", active_nav="replay",
                           replay_qs=replay_qs)


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
    if civ_name not in _valid_civs():
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


# =====================================================================
# SEO: robots.txt, sitemap.xml, and per-matchup landing pages
# =====================================================================

@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


def _matchup_seed_pairs(limit_per_side=200):
    """Return a list of (civ_a, slug_a, civ_b, slug_b) tuples for the sitemap.

    Strategy: every unique unit (one per civ) vs every other unique unit. That
    gives us a few thousand long-tail SEO targets without exploding to millions.
    """
    conn = get_ref_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT civ_name, unit_slug
           FROM ref_units
           WHERE age='Imperial' AND unit_slug LIKE '%\\_%' ESCAPE '\\'
           ORDER BY civ_name, unit_slug"""
    )
    rows = cur.fetchall()
    conn.close()

    # Keep one (civ, slug) per civ — prefer the Elite (Imperial) variant when one
    # exists, otherwise fall back to the Castle-age unique.
    by_civ = {}  # civ -> slug, with elite_* taking precedence
    for r in rows:
        civ, slug = r["civ_name"], r["unit_slug"]
        # Slugs that end with civ name (lowercased) are uniques: e.g. "berserk_vikings"
        if not slug.endswith("_" + civ.lower()):
            continue
        existing = by_civ.get(civ)
        if existing is None or (slug.startswith("elite_") and not existing.startswith("elite_")):
            by_civ[civ] = slug
    uniques = sorted(by_civ.items())[:limit_per_side]
    uniques = [(civ, slug) for civ, slug in uniques]

    pairs = []
    for i, a in enumerate(uniques):
        for b in uniques[i + 1:]:
            pairs.append((a[0], a[1], b[0], b[1]))
    return pairs


@app.route("/sitemap.xml")
def sitemap_xml():
    urls = ["/", "/units", "/civilizations", "/matchup-advisor"]
    for civ in sorted(_valid_civs()):
        urls.append(f"/civilizations/{civ}")

    # Per-matchup landing pages — every unique-unit pair.
    for civ_a, slug_a, civ_b, slug_b in _matchup_seed_pairs():
        urls.append(f"/vs/{civ_a}/{slug_a}/{civ_b}/{slug_b}")

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml_parts.append(f"<url><loc>{SITE_URL}{u}</loc></url>")
    xml_parts.append("</urlset>")
    return Response("\n".join(xml_parts), mimetype="application/xml")


def _load_unit_for_landing(civ_name, unit_slug):
    """Fetch ref_units row for landing page. Returns dict or None."""
    conn = get_ref_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
        (civ_name, unit_slug),
    )
    row = cur.fetchone()
    if not row:
        cur.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?",
            (civ_name, unit_slug),
        )
        row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


@app.route("/vs/<civ_a>/<unit_a>/<civ_b>/<unit_b>")
def matchup_landing(civ_a, unit_a, civ_b, unit_b):
    """SEO landing page for a unit-vs-unit matchup. Stat comparison + CTA to live sim."""
    if civ_a not in _valid_civs() or civ_b not in _valid_civs():
        abort(404)
    a = _load_unit_for_landing(civ_a, unit_a)
    b = _load_unit_for_landing(civ_b, unit_b)
    if not a or not b:
        abort(404)

    a_name = a.get("unit_name") or unit_a.replace("_", " ").title()
    b_name = b.get("unit_name") or unit_b.replace("_", " ").title()

    page_title = f"{a_name} ({civ_a}) vs {b_name} ({civ_b}) — Who Wins? | AoE2 Simulator"
    meta_description = (
        f"Simulated 1v1 result for {a_name} ({civ_a}) versus {b_name} ({civ_b}) in "
        f"Age of Empires II at full upgrades. Stat comparison, costs, armor classes, "
        f"and a live battle simulator to test it yourself."
    )
    canonical = f"{SITE_URL}/vs/{civ_a}/{unit_a}/{civ_b}/{unit_b}"

    return render_template(
        "matchup_landing.html",
        a=a, b=b,
        civ_a=civ_a, civ_b=civ_b,
        unit_a=unit_a, unit_b=unit_b,
        a_name=a_name, b_name=b_name,
        page_title=page_title,
        meta_description=meta_description,
        canonical_url=canonical,
        active_nav="simulate",
    )


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
    "Mapuche",
    "Mayans",
    "Mongols",
    "Muisca",
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
    "Tupi",
    "Turks",
    "Vietnamese",
    "Vikings",
    "Wei",
    "Wu",
]

@app.route("/api/ref/civ/<civ_name>")
def api_ref_civ(civ_name):
    """Get all reference data for a civilization."""
    err = _validate_civ_name(civ_name)
    if err:
        return err

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
# build_combat_dict_from_ref() is imported from combat_unit_loader


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
    err = _validate_civ_name(civ_name)
    if err:
        return err

    age = request.args.get("age", "Imperial")
    err = _validate_age(age)
    if err:
        return err

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

    result = build_combat_dict_from_ref(row)

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


INFANTRY_LINE_SLUGS = {"militia", "spear", "shock_infantry"}
ARCHERY_LINE_SLUGS = {"archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"}
STABLE_LINE_SLUGS = {"knight", "light_cav", "camel", "steppe_lancer", "elephant"}
SIEGE_LINE_SLUGS = {"ram", "mangonel", "trebuchet", "bombard_cannon", "cannon_galleon"}
NAVAL_LINE_SLUGS = {"galleon", "fire", "hulk", "naval"}

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
    _score_line_slugs = [
        s for s in sub_lines
        if s in INFANTRY_LINE_SLUGS or s in ARCHERY_LINE_SLUGS or s in NAVAL_LINE_SLUGS
    ]
    # Stable and siege scores are stored per sub-line in DB
    if line_slug == "stable":
        _score_line_slugs = list(STABLE_LINE_SLUGS)
    elif line_slug == "siege":
        _score_line_slugs = ["ram", "trebuchet", "bombard_cannon", "cannon_galleon"]
    elif line_slug == "naval":
        _score_line_slugs = ["galleon", "fire", "hulk"]
    if _score_line_slugs:
        # Battle scores live in derived_data.db (produced by
        # webapp/derive_unit_rankings.py from raw matchup_db.db rows).
        # Fall back to the reference DB only if derived_data is missing — the
        # legacy reference battle_scores table has been empty since the
        # simulation pipeline was rebuilt for the sim-improvements branch.
        derived_conn = get_derived_db()
        placeholders = ",".join("?" for _ in _score_line_slugs)
        _bld = current_build()
        if _bld:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value "
                f"FROM battle_scores WHERE line_slug IN ({placeholders}) "
                f"AND build_number = ?",
                _score_line_slugs + [_bld],
            ).fetchall()
        else:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value "
                f"FROM battle_scores WHERE line_slug IN ({placeholders})",
                _score_line_slugs,
            ).fetchall()
        derived_conn.close()

        if not derived_rows:
            rc.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value FROM battle_scores WHERE line_slug IN ({placeholders})",
                _score_line_slugs,
            )
            derived_rows = rc.fetchall()

        for bs_row in derived_rows:
            uk = f"{bs_row['age'].lower()}|{bs_row['civ_name']}|{bs_row['unit_slug']}"
            _db_role_scores.setdefault(uk, {})[bs_row["score_type"]] = bs_row[
                "score_value"
            ]

    def _attach_scores(entry, age_key, sub_slug):
        """Attach battle scores: DB role scores for infantry/archery/stable/siege/naval, JSON for other lines."""
        unit_key = f"{age_key}|{entry['civ_name']}|{entry['unit_slug']}"
        if (sub_slug in INFANTRY_LINE_SLUGS or sub_slug in ARCHERY_LINE_SLUGS or sub_slug in STABLE_LINE_SLUGS or sub_slug in SIEGE_LINE_SLUGS or sub_slug in NAVAL_LINE_SLUGS) and _db_role_scores:
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

    # Build reference tech sets per unit_slug across all civs in scope.
    # For each slug, the set of standard techs that ≥2 civs have applied.
    # Used for missing-techs computation — a civ "missing" a tech is one in
    # this reference set that they don't have applied.
    #
    # The ≥2 civ filter drops civ-locked work_rate / standard techs that only
    # one civ ever has (e.g. Goths' "Gothic Perfusion" has tech_type='work_rate'
    # and only Goths get it — without this filter every other civ's militia
    # line would falsely show "Missing: Gothic Perfusion").
    _per_slug_civ_techs: dict[tuple[str, str], list[tuple[str, str]]] = {}
    rc.execute("""
        SELECT ru.civ_name, ru.unit_slug, rta.tech_name, rta.tech_type
          FROM ref_units ru
          JOIN ref_techs_applied rta ON rta.ref_unit_id = ru.id
    """)
    for r in rc.fetchall():
        _per_slug_civ_techs.setdefault((r["civ_name"], r["unit_slug"]), []).append(
            (r["tech_name"], r["tech_type"])
        )
    # Count, per (slug, tech), how many civs apply it.
    _slug_tech_civ_counts: dict[tuple[str, str], int] = {}
    for (civ, slug), techs in _per_slug_civ_techs.items():
        standard_techs, _bonus, _eff = parse_techs_and_bonuses(techs, [])
        for tech in standard_techs:
            _slug_tech_civ_counts[(slug, tech)] = _slug_tech_civ_counts.get((slug, tech), 0) + 1
    # Reference set per slug = standard techs applied by ≥2 civs.
    _reference_techs_by_slug: dict[str, set[str]] = {}
    for (slug, tech), count in _slug_tech_civ_counts.items():
        if count >= 2:
            _reference_techs_by_slug.setdefault(slug, set()).add(tech)

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

        # Missing techs: this civ's standard techs vs the per-slug reference.
        civ_techs = _per_slug_civ_techs.get((entry["civ_name"], entry["unit_slug"]), [])
        standard_techs, bonus_abilities, _eff = parse_techs_and_bonuses(civ_techs, [])
        reference = _reference_techs_by_slug.get(entry["unit_slug"], set())
        entry["missing_techs"] = compute_missing_techs(standard_techs, reference, entry["unit_slug"])

        # Civ bonuses + unique techs as a separate display field. These are stat
        # boosts (e.g. "+15 HP" via "Skirm Spear +5 HP × 3 ages") and named effects
        # (e.g. "Garland Wars", "Druzhina") that don't fit ref_special_effects but
        # belong in the Special cell as the third info line.
        # De-dupe and drop blatantly internal-looking names (containing 'attr_').
        seen = set()
        cleaned = []
        for name in bonus_abilities:
            if "attr_" in name:
                continue
            if name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        entry["civ_bonus_techs"] = cleaned

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
                    if (row["civ_name"], slug) in CIV_MISSING_UNITS:
                        continue
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
                if (row["civ_name"], extra_slug) in CIV_MISSING_UNITS:
                    continue
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
                if (row["civ_name"], extra_slug) in CIV_MISSING_UNITS:
                    continue
                entry = dict(row)
                entry["is_unique"] = False
                entry["line_slug"] = sub_slug
                _attach_scores(entry, "imperial", sub_slug)
                _attach_special(entry)
                result["imperial"].append(entry)

        # Unique units (value may be a single (castle, imperial) tuple or a list of such tuples)
        for civ_name, entries in sub_line.get("unique_units", {}).items():
            entries = entries if isinstance(entries, list) else [entries]
            for castle_uu, imperial_uu in entries:
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

    # Attach pool_scores payload for units covered by pool_scores.db.
    # Out-of-pool units (siege/naval) simply don't get the field.
    pool_scores_db_path = os.path.join(os.path.dirname(__file__), "pool_scores.db")
    all_unit_pairs = [
        (entry["civ_name"], entry["unit_slug"])
        for age_key in ("castle", "imperial")
        for entry in result[age_key]
    ]
    pool_scores_by_unit = load_pool_scores(pool_scores_db_path, all_unit_pairs,
                                           build_number=current_build())
    for age_key in ("castle", "imperial"):
        for entry in result[age_key]:
            key = (entry["civ_name"], entry["unit_slug"])
            if key in pool_scores_by_unit:
                entry["pool_scores"] = pool_scores_by_unit[key]

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


# ============== Input validation ==============

_VALID_AGES = frozenset({"castle", "imperial"})


@lru_cache(maxsize=1)
def _valid_civs():
    """Cached frozenset of canonical civ names from the reference DB.
    Cached for the lifetime of the process — restart Flask if civs are added
    to the DB. Used for fast O(1) membership checks in input validators."""
    return frozenset(_get_ref_civs())


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
            jsonify({"error": f"Invalid age: {age!r}. Must be 'castle' or 'imperial'."}),
            400,
        )
    return None


@app.route("/matchup-advisor")
def matchup_advisor():
    """Matchup Advisor — civ vs civ comparison."""
    civs = _get_ref_civs()
    return render_template("matchup_advisor.html", civs=civs, active_nav="matchup")


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
    data = load_civ_power_units(build_number=current_build())
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
