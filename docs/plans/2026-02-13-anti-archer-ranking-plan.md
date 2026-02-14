# Anti Archer Ranking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new "Anti Archer Rankings" tab for ranged units that scores their effectiveness against archer-class opponents using the formula `0.5*eco + 0.3*pop + 0.2*power`.

**Architecture:** New `compute_anti_archer_scores()` function in `compute_battle_scores.py` runs 8 benchmark sims per ranged unit, merges results with existing archery scores, and writes to the `battle_scores` DB table. Frontend gets a new tab via line definitions in `app.py` and `index.html`.

**Tech Stack:** Python (compute_battle_scores.py, app.py), JavaScript (index.html template), SQLite (aoe2_reference.db)

---

### Task 1: Add anti-archer benchmarks and compute function

**Files:**
- Modify: `webapp/compute_battle_scores.py:888-917` (after ARCHERY_ROLE_SCORE_TYPES)

**Step 1: Add benchmark config and score types list**

After `ARCHERY_ROLE_SCORE_TYPES` (line 917), add:

```python
ANTI_ARCHER_BENCHMARKS = [
    # Eco benchmarks (3K resources each) — vs archer-class units
    ("aa_eco_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
    ("aa_eco_vs_ca", "Chinese", "heavy_cav_archer", "Imperial", "res", 3000),
    ("aa_eco_vs_hc", "Spanish", "hand_cannoneer", "Imperial", "res", 3000),
    # Pop benchmarks (30v30 fixed count) — vs archer-class units
    ("aa_pop_vs_arb", "Chinese", "arbalester", "Imperial", "fixed_hp", (30, 30)),
    ("aa_pop_vs_ca", "Chinese", "heavy_cav_archer", "Imperial", "fixed_hp", (30, 30)),
    ("aa_pop_vs_hc", "Spanish", "hand_cannoneer", "Imperial", "fixed_hp", (30, 30)),
    # Power benchmarks (3K resources) — vs non-archer threats
    ("aa_power_vs_hussar", "Spanish", "hussar", "Imperial", "res", 3000),
    ("aa_power_vs_champ", "Chinese", "champion", "Imperial", "res", 3000),
]

ANTI_ARCHER_SCORE_TYPES = [
    "anti_archer",
    "aa_eco_score",
    "aa_pop_score",
    "aa_power",
    "aa_eco_vs_arb",
    "aa_eco_vs_ca",
    "aa_eco_vs_hc",
    "aa_pop_vs_arb",
    "aa_pop_vs_ca",
    "aa_pop_vs_hc",
    "aa_power_vs_hussar",
    "aa_power_vs_champ",
]
```

**Step 2: Add the compute function**

After `compute_archery_role_scores()` (after line 1206), add:

```python
def compute_anti_archer_scores():
    """Compute anti-archer role scores for all Imperial archery units.
    Returns dict: {"archer|imperial": {...}, "cav_archer|imperial": {...}, ...}"""

    bench_cache = {}
    for key, civ, slug, age, mode, param in ANTI_ARCHER_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: anti-archer benchmark {civ}/{slug}/{age} not found")

    all_scores = {}
    sk_to_line = {}

    for line_slug in ARCHERY_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
        if not units:
            continue

        for u in units:
            cu = u["combat_unit"]
            unit_cost = calc_weighted_cost(
                cu["cost_food"], cu["cost_wood"], cu["cost_gold"], True
            )
            sk = f"{u['civ_name']}|{u['unit_slug']}"
            scores = {}

            for key, civ, slug, age, mode, param in ANTI_ARCHER_BENCHMARKS:
                bench = bench_cache[(civ, slug, age)]
                if bench is None:
                    scores[key] = 0.0
                    continue

                if mode == "res":
                    bench_cost = calc_weighted_cost(
                        bench["cost_food"],
                        bench["cost_wood"],
                        bench["cost_gold"],
                        True,
                    )
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        param,
                        cost1_override=unit_cost,
                        cost2_override=bench_cost,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

                elif mode == "fixed_hp":
                    m_count, o_count = param
                    fake_res = m_count * o_count
                    winner, _, _, hp1, hp2 = simulate_battle(
                        cu,
                        bench,
                        fake_res,
                        cost1_override=fake_res // m_count,
                        cost2_override=fake_res // o_count,
                        return_hp=True,
                    )
                    if winner == 1:
                        scores[key] = round(hp1 * 100, 1)
                    elif winner == 2:
                        scores[key] = round(-hp2 * 100, 1)
                    else:
                        scores[key] = 0.0

            all_scores[sk] = scores
            sk_to_line[sk] = line_slug

    # Compute derived scores
    for sk, scores in all_scores.items():
        scores["aa_eco_score"] = round(
            (scores["aa_eco_vs_arb"] + scores["aa_eco_vs_ca"] + scores["aa_eco_vs_hc"])
            / 3,
            1,
        )
        scores["aa_pop_score"] = round(
            (scores["aa_pop_vs_arb"] + scores["aa_pop_vs_ca"] + scores["aa_pop_vs_hc"])
            / 3,
            1,
        )
        scores["aa_power"] = round(
            (scores["aa_power_vs_hussar"] + scores["aa_power_vs_champ"]) / 2,
            1,
        )
        scores["anti_archer"] = round(
            0.50 * scores["aa_eco_score"]
            + 0.30 * scores["aa_pop_score"]
            + 0.20 * scores["aa_power"],
            1,
        )

    # Regroup by line for DB storage
    all_role_scores = {}
    for sk, scores in all_scores.items():
        line_slug = sk_to_line[sk]
        line_key = f"{line_slug}|imperial"
        if line_key not in all_role_scores:
            all_role_scores[line_key] = {}
        all_role_scores[line_key][sk] = scores

    return all_role_scores
```

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: add compute_anti_archer_scores function and benchmarks"
```

---

### Task 2: Merge anti-archer scores into archery DB write

**Files:**
- Modify: `webapp/compute_battle_scores.py:1471-1485` (roles_only block)
- Modify: `webapp/compute_battle_scores.py:1642-1650` (main full-run block)

**Context:** `write_role_scores_to_db()` deletes ALL rows for a line_slug before inserting. Since anti-archer uses the same line slugs (archer, skirmisher, cav_archer), we must merge both score dicts and write once with a combined score_types list.

**Step 1: Update the `--roles-only` block (lines 1479-1485)**

Replace:
```python
        archery_start = time.time()
        archery_scores = compute_archery_role_scores()
        write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
        total_archery = sum(len(v) for v in archery_scores.values())
        print(
            f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {time.time() - archery_start:.1f}s"
        )
```

With:
```python
        archery_start = time.time()
        archery_scores = compute_archery_role_scores()
        aa_scores = compute_anti_archer_scores()
        # Merge anti-archer scores into archery scores (same line keys, same unit keys)
        for line_key, unit_scores in aa_scores.items():
            for uk, scores in unit_scores.items():
                archery_scores.setdefault(line_key, {}).setdefault(uk, {}).update(scores)
        combined_types = ARCHERY_ROLE_SCORE_TYPES + ANTI_ARCHER_SCORE_TYPES
        write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, combined_types)
        total_archery = sum(len(v) for v in archery_scores.values())
        print(
            f"Archery roles (incl. anti-archer): {total_archery} units across {len(archery_scores)} lines in {time.time() - archery_start:.1f}s"
        )
```

**Step 2: Update the main full-run block (lines 1642-1650)**

Replace:
```python
    # Archery role scores (written to DB, not JSON)
    archery_start = time.time()
    archery_scores = compute_archery_role_scores()
    write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
    archery_time = time.time() - archery_start
    total_archery = sum(len(v) for v in archery_scores.values())
    print(
        f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {archery_time:.1f}s"
    )
```

With:
```python
    # Archery role scores + anti-archer scores (written to DB, not JSON)
    archery_start = time.time()
    archery_scores = compute_archery_role_scores()
    aa_scores = compute_anti_archer_scores()
    # Merge anti-archer scores into archery scores (same line keys, same unit keys)
    for line_key, unit_scores in aa_scores.items():
        for uk, scores in unit_scores.items():
            archery_scores.setdefault(line_key, {}).setdefault(uk, {}).update(scores)
    combined_types = ARCHERY_ROLE_SCORE_TYPES + ANTI_ARCHER_SCORE_TYPES
    write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, combined_types)
    archery_time = time.time() - archery_start
    total_archery = sum(len(v) for v in archery_scores.values())
    print(
        f"Archery roles (incl. anti-archer): {total_archery} units across {len(archery_scores)} lines in {archery_time:.1f}s"
    )
```

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: merge anti-archer scores into archery DB write"
```

---

### Task 3: Run compute and verify DB

**Step 1: Run the compute script**

```bash
cd webapp && python3 compute_battle_scores.py --roles-only
```

Expected: prints "Archery roles (incl. anti-archer): NN units across 3 lines in X.Xs" and "Wrote NNN battle_scores rows to DB". Row count should be roughly double what it was before (since we added 12 score types per unit on top of the existing 13).

**Step 2: Verify anti-archer scores exist in DB**

```bash
cd webapp && python3 -c "
import sqlite3
conn = sqlite3.connect('aoe2_reference.db')
c = conn.cursor()
c.execute(\"SELECT COUNT(*) FROM battle_scores WHERE score_type='anti_archer'\")
print(f'anti_archer rows: {c.fetchone()[0]}')
c.execute(\"SELECT civ_name, unit_slug, score_value FROM battle_scores WHERE score_type='anti_archer' ORDER BY score_value DESC LIMIT 5\")
for row in c.fetchall():
    print(f'  {row[0]:15s} {row[1]:30s} {row[2]:6.1f}')
conn.close()
"
```

Expected: Non-zero count, top 5 units with positive scores.

**Step 3: Verify existing archery scores not broken**

```bash
cd webapp && python3 -c "
import sqlite3
conn = sqlite3.connect('aoe2_reference.db')
c = conn.cursor()
c.execute(\"SELECT COUNT(*) FROM battle_scores WHERE score_type='ranged_power'\")
print(f'ranged_power rows: {c.fetchone()[0]}')
c.execute(\"SELECT civ_name, unit_slug, score_value FROM battle_scores WHERE score_type='ranged_power' ORDER BY score_value DESC LIMIT 3\")
for row in c.fetchall():
    print(f'  {row[0]:15s} {row[1]:30s} {row[2]:6.1f}')
conn.close()
"
```

Expected: Same count and scores as before the change.

---

### Task 4: Add anti_archer line definition to app.py

**Files:**
- Modify: `webapp/app.py:1488-1498` (UNIT_LINES dict, after "raiding_infantry")

**Step 1: Add the line definition**

After the `"raiding_infantry"` entry (line 1497) and before the closing `}` of `UNIT_LINES`, add:

```python
    "anti_archer": {
        "name": "Anti Archer Rankings",
        "building": "Archery Range",
        "sub_lines": ["archer", "cav_archer", "skirmisher"],
    },
```

**Step 2: Commit**

```bash
git add webapp/app.py
git commit -m "feat: add anti_archer line definition to UNIT_LINES"
```

---

### Task 5: Add anti_archer tab and columns to frontend

**Files:**
- Modify: `webapp/templates/index.html`

There are 5 specific locations to modify in `index.html`:

**Step 1: Add line card definition (after line 764, the "archery" entry)**

Add to the `UNIT_LINES` JS object:

```javascript
                anti_archer: {
                    name: "Anti Archer Rankings",
                    building: "Archery Range",
                    castle: "Crossbowman",
                    imperial: "Arbalester",
                    hasUnique: true,
                },
```

**Step 2: Add to ARCHERY_SLUGS set (line 1664-1669)**

Change:
```javascript
            const ARCHERY_SLUGS = new Set([
                "archer",
                "skirmisher",
                "cav_archer",
                "archery",
            ]);
```

To:
```javascript
            const ARCHERY_SLUGS = new Set([
                "archer",
                "skirmisher",
                "cav_archer",
                "archery",
                "anti_archer",
            ]);
```

**Step 3: Add default sort column (line 1686-1695)**

Change the sort column selection in `selectLine()`:
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

To:
```javascript
                sortColumn =
                    slug === "anti_cav_infantry"
                        ? "anti_cav_value"
                        : slug === "raiding_infantry"
                          ? "raiding_value"
                          : slug === "anti_archer"
                            ? "anti_archer"
                            : INFANTRY_SLUGS.has(slug)
                              ? "militia_value"
                              : ARCHERY_SLUGS.has(slug)
                                ? "ranged_power"
                                : "pes";
```

**Step 4: Add stat cols and column definitions (before the `const columns =` ternary, around line 2092)**

Add new stat cols array (after `archeryStatCols`, around line 1894):
```javascript
                const antiArcherStatCols = [
                    "anti_archer",
                    "aa_eco_score",
                    "aa_pop_score",
                    "aa_power",
                    "dps",
                    "final_hp",
                    "final_attack",
                    "final_melee_armor",
                    "final_pierce_armor",
                    "final_speed",
                    "final_range",
                ];
```

Update the `statCols` ternary (around line 1896) to add anti_archer before the general isArchery check:
```javascript
                const statCols =
                    currentLine === "anti_cav_infantry"
                        ? antiCavStatCols
                        : currentLine === "anti_archer"
                          ? antiArcherStatCols
                          : isInfantry
                            ? infantryStatCols
                            : isArchery
                              ? archeryStatCols
                              : defaultStatCols;
```

Add new column definition array (after `archeryColumns`, around line 2092):
```javascript
                const antiArcherColumns = [
                    { key: "civ_name", label: "Civ" },
                    { key: "unit_name", label: "Unit" },
                    { key: "line_slug", label: "Line" },
                    {
                        key: "anti_archer",
                        label: "Score",
                        info: "Weighted aggregate: 50% Eco + 30% Pop + 20% Power",
                    },
                    {
                        key: "aa_eco_score",
                        label: "Eco",
                        info: "Avg HP% remaining after 3K resource fights vs Chinese Arb, Chinese Cav Archer, Spanish Hand Cannoneer",
                    },
                    {
                        key: "aa_pop_score",
                        label: "Pop",
                        info: "Avg HP% remaining after 30v30 fights vs Chinese Arb, Chinese Cav Archer, Spanish Hand Cannoneer",
                    },
                    {
                        key: "aa_power",
                        label: "Power",
                        info: "Avg HP% remaining after 3K resource fights vs Spanish Hussar, Chinese Champion",
                    },
                    { key: "dps", label: "DPS" },
                    { key: "final_hp", label: "HP" },
                    { key: "final_attack", label: "Atk" },
                    { key: "final_melee_armor", label: "M.Arm" },
                    { key: "final_pierce_armor", label: "P.Arm" },
                    { key: "final_speed", label: "Speed" },
                    { key: "final_range", label: "Range" },
                    { key: "total_cost", label: "Cost" },
                    { key: "total_upgrade_cost", label: "Upg Cost" },
                    { key: "special_abilities", label: "Special" },
                ];
```

**Step 5: Update the columns ternary (around line 2093)**

Change:
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

To:
```javascript
                const columns =
                    currentLine === "anti_cav_infantry"
                        ? antiCavColumns
                        : currentLine === "raiding_infantry"
                          ? raidingColumns
                          : currentLine === "anti_archer"
                            ? antiArcherColumns
                            : isInfantry
                              ? infantryColumns
                              : isArchery
                                ? archeryColumns
                                : defaultColumns;
```

**Step 6: Commit**

```bash
git add webapp/templates/index.html
git commit -m "feat: add Anti Archer Rankings tab and columns to frontend"
```

---

### Task 6: End-to-end verification

**Step 1: Start the webapp**

```bash
cd webapp && python3 app.py
```

(Use port 5001 if 5000 is in use: modify or pass `--port 5001`)

**Step 2: Verify API returns anti-archer scores**

```bash
curl -s http://localhost:5001/api/ref/unit-line/anti_archer | python3 -m json.tool | head -50
```

Expected: JSON with `"line_name": "Anti Archer Rankings"`, imperial array with units containing `anti_archer`, `aa_eco_score`, `aa_pop_score`, `aa_power` fields.

**Step 3: Verify existing archery endpoint still works**

```bash
curl -s http://localhost:5001/api/ref/unit-line/archery | python3 -c "import sys,json; d=json.load(sys.stdin); u=d['imperial'][0]; print(u.get('ranged_power','MISSING'), u.get('anti_archer','MISSING'))"
```

Expected: Both `ranged_power` and `anti_archer` scores present on each unit (since both read from same DB rows for the same line slugs).

**Step 4: Visual check**

Open browser to `http://localhost:5001/`, click the "Anti Archer Rankings" tab in the Archery Range section. Verify:
- Table renders with correct columns (Score, Eco, Pop, Power, DPS, HP, etc.)
- Scores are populated (not -999 or blank)
- Sorting by Score column works
- Hovering over score cells shows tooltip descriptions
- Line column shows "archer"/"skirmisher"/"cav_archer" for each unit
- Existing "Ranged Power Rankings" tab still works correctly
