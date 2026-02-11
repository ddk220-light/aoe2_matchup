# AoE2 Unit Analyzer

Extract and analyze unit data from Age of Empires II: Definitive Edition game files, with a full-featured web application for browsing, comparing, and simulating unit battles.

## Features

- **Data Extraction**: Parse the game's `.dat` file to extract unit stats, technologies, and civilizations
- **Web Application**: Flask-based webapp with unit browser, civ browser, battle simulator, matchup advisor, and unit line rankings
- **50 Civilizations**: Full coverage including Three Kingdoms DLC (Jurchens, Khitans, Shu, Wei, Wu)
- **Battle Simulation**: Tick-based combat simulator with 20 mechanics (trample, charge, bleed, dodge, etc.)
- **Unit Explorer**: Interactive CLI tool to search, compare, and analyze units
- **JSON Export**: All data exported to easily accessible JSON files
- **Comprehensive Coverage**: 1,182 units including all DLC content (Three Kingdoms, Battle for Greece, etc.)

## Quick Start

### 1. Setup

```bash
# Clone the repository
git clone https://github.com/ddk220-light/aoe2-unit-analyzer.git
cd aoe2-unit-analyzer

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Get the Game Data File

Copy the `.dat` file from your AoE2:DE installation:

**macOS (Steam):**
```bash
cp ~/Library/Application\ Support/Steam/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat .
```

**Windows (Steam):**
```bash
copy "C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat" .
```

### 3. Extract Data

```bash
python extract.py
```

This creates JSON files in the `output/` directory:
- `units.json` - All units with stats (1,182 units)
- `technologies.json` - All technologies (1,309 techs)
- `civilizations.json` - All civilizations (45 civs)
- `armor_classes.json` - Attack/armor class definitions

### 4. Explore the Data

```bash
# Interactive mode
python explore.py

# Command line mode
python explore.py search knight
python explore.py unit 38
python explore.py compare 38 93
python explore.py counters 38
```

## Web Application

The main product is a Flask web application with several features:

- **Unit Browser** (`/units`) — Compare any unit type across all 50 civilizations
- **Civilization Browser** (`/civ`) — Browse all units available to each civ
- **Battle Simulator** (`/simulate`) — Interactive 2D canvas battle visualization
- **Matchup Advisor** (`/matchup-advisor`) — AI-powered civ matchup analysis with army composition suggestions
- **Unit Line Rankings** — Pre-computed round-robin battle scores for every unit line

### Running the Web App

```bash
# Generate databases (requires dat file)
source venv/bin/activate
python3 -m database_creation.run

# Pre-compute battle scores
cd webapp && python3 compute_battle_scores.py

# Start the server
PORT=5002 python3 webapp/app.py
```

Visit `http://localhost:5002` in your browser.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full API reference and feature documentation.

## CLI Usage Examples

### Search for units
```bash
$ python explore.py search archer
[   4] Archer                    HP: 30 Class:Archer
[  24] Crossbowman               HP: 35 Class:Archer
[ 492] Arbalester                HP: 40 Class:Archer
[1968] Fire Archer               HP: 35 Class:Archer
...
```

### Get unit details
```bash
$ python explore.py unit 38

==================================================
Knight (ID: 38)
==================================================
Class: Cavalry | Type: Combat
HP: 100 | Speed: 1.35
Cost: 60 food, 75 gold
Train Time: 30s
Reload Time: 1.8s | Accuracy: 100%

Attacks:
  +10 vs Base Melee

Armor: 2/2 (melee/pierce)
```

### Compare units
```bash
$ python explore.py compare 38 93

============================================================
                      UNIT COMPARISON
============================================================
Stat            Knight                 Spearman
------------------------------------------------------------
HP              100                    45
Speed           1.35                   1.0
Range           0.0                    0.0
Reload          1.8                    3.0
Accuracy        100                    100
Cost            60f, 75g               35f, 25w
Armor (m/p)     2/2                    0/0
Main Attack     10 (Base Melee)        15 (War Elepha)
```

### Find counters
```bash
$ python explore.py counters 38

Knight is countered by:
  Halberdier                (+32 vs Cavalry)
  Pikeman                   (+22 vs Cavalry)
  Heavy Camel Rider         (+18 vs Cavalry)
  ...
```

## Data Structure

### Unit JSON Format
```json
{
  "id": 38,
  "name": "Knight",
  "internal_name": "KNGHT",
  "type": 70,
  "class": 12,
  "class_name": "Cavalry",
  "hit_points": 100,
  "speed": 1.35,
  "cost": {"food": 60, "gold": 75},
  "train_time": 30,
  "range": 0.0,
  "reload_time": 1.8,
  "accuracy": 100,
  "attacks": [
    {"class": 4, "class_name": "Base Melee", "amount": 10}
  ],
  "armors": [
    {"class": 4, "class_name": "Base Melee", "amount": 2},
    {"class": 3, "class_name": "Base Pierce", "amount": 2}
  ]
}
```

## Included Civilizations (50)

- **Base Game**: Britons, Byzantines, Celts, Chinese, Franks, Goths, Japanese, Mongols, Persians, Saracens, Teutons, Turks, Vikings
- **The Conquerors**: Aztecs, Huns, Koreans, Mayans, Spanish
- **The Forgotten**: Incas, Italians, Magyars, Slavs
- **African Kingdoms**: Berbers, Ethiopians, Malians, Portuguese
- **Rise of the Rajas**: Burmese, Khmer, Malay, Vietnamese
- **Last Khans**: Bulgarians, Cumans, Lithuanians, Tatars
- **Lords of the West**: Burgundians, Sicilians
- **Dawn of the Dukes**: Bohemians, Poles
- **Dynasties of India**: Bengalis, Dravidians, Gurjaras, Hindustanis
- **Return of Rome**: Romans
- **The Mountain Royals**: Armenians, Georgians
- **Chronicles: Three Kingdoms**: Jurchens, Khitans, Shu, Wei, Wu

## Requirements

- Python 3.8+
- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) - For parsing .dat files
- Age of Empires II: Definitive Edition (for the data file)

## Project Structure

```
aoe2-unit-analyzer/
├── README.md
├── DESIGN.md                    # Database pipeline design doc
├── ARCHITECTURE.md              # System architecture & product features
├── ADDING_CIVS.md               # Guide for adding new civilizations
├── requirements.txt
├── extract.py                   # Standalone extraction script
├── explore.py                   # Interactive data explorer (CLI)
│
├── database_creation/           # Data pipeline package
│   ├── run.py                   # Entry point (extract + generate)
│   ├── config.py                # Unit definitions, combat properties
│   ├── extract_units.py         # dat → units.json
│   ├── extract_techs.py         # dat → technologies.json, tech_ages.json
│   ├── extract_effects.py       # dat → effects.json, civ_tech_trees.json
│   ├── unit_analyzer.py         # Stat computation engine
│   ├── combat_properties.py     # Combat property extraction + layering
│   ├── generate_reference.py    # Builds reference DB (5 tables)
│   └── generate_main_db.py      # Builds main DB (flat unit_stats)
│
├── webapp/                      # Flask web application
│   ├── app.py                   # Flask app + API endpoints
│   ├── simulation.py            # Tick-based battle simulator
│   ├── compute_battle_scores.py # Pre-compute round-robin rankings
│   ├── aoe2_units.db            # Main database (gitignored)
│   ├── aoe2_reference.db        # Reference database (gitignored)
│   ├── battle_scores.json       # Pre-computed rankings (gitignored)
│   ├── Procfile                 # Railway deployment
│   └── templates/               # HTML templates
│       ├── home.html            # Landing page
│       ├── index.html           # Unit browser
│       ├── civ_select.html      # Civilization grid
│       ├── civ_detail.html      # Civ detail page
│       ├── simulate.html        # Battle simulator (2D canvas)
│       ├── matchup_advisor.html # Matchup advisor
│       └── analysis.html        # Audit/verification tool
│
└── output/                      # Standalone extraction output
    ├── units.json
    ├── technologies.json
    ├── civilizations.json
    └── armor_classes.json
```

## Documentation

- [DESIGN.md](DESIGN.md) — Database pipeline engineering design
- [ARCHITECTURE.md](ARCHITECTURE.md) — System architecture, product features, API reference
- [ADDING_CIVS.md](ADDING_CIVS.md) — Guide for adding new civilizations and combat mechanics

## License

Code is MIT licensed. Game data extracted from Age of Empires II: Definitive Edition is subject to Microsoft's Game Content Usage Rules.

## Credits

- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) by Siege Engineers
- [Age of Empires II: Definitive Edition](https://www.ageofempires.com/games/aoeiide/) by Xbox Game Studios
