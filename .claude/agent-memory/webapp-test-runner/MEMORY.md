# Webapp Test Runner - Agent Memory

## Environment
- Python: `python3` (macOS, `python` not in PATH)
- Virtual env: `venv/` (has flask + numpy), `.venv/` (flask only). Use `venv/`.
- Port 5000: AirPlay Receiver. Ports 5001-5003 often occupied by prior Flask runs. Use 5010+.
- Flask start: `cd webapp && PORT=5010 python3 app.py`
- DB: `webapp/aoe2_units.db` (SQLite)

## Simulation Testing
- No direct simulation API endpoint. Backend `simulate_battle()` is used internally only.
- Frontend (`simulate.html`) runs simulation in JavaScript (BattleUnit class).
- To test simulation: import directly from `simulation.py` via Python script.
- `sqlite3.Row` does NOT support `.get()`. Must convert to `dict()` before calling `prepare_combat_unit()`.
- Missing fields to add when querying unit_stats directly: `accuracy`, `attack_bonus_nearby`, `nearby_bonus_count`, `damage_reflect_percent`, `bonus_hp_nearby`, `nearby_hp_bonus_count` (default to 0).
- Query pattern: `SELECT us.*, u.slug FROM unit_stats us JOIN units u ON us.unit_id = u.id JOIN civilizations c ON us.civ_id = c.id WHERE u.slug = ? AND u.age_id = ? AND c.name = ?`
- `unit_category` and `paired_unit_slug` are already columns in `unit_stats` table.
- `simulate_battle(unit1, unit2, resources, fixed_count=N, return_hp=True, return_ticks=True)` returns 6-tuple.

## API Endpoints (confirmed working)
- `/api/ref/combat-unit/<civ_name>/<unit_slug>?age=Imperial` - combat-ready stats from reference DB
- `/api/ref/unit-line/<slug>` - unit line ranking data (21 backend slugs, 18 frontend-visible)
- `/api/ref/unit-line/stable` - virtual stable line, 127 imperial units, 16 score types
- `/api/ref/unit-line/all_cavalry` - REMOVED (returns 404). Replaced by "stable" virtual line.
- Individual sub-lines still work: knight (54), camel (13), light_cav (48), steppe_lancer (5), elephant (6)
- Server responds at `/` with 200

## Unit Rankings Page (`/units`)
- Route: `/units` -> `webapp/templates/rankings.html` (renamed from index.html 2026-06-10), title "Unit Rankings"
- Client-side SPA: JS fetches `/api/ref/unit-line/{slug}` on click (no auto-load)
- 18 lines in frontend UNIT_LINES; 21 in backend (militia/spear/shock_infantry are sub_lines of infantry aggregates)
- Knight line imperial_slug=paladin: only Paladin-tier civs in imperial (by design)
- API response: `{line_name, building, castle: [...], imperial: [...]}`
- Stats are floats (HP, ATK, etc.) -- use int() for display
- Port 5001 can also be occupied by prior Flask runs; use 5002+ if needed

## Performance Benchmarks
- Single 30v30 simulation: ~1.4ms
- 10x runs: ~13.8ms total (~1.38ms/run)
- Simulation is fully deterministic (no random variance in 10 runs)

## Key Findings
- Britons Champion: HP=70, Atk=18, MA=4, PA=6, Speed=1.06, Melee
- Britons Arbalester: HP=40, Atk=6 (10 pierce in attacks_json), MA=3, PA=4, Range=11, Speed=0.96
- 30v30 result: Champions win decisively (30 surviving, 0.7 HP remaining total)
- Simulation is symmetric: same result regardless of team assignment
- Arbalester attack_delay=0.333 (from API), pierce attack class 3 = 10 damage

## Stable Scoring (verified 2026-02-13)
- 127 units across 20 distinct slugs, 47 civs, Imperial age only
- Score types (16): stable_power, attack_power, movement_speed_score, survivability_score, 6 atk_*, 6 surv_*
- Sub-scores (atk_*/surv_*) range -100 to +100 (battle outcome). Composites shifted to 0-100.
- Formula: stable_power = 0.6*attack + 0.2*speed + 0.2*survivability (max rounding error 0.04)
- Ranges: stable_power 22.7-70.2, attack_power 9.1-85.3, speed 0-100, survivability 6.3-71.5
- Top: Ratha (70.2), Leitis (68.9), Monaspa (67.6), Konnik (66.6). Bottom: Viking Hussar (22.7)
- Scoring DB: `webapp/aoe2_reference.db` (NOT aoe2_units.db)
- compute_battle_scores.py --roles-only: runs infantry(~6s) + archery(~9s) + stable(~4.6s) = ~20s total
- Stale .pyc files can cause errors after code changes; if you see unexpected KeyErrors, try `find webapp -name '*.pyc' -delete`

## New Civs (verified 2026-04-12)
- 53 total civs (was 50). Added: Muisca, Mapuche, Tupi.
- Muisca uniques: Guecha Warrior (HP=50, ATK=6, Castle), Temple Guard (HP=100, ATK=14, Castle)
- Mapuche uniques: Kona (HP=125, ATK=11, Castle), Bolas Rider (HP=55, ATK=5, Castle)
- Tupi uniques: Blackwood Archer (HP=20, ATK=4, Castle, ranged range=7), Ibirapema Warrior (HP=80, ATK=10)
- All three share Champi Warrior (standard, not unique). Incas also gets Champi, loses Eagle Warrior.
- Blackwood Archer: bleed_dps=2.0, bleed_duration=15.0, pass_through_count=1
- `/api/ref/civs` endpoint does NOT exist (404). Query DB directly for civ list.
- Battle scores: loaded 0 round-robin, 0 benchmark -- scores not yet computed for new civs.

## Matchup Sims API (verified 2026-02-22)
- Endpoint: `POST /api/matchup-sims` with JSON body `{civ_left, civ_right, age}`
- Response: `{left: {slug: {wins:[], highlighted:[]}}, right: {...}, name_map: {slug: displayName}}`
- Franks vs Saracens: 13 left units, 14 right units, 15 name_map entries
- Runs N*M*2 sim pairs (up to 728 for 13x14); each pair = 30v30 + 3k-resource battle
- Timing: ~2.2s for Franks vs Saracens (marginally over 2s target)
- Same-civ test: symmetric (left and right win sets identical)
- Error handling: empty JSON->400, missing fields->400, non-JSON Content-Type->415 HTML (Flask default)
- Invalid civ/age: returns 200 with empty `{left:{}, right:{}, name_map:{}}` (soft fail)
- Page: `GET /matchup-advisor` -> 200, 5.7KB HTML

## Team Analysis API (verified 2026-02-16)
- Endpoint: `/api/team-analysis?team1=...&team2=...&stage=...&tab=...`
- Stages: cavalry (3 tabs), infantry (4 tabs), ranged (4 tabs), siege (2 tabs)
- BUG FIXED: `age` column casing mismatch -- stable stored "Imperial", all others "imperial". Fixed in compute_battle_scores.py (line 1323) and app.py (line 1593: `.lower()`).
- Response shape: `{stage, tab, tab_label, available_tabs: [{key, label}], age, score_type, median, team1: {civs, above_median_units, total_delta}, team2: {...}, advantage}`
- Each unit in above_median_units: `{civ, unit_slug, score, rank, median_delta}`
- Error responses: 400 for invalid stage/tab, 404 for no scores found
- macOS `date +%s%3N` not supported; use Python `time.time()` for timing in test scripts
