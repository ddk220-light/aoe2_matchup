"""Role: serving — Flask app for aoe2matchup.com.

All page + API routes (battle sim home, rankings, civ pages, matchup advisor,
patch tracker, SEO landing pages, sitemap). Serves the committed data artifacts —
aoe2_reference.db, derived_data.db, derived_data_v3.db, patches.db,
civ_power_units/<build>.json — and only simulates at serve
time for the live Matchup Advisor endpoints (best_units.get_matchup_sims /
get_matchup_recommendations).
"""

# Deploy marker: 2026-06-19 — promote 6691828 to production via PR merge
# (per-line projectiles, red-sprite battle animations, civ-page siege/Mangonel
# line, regenerated unit animations). No-op comment; exists to give `main` a
# fresh commit so Railway's production build retriggers.
import html as _html
import json
import os
import re as _re
import secrets
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from functools import lru_cache
from urllib.parse import urlencode

# Make the repo root importable so `aoe2x.*` resolves when this file is run
# directly (`python apps/website/app.py`) and not just under gunicorn's path.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from aoe2x.advisor.best_units import (
    load_civ_power_units,
    get_matchup_recommendations,
    get_matchup_sims,
    CIVS_WITHOUT_TREBUCHET,
    _compute_missing_techs as compute_missing_techs,
    _parse_techs_and_bonuses as parse_techs_and_bonuses,
)
from aoe2x.sim.combat_unit_loader import build_combat_dict_from_ref
from aoe2x.dbgen.v3_mechanics import (
    MECHANICS_SCHEMA_VERSION,
    mechanics_hash as calculate_mechanics_hash,
    validate_runtime_profile,
)
from aoe2x.js_simulation.scenario_config import (
    build_arena_preview_payload,
    build_scenario_payload,
)
from aoe2x.advisor.top_units import load_top_units, compute_top_units
from aoe2x.sim.unit_lines import UNIT_LINES, TREBUCHET_SLUGS, CIV_MISSING_UNITS
from aoe2x.batch.patches_db import get_current_build
from aoe2x.assets import config as _assets_cfg
from aoe2x.assets import catalog as _assets_catalog


app = Flask(__name__)
app.json.sort_keys = False
# Reject unexpectedly large request bodies before Flask buffers them.
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

_V3_RUNTIME_ROOT = os.path.join(_REPO_ROOT, "aoe2x", "js_simulation")


@app.get("/v3-runtime/<path:filename>")
def v3_runtime_module(filename):
    """Serve the checked-in shared V3 engine directly to browser workers.

    Only JavaScript under the host-agnostic engine tree and the shared Golden
    Arena renderer are public. Fixtures, calibration captures, reports, tests,
    and Node-only runners stay outside the HTTP surface.
    """
    normalized = filename.replace("\\", "/")
    allowed = normalized.startswith("src/") or normalized == "viewer/map-renderer.js"
    if not allowed or not normalized.endswith(".js"):
        abort(404)
    response = send_from_directory(_V3_RUNTIME_ROOT, normalized, conditional=True)
    response.cache_control.no_cache = True
    return response

# Public site URL — used for canonical URLs, sitemap, OG tags.
# Override with SITE_URL env var if you ever change domains.
SITE_URL = os.environ.get("SITE_URL", "https://aoe2matchup.com").rstrip("/")


@app.context_processor
def inject_site_url():
    """Make site_url, canonical_url and search-engine verification tokens
    available in every template.

    GOOGLE_SITE_VERIFICATION / BING_SITE_VERIFICATION are the HTML-tag
    verification tokens from Google Search Console / Bing Webmaster Tools.
    Unset -> None so base.html simply omits the meta tag."""
    return {
        "site_url": SITE_URL,
        "canonical_url": None,
        "google_site_verification": os.environ.get("GOOGLE_SITE_VERIFICATION") or None,
        "bing_site_verification": os.environ.get("BING_SITE_VERIFICATION") or None,
    }


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


# Database paths — committed golden artifacts (see aoe2x/paths.py)
from aoe2x.paths import GOLDEN_DIR as _GOLDEN_DIR

DB_PATH = os.path.join(str(_GOLDEN_DIR), "aoe2_units.db")
REF_DB_PATH = os.path.join(str(_GOLDEN_DIR), "aoe2_reference.db")
RANKINGS_DERIVED_DB_PATH = os.path.join(str(_GOLDEN_DIR), "derived_data_v3.db")
PATCHES_DB_PATH = os.path.join(str(_GOLDEN_DIR), "patches.db")

# Age definitions — the site is Imperial-only (2026-06-11): the DBs carry
# only fully-upgraded Imperial rows, so Imperial is the only servable age.
AGES = {
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


def get_rankings_derived_db():
    """Get the staged V3 rankings database, including retained siege/naval rows."""
    conn = sqlite3.connect(RANKINGS_DERIVED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def current_build():
    """Resolve the live build once per call (None if patches.db absent)."""
    return get_current_build(patches_db_path=PATCHES_DB_PATH)


def _format_inline(text):
    """**bold** + [text](url) on an already-escaped string."""
    text = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = _re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
                   r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    return text


def _norm_unit(text):
    """Loose unit token from free text (drop Elite/parens/punctuation)."""
    text = _re.sub(r"\(elite\)|elite", " ", text, flags=_re.I)
    return _re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _first_bold(text):
    m = _re.search(r"\*\*(.+?)\*\*", text)
    return m.group(1) if m else None


def _token_of_slug(slug, civ):
    """Match token for a unit slug: drop civ suffix + elite/imp tier prefix."""
    s = slug
    suf = "_" + civ.lower().replace(" ", "_")
    if s.endswith(suf):
        s = s[: -len(suf)]
    for pre in ("imp_elite_", "elite_", "imp_"):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return s.replace("_", " ").strip()


def _render_unit_table_html(t, is_open):
    esc = _html.escape
    rows = "".join(
        f'<tr><td>{esc(r["opp"])}</td>'
        f'<td class="num">{r["old_score"]} &#8594; {r["new_score"]}</td>'
        f'<td class="swing {r["dir"]}">{"%+.0f" % r["swing"]}</td>'
        f'<td><a href="{esc(r["link"])}">&#9654; View fight</a></td></tr>'
        for r in t["rows"])
    stat = (f'<span class="acc-stat">{esc(t["stat_summary"])}</span>'
            if t.get("stat_summary") else "")
    return (
        f'<details class="unit-acc"{" open" if is_open else ""}>'
        f'<summary>{esc(t["title"])}{stat}'
        f'<span class="acc-scale">{esc(t["scale"])}</span></summary>'
        f'<table class="mtable"><tr><th>Opponent</th><th>Score</th>'
        f'<th>Swing</th><th></th></tr>{rows}</table>'
        f'<div class="acc-foot"><a href="{esc(t["detail_url"])}">'
        f'Full breakdown &#8594;</a></div></details>')


def render_patch_summary(md, unit_tables=None):
    """Safe markdown -> HTML for user-pasted patch notes, with each changed
    unit's matchup table inlined right after the note bullet that mentions it.

    Matching: a bullet's first **bold** unit name is matched (by loose token)
    against the unit tables; within a `## <Civ>` section only that civ's tables
    are eligible, in a non-civ section (e.g. "Units (all civs)") any civ's.
    A civ's tables not tied to a specific bullet are flushed at the end of that
    civ's section; anything still unplaced lands under "Other changed units".
    """
    if not md:
        return ""
    tables = list(unit_tables or [])
    tokens = [_token_of_slug(t["slug"], t["civ"]) for t in tables]
    civ_set = {t["civ"] for t in tables}
    placed = [False] * len(tables)
    first_open = [True]

    def emit(predicate):
        html = ""
        for i, t in enumerate(tables):
            if placed[i] or not predicate(i, t):
                continue
            placed[i] = True
            html += _render_unit_table_html(t, first_open[0])
            first_open[0] = False
        return html

    out, in_list, current_civ = [], False, None

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in _html.escape(md).splitlines():
        line = raw.rstrip()
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_format_inline(line[2:].strip())}</li>")
            bold = _first_bold(line[2:])
            if bold is not None:
                nt = _norm_unit(bold)

                def pred(i, t, nt=nt):
                    tk = tokens[i]
                    if not tk or not (tk in nt or nt in tk):
                        return False
                    return t["civ"] == current_civ if current_civ in civ_set else True

                tbl = emit(pred)
                if tbl:
                    close_list()
                    out.append(tbl)
            continue
        close_list()
        if line.startswith(("## ", "# ")):
            if current_civ:                      # flush prior civ's leftover tables
                out.append(emit(lambda i, t: t["civ"] == current_civ))
        if not line:
            out.append("")
        elif line.startswith("### "):
            out.append(f"<h4>{_format_inline(line[4:].strip())}</h4>")
        elif line.startswith("## "):
            heading = line[3:].strip()
            current_civ = heading if heading in civ_set else None
            out.append(f"<h3>{_format_inline(heading)}</h3>")
        elif line.startswith("# "):
            current_civ = None
            out.append(f"<h2>{_format_inline(line[2:].strip())}</h2>")
        else:
            out.append(f"<p>{_format_inline(line)}</p>")
    close_list()
    if current_civ:
        out.append(emit(lambda i, t: t["civ"] == current_civ))
    orphan = emit(lambda i, t: True)
    if orphan:
        out.append('<h3>Other changed units</h3>')
        out.append(orphan)
    return "\n".join(out)


def _patches_conn():
    conn = sqlite3.connect(PATCHES_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


_SLUG_TO_LINE = None


def _slug_to_line():
    """Reverse map: unit_slug -> line key (for same-line mirror detection)."""
    global _SLUG_TO_LINE
    if _SLUG_TO_LINE is None:
        m = {}
        for line_key, line in UNIT_LINES.items():
            for s in (line.get("castle_slug"), line.get("imperial_slug")):
                if s:
                    m[s] = line_key
            for uu in line.get("unique_units", {}).values():
                pairs = uu if isinstance(uu, list) else [uu]
                for cs, isl in pairs:
                    if cs:
                        m[cs] = line_key
                    if isl:
                        m[isl] = line_key
        _SLUG_TO_LINE = m
    return _SLUG_TO_LINE


def _line_of(slug):
    return _slug_to_line().get(slug, slug)


def _pretty_unit(slug, civ):
    """Human label for a unit slug, dropping a redundant trailing civ suffix."""
    suffix = "_" + civ.lower().replace(" ", "_")
    if slug.endswith(suffix):
        slug = slug[: -len(suffix)]
    return slug.replace("_", " ").strip().title()


_REF_UNIT_NAMES = None


def _ref_unit_name(civ, slug):
    """Actual unit a civ fields for a line slug (e.g. Berbers 'paladin' ->
    Cavalier, Persians -> Savar), from ref_units. Prefers the Imperial-age name,
    falls back to Castle (units kept un-upgraded), then to the prettified slug."""
    global _REF_UNIT_NAMES
    if _REF_UNIT_NAMES is None:
        m = {}
        conn = sqlite3.connect(REF_DB_PATH)
        for civ_name, unit_slug, unit_name, age in conn.execute(
            "SELECT civ_name, unit_slug, unit_name, age FROM ref_units"):
            key = (civ_name, unit_slug)
            if age == "Imperial":
                m[key] = unit_name                 # Imperial always wins
            else:
                m.setdefault(key, unit_name)       # Castle only if no Imperial
        conn.close()
        _REF_UNIT_NAMES = m
    return _REF_UNIT_NAMES.get((civ, slug)) or _pretty_unit(slug, civ)


# How many top matchups to show per unit, and which opponents to drop.
_PATCH_MAX_MATCHUPS = 5


def _patch_unit_tables(conn, pid, build):
    """Per changed unit (that we have matchup stats for): up to 5 biggest matchup
    swings on a SINGLE scale, excluding same-line mirrors and scorpion opponents.
    Ordered by impact (largest swing first) so the first table is the headline."""
    # stat-change summary per unit (context shown under each unit's header).
    stat_by_unit = defaultdict(list)
    for r in conn.execute(
        "SELECT civ_name, unit_slug, field, old_value, new_value "
        "FROM patch_unit_changes WHERE patch_id=? ORDER BY field", (pid,)):
        stat_by_unit[(r["civ_name"], r["unit_slug"])].append(
            f"{r['field']} {r['old_value']} → {r['new_value']}")

    rows_by_unit = defaultdict(list)
    for m in conn.execute(
        "SELECT * FROM patch_matchup_changes WHERE patch_id=?", (pid,)):
        my_line, opp_line = _line_of(m["my_unit_slug"]), _line_of(m["opp_unit_slug"])
        if my_line == opp_line:
            continue                                   # same-line mirror (halb v halb)
        if opp_line == "scorpion" or "scorpion" in m["opp_unit_slug"]:
            continue                                   # ignore scorpions
        rows_by_unit[(m["my_civ"], m["my_unit_slug"])].append(dict(m))

    tables = []
    for (civ, slug), mrows in rows_by_unit.items():
        # Pick ONE scale: the one holding this unit's single biggest swing
        # (tie -> 30v30). Never mix scales within a unit's table.
        by_scale = defaultdict(list)
        for r in mrows:
            by_scale[r["scale"]].append(r)
        best_scale = max(
            by_scale,
            key=lambda s: (max(abs(x["swing"]) for x in by_scale[s]),
                           1 if s == "30v30" else 0))
        chosen = sorted(by_scale[best_scale], key=lambda x: -abs(x["swing"]))
        # Dedupe to DISTINCT opponent units: the same unit across many civs
        # (e.g. Heavy Cav Archer for 5 civs) collapses to its single biggest
        # swing, so the table shows variety rather than near-duplicates.
        seen, deduped = set(), []
        for r in chosen:
            if r["opp_unit_slug"] in seen:
                continue
            seen.add(r["opp_unit_slug"])
            deduped.append(r)
        top = deduped[: _PATCH_MAX_MATCHUPS]
        out_rows = []
        for r in top:
            out_rows.append({
                "opp": f"{r['opp_civ']} {_ref_unit_name(r['opp_civ'], r['opp_unit_slug'])}",
                "old_score": r["old_score"], "new_score": r["new_score"],
                "swing": r["swing"], "dir": "up" if r["swing"] >= 0 else "down",
                "link": battle_sim_deep_link(r["my_civ"], r["my_unit_slug"],
                                             r["opp_civ"], r["opp_unit_slug"], r["scale"]),
            })
        tables.append({
            "civ": civ, "slug": slug,
            "title": f"{civ} {_ref_unit_name(civ, slug)}",
            "scale": best_scale,
            "stat_summary": "; ".join(stat_by_unit.get((civ, slug), [])),
            "detail_url": f"/patches/{build}/{civ}/{slug}",
            "max_swing": max(abs(r["swing"]) for r in top),
            "rows": out_rows,
        })
    tables.sort(key=lambda t: -t["max_swing"])
    return tables


def get_patch_overview(build):
    """Assemble one patch's full landing-page data: metadata + rendered summary
    (notes with inlined matchup tables) + per-unit headline tables. Reuses the
    same render_patch_summary / _patch_unit_tables the hub uses, so the per-patch
    page and the hub can't diverge. Returns None for an unknown/absent build."""
    if not os.path.exists(PATCHES_DB_PATH):
        return None
    conn = _patches_conn()
    p = conn.execute("SELECT * FROM patches WHERE build_number=?", (build,)).fetchone()
    if p is None:
        conn.close()
        return None
    tables = _patch_unit_tables(conn, p["id"], p["build_number"])
    summary_html = render_patch_summary(p["summary_md"], tables)
    conn.close()
    return {
        "build_number": p["build_number"],
        "title": p["title"],
        "release_date": p["release_date"],
        "source_url": p["source_url"],
        "summary_html": summary_html,
        "unit_tables": tables,
    }


@app.route("/patches")
def patches_page():
    if not os.path.exists(PATCHES_DB_PATH):
        return render_template("patches.html", patches=[], active_nav="patches")
    conn = _patches_conn()
    rows = conn.execute("SELECT * FROM patches ORDER BY release_date DESC").fetchall()
    patches = []
    for p in rows:
        tables = _patch_unit_tables(conn, p["id"], p["build_number"])
        patches.append({
            "build_number": p["build_number"], "title": p["title"],
            "release_date": p["release_date"], "source_url": p["source_url"],
            "summary_html": render_patch_summary(p["summary_md"], tables),
        })
    conn.close()
    return render_template("patches.html", patches=patches, active_nav="patches")


@app.route("/patches/<build>")
def patch_build_page(build):
    """Canonical per-patch landing page — the 'AoE2 Update <build> patch notes' target."""
    data = get_patch_overview(build)
    if data is None:
        abort(404)
    return render_template("patch_build.html", active_nav="patches", **data)


def battle_sim_deep_link(my_civ, my_slug, opp_civ, opp_slug, scale,
                         age1="Imperial", age2="Imperial"):
    """Build a Battle Sim URL that pre-loads + auto-runs this exact matchup."""
    params = {"civ1": my_civ, "unit1": my_slug, "civ2": opp_civ, "unit2": opp_slug,
              "age1": age1, "age2": age2, "autorun": "1"}
    if scale == "3k":
        params["mode"] = "resources"; params["resources"] = "3000"
    else:
        params["mode"] = "count"; params["count1"] = "30"; params["count2"] = "30"
    return "/?" + urlencode(params)


@app.route("/patches/<build>/<civ>/<path:unit>")
def patch_unit_page(build, civ, unit):
    if not os.path.exists(PATCHES_DB_PATH):
        abort(404)
    conn = _patches_conn()
    patch = conn.execute("SELECT * FROM patches WHERE build_number=?", (build,)).fetchone()
    if patch is None:
        conn.close(); abort(404)
    pid = patch["id"]
    stat_changes = [dict(r) for r in conn.execute(
        "SELECT field, old_value, new_value, note FROM patch_unit_changes "
        "WHERE patch_id=? AND civ_name=? AND unit_slug=? ORDER BY field",
        (pid, civ, unit)).fetchall()]
    ranking = [dict(r) for r in conn.execute(
        "SELECT score_type, old_score, new_score, old_rank, new_rank "
        "FROM patch_unit_ranking WHERE patch_id=? AND civ_name=? AND unit_slug=? "
        "ORDER BY score_type", (pid, civ, unit)).fetchall()]
    mrows = conn.execute(
        "SELECT * FROM patch_matchup_changes WHERE patch_id=? AND my_civ=? "
        "AND my_unit_slug=? ORDER BY swing", (pid, civ, unit)).fetchall()
    now_beats, now_loses, shifted = [], [], []
    for m in mrows:
        d = dict(m)
        d["opp"] = f"{m['opp_civ']} {_ref_unit_name(m['opp_civ'], m['opp_unit_slug'])}"
        d["link"] = battle_sim_deep_link(m["my_civ"], m["my_unit_slug"],
                                         m["opp_civ"], m["opp_unit_slug"], m["scale"])
        flipped_to_win = m["old_winner"] != 1 and m["new_winner"] == 1
        flipped_to_loss = m["old_winner"] == 1 and m["new_winner"] != 1
        if flipped_to_win:
            now_beats.append(d)
        elif flipped_to_loss:
            now_loses.append(d)
        else:
            shifted.append(d)
    # timeline: this unit across all patches
    timeline = [dict(r) for r in conn.execute(
        "SELECT p.build_number, p.release_date, c.field, c.old_value, c.new_value "
        "FROM patch_unit_changes c JOIN patches p ON p.id=c.patch_id "
        "WHERE c.civ_name=? AND c.unit_slug=? ORDER BY p.release_date",
        (civ, unit)).fetchall()]
    conn.close()
    return render_template("patch_unit.html", build=build, civ=civ, unit=unit,
                           unit_title=_ref_unit_name(civ, unit),
                           patch=dict(patch), stat_changes=stat_changes, ranking=ranking,
                           now_beats=now_beats, now_loses=now_loses, shifted=shifted,
                           timeline=timeline, active_nav="patches")


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
    return render_template("simulate.html", active_nav="simulate",
                           unit_search=_unit_search_index())


@app.route("/about")
def about():
    """Methodology / how-it-works page — the authoritative explanation of the data
    and simulation behind the site."""
    return render_template("about.html", active_nav=None)


@app.route("/units")
def units():
    units_by_age = get_units_by_age()
    ages = {k: v["name"] for k, v in AGES.items()}
    return render_template(
        "rankings.html",
        units_by_age=units_by_age, ages=ages,
        rankings_overview=get_rankings_overview_data(),
        unit_line_pages=[(p["url"], p["short"]) for p in _UNIT_LINE_PAGES],
        active_nav="rankings",
    )


# Per-unit-line landing pages ("aoe2 fire lancer", "aoe2 paladin", ...).
# url = hyphenated URL slug; line = UNIT_LINES key; short = link-list label.
_UNIT_LINE_PAGES = [
    {"url": "militia", "line": "militia", "short": "Militia / Champion",
     "title": "Militia Line — AoE2 Champion Rankings by Civilization",
     "desc": "Champion and infantry unique-unit rankings for Age of Empires II: every civilization's militia line at full Imperial upgrades, scored by round-robin battle simulations."},
    {"url": "spearman", "line": "spear", "short": "Spearman / Halberdier",
     "title": "Spearman Line — AoE2 Pikeman & Halberdier Rankings by Civ",
     "desc": "Pikeman and Halberdier rankings for Age of Empires II: which civilizations field the best anti-cavalry spearmen at full upgrades, simulated head-to-head."},
    {"url": "shock-infantry", "line": "shock_infantry", "short": "Fire Lancer & Eagles",
     "title": "Fire Lancer & Eagle Warrior — AoE2 Shock Infantry Rankings",
     "desc": "Fire Lancer and Eagle Warrior rankings for Age of Empires II: every civilization's shock infantry at full upgrades, scored by round-robin battle simulations."},
    {"url": "archer", "line": "archer", "short": "Archer / Arbalester",
     "title": "Archer Line — AoE2 Crossbowman & Arbalester Rankings by Civ",
     "desc": "Crossbowman and Arbalester rankings for Age of Empires II: the best foot-archer civilizations at full upgrades, simulated head-to-head across all 53 civs."},
    {"url": "skirmisher", "line": "skirmisher", "short": "Skirmisher",
     "title": "Skirmisher Line — AoE2 Elite Skirmisher Rankings by Civ",
     "desc": "Elite and Imperial Skirmisher rankings for Age of Empires II: the best anti-archer skirmishers at full upgrades, scored by battle simulations."},
    {"url": "cavalry-archer", "line": "cav_archer", "short": "Cavalry Archer",
     "title": "Cavalry Archer — AoE2 Heavy Cavalry Archer Rankings by Civ",
     "desc": "Heavy Cavalry Archer and Elephant Archer rankings for Age of Empires II: the best mounted-archer civilizations at full upgrades, simulated head-to-head."},
    {"url": "knight", "line": "knight", "short": "Knight / Paladin",
     "title": "Knight Line — AoE2 Cavalier & Paladin Rankings by Civ",
     "desc": "Knight, Cavalier and Paladin rankings for Age of Empires II: which civilizations have the strongest heavy cavalry at full upgrades, simulated head-to-head."},
    {"url": "light-cavalry", "line": "light_cav", "short": "Light Cav / Hussar",
     "title": "Light Cavalry — AoE2 Hussar Rankings by Civilization",
     "desc": "Light Cavalry and Hussar rankings for Age of Empires II: the best raiding and trash cavalry at full upgrades, scored by round-robin battle simulations."},
    {"url": "camel", "line": "camel", "short": "Camel Rider",
     "title": "Camel Rider — AoE2 Heavy Camel Rankings by Civilization",
     "desc": "Camel Rider and Heavy Camel rankings for Age of Empires II: the best anti-cavalry camels at full upgrades, simulated head-to-head across all civilizations."},
    {"url": "steppe-lancer", "line": "steppe_lancer", "short": "Steppe Lancer",
     "title": "Steppe Lancer — AoE2 Elite Steppe Lancer Rankings by Civ",
     "desc": "Steppe Lancer and Elite Steppe Lancer rankings for Age of Empires II at full upgrades, scored by round-robin battle simulations."},
    {"url": "battle-elephant", "line": "elephant", "short": "Battle Elephant",
     "title": "Battle Elephant — AoE2 Elite Battle Elephant Rankings by Civ",
     "desc": "Battle Elephant and Elite Battle Elephant rankings for Age of Empires II: the strongest elephant civilizations at full upgrades, simulated head-to-head."},
    {"url": "ram", "line": "ram", "short": "Battering Ram",
     "title": "Battering Ram — AoE2 Siege Ram Rankings by Civilization",
     "desc": "Battering Ram, Capped Ram and Siege Ram rankings for Age of Empires II: the best ram civilizations at full upgrades, scored by battle simulations."},
    {"url": "mangonel", "line": "mangonel", "short": "Mangonel / Onager",
     "title": "Mangonel — AoE2 Onager & Siege Onager Rankings by Civ",
     "desc": "Mangonel, Onager and Siege Onager rankings for Age of Empires II: the best splash-damage siege at full upgrades, simulated head-to-head."},
    {"url": "hand-cannoneer", "line": "gunpowder", "short": "Hand Cannoneer",
     "title": "Hand Cannoneer — AoE2 Gunpowder Rankings by Civilization",
     "desc": "Hand Cannoneer and gunpowder unique-unit rankings for Age of Empires II at full upgrades, scored by round-robin battle simulations."},
    {"url": "scorpion", "line": "scorpion", "short": "Scorpion",
     "title": "Scorpion — AoE2 Heavy Scorpion Rankings by Civilization",
     "desc": "Scorpion and Heavy Scorpion rankings for Age of Empires II: the best scorpion civilizations at full upgrades, simulated head-to-head."},
    {"url": "trebuchet", "line": "trebuchet", "short": "Trebuchet",
     "title": "Trebuchet — AoE2 Trebuchet Rankings by Civilization",
     "desc": "Trebuchet rankings for Age of Empires II: which civilizations field the best trebuchets at full upgrades, scored by battle simulations."},
    {"url": "bombard-cannon", "line": "bombard_cannon", "short": "Bombard Cannon",
     "title": "Bombard Cannon — AoE2 Rankings by Civilization",
     "desc": "Bombard Cannon and Traction Trebuchet rankings for Age of Empires II at full upgrades, scored by round-robin battle simulations."},
    {"url": "galleon", "line": "galleon", "short": "Galleon",
     "title": "Galleon — AoE2 War Galley & Galleon Rankings by Civ",
     "desc": "War Galley and Galleon rankings for Age of Empires II: the best warship civilizations at full upgrades, simulated head-to-head."},
    {"url": "fire-ship", "line": "fire", "short": "Fire Ship",
     "title": "Fire Ship — AoE2 Fast Fire Ship Rankings by Civilization",
     "desc": "Fire Ship and Fast Fire Ship rankings for Age of Empires II at full upgrades, scored by round-robin battle simulations."},
    {"url": "hulk", "line": "hulk", "short": "Hulk",
     "title": "Hulk — AoE2 Warship Rankings by Civilization",
     "desc": "Hulk warship rankings for Age of Empires II at full upgrades, scored by round-robin battle simulations across all naval civilizations."},
    {"url": "cannon-galleon", "line": "cannon_galleon", "short": "Cannon Galleon",
     "title": "Cannon Galleon — AoE2 Elite Cannon Galleon Rankings by Civ",
     "desc": "Cannon Galleon and Elite Cannon Galleon rankings for Age of Empires II at full upgrades, scored by battle simulations."},
]
_UNIT_LINE_PAGE_BY_URL = {p["url"]: p for p in _UNIT_LINE_PAGES}

@app.route("/units/<line_url>")
def unit_line_page(line_url):
    """Per-unit-line landing page ("aoe2 fire lancer" searches): SSR ranked
    table for the line plus a deep link into the interactive rankings."""
    page = _UNIT_LINE_PAGE_BY_URL.get(line_url.lower())
    if page is None:
        abort(404)
    if line_url != line_url.lower():
        return redirect(f"/units/{line_url.lower()}", code=301)
    data = get_unit_line_data(page["line"])
    if data is None:
        abort(404)

    def _row_score(r):
        value = r.get("ranking_score")
        return value if isinstance(value, (int, float)) else None

    rows = [(r, _row_score(r)) for r in data["imperial"]]
    rows.sort(key=lambda t: (-(t[1] if t[1] is not None else float("-inf")),
                             t[0]["civ_name"]))
    return render_template("unit_line.html", page=page, line=data, rows=rows,
                           active_nav="rankings")


@app.route("/civilizations")
def civ_view():
    """Civilization analysis page — shows power units, strengths, and strategic identity."""
    civs = _get_ref_civs()
    return render_template(
        "civ_overview.html",
        civs=civs,
        civ_overview=get_civ_overview_data(),
        active_nav="civ_select",
    )


@app.route("/civilizations/<civ_name>")
def civ_detail(civ_name):
    """Per-civ landing page ("aoe2 <civ>" searches) — SSR identity + power
    units, with the interactive analyzer preselected. Canonical is lowercase."""
    slug = civ_name.lower()
    if civ_name != slug:
        return redirect(f"/civilizations/{slug}", code=301)
    civ = get_civ_detail(slug)
    if civ is None:
        abort(404)
    first_sentence = (civ["description"].split(". ")[0].strip().rstrip(".") + ".") \
        if civ["description"] else ""
    meta_desc = (f"{civ['name']} in Age of Empires II — strongest fully-upgraded "
                 f"units by role, tiers, and strategy. {first_sentence}").strip()[:250]
    return render_template("civ_detail.html", civ=civ, civs=_get_ref_civs(),
                           meta_desc=meta_desc, active_nav="civ_select")


@app.route("/civ")
def civ_redirect():
    """Backward compat redirect."""
    return redirect("/civilizations", code=301)


@app.route("/civ/<civ_name>")
def civ_detail_redirect(civ_name):
    """Backward compat redirect."""
    return redirect(f"/civilizations/{civ_name.lower()}", code=301)


@app.route("/simulate")
def simulate_redirect():
    """Redirect old /simulate URL to homepage."""
    return redirect("/", code=301)


# =====================================================================
# SEO: robots.txt, sitemap.xml, and per-matchup landing pages
# =====================================================================

@app.before_request
def _seo_canonical_redirects():
    """301 duplicate-URL variants to the canonical URL (one URL per page).

    - www.aoe2matchup.com -> apex (takes effect once the www DNS record exists;
      local/staging hosts are untouched because we match the www host exactly).
    - Trailing-slash variants (/matchups/ -> /matchups), which would otherwise
      404 and drop the link equity of external links written with a slash.
    """
    qs = request.query_string.decode()
    suffix = f"?{qs}" if qs else ""
    www_host = "www." + SITE_URL.split("://", 1)[-1]
    if request.host.partition(":")[0] == www_host:
        return redirect(f"{SITE_URL}{request.path}{suffix}", code=301)
    if request.path != "/" and request.path.endswith("/"):
        return redirect(request.path.rstrip("/") + suffix, code=301)


@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


# Hand-curated high-traffic "generic" matchups. Each uses a representative civ
# that reaches the canonical fully-upgraded unit (verified against ref_units).
# Surfaced on /matchups with the search-term label as anchor text; small set by
# design (avoids thin/doorway pages).
_POPULAR_MATCHUPS = [
    {"label": "Knight vs Pikeman",            "a": ("Franks", "paladin"),       "b": ("Bulgarians", "halberdier")},
    {"label": "Knight vs Camel",              "a": ("Franks", "paladin"),       "b": ("Berbers", "heavy_camel")},
    {"label": "Knight vs Archer",             "a": ("Franks", "paladin"),       "b": ("Britons", "arbalester")},
    {"label": "Knight vs Skirmisher",         "a": ("Franks", "paladin"),       "b": ("Mayans", "imp_elite_skirm")},
    {"label": "Knight vs Hand Cannoneer",     "a": ("Franks", "paladin"),       "b": ("Turks", "hand_cannoneer")},
    {"label": "Archer vs Skirmisher",         "a": ("Britons", "arbalester"),   "b": ("Mayans", "imp_elite_skirm")},
    {"label": "Archer vs Pikeman",            "a": ("Britons", "arbalester"),   "b": ("Bulgarians", "halberdier")},
    {"label": "Crossbowman vs Eagle Warrior", "a": ("Mayans", "arbalester"),    "b": ("Aztecs", "elite_eagle")},
    {"label": "Champion vs Pikeman",          "a": ("Aztecs", "champion"),      "b": ("Bulgarians", "halberdier")},
    {"label": "Champion vs Eagle Warrior",    "a": ("Teutons", "champion"),     "b": ("Aztecs", "elite_eagle")},
    {"label": "Champion vs Skirmisher",       "a": ("Aztecs", "champion"),      "b": ("Mayans", "imp_elite_skirm")},
    {"label": "Hand Cannoneer vs Pikeman",    "a": ("Turks", "hand_cannoneer"), "b": ("Bulgarians", "halberdier")},
    {"label": "Hand Cannoneer vs Skirmisher", "a": ("Turks", "hand_cannoneer"), "b": ("Mayans", "imp_elite_skirm")},
    {"label": "Cavalry Archer vs Skirmisher", "a": ("Tatars", "heavy_cav_archer"), "b": ("Mayans", "imp_elite_skirm")},
    {"label": "Cavalry Archer vs Pikeman",    "a": ("Tatars", "heavy_cav_archer"), "b": ("Bulgarians", "halberdier")},
    {"label": "Hussar vs Skirmisher",         "a": ("Byzantines", "hussar"),    "b": ("Mayans", "imp_elite_skirm")},
    {"label": "Hussar vs Archer",             "a": ("Byzantines", "hussar"),    "b": ("Britons", "arbalester")},
    {"label": "Camel vs Cavalry Archer",      "a": ("Saracens", "heavy_camel"), "b": ("Tatars", "heavy_cav_archer")},
    {"label": "Mangonel vs Archers",          "a": ("Celts", "siege_onager"),   "b": ("Britons", "arbalester")},
    {"label": "Mangonel vs Skirmishers",      "a": ("Celts", "siege_onager"),   "b": ("Mayans", "imp_elite_skirm")},
    {"label": "Scorpion vs Champion",         "a": ("Bengalis", "heavy_scorpion"), "b": ("Aztecs", "champion")},
    {"label": "Eagle Warrior vs Pikeman",     "a": ("Aztecs", "elite_eagle"),   "b": ("Bulgarians", "halberdier")},
]


def _popular_matchup_links():
    """[(label, url)] for the curated popular matchups."""
    out = []
    for m in _POPULAR_MATCHUPS:
        (ca, ua), (cb, ub) = m["a"], m["b"]
        out.append((m["label"], f"/vs/{ca}/{ua}/{cb}/{ub}"))
    return out


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


@lru_cache(maxsize=1)
def _data_lastmod():
    """ISO date of the newest committed data artifact.

    Used as the sitemap <lastmod> so it reflects real data builds rather than
    the deploy day — a stable signal that only moves when the data actually
    changes. Falls back to today if no artifact is present (fresh checkout)."""
    candidates = [
        os.path.join(str(_GOLDEN_DIR), "derived_data_v3.db"),
        os.path.join(str(_GOLDEN_DIR), "derived_data.db"),
        os.path.join(str(_GOLDEN_DIR), "aoe2_reference.db"),
    ]
    mtimes = [os.path.getmtime(p) for p in candidates if os.path.exists(p)]
    if not mtimes:
        return date.today().isoformat()
    return date.fromtimestamp(max(mtimes)).isoformat()


@app.route("/sitemap.xml")
def sitemap_xml():
    lastmod = _data_lastmod()

    # (path, changefreq, priority) for the hand-curated hub pages.
    hub = [
        ("/", "weekly", "1.0"),
        ("/matchup-advisor", "weekly", "0.9"),
        ("/units", "weekly", "0.9"),
        ("/civilizations", "weekly", "0.9"),
        ("/matchups", "weekly", "0.6"),
        ("/about", "monthly", "0.5"),
        ("/patches", "weekly", "0.7"),
    ]
    def _url(path, changefreq, priority):
        return (f"<url><loc>{SITE_URL}{path}</loc>"
                f"<lastmod>{lastmod}</lastmod>"
                f"<changefreq>{changefreq}</changefreq>"
                f"<priority>{priority}</priority></url>")

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, cf, pr in hub:
        xml_parts.append(_url(path, cf, pr))

    # Per-civ landing pages ("aoe2 <civ>" searches).
    for _c in _get_ref_civs():
        xml_parts.append(_url(f"/civilizations/{_c.lower()}", "weekly", "0.7"))

    # Per-unit-line landing pages ("aoe2 fire lancer", "aoe2 paladin", ...).
    for _p in _UNIT_LINE_PAGES:
        xml_parts.append(_url(f"/units/{_p['url']}", "weekly", "0.7"))

    # Curated popular matchups — higher priority than the long-tail pairs.
    for _label, _path in _popular_matchup_links():
        xml_parts.append(_url(_path, "monthly", "0.6"))

    # Per-matchup landing pages — every unique-unit pair. These are long-tail
    # SEO targets ("X vs Y who wins"), so a lower priority than the hubs.
    for civ_a, slug_a, civ_b, slug_b in _matchup_seed_pairs():
        xml_parts.append(_url(f"/vs/{civ_a}/{slug_a}/{civ_b}/{slug_b}", "monthly", "0.4"))

    # Per-patch landing pages + per-unit patch pages, each dated by release.
    if os.path.exists(PATCHES_DB_PATH):
        pconn = _patches_conn()
        prows = pconn.execute(
            "SELECT id, build_number, release_date FROM patches").fetchall()
        for pr in prows:
            rd = pr["release_date"] or lastmod
            xml_parts.append(
                f"<url><loc>{SITE_URL}/patches/{pr['build_number']}</loc>"
                f"<lastmod>{rd}</lastmod><changefreq>monthly</changefreq>"
                f"<priority>0.6</priority></url>")
            seen = set()
            for ur in pconn.execute(
                "SELECT DISTINCT civ_name, unit_slug FROM patch_unit_changes WHERE patch_id=? "
                "UNION SELECT DISTINCT my_civ, my_unit_slug FROM patch_matchup_changes WHERE patch_id=?",
                (pr["id"], pr["id"]),
            ).fetchall():
                key = (ur[0], ur[1])
                if key in seen:
                    continue
                seen.add(key)
                xml_parts.append(
                    f"<url><loc>{SITE_URL}/patches/{pr['build_number']}/{ur[0]}/{ur[1]}</loc>"
                    f"<lastmod>{rd}</lastmod><changefreq>monthly</changefreq>"
                    f"<priority>0.3</priority></url>")
        pconn.close()

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


@lru_cache(maxsize=1)
def _unique_units_list():
    """Cached [(civ, slug, name)] — one unique unit per civ (Elite preferred).

    Shared by the related-matchups cross-linker so every /vs/ landing page links
    to a handful of siblings. Without these internal links the landing pages are
    orphans (reachable only via sitemap.xml), which crawlers heavily deprioritize."""
    conn = get_ref_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT civ_name, unit_slug, unit_name FROM ref_units
           WHERE age='Imperial' AND unit_slug LIKE '%\\_%' ESCAPE '\\'
           ORDER BY civ_name, unit_slug"""
    )
    rows = cur.fetchall()
    conn.close()
    by_civ = {}  # civ -> (slug, name), elite_* taking precedence
    for r in rows:
        civ, slug, name = r["civ_name"], r["unit_slug"], r["unit_name"]
        if not slug.endswith("_" + civ.lower()):
            continue
        existing = by_civ.get(civ)
        if existing is None or (slug.startswith("elite_") and not existing[0].startswith("elite_")):
            by_civ[civ] = (slug, name or slug.replace("_", " ").title())
    return [(civ, slug, name) for civ, (slug, name) in sorted(by_civ.items())]


def _related_matchups(civ_a, unit_a, a_name, civ_b, unit_b, b_name, limit=12):
    """Build internal links to sibling /vs/ pages so landing pages aren't orphans.

    Alternates "A vs other" and "other vs B" so every page is reachable through a
    densely-connected graph of internal links that crawlers can follow."""
    out = []
    pool = [u for u in _unique_units_list() if u[0] not in (civ_a, civ_b)]
    for civ, slug, name in pool:
        out.append((f"/vs/{civ_a}/{unit_a}/{civ}/{slug}", f"{a_name} vs {name}"))
        out.append((f"/vs/{civ}/{slug}/{civ_b}/{unit_b}", f"{name} vs {b_name}"))
        if len(out) >= limit:
            break
    return out[:limit]


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
    related = _related_matchups(civ_a, unit_a, a_name, civ_b, unit_b, b_name)

    return render_template(
        "matchup_landing.html",
        a=a, b=b,
        civ_a=civ_a, civ_b=civ_b,
        unit_a=unit_a, unit_b=unit_b,
        a_name=a_name, b_name=b_name,
        page_title=page_title,
        meta_description=meta_description,
        canonical_url=canonical,
        related=related,
        active_nav="simulate",
    )


@app.route("/matchups")
def matchups_hub():
    """Crawlable index into every /vs/ landing page.

    Lists each unordered unique-unit matchup exactly once (civ A vs civ B where
    A precedes B), grouped by the first civ. A permanent internal entry point so
    the long-tail /vs/ pages aren't reachable only through the sitemap."""
    uniques = _unique_units_list()  # [(civ, slug, name), ...] sorted by civ
    groups = []
    for i, (civ_a, slug_a, name_a) in enumerate(uniques):
        links = []
        for j, (civ_b, slug_b, name_b) in enumerate(uniques):
            if j <= i:
                continue
            links.append({
                "url": f"/vs/{civ_a}/{slug_a}/{civ_b}/{slug_b}",
                "label": f"{name_a} vs {name_b}",
            })
        if links:
            groups.append({"civ": civ_a, "unit": name_a, "links": links})
    return render_template("matchups.html", groups=groups, active_nav="simulate",
                           popular=_popular_matchup_links())


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
    /assets bucket-broker route when the bucket is configured, otherwise /static.
    Restart/redeploy refreshes it (catalog changes only at publish time)."""
    try:
        build = get_current_build() or "local"
    except Exception:
        build = "local"
    if _assets_cfg.database_url():
        from aoe2x.assets import catalog_pg
        return catalog_pg.load_catalog(build, "")
    base = _assets_cfg.ASSET_ROUTE_PREFIX if _assets_cfg.assets_enabled() else ""
    return _assets_catalog.synthesize_local(asset_base=base, build=str(build))


@app.route("/api/assets/catalog")
def assets_catalog():
    return jsonify(_catalog_payload())


@app.route("/assets/<path:key>")
def asset_redirect(key):
    """Broker access to the private Railway Bucket: 302 -> short-lived presigned
    URL so the browser fetches bytes straight from the bucket (free egress)."""
    if not _assets_cfg.assets_enabled():
        abort(404)
    from aoe2x.assets import bucket as _assets_bucket
    return redirect(_assets_bucket.presigned_get(key), code=302)


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


def _find_ref_unit(rc, civ_name, unit_slug, age):
    rc.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if row is None:
        rc.execute(
            "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?",
            (civ_name, unit_slug),
        )
        row = rc.fetchone()
    return row


def _load_v3_mechanics(rc, ref_unit_id, requested_mode=None):
    modes = rc.execute(
        """
        SELECT mode, is_default, schema_version, mechanics_json,
               mechanics_hash, source_build
        FROM ref_unit_mechanics
        WHERE ref_unit_id=?
        ORDER BY is_default DESC, mode
        """,
        (ref_unit_id,),
    ).fetchall()
    if not modes:
        raise LookupError(f"V3 mechanics missing for ref_unit_id={ref_unit_id}")
    selected = next(
        (
            row for row in modes
            if row["mode"] == requested_mode
        ),
        None,
    ) if requested_mode else next((row for row in modes if row["is_default"]), None)
    if selected is None:
        available = ", ".join(row["mode"] for row in modes)
        raise ValueError(f"unknown mechanics mode {requested_mode!r}; available: {available}")
    if selected["schema_version"] != MECHANICS_SCHEMA_VERSION:
        raise RuntimeError(
            f"mechanics schema {selected['schema_version']} is incompatible with "
            f"server schema {MECHANICS_SCHEMA_VERSION}"
        )
    try:
        mechanics = json.loads(selected["mechanics_json"])
        validate_runtime_profile(mechanics)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid mechanics payload for ref_unit_id={ref_unit_id}"
        ) from exc
    actual_hash = calculate_mechanics_hash(mechanics)
    if actual_hash != selected["mechanics_hash"]:
        raise RuntimeError(f"mechanics hash mismatch for ref_unit_id={ref_unit_id}")
    return {
        "mechanics": mechanics,
        "mechanics_hash": actual_hash,
        "mechanics_schema_version": selected["schema_version"],
        "mechanics_source_build": selected["source_build"],
        "mechanics_mode": selected["mode"],
        "mechanics_modes": [row["mode"] for row in modes],
    }


def _load_v3_auxiliary_mechanics(rc, actor_slug, mode="default"):
    row = rc.execute(
        """
        SELECT schema_version, mechanics_json, mechanics_hash, source_build
        FROM ref_auxiliary_mechanics
        WHERE actor_slug=? AND mode=?
        """,
        (actor_slug, mode),
    ).fetchone()
    if row is None:
        raise LookupError(f"V3 auxiliary mechanics missing for {actor_slug}:{mode}")
    if row["schema_version"] != MECHANICS_SCHEMA_VERSION:
        raise RuntimeError(
            f"auxiliary mechanics schema {row['schema_version']} is incompatible"
        )
    try:
        mechanics = json.loads(row["mechanics_json"])
        validate_runtime_profile(mechanics)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"invalid auxiliary mechanics payload for {actor_slug}:{mode}"
        ) from exc
    actual_hash = calculate_mechanics_hash(mechanics)
    if actual_hash != row["mechanics_hash"]:
        raise RuntimeError(f"auxiliary mechanics hash mismatch for {actor_slug}:{mode}")
    return {
        "mechanics": mechanics,
        "mechanics_hash": actual_hash,
        "mechanics_source_build": row["source_build"],
    }


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


_V3_FAMILY_CAPACITIES = {
    # The public Golden Arena supplies 27 authored placement cells on both
    # sides for every visual family. Internal calibration tables may be smaller,
    # but public fights pass these explicit scenario placements to the engine.
    "rvr": (27, 27),
    "kite": (27, 27),
    "siege": (27, 27),
    "waves": (27, 27),
}


def _v3_engine_family(class2, class3):
    ranged = {"mobile_ranged", "siege_ranged"}
    if class2 in ranged and class3 in ranged:
        return "rvr"
    if "mobile_ranged" in (class2, class3):
        return "kite"
    if "siege_ranged" in (class2, class3):
        return "siege"
    return "waves"


def _v3_visual_family(class2, class3):
    ranged = {"mobile_ranged", "siege_ranged"}
    if class2 not in ranged and class3 not in ranged:
        return "melee_vs_melee"
    if class2 in ranged and class3 in ranged:
        return "ranged_vs_ranged"
    return "ranged_vs_melee" if class2 in ranged else "melee_vs_ranged"


def _v3_public_capacities(class2, class3, family):
    inner2, inner3 = _V3_FAMILY_CAPACITIES[family]
    role = {"kite": "mobile_ranged", "siege": "siege_ranged"}.get(family)
    normalized = role is not None and class3 == role
    return ((inner3, inner2) if normalized else (inner2, inner3)), normalized


def _positive_number(value, label, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{label} must be a positive number")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return float(value)


def _nonnegative_number(value, label, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{label} must be a nonnegative number")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return float(value)


def _bounded_integer(value, label, *, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if integer != value or integer < minimum or integer > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return integer


def _v3_counts(army, teams, capacities):
    if not isinstance(army, dict):
        raise ValueError("army must be an object")
    mode = army.get("mode", "equal_resources")
    cap = _bounded_integer(army.get("cap", 27), "army.cap", minimum=1, maximum=27)
    limits = (min(cap, capacities[0]), min(cap, capacities[1]))
    if mode == "explicit":
        counts = tuple(
            _bounded_integer(
                team.get("count"), f"team {index} count", minimum=1, maximum=limit
            )
            for index, (team, limit) in enumerate(zip(teams, limits), 1)
        )
    elif mode == "equal_count":
        count = _bounded_integer(
            army.get("count", 20), "army.count", minimum=1, maximum=min(limits)
        )
        counts = (count, count)
    elif mode in {"equal_resources", "resource_budgets"}:
        weights = army.get("weights", {})
        if not isinstance(weights, dict):
            raise ValueError("army.weights must be an object")
        wf = _nonnegative_number(weights.get("food", 1), "food weight", maximum=10)
        ww = _nonnegative_number(weights.get("wood", 1), "wood weight", maximum=10)
        wg = _nonnegative_number(weights.get("gold", 1), "gold weight", maximum=10)
        if wf + ww + wg <= 0:
            raise ValueError("at least one resource weight must be positive")
        costs = []
        for team in teams:
            cost = team["mechanics"]["cost"]
            costs.append(cost["food"] * wf + cost["wood"] * ww + cost["gold"] * wg)
        if costs[0] <= 0 or costs[1] <= 0:
            raise ValueError("selected unit has zero weighted resource cost")
        if mode == "equal_resources":
            budget = _positive_number(
                army.get("budget", 3000), "army.budget", maximum=20000
            )
            cheap = 0 if costs[0] <= costs[1] else 1
            dear = 1 - cheap
            counts = [0, 0]
            counts[cheap] = min(limits[cheap], int(budget // costs[cheap]))
            counts[dear] = min(
                limits[dear],
                max(1, int((counts[cheap] * costs[cheap]) // costs[dear])),
            )
            counts = tuple(counts)
        else:
            budgets = army.get("budgets")
            if not isinstance(budgets, list) or len(budgets) != 2:
                raise ValueError("army.budgets must contain Team A and Team B budgets")
            budgets = tuple(
                _positive_number(value, f"team {index} budget")
                for index, value in enumerate(budgets, 1)
            )
            # Resource-based armies preserve the requested Team A : Team B
            # spending ratio. If either side would exceed the scenario's 27-unit
            # capacity, scale both theoretical counts by the same factor before
            # flooring. Equal budgets therefore retain the established behavior:
            # the cheaper army fills to 27 and the dearer army matches its spend.
            theoretical = tuple(
                budget / cost for budget, cost in zip(budgets, costs)
            )
            scale = min(
                1.0,
                *(limit / count for limit, count in zip(limits, theoretical)),
            )
            counts = tuple(
                min(limit, max(1, int(count * scale)))
                for limit, count in zip(limits, theoretical)
            )
    else:
        raise ValueError(
            "army.mode must be explicit, equal_count, equal_resources, or resource_budgets"
        )
    for index, (count, limit) in enumerate(zip(counts, limits), 1):
        if count < 1 or count > limit:
            raise ValueError(f"team {index} count must be between 1 and {limit}")
    return counts


@app.get("/api/v3/arena-preview")
def api_v3_arena_preview():
    """Golden Arena geometry for the empty picker and selection previews."""
    return jsonify(build_arena_preview_payload())


@app.post("/api/v3/battle-config")
def api_v3_battle_config():
    document = request.get_json(silent=True)
    if not isinstance(document, dict):
        return jsonify({"error": "JSON object required"}), 400
    selections = document.get("teams")
    if not isinstance(selections, list) or len(selections) != 2:
        return jsonify({"error": "teams must contain exactly two selections"}), 400
    connection = get_ref_db()
    cursor = connection.cursor()
    teams = []
    try:
        for selection in selections:
            if not isinstance(selection, dict):
                raise ValueError("each team selection must be an object")
            civ = selection.get("civ")
            slug = selection.get("unit_slug")
            age = selection.get("age", "Imperial")
            if _validate_civ_name(civ) is not None:
                raise ValueError(f"unknown civilization {civ!r}")
            if _validate_age(age) is not None:
                raise ValueError(f"invalid age {age!r}")
            row = _find_ref_unit(cursor, civ, slug, age)
            if row is None:
                raise ValueError(f"unit {slug!r} is unavailable for {civ}")
            combat = _combat_response(
                cursor, row, selection.get("mode"), include_stat_chain=False
            )
            teams.append({
                "civ": civ,
                "unit_slug": slug,
                "unit_name": row["unit_name"],
                "mode": combat["mechanics_mode"],
                "mechanics_hash": combat["mechanics_hash"],
                "mechanics": combat["mechanics"],
                "count": selection.get("count"),
            })
        classes = (teams[0]["mechanics"]["behavior_class"], teams[1]["mechanics"]["behavior_class"])
        engine_family = _v3_engine_family(*classes)
        visual_family = _v3_visual_family(*classes)
        capacities, normalized = _v3_public_capacities(*classes, engine_family)
        counts = _v3_counts(document.get("army", {}), teams, capacities)
        for team, count in zip(teams, counts):
            team["count"] = count
        engagement = document.get("engagement_mode", "direct")
        if engagement not in ("direct", "ranged_buffer"):
            raise ValueError("engagement_mode must be direct or ranged_buffer")
        # The public option is intentionally safe to leave on. It only changes
        # mixed ranged/melee fights; same-family fights continue as direct
        # engagements instead of rejecting an otherwise valid battle.
        if engagement == "ranged_buffer" and visual_family not in (
            "ranged_vs_melee", "melee_vs_ranged"
        ):
            engagement = "direct"
        scenario = build_scenario_payload(
            visual_family,
            engine_family=engine_family,
            include_buffer=engagement == "ranged_buffer",
        )
        if engagement == "ranged_buffer":
            buffer_combat = _load_v3_auxiliary_mechanics(cursor, "scout_cavalry")
            buffer = scenario["auxiliaryArmiesByOwner"]["4"]
            buffer.update(
                {
                    "unit_name": "Scout Cavalry",
                    "mechanics_hash": buffer_combat["mechanics_hash"],
                    "mechanics": buffer_combat["mechanics"],
                }
            )
        seed = document.get("seed")
        if seed is None:
            seed = secrets.randbits(32)
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("seed must be a uint32")
    except (LookupError, RuntimeError, sqlite3.DatabaseError) as exc:
        connection.close()
        app.logger.error("V3 mechanics unavailable: %s", exc)
        return jsonify({"error": "V3 mechanics unavailable", "detail": str(exc)}), 503
    except ValueError as exc:
        connection.close()
        return jsonify({"error": str(exc)}), 400
    connection.close()
    return jsonify({
        "schemaVersion": 1,
        "engineVersion": "simulationv3",
        "mechanicsSchemaVersion": MECHANICS_SCHEMA_VERSION,
        "seed": seed,
        "engagementMode": engagement,
        "teams": teams,
        "scenario": {**scenario, "orientationNormalized": normalized},
    })


INFANTRY_LINE_SLUGS = {"militia", "spear", "shock_infantry"}
ARCHERY_LINE_SLUGS = {"archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"}
STABLE_LINE_SLUGS = {"knight", "light_cav", "camel", "steppe_lancer", "elephant"}
SIEGE_LINE_SLUGS = {"ram", "mangonel", "trebuchet", "bombard_cannon", "cannon_galleon"}
NAVAL_LINE_SLUGS = {"galleon", "fire", "hulk", "naval"}

FINAL_SCORE_TYPE_BY_LINE = {
    "militia": "militia_value",
    "spear": "militia_value",
    "shock_infantry": "militia_value",
    "archer": "ranged_effectiveness",
    "skirmisher": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness",
    "scorpion": "ranged_effectiveness",
    "gunpowder": "ranged_effectiveness",
    "knight": "stable_effectiveness",
    "light_cav": "stable_effectiveness",
    "camel": "stable_effectiveness",
    "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
    "ram": "anti_building_score",
    "trebuchet": "anti_building_score",
    "bombard_cannon": "anti_building_score",
    "cannon_galleon": "anti_building_score",
    "galleon": "naval_effectiveness",
    "fire": "naval_effectiveness",
    "hulk": "naval_effectiveness",
}

_V3_FINAL_SCORE_TYPES = {
    "militia_value",
    "ranged_effectiveness",
    "stable_effectiveness",
}

_V3_BREAKDOWN_YARDSTICKS = (
    ("champion", "Champion", "gc_v3_27_vs_champ"),
    ("paladin", "Paladin", "gc_v3_27_vs_paladin"),
    ("arbalester", "Arbalester", "gc_v3_27_vs_arb"),
    ("halberdier", "Halberdier", "at_v3_27_vs_halb"),
    ("elite_skirmisher", "Elite Skirmisher", "at_v3_27_vs_elite_skirm"),
    ("hussar", "Hussar", "at_v3_27_vs_hussar"),
)

def get_unit_line_data(line_slug):
    """Return comparison data for a unit line across all civs as a plain dict.

    Returns None if line_slug is not a known unit line.
    Used by api_ref_unit_line and server-side rendering tasks.
    """
    if line_slug not in UNIT_LINES:
        return None

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
        "imperial": [],
    }

    # Load role scores from DB (keyed by "age|civ_name|unit_slug")
    _db_role_scores = {}
    scored_lines = (
        INFANTRY_LINE_SLUGS
        | ARCHERY_LINE_SLUGS
        | STABLE_LINE_SLUGS
        | SIEGE_LINE_SLUGS
        | NAVAL_LINE_SLUGS
    )
    _score_line_slugs = [s for s in sub_lines if s in scored_lines]
    if _score_line_slugs:
        derived_conn = get_rankings_derived_db()
        placeholders = ",".join("?" for _ in _score_line_slugs)
        _bld = current_build()
        if _bld:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value, rank, median_delta "
                f"FROM battle_scores WHERE line_slug IN ({placeholders}) "
                f"AND build_number = ?",
                _score_line_slugs + [_bld],
            ).fetchall()
        else:
            derived_rows = derived_conn.execute(
                f"SELECT age, civ_name, unit_slug, score_type, score_value, rank, median_delta "
                f"FROM battle_scores WHERE line_slug IN ({placeholders})",
                _score_line_slugs,
            ).fetchall()
        derived_conn.close()

        for bs_row in derived_rows:
            uk = f"{bs_row['age'].lower()}|{bs_row['civ_name']}|{bs_row['unit_slug']}"
            _db_role_scores.setdefault(uk, {})[bs_row["score_type"]] = {
                "score_value": bs_row["score_value"],
                "rank": bs_row["rank"],
                "median_delta": bs_row["median_delta"],
            }

    def _attach_scores(entry, age_key, sub_slug):
        """Attach role scores from derived_data.db (battle_scores table).

        Scores are only loaded for the infantry/archery/stable/siege/naval
        sub-lines, so other lines simply get no score keys — rankings.js
        treats missing keys as "no score" (same as the old -999 sentinels).
        """
        unit_key = f"{age_key}|{entry['civ_name']}|{entry['unit_slug']}"
        score_rows = _db_role_scores.get(unit_key, {})
        for score_type, score_row in score_rows.items():
            entry[score_type] = score_row["score_value"]

        final_type = FINAL_SCORE_TYPE_BY_LINE.get(sub_slug)
        final_row = score_rows.get(final_type) if final_type else None
        if final_row:
            entry["ranking_score_type"] = final_type
            entry["ranking_score"] = final_row["score_value"]
            entry["ranking_rank"] = final_row["rank"]
            entry["ranking_median_delta"] = final_row["median_delta"]

        if final_type in _V3_FINAL_SCORE_TYPES:
            roles = {
                label: entry.get(score_type)
                for label, score_type in (
                    ("GC", "general_combat"),
                    ("AC", "anti_cav"),
                    ("AT", "anti_trash"),
                    ("AA", "anti_archer"),
                )
                if entry.get(score_type) is not None
            }
            yardsticks = [
                {"key": key, "label": label, "score": entry.get(score_type)}
                for key, label, score_type in _V3_BREAKDOWN_YARDSTICKS
                if entry.get(score_type) is not None
            ]
            if roles or yardsticks:
                entry["ranking_breakdown"] = {
                    "roles": roles,
                    "yardsticks": yardsticks,
                }

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

        # Standard units (Imperial only)
        for age_key, slug_key, slugs_key, db_age in [
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

        # Unique units (value may be a single (castle, imperial) tuple or a list
        # of such tuples — only the imperial slug is served)
        for civ_name, entries in sub_line.get("unique_units", {}).items():
            entries = entries if isinstance(entries, list) else [entries]
            for _castle_uu, imperial_uu in entries:
                for uu_slug, age_key, db_age in [
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
        result["imperial"] = [u for u in result["imperial"] if "ele_archer" not in u["unit_slug"]]

    ref_conn.close()
    return result


# Headline categories for the server-rendered "Rankings at a glance" section.
_RANKINGS_HEADLINE_LINES = [
    ("infantry", "Infantry"),
    ("archery", "Archers & Gunpowder"),
    ("stable", "Cavalry"),
    ("siege", "Siege"),
    ("naval", "Naval"),
]
def _ranking_default_score(unit):
    """Return the one published final ranking score for a unit."""
    value = unit.get("ranking_score")
    return value if isinstance(value, (int, float)) else None


def get_rankings_overview_data(top_n=8):
    """Top units per headline category by the published final score, for SSR.
    Reuses get_unit_line_data so the overview can't diverge from the API."""
    out = []
    for line_slug, label in _RANKINGS_HEADLINE_LINES:
        line = get_unit_line_data(line_slug) or {}
        scored = []
        for u in line.get("imperial", []):
            s = _ranking_default_score(u)
            if s is None:
                continue
            scored.append({
                "civ": u["civ_name"],
                "name": u.get("unit_name") or u["unit_slug"],
                "slug": u["unit_slug"],
                "score": round(s, 1),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        out.append({"line_slug": line_slug, "label": label, "units": scored[:top_n]})
    return out


@app.route("/api/ref/unit-line/<line_slug>")
def api_ref_unit_line(line_slug):
    """Get comparison data for a unit line across all civs."""
    data = get_unit_line_data(line_slug)
    if data is None:
        return jsonify({"error": "Unknown unit line"}), 404
    return jsonify(data)


# ============== Civ Matchup ==============

# Role columns shown on the civilizations overview, in display order.
# Keys match the top-level groups of power_units in civ_power_units/<build>.json.
_CIV_ROLE_LABELS = [
    ("cavalry", "Cavalry"),
    ("ranged", "Ranged"),
    ("infantry", "Infantry"),
    ("siege", "Siege"),
    ("navy", "Navy"),
]


def get_civ_overview_data():
    """Server-renderable overview for every civ: name, the auto-generated
    strategic description, and power units grouped by role.

    Shares its data source (load_civ_power_units) with the /api/civ-power-units
    route, so the server-rendered page and the JSON API never diverge. Degrades
    to empty descriptions/roles if the power-units file is missing, so the page
    still renders the civ list rather than 500ing."""
    civs = _get_ref_civs()
    power = load_civ_power_units(build_number=current_build()) or {}
    out = []
    for civ in civs:
        civ_age = (power.get(civ) or {}).get("imperial") or {}
        power_units = civ_age.get("power_units") or {}
        roles = []
        for role_key, role_label in _CIV_ROLE_LABELS:
            units = []
            for _line_slug, entries in (power_units.get(role_key) or {}).items():
                for e in (entries or []):
                    slug = e.get("unit_slug") or ""
                    units.append({
                        "name": e.get("unit_name") or slug.replace("_", " ").title(),
                        "slug": slug,
                        # `tier` is the real field; `strength` is a legacy synonym
                        # kept only as a defensive fallback (absent in current data).
                        "tier": (e.get("tier") or e.get("strength") or "").title(),
                        "is_unique": bool(e.get("is_unique")),
                    })
            if units:
                roles.append({"label": role_label, "units": units})
        out.append({
            "name": civ,
            "slug": civ.lower(),
            "description": civ_age.get("strategic_description") or "",
            "roles": roles,
        })
    return out


def get_civ_detail(slug):
    """Single-civ entry from get_civ_overview_data() for the per-civ landing
    page. slug is the lowercase civ name; returns None if unknown."""
    for civ in get_civ_overview_data():
        if civ["slug"] == slug:
            return civ
    return None


def _get_ref_civs():
    """Get list of civilizations from the reference DB."""
    ref_conn = get_ref_db()
    rc = ref_conn.cursor()
    rc.execute("SELECT DISTINCT civ_name FROM ref_units ORDER BY civ_name")
    civs = [row["civ_name"] for row in rc.fetchall()]
    ref_conn.close()
    return civs


@lru_cache(maxsize=1)
def _unit_search_index():
    """Compact search index for the Battle Sim picker search box: every civ's
    Imperial-age unique units (display name + slug + civ). Lets a search jump
    straight to a unique unit, which selects its civ + that unit. Standard units
    stay reachable via the civ -> unit grid. Cached for the process lifetime
    (restart Flask if the unit roster changes)."""
    ref_conn = get_ref_db()
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
        return jsonify({"error": "civ_power_units/<build>.json not found"}), 500
    civ_data = data.get(civ_name)
    if not civ_data:
        return jsonify({"error": f"Civilization '{civ_name}' not found"}), 404
    age_data = civ_data.get(age)
    if not age_data:
        return jsonify({"error": f"No {age} data for {civ_name}"}), 404
    return jsonify({"civ_name": civ_name, "age": age, **age_data})


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


if __name__ == "__main__":
    # Local dev convenience: load a gitignored .env so the dev server picks up
    # BUCKET_*/ASSET_ENV/etc. On Railway there is no .env file and real service
    # env vars win (setdefault never overrides). Tests import this module without
    # running __main__, so they are unaffected.
    _envf = os.path.join(_REPO_ROOT, ".env")
    if os.path.exists(_envf):
        with open(_envf) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
