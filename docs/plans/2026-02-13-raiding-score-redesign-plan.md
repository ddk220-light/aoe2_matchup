# Raiding Score Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace pure-DPS building score with attrition-based N_min formula that models buildings fighting back with arrows.

**Architecture:** O(1) closed-form formula replaces DPS calculation in `compute_raiding_scores()`. Building definitions expanded to 4 variants (castle/tc x with/without Masonry+Architecture). Weights updated to 25/25/50.

**Tech Stack:** Python, math.ceil/math.sqrt, existing compute_battle_scores.py infrastructure.

---

### Task 1: Add math import and replace BUILDING_TARGETS

**Files:**
- Modify: `webapp/compute_battle_scores.py:15` (imports)
- Modify: `webapp/compute_battle_scores.py:1645-1648` (BUILDING_TARGETS)

**Step 1: Add math import**

At line 15 (after `import json`), add:

```python
import math
```

**Step 2: Replace BUILDING_TARGETS**

Replace lines 1645-1648 with:

```python
# Fully upgraded Spanish buildings (Fletching/Bodkin/Bracer/Chemistry always applied).
# Two variants per building: with and without Masonry+Architecture.
BUILDING_TARGETS = {
    "castle_uni": {
        "name": "Castle (Masonry+Arch)",
        "hp": 7028,           # 4800 * 1.1 * 1.1 * 1.21 (Hoardings)
        "melee_armor": 10,    # 8 + 1 + 1
        "building_armor": 6,  # 0 + 3 + 3
        "arrows": 5,          # base (no garrison)
        "arrow_attack": 15,   # 11 + 1 + 1 + 1 + 1 (Chemistry)
        "reload": 2.0,
    },
    "castle_no_uni": {
        "name": "Castle (no uni)",
        "hp": 5808,           # 4800 * 1.21 (Hoardings only)
        "melee_armor": 8,
        "building_armor": 0,
        "arrows": 5,
        "arrow_attack": 15,
        "reload": 2.0,
    },
    "tc_uni": {
        "name": "TC (Masonry+Arch, 15 vills)",
        "hp": 2904,           # 2400 * 1.1 * 1.1
        "melee_armor": 5,     # 3 + 1 + 1
        "building_armor": 6,  # 0 + 3 + 3
        "arrows": 15,         # 1 per garrisoned villager
        "arrow_attack": 9,    # 5 + 1 + 1 + 1 + 1
        "reload": 2.0,
    },
    "tc_no_uni": {
        "name": "TC (no uni, 15 vills)",
        "hp": 2400,
        "melee_armor": 3,
        "building_armor": 0,
        "arrows": 15,
        "arrow_attack": 9,
        "reload": 2.0,
    },
}
```

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "refactor: expand BUILDING_TARGETS to 4 variants with arrow/armor stats"
```

---

### Task 2: Replace building DPS calculation with N_min formula

**Files:**
- Modify: `webapp/compute_battle_scores.py:1684-1697` (section 3 of compute_raiding_scores)

**Step 1: Replace the anti-building DPS section (lines 1684-1697)**

Replace the block starting with `# 3. Anti-building DPS calculation` through the end of the `for bkey` loop with:

```python
    # 3. Anti-building N_min calculation (attrition model with focus fire)
    # Each arrow individually does max(1, arrow_attack - pierce_armor) damage.
    # Building focus-fires one unit at a time; army DPS drops as units die.
    # N_min = ceil((-1 + sqrt(1 + 4*C)) / 2) where C = 2*B*f / (d*h)
    for sk, scores in all_scores.items():
        cu = scores["_combat_unit"]
        attacks = cu.get("attacks", {})
        base_melee = attacks.get(4, 0)  # class 4 = melee
        bonus_vs_buildings = attacks.get(21, 0)  # class 21 = Standard Buildings
        reload_time = 1.0 / cu["attack_speed"] if cu["attack_speed"] > 0 else 2.0
        unit_hp = cu["hp"]
        unit_pierce_armor = cu["pierce_armor"]

        for bkey, bstats in BUILDING_TARGETS.items():
            # Unit DPS vs building (separate armor classes)
            melee_dmg = base_melee - bstats["melee_armor"]
            building_dmg = bonus_vs_buildings - bstats["building_armor"]
            damage_per_hit = max(1, melee_dmg + building_dmg)
            d = damage_per_hit / reload_time  # unit anti-building DPS

            # Building DPS vs unit (each arrow reduced by pierce armor individually)
            dmg_per_arrow = max(1, bstats["arrow_attack"] - unit_pierce_armor)
            f = bstats["arrows"] * dmg_per_arrow / bstats["reload"]  # building DPS

            # Attrition formula: N*(N+1) >= 2*B*f / (d*h)
            B = bstats["hp"]
            C = 2.0 * B * f / (d * unit_hp)
            n_min = math.ceil((-1.0 + math.sqrt(1.0 + 4.0 * C)) / 2.0)
            scores[f"raid_vs_{bkey}_nmin"] = n_min
```

**Step 2: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: replace building DPS with attrition N_min formula"
```

---

### Task 3: Update normalization and composite calculation

**Files:**
- Modify: `webapp/compute_battle_scores.py:1717-1739` (normalization + composite + weights)

**Step 1: Replace the building normalization block**

Replace from `# Normalize each building DPS sub-score 0–100` through the end of `raiding_value` computation (lines 1717-1739) with:

```python
    # Normalize N_min sub-scores: average the two variants per building type
    # Then normalize 0-100 (inverted: lower N = higher score)
    for sk, scores in all_scores.items():
        scores["raid_vs_castle_nmin"] = (
            scores.pop("raid_vs_castle_uni_nmin") + scores.pop("raid_vs_castle_no_uni_nmin")
        ) / 2.0
        scores["raid_vs_tc_nmin"] = (
            scores.pop("raid_vs_tc_uni_nmin") + scores.pop("raid_vs_tc_no_uni_nmin")
        ) / 2.0

    for bkey in ("castle", "tc"):
        nmin_key = f"raid_vs_{bkey}_nmin"
        vals = [s[nmin_key] for s in all_scores.values()]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for s in all_scores.values():
            # Invert: lowest N_min → 100 (best raider), highest → 0
            s[nmin_key] = round((hi - s[nmin_key]) / span * 100, 1)

    # Compute building composite (average of TC and Castle N_min scores)
    for sk, scores in all_scores.items():
        scores["raid_building"] = round(
            (scores["raid_vs_tc_nmin"] + scores["raid_vs_castle_nmin"]) / 2, 1
        )

    # Compute weighted composite (25% speed, 25% vill kill, 50% building)
    for sk, scores in all_scores.items():
        scores["raiding_value"] = round(
            0.25 * scores["raid_speed"]
            + 0.25 * scores["raid_vill_kill"]
            + 0.50 * scores["raid_building"],
            1,
        )
```

**Step 2: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: update raiding normalization to N_min with 25/25/50 weights"
```

---

### Task 4: Update score type list

**Files:**
- Modify: `webapp/compute_battle_scores.py:1557-1563` (INFANTRY_ROLE_SCORE_TYPES)

**Step 1: Replace old DPS score type names with N_min names**

In the `INFANTRY_ROLE_SCORE_TYPES` list, replace:

```python
    "raid_vs_tc_dps",
    "raid_vs_castle_dps",
```

with:

```python
    "raid_vs_tc_nmin",
    "raid_vs_castle_nmin",
```

**Step 2: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "refactor: rename raid score types from dps to nmin"
```

---

### Task 5: Update frontend score references

**Files:**
- Modify: `webapp/templates/index.html` (score key references and labels)

**Step 1: Update the score breakdown definitions (~line 1012-1026)**

Replace the `raid_building` breakdown object:

```javascript
                raid_building: {
                    title: "Anti-Building DPS",
                    formula:
                        "Average of melee DPS vs Imperial Town Center and Castle (normalized 0\u2013100)",
                    subs: [
                        {
                            key: "raid_vs_tc_dps",
                            label: "vs Town Center",
                        },
                        {
                            key: "raid_vs_castle_dps",
                            label: "vs Castle",
                        },
                    ],
                },
```

with:

```javascript
                raid_building: {
                    title: "Building Destruction",
                    formula:
                        "Min units to destroy building (attrition model, building fights back). Avg of upgraded/non-upgraded variants. Lower N = higher score.",
                    subs: [
                        {
                            key: "raid_vs_tc_nmin",
                            label: "vs Town Center",
                        },
                        {
                            key: "raid_vs_castle_nmin",
                            label: "vs Castle",
                        },
                    ],
                },
```

**Step 2: Update the score type list (~line 1238-1239)**

Replace:

```javascript
                "raid_vs_tc_dps",
                "raid_vs_castle_dps",
```

with:

```javascript
                "raid_vs_tc_nmin",
                "raid_vs_castle_nmin",
```

**Step 3: Update the filter conditions (~line 2538-2539)**

Replace:

```javascript
                        k === "raid_vs_tc_dps" ||
                        k === "raid_vs_castle_dps" ||
```

with:

```javascript
                        k === "raid_vs_tc_nmin" ||
                        k === "raid_vs_castle_nmin" ||
```

**Step 4: Commit**

```bash
git add webapp/templates/index.html
git commit -m "feat: update frontend raid score keys and labels for N_min"
```

---

### Task 6: Run compute_battle_scores and validate

**Step 1: Run the score computation**

```bash
cd webapp && python3 compute_battle_scores.py --roles-only
```

Expected: completes without errors, prints score counts.

**Step 2: Spot-check Champion scores**

Query the reference DB for a known Champion to verify N_min values match the design doc validation:

```bash
cd webapp && python3 -c "
import sqlite3
conn = sqlite3.connect('aoe2_reference.db')
c = conn.cursor()
rows = c.execute('''
    SELECT score_type, score_value FROM battle_scores
    WHERE unit_slug='champion' AND civ_name='Spanish'
    AND score_type IN ('raid_vs_tc_nmin','raid_vs_castle_nmin','raid_building','raiding_value','raid_speed','raid_vill_kill')
''').fetchall()
for r in rows:
    print(f'{r[0]:25s} = {r[1]}')
conn.close()
"
```

Verify `raid_vs_castle_nmin` and `raid_vs_tc_nmin` are normalized 0-100 values (not raw N counts).

**Step 3: Commit (if any fixes were needed)**

```bash
git add webapp/compute_battle_scores.py
git commit -m "fix: address any issues found during validation"
```

---

### Task 7: Final integration test

**Step 1: Start the webapp and verify the raiding tab loads**

```bash
cd webapp && python3 app.py --port 5050 &
sleep 2
curl -s http://localhost:5050/api/infantry-rankings | python3 -m json.tool | head -50
kill %1
```

Verify the API response includes `raiding_value`, `raid_speed`, `raid_vill_kill`, `raid_building`, `raid_vs_tc_nmin`, `raid_vs_castle_nmin` for each unit.

**Step 2: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: complete raiding score redesign with attrition N_min formula"
```
