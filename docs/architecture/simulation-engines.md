# Simulation Engines

*Last verified: 2026-06-10 · game build 177723 · branch `staging`*

The project contains **three** battle-simulation implementations of the same combat model. They share a single input contract (the "combat dict") and, for the two backend engines, a common call signature, but they make different speed/realism trade-offs and serve different consumers.

| Engine | File | Model | Tick | Used by |
|---|---|---|---|---|
| Abstract tick engine | `webapp/simulation.py` | No positions; damage phases + statistical targeting | 0.1 s fixed (`DT`), max 2500 ticks (250 s) | `/api/matchup-sims`, `compute_battle_scores.py`, `.golden` regression tests |
| Position-based engine | `webapp/simulation_real.py` | Real 2D positions, movement, projectile flight | 1/30 s fixed (`DT`), max 600 game-seconds | `run_matchup_battles.py`, `rebuild_matchup_baseline.py`, `patch_resim.py`, `verify_flips.py` |
| Frontend canvas sim | `webapp/static/js/simulate.js` | Same model as the position engine, in pixels | Variable (requestAnimationFrame, capped at 0.1 s) | The interactive Battle Sim page at `/` only |

Historically the JS canvas sim came first; `webapp/simulation_real.py` is explicitly a Python port of it (see its module docstring). Where the engines load their data from is covered in [data-pipeline.md](data-pipeline.md); what the batch runners write is covered in [derived-data.md](derived-data.md).

## 1. Abstract tick engine — `webapp/simulation.py`

Entry point: `simulate_battle(unit1, unit2, resources, fixed_count=None, cost1_override=None, cost2_override=None, return_hp=False, return_ticks=False)`. Army sizes come either from `fixed_count / pop_space` per side, or from `resources // cost` (cost overridable per side). The battle runs in three phases (`_init_battle_state` → `_run_opening_volley` → tick loop → `_determine_winner`).

**Tick rate and duration.** `DT = 0.1` seconds, `MAX_TICKS = 2500`, so a battle is capped at 250 game-seconds. There is no wall-clock cap (a single sim runs in ~1–2 ms).

**Opening volley (kiting model).** Instead of simulating movement, the engine pre-computes how many free shots the longer-ranged side gets before melee contact, using a closing-time physics model: the ranged side retreats at an effective speed reduced by the fraction of each reload cycle spent in attack-delay animation, up to `RETREAT_MAX = 10` tiles; if its effective retreat speed exceeds the chaser's speed it earns extra "kite bonus" shots over `MAP_SPACE * 0.4 - RETREAT_MAX` tiles (`MAP_SPACE = 22`). The same logic applies ranged-vs-ranged using the range difference. Opening shots use focus-fire targeting and full hit mechanics (accuracy, dodge shields, splash, bleed).

**Targeting (per tick).**
- Ranged attackers use `_assign_targets_focus`: just enough attackers are grouped on each enemy to kill it, based on expected per-shot damage (main + extra projectiles weighted by extra-projectile accuracy).
- Melee attacking ranged uses `_assign_targets_melee_capped`: an *engagement ramp* — only `MELEE_ENGAGE_START = 30%` of enemies are engageable at first, growing by `MELEE_ENGAGE_STEP = 10%` every `MELEE_ENGAGE_ROUND_TICKS = 20` ticks (~2 s), with at most `MELEE_MAX_PER_TARGET = 1` attacker per target. Surplus melee units idle.
- Melee attacking melee uses `_assign_targets_spread_capped`: spread evenly with a per-target cap that ramps from 1 to `MELEE_VS_MELEE_MAX = 2` after `MELEE_VS_MELEE_RAMP_TICKS = 20` ticks. Infantry attacking cavalry (detected via armor classes 1 and 8) gets higher caps: `INF_VS_CAV_INITIAL_CAP = 2` → `INF_VS_CAV_MAX_CAP = 3`, modeling larger cavalry hitboxes.
- Melee units that switch targets pay a retarget walk delay (`RETARGET_DIST = 1.5` tiles / speed), unless the new target is already attacking them.
- Team order alternates each tick, and all damage for a tick is collected into `pending_damage` and applied atomically by `_apply_tick_damage`.

**The damage formula** (`_calc_damage`, line 215). Attacks and armors are `{armor_class_id: value}` dicts. Class 3 is pierce, class 4 is melee.

```
base_damage = attacks[3 or 4]                      # pierce if ranged attacker, else melee
target_armor = armors[3 or 4]                      # 0 if ignores_pierce/melee_armor
bonus = Σ over shared classes (≠3,4): max(0, attack[class] − armor[class])
bonus = int(bonus * (1 − bonus_damage_reduction))  # e.g. Sicilians
damage = max(1, base_damage + bonus − target_armor)
```

A unit whose only base attack class is melee (class 4) does melee damage even at range (Mameluke, Throwing Axeman) — `_does_melee_damage` decides this, and such units with range < 2 are treated as melee for kiting purposes (Steppe Lancer, Kamayuk). Damage between asymmetric forms (dismounted Konnik, transformed Jian Swordsman) is pre-computed in all four attacker/defender combinations.

**Accuracy and misses.** The primary projectile rolls `accuracy` (post-Thumb-Ring value); extra projectiles roll `base_accuracy` (Thumb Ring is primary-only). A missed primary shot has a stray chance of `min(0.5, alive_enemies * 0.05)` to hit a random enemy — unless the unit has `miss_damage_percent` (Arambai), which replaces the stray chance.

**Splash without positions.** `_splash_targets(radius)` converts a splash radius into a number of extra victims: `max(1, int(radius / UNIT_SPACING))` with `UNIT_SPACING = 0.75`. Trample additionally only fires on `TRAMPLE_HIT_CHANCE = 25%` of hits.

**Winner determination** (`_determine_winner`): elimination first; on timeout, fewer units lost wins; then higher remaining HP fraction; else draw (winner 0). Returns plain tuples — `(winner, rem1, rem2[, hp_pct1, hp_pct2[, ticks]])` — not `BattleOutcome`.

### Special abilities and their driving columns

`prepare_combat_unit()` (line 87) reads these fields from the combat dict; each is sourced from the identically-named column of `ref_units` in `webapp/aoe2_reference.db` via `combat_unit_loader.build_combat_dict_from_ref()` (JSON-suffixed columns are parsed into int-keyed dicts; one exception: `min_attack_range` is stored as column `min_range`). The full ability/param/engine declaration now lives in `analysis/ability_registry.py`, validated by `tests/test_ability_registry.py`.

| Ability | Driving columns | Example unit |
|---|---|---|
| Melee charge attack | `charge_attack_melee`, `charge_recharge_time` | Coustillier, Urumi, Centurion |
| Charge projectile | `charge_projectile_count`, `charge_projectile_attacks_json`, `charge_projectile_speed` | Bolas Rider, Fire Lancer |
| Charge slow on hit | `charge_slow_percent`, `charge_slow_duration` | Bolas Rider |
| Trample | `trample_percent`, `trample_radius`, `trample_flat_damage` | Cataphract, War Elephant |
| Siege blast splash | `is_siege_projectile`, `splash_radius` | Mangonel line |
| Splash on hit | `splash_on_hit_radius`, `splash_on_hit_fraction` | Grenadier (dat blast level 11; fraction is default-only 1.0, no producer sets it) |
| Pass-through bolts | `pass_through_percent`, `pass_through_count` | Scorpion line |
| Extra projectiles | `extra_projectiles`, `extra_projectile_attacks_json` | Chu Ko Nu, Organ Gun |
| First-attack burst | `first_attack_extra_projectiles` | Xianbei Raider (the only non-zero row in the committed DB; Kipchak is sustained `extra_projectiles`, not a first-attack burst) |
| Scattering extras | `extra_proj_scatter` | Organ Gun |
| Accuracy / miss damage | `accuracy`, `base_accuracy`, `miss_damage_percent` | Arambai (`miss_damage_percent`) |
| Dodge shield (anti-ranged) | `dodge_shield_max`, `dodge_shield_recharge` | Shrivamsha Rider |
| Bleed damage-over-time | `bleed_dps`, `bleed_duration` | Liao Dao, Tupi Curare (Urumi does not bleed — it is charge+trample) |
| Block first melee hit | `block_first_melee` | Iron Pagoda (the only carrier; Sicilians have `bonus_damage_reduction`, not this) |
| Attack stacking per kill | `attack_bonus_per_kill` (value = max cap, +1 per kill) | Jaguar Warrior, Tiger Cavalry |
| HP heal per kill | `hp_per_kill`, `hp_per_kill_max` | Tiger Cavalry |
| HP regeneration | `hp_regen` (HP/minute) | Berserk |
| Armor ignore | `ignores_pierce_armor`, `ignores_melee_armor` | (config-driven) |
| Bonus-damage resistance | `bonus_damage_reduction` | Sicilian units |
| Armor strip per hit | `armor_strip_per_hit` | Obuch |
| Melee damage reflect | `damage_reflect_percent` | Khitan Lamellar Armor units |
| Attack-speed ramp | `attack_speed_ramp`, `attack_speed_min` | Temple Guard |
| Execute (missing-HP bonus) | `execute_damage_per_step`, `execute_hp_step` | Kona |
| Nearby-ally attack aura | `attack_bonus_nearby`, `nearby_bonus_count` | Monaspa |
| Nearby-ally HP aura | `hp_nearby_percent_per_unit`, `hp_nearby_max_units` | Shu (Coiled Serpent Array) |
| Ally-death heal-over-time | `ally_death_heal`, `ally_death_heal_duration` | Guecha Warrior |
| Dismount on death | `dismount_hp/attack/armors…` (9 `dismount_*` columns) | Konnik |
| HP-threshold transform | `hp_transform_threshold`, 9 `transform_*` columns | Jian Swordsman |
| Minimum range | `min_attack_range` (≥2 ⇒ cannot fire once melee closes) | Mangonel line |
| Population sizing | `pop_space` | Elephants in `fixed_count` battles |

Two fields are parsed by `prepare_combat_unit()` but only implemented in the position engine: `hp_regen_in_combat` (Khitan Ordo Cavalry — combat-gated regen) and the `food/wood/gold_per_kill` trio (Mapuche-style kill economy), which `simulation.py` does not read at all.

## 2. Position-based engine — `webapp/simulation_real.py`

Entry point: `simulate_real_battle(...)` — same positional signature as `simulate_battle` plus `max_seconds`, `max_wallclock`, `seed`, `_legacy_tuple`. By default it returns a `BattleOutcome`; pass `_legacy_tuple=True` to get the old tuple shape (this is how `best_units.get_matchup_sims` can swap it in via `sim_func`).

**Space and time.** Coordinates are in tiles. The map is `MAP_W = 60` × `MAP_H = 20` tiles; each team spawns in a vertical line `TEAM_OFFSET_FROM_CENTER = 15` tiles from map center (15 tiles of kiting room behind each army). Fixed tick `DT = 1/30` s. Hard game-time cap `MAX_BATTLE_SECONDS = 600` and wall-clock backstop `DEFAULT_MAX_WALLCLOCK_SECONDS = 180`; on either cap the winner is decided by remaining HP% (`end_reason = "time_cap"` vs `"eliminated"`).

**Movement and collision.** Units steer toward/away from their target with neighbor-avoidance forces and velocity smoothing (`MOVE_SMOOTHING = 0.3`). A `SpatialGrid` (uniform buckets, cell size auto-tuned from max unit radius and max attack range, floor `GRID_CELL_SIZE = 3.5`) is rebuilt twice per tick and makes avoidance and the two-pass hard-collision resolution O(N) instead of O(N²). Stuck detection (`STUCK_TIMER_LIMIT = 0.8` s without progress) blacklists an unreachable target and retargets. Unit radius derives from the dat `outline_size` column: `(10 + min(outline,1)*20)/30` tiles.

**Projectiles and misses.** Ranged attacks spawn `Projectile` objects that travel at `projectile_speed` (fallback 7 tiles/s) and apply damage via an `on_hit` closure on arrival — so a shot can land after its shooter dies. The accuracy roll happens at fire time; a missed shot still flies, then lands at a random point within `MISS_SPREAD_RADIUS = 2.0` tiles of the intended impact. If any enemy's hitbox covers that landing point it is grazed for 0.5× damage (or `miss_damage_percent`× for Arambai); otherwise the miss does nothing. Siege splash uses real radii with linear falloff `1 − 0.75·(d/r)`.

**Kiting and the 60-second kite stop.** Ranged units kite away from melee targets during reload, and min-range units back out of their dead zone. After `KITE_STOP_TIME = 60` game-seconds, kiting is disabled (modeling micro failure / map edges) so fights resolve: units stand and shoot, and min-range units try `find_target_outside_dead_zone()` or go idle if surrounded. Pursuit is never disabled — only running away.

**Damage formula.** Same class-vs-class model as `simulation.py` with one deliberate difference: the base component is clamped at zero *before* bonus damage is added (`max(0, base_attack − armor)` then `max(1, base + bonus + execute_bonus)`), matching the JS sim.

**Army sizing and cost weighting.** Resource-budget battles use `weighted_cost` (food ×1.0, wood ×0.7, gold ×1.5) and the `SCALE_3K_UNIT_CAP = 30` rule: a side that would exceed 30 units is capped at 30 and the other side's count is re-matched to equal total weighted cost (`_calc_counts`).

**Ability parity.** All special abilities in the table above are implemented in `BattleUnit` (verified against `tests/test_position_sim_abilities.py`, 13 tests), including the two refinements that were historically open and are now **done**:

- *Urumi splash-charge*: trample for charge-melee units fires only on the charged strike — `perform_attack_on` gates trample on `charge_attack_melee <= 0 or charged` (line 1169). Always-on tramplers are unaffected.
- *Ranged-path charge*: `perform_attack` (line 919) fires charge projectiles for ranged units — `charge_recharge_time <= 0` means an every-attack charge that **replaces** the normal shot (Fire Archer); `> 0` fires the charge **in addition** and then recharges (Xianbei Raider, Bolas Rider).

Additions beyond the abstract engine: `hp_regen_in_combat` (regen only within `COMBAT_WINDOW_S = 5` s of attacking), `food/wood/gold_per_kill` tracked into `BattleOutcome` gained fields, `charge_attack_range` / `charge_ignores_armor` for melee-launched charge projectiles (Fire Lancer), and an out-of-combat reset for the Temple Guard attack-speed ramp. The abstract engine's `TRAMPLE_HIT_CHANCE` randomness does not exist here — trample uses real radii.

## 3. Frontend canvas sim — `webapp/static/js/simulate.js`

The Battle Sim page at `/` (legacy `/simulate` 301-redirects there; `webapp/templates/simulate.html`) loads this file with a `<script src>` tag (line 222) — it is **not** inlined in the template. It fetches both units from `GET /api/ref/combat-unit/<civ>/<slug>?age=...` (served by `app.py:api_ref_combat_unit`, which returns `build_combat_dict_from_ref()` output as JSON) and runs the battle entirely client-side in a `BattleUnit` class on a 900×600 px canvas (`TILE_SIZE = 30` ⇒ a 30×20-tile map).

**What it mirrors.** Mechanically it is the same model as `simulation_real.py` (which was ported *from* it): per-class damage with zero-clamped base, projectile flight, miss scatter within 2 tiles with 0.5×/`missDamagePercent` graze, primary-vs-extra accuracy split, kiting, avoidance + hard collision, and the full ability set (melee charge, charged-only Urumi trample, charge projectiles for both melee and ranged paths, armor strip, execute, auras, ally-death heal, transform, dodge shield, reflect, ramp — all present and verified by grep against the Python engine).

**Where it intentionally diverges.**
- Variable timestep: `requestAnimationFrame` delta capped at 0.1 s, scaled by the user's speed multiplier — not a fixed 30 Hz tick.
- 30-tile-wide map with teams spawned near the canvas edges, vs. the backend's 60-tile map anchored ±15 from center.
- No 60-second kite-stop — units kite indefinitely; battles end only by elimination (no 600 s game-time or wall-clock cap).
- Non-deterministic by design: unseeded `Math.random()` everywhere, plus random X jitter on spawn positions.
- Rendering concerns (sprites, effects, debug panel) interleaved with sim logic.

**How tests keep it honest.** `tests/test_frontend_projectile_miss.js` (run with `node tests/test_frontend_projectile_miss.js`) brace-matches and `eval`s the **live** `BattleUnit` class straight out of `simulate.js` under mocked browser globals, then asserts the accuracy/miss-graze model (7 tests): accuracy parsing, guaranteed hit/miss behavior, 0.5× default graze, Arambai full-damage graze, statistical ~50% hit rate, and `baseAccuracy` for extra projectiles. Because it extracts the shipped source rather than a copy, frontend refactors that break the contract fail CI-style. The backend mirror of the same model is `tests/test_position_sim_abilities.py`.

## 4. Who uses which engine (verified by imports)

| Consumer | Engine | Evidence |
|---|---|---|
| Interactive Battle Sim page at `/` (legacy `/simulate` 301-redirects there) | Frontend JS only | `simulate.html` line 222 script tag; `app.py` imports neither Python engine |
| `POST /api/matchup-sims` (matchup advisor "who beats whom") | Abstract (`simulate_battle`) | `app.py` → `best_units.get_matchup_sims()` called without `sim_func`; default is `simulate_battle` (`best_units.py` line 1468) |
| `webapp/compute_battle_scores.py` (battle_scores.json + role scores) | Abstract | `from simulation import prepare_combat_unit, simulate_battle` (line 21) |
| `webapp/run_matchup_battles.py` (matchup_db batch) | Position | `from simulation_real import simulate_real_battle, prepare_combat_unit` (line 31) |
| `webapp/rebuild_matchup_baseline.py` (multi-seed baseline) | Position | `from simulation_real import simulate_real_battle` (line 41) |
| `webapp/patch_resim.py`, `webapp/verify_flips.py` | Position | direct imports |
| `webapp/best_units.py` (power-unit scoring + matchup sims) | Both imported; abstract by default | lines 1087–1088; `sim_func=simulate_real_battle` is an opt-in |
| `.golden` regression (`tests/test_simulations.py`, `.golden/capture_baseline.py`) | Abstract (via `get_matchup_sims`) | seeded with `GOLDEN_SEED = 20260411` |
| `tests/test_position_sim_abilities.py` | Position | imports `BattleUnit`, `BattleSimulation` |

**`webapp/sim_version.py`** hashes exactly two files — `webapp/simulation_real.py` and `analysis/config_combat.py` — into a 16-character SHA-256 prefix. It is the row-level cache key in `matchup_db` (`matchup_battles.sim_version`): rows with a stale version get re-simulated on the next batch run. Note it does **not** hash `simulation.py` or `simulate.js`; changes to those never invalidate matchup rows.

## 5. Shared contracts

**The combat dict.** Every backend sim path is: `ref_units` row (`webapp/aoe2_reference.db`) → `combat_unit_loader.build_combat_dict_from_ref(row)` (96 keys: identity, final stats, costs + upgrade costs, `*_json` strings, all combat-property and ability columns, `outline_size` from `outline_size_x`) → `simulation.prepare_combat_unit(dict)` (73 keys: JSON parsed into int-keyed `attacks`/`armors` dicts, defaults applied, `transform`/`dismount` sub-dicts built) → either engine. The webapp's flat `unit_stats` table in `aoe2_units.db` is *not* on this path. `simulation_real.py` also defines its own `prepare_combat_unit()` — a thin normalizer that accepts both raw and prepared shapes (its `_stat_attacks` helpers handle either), used by `run_matchup_battles.py`.

**`battle_outcome.BattleOutcome`** (`webapp/battle_outcome.py`) is the rich result dataclass produced only by `simulate_real_battle`: winner, `end_reason`, `game_time_s`, per-team HP%, survivors, start counts, per-resource HP-weighted losses, per-kill resource gains, weighted `value_lost`, and cached per-unit costs. `signed_score(outcome)` collapses it to a single −100…+100 number: `±100 × (winner_hp_pct − loser_hp_pct)`, 0 on draw. `average_outcomes(list)` aggregates multi-seed runs (means for numerics, majority vote for winner with HP tiebreak) — both batch runners persist averaged outcomes.

## 6. Determinism rules

- `simulation.py` uses the **unseeded module-level `random`** (accuracy rolls, stray shots, trample chance, scatter). The project convention "simulations are deterministic — run once" holds only because callers that need reproducibility seed globally first: the golden tests call `random.seed(20260411)` before each scenario. `compute_battle_scores.py` does not seed at all, so its outputs have small run-to-run noise for inaccurate/trample units.
- `simulation_real.py` takes an explicit `seed=` parameter (`random.seed(seed)` at entry) and spawns units without RNG, so a given (units, scale, seed) triple is fully reproducible. `deterministic_seed(*parts)` builds a stable seed from civ/slug strings.
- Multi-seed sampling exists because contested matchups flip between seeds: `run_matchup_battles.py` runs seed 0 and only adds seeds 1–2 when `|signed_score| ≤ CLOSE_MATCH_THRESHOLD = 5.0`; `rebuild_matchup_baseline.py` uses a matched-seed escalating sampler (seeds 0…n, batches of 8 up to `MAX_SEEDS = 40`) until the standard error drops below `SE_TARGET = 4.0`, then derives a win/loss/tossup verdict (`BAND = 10`).
- The JS canvas sim is intentionally non-deterministic (unseeded `Math.random`, variable frame timing) — it is a visualization, not a data source.

## Update triggers

| If this changes… | …update |
|---|---|
| `simulation.py` constants (DT, caps, engage ramp) or targeting helpers | §1; rerun `compute_battle_scores.py` and regenerate `.golden/baseline.json` |
| A new special ability / `ref_units` combat column | ability table in §1, §5 key counts (96/73); port to all three engines and both ability test files |
| `simulation_real.py` or `analysis/config_combat.py` | §2; `sim_version` changes ⇒ matchup rows re-sim on next batch (note in §4) |
| `static/js/simulate.js` `BattleUnit` | §3; keep `tests/test_frontend_projectile_miss.js` passing |
| `sim_version.py` `DEFAULT_FILES` | §4 hashing note |
| `BattleOutcome` fields or `signed_score` formula | §5; also `matchup_db` schema and both batch runners |
| Seed strategy in `run_matchup_battles.py` / `rebuild_matchup_baseline.py` | §6 |
| `/api/matchup-sims` switching to `sim_func=simulate_real_battle` | §4 consumer table |
