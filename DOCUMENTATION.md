# AoE2 Data Analyzer - Technical Documentation

This document provides a comprehensive overview of the Age of Empires II: Definitive Edition data extraction and analysis system. It covers the extraction pipeline, output data formats, and the unit comparison analysis tool.

## Table of Contents

1. [Project Overview](#project-overview)
2. [File Structure](#file-structure)
3. [Data Extraction Pipeline](#data-extraction-pipeline)
4. [Output Data Formats](#output-data-formats)
5. [Unit Comparison Tool](#unit-comparison-tool)
6. [Key Concepts](#key-concepts)
7. [Known Issues and Limitations](#known-issues-and-limitations)

---

## Project Overview

This project extracts game data from the AoE2:DE `.dat` file (`empires2_x2_p1.dat`) using the `genieutils-py` library and provides tools to analyze unit statistics across all civilizations.

### Key Features

- Extract unit stats, technologies, civilizations, and effects from the game data
- Dynamically determine which techs are available in which age
- Compare any unit across all 50 ranked-play civilizations
- Account for civ bonuses, unique techs, and disabled techs per civ
- Calculate upgrade costs including unique tech costs

### Supported Civilizations

The system supports 50 civilizations available in ranked play:
- **Base game + DLCs**: Britons through Georgians (IDs 1-45)
- **Three Kingdoms DLC**: Shu, Wu, Wei, Jurchens, Khitans (IDs 49-53)
- **Excluded**: Age of Antiquity and Alexander campaign civs (not in ranked play)

---

## File Structure

```
aoe2unitanalyzer/
├── empires2_x2_p1.dat       # Game data file (input)
├── extract.py               # Main extraction script
├── extract_advanced.py      # Advanced extraction (effects, civ tech trees)
├── explore.py               # Exploration/debugging utilities
├── requirements.txt         # Python dependencies (genieutils-py)
├── venv/                    # Python virtual environment
├── output/                  # Extracted JSON data
│   ├── units.json           # Unit definitions and stats
│   ├── technologies.json    # Technology definitions
│   ├── civilizations.json   # Civilization definitions
│   ├── armor_classes.json   # Attack/armor class definitions
│   ├── tech_ages.json       # Tech age requirements (auto-generated)
│   ├── effects.json         # All effect definitions
│   ├── civ_tech_trees.json  # Per-civ disabled units/techs
│   └── tech_effects.json    # Technology effect commands
└── experiments/
    └── unit_comparison.py   # Main analysis tool
```

---

## Data Extraction Pipeline

### Step 1: Basic Extraction (`extract.py`)

The main extraction script parses the `.dat` file and outputs core game data.

**Key Functions:**

- `extract_units()` - Extracts all unit definitions with stats
- `extract_technologies()` - Extracts all tech definitions
- `extract_civilizations()` - Extracts civ definitions
- `determine_tech_age()` - Determines which age a tech requires based on `required_techs`
- `generate_tech_ages()` - Creates `tech_ages.json` for standard techs

**Civilization List:**

```python
CIV_NAMES = [
    "Gaia",        # 0 (skipped)
    "Britons", "Franks", ... "Georgians",   # 1-45
    None, None, None,  # 46-48 (Age of Antiquity - skipped)
    "Shu", "Wu", "Wei", "Jurchens", "Khitans",  # 49-53 (Three Kingdoms)
    None, None, None,  # 54-56 (Alexander - skipped)
]
```

**Age Detection Logic:**

Tech age is determined by checking `required_techs` for age-up tech IDs:
- Tech ID 101 = Feudal Age (age 2)
- Tech ID 102 = Castle Age (age 3)
- Tech ID 103 = Imperial Age (age 4)

**Usage:**
```bash
cd /Users/deepak/AI/aoe2unitanalyzer
source venv/bin/activate
python extract.py
```

### Step 2: Advanced Extraction (`extract_advanced.py`)

Extracts effect commands and civilization-specific data.

**Key Functions:**

- `extract_effects()` - Extracts all effect definitions with parsed commands
- `extract_civ_tech_trees()` - Extracts disabled techs/units per civ
- `extract_tech_effects()` - Maps technologies to their effect commands
- `parse_effect_command()` - Parses individual effect commands

**Effect Command Types:**

| Type | Name | Description |
|------|------|-------------|
| 0 | SET_ATTRIBUTE | Set unit attribute to value |
| 2 | ENABLE_DISABLE_UNIT | Enable/disable unit |
| 3 | UPGRADE_UNIT | Upgrade unit A to unit B |
| 4 | ADD_ATTRIBUTE | Add value to unit attribute |
| 5 | MULTIPLY_ATTRIBUTE | Multiply unit attribute by value |
| 101 | TECH_COST_SET | Set technology cost |
| 102 | DISABLE_TECH | Disable technology |
| 103 | DISABLE_UNIT | Disable unit |

**Unit Attribute IDs:**

| ID | Attribute |
|----|-----------|
| 0 | hit_points |
| 5 | movement_speed |
| 8 | armor (by class) |
| 9 | attack (by class) |
| 10 | attack_reload_time |
| 12 | max_range |
| 13 | work_rate |
| 19 | train_time |
| 103 | food_cost_abs |
| 105 | gold_cost_abs |

**Usage:**
```bash
python extract_advanced.py
```

---

## Output Data Formats

### units.json

Contains all unit definitions with their base stats.

```json
{
  "id": 38,
  "name": "Knight",
  "internal_name": "KNGHT",
  "class": 12,
  "class_name": "Cavalry",
  "hit_points": 100,
  "speed": 1.35,
  "range": 0.0,
  "reload_time": 1.8,
  "accuracy": 100,
  "train_time": 30,
  "cost": {"food": 60, "gold": 75},
  "displayed_attack": 10,
  "displayed_melee_armor": 2,
  "displayed_pierce_armor": 2,
  "attacks": [{"class": 4, "class_name": "Base Melee", "amount": 10}, ...],
  "armors": [{"class": 4, "class_name": "Base Melee", "amount": 2}, ...]
}
```

### technologies.json

Contains all technology definitions.

```json
{
  "id": 199,
  "name": "Fletching",
  "internal_name": "FLETCH",
  "civ": -1,
  "cost": {"food": 100, "gold": 50},
  "research_time": 30,
  "required_techs": [101],
  "effect_id": 199,
  "research_location": 84
}
```

Key fields:
- `civ`: -1 for universal techs, civ ID for civ-specific techs
- `required_techs`: Tech IDs that must be researched first (101/102/103 = age requirements)

### tech_ages.json

Auto-generated file mapping standard (non-civ-specific) techs to their age requirements.

```json
{
  "techs": {
    "75": {"name": "Blast Furnace", "age": 4, "building": "Blacksmith"},
    "199": {"name": "Fletching", "age": 2, "building": "Blacksmith"},
    "209": {"name": "Cavalier", "age": 4, "building": "Stable"}
  }
}
```

### civ_tech_trees.json

Contains per-civilization data including disabled units/techs.

```json
{
  "id": 53,
  "name": "Khitans",
  "tech_tree_effect_id": 988,
  "team_bonus_effect_id": 989,
  "disabled_techs": [
    {"id": 166, "name": "Knight (make avail)"},
    {"id": 209, "name": "Cavalier"},
    ...
  ],
  "disabled_units": [],
  "team_bonus": {...}
}
```

**Unit Availability:**

Units are disabled via "make avail" techs in `disabled_techs`. For example:
- `"Knight (make avail)"` disabled = civilization cannot train Knights

### effects.json

Contains all effect definitions with their commands.

```json
{
  "id": 685,
  "name": "Khmer UT",
  "commands": [
    {
      "type": 5,
      "type_name": "MULTIPLY_ATTRIBUTE",
      "a": -1,
      "b": 47,
      "c": 10,
      "d": 0.75,
      "description": "Multiply unit -1 attack_reload_time by 0.75"
    }
  ]
}
```

Command fields:
- `a`: Unit ID (-1 = class-based)
- `b`: Unit class (if a=-1)
- `c`: Attribute ID
- `d`: Value

### tech_effects.json

Maps technologies to their effects for easy lookup.

```json
{
  "tech_id": 199,
  "tech_name": "Fletching",
  "effect_id": 199,
  "commands": [...]
}
```

---

## Unit Comparison Tool

### Location

`experiments/unit_comparison.py`

### Usage

```bash
cd /Users/deepak/AI/aoe2unitanalyzer/experiments
source ../venv/bin/activate

# Compare Knights in Castle Age (default)
python unit_comparison.py 38

# Compare Archers in Imperial Age
python unit_comparison.py 4 --age imperial

# Show detailed breakdown for specific civs
python unit_comparison.py 38 --detail Bulgarians Franks
```

### Features

1. **Dynamic Tech Discovery**: Finds all techs affecting a unit by ID or class
2. **Age-Gated Bonuses**: Respects age requirements for civ bonuses and techs
3. **Unique Tech Support**: Applies Castle/Imperial age unique techs with costs
4. **Upgrade Cost Calculation**: Totals all relevant tech costs including unique techs
5. **Grouping**: Groups civs with identical stats into single rows
6. **Conditional Columns**: Shows Range column only for ranged units

### Output Columns

| Column | Description |
|--------|-------------|
| HP | Hit points |
| Atk | Attack damage |
| Rng | Range (ranged units only) |
| AtkSpd | Attacks per second (1 / reload_time) |
| M.Arm | Melee armor |
| P.Arm | Pierce armor |
| Speed | Movement speed |
| Cost | Unit cost (F=food, W=wood, G=gold) |
| Train | Train time in seconds |
| Upgr | Total upgrade cost (all relevant techs + unique techs) |

### Key Classes

**UnitStats**: Dataclass holding mutable unit stats
- `attack_rate()` method calculates attacks/second from reload_time

**UnitAnalyzer**: Main analysis class
- `load_data()` - Loads all JSON data files
- `find_techs_affecting_unit()` - Discovers relevant standard techs
- `get_unique_techs_for_unit()` - Finds applicable unique techs
- `get_civ_bonus_techs_for_unit()` - Finds C-Bonus techs for a civ
- `calculate_civ_stats()` - Calculates final stats for one civ
- `is_unit_disabled()` - Checks if unit is unavailable for a civ

### Civ Bonus Age Gating

C-Bonus techs can have age requirements in `required_techs`:
- Tech 101 = Feudal Age requirement
- Tech 102 = Castle Age requirement  
- Tech 103 = Imperial Age requirement

Example: Britons have two archer range bonuses:
- Tech 382: `required_techs: [102]` = Castle Age (+1 range)
- Tech 403: `required_techs: [103]` = Imperial Age (+1 more range)

### Unique Tech Classification

Unique techs are identified by:
- `civ` field >= 0 (civ-specific)
- Has non-empty `cost` field
- Name does NOT start with "C-Bonus"

Age classification uses cost heuristic:
- Total cost < 800 = Castle Age unique tech
- Total cost >= 800 = Imperial Age unique tech

---

## Key Concepts

### Effect Command Targeting

Commands can target units in two ways:
1. **Direct**: `a = unit_id` (affects specific unit)
2. **Class-based**: `a = -1, b = class_id` (affects all units of a class)

### Attack/Armor Encoding

Attack and armor values are encoded in field `d`:
- `armor_class = d // 256`
- `amount = d % 256` (signed: >127 means negative)

### Unit Classes

| ID | Class Name |
|----|------------|
| 0 | Archer |
| 6 | Infantry |
| 12 | Cavalry |
| 13 | Siege |
| 36 | Cavalry Archer |

### Building Work Rate

Team bonuses can affect building work rate (attribute 13), which inversely affects train time:
```python
train_time = base_train_time / work_rate_multiplier
```

Example: Huns team bonus gives Stable +20% work rate, reducing cavalry train time.

---

## Known Issues and Limitations

### Data Labeling Issues

Some techs have incorrect names in the dat file:
- Bulgarian "Stirrups" is labeled as "Khmer UT" (tech ID 685)
- This is a game data issue, not an extraction bug

### Unique Tech Age Detection

The cost-based heuristic for classifying unique techs as Castle vs Imperial age is approximate:
- Works for most cases (Castle UTs typically cost 400-750 total)
- Some edge cases may be misclassified

### Special Upgrade Availability

Some civs have special upgrade availability (e.g., Burgundians can research Cavalier in Castle Age). Currently this is hardcoded for known cases:
- Burgundians: Cavalier available in Castle Age

### Unit Classes

Some effect commands use unusual class IDs:
- Class 47 appears in Stirrups effect (cavalry attack speed)
- The exact mapping of all class IDs is not fully documented

### Missing Data

The following are not yet fully extracted/analyzed:
- Building bonuses
- Gathering rate bonuses
- Unique unit stats across civs
- Team bonus synergies

---

## Future Improvements

1. **Dynamic Special Upgrade Detection**: Parse tech tree effects to find age modifications
2. **Building Analysis**: Track building bonuses and their effects on units
3. **Full Bonus Descriptions**: Generate human-readable bonus descriptions from effects
4. **Web Interface**: Create a web-based tool for easier unit comparison
5. **Matchup Analysis**: Compare units against each other considering bonuses
