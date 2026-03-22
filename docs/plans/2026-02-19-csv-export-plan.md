# CSV Export for Unit Rankings — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-category CSV export buttons to the unit rankings page that include all scores (composite, sub-scores raw + normalized), rank, and unit stats.

**Architecture:** Modify `compute_battle_scores.py` to persist raw (pre-normalization) scores with `_raw` suffix alongside normalized scores. The API already serves all `battle_scores` rows automatically. Add a client-side `exportCSV()` function in `rankings.js` that builds CSV from `currentEnriched[]` and triggers a browser download. Push to remote at the end.

**Tech Stack:** Python (compute_battle_scores.py), Flask (app.py), Vanilla JS (rankings.js), CSS (rankings.css)

---

### Task 1: Persist Raw Infantry Scores Before Normalization

**Files:**
- Modify: `webapp/compute_battle_scores.py:988-998` (infantry normalization)
- Modify: `webapp/compute_battle_scores.py:1480-1510` (INFANTRY_ROLE_SCORE_TYPES)

**Step 1: Save raw scores before normalization in `compute_infantry_role_scores()`**

At line 991, before the normalization loop, insert code to copy raw values with `_raw` suffix:

```python
    # Save raw scores before normalization
    bench_keys = [k for k, _, _, _, _, _ in MILITIA_ROLE_BENCHMARKS]
    for key in bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Normalize each benchmark score to 0–100 across ALL infantry units
    for key in bench_keys:
```

Note: the `bench_keys` line already exists at 992; move it above the new block and remove the duplicate.

**Step 2: Add raw score types to INFANTRY_ROLE_SCORE_TYPES**

Add these entries to the list at line 1480:

```python
INFANTRY_ROLE_SCORE_TYPES = [
    "militia_value",
    "general_combat",
    "anti_cav",
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "ac_30v30_vs_elephant",
    "ac_30v30_vs_hussar",
    "ac_3k_vs_elephant",
    "ac_3k_vs_hussar",
    # Raw (pre-normalization) scores
    "gc_30v30_vs_paladin_raw",
    "gc_30v30_vs_arb_raw",
    "gc_30v30_vs_champ_raw",
    "gc_3k_vs_paladin_raw",
    "gc_3k_vs_arb_raw",
    "gc_3k_vs_champ_raw",
    "ac_30v30_vs_elephant_raw",
    "ac_30v30_vs_hussar_raw",
    "ac_3k_vs_elephant_raw",
    "ac_3k_vs_hussar_raw",
    # Anti-cav ranking scores
    "anti_cav_total",
    ...  # rest unchanged
]
```

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: persist raw infantry scores before normalization"
```

---

### Task 2: Persist Raw Archery Scores Before Normalization

**Files:**
- Modify: `webapp/compute_battle_scores.py:1128-1138` (archery normalization)
- Modify: `webapp/compute_battle_scores.py:855-876` (ARCHERY_ROLE_SCORE_TYPES)

**Step 1: Save raw scores before archery normalization in `compute_archery_role_scores()`**

At line 1128, before the normalization loop, insert:

```python
    # Save raw scores before normalization
    gc_keys = [k for k, *_ in ARCHERY_ROLE_BENCHMARKS if k.startswith("gc_")]
    aa_keys = [k for k, *_ in ARCHERY_ROLE_BENCHMARKS if k.startswith("aa_")]
    all_bench_keys = gc_keys + aa_keys

    for key in all_bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Min-max normalize each benchmark score across all archery units (0-100)
    for bk in all_bench_keys:
```

Note: `gc_keys`, `aa_keys`, `all_bench_keys` already exist at 1129-1131; move them above the raw-save block and remove duplicates.

**Step 2: Add raw score types to ARCHERY_ROLE_SCORE_TYPES**

```python
ARCHERY_ROLE_SCORE_TYPES = [
    "ranged_effectiveness",
    "general_combat",
    "anti_archer",
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "aa_30v30_vs_arb",
    "aa_30v30_vs_ca",
    "aa_30v30_vs_ele_archer",
    "aa_3k_vs_arb",
    "aa_3k_vs_ca",
    "aa_3k_vs_ele_archer",
    # Raw (pre-normalization) scores
    "gc_30v30_vs_paladin_raw",
    "gc_30v30_vs_arb_raw",
    "gc_30v30_vs_champ_raw",
    "gc_3k_vs_paladin_raw",
    "gc_3k_vs_arb_raw",
    "gc_3k_vs_champ_raw",
    "aa_30v30_vs_arb_raw",
    "aa_30v30_vs_ca_raw",
    "aa_30v30_vs_ele_archer_raw",
    "aa_3k_vs_arb_raw",
    "aa_3k_vs_ca_raw",
    "aa_3k_vs_ele_archer_raw",
    # Mobility ranking scores
    "mobility_score",
    "mobility_speed_dps",
    "mobility_pierce_armor",
    "mobility_hp",
]
```

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: persist raw archery scores before normalization"
```

---

### Task 3: Persist Raw Stable Scores Before Normalization

**Files:**
- Modify: `webapp/compute_battle_scores.py:1295-1305` (stable normalization)
- Modify: `webapp/compute_battle_scores.py:903-917` (STABLE_SCORE_TYPES)

**Step 1: Save raw scores before stable normalization in `compute_stable_role_scores()`**

At line 1295, before normalization, insert:

```python
    # Save raw scores before normalization
    gc_keys = [k for k, *_ in STABLE_BENCHMARKS if k.startswith("gc_")]
    ac_only_keys = [k for k, *_ in STABLE_BENCHMARKS if k.startswith("ac_")]
    all_bench_keys = gc_keys + ac_only_keys

    for key in all_bench_keys:
        for s in all_scores.values():
            s[f"{key}_raw"] = s[key]

    # Min-max normalize each benchmark score across all stable units (0-100)
    for bk in all_bench_keys:
```

Note: same pattern — move existing variable declarations above the raw-save block, remove duplicates.

**Step 2: Add raw score types to STABLE_SCORE_TYPES**

```python
STABLE_SCORE_TYPES = [
    "stable_effectiveness",
    "general_combat",
    "anti_cav",
    "gc_30v30_vs_paladin",
    "gc_30v30_vs_arb",
    "gc_30v30_vs_champ",
    "gc_3k_vs_paladin",
    "gc_3k_vs_arb",
    "gc_3k_vs_champ",
    "ac_30v30_vs_heavy_camel",
    "ac_30v30_vs_elephant",
    "ac_3k_vs_heavy_camel",
    "ac_3k_vs_elephant",
    # Raw (pre-normalization) scores
    "gc_30v30_vs_paladin_raw",
    "gc_30v30_vs_arb_raw",
    "gc_30v30_vs_champ_raw",
    "gc_3k_vs_paladin_raw",
    "gc_3k_vs_arb_raw",
    "gc_3k_vs_champ_raw",
    "ac_30v30_vs_heavy_camel_raw",
    "ac_30v30_vs_elephant_raw",
    "ac_3k_vs_heavy_camel_raw",
    "ac_3k_vs_elephant_raw",
]
```

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: persist raw stable scores before normalization"
```

---

### Task 4: Persist Raw Siege Scores (TTK is Already Raw)

**Files:**
- Modify: `webapp/compute_battle_scores.py:1343-1346` (SIEGE_SCORE_TYPES)

Siege scores work differently: `time_to_kill` IS the raw value (seconds), and `anti_building_score` is the normalized 0-100 version. Both are already stored. No code changes needed to the computation function.

**Step 1: Verify siege already stores both**

Confirm `time_to_kill` (raw TTK in seconds) and `anti_building_score` (normalized 0-100) are both in SIEGE_SCORE_TYPES. They are — no change needed here.

**Step 2: Commit (skip — no changes)**

---

### Task 5: Recompute Battle Scores

**Files:**
- Run: `webapp/compute_battle_scores.py`

**Step 1: Run full recompute to populate raw scores**

```bash
cd /home/claude-wukong/aoe2-unit-analyzer/webapp && python3 compute_battle_scores.py --full
```

Expected: Completes successfully, "Wrote N battle_scores rows to DB" with higher counts than before (raw types added).

**Step 2: Verify raw scores exist in DB**

```bash
cd /home/claude-wukong/aoe2-unit-analyzer/webapp && python3 -c "
import sqlite3
conn = sqlite3.connect('aoe2_reference.db')
c = conn.cursor()
c.execute(\"SELECT COUNT(*) FROM battle_scores WHERE score_type LIKE '%_raw'\")
print(f'Raw scores: {c.fetchone()[0]}')
c.execute(\"SELECT DISTINCT score_type FROM battle_scores WHERE score_type LIKE '%_raw' ORDER BY score_type\")
for r in c.fetchall(): print(f'  {r[0]}')
conn.close()
"
```

Expected: Multiple raw score types listed.

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "chore: recompute battle scores with raw values"
```

---

### Task 6: Add CSV Export Function to rankings.js

**Files:**
- Modify: `webapp/static/js/rankings.js` (add exportCSV function before the INIT section at line ~1256)

**Step 1: Add the exportCSV function**

Insert before `// ===== INIT =====` (line 1256):

```javascript
// ===== CSV EXPORT =====
function exportCSV() {
    if (!currentEnriched || currentEnriched.length === 0) return;

    const isInfantry = INFANTRY_SLUGS.has(currentLine);
    const isArchery = ARCHERY_SLUGS.has(currentLine);
    const isSiege = SIEGE_SLUGS.has(currentLine);
    const isStable = currentLine === "stable";

    // Sort by primary composite score descending to compute rank
    const primaryScore = isInfantry ? "militia_value"
        : isArchery ? "ranged_effectiveness"
        : isStable ? "stable_effectiveness"
        : isSiege ? "anti_building_score"
        : "pes";
    const ranked = [...currentEnriched].sort((a, b) => {
        const va = a[primaryScore] ?? -999;
        const vb = b[primaryScore] ?? -999;
        return vb - va;
    });
    const rankMap = new Map();
    ranked.forEach((row, i) => rankMap.set(row, i + 1));

    // Define columns per category
    let csvColumns;
    if (isInfantry) {
        csvColumns = [
            { key: "_rank", label: "Rank" },
            { key: "civ_name", label: "Civilization" },
            { key: "unit_name", label: "Unit" },
            { key: "line_slug", label: "Line" },
            { key: "is_unique", label: "Is Unique" },
            // Composite scores
            { key: "militia_value", label: "Overall Score" },
            { key: "general_combat", label: "General Combat" },
            { key: "anti_cav", label: "Anti-Cav" },
            { key: "raid_building", label: "Anti-Building" },
            // GC sub-scores (normalized)
            { key: "gc_30v30_vs_paladin", label: "GC vs Paladin 30v30 (norm)" },
            { key: "gc_30v30_vs_arb", label: "GC vs Arbalester 30v30 (norm)" },
            { key: "gc_30v30_vs_champ", label: "GC vs Champion 30v30 (norm)" },
            { key: "gc_3k_vs_paladin", label: "GC vs Paladin 3K (norm)" },
            { key: "gc_3k_vs_arb", label: "GC vs Arbalester 3K (norm)" },
            { key: "gc_3k_vs_champ", label: "GC vs Champion 3K (norm)" },
            // GC sub-scores (raw)
            { key: "gc_30v30_vs_paladin_raw", label: "GC vs Paladin 30v30 (raw)" },
            { key: "gc_30v30_vs_arb_raw", label: "GC vs Arbalester 30v30 (raw)" },
            { key: "gc_30v30_vs_champ_raw", label: "GC vs Champion 30v30 (raw)" },
            { key: "gc_3k_vs_paladin_raw", label: "GC vs Paladin 3K (raw)" },
            { key: "gc_3k_vs_arb_raw", label: "GC vs Arbalester 3K (raw)" },
            { key: "gc_3k_vs_champ_raw", label: "GC vs Champion 3K (raw)" },
            // AC sub-scores (normalized)
            { key: "ac_30v30_vs_elephant", label: "AC vs War Elephant 30v30 (norm)" },
            { key: "ac_30v30_vs_hussar", label: "AC vs Hussar 30v30 (norm)" },
            { key: "ac_3k_vs_elephant", label: "AC vs War Elephant 3K (norm)" },
            { key: "ac_3k_vs_hussar", label: "AC vs Hussar 3K (norm)" },
            // AC sub-scores (raw)
            { key: "ac_30v30_vs_elephant_raw", label: "AC vs War Elephant 30v30 (raw)" },
            { key: "ac_30v30_vs_hussar_raw", label: "AC vs Hussar 30v30 (raw)" },
            { key: "ac_3k_vs_elephant_raw", label: "AC vs War Elephant 3K (raw)" },
            { key: "ac_3k_vs_hussar_raw", label: "AC vs Hussar 3K (raw)" },
            // Raid sub-scores (normalized)
            { key: "raid_vs_tc_nmin", label: "Raid vs TC (norm)" },
            { key: "raid_vs_castle_nmin", label: "Raid vs Castle (norm)" },
            // Unit stats
            { key: "dps", label: "DPS" },
            { key: "final_hp", label: "HP" },
            { key: "final_attack", label: "Attack" },
            { key: "final_melee_armor", label: "Melee Armor" },
            { key: "final_pierce_armor", label: "Pierce Armor" },
            { key: "final_speed", label: "Speed" },
            { key: "total_cost", label: "Total Cost" },
            { key: "total_upgrade_cost", label: "Upgrade Cost" },
        ];
    } else if (isArchery) {
        csvColumns = [
            { key: "_rank", label: "Rank" },
            { key: "civ_name", label: "Civilization" },
            { key: "unit_name", label: "Unit" },
            { key: "line_slug", label: "Line" },
            { key: "is_unique", label: "Is Unique" },
            // Composite scores
            { key: "ranged_effectiveness", label: "Ranged Effectiveness" },
            { key: "general_combat", label: "General Combat" },
            { key: "anti_archer", label: "Anti-Archer" },
            // GC sub-scores (normalized)
            { key: "gc_30v30_vs_paladin", label: "GC vs Paladin 30v30 (norm)" },
            { key: "gc_30v30_vs_arb", label: "GC vs Arbalester 30v30 (norm)" },
            { key: "gc_30v30_vs_champ", label: "GC vs Champion 30v30 (norm)" },
            { key: "gc_3k_vs_paladin", label: "GC vs Paladin 3K (norm)" },
            { key: "gc_3k_vs_arb", label: "GC vs Arbalester 3K (norm)" },
            { key: "gc_3k_vs_champ", label: "GC vs Champion 3K (norm)" },
            // GC sub-scores (raw)
            { key: "gc_30v30_vs_paladin_raw", label: "GC vs Paladin 30v30 (raw)" },
            { key: "gc_30v30_vs_arb_raw", label: "GC vs Arbalester 30v30 (raw)" },
            { key: "gc_30v30_vs_champ_raw", label: "GC vs Champion 30v30 (raw)" },
            { key: "gc_3k_vs_paladin_raw", label: "GC vs Paladin 3K (raw)" },
            { key: "gc_3k_vs_arb_raw", label: "GC vs Arbalester 3K (raw)" },
            { key: "gc_3k_vs_champ_raw", label: "GC vs Champion 3K (raw)" },
            // AA sub-scores (normalized)
            { key: "aa_30v30_vs_arb", label: "AA vs Arbalester 30v30 (norm)" },
            { key: "aa_30v30_vs_ca", label: "AA vs Cav Archer 30v30 (norm)" },
            { key: "aa_30v30_vs_ele_archer", label: "AA vs Ele Archer 30v30 (norm)" },
            { key: "aa_3k_vs_arb", label: "AA vs Arbalester 3K (norm)" },
            { key: "aa_3k_vs_ca", label: "AA vs Cav Archer 3K (norm)" },
            { key: "aa_3k_vs_ele_archer", label: "AA vs Ele Archer 3K (norm)" },
            // AA sub-scores (raw)
            { key: "aa_30v30_vs_arb_raw", label: "AA vs Arbalester 30v30 (raw)" },
            { key: "aa_30v30_vs_ca_raw", label: "AA vs Cav Archer 30v30 (raw)" },
            { key: "aa_30v30_vs_ele_archer_raw", label: "AA vs Ele Archer 30v30 (raw)" },
            { key: "aa_3k_vs_arb_raw", label: "AA vs Arbalester 3K (raw)" },
            { key: "aa_3k_vs_ca_raw", label: "AA vs Cav Archer 3K (raw)" },
            { key: "aa_3k_vs_ele_archer_raw", label: "AA vs Ele Archer 3K (raw)" },
            // Unit stats
            { key: "dps", label: "DPS" },
            { key: "final_hp", label: "HP" },
            { key: "final_attack", label: "Attack" },
            { key: "final_melee_armor", label: "Melee Armor" },
            { key: "final_pierce_armor", label: "Pierce Armor" },
            { key: "final_speed", label: "Speed" },
            { key: "final_range", label: "Range" },
            { key: "total_cost", label: "Total Cost" },
            { key: "total_upgrade_cost", label: "Upgrade Cost" },
        ];
    } else if (isStable) {
        csvColumns = [
            { key: "_rank", label: "Rank" },
            { key: "civ_name", label: "Civilization" },
            { key: "unit_name", label: "Unit" },
            { key: "line_slug", label: "Line" },
            { key: "is_unique", label: "Is Unique" },
            // Composite scores
            { key: "stable_effectiveness", label: "Stable Effectiveness" },
            { key: "general_combat", label: "General Combat" },
            { key: "anti_cav", label: "Anti-Cav" },
            // GC sub-scores (normalized)
            { key: "gc_30v30_vs_paladin", label: "GC vs Paladin 30v30 (norm)" },
            { key: "gc_30v30_vs_arb", label: "GC vs Arbalester 30v30 (norm)" },
            { key: "gc_30v30_vs_champ", label: "GC vs Champion 30v30 (norm)" },
            { key: "gc_3k_vs_paladin", label: "GC vs Paladin 3K (norm)" },
            { key: "gc_3k_vs_arb", label: "GC vs Arbalester 3K (norm)" },
            { key: "gc_3k_vs_champ", label: "GC vs Champion 3K (norm)" },
            // GC sub-scores (raw)
            { key: "gc_30v30_vs_paladin_raw", label: "GC vs Paladin 30v30 (raw)" },
            { key: "gc_30v30_vs_arb_raw", label: "GC vs Arbalester 30v30 (raw)" },
            { key: "gc_30v30_vs_champ_raw", label: "GC vs Champion 30v30 (raw)" },
            { key: "gc_3k_vs_paladin_raw", label: "GC vs Paladin 3K (raw)" },
            { key: "gc_3k_vs_arb_raw", label: "GC vs Arbalester 3K (raw)" },
            { key: "gc_3k_vs_champ_raw", label: "GC vs Champion 3K (raw)" },
            // AC sub-scores (normalized)
            { key: "ac_30v30_vs_heavy_camel", label: "AC vs Heavy Camel 30v30 (norm)" },
            { key: "ac_30v30_vs_elephant", label: "AC vs Battle Elephant 30v30 (norm)" },
            { key: "ac_3k_vs_heavy_camel", label: "AC vs Heavy Camel 3K (norm)" },
            { key: "ac_3k_vs_elephant", label: "AC vs Battle Elephant 3K (norm)" },
            // AC sub-scores (raw)
            { key: "ac_30v30_vs_heavy_camel_raw", label: "AC vs Heavy Camel 30v30 (raw)" },
            { key: "ac_30v30_vs_elephant_raw", label: "AC vs Battle Elephant 30v30 (raw)" },
            { key: "ac_3k_vs_heavy_camel_raw", label: "AC vs Heavy Camel 3K (raw)" },
            { key: "ac_3k_vs_elephant_raw", label: "AC vs Battle Elephant 3K (raw)" },
            // Unit stats
            { key: "dps", label: "DPS" },
            { key: "final_hp", label: "HP" },
            { key: "final_attack", label: "Attack" },
            { key: "final_melee_armor", label: "Melee Armor" },
            { key: "final_pierce_armor", label: "Pierce Armor" },
            { key: "final_speed", label: "Speed" },
            { key: "total_cost", label: "Total Cost" },
            { key: "total_upgrade_cost", label: "Upgrade Cost" },
        ];
    } else if (isSiege) {
        csvColumns = [
            { key: "_rank", label: "Rank" },
            { key: "civ_name", label: "Civilization" },
            { key: "unit_name", label: "Unit" },
            { key: "line_slug", label: "Line" },
            { key: "is_unique", label: "Is Unique" },
            // Scores (anti_building_score is normalized, time_to_kill is raw)
            { key: "anti_building_score", label: "Anti-Building Score (norm)" },
            { key: "time_to_kill", label: "Time To Kill seconds (raw)" },
            // Unit stats
            { key: "dps", label: "DPS" },
            { key: "final_hp", label: "HP" },
            { key: "final_attack", label: "Attack" },
            { key: "final_melee_armor", label: "Melee Armor" },
            { key: "final_pierce_armor", label: "Pierce Armor" },
            { key: "final_speed", label: "Speed" },
            { key: "final_range", label: "Range" },
            { key: "total_cost", label: "Total Cost" },
            { key: "total_upgrade_cost", label: "Upgrade Cost" },
        ];
    } else {
        // Default/fallback (other lines with round-robin scores)
        csvColumns = [
            { key: "_rank", label: "Rank" },
            { key: "civ_name", label: "Civilization" },
            { key: "unit_name", label: "Unit" },
            { key: "is_unique", label: "Is Unique" },
            { key: "pes", label: "PES" },
            { key: "res", label: "RES" },
            { key: "score_30v30", label: "30v30" },
            { key: "score_3k", label: "3K Res" },
            { key: "score_5k", label: "5K+Upg" },
            { key: "pop_vs_champ", label: "30v Champ" },
            { key: "pop_vs_paladin", label: "30v Paladin" },
            { key: "pop_vs_arb", label: "30v Arbalester" },
            { key: "vs_champ", label: "vs Champ" },
            { key: "vs_paladin", label: "vs Paladin" },
            { key: "vs_arb", label: "vs Arbalester" },
            { key: "dps", label: "DPS" },
            { key: "final_hp", label: "HP" },
            { key: "final_attack", label: "Attack" },
            { key: "final_melee_armor", label: "Melee Armor" },
            { key: "final_pierce_armor", label: "Pierce Armor" },
            { key: "final_speed", label: "Speed" },
            { key: "final_range", label: "Range" },
            { key: "total_cost", label: "Total Cost" },
            { key: "total_upgrade_cost", label: "Upgrade Cost" },
        ];
    }

    // Build CSV content
    const headers = csvColumns.map(c => c.label);
    const csvRows = [headers.join(",")];

    for (const row of currentEnriched) {
        const vals = csvColumns.map(col => {
            if (col.key === "_rank") return rankMap.get(row) ?? "";
            if (col.key === "is_unique") return row.is_unique ? "Yes" : "No";
            if (col.key === "line_slug") return LINE_LABELS[row.line_slug] || row.line_slug || "";
            const v = row[col.key];
            if (v === undefined || v === null || v <= -999) return "";
            if (typeof v === "string") {
                // Escape quotes in strings
                return `"${v.replace(/"/g, '""')}"`;
            }
            return typeof v === "number" ? v : v;
        });
        csvRows.push(vals.join(","));
    }

    // Trigger download
    const csvContent = csvRows.join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const lineName = currentLine || "units";
    const age = currentAge.toLowerCase();
    a.href = url;
    a.download = `${lineName}_${age}_rankings.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
```

**Step 2: Commit**

```bash
git add webapp/static/js/rankings.js
git commit -m "feat: add CSV export function to rankings page"
```

---

### Task 7: Add Export Button to Rankings UI

**Files:**
- Modify: `webapp/static/js/rankings.js:1126-1137` (renderTable civ-filter-wrap HTML)
- Modify: `webapp/static/css/rankings.css` (add export button styles)

**Step 1: Add export button to the civ-filter-wrap in renderTable()**

In the `renderTable()` function around line 1126, modify the HTML that builds the `civ-filter-wrap` div. After the civ filter input (and before the line-filters), add the export button:

```javascript
    let html = `<div class="civ-filter-wrap">
        <input type="text" id="civFilterInput" placeholder="Filter by civilization..." value="${civFilter}" oninput="renderTable()" />
        <button class="export-btn" onclick="exportCSV()" title="Export current view as CSV">Export CSV</button>`;
```

**Step 2: Add CSS for the export button**

Append to `webapp/static/css/rankings.css`:

```css
/* Export CSV button */
.export-btn {
    font-family: "Cinzel", serif;
    font-size: 0.75rem;
    padding: 6px 14px;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    background: var(--bg-warm);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}
.export-btn:hover {
    border-color: var(--gold-dark);
    color: var(--text);
    background: var(--bg);
}
```

**Step 3: Commit**

```bash
git add webapp/static/js/rankings.js webapp/static/css/rankings.css
git commit -m "feat: add export CSV button to rankings UI"
```

---

### Task 8: Manual Verification

**Step 1: Start the Flask dev server**

```bash
cd /home/claude-wukong/aoe2-unit-analyzer/webapp && python3 app.py
```

**Step 2: Test in browser**

1. Open the rankings page
2. Select Infantry tab → click "Export CSV" → verify file downloads with correct columns and raw scores
3. Select Archery tab → click "Export CSV" → verify
4. Select Stable tab → click "Export CSV" → verify
5. Select Siege tab → click "Export CSV" → verify
6. Apply a civ filter (e.g., "Chinese") → export → verify only filtered rows appear
7. Switch to Castle Age → export → verify age in filename

**Step 3: Commit any fixes if needed**

---

### Task 9: Push to Remote

**Step 1: Push**

```bash
cd /home/claude-wukong/aoe2-unit-analyzer && git push
```
