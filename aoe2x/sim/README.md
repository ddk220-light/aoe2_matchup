# aoe2x/sim — battle-simulation engines (layer 4)

Stdlib-only. Three engines, three jobs — keep behavior-synced (golden tests
pin them; a mechanic change is incomplete until all three + `.golden/baseline.json` agree):

| Engine | File | Job |
|---|---|---|
| Abstract tick (no positions) | `simulation.py` | live `/api/matchup-sims` (via aoe2x.advisor) |
| Position-based 2D | `simulation_real.py` | ALL batch matchup data (aoe2x.batch, PyPy3) |
| Frontend canvas | `apps/website/static/js/simulate.js` | the interactive Battle Sim page |

**In:** combat dicts from `combat_unit_loader.build_combat_dict_from_ref(row)`
(a `ref_units` sqlite row from `data/golden/aoe2_reference.db`).
**Out:** `BattleOutcome` (battle_outcome.py): winner, HP%, survivors,
per-resource losses, signed_score.

INVARIANTS:
- `simulation_real.py` content is byte-hashed (with
  `aoe2x/dbgen/config_combat.py`) into `sim_version.compute_sim_version()` —
  the matchup-row cache key. NEVER edit it outside a planned full re-sim.
  (Its `from battle_outcome import …` fallback resolves via the alias in
  `__init__.py` — that's why this package aliases the module.)
- `simulation.py` is NOT hashed; its only guard is the golden baseline.
- `unit_lines.py` UNIT_LINES has a manually-synced JS copy in
  `apps/website/static/js/rankings.js` — update both.

Determinism: single sims are seed-deterministic; batch data uses 8→40
escalating multi-seed; golden tests pin `GOLDEN_SEED=20260411`.
