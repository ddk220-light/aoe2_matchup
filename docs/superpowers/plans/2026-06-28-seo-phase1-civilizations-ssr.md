# SEO Phase 1 — Civilizations SSR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server-render all 53 civilizations — name, the auto-generated strategic description, and power units grouped by role — as crawlable HTML on `/civilizations`, so crawlers and JS-less AI sources can read every civ's identity and key units. The interactive click-to-analyze selector is untouched.

**Architecture:** Add a `get_civ_overview_data()` helper that shapes the existing `load_civ_power_units()` data for server rendering (same data source as `/api/civ-power-units`, so SSR and API never diverge). The `/civilizations` route passes it to the template, which renders an always-present, crawlable "all civs" `<section id="civ-ssr">`. An inline `<script>` hides that section the instant it parses, so JS users see only the existing interactive UI (zero changes to `matchup.js`); crawlers and no-JS visitors get the full content. Add `ItemList` JSON-LD listing all civs.

**Tech Stack:** Flask, Jinja2, pytest (`client` fixture in `tests/conftest.py`). Data: `data/golden/civ_power_units/<build>.json` (current build `177723`, 53 civs), read via `load_civ_power_units` (`aoe2x/advisor/best_units.py`).

**Key design decisions (from the Phase-1 investigation):**
- **No net-new content corpus.** The spec floated authoring a `civ_identity.json`. Unnecessary — `civ_power_units/<build>.json` already contains a per-civ `strategic_description` (a real narrative: strengths, what to build, vulnerabilities). That IS the identity text. The spec's `civ_identity.json` task is dropped.
- **Hydration = "visible SSR, hide-on-parse."** The SSR section renders visible by default (so JS-less crawlers see it); an inline script immediately after it sets `hidden = true` (runs only in JS browsers, before paint → no flash, no UX change). This avoids touching the interactive render path (`matchup.js` is not modified). It is NOT cloaking: identical HTML is served to everyone; JS in the user's browser hides a redundant section.
- **Streamlined semantic SSR, not full badge fidelity.** Crawlers need the civ name, description, and power-unit names grouped by role — not the interactive tooltips/sprites. The SSR is a clean semantic subset; the interactive UI remains the rich human view.

**Test command (exact interpreter — bare `python`/`pytest` are the wrong env):**
`.venv/bin/python -m pytest tests/test_seo_phase1.py -v` (run from repo root). "Replay Analyzer disabled (no mgz)" on import is expected/harmless.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/app.py` | Modify | Add `_CIV_ROLE_LABELS` + `get_civ_overview_data()`; pass it from the `/civilizations` route. |
| `apps/website/templates/civ_overview.html` | Modify | Render the `#civ-ssr` crawlable section + inline hide script + `ItemList` JSON-LD. |
| `apps/website/static/css/matchup.css` | Modify | Minimal readable styling for the SSR section (only seen by no-JS visitors). |
| `tests/test_seo_phase1.py` | Create | Phase 1 regression tests. |

---

## Task 1: `get_civ_overview_data()` helper

A pure data-shaping function: turn `load_civ_power_units()` output into a server-render-friendly list. Same data source as the API route, so no logic divergence.

**Files:**
- Modify: `apps/website/app.py` (add near `_get_ref_civs`, ~line 1440)
- Test: `tests/test_seo_phase1.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seo_phase1.py
def test_get_civ_overview_data_shape(client):
    import app
    data = app.get_civ_overview_data()
    # One entry per civ in the reference DB.
    civs = app._get_ref_civs()
    assert len(data) == len(civs)
    assert [c["name"] for c in data] == civs  # same order (alphabetical)
    # Every entry has the SSR fields.
    for c in data:
        assert set(c.keys()) == {"name", "slug", "description", "roles"}
        assert c["slug"] == c["name"].lower()
        assert isinstance(c["roles"], list)
    # At least one civ has a non-empty description and at least one unit.
    rich = [c for c in data if c["description"] and c["roles"]]
    assert rich, "expected some civ with description + roles"
    unit = rich[0]["roles"][0]["units"][0]
    assert set(unit.keys()) == {"name", "slug", "tier", "is_unique"}
    assert unit["name"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_seo_phase1.py::test_get_civ_overview_data_shape -v`
Expected: FAIL with `AttributeError: module 'app' has no attribute 'get_civ_overview_data'`

- [ ] **Step 3: Implement the helper**

In `apps/website/app.py`, add immediately above `def _get_ref_civs():`:

```python
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
```

(`load_civ_power_units` and `current_build` are already imported in `app.py` — verify with a grep before assuming, do not add imports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_seo_phase1.py::test_get_civ_overview_data_shape -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py tests/test_seo_phase1.py
git commit -m "feat(seo): add get_civ_overview_data helper for civ SSR

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Render the crawlable civ section (+ wire route, hide-on-parse, CSS)

**Files:**
- Modify: `apps/website/app.py` (the `/civilizations` route, ~line 569)
- Modify: `apps/website/templates/civ_overview.html`
- Modify: `apps/website/static/css/matchup.css`
- Test (APPEND): `tests/test_seo_phase1.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_seo_phase1.py`:

```python
def test_civ_overview_ssr_renders_all_civs(client):
    import app
    civs = app._get_ref_civs()
    body = client.get("/civilizations").data.decode()
    for civ in civs:
        assert civ in body, f"{civ} missing from civ SSR"
    assert 'id="civ-ssr"' in body


def test_civ_overview_ssr_has_descriptions_and_units(client):
    import app
    data = app.get_civ_overview_data()
    body = client.get("/civilizations").data.decode()
    # At least one strategic description rendered (they begin "This civ ...").
    assert "This civ" in body
    # A power-unit name renders as crawlable text.
    sample = next(c for c in data if c["roles"])
    assert sample["roles"][0]["units"][0]["name"] in body


def test_civ_overview_ssr_hidden_for_js(client):
    # The inline hide-on-parse script must be present so JS users don't see it.
    body = client.get("/civilizations").data.decode()
    assert "getElementById('civ-ssr')" in body
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_seo_phase1.py -k ssr -v`
Expected: FAIL (no `#civ-ssr` section yet).

- [ ] **Step 3a: Pass the data from the route.** In `apps/website/app.py`, change the `/civilizations` route to:

```python
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
```

- [ ] **Step 3b: Render the section.** In `apps/website/templates/civ_overview.html`, replace the closing of the content block. Find:

```html
    <div id="results" class="results-container"></div>
</div>
{% endblock %}
```

and replace with:

```html
    <div id="results" class="results-container"></div>

    {# Server-rendered, crawlable fallback: every civ's identity + power units.
       Hidden the instant it parses for JS users (the interactive selector above
       is the rich view); remains for crawlers and no-JS visitors. Same data as
       /api/civ-power-units via get_civ_overview_data(). #}
    <section id="civ-ssr" class="civ-ssr" aria-label="All civilizations">
        <h2 class="civ-ssr-title">All {{ civ_overview | length }} civilizations at a glance</h2>
        {% for civ in civ_overview %}
        <article class="civ-ssr-civ" id="civ-{{ civ.slug }}">
            <h3>{{ civ.name }}</h3>
            {% if civ.description %}<p class="civ-ssr-desc">{{ civ.description }}</p>{% endif %}
            {% for role in civ.roles %}
            <p class="civ-ssr-role"><span class="civ-ssr-role-label">{{ role.label }}:</span>
                {% for unit in role.units %}{{ unit.name }}{% if unit.tier %} ({{ unit.tier }}){% endif %}{% if not loop.last %}, {% endif %}{% endfor %}
            </p>
            {% endfor %}
        </article>
        {% endfor %}
    </section>
    <script>var _ssr = document.getElementById('civ-ssr'); if (_ssr) _ssr.hidden = true;</script>
</div>
{% endblock %}
```

- [ ] **Step 3c: Minimal CSS.** Append to `apps/website/static/css/matchup.css`:

```css
/* Server-rendered civ fallback — hidden for JS users (see civ_overview.html).
   Styled lightly so no-JS visitors still get a readable page. */
.civ-ssr {
    max-width: var(--container-max);
    margin: 0 auto;
    padding: 8px var(--gutter) 48px;
}
.civ-ssr-title {
    font-family: var(--font-display);
    color: var(--gold);
    font-size: var(--fs-lg);
    letter-spacing: 0.04em;
    margin: 0 0 18px;
}
.civ-ssr-civ {
    border-top: 1px solid var(--border);
    padding: 16px 0;
}
.civ-ssr-civ h3 {
    color: var(--gold);
    font-size: var(--fs-md);
    margin: 0 0 6px;
}
.civ-ssr-desc {
    color: var(--text-muted);
    font-size: var(--fs-sm);
    margin: 0 0 8px;
    line-height: var(--lh-base);
}
.civ-ssr-role {
    font-size: var(--fs-sm);
    margin: 2px 0;
}
.civ-ssr-role-label {
    color: var(--gold);
    font-weight: 600;
    margin-right: 4px;
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_seo_phase1.py -v`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py apps/website/templates/civ_overview.html apps/website/static/css/matchup.css tests/test_seo_phase1.py
git commit -m "feat(seo): server-render all 53 civs (identity + power units) on /civilizations

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `ItemList` JSON-LD for the civ list

**Files:**
- Modify: `apps/website/templates/civ_overview.html`
- Test (APPEND): `tests/test_seo_phase1.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_civ_overview_itemlist_jsonld(client):
    import app
    n = len(app._get_ref_civs())
    body = client.get("/civilizations").data.decode()
    assert '"@type": "ItemList"' in body
    assert f'"numberOfItems": {n}' in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_seo_phase1.py::test_civ_overview_itemlist_jsonld -v`
Expected: FAIL (no ItemList yet).

- [ ] **Step 3: Add the JSON-LD.** In `apps/website/templates/civ_overview.html`, immediately AFTER the `{% block content %}` line (before the `<div class="page-header">`), add:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Age of Empires II civilizations",
  "numberOfItems": {{ civ_overview | length }},
  "itemListElement": [
    {% for civ in civ_overview %}{ "@type": "ListItem", "position": {{ loop.index }}, "name": "{{ civ.name }}", "url": "{{ site_url }}/civilizations#civ-{{ civ.slug }}" }{% if not loop.last %},{% endif %}
    {% endfor %}
  ]
}
</script>
```

(`site_url` is a global from the `inject_site_url` context processor; `civ_overview` is passed by the route in Task 2.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_seo_phase1.py::test_civ_overview_itemlist_jsonld -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/website/templates/civ_overview.html tests/test_seo_phase1.py
git commit -m "feat(seo): add ItemList JSON-LD to /civilizations

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Verification & ship to staging

**Files:** none (verification only)

- [ ] **Step 1: Full suite.** Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all prior tests (Phase 0 included) plus the new Phase 1 tests; no regressions. The existing `/api/civ-power-units/<civ>` JSON is unchanged (the route was not modified), confirming SSR and API share the data source without divergence.

- [ ] **Step 2: Render + interactivity smoke test.** Start the server (`launch.json` config `aoe2-flask` via the preview tool, or `PORT=5002 .venv/bin/python apps/website/app.py`). Then:
  - Load `/civilizations` with **JavaScript disabled** (or `curl`): confirm all 53 civ names + descriptions + power-unit names are in the raw HTML inside `#civ-ssr`.
  - Load `/civilizations` with JS **enabled**: confirm `#civ-ssr` is hidden (not visible), the interactive civ grid still works, and clicking a civ still loads its analysis. No duplicated/doubled content, no console errors.

- [ ] **Step 3: Confirm branch + push.**

```bash
git status            # on staging, Phase 1 commits in, no stray files staged
git log --oneline -6
git push origin staging
```

Then ask the user to verify on the staging URL. **Do not** push to `main`.

---

## Self-Review

**Spec coverage (Phase 2 "Civilizations SSR" slice of the design spec):**
- Server-render all 53 civs (name, power units, identity) → Tasks 1–2 ✓
- Progressive enhancement, interactive UI preserved → hide-on-parse, `matchup.js` untouched ✓
- `ItemList` JSON-LD → Task 3 ✓
- Single shared data source (SSR ↔ API) → `get_civ_overview_data` wraps `load_civ_power_units`, the same loader the API uses ✓
- Civ identity text → resolved to the existing `strategic_description` (no `civ_identity.json` authored) ✓

**Placeholder scan:** none — every step has exact code, paths, and commands.

**Type/name consistency:** `get_civ_overview_data()` returns dicts with keys `{name, slug, description, roles}`; each role `{label, units}`; each unit `{name, slug, tier, is_unique}`. The template iterates exactly these (`civ.name`, `civ.slug`, `civ.description`, `civ.roles`, `role.label`, `role.units`, `unit.name`, `unit.tier`). Tests assert the same key sets. The route passes `civ_overview=get_civ_overview_data()`; template and JSON-LD both read `civ_overview`. The hide script targets `id="civ-ssr"`, which the section defines and the test asserts.
