# Matchup Advisor Simulation Overlay — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add live combat simulation results to the matchup advisor, showing which opponent units each civ's unit beats as small icons below the percentile bar, with highlighted exclusive wins.

**Architecture:** New `POST /api/matchup-sims` endpoint in `best_units.py` runs ~650 cross-matchup simulations on-demand (~0.8s). Frontend fires this as a background fetch after initial percentile comparison renders. Response includes win lists and highlight flags per unit. Follows existing `get_matchup_recommendations()` pattern for loading combat units and running simulations.

**Tech Stack:** Flask API (Python), vanilla JS, `simulate_battle()` from `simulation.py`

---

### Task 1: Add `get_matchup_sims()` to best_units.py

**Files:**
- Modify: `webapp/best_units.py` (after `get_matchup_recommendations()`, ~line 1060)

**What to build:**

A function `get_matchup_sims(civ_left, civ_right, age)` that:

1. Loads `civ_power_units.json` to get both civs' unit lists
2. For every unit on both sides, loads combat-ready unit via `_load_combat_unit()`
3. Runs all cross-matchups (every left unit vs every right unit, AND vice versa)
4. Applies win logic and highlight logic
5. Returns structured results

**Implementation:**

```python
def get_matchup_sims(civ_left, civ_right, age="imperial"):
    """Run cross-matchup simulations between two civs' power units.

    Returns dict with per-unit win lists and highlighted exclusive wins.
    """
    power_data = load_civ_power_units()
    if not power_data:
        return {"error": "civ_power_units.json not found"}

    data_l = power_data.get(civ_left, {}).get(age)
    data_r = power_data.get(civ_right, {}).get(age)
    if not data_l or not data_r:
        return {"error": f"No data for {civ_left} or {civ_right} in {age}"}

    db_age = "Imperial" if age == "imperial" else "Castle"

    # Collect all units from both sides
    # Each entry: {unit_slug, unit_name, civ_name, line_slug, col_key}
    def _collect_units(civ_name, age_data):
        units = []
        pu = age_data.get("power_units", {})
        for col_key in ["cavalry", "ranged", "infantry", "siege"]:
            col = pu.get(col_key, {})
            for line_slug, entries in col.items():
                if not entries:
                    continue
                for entry in entries:
                    units.append({
                        "unit_slug": entry["unit_slug"],
                        "unit_name": entry["unit_name"],
                        "line_slug": line_slug,
                        "col_key": col_key,
                        "civ_name": civ_name,
                    })
        return units

    units_l = _collect_units(civ_left, data_l)
    units_r = _collect_units(civ_right, data_r)

    # Load combat-ready versions (cache to avoid duplicate loads)
    combat_cache = {}
    def _get_cu(civ_name, unit_slug):
        key = (civ_name, unit_slug)
        if key not in combat_cache:
            combat_cache[key] = _load_combat_unit(civ_name, unit_slug, db_age)
        return combat_cache[key]

    # Run simulations: check if unit A wins against unit B
    # Win = A has >10% HP remaining in BOTH 30v30 AND 3k-resource
    def _check_win(cu_a, cu_b):
        if not cu_a or not cu_b:
            return False
        cost_a = _calc_weighted_cost(cu_a["cost_food"], cu_a["cost_wood"], cu_a["cost_gold"])
        cost_b = _calc_weighted_cost(cu_b["cost_food"], cu_b["cost_wood"], cu_b["cost_gold"])

        # 30v30
        w1, _, _, hp1_1, _ = simulate_battle(
            cu_a, cu_b, 0, fixed_count=30, return_hp=True
        )
        if w1 != 1 or hp1_1 < 0.10:
            return False

        # 3k resources
        w2, _, _, hp1_2, _ = simulate_battle(
            cu_a, cu_b, 3000, cost1_override=cost_a, cost2_override=cost_b, return_hp=True
        )
        return w2 == 1 and hp1_2 >= 0.10

    # Build wins for all left units vs all right units
    wins_l = {}  # key: unit_slug -> list of opponent unit_slugs beaten
    for ul in units_l:
        cu_a = _get_cu(ul["civ_name"], ul["unit_slug"])
        beaten = []
        for ur in units_r:
            cu_b = _get_cu(ur["civ_name"], ur["unit_slug"])
            if _check_win(cu_a, cu_b):
                beaten.append(ur["unit_slug"])
        wins_l[ul["unit_slug"]] = beaten

    # Build wins for all right units vs all left units
    wins_r = {}
    for ur in units_r:
        cu_a = _get_cu(ur["civ_name"], ur["unit_slug"])
        beaten = []
        for ul in units_l:
            cu_b = _get_cu(ul["civ_name"], ul["unit_slug"])
            if _check_win(cu_a, cu_b):
                beaten.append(ul["unit_slug"])
        wins_r[ur["unit_slug"]] = beaten

    # Highlight logic: per unit line, find exclusive wins
    # Group units by line_slug for each side
    lines_l = {}  # line_slug -> [unit_slug, ...]
    for ul in units_l:
        lines_l.setdefault(ul["line_slug"], []).append(ul["unit_slug"])
    lines_r = {}
    for ur in units_r:
        lines_r.setdefault(ur["line_slug"], []).append(ur["unit_slug"])

    def _calc_highlights(my_units_by_line, my_wins, opp_units_by_line, opp_wins):
        """For each of my units, find wins that no opponent unit in the same line achieves."""
        highlights = {}
        for line_slug, my_slugs in my_units_by_line.items():
            opp_slugs = opp_units_by_line.get(line_slug, [])
            # Collect all opponent wins for this line
            opp_combined_wins = set()
            for opp_slug in opp_slugs:
                opp_combined_wins.update(opp_wins.get(opp_slug, []))
            # For each of my units in this line
            for my_slug in my_slugs:
                my_unit_wins = set(my_wins.get(my_slug, []))
                exclusive = my_unit_wins - opp_combined_wins
                highlights[my_slug] = list(exclusive)
        return highlights

    highlights_l = _calc_highlights(lines_l, wins_l, lines_r, wins_r)
    highlights_r = _calc_highlights(lines_r, wins_r, lines_l, wins_l)

    # Build response keyed by unit_slug
    results_l = {}
    for ul in units_l:
        slug = ul["unit_slug"]
        results_l[slug] = {
            "wins": wins_l.get(slug, []),
            "highlighted": highlights_l.get(slug, []),
        }

    results_r = {}
    for ur in units_r:
        slug = ur["unit_slug"]
        results_r[slug] = {
            "wins": wins_r.get(slug, []),
            "highlighted": highlights_r.get(slug, []),
        }

    # Build a slug->name map for icon resolution on frontend
    name_map = {}
    for u in units_l + units_r:
        name_map[u["unit_slug"]] = u["unit_name"]

    return {
        "left": results_l,
        "right": results_r,
        "name_map": name_map,
    }
```

---

### Task 2: Add API endpoint in app.py

**Files:**
- Modify: `webapp/app.py` (line 6: add import, after line 1196: add endpoint)

**Changes:**

1. Update the import at line 6:

```python
from best_units import load_civ_power_units, get_matchup_recommendations, get_matchup_sims, CIVS_WITHOUT_TREBUCHET
```

2. Add the endpoint after the `api_matchup_recommendations` route (~line 1197):

```python
@app.route("/api/matchup-sims", methods=["POST"])
def api_matchup_sims():
    """Run cross-matchup simulations between two civs' power units."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    civ_left = data.get("civ_left", "")
    civ_right = data.get("civ_right", "")
    age = data.get("age", "imperial").lower()

    if not civ_left or not civ_right:
        return jsonify({"error": "civ_left and civ_right required"}), 400

    result = get_matchup_sims(civ_left, civ_right, age)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)
```

---

### Task 3: Update matchup_advisor.js — background sim fetch and rendering

**Files:**
- Modify: `webapp/static/js/matchup_advisor.js`

**Changes:**

1. Add a state variable for sim data at the top (after `let currentAge`):

```javascript
let simData = null;  // populated by background /api/matchup-sims call
```

2. Modify `loadComparison()` to fire the sim fetch in parallel after rendering:

```javascript
async function loadComparison() {
    resultsEl.innerHTML = '<div class="ma-loading"><div class="spinner"></div>Loading comparison...</div>';
    simData = null;  // Reset

    try {
        const [respL, respR] = await Promise.all([
            fetch(`/api/civ-power-units/${encodeURIComponent(civLeft)}?age=${currentAge}`),
            fetch(`/api/civ-power-units/${encodeURIComponent(civRight)}?age=${currentAge}`),
        ]);

        if (!respL.ok || !respR.ok) {
            resultsEl.innerHTML = '<div class="ma-loading">Error loading data.</div>';
            return;
        }

        const dataL = await respL.json();
        const dataR = await respR.json();
        renderComparison(dataL, dataR);

        // Fire background sim fetch
        loadSims();
    } catch (e) {
        resultsEl.innerHTML = '<div class="ma-loading">Error loading data.</div>';
    }
}

async function loadSims() {
    try {
        const resp = await fetch("/api/matchup-sims", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                civ_left: civLeft,
                civ_right: civRight,
                age: currentAge,
            }),
        });
        if (!resp.ok) return;
        simData = await resp.json();
        renderSimOverlays();
    } catch (e) {
        // Silently fail — sim overlay is non-critical
    }
}
```

3. Add `renderSimOverlays()` function that populates the beats rows:

```javascript
function renderSimOverlays() {
    if (!simData) return;
    // Find all .ma-unit-side elements and populate their .ma-beats-row
    document.querySelectorAll(".ma-beats-row").forEach((row) => {
        const slug = row.dataset.unitSlug;
        const side = row.dataset.side;
        const sideData = simData[side];
        if (!sideData || !sideData[slug]) {
            row.innerHTML = "";
            return;
        }

        const { wins, highlighted } = sideData[slug];
        if (!wins || wins.length === 0) {
            row.innerHTML = "";
            return;
        }

        row.innerHTML = "";
        const label = document.createElement("span");
        label.className = "ma-beats-label";
        label.textContent = "Beats:";
        row.appendChild(label);

        const iconWrap = document.createElement("div");
        iconWrap.className = "ma-beats-icons";

        const highlightSet = new Set(highlighted || []);

        wins.forEach((oppSlug) => {
            const oppName = simData.name_map[oppSlug] || oppSlug;
            const icon = document.createElement("img");
            icon.className = "ma-beats-icon";
            if (highlightSet.has(oppSlug)) {
                icon.classList.add("exclusive");
            }
            const iconUrl = getIconUrl(oppName);
            if (iconUrl) {
                icon.src = iconUrl;
            }
            icon.alt = oppName;
            icon.title = oppName;
            iconWrap.appendChild(icon);
        });

        row.appendChild(iconWrap);
    });

    // Remove any remaining spinners
    document.querySelectorAll(".ma-beats-spinner").forEach((s) => s.remove());
}
```

4. Modify `buildUnitSide()` to include the beats row placeholder (after the strength label, before the return):

Add after the `side.appendChild(strength)` line (~line 394):

```javascript
    // Beats row (populated by sim overlay)
    const beatsRow = document.createElement("div");
    beatsRow.className = "ma-beats-row";
    beatsRow.dataset.unitSlug = entry.unit_slug;
    beatsRow.dataset.side = side === civLeft ? "left" : "right";
    // Show spinner while waiting for sim data
    const spinner = document.createElement("div");
    spinner.className = "ma-beats-spinner";
    beatsRow.appendChild(spinner);
    side.appendChild(beatsRow);
```

**Note:** The `buildUnitSide()` function signature needs a new parameter to know which side this unit belongs to. Currently it receives `(entry, civName, isWinner)`. We need to know if this is the left or right side for the `data-side` attribute. Since `civName` is passed in, we can compare it to `civLeft` to determine the side.

---

### Task 4: Add CSS for beats row

**Files:**
- Modify: `webapp/static/css/matchup_advisor.css`

**Styles to add at the end (before responsive breakpoints):**

```css
/* --- Beats Row (sim overlay) --- */
.ma-beats-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 6px;
    min-height: 20px;
    flex-wrap: wrap;
}
.ma-beats-label {
    font-size: 0.62rem;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-right: 2px;
}
.ma-beats-icons {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
}
.ma-beats-icon {
    width: 20px;
    height: 20px;
    border-radius: 3px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    object-fit: cover;
    background: rgba(0, 0, 0, 0.3);
    transition: transform 0.15s ease;
}
.ma-beats-icon:hover {
    transform: scale(1.3);
    z-index: 1;
}
.ma-beats-icon.exclusive {
    border-color: var(--gold);
    box-shadow: 0 0 6px rgba(201, 168, 76, 0.4);
}
.ma-beats-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(201, 168, 76, 0.15);
    border-top-color: var(--gold);
    border-radius: 50%;
    animation: maSpin 0.8s linear infinite;
}

/* Light mode overrides for beats */
[data-theme="light"] .ma-beats-icon {
    background: rgba(0, 0, 0, 0.06);
    border-color: rgba(0, 0, 0, 0.12);
}
[data-theme="light"] .ma-beats-icon.exclusive {
    border-color: var(--gold);
    box-shadow: 0 0 6px rgba(139, 105, 20, 0.3);
}
```

---

### Task 5: Verify and commit

**Steps:**

1. Start the Flask app on a non-5000 port:
   ```bash
   cd webapp && python3 app.py
   ```

2. Navigate to `/matchup-advisor`, select two civs (e.g., Franks vs Saracens)

3. Verify:
   - Percentile comparison cards render immediately (existing behavior, unchanged)
   - Small spinner appears in each unit card's beats area
   - After ~1 second, "Beats:" row appears with small unit icons
   - Highlighted wins have gold border/glow
   - Non-highlighted wins have subtle border
   - Units with no wins show no beats row
   - Toggling age re-fetches both percentile and sim data
   - Deselecting a civ clears both results and sim data

4. Test edge cases:
   - Civ with missing unit lines (e.g., no camels) — N/A sides should have no beats row
   - Same civ vs itself — should work (symmetrical results)

5. Commit all changes
