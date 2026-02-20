# Speed-Weighted Score Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Multiply each unit's final composite score by its movement speed, then re-normalize to 0-100, so faster units rank higher across all categories.

**Architecture:** A single helper function `_apply_speed_weighting()` handles the multiply-and-renormalize pattern. Each scoring function calls it after computing composites. Speed is stored in the scores dict during the simulation loop so it's available at normalization time.

**Tech Stack:** Python, SQLite (existing `compute_battle_scores.py`)

---

### Task 1: Add the `_apply_speed_weighting` helper function

**Files:**
- Modify: `webapp/compute_battle_scores.py` (add after line ~535, near other helper functions)

**Step 1: Write the helper function**

Add this function near the top of the file, after the existing `calc_weighted_cost` helper (~line 535):

```python
def _apply_speed_weighting(all_scores, score_keys, scope="pool", line_groups=None):
    """Multiply composite scores by movement speed, then re-normalize to 0-100.

    Args:
        all_scores: dict {sk: {score_key: value, "_speed": float, ...}}
        score_keys: list of score keys to apply speed weighting to
        scope: "pool" = normalize across all units; "per_line" = normalize per line group
        line_groups: dict {line_slug: [sk, ...]} — required when scope="per_line"
    """
    if scope == "per_line" and line_groups:
        for key in score_keys:
            for line, sks in line_groups.items():
                # Multiply by speed
                weighted = {}
                for sk in sks:
                    speed = all_scores[sk].get("_speed", 1.0)
                    weighted[sk] = all_scores[sk][key] * speed
                # Re-normalize 0-100
                vals = list(weighted.values())
                lo, hi = min(vals), max(vals)
                span = hi - lo if hi != lo else 1
                for sk in sks:
                    all_scores[sk][key] = round((weighted[sk] - lo) / span * 100, 1)
    else:
        for key in score_keys:
            # Multiply by speed
            weighted = {}
            for sk, scores in all_scores.items():
                speed = scores.get("_speed", 1.0)
                weighted[sk] = scores[key] * speed
            # Re-normalize 0-100
            vals = list(weighted.values())
            lo, hi = min(vals), max(vals)
            span = hi - lo if hi != lo else 1
            for sk in all_scores:
                all_scores[sk][key] = round((weighted[sk] - lo) / span * 100, 1)
```

**Step 2: Verify no syntax errors**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 -c "import compute_battle_scores; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: add _apply_speed_weighting helper for speed-weighted normalization"
```

---

### Task 2: Apply speed weighting to infantry scores

**Files:**
- Modify: `webapp/compute_battle_scores.py` — `compute_infantry_role_scores()` (~lines 1011, 1040-1055), `compute_anti_cav_scores()` (~lines 1648-1651), `compute_raiding_scores()` (~lines 1919-1932)

**Step 1: Store speed during infantry simulation loop**

At line 1011, where `scores["_combat_unit"] = cu` is set, add speed storage:

```python
            scores["_combat_unit"] = cu  # temp ref for anti-cav scoring
            scores["_speed"] = cu["movement_speed"]
```

**Step 2: Apply speed weighting after composites are computed**

After the `militia_value` computation (after line 1055), add:

```python
    # Apply speed weighting: multiply composites by speed, re-normalize 0-100
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "militia_value", "raid_building", "anti_cav_value"],
        scope="pool",
    )
```

**Important ordering note:** This must go AFTER `compute_anti_cav_scores()` and `compute_raiding_scores()` have run (line 1043-1046) and after `militia_value` is computed (line 1049-1055), but BEFORE `_combat_unit` cleanup (line 1058). Since `militia_value` depends on `general_combat`, `anti_cav`, and `raid_building`, we speed-weight all of them together at the end — the composites will use the un-speed-weighted sub-scores, then the final values all get speed-weighted.

**Step 3: Verify computation runs**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 compute_battle_scores.py --roles-only 2>&1 | head -20`
Expected: No errors, infantry/archery/stable scores compute normally.

**Step 4: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: apply speed weighting to infantry composite scores"
```

---

### Task 3: Apply speed weighting to archery scores

**Files:**
- Modify: `webapp/compute_battle_scores.py` — `compute_archery_role_scores()` (~lines 1101-1194)

**Step 1: Store speed during archery simulation loop**

At line 1155, right before `all_scores[sk] = scores`, add speed storage:

```python
            scores["_speed"] = cu["movement_speed"]
            all_scores[sk] = scores
```

(Replace the existing `all_scores[sk] = scores` line.)

**Step 2: Apply speed weighting after composites**

After `ranged_effectiveness` computation (after line 1194), add:

```python
    # Apply speed weighting: multiply composites by speed, re-normalize per line
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_archer", "ranged_effectiveness"],
        scope="per_line",
        line_groups=line_groups,
    )

    # Clean up temp speed refs
    for s in all_scores.values():
        s.pop("_speed", None)
```

Note: `line_groups` already exists from line 1170-1173.

**Step 3: Verify computation runs**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 compute_battle_scores.py --roles-only 2>&1 | head -20`
Expected: No errors.

**Step 4: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: apply speed weighting to archery composite scores (per-line)"
```

---

### Task 4: Apply speed weighting to stable scores

**Files:**
- Modify: `webapp/compute_battle_scores.py` — `compute_stable_role_scores()` (~lines 1290-1379)

**Step 1: Store speed during stable simulation loop**

At line 1344, right before `all_scores[sk] = scores`, add:

```python
        scores["_speed"] = cu["movement_speed"]
        all_scores[sk] = scores
```

(Replace the existing `all_scores[sk] = scores`.)

**Step 2: Apply speed weighting after composites**

After `stable_effectiveness` computation (after line 1376), add:

```python
    # Apply speed weighting: multiply composites by speed, re-normalize across all stable
    _apply_speed_weighting(
        all_scores,
        ["general_combat", "anti_cav", "stable_effectiveness"],
        scope="pool",
    )

    # Clean up temp speed refs
    for s in all_scores.values():
        s.pop("_speed", None)
```

**Step 3: Verify computation runs**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 compute_battle_scores.py --roles-only 2>&1 | head -20`
Expected: No errors.

**Step 4: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: apply speed weighting to stable composite scores"
```

---

### Task 5: Apply speed weighting to siege scores (exempt trebuchets)

**Files:**
- Modify: `webapp/compute_battle_scores.py` — `compute_siege_antibuilding_scores()` (~lines 1476-1533)

**Step 1: Store speed during siege simulation loop**

At line 1517, in the dict being stored in `all_scores`, add speed:

```python
                sk = f"{u['civ_name']}|{u['unit_slug']}"
                all_scores.setdefault((line_slug, age), {})[sk] = {
                    "time_to_kill": round(min(ttk, 600.0), 1),
                    "_speed": cu["movement_speed"],
                }
```

**Step 2: Apply speed weighting after anti_building_score normalization**

After `anti_building_score` is computed (after line 1527), but before the format-for-DB section, add speed weighting for non-trebuchet lines:

```python
    # Apply speed weighting per line (exempt trebuchet — speed=0)
    for (line_slug, age), scores in all_scores.items():
        if line_slug == "trebuchet":
            continue
        weighted = {}
        for sk, s in scores.items():
            speed = s.get("_speed", 1.0)
            weighted[sk] = s["anti_building_score"] * speed
        vals = list(weighted.values())
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi != lo else 1
        for sk in scores:
            scores[sk]["anti_building_score"] = round(
                (weighted[sk] - lo) / span * 100, 1
            )
```

Note: We inline the speed weighting here rather than using `_apply_speed_weighting()` because siege `all_scores` is keyed by `(line_slug, age)` tuples, not flat `sk` keys — a different structure than the other functions.

**Step 3: Clean up `_speed` keys before returning**

After the speed weighting block, add cleanup:

```python
    # Clean up temp speed refs
    for (line_slug, age), scores in all_scores.items():
        for s in scores.values():
            s.pop("_speed", None)
```

**Step 4: Verify computation runs**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 compute_battle_scores.py --roles-only 2>&1 | head -20`
Expected: No errors.

**Step 5: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: apply speed weighting to siege scores (exempt trebuchets)"
```

---

### Task 6: Apply speed weighting to combined anti-cav pool

**Files:**
- Modify: `webapp/compute_battle_scores.py` — `compute_combined_anti_cav_scores()` (~lines 1713-1770)

**Step 1: Store speed when building pool entries**

At line 1721, when infantry units are added to pool, also store speed:

```python
            pool[sk] = _sim_unit_vs_benchmarks(cu)
            pool[sk]["_speed"] = cu["movement_speed"]
```

At line 1746, when stable units are added:

```python
            pool[sk] = _sim_unit_vs_benchmarks(cu)
            pool[sk]["_speed"] = cu["movement_speed"]
            stable_count += 1
```

**Step 2: Apply speed weighting after anti_cav_combined is computed**

After line 1766 (after `anti_cav_combined` computation), add:

```python
    # Apply speed weighting: multiply anti_cav_combined by speed, re-normalize
    _apply_speed_weighting(pool, ["anti_cav_combined"], scope="pool")

    # Clean up temp speed refs
    for p in pool.values():
        p.pop("_speed", None)
```

**Step 3: Verify computation runs**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 compute_battle_scores.py --roles-only 2>&1 | head -20`
Expected: No errors.

**Step 4: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat: apply speed weighting to combined anti-cav pool scores"
```

---

### Task 7: Full recompute and validate results

**Step 1: Run full roles-only recompute**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 compute_battle_scores.py --roles-only
```

Expected: All categories compute without error. Timing output for each category.

**Step 2: Regenerate civ power units**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 best_units.py
```

Expected: Writes `civ_power_units.json` with 50 civs.

**Step 3: Spot-check rankings for expected impact**

Run a quick validation to ensure speed weighting changed rankings as expected:

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && source ../venv/bin/activate && python3 -c "
import sqlite3
conn = sqlite3.connect('aoe2_reference.db')
c = conn.cursor()

# Check infantry: Eagle Warrior should rank higher, Teutonic Knight lower
print('=== Infantry militia_value (top 10) ===')
c.execute('''SELECT civ_name, unit_slug, score_value, rank
             FROM battle_scores
             WHERE score_type='militia_value' AND LOWER(age)='imperial'
             ORDER BY score_value DESC LIMIT 10''')
for r in c.fetchall():
    print(f'  {r[0]:15s} {r[1]:30s} score={r[2]:5.1f} rank={r[3]}')

# Check stable: War Elephant should rank lower vs Paladin
print()
print('=== Stable stable_effectiveness (top 10) ===')
c.execute('''SELECT civ_name, unit_slug, score_value, rank
             FROM battle_scores
             WHERE score_type='stable_effectiveness' AND LOWER(age)='imperial'
             ORDER BY score_value DESC LIMIT 10''')
for r in c.fetchall():
    print(f'  {r[0]:15s} {r[1]:30s} score={r[2]:5.1f} rank={r[3]}')

# Check Teutonic Knight specifically
print()
print('=== Teutonic Knight scores ===')
c.execute('''SELECT score_type, score_value, rank
             FROM battle_scores
             WHERE unit_slug='elite_teutonic_knight_teutons'
               AND LOWER(age)='imperial'
             ORDER BY score_type''')
for r in c.fetchall():
    print(f'  {r[0]:30s} score={r[1]:5.1f} rank={r[2]}')
conn.close()
"
```

Expected: Fast infantry (Eagles, Woad Raiders) rank higher than before; slow infantry (Teutonic Knight) ranks lower. Fast cavalry (Hussars, Paladins) rank higher than War Elephants.

**Step 4: Commit any remaining changes**

If everything looks good, final commit:

```bash
git add -A
git commit -m "chore: regenerate battle scores with speed-weighted normalization"
```
