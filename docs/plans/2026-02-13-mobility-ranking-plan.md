# Mobility Ranking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Mobility Rankings" tab for ranged units that scores units by normalized(speed * dps) + normalized(pierce_armor) + normalized(hp), equally weighted.

**Architecture:** Compute mobility scores inside the existing `compute_archery_role_scores()` function in `compute_battle_scores.py`, storing them in the `battle_scores` DB table alongside existing archery scores. The frontend gets a new UNIT_LINES entry, column definition, and score breakdown. No API changes needed — the existing `_attach_scores()` mechanism loads all `battle_scores` rows automatically.

**Tech Stack:** Python (compute_battle_scores.py), JavaScript (index.html template), SQLite (battle_scores table)

---

### Task 1: Add mobility score computation to backend

**Files:**
- Modify: `webapp/compute_battle_scores.py:903-917` (ARCHERY_ROLE_SCORE_TYPES)
- Modify: `webapp/compute_battle_scores.py:1171-1206` (end of compute_archery_role_scores)

**Step 1: Add new score types to ARCHERY_ROLE_SCORE_TYPES**

In `webapp/compute_battle_scores.py`, find the `ARCHERY_ROLE_SCORE_TYPES` list (line 903) and add the 4 new score types at the end:

```python
ARCHERY_ROLE_SCORE_TYPES = [
    "ranged_power",
    "raw_dps_score",
    "eco_dps_score",
    "survivability_score",
    "eco_vs_champ",
    "eco_vs_paladin",
    "eco_vs_arb",
    "raw_vs_champ",
    "raw_vs_paladin",
    "raw_vs_arb",
    "surv_vs_skirm",
    "surv_vs_cav_archer",
    "surv_vs_halb",
    # Mobility ranking scores
    "mobility_score",
    "mobility_speed_dps",
    "mobility_pierce_armor",
    "mobility_hp",
]
```

**Step 2: Add mobility computation after existing derived scores**

In `compute_archery_role_scores()`, after the `ranged_power` computation (line 1195) and before the "Regroup by line" comment (line 1197), add:

```python
    # Compute mobility ranking scores
    # Step 1: Collect raw values from combat units
    mobility_raw = {}
    for line_slug in ARCHERY_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
        for u in units:
            cu = u["combat_unit"]
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            if sk not in all_scores:
                continue
            attack = cu["attack"]
            attack_speed = cu["attack_speed"]  # already 1/reload from prepare_combat_unit
            reload_time = 1.0 / attack_speed if attack_speed > 0 else 2.0
            dps = attack / reload_time
            mobility_raw[sk] = {
                "speed_dps": cu["movement_speed"] * dps,
                "pierce_armor": cu["pierce_armor"],
                "hp": cu["hp"],
            }

    # Step 2: Normalize each component 0-100
    if mobility_raw:
        for component in ["speed_dps", "pierce_armor", "hp"]:
            vals = [r[component] for r in mobility_raw.values()]
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1
            for r in mobility_raw.values():
                r[f"norm_{component}"] = round((r[component] - lo) / span * 100, 1)

        # Step 3: Compute composite and store
        for sk, raw in mobility_raw.items():
            scores = all_scores[sk]
            scores["mobility_speed_dps"] = raw["norm_speed_dps"]
            scores["mobility_pierce_armor"] = raw["norm_pierce_armor"]
            scores["mobility_hp"] = raw["norm_hp"]
            scores["mobility_score"] = round(
                (raw["norm_speed_dps"] + raw["norm_pierce_armor"] + raw["norm_hp"]) / 3,
                1,
            )
```

**Important:** The `build_line_units()` call here re-fetches units to access `combat_unit` dicts, which aren't stored in `all_scores`. This matches the pattern used for infantry raiding scores.

**Step 3: Run the compute script to verify**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 compute_battle_scores.py --roles-only`

Expected: Script completes without errors, prints archery role score counts (should be higher now with 4 extra score types per unit).

**Step 4: Verify scores in DB**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && python3 -c "import sqlite3; conn = sqlite3.connect('webapp/aoe2_reference.db'); c = conn.cursor(); c.execute(\"SELECT civ_name, unit_slug, score_type, score_value FROM battle_scores WHERE score_type LIKE 'mobility%' ORDER BY score_type, score_value DESC LIMIT 20\"); [print(r) for r in c.fetchall()]"`

Expected: Rows with `mobility_score`, `mobility_speed_dps`, `mobility_pierce_armor`, `mobility_hp` score types, values between 0 and 100.

**Step 5: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: add mobility ranking score computation for ranged units"
```

---

### Task 2: Add mobility meta-line to app.py

**Files:**
- Modify: `webapp/app.py:1478-1482` (META_LINES dict)

**Step 1: Add the mobility entry to META_LINES**

In `webapp/app.py`, find the `META_LINES` dict. After the `"archery"` entry (line 1478-1482), add:

```python
    "mobility": {
        "name": "Mobility Rankings",
        "building": "Archery Range",
        "sub_lines": ["archer", "cav_archer", "skirmisher"],
    },
```

This points to the same underlying sub-lines as "archery", so the API will return the same units with all their battle_scores (including the new mobility scores).

**Step 2: Verify the API serves mobility data**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && python3 -c "
import sys; sys.path.insert(0, 'webapp')
from app import app
with app.test_client() as c:
    r = c.get('/api/ref/unit-line/mobility')
    data = r.get_json()
    print('Line name:', data.get('line_name'))
    print('Imperial units:', len(data.get('imperial', [])))
    u = data['imperial'][0] if data.get('imperial') else {}
    print('First unit:', u.get('civ_name'), u.get('unit_name'))
    print('mobility_score:', u.get('mobility_score'))
    print('mobility_speed_dps:', u.get('mobility_speed_dps'))
"`

Expected: Shows "Mobility Rankings", unit count, and mobility scores on units.

**Step 3: Commit**

```bash
git add webapp/app.py
git commit -m "feat: add mobility meta-line to API"
```

---

### Task 3: Add mobility ranking tab to frontend

**Files:**
- Modify: `webapp/templates/index.html`

This task has several sub-steps modifying index.html. Apply each edit in order.

**Step 1: Add UNIT_LINES entry for mobility**

Find the `UNIT_LINES` object (around line 758). After the `archery` entry (line 758-764), add:

```javascript
                mobility: {
                    name: "Mobility Rankings",
                    building: "Archery Range",
                    castle: "Crossbowman",
                    imperial: "Arbalester",
                    hasUnique: true,
                },
```

**Step 2: Add "mobility" to ARCHERY_SLUGS**

Find `ARCHERY_SLUGS` (line 1664). Add `"mobility"` to the set:

```javascript
            const ARCHERY_SLUGS = new Set([
                "archer",
                "skirmisher",
                "cav_archer",
                "archery",
                "mobility",
            ]);
```

**Step 3: Add mobility scores to SCORE_KEYS**

Find `SCORE_KEYS` (line 1154). After `"surv_vs_cav_archer"` (line 1181), add:

```javascript
                // Mobility scores
                "mobility_score",
                "mobility_speed_dps",
                "mobility_pierce_armor",
                "mobility_hp",
```

**Step 4: Add mobility scores to numeric formatting**

Find the formatting chain in `renderTable()` (around line 2174). In the `else if` block that uses `.toFixed(1)`, add the mobility score keys. After `"raid_vs_castle_dps"` (line 2190), add:

```javascript
                        k === "mobility_score" ||
                        k === "mobility_speed_dps" ||
                        k === "mobility_pierce_armor" ||
                        k === "mobility_hp" ||
```

**Step 5: Add score breakdown popover for mobility_score**

Find the `composites` object in the hover card logic (around line 1320). After the `ranged_power` entry (ends around line 1370), add:

```javascript
                        mobility_score: {
                            title: "Mobility Score",
                            parts: [
                                {
                                    key: "mobility_speed_dps",
                                    label: "Speed \u00d7 DPS",
                                    weight: "33%",
                                },
                                {
                                    key: "mobility_pierce_armor",
                                    label: "Pierce Armor",
                                    weight: "33%",
                                },
                                {
                                    key: "mobility_hp",
                                    label: "HP",
                                    weight: "33%",
                                },
                            ],
                        },
```

**Step 6: Add default sort for mobility tab**

Find the `selectLine` function's sort logic (around line 1686-1695). The current chain is:

```javascript
                sortColumn =
                    slug === "anti_cav_infantry"
                        ? "anti_cav_value"
                        : slug === "raiding_infantry"
                          ? "raiding_value"
                          : INFANTRY_SLUGS.has(slug)
                            ? "militia_value"
                            : ARCHERY_SLUGS.has(slug)
                              ? "ranged_power"
                              : "pes";
```

Change it so `mobility` uses `mobility_score` while other archery slugs still use `ranged_power`:

```javascript
                sortColumn =
                    slug === "anti_cav_infantry"
                        ? "anti_cav_value"
                        : slug === "raiding_infantry"
                          ? "raiding_value"
                          : slug === "mobility"
                            ? "mobility_score"
                            : INFANTRY_SLUGS.has(slug)
                              ? "militia_value"
                              : ARCHERY_SLUGS.has(slug)
                                ? "ranged_power"
                                : "pes";
```

**Step 7: Add mobilityColumns definition and wire it into column selection**

Find the `archeryColumns` definition (around line 2056). After it (before the `const columns =` line), add `mobilityColumns`:

```javascript
                const mobilityColumns = [
                    { key: "civ_name", label: "Civ" },
                    { key: "unit_name", label: "Unit" },
                    { key: "line_slug", label: "Line" },
                    {
                        key: "mobility_score",
                        label: "Score",
                        info: "Equal average of normalized Speed\u00d7DPS + Pierce Armor + HP (each 0\u2013100)",
                    },
                    {
                        key: "mobility_speed_dps",
                        label: "Spd\u00d7DPS",
                        info: "Movement speed \u00d7 DPS, normalized 0\u2013100 across all ranged units",
                    },
                    {
                        key: "mobility_pierce_armor",
                        label: "P.Arm",
                        info: "Pierce armor, normalized 0\u2013100 across all ranged units",
                    },
                    {
                        key: "mobility_hp",
                        label: "HP",
                        info: "Hit points, normalized 0\u2013100 across all ranged units",
                    },
                    { key: "dps", label: "DPS (raw)" },
                    { key: "final_hp", label: "HP (raw)" },
                    { key: "final_pierce_armor", label: "P.Arm (raw)" },
                    { key: "final_speed", label: "Speed (raw)" },
                    { key: "final_range", label: "Range" },
                    { key: "total_cost", label: "Cost" },
                    { key: "special_abilities", label: "Special" },
                ];
```

Then update the `const columns =` ternary chain (around line 2093). Currently:

```javascript
                const columns =
                    currentLine === "anti_cav_infantry"
                        ? antiCavColumns
                        : currentLine === "raiding_infantry"
                          ? raidingColumns
                          : isInfantry
                            ? infantryColumns
                            : isArchery
                              ? archeryColumns
                              : defaultColumns;
```

Change to:

```javascript
                const columns =
                    currentLine === "anti_cav_infantry"
                        ? antiCavColumns
                        : currentLine === "raiding_infantry"
                          ? raidingColumns
                          : currentLine === "mobility"
                            ? mobilityColumns
                            : isInfantry
                              ? infantryColumns
                              : isArchery
                                ? archeryColumns
                                : defaultColumns;
```

**Step 8: Add mobility stat columns for sorting**

Find the `archeryStatCols` array (around line 1882). After it, add:

```javascript
                const mobilityStatCols = [
                    "mobility_score",
                    "mobility_speed_dps",
                    "mobility_pierce_armor",
                    "mobility_hp",
                    "dps",
                    "final_hp",
                    "final_pierce_armor",
                    "final_speed",
                    "final_range",
                ];
```

Then find where `statCols` is assigned (around line 1896). Currently:

```javascript
                const statCols =
                    currentLine === "anti_cav_infantry"
                        ? antiCavStatCols
                        : currentLine === "raiding_infantry"
                          ? raidingStatCols
                          : isInfantry
                            ? infantryStatCols
                            : isArchery
                              ? archeryStatCols
                              : defaultStatCols;
```

Change to:

```javascript
                const statCols =
                    currentLine === "anti_cav_infantry"
                        ? antiCavStatCols
                        : currentLine === "raiding_infantry"
                          ? raidingStatCols
                          : currentLine === "mobility"
                            ? mobilityStatCols
                            : isInfantry
                              ? infantryStatCols
                              : isArchery
                                ? archeryStatCols
                                : defaultStatCols;
```

**Step 9: Commit**

```bash
git add webapp/templates/index.html
git commit -m "feat: add mobility ranking tab to frontend"
```

---

### Task 4: Manual testing and verification

**Step 1: Start the webapp**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 app.py --port 5001`

**Step 2: Verify in browser**

Open `http://localhost:5001` and check:
1. The "Mobility Rankings" card appears in the Archery Range section
2. Clicking it shows a table with Score, Spd*DPS, P.Arm, HP columns
3. Default sort is by Score descending
4. Clicking Score shows the 3-part breakdown popover
5. All sub-scores are between 0 and 100
6. Units with high speed and DPS (e.g., Mangudai) should rank highly
7. The Line column shows which line each unit is from (archer/skirmisher/cav_archer)

**Step 3: Stop the server and commit any fixes if needed**
