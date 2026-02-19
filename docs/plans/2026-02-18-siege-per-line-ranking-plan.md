# Siege Per-Line Ranking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rank each siege line (rams, trebuchets, bombard cannons) independently against other civs' versions of the same line, instead of pooling all siege into one ranking.

**Architecture:** Change `compute_siege_antibuilding_scores()` to store scores keyed by actual line_slug instead of generic "siege". Update both `write_role_scores_to_db` call sites and `ROLE_DEFS` in best_units.py. Normalization changes to per-line so each line's scores range 0-100 independently.

**Tech Stack:** Python (compute_battle_scores.py, best_units.py)

---

### Task 1: Restructure `compute_siege_antibuilding_scores()` for per-line storage

**Files:**
- Modify: `webapp/compute_battle_scores.py:1406-1480`

**Step 1: Change data structure from `all_scores[age]` to `all_scores[(line_slug, age)]`**

The current code stores all siege units (rams, trebs, bbc) in a flat `all_scores[age]` dict. Change to store per `(line_slug, age)` so each line is separate.

In `compute_siege_antibuilding_scores()`, replace the entire accumulation and normalization logic:

```python
def compute_siege_antibuilding_scores():
    """Compute anti-building scores for all siege units (Castle + Imperial).

    Each unit gets 1000 weighted resources. They attack a fully upgraded
    Spanish Castle. Ranked by time to destroy (faster = higher score).

    Returns dict in write_role_scores_to_db format, keyed per line_slug.
    """
    castle = SIEGE_CASTLE_TARGET
    all_scores = {}  # (line_slug, age) -> {sk: scores}

    for age in ["castle", "imperial"]:
        is_imperial = age == "imperial"

        for line_slug in SIEGE_LINE_SLUGS:
            units = build_line_units(line_slug, age)
            if not units:
                continue

            for u in units:
                cu = u["combat_unit"]
                unit_cost = calc_weighted_cost(
                    cu["cost_food"], cu["cost_wood"], cu["cost_gold"], is_imperial
                )
                n_units = max(1, 1000 // unit_cost)

                # Damage per hit vs castle (full AoE2 damage model)
                attacks = cu.get("attacks", {})
                damage_per_hit = _calc_building_damage(attacks, castle["armor"])
                reload_time = 1.0 / cu["attack_speed"] if cu["attack_speed"] > 0 else 2.0
                unit_dps = damage_per_hit / reload_time

                # Fire Archer (Wu): Red Cliffs Tactics adds 5 fire damage over 5s
                # to buildings, ignoring armor, stacking per unit (= 1.0 DPS/unit)
                if "fire_archer_wu" in u["unit_slug"]:
                    unit_dps += 1.0

                # Does the unit outrange the castle?
                outranges = cu["attack_range"] > castle["arrow_range"]

                if outranges:
                    # No attrition — pure DPS
                    total_dps = n_units * unit_dps
                    ttk = castle["hp"] / total_dps if total_dps > 0 else 600.0
                else:
                    # Attrition: castle fires at units
                    dmg_per_arrow = max(1, castle["arrow_attack"] - cu["pierce_armor"])
                    castle_dps = castle["arrows"] * dmg_per_arrow / castle["reload"]

                    ttk = _simulate_siege_vs_castle(
                        n_units, cu["hp"], unit_dps, castle["hp"], castle_dps,
                        cu["movement_speed"], cu["attack_range"], castle["arrow_range"],
                    )

                sk = f"{u['civ_name']}|{u['unit_slug']}"
                all_scores.setdefault((line_slug, age), {})[sk] = {
                    "time_to_kill": round(min(ttk, 600.0), 1),
                }

    # Normalize per (line_slug, age): faster = higher score (0-100, inverted)
    for (line_slug, age), scores in all_scores.items():
        ttk_vals = [s["time_to_kill"] for s in scores.values()]
        lo, hi = min(ttk_vals), max(ttk_vals)
        span = hi - lo if hi != lo else 1
        for s in scores.values():
            s["anti_building_score"] = round((hi - s["time_to_kill"]) / span * 100, 1)

    # Format for write_role_scores_to_db
    result = {}
    for (line_slug, age), scores in all_scores.items():
        result[f"{line_slug}|{age}"] = scores
    return result
```

Key changes from original:
- `all_scores` keyed by `(line_slug, age)` tuple instead of just `age`
- Normalization iterates over `(line_slug, age)` pairs — each line normalized independently
- Return keys are `"{line_slug}|{age}"` (e.g., `"ram|imperial"`) instead of `"siege|{age}"`

**Step 2: Update both `write_role_scores_to_db` call sites**

There are 2 call sites. Change `["siege"]` to `SIEGE_LINE_SLUGS` in both:

At line ~1996 (incremental path):
```python
write_role_scores_to_db(siege_scores, SIEGE_LINE_SLUGS, SIEGE_SCORE_TYPES)
```

At line ~2185 (full recompute path):
```python
write_role_scores_to_db(siege_scores, SIEGE_LINE_SLUGS, SIEGE_SCORE_TYPES)
```

**Step 3: Verify change compiles**

Run: `cd /Users/deepak/AI/aoe2unitanalyzer && python3 -c "from webapp.compute_battle_scores import compute_siege_antibuilding_scores; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add webapp/compute_battle_scores.py
git commit -m "feat(siege): store per-line scores instead of aggregated siege"
```

---

### Task 2: Update ROLE_DEFS in best_units.py

**Files:**
- Modify: `webapp/best_units.py:53`

**Step 1: Change siege line_slugs from `["siege"]` to individual lines**

```python
# Before:
("siege", ["siege"], "anti_building_score"),
# After:
("siege", ["ram", "trebuchet", "bombard_cannon"], "anti_building_score"),
```

**Step 2: Commit**

```bash
git add webapp/best_units.py
git commit -m "feat(siege): query per-line slugs in ROLE_DEFS"
```

---

### Task 3: Recompute and verify

**Step 1: Run the compute pipeline**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer && source venv/bin/activate && cd webapp && python3 compute_battle_scores.py --roles-only
```

Expected: Siege lines print separately in output. No errors.

**Step 2: Regenerate civ power units**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 best_units.py
```

Expected: Writes `civ_power_units.json` with siege units having per-line ranks.

**Step 3: Verify per-line ranking in the JSON**

```bash
python3 -c "
import json
data = json.load(open('civ_power_units.json'))
# Check a civ known to have good BBC but average rams (e.g., Turks)
turks = data.get('Turks', {}).get('imperial', {}).get('power_units', {}).get('siege', {})
for u in turks.get('all_units', []):
    print(f\"{u['unit_name']:30s} line={u['line_slug']:20s} rank=#{u['rank']} score={u['score']} delta={u['median_delta']}\")
"
```

Expected: Each unit shows its actual line_slug (ram/trebuchet/bombard_cannon) and ranks are per-line (a BBC could be #1 while ram is #30+).

**Step 4: Start webapp and visually verify**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp && python3 app.py --port 5001
```

Open `http://localhost:5001/civilizations`, click a civ, verify siege column shows units with per-line ranks.

---
