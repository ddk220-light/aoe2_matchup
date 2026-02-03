# AoE2 Unit Analyzer

Extract and analyze unit data from Age of Empires II: Definitive Edition game files.

## Features

- **Data Extraction**: Parse the game's `.dat` file to extract unit stats, technologies, and civilizations
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

## Usage Examples

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

## Included Content

- **Base Game**: All original units and civilizations
- **The Conquerors**: Spanish, Aztecs, Mayans, Huns, Koreans
- **The Forgotten**: Italians, Indians, Incas, Magyars, Slavs
- **African Kingdoms**: Portuguese, Ethiopians, Malians, Berbers
- **Rise of the Rajas**: Khmer, Malay, Burmese, Vietnamese
- **Last Khans**: Bulgarians, Tatars, Cumans, Lithuanians
- **Lords of the West**: Burgundians, Sicilians
- **Dawn of the Dukes**: Poles, Bohemians
- **Dynasties of India**: Dravidians, Bengalis, Gurjaras
- **Return of Rome**: Romans (ranked mode units)
- **The Mountain Royals**: Armenians, Georgians
- **Chronicles: Three Kingdoms**: Fire Archer, Tiger Cavalry, Jian Swordsman, etc.
- **Chronicles: Battle for Greece**: Hoplite, Strategos, Hippeus, Alexander, etc.

## Requirements

- Python 3.8+
- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) - For parsing .dat files
- Age of Empires II: Definitive Edition (for the data file)

## Project Structure

```
aoe2-unit-analyzer/
├── README.md
├── requirements.txt
├── extract.py          # Main extraction script
├── explore.py          # Interactive data explorer
├── output/             # Generated JSON files
│   ├── units.json
│   ├── technologies.json
│   ├── civilizations.json
│   └── armor_classes.json
└── empires2_x2_p1.dat  # Game data (not included, copy from game)
```

## Future Plans

See [aoe2-data-project-plan.md](aoe2-data-project-plan.md) for the full roadmap:
- REST API (Cloudflare Workers)
- MCP Server for Claude integration
- Unit combat simulation (Modal)
- Army composition optimizer

## License

Code is MIT licensed. Game data extracted from Age of Empires II: Definitive Edition is subject to Microsoft's Game Content Usage Rules.

## Credits

- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) by Siege Engineers
- [Age of Empires II: Definitive Edition](https://www.ageofempires.com/games/aoeiide/) by Xbox Game Studios
