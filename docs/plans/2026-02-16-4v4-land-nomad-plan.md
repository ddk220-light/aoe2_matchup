# 4v4 Land Nomad Team Analysis — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Team Analysis" tab where users pick 4 civs per team and see which side has the cavalry advantage, using pre-computed rank/median-delta data from the battle_scores table.

**Architecture:** Extend the existing `battle_scores` table with `rank` and `median_delta` columns computed during batch scoring. A new Flask API endpoint does a simple filtered SELECT. A new frontend page with two side-by-side civ grids calls this endpoint and renders stage cards.

**Tech Stack:** Python/Flask (backend), SQLite (DB), vanilla JS + CSS (frontend), numpy (median computation)

**Design doc:** `docs/plans/2026-02-16-4v4-land-nomad-design.md`

---

### Task 1: Add rank and median_delta columns to battle_scores schema

**Files:**
- Modify: `analysis/generate_reference.py:366-378`

**Step 1: Add columns to CREATE TABLE**

In `analysis/generate_reference.py`, find the `CREATE TABLE battle_scores` block (line 366) and add two nullable columns:

```python
    cursor.execute("""
        CREATE TABLE battle_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_slug TEXT NOT NULL,
            age TEXT NOT NULL,
            civ_name TEXT NOT NULL,
            unit_slug TEXT NOT NULL,
            score_type TEXT NOT NULL,
            score_value REAL NOT NULL,
            rank INTEGER,
            median_delta REAL
        );
    """)
```

The columns are nullable because they are populated in a second pass by `compute_battle_scores.py` after scores are written.

**Step 2: Add index for team analysis queries**

After the existing index creation (line 377), add:

```python
    cursor.execute(
        "CREATE INDEX idx_battle_scores_lookup ON battle_scores (line_slug, age, score_type, civ_name);"
    )
```

This composite index supports the team analysis query: `WHERE line_slug=? AND age=? AND score_type=? AND civ_name IN (...)`.

**Step 3: Commit**

```bash
git add analysis/generate_reference.py
git commit -m "feat: add rank and median_delta columns to battle_scores schema"
```

---

### Task 2: Add ranking computation to compute_battle_scores.py

**Files:**
- Modify: `webapp/compute_battle_scores.py` (after line 1787, before `main()`)

**Step 1: Write the compute_rankings function**

Add this function before `main()`:

```python
def compute_rankings():
    """Compute rank and median_delta for every (line_slug, age, score_type) group.

    For each group:
    - median = numpy.median(score_values)
    - rank = position sorted by score_value desc (1 = highest)
    - median_delta = score_value - median
    """
    import numpy as np

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all distinct groups
    c.execute("SELECT DISTINCT line_slug, age, score_type FROM battle_scores")
    groups = c.fetchall()

    total_updated = 0
    for line_slug, age, score_type in groups:
        # Fetch all rows in this group
        c.execute(
            "SELECT id, score_value FROM battle_scores WHERE line_slug=? AND age=? AND score_type=?",
            (line_slug, age, score_type),
        )
        rows = c.fetchall()
        if not rows:
            continue

        values = [r[1] for r in rows]
        median = float(np.median(values))

        # Sort by score_value desc for ranking
        ranked = sorted(rows, key=lambda r: r[1], reverse=True)

        for rank, (row_id, score_value) in enumerate(ranked, start=1):
            delta = round(score_value - median, 4)
            c.execute(
                "UPDATE battle_scores SET rank=?, median_delta=? WHERE id=?",
                (rank, delta, row_id),
            )
            total_updated += 1

    conn.commit()
    conn.close()
    print(f"Rankings: updated {total_updated} rows across {len(groups)} groups")
```

**Step 2: Call compute_rankings at the end of main()**

In the `main()` function, add the call right before `"Write output"` (before line 2021). Also add it in the `--roles-only` branch (before `return` on line 1835):

In the `--roles-only` branch, before `return`:
```python
        # Compute rankings for all scores
        ranking_start = time.time()
        compute_rankings()
        print(f"Rankings: {time.time() - ranking_start:.1f}s")
        return
```

In the full run, after siege scores and before JSON output:
```python
    # Compute rankings for all DB scores (rank + median_delta)
    ranking_start = time.time()
    compute_rankings()
    ranking_time = time.time() - ranking_start
    print(f"Rankings: {ranking_time:.1f}s")
```

**Step 3: Regenerate the database**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer && python3 -m analysis.generate_reference
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 compute_battle_scores.py --roles-only
```

**Step 4: Verify rankings were written**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 -c "
import sqlite3
conn = sqlite3.connect('aoe2_reference.db')
c = conn.cursor()
# Check stable_effectiveness rankings exist
c.execute('''SELECT civ_name, unit_slug, score_value, rank, median_delta
             FROM battle_scores
             WHERE line_slug=\"stable\" AND age=\"Imperial\" AND score_type=\"stable_effectiveness\"
             ORDER BY rank LIMIT 10''')
for row in c.fetchall():
    print(f'Rank {row[3]}: {row[0]} {row[1]} = {row[2]:.1f} (delta: {row[4]:+.1f})')
conn.close()
"
```

Expected: 10 rows with rank 1-10, positive median_delta values, sorted by score descending.

**Step 5: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: compute rank and median_delta for all battle scores"
```

---

### Task 3: Add team analysis API endpoint

**Files:**
- Modify: `webapp/app.py` (add after matchup advisor endpoints, around line 1978)

**Step 1: Add the stage-to-query mapping constant**

Add near the top of app.py with other constants (after `UNIT_LINES`):

```python
# Stage-to-query mapping for team analysis
TEAM_ANALYSIS_STAGES = {
    "cavalry": {"line_slug": "stable", "score_type": "stable_effectiveness"},
    # Future stages:
    # "ranged": {"line_slug": "archery", "score_type": "ranged_effectiveness"},
    # "infantry": {"line_slug": "infantry", "score_type": "militia_value"},
}
```

**Step 2: Add the page route**

```python
@app.route("/team-analysis")
def team_analysis():
    """Team Analysis page."""
    civs = _get_ref_civs()
    return render_template("team_analysis.html", civs=civs, active_nav="team_analysis")
```

**Step 3: Add the API endpoint**

```python
@app.route("/api/team-analysis")
def api_team_analysis():
    """Team analysis: compare two teams' strength in a given stage."""
    team1_raw = request.args.get("team1", "")
    team2_raw = request.args.get("team2", "")
    stage = request.args.get("stage", "cavalry")
    age = request.args.get("age", "Imperial")

    if stage not in TEAM_ANALYSIS_STAGES:
        return jsonify({"error": f"Unknown stage: {stage}"}), 400

    team1_civs = [c.strip() for c in team1_raw.split(",") if c.strip()]
    team2_civs = [c.strip() for c in team2_raw.split(",") if c.strip()]

    if len(team1_civs) != 4 or len(team2_civs) != 4:
        return jsonify({"error": "Each team must have exactly 4 civs"}), 400

    stage_cfg = TEAM_ANALYSIS_STAGES[stage]
    line_slug = stage_cfg["line_slug"]
    score_type = stage_cfg["score_type"]

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Get median for this group (from any row — they all have same median_delta offset)
    rc.execute(
        "SELECT score_value, median_delta FROM battle_scores WHERE line_slug=? AND age=? AND score_type=? LIMIT 1",
        (line_slug, age, score_type),
    )
    sample = rc.fetchone()
    if not sample:
        ref_conn.close()
        return jsonify({"error": "No scores found for this stage/age"}), 404
    median = round(sample["score_value"] - sample["median_delta"], 4)

    def get_team_data(civs):
        placeholders = ",".join("?" for _ in civs)
        rc.execute(
            f"""SELECT civ_name, unit_slug, score_value, rank, median_delta
                FROM battle_scores
                WHERE line_slug=? AND age=? AND score_type=?
                  AND civ_name IN ({placeholders})
                  AND median_delta > 0
                ORDER BY score_value DESC""",
            [line_slug, age, score_type] + civs,
        )
        above = [
            {
                "civ": row["civ_name"],
                "unit_slug": row["unit_slug"],
                "score": round(row["score_value"], 1),
                "rank": row["rank"],
                "median_delta": round(row["median_delta"], 1),
            }
            for row in rc.fetchall()
        ]
        total_delta = round(sum(u["median_delta"] for u in above), 1)
        return {"civs": civs, "above_median_units": above, "total_delta": total_delta}

    t1 = get_team_data(team1_civs)
    t2 = get_team_data(team2_civs)
    ref_conn.close()

    if t1["total_delta"] > t2["total_delta"]:
        advantage = "team1"
    elif t2["total_delta"] > t1["total_delta"]:
        advantage = "team2"
    else:
        advantage = "even"

    return jsonify({
        "stage": stage,
        "age": age,
        "score_type": score_type,
        "median": round(median, 1),
        "team1": t1,
        "team2": t2,
        "advantage": advantage,
        "advantage_margin": round(abs(t1["total_delta"] - t2["total_delta"]), 1),
    })
```

**Step 4: Verify the endpoint manually**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 -c "
from app import app
with app.test_client() as c:
    r = c.get('/api/team-analysis?team1=Franks,Persians,Mongols,Huns&team2=Aztecs,Celts,Japanese,Byzantines&stage=cavalry')
    import json
    data = json.loads(r.data)
    print(json.dumps(data, indent=2))
    assert 'team1' in data
    assert 'advantage' in data
    assert data['stage'] == 'cavalry'
    print('API endpoint OK')
"
```

**Step 5: Commit**

```bash
git add webapp/app.py
git commit -m "feat: add /api/team-analysis endpoint for team cavalry comparison"
```

---

### Task 4: Add Team Analysis nav tab to base.html

**Files:**
- Modify: `webapp/templates/base.html:25-29` (between Matchup Advisor and Rankings tabs)

**Step 1: Add the nav tab**

Insert between the Matchup Advisor tab and the Rankings tab:

```html
            <a href="/team-analysis" class="nav-tab {% if active_nav == 'team_analysis' %}active{% endif %}">
                <span class="nav-tab-icon">&#9881;</span>
                <span class="nav-tab-label">Team Analysis</span>
                <span class="nav-tab-desc">4v4 team matchups</span>
            </a>
```

**Step 2: Commit**

```bash
git add webapp/templates/base.html
git commit -m "feat: add Team Analysis nav tab"
```

---

### Task 5: Create team_analysis.html template

**Files:**
- Create: `webapp/templates/team_analysis.html`

**Step 1: Write the template**

Follow the pattern from `matchup_advisor.html`: extends base.html, injects CIVS via Jinja, links to external CSS and JS files.

```html
{% extends 'base.html' %}

{% block title %}Team Analysis — AoE2 Unit Analyzer{% endblock %}

{% block page_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/team_analysis.css') }}" />
{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Team Analysis</h1>
    <p class="subtitle">Compare 4v4 team strengths across combat categories</p>
</div>

<div class="container">
    <div class="team-picker">
        <div class="team-panel team1-panel">
            <h3 class="team-title team1-title">Team 1</h3>
            <div class="team-slots" id="team1-slots"></div>
            <div class="civ-grid" id="team1-grid"></div>
        </div>
        <div class="team-panel team2-panel">
            <h3 class="team-title team2-title">Team 2</h3>
            <div class="team-slots" id="team2-slots"></div>
            <div class="civ-grid" id="team2-grid"></div>
        </div>
    </div>

    <button id="analyze-btn" class="compare-btn" disabled>
        Analyze Teams
    </button>

    <div id="results" class="results-container"></div>
</div>
{% endblock %}

{% block page_js %}
<script>
    const CIVS = {{ civs | tojson }};
</script>
<script src="{{ url_for('static', filename='js/team_analysis.js') }}"></script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add webapp/templates/team_analysis.html
git commit -m "feat: add team_analysis.html template"
```

---

### Task 6: Create team_analysis.css

**Files:**
- Create: `webapp/static/css/team_analysis.css`

**Step 1: Write the CSS**

Reuse patterns from `matchup.css` for civ grid. Key new styles: side-by-side team panels, team slots, stage cards.

```css
/* ==========================================================================
   AoE2 Unit Analyzer - Team Analysis Page Styles
   Extends base.css — do NOT duplicate body, container, header, nav, or h1 rules.
   ========================================================================== */

/* --- Team Picker Layout --- */
.team-picker {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
}

.team-panel {
    border: 2px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    background: rgba(255, 255, 255, 0.02);
}

.team1-panel { border-color: rgba(192, 57, 43, 0.4); }
.team2-panel { border-color: rgba(41, 128, 185, 0.4); }

.team-title {
    text-align: center;
    margin: 0 0 12px;
    font-size: 1rem;
    font-family: "Cinzel", serif;
}
.team1-title { color: var(--team1); }
.team2-title { color: var(--team2); }

/* --- Team Slots (selected civs) --- */
.team-slots {
    display: flex;
    justify-content: center;
    gap: 10px;
    margin-bottom: 12px;
    min-height: 70px;
}

.team-slot {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 60px;
    cursor: pointer;
    transition: opacity 0.2s;
}
.team-slot:hover { opacity: 0.7; }

.team-slot .slot-emblem {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 2px solid var(--border);
    object-fit: cover;
    background: rgba(0, 0, 0, 0.3);
}
.team-slot.filled .slot-emblem { border-color: var(--gold); }

.team-slot .slot-label {
    font-size: 0.65rem;
    text-align: center;
    margin-top: 3px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 60px;
}
.team-slot.empty .slot-emblem {
    border-style: dashed;
    opacity: 0.4;
}

/* --- Civ Grid (inside each team panel) --- */
.team-panel .civ-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
    gap: 6px;
    max-height: 300px;
    overflow-y: auto;
}

.team-panel .civ-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 6px 4px 5px;
    background: rgba(255, 255, 255, 0.05);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
    color: var(--text);
}
.team-panel .civ-card:hover {
    transform: translateY(-1px);
    border-color: rgba(201, 168, 76, 0.3);
}
.team-panel .civ-card .civ-emblem {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 1px solid rgba(201, 168, 76, 0.3);
    object-fit: cover;
    background: rgba(0, 0, 0, 0.3);
    margin-bottom: 3px;
}
.team-panel .civ-card .civ-card-name {
    font-size: 0.6rem;
    text-align: center;
    line-height: 1.1;
}

.team1-panel .civ-card.selected {
    border-color: var(--team1);
    background: rgba(192, 57, 43, 0.15);
}
.team2-panel .civ-card.selected {
    border-color: var(--team2);
    background: rgba(41, 128, 185, 0.15);
}
.team-panel .civ-card.disabled {
    opacity: 0.3;
    pointer-events: none;
}

/* --- Analyze Button (reuse matchup pattern) --- */
.compare-btn {
    display: block;
    margin: 10px auto 20px;
    padding: 15px 40px;
    background: linear-gradient(135deg, var(--gold-dark), var(--gold));
    border: none;
    border-radius: 25px;
    color: var(--bg-deep);
    font-family: "Cinzel", serif;
    font-size: 1.1rem;
    font-weight: bold;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
}
.compare-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}
.compare-btn:not(:disabled):hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(201, 168, 76, 0.4);
}

/* --- Results Container --- */
.results-container {
    max-width: 1000px;
    margin: 0 auto;
}

/* --- Stage Card --- */
.stage-card {
    border: 2px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    background: rgba(255, 255, 255, 0.02);
}

.stage-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
}
.stage-title {
    font-family: "Cinzel", serif;
    font-size: 1.2rem;
    color: var(--gold);
}
.stage-advantage {
    font-size: 0.9rem;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 8px;
}
.stage-advantage.team1 {
    color: var(--team1);
    background: rgba(192, 57, 43, 0.15);
}
.stage-advantage.team2 {
    color: var(--team2);
    background: rgba(41, 128, 185, 0.15);
}
.stage-advantage.even {
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.05);
}

/* --- Stage Columns (team1 vs team2) --- */
.stage-columns {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}
.stage-column-header {
    font-weight: 600;
    font-size: 0.85rem;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
}
.stage-column-header.team1 { color: var(--team1); }
.stage-column-header.team2 { color: var(--team2); }

/* --- Unit Cards in Stage --- */
.unit-entry {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    margin-bottom: 6px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
}
.unit-entry .civ-emblem {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 1px solid rgba(201, 168, 76, 0.3);
    object-fit: cover;
    flex-shrink: 0;
}
.unit-entry-info {
    flex: 1;
    min-width: 0;
}
.unit-entry-name {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text);
}
.unit-entry-civ {
    font-size: 0.7rem;
    color: var(--text-muted);
}
.unit-entry-stats {
    text-align: right;
    flex-shrink: 0;
}
.unit-entry-score {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--gold);
}
.unit-entry-meta {
    font-size: 0.65rem;
    color: var(--text-muted);
}

.no-units-msg {
    font-size: 0.8rem;
    color: var(--text-muted);
    font-style: italic;
    padding: 8px 0;
}

/* --- Footer: civs without above-median units --- */
.stage-footer {
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
    font-size: 0.75rem;
    color: var(--text-muted);
}

/* --- Loading spinner --- */
.loading-indicator {
    text-align: center;
    padding: 30px;
    color: var(--text-muted);
}

/* --- Responsive --- */
@media (max-width: 768px) {
    .team-picker {
        grid-template-columns: 1fr;
    }
    .stage-columns {
        grid-template-columns: 1fr;
    }
}
```

**Step 2: Commit**

```bash
git add webapp/static/css/team_analysis.css
git commit -m "feat: add team_analysis.css styles"
```

---

### Task 7: Create team_analysis.js

**Files:**
- Create: `webapp/static/js/team_analysis.js`

**Step 1: Write the JavaScript**

This file handles: civ grid rendering for both teams, slot management, API call, and results rendering. Follows patterns from `matchup.js`.

```javascript
/* ==========================================================================
   AoE2 Unit Analyzer - Team Analysis Page Logic
   Depends on: constants.js (CIV_EMBLEM_BASE)
   Expects global: CIVS (injected by inline <script> from Jinja2)
   ========================================================================== */

/* ---- State ---- */
const team1 = [];
const team2 = [];
const MAX_PER_TEAM = 4;

/* ---- DOM refs ---- */
const team1Slots = document.getElementById("team1-slots");
const team2Slots = document.getElementById("team2-slots");
const team1Grid = document.getElementById("team1-grid");
const team2Grid = document.getElementById("team2-grid");
const analyzeBtn = document.getElementById("analyze-btn");
const resultsEl = document.getElementById("results");

/* ---- Helpers ---- */
function civSlug(name) { return name.toLowerCase(); }
function civEmblemUrl(name) { return CIV_EMBLEM_BASE + civSlug(name) + ".png"; }

function formatUnitName(slug) {
    return slug.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

/* ---- Render slots ---- */
function renderSlots(container, teamArr, teamColor) {
    container.innerHTML = "";
    for (let i = 0; i < MAX_PER_TEAM; i++) {
        const slot = document.createElement("div");
        const civ = teamArr[i];
        slot.className = "team-slot " + (civ ? "filled" : "empty");

        const img = document.createElement("img");
        img.className = "slot-emblem";
        img.src = civ ? civEmblemUrl(civ) : "";
        img.alt = civ || "Empty";
        if (!civ) img.style.visibility = "hidden";

        const label = document.createElement("span");
        label.className = "slot-label";
        label.textContent = civ || "Pick...";

        slot.appendChild(img);
        slot.appendChild(label);

        if (civ) {
            slot.addEventListener("click", () => {
                const idx = teamArr.indexOf(civ);
                if (idx !== -1) teamArr.splice(idx, 1);
                updateAll();
            });
        }
        container.appendChild(slot);
    }
}

/* ---- Render civ grids ---- */
function renderGrid(container, teamArr, otherArr) {
    container.innerHTML = "";
    CIVS.forEach(name => {
        const card = document.createElement("div");
        card.className = "civ-card";
        card.dataset.civ = name;

        const inThis = teamArr.includes(name);
        const inOther = otherArr.includes(name);
        const full = teamArr.length >= MAX_PER_TEAM;

        if (inThis) card.classList.add("selected");
        if (inOther || (full && !inThis)) card.classList.add("disabled");

        const img = document.createElement("img");
        img.className = "civ-emblem";
        img.src = civEmblemUrl(name);
        img.alt = name;
        img.loading = "lazy";

        const label = document.createElement("span");
        label.className = "civ-card-name";
        label.textContent = name;

        card.appendChild(img);
        card.appendChild(label);

        card.addEventListener("click", () => {
            if (inOther) return;
            if (inThis) {
                const idx = teamArr.indexOf(name);
                if (idx !== -1) teamArr.splice(idx, 1);
            } else if (!full) {
                teamArr.push(name);
            }
            updateAll();
        });

        container.appendChild(card);
    });
}

/* ---- Sync everything ---- */
function updateAll() {
    renderSlots(team1Slots, team1, "team1");
    renderSlots(team2Slots, team2, "team2");
    renderGrid(team1Grid, team1, team2);
    renderGrid(team2Grid, team2, team1);
    analyzeBtn.disabled = team1.length !== MAX_PER_TEAM || team2.length !== MAX_PER_TEAM;
    resultsEl.innerHTML = "";
}

/* ---- Initial render ---- */
updateAll();

/* ---- Analysis ---- */
analyzeBtn.addEventListener("click", async () => {
    resultsEl.innerHTML = '<div class="loading-indicator">Analyzing teams...</div>';
    analyzeBtn.disabled = true;

    const params = new URLSearchParams({
        team1: team1.join(","),
        team2: team2.join(","),
        stage: "cavalry",
    });

    try {
        const resp = await fetch("/api/team-analysis?" + params);
        if (!resp.ok) throw new Error("API error: " + resp.status);
        const data = await resp.json();
        renderResults(data);
    } catch (err) {
        resultsEl.innerHTML = `<div class="loading-indicator" style="color:var(--team1)">Error: ${err.message}</div>`;
    } finally {
        analyzeBtn.disabled = false;
    }
});

/* ---- Render results ---- */
function renderResults(data) {
    resultsEl.innerHTML = "";
    resultsEl.appendChild(buildStageCard(data));
}

function buildStageCard(data) {
    const card = document.createElement("div");
    card.className = "stage-card";

    // Header
    const header = document.createElement("div");
    header.className = "stage-header";

    const title = document.createElement("span");
    title.className = "stage-title";
    const stageLabels = { cavalry: "Cavalry Matchup", ranged: "Ranged Matchup", infantry: "Infantry Matchup" };
    title.textContent = stageLabels[data.stage] || data.stage;

    const adv = document.createElement("span");
    adv.className = "stage-advantage " + data.advantage;
    if (data.advantage === "team1") {
        adv.textContent = "Team 1 +" + data.advantage_margin.toFixed(1);
    } else if (data.advantage === "team2") {
        adv.textContent = "Team 2 +" + data.advantage_margin.toFixed(1);
    } else {
        adv.textContent = "Even";
    }

    header.appendChild(title);
    header.appendChild(adv);
    card.appendChild(header);

    // Columns
    const cols = document.createElement("div");
    cols.className = "stage-columns";
    cols.appendChild(buildTeamColumn("Team 1", "team1", data.team1));
    cols.appendChild(buildTeamColumn("Team 2", "team2", data.team2));
    card.appendChild(cols);

    // Footer — civs with no above-median units
    const t1Above = new Set(data.team1.above_median_units.map(u => u.civ));
    const t2Above = new Set(data.team2.above_median_units.map(u => u.civ));
    const t1Missing = data.team1.civs.filter(c => !t1Above.has(c));
    const t2Missing = data.team2.civs.filter(c => !t2Above.has(c));

    if (t1Missing.length || t2Missing.length) {
        const footer = document.createElement("div");
        footer.className = "stage-footer";
        const parts = [];
        if (t1Missing.length) parts.push("Team 1: " + t1Missing.join(", "));
        if (t2Missing.length) parts.push("Team 2: " + t2Missing.join(", "));
        footer.textContent = "No above-median cavalry: " + parts.join(" | ");
        card.appendChild(footer);
    }

    return card;
}

function buildTeamColumn(label, teamClass, teamData) {
    const col = document.createElement("div");

    const hdr = document.createElement("div");
    hdr.className = "stage-column-header " + teamClass;
    hdr.textContent = label + " (+" + teamData.total_delta.toFixed(1) + " total)";
    col.appendChild(hdr);

    if (teamData.above_median_units.length === 0) {
        const msg = document.createElement("div");
        msg.className = "no-units-msg";
        msg.textContent = "No above-median units in this category";
        col.appendChild(msg);
        return col;
    }

    teamData.above_median_units.forEach(unit => {
        const entry = document.createElement("div");
        entry.className = "unit-entry";

        const img = document.createElement("img");
        img.className = "civ-emblem";
        img.src = civEmblemUrl(unit.civ);
        img.alt = unit.civ;

        const info = document.createElement("div");
        info.className = "unit-entry-info";
        info.innerHTML = `<div class="unit-entry-name">${formatUnitName(unit.unit_slug)}</div>`
            + `<div class="unit-entry-civ">${unit.civ}</div>`;

        const stats = document.createElement("div");
        stats.className = "unit-entry-stats";
        stats.innerHTML = `<div class="unit-entry-score">${unit.score.toFixed(1)}</div>`
            + `<div class="unit-entry-meta">Rank #${unit.rank} | +${unit.median_delta.toFixed(1)}</div>`;

        entry.appendChild(img);
        entry.appendChild(info);
        entry.appendChild(stats);
        col.appendChild(entry);
    });

    return col;
}
```

**Step 2: Commit**

```bash
git add webapp/static/js/team_analysis.js
git commit -m "feat: add team_analysis.js with civ picker and results rendering"
```

---

### Task 8: End-to-end verification

**Step 1: Start the server**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 app.py --port 5050
```

**Step 2: Verify in browser**

1. Open http://localhost:5050/team-analysis
2. Verify "Team Analysis" tab is active in nav
3. Pick 4 civs for each team (e.g., Team 1: Franks, Persians, Mongols, Huns; Team 2: Aztecs, Celts, Japanese, Byzantines)
4. Click "Analyze Teams"
5. Verify the cavalry matchup stage card renders with:
   - Correct advantage indicator
   - Above-median units listed per team with scores, ranks, deltas
   - Footer showing civs without above-median cavalry

**Step 3: Verify API response shape**

```bash
curl "http://localhost:5050/api/team-analysis?team1=Franks,Persians,Mongols,Huns&team2=Aztecs,Celts,Japanese,Byzantines&stage=cavalry" | python3 -m json.tool
```

Verify: JSON structure matches design doc. `advantage` is set. `above_median_units` are sorted by score desc.

**Step 4: Test edge cases**

- Both teams pick cavalry-strong civs (e.g., Franks, Huns, Mongols, Lithuanians vs Berbers, Teutons, Persians, Burmese)
- Both teams pick infantry-focused civs (few above-median cavalry units expected)
- Error case: submit fewer than 4 civs per team (should get 400 error)

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A && git commit -m "fix: end-to-end fixes for team analysis"
```
