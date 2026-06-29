# SEO Phase 4 — Per-Patch Landing Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `/patches/<build>` per-patch landing page — the canonical URL that ranks for "Age of Empires II Update <build> patch notes" / "AoE2 new patch" — with `NewsArticle` structured data (the freshness signal), link it from the hub, and list every patch URL in the sitemap with a real `lastmod`.

**Architecture:** The `/patches` hub already server-renders each patch's `summary_html` (via `render_patch_summary` + `_patch_unit_tables`). We reuse those exact functions in a new `get_patch_overview(build)` helper and a `/patches/<build>` route that renders one patch as its own page (its own `<h1>`, title, `NewsArticle` + `BreadcrumbList` JSON-LD). No new data; one patch broken out of the existing hub into a canonical, crawlable, dated page.

**Tech Stack:** Flask, Jinja2, pytest. Data: `patches.db` (`patches`, `patch_unit_changes`, `patch_unit_ranking`, `patch_matchup_changes`).

**Confirmed data:** 2 builds (`170934`, `177723`); `patches` row has `build_number`, `title`, `release_date`, `summary_md`, `source_url`. `_patch_unit_tables(conn, pid, build)` already returns per-unit headline tables (`civ`, `slug`, `title`, `stat_summary`, `detail_url`, `rows`). `render_patch_summary(summary_md, tables)` already produces the full HTML (notes + inlined matchup tables with `/patches/<build>/<civ>/<unit>` detail links).

**Test command:** `.venv/bin/python -m pytest tests/test_seo_phase4.py -v` (from repo root). "Replay Analyzer disabled (no mgz)" on import is expected/harmless.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/app.py` | Modify | Add `get_patch_overview(build)`; add `/patches/<build>` route; add patch URLs (with `release_date` lastmod) to `sitemap_xml`. |
| `apps/website/templates/patch_build.html` | Create | The per-patch landing page (headline + summary_html + JSON-LD). |
| `apps/website/templates/patches.html` | Modify | Link each patch title to its `/patches/<build>` page. |
| `tests/test_seo_phase4.py` | Create | Phase 4 tests. |

---

## Task 1: `get_patch_overview(build)` helper

**Files:**
- Modify: `apps/website/app.py` (add near the other `_patch_*` helpers, ~line 365–446)
- Test: `tests/test_seo_phase4.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seo_phase4.py
def test_get_patch_overview(client):
    import app
    # Use the build with changes (confirmed: 177723).
    data = app.get_patch_overview("177723")
    assert data is not None
    assert data["build_number"] == "177723"
    assert data["release_date"]
    assert data["title"]
    assert "<" in data["summary_html"]  # rendered HTML
    assert isinstance(data["unit_tables"], list) and data["unit_tables"]
    t = data["unit_tables"][0]
    assert {"civ", "slug", "title", "detail_url"}.issubset(t.keys())
    # Unknown build returns None.
    assert app.get_patch_overview("000000") is None
```

- [ ] **Step 2: Run — FAIL** (`AttributeError: ... get_patch_overview`).

- [ ] **Step 3: Implement.** Add to `apps/website/app.py` (after `_patch_unit_tables`):

```python
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
```

- [ ] **Step 4: Run — PASS.**

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py tests/test_seo_phase4.py
git commit -m "feat(seo): add get_patch_overview helper for per-patch landing pages

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `/patches/<build>` route + template + hub link

**Files:**
- Modify: `apps/website/app.py` (add route after `patches_page`, ~line 446)
- Create: `apps/website/templates/patch_build.html`
- Modify: `apps/website/templates/patches.html`
- Test (APPEND): `tests/test_seo_phase4.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_patch_build_page_renders(client):
    import app
    data = app.get_patch_overview("177723")
    body = client.get("/patches/177723").data.decode()
    assert "177723" in body
    assert data["release_date"] in body
    # at least one changed-unit title from the summary is present
    assert data["unit_tables"][0]["title"].split()[-1] in body  # e.g. "Cavalry"


def test_patch_build_newsarticle_jsonld(client):
    import app
    data = app.get_patch_overview("177723")
    body = client.get("/patches/177723").data.decode()
    assert '"@type": "NewsArticle"' in body
    assert f'"datePublished": "{data["release_date"]}"' in body


def test_patch_build_404(client):
    assert client.get("/patches/000000").status_code == 404


def test_patches_hub_links_to_build_pages(client):
    body = client.get("/patches").data.decode()
    assert 'href="/patches/177723"' in body
```

- [ ] **Step 2: Run — FAIL** (route + template + hub link missing).

- [ ] **Step 3a: Add the route.** In `apps/website/app.py`, after `patches_page` (~line 446):

```python
@app.route("/patches/<build>")
def patch_build_page(build):
    """Canonical per-patch landing page — the 'AoE2 Update <build> patch notes' target."""
    data = get_patch_overview(build)
    if data is None:
        abort(404)
    return render_template("patch_build.html", active_nav="patches", **data)
```

- [ ] **Step 3b: Create the template** `apps/website/templates/patch_build.html`:

```html
{% extends "base.html" %}

{% block title %}Age of Empires II Update {{ build_number }} — Patch Notes &amp; Balance Changes{% endblock %}
{% block meta_description %}Full balance changes for Age of Empires II Update {{ build_number }} ({{ release_date }}): every unit buffed or nerfed, with the simulated matchup shifts each change caused.{% endblock %}
{% block og_type %}article{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/patches.css') if false else '' }}" />
{% endblock %}

{% block structured_data %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "Age of Empires II Update {{ build_number }} — Balance Changes",
  "datePublished": "{{ release_date }}",
  "dateModified": "{{ release_date }}",
  "author": { "@type": "Organization", "name": "AoE2 Matchup" },
  "publisher": { "@type": "Organization", "name": "AoE2 Matchup" },
  "mainEntityOfPage": "{{ site_url }}/patches/{{ build_number }}"
}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "{{ site_url }}/" },
    { "@type": "ListItem", "position": 2, "name": "Patches", "item": "{{ site_url }}/patches" },
    { "@type": "ListItem", "position": 3, "name": "Update {{ build_number }}", "item": "{{ site_url }}/patches/{{ build_number }}" }
  ]
}
</script>
{% endblock %}

{% block content %}
<div class="patch-wrap">
    <h1>Update {{ build_number }} — Balance Changes</h1>
    <p class="patch-date">
        Released {{ release_date }}
        {% if source_url %}· <a class="patch-link" href="{{ source_url }}" target="_blank" rel="nofollow noopener">Official notes ↗</a>{% endif %}
    </p>
    <p class="patch-intro">
        Every unit changed in Age of Empires II Update {{ build_number }}, and how each change moved
        its fully-upgraded matchups in simulation. Click any unit for the full breakdown.
    </p>
    <div class="patch-summary">{{ summary_html|safe }}</div>
</div>
{% endblock %}
```

(Reuse the existing `.patch-wrap` / `.patch-summary` styles already defined in `patches.html`'s inline CSS — confirm they're global or move the shared rules to a stylesheet if they're scoped to the hub template. If `patches.html` defines them inline in its own `page_css`, copy the needed `.patch-wrap/.patch-date/.patch-summary/.patch-link` rules into `patch_build.html`'s `page_css` block. Drop the placeholder `page_css` link line above and inline the rules instead.)

- [ ] **Step 3c: Link from the hub.** In `apps/website/templates/patches.html`, change the patch title heading to link to its build page:

```html
<h2><a href="/patches/{{ p.build_number }}">{{ p.title }}</a></h2>
```

- [ ] **Step 4: Run — PASS.** Then full suite.

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py apps/website/templates/patch_build.html apps/website/templates/patches.html tests/test_seo_phase4.py
git commit -m "feat(seo): add /patches/<build> per-patch landing page with NewsArticle

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Sitemap — per-patch + per-unit URLs with real `lastmod`

**Files:**
- Modify: `apps/website/app.py` (`sitemap_xml`)
- Test (APPEND): `tests/test_seo_phase4.py`

- [ ] **Step 1: Write the failing test**

```python
def test_sitemap_includes_patch_pages(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/patches/177723</loc>" in body
    # per-patch lastmod uses the release date
    import app
    rd = app.get_patch_overview("177723")["release_date"]
    assert f"<loc>{app.SITE_URL}/patches/177723</loc><lastmod>{rd}</lastmod>" in body
```

- [ ] **Step 2: Run — FAIL** (patch pages not in sitemap).

- [ ] **Step 3: Implement.** In `sitemap_xml` (`apps/website/app.py`), after the `/vs/` loop and before `xml_parts.append("</urlset>")`, add:

```python
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
```

- [ ] **Step 4: Run — PASS.** Then full suite.

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py tests/test_seo_phase4.py
git commit -m "feat(seo): list per-patch and per-unit patch pages in the sitemap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Verification & ship

- [ ] **Step 1:** Full suite green.
- [ ] **Step 2:** Browser/`curl` smoke (preview `aoe2-flask`): `/patches/177723` renders the headline, release date, and the unit change tables; `/patches` shows the title linking to it; `/sitemap.xml` lists `/patches/177723` (+ per-unit) with `release_date` lastmod; `/patches/000000` → 404; the existing `/patches` hub and `/patches/<build>/<civ>/<unit>` pages still work. Validate the `NewsArticle` JSON-LD parses. Screenshot the new page.
- [ ] **Step 3:** `git push origin staging`; ask user to verify on staging. Do NOT push `main`.

---

## Self-Review

**Spec coverage (Phase 6 Patch tracker):** new `/patches/<build>` page ✓ (Task 2); `NewsArticle` + `datePublished` freshness ✓; hub links to it ✓; sitemap with per-patch + per-unit URLs and `release_date` lastmod ✓ (Task 3); reuses `render_patch_summary`/`_patch_unit_tables` so hub and landing can't diverge ✓.

**Placeholder scan:** one soft spot — Task 3b notes the shared `.patch-*` CSS may be inline in `patches.html`; the implementer must read it and either confirm it's global or copy the rules into `patch_build.html`. Called out explicitly rather than hidden.

**Type/name consistency:** `get_patch_overview` returns `{build_number, title, release_date, source_url, summary_html, unit_tables}`; the route passes them via `**data`; the template reads exactly those names; tests assert the same. Sitemap loop emits `<loc>{SITE_URL}/patches/{build}</loc><lastmod>{release_date}</lastmod>`, matching the test's exact-string assertion.
