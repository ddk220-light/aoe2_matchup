# Matchup Advisor Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 4-phase simulation-heavy matchup advisor with a fast, pre-computed power-units display backed by `best_units.py`.

**Architecture:** The pre-computed `civ_power_units.json` (enriched with summary stats at build time) serves Phase A instantly. Phase B matchup recommendations load asynchronously via the existing `/api/matchup-recommendations` endpoint. The old simulation-based pipeline (`_run_matchup_analysis`, `_run_army_sims`, and ~6 helper functions) is deleted from `app.py`.

**Tech Stack:** Python/Flask backend, vanilla JS frontend, existing CSS variable system.

---

### Task 1: Enrich `civ_power_units.json` with unit stats

**Files:**
- Modify: `webapp/best_units.py:44-145` (the `compute_civ_power_units` function)

**Step 1: Add stat enrichment after each role query**

In `compute_civ_power_units()`, after finding the best unit per role (line ~82-93), join `ref_units` to fetch stats. Add a helper `_fetch_unit_stats` at the top of the function block.

After line 16 (`return conn`), add:

```python
def _fetch_unit_stats(conn, civ_name, unit_slug, age="Imperial"):
    """Fetch summary stats for a unit from ref_units."""
    rc = conn.cursor()
    rc.execute(
        """SELECT unit_name, final_hp, final_attack, final_melee_armor,
                  final_pierce_armor, final_speed, final_range,
                  final_cost_food, final_cost_wood, final_cost_gold
           FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?""",
        (civ_name, unit_slug, age),
    )
    row = rc.fetchone()
    if not row:
        return None, None
    stats = {
        "hp": row["final_hp"],
        "attack": row["final_attack"],
        "melee_armor": row["final_melee_armor"],
        "pierce_armor": row["final_pierce_armor"],
        "speed": row["final_speed"],
        "range": row["final_range"] or 0,
        "cost_food": row["final_cost_food"] or 0,
        "cost_wood": row["final_cost_wood"] or 0,
        "cost_gold": row["final_cost_gold"] or 0,
    }
    return row["unit_name"], stats
```

Then in the loop body where `power_units[role_key]` is assigned (line ~85-93), enrich each entry:

Change:
```python
if row:
    strength = _classify_strength(row["rank"], row["median_delta"])
    power_units[role_key] = {
        "unit_slug": row["unit_slug"],
        "line_slug": row["line_slug"],
        "score": round(row["score_value"], 1),
        "rank": row["rank"],
        "median_delta": round(row["median_delta"], 1),
        "is_signature": strength == "signature",
        "strength": strength,
    }
```

To:
```python
if row:
    strength = _classify_strength(row["rank"], row["median_delta"])
    unit_name, stats = _fetch_unit_stats(conn, civ, row["unit_slug"], db_age)
    power_units[role_key] = {
        "unit_slug": row["unit_slug"],
        "unit_name": unit_name or row["unit_slug"],
        "line_slug": row["line_slug"],
        "score": round(row["score_value"], 1),
        "rank": row["rank"],
        "median_delta": round(row["median_delta"], 1),
        "is_signature": strength == "signature",
        "strength": strength,
        "stats": stats,
    }
```

where `db_age` is `"Imperial"` (derived from the `age_key` loop variable — set `db_age = "Imperial" if age_key == "imperial" else "Castle"` at the top of the age loop).

Apply the same enrichment to the trash unit block (lines ~115-125).

**Step 2: Rebuild `civ_power_units.json`**

Run: `cd webapp && source ../venv/bin/activate && python3 best_units.py`
Expected: `Wrote .../civ_power_units.json (50 civs)`

**Step 3: Verify the enriched JSON**

Run: `python3 -c "import json; d=json.load(open('webapp/civ_power_units.json')); e=d['Franks']['imperial']['power_units']['cavalry']; print(e['unit_name'], e['stats'])"`
Expected: Something like `Paladin {'hp': 192, 'attack': 22, ...}` (Frankish Paladin with HP bonus).

**Step 4: Commit**

```bash
git add webapp/best_units.py webapp/civ_power_units.json
git commit -m "feat: enrich civ_power_units.json with unit stats and names"
```

---

### Task 2: Delete old matchup advisor backend code from `app.py`

**Files:**
- Modify: `webapp/app.py`

**Step 1: Delete the old matchup advisor helper functions and endpoints**

Delete these contiguous blocks from `app.py`:

1. Lines 1054-1570: The `# ============== Matchup Advisor ==============` section containing:
   - `_MOBILE_SPEED_THRESHOLD`, `_SIEGE_CLASSES`, `_ADVISOR_EXCLUDED` constants
   - `_categorize_units()`
   - `_find_clear_winner_and_scores()`
   - `_find_best_counter()`
   - `_build_combos_for_civ()`
   - `_run_army_sims()`

2. Lines 1685-2102: `_run_matchup_analysis()` function

3. Lines 2105-2114: `/api/matchup-advisor/analysis/<civ1>/<civ2>` endpoint

4. Lines 2117-2253: `/api/matchup-advisor/army/<civ1>/<civ2>` endpoint

**Keep:**
- The `/matchup-advisor` route (line 1573-1577) — the page route
- `_build_combat_dict_from_ref()` (line 336) — used by `/api/ref/combat-unit`
- `/api/civ-power-units/<civ_name>` (line 2256)
- `/api/matchup-recommendations/<civ_a>/<civ_b>` (line 2272)
- `AGES` dict (line 17) — used by civ detail page

**Step 2: Verify the server still starts**

Run: `cd webapp && source ../venv/bin/activate && python3 -c "from app import app; print('OK')"`
Expected: `OK`

**Step 3: Verify kept endpoints still work**

Run: `cd webapp && source ../venv/bin/activate && python3 -c "from app import app; c=app.test_client(); r=c.get('/api/civ-power-units/Franks'); print(r.status_code, 'power_units' in r.get_json())"`
Expected: `200 True`

**Step 4: Commit**

```bash
git add webapp/app.py
git commit -m "refactor: remove old 4-phase matchup advisor backend"
```

---

### Task 3: Rewrite `matchup.js` for power-units display

**Files:**
- Rewrite: `webapp/static/js/matchup.js`

**Step 1: Write the new JS**

Replace the entire contents of `matchup.js` with the new implementation. The civ selector logic (lines 1-77 of the old file) is reused with minor tweaks. Everything from line 79 onward is replaced.

The new JS must:

1. **Keep the civ selector** (CIVS grid, onCivClick, updateGrid) — copy from old file
2. **On "Analyze Matchup" click**: fetch both civs' power units in parallel via `/api/civ-power-units/<civ>`
3. **Render `renderPowerUnits(civ1Data, civ2Data, civ1Name, civ2Name)`**: builds a side-by-side grid with 6 role rows
4. **Each unit cell**: icon + name (linked to `/?line=<line_slug>`), strength badge, rank text. Wrapped in a `.unit-cell` with a `.tooltip` child containing stats.
5. **Fire Phase B** (`/api/matchup-recommendations/<civ_a>/<civ_b>`) in background
6. **`renderRecommendations(data)`**: appends a section below the grid when Phase B returns

Key constants for the role display:
```javascript
const ROLE_ORDER = ["cavalry", "ranged", "infantry", "anti_cavalry", "trash", "siege"];
const ROLE_LABELS = {
    cavalry: "Cavalry",
    ranged: "Ranged",
    infantry: "Infantry",
    anti_cavalry: "Anti-Cavalry",
    trash: "Trash",
    siege: "Siege",
};
const LINE_TO_RANKINGS = {
    stable: "stable",
    archer: "archery",
    cav_archer: "archery",
    scorpion: "archery",
    gunpowder: "archery",
    skirmisher: "archery",
    militia: "infantry",
    shock_infantry: "infantry",
    spear: "infantry",
    siege: "siege",
};
const STRENGTH_COLORS = {
    signature: { bg: "rgba(201, 168, 76, 0.2)", text: "var(--gold)", label: "Signature" },
    strong: { bg: "rgba(46, 204, 113, 0.15)", text: "#2ecc71", label: "Strong" },
    average: { bg: "rgba(255, 255, 255, 0.05)", text: "var(--text-muted)", label: "Average" },
    weak: { bg: "rgba(231, 76, 60, 0.15)", text: "#e74c3c", label: "Weak" },
};
```

Unit cell HTML structure:
```javascript
function unitCellHtml(entry, civColor) {
    if (!entry) return `<div class="unit-cell empty">—</div>`;
    const s = entry.stats || {};
    const iconUrl = getIconUrl(entry.unit_name);
    const rankingsLine = LINE_TO_RANKINGS[entry.line_slug] || "infantry";
    const str = STRENGTH_COLORS[entry.strength] || STRENGTH_COLORS.average;
    const deltaSign = entry.median_delta > 0 ? "+" : "";
    const iconImg = iconUrl
        ? `<img src="${iconUrl}" class="unit-icon sm" width="28" height="28" alt="${entry.unit_name}" onerror="this.style.display='none'">`
        : '';
    return `
        <div class="unit-cell" style="border-left: 3px solid ${str.text}">
            <a href="/?line=${rankingsLine}" class="unit-link">
                ${iconImg}
                <span class="unit-cell-name">${entry.unit_name}</span>
            </a>
            <span class="strength-badge" style="background:${str.bg};color:${str.text}">${str.label}</span>
            <span class="rank-text">#${entry.rank}</span>
            <div class="unit-tooltip">
                <div class="tooltip-header">${entry.unit_name}</div>
                <div class="tooltip-stats">
                    <span>HP: ${s.hp || '?'}</span>
                    <span>Atk: ${s.attack || '?'}</span>
                    <span>MA: ${s.melee_armor || 0}</span>
                    <span>PA: ${s.pierce_armor || 0}</span>
                    <span>Spd: ${s.speed || '?'}</span>
                    ${s.range ? `<span>Rng: ${s.range}</span>` : ''}
                </div>
                <div class="tooltip-cost">
                    ${s.cost_food ? `<span class="cost-food">${s.cost_food}F</span>` : ''}
                    ${s.cost_wood ? `<span class="cost-wood">${s.cost_wood}W</span>` : ''}
                    ${s.cost_gold ? `<span class="cost-gold">${s.cost_gold}G</span>` : ''}
                </div>
                <div class="tooltip-score">
                    Score: ${entry.score} (${deltaSign}${entry.median_delta} vs median)
                </div>
            </div>
        </div>`;
}
```

Main render function:
```javascript
function renderPowerUnits(c1, c2, name1, name2) {
    const pu1 = c1.power_units;
    const pu2 = c2.power_units;

    let html = `
        <div class="matchup-header">
            <h2><span class="civ1-color">${name1}</span>
                <span style="color:var(--text-muted)">vs</span>
                <span class="civ2-color">${name2}</span></h2>
        </div>
        <div class="power-grid">
            <div class="power-grid-header">
                <div class="role-col">Role</div>
                <div class="civ-col civ1-color">${name1}</div>
                <div class="civ-col civ2-color">${name2}</div>
            </div>`;

    for (const role of ROLE_ORDER) {
        const label = ROLE_LABELS[role];
        html += `
            <div class="power-grid-row">
                <div class="role-col">${label}</div>
                <div class="civ-col">${unitCellHtml(pu1[role], "civ1")}</div>
                <div class="civ-col">${unitCellHtml(pu2[role], "civ2")}</div>
            </div>`;
    }

    html += `</div>`;
    html += `<div id="recommendations-section"></div>`;
    return html;
}
```

Phase B render:
```javascript
function renderRecommendations(data) {
    const el = document.getElementById("recommendations-section");
    if (!el || data.error) return;

    const comps = data.recommended_compositions || [];
    if (comps.length === 0) {
        el.innerHTML = '';
        return;
    }

    let html = `<div class="recs-section">
        <div class="recs-header">Recommended Compositions for ${data.civ_a} vs ${data.civ_b}</div>
        <div class="recs-cards">`;

    for (const comp of comps) {
        const goldName = comp.gold_unit?.unit_slug?.replace(/_/g, ' ') || '?';
        const trashName = comp.trash_unit?.unit_slug?.replace(/_/g, ' ') || '?';
        html += `
            <div class="rec-card">
                <div class="rec-rank">#${comp.rank}</div>
                <div class="rec-units">
                    <span class="rec-gold">${goldName}</span>
                    <span class="combo-plus">+</span>
                    <span class="rec-trash">${trashName}</span>
                </div>
                <div class="rec-reasoning">${comp.reasoning || ''}</div>
                <div class="rec-scores">
                    Res: ${comp.scores?.resource_efficiency || '?'} | Pop: ${comp.scores?.pop_efficiency || '?'}
                </div>
            </div>`;
    }

    html += `</div></div>`;
    el.innerHTML = html;
    el.classList.add("visible");
}
```

Analyze button handler:
```javascript
analyzeBtn.addEventListener("click", async () => {
    const c1 = selectedCiv1, c2 = selectedCiv2;
    if (!c1 || !c2 || c1 === c2) return;
    analyzeBtn.disabled = true;

    resultsEl.className = "results-container visible";
    resultsEl.innerHTML = `<div class="loading-spinner"><div class="spinner"></div><div>Loading power units...</div></div>`;

    try {
        const [r1, r2] = await Promise.all([
            fetch(`/api/civ-power-units/${encodeURIComponent(c1)}`).then(r => r.json()),
            fetch(`/api/civ-power-units/${encodeURIComponent(c2)}`).then(r => r.json()),
        ]);

        if (r1.error || r2.error) throw new Error(r1.error || r2.error);

        resultsEl.innerHTML = renderPowerUnits(r1, r2, c1, c2);

        // Phase B in background
        fetch(`/api/matchup-recommendations/${encodeURIComponent(c1)}/${encodeURIComponent(c2)}`)
            .then(r => r.json())
            .then(data => renderRecommendations(data))
            .catch(() => {});
    } catch (e) {
        resultsEl.innerHTML = `<div class="no-data">Error: ${e.message}</div>`;
    } finally {
        analyzeBtn.disabled = false;
    }
});
```

**Step 2: Verify the page loads without JS errors**

Start server and open `/matchup-advisor` in browser. Select two civs and click Analyze.
Expected: Side-by-side power units grid renders instantly, recommendations slide in after ~1-2s.

**Step 3: Commit**

```bash
git add webapp/static/js/matchup.js
git commit -m "feat: rewrite matchup.js for power-units display"
```

---

### Task 4: Update `matchup.css` for new layout

**Files:**
- Modify: `webapp/static/css/matchup.css`

**Step 1: Replace the results section styles**

Keep lines 1-143 (civ selector, selected display, compare button, responsive) unchanged.

Replace everything from line 145 onward (results container through end of file) with new styles for the power grid, unit cells, tooltips, strength badges, and recommendations section.

New styles to add after line 143:

```css
/* --- Results --- */
.results-container { display: none; }
.results-container.visible { display: block; }

.matchup-header {
    text-align: center;
    margin-bottom: 24px;
    padding: 16px;
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
}
.matchup-header h2 { font-size: 1.6rem; margin: 0; }
.civ1-color { color: var(--team1); }
.civ2-color { color: var(--team2); }

/* --- Power Grid --- */
.power-grid {
    max-width: 900px;
    margin: 0 auto;
}
.power-grid-header, .power-grid-row {
    display: grid;
    grid-template-columns: 120px 1fr 1fr;
    gap: 12px;
    align-items: center;
}
.power-grid-header {
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 8px;
}
.power-grid-header .role-col { color: var(--text-dim); }
.power-grid-row {
    padding: 10px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.power-grid-row .role-col {
    font-size: 0.85rem;
    color: var(--gold);
    font-weight: 600;
}

/* --- Unit Cell --- */
.unit-cell {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(255,255,255,0.03);
    position: relative;
    transition: background 0.2s;
}
.unit-cell:hover { background: rgba(255,255,255,0.08); }
.unit-cell.empty {
    color: var(--text-dim);
    font-style: italic;
    border-left: 3px solid transparent;
}
.unit-link {
    display: flex;
    align-items: center;
    gap: 6px;
    text-decoration: none;
    color: var(--text);
    flex: 1;
    min-width: 0;
}
.unit-link:hover { color: var(--gold); }
.unit-cell-name {
    font-size: 0.85rem;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.strength-badge {
    font-size: 0.65rem;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 8px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    white-space: nowrap;
}
.rank-text {
    font-size: 0.7rem;
    color: var(--text-dim);
    white-space: nowrap;
}

/* --- Tooltip (CSS hover) --- */
.unit-tooltip {
    display: none;
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-card, #1a1a2e);
    border: 1px solid rgba(201,168,76,0.3);
    border-radius: 10px;
    padding: 12px 14px;
    min-width: 200px;
    z-index: 100;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    pointer-events: none;
}
.unit-cell:hover .unit-tooltip { display: block; }
.tooltip-header {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--gold);
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.tooltip-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 12px;
    font-size: 0.8rem;
    color: var(--text);
    margin-bottom: 6px;
}
.tooltip-cost {
    display: flex;
    gap: 8px;
    font-size: 0.8rem;
    margin-bottom: 6px;
}
.cost-food { color: #e74c3c; }
.cost-wood { color: #8B4513; }
.cost-gold { color: var(--gold); }
.tooltip-score {
    font-size: 0.75rem;
    color: var(--text-muted);
    padding-top: 6px;
    border-top: 1px solid rgba(255,255,255,0.06);
}

/* --- Recommendations Section --- */
#recommendations-section {
    max-width: 900px;
    margin: 24px auto 0;
    opacity: 0;
    transition: opacity 0.4s ease;
}
#recommendations-section.visible { opacity: 1; }
.recs-section {
    background: rgba(255,255,255,0.05);
    border-radius: 12px;
    padding: 20px;
}
.recs-header {
    font-size: 1.1rem;
    color: var(--gold);
    font-weight: 600;
    margin-bottom: 16px;
    text-align: center;
}
.recs-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}
@media (max-width: 768px) {
    .power-grid-header, .power-grid-row {
        grid-template-columns: 80px 1fr 1fr;
        gap: 8px;
    }
    .recs-cards { grid-template-columns: 1fr; }
}
.rec-card {
    padding: 14px;
    background: rgba(0,0,0,0.2);
    border-radius: 8px;
    border-left: 3px solid var(--gold);
}
.rec-rank {
    font-size: 0.75rem;
    color: var(--text-dim);
    margin-bottom: 4px;
}
.rec-units {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
    margin-bottom: 6px;
}
.rec-gold { color: var(--gold); }
.rec-trash { color: var(--text-muted); }
.rec-reasoning {
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.4;
    margin-bottom: 4px;
}
.rec-scores {
    font-size: 0.75rem;
    color: var(--text-dim);
}

/* --- Loading / No-data --- */
.loading-spinner {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 30px;
    color: var(--text-muted);
}
.loading-spinner .spinner {
    width: 32px; height: 32px;
    border: 3px solid rgba(201,168,76,0.2);
    border-top-color: var(--gold);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 10px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.no-data {
    color: var(--text-dim);
    font-style: italic;
    padding: 20px;
    text-align: center;
}
```

**Step 2: Verify styles render correctly**

Open `/matchup-advisor`, select two civs, click Analyze. Check:
- Grid alignment, tooltips appear on hover above the cell, badges are colored by strength.
- Responsive: shrinks on mobile widths.

**Step 3: Commit**

```bash
git add webapp/static/css/matchup.css
git commit -m "feat: update matchup.css for power-units grid layout"
```

---

### Task 5: Smoke test the full flow

**Files:** None (testing only)

**Step 1: Start the server**

Run: `cd webapp && source ../venv/bin/activate && python3 app.py --port 5001`

**Step 2: Test Phase A API**

Run: `curl -s http://localhost:5001/api/civ-power-units/Franks | python3 -m json.tool | head -30`
Expected: JSON with `power_units` containing `unit_name` and `stats` fields.

**Step 3: Test Phase B API**

Run: `curl -s http://localhost:5001/api/matchup-recommendations/Franks/Byzantines | python3 -m json.tool | head -40`
Expected: JSON with `recommended_compositions` array.

**Step 4: Test the page**

Open `http://localhost:5001/matchup-advisor` in browser:
1. Select Franks vs Byzantines
2. Click "Analyze Matchup"
3. Verify: power grid renders instantly with 6 role rows
4. Hover over a unit: tooltip shows stats
5. Click a unit name: navigates to rankings page
6. Wait ~1-2s: recommendations section slides in below

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: matchup advisor smoke test fixes"
```
