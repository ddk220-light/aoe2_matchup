# SEO Phase 6 — Curated Popular Matchups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Capture high-traffic generic matchup searches ("knight vs pikeman", "archer vs skirmisher", …) with a CURATED set of ~22 standard-unit `/vs/` pages, surfaced via a "Popular matchups" section on the `/matchups` hub (keyword-rich anchor text) and the sitemap. Deliberately small to avoid thin/doorway-page risk.

**Architecture:** A hand-curated `_POPULAR_MATCHUPS` list (each: a search-friendly label + two verified `(civ, unit_slug)` pairs that reach the canonical fully-upgraded unit). The existing `/vs/` route already renders these pairs — no route change. The `/matchups` hub gets a "Popular matchups" section at the top linking them with the search-term label as anchor text; the sitemap lists them at a higher priority than the long-tail unique pairs.

**Why this is safe (not doorway pages):** only ~22 pages, each a *real* fully-upgraded unit matchup with distinct stats, linked with descriptive anchor text. No auto-generated near-duplicates.

**Data is verified:** every `(civ, slug)` below was confirmed against `ref_units` to resolve to the canonical full-upgrade name (Franks→Paladin, Bulgarians→Halberdier, Britons→Arbalester, Mayans→Elite Skirmisher, Aztecs→Champion/Elite Eagle Warrior, Berbers/Saracens→Heavy Camel Rider, Turks→Hand Cannoneer, Tatars→Heavy Cavalry Archer, Byzantines→Hussar, Celts→Siege Onager, Bengalis→Heavy Scorpion, Teutons→Champion/Halberdier).

**Test command:** `.venv/bin/python -m pytest tests/test_seo_phase6.py -v` (from repo root).

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/app.py` | Modify | Add `_POPULAR_MATCHUPS`; pass to `matchups_hub`; add to `sitemap_xml`. |
| `apps/website/templates/matchups.html` | Modify | Render the "Popular matchups" section at the top. |
| `tests/test_seo_phase6.py` | Create | Phase 6 tests (incl. all-pairs-resolve-200). |

---

## Task 1: Curated data + hub section + sitemap

**Files:**
- Modify: `apps/website/app.py`, `apps/website/templates/matchups.html`
- Test: `tests/test_seo_phase6.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_seo_phase6.py`:

```python
# tests/test_seo_phase6.py
def test_popular_matchups_all_resolve(client):
    import app
    for m in app._POPULAR_MATCHUPS:
        (ca, ua), (cb, ub) = m["a"], m["b"]
        url = f"/vs/{ca}/{ua}/{cb}/{ub}"
        assert client.get(url).status_code == 200, f"{m['label']} -> {url} did not 200"


def test_popular_matchups_on_hub(client):
    body = client.get("/matchups").data.decode()
    assert "Popular matchups" in body
    assert "Knight vs Pikeman" in body          # a label as anchor text
    assert "/vs/Franks/paladin/Bulgarians/halberdier" in body


def test_popular_matchups_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/vs/Franks/paladin/Bulgarians/halberdier</loc>" in body
```

- [ ] **Step 2: Run — FAIL** (`AttributeError: ... _POPULAR_MATCHUPS`).

- [ ] **Step 3a: Add the curated data.** In `apps/website/app.py`, add near `_matchup_seed_pairs` (~line 616):

```python
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
```

- [ ] **Step 3b: Pass to the hub.** In the `matchups_hub` route, add `popular=_popular_matchup_links()` to the `render_template("matchups.html", ...)` call (keep the existing `groups` and `active_nav` args).

- [ ] **Step 3c: Render the hub section.** In `apps/website/templates/matchups.html`, immediately AFTER the `<div class="page-header">…</div>` block and BEFORE `<div class="container">`, add:

```html
{% if popular %}
<div class="container">
    <section class="popular-matchups">
        <h2>Popular matchups</h2>
        <ul class="popular-matchups-list">
            {% for label, url in popular %}
            <li><a href="{{ url }}">{{ label }}</a></li>
            {% endfor %}
        </ul>
    </section>
</div>
{% endif %}
```

And append to `apps/website/static/css/matchups.css`:

```css
.popular-matchups { margin: 0 0 28px; padding: 18px 20px; background: var(--bg-warm); border: 1px solid var(--border); border-radius: 12px; }
.popular-matchups h2 { font-family: var(--font-display); color: var(--gold); font-size: var(--fs-lg); margin: 0 0 12px; letter-spacing: 0.04em; }
.popular-matchups-list { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 4px 18px; }
.popular-matchups-list a { color: var(--text); text-decoration: none; font-size: var(--fs-sm); display: block; padding: 4px 6px; border-radius: 6px; }
.popular-matchups-list a:hover { color: var(--gold); background: var(--bg-hover); }
```

- [ ] **Step 3d: Sitemap.** In `sitemap_xml`, after the `hub` loop and BEFORE the `_matchup_seed_pairs()` loop, add the popular matchups at a higher priority:

```python
    for _label, _path in _popular_matchup_links():
        xml_parts.append(_url(_path, "monthly", "0.6"))
```

- [ ] **Step 4: Run — all 3 PASS** (the all-resolve test hits every curated URL → 200, catching any bad pair). Then full suite (0 failures).

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py apps/website/templates/matchups.html apps/website/static/css/matchups.css tests/test_seo_phase6.py
git commit -m "feat(seo): curated popular matchups on /matchups hub + sitemap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Verification & ship

- [ ] **Step 1:** Full suite green. The all-resolve test confirms every curated `/vs/` page returns 200.
- [ ] **Step 2:** Browser smoke (preview): `/matchups` shows the "Popular matchups" section at the top with the labels; clicking "Knight vs Pikeman" loads the Paladin-vs-Halberdier page; `/sitemap.xml` lists the curated URLs. Screenshot the hub section.
- [ ] **Step 3:** `git push origin staging`; ask user to verify. Do NOT push `main`.

---

## Self-Review

**Spec coverage (Phase 8 generic matchups, curated variant per user decision):** ~22 high-traffic standard matchups as real `/vs/` pages ✓; surfaced via hub "Popular matchups" with search-term anchor text ✓; sitemap ✓; bounded set (no doorway-page risk) ✓.

**Placeholder scan:** none — full verified data list + exact template/CSS provided.

**Type/name consistency:** `_POPULAR_MATCHUPS` entries are `{label, a:(civ,slug), b:(civ,slug)}`; `_popular_matchup_links()` returns `[(label, url)]`; the hub iterates `(label, url)`; tests assert `_POPULAR_MATCHUPS` resolves, the hub anchor text, and the sitemap loc. All `(civ, slug)` pairs verified against `ref_units`.
