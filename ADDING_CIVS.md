# Adding New Civilizations

This guide explains how to add a new civilization to the AoE2 Unit Analyzer, including unit definitions, special effects, and which product features need updating.

## Prerequisites

- A copy of `empires2_x2_p1.dat` from the game installation in `database_creation/`
- Python 3.8+ with `genieutils` installed
- Familiarity with the [DESIGN.md](DESIGN.md) database pipeline

## Step-by-step: Adding a New Civ

### 1. Add the civilization name

**File:** `database_creation/config.py`

Add the civ name to `ORIGINAL_13_CIVS` (rename this list if expanding beyond 13):

```python
ORIGINAL_13_CIVS = [
    "Britons",
    # ... existing civs ...
    "Vikings",
    "Ethiopians",  # NEW
]
```

The name must match exactly what appears in `extracted_data/civ_tech_trees.json` (case-sensitive).

### 2. Add unique units

**File:** `database_creation/config.py` → `UNIQUE_UNITS`

Add an entry for the new civ with its unique unit(s):

```python
UNIQUE_UNITS = {
    # ... existing civs ...
    "Ethiopians": [
        {
            "base_id": 1068,               # Castle-age unit ID from units.json
            "display_name": "Shotel Warrior",
            "unit_class": 6,               # 0=Archer, 6=Infantry, 12=Cavalry
            "availability_tech": 590,       # Tech that enables this unit
            "elite_tech": 591,             # Tech for elite upgrade
            "elite_id": 1069,             # Elite unit ID
            "elite_name": "Elite Shotel Warrior",
        },
    ],
}
```

**How to find these IDs:**
- `base_id`: Search `extracted_data/units.json` by `internal_name` (more reliable than `name` which can be scrambled)
- `availability_tech`: Search `extracted_data/technologies.json` for a tech that enables this unit (look for effect commands with `type=2`, `a=unit_id`)
- `elite_tech` / `elite_id`: Search technologies for the elite upgrade tech (effect commands with `type=3`, upgrading base to elite)

### 3. Handle civ-specific unit overrides

If the civ gets a unique replacement for a standard unit line (like Persians get Savar instead of Paladin), add a `civ_upgrades` entry to the standard unit definition.

**File:** `database_creation/config.py` → `IMPERIAL_UNITS` or `CASTLE_UNITS`

```python
"paladin": {
    "base_id": 38,
    "display_name": "Cavalier",
    "upgrades": [
        (209, 283, "Cavalier"),
        (265, 569, "Paladin"),
    ],
    "civ_upgrades": {
        "Persians": [(tech_id, unit_id, "Savar")],
        # NEW: if your civ replaces paladin with something
    },
},
```

### 4. Add special combat properties

There are three layers of combat properties, applied in priority order.

#### 4a. Data-driven properties (automatic)

Most combat properties are extracted automatically from the dat file by `combat_properties.py`:
- `min_attack_range`, `projectile_speed`
- `splash_radius`, `is_siege_projectile`
- `extra_projectiles`, `extra_projectile_attacks_json`
- `charge_projectile_count/attacks_json/speed`
- `trample_percent`, `trample_radius`
- `dodge_shield_max`, `dodge_shield_recharge`
- `hp_regen`
- `bonus_damage_reduction`

These require **no manual configuration**. They are read from the unit's data in `units.json`.

#### 4b. Unique unit properties (hardcoded)

For abilities not extractable from the dat file, add entries to `UNIQUE_COMBAT_PROPERTIES`:

**File:** `database_creation/config.py`

```python
UNIQUE_COMBAT_PROPERTIES = {
    # ... existing entries ...
    # Example: unit that ignores armor
    "shotel_warrior": {"ignores_melee_armor": 1},
    "elite_shotel_warrior": {"ignores_melee_armor": 1},
}
```

Key is the base unit name (without civ suffix). Available properties:

| Property | Type | Description |
|----------|------|-------------|
| `ignores_melee_armor` | int (0/1) | Melee attacks ignore target's melee armor |
| `ignores_pierce_armor` | int (0/1) | Ranged attacks ignore target's pierce armor |
| `dismount_unit_id` | int | Unit spawned on death (e.g., Konnik) |
| `bleed_dps` / `bleed_duration` | float | Damage-over-time effect |
| `block_first_melee` | int (0/1) | Blocks first melee hit |
| `attack_bonus_per_kill` | int | Attack bonus gained per kill |
| `hp_transform_threshold` | float | HP fraction that triggers transformation |
| `charge_attack_range` | float | Range of charge attack |
| `charge_ignores_armor` | int (0/1) | Charge attack ignores armor |

#### 4c. Civ-conditional properties (unique tech effects)

For effects that come from unique technologies (e.g., Logistica giving Cataphracts trample), add to `CIV_COMBAT_PROPERTIES`:

**File:** `database_creation/config.py`

```python
CIV_COMBAT_PROPERTIES = {
    # ... existing entries ...
    # Example: Ethiopian Royal Heirs (hypothetical melee boost)
    ("Ethiopians", "shotel_warrior"): {"some_property": value},
    ("Ethiopians", "elite_shotel_warrior"): {"some_property": value},
}
```

Key is a `(civ_name, unit_slug)` tuple. The slug is either:
- Standard unit slug (e.g., `"champion"`, `"hussar"`)
- Unique unit slug with civ suffix (e.g., `"cataphract"` — note: NOT `"cataphract_byzantines"`, use the base name)

Common civ-conditional properties:

| Property | Example |
|----------|---------|
| `trample_flat_damage` + `trample_radius` | Logistica (Byzantines): 5 dmg, 0.5 radius |
| `ignores_melee_armor` | Wootz Steel (Dravidians) |
| `bonus_damage_reduction` | Paiks (Bengalis): 25% |
| `damage_reflect_percent` | Lamellar Armor (Khitans): 25% melee reflect |
| `bonus_hp_nearby` + `nearby_hp_bonus_count` | Coiled Serpent Array (Shu): +5 HP per nearby, max 4 |
| `hp_regen` | Ordo Cavalry (Khitans): 20 HP/min for cavalry |
| `charge_attack_melee` + `charge_recharge_time` | Comitatenses (Romans): 5 charge damage |

### 5. Handle non-elite unique units

Some unique units have no elite upgrade (e.g., Warrior Priest, Jian Swordsman, Grenadier, Xianbei Raider, Mounted Trebuchet). Set `elite_id` and `elite_tech` to `None`:

```python
"Jurchens": [
    {
        "base_id": 1908,
        "display_name": "Iron Pagoda",
        "unit_class": 12,
        "availability_tech": 1006,
        "elite_tech": 1007,
        "elite_id": 1910,
        "elite_name": "Elite Iron Pagoda",
    },
    {
        "base_id": 1911,
        "display_name": "Grenadier",
        "unit_class": 44,              # Gunpowder
        "availability_tech": 1008,
        "elite_tech": None,            # No elite upgrade
        "elite_id": None,
    },
],
```

The pipeline will create both Castle and Imperial Age entries for these units. The Imperial entry uses the same base unit with Imperial age techs applied (Blacksmith upgrades, unique techs, etc.).

In the `UNIT_LINES` config, use the same slug for both ages:
```python
"unique_units": {
    "Jurchens": ("grenadier_jurchens", "grenadier_jurchens"),  # Same slug both ages
}
```

### 6. Handle unique building placement

By default, unique units are shown under the Castle in the frontend. If a unique unit is trained in a different building, add it to the `UNIQUE_BUILDING` mapping in both `simulate.html` and `civ_detail.html`:

```javascript
const UNIQUE_BUILDING = {
    "Jian Swordsman": "Barracks",
    "Xianbei Raider": "Archery Range",
    "Grenadier": "Archery Range",
    "Warrior Priest": "Barracks",
    "Shrivamsha Rider": "Stable",
    "Elite Shrivamsha Rider": "Stable",
    "Mounted Trebuchet": "Siege Workshop",
};
```

### 7. Add unit icons to templates

Unit icons must be added to `NAME_TO_ICON` in **4 template files**:
- `webapp/templates/index.html`
- `webapp/templates/simulate.html`
- `webapp/templates/civ_detail.html`
- `webapp/templates/matchup_advisor.html`

```javascript
"Iron Pagoda": 1908,
"Elite Iron Pagoda": 1910,
```

The icon ID maps to the unit's game ID. Icons are loaded from two CDN sources (primary GitHub, fallback aoe2techtree.net).

### 8. Add unit line config for rankings (if applicable)

If the civ has a unique unit that should appear in unit line rankings:

**File:** `webapp/app.py` → `UNIT_LINES`

```python
UNIT_LINES = {
    "militia": {
        "name": "Militia Line",
        "building": "Barracks",
        "castle_slug": "swordsmen",
        "imperial_slug": "champion",
        "unique_units": {
            # ... existing entries ...
            "Ethiopians": ("shotel_warrior_ethiopians", "elite_shotel_warrior_ethiopians"),
        },
    },
}
```

Also update the matching config in `webapp/compute_battle_scores.py` (it duplicates `UNIT_LINES`).

### 9. Regenerate databases

```bash
# Full pipeline: extract from dat + generate both databases
python3 -m database_creation.run

# Or just regenerate from existing JSON (if dat file hasn't changed)
python3 -m database_creation.generate_reference
python3 generate_database.py
```

### 10. Recompute battle scores

```bash
cd webapp && python3 compute_battle_scores.py
```

This runs round-robin simulations for all unit lines and saves results to `battle_scores.json`. Takes a few minutes.

### 11. Verify the new civ

1. Start the server: `PORT=5002 python3 webapp/app.py`
2. Visit `/analysis` and select the new civ
3. Check each unit's stats, tech chain, and special effects
4. Compare values against the in-game tech tree or [aoe2techtree.net](https://aoe2techtree.net)
5. Mark units as verified once confirmed

---

## Adding a New Combat Property

When the game adds a new mechanic not yet in the simulation:

### 1. Check if it's extractable from dat

Look in `extracted_data/units.json` for the relevant unit. Check fields like:
- `blast_damage`, `blast_width` (trample/splash)
- `charge_type`, `charge_attack`, `charge_recharge_rate` (charge mechanics)
- `rear_attack_modifier` (HP regen)
- `bonus_damage_resistance` (bonus damage reduction)
- Projectile units (type 60 in dat) for projectile-based mechanics

If the data is in the dat file, add extraction logic to `combat_properties.py` → `get_extracted_combat_properties()`.

### 2. If not extractable, add to config

Add the property to `UNIQUE_COMBAT_PROPERTIES` or `CIV_COMBAT_PROPERTIES` in `config.py`.

### 3. Add to database schema

**File:** `generate_database.py`

Add the new column to the `unit_stats` CREATE TABLE statement and populate it in the INSERT.

### 4. Add to reference DB

**File:** `database_creation/generate_reference.py`

Record the property in the `ref_special_effects` table (in the special effects recording section).

### 5. Add to simulation

**File:** `webapp/simulation.py`

1. Read the new property in `prepare_combat_unit()` (parse from DB row)
2. Implement the mechanic in `simulate_battle()` tick loop
3. Also implement in `simulate_mixed_battle()` if it applies to mixed armies

### 6. Add to frontend simulation (optional)

**File:** `webapp/templates/simulate.html`

The frontend JavaScript simulation (`BattleUnit` class) has its own combat logic. Add the mechanic there too if you want it visible in the battle visualizer.

### 7. Update API responses

**File:** `webapp/app.py`

Add the new field to:
- `api_combat_unit()` — for the JS battle simulator
- `_build_combat_dict_from_ref()` — for the matchup advisor

### 8. Recompute battle scores

Re-run `compute_battle_scores.py` since the new mechanic affects simulation outcomes.

---

## Adding a New Unit Line

To add an entirely new unit type (e.g., a new siege unit or mounted unit):

### 1. Add to config

**File:** `database_creation/config.py`

Add entries to `CASTLE_UNITS` and/or `IMPERIAL_UNITS`:

```python
CASTLE_UNITS = {
    # ... existing ...
    "new_unit": {
        "base_id": 1234,               # Base unit ID from units.json
        "display_name": "New Unit",
        "unit_class": 12,              # Unit class ID
        "availability_tech": None,      # Tech required (None = always available)
        "upgrades": [
            (tech_id, unit_id, "Upgraded Name"),
        ],
    },
}
```

### 2. Add combat properties

Add to `COMBAT_PROPERTIES` if the unit type needs special handling:

```python
COMBAT_PROPERTIES = {
    "new_unit": {"unit_category": "siege"},  # or "trash", "military" (default)
}
```

### 3. Add to UNIT_LINES for rankings

**File:** `webapp/app.py` + `webapp/compute_battle_scores.py`

```python
UNIT_LINES = {
    "new_unit": {
        "name": "New Unit Line",
        "building": "Stable",
        "castle_slug": "new_unit",
        "imperial_slug": "elite_new_unit",
        "unique_units": {},
    },
}
```

### 4. Add to matchup advisor exclusions (if needed)

If the unit shouldn't appear in matchup advisor analysis (like Trebuchet/Ram):

**File:** `webapp/app.py`

```python
_ADVISOR_EXCLUDED = {"trebuchet", "ram", "siege_ram", "new_unit"}
```

### 5. Regenerate and recompute

```bash
python3 -m database_creation.run
cd webapp && python3 compute_battle_scores.py
```

---

## Checklist: Features to Update When Adding Stats

When a new stat or mechanic is added, these features may need updates:

| Feature | Files | What to update |
|---------|-------|---------------|
| Database schema | `generate_database.py` | Add column to `unit_stats` table |
| Reference DB | `generate_reference.py` | Record in `ref_special_effects` |
| Combat properties | `combat_properties.py`, `config.py` | Extraction logic or hardcoded values |
| Backend simulation | `simulation.py` | `prepare_combat_unit()` + tick loop |
| Frontend simulation | `templates/simulate.html` | `BattleUnit` class + render loop |
| Unit API | `app.py` → `api_combat_unit()` | Add field to JSON response |
| Ref combat API | `app.py` → `_build_combat_dict_from_ref()` | Add field from ref DB |
| Battle scores | `compute_battle_scores.py` | Re-run after sim changes |
| Matchup advisor | `app.py` → matchup advisor section | If the stat affects unit categorization or combo building |

---

## Common Pitfalls

1. **Scrambled unit names**: Newer units in the dat file have incorrect `name` fields (e.g., "FLNCER" for Fire Lancer, "SIEGECAMEL" for Mounted Trebuchet). Always use `internal_name` or numeric `id` for identification. The `display_name` in config overrides the dat name.

2. **Unit slugs for unique units**: In the database, unique unit slugs include the civ suffix (e.g., `longbowman_britons`). In `UNIQUE_COMBAT_PROPERTIES`, keys use the base name only (e.g., `longbowman`). In `CIV_COMBAT_PROPERTIES`, keys use `(civ_name, base_name)`.

3. **Cataphract-style trample**: Units with `blast_damage = -5.0` in the dat have NO trample — this is the standard value for infantry/cavalry. Trample from unique techs must be added via `CIV_COMBAT_PROPERTIES`.

4. **Attribute 63 is NOT "ignores armor"**: It's a general-purpose attribute used for many things. Keep `ignores_armor` hardcoded.

5. **HP regen source**: `rear_attack_modifier` on the creatable object, NOT `resource_decay` (which is corpse decay time = 25.0 for all combat units).

6. **UNIT_LINES duplication**: `webapp/app.py` and `webapp/compute_battle_scores.py` both define `UNIT_LINES`. Keep them in sync when adding unit lines.

7. **NAME_TO_ICON duplication**: Icon mappings are duplicated across 4 templates (`index.html`, `simulate.html`, `civ_detail.html`, `matchup_advisor.html`). Update all 4 when adding new units.

8. **Non-elite unique units need age-filtered queries**: When the same slug exists in both Castle and Imperial ages (non-elite unique units), queries must include `AND age=?` to avoid returning Castle data for Imperial lookups. Both `app.py` and `compute_battle_scores.py` filter by age.

9. **Civ upgrade replacements (civ_upgrades)**: When a standard unit is replaced for a civ (e.g., Persians' Savar, Romans' Legionary), the slug stays the same in the database (e.g., `champion`) but `unit_name` changes. The replacement unit must exist in `extracted_data/units.json` — add it to `UNIT_NAMES` in `extract_units.py` if missing.

10. **Misleading internal names**: Unit 1923 has internal name SIEGECAMEL but is actually the Mounted Trebuchet (ranged siege, range 10, Siege Workshop). Always verify unit stats before trusting the name.

11. **Port 5000**: macOS uses port 5000 for AirPlay Receiver. Use `PORT=5002 python3 webapp/app.py` for local testing.

12. **Pair cache keys**: The matchup advisor caches simulation results by Python `id()` of unit dicts, not by slug. This correctly handles same-slug units from different civs.

13. **Three Kingdoms civ tech trees**: 3K civs use `disabled_techs` arrays in `civ_tech_trees.json` (same as other civs). They are NOT "empty" trees — the pipeline handles them correctly.
