# AoE2 Unit Analyzer - Context for Gemini

## Project Overview
This project is a web application (aoe2matchup.com) that analyzes Age of Empires II: Definitive Edition unit matchups. It uses the game's binary data file (`empires2_x2_p1.dat`) to extract unit stats, computes fully-upgraded stats for all 53 civilizations, pre-simulates ~500k unit matchups, and provides web tools for battle simulation, unit rankings, matchup advising, patch tracking, and replay analysis.

**Authoritative architecture docs: `docs/architecture/README.md` (system map + single-sources-of-truth table) and `docs/architecture/runbooks.md` (when-X-changes-update-Y checklists).**

## Tech Stack
- **Backend:** Python 3.8+, Flask, SQLite (committed pre-computed databases)
- **Frontend:** Jinja2 templates + shared static assets (`webapp/static/js/*.js`, `static/css/*.css`); the interactive battle sim runs client-side in `static/js/simulate.js`
- **Data extraction:** `genieutils-py` (conda python); **batch sims:** PyPy; **replays:** `mgz` fork

## Architecture & Pipeline
1. **Extraction (`extraction/`):** Parses `empires2_x2_p1.dat` into 8 JSON files via `genieutils-py`.
2. **Reference DB (`analysis/generate_reference.py`):** Applies tech effects/civ bonuses per civ into `webapp/aoe2_reference.db` with a full audit trail. Hardcoded combat properties layer on from `analysis/config_combat.py`.
3. **Main DB (`analysis/generate_main_db.py`):** Flattens into `aoe2_units.db` (legacy — app routes read `aoe2_reference.db`).
4. **Sim data:** Batch matchup sims (`webapp/simulation_real.py`, position-based engine) → `derive_unit_rankings.py` / `derive_pool_scores.py` / `best_units.py` → `derived_data.db` / `pool_scores.db` / `civ_power_units/<build>.json`, all keyed by build number (`patches.db`).
5. **Serving (`webapp/app.py`):** 24 Flask routes + replay blueprint. Note: `compute_battle_scores.py` is retired; `battle_scores.json` was deleted (scores live in `derived_data.db`).

## Guidelines for AI Assistant (Gemini)
1. **Data Pipeline Awareness:** Data flows strictly `extraction` → `analysis` → sim batch → derive → `webapp`. Stat/logic changes usually require rebuilding databases — follow `docs/architecture/runbooks.md`.
2. **Three sim engines:** `simulation.py` (abstract, backs /api/matchup-sims), `simulation_real.py` (position-based, backs all batch matchup data, hashed into `sim_version`), `static/js/simulate.js` (interactive page). A mechanic change must touch all three.
3. **Configuration over Hardcoding:** Don't hardcode stats in databases; update `analysis/config_*.py` and regenerate.
4. **Rebuilding stats DBs:** `python -m extraction.run`, `python -m analysis.generate_reference`, `python -m analysis.generate_main_db`. Rankings need the sim-data chain (runbooks §1), not `compute_battle_scores.py`.
5. **Running the webapp:** `PORT=5002 python webapp/app.py`. Tests: `pytest`.
6. **Git:** work on `staging`; never push `main` (production auto-deploys).
