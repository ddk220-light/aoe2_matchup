# SEO Phase 5 — Homepage Flagship Content + /about Methodology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the site a crawlable "what this whole thing is and how it works" layer: a new `/about` methodology page (linked site-wide from the footer) and a flagship descriptive section on the homepage (today just the battle-sim canvas + one `<h1>`, no prose). This is the authoritative explanation an AI quotes when asked "how does aoe2matchup calculate this / where does the data come from".

**Architecture:** Pure additive content — a new `/about` route + `about.html` template, a server-rendered section appended to the homepage (`simulate.html`) content block, a footer link, a sitemap entry, and `AboutPage`/`FAQPage` JSON-LD. No data flow, no JS changes, no interactive behavior touched.

**Tech Stack:** Flask, Jinja2, pytest. No DB.

**Content is factual (from the codebase/CLAUDE.md):** extracts unit data from the AoE2:DE binary `.dat`; computes fully-upgraded Imperial-age stats for all 53 civilizations (every unique unit + Three Kingdoms), applying all blacksmith/university/unique-tech upgrades and civ bonuses; pre-simulates ~500k unit matchups with a deterministic tick-by-tick model (armor classes, attack reload/delays, projectile travel & accuracy, charge attacks, trample, bleed, healing); scores come from a 30-vs-30 population fight (30v30) and a 3,000-resource cost-parity fight (3k), with "Average" blending the two; data is re-derived on each game patch (tracked in the Patch Tracker). Fan project, not affiliated with Microsoft.

**Test command:** `.venv/bin/python -m pytest tests/test_seo_phase5.py -v` (from repo root).

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/website/app.py` | Modify | Add `/about` route; add `/about` to the sitemap hub list. |
| `apps/website/templates/about.html` | Create | The methodology page (content + `AboutPage`/`FAQPage` JSON-LD). |
| `apps/website/templates/simulate.html` | Modify | Append a flagship "About this site" section to the homepage content block. |
| `apps/website/templates/_footer.html` | Modify | Add a "How it works" → `/about` footer link. |
| `tests/test_seo_phase5.py` | Create | Phase 5 tests. |

---

## Task 1: `/about` methodology page

**Files:**
- Modify: `apps/website/app.py` (add route near the other simple page routes; add `/about` to `sitemap_xml` hub list)
- Create: `apps/website/templates/about.html`
- Modify: `apps/website/templates/_footer.html`
- Test: `tests/test_seo_phase5.py`

- [ ] **Step 1: Write the failing tests.** Create `tests/test_seo_phase5.py`:

```python
# tests/test_seo_phase5.py
def test_about_page_renders(client):
    resp = client.get("/about")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "How AoE2 Matchup works" in body
    assert ".dat" in body            # data source explained
    assert "30v30" in body and "3k" in body  # scoring explained
    assert "53 civilizations" in body


def test_about_jsonld(client):
    body = client.get("/about").data.decode()
    assert '"@type": "AboutPage"' in body or '"@type": "FAQPage"' in body


def test_about_in_footer(client):
    body = client.get("/").data.decode()
    assert 'href="/about"' in body


def test_about_in_sitemap(client):
    body = client.get("/sitemap.xml").data.decode()
    assert "/about</loc>" in body
```

- [ ] **Step 2: Run — FAIL** (no `/about`).

- [ ] **Step 3a: Add the route.** In `apps/website/app.py`, add near `home()` (~line 569):

```python
@app.route("/about")
def about():
    """Methodology / how-it-works page — the authoritative explanation of the data
    and simulation behind the site."""
    return render_template("about.html", active_nav=None)
```

- [ ] **Step 3b: Add `/about` to the sitemap.** In `sitemap_xml`, add to the `hub` list (after `/matchups`):

```python
        ("/about", "monthly", "0.5"),
```

- [ ] **Step 3c: Create the template** `apps/website/templates/about.html`:

```html
{% extends "base.html" %}

{% block title %}How AoE2 Matchup works — data &amp; simulation methodology{% endblock %}
{% block meta_description %}How AoE2 Matchup works: unit data extracted from the Age of Empires II:DE game files, fully-upgraded stats for all 53 civilizations, and ~500,000 simulated battles deciding every matchup.{% endblock %}

{% block page_css %}
<style>
.about-page { max-width: 820px; margin: 0 auto; padding: 8px var(--gutter) 64px; }
.about-page h2 { font-family: var(--font-display); color: var(--gold); font-size: var(--fs-lg); margin: 32px 0 10px; }
.about-page p, .about-page li { color: var(--text); font-size: var(--fs-base); line-height: var(--lh-base); }
.about-page p { margin: 0 0 12px; max-width: 760px; }
.about-page ul { margin: 0 0 16px; padding-left: 20px; }
.about-page a { color: var(--gold); }
.about-faq dt { font-weight: 600; color: var(--gold); margin-top: 16px; }
.about-faq dd { margin: 4px 0 0; color: var(--text-muted); }
</style>
{% endblock %}

{% block structured_data %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "AboutPage",
  "name": "How AoE2 Matchup works",
  "url": "{{ site_url }}/about",
  "description": "Methodology behind AoE2 Matchup: data extracted from the Age of Empires II:DE game files, fully-upgraded stats for all 53 civilizations, and ~500,000 simulated battles."
}
</script>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    { "@type": "Question", "name": "Where does the data come from?",
      "acceptedAnswer": { "@type": "Answer", "text": "Unit stats are extracted directly from the Age of Empires II: Definitive Edition game files (the .dat), then fully upgraded for each of the 53 civilizations using every blacksmith, university and unique-tech upgrade plus that civ's bonuses." } },
    { "@type": "Question", "name": "How is the winner of a matchup decided?",
      "acceptedAnswer": { "@type": "Answer", "text": "A deterministic, tick-by-tick battle simulation models armor classes, attack delays, projectile travel time and accuracy, charge attacks, trample, bleed and healing. About 500,000 matchups are pre-simulated." } },
    { "@type": "Question", "name": "What do the 30v30 and 3k scores mean?",
      "acceptedAnswer": { "@type": "Answer", "text": "30v30 is an equal-population fight (30 units a side); 3k is an equal-resources, cost-parity fight (3,000 resources a side). The Average score blends both, so it rewards raw strength and cost-efficiency together." } },
    { "@type": "Question", "name": "Is this an official Microsoft site?",
      "acceptedAnswer": { "@type": "Answer", "text": "No. AoE2 Matchup is a free fan-made tool and is not affiliated with or endorsed by Microsoft, Forgotten Empires, or World's Edge." } }
  ]
}
</script>
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>How AoE2 Matchup works</h1>
    <p class="subtitle">The data and the simulation behind every stat, score, and matchup.</p>
</div>

<article class="about-page">
    <p>
        <strong>AoE2 Matchup</strong> is a free, fan-made analysis suite for
        <em>Age of Empires II: Definitive Edition</em>. It turns the game's own data into
        battle simulations, unit rankings, and civilization breakdowns you can explore.
    </p>

    <h2>Where the data comes from</h2>
    <p>
        Every unit's stats are extracted directly from the game's binary data file
        (the <code>.dat</code>) — the same source the game itself reads. We then compute
        <strong>fully-upgraded Imperial-age stats</strong> for all <strong>53 civilizations</strong>
        (including every unique unit and the Three Kingdoms civs), applying all the blacksmith,
        university and unique-technology upgrades a civilization can reach, plus its civ bonuses.
        So the numbers you see are what a unit actually looks like late-game for that civ — not the base stat card.
    </p>

    <h2>How a matchup is decided</h2>
    <p>
        Who wins isn't guessed from a formula — it's <strong>simulated</strong>. A deterministic,
        tick-by-tick model fights the units against each other, accounting for armor classes,
        attack reload and delays, projectile travel time and accuracy, charge attacks, trample,
        bleed, healing, and the other special mechanics in the game. Roughly
        <strong>500,000 unit matchups</strong> are pre-simulated so the rankings and matchup pages load instantly.
    </p>

    <h2>What the scores mean</h2>
    <p>Each unit is scored from two kinds of fight, because they test different things:</p>
    <ul>
        <li><strong>30v30 (population)</strong> — 30 units a side. This rewards raw, per-unit strength at the population cap.</li>
        <li><strong>3k (cost-parity)</strong> — 3,000 resources a side. This rewards cost-efficiency: cheap units field bigger armies.</li>
        <li><strong>Average</strong> — blends the two, so a unit has to be both strong and cost-effective to top the list. Higher is better.</li>
    </ul>

    <h2>The tools</h2>
    <ul>
        <li><a href="/">Battle Simulator</a> — pit any units from any civs against each other and watch the fight.</li>
        <li><a href="/units">Unit Rankings</a> — every unit scored and ranked across all civs.</li>
        <li><a href="/civilizations">Civilizations</a> — each civ's strategic identity and strongest units.</li>
        <li><a href="/matchup-advisor">Matchup Advisor</a> — what to build against a given civ.</li>
        <li><a href="/matchups">Unit Matchups</a> — head-to-head pages for every unique-unit pairing.</li>
        <li><a href="/patches">Patch Tracker</a> — how each balance update changed the numbers.</li>
        <li><a href="/replay">Replay Analyzer</a> — watch and share recorded games on an isometric map.</li>
    </ul>

    <h2>Keeping current</h2>
    <p>
        When Age of Empires II ships a balance patch, the stats and simulations are re-derived and the
        <a href="/patches">Patch Tracker</a> shows exactly which units and matchups moved.
    </p>

    <h2>Frequently asked</h2>
    <dl class="about-faq">
        <dt>Is this an official Microsoft site?</dt>
        <dd>No — it's a free fan project, not affiliated with or endorsed by Microsoft, Forgotten Empires, or World's Edge.</dd>
        <dt>Why might a result differ from my own game?</dt>
        <dd>Simulations assume fully-upgraded Imperial-age units fighting head-on; real games add micro, terrain, and tech timing the sim doesn't model.</dd>
    </dl>
</article>
{% endblock %}
```

- [ ] **Step 3d: Footer link.** In `apps/website/templates/_footer.html`, add to the Explore column `<ul>` (after "Unit Matchups"):

```html
                <li><a href="/about">How it works</a></li>
```

- [ ] **Step 4: Run — all 4 PASS.** Then full suite. Verify both JSON-LD blocks parse.

- [ ] **Step 5: Commit**

```bash
git add apps/website/app.py apps/website/templates/about.html apps/website/templates/_footer.html tests/test_seo_phase5.py
git commit -m "feat(seo): add /about methodology page + footer link + sitemap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Homepage flagship section

Add a server-rendered descriptive section to the homepage (below the battle-sim UI) so `/` has real crawlable content beyond the canvas, with links into every tool and to `/about`.

**Files:**
- Modify: `apps/website/templates/simulate.html` (append inside the content block, before its final `{% endblock %}`)
- Modify: `apps/website/static/css/simulate.css` (append styles)
- Test (APPEND): `tests/test_seo_phase5.py`

- [ ] **Step 1: Append the failing test**

```python
def test_homepage_has_flagship_content(client):
    body = client.get("/").data.decode()
    assert 'id="home-about"' in body
    # describes the site + links to the methodology and tools
    assert "53 civ" in body.lower()
    assert 'href="/about"' in body
    assert 'href="/units"' in body and 'href="/civilizations"' in body
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3a: Add the section.** In `apps/website/templates/simulate.html`, find the END of the `{% block content %}` (the final `</div>` immediately before `{% endblock %}` at ~line 147). Insert this section right before that closing `{% endblock %}` (after the last content `</div>`):

```html
<section id="home-about" class="home-about" aria-label="About AoE2 Matchup">
    <div class="home-about-inner">
        <h2>Every Age of Empires II matchup, simulated</h2>
        <p>
            AoE2 Matchup pits any units from any of the <strong>53 civilizations</strong> against each other in a
            deterministic, tick-by-tick battle simulation — fully upgraded to the Imperial age, with armor classes,
            projectiles, charges and every special mechanic accounted for. Around <strong>500,000 matchups</strong> are
            pre-simulated, so you can see who actually wins, not just compare stat cards.
            <a href="/about">How it works →</a>
        </p>
        <ul class="home-about-tools">
            <li><a href="/units"><strong>Unit Rankings</strong><span>Every unit scored across all civs</span></a></li>
            <li><a href="/civilizations"><strong>Civilizations</strong><span>Each civ's strengths &amp; best units</span></a></li>
            <li><a href="/matchup-advisor"><strong>Matchup Advisor</strong><span>What to build against any civ</span></a></li>
            <li><a href="/matchups"><strong>Unit Matchups</strong><span>Head-to-head for every unique unit</span></a></li>
            <li><a href="/patches"><strong>Patch Tracker</strong><span>What each balance update changed</span></a></li>
            <li><a href="/replay"><strong>Replay Analyzer</strong><span>Watch &amp; share recorded games</span></a></li>
        </ul>
    </div>
</section>
```

(If `simulate.html`'s content block doesn't end with a clean single `</div>`, just ensure this `<section>` is the LAST element inside `{% block content %}`.)

- [ ] **Step 3b: Append CSS** to `apps/website/static/css/simulate.css`:

```css
/* Homepage flagship "about" section — crawlable site description + tool links. */
.home-about { border-top: 1px solid var(--border); margin-top: 32px; padding: 32px var(--gutter) 8px; }
.home-about-inner { max-width: var(--container-max); margin: 0 auto; }
.home-about h2 { font-family: var(--font-display); color: var(--gold); font-size: var(--fs-lg); margin: 0 0 12px; letter-spacing: 0.03em; }
.home-about p { color: var(--text-muted); font-size: var(--fs-base); line-height: var(--lh-base); max-width: 820px; margin: 0 0 20px; }
.home-about p a { color: var(--gold); white-space: nowrap; }
.home-about-tools { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
.home-about-tools a { display: block; padding: 12px 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--bg-warm); color: var(--text); text-decoration: none; transition: border-color 0.15s ease, background 0.15s ease; }
.home-about-tools a:hover { border-color: var(--gold); background: var(--bg-hover); }
.home-about-tools strong { display: block; color: var(--gold); font-size: var(--fs-md); margin-bottom: 2px; }
.home-about-tools span { color: var(--text-muted); font-size: var(--fs-sm); }
```

(Confirm `simulate.html` links `simulate.css` via its `page_css` block — it does; the section's CSS lives there.)

- [ ] **Step 4: Run — PASS.** Then full suite. Browser smoke (preview): homepage battle sim still works (canvas + controls), the flagship section renders below it, no console errors. Screenshot.

- [ ] **Step 5: Commit**

```bash
git add apps/website/templates/simulate.html apps/website/static/css/simulate.css tests/test_seo_phase5.py
git commit -m "feat(seo): add flagship description + tool links to the homepage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Verification & ship

- [ ] **Step 1:** Full suite green. Both `/about` JSON-LD blocks parse.
- [ ] **Step 2:** Browser smoke (preview `aoe2-flask`): `/about` renders the full methodology; `/` shows the battle sim AND the flagship section + tool links; footer "How it works" link present on every page; `/sitemap.xml` lists `/about`; `/simulate` still 301s to `/`. Screenshot `/about` and the homepage section.
- [ ] **Step 3:** `git push origin staging`; ask user to verify on staging. Do NOT push `main`.

---

## Self-Review

**Spec coverage (Phase 7 homepage + methodology):** `/about` methodology page ✓; homepage flagship content + tool links ✓; footer link site-wide ✓; sitemap ✓; `AboutPage` + `FAQPage` JSON-LD ✓.

**Placeholder scan:** none — full page copy and CSS are provided verbatim.

**Type/name consistency:** new route `about()` → `about.html`; tests assert `/about` 200, the methodology strings, `AboutPage`/`FAQPage`, footer + sitemap presence, and the homepage `#home-about` section with `/about` + tool links. All copy is static (no data interpolation → no JSON-LD escaping risk).
