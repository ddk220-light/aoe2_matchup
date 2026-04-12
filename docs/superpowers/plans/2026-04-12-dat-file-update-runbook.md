# Dat File Update Runbook

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repeatable process to integrate a new `empires2_x2_p1.dat` file containing stat changes and/or new civilizations into the full pipeline — extraction, analysis, simulation, webapp, and tests.

**Architecture:** The pipeline flows in one direction: `.dat` binary &rarr; 8 JSON files &rarr; `aoe2_reference.db` &rarr; `aoe2_units.db` &rarr; `battle_scores` &rarr; `civ_power_units.json`. Config files act as side-inputs at the analysis stage, providing unit definitions, combat properties, and civ lists that the extraction layer can't express. The webapp reads from the databases at runtime; the frontend reads from `constants.js` for civ lists and icon mappings.

**Tech Stack:** Python 3 (genieutils, sqlite3, Flask), JavaScript (vanilla), pytest

**CRITICAL:** NEVER change scoring formulas or weights without explicit user approval.

---

## Pre-flight: What You Need Before Starting

Before touching any code, gather this information about the new dat file:

1. **New civ names** (exact spelling, e.g., "Helvetii") and their **dat file index** (the position in the `df.civs` array — run extraction once to discover this, see Task 1)
2. **New unique unit IDs and names** — look up on the AoE2 wiki, patch notes, or run extraction to discover new unit IDs in the dat
3. **New unique unit properties** — which unit line each unique replaces (militia, knight, archer, etc.), unit class (infantry=6, cavalry=12, archer=0, cav_archer=36, siege=13), base/elite IDs, availability and elite tech IDs
4. **Special combat abilities** — does any new unit have abilities not extractable from the dat? (Examples: ignores armor, bleed damage, block first hit, per-kill bonuses, HP transformation, dismount, armor stripping, pass-through). These go in hardcoded config.
5. **Civ-specific combat bonuses** — does any new civ have unique techs that modify generic units? (Examples: Druzhina gives Slavs infantry trample, Wootz Steel gives Dravidians melee ignores-armor). These go in `CIV_COMBAT_PROPERTIES`.
6. **Tech tree gaps** — do any new civs lack trebuchets? (Goes in `CIVS_WITHOUT_TREBUCHET`). Any unique units trainable from barracks? (Goes in `UNIQUE_UNITS_IN_BARRACKS`).
7. **Icon availability** — find the `picture_index` for new units (not the game ID). For units with game ID > 1665, the primary CDN (qwyt GitHub) won't have icons; the fallback CDN (aoe2techtree.net) uses `picture_index`.

---

## Task 1: Discovery — Extract JSON and Identify Changes

**Purpose:** Run extraction to produce JSON files, then diff against previous JSON to discover new civ indices, new unit IDs, and stat changes. This task is read-only reconnaissance.

**Files:**
- Read: `extraction/empires2_x2_p1.dat` (the new file you just copied)
- Read: `extraction/extracted_data/*.json` (previous extraction output)

- [ ] **Step 1: Back up previous extraction output**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
cp -r extraction/extracted_data extraction/extracted_data_previous
```

- [ ] **Step 2: Run extraction**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m extraction.run
```

Expected output: "Extracting data from dat file..." followed by counts for units, technologies, civilizations, etc., ending with "Done! JSON files written to extraction/extracted_data/"

If the civ count increased (e.g., "53 civilizations" &rarr; "56 civilizations"), new civs are present but their names will show as `null` because `CIV_NAMES` in `extract_constants.py` hasn't been updated yet. That's expected — we fix it in Task 2.

- [ ] **Step 3: Diff civilizations.json to find new civ indices**

```bash
diff extraction/extracted_data_previous/civilizations.json extraction/extracted_data/civilizations.json
```

New entries will appear with `"name": null` if `CIV_NAMES` doesn't include them yet. Note the `"id"` values — these are the dat file indices you need for Task 2.

If no new civs, skip to Step 5.

- [ ] **Step 4: Identify new civ names**

Open the dat file with the AoE2 Genie Editor or check patch notes to get the exact civ names for each new index. The `internal_name` in the dat may be garbled for newer civs — don't trust it.

- [ ] **Step 5: Diff units.json to find stat changes and new units**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -c "
import json
with open('extraction/extracted_data_previous/units.json') as f:
    old = {u['id']: u for u in json.load(f)}
with open('extraction/extracted_data/units.json') as f:
    new = {u['id']: u for u in json.load(f)}

# New unit IDs
new_ids = set(new.keys()) - set(old.keys())
if new_ids:
    print('=== NEW UNITS ===')
    for uid in sorted(new_ids):
        u = new[uid]
        print(f'  ID {uid}: {u[\"name\"]} (class={u[\"class\"]}, internal={u[\"internal_name\"]})')

# Stat changes on existing units
print('\n=== STAT CHANGES ===')
for uid in sorted(set(old.keys()) & set(new.keys())):
    diffs = []
    for key in ['hit_points', 'speed', 'cost', 'attacks', 'armors', 'reload_time', 'range', 'accuracy']:
        if old[uid].get(key) != new[uid].get(key):
            diffs.append(f'{key}: {old[uid].get(key)} -> {new[uid].get(key)}')
    if diffs:
        print(f'  ID {uid} ({new[uid][\"name\"]}): {\", \".join(diffs)}')
"
```

- [ ] **Step 6: Record findings**

Write down:
- New civ names + dat indices (e.g., "Helvetii" at index 57)
- New unit IDs + display names + unit classes
- Which unit line each new unique replaces
- Any stat changes on existing units (these flow through automatically — no config changes needed)
- Any special abilities per pre-flight research

- [ ] **Step 7: Clean up backup**

```bash
rm -rf /Users/deepak/AI/aoe2unitanalyzer/extraction/extracted_data_previous
```

---

## Task 2: Update Extraction Constants — `CIV_NAMES` and `UNIT_NAMES`

**Purpose:** Register new civs and units so the extraction layer includes them in JSON output.

**Files:**
- Modify: `extraction/extract_constants.py` — `CIV_NAMES` list
- Modify: `extraction/extract_units.py` — `UNIT_NAMES` dict

- [ ] **Step 1: Add new civ names to `CIV_NAMES`**

Open `extraction/extract_constants.py`. The `CIV_NAMES` list is index-ordered — position must match the dat file civ ID. Add new civs at their correct indices.

Example — if adding 3 new civs at indices 57, 58, 59:

```python
# Before (end of CIV_NAMES):
    None,  # 54 Macedonians - skip
    None,  # 55 Thracians - skip
    None,  # 56 Puru - skip
]

# After:
    None,  # 54 Macedonians - skip
    None,  # 55 Thracians - skip
    None,  # 56 Puru - skip
    # New DLC (in ranked play)
    "NewCiv1",  # 57
    "NewCiv2",  # 58
    "NewCiv3",  # 59
]
```

If new civs are NOT in ranked play (like Chronicles DLC), use `None` instead and stop here for those civs — the pipeline will skip them entirely.

- [ ] **Step 2: Add new unit IDs to `UNIT_NAMES`**

Open `extraction/extract_units.py`. Add entries to `UNIT_NAMES` dict for every new unit ID discovered in Task 1.

**Gotcha:** Unit names in `units.json` are often **scrambled** for newer units. Use the display name from the wiki/patch notes, NOT the extracted `name` field. The `internal_name` is more reliable but still not always correct.

Example:

```python
    # ===== Unique Units - NewCiv1 =====
    2200: "New Unit Name",
    2202: "Elite New Unit Name",
```

Include ALL variant IDs (some units have alternate dat entries — Genoa Crossbow has IDs 866, 868, 1004, 1006). Check if new units have multiple dat entries by searching the extracted `units.json` for similar `internal_name` values.

- [ ] **Step 3: Re-run extraction with updated constants**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m extraction.run
```

Verify output: civ count should now include new civs by name (not null), and unit count should include new units.

- [ ] **Step 4: Spot-check new units in JSON**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -c "
import json
with open('extraction/extracted_data/units.json') as f:
    units = {u['id']: u for u in json.load(f)}
# Replace 2200 with your actual new unit IDs:
for uid in [2200, 2202]:
    if uid in units:
        u = units[uid]
        print(f'ID {uid}: {u[\"name\"]}, HP={u[\"hit_points\"]}, ATK={u.get(\"attacks\")}, cost={u.get(\"cost\")}')
    else:
        print(f'ID {uid}: NOT FOUND — check UNIT_NAMES dict')
"
```

- [ ] **Step 5: Commit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add extraction/extract_constants.py extraction/extract_units.py
git commit -m "data: add new civ names and unit IDs for [DLC name] dat update"
```

---

## Task 3: Update Analysis Config — Unit Definitions

**Purpose:** Tell the analysis layer how to build database entries for new unique units, including which techs apply, which upgrade chains exist, and any civ-specific unit overrides.

**Files:**
- Modify: `analysis/config_units.py` — `UNIQUE_UNITS` dict, possibly `UNIT_STAT_OVERRIDES`, `UNIQUE_UNITS_IN_BARRACKS`, `PAIRED_UNITS`
- Modify: `analysis/config_units.py` — `IMPERIAL_UNITS` (only if new civs have `civ_upgrades` on generic lines, like Savar replacing Paladin for Persians)

### Key context for the implementer

The `UNIQUE_UNITS` dict maps civ name &rarr; list of unique unit configs. Each config needs:

| Field | Source | Example |
|-------|--------|---------|
| `base_id` | dat file unit ID (non-elite version) | `1908` |
| `display_name` | Wiki / patch notes | `"Iron Pagoda"` |
| `unit_class` | dat file `class` field (infantry=6, cavalry=12, archer=0, cav_archer=36, siege=13) | `12` |
| `availability_tech` | The tech ID that enables training this unit (find in `technologies.json` — look for techs with `research_location` = Castle ID and name matching the unit) | `990` |
| `elite_tech` | Tech ID for the elite upgrade (find in `technologies.json` — look for tech name containing "Elite" + unit name). Set to `None` if no elite exists. | `991` |
| `elite_id` | dat file unit ID for the elite version. Set to `None` if no elite exists. | `1910` |
| `elite_name` | Display name for elite. Set to `None` if no elite exists. | `"Elite Iron Pagoda"` |

Optional fields (add only when needed):
- `extra_unit_classes`: list of additional class IDs for tech filtering (e.g., Ballista Elephant gets cavalry class 12 techs in addition to siege)
- `excluded_tech_ids`: list of tech IDs to exclude from applying (e.g., Warrior Priest excludes monk-specific techs)

- [ ] **Step 1: Find availability and elite tech IDs for each new unique unit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -c "
import json
with open('extraction/extracted_data/technologies.json') as f:
    techs = json.load(f)
# Search for techs related to new units — adjust search terms:
for t in techs:
    name = t.get('name', '').lower()
    # Replace with your new unit names:
    if any(term in name for term in ['newunit', 'elite newunit']):
        print(f'Tech {t[\"id\"]}: {t[\"name\"]} (research_location={t.get(\"research_location\")})')
"
```

Castle-trained units have `research_location` = 82 (Castle building ID). If the tech has `research_location` = -1, it may be a shadow tech — check `ALLOWED_SHADOW_TECHS` in `config_constants.py`.

- [ ] **Step 2: Add entries to `UNIQUE_UNITS` dict**

Open `analysis/config_units.py`, find the `UNIQUE_UNITS` dict (starts around line 677). Add a new entry for each new civ, inserted alphabetically by civ name.

Example for a civ with 2 unique units (one without elite):

```python
    "NewCiv1": [
        {
            "base_id": 2200,
            "display_name": "New Unit",
            "unit_class": 12,
            "availability_tech": 1100,
            "elite_tech": 1101,
            "elite_id": 2202,
            "elite_name": "Elite New Unit",
        },
        {
            "base_id": 2210,
            "display_name": "Second Unit",
            "unit_class": 6,
            "availability_tech": 1102,
            "elite_tech": None,    # No elite upgrade
            "elite_id": None,
            "elite_name": None,
        },
    ],
```

**Gotcha for units without elite:** When `elite_id=None`, the pipeline creates entries for BOTH Castle and Imperial ages using the same base unit (applying age-appropriate techs to each). This is correct for units like Warrior Priest, Grenadier, and Xianbei Raider.

- [ ] **Step 3: Check if any new civs need `civ_upgrades` on generic unit lines**

Some civs replace generic Imperial upgrades with unique variants. Examples from existing code:
- **Persians**: Savar replaces Paladin → `civ_upgrades` on the `paladin` entry in `IMPERIAL_UNITS`
- **Romans**: Legionary replaces Champion → `civ_upgrades` on the `champion` entry in `IMPERIAL_UNITS`
- **Hindustanis**: Imperial Camel Rider → `civ_upgrades` on the `heavy_camel` entry

If any new civ has this pattern, add a `civ_upgrades` entry to the appropriate `IMPERIAL_UNITS` (or `CASTLE_UNITS`) dict entry. The format is:

```python
"civ_upgrades": {
    "NewCiv": [(upgrade_tech_id, upgraded_unit_id, "Upgraded Name")],
},
```

- [ ] **Step 4: Check for special config entries**

- If any new unique unit is trainable from Barracks (not Castle), add to `UNIQUE_UNITS_IN_BARRACKS`
- If any new unit has paired modes (like Ratha melee/ranged), add to `PAIRED_UNITS`
- If any new unit has incorrect dat file stats, add to `UNIT_STAT_OVERRIDES` (keyed by unit ID)

- [ ] **Step 5: Commit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add analysis/config_units.py
git commit -m "config: add unit definitions for [new civ names]"
```

---

## Task 4: Update Analysis Config — Combat Properties

**Purpose:** Register any special combat abilities and civ-specific bonuses that aren't extractable from the dat file.

**Files:**
- Modify: `analysis/config_combat.py` — `COMBAT_PROPERTIES`, `UNIQUE_COMBAT_PROPERTIES`, `CIV_COMBAT_PROPERTIES`

### Key context for the implementer

Three dicts, applied in priority order (later overrides earlier):

1. **`COMBAT_PROPERTIES`** — keyed by unit slug (e.g., `"mangonel"`). Used for `unit_category` classification and generic unit combat flags. Only add entries here if a new generic unit type is introduced or a new unique unit needs a category override (e.g., `"grenadier": {"unit_category": "siege"}`).

2. **`UNIQUE_COMBAT_PROPERTIES`** — keyed by base slug WITHOUT civ suffix (e.g., `"leitis"` not `"leitis_lithuanians"`). Add entries here for ability flags that **cannot be extracted from the dat file**: `ignores_melee_armor`, `ignores_pierce_armor`, `bleed_dps/duration`, `block_first_melee`, `attack_bonus_per_kill`, `hp_per_kill`, `hp_transform_threshold`, `dismount_*`, `armor_strip_per_hit`, `charge_attack_melee/charge_recharge_time`, `pass_through_count/percent`, `miss_damage_percent`, `pop_space`, `extra_proj_scatter`.

   Properties that ARE data-driven from dat (do NOT hardcode): `extra_projectiles`, `trample_percent/radius`, `dodge_shield_max/recharge`, `splash_radius`, `projectile_speed`, `min_attack_range`, `hp_regen`, `splash_on_hit_radius`.

3. **`CIV_COMBAT_PROPERTIES`** — keyed by tuple `("CivName", "unit_slug")`. Add entries here for civ-unique-tech effects that modify generic or unique units. The slug must match the exact DB slug (e.g., `"champion"`, `"halberdier"`, `"swordsmen"` for the Long Swordsman, `"elite_skirm"`).

- [ ] **Step 1: Add `COMBAT_PROPERTIES` entries (if needed)**

If any new unique unit needs a `unit_category` override (most commonly `"siege"` or `"infantry"` for ranged infantry like Chakram Thrower), add it:

```python
    "new_unit": {"unit_category": "siege"},
```

- [ ] **Step 2: Add `UNIQUE_COMBAT_PROPERTIES` entries**

For each new unique unit with special abilities not in the dat file:

```python
    # Example: new unit ignores pierce armor
    "new_unit": {"ignores_pierce_armor": 1},
    "elite_new_unit": {"ignores_pierce_armor": 1},
```

**Important:** Always add entries for BOTH base and elite versions. The slug here is the base name without civ suffix.

- [ ] **Step 3: Add `CIV_COMBAT_PROPERTIES` entries**

For each new civ's unique techs that modify combat properties on generic or unique units:

```python
    # Example: NewCiv Imperial UT gives infantry +trample
    ("NewCiv1", "champion"): {"trample_flat_damage": 5, "trample_radius": 0.5},
    ("NewCiv1", "halberdier"): {"trample_flat_damage": 5, "trample_radius": 0.5},
    ("NewCiv1", "swordsmen"): {"trample_flat_damage": 5, "trample_radius": 0.5},
```

**Gotcha:** You need one entry per (civ, slug) pair. If a civ bonus applies to 10 different units, that's 10 entries. Check existing examples (Sicilians has ~20 entries for 40% bonus damage reduction).

- [ ] **Step 4: Commit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add analysis/config_combat.py
git commit -m "config: add combat properties for [new civ/unit names]"
```

---

## Task 5: Update Civ Lists — `ORIGINAL_13_CIVS` and `ENABLED_CIVS`

**Purpose:** Register new civs in all hardcoded civ lists so they appear in dropdowns and are included in team analysis.

**Files:**
- Modify: `analysis/config_constants.py` — `ORIGINAL_13_CIVS` list (line ~81)
- Modify: `webapp/app.py` — `ORIGINAL_13_CIVS` list (line ~125)
- Modify: `webapp/static/js/constants.js` — `ENABLED_CIVS` array (line ~11)

All three lists must contain the same civs, sorted alphabetically.

- [ ] **Step 1: Add to `analysis/config_constants.py`**

Open `analysis/config_constants.py`, find `ORIGINAL_13_CIVS` (line ~81). Insert new civ names in alphabetical order.

```python
ORIGINAL_13_CIVS = [
    "Armenians",
    "Aztecs",
    ...
    "NewCiv1",  # <-- insert alphabetically
    "NewCiv2",
    "NewCiv3",
    ...
    "Wu",
]
```

- [ ] **Step 2: Add to `webapp/app.py`**

Open `webapp/app.py`, find `ORIGINAL_13_CIVS` (line ~125). Insert same civ names in same alphabetical order. This list must be a **byte-identical copy** of the one in `config_constants.py`.

- [ ] **Step 3: Add to `webapp/static/js/constants.js`**

Open `webapp/static/js/constants.js`, find `ENABLED_CIVS` (line ~11). Insert new civ names as quoted strings in alphabetical order.

```javascript
const ENABLED_CIVS = [
    "Armenians",
    "Aztecs",
    ...
    "NewCiv1",
    "NewCiv2",
    "NewCiv3",
    ...
    "Wu",
];
```

- [ ] **Step 4: Commit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add analysis/config_constants.py webapp/app.py webapp/static/js/constants.js
git commit -m "config: add [new civ names] to all civ lists"
```

---

## Task 6: Update Unit Lines and Frontend Icons

**Purpose:** Map new unique units into the unit line system (which determines how they appear in rankings and matchup advisor) and add icon mappings for the frontend.

**Files:**
- Modify: `webapp/unit_lines.py` — `UNIT_LINES` dict
- Modify: `webapp/static/js/constants.js` — `NAME_TO_ICON` dict, possibly `UNIQUE_BUILDING` dict
- Modify: `webapp/best_units.py` — `CIVS_WITHOUT_TREBUCHET` set (if applicable)

- [ ] **Step 1: Add unique units to `UNIT_LINES`**

Open `webapp/unit_lines.py`. For each new civ's unique unit, add it to the `unique_units` sub-dict of the unit line it replaces.

The slug format is: `{snake_case_unit_name}_{lowercase_civ_name}` for Castle age, `elite_{snake_case_unit_name}_{lowercase_civ_name}` for Imperial age.

Example — a new cavalry unique unit for "NewCiv1" that replaces the knight line:

```python
    "knight": {
        ...
        "unique_units": {
            ...
            "NewCiv1": ("new_unit_newciv1", "elite_new_unit_newciv1"),
            ...
        },
    },
```

**For units without elite** (like Warrior Priest, Jian Swordsman), use the same slug for both Castle and Imperial:

```python
            "NewCiv2": ("second_unit_newciv2", "second_unit_newciv2"),
```

**Determine which line** by looking at what the unique unit replaces in the tech tree:
- Replaces Champion? &rarr; `"militia"` line
- Replaces Paladin? &rarr; `"knight"` line
- Replaces Arbalester? &rarr; `"archer"` line
- Replaces Heavy Cav Archer? &rarr; `"cav_archer"` line
- Replaces Elite Skirmisher? &rarr; `"skirmisher"` line
- Replaces Heavy Scorpion? &rarr; `"scorpion"` line
- Replaces Hussar? &rarr; `"light_cav"` line
- Is a gunpowder/ranged unique? &rarr; `"gunpowder"` line
- Is a Fire Lancer/Eagle replacement? &rarr; `"shock_infantry"` line

- [ ] **Step 2: Add icon mappings to `NAME_TO_ICON`**

Open `webapp/static/js/constants.js`. Add entries to `NAME_TO_ICON` for each new unit's display name. The value is the wiki icon filename (spaces replaced with underscores).

```javascript
    // New DLC
    "New Unit": "New_Unit",
    "Elite New Unit": "Elite_New_Unit",
    "Second Unit": "Second_Unit",
```

**Icon ID gotcha:** For units with game ID > 1665, the primary CDN (qwyt GitHub) won't have the icon. The fallback CDN (aoe2techtree.net) uses `picture_index`, not game ID. If icons aren't loading, you may need to download them locally to `webapp/static/img/units/` and use those paths instead.

- [ ] **Step 3: Add `UNIQUE_BUILDING` entries (if needed)**

If any new unique unit is trained from a building other than Castle (e.g., Barracks, Archery Range, Siege Workshop), add to the `UNIQUE_BUILDING` dict in `constants.js`:

```javascript
const UNIQUE_BUILDING = {
    ...
    "Second Unit": "Barracks",
};
```

- [ ] **Step 4: Update `CIVS_WITHOUT_TREBUCHET` (if needed)**

Open `webapp/best_units.py`. If any new civ doesn't have access to trebuchets, add to the set:

```python
CIVS_WITHOUT_TREBUCHET = {"Wu", "Wei", "Shu", "NewCiv1"}
```

Also check `webapp/app.py` for the same set — search for `CIVS_WITHOUT_TREBUCHET` and update if duplicated there.

- [ ] **Step 5: Commit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add webapp/unit_lines.py webapp/static/js/constants.js webapp/best_units.py
git commit -m "config: add unit lines, icons, and building overrides for [new civs]"
```

---

## Task 7: Regenerate All Databases

**Purpose:** Run the full pipeline to produce updated databases from the new dat file with all config changes applied.

**Files:**
- Output: `extraction/extracted_data/*.json` (8 files)
- Output: `analysis/aoe2_reference.db`
- Output: `webapp/aoe2_reference.db`
- Output: `webapp/aoe2_units.db`

- [ ] **Step 1: Run extraction**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m extraction.run
```

Expected: all new civs appear by name, all new units appear with correct display names.

- [ ] **Step 2: Generate reference database**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m analysis.generate_reference
```

This takes 1-3 minutes. Watch for errors — common failure modes:
- `KeyError` on a unit ID &rarr; missing entry in `UNIT_NAMES`
- `KeyError` on a civ name &rarr; missing entry in `UNIQUE_UNITS` or `CIV_NAMES`
- Assertion errors &rarr; tech ID mismatch in `UNIQUE_UNITS` availability/elite tech fields

- [ ] **Step 3: Generate main database**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m analysis.generate_main_db
```

- [ ] **Step 4: Spot-check new civs in the database**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db')
conn.row_factory = sqlite3.Row
# Replace 'NewCiv1' with actual civ name:
rows = conn.execute('SELECT unit_slug, age, final_hp, final_attack, final_range FROM ref_units WHERE civ_name=? ORDER BY age, unit_slug', ('NewCiv1',)).fetchall()
print(f'Found {len(rows)} unit entries for NewCiv1:')
for r in rows:
    print(f'  {r[\"age\"]:10s} {r[\"unit_slug\"]:30s} HP={r[\"final_hp\"]} ATK={r[\"final_attack\"]} RNG={r[\"final_range\"]}')
conn.close()
"
```

Verify: unique units appear with reasonable stats, generic units appear for the civ's tech tree.

- [ ] **Step 5: Commit database files** (if databases are tracked in git)

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add webapp/aoe2_reference.db webapp/aoe2_units.db
git commit -m "data: regenerate databases from updated dat file"
```

If databases are `.gitignore`d, skip this commit — they'll be regenerated in CI/deploy.

---

## Task 8: Recompute Battle Scores and Power Units

**Purpose:** Run the simulation-based scoring pipeline that powers the unit rankings and matchup advisor pages.

**Files:**
- Output: `webapp/battle_cache.json`
- Output: `webapp/civ_power_units.json`

- [ ] **Step 1: Recompute battle scores**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp
python3 compute_battle_scores.py --full
```

**This takes 10-30 minutes** depending on civ count. The `--full` flag forces recomputation of all matchups (necessary when new civs/units are added). Without `--full`, only changed fingerprints are recomputed.

Watch for errors — common failure modes:
- Missing combat property &rarr; add to `COMBAT_PROPERTIES` or `UNIQUE_COMBAT_PROPERTIES`
- Missing unit line mapping &rarr; add to `UNIT_LINES` in `unit_lines.py`
- Simulation crash &rarr; likely a missing or malformed `attacks_json`/`armors_json` in the database

- [ ] **Step 2: Recompute civ power units**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp
python3 best_units.py
```

This reads `aoe2_reference.db` and produces `civ_power_units.json`.

- [ ] **Step 3: Verify new civs appear in power units**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -c "
import json
with open('webapp/civ_power_units.json') as f:
    data = json.load(f)
# Replace with actual new civ names:
for civ in ['NewCiv1', 'NewCiv2', 'NewCiv3']:
    if civ in data:
        print(f'{civ}: {len(data[civ])} power unit entries')
    else:
        print(f'{civ}: MISSING — check UNIQUE_UNITS and unit_lines.py')
"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add webapp/battle_cache.json webapp/civ_power_units.json
git commit -m "data: recompute battle scores and power units for [new civs/stat changes]"
```

---

## Task 9: Regenerate Golden Baselines and Run Tests

**Purpose:** Update the deterministic test snapshots to reflect the new dat file's stat values, then verify all tests pass.

**Files:**
- Modify: `.golden/baseline.json` (auto-generated)
- Possibly modify: `.golden/capture_baseline.py` — `MATCHUPS` list
- Possibly modify: `tests/test_simulations.py` — `MATCHUPS` list

- [ ] **Step 1: Regenerate golden baselines**

Stat changes will cause existing golden tests to fail because simulation outputs change. Regenerate:

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 .golden/capture_baseline.py
```

Expected: "Wrote .golden/baseline.json" with a count of matchup_sims entries.

- [ ] **Step 2: (Optional) Add new civ matchups to golden tests**

If you want regression coverage for new civs, add 1-2 pairs to the `MATCHUPS` list in BOTH files:

In `.golden/capture_baseline.py` (line ~37):
```python
MATCHUPS = [
    ("Aztecs", "Armenians"),
    ...
    ("NewCiv1", "NewCiv2"),  # New DLC coverage
]
```

In `tests/test_simulations.py`, mirror the same addition to its `MATCHUPS` list.

Then regenerate baselines again:
```bash
python3 .golden/capture_baseline.py
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
python3 -m pytest tests/ -v
```

Expected: all 27+ tests pass (more if you added new matchup pairs).

If tests fail:
- **Schema test failures** &rarr; a field is missing from the API response. Check `combat_unit_loader.py` and `generate_main_db.py`.
- **Golden regression failures** &rarr; you forgot to regenerate baselines (Step 1).
- **Import errors** &rarr; a config file has a syntax error. Check the traceback.

- [ ] **Step 4: Commit**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer
git add .golden/baseline.json
# Only if you modified these:
git add .golden/capture_baseline.py tests/test_simulations.py
git commit -m "test: regenerate golden baselines for updated dat file"
```

---

## Task 10: Smoke Test the Webapp

**Purpose:** Start the Flask server and manually verify new civs appear correctly in the UI.

**Files:**
- No changes — this is a verification task

- [ ] **Step 1: Start the server**

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/webapp
python3 app.py
```

The server will start on a port (default 5000, but macOS AirPlay uses 5000 — check output for actual port). If port 5000 is busy, set `PORT` environment variable:

```bash
PORT=8080 python3 app.py
```

- [ ] **Step 2: Verify civ list API**

```bash
curl -s http://localhost:8080/api/ref/civs | python3 -m json.tool | head -20
```

New civ names should appear in the list.

- [ ] **Step 3: Verify new civ's unit data**

```bash
# Replace NewCiv1 with actual civ name:
curl -s "http://localhost:8080/api/ref/civ/NewCiv1" | python3 -m json.tool | head -40
```

Should return unit data with stats, techs applied, and combat properties.

- [ ] **Step 4: Verify matchup advisor works with new civs**

```bash
# Replace civ names:
curl -s -X POST "http://localhost:8080/api/matchup-sims" \
  -H "Content-Type: application/json" \
  -d '{"civ_a": "NewCiv1", "civ_b": "Franks", "age": "imperial"}' | python3 -m json.tool | head -30
```

Should return matchup sim results with top units for both civs.

- [ ] **Step 5: Quick UI check in browser**

Open `http://localhost:8080` in a browser. Check:
- New civs appear in all dropdown menus
- Selecting a new civ shows its unique units with icons
- Matchup advisor shows results for new civ matchups
- Unit rankings page includes new unique units in correct lines

- [ ] **Step 6: Stop the server and note any issues**

If icons are missing, go back to Task 6 Step 2 and add `NAME_TO_ICON` entries or download icons locally.

---

## Summary: Quick Reference Checklist

For **stat-only changes** (no new civs, no new units), you only need:
- Task 1 (discovery — confirm no new civs/units)
- Task 7 (regenerate databases)
- Task 8 (recompute battle scores)
- Task 9 (regenerate baselines + run tests)

For **new civs**, the full sequence is Tasks 1-10.

### Files that must be updated per new civ

| File | What to add |
|------|-------------|
| `extraction/extract_constants.py` | Civ name at correct index in `CIV_NAMES` |
| `extraction/extract_units.py` | New unit IDs &rarr; display names in `UNIT_NAMES` |
| `analysis/config_units.py` | Civ &rarr; unique unit config in `UNIQUE_UNITS` |
| `analysis/config_combat.py` | Ability flags in `UNIQUE_COMBAT_PROPERTIES`, civ bonuses in `CIV_COMBAT_PROPERTIES` |
| `analysis/config_constants.py` | Civ name in `ORIGINAL_13_CIVS` (alphabetical) |
| `webapp/app.py` | Civ name in `ORIGINAL_13_CIVS` copy (alphabetical) |
| `webapp/static/js/constants.js` | Civ name in `ENABLED_CIVS`, unit names in `NAME_TO_ICON` |
| `webapp/unit_lines.py` | Civ &rarr; unique slugs in `UNIT_LINES[line]["unique_units"]` |
| `webapp/best_units.py` | Civ name in `CIVS_WITHOUT_TREBUCHET` (if applicable) |

### Pipeline execution order (always this order)

```
1. python3 -m extraction.run
2. python3 -m analysis.generate_reference
3. python3 -m analysis.generate_main_db
4. cd webapp && python3 compute_battle_scores.py --full
5. cd webapp && python3 best_units.py
6. python3 .golden/capture_baseline.py
7. python3 -m pytest tests/ -v
```
