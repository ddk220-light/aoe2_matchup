# Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the AoE2 Unit Analyzer webapp for visual consistency, better navigation, and clean code architecture — extracting all inline CSS/JS into external files, adding Jinja2 template inheritance, unifying the color palette and typography, and removing the review/comment system.

**Architecture:** Jinja2 `base.html` template provides shared `<head>`, nav bar (sticky, with dropdown), and footer. Each page extends it and defines `{% block page_css %}`, `{% block content %}`, and `{% block page_js %}`. All CSS goes to `static/css/`, all JS to `static/js/`. Shared constants (NAME_TO_ICON, UNIQUE_BUILDING, ENABLED_CIVS) move to `constants.js`.

**Tech Stack:** Flask/Jinja2, vanilla CSS/JS, Google Fonts (Cinzel, Alegreya Sans, JetBrains Mono)

**Design Doc:** `docs/plans/2026-02-15-frontend-redesign-design.md`

---

### Task 1: Remove review/comment system

Remove the review page, all comment API routes, and associated backend code from app.py. This is a clean deletion with no dependencies.

**Files:**
- Delete: `webapp/templates/review.html`
- Delete: `webapp/templates/home.html`
- Modify: `webapp/app.py` — lines 83-284 (comment system + review route), lines 14, 31-35 (APP_DB_PATH, get_app_db), line 71-73 (home route)

**Step 1: Delete review.html and home.html templates**

```bash
rm webapp/templates/review.html webapp/templates/home.html
```

**Step 2: Remove comment system from app.py**

Remove these sections from `webapp/app.py`:
- Line 14: `APP_DB_PATH = ...`
- Lines 31-35: `get_app_db()` function
- Lines 71-73: `home()` route (will be replaced later)
- Lines 83-284: Everything from `# ============== Comment System ==============` through the `delete_comment` function AND the `review_comments` route

Keep everything else intact. The file should go from the `get_ref_db()` function directly to the `civ_view()` route.

**Step 3: Verify the app still starts**

```bash
cd webapp && python3 -c "from app import app; print('OK')"
```

Expected: `OK` (no import errors)

**Step 4: Commit**

```bash
git add -A && git commit -m "chore: remove review/comment system and home landing page"
```

---

### Task 2: Create static file directory structure and base.css

Create the static/ directory structure and write `base.css` with the unified design system: CSS variables, reset, typography, navigation bar, card components, button styles, and modal base styles.

**Files:**
- Create: `webapp/static/css/base.css`
- Create: `webapp/static/js/constants.js` (empty placeholder)

**Step 1: Create directory structure**

```bash
mkdir -p webapp/static/css webapp/static/js
```

**Step 2: Write base.css**

Create `webapp/static/css/base.css` with these sections:

```css
/* ============================================
   AoE2 Unit Analyzer — Base Styles
   ============================================ */

/* --- CSS Variables --- */
:root {
    /* Primary: Aged Gold */
    --gold:            #c9a84c;
    --gold-light:      #dbb960;
    --gold-dark:       #8b6914;
    --gold-glow:       rgba(201, 168, 76, 0.15);

    /* Background: Dark Parchment */
    --bg-deep:         #120d07;
    --bg:              #1e1610;
    --bg-warm:         #2a1f14;
    --bg-hover:        #342618;

    /* Borders */
    --border:          #3d2e1e;
    --border-light:    #5a4228;

    /* Text */
    --text:            #e8dcc8;
    --text-muted:      #a89878;
    --text-dim:        #6d5d48;

    /* Accents */
    --red-accent:      #7a1a1a;
    --red-deep:        #3a0e0e;
    --green:           #5a9a3a;
    --red:             #a83030;

    /* Team Colors (battle sim) */
    --team1:           #c0392b;
    --team2:           #2980b9;
}

/* --- Reset --- */
*, *::before, *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

/* --- Base Typography --- */
body {
    font-family: "Alegreya Sans", sans-serif;
    background: var(--bg-deep);
    background-image: radial-gradient(ellipse at center, var(--bg) 0%, var(--bg-deep) 70%);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.5;
}

h1, h2, h3 {
    font-family: "Cinzel", serif;
    color: var(--gold);
}

h1 { font-weight: 700; }
h2, h3 { font-weight: 600; }

a { color: var(--gold); text-decoration: none; }
a:hover { color: var(--gold-light); }

/* --- Site Navigation --- */
.site-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    height: 52px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 1000;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
}

.site-nav .nav-brand {
    font-family: "Cinzel", serif;
    font-weight: 700;
    font-size: 1rem;
    color: var(--gold);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
}

.site-nav .nav-brand:hover {
    color: var(--gold-light);
}

.site-nav .nav-links {
    display: flex;
    align-items: center;
    gap: 4px;
    list-style: none;
}

.site-nav .nav-link {
    color: var(--text-muted);
    text-decoration: none;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 500;
    transition: color 0.2s, background 0.2s;
    position: relative;
}

.site-nav .nav-link:hover {
    color: var(--text);
    background: var(--gold-glow);
}

.site-nav .nav-link.active {
    color: var(--gold);
}

.site-nav .nav-link.active::after {
    content: "";
    position: absolute;
    bottom: -8px;
    left: 14px;
    right: 14px;
    height: 2px;
    background: var(--gold);
    border-radius: 1px;
}

/* Dropdown */
.nav-dropdown {
    position: relative;
}

.nav-dropdown-toggle {
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
}

.nav-dropdown-toggle::after {
    content: "";
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid currentColor;
    margin-top: 1px;
}

.nav-dropdown-menu {
    display: none;
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    background: var(--bg-warm);
    border: 1px solid var(--border-light);
    border-radius: 8px;
    padding: 4px;
    min-width: 180px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    z-index: 1001;
}

.nav-dropdown:hover .nav-dropdown-menu,
.nav-dropdown-menu:hover {
    display: block;
}

.nav-dropdown-menu a {
    display: block;
    padding: 8px 14px;
    color: var(--text-muted);
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 500;
    transition: color 0.2s, background 0.2s;
}

.nav-dropdown-menu a:hover {
    color: var(--text);
    background: var(--gold-glow);
}

.nav-dropdown-menu a.active {
    color: var(--gold);
}

/* --- Page Header --- */
.page-header {
    padding: 20px 24px 16px;
    background: linear-gradient(180deg, var(--red-deep) 0%, var(--bg) 100%);
    border-bottom: 2px solid;
    border-image: linear-gradient(90deg, transparent 5%, var(--gold-dark) 30%, var(--gold) 50%, var(--gold-dark) 70%, transparent 95%) 1;
    text-align: center;
}

.page-header h1 {
    font-size: 1.5rem;
    margin-bottom: 4px;
}

.page-header .subtitle {
    font-size: 0.85rem;
    color: var(--text-muted);
}

/* --- Container --- */
.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 16px 20px;
}

.container-wide {
    max-width: 1600px;
    margin: 0 auto;
    padding: 16px 20px;
}

/* --- Cards --- */
.card {
    background: var(--bg-warm);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    transition: border-color 0.2s, box-shadow 0.2s;
}

.card:hover {
    border-color: var(--gold-dark);
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--gold-glow);
}

/* --- Buttons --- */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 20px;
    border: none;
    border-radius: 6px;
    font-family: "Cinzel", serif;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-gold {
    background: linear-gradient(135deg, var(--gold) 0%, var(--gold-dark) 100%);
    color: var(--bg-deep);
}

.btn-gold:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(201, 168, 76, 0.3);
}

.btn-gold:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
}

/* --- Age Toggle --- */
.age-toggle {
    display: flex;
    gap: 4px;
    justify-content: center;
}

.age-btn {
    padding: 6px 18px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    font-family: "Alegreya Sans", sans-serif;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.age-btn:hover {
    border-color: var(--gold-dark);
    color: var(--text);
}

.age-btn.active {
    background: var(--gold-dark);
    color: var(--bg-deep);
    border-color: var(--gold-dark);
    font-weight: 600;
}

/* --- Responsive --- */
@media (max-width: 768px) {
    .site-nav {
        padding: 0 12px;
        height: 48px;
    }
    .site-nav .nav-brand {
        font-size: 0.85rem;
    }
    .site-nav .nav-link {
        padding: 6px 8px;
        font-size: 0.8rem;
    }
    .page-header {
        padding: 12px 16px;
    }
    .page-header h1 {
        font-size: 1.2rem;
    }
    .container, .container-wide {
        padding: 12px;
    }
}
```

**Step 3: Create empty placeholder JS file**

Create `webapp/static/js/constants.js` as an empty file (will be populated in Task 3).

**Step 4: Commit**

```bash
git add webapp/static/ && git commit -m "feat: add base.css with unified design system and static directory structure"
```

---

### Task 3: Extract shared JavaScript constants

Extract NAME_TO_ICON, UNIQUE_BUILDING, ENABLED_CIVS, and icon utility functions from the templates into `webapp/static/js/constants.js`.

**Files:**
- Create: `webapp/static/js/constants.js`

**Step 1: Write constants.js**

Copy the NAME_TO_ICON dictionary from `webapp/templates/index.html` lines 547-731 as the canonical source. Also include:

- `ICON_BASE` and `ICON_BASE_FALLBACK` URLs (from matchup_advisor.html line 655-656 and index.html)
- `ENABLED_CIVS` array (from index.html lines 488-540)
- `UNIQUE_BUILDING` dict (from simulate.html lines 1170-1178)
- `CIV_EMBLEM_BASE` URL (from simulate.html — `https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/`)
- Shared `getIconUrl(name)` helper function that resolves icon URLs with fallback logic

The file should export these as globals on `window` (no module system needed since we're using plain `<script>` tags).

Pattern:
```javascript
/* AoE2 Unit Analyzer — Shared Constants */

const ICON_BASE = "https://raw.githubusercontent.com/qwyt/aoe2-icon-resources/master/objects/";
const ICON_BASE_FALLBACK = "https://aoe2techtree.net/img/Units/";
const CIV_EMBLEM_BASE = "https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/";

const ENABLED_CIVS = [ /* ... full list from index.html ... */ ];

const NAME_TO_ICON = { /* ... full dict from index.html ... */ };

const UNIQUE_BUILDING = { /* ... from simulate.html ... */ };

function getIconUrl(name) {
    const id = NAME_TO_ICON[name];
    if (!id) return null;
    return `${ICON_BASE}${id}.png`;
}

function getIconFallbackUrl(name) {
    const id = NAME_TO_ICON[name];
    if (!id) return null;
    return `${ICON_BASE_FALLBACK}${id}.png`;
}
```

**Step 2: Commit**

```bash
git add webapp/static/js/constants.js && git commit -m "feat: extract shared JS constants (NAME_TO_ICON, ENABLED_CIVS, UNIQUE_BUILDING)"
```

---

### Task 4: Create base.html template with Jinja2 inheritance

Create the base template that all pages will extend. It provides the `<head>`, nav bar, content block, and page-specific CSS/JS blocks.

**Files:**
- Create: `webapp/templates/base.html`

**Step 1: Write base.html**

```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{% block title %}AoE2 Unit Analyzer{% endblock %}</title>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Alegreya+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="{{ url_for('static', filename='css/base.css') }}" />
    {% block page_css %}{% endblock %}
</head>
<body>
    <nav class="site-nav">
        <a href="/" class="nav-brand">AoE2 Analyzer</a>
        <div class="nav-links">
            <a href="/" class="nav-link {% if active_nav == 'simulate' %}active{% endif %}">Battle Sim</a>
            <a href="/matchup-advisor" class="nav-link {% if active_nav == 'matchup' %}active{% endif %}">Matchup Advisor</a>
            <a href="/units" class="nav-link {% if active_nav == 'rankings' %}active{% endif %}">Rankings</a>
            <div class="nav-dropdown">
                <span class="nav-link nav-dropdown-toggle {% if active_nav in ['civ_select', 'civ_detail'] %}active{% endif %}">Database</span>
                <div class="nav-dropdown-menu">
                    <a href="/civilizations" {% if active_nav in ['civ_select', 'civ_detail'] %}class="active"{% endif %}>Civilizations</a>
                </div>
            </div>
        </div>
    </nav>

    {% block content %}{% endblock %}

    <script src="{{ url_for('static', filename='js/constants.js') }}"></script>
    {% block page_js %}{% endblock %}
</body>
</html>
```

Key details:
- `active_nav` is a template variable set by each Flask route (passed via render_template)
- `constants.js` is loaded on every page (shared data)
- Pages add their own CSS via `{% block page_css %}` (as `<link>` tags)
- Pages add their own JS via `{% block page_js %}` (as `<script>` tags)

**Step 2: Commit**

```bash
git add webapp/templates/base.html && git commit -m "feat: add base.html template with Jinja2 inheritance and unified nav"
```

---

### Task 5: Update Flask routes

Update app.py routes to: make `/` serve simulate.html, add `/civilizations` routes, add redirects for old URLs, and pass `active_nav` to all template renders.

**Files:**
- Modify: `webapp/app.py`

**Step 1: Update routes**

Replace the existing route functions with:

```python
@app.route("/")
def home():
    """Battle Sim is the homepage."""
    return render_template("simulate.html", active_nav="simulate")

@app.route("/simulate")
def simulate_redirect():
    """Redirect old /simulate URL to homepage."""
    return redirect("/", code=301)

@app.route("/units")
def units():
    units_by_age = get_units_by_age()
    ages = {k: v["name"] for k, v in AGES.items()}
    return render_template("index.html", units_by_age=units_by_age, ages=ages, active_nav="rankings")

@app.route("/civilizations")
def civ_view():
    """Civilization selection grid."""
    return render_template("civ_select.html", active_nav="civ_select")

@app.route("/civilizations/<civ_name>")
def civ_detail(civ_name):
    """Civilization unit detail page."""
    if civ_name not in ORIGINAL_13_CIVS:
        return redirect("/civilizations")
    return render_template("civ_detail.html", civ_name=civ_name, active_nav="civ_detail")

# Backward compat redirects
@app.route("/civ")
def civ_redirect():
    return redirect("/civilizations", code=301)

@app.route("/civ/<civ_name>")
def civ_detail_redirect(civ_name):
    return redirect(f"/civilizations/{civ_name}", code=301)

@app.route("/matchup-advisor")
def matchup_advisor():
    """Matchup Advisor page."""
    civs = _get_ref_civs()
    return render_template("matchup_advisor.html", civs=civs, active_nav="matchup")
```

Also remove the old `simulate()` route at line 304-307 (replaced by the redirect).

**Step 2: Verify app starts**

```bash
cd webapp && python3 -c "from app import app; print('OK')"
```

**Step 3: Commit**

```bash
git add webapp/app.py && git commit -m "feat: update routes — Battle Sim at /, /civilizations, redirects for old URLs"
```

---

### Task 6: Convert simulate.html to use base.html + external files

This is the biggest template (3,356 lines). Extract its CSS to `static/css/simulate.css`, its JS to `static/js/simulate.js`, and convert it to extend `base.html`.

**Files:**
- Modify: `webapp/templates/simulate.html` — rewrite to use `{% extends 'base.html' %}`
- Create: `webapp/static/css/simulate.css` — extract lines 12-604 (CSS), removing variables/reset/nav that are now in base.css
- Create: `webapp/static/js/simulate.js` — extract lines 825-3353 (JS), removing NAME_TO_ICON/ENABLED_CIVS/UNIQUE_BUILDING that are now in constants.js

**Step 1: Create simulate.css**

Copy `simulate.html` lines 12-604 (the `<style>` block) into `webapp/static/css/simulate.css`.

Then **remove** from simulate.css:
- The `:root { ... }` block (now in base.css)
- The `* { margin: 0; ... }` reset (now in base.css)
- The `body { ... }` styles (now in base.css)
- The `.page-header` styles (now in base.css)
- The `.nav-links` and `.nav-link` styles (nav is now in base.css site-nav)
- The `.container` base styles (now in base.css — but keep `.container` overrides like `max-width: 1600px` as `.container-wide` if needed)

Keep all simulate-specific styles: `.config-panel`, `.team-config`, `.army-config`, `.main-layout`, `.stats-panel`, `.center-panel`, `.right-panel`, canvas styles, battle cards, debug panel, etc.

Update any font-family references: change `"Inter"` to `"Alegreya Sans"`.

**Step 2: Create simulate.js**

Copy `simulate.html` lines 825-3353 (the `<script>` block) into `webapp/static/js/simulate.js`.

Then **remove** from simulate.js:
- The `ENABLED_CIVS` array (now in constants.js)
- The `NAME_TO_ICON` dictionary (now in constants.js)
- The `UNIQUE_BUILDING` dictionary (now in constants.js)
- Any `ICON_BASE` / icon URL constants (now in constants.js)

These are now global variables loaded from constants.js which runs before simulate.js.

**Step 3: Rewrite simulate.html**

Replace the entire file with:

```html
{% extends 'base.html' %}

{% block title %}Battle Simulation — AoE2 Unit Analyzer{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/simulate.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Battle Simulation</h1>
    <p class="subtitle">Watch two armies clash in real-time</p>
</div>

<div class="container-wide">
    <!-- Paste the HTML body content from the old simulate.html here -->
    <!-- Everything between the old <div class="container"> and its closing </div> -->
    <!-- (lines ~618-822 of the original file) -->
</div>
{% endblock %}

{% block page_js %}
<script src="{{ url_for('static', filename='js/simulate.js') }}"></script>
{% endblock %}
```

The HTML body content (team selectors, canvas, controls, debug panel) stays the same — just the wrapping `<html>/<head>/<body>` structure and inline `<style>`/`<script>` tags are removed.

**Step 4: Verify the page loads in browser**

```bash
cd webapp && python3 -c "from app import app; client = app.test_client(); resp = client.get('/'); print(resp.status_code, len(resp.data))"
```

Expected: `200` with a substantial response body.

**Step 5: Commit**

```bash
git add webapp/templates/simulate.html webapp/static/css/simulate.css webapp/static/js/simulate.js && git commit -m "refactor: extract simulate.html CSS/JS to external files, use base.html inheritance"
```

---

### Task 7: Convert index.html (Unit Rankings) to use base.html + external files

**Files:**
- Modify: `webapp/templates/index.html` — rewrite to use `{% extends 'base.html' %}`
- Create: `webapp/static/css/rankings.css` — extract lines 12-456 minus shared styles
- Create: `webapp/static/js/rankings.js` — extract lines 486-2056 minus shared constants

**Step 1: Create rankings.css**

Copy index.html lines 12-456 into `webapp/static/css/rankings.css`. Remove the shared styles already in base.css (`:root`, reset, body, `.page-header`, `.nav-links`/`.nav-link`, `.container`). Keep all table styles, hover card styles, line selector styles, age toggle customizations, etc.

Update `"Inter"` → `"Alegreya Sans"` in any font-family references.

**Step 2: Create rankings.js**

Copy index.html lines 486-2056 into `webapp/static/js/rankings.js`. Remove:
- `ENABLED_CIVS` array
- `NAME_TO_ICON` dictionary
- `ICON_BASE` / `ICON_BASE_FALLBACK` constants

**Step 3: Rewrite index.html**

```html
{% extends 'base.html' %}

{% block title %}Unit Rankings — AoE2 Unit Analyzer{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/rankings.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Unit Rankings</h1>
    <p class="subtitle">Compare unit stats across civilizations</p>
</div>

<div class="container">
    <!-- age toggle, line selector, table container from original lines 472-483 -->
    <div class="age-toggle">
        <button class="age-btn" onclick="setAge('Castle')">Castle Age</button>
        <button class="age-btn active" onclick="setAge('Imperial')">Imperial Age</button>
    </div>
    <div id="lineSelector"></div>
    <div class="table-container" id="tableContainer"></div>
</div>
{% endblock %}

{% block page_js %}
<script>
    const UNITS_BY_AGE = {{ units_by_age | tojson }};
    const AGES = {{ ages | tojson }};
</script>
<script src="{{ url_for('static', filename='js/rankings.js') }}"></script>
{% endblock %}
```

Note: The Jinja2 template variables `units_by_age` and `ages` are passed as inline `<script>` before the external JS file, so rankings.js can reference them as globals.

**Step 4: Verify**

```bash
cd webapp && python3 -c "from app import app; client = app.test_client(); resp = client.get('/units'); print(resp.status_code, len(resp.data))"
```

**Step 5: Commit**

```bash
git add webapp/templates/index.html webapp/static/css/rankings.css webapp/static/js/rankings.js && git commit -m "refactor: extract index.html CSS/JS to external files, use base.html inheritance"
```

---

### Task 8: Convert matchup_advisor.html to use base.html + external files + unified theme

This is the most visually divergent page — it uses a completely different color scheme (dark blue gradient, system fonts, #ffd700 gold). It must be brought in line with the medieval parchment theme.

**Files:**
- Modify: `webapp/templates/matchup_advisor.html` — rewrite to use `{% extends 'base.html' %}`
- Create: `webapp/static/css/matchup.css` — extract lines 7-616 with color/font corrections
- Create: `webapp/static/js/matchup.js` — extract lines 653-1178 minus shared constants

**Step 1: Create matchup.css**

Copy matchup_advisor.html lines 7-616 into `webapp/static/css/matchup.css`. Then make these corrections:

1. **Remove** the `body` rule entirely (base.css handles this)
2. **Remove** the reset (`*`) rule
3. **Remove** `.container` base rule (base.css has it)
4. **Remove** `header`, `.nav-links`, `.nav-link` rules (now in base.css site-nav)
5. **Replace** all hardcoded colors with CSS variables:
   - `#ffd700` → `var(--gold)`
   - `#ff8c00` → `var(--gold-dark)`
   - `#1a1a2e` → `var(--bg-deep)`
   - `#16213e` → `var(--bg)`
   - `rgba(255, 215, 0, ...)` → `var(--gold-glow)` or equivalent
   - `#888` → `var(--text-muted)`
   - `#e4e4e4` → `var(--text)`
   - `#333` → `var(--bg-warm)`
   - `#2a2a4e` → `var(--bg-warm)`
   - `#1e1e3e` → `var(--bg)`
   - `#555` / `#666` → `var(--text-dim)`
   - `#4a90d9` / `#00bcd4` (team2/cyan) → `var(--team2)`
   - `#e74c3c` (team1) → `var(--team1)`
6. **Replace** `font-family: -apple-system, ...` references with nothing (base.css sets it)
7. **Replace** `h1` gradient background with: `color: var(--gold);` (simple gold, no gradient text needed since we have Cinzel)

**Step 2: Create matchup.js**

Copy lines 653-1178 into `webapp/static/js/matchup.js`. Remove:
- `ICON_BASE`, `ICON_BASE_FALLBACK` constants
- `NAME_TO_ICON` dictionary
- Any icon URL helper that's now in constants.js

**Step 3: Rewrite matchup_advisor.html**

```html
{% extends 'base.html' %}

{% block title %}Civ Matchup — AoE2 Unit Analyzer{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/matchup.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Civ Matchup</h1>
    <p class="subtitle">Strategic army composition analysis for any civ matchup</p>
</div>

<div class="container">
    <!-- Civ selector, analyze button, results container from original lines 634-650 -->
    <div class="civ-selector">
        <div class="step-label step-civ1" id="step-label">Click a civilization to select Civ 1</div>
        <div class="civ-grid" id="civ-grid"></div>
        <div class="selected-display" id="selected-display">
            <span class="civ1-pick" id="pick-civ1">&mdash;</span>
            <span class="vs-text">vs</span>
            <span class="civ2-pick" id="pick-civ2">&mdash;</span>
        </div>
    </div>
    <button id="analyze-btn" class="compare-btn" disabled>Analyze Matchup</button>
    <div id="results" class="results-container"></div>
</div>
{% endblock %}

{% block page_js %}
<script>
    const CIVS = {{ civs | tojson }};
</script>
<script src="{{ url_for('static', filename='js/matchup.js') }}"></script>
{% endblock %}
```

**Step 4: Verify**

```bash
cd webapp && python3 -c "from app import app; client = app.test_client(); resp = client.get('/matchup-advisor'); print(resp.status_code, len(resp.data))"
```

**Step 5: Commit**

```bash
git add webapp/templates/matchup_advisor.html webapp/static/css/matchup.css webapp/static/js/matchup.js && git commit -m "refactor: extract matchup_advisor CSS/JS, unify to medieval theme, use base.html"
```

---

### Task 9: Convert civ_select.html to use base.html + external files

**Files:**
- Modify: `webapp/templates/civ_select.html` — rewrite to use `{% extends 'base.html' %}`
- Create: `webapp/static/css/civ-select.css` — extract lines 11-273 minus shared styles
- Create: `webapp/static/js/civ-select.js` — extract lines 431-540

**Step 1: Create civ-select.css**

Copy lines 11-273 into `webapp/static/css/civ-select.css`. Remove shared styles (`:root`, reset, body, `.page-header`, `.nav-links`). Keep expansion grid styles, civ card styles, badges, responsive rules.

Update colors/fonts: any hardcoded values should use CSS variables. The existing styles already mostly use the medieval theme, so fewer changes needed here.

Update any `/civ` links in CSS (if any hover/click references).

**Step 2: Create civ-select.js**

Copy lines 431-540 into `webapp/static/js/civ-select.js`. This populates the civ grids with emblem images. Update any references to `/civ/` URLs to `/civilizations/`.

**Step 3: Rewrite civ_select.html**

```html
{% extends 'base.html' %}

{% block title %}Civilizations — AoE2 Unit Analyzer{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/civ-select.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Unit Details by Civilization</h1>
    <p class="subtitle">Select a civilization to view detailed unit stats, upgrades, and bonuses</p>
</div>

<div class="expansions">
    <!-- All expansion sections from original lines 286-429 -->
    <!-- Update any href="/civ/..." to href="/civilizations/..." -->
</div>
{% endblock %}

{% block page_js %}
<script src="{{ url_for('static', filename='js/civ-select.js') }}"></script>
{% endblock %}
```

**Important:** In both the HTML and JS, update all `/civ/` links to `/civilizations/`.

**Step 4: Verify**

```bash
cd webapp && python3 -c "from app import app; client = app.test_client(); resp = client.get('/civilizations'); print(resp.status_code, len(resp.data))"
```

**Step 5: Commit**

```bash
git add webapp/templates/civ_select.html webapp/static/css/civ-select.css webapp/static/js/civ-select.js && git commit -m "refactor: extract civ_select CSS/JS to external files, use base.html, update /civ to /civilizations"
```

---

### Task 10: Convert civ_detail.html to use base.html + external files

**Files:**
- Modify: `webapp/templates/civ_detail.html` — rewrite to use `{% extends 'base.html' %}`
- Create: `webapp/static/css/civ-detail.css` — extract lines 11-461 minus shared styles
- Create: `webapp/static/js/civ-detail.js` — extract lines 587-1239 minus shared constants

**Step 1: Create civ-detail.css**

Copy lines 11-461 into `webapp/static/css/civ-detail.css`. Remove shared styles. Keep: header-top layout, civ-emblem, building groups grid, unit cards, modal overlay, stat chains, etc.

Update `"Inter"` → `"Alegreya Sans"`.

**Step 2: Create civ-detail.js**

Copy lines 587-1239 into `webapp/static/js/civ-detail.js`. Remove:
- `NAME_TO_ICON` dictionary
- `UNIQUE_BUILDING` dictionary

Update any `/civ` references to `/civilizations`.

**Step 3: Rewrite civ_detail.html**

```html
{% extends 'base.html' %}

{% block title %}{{ civ_name }} — AoE2 Unit Analyzer{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/civ-detail.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <div class="header-top">
        <a href="/civilizations" class="back-link">&#8592; Back to Civilizations</a>
        <div class="header-main">
            <img class="civ-emblem" src="https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/{{ civ_name|lower }}.png" alt="{{ civ_name }}" />
            <h1>{{ civ_name }}</h1>
            <!-- Age toggle from original -->
        </div>
    </div>
</div>

<div class="container">
    <div class="buildings-container" id="buildingsContainer"></div>
</div>

<!-- Modal (from original) -->
<div class="modal-overlay" id="modalOverlay">
    <!-- Modal content from original lines -->
</div>
{% endblock %}

{% block page_js %}
<script>
    const CIV_NAME = "{{ civ_name }}";
</script>
<script src="{{ url_for('static', filename='js/civ-detail.js') }}"></script>
{% endblock %}
```

**Step 4: Verify**

```bash
cd webapp && python3 -c "from app import app; client = app.test_client(); resp = client.get('/civilizations/Britons'); print(resp.status_code, len(resp.data))"
```

**Step 5: Commit**

```bash
git add webapp/templates/civ_detail.html webapp/static/css/civ-detail.css webapp/static/js/civ-detail.js && git commit -m "refactor: extract civ_detail CSS/JS to external files, use base.html, update URLs"
```

---

### Task 11: Visual polish and final consistency pass

Do a final pass across all CSS files to ensure visual consistency. Check that every page uses the same variables, same card styles, same button patterns, and that no hardcoded colors remain.

**Files:**
- Review/modify: all files in `webapp/static/css/`
- Review/modify: `webapp/templates/base.html`

**Step 1: Audit for hardcoded colors**

Search all CSS files for hex color codes that should be CSS variables:

```bash
grep -rn '#[0-9a-fA-F]\{3,6\}' webapp/static/css/ --include="*.css" | grep -v 'base.css' | grep -v '^\s*/\*'
```

Replace any remaining hardcoded hex values with the appropriate CSS variable from base.css.

**Step 2: Audit for font-family references**

```bash
grep -rn 'font-family' webapp/static/css/ webapp/templates/
```

Ensure:
- No `"Inter"` references remain
- No `-apple-system` system font stacks remain
- No `"Open Sans"` references remain
- Only `"Cinzel"`, `"Alegreya Sans"`, and `"JetBrains Mono"` are used

**Step 3: Audit for old URL patterns**

```bash
grep -rn '"/civ"' webapp/templates/ webapp/static/js/
grep -rn 'href="/civ/' webapp/templates/ webapp/static/js/
grep -rn '"/simulate"' webapp/templates/ webapp/static/js/
```

Ensure all links point to the new routes (`/civilizations`, `/`).

**Step 4: Test all pages load**

```bash
cd webapp && python3 -c "
from app import app
client = app.test_client()
for path in ['/', '/units', '/matchup-advisor', '/civilizations', '/civilizations/Britons']:
    resp = client.get(path)
    print(f'{path}: {resp.status_code} ({len(resp.data)} bytes)')
for path in ['/simulate', '/civ', '/civ/Britons']:
    resp = client.get(path)
    print(f'{path}: {resp.status_code} (redirect)')
"
```

Expected: 200 for all main routes, 301 for redirect routes.

**Step 5: Commit**

```bash
git add -A && git commit -m "style: final consistency pass — unified colors, fonts, and URLs across all pages"
```

---

### Task 12: Manual browser testing

Open each page in a browser and verify:

1. **Navigation**: Sticky nav bar appears on all 5 pages with correct active state
2. **Typography**: Cinzel for headings, Alegreya Sans for body text, no Inter/system fonts
3. **Colors**: Same dark parchment palette everywhere, no blue pages
4. **Battle Sim (/)**: Canvas works, unit selection works, simulation runs
5. **Matchup Advisor**: Civ selector works, analysis loads, results display correctly
6. **Rankings**: Table loads, sorting works, hover cards work
7. **Civilizations**: All expansion sections show, clicking a civ navigates to detail
8. **Civ Detail**: Units load, modal opens, stat chains display
9. **Redirects**: `/simulate` → `/`, `/civ` → `/civilizations`, `/civ/Britons` → `/civilizations/Britons`
10. **Responsive**: Shrink browser to mobile width, verify nav and layouts adapt

```bash
cd webapp && python3 app.py
# Open http://localhost:5001 in browser (use port 5001 to avoid macOS AirPlay conflict on 5000)
```

Fix any issues found during testing and commit fixes.

---

## Summary

| Task | Description | Key Files |
|------|------------|-----------|
| 1 | Remove review/comment system | app.py, delete review.html + home.html |
| 2 | Create base.css + directory structure | static/css/base.css |
| 3 | Extract shared JS constants | static/js/constants.js |
| 4 | Create base.html template | templates/base.html |
| 5 | Update Flask routes | app.py |
| 6 | Convert simulate.html | simulate.html + .css + .js |
| 7 | Convert index.html | index.html + rankings.css + rankings.js |
| 8 | Convert matchup_advisor.html (+ unify theme) | matchup_advisor.html + matchup.css + matchup.js |
| 9 | Convert civ_select.html | civ_select.html + civ-select.css + civ-select.js |
| 10 | Convert civ_detail.html | civ_detail.html + civ-detail.css + civ-detail.js |
| 11 | Visual polish + consistency audit | All CSS files |
| 12 | Manual browser testing | All pages |

**Estimated new file count:** 13 new files (1 base template, 5 CSS, 6 JS, 1 design doc already committed)
**Estimated lines eliminated by dedup:** ~800 (NAME_TO_ICON x4 → x1, etc.)
**Templates deleted:** 2 (review.html, home.html)
