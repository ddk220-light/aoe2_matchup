# Archery Line Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace round-robin/PES/RES archery scoring with a role-based "Ranged Power Ranking" stored in `aoe2_reference.db`, combining archer + cav_archer + skirmisher into one unified "archery" view with infantry-style UI.

**Architecture:** Add `compute_archery_role_scores()` to `compute_battle_scores.py` that simulates 5 benchmark matchups per archery unit and writes scores to the `battle_scores` table. Modify `app.py` to read archery scores from the DB (not JSON). Update `index.html` to use archery-specific columns, hover cards, and score breakdowns.

**Tech Stack:** Python (Flask), SQLite, vanilla JS

---

### Task 1: Add archery scoring to compute_battle_scores.py

**Files:**
- Modify: `webapp/compute_battle_scores.py`

**Step 1: Add ARCHERY_ROLE_BENCHMARKS and ARCHERY_LINE_SLUGS constants**

After `INFANTRY_LINE_SLUGS` (line 932), add:

```python
ARCHERY_LINE_SLUGS = ["archer", "skirmisher", "cav_archer"]

ARCHERY_ROLE_BENCHMARKS = [
    # DPS benchmarks (3K resources each)
    ("ar_vs_champ", "Chinese", "champion", "Imperial", "res", 3000),
    ("ar_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
    ("ar_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
    # Survivability benchmarks (3K resources each)
    ("ar_vs_skirm", "Spanish", "imp_elite_skirm", "Imperial", "res", 3000),
    ("ar_vs_cav_archer", "Chinese", "heavy_cav_archer", "Imperial", "res", 3000),
]

ARCHERY_ROLE_SCORE_TYPES = [
    "ranged_power",
    "dps_score",
    "survivability_score",
    "ar_vs_champ",
    "ar_vs_paladin",
    "ar_vs_arb",
    "ar_vs_skirm",
    "ar_vs_cav_archer",
]
```

**Step 2: Add compute_archery_role_scores() function**

After `compute_infantry_role_scores()` (after line ~1091), add:

```python
def compute_archery_role_scores():
    """Compute role-based scores for all Imperial archery units.
    Returns dict: {"archer|imperial": {...}, "cav_archer|imperial": {...}, ...}"""

    # Load benchmark opponents (once, shared across all lines)
    bench_cache = {}
    for key, civ, slug, age, mode, param in ARCHERY_ROLE_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: archery benchmark {civ}/{slug}/{age} not found")

    all_scores = {}  # sk -> scores dict
    sk_to_line = {}  # sk -> line_slug

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

            for key, civ, slug, age, mode, param in ARCHERY_ROLE_BENCHMARKS:
                bench = bench_cache[(civ, slug, age)]
                if bench is None:
                    scores[key] = 0.0
                    continue

                bench_cost = calc_weighted_cost(
                    bench["cost_food"], bench["cost_wood"], bench["cost_gold"], True
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

            all_scores[sk] = scores
            sk_to_line[sk] = line_slug

    # Compute derived scores (raw HP% averages, no normalization)
    for sk, scores in all_scores.items():
        scores["dps_score"] = round(
            (scores["ar_vs_champ"] + scores["ar_vs_paladin"] + scores["ar_vs_arb"]) / 3,
            1,
        )
        scores["survivability_score"] = round(
            (scores["ar_vs_skirm"] + scores["ar_vs_cav_archer"]) / 2,
            1,
        )
        scores["ranged_power"] = round(
            0.70 * scores["dps_score"] + 0.30 * scores["survivability_score"],
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

**Step 3: Update write_role_scores_to_db() to handle archery scores**

Modify `write_role_scores_to_db()` (line 1304) to accept a `score_types` parameter and handle both infantry and archery:

```python
def write_role_scores_to_db(role_scores_dict, line_slugs, score_types):
    """Write role scores into the battle_scores table in aoe2_reference.db.

    Clears existing scores for the given line_slugs before inserting.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for slug in line_slugs:
        c.execute("DELETE FROM battle_scores WHERE line_slug=?", (slug,))

    rows = []
    for line_age_key, unit_scores in role_scores_dict.items():
        line_slug, age = line_age_key.split("|")
        for unit_key, scores in unit_scores.items():
            civ_name, unit_slug = unit_key.split("|")
            for score_type in score_types:
                if score_type in scores:
                    rows.append(
                        (
                            line_slug,
                            age,
                            civ_name,
                            unit_slug,
                            score_type,
                            scores[score_type],
                        )
                    )

    c.executemany(
        "INSERT INTO battle_scores (line_slug, age, civ_name, unit_slug, score_type, score_value) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"  Wrote {len(rows)} battle_scores rows to DB")
```

**Step 4: Update main() to call archery scoring**

In `main()`, update the `--roles-only` block (line 1356) to also compute archery:

```python
    if args.roles_only:
        role_scores = compute_infantry_role_scores()
        write_role_scores_to_db(role_scores, INFANTRY_LINE_SLUGS, INFANTRY_ROLE_SCORE_TYPES)
        total = sum(len(v) for v in role_scores.values())
        print(f"Infantry roles: {total} units across {len(role_scores)} lines in {time.time() - start:.1f}s")

        archery_start = time.time()
        archery_scores = compute_archery_role_scores()
        write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
        total_archery = sum(len(v) for v in archery_scores.values())
        print(f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {time.time() - archery_start:.1f}s")
        return
```

Also update the full run section (after line 1509) to also compute archery:

```python
    # Archery role scores (written to DB, not JSON)
    archery_start = time.time()
    archery_scores = compute_archery_role_scores()
    write_role_scores_to_db(archery_scores, ARCHERY_LINE_SLUGS, ARCHERY_ROLE_SCORE_TYPES)
    archery_time = time.time() - archery_start
    total_archery = sum(len(v) for v in archery_scores.values())
    print(f"Archery roles: {total_archery} units across {len(archery_scores)} lines in {archery_time:.1f}s")
```

And update the infantry write_role_scores_to_db call to use the new signature:

```python
    write_role_scores_to_db(role_scores, INFANTRY_LINE_SLUGS, INFANTRY_ROLE_SCORE_TYPES)
```

**Step 5: Exclude archery lines from round-robin/benchmark computation**

In the round-robin loop (line 1477) and the fingerprint loop (line 1394), add archery to the skip list:

Change:
```python
        if line_slug in INFANTRY_LINE_SLUGS:
            continue
```
To:
```python
        if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS:
            continue
```

Do this in both loops (lines ~1394-1396 and ~1477-1479).

**Step 6: Run and verify**

Run: `cd webapp && python3 compute_battle_scores.py --roles-only`

Expected: See output like:
```
Infantry roles: N units across 3 lines in X.Xs
Archery roles: M units across 3 lines in Y.Ys
  Wrote Z battle_scores rows to DB
```

Verify scores are in DB:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db')
c = conn.cursor()
c.execute('SELECT DISTINCT line_slug FROM battle_scores')
print('Lines:', [r[0] for r in c.fetchall()])
c.execute(\"SELECT civ_name, unit_slug, score_type, score_value FROM battle_scores WHERE line_slug='archer' AND score_type='ranged_power' ORDER BY score_value DESC LIMIT 5\")
for r in c.fetchall(): print(r)
conn.close()
"
```

**Step 7: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: add archery role-based scoring to battle_scores DB"
```

---

### Task 2: Update app.py to serve archery scores from DB

**Files:**
- Modify: `webapp/app.py`

**Step 1: Add ARCHERY_LINE_SLUGS constant and "archery" virtual line**

After `INFANTRY_LINE_SLUGS` (line 1532), add:

```python
ARCHERY_LINE_SLUGS = {"archer", "skirmisher", "cav_archer"}
```

In the `UNIT_LINES` dict, replace `"all_ranged"` entry (line ~1469) with:

```python
    "archery": {
        "name": "Ranged Power Rankings",
        "building": "Archery Range",
        "sub_lines": ["archer", "cav_archer", "skirmisher"],
    },
```

**Step 2: Update _attach_scores() to handle archery**

Modify `_attach_scores()` (line 1600) to check for archery lines too:

```python
    def _attach_scores(entry, age_key, sub_slug):
        """Attach battle scores: DB role scores for infantry/archery, JSON for other lines."""
        unit_key = f"{entry['civ_name']}|{entry['unit_slug']}"
        if (sub_slug in INFANTRY_LINE_SLUGS or sub_slug in ARCHERY_LINE_SLUGS) and _db_role_scores:
            rs = _db_role_scores.get(unit_key, {})
            for rk, rv in rs.items():
                entry[rk] = rv
        else:
            # Other lines: round-robin + benchmark from JSON
            line_key = f"{sub_slug}|{age_key}"
            rr = _ROUND_ROBIN.get(line_key, {}).get(unit_key, {})
            entry["score_30v30"] = rr.get("score_30v30", -999)
            entry["score_3k"] = rr.get("score_3k", -999)
            entry["score_5k"] = rr.get("score_5k", -999)
            bm = _BENCHMARKS.get(line_key, {}).get(unit_key, {})
            entry["vs_champ"] = bm.get("vs_champ", -999)
            entry["vs_paladin"] = bm.get("vs_paladin", -999)
            entry["vs_arb"] = bm.get("vs_arb", -999)
            entry["pop_vs_champ"] = bm.get("pop_vs_champ", -999)
            entry["pop_vs_paladin"] = bm.get("pop_vs_paladin", -999)
            entry["pop_vs_arb"] = bm.get("pop_vs_arb", -999)
```

**Step 3: Update DB score loading to include archery slugs**

Modify the `_score_line_slugs` filter (line 1587) to include archery:

```python
    _score_line_slugs = [s for s in sub_lines if s in INFANTRY_LINE_SLUGS or s in ARCHERY_LINE_SLUGS]
```

**Step 4: Update the UNIT_LINES in index.html nav**

In `webapp/templates/index.html`, in the `UNIT_LINES` JS object (line ~757), replace the three individual archery entries with:

```javascript
                archery: {
                    name: "Ranged Power Rankings",
                    building: "Archery Range",
                    castle: "Crossbowman",
                    imperial: "Arbalester",
                    hasUnique: true,
                },
```

And keep the individual lines for sub-line viewing:
```javascript
                archer: {
                    name: "Archers & Gunpowder",
                    building: "Archery Range",
                    castle: "Crossbowman",
                    imperial: "Arbalester",
                    hasUnique: true,
                },
                skirmisher: {
                    name: "Skirmisher Line",
                    building: "Archery Range",
                    castle: "Elite Skirmisher",
                    imperial: "Elite Skirmisher",
                    hasUnique: false,
                },
                cav_archer: {
                    name: "Cav Archer Line",
                    building: "Archery Range",
                    castle: "Cavalry Archer",
                    imperial: "Heavy Cavalry Archer",
                    hasUnique: true,
                },
```

Remove the `all_ranged` entry (line ~857).

**Step 5: Commit**

```bash
git add webapp/app.py webapp/templates/index.html
git commit -m "feat: serve archery scores from DB, add archery virtual line"
```

---

### Task 3: Update index.html frontend columns and hover cards

**Files:**
- Modify: `webapp/templates/index.html`

**Step 1: Add ARCHERY_SLUGS set**

After `INFANTRY_SLUGS` (line 1539), add:

```javascript
            const ARCHERY_SLUGS = new Set([
                "archer",
                "skirmisher",
                "cav_archer",
                "archery",
            ]);
```

**Step 2: Add archery entries to SCORE_BREAKDOWN**

In the `SCORE_BREAKDOWN` object (line 885), add after the last infantry entry:

```javascript
                // Archery score breakdowns
                dps_score: {
                    title: "DPS Score Breakdown",
                    formula: "Average of 3 matchups (3K resources each)",
                    subs: [
                        {
                            key: "ar_vs_champ",
                            label: "vs Champion",
                            civ: "Chinese",
                            slug: "champion",
                            mode: "resources",
                            res: 3000,
                        },
                        {
                            key: "ar_vs_paladin",
                            label: "vs Paladin",
                            civ: "Spanish",
                            slug: "paladin",
                            mode: "resources",
                            res: 3000,
                        },
                        {
                            key: "ar_vs_arb",
                            label: "vs Arbalester",
                            civ: "Chinese",
                            slug: "arbalester",
                            mode: "resources",
                            res: 3000,
                        },
                    ],
                },
                survivability_score: {
                    title: "Survivability Breakdown",
                    formula: "Average of 2 matchups (3K resources each)",
                    subs: [
                        {
                            key: "ar_vs_skirm",
                            label: "vs Elite Skirm",
                            civ: "Spanish",
                            slug: "imp_elite_skirm",
                            mode: "resources",
                            res: 3000,
                        },
                        {
                            key: "ar_vs_cav_archer",
                            label: "vs Heavy Cav Archer",
                            civ: "Chinese",
                            slug: "heavy_cav_archer",
                            mode: "resources",
                            res: 3000,
                        },
                    ],
                },
```

**Step 3: Add archery keys to SCORE_KEYS set**

Update `SCORE_KEYS` (line 1071) to include archery score keys:

```javascript
            const SCORE_KEYS = new Set([
                "melee_power",
                "meat_shield",
                "raid",
                "anti_cav",
                "militia_value",
                "anti_cav_total",
                "frontline",
                "anti_cav_value",
                "raid_speed",
                "raid_vill_kill",
                "raid_building",
                "raiding_value",
                "raid_vs_tc_dps",
                "raid_vs_castle_dps",
                // Archery scores
                "ranged_power",
                "dps_score",
                "survivability_score",
                "ar_vs_champ",
                "ar_vs_paladin",
                "ar_vs_arb",
                "ar_vs_skirm",
                "ar_vs_cav_archer",
            ]);
```

**Step 4: Add archeryColumns definition**

After `raidingColumns` (line ~1911), add:

```javascript
                const archeryColumns = [
                    { key: "civ_name", label: "Civ" },
                    { key: "unit_name", label: "Unit" },
                    ...(currentLine === "archery"
                        ? [{ key: "line_slug", label: "Line" }]
                        : []),
                    {
                        key: "ranged_power",
                        label: "Score",
                        info: "Weighted aggregate: 70% DPS Score + 30% Survivability",
                    },
                    {
                        key: "dps_score",
                        label: "DPS Score",
                        info: "Avg HP% remaining after 3K resource fights vs Chinese Champion, Spanish Paladin, Chinese Arbalester",
                    },
                    {
                        key: "survivability_score",
                        label: "Survivability",
                        info: "Avg HP% remaining after 3K resource fights vs Spanish Elite Skirm and Chinese Heavy Cav Archer",
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

**Step 5: Add archeryStatCols for median computation**

After `antiCavStatCols` (line ~1753), add:

```javascript
                const archeryStatCols = [
                    "ranged_power",
                    "dps_score",
                    "survivability_score",
                    "dps",
                    "final_hp",
                    "final_attack",
                    "final_melee_armor",
                    "final_pierce_armor",
                    "final_speed",
                    "final_range",
                ];
```

**Step 6: Wire up archery in column/statCols selection logic**

Update the `statCols` selection (line ~1754):

```javascript
                const isArchery = ARCHERY_SLUGS.has(currentLine);
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

Update the `columns` selection (line ~1912):

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

**Step 7: Update default sort column for archery**

Update `selectLine()` sort logic (line ~1563):

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

**Step 8: Add LINE_LABELS for archery sub-lines**

Update `LINE_LABELS` (line ~1575):

```javascript
            const LINE_LABELS = {
                militia: "Militia",
                spear: "Spear",
                shock_infantry: "Shock",
                archer: "Archer",
                skirmisher: "Skirm",
                cav_archer: "Cav Archer",
            };
```

**Step 9: Commit**

```bash
git add webapp/templates/index.html
git commit -m "feat: add archery columns, hover cards, and score breakdowns"
```

---

### Task 4: Run full compute and verify end-to-end

**Step 1: Run the scoring**

```bash
cd webapp && python3 compute_battle_scores.py --roles-only
```

**Step 2: Verify DB has archery scores**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db')
c = conn.cursor()
c.execute('SELECT line_slug, COUNT(*) FROM battle_scores GROUP BY line_slug')
print(dict(c.fetchall()))
c.execute(\"SELECT civ_name, unit_slug, score_type, score_value FROM battle_scores WHERE line_slug='archer' AND score_type='ranged_power' ORDER BY score_value DESC LIMIT 10\")
for r in c.fetchall(): print(r)
conn.close()
"
```

**Step 3: Start webapp and test**

```bash
cd webapp && python3 app.py
```

Open browser, navigate to the "Ranged Power Rankings" card. Verify:
- All three sub-lines appear (archer, cav_archer, skirmisher)
- Score/DPS Score/Survivability columns have values
- Hover cards show formula + sub-matchup values + simulate links
- Clicking simulate links opens the correct battle sim
- Line column shows archer/skirm/cav_archer labels

**Step 4: Final commit**

```bash
git add webapp/aoe2_reference.db
git commit -m "chore: update reference DB with archery battle scores"
```

---

### Task 5: Clean up old code

**Files:**
- Modify: `webapp/app.py` (remove `all_ranged` from UNIT_LINES if still present)
- Modify: `webapp/templates/index.html` (remove `all_ranged` from UNIT_LINES JS)

**Step 1:** Verify `all_ranged` entry is fully removed from both app.py and index.html UNIT_LINES.

**Step 2:** The round-robin and benchmark computation in `compute_battle_scores.py` still runs for other lines (knight, light_cav, etc.) — no need to remove that code yet. But archery lines are now excluded from it.

**Step 3: Commit**

```bash
git add webapp/app.py webapp/templates/index.html
git commit -m "chore: remove all_ranged entry, archery now uses role-based scoring"
```
