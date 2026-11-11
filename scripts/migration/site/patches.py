"""Patch tracker data and rendered patch notes (moved from the website's HTML routes).

Reads the committed patches.db read-only; nothing here simulates.
"""
from collections import defaultdict
from functools import lru_cache
import html as _html
import os
import re as _re
import sqlite3
from urllib.parse import urlencode

from .sources import PATCHES_DB_PATH, REF_DB_PATH, UNIT_LINES, connect_readonly


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


@lru_cache(maxsize=1)
def _slug_to_line():
    """Reverse map: unit_slug -> line key (for same-line mirror detection)."""
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
    return m


def _line_of(slug):
    return _slug_to_line().get(slug, slug)


def _pretty_unit(slug, civ):
    """Human label for a unit slug, dropping a redundant trailing civ suffix."""
    suffix = "_" + civ.lower().replace(" ", "_")
    if slug.endswith(suffix):
        slug = slug[: -len(suffix)]
    return slug.replace("_", " ").strip().title()


@lru_cache(maxsize=1)
def _ref_unit_names():
    m = {}
    conn = connect_readonly(REF_DB_PATH)
    try:
        for civ_name, unit_slug, unit_name, age in conn.execute(
            "SELECT civ_name, unit_slug, unit_name, age FROM ref_units"):
            key = (civ_name, unit_slug)
            if age == "Imperial":
                m[key] = unit_name                 # Imperial always wins
            else:
                m.setdefault(key, unit_name)       # Castle only if no Imperial
    finally:
        conn.close()
    return m


def ref_unit_name(civ, slug):
    """Actual unit a civ fields for a line slug (e.g. Berbers 'paladin' ->
    Cavalier, Persians -> Savar), from ref_units. Prefers the Imperial-age name,
    falls back to Castle (units kept un-upgraded), then to the prettified slug."""
    return _ref_unit_names().get((civ, slug)) or _pretty_unit(slug, civ)


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
                "opp": f"{r['opp_civ']} {ref_unit_name(r['opp_civ'], r['opp_unit_slug'])}",
                "old_score": r["old_score"], "new_score": r["new_score"],
                "swing": r["swing"], "dir": "up" if r["swing"] >= 0 else "down",
                "link": battle_sim_deep_link(r["my_civ"], r["my_unit_slug"],
                                             r["opp_civ"], r["opp_unit_slug"], r["scale"]),
            })
        tables.append({
            "civ": civ, "slug": slug,
            "title": f"{civ} {ref_unit_name(civ, slug)}",
            "scale": best_scale,
            "stat_summary": "; ".join(stat_by_unit.get((civ, slug), [])),
            "detail_url": f"/patches/{build}/{civ}/{slug}",
            "max_swing": max(abs(r["swing"]) for r in top),
            "rows": out_rows,
        })
    tables.sort(key=lambda t: -t["max_swing"])
    return tables


def connect(path=None):
    conn = connect_readonly(path or PATCHES_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_patch_overview(build, path=None):
    """Assemble one patch's full landing-page data: metadata + rendered summary
    (notes with inlined matchup tables) + per-unit headline tables. Reuses the
    same render_patch_summary / _patch_unit_tables the hub uses, so the per-patch
    page and the hub can't diverge. Returns None for an unknown/absent build."""
    path = path or PATCHES_DB_PATH
    if not os.path.exists(path):
        return None
    conn = connect(path)
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


def patch_index(path=None):
    """Every patch, newest first, with its rendered summary (the /patches hub)."""
    path = path or PATCHES_DB_PATH
    if not os.path.exists(path):
        return []
    conn = connect(path)
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
    return patches


def patch_unit(build, civ, unit, path=None):
    """One unit's changes in one patch; None when the build is unknown.

    Any civ/unit is accepted for a known build (an unchanged unit simply has
    empty sections), like the original route."""
    path = path or PATCHES_DB_PATH
    if not os.path.exists(path):
        return None
    conn = connect(path)
    patch = conn.execute("SELECT * FROM patches WHERE build_number=?", (build,)).fetchone()
    if patch is None:
        conn.close()
        return None
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
        d["opp"] = f"{m['opp_civ']} {ref_unit_name(m['opp_civ'], m['opp_unit_slug'])}"
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
    return {"build": build, "civ": civ, "unit": unit, "unit_title": ref_unit_name(civ, unit),
            "patch": dict(patch), "stat_changes": stat_changes, "ranking": ranking,
            "now_beats": now_beats, "now_loses": now_loses, "shifted": shifted,
            "timeline": timeline}


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
