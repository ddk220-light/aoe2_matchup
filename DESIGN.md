# AoE2 Reference Database — Engineering Design Document

## Overview

The `database_creation/` package extracts Age of Empires II: Definitive Edition unit and technology data from the game's binary data file, computes fully-upgraded unit stats for each civilization, and writes a golden reference database (`webapp/aoe2_reference.db`).

The pipeline has two phases:

```
empires2_x2_p1.dat  ──►  extracted_data/*.json  ──►  webapp/aoe2_reference.db
    (binary)           (8 intermediate files)         (SQLite, 5 tables)
     Phase 1: extract        Phase 2: generate
```

**Single command:** `python3 -m database_creation.run`

**Scope:** 13 original civilizations (Britons through Vikings), Castle and Imperial age units, including unique units. 326 total unit entries.

---

## Directory Structure

```
database_creation/
├── __init__.py              # Package marker
├── run.py                   # Entry point — runs Phase 1 then Phase 2
│
│  ── Phase 1: Extraction (dat → JSON) ──
├── extract_constants.py     # Shared: ARMOR_CLASSES, CIV_NAMES
├── extract_units.py         # dat → units.json (1182 units)
├── extract_techs.py         # dat → technologies.json (1309), tech_ages.json (62)
├── extract_effects.py       # dat → effects.json (1064), civ_tech_trees.json (50), tech_effects.json (956)
│
│  ── Phase 2: Reference DB Generation (JSON → SQLite) ──
├── config.py                # Unit definitions, combat properties, constants
├── unit_analyzer.py         # UnitStats dataclass + UnitAnalyzer (loads JSON, applies techs)
├── combat_properties.py     # Combat property extraction and layering
├── generate_reference.py    # Builds the 5-table reference database
│
│  ── Data ──
├── empires2_x2_p1.dat       # Game binary (10MB, gitignored)
└── extracted_data/           # Intermediate JSON files (7.6MB, gitignored)
    ├── units.json            # All combat units with stats, attacks, armors
    ├── technologies.json     # All techs with costs, prerequisites, effects
    ├── effects.json          # All effect commands (set/add/multiply attribute)
    ├── tech_effects.json     # Tech → effect command mapping
    ├── civ_tech_trees.json   # Disabled techs/units per civ, team bonuses
    ├── tech_ages.json        # Standard tech → age availability
    ├── civilizations.json    # Civ names and IDs
    └── armor_classes.json    # Armor class ID → name mapping
```

---

## Phase 1: Extraction

### How It Works

`run.py` calls `extract_all(dat_path, output_dir)` which:
1. Parses `empires2_x2_p1.dat` once using the `genieutils` Python library (`DatFile.parse()`)
2. Passes the parsed `DatFile` object to each extractor module
3. Writes 8 JSON files to `extracted_data/`

The dat file is only parsed once. The old pipeline (`old/extract.py` + `old/extract_advanced.py`) parsed it twice.

### Extractor Modules

#### `extract_constants.py`
Shared constants used by multiple extractors:
- `ARMOR_CLASSES`: dict of `{class_id: name}` (40 classes, e.g., `{4: "Base Melee", 8: "Cavalry"}`)
- `CIV_NAMES`: list indexed by civ ID (50 civs + Gaia, `None` for non-ranked DLC civs)

#### `extract_units.py` → `units.json`
Extracts all combat units (type 70/80, HP > 0) from Gaia civ (which has all base units).

For each unit, extracts:
- Basic stats: `id`, `name`, `internal_name`, `type`, `class`, `hit_points`, `speed`, `line_of_sight`
- Combat stats: `range`, `min_range`, `reload_time`, `attack_delay`, `accuracy`, `blast_width`, `blast_damage`
- Attacks/armors: `attacks` (list of `{class, class_name, amount}`), `armors` (same format)
- Display stats: `displayed_attack`, `displayed_melee_armor`, `displayed_pierce_armor`
- Cost: `cost` dict (`{food, wood, gold, stone}`), `train_time`
- Projectiles: `total_projectiles`, `max_total_projectiles`, `projectile_speed` (looked up from type-60 projectile unit), `secondary_projectile_unit`, `secondary_projectile_attacks`
- Charge mechanics: `charge_attack`, `charge_recharge_rate`, `charge_type`, `charge_projectile_unit`, `charge_projectile_speed`, `charge_projectile_attacks`
- Special: `hp_regen` (from `rear_attack_modifier` attribute), `bonus_damage_resistance`

**Key implementation detail:** Projectile speed is not on the main unit — it's on the projectile unit (type 60 in dat). The extractor builds a lookup dict of all units (including type 60) and resolves projectile IDs to get speed and attack data.

**Name resolution:** Unit names in the dat file are scrambled for newer units. `UNIT_NAMES` (by ID) and `INTERNAL_NAME_MAP` (by internal name) provide correct display names.

#### `extract_techs.py` → `technologies.json`, `tech_ages.json`
- `extract_technologies(df)`: Extracts all named techs with `id`, `name`, `research_time`, `civ` (-1 = all civs), `effect_id`, `required_techs`, `research_location`, `cost`
- `generate_tech_ages(techs)`: Computes which age each standard tech becomes available (1=Dark through 4=Imperial) by resolving prerequisite chains. Only outputs standard techs (blacksmith upgrades, unit line upgrades, etc.)

#### `extract_effects.py` → `effects.json`, `civ_tech_trees.json`, `tech_effects.json`
- `extract_effects(df)`: Extracts all effect command lists. Each effect has commands with `type`, `a`, `b`, `c`, `d` fields plus human-readable `description`.
- `extract_civ_tech_trees(df, techs_by_id, units_by_id)`: For each civ, extracts disabled techs/units (from tech tree effect), team bonus commands, and civ bonus effect IDs.
- `extract_tech_effects(df)`: Maps each technology to its effect commands.

**Effect command types** (most relevant):
| Type | Name | Meaning |
|------|------|---------|
| 0 | SET_ATTRIBUTE | Set unit attribute to value |
| 2 | ENABLE_DISABLE_UNIT | Enable/disable a unit |
| 3 | UPGRADE_UNIT | Upgrade unit A to unit B |
| 4 | ADD_ATTRIBUTE | Add value to unit attribute (for attack/armor: `d = class*256 + amount`) |
| 5 | MULTIPLY_ATTRIBUTE | Multiply unit attribute by factor |
| 102 | DISABLE_TECH | Disable a technology |
| 103 | DISABLE_UNIT | Disable a unit |

### Civilizations and Armor Classes
`run.py` writes `civilizations.json` and `armor_classes.json` directly (trivial extractions not worth separate modules).

---

## Phase 2: Reference DB Generation

### Architecture

```
config.py (unit definitions, combat properties)
    │
    ▼
unit_analyzer.py (loads JSON, applies tech effects to compute stats)
    │
    ▼
combat_properties.py (extracts special properties from dat data + config overrides)
    │
    ▼
generate_reference.py (orchestrates per-civ, per-unit processing → SQLite)
```

### config.py — Unit Definitions

**`ORIGINAL_13_CIVS`**: The 13 civs currently covered:
Britons, Byzantines, Celts, Chinese, Franks, Goths, Japanese, Mongols, Persians, Saracens, Teutons, Turks, Vikings.

**`CASTLE_UNITS`** and **`IMPERIAL_UNITS`**: Dicts keyed by slug (e.g., `"swordsmen"`, `"arbalester"`, `"cavalier"`). Each entry defines:
```python
{
    "base_id": 75,                          # Starting unit ID (e.g., Man-at-Arms)
    "display_name": "Long Swordsman",       # Name at this age
    "unit_class": 6,                        # Unit class (6=Infantry)
    "availability_tech": None,              # Tech that makes unit available (or None)
    "upgrades": [
        (207, 77, "Long Swordsman"),        # (tech_id, resulting_unit_id, name)
    ],
    "civ_upgrades": {                       # Optional: civ-specific overrides
        "Persians": [(tech_id, unit_id, "Savar")],
    },
}
```

The `upgrades` list defines the unit line evolution. Each tuple `(tech_id, unit_id, name)` is a line upgrade that transforms the unit. `calculate_unit_stats_for_civ()` applies these in order, checking if the civ has access to each tech.

**`UNIQUE_UNITS`**: Dict keyed by civ name. Each civ has a list of unique unit entries:
```python
{
    "base_id": 8,                   # Castle-age unique unit ID
    "display_name": "Longbowman",
    "unit_class": 0,                # 0=Archer
    "availability_tech": 263,       # Tech that enables this unit
    "elite_tech": 360,              # Tech for elite upgrade
    "elite_id": 530,                # Elite unit ID
    "elite_name": "Elite Longbowman",
}
```

**Combat property dicts** (three layers, applied in order):

1. `COMBAT_PROPERTIES`: keyed by unit slug. Properties that apply to all civs for a unit type (e.g., `"mangonel": {"is_siege_projectile": True}`).

2. `UNIQUE_COMBAT_PROPERTIES`: keyed by base unit name. Properties for unique units regardless of civ (e.g., `"leitis": {"ignores_melee_armor": True, "ignores_pierce_armor": True}`).

3. `CIV_COMBAT_PROPERTIES`: keyed by `(civ_name, unit_slug)` tuple. Civ-specific overrides, typically from unique techs (e.g., `("Byzantines", "cataphract"): {"trample_flat_damage": 5, "trample_radius": 0.5}` for Logistica).

### unit_analyzer.py — Stat Computation

**`UnitStats`** dataclass fields:
```
hp, attack, melee_armor, pierce_armor, speed, range, reload_time,
attack_delay, accuracy, los, cost_food, cost_wood, cost_gold, cost_stone,
train_time, upgrade_cost, attacks (dict), armors (dict)
```

**`UnitAnalyzer`** loads all 7 JSON files in `__init__()` and builds indexed lookups:
- `self.units`: `{unit_id: unit_dict}`
- `self.techs`: `{tech_id: tech_dict}`
- `self.effects`: `{effect_id: effect_dict}`
- `self.tech_effect_map`: `{tech_id: tech_effect_dict}`
- `self.civ_tech_trees`: `{civ_name: tech_tree_dict}`
- `self.civ_disabled_tech_ids`: `{civ_name: set(disabled_tech_ids)}`
- `self.tech_ages`: `{tech_id_str: {"age": int}}`

**Key method: `calculate_unit_stats_for_civ(civ_name, base_unit_id, unit_class, max_age, upgrades, availability_tech, display_name, civ_upgrades)`**

Returns `(stats, applied_techs, unit_id, unit_name)` where:
- `stats`: Final `UnitStats` after all techs applied
- `applied_techs`: List of `(tech_id, tech_name, tech_type, building, age, effects_desc, cost)` tuples
- `unit_id`: The final game unit ID (after all line upgrades)
- `unit_name`: The display name of the final unit

**Tech application order** (order matters — additive before multiplicative):
1. **Line upgrades**: Apply upgrade techs from the `upgrades` list (each may change the unit ID)
2. **Standard techs**: Blacksmith, university, barracks techs etc. that affect this unit (filtered by civ tech tree)
3. **Civ bonus techs**: Civ-specific bonuses (identified by `tech.civ == civ_id` and no research cost)
4. **Team bonus attacks**: Attack/armor bonuses from team bonus effects
5. **Unique techs**: Castle-age and Imperial-age unique techs for this civ
6. **Work rate**: Building work rate adjustments (affects train time)

**`apply_effect_command(stats, cmd)`**: Handles effect types 0 (SET), 4 (ADD), 5 (MULTIPLY) for all unit attributes. For attack/armor (attributes 8/9), decodes the packed `d = class*256 + amount` format.

### combat_properties.py — Special Properties

Three functions that build a layered property dict:

**`get_extracted_combat_properties(unit_id, units_data)`**: Reads the unit's JSON data to extract data-driven properties:
- `min_attack_range`, `projectile_speed`
- `splash_radius` (from `blast_width` for siege units where `blast_damage == 1.0`)
- `is_siege_projectile` (class 13 + `blast_damage == 1.0`)
- `extra_projectiles`, `extra_projectile_attacks_json` (for Chu Ko Nu, Kipchak, etc.)
- `charge_projectile_count/attacks_json/speed` (for Fire Lancer, Fire Archer)
- `trample_percent/radius` (from `blast_damage` fractional values)
- `dodge_shield_max/recharge`, `splash_on_hit_radius`
- `bonus_damage_reduction`, `hp_regen`

**`get_combat_properties(unit_slug, civ_name, unit_id, units_data)`**: Merges properties in priority order:
1. Start with defaults (all properties = 0/False/None)
2. Apply extracted data from dat file
3. Apply `COMBAT_PROPERTIES[unit_slug]` overrides
4. Apply `UNIQUE_COMBAT_PROPERTIES[base_name]` overrides
5. Apply `CIV_COMBAT_PROPERTIES[(civ_name, unit_slug)]` overrides

**`compute_dismount_stats(analyzer, dismount_unit_id, civ_name, max_age)`**: For units like Konnik that have a dismounted form.

### generate_reference.py — Database Builder

**`generate_reference_database(analyzer)`**: The main function. For each civ in `ORIGINAL_13_CIVS`:

1. **Castle age units**: Iterates `CASTLE_UNITS`, calls `calculate_unit_stats_for_civ()`, records results
2. **Imperial age units**: Iterates `IMPERIAL_UNITS`, same process with `max_age=IMPERIAL_AGE`
3. **Unique units**: Iterates `UNIQUE_UNITS[civ_name]`, calls `calculate_unique_unit_stats()` for both Castle and Imperial (elite) versions

For each unit, it:
- Computes base stats and final stats
- Records every tech applied with its effect
- Builds a stat chain (snapshot after each tech)
- Extracts combat properties and records special effects
- Records projectile data
- Computes total upgrade cost

It then calls `print_reference_display()` to output a human-readable summary.

---

## Database Schema

### `ref_units` (326 rows)
The main table. One row per (civ, unit, age) combination.

| Column | Type | Description |
|--------|------|-------------|
| `civ_name` | TEXT | Civilization name (e.g., "Britons") |
| `unit_name` | TEXT | Actual unit name after upgrades (e.g., "Crossbowman" for Persians' arbalester slot) |
| `unit_slug` | TEXT | Config slot name (e.g., "arbalester"). Unique units: `base_name_civname` (e.g., "longbowman_britons") |
| `unit_type` | TEXT | "standard" or "unique" |
| `age` | TEXT | "Castle" or "Imperial" |
| `unit_class` | INTEGER | Unit class ID (0=Archer, 6=Infantry, 12=Cavalry, 13=Siege, etc.) |
| `is_ranged` | INTEGER | 1 if `base_range > 0` |
| `base_*` | REAL | Stats before any tech upgrades |
| `final_*` | REAL | Stats after all available techs applied |
| `base_attacks_json` | TEXT | JSON dict of `{class_id: amount}` for base attacks |
| `final_attacks_json` | TEXT | Same, after upgrades |
| `total_projectiles` | REAL | Number of projectiles per attack |
| `projectile_speed` | REAL | Speed of primary projectile |
| `min_range` | REAL | Minimum attack range |
| `upgrade_cost_food/wood/gold` | INTEGER | Total resource cost of all upgrades applied |
| `applied_bonuses_summary` | TEXT | Human-readable summary of applied techs |

**Important:** `unit_slug` vs `unit_name` — the slug is the config slot key (e.g., "arbalester") but `unit_name` is the actual unit the civ gets. Persians don't get Arbalester, so their "arbalester" slug has `unit_name="Crossbowman"` because their line stops at Crossbowman.

### `ref_techs_applied` (2080 rows)
Every technology applied to each unit.

| Column | Type | Description |
|--------|------|-------------|
| `ref_unit_id` | INTEGER | FK to ref_units |
| `tech_id` | INTEGER | Technology ID from dat file |
| `tech_name` | TEXT | Technology name |
| `tech_type` | TEXT | "standard", "civ_bonus", "unique_tech", or "work_rate" |
| `building` | TEXT | Building where researched (e.g., "Blacksmith", "Castle") |
| `age_available` | TEXT | Age when tech becomes available |
| `effect_description` | TEXT | Human-readable description of what it does |
| `cost_food/wood/gold` | INTEGER | Research cost |

### `ref_stat_chain` (2392 rows)
Snapshot of unit stats after each tech is applied, in order. Step 0 is always "Base Stats".

| Column | Type | Description |
|--------|------|-------------|
| `ref_unit_id` | INTEGER | FK to ref_units |
| `step_order` | INTEGER | 0 = base, 1 = first tech, 2 = second tech, ... |
| `tech_name` | TEXT | Name of tech applied at this step |
| `tech_type` | TEXT | "base", "standard", "civ_bonus", "unique_tech", "work_rate" |
| `hp`, `attack`, `melee_armor`, ... | REAL | Full stat snapshot after this step |
| `attacks_json`, `armors_json` | TEXT | Full attack/armor class breakdown as JSON |

### `ref_special_effects` (47 rows)
Special combat properties that don't fit in standard stat columns.

| Column | Type | Description |
|--------|------|-------------|
| `ref_unit_id` | INTEGER | FK to ref_units |
| `property_name` | TEXT | Property key (e.g., "trample_flat_damage", "hp_regen", "extra_projectiles") |
| `property_value` | TEXT | Value as string |
| `source` | TEXT | "extracted_data", "CIV_COMBAT_PROPERTIES", or "UNIQUE_COMBAT_PROPERTIES" |

### `ref_projectiles` (327 rows)
Projectile data for ranged/siege units.

| Column | Type | Description |
|--------|------|-------------|
| `ref_unit_id` | INTEGER | FK to ref_units |
| `projectile_type` | TEXT | "primary", "extra", or "charge" |
| `projectile_count` | INTEGER | Number of projectiles of this type |
| `projectile_speed` | REAL | Projectile speed |
| `attacks_json` | TEXT | Attack classes for this projectile type (JSON dict) |
| `blast_radius` | REAL | Splash damage radius |
| `is_siege_projectile` | INTEGER | 1 for area-damage siege projectiles |

---

## Common Queries

### Get fully-upgraded stats for a unit

```sql
SELECT unit_name, civ_name, age, final_hp, final_attack, final_melee_armor,
       final_pierce_armor, final_speed, final_range, final_reload_time
FROM ref_units
WHERE unit_slug = 'arbalester' AND civ_name = 'Britons';
```

### Get all techs applied to a unit

```sql
SELECT ta.tech_name, ta.tech_type, ta.building, ta.age_available,
       ta.effect_description, ta.cost_food, ta.cost_wood, ta.cost_gold
FROM ref_techs_applied ta
JOIN ref_units u ON ta.ref_unit_id = u.id
WHERE u.unit_slug = 'knight' AND u.civ_name = 'Franks' AND u.age = 'Castle'
ORDER BY ta.id;
```

### Trace stat progression through upgrades

```sql
SELECT sc.step_order, sc.tech_name, sc.tech_type,
       sc.hp, sc.attack, sc.range_val, sc.speed
FROM ref_stat_chain sc
JOIN ref_units u ON sc.ref_unit_id = u.id
WHERE u.unit_slug = 'arbalester' AND u.civ_name = 'Britons'
ORDER BY sc.step_order;
```

Returns the stat snapshot after each tech:
```
0  Base Stats              40.0  6.0   5.0   0.96
1  Chemistry               40.0  6.0   5.0   0.96   (Chemistry adds +1 pierce attack but base attack display stays 6)
2  Fletching               40.0  6.0   6.0   0.96
3  Bodkin Arrow            40.0  6.0   7.0   0.96
4  Bracer                  40.0  6.0   8.0   0.96
...
8  C-Bonus, +1 range       40.0  6.0   9.0   0.96
9  C-Bonus, +1 range       40.0  6.0  10.0   0.96
10 British Yeoman          40.0  6.0  11.0   0.96
```

### Get special combat properties

```sql
SELECT se.property_name, se.property_value, se.source
FROM ref_special_effects se
JOIN ref_units u ON se.ref_unit_id = u.id
WHERE u.unit_name LIKE '%Cataphract%' AND u.civ_name = 'Byzantines';
```

Returns: `trample_flat_damage = 5`, `trample_radius = 0.5` (from Logistica).

### Get projectile data (e.g., Chu Ko Nu's extra arrows)

```sql
SELECT p.projectile_type, p.projectile_count, p.projectile_speed, p.attacks_json
FROM ref_projectiles p
JOIN ref_units u ON p.ref_unit_id = u.id
WHERE u.unit_slug = 'chu_ko_nu_chinese' AND u.age = 'Castle';
```

Returns:
- `primary, 3, 7.0, NULL` — 3 primary projectiles
- `extra, 2, 7.0, {"3": 3}` — 2 extra arrows doing 3 pierce damage each

### Compare a unit across civilizations

```sql
SELECT civ_name, unit_name, final_hp, final_attack, final_range,
       final_melee_armor, final_pierce_armor, final_speed
FROM ref_units
WHERE unit_slug = 'knight' AND age = 'Castle'
ORDER BY civ_name;
```

### Get total upgrade cost

```sql
SELECT unit_name, civ_name, age,
       upgrade_cost_food, upgrade_cost_wood, upgrade_cost_gold
FROM ref_units
WHERE unit_slug = 'arbalester' AND civ_name = 'Britons';
-- Returns: 1400F, 750W, 1400G (sum of all upgrade tech costs)
```

### Find which unit a civ actually gets for a slot

```sql
-- Persians don't get Arbalester — what do they get?
SELECT unit_name, unit_slug, age
FROM ref_units
WHERE civ_name = 'Persians' AND unit_slug = 'arbalester';
-- Returns: Crossbowman (their line stops at Crossbowman)
```

---

## Data Flow Detail

### How `unit_slug` maps to actual units

The slug is the config key (e.g., `"arbalester"` in `IMPERIAL_UNITS`). The config defines the base unit and upgrade chain:

```python
"arbalester": {
    "base_id": 4,           # Archer
    "upgrades": [
        (196, 24, "Crossbowman"),   # tech 196 upgrades to unit 24
        (237, 492, "Arbalester"),   # tech 237 upgrades to unit 492
    ],
}
```

When computing for Persians, `calculate_unit_stats_for_civ()` checks if tech 237 (Arbalester) is disabled for Persians. It is, so the chain stops at Crossbowman (unit 24). The returned `unit_name` is "Crossbowman" and `unit_id` is 24, even though the slug is "arbalester".

### Attack/armor encoding

In the extracted JSON, attacks and armors are lists of `{class, amount}` dicts. In the database, they're stored as JSON dicts: `{class_id: amount}`.

In effect commands (tech application), attack/armor values are packed as: `d = class_id * 256 + amount`. Negative `d` means negative amount. `_decode_armor_attack_value()` unpacks this.

### Combat property priority

```
defaults (all zero/false)
    ↓ override with
extracted data from dat file (data-driven: projectile speed, trample, etc.)
    ↓ override with
COMBAT_PROPERTIES[unit_slug] (hardcoded per unit type)
    ↓ override with
UNIQUE_COMBAT_PROPERTIES[base_name] (hardcoded per unique unit)
    ↓ override with
CIV_COMBAT_PROPERTIES[(civ, slug)] (hardcoded per civ+unit, e.g., Logistica)
```

Later layers override earlier layers.

---

## Running the Pipeline

### Prerequisites
- Python 3.8+
- `genieutils` package (`pip install genieutils`)
- `empires2_x2_p1.dat` in `database_creation/` (copy from AoE2:DE installation, gitignored)

### Full pipeline (extract + generate)
```bash
python3 -m database_creation.run
```

### Generate DB only (from existing JSON)
```bash
python3 -m database_creation.generate_reference
```

### Adding a new civilization

1. Add civ name to `ORIGINAL_13_CIVS` in `config.py`
2. Add any civ-specific entries to `CIV_COMBAT_PROPERTIES` (for unique tech effects like Logistica trample)
3. Add unique units to `UNIQUE_UNITS[civ_name]`
4. Add civ-specific unit overrides to `civ_upgrades` in `CASTLE_UNITS`/`IMPERIAL_UNITS` if needed (e.g., Persians' Savar replacing Paladin)
5. Run `python3 -m database_creation.run`

### Adding a new unit line

1. Add entry to `CASTLE_UNITS` and/or `IMPERIAL_UNITS` in `config.py` with `base_id`, `display_name`, `unit_class`, and `upgrades` chain
2. Add any special combat properties to `COMBAT_PROPERTIES`
3. Run the pipeline

### Adding a new combat property

1. Add property extraction logic to `get_extracted_combat_properties()` in `combat_properties.py` (if data-driven from dat)
2. Or add to `COMBAT_PROPERTIES`/`UNIQUE_COMBAT_PROPERTIES`/`CIV_COMBAT_PROPERTIES` in `config.py` (if hardcoded)
3. Add property recording to `generate_reference.py` in the special effects section
4. Run the pipeline

---

## Known Quirks

- **Scrambled unit names**: Newer units in the dat file have wrong `name` fields (e.g., ID 1231 has name "Arambai" but internal_name "KIPCHAK"). The extractor uses `UNIT_NAMES` by ID and `INTERNAL_NAME_MAP` by internal name as fallbacks. `calculate_unit_stats_for_civ` uses the config `display_name` instead of dat name.

- **Cataphract trample**: Not in base unit data (`blast_damage=-5.0` = no trample). Applied via `CIV_COMBAT_PROPERTIES` for Byzantines only (represents Logistica unique tech: 5 flat trample damage).

- **Leitis ignores armor**: Hardcoded in `UNIQUE_COMBAT_PROPERTIES` — no dat file source found for this property.

- **Armor class 39 (Mounted Archers)**: Many units have `attack class 39 = -3` and `armor class 39 = -3`. These cancel out normally (0 net). Ethiopian Royal Heirs tech adds +3 to armor class 39, making it 0, so attacks from mounted units do 3 less damage. Not relevant for the original 13 civs.

- **Attribute 63**: In the dat file, this is a general-purpose attribute (not exclusively "ignores armor"). Keep `ignores_armor` hardcoded.

- **`blast_damage` interpretation**: Fractional values (0.2–0.5) = trample percent; 1.0 = full siege area damage; -5.0 = standard unit (no trample).

- **`hp_regen`**: Stored as `rear_attack_modifier` on the creatable object in genieutils, NOT `resource_decay` (which is corpse decay time = 25.0 for all combat units).
