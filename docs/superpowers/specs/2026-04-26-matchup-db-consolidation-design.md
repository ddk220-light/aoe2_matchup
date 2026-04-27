# Matchup DB Consolidation & Resource-Aware Sim

**Date:** 2026-04-26
**Status:** Design approved — awaiting implementation plan

## Problem

The repo currently maintains three overlapping databases:

| DB | Rows | Use | State |
|---|---|---|---|
| `matchup_combos.db` | 6,874 | Old fast-sim civ-vs-civ recommendations | Dead (not read by live code) |
| `matchup_combos_real.db` | 6,189 | Real-sim civ-vs-civ recommendations | BattleOutcome cols all NULL; missing 3 civs |
| `yardstick_battles.db` | 10,908 | Real-sim ranking benchmarks | Fully populated, only consumer of new sim outcomes |

The `matchup_combos*` DBs conflate two concerns: **raw simulation outcomes** and **derived recommendations** (`combo_type`, `top_unit_slug`, `partner_slug`, `gap`, …). Recommendations live in the same rows as the sim data that produced them. Adding new ranking criteria or new advisor logic requires regenerating the entire matchup batch.

The yardstick DB has the right shape — pure 1v1 outcomes — but its scope is limited to ranking benchmarks, so the matchup advisor still depends on the stale, recommendation-coupled real DB.

## Goals

1. **One raw-data DB** (`matchup_db.db`) containing only 1v1 simulation outcomes for every (my_civ, my_unit, opp_civ, opp_unit, scale) combination in scope. No derived metadata.
2. **Downstream tables** (rankings, advisor, future tier lists) computed from the raw DB. Each derivation is its own small script with no sim coupling.
3. **Sim engine extension** to track per-resource losses, per-resource gains (from kill bonuses), and HP-weighted value lost.
4. **Runtime under 4 hours** for a full rebuild on a developer laptop, with PyPy + dedup + symmetry; near-instant on incremental re-runs.
5. **Retire** `matchup_combos.db` and `yardstick_battles.db`. Migrate `matchup_combos_real.db` data into the new schema, then delete that file too.

## Non-Goals

- **Combo battles** (top_unit + partner sims). Advisor v2 uses 1v1 raw data only; if quality drops, a separate `combo_battles` table is a follow-up project.
- **Castle Age coverage.** Imperial only, matching all current consumers.
- **Pair-level gating within included units.** All eligible pairs sim; the data is the data.
- **C/Cython sim rewrite.** PyPy gives most of the speedup with no code changes.

## Architecture

```
                        run_matchup_battles.py
                                  │
                                  ▼
                  ┌────────────────────────────────┐
                  │  matchup_db.db                  │
                  │   table: matchup_battles        │
                  │   ~130K rows after dedup        │
                  └────────────────────────────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              ▼                   ▼                    ▼
   derive_unit_rankings   derive_advisor_recs    (future consumers)
              │                   │
              ▼                   ▼
       battle_scores       advisor_recommendations
       (in derived_data.db or aoe2_reference.db)
```

The sim binary, `run_matchup_battles.py`, is the single entry point that produces raw data. Both `derive_unit_rankings.py` (replaces `derive_scores_from_yardsticks.py`) and `derive_advisor_recs.py` (replaces the embedded advisor logic in `generate_matchup_db_real.py`) read from `matchup_battles` and write to their own derived tables.

## Components

### 1. `matchup_db.db` — schema

```sql
CREATE TABLE matchup_battles (
    id INTEGER PRIMARY KEY,

    -- Identity
    my_civ TEXT NOT NULL,
    my_unit_slug TEXT NOT NULL,
    opp_civ TEXT NOT NULL,
    opp_unit_slug TEXT NOT NULL,
    scale TEXT NOT NULL,                   -- '30v30' | '3k'
    my_count INTEGER NOT NULL,
    opp_count INTEGER NOT NULL,

    -- Per-unit costs (cached for downstream consumers)
    my_cost_food REAL, my_cost_wood REAL, my_cost_gold REAL,
    opp_cost_food REAL, opp_cost_wood REAL, opp_cost_gold REAL,

    -- Battle resolution
    winner INTEGER NOT NULL,               -- 1 = my, 2 = opp, 0 = draw
    end_reason TEXT NOT NULL,              -- 'eliminated' | 'time_cap'
    game_time_s REAL NOT NULL,

    -- Team 1 (my) outcome
    team1_hp_pct REAL NOT NULL,
    team1_survivors INTEGER NOT NULL,
    team1_food_lost REAL NOT NULL,         -- HP-weighted: cost × (1 - current_hp / max_hp), summed
    team1_wood_lost REAL NOT NULL,
    team1_gold_lost REAL NOT NULL,
    team1_food_gained REAL NOT NULL,       -- from kill-bonus civ effects
    team1_wood_gained REAL NOT NULL,
    team1_gold_gained REAL NOT NULL,
    team1_value_lost REAL NOT NULL,        -- (food + wood + gold lost) - (food + wood + gold gained)

    -- Team 2 (opp) outcome — mirror
    team2_hp_pct REAL NOT NULL,
    team2_survivors INTEGER NOT NULL,
    team2_food_lost REAL NOT NULL, team2_wood_lost REAL NOT NULL, team2_gold_lost REAL NOT NULL,
    team2_food_gained REAL NOT NULL, team2_wood_gained REAL NOT NULL, team2_gold_gained REAL NOT NULL,
    team2_value_lost REAL NOT NULL,

    team1_start_count INTEGER NOT NULL,
    team2_start_count INTEGER NOT NULL,

    -- Repetition tracking
    runs_count INTEGER NOT NULL,           -- 1 or 3
    score_stddev REAL,                     -- NULL when runs_count = 1
    dedup_group TEXT NOT NULL,             -- 16-char hex of (fingerprint pair, scale)

    -- Sim version: incremental rebuild key
    sim_version TEXT NOT NULL,             -- hash of simulation_real.py + relevant config files

    UNIQUE(my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale)
);

CREATE INDEX idx_my  ON matchup_battles(my_civ, my_unit_slug);
CREATE INDEX idx_opp ON matchup_battles(opp_civ, opp_unit_slug);
CREATE INDEX idx_dedup ON matchup_battles(dedup_group);
CREATE INDEX idx_simver ON matchup_battles(sim_version);
```

### 2. Sim engine extensions in `simulation_real.py`

#### 2.1 New combat-property properties

Add to `BattleUnit.__slots__` and stat parsing:

| Property | Meaning |
|---|---|
| `food_per_kill` | Food awarded to my team when this unit kills any enemy |
| `wood_per_kill` | Wood awarded |
| `gold_per_kill` | Gold awarded (e.g. Mapuche mounted units = 3) |

These are read from `analysis/config_combat.py` `CIV_COMBAT_PROPERTIES` / `UNIQUE_COMBAT_PROPERTIES` like all other special effects.

#### 2.2 Per-team accumulators

`BattleSimulation.__init__` adds:

```python
self.team1_food_gained = 0.0
self.team1_wood_gained = 0.0
self.team1_gold_gained = 0.0
self.team2_food_gained = 0.0
self.team2_wood_gained = 0.0
self.team2_gold_gained = 0.0
```

When a unit dies, the killer's team's accumulators add the killer's `*_per_kill` values.

#### 2.3 `BattleOutcome` dataclass extension

```python
@dataclass
class BattleOutcome:
    # ... existing fields ...
    team1_food_lost: float
    team1_wood_lost: float
    team1_gold_lost: float
    team1_food_gained: float
    team1_wood_gained: float
    team1_gold_gained: float
    team1_value_lost: float
    team2_food_lost: float
    team2_wood_lost: float
    team2_gold_lost: float
    team2_food_gained: float
    team2_wood_gained: float
    team2_gold_gained: float
    team2_value_lost: float
    my_cost_food: float
    my_cost_wood: float
    my_cost_gold: float
    opp_cost_food: float
    opp_cost_wood: float
    opp_cost_gold: float
```

#### 2.4 `value_lost` computation (HP-weighted)

At end of sim, for each side:

```python
team_food_lost = sum(unit.cost_food * (1 - unit.current_hp / unit.max_hp)
                     for unit in team_units_alive_or_dead)
# Same for wood, gold
team_value_lost = (team_food_lost + team_wood_lost + team_gold_lost
                   - team_food_gained - team_wood_gained - team_gold_gained)
```

A unit at 100% HP contributes 0 lost. A dead unit contributes full cost. A survivor at 50% HP contributes 50% of cost.

`average_outcomes()` averages all the new fields elementwise.

### 3. `unit_lines.py` reclassification

Two slugs move to their correct pools:

| Unit | Current line | New line | Reason |
|---|---|---|---|
| `tarkan_huns`, `elite_tarkan_huns` | `ram` (anti-building) | `light_cav` | It's a melee cavalry unit; anti-building bonus is just bonus damage |
| `elite_fire_archer_wu` | `bombard_cannon` | `archer` | Foot archer unit; gunpowder classification was wrong |

### 4. `run_matchup_battles.py` — replaces `run_yardstick_battles.py` and `generate_matchup_db_real.py`

#### 4.1 Coverage policy

For each civ, the runner enumerates **imperial-age units in the following lines**:

- `militia`, `spear`, `shock_infantry` (infantry pool)
- `archer`, `skirmisher`, `cav_archer`, `gunpowder`, `scorpion` (ranged pool)
- `knight`, `light_cav`, `camel`, `steppe_lancer`, `elephant` (cavalry pool)

`CIV_MISSING_UNITS` is honored. Excluded entirely: ram, mangonel, trebuchet, bombard_cannon, cannon_galleon, galleon, fire, hulk, demo, xebec_berbers.

Approximate count: **515 (civ, unit) pairs**.

#### 4.2 Pairings

Cartesian product over the 515 pairs at 2 scales (`30v30`, `3k`):

```
515 × 515 × 2 = 530,450 raw slots
```

Reduced by:
- **Mirror symmetry**: `(A vs B)` and `(B vs A)` are the same sim from opposite sides; record one row per unordered pair, query both directions in the deriver. Halves work to 265K.
- **Fingerprint dedup**: identical fingerprint pairs share one sim. Empirical reduction ~2x → **~130K unique sims**.

#### 4.3 Worker pool & batching

- `multiprocessing.Pool(workers=cpu_count - 1)` (current default).
- Pre-pass in main process builds dedup groups; workers each process one group.
- Resume support: skip groups where every member already has a row with matching `sim_version`.

#### 4.4 Sim version + incremental rebuild

`sim_version` = SHA256 prefix of:
- `simulation_real.py`
- `analysis/config_combat.py`
- `analysis/config_combat_civ.py`
- `analysis/config_combat_unique.py`

Rows whose `sim_version` matches the current value are skipped on resume. Rows whose `sim_version` differs are re-simulated. This makes routine re-runs after sim tweaks fast — only invalidated groups re-run.

#### 4.5 Close-match repeats

Tightened from `|score| ≤ 10` to `|score| ≤ 5` based on Approach-2 plan. Reduces 3-seed runs without meaningfully increasing variance.

### 5. PyPy worker process

`run_matchup_battles.py` shells out to PyPy for the worker function:

- Main process (CPython): pre-pass, group dispatch, DB writes.
- Worker pool (PyPy): runs `simulation_real.simulate_real_battle` only.
- Communication: pickled `BattleOutcome` over multiprocessing pipes (works cross-runtime as long as the dataclass is importable in both).

PyPy install becomes a documented prerequisite. Falls back to CPython if `pypy3` not on PATH (with a 5–10x runtime warning).

### 6. `derive_unit_rankings.py` — replaces `derive_scores_from_yardsticks.py`

Reads `matchup_battles` and computes ranking scores using the canonical yardstick subset:

```python
YARDSTICKS = [
    ("Vikings", "champion"),
    ("Franks", "paladin"),
    ("Britons", "arbalester"),
    ("Britons", "halberdier"),
    ("Britons", "imp_elite_skirm"),
    ("Magyars", "hussar"),
]
```

For each (my_civ, my_unit), look up its rows where `(opp_civ, opp_unit) ∈ YARDSTICKS`. Compute `signed_score`, role aggregates, composites, normalize per pool. Same math as today's deriver. Writes to `battle_scores`.

### 7. `derive_advisor_recs.py` — replaces matchup-recommendation logic in `generate_matchup_db_real.py`

For each (my_civ, opp_civ) directional pair:
1. Pull all rows where `(my_civ, my_unit) ∈ my_civ_units` and `(opp_civ, opp_unit) ∈ opp_civ_units`.
2. For each candidate `my_unit`, score it across all opp_units (e.g. mean signed_score, or HP-margin-weighted score).
3. Pick top-1 and top-2 candidates → write to `advisor_recommendations` table.
4. Partner selection: pick a "trash sidekick" (cheapest unit that beats the top opp counter to my top unit) — same heuristic as today's matchup_combos.

Writes to `advisor_recommendations` table in the same DB or in `derived_data.db` (TBD: see Open Questions).

### 8. Migration plan

1. Build new schema in `matchup_db.db`.
2. Migrate yardstick rows: every yardstick row becomes a `matchup_battles` row with new fields populated to 0 (food/wood/gold lost computed from existing `team*_resources_lost` if recoverable, else 0; gained = 0).
3. Migrate matchup_combos_real raw rows: only those with non-NULL BattleOutcome (currently 0 rows) — practically a no-op.
4. Update `webapp/yardstick_db.py` → `matchup_db.py`.
5. Update yardstick deriver path → reads from `matchup_db.db`.
6. Verify rankings unchanged via `compare_sims.py` + visual diff of /units page.
7. Add resources-from-kills sim feature (new `*_per_kill` properties).
8. Add Mapuche `gold_per_kill: 3` for mounted units to `CIV_COMBAT_PROPERTIES`.
9. Add `value_lost` computation to sim.
10. Run full batch (`run_matchup_battles.py --reset`) — populates all new fields.
11. Re-derive scores; verify rankings still sane.
12. Build `derive_advisor_recs.py`; populate `advisor_recommendations`.
13. Cut over advisor API to read from new table; verify advisor still works.
14. **Delete** `matchup_combos.db`, `matchup_combos_real.db`, `yardstick_battles.db`.

Each step is independently reversible until step 14.

## Runtime budget

| Stage | Estimate |
|---|---|
| Pre-pass (build dedup groups) | < 30s |
| Full sim run, CPython, all opts | ~18 hours |
| Full sim run, PyPy, all opts | **~3.6 hours** |
| Incremental run after small sim change | seconds to minutes |
| Unit-rankings deriver | < 30s |
| Advisor deriver | < 60s |

Target: full rebuild fits an after-work overnight run; routine re-derives are seconds.

## Testing

- `tests/test_matchup_db.py` — schema, insert/upsert, dedup_group hash stability
- `tests/test_resource_per_kill.py` — sim test: Mapuche Bolas Rider kills opponent → team1_gold_gained increases by 3
- `tests/test_value_lost.py` — sim test: team that wins with 100% HP has value_lost = 0; team that loses has value_lost = full team cost
- `tests/test_unit_ranking_derive.py` — synthetic matchup_db → expected battle_scores
- `tests/test_advisor_derive.py` — synthetic matchup_db → expected advisor_recommendations
- Sanity: Lithuanian Leitis still rank-1 stable_effectiveness; Aztec Jaguar still high anti_trash; Spanish Conquistador still top of ranged.

## Resolved decisions

**1. Derived tables live in `derived_data.db`** — a new file separate from `aoe2_reference.db`. `battle_scores` and `advisor_recommendations` both move there. `aoe2_reference.db` stays purely for unit/tech reference data and never needs backing up before a derive run.

**2. PyPy is hard-required.** If `pypy3` is not on PATH at runtime, the runner exits with a clear error message and a debug pointer. No fallback. This forces the install once and avoids silent slowdowns.

**3. Migration is clean-slate.** No backfill of existing yardstick rows. The first run after schema cutover is a full PyPy batch (~3.6 hours). Old DB files are kept on disk until step 14 of the migration plan completes successfully.
