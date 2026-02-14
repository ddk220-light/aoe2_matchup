# Stable Units Ranking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all 6 cavalry tables with a single "Stable Units" ranking using benchmark-based composite scoring (0.6*attack + 0.2*speed + 0.2*survivability).

**Architecture:** New `compute_stable_role_scores()` function in `compute_battle_scores.py` runs 12 benchmark sims per stable unit, computes composite score, writes to `battle_scores` DB table under virtual line `"stable"`. Frontend replaces 6 Stable entries with one. API serves via existing `/api/ref/unit-line/stable` endpoint.

**Tech Stack:** Python (compute_battle_scores.py, app.py), SQLite (battle_scores table), JavaScript (index.html template)

---

### Task 1: Add stable benchmarks and scoring function to compute_battle_scores.py

**Files:**
- Modify: `webapp/compute_battle_scores.py` (after line 950, the ANTI_ARCHER_SCORE_TYPES section)

**Step 1: Add STABLE constants**

Add after the `ANTI_ARCHER_SCORE_TYPES` list (around line 950):

```python
# ===== Stable unit scoring =====
STABLE_LINE_SLUGS = ["knight", "light_cav", "camel", "steppe_lancer", "elephant"]

STABLE_BENCHMARKS = [
    # Attack Power — 30v30 fixed count (HP% scoring)
    ("atk_30v30_vs_paladin", "Spanish", "paladin", "Imperial", "fixed_hp", (30, 30)),
    ("atk_30v30_vs_arb", "Chinese", "arbalester", "Imperial", "fixed_hp", (30, 30)),
    ("atk_30v30_vs_champ", "Chinese", "champion", "Imperial", "fixed_hp", (30, 30)),
    # Attack Power — 3K resource (HP% scoring)
    ("atk_3k_vs_paladin", "Spanish", "paladin", "Imperial", "res", 3000),
    ("atk_3k_vs_arb", "Chinese", "arbalester", "Imperial", "res", 3000),
    ("atk_3k_vs_champ", "Chinese", "champion", "Imperial", "res", 3000),
    # Survivability — 30v30 fixed count (HP% scoring)
    ("surv_30v30_vs_halb", "Chinese", "halberdier", "Imperial", "fixed_hp", (30, 30)),
    ("surv_30v30_vs_camel", "Turks", "heavy_camel", "Imperial", "fixed_hp", (30, 30)),
    ("surv_30v30_vs_ca", "Berbers", "elite_camel_archer_berbers", "Imperial", "fixed_hp", (30, 30)),
    # Survivability — 3K resource (HP% scoring)
    ("surv_3k_vs_halb", "Chinese", "halberdier", "Imperial", "res", 3000),
    ("surv_3k_vs_camel", "Turks", "heavy_camel", "Imperial", "res", 3000),
    ("surv_3k_vs_ca", "Berbers", "elite_camel_archer_berbers", "Imperial", "res", 3000),
]

STABLE_SCORE_TYPES = [
    "stable_power",
    "attack_power",
    "movement_speed_score",
    "survivability_score",
    # Individual benchmark sub-scores
    "atk_30v30_vs_paladin",
    "atk_30v30_vs_arb",
    "atk_30v30_vs_champ",
    "atk_3k_vs_paladin",
    "atk_3k_vs_arb",
    "atk_3k_vs_champ",
    "surv_30v30_vs_halb",
    "surv_30v30_vs_camel",
    "surv_30v30_vs_ca",
    "surv_3k_vs_halb",
    "surv_3k_vs_camel",
    "surv_3k_vs_ca",
]
```

**Step 2: Add compute_stable_role_scores() function**

Add after the constants (around the same area where `compute_archery_role_scores` and `compute_anti_archer_scores` live):

```python
def compute_stable_role_scores():
    """Compute benchmark-based scores for all Imperial stable units.
    Returns dict: {"stable|Imperial": {civ|slug: {score_type: value, ...}, ...}}"""

    # Load benchmark units
    bench_cache = {}
    for key, civ, slug, age, mode, param in STABLE_BENCHMARKS:
        cache_key = (civ, slug, age)
        if cache_key not in bench_cache:
            bench_cache[cache_key] = _load_benchmark_unit(civ, slug, age)
        if bench_cache[cache_key] is None:
            print(f"  WARNING: stable benchmark {civ}/{slug}/{age} not found")

    # Collect all Imperial stable units from all source lines
    all_units = []
    for line_slug in STABLE_LINE_SLUGS:
        units = build_line_units(line_slug, "imperial")
        all_units.extend(units)

    if not all_units:
        return {}

    all_scores = {}

    # Run each unit against all benchmarks
    for u in all_units:
        cu = u["combat_unit"]
        unit_cost = calc_weighted_cost(
            cu["cost_food"], cu["cost_wood"], cu["cost_gold"], True
        )
        sk = f"{u['civ_name']}|{u['unit_slug']}"
        scores = {}

        for key, civ, slug, age, mode, param in STABLE_BENCHMARKS:
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

    # Compute attack_power and survivability_score (shifted to 0-100)
    atk_keys = [k for k, *_ in STABLE_BENCHMARKS if k.startswith("atk_")]
    surv_keys = [k for k, *_ in STABLE_BENCHMARKS if k.startswith("surv_")]

    for sk, scores in all_scores.items():
        # Shift each sim score from -100..+100 to 0..100, then average
        atk_shifted = [(scores.get(k, 0.0) + 100) / 2 for k in atk_keys]
        surv_shifted = [(scores.get(k, 0.0) + 100) / 2 for k in surv_keys]

        scores["attack_power"] = round(sum(atk_shifted) / len(atk_shifted), 1)
        scores["survivability_score"] = round(sum(surv_shifted) / len(surv_shifted), 1)

    # Compute movement_speed_score (min-max normalized 0-100)
    # Re-read movement speeds from the units
    speed_map = {}
    for u in all_units:
        sk = f"{u['civ_name']}|{u['unit_slug']}"
        speed_map[sk] = u["combat_unit"]["movement_speed"]

    speeds = list(speed_map.values())
    min_speed = min(speeds)
    max_speed = max(speeds)
    speed_range = max_speed - min_speed if max_speed != min_speed else 1

    for sk, scores in all_scores.items():
        raw_speed = speed_map.get(sk, min_speed)
        scores["movement_speed_score"] = round(
            (raw_speed - min_speed) / speed_range * 100, 1
        )

    # Compute composite stable_power
    for sk, scores in all_scores.items():
        scores["stable_power"] = round(
            0.6 * scores["attack_power"]
            + 0.2 * scores["movement_speed_score"]
            + 0.2 * scores["survivability_score"],
            1,
        )

    # Return in the format write_role_scores_to_db expects: {line_age_key: {unit_key: scores}}
    return {"stable|Imperial": all_scores}
```

**Step 3: Verify benchmark slugs exist**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db')
c = conn.cursor()
for slug, civ in [('paladin', 'Spanish'), ('arbalester', 'Chinese'), ('champion', 'Chinese'), ('halberdier', 'Chinese'), ('heavy_camel', 'Turks'), ('elite_camel_archer_berbers', 'Berbers')]:
    c.execute('SELECT COUNT(*) FROM ref_units WHERE unit_slug=? AND civ_name=? AND age=?', (slug, civ, 'Imperial'))
    print(f'{civ} {slug}: {c.fetchone()[0]} rows')
conn.close()
"`

Expected: All 6 benchmarks show `1 rows`.

**Step 4: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: add stable unit benchmark scoring function

Adds STABLE_BENCHMARKS, STABLE_SCORE_TYPES, and compute_stable_role_scores()
with 12 benchmark sims and 0.6*attack + 0.2*speed + 0.2*survivability formula."
```

---

### Task 2: Remove old cavalry lines from compute_battle_scores.py

**Files:**
- Modify: `webapp/compute_battle_scores.py`

**Step 1: Remove the 6 cavalry entries from UNIT_LINES**

Remove these entries from the `UNIT_LINES` dict (lines 186-319 in compute_battle_scores.py):
- `"knight"` (lines 186-211)
- `"light_cav"` (lines 213-221)
- `"camel"` (lines 222-228)
- `"steppe_lancer"` (lines 229-235)
- `"elephant"` (lines 236-246)
- `"all_cavalry"` (lines 290-319)

Keep the siege lines (ram, mangonel, scorpion, trebuchet, bombard_cannon) — they still use round-robin.

**Step 2: Verify no remaining references break**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && python3 -c "from webapp.compute_battle_scores import UNIT_LINES; print([k for k in UNIT_LINES])"`

Expected: Should show militia, spear, shock_infantry, archer, skirmisher, cav_archer, ram, mangonel, scorpion, trebuchet, bombard_cannon — NO cavalry lines.

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "refactor: remove cavalry lines from UNIT_LINES in compute_battle_scores

Knight, light_cav, camel, steppe_lancer, elephant, and all_cavalry removed.
These are replaced by the new stable scoring function."
```

---

### Task 3: Wire stable scoring into main() and --roles-only

**Files:**
- Modify: `webapp/compute_battle_scores.py` (main function, lines 1643-1867)

**Step 1: Add STABLE_LINE_SLUGS to the skip list**

In `main()`, find the lines that check `INFANTRY_LINE_SLUGS or ARCHERY_LINE_SLUGS` (lines 1710, 1793) and add `STABLE_LINE_SLUGS`:

Change:
```python
if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS:
```
To:
```python
if line_slug in INFANTRY_LINE_SLUGS or line_slug in ARCHERY_LINE_SLUGS or line_slug in STABLE_LINE_SLUGS:
```

Wait — since the cavalry lines are now removed from UNIT_LINES entirely (Task 2), this is not needed. The skip checks iterate `UNIT_LINES.items()`, so removed entries won't appear. No change needed here.

**Step 2: Add stable scoring to the --roles-only path**

In `main()`, after the archery scoring block (around line 1677), add:

```python
        stable_start = time.time()
        stable_scores = compute_stable_role_scores()
        write_role_scores_to_db(stable_scores, ["stable"], STABLE_SCORE_TYPES)
        total_stable = sum(len(v) for v in stable_scores.values())
        print(
            f"Stable roles: {total_stable} units in {time.time() - stable_start:.1f}s"
        )
```

**Step 3: Add stable scoring to the full computation path**

In `main()`, after the archery role scoring block (around line 1848), add:

```python
    # Stable role scores (written to DB, not JSON)
    stable_start = time.time()
    stable_scores = compute_stable_role_scores()
    write_role_scores_to_db(stable_scores, ["stable"], STABLE_SCORE_TYPES)
    stable_time = time.time() - stable_start
    total_stable = sum(len(v) for v in stable_scores.values())
    print(
        f"Stable roles: {total_stable} units in {stable_time:.1f}s"
    )
```

**Step 4: Test the scoring function runs end-to-end**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 compute_battle_scores.py --roles-only`

Expected: Should print stable role timing with unit count, no errors.

**Step 5: Verify scores in DB**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT civ_name, unit_slug, score_type, score_value FROM battle_scores WHERE line_slug=\"stable\" ORDER BY score_value DESC LIMIT 20')
for r in c.fetchall():
    print(f'{r[\"civ_name\"]:15} {r[\"unit_slug\"]:30} {r[\"score_type\"]:25} {r[\"score_value\"]:7.1f}')
conn.close()
"`

Expected: 20 rows with stable_power, attack_power, etc. scores. Values should be in 0-100 range.

**Step 6: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: wire stable scoring into main() and --roles-only paths"
```

---

### Task 4: Update app.py — remove old cavalry lines, add stable virtual line

**Files:**
- Modify: `webapp/app.py` (UNIT_LINES dict, lines 1226-1508; INFANTRY/ARCHERY_LINE_SLUGS, lines 1510-1511)

**Step 1: Remove 6 cavalry entries from UNIT_LINES**

Remove from `UNIT_LINES` in app.py:
- `"knight"` (lines 1344-1369)
- `"light_cav"` (lines 1371-1379)
- `"camel"` (lines 1380-1386)
- `"steppe_lancer"` (lines 1387-1393)
- `"elephant"` (lines 1394-1404)
- `"all_cavalry"` (lines 1448-1477)

**Step 2: Add "stable" virtual line entry**

Add after the last `"anti_archer"` entry (before the closing `}` of UNIT_LINES):

```python
    "stable": {
        "name": "Stable Units",
        "building": "Stable",
        "sub_lines": ["knight", "light_cav", "camel", "steppe_lancer", "elephant"],
    },
```

Wait — but we just removed knight/light_cav/camel/steppe_lancer/elephant from UNIT_LINES. The API endpoint iterates `sub_lines` and looks them up in `UNIT_LINES[sub_slug]`. So we need to **keep the individual stable line definitions** in app.py's UNIT_LINES for the API to fetch units, but just not expose them in the frontend sidebar.

Actually re-reading the code at line 1647-1648:
```python
for sub_slug in sub_lines:
    sub_line = UNIT_LINES[sub_slug]
```

The sub_lines entries MUST exist in UNIT_LINES. So the individual cavalry lines must stay in app.py's UNIT_LINES — they're just not directly exposed in the frontend. The only thing that changes is:
1. The frontend no longer shows knight/light_cav/camel/steppe_lancer/elephant/all_cavalry as selectable tabs
2. We add a `"stable"` virtual line that uses those as sub_lines
3. The API `_attach_scores` needs to recognize stable sub-lines and load from DB

**Revised Step 1: Keep cavalry line entries in app.py UNIT_LINES** (they're needed by the sub_lines mechanism). Only remove `"all_cavalry"` since it's fully replaced.

**Revised Step 2: Add "stable" virtual line**

```python
    "stable": {
        "name": "Stable Units",
        "building": "Stable",
        "sub_lines": ["knight", "light_cav", "camel", "steppe_lancer", "elephant"],
    },
```

**Step 3: Add STABLE_LINE_SLUGS set**

After `ARCHERY_LINE_SLUGS` (line 1511), add:

```python
STABLE_LINE_SLUGS = {"knight", "light_cav", "camel", "steppe_lancer", "elephant"}
```

**Step 4: Update _attach_scores to handle stable lines**

In `_attach_scores()` (line 1579), update the condition to also route stable sub-lines through DB scores:

Change:
```python
    _score_line_slugs = [s for s in sub_lines if s in INFANTRY_LINE_SLUGS or s in ARCHERY_LINE_SLUGS]
```
To:
```python
    _score_line_slugs = [s for s in sub_lines if s in INFANTRY_LINE_SLUGS or s in ARCHERY_LINE_SLUGS or s in STABLE_LINE_SLUGS]
```

And in `_attach_scores`:

Change:
```python
        if (sub_slug in INFANTRY_LINE_SLUGS or sub_slug in ARCHERY_LINE_SLUGS) and _db_role_scores:
```
To:
```python
        if (sub_slug in INFANTRY_LINE_SLUGS or sub_slug in ARCHERY_LINE_SLUGS or sub_slug in STABLE_LINE_SLUGS) and _db_role_scores:
```

But wait — the stable scores are stored with `line_slug="stable"` in the DB (from `write_role_scores_to_db`), NOT under "knight", "light_cav", etc. So the DB query `WHERE line_slug IN ('knight', 'light_cav', ...)` won't find them.

Looking at `write_role_scores_to_db()` more carefully: it splits the key `"stable|Imperial"` to get `line_slug="stable"`. So all scores are under `line_slug="stable"`.

The `_score_line_slugs` query fetches by `line_slug`. So we need to query for `"stable"` not the sub-line slugs.

**Revised approach:** Instead of using sub_lines for score loading, add special handling:

Change the score loading block (lines 1564-1577) to also load stable scores:

```python
    # Load role scores from DB
    _db_role_scores = {}
    _score_line_slugs = [s for s in sub_lines if s in INFANTRY_LINE_SLUGS or s in ARCHERY_LINE_SLUGS]
    # For stable virtual line, scores are stored under "stable" line_slug
    if line_slug == "stable":
        _score_line_slugs = ["stable"]
    if _score_line_slugs:
        placeholders = ",".join("?" for _ in _score_line_slugs)
        rc.execute(
            f"SELECT civ_name, unit_slug, score_type, score_value FROM battle_scores WHERE line_slug IN ({placeholders})",
            _score_line_slugs,
        )
        for bs_row in rc.fetchall():
            uk = f"{bs_row['civ_name']}|{bs_row['unit_slug']}"
            _db_role_scores.setdefault(uk, {})[bs_row["score_type"]] = bs_row["score_value"]
```

And update `_attach_scores` to use DB scores for stable sub-lines:

```python
    def _attach_scores(entry, age_key, sub_slug):
        """Attach battle scores: DB role scores for infantry/archery/stable, JSON for other lines."""
        unit_key = f"{entry['civ_name']}|{entry['unit_slug']}"
        if (sub_slug in INFANTRY_LINE_SLUGS or sub_slug in ARCHERY_LINE_SLUGS or line_slug == "stable") and _db_role_scores:
            rs = _db_role_scores.get(unit_key, {})
            for rk, rv in rs.items():
                entry[rk] = rv
        else:
            # Other lines: round-robin + benchmark from JSON
            ...
```

**Step 5: Handle Imperial-only for stable**

The API endpoint iterates both castle and imperial ages. For the stable line, we only want Imperial. The individual sub_lines still have `castle_slug` defined, so Castle age units would be fetched. We need to skip castle for the stable virtual line.

Add after `sub_lines` determination (line 1555):

```python
    # Stable line is Imperial-only
    ages_to_fetch = ["castle", "imperial"]
    if line_slug == "stable":
        ages_to_fetch = ["imperial"]
```

Then in the unit-fetching loop (line 1651), use `ages_to_fetch` instead of hardcoded ages. Or simpler: just return an empty castle list:

After fetching all units (before the return), if stable:
```python
    if line_slug == "stable":
        result["castle"] = []
```

**Step 6: Test the API endpoint**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 -c "
import app
with app.app.test_client() as c:
    resp = c.get('/api/ref/unit-line/stable')
    data = resp.get_json()
    print(f'Castle units: {len(data[\"castle\"])}')
    print(f'Imperial units: {len(data[\"imperial\"])}')
    if data['imperial']:
        u = data['imperial'][0]
        print(f'First: {u[\"civ_name\"]} {u[\"unit_slug\"]}')
        print(f'  stable_power: {u.get(\"stable_power\", \"MISSING\")}')
        print(f'  attack_power: {u.get(\"attack_power\", \"MISSING\")}')
"`

Expected: Castle=0, Imperial has many units, scores present.

**Step 7: Commit**

```bash
git add webapp/app.py
git commit -m "feat: add stable virtual line to app.py API

Adds 'stable' virtual line with sub_lines pointing to 5 cavalry lines.
Removes all_cavalry entry. Scores loaded from battle_scores DB table."
```

---

### Task 5: Update frontend — replace cavalry tabs with single Stable Units tab

**Files:**
- Modify: `webapp/templates/index.html`

**Step 1: Remove 6 cavalry LINE_CONFIG entries**

In the `LINE_CONFIG` object (around lines 801-877), remove:
- `knight` (lines 801-807)
- `light_cav` (lines 808-814)
- `camel` (lines 815-821)
- `steppe_lancer` (lines 822-828)
- `elephant` (lines 829-835)
- `all_cavalry` (lines 871-877)

**Step 2: Add single stable entry**

Add in the Stable section of LINE_CONFIG:

```javascript
                stable: {
                    name: "Stable Units",
                    building: "Stable",
                    castle: null,
                    imperial: "Paladin",
                    hasUnique: true,
                },
```

**Step 3: Add SCORE_BREAKDOWN entries for stable scores**

In the `SCORE_BREAKDOWN` object (around line 899), add:

```javascript
                // Stable score breakdowns
                attack_power: {
                    title: "Attack Power Breakdown",
                    formula: "Average of 6 matchups (3 × 30v30 + 3 × 3K res), shifted to 0-100",
                    subs: [
                        {
                            key: "atk_30v30_vs_paladin",
                            label: "vs Paladin (30v30)",
                            civ: "Spanish",
                            slug: "paladin",
                            mode: "count",
                            count: 30,
                        },
                        {
                            key: "atk_30v30_vs_arb",
                            label: "vs Arbalester (30v30)",
                            civ: "Chinese",
                            slug: "arbalester",
                            mode: "count",
                            count: 30,
                        },
                        {
                            key: "atk_30v30_vs_champ",
                            label: "vs Champion (30v30)",
                            civ: "Chinese",
                            slug: "champion",
                            mode: "count",
                            count: 30,
                        },
                        {
                            key: "atk_3k_vs_paladin",
                            label: "vs Paladin (3K res)",
                            civ: "Spanish",
                            slug: "paladin",
                            mode: "resources",
                            res: 3000,
                        },
                        {
                            key: "atk_3k_vs_arb",
                            label: "vs Arbalester (3K res)",
                            civ: "Chinese",
                            slug: "arbalester",
                            mode: "resources",
                            res: 3000,
                        },
                        {
                            key: "atk_3k_vs_champ",
                            label: "vs Champion (3K res)",
                            civ: "Chinese",
                            slug: "champion",
                            mode: "resources",
                            res: 3000,
                        },
                    ],
                },
                survivability_stable: {
                    title: "Survivability Breakdown",
                    formula: "Average of 6 matchups (3 × 30v30 + 3 × 3K res), shifted to 0-100",
                    subs: [
                        {
                            key: "surv_30v30_vs_halb",
                            label: "vs Halberdier (30v30)",
                            civ: "Chinese",
                            slug: "halberdier",
                            mode: "count",
                            count: 30,
                        },
                        {
                            key: "surv_30v30_vs_camel",
                            label: "vs Heavy Camel (30v30)",
                            civ: "Turks",
                            slug: "heavy_camel",
                            mode: "count",
                            count: 30,
                        },
                        {
                            key: "surv_30v30_vs_ca",
                            label: "vs Camel Archer (30v30)",
                            civ: "Berbers",
                            slug: "elite_camel_archer_berbers",
                            mode: "count",
                            count: 30,
                        },
                        {
                            key: "surv_3k_vs_halb",
                            label: "vs Halberdier (3K res)",
                            civ: "Chinese",
                            slug: "halberdier",
                            mode: "resources",
                            res: 3000,
                        },
                        {
                            key: "surv_3k_vs_camel",
                            label: "vs Heavy Camel (3K res)",
                            civ: "Turks",
                            slug: "heavy_camel",
                            mode: "resources",
                            res: 3000,
                        },
                        {
                            key: "surv_3k_vs_ca",
                            label: "vs Camel Archer (3K res)",
                            civ: "Berbers",
                            slug: "elite_camel_archer_berbers",
                            mode: "resources",
                            res: 3000,
                        },
                    ],
                },
                movement_speed_stable: {
                    title: "Movement Speed",
                    formula: "Min-max normalized within stable units (0-100)",
                    subs: [],
                },
```

**Step 4: Update the table rendering for stable line**

The table rendering function needs to know which score columns to show for the stable line. Look at how the existing rendering handles infantry vs archery vs other lines and follow the same pattern.

Find the table header rendering code and add a case for `stable`:
- Primary sort column: `stable_power`
- Display columns: Stable Power, Attack Power, Speed, Survivability (all clickable for breakdown)

The exact changes depend on the existing rendering code structure. The key score fields to display:
- `stable_power` (composite, primary sort)
- `attack_power` (clickable → shows attack_power breakdown)
- `movement_speed_score` (clickable → shows movement_speed_stable breakdown)
- `survivability_score` (clickable → shows survivability_stable breakdown)

Follow the same rendering pattern used by archery's `ranged_power`, `raw_dps_score`, `survivability_score` columns.

**Step 5: Disable Castle age toggle for stable line**

When `currentLine === "stable"`, hide or disable the Castle/Imperial age toggle buttons. Always show Imperial.

**Step 6: Test the frontend**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 app.py`

Open browser to `http://localhost:5001` (or available port). Verify:
1. Stable section shows single "Stable Units" tab (not 6 separate tabs)
2. Table loads with Imperial units, sorted by stable_power
3. Clicking score cells shows breakdown popover
4. No JavaScript console errors

**Step 7: Commit**

```bash
git add webapp/templates/index.html
git commit -m "feat: replace 6 cavalry tabs with single Stable Units ranking

Shows Imperial-only table sorted by stable_power composite score.
Score breakdown popovers for attack_power, survivability, and speed."
```

---

### Task 6: Remove old cavalry lines from compute_battle_scores.py UNIT_LINES (already done in Task 2)

This task was merged with Task 2. Skip.

---

### Task 7: End-to-end verification

**Step 1: Full recompute**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 compute_battle_scores.py --roles-only`

Expected: Infantry, Archery, and Stable role scores all computed successfully.

**Step 2: Run full compute (with round-robin for siege)**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 compute_battle_scores.py`

Expected: Round-robin for siege lines + role scores for infantry/archery/stable. No errors about missing cavalry lines.

**Step 3: Verify API returns correct data**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && python3 -c "
import sys; sys.path.insert(0, 'webapp')
import app
with app.app.test_client() as c:
    resp = c.get('/api/ref/unit-line/stable')
    data = resp.get_json()
    print(f'Imperial units: {len(data[\"imperial\"])}')
    # Check top 5 by stable_power
    units = sorted(data['imperial'], key=lambda x: x.get('stable_power', 0), reverse=True)
    for u in units[:5]:
        print(f'  {u[\"civ_name\"]:15} {u[\"unit_slug\"]:30} power={u.get(\"stable_power\",0):5.1f} atk={u.get(\"attack_power\",0):5.1f} spd={u.get(\"movement_speed_score\",0):5.1f} surv={u.get(\"survivability_score\",0):5.1f}')
"`

Expected: Top 5 stable units by composite score, all score fields populated.

**Step 4: Visual check in browser**

Start the webapp and verify the Stable Units table looks correct in the browser. Check that all old cavalry tabs are gone.

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address any issues found during end-to-end verification"
```
