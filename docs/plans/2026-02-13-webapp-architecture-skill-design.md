# Webapp Architecture Skill — Design

## Goal
Create a skill that helps future Claude instances understand how the AoE2 unit analyzer webapp works, where features live, and how to modify the correct places without missing related files.

## Audience
Future Claude Code instances working on this codebase.

## Pain Points Addressed
1. **Misses related files** — changes one place but doesn't update files that must stay in sync
2. **Doesn't understand data flow** — doesn't grasp how data moves from DB → app.py → template → frontend

## Approach
A+B Hybrid: architecture overview for context, then task-oriented modification recipes and sync rules.

## Skill Location
`.claude/skills/webapp-architecture/SKILL.md` (project-local)

## Skill Type
Reference skill (architecture guide + modification patterns)

## Sections

### 1. Metadata
- name: `webapp-architecture`
- description: triggering conditions for when to load (modifying webapp features, adding units, changing simulation, updating UI)

### 2. Architecture Overview (~150 words)
- Core files: app.py, simulation.py, compute_battle_scores.py, templates/
- Data flow summary: SQLite → app.py queries → JSON API → frontend JS → simulation.py
- 3 databases: aoe2_units.db (main), aoe2_reference.db (audit), app_data.db (user content)

### 3. Feature Map
Table mapping each feature to backend/frontend/data files:
- Unit Rankings, Battle Simulation, Civ Detail, Matchup Advisor, Comments, Verification, Battle Scores

### 4. Sync Rules
6 hard sync rules (breaking if missed):
- UNIT_LINES in app.py + compute_battle_scores.py
- NAME_TO_ICON across 4 templates
- UNIQUE_BUILDING in simulate.html + civ_detail.html
- ENABLED_CIVS in index.html + simulate.html + app.py
- Combat property columns across DB schema + app.py + simulation.py + template
- UNIT_LINES unique unit slugs must match DB slugs

Soft sync: battle scores stale after sim changes, ref DB vs main DB drift.

### 5. Modification Recipes
5 step-by-step recipes:
1. Add new simulation mechanic (DB → config → simulation.py → frontend)
2. Add new unit or civ (extraction → pipeline → UNIT_LINES → templates)
3. Add new API endpoint (app.py route → DB query → template fetch)
4. Modify damage calculation (simulation.py → rerun scores)
5. Change frontend UI (inline in templates → check sync rules)

### 6. Data Flow Details
- Combat unit data flow (most common): extracted_data → generate_reference → generate_main_db → app.py → API → frontend/simulation
- Config override priority: DB defaults → extracted → COMBAT_PROPERTIES → UNIQUE → CIV
- Matchup advisor flow: 4 phases, fast (1-3) + slow (4)
- Battle scores flow: offline compute → JSON cache → loaded at startup

## Estimated Size
600-800 words total.

## Testing Approach
Reference skill testing:
- Retrieval scenarios: give subagent a task, check if it finds right files
- Application scenarios: does it modify all sync-related files?
- Baseline (without skill) vs. with-skill comparison
