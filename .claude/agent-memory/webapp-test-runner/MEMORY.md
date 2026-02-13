# Webapp Test Runner - Agent Memory

## Environment
- Python: `python3` (macOS, `python` not in PATH)
- Virtual env: `venv/` (has flask + numpy), `.venv/` (flask only). Use `venv/`.
- Port 5000: AirPlay Receiver. Use 5001-5004.
- Flask start: `cd webapp && PORT=5003 python3 app.py`
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
- Server responds at `/` with 200

## Unit Rankings Page (`/units`)
- Route: `/units` -> `webapp/templates/index.html`, title "Unit Rankings"
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
