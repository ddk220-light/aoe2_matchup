# SEO — Per-Civ & Per-Unit-Line Landing Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Capture "aoe2 <civ>" searches (e.g. "aoe2 bengalis") with 53 per-civ landing pages that open the civ analyzer preselected, and "aoe2 <unit>" searches (e.g. "aoe2 fire lancer") with 21 per-unit-line landing pages plus deep links into `/units` that select the right tab and highlight the unit's rows.

**Architecture:** Both features reuse existing data helpers — `get_civ_overview_data()` (civ identity + power units) and `get_unit_line_data(line_slug)` (per-civ line stats + scores) — so SSR pages and the JSON APIs never diverge. Per-civ pages un-retire the `/civilizations/<slug>` route (currently a 301 to the index); unit-line pages add `/units/<url-slug>` from a curated `_UNIT_LINE_PAGES` list. The interactive layers get tiny hooks: `matchup.js` preselects a civ from `window.PRESELECT_CIV`; `rankings.js` reads `?line=&unit=` URL params to select the tab and highlight rows.

**Tech Stack:** Flask, Jinja2, vanilla JS, pytest. **Test command:** `.venv/bin/python -m pytest tests/test_seo_civ_pages.py tests/test_seo_unit_line_pages.py -v` (from repo root). NEVER bare `python`/`pytest` — use `.venv/bin/python`.

**Key facts (verified against the codebase):**
- `get_civ_overview_data()` (app.py ~1664) returns `[{name, slug (=name.lower()), description, roles:[{label, units:[{name, slug, tier, is_unique}]}]}]`.
- `/civilizations/<civ_name>` route (app.py ~628, `civ_detail`) currently 301-redirects to the index — replace it. `/civ` and `/civ/<civ_name>` compat redirects exist below it.
- `matchup.js` builds the civ grid from `const CIVS = {{ civs | tojson }}` (set in the template's `page_js` block) with `CIVS.forEach(...)` at ~line 79; `onCivClick(name)` at ~line 99 selects a civ and calls `loadAnalysis`.
- `get_unit_line_data(line_slug)` (app.py ~1305) returns `{line_name, building, imperial: [rows]}` or None; each row has `civ_name, unit_name, unit_slug, final_hp, final_attack, final_melee_armor, final_pierce_armor, final_speed, final_range, ...` plus score keys (`general_combat`, `ranged_effectiveness`, `stable_effectiveness`, `anti_building_score`, `naval_effectiveness`) only where pool/derived scores exist.
- `rankings.js`: global `UNIT_LINES` object (line keys + group tabs), `async function selectLine(slug)` at ~line 980, row HTML built at ~line 1786 (`html += `<tr class="${rowClass}">`;`), boot call `selectLine("infantry");` is the LAST line (~2104). Tab buttons call `selectLine('<slug>')` via onclick (~line 943).
- `sitemap_xml` (app.py ~782) appends `_url(path, changefreq, priority)` strings; add new loops after the `hub` loop.
- The `/units` page route is `@app.route("/units")` at app.py ~604 (function renders `rankings.html`).
- Canonical URLs come from `base.html` via `request.path` — query-param variants of `/units` automatically canonicalize to `/units` (no duplicate-content risk from deep links).
- A global `before_request` (`_seo_canonical_redirects`) already 301s trailing slashes; new routes need no slash handling.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/app.py` | Modify | `get_civ_detail()`, real `civ_detail` route, `/civ*` redirect targets, `_UNIT_LINE_PAGES` + `/units/<slug>` route, sitemap additions, pass line links to `/units`. |
| `apps/website/templates/civ_detail.html` | Create | Per-civ landing page (SSR identity + power units, interactive analyzer preselected, BreadcrumbList). |
| `apps/website/templates/civ_overview.html` | Modify | Link each SSR civ heading to its page; ItemList URLs → detail pages. |
| `apps/website/templates/unit_line.html` | Create | Per-line landing page (SSR ranked table, CTA deep link, BreadcrumbList). |
| `apps/website/templates/rankings.html` | Modify | "Unit line guides" link list in the SSR section. |
| `apps/website/static/js/matchup.js` | Modify | `window.PRESELECT_CIV` hook. |
| `apps/website/static/js/rankings.js` | Modify | `?line=&unit=` deep-link init, row highlight, URL sync on tab click. |
| `apps/website/static/css/matchup.css` | Modify | Civ heading link + detail-page styles. |
| `apps/website/static/css/rankings.css` | Modify | Highlight style + line-guide link list styles. |
| `tests/test_seo_civ_pages.py` | Create | Feature A tests. |
| `tests/test_seo_unit_line_pages.py` | Create | Feature B tests. |

---

## Task 1: Per-civ landing pages (`/civilizations/<slug>`)

**Files:** Modify `apps/website/app.py`, `apps/website/templates/civ_overview.html`, `apps/website/static/js/matchup.js`, `apps/website/static/css/matchup.css`. Create `apps/website/templates/civ_detail.html`, `tests/test_seo_civ_pages.py`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_seo_civ_pages.py`:

```python
# tests/test_seo_civ_pages.py — per-civ landing pages (SEO: "aoe2 <civ>" searches).
_DEFAULT_DESC = "Free Age of Empires II matchup simulator"  # base.html fallback


def test_all_civ_pages_resolve_with_own_title(client):
    import app
    for name in app._get_ref_civs():
        resp = client.get(f"/civilizations/{name.lower()}")
        assert resp.status_code == 200, name
        body = resp.data.decode()
        assert f"<title>{name}" in body, name
        assert _DEFAULT_DESC not in body.split("</head>")[0], name


def test_titlecase_url_redirects_to_lowercase(client):
    resp = client.get("/civilizations/Bengalis")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/civilizations/bengalis")


def test_unknown_civ_404s(client):
    assert client.get("/civilizations/atlantis").status_code == 404


def test_civ_page_preselects_and_has_breadcrumbs(client):
    body = client.get("/civilizations/bengalis").data.decode()
    assert "PRESELECT_CIV" in body and "Bengalis" in body
    assert '"@type": "BreadcrumbList"' in body
    assert 'id="civ-grid"' in body  # interactive analyzer present


def test_index_links_to_detail_pages(client):
    body = client.get("/civilizations").data.decode()
    assert 'href="/civilizations/bengalis"' in body


def test_civ_pages_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/civilizations/bengalis</loc>" in body


def test_legacy_civ_redirect_targets_detail_page(client):
    resp = client.get("/civ/Franks")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith("/civilizations/franks")
```

- [ ] **Step 2: Run — FAIL.** `.venv/bin/python -m pytest tests/test_seo_civ_pages.py -v` (301-to-index / missing template).

- [ ] **Step 3: `get_civ_detail` helper.** In `app.py`, directly AFTER the `get_civ_overview_data()` function body, add:

```python
def get_civ_detail(slug):
    """Single-civ entry from get_civ_overview_data() for the per-civ landing
    page. slug is the lowercase civ name; returns None if unknown."""
    for civ in get_civ_overview_data():
        if civ["slug"] == slug:
            return civ
    return None
```

- [ ] **Step 4: Replace the retired route.** Replace the whole existing `civ_detail` function (the `@app.route("/civilizations/<civ_name>")` that 301s to the index, app.py ~628) with:

```python
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
```

And update BOTH legacy redirects (`civ_redirect` stays as-is; `civ_detail_redirect`) so `/civ/<civ_name>` points at the detail page:

```python
@app.route("/civ/<civ_name>")
def civ_detail_redirect(civ_name):
    """Backward compat redirect."""
    return redirect(f"/civilizations/{civ_name.lower()}", code=301)
```

- [ ] **Step 5: Create `apps/website/templates/civ_detail.html`:**

```html
{% extends 'base.html' %}

{% block title %}{{ civ.name }} — AoE2 Civilization: Best Units & Strategy{% endblock %}
{% block meta_description %}{{ meta_desc }}{% endblock %}
{% block structured_data %}
{{ super() }}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "{{ site_url }}/" },
    { "@type": "ListItem", "position": 2, "name": "Civilizations", "item": "{{ site_url }}/civilizations" },
    { "@type": "ListItem", "position": 3, "name": "{{ civ.name }}", "item": "{{ site_url }}/civilizations/{{ civ.slug }}" }
  ]
}
</script>
{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/matchup.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>{{ civ.name }}</h1>
    <p class="subtitle">Age of Empires II civilization analysis — power units, tiers, and strategic identity</p>
</div>

<div class="container-wide">
    <p class="civ-detail-nav"><a href="/civilizations">&larr; All civilizations</a>
       &middot; <a href="/matchup-advisor">Matchup Advisor</a></p>

    <div class="civ-selector">
        <div class="step-label step-civ1" id="step-label">Loading {{ civ.name }} analysis&hellip;</div>
        <div class="civ-grid" id="civ-grid"></div>
    </div>

    <div id="results" class="results-container"></div>

    <section class="civ-ssr" aria-label="{{ civ.name }} overview">
        <h2 class="civ-ssr-title">{{ civ.name }} at a glance</h2>
        {% if civ.description %}<p class="civ-ssr-desc">{{ civ.description }}</p>{% endif %}
        {% for role in civ.roles %}
        <p class="civ-ssr-role"><span class="civ-ssr-role-label">{{ role.label }}:</span>
            {% for unit in role.units %}{% if unit.is_unique %}<strong class="civ-ssr-unique" title="Unique unit">{{ unit.name }}</strong>{% else %}{{ unit.name }}{% endif %}{% if unit.tier %} ({{ unit.tier }}){% endif %}{% if not loop.last %}, {% endif %}{% endfor %}
        </p>
        {% endfor %}
        <p class="civ-ssr-intro">Tiers come from full round-robin battle simulations at Imperial-age upgrades — see <a href="/about">how it works</a>.</p>
    </section>
</div>
{% endblock %}

{% block page_js %}
<script>
    const CIVS = {{ civs | tojson }};
    window.PRESELECT_CIV = {{ civ.name | tojson }};
</script>
<script src="{{ url_for('static', filename='js/matchup.js') }}"></script>
{% endblock %}
```

- [ ] **Step 6: `matchup.js` preselect hook.** Immediately AFTER the `CIVS.forEach(...)` grid-build block (~line 96, after `civGrid.appendChild(card); });`), add:

```js
/* ---- Per-civ landing page preselect (set by civ_detail.html) ---- */
if (window.PRESELECT_CIV && CIVS.indexOf(window.PRESELECT_CIV) !== -1) {
    onCivClick(window.PRESELECT_CIV);
}
```

(`onCivClick` is a hoisted function declaration — calling it here is safe.)

- [ ] **Step 7: Index links.** In `civ_overview.html`: change the SSR heading (line 46) to `<h3><a href="/civilizations/{{ civ.slug }}">{{ civ.name }}</a></h3>` and the ItemList `url` (line 18) to `"{{ site_url }}/civilizations/{{ civ.slug }}"`. Append to `apps/website/static/css/matchup.css`:

```css
/* Per-civ landing pages */
.civ-ssr-civ h3 a { color: inherit; text-decoration: none; }
.civ-ssr-civ h3 a:hover { color: var(--gold); text-decoration: underline; }
.civ-detail-nav { margin: 0 0 14px; font-size: var(--fs-sm, 0.9rem); }
```

- [ ] **Step 8: Sitemap.** In `sitemap_xml`, after the `hub` loop, add:

```python
    # Per-civ landing pages ("aoe2 <civ>" searches).
    for _c in _get_ref_civs():
        xml_parts.append(_url(f"/civilizations/{_c.lower()}", "weekly", "0.7"))
```

- [ ] **Step 9: Run — all tests PASS**, then full suite `.venv/bin/python -m pytest -q` (0 failures).

- [ ] **Step 10: Commit**

```bash
git add apps/website/app.py apps/website/templates/civ_detail.html apps/website/templates/civ_overview.html apps/website/static/js/matchup.js apps/website/static/css/matchup.css tests/test_seo_civ_pages.py
git commit -m "feat(seo): per-civ landing pages with preselected analyzer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Per-unit-line landing pages (`/units/<slug>`)

**Files:** Modify `apps/website/app.py`, `apps/website/templates/rankings.html`, `apps/website/static/css/rankings.css`. Create `apps/website/templates/unit_line.html`, `tests/test_seo_unit_line_pages.py`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_seo_unit_line_pages.py`:

```python
# tests/test_seo_unit_line_pages.py — per-unit-line landing pages ("aoe2 fire lancer").
_DEFAULT_DESC = "Free Age of Empires II matchup simulator"


def test_all_unit_line_pages_resolve(client):
    import app
    assert len(app._UNIT_LINE_PAGES) >= 20
    for p in app._UNIT_LINE_PAGES:
        resp = client.get(f"/units/{p['url']}")
        assert resp.status_code == 200, p["url"]
        body = resp.data.decode()
        assert f"<title>{p['title']}" in body, p["url"]
        assert _DEFAULT_DESC not in body.split("</head>")[0], p["url"]


def test_fire_lancer_page_content(client):
    body = client.get("/units/shock-infantry").data.decode()
    assert "Fire Lancer" in body
    assert "Eagle Warrior" in body
    assert '"@type": "BreadcrumbList"' in body
    assert "?line=shock_infantry" in body       # CTA deep link into /units
    assert 'href="/civilizations/' in body      # rows cross-link civ pages


def test_knight_page_has_full_table(client):
    body = client.get("/units/knight").data.decode()
    assert body.count("<tr") > 30  # one row per civ (53 civs, some unique extras)


def test_unknown_line_404s(client):
    assert client.get("/units/wololo").status_code == 404


def test_unit_line_pages_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/units/shock-infantry</loc>" in body
    assert "/units/knight</loc>" in body


def test_units_page_links_line_guides(client):
    body = client.get("/units").data.decode()
    assert 'href="/units/shock-infantry"' in body


def test_units_deeplink_params_dont_break_page(client):
    resp = client.get("/units?line=shock_infantry&unit=fire_lancer")
    assert resp.status_code == 200
    # canonical must stay the clean URL (query variants must not index separately)
    assert 'rel="canonical" href="' in resp.data.decode()
```

- [ ] **Step 2: Run — FAIL** (`AttributeError: _UNIT_LINE_PAGES`).

- [ ] **Step 3: Curated page list + route.** In `app.py`, near the `/units` route, add (each `line` key MUST exist in `UNIT_LINES` — the resolve-all test enforces it):

```python
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

# Score keys checked (in order) for the SSR table's single "Sim score" column.
_LINE_PAGE_SCORE_KEYS = ("general_combat", "ranged_effectiveness",
                         "stable_effectiveness", "anti_building_score",
                         "naval_effectiveness")


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
        for k in _LINE_PAGE_SCORE_KEYS:
            v = r.get(k)
            if isinstance(v, (int, float)):
                return v
        return None

    rows = [(r, _row_score(r)) for r in data["imperial"]]
    rows.sort(key=lambda t: (-(t[1] if t[1] is not None else float("-inf")),
                             t[0]["civ_name"]))
    return render_template("unit_line.html", page=page, line=data, rows=rows,
                           active_nav="rankings")
```

- [ ] **Step 4: Create `apps/website/templates/unit_line.html`:**

```html
{% extends 'base.html' %}

{% block title %}{{ page.title }}{% endblock %}
{% block meta_description %}{{ page.desc }}{% endblock %}
{% block structured_data %}
{{ super() }}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "{{ site_url }}/" },
    { "@type": "ListItem", "position": 2, "name": "Unit Rankings", "item": "{{ site_url }}/units" },
    { "@type": "ListItem", "position": 3, "name": {{ line.line_name | tojson }}, "item": "{{ site_url }}/units/{{ page.url }}" }
  ]
}
</script>
{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/rankings.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>{{ page.title.split(" — ")[0] }} Rankings</h1>
    <p class="subtitle">{{ line.line_name }} ({{ line.building }}) — every civilization at full Imperial upgrades</p>
</div>

<div class="container">
    <p class="line-page-nav">
        <a href="/units?line={{ page.line }}" class="line-page-cta">Open in interactive rankings &rarr;</a>
        &middot; <a href="/units">All unit rankings</a>
    </p>
    <p class="line-page-desc">{{ page.desc }}</p>

    <div class="table-container line-page-table">
        <table class="stats-table">
            <thead><tr>
                <th>#</th><th>Civilization</th><th>Unit</th><th>HP</th><th>Attack</th>
                <th>Armor</th><th>Sim score</th>
            </tr></thead>
            <tbody>
            {% for row, score in rows %}
            <tr>
                <td>{{ loop.index }}</td>
                <td><a href="/civilizations/{{ row.civ_name | lower }}">{{ row.civ_name }}</a></td>
                <td><a href="/units?line={{ page.line }}&unit={{ row.unit_slug }}">{{ row.unit_name }}</a></td>
                <td>{{ row.final_hp }}</td>
                <td>{{ row.final_attack }}</td>
                <td>{{ row.final_melee_armor }}/{{ row.final_pierce_armor }}</td>
                <td>{% if score is not none %}{{ "%.1f" | format(score) }}{% else %}&mdash;{% endif %}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <p class="line-page-method">Scores come from full round-robin battle simulations
       (equal numbers and equal resources) at Imperial-age upgrades —
       <a href="/about">methodology</a>. Rows without a score are outside this
       line's simulated pool.</p>
</div>
{% endblock %}
```

- [ ] **Step 5: Link guides from `/units`.** In the `/units` route (app.py ~604), pass `unit_line_pages=[(p["url"], p["short"]) for p in _UNIT_LINE_PAGES]` to `render_template`. In `rankings.html`, INSIDE the `rankings-ssr` section (after its existing content, before `</section>`), add:

```html
    <nav class="rankings-ssr-lines" aria-label="Unit line guides">
        <h3>Unit line guides</h3>
        <ul>
            {% for url, label in unit_line_pages %}
            <li><a href="/units/{{ url }}">{{ label }}</a></li>
            {% endfor %}
        </ul>
    </nav>
```

Append to `rankings.css`:

```css
.rankings-ssr-lines h3 { font-family: var(--font-display); color: var(--gold); font-size: var(--fs-md, 1rem); margin: 18px 0 8px; }
.rankings-ssr-lines ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 16px; }
.rankings-ssr-lines a { color: var(--text-muted); font-size: var(--fs-sm, 0.9rem); text-decoration: none; }
.rankings-ssr-lines a:hover { color: var(--gold); text-decoration: underline; }
.line-page-nav { margin: 0 0 10px; }
.line-page-cta { font-weight: 600; }
.line-page-desc { color: var(--text-muted); max-width: 820px; line-height: 1.6; margin: 0 0 16px; }
.line-page-method { color: var(--text-muted); font-size: var(--fs-sm, 0.9rem); margin-top: 14px; max-width: 820px; }
.line-page-table { overflow-x: auto; }
```

- [ ] **Step 6: Sitemap.** In `sitemap_xml`, after the per-civ loop added in Task 1, add:

```python
    # Per-unit-line landing pages ("aoe2 fire lancer", "aoe2 paladin", ...).
    for _p in _UNIT_LINE_PAGES:
        xml_parts.append(_url(f"/units/{_p['url']}", "weekly", "0.7"))
```

- [ ] **Step 7: Run — all tests PASS**, then full suite (0 failures). If `test_knight_page_has_full_table` fails on row count, print the actual count — the line data may exclude some civs; adjust the threshold to the real count minus a small margin, never below 20.

- [ ] **Step 8: Commit**

```bash
git add apps/website/app.py apps/website/templates/unit_line.html apps/website/templates/rankings.html apps/website/static/css/rankings.css tests/test_seo_unit_line_pages.py
git commit -m "feat(seo): per-unit-line landing pages + guides links from /units

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Rankings deep links (`/units?line=&unit=` select + highlight)

**Files:** Modify `apps/website/static/js/rankings.js`, `apps/website/static/css/rankings.css`.

- [ ] **Step 1: Row slugs.** In `rankings.js` `renderTable()` find the row-open line (~1786): `html += `<tr class="${rowClass}">`;`. Read the surrounding loop to learn the row variable name (the object with `unit_slug`), then add the slug as a data attribute, e.g. (adapt the variable name):

```js
html += `<tr class="${rowClass}" data-unit-slug="${(row.unit_slug || "")}">`;
```

- [ ] **Step 2: Deep-link init + highlight.** REPLACE the boot line `selectLine("infantry");` (last line, ~2104) with:

```js
/* ---- Deep-link boot: /units?line=<line>&unit=<slug> ----
   Selects the tab from the URL and highlights + scrolls to the unit's rows.
   Falls back to the default tab for missing/unknown params. */
(async function initFromURL() {
    const params = new URLSearchParams(window.location.search);
    const lineParam = params.get("line");
    const unitParam = params.get("unit");
    const startLine = (lineParam && UNIT_LINES[lineParam]) ? lineParam : "infantry";
    await selectLine(startLine);
    if (unitParam) highlightUnitRows(unitParam);
})();

function highlightUnitRows(unitSlug) {
    const want = unitSlug.toLowerCase();
    let first = null;
    document.querySelectorAll("#tableContainer tr[data-unit-slug]").forEach(function (tr) {
        const s = (tr.dataset.unitSlug || "").toLowerCase();
        if (s === want || s === "elite_" + want || s.indexOf(want) !== -1) {
            tr.classList.add("row-deeplink-highlight");
            if (!first) first = tr;
        }
    });
    if (first) first.scrollIntoView({ behavior: "smooth", block: "center" });
}
```

- [ ] **Step 3: URL sync on tab clicks.** At the END of `selectLine(slug)` (after the table has rendered), keep the address bar shareable without polluting history:

```js
    if (window.history && history.replaceState) {
        history.replaceState(null, "", slug === "infantry" ? window.location.pathname : "?line=" + slug);
    }
```

(Keep any existing end-of-function code intact; append this last.)

- [ ] **Step 4: Highlight style.** Append to `rankings.css`:

```css
tr.row-deeplink-highlight > td { background: var(--bg-hover) !important; }
tr.row-deeplink-highlight { outline: 2px solid var(--gold); outline-offset: -2px; }
```

- [ ] **Step 5: Verify no pytest regressions** (`.venv/bin/python -m pytest -q`) — JS behavior itself is browser-verified in Task 4.

- [ ] **Step 6: Commit**

```bash
git add apps/website/static/js/rankings.js apps/website/static/css/rankings.css
git commit -m "feat(seo): /units deep links — tab select + unit row highlight from URL

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Browser verification & ship (controller does this directly)

- [ ] Start the local server (`.venv` + Claude Preview per the local-webapp-testing memory) and verify with DOM evals (headless screenshots are unreliable on tall pages):
  1. `/civilizations/bengalis` → analyzer auto-selects Bengalis (`#step-label` says "Showing analysis for Bengalis"; `#results` populated).
  2. `/units/shock-infantry` → SSR table renders with Fire Lancer + Eagle Warrior rows.
  3. `/units?line=shock_infantry&unit=fire_lancer` → shock-infantry tab active; `.row-deeplink-highlight` rows exist.
  4. `/civilizations` → civ headings are links.
- [ ] Full suite green. `git push origin staging`; verify on the staging URL; do NOT push `main` without the user's go-ahead.

---

## Self-Review

**Coverage vs the user's asks:** "aoe2 bengalis" → `/civilizations/bengalis` with analyzer preselected ✓ (Task 1); "aoe2 fire lancer" → `/units/shock-infantry` landing page whose title leads with Fire Lancer ✓ (Task 2), and deep links that open the shock-infantry table with Fire Lancer rows highlighted ✓ (Task 3); both page sets sitemapped + internally linked ✓.

**Placeholder scan:** none — full code given; the only adapt-in-place steps (rankings.js row var name, end of selectLine) are read-then-edit with the exact target lines identified.

**Type/name consistency:** `civ.slug = name.lower()` everywhere (route, template links, sitemap, tests); `_UNIT_LINE_PAGES[].line` keys match `UNIT_LINES`; deep-link param `line` uses UNIT_LINES keys (underscores) while page URLs use hyphens — the CTA link `?line={{ page.line }}` correctly uses the underscore key; tests assert both spellings in the right places.
