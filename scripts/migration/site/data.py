"""Page data that only the published pages need (moved from the website's HTML routes).

Matchup hub and landing data come from the reference DB; the rankings overview
reuses the API's unit-line projection so the two cannot diverge.
"""
from functools import lru_cache
import sqlite3

from .content import POPULAR_MATCHUPS
from .sources import REF_DB_PATH, connect_readonly, unit_line_data


def _reference():
    conn = connect_readonly(REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=1)
def unique_units_list():
    """Cached [(civ, slug, name)] — one unique unit per civ (Elite preferred).

    Shared by the related-matchups cross-linker so every /vs/ landing page links
    to a handful of siblings. Without these internal links the landing pages are
    orphans (reachable only via sitemap.xml), which crawlers heavily deprioritize."""
    conn = _reference()
    rows = conn.execute(
        """SELECT civ_name, unit_slug, unit_name FROM ref_units
           WHERE age='Imperial' AND unit_slug LIKE '%\\_%' ESCAPE '\\'
           ORDER BY civ_name, unit_slug""").fetchall()
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


def load_unit_for_landing(civ_name, unit_slug):
    """ref_units row for a /vs/ landing page (Imperial preferred), or None."""
    conn = _reference()
    row = conn.execute("SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'",
                       (civ_name, unit_slug)).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=?",
                           (civ_name, unit_slug)).fetchone()
    conn.close()
    return dict(row) if row else None


def popular_matchup_links():
    """[(label, url)] for the curated popular matchups."""
    out = []
    for m in POPULAR_MATCHUPS:
        (ca, ua), (cb, ub) = m["a"], m["b"]
        out.append((m["label"], f"/vs/{ca}/{ua}/{cb}/{ub}"))
    return out


def matchup_seed_pairs(limit_per_side=200):
    """(civ_a, slug_a, civ_b, slug_b) for the sitemap: every unique unit (one per
    civ, Elite preferred) vs every other unique unit."""
    conn = _reference()
    rows = conn.execute(
        """SELECT civ_name, unit_slug
           FROM ref_units
           WHERE age='Imperial' AND unit_slug LIKE '%\\_%' ESCAPE '\\'
           ORDER BY civ_name, unit_slug""").fetchall()
    conn.close()
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
    pairs = []
    for i, a in enumerate(uniques):
        for b in uniques[i + 1:]:
            pairs.append((a[0], a[1], b[0], b[1]))
    return pairs


def matchup_groups():
    """The /matchups hub: each unordered unique-unit matchup exactly once (civ A
    vs civ B where A precedes B), grouped by the first civ."""
    uniques = unique_units_list()
    groups = []
    for i, (civ_a, slug_a, name_a) in enumerate(uniques):
        links = [{"url": f"/vs/{civ_a}/{slug_a}/{civ_b}/{slug_b}", "label": f"{name_a} vs {name_b}"}
                 for j, (civ_b, slug_b, name_b) in enumerate(uniques) if j > i]
        if links:
            groups.append({"civ": civ_a, "unit": name_a, "links": links})
    return groups


# Headline categories for the server-rendered "Rankings at a glance" section.
RANKINGS_HEADLINE_LINES = [
    ("infantry", "Infantry"),
    ("archery", "Archers & Gunpowder"),
    ("stable", "Cavalry"),
    ("siege", "Siege"),
    ("naval", "Naval"),
]


def ranking_score(unit):
    """The one published final ranking score for a unit, or None."""
    value = unit.get("ranking_score")
    return value if isinstance(value, (int, float)) else None


def rankings_overview(top_n=8):
    """Top units per headline category by the published final score."""
    out = []
    for line_slug, label in RANKINGS_HEADLINE_LINES:
        line = unit_line_data(line_slug) or {}
        scored = []
        for u in line.get("imperial", []):
            s = ranking_score(u)
            if s is None:
                continue
            scored.append({"civ": u["civ_name"], "name": u.get("unit_name") or u["unit_slug"],
                           "slug": u["unit_slug"], "score": round(s, 1)})
        scored.sort(key=lambda x: x["score"], reverse=True)
        out.append({"line_slug": line_slug, "label": label, "units": scored[:top_n]})
    return out
