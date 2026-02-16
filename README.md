# AoE2 Unit Analyzer

A web application for analyzing Age of Empires II: Definitive Edition unit matchups. Extracts unit stats directly from the game's binary data file, computes fully-upgraded stats for all 50 civilizations, and provides interactive tools for comparing units and simulating battles.

**Live:** Deployed on Railway.

## What It Does

- **Unit Browser** (`/units`) -- Compare any unit line across all 50 civilizations with pre-computed round-robin battle scores
- **Civilization Browser** (`/civ`) -- See every unit available to a civ with full stats
- **Battle Simulator** (`/simulate`) -- Interactive 2D canvas battle visualization with tick-based combat (20 mechanics: trample, charge, bleed, dodge, etc.)
- **Matchup Advisor** (`/matchup-advisor`) -- Civ vs civ matchup analysis with army composition suggestions

## How It Works

The pipeline has 4 steps:

```
empires2_x2_p1.dat
       |
       v
 [extraction/]     python3 -m extraction.run
   dat -> JSON        8 JSON files (units, techs, civs, effects, ...)
       |
       v
 [analysis/]       python3 -m analysis.generate_reference
   JSON -> ref DB     Computes fully-upgraded stats for every unit x civ combo
       |
       v
 [analysis/]       python3 -m analysis.generate_main_db
   ref DB -> main DB  Flattens into webapp-ready unit_stats table
       |
       v
 [webapp/]         cd webapp && python3 compute_battle_scores.py
   main DB -> scores  Round-robin battle simulations for unit line rankings
```

The webapp reads the final `aoe2_units.db` and `aoe2_reference.db` databases, plus pre-computed `battle_scores.json`.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Get the Game Data File

Copy `empires2_x2_p1.dat` from your AoE2:DE installation into `extraction/`:

```bash
# macOS (Steam)
cp ~/Library/Application\ Support/Steam/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat extraction/

# Windows (Steam)
copy "C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat" extraction\
```

### Build Databases

```bash
python3 -m extraction.run               # ~10s, writes JSON to extraction/extracted_data/
python3 -m analysis.generate_reference   # ~30s, writes webapp/aoe2_reference.db
python3 -m analysis.generate_main_db     # ~2s,  writes webapp/aoe2_units.db
cd webapp && python3 compute_battle_scores.py  # ~20s, writes battle_scores.json
```

### Run

```bash
PORT=5002 python3 webapp/app.py
```

Visit `http://localhost:5002`.

## Project Structure

```
extraction/                  # Step 1: dat -> JSON
  run.py                     # Entry point
  extract_units.py           # Units, armor classes, projectiles
  extract_techs.py           # Technologies, tech ages
  extract_effects.py         # Effects, civ tech trees
  extract_constants.py       # Shared constants (armor classes, civ names)

analysis/                    # Steps 2-3: JSON -> databases
  config.py                  # Unit definitions, combat properties, civ bonuses
  unit_analyzer.py           # Stat computation (base stats + tech effects)
  combat_properties.py       # Combat property layering (defaults -> extracted -> config)
  generate_reference.py      # Builds reference DB (full audit trail)
  generate_main_db.py        # Builds main DB (flat unit_stats for webapp)

webapp/                      # Step 4 + serving
  app.py                     # Flask app + all API endpoints
  simulation.py              # Tick-based battle simulator (pure Python, ~1.3ms/sim)
  compute_battle_scores.py   # Round-robin rankings for unit lines
  templates/                 # HTML templates (7 pages)
```

## 50 Civilizations

Britons, Byzantines, Celts, Chinese, Franks, Goths, Japanese, Mongols, Persians, Saracens, Teutons, Turks, Vikings, Aztecs, Huns, Koreans, Mayans, Spanish, Incas, Italians, Magyars, Slavs, Berbers, Ethiopians, Malians, Portuguese, Burmese, Khmer, Malay, Vietnamese, Bulgarians, Cumans, Lithuanians, Tatars, Burgundians, Sicilians, Bohemians, Poles, Bengalis, Dravidians, Gurjaras, Hindustanis, Romans, Armenians, Georgians, Jurchens, Khitans, Shu, Wei, Wu

## Requirements

- Python 3.8+
- [genieutils-py](https://github.com/SiegeEngineers/genieutils-py) -- for parsing .dat files
- Flask, gunicorn (see `requirements.txt`)
- Age of Empires II: Definitive Edition (for the data file)

## License

Code is MIT licensed. Game data extracted from Age of Empires II: Definitive Edition is subject to Microsoft's Game Content Usage Rules.
