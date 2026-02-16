# Anti-Building Unit Rankings: Traction Trebuchet, Siege Elephant Fix, Fire Archer

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Traction Trebuchet (Shu/Wu/Wei) and Fire Archer (Wu, anti-building mode) to the bombard cannon line, and fix the Siege Elephant's missing blacksmith/stable upgrades in the ram line.

**Architecture:** Three changes: (A) Fix `unit_analyzer.py` to use alternate unit_class (12 for Siege Elephant) so class-targeted techs (Forging, Barding, Bloodlines, Husbandry) are applied correctly. (B) Add Traction Trebuchet (unit 1942) to the extraction pipeline as a Shu/Wu/Wei-only Imperial unit. (C) Add Fire Archer as Wu unique unit in the bombard_cannon line, with castle armor class 21 added to the anti-building damage calculation.

**Tech Stack:** Python 3, SQLite, genieutils

---

### Task 1: Fix Siege Elephant unit_class in alternate config

The Armored/Siege Elephant is unit class 12 (not 13 like rams). Blacksmith barding (81/82/80), Forging (67), Iron Casting (68), Blast Furnace (75), Bloodlines (435), and Husbandry (39) all target class 12. The current pipeline always uses the parent config's `unit_class: 13`, missing all these techs.

**Files:**
- Modify: `analysis/config.py:942-949`
- Modify: `analysis/unit_analyzer.py:840`
- Modify: `analysis/generate_reference.py:1267-1277`

**Step 1: Add unit_class to alternate config**

In `analysis/config.py`, change the siege_ram alternate block (lines 942-949) to include `"unit_class": 12`:

```python
        "alternate": {
            "availability_tech": 837,
            "base_id": 1744,  # Armored Elephant
            "display_name": "Siege Elephant",
            "unit_class": 12,  # Cavalry/elephant class — gets blacksmith barding, Bloodlines, Husbandry
            "upgrades": [
                (838, 1746, "Siege Elephant"),  # Correct ID for Siege Elephant
            ],
        },
```

**Step 2: Use alternate unit_class in unit_analyzer.py**

In `analysis/unit_analyzer.py`, change line 840 from:
```python
        unit_class = unit_config["unit_class"]
```
to:
```python
        # Use alternate unit_class if available (e.g., Siege Elephant is class 12, not 13 like rams)
        if use_alternate and "unit_class" in alternate:
            unit_class = alternate["unit_class"]
        else:
            unit_class = unit_config["unit_class"]
```

Also add `unit_class` to the return dict. In the return statement around line 965-971, change:
```python
        return {
            "unit_name": final_unit_name,
            "unit_id": final_unit_id,
            "stats": stats,
            "has_unit": True,
            "applied_bonuses": applied_bonuses,
        }
```
to:
```python
        return {
            "unit_name": final_unit_name,
            "unit_id": final_unit_id,
            "unit_class": unit_class,
            "stats": stats,
            "has_unit": True,
            "applied_bonuses": applied_bonuses,
        }
```

**Step 3: Use returned unit_class in generate_reference.py**

In `analysis/generate_reference.py`, change the Imperial units block (lines 1267-1277) from:
```python
            process_unit_audited(
                civ_name,
                final_unit_id,
                config["unit_class"],
                result["unit_name"],
                ...
```
to:
```python
            process_unit_audited(
                civ_name,
                final_unit_id,
                result.get("unit_class", config["unit_class"]),
                result["unit_name"],
                ...
```

Do the same for the Castle Age units block (around line 1242-1252) — change `config["unit_class"]` to `result.get("unit_class", config["unit_class"])`.

**Step 4: Verify the fix**

Run: `python3 -m extraction.run && python3 -m analysis.generate_main_db`

Then verify Siege Elephant stats changed:
```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('webapp/aoe2_reference.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('''SELECT civ_name, unit_name, final_hp, final_attack, final_melee_armor,
    final_pierce_armor, final_speed, final_reload_time, applied_bonuses_summary
    FROM ref_units WHERE unit_name LIKE '%Siege Elephant%' ORDER BY civ_name''').fetchall()
for r in rows:
    print(f'{r[\"civ_name\"]:15s} HP={r[\"final_hp\"]} ATK={r[\"final_attack\"]} MA={r[\"final_melee_armor\"]} PA={r[\"final_pierce_armor\"]} SPD={r[\"final_speed\"]} Reload={r[\"final_reload_time\"]}')
    print(f'  Bonuses: {r[\"applied_bonuses_summary\"]}')
"
```

Expected: Bengalis Siege Elephant should show ~240 HP (220+20 Bloodlines), ~8 attack (4+4 blacksmith), ~1 MA (-2+3 barding), ~154 PA (150+4 barding), ~0.66 speed (0.6*1.1 Husbandry). Other civs should differ based on which techs they have.

**Step 5: Commit**

```bash
git add analysis/config.py analysis/unit_analyzer.py analysis/generate_reference.py
git commit -m "fix: Siege Elephant now gets blacksmith/stable upgrades (class 12 alternate)"
```

---

### Task 2: Add Traction Trebuchet to extraction pipeline

Unit 1942 (TRTREB) needs to be added to the extraction pipeline. Shadow tech 1025 auto-enables it at Imperial Age. Restrict to Shu/Wu/Wei via `civ_only`.

Stats from dat: HP=115, Speed=0.57, Range=14 (min 4), Reload=11.0, Accuracy=30%, Blast level=1. Attacks: Class 11 (Buildings)=230, Class 4 (Melee)=50. Cost: 175 Wood, 210 Gold. Trained at Siege Workshop (unit 49).

**Files:**
- Modify: `extraction/extract_units.py:323-328`
- Modify: `analysis/config.py:142-145` (ALLOWED_SHADOW_TECHS)
- Modify: `analysis/config.py:246-266` (COMBAT_PROPERTIES)
- Modify: `analysis/config.py:1003-1009` (IMPERIAL_UNITS, add after trebuchet)

**Step 1: Add unit 1942 to UNIT_NAMES**

In `extraction/extract_units.py`, add after line 327 (`1946: "Heavy Hei-Kuang Cavalry",`):
```python
    # ===== Traction Trebuchet (Castle Age trebuchet variant) =====
    1942: "Traction Trebuchet",
```

**Step 2: Add tech 1025 to ALLOWED_SHADOW_TECHS**

In `analysis/config.py`, change ALLOWED_SHADOW_TECHS (line 142):
```python
ALLOWED_SHADOW_TECHS = {
    774,  # Flemish Militia Age3: +10 HP, +3 attack, +anti-cav bonuses
    797,  # Flemish Militia Age4: +5 HP, +3 attack, +anti-cav bonuses
    1025,  # Traction Trebuchet (make avail): enables unit 1942 at Imperial Age
}
```

**Step 3: Add COMBAT_PROPERTIES entry**

In `analysis/config.py`, add after the `"bombard_cannon"` entry (line 266):
```python
    "traction_trebuchet": {"unit_category": "siege"},
```

**Step 4: Add IMPERIAL_UNITS config entry**

In `analysis/config.py`, add after the `"trebuchet"` entry (after line 1009):
```python
    "traction_trebuchet": {
        "base_id": 1942,
        "display_name": "Traction Trebuchet",
        "unit_class": 13,
        "availability_tech": 1025,  # Shadow tech, auto-researches at Imperial Age
        "upgrades": [],
        "civ_only": ["Shu", "Wu", "Wei"],
    },
```

**Step 5: Extract and verify**

Run: `python3 -m extraction.run`

Verify unit 1942 appears in extracted data:
```bash
python3 -c "
import json
with open('extraction/extracted_data/units.json') as f:
    units = json.load(f)
for u in units:
    if u.get('id') == 1942:
        print(f'ID={u[\"id\"]}, name={u[\"name\"]}, class={u[\"class\"]}')
        c = u.get('creatable', {})
        print(f'Attacks: {c.get(\"attacks\")}')
        break
"
```

Then run: `python3 -m analysis.generate_main_db`

Verify in reference DB:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('''SELECT civ_name, unit_name, final_hp, final_attack, final_range, final_reload_time, final_attacks_json, applied_bonuses_summary
    FROM ref_units WHERE unit_slug='traction_trebuchet' ORDER BY civ_name''').fetchall()
for r in rows:
    print(f'{r[\"civ_name\"]:10s} {r[\"unit_name\"]:25s} HP={r[\"final_hp\"]} ATK={r[\"final_attack\"]} RNG={r[\"final_range\"]} Reload={r[\"final_reload_time\"]}')
    print(f'  Bonuses: {r[\"applied_bonuses_summary\"]}')
print(f'Total: {len(rows)} entries (expected: 3 civs x 1 age = 3)')
"
```

Expected: Shu, Wu, Wei each have a Traction Trebuchet entry with ~115 HP, ~230 building attack (class 11), range 14.

**Step 6: Commit**

```bash
git add extraction/extract_units.py analysis/config.py
git commit -m "feat: add Traction Trebuchet (unit 1942) for Shu/Wu/Wei"
```

---

### Task 3: Update UNIT_LINES for bombard_cannon and anti-building scoring

Add Traction Trebuchet and Fire Archer to the bombard_cannon line in BOTH app.py and compute_battle_scores.py. Add castle armor class 21 to anti-building damage calculation.

**Files:**
- Modify: `webapp/app.py:1453-1459` (bombard_cannon UNIT_LINES)
- Modify: `webapp/compute_battle_scores.py:291-297` (bombard_cannon UNIT_LINES)
- Modify: `webapp/compute_battle_scores.py:1344-1355` (SIEGE_CASTLE_TARGET — add class 21)

**Step 1: Update UNIT_LINES in app.py**

Change the bombard_cannon entry in `webapp/app.py` (lines 1453-1459) to:
```python
    "bombard_cannon": {
        "name": "Bombard Cannon",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "bombard_cannon",
        "extra_imperial_slugs": ["traction_trebuchet"],
        "unique_units": {
            "Wu": (None, "elite_fire_archer_wu"),
        },
    },
```

Note: Fire Archer castle_slug is None (only Imperial/elite version in anti-building line).

**Step 2: Update UNIT_LINES in compute_battle_scores.py**

Change the bombard_cannon entry in `webapp/compute_battle_scores.py` (lines 291-297) to match:
```python
    "bombard_cannon": {
        "name": "Bombard Cannon",
        "building": "Siege Workshop",
        "castle_slug": None,
        "imperial_slug": "bombard_cannon",
        "extra_imperial_slugs": ["traction_trebuchet"],
        "unique_units": {
            "Wu": (None, "elite_fire_archer_wu"),
        },
    },
```

**Step 3: Add armor class 21 to SIEGE_CASTLE_TARGET**

In `webapp/compute_battle_scores.py`, update SIEGE_CASTLE_TARGET (lines 1344-1355) to include class 21:
```python
SIEGE_CASTLE_TARGET = {
    "hp": 7028,           # 4800 * 1.1 * 1.1 * 1.21
    "armor": {
        3: 13,            # pierce: 11 + 1 + 1
        4: 10,            # melee: 8 + 1 + 1
        11: 6,            # standard building: 0 + 3 + 3
        21: 0,            # standard buildings class (no bonus armor)
    },
    "arrows": 5,          # base arrows (no garrison)
    "arrow_attack": 15,   # 11 + 1 + 1 + 1 + 1 (Fletching/Bodkin/Bracer/Chemistry)
    "arrow_range": 11,    # 8 + 1 + 1 + 1
    "reload": 2.0,
}
```

**Step 4: Verify changes parse correctly**

```bash
cd webapp && python3 -c "
from compute_battle_scores import UNIT_LINES, SIEGE_CASTLE_TARGET
bc = UNIT_LINES['bombard_cannon']
print('Bombard Cannon line:')
print(f'  imperial_slug: {bc[\"imperial_slug\"]}')
print(f'  extra_imperial_slugs: {bc.get(\"extra_imperial_slugs\", [])}')
print(f'  unique_units: {bc.get(\"unique_units\", {})}')
print(f'Castle armor classes: {SIEGE_CASTLE_TARGET[\"armor\"]}')
"
```

**Step 5: Commit**

```bash
git add webapp/app.py webapp/compute_battle_scores.py
git commit -m "feat: add Traction Trebuchet and Fire Archer to bombard cannon line"
```

---

### Task 4: Rebuild databases and compute battle scores

Run the full pipeline to regenerate all data with the fixes.

**Step 1: Re-extract and generate reference DB**

```bash
python3 -m extraction.run
```

**Step 2: Generate main DB**

```bash
python3 -m analysis.generate_main_db
```

**Step 3: Compute battle scores**

```bash
cd webapp && python3 compute_battle_scores.py
```

**Step 4: Verify anti-building rankings include new units**

```bash
cd webapp && python3 -c "
import sqlite3
conn = sqlite3.connect('aoe2_reference.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('''SELECT civ_name, unit_slug, score_type, score_value
    FROM battle_scores WHERE line_slug='siege' AND score_type='anti_building_score'
    AND (unit_slug LIKE '%fire_archer%' OR unit_slug LIKE '%traction%' OR unit_slug LIKE '%siege_elephant%' OR unit_slug LIKE '%siege_ram%')
    ORDER BY score_value DESC''').fetchall()
for r in rows:
    print(f'{r[\"civ_name\"]:15s} {r[\"unit_slug\"]:30s} score={r[\"score_value\"]}')
print(f'Total: {len(rows)} entries')
"
```

Expected: Should see Traction Trebuchet entries for Shu/Wu/Wei, Fire Archer for Wu, and Siege Elephant entries for Bengalis/Dravidians/Gurjaras/Hindustanis with improved scores.

**Step 5: Commit generated files**

```bash
git add webapp/aoe2_units.db webapp/battle_scores.json webapp/battle_cache.json
git commit -m "chore: rebuild databases with anti-building unit changes"
```
