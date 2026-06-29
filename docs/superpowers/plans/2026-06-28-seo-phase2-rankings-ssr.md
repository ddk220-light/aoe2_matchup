# SEO Phase 2 — Rankings SSR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a crawlable, user-facing "Rankings at a glance" section to `/units` — a plain-language explainer of what the scores mean plus a server-rendered top-units-per-category table — so crawlers/AI and humans get context around the "big table". The existing interactive rankings table is untouched.

**Architecture:** Factor the per-line data assembly out of the `/api/ref/unit-line/<slug>` route into a shared `get_unit_line_data(line_slug)` helper (the API becomes a thin wrapper — one logic path, no divergence). Add `get_rankings_overview_data()` that reuses it to compute each unit's default ("Average") score and return the top N per headline category. The `/units` route passes it to the template, which renders a visible "Rankings at a glance" reference below the interactive table. `matchup`-style progressive enhancement: `rankings.js` is not modified.

**Tech Stack:** Flask, Jinja2, pytest. Data via the existing `get_unit_line_data` path: `aoe2_reference.db` (ref_units) + `derived_data.db` (battle_scores) + `pool_scores.db` (pool_scores). Score field paths confirmed by investigation.

**Key design decision — "Rankings at a glance" reference, not a second full table.** The interactive table has per-line column variants, hover stat-chains, and scale toggles — re-rendering all that server-side would duplicate huge JS logic. Instead the SSR section is a compact, semantic *summary*: for each of the 5 headline categories (Infantry, Archers, Cavalry, Siege, Naval), the top 8 units by default "Average" score, as a small table (rank, civ, unit, score). This is what an AI needs to answer "best infantry unit in AoE2" and what a human wants at a glance — complementary to the interactive deep-dive, not a redundant clone. Plus a 2–3 sentence explainer of what the score means.

**Default score (confirmed from the API data shape):**
- Pool-scored lines (infantry/archery/stable): a unit's `pool_scores.scales["30v30"].hp.final` and `["3k"].hp.final` averaged — this is exactly the JS "Average" view.
- Siege line: `anti_building_score`. Naval line: `naval_effectiveness` (role scores attached by the existing `_attach_scores`).

**Test command:** `.venv/bin/python -m pytest tests/test_seo_phase2.py -v` (from repo root). "Replay Analyzer disabled (no mgz)" on import is expected/harmless.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/app.py` | Modify | Extract `get_unit_line_data(line_slug)` from `api_ref_unit_line`; add `_ranking_default_score`, `_RANKINGS_HEADLINE_LINES`, `get_rankings_overview_data()`; pass overview from `/units`. |
| `apps/website/templates/rankings.html` | Modify | Render the "Rankings at a glance" section + explainer + `ItemList` JSON-LD. |
| `apps/website/static/css/rankings.css` | Modify | Style the SSR section. |
| `tests/test_seo_phase2.py` | Create | Phase 2 tests. |

---

## Task 1: Extract `get_unit_line_data(line_slug)` (shared helper, API-parity)

Mechanical refactor: move the body of `api_ref_unit_line` into a reusable function; the route becomes a thin wrapper. No behavior change — pinned by an API-parity test.

**Files:**
- Modify: `apps/website/app.py` (`api_ref_unit_line`, ~lines 1121–1439)
- Test: `tests/test_seo_phase2.py`

- [ ] **Step 1: Write the API-parity test (captures current output as the contract)**

```python
# tests/test_seo_phase2.py
import json


def test_unit_line_api_parity(client):
    # The /api/ref/unit-line/<slug> JSON must be byte-identical before/after the
    # refactor. We assert the route still returns a well-formed payload with the
    # expected top-level keys for a representative line.
    resp = client.get("/api/ref/unit-line/infantry")
    assert resp.status_code == 200
    data = resp.get_json()
    assert set(["line_name", "building", "imperial"]).issubset(data.keys())
    assert isinstance(data["imperial"], list) and data["imperial"]
    # Unknown line still 404s.
    assert client.get("/api/ref/unit-line/not_a_line").status_code == 404


def test_get_unit_line_data_matches_api(client):
    import app
    api = client.get("/api/ref/unit-line/infantry").get_json()
    helper = app.get_unit_line_data("infantry")
    assert helper == api  # same object the route serializes
```

- [ ] **Step 2: Run — `test_get_unit_line_data_matches_api` FAILS** (`AttributeError: ... get_unit_line_data`); `test_unit_line_api_parity` PASSES (route already exists).

Run: `.venv/bin/python -m pytest tests/test_seo_phase2.py -v`

- [ ] **Step 3: Extract the helper.** In `apps/website/app.py`:
  1. Rename the existing function `def api_ref_unit_line(line_slug):` body into a new module-level function `def get_unit_line_data(line_slug):` that **returns the `result` dict** (the same dict currently passed to `jsonify`) for a known line, and returns `None` for an unknown line (replace the early `return jsonify({"error": "Unknown unit line"}), 404` with `return None`). Keep ALL the existing logic (ref_units query, `_attach_scores`, `_attach_special`, pool_scores attachment) unchanged — only the function name, the unknown-line return, and the final `return result` (instead of `return jsonify(result)`).
  2. Re-add the route as a thin wrapper directly above/below it:

```python
@app.route("/api/ref/unit-line/<line_slug>")
def api_ref_unit_line(line_slug):
    """Get comparison data for a unit line across all civs."""
    data = get_unit_line_data(line_slug)
    if data is None:
        return jsonify({"error": "Unknown unit line"}), 404
    return jsonify(data)
```

(The route keeps its `@app.route` decorator and name so `url_for`/tests are unaffected; `get_unit_line_data` is the un-decorated worker.)

- [ ] **Step 4: Run — both tests PASS.** Then run the FULL suite to confirm no endpoint regressed: `.venv/bin/python -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py tests/test_seo_phase2.py
git commit -m "refactor(seo): extract get_unit_line_data from the unit-line API route

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `get_rankings_overview_data()` helper

**Files:**
- Modify: `apps/website/app.py` (add after `get_unit_line_data`)
- Test (APPEND): `tests/test_seo_phase2.py`

- [ ] **Step 1: Write the failing test**

```python
def test_rankings_overview_shape(client):
    import app
    data = app.get_rankings_overview_data(top_n=8)
    labels = [g["label"] for g in data]
    assert labels == ["Infantry", "Archers & Gunpowder", "Cavalry", "Siege", "Naval"]
    for g in data:
        assert g["units"], f"{g['label']} has no ranked units"
        assert len(g["units"]) <= 8
        # sorted by score descending
        scores = [u["score"] for u in g["units"]]
        assert scores == sorted(scores, reverse=True)
        u = g["units"][0]
        assert set(u.keys()) == {"civ", "name", "slug", "score"}
        assert isinstance(u["score"], (int, float))
```

- [ ] **Step 2: Run — FAIL** (`AttributeError: ... get_rankings_overview_data`).

- [ ] **Step 3: Implement.** Add to `apps/website/app.py` after `get_unit_line_data`:

```python
# Headline categories for the server-rendered "Rankings at a glance" section.
_RANKINGS_HEADLINE_LINES = [
    ("infantry", "Infantry"),
    ("archery", "Archers & Gunpowder"),
    ("stable", "Cavalry"),
    ("siege", "Siege"),
    ("naval", "Naval"),
]
# Role-score keys to fall back on when a unit has no pool_scores (siege/naval).
_RANKING_FALLBACK_SCORE_KEYS = (
    "anti_building_score", "naval_effectiveness",
    "general_combat", "ranged_effectiveness", "stable_effectiveness",
)


def _ranking_default_score(unit):
    """A unit's default 'Average' score: mean of its 30v30 and 3k pool HP-scores,
    or a role score for siege/naval. Mirrors the interactive table's default view.
    Returns None if the unit has no usable score."""
    ps = unit.get("pool_scores")
    if ps:
        vals = []
        for scale in ("30v30", "3k"):
            v = ((ps.get("scales", {}) or {}).get(scale, {}) or {}).get("hp", {}) or {}
            f = v.get("final")
            if isinstance(f, (int, float)):
                vals.append(f)
        if vals:
            return sum(vals) / len(vals)
    for k in _RANKING_FALLBACK_SCORE_KEYS:
        v = unit.get(k)
        if isinstance(v, (int, float)) and v != -999:
            return v
    return None


def get_rankings_overview_data(top_n=8):
    """Top units per headline category by default 'Average' score, for SSR.
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
```

- [ ] **Step 4: Run — PASS.**

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py tests/test_seo_phase2.py
git commit -m "feat(seo): add get_rankings_overview_data (top units per category)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Render the "Rankings at a glance" section + explainer + JSON-LD

**Files:**
- Modify: `apps/website/app.py` (the `/units` route, ~line 562)
- Modify: `apps/website/templates/rankings.html`
- Modify: `apps/website/static/css/rankings.css`
- Test (APPEND): `tests/test_seo_phase2.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_rankings_ssr_renders(client):
    import app
    body = client.get("/units").data.decode()
    assert 'id="rankings-ssr"' in body
    # explainer text present
    assert "Average" in body and "30v30" in body
    # a top unit from the overview appears as crawlable text
    ov = app.get_rankings_overview_data()
    top = next(g["units"][0]["name"] for g in ov if g["units"])
    assert top in body


def test_rankings_ssr_itemlist_jsonld(client):
    body = client.get("/units").data.decode()
    assert '"@type": "ItemList"' in body
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3a: Pass data from the route.** In `apps/website/app.py`, change `def units():` to also pass the overview:

```python
@app.route("/units")
def units():
    units_by_age = get_units_by_age()
    ages = {k: v["name"] for k, v in AGES.items()}
    return render_template(
        "rankings.html",
        units_by_age=units_by_age, ages=ages,
        rankings_overview=get_rankings_overview_data(),
        active_nav="rankings",
    )
```

- [ ] **Step 3b: Render the section.** In `apps/website/templates/rankings.html`, find the closing of the content block (after `<div class="table-container" id="tableContainer"></div>` and its wrapper `</div>`) and add, before `{% endblock %}` of the content block:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Age of Empires II top units by category",
  "itemListElement": [
    {% set ns = namespace(pos=0) %}
    {% for group in rankings_overview %}{% for u in group.units %}{% set ns.pos = ns.pos + 1 %}{{ "," if ns.pos > 1 else "" }}
    { "@type": "ListItem", "position": {{ ns.pos }}, "name": "{{ u.name }} ({{ u.civ }})" }{% endfor %}{% endfor %}
  ]
}
</script>

<section id="rankings-ssr" class="rankings-ssr" aria-label="Rankings at a glance">
    <h2 class="rankings-ssr-title">Rankings at a glance</h2>
    <p class="rankings-ssr-intro">
        Every unit is scored from thousands of simulated battles at full upgrades.
        The <strong>Average</strong> score blends two scenarios: a 30-vs-30 population fight
        (<em>30v30</em>) and a 3,000-resource cost-parity fight (<em>3k</em>). Higher is stronger.
        Below are the top units in each category; use the interactive table above to explore every line, civ, and matchup.
    </p>
    {% for group in rankings_overview %}
    <div class="rankings-ssr-group">
        <h3>Best {{ group.label }}</h3>
        <table class="rankings-ssr-table">
            <thead><tr><th>#</th><th>Unit</th><th>Civilization</th><th>Score</th></tr></thead>
            <tbody>
                {% for u in group.units %}
                <tr><td>{{ loop.index }}</td><td>{{ u.name }}</td><td>{{ u.civ }}</td><td>{{ u.score }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endfor %}
</section>
```

- [ ] **Step 3c: Append CSS** to `apps/website/static/css/rankings.css`:

```css
/* "Rankings at a glance" — visible, crawlable top-units-per-category summary. */
.rankings-ssr {
    max-width: var(--container-max);
    margin: 40px auto 0;
    padding: 28px var(--gutter) 56px;
    border-top: 1px solid var(--border);
}
.rankings-ssr-title {
    font-family: var(--font-display);
    color: var(--gold);
    font-size: var(--fs-lg);
    letter-spacing: 0.04em;
    margin: 0 0 8px;
}
.rankings-ssr-intro {
    color: var(--text-muted);
    font-size: var(--fs-sm);
    line-height: var(--lh-base);
    max-width: 760px;
    margin: 0 0 24px;
}
.rankings-ssr-group { margin-bottom: 28px; }
.rankings-ssr-group h3 {
    color: var(--gold);
    font-size: var(--fs-md);
    margin: 0 0 8px;
}
.rankings-ssr-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-sm);
}
.rankings-ssr-table th,
.rankings-ssr-table td {
    text-align: left;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
}
.rankings-ssr-table th {
    color: var(--text-muted);
    font-weight: 600;
}
.rankings-ssr-table td:last-child,
.rankings-ssr-table th:last-child { text-align: right; }
```

- [ ] **Step 4: Run — PASS.** Then full suite: `.venv/bin/python -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py apps/website/templates/rankings.html apps/website/static/css/rankings.css tests/test_seo_phase2.py
git commit -m "feat(seo): server-render 'Rankings at a glance' top-units summary on /units

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Verification & ship

- [ ] **Step 1:** Full suite green (`.venv/bin/python -m pytest -q`). Confirm the unit-line API is unchanged (Task 1 parity tests pass).
- [ ] **Step 2:** Browser smoke test (preview `aoe2-flask`): `/units` interactive table + toggles still work; the "Rankings at a glance" section renders below with the 5 category tables; `curl /units` shows the top unit names + explainer in raw HTML; no console errors. Screenshot.
- [ ] **Step 3:** `git push origin staging`; ask user to verify on staging. Do NOT push `main`.

---

## Self-Review

**Spec coverage (Phase 3 Rankings SSR):** server-rendered default ranked content ✓ (Task 3); explainer "what the score means / how to read it" ✓ (intro copy); `ItemList` JSON-LD ✓; shared data path (SSR ↔ API both via `get_unit_line_data`) ✓ (Task 1).

**Placeholder scan:** Task 1 is a described mechanical extraction of existing code (not new code to invent) pinned by an API-parity test; all other steps have exact code.

**Type/name consistency:** `get_unit_line_data(line_slug)` returns the dict (or `None`); `api_ref_unit_line` wraps it. `get_rankings_overview_data()` returns `[{line_slug,label,units:[{civ,name,slug,score}]}]`; the template iterates exactly those; tests assert the same keys. `_ranking_default_score` reads `pool_scores.scales[scale].hp.final` — the path confirmed in the API data shape.
