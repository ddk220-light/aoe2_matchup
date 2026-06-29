# SEO Phase 0 — Zero-Risk Crawl Wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the lowest-risk, highest-leverage crawl improvements from the discoverability spec — honest `lastmod`, fonts preconnect, breadcrumb structured data on matchup pages, and a new `/matchups` crawl-hub — without touching any interactive JS render path, so the freshly-verified Search Console crawler sees real, well-linked content immediately.

**Architecture:** All changes are server-side template/route additions in the Flask app (`apps/website/`). No new data pipelines, no sim code, no client JS changes. Each task is independently shippable to `staging` and verified by a Flask test-client test in `tests/test_seo_phase0.py`.

**Tech Stack:** Flask, Jinja2 templates, pytest (`client` fixture in `tests/conftest.py`), SQLite reference DB (read-only via existing helpers).

**Scope note — items verified already-done (no task needed):**
- **Single `<h1>` per page:** every template in `apps/website/templates/*.html` already has exactly one `<h1>` (verified by grep). No work.
- **`alt` text on server-rendered images:** the only server-rendered `<img>` tags are the two JS-swapped progress icons in `simulate.html`, already `alt=""` (correct for decorative/JS-populated). All unit/civ icons render client-side and are out of scope for crawl HTML. No work.
- The `/vs/` **verdict sentence**, **civ-identity corpus**, and all **SSR page work** are deliberately deferred to later phase plans (they need a sim-backed helper / new data file), per the spec's phasing.

**Deviation from spec, with rationale:** the spec said link `/matchups` from "footer + nav". This plan links it from the **footer only** — the top nav already carries 6 tool tabs and a 7th crowds mobile. The footer "Explore" column is the conventional home for an SEO hub link and keeps the clean UI the user wants. (A nav tab can be added later if desired.)

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/app.py` | Modify | Add `_data_lastmod()` helper; use it in `sitemap_xml`; add `/matchups` hub list entry; add `matchups_hub` route; pass `site_url` to the `/vs/` render. |
| `apps/website/templates/base.html` | Modify | Add fonts `preconnect` links in `<head>`. |
| `apps/website/templates/matchup_landing.html` | Modify | Add `BreadcrumbList` JSON-LD. |
| `apps/website/templates/matchups.html` | Create | The `/matchups` crawl-hub page. |
| `apps/website/templates/_footer.html` | Modify | Add `/matchups` link to the Explore column. |
| `tests/test_seo_phase0.py` | Create | All Phase 0 regression tests. |

---

## Task 1: Data-derived sitemap `<lastmod>`

Drive `<lastmod>` from the newest committed data artifact's mtime instead of `date.today()`, so the crawler doesn't see every URL "change" on every deploy (which erodes trust in the signal).

**Files:**
- Modify: `apps/website/app.py` (function `sitemap_xml`, ~line 654; add helper just above it)
- Test: `tests/test_seo_phase0.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seo_phase0.py
import datetime


def test_sitemap_lastmod_reflects_data_build(client):
    import app
    body = client.get("/sitemap.xml").data.decode()
    expected = app._data_lastmod()
    # Every <lastmod> in the sitemap uses the data-build date, not "today".
    assert f"<lastmod>{expected}</lastmod>" in body
    # And it is a valid ISO date.
    datetime.date.fromisoformat(expected)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seo_phase0.py::test_sitemap_lastmod_reflects_data_build -v`
Expected: FAIL with `AttributeError: module 'app' has no attribute '_data_lastmod'`

- [ ] **Step 3: Add the helper and use it**

Add this helper immediately above `@app.route("/sitemap.xml")` in `apps/website/app.py`:

```python
@lru_cache(maxsize=1)
def _data_lastmod():
    """ISO date of the newest committed data artifact.

    Used as the sitemap <lastmod> so it reflects real data builds rather than
    the deploy day — a stable signal that only moves when the data actually
    changes. Falls back to today if no artifact is present (fresh checkout)."""
    candidates = [
        os.path.join(str(_GOLDEN_DIR), "derived_data.db"),
        os.path.join(str(_GOLDEN_DIR), "aoe2_reference.db"),
        os.path.join(str(_GOLDEN_DIR), "pool_scores.db"),
    ]
    mtimes = [os.path.getmtime(p) for p in candidates if os.path.exists(p)]
    if not mtimes:
        return date.today().isoformat()
    return date.fromtimestamp(max(mtimes)).isoformat()
```

Then in `sitemap_xml`, replace the first line:

```python
    today = date.today().isoformat()
```

with:

```python
    lastmod = _data_lastmod()
```

and update the inner `_url` helper to use `lastmod` instead of `today`:

```python
    def _url(path, changefreq, priority):
        return (f"<url><loc>{SITE_URL}{path}</loc>"
                f"<lastmod>{lastmod}</lastmod>"
                f"<changefreq>{changefreq}</changefreq>"
                f"<priority>{priority}</priority></url>")
```

(`lru_cache`, `os`, `date`, and `_GOLDEN_DIR` are already imported/defined in `app.py` — no new imports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seo_phase0.py::test_sitemap_lastmod_reflects_data_build -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py tests/test_seo_phase0.py
git commit -m "feat(seo): drive sitemap lastmod from data-build date, not deploy day

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Fonts `preconnect`

Cut LCP by opening the Google Fonts connections early. The stylesheet `<link>` already exists at `base.html:55`; just add two preconnects before it.

**Files:**
- Modify: `apps/website/templates/base.html` (in `<head>`, immediately before line 55's fonts stylesheet link)
- Test: `tests/test_seo_phase0.py`

- [ ] **Step 1: Write the failing test**

```python
def test_fonts_preconnect_present(client):
    body = client.get("/").data.decode()
    assert '<link rel="preconnect" href="https://fonts.googleapis.com"' in body
    assert '<link rel="preconnect" href="https://fonts.gstatic.com"' in body
    assert 'crossorigin' in body  # gstatic preconnect must be crossorigin
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seo_phase0.py::test_fonts_preconnect_present -v`
Expected: FAIL (preconnect links not present)

- [ ] **Step 3: Add the preconnect links**

In `apps/website/templates/base.html`, find the fonts stylesheet line (line 55):

```html
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Source+Sans+3:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
```

Insert these two lines immediately **before** it:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seo_phase0.py::test_fonts_preconnect_present -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/website/templates/base.html tests/test_seo_phase0.py
git commit -m "perf(seo): preconnect to Google Fonts origins to cut LCP

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `BreadcrumbList` JSON-LD on `/vs/` pages

Add breadcrumb structured data (Home → Matchups → "A vs B") so SERP shows a breadcrumb trail and crawlers understand the hierarchy. The route already has `canonical_url`; we add `site_url` (already a template global via the context processor, but pass it explicitly for clarity) and a second JSON-LD block.

**Files:**
- Modify: `apps/website/templates/matchup_landing.html` (after the existing FAQPage JSON-LD, ~line 35)
- Test: `tests/test_seo_phase0.py`

- [ ] **Step 1: Write the failing test**

```python
def test_vs_page_has_breadcrumb_jsonld(client):
    import app
    pairs = app._unique_units_list()  # [(civ, slug, name), ...]
    (civ_a, slug_a, _), (civ_b, slug_b, _) = pairs[0], pairs[1]
    body = client.get(f"/vs/{civ_a}/{slug_a}/{civ_b}/{slug_b}").data.decode()
    assert '"@type": "BreadcrumbList"' in body
    assert '"name": "Matchups"' in body
    assert '/matchups' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seo_phase0.py::test_vs_page_has_breadcrumb_jsonld -v`
Expected: FAIL (no BreadcrumbList in body)

- [ ] **Step 3: Add the BreadcrumbList JSON-LD**

In `apps/website/templates/matchup_landing.html`, the file opens with a FAQPage JSON-LD `<script>` block (starts line 8). Immediately after that block's closing `</script>`, add:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "{{ site_url }}/" },
    { "@type": "ListItem", "position": 2, "name": "Matchups", "item": "{{ site_url }}/matchups" },
    { "@type": "ListItem", "position": 3, "name": "{{ a_name }} vs {{ b_name }}", "item": "{{ canonical_url }}" }
  ]
}
</script>
```

(`site_url`, `a_name`, `b_name`, and `canonical_url` are all already in this template's render context — `site_url` via the `inject_site_url` context processor, the rest via the `matchup_landing` route.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seo_phase0.py::test_vs_page_has_breadcrumb_jsonld -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/website/templates/matchup_landing.html tests/test_seo_phase0.py
git commit -m "feat(seo): add BreadcrumbList JSON-LD to /vs/ matchup pages

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `/matchups` crawl-hub page

A real, crawlable index linking into every `/vs/` landing page (each unordered unique-unit matchup listed once), so the long-tail pages have a permanent entry point beyond the sitemap, plus a keyword-rich page in its own right. Linked from the footer Explore column and listed in the sitemap.

**Files:**
- Create: `apps/website/templates/matchups.html`
- Modify: `apps/website/app.py` (add `matchups_hub` route; add `("/matchups", ...)` to the sitemap `hub` list)
- Modify: `apps/website/templates/_footer.html` (Explore column)
- Test: `tests/test_seo_phase0.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_matchups_hub_renders(client):
    resp = client.get("/matchups")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "AoE2 Unit Matchups" in body
    assert "/vs/" in body  # links into landing pages


def test_matchups_hub_linked_from_footer(client):
    body = client.get("/").data.decode()
    assert 'href="/matchups"' in body


def test_matchups_hub_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/matchups</loc>" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_seo_phase0.py -k matchups_hub -v`
Expected: FAIL — `/matchups` 404s; footer/sitemap lack the link.

- [ ] **Step 3a: Add the route**

In `apps/website/app.py`, add this route (place it near the other page routes, e.g. just after the `matchup_landing` route ~line 783):

```python
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
    return render_template("matchups.html", groups=groups, active_nav="simulate")
```

- [ ] **Step 3b: Add the sitemap entry**

In `sitemap_xml`, add `/matchups` to the `hub` list (after the `/patches` entry):

```python
    hub = [
        ("/", "weekly", "1.0"),
        ("/matchup-advisor", "weekly", "0.9"),
        ("/units", "weekly", "0.9"),
        ("/civilizations", "weekly", "0.9"),
        ("/matchups", "weekly", "0.6"),
        ("/patches", "weekly", "0.7"),
    ]
```

- [ ] **Step 3c: Create the template**

Create `apps/website/templates/matchups.html`:

```html
{% extends "base.html" %}

{% block title %}AoE2 Unit Matchups — Every unique-unit battle, simulated{% endblock %}
{% block meta_description %}Browse simulated Age of Empires II unit matchups across all 53 civilizations — every unique unit versus every other, with full-upgrade stat comparisons and a live battle simulator.{% endblock %}

{% block content %}
<div class="page-header">
    <h1>AoE2 Unit Matchups</h1>
    <p class="subtitle">Every civilization's unique unit, simulated against every other — pick a matchup to see who wins at full upgrades.</p>
</div>

<div class="container">
    {% for group in groups %}
    <section class="matchup-group">
        <h2>{{ group.unit }} <span class="matchup-group-civ">({{ group.civ }})</span></h2>
        <ul class="matchup-link-list">
            {% for link in group.links %}
            <li><a href="{{ link.url }}">{{ link.label }}</a></li>
            {% endfor %}
        </ul>
    </section>
    {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 3d: Add the footer link**

In `apps/website/templates/_footer.html`, the Explore column lists four links. Add `/matchups` after Civilizations:

```html
            <ul class="site-footer-list">
                <li><a href="/">Battle Sim</a></li>
                <li><a href="/matchup-advisor">Matchup Advisor</a></li>
                <li><a href="/units">Rankings</a></li>
                <li><a href="/civilizations">Civilizations</a></li>
                <li><a href="/matchups">Unit Matchups</a></li>
            </ul>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_seo_phase0.py -k matchups_hub -v`
Expected: PASS (all three)

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py apps/website/templates/matchups.html apps/website/templates/_footer.html tests/test_seo_phase0.py
git commit -m "feat(seo): add /matchups crawl-hub indexing all unique-unit matchups

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Phase 0 verification & ship to staging

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest`
Expected: PASS — all existing tests plus the 6 new Phase 0 tests green. If anything fails, fix before proceeding (do not ship red).

- [ ] **Step 2: Smoke-test the running app**

Run: `PORT=5002 python apps/website/app.py` in one shell, then in another:

```bash
curl -s localhost:5002/sitemap.xml | grep -c "<lastmod>"          # > 0, and dates are the data-build date
curl -s localhost:5002/matchups | grep -c "/vs/"                  # > 0 (hub has links)
curl -s "localhost:5002/" | grep -c 'rel="preconnect"'            # 2
```

Expected: lastmod count > 0 (not today's deploy date), `/matchups` link count > 0, preconnect count = 2.

- [ ] **Step 3: Confirm the branch and push to staging**

```bash
git status                 # on staging, clean working tree (Phase 0 commits in)
git log --oneline -6       # the 4 feature commits present
git push origin staging
```

Then ask the user to verify on the staging URL before any promotion to `main`. **Do not** push to `main` (production) — that is the user's explicit decision per the repo git workflow.

---

## Self-Review

**Spec coverage (Phase 0 slice of `2026-06-28-seo-ssr-discoverability-design.md`):**
- Real `lastmod` → Task 1 ✓
- Fonts `preconnect` → Task 2 ✓
- `BreadcrumbList` on `/vs/` → Task 3 ✓
- `/matchups` hub + footer link + sitemap → Task 4 ✓
- Single-`<h1>` audit → verified already satisfied (Scope note) ✓
- `alt` text → verified non-issue server-side (Scope note) ✓
- `/vs/` verdict, civ identity, SSR pages, patch landing → explicitly deferred to later phase plans ✓

**Placeholder scan:** none — every step has exact code, paths, and commands.

**Type/name consistency:** `_data_lastmod()` (Task 1) is the only new helper and is referenced consistently. `matchups_hub` route renders `matchups.html` with a `groups` variable; the template iterates `groups` with `.unit`, `.civ`, `.links[].url`, `.links[].label` — matches the route's dict shape. The sitemap test asserts `"/matchups</loc>"`, which matches `_url`'s `<loc>{SITE_URL}{path}</loc>` output for `path="/matchups"`.
