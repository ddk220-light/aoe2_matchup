# Team Analysis Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand team analysis from cavalry-only to cavalry+infantry+ranged+siege with tabbed sub-category breakdowns per stage card.

**Architecture:** Extend `TEAM_ANALYSIS_STAGES` to hold per-stage `line_slugs` (list) and `tabs` (OrderedDict of sub-categories). API gains a `tab` query param and returns `available_tabs`. Frontend fetches all 4 stages in parallel on Analyze, renders tab bars in each stage card, and re-fetches on tab click.

**Tech Stack:** Flask (Python), vanilla JS, CSS. SQLite battle_scores table (pre-computed, no changes needed).

---

### Task 1: Expand TEAM_ANALYSIS_STAGES constant

**Files:**
- Modify: `webapp/app.py:777-783`

**Step 1: Replace `TEAM_ANALYSIS_STAGES`**

Replace lines 777-783 in `webapp/app.py`:

```python
# Stage-to-query mapping for team analysis
TEAM_ANALYSIS_STAGES = {
    "cavalry": {"line_slug": "stable", "score_type": "stable_effectiveness"},
    # Future stages:
    # "ranged": {"line_slug": "archery", "score_type": "ranged_effectiveness"},
    # "infantry": {"line_slug": "infantry", "score_type": "militia_value"},
}
```

With:

```python
# Stage-to-query mapping for team analysis
# Each stage has line_slugs (list of DB line_slug values to query) and tabs
# (ordered dict of sub-category breakdowns, each mapping to a score_type).
TEAM_ANALYSIS_STAGES = {
    "cavalry": {
        "line_slugs": ["stable"],
        "tabs": {
            "overall":        {"score_type": "stable_effectiveness", "label": "Overall"},
            "general_combat": {"score_type": "general_combat",       "label": "General Combat"},
            "anti_cav":       {"score_type": "anti_cav",             "label": "Anti-Cav"},
        },
    },
    "infantry": {
        "line_slugs": ["militia", "spear", "shock_infantry"],
        "tabs": {
            "overall":        {"score_type": "militia_value",    "label": "Overall"},
            "general_combat": {"score_type": "general_combat",   "label": "General Combat"},
            "anti_cav":       {"score_type": "anti_cav",         "label": "Anti-Cav"},
            "raiding":        {"score_type": "raiding_value",    "label": "Raiding"},
        },
    },
    "ranged": {
        "line_slugs": ["archer", "skirmisher", "cav_archer", "scorpion", "gunpowder"],
        "tabs": {
            "overall":        {"score_type": "ranged_effectiveness", "label": "Overall"},
            "general_combat": {"score_type": "general_combat",       "label": "General Combat"},
            "anti_archer":    {"score_type": "anti_archer",          "label": "Anti-Archer"},
            "mobility":       {"score_type": "mobility_score",       "label": "Mobility"},
        },
    },
    "siege": {
        "line_slugs": ["siege"],
        "tabs": {
            "overall":      {"score_type": "anti_building_score", "label": "Overall"},
            "time_to_kill": {"score_type": "time_to_kill",        "label": "Time to Kill"},
        },
    },
}
```

Note: Python 3.7+ dicts are insertion-ordered, so no need for `OrderedDict`.

**Step 2: Commit**

```bash
git add webapp/app.py
git commit -m "feat(team-analysis): expand TEAM_ANALYSIS_STAGES to 4 stages with tabs"
```

---

### Task 2: Update `/api/team-analysis` endpoint

**Files:**
- Modify: `webapp/app.py:1555-1634`

**Step 1: Update the endpoint to support `tab` param and multi-line queries**

Replace the entire `api_team_analysis()` function (lines 1555-1634) with:

```python
@app.route("/api/team-analysis")
def api_team_analysis():
    """Team analysis: compare two teams' strength in a given stage/tab."""
    team1_raw = request.args.get("team1", "")
    team2_raw = request.args.get("team2", "")
    stage = request.args.get("stage", "cavalry")
    tab = request.args.get("tab", "overall")
    age = request.args.get("age", "Imperial")

    if stage not in TEAM_ANALYSIS_STAGES:
        return jsonify({"error": f"Unknown stage: {stage}"}), 400

    stage_cfg = TEAM_ANALYSIS_STAGES[stage]
    tabs = stage_cfg["tabs"]

    if tab not in tabs:
        return jsonify({"error": f"Unknown tab '{tab}' for stage '{stage}'"}), 400

    team1_civs = [c.strip() for c in team1_raw.split(",") if c.strip()]
    team2_civs = [c.strip() for c in team2_raw.split(",") if c.strip()]

    if len(team1_civs) != 4 or len(team2_civs) != 4:
        return jsonify({"error": "Each team must have exactly 4 civs"}), 400

    line_slugs = stage_cfg["line_slugs"]
    score_type = tabs[tab]["score_type"]

    ref_conn = get_ref_db()
    rc = ref_conn.cursor()

    # Build line_slug IN clause
    ls_placeholders = ",".join("?" for _ in line_slugs)

    # Get median for this group
    rc.execute(
        f"SELECT score_value, median_delta FROM battle_scores WHERE line_slug IN ({ls_placeholders}) AND age=? AND score_type=? LIMIT 1",
        line_slugs + [age, score_type],
    )
    sample = rc.fetchone()
    if not sample:
        ref_conn.close()
        return jsonify({"error": "No scores found for this stage/tab/age"}), 404
    median = round(sample["score_value"] - sample["median_delta"], 4)

    def get_team_data(civs):
        civ_placeholders = ",".join("?" for _ in civs)
        rc.execute(
            f"""SELECT civ_name, unit_slug, score_value, rank, median_delta
                FROM battle_scores
                WHERE line_slug IN ({ls_placeholders}) AND age=? AND score_type=?
                  AND civ_name IN ({civ_placeholders})
                  AND median_delta > 0
                ORDER BY score_value DESC""",
            line_slugs + [age, score_type] + civs,
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
        "tab": tab,
        "tab_label": tabs[tab]["label"],
        "available_tabs": [{"key": k, "label": v["label"]} for k, v in tabs.items()],
        "age": age,
        "score_type": score_type,
        "median": round(median, 1),
        "team1": t1,
        "team2": t2,
        "advantage": advantage,
        "advantage_margin": round(abs(t1["total_delta"] - t2["total_delta"]), 1),
    })
```

**Step 2: Verify with curl**

```bash
# Test cavalry overall (same as before, should still work)
curl -s "http://localhost:PORT/api/team-analysis?team1=Franks,Persians,Huns,Mongols&team2=Aztecs,Celts,Japanese,Byzantines&stage=cavalry" | python3 -m json.tool | head -20

# Test infantry with anti_cav tab
curl -s "http://localhost:PORT/api/team-analysis?team1=Aztecs,Japanese,Celts,Byzantines&team2=Franks,Persians,Huns,Mongols&stage=infantry&tab=anti_cav" | python3 -m json.tool | head -20

# Test invalid tab
curl -s "http://localhost:PORT/api/team-analysis?team1=Franks,Persians,Huns,Mongols&team2=Aztecs,Celts,Japanese,Byzantines&stage=cavalry&tab=invalid"
# Expected: {"error": "Unknown tab 'invalid' for stage 'cavalry'"}
```

**Step 3: Commit**

```bash
git add webapp/app.py
git commit -m "feat(team-analysis): update API for tab param and multi-line queries"
```

---

### Task 3: Add tab bar CSS styles

**Files:**
- Modify: `webapp/static/css/team_analysis.css`

**Step 1: Add tab styles after the `.stage-header` rules (after line 199)**

Insert after the `.stage-advantage.even` block:

```css
/* --- Stage Tabs (sub-category breakdown) --- */
.stage-tabs {
    display: flex;
    gap: 0;
    margin-bottom: 16px;
    border-bottom: 2px solid var(--border);
    overflow-x: auto;
}
.stage-tab {
    padding: 8px 16px;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: color 0.2s, border-color 0.2s;
    white-space: nowrap;
    background: none;
    border-top: none;
    border-left: none;
    border-right: none;
    font-family: inherit;
}
.stage-tab:hover {
    color: var(--text);
}
.stage-tab.active {
    color: var(--gold);
    border-bottom-color: var(--gold);
}
```

**Step 2: Commit**

```bash
git add webapp/static/css/team_analysis.css
git commit -m "feat(team-analysis): add tab bar CSS styles"
```

---

### Task 4: Rewrite frontend JS for multi-stage + tabs

**Files:**
- Modify: `webapp/static/js/team_analysis.js`

**Step 1: Replace the entire analysis/rendering section**

The team picker code (lines 1-114) stays the same. Replace everything from line 116 onwards (the analysis click handler and all render functions) with the following:

```javascript
/* ---- Stage labels ---- */
const STAGE_LABELS = {
    cavalry: "Cavalry Matchup",
    infantry: "Infantry Matchup",
    ranged: "Ranged Matchup",
    siege: "Siege Matchup",
};

const STAGE_ORDER = ["cavalry", "infantry", "ranged", "siege"];

/* ---- Analysis ---- */
analyzeBtn.addEventListener("click", async () => {
    resultsEl.innerHTML = '<div class="loading-indicator">Analyzing teams...</div>';
    analyzeBtn.disabled = true;

    try {
        // Fetch all 4 stages in parallel (overall tab for each)
        const fetches = STAGE_ORDER.map(stage => {
            const params = new URLSearchParams({
                team1: team1.join(","),
                team2: team2.join(","),
                stage: stage,
                tab: "overall",
            });
            return fetch("/api/team-analysis?" + params).then(r => {
                if (!r.ok) throw new Error(`${stage}: API error ${r.status}`);
                return r.json();
            });
        });

        const results = await Promise.all(fetches);
        renderAllResults(results);
    } catch (err) {
        resultsEl.innerHTML = `<div class="loading-indicator" style="color:var(--team1)">Error: ${err.message}</div>`;
    } finally {
        analyzeBtn.disabled = false;
    }
});

/* ---- Render all stage cards ---- */
function renderAllResults(resultsArray) {
    resultsEl.innerHTML = "";
    resultsArray.forEach(data => {
        resultsEl.appendChild(buildStageCard(data));
    });
}

/* ---- Build a single stage card with tabs ---- */
function buildStageCard(data) {
    const card = document.createElement("div");
    card.className = "stage-card";
    card.dataset.stage = data.stage;

    // Header
    const header = document.createElement("div");
    header.className = "stage-header";

    const title = document.createElement("span");
    title.className = "stage-title";
    title.textContent = STAGE_LABELS[data.stage] || data.stage;

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

    // Tab bar (only if more than 1 tab)
    if (data.available_tabs && data.available_tabs.length > 1) {
        const tabBar = document.createElement("div");
        tabBar.className = "stage-tabs";

        data.available_tabs.forEach(tabInfo => {
            const btn = document.createElement("button");
            btn.className = "stage-tab" + (tabInfo.key === data.tab ? " active" : "");
            btn.textContent = tabInfo.label;
            btn.dataset.tab = tabInfo.key;

            btn.addEventListener("click", async () => {
                if (btn.classList.contains("active")) return;

                // Mark active
                tabBar.querySelectorAll(".stage-tab").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");

                // Fetch new tab data
                const params = new URLSearchParams({
                    team1: team1.join(","),
                    team2: team2.join(","),
                    stage: data.stage,
                    tab: tabInfo.key,
                });

                try {
                    const body = card.querySelector(".stage-body");
                    body.innerHTML = '<div class="loading-indicator">Loading...</div>';

                    const resp = await fetch("/api/team-analysis?" + params);
                    if (!resp.ok) throw new Error("API error: " + resp.status);
                    const tabData = await resp.json();

                    // Update advantage indicator
                    const advEl = card.querySelector(".stage-advantage");
                    advEl.className = "stage-advantage " + tabData.advantage;
                    if (tabData.advantage === "team1") {
                        advEl.textContent = "Team 1 +" + tabData.advantage_margin.toFixed(1);
                    } else if (tabData.advantage === "team2") {
                        advEl.textContent = "Team 2 +" + tabData.advantage_margin.toFixed(1);
                    } else {
                        advEl.textContent = "Even";
                    }

                    // Re-render body
                    body.innerHTML = "";
                    body.appendChild(buildStageBody(tabData));
                } catch (err) {
                    const body = card.querySelector(".stage-body");
                    body.innerHTML = `<div class="loading-indicator" style="color:var(--team1)">Error: ${err.message}</div>`;
                }
            });

            tabBar.appendChild(btn);
        });

        card.appendChild(tabBar);
    }

    // Body wrapper
    const body = document.createElement("div");
    body.className = "stage-body";
    body.appendChild(buildStageBody(data));
    card.appendChild(body);

    return card;
}

/* ---- Build stage body (columns + footer) ---- */
function buildStageBody(data) {
    const frag = document.createDocumentFragment();

    // Columns
    const cols = document.createElement("div");
    cols.className = "stage-columns";
    cols.appendChild(buildTeamColumn("Team 1", "team1", data.team1));
    cols.appendChild(buildTeamColumn("Team 2", "team2", data.team2));
    frag.appendChild(cols);

    // Footer — civs with no above-median units
    const t1Above = new Set(data.team1.above_median_units.map(u => u.civ));
    const t2Above = new Set(data.team2.above_median_units.map(u => u.civ));
    const t1Missing = data.team1.civs.filter(c => !t1Above.has(c));
    const t2Missing = data.team2.civs.filter(c => !t2Above.has(c));

    if (t1Missing.length || t2Missing.length) {
        const footer = document.createElement("div");
        footer.className = "stage-footer";
        const stageName = (STAGE_LABELS[data.stage] || data.stage).replace(" Matchup", "").toLowerCase();
        const parts = [];
        if (t1Missing.length) parts.push("Team 1: " + t1Missing.join(", "));
        if (t2Missing.length) parts.push("Team 2: " + t2Missing.join(", "));
        footer.textContent = "No above-median " + stageName + ": " + parts.join(" | ");
        frag.appendChild(footer);
    }

    return frag;
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
git commit -m "feat(team-analysis): multi-stage fetch with tab switching"
```

---

### Task 5: Manual verification

**Step 1: Start the webapp**

```bash
cd webapp && source ../venv/bin/activate && python3 app.py --port 5050
```

**Step 2: Open in browser and verify**

Navigate to `http://localhost:5050/team-analysis`. Verify:

1. Pick 4 civs per team, click Analyze
2. **4 stage cards** appear (Cavalry, Infantry, Ranged, Siege)
3. Each card shows tab bar with sub-categories
4. Clicking a tab (e.g., Anti-Cav on Infantry) fetches and re-renders that card's body
5. Advantage indicator updates per tab
6. Footer shows correct stage name (e.g., "No above-median infantry" not "cavalry")
7. Mobile: test at narrow width — tabs overflow-x scroll, columns stack

**Step 3: Final commit**

If any small fixes were needed, commit them:

```bash
git add -A
git commit -m "fix(team-analysis): polish multi-stage tab UI"
```
