# Site Footer + Rename to "AoE2 Matchup" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a four-column site footer with sources, social links, and a Formspree-backed contact modal to every page; rename the user-visible site name from "AoE2 Unit Analyzer" / "AoE2 Analyzer" to "AoE2 Matchup".

**Architecture:** A new Jinja partial `webapp/templates/_footer.html` is included by `base.html` so the footer renders on all 6 templates. A new `@app.context_processor` in `webapp/app.py` exposes the Formspree endpoint and three social-profile URLs (Discord, YouTube, Instagram) from environment variables, so unset vars hide the corresponding links cleanly. The contact form posts to Formspree via async `fetch` — no new backend route. Footer + modal CSS appends to the existing `webapp/static/css/base.css` and uses existing theme CSS variables.

**Tech Stack:** Flask + Jinja2 templates, vanilla JS (no new dependencies), Formspree (third-party form endpoint), pytest with the existing `client` fixture in `tests/conftest.py`.

**Spec:** [docs/superpowers/specs/2026-05-01-site-footer-and-rename-design.md](../specs/2026-05-01-site-footer-and-rename-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `webapp/app.py` | Modify | Add `inject_footer_config()` context processor reading 4 env vars |
| `webapp/templates/base.html` | Modify | Rename strings, add `sameAs` JSON-LD, define social-link Jinja vars, include footer partial |
| `webapp/templates/_footer.html` | **Create** | Footer markup + contact modal markup + modal JS |
| `webapp/templates/deprecated-civ.html` | Modify | Replace "AoE2 Analyzer" string |
| `webapp/static/css/base.css` | Modify | Append `.site-footer` and `.contact-modal` CSS |
| `tests/test_footer.py` | **Create** | Smoke tests for context processor, rename, footer rendering, sameAs JSON-LD |
| `README.md` | Modify | Document the 4 new env vars |

---

## Task 1: Footer-config context processor

Add a context processor that reads four env vars and exposes them to all templates. Unset vars resolve to `None` so templates can hide the corresponding link.

**Files:**
- Modify: `webapp/app.py:29-32` (insert new context processor right after `inject_site_url`)
- Create: `tests/test_footer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_footer.py`:

```python
import importlib
import os

import pytest


@pytest.fixture
def reload_app(monkeypatch):
    """Reload webapp.app with a clean env so context processors re-read env vars."""
    def _reload(env_overrides):
        for k, v in env_overrides.items():
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        import app as flask_app
        importlib.reload(flask_app)
        flask_app.app.config["TESTING"] = True
        return flask_app

    return _reload


def test_footer_config_all_set(reload_app):
    flask_app = reload_app({
        "CONTACT_FORM_ENDPOINT": "https://formspree.io/f/abc123",
        "SOCIAL_DISCORD_URL": "https://discord.gg/example",
        "SOCIAL_YOUTUBE_URL": "https://youtube.com/@example",
        "SOCIAL_INSTAGRAM_URL": "https://instagram.com/example",
    })
    with flask_app.app.test_request_context("/"):
        ctx = {}
        for processor in flask_app.app.template_context_processors[None]:
            ctx.update(processor())
        assert ctx["contact_form_endpoint"] == "https://formspree.io/f/abc123"
        assert ctx["social_links"] == {
            "discord": "https://discord.gg/example",
            "youtube": "https://youtube.com/@example",
            "instagram": "https://instagram.com/example",
        }


def test_footer_config_all_unset(reload_app):
    flask_app = reload_app({
        "CONTACT_FORM_ENDPOINT": None,
        "SOCIAL_DISCORD_URL": None,
        "SOCIAL_YOUTUBE_URL": None,
        "SOCIAL_INSTAGRAM_URL": None,
    })
    with flask_app.app.test_request_context("/"):
        ctx = {}
        for processor in flask_app.app.template_context_processors[None]:
            ctx.update(processor())
        assert ctx["contact_form_endpoint"] is None
        assert ctx["social_links"] == {
            "discord": None,
            "youtube": None,
            "instagram": None,
        }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_footer.py -v`
Expected: FAIL — `KeyError: 'contact_form_endpoint'` or similar (the keys don't exist yet).

- [ ] **Step 3: Implement the context processor**

In `webapp/app.py`, immediately after the existing `inject_site_url` function (currently lines 29–32), add:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_footer.py -v`
Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```bash
git add webapp/app.py tests/test_footer.py
git commit -m "feat(footer): add context processor for footer config env vars"
```

---

## Task 2: Rename to "AoE2 Matchup"

Replace the 6 hardcoded user-visible strings (`AoE2 Unit Analyzer` / `AoE2 Analyzer`) across `base.html` and `deprecated-civ.html`. Per-page `{% block title %}` overrides in other templates already use neutral phrasing ("AoE2 Battle Simulator", "AoE2 Civilizations", etc.) so they need no change.

**Files:**
- Modify: `webapp/templates/base.html` (5 strings)
- Modify: `webapp/templates/deprecated-civ.html` (1 string)
- Modify: `tests/test_footer.py` (add rename smoke test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_footer.py`:

```python
def test_home_page_uses_new_site_name(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "AoE2 Matchup" in body
    # Old name must not appear anywhere in the rendered HTML
    assert "AoE2 Unit Analyzer" not in body
    assert "AoE2 Analyzer" not in body


def test_og_site_name_is_renamed(client):
    resp = client.get("/")
    body = resp.data.decode()
    assert '<meta property="og:site_name" content="AoE2 Matchup"' in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_footer.py::test_home_page_uses_new_site_name tests/test_footer.py::test_og_site_name_is_renamed -v`
Expected: FAIL — old strings still present.

- [ ] **Step 3: Apply the rename in `base.html`**

Edit `webapp/templates/base.html`:

- Line 6 — change
  ```html
  <title>{% block title %}AoE2 Unit Analyzer — Simulate any matchup, fully upgraded{% endblock %}</title>
  ```
  to
  ```html
  <title>{% block title %}AoE2 Matchup — Simulate any matchup, fully upgraded{% endblock %}</title>
  ```

- Line 12 — change
  ```html
  <meta property="og:site_name" content="AoE2 Unit Analyzer" />
  ```
  to
  ```html
  <meta property="og:site_name" content="AoE2 Matchup" />
  ```

- Line 29 — inside the JSON-LD `<script>`, change
  ```json
  "name": "AoE2 Unit Analyzer",
  ```
  to
  ```json
  "name": "AoE2 Matchup",
  ```

- Line 30 — inside the JSON-LD `<script>`, change
  ```json
  "description": "Age of Empires II battle simulator and unit matchup database covering all 50 civilizations with fully-upgraded stats.",
  ```
  Leave the description string alone — it doesn't reference the site name.

- Line 56 — inside `.nav-brand`, change
  ```html
              AoE2 Analyzer
  ```
  to
  ```html
              AoE2 Matchup
  ```

- [ ] **Step 4: Apply the rename in `deprecated-civ.html`**

Edit `webapp/templates/deprecated-civ.html` line 3 — change
```html
{% block title %}{{ civ_name }} — Unit stats, civ bonuses & best matchups | AoE2 Analyzer{% endblock %}
```
to
```html
{% block title %}{{ civ_name }} — Unit stats, civ bonuses & best matchups | AoE2 Matchup{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_footer.py -v`
Expected: PASS for all four tests.

- [ ] **Step 6: Verify nothing else still uses the old names**

Run: `grep -rn "AoE2 Unit Analyzer\|AoE2 Analyzer" webapp/templates/ webapp/app.py`
Expected: no output (zero matches).

- [ ] **Step 7: Commit**

```bash
git add webapp/templates/base.html webapp/templates/deprecated-civ.html tests/test_footer.py
git commit -m "feat(rename): rename site to AoE2 Matchup across templates"
```

---

## Task 3: Add `sameAs` JSON-LD array

Extend the `WebApplication` JSON-LD block in `base.html` so search engines see the linked Discord/YouTube/Instagram profiles as belonging to the same entity. Driven by the `social_links` context var so it stays in sync with the footer's Connect column.

**Files:**
- Modify: `webapp/templates/base.html` lines 23–37 (the `{% block structured_data %}` block)
- Modify: `tests/test_footer.py` (add JSON-LD test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_footer.py`:

```python
def test_jsonld_includes_sameas_when_social_urls_set(monkeypatch):
    monkeypatch.setenv("SOCIAL_DISCORD_URL",   "https://discord.gg/example")
    monkeypatch.setenv("SOCIAL_YOUTUBE_URL",   "https://youtube.com/@example")
    monkeypatch.setenv("SOCIAL_INSTAGRAM_URL", "https://instagram.com/example")
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert '"sameAs"' in body
    assert "https://discord.gg/example" in body
    assert "https://youtube.com/@example" in body
    assert "https://instagram.com/example" in body


def test_jsonld_omits_sameas_when_no_social_urls(monkeypatch):
    monkeypatch.delenv("SOCIAL_DISCORD_URL",   raising=False)
    monkeypatch.delenv("SOCIAL_YOUTUBE_URL",   raising=False)
    monkeypatch.delenv("SOCIAL_INSTAGRAM_URL", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    # When all social URLs are unset, the sameAs key should not appear.
    assert '"sameAs"' not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_footer.py::test_jsonld_includes_sameas_when_social_urls_set tests/test_footer.py::test_jsonld_omits_sameas_when_no_social_urls -v`
Expected: First test FAILs (`"sameAs"` not in body); second test passes incidentally.

- [ ] **Step 3: Update the JSON-LD block in `base.html`**

Replace the `{% block structured_data %}` section in `webapp/templates/base.html` (currently lines 24–37) with:

```html
    {% block structured_data %}
    {% set _social_urls = (social_links.values() | reject('none') | list) if social_links is defined else [] %}
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      "name": "AoE2 Matchup",
      "description": "Age of Empires II battle simulator and unit matchup database covering all 50 civilizations with fully-upgraded stats.",
      "applicationCategory": "GameApplication",
      "operatingSystem": "Web",
      "url": "{{ site_url }}",
      "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" }{% if _social_urls %},
      "sameAs": [{% for u in _social_urls %}"{{ u }}"{% if not loop.last %}, {% endif %}{% endfor %}]{% endif %}
    }
    </script>
    {% endblock %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_footer.py -v`
Expected: PASS for all 6 tests.

- [ ] **Step 5: Smoke-test in the browser**

Run: `PORT=5002 python3 webapp/app.py` (in another terminal)
Open http://localhost:5002, View Source, confirm:
- `<title>AoE2 Matchup — ...</title>`
- `og:site_name` is `AoE2 Matchup`
- JSON-LD `name` is `"AoE2 Matchup"`
- JSON-LD has no `sameAs` (env vars unset locally)

Stop the server (Ctrl-C).

- [ ] **Step 6: Commit**

```bash
git add webapp/templates/base.html tests/test_footer.py
git commit -m "feat(seo): add sameAs JSON-LD driven by social-link context"
```

---

## Task 4: Footer partial + footer CSS

Create the four-column footer partial, include it from `base.html`, and append matching CSS to `base.css`. The contact button is included as a placeholder `<button>` with `data-action="open-contact-modal"` — its modal is wired up in Task 5.

**Files:**
- Create: `webapp/templates/_footer.html`
- Modify: `webapp/templates/base.html` (include the partial)
- Modify: `webapp/static/css/base.css` (append footer styles)
- Modify: `tests/test_footer.py` (rendering smoke tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_footer.py`:

```python
def test_footer_renders_on_home_page(client):
    body = client.get("/").data.decode()
    assert '<footer class="site-footer"' in body
    # Brand column
    assert "AoE2 Matchup" in body
    # Explore column has the four nav links
    for href in ["/", "/matchup-advisor", "/units", "/civilizations"]:
        assert f'href="{href}"' in body
    # Sources column
    assert "aoe2techtree.net" in body
    assert "genieutils" in body.lower()
    assert "ageofempires.fandom.com" in body
    # Microsoft disclaimer
    assert "not affiliated" in body.lower()
    assert "Microsoft" in body


def test_footer_hides_contact_button_when_endpoint_unset(client, monkeypatch):
    monkeypatch.delenv("CONTACT_FORM_ENDPOINT", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert 'data-action="open-contact-modal"' not in body


def test_footer_hides_social_link_when_url_unset(client, monkeypatch):
    monkeypatch.delenv("SOCIAL_DISCORD_URL",   raising=False)
    monkeypatch.setenv("SOCIAL_YOUTUBE_URL",   "https://youtube.com/@example")
    monkeypatch.delenv("SOCIAL_INSTAGRAM_URL", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert "youtube.com/@example" in body
    # No discord or instagram link rendered
    assert "discord.gg" not in body
    assert "instagram.com" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_footer.py -v`
Expected: FAIL on the new three tests — `<footer class="site-footer"` not in body.

- [ ] **Step 3: Create `webapp/templates/_footer.html`**

Create the file with this content:

```html
{# AoE2 Matchup site footer. Included by base.html on every page. #}
<footer class="site-footer" role="contentinfo">
    <div class="site-footer-inner">

        {# Column 1 — Brand #}
        <div class="site-footer-col site-footer-brand">
            <div class="site-footer-brand-row">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
                </svg>
                <span class="site-footer-brand-name">AoE2 Matchup</span>
            </div>
            <p class="site-footer-tagline">
                Free fan tool for Age of Empires II:DE matchup analysis.
                All 50 civs, fully upgraded.
            </p>
        </div>

        {# Column 2 — Explore #}
        <nav class="site-footer-col" aria-label="Explore">
            <h3 class="site-footer-heading">Explore</h3>
            <ul class="site-footer-list">
                <li><a href="/">Battle Sim</a></li>
                <li><a href="/matchup-advisor">Matchup Advisor</a></li>
                <li><a href="/units">Rankings</a></li>
                <li><a href="/civilizations">Civilizations</a></li>
            </ul>
        </nav>

        {# Column 3 — Sources #}
        <nav class="site-footer-col" aria-label="Sources">
            <h3 class="site-footer-heading">Sources</h3>
            <ul class="site-footer-list">
                <li>
                    <a href="https://github.com/Tapsa/genieutils" target="_blank" rel="nofollow noopener">
                        genieutils-py <span aria-hidden="true">↗</span>
                    </a>
                </li>
                <li>
                    <a href="https://aoe2techtree.net" target="_blank" rel="nofollow noopener">
                        aoe2techtree.net <span aria-hidden="true">↗</span>
                    </a>
                </li>
                <li>
                    <a href="https://ageofempires.fandom.com/wiki/Age_of_Empires_Series_Wiki" target="_blank" rel="nofollow noopener">
                        AoE2 Wiki <span aria-hidden="true">↗</span>
                    </a>
                </li>
            </ul>
        </nav>

        {# Column 4 — Connect #}
        <div class="site-footer-col" aria-label="Connect">
            <h3 class="site-footer-heading">Connect</h3>
            <ul class="site-footer-list site-footer-social">
                {% if social_links.discord %}
                <li><a href="{{ social_links.discord }}" target="_blank" rel="noopener" aria-label="AoE2 Matchup on Discord">
                    <svg class="site-footer-social-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M20.317 4.369A19.79 19.79 0 0016.558 3.2a.077.077 0 00-.082.038c-.357.638-.755 1.47-1.034 2.124a18.27 18.27 0 00-5.482 0 12.51 12.51 0 00-1.05-2.124.08.08 0 00-.082-.038A19.74 19.74 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.056 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028 14.27 14.27 0 001.226-1.994.076.076 0 00-.041-.105 13.1 13.1 0 01-1.872-.892.077.077 0 01-.008-.128c.126-.094.252-.192.372-.291a.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.009c.12.099.246.198.373.292a.077.077 0 01-.006.127 12.3 12.3 0 01-1.873.892.077.077 0 00-.04.106c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.84 19.84 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.029zM8.02 15.331c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
                    Discord <span aria-hidden="true">↗</span>
                </a></li>
                {% endif %}
                {% if social_links.youtube %}
                <li><a href="{{ social_links.youtube }}" target="_blank" rel="me noopener" aria-label="AoE2 Matchup on YouTube">
                    <svg class="site-footer-social-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.016 3.016 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.016 3.016 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                    YouTube <span aria-hidden="true">↗</span>
                </a></li>
                {% endif %}
                {% if social_links.instagram %}
                <li><a href="{{ social_links.instagram }}" target="_blank" rel="noopener" aria-label="AoE2 Matchup on Instagram">
                    <svg class="site-footer-social-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>
                    Instagram <span aria-hidden="true">↗</span>
                </a></li>
                {% endif %}
                {% if contact_form_endpoint %}
                <li><button type="button" class="site-footer-contact-btn" data-action="open-contact-modal">
                    Contact
                </button></li>
                {% endif %}
            </ul>
        </div>
    </div>

    <div class="site-footer-legal">
        <span>© 2026 AoE2 Matchup</span>
        <span class="site-footer-disclaimer">
            Age of Empires II is a trademark of Microsoft Corporation. This site is not
            affiliated with or endorsed by Microsoft, Forgotten Empires, or World's Edge.
        </span>
    </div>
</footer>
```

- [ ] **Step 4: Include the partial in `base.html`**

In `webapp/templates/base.html`, find the line `{% block content %}{% endblock %}` (line 88) and insert immediately after it (still inside `<body>`, before the trailing `<script>` blocks):

```html
    {% block content %}{% endblock %}

    {% include '_footer.html' %}

    <script src="{{ url_for('static', filename='js/constants.js') }}"></script>
```

- [ ] **Step 5: Append footer CSS to `webapp/static/css/base.css`**

Append at the end of the file:

```css
/* ============================================================
   Site footer
   ============================================================ */
.site-footer {
    margin-top: 4rem;
    padding: 2.5rem 1.5rem 1.25rem;
    background: linear-gradient(180deg, var(--bg) 0%, var(--bg-deep) 100%);
    border-top: 2px solid var(--border);
    color: var(--text-muted);
    font-family: 'Source Sans 3', sans-serif;
    font-size: 0.95rem;
    line-height: 1.5;
}
.site-footer-inner {
    max-width: 1280px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1.4fr 1fr 1fr 1fr;
    gap: 2rem;
    padding-bottom: 2rem;
}
.site-footer-col {
    min-width: 0;
}
.site-footer-brand-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    color: var(--text);
    margin-bottom: 0.75rem;
}
.site-footer-brand-name {
    font-family: 'Cinzel', serif;
    font-weight: 700;
    font-size: 1.15rem;
    letter-spacing: 0.02em;
}
.site-footer-tagline {
    color: var(--text-muted);
    margin: 0;
    max-width: 28ch;
}
.site-footer-heading {
    font-family: 'Cinzel', serif;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text);
    margin: 0 0 0.85rem;
}
.site-footer-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
}
.site-footer-list a,
.site-footer-contact-btn {
    color: var(--text-muted);
    text-decoration: none;
    background: none;
    border: 0;
    padding: 0;
    font: inherit;
    cursor: pointer;
    transition: color 0.15s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
}
.site-footer-list a:hover,
.site-footer-contact-btn:hover {
    color: var(--text);
}
.site-footer-social-icon {
    flex: 0 0 auto;
    opacity: 0.85;
}

.site-footer-legal {
    max-width: 1280px;
    margin: 0 auto;
    padding-top: 1.25rem;
    border-top: 1px solid var(--border);
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.75rem 2rem;
    font-size: 0.82rem;
    color: var(--text-dim);
}
.site-footer-disclaimer {
    max-width: 60ch;
}

@media (max-width: 640px) {
    .site-footer { padding: 2rem 1rem 1rem; margin-top: 2.5rem; }
    .site-footer-inner {
        grid-template-columns: 1fr;
        gap: 1.75rem;
        padding-bottom: 1.5rem;
    }
    .site-footer-legal {
        flex-direction: column;
        align-items: flex-start;
    }
    .site-footer-list a,
    .site-footer-contact-btn {
        min-height: 44px;
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_footer.py -v`
Expected: PASS for all 9 tests.

- [ ] **Step 7: Smoke-test in the browser**

Run in one terminal: `PORT=5002 python3 webapp/app.py`

In another terminal:
```bash
SOCIAL_DISCORD_URL=https://discord.gg/example \
SOCIAL_YOUTUBE_URL=https://youtube.com/@example \
SOCIAL_INSTAGRAM_URL=https://instagram.com/example \
CONTACT_FORM_ENDPOINT=https://formspree.io/f/test \
PORT=5002 python3 webapp/app.py
```

Open http://localhost:5002 and visually confirm:
- Footer appears at the bottom of every page (try `/`, `/matchup-advisor`, `/units`, `/civilizations`).
- Four columns visible on desktop; stacks to one column when window narrowed below ~640px.
- Toggle theme via the navbar button — footer recolors correctly in both light and dark.
- Discord/YouTube/Instagram/Contact all visible.

Stop the server.

- [ ] **Step 8: Commit**

```bash
git add webapp/templates/_footer.html webapp/templates/base.html webapp/static/css/base.css tests/test_footer.py
git commit -m "feat(footer): add four-column site footer with sources and social links"
```

---

## Task 5: Contact modal (markup, JS, and CSS)

Add the modal markup, focus-trap JS, and Formspree submit handler to the bottom of `_footer.html`. Append modal CSS to `base.css`. Modal is rendered only when `contact_form_endpoint` is set (so deploys without the env var skip it entirely).

**Files:**
- Modify: `webapp/templates/_footer.html` (append modal markup + script)
- Modify: `webapp/static/css/base.css` (append modal styles)
- Modify: `tests/test_footer.py` (modal markup test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_footer.py`:

```python
def test_contact_modal_renders_when_endpoint_set(client, monkeypatch):
    monkeypatch.setenv("CONTACT_FORM_ENDPOINT", "https://formspree.io/f/abc123")
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert 'class="contact-modal"' in body
    assert 'action="https://formspree.io/f/abc123"' in body
    # Honeypot field present
    assert 'name="_gotcha"' in body
    # Required fields
    assert 'name="email"' in body
    assert 'name="message"' in body


def test_contact_modal_absent_when_endpoint_unset(client, monkeypatch):
    monkeypatch.delenv("CONTACT_FORM_ENDPOINT", raising=False)
    import importlib, app as flask_app
    importlib.reload(flask_app)
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        body = c.get("/").data.decode()
    assert 'class="contact-modal"' not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_footer.py::test_contact_modal_renders_when_endpoint_set tests/test_footer.py::test_contact_modal_absent_when_endpoint_unset -v`
Expected: First test FAILs, second passes incidentally.

- [ ] **Step 3: Append modal markup + script to `_footer.html`**

At the **end** of `webapp/templates/_footer.html` (after the closing `</footer>`), append:

```html
{% if contact_form_endpoint %}
<div class="contact-modal" id="contactModal" role="dialog" aria-modal="true" aria-labelledby="contactModalTitle" hidden>
    <div class="contact-modal-backdrop" data-action="close-contact-modal"></div>
    <div class="contact-modal-panel" role="document">
        <button type="button" class="contact-modal-close" data-action="close-contact-modal" aria-label="Close">×</button>
        <h2 id="contactModalTitle" class="contact-modal-title">Contact</h2>
        <p class="contact-modal-intro">
            Question, bug report, or just want to say hi? Drop a note.
        </p>
        <form class="contact-modal-form" id="contactForm" action="{{ contact_form_endpoint }}" method="POST" novalidate>
            <label class="contact-modal-label">
                Name
                <input type="text" name="name" autocomplete="name" />
            </label>
            <label class="contact-modal-label">
                Email
                <input type="email" name="email" required autocomplete="email" />
            </label>
            <label class="contact-modal-label">
                Message
                <textarea name="message" rows="5" required minlength="10"></textarea>
            </label>
            <input type="text" name="_gotcha" tabindex="-1" autocomplete="off" style="position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden" aria-hidden="true" />
            <button type="submit" class="contact-modal-submit">Send</button>
            <div class="contact-modal-status" id="contactStatus" role="status" aria-live="polite"></div>
        </form>
    </div>
</div>

<script>
(function() {
    var modal       = document.getElementById('contactModal');
    var form        = document.getElementById('contactForm');
    var statusEl    = document.getElementById('contactStatus');
    var openBtn     = document.querySelector('[data-action="open-contact-modal"]');
    var closeEls    = modal.querySelectorAll('[data-action="close-contact-modal"]');
    var lastFocused = null;

    if (!openBtn) return;

    function trapFocusable() {
        return modal.querySelectorAll(
            'a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
    }
    function openModal() {
        lastFocused = document.activeElement;
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
        var focusable = trapFocusable();
        if (focusable.length) focusable[0].focus();
    }
    function closeModal() {
        modal.hidden = true;
        document.body.style.overflow = '';
        statusEl.textContent = '';
        statusEl.className   = 'contact-modal-status';
        form.style.display   = '';
        form.reset();
        if (lastFocused) lastFocused.focus();
    }
    function onKeydown(e) {
        if (modal.hidden) return;
        if (e.key === 'Escape') { e.preventDefault(); closeModal(); return; }
        if (e.key === 'Tab') {
            var focusable = Array.prototype.slice.call(trapFocusable());
            if (!focusable.length) return;
            var first = focusable[0], last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
    }

    openBtn.addEventListener('click', openModal);
    closeEls.forEach(function(el) { el.addEventListener('click', closeModal); });
    document.addEventListener('keydown', onKeydown);

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled  = true;
        submitBtn.textContent = 'Sending...';
        statusEl.textContent = '';
        statusEl.className   = 'contact-modal-status';

        fetch(form.action, {
            method:  'POST',
            body:    new FormData(form),
            headers: { 'Accept': 'application/json' }
        }).then(function(resp) {
            if (resp.ok) {
                form.style.display = 'none';
                statusEl.textContent = "Thanks! I'll get back to you soon.";
                statusEl.className   = 'contact-modal-status is-success';
            } else {
                throw new Error('Bad status: ' + resp.status);
            }
        }).catch(function() {
            statusEl.textContent = 'Something went wrong. Please try again later.';
            statusEl.className   = 'contact-modal-status is-error';
        }).finally(function() {
            submitBtn.disabled    = false;
            submitBtn.textContent = 'Send';
        });
    });
})();
</script>
{% endif %}
```

- [ ] **Step 4: Append modal CSS to `webapp/static/css/base.css`**

Append at the end of the file (after the footer styles from Task 4):

```css
/* ============================================================
   Contact modal
   ============================================================ */
.contact-modal[hidden] {
    display: none;
}
.contact-modal {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
}
.contact-modal-backdrop {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(2px);
}
.contact-modal-panel {
    position: relative;
    width: 100%;
    max-width: 480px;
    background: var(--bg-warm);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 1.75rem 1.5rem 1.5rem;
    color: var(--text);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
    font-family: 'Source Sans 3', sans-serif;
    max-height: calc(100vh - 2rem);
    overflow-y: auto;
}
.contact-modal-close {
    position: absolute;
    top: 0.5rem;
    right: 0.6rem;
    background: none;
    border: 0;
    color: var(--text-muted);
    font-size: 1.6rem;
    line-height: 1;
    width: 2rem;
    height: 2rem;
    cursor: pointer;
    border-radius: 50%;
}
.contact-modal-close:hover {
    color: var(--text);
    background: var(--bg-hover);
}
.contact-modal-title {
    font-family: 'Cinzel', serif;
    font-size: 1.4rem;
    margin: 0 0 0.4rem;
}
.contact-modal-intro {
    color: var(--text-muted);
    margin: 0 0 1.25rem;
    font-size: 0.95rem;
}
.contact-modal-form {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
}
.contact-modal-label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.85rem;
    color: var(--text-muted);
}
.contact-modal-label input,
.contact-modal-label textarea {
    background: var(--bg-deep);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.55rem 0.7rem;
    color: var(--text);
    font: inherit;
    font-size: 0.95rem;
    resize: vertical;
}
.contact-modal-label input:focus,
.contact-modal-label textarea:focus {
    outline: 2px solid var(--border-light);
    outline-offset: 1px;
}
.contact-modal-submit {
    margin-top: 0.5rem;
    background: var(--text);
    color: var(--bg-deep);
    border: 0;
    border-radius: 6px;
    padding: 0.65rem 1rem;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s ease;
}
.contact-modal-submit:hover { opacity: 0.9; }
.contact-modal-submit:disabled { opacity: 0.6; cursor: not-allowed; }
.contact-modal-status {
    font-size: 0.9rem;
    min-height: 1.2em;
}
.contact-modal-status.is-success { color: #6fbe6f; }
.contact-modal-status.is-error   { color: #d97a7a; }

@media (max-width: 640px) {
    .contact-modal-panel { padding: 1.5rem 1.1rem 1.25rem; }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_footer.py -v`
Expected: PASS for all 11 tests.

- [ ] **Step 6: Smoke-test the modal in a browser**

Run with all env vars set:
```bash
CONTACT_FORM_ENDPOINT=https://formspree.io/f/test \
SOCIAL_DISCORD_URL=https://discord.gg/example \
SOCIAL_YOUTUBE_URL=https://youtube.com/@example \
SOCIAL_INSTAGRAM_URL=https://instagram.com/example \
PORT=5002 python3 webapp/app.py
```

Open http://localhost:5002 and verify:
- Click footer "Contact" → modal opens centered, backdrop dims page.
- `Esc` key closes the modal.
- Click on the dim backdrop closes it.
- Click the × button closes it.
- Tab cycles only within the modal (focus trap).
- Submit empty form → browser native required-field error on email/message.
- Fill in form → submit → submit button disables and says "Sending..." → since the endpoint is fake, error message appears: "Something went wrong. Please try again later."
- Re-open modal → form is reset.
- Toggle light theme → modal recolors correctly.

Stop the server.

- [ ] **Step 7: Commit**

```bash
git add webapp/templates/_footer.html webapp/static/css/base.css tests/test_footer.py
git commit -m "feat(footer): add Formspree-backed contact modal with focus trap"
```

---

## Task 6: Document the new env vars in README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find the right spot in README**

Run: `grep -n "SITE_URL\|env var\|environment" README.md`
Pick the section that documents env vars (or the deploy/Railway section if none exists). If no env-var section exists, add a new `## Environment variables` section near the bottom, before any "License" or footer-style content.

- [ ] **Step 2: Add the env var documentation**

Add (or extend) a section that reads:

```markdown
## Environment variables

| Variable | Purpose | If unset |
|---|---|---|
| `SITE_URL` | Public origin for canonical / OG / sitemap URLs | Defaults to `https://aoe2matchup.com` |
| `CONTACT_FORM_ENDPOINT` | Formspree endpoint URL (e.g. `https://formspree.io/f/xxxx`) — backs the footer Contact modal | Contact button + modal are hidden |
| `SOCIAL_DISCORD_URL` | Public Discord invite shown in footer + JSON-LD `sameAs` | Discord link is hidden |
| `SOCIAL_YOUTUBE_URL` | YouTube channel URL shown in footer + JSON-LD `sameAs` | YouTube link is hidden |
| `SOCIAL_INSTAGRAM_URL` | Instagram profile URL shown in footer + JSON-LD `sameAs` | Instagram link is hidden |

For Railway: set these in the project's Variables tab. For local dev: prepend to the `python3 webapp/app.py` command, or use a `.env` loader of your choice.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): document contact form and social link env vars"
```

---

## Final verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest`
Expected: all tests pass, including the new `tests/test_footer.py`.

- [ ] **Step 2: Confirm no leftover old name**

Run: `grep -rn "AoE2 Unit Analyzer\|AoE2 Analyzer" webapp/ docs/superpowers/specs/ 2>/dev/null | grep -v "\.git"`
Expected: only references inside the spec doc itself (which describes the rename) — no live template / code matches.

- [ ] **Step 3: Visual smoke test on each page**

Start the dev server with all env vars set, then open each page and confirm the footer renders and the modal opens:
- http://localhost:5002/ (home)
- http://localhost:5002/matchup-advisor
- http://localhost:5002/units
- http://localhost:5002/civilizations
- http://localhost:5002/civ/franks (a civ_detail page)

Toggle light/dark theme on each, resize to mobile width on at least one.

- [ ] **Step 4: Push to staging**

```bash
git push origin staging
```

Ask the user to set the four new env vars in the Railway **staging** environment, then verify the staging URL renders the footer correctly. Do NOT promote to `main` until the user has confirmed staging looks right.

---

## Self-review notes

- **Spec coverage:** every section of the spec is covered. Section 1 (scope/rename) → Task 2. Section 2 (layout) → Tasks 4. Section 3 (modal) → Task 5. Section 4 (SEO `sameAs` + `rel` attributes + `aria-label`) → Tasks 3, 4, 5. Section 5 (files touched) → all tasks. Section "Configuration" (env vars + behavior when unset) → Tasks 1, 4, 5, 6.
- **Placeholders:** every template, CSS, JS, and Python code block is fully populated. The genieutils-py URL `https://github.com/Tapsa/genieutils` is the most plausible upstream; the user can correct it during implementation if it's a different fork — that's an explicit "open question" in the spec, not a blocker.
- **Type/name consistency:** `social_links` keys (`discord`/`youtube`/`instagram`) match between the context processor (Task 1), the template (Task 4), the JSON-LD `sameAs` driver (Task 3), and the tests. `contact_form_endpoint` likewise consistent. CSS class names (`.site-footer*`, `.contact-modal*`) used identically in markup and CSS.
- **Test fixture compatibility:** the existing `tests/conftest.py` `client` fixture creates a test client from the already-imported `app` module. The footer tests that need to vary env vars use `importlib.reload(app)` after `monkeypatch.setenv` to force the context processors to re-read the environment. The standalone `client` fixture is reused for tests that don't need env-var manipulation (rename smoke test, default footer rendering).
