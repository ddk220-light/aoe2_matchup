# Matchup Advisor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a two-civ comparison page that shows side-by-side percentile bars for every unit line.

**Architecture:** Frontend-only — fetch existing `/api/civ-power-units/<civ>` for both civs, compare client-side. Reuse civ picker patterns from team_analysis.js and strength colors from matchup.js.

**Tech Stack:** Jinja2 template, vanilla JS, CSS custom properties

---

### Task 1: Update app.py route and template

**Files:**
- Modify: `webapp/app.py` (matchup_advisor route ~line 1061)
- Replace: `webapp/templates/matchup_wip.html`

**Changes:**

1. In `app.py`, update the `matchup_advisor()` route to pass civs:

```python
@app.route("/matchup-advisor")
def matchup_advisor():
    """Matchup Advisor — civ vs civ comparison."""
    civs = _get_ref_civs()
    return render_template("matchup_advisor.html", civs=civs, active_nav="matchup")
```

2. Create `webapp/templates/matchup_advisor.html` (replacing matchup_wip.html):

```html
{% extends 'base.html' %}
{% block title %}Matchup Advisor — AoE2 Unit Analyzer{% endblock %}
{% block page_css %}
<link rel="stylesheet" href="/static/css/matchup_advisor.css">
{% endblock %}
{% block content %}
<div class="page-header">
    <h1>Matchup Advisor</h1>
    <p class="subtitle">Compare two civilizations side by side</p>
</div>
<div class="container">
    <!-- Civ Picker -->
    <div class="ma-picker">
        <div class="ma-slot ma-slot-left" id="slot-left">
            <span class="ma-slot-label">Your Civ</span>
        </div>
        <div class="ma-vs">vs</div>
        <div class="ma-slot ma-slot-right" id="slot-right">
            <span class="ma-slot-label">Opponent</span>
        </div>
    </div>
    <div class="ma-civ-grid" id="civ-grid"></div>
    <!-- Age Toggle -->
    <div class="ma-age-toggle" id="age-toggle" style="display:none;">
        <button class="ma-age-btn active" data-age="imperial">Imperial</button>
        <button class="ma-age-btn" data-age="castle">Castle</button>
    </div>
    <!-- Results -->
    <div id="results"></div>
</div>
<script>const CIVS = {{ civs | tojson }};</script>
<script src="/static/js/constants.js"></script>
<script src="/static/js/matchup_advisor.js"></script>
{% endblock %}
```

3. Delete `webapp/templates/matchup_wip.html` (no longer needed).

---

### Task 2: Create matchup_advisor.css

**Files:**
- Create: `webapp/static/css/matchup_advisor.css`

**Styles needed:**

- `.ma-picker` — flex row, center-aligned, gap, with the two slots and "vs" divider
- `.ma-slot` — 120px wide, bordered card, shows civ emblem+name when selected, placeholder when empty
- `.ma-slot-left` — gold border accent (`var(--gold)`)
- `.ma-slot-right` — blue border accent (`var(--team2)`)
- `.ma-civ-grid` — reuse pattern from team_analysis: `grid-template-columns: repeat(auto-fill, minmax(72px, 1fr))`, max-width 900px, centered
- `.ma-civ-card` — flex column, emblem + name, hover effects (same as team_analysis .civ-card)
- `.ma-civ-card.selected-left` — gold border highlight
- `.ma-civ-card.selected-right` — blue border highlight
- `.ma-age-toggle` — centered flex, pill buttons
- `.ma-section` — section card per column (cavalry/ranged/infantry/siege), with header
- `.ma-row` — unit line row with left/right halves
- `.ma-unit-side` — one civ's unit within a row (name, bar, strength label)
- `.ma-bar` — percentile bar (height 8px, border-radius, colored fill)
- `.ma-bar-fill` — inner fill element, width set via `style="width: XX%"`
- `.ma-na` — greyed out "Not Available" state
- `.ma-winner` — subtle highlight on the winning side
- Responsive: stack to single column on mobile (<768px)

---

### Task 3: Create matchup_advisor.js

**Files:**
- Create: `webapp/static/js/matchup_advisor.js`

**State:**
```javascript
let civLeft = null;   // selected civ name (string)
let civRight = null;
let activeSlot = "left";  // which slot gets the next click
let currentAge = "imperial";
```

**Functions:**

1. `init()` — build civ grid from `CIVS`, attach click handlers, attach age toggle handlers.

2. `onCivClick(civName)` —
   - If civName is already selected on left → deselect, set activeSlot="left"
   - If civName is already selected on right → deselect, set activeSlot="right"
   - Else if activeSlot is "left" → set civLeft, advance activeSlot to "right"
   - Else → set civRight
   - Call `updateUI()`
   - If both selected → call `loadComparison()`

3. `updateUI()` — update slot displays (emblem+name or placeholder), update grid card classes (selected-left, selected-right), show/hide age toggle.

4. `loadComparison()` — fetch both `/api/civ-power-units/<civ>?age=<age>`, call `renderComparison(dataLeft, dataRight)`.

5. `renderComparison(dataLeft, dataRight)` — for each column (cavalry, ranged, infantry, siege), create a section card. For each unit line in the column, build a row with left and right sides. Use `COLUMN_DEFS` and `LINE_NAMES` (same as matchup.js constants). For each side, extract the entry from power_units data (or null if line is null). Render percentile bar + strength tier + unit name, or "N/A" if null.

6. `buildUnitSide(entry, civName)` — returns DOM element for one side of a comparison row. Shows:
   - Civ emblem (small, 20px)
   - Unit name (from entry.unit_name)
   - Percentile bar (width = entry.percentile + "%", colored by strength)
   - Strength label
   - Or "Not Available" if entry is null

7. `getStrengthColor(strength)` — return {bg, text, label} from STRENGTH_COLORS constant (same as matchup.js).

**Constants to define (copy from matchup.js):**
```javascript
const COLUMN_DEFS = {
    cavalry: ["light_cav", "knight", "camel", "steppe_lancer", "elephant"],
    ranged: ["skirmisher", "archer", "cav_archer", "gunpowder", "scorpion"],
    infantry: ["militia", "spear", "shock_infantry"],
    siege: ["ram", "bombard_cannon", "trebuchet"],
};
const COLUMN_LABELS = { cavalry: "Cavalry", ranged: "Ranged", infantry: "Infantry", siege: "Siege" };
const LINE_NAMES = { /* same as matchup.js */ };
const COLUMN_ORDER = ["cavalry", "ranged", "infantry", "siege"];
const STRENGTH_COLORS = { /* same as matchup.js */ };
```

**Multi-unit handling:** `power_units[column][line]` is an array (can have multiple entries, e.g., unique unit + generic). Show the first entry (top/best unit in that line) for comparison. If the array has >1 entry, show additional units below in smaller text.

---

### Task 4: Verify and commit

**Steps:**
1. Run the Flask app and navigate to `/matchup-advisor`
2. Select two civs (e.g., Franks vs Britons)
3. Verify all 4 sections render with correct unit lines
4. Verify percentile bars match `civ_power_units.json` data
5. Verify N/A shows for missing lines (e.g., Franks have no camels)
6. Toggle Castle/Imperial and verify data updates
7. Test deselecting and reselecting civs
8. Test responsive layout on narrow viewport
9. Commit all changes
