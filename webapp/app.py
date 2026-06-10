"""Role: serving — Flask app for aoe2matchup.com.

All page + API routes (battle sim home, rankings, civ pages, matchup advisor,
patch tracker, SEO landing pages, sitemap) plus the /replay/* blueprint
mounted from replay_core. Serves the committed data artifacts —
aoe2_reference.db, derived_data.db, pool_scores.db, patches.db,
matchup_db.db, civ_power_units/<build>.json — and only simulates at serve
time for the live Matchup Advisor endpoints (best_units.get_matchup_sims /
get_matchup_recommendations).
"""
import html as _html
import json
import os
import re as _re
import sqlite3
from collections import defaultdict
from functools import lru_cache
from urllib.parse import urlencode

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
from top_units import load_top_units, compute_top_units
from unit_lines import UNIT_LINES, TREBUCHET_SLUGS, CIV_MISSING_UNITS
from pool_scores_query import load_pool_scores
from patches_db import get_current_build


app = Flask(__name__)
app.json.sort_keys = False
# Cap request bodies (replay uploads are single-digit MB; 50 MB is generous).
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

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


@app.context_processor
def inject_replay_enabled():
    """Expose whether the replay blueprint mounted, so base.html can hide
    the Replay nav tab when its optional deps failed to import."""
    return {"replay_enabled": REPLAY_ENABLED}


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
    return render_template("simulate.html", active_nav="simulate")


@app.route("/replay")
def replay():
    """Replay Analyzer tab. Embeds the full-screen visualizer in an isolated
    iframe so the analyzer nav + theme stay on top with no CSS conflicts.
    Forwards deep-link params (?match=&profile=&t=) into the iframe so shared
    links auto-load a replay (and optionally jump to a timestamp).

    Returns 503 with a friendly notice when the replay blueprint failed to
    mount (optional deps missing) — otherwise the SPA would render but every
    API call would 404."""
    if not REPLAY_ENABLED:
        return render_template("replay_disabled.html", active_nav="replay"), 503
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
    return render_template("rankings.html", units_by_age=units_by_age, ages=ages, active_nav="rankings")


@app.route("/civilizations")
def civ_view():
    """Civilization analysis page — shows power units, strengths, and strategic identity."""
    civs = _get_ref_civs()
    return render_template("civ_overview.html", civs=civs, active_nav="civ_select")


@app.route("/civilizations/<civ_name>")
def civ_detail(civ_name):
    """Civilization unit detail page."""
    if civ_name not in _valid_civs():
        return redirect("/civilizations")
    return render_template("civ_detail.html", civ_name=civ_name, active_nav="civ_detail")


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
        """Attach role scores from derived_data.db (battle_scores table).

        Scores are only loaded for the infantry/archery/stable/siege/naval
        sub-lines, so other lines simply get no score keys — rankings.js
        treats missing keys as "no score" (same as the old -999 sentinels).
        """
        unit_key = f"{age_key}|{entry['civ_name']}|{entry['unit_slug']}"
        for rk, rv in _db_role_scores.get(unit_key, {}).items():
            entry[rk] = rv

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
