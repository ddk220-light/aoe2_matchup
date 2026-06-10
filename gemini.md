# AoE2 Unit Analyzer - Context for Gemini

## Project Overview
This project is a web application that analyzes Age of Empires II: Definitive Edition unit matchups. It uses the game's binary data file (`empires2_x2_p1.dat`) to extract unit stats, computes fully-upgraded stats for all 50 civilizations, and provides interactive web tools for comparison, matchup advising, and battle simulation.

## Tech Stack
- **Backend:** Python 3.8+, Flask, SQLite (for pre-computed databases)
- **Frontend:** HTML, CSS, JavaScript (using Jinja2 templates via Flask)
- **Data extraction:** `genieutils-py`

## Architecture & Pipeline
The application works in four main steps:
1. **Extraction (`extraction/`):** Reads the binary `empires2_x2_p1.dat` and exports data to JSON using `genieutils-py`. Scripts: `extract_units.py`, `extract_techs.py`, `extract_effects.py`, etc.
2. **Analysis / Reference DB (`analysis/`):** Generates fully-upgraded stats for every unit x civilization combination. The `generate_reference.py` script computes stat chains and saves an audit trail to `aoe2_reference.db`.
3. **Main DB (`analysis/`):** Flattens the reference data into a lightweight `aoe2_units.db` via `generate_main_db.py` for fast querying.
4. **Webapp / Serving (`webapp/`):** The Flask application (`webapp/app.py`) serves the HTML templates and API endpoints. Includes an interactive tick-based battle simulator (`simulation.py`) and pre-computes battle scores via `compute_battle_scores.py`.

## Key Files & Directories
- `extraction/`: Code to parse the binary `.dat` file into JSON files.
- `analysis/`: Stat computation logic (`unit_analyzer.py`, `combat_properties.py`, `config.py`) that applies tech trees and stat modifications.
- `webapp/app.py`: Main Flask application. Contains all routing and API endpoints for the frontend.
- `webapp/simulation.py`: Pure Python tick-based battle simulator.
- `webapp/compute_battle_scores.py`: Precomputes round-robin battle simulations for rankings.

## Guidelines for AI Assistant (Gemini)
1. **Data Pipeline Awareness:** Data flows strictly from `extraction` -> `analysis` -> `webapp`. Modifications to base stats or logic often require rebuilding the databases.
2. **Databases:** The webapp depends on two databases: `aoe2_units.db` (fast reads, flattened) and `aoe2_reference.db` (detailed stats, tech chains). 
3. **Configuration over Hardcoding:** Data is generated procedurally from game data combined with `analysis/config.py`. Don't hardcode stats in the database; update the data pipeline or configuration instead.
4. **Testing and Running:** 
   - Rebuilding DBs: Run `python3 -m extraction.run`, `python3 -m analysis.generate_reference`, `python3 -m analysis.generate_main_db`, and `cd webapp && python3 compute_battle_scores.py`.
   - Running the webapp: `PORT=5002 python3 webapp/app.py`.
5. **Style:** Keep Python code clean, use modern Python features (the project supports 3.8+), and maintain the existing procedural and component-based project structure.
