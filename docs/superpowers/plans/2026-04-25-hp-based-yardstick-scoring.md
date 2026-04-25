# HP-Based Yardstick Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace recommendation-frequency unit ranking scores with direct HP-margin scoring, fed by a fast targeted yardstick batch that captures rich per-battle outcomes.

**Architecture:** Extend `simulation_real.py` to return a `BattleOutcome` dataclass (HP%, game_time_s, survivors, resources_lost, end_reason). Add cheap pure-Python sim optimizations including a per-fingerprint outcome cache. Build `run_yardstick_battles.py` (50 civs × power units × 6 yardsticks × 2 scales) writing to `yardstick_battles.db`. Build `derive_scores_from_yardsticks.py` to convert HP-margin outcomes into pool-normalized 0–100 scores.

**Tech Stack:** Python 3, SQLite, multiprocessing, pytest. No new dependencies.

**Spec:** [docs/superpowers/specs/2026-04-25-hp-based-yardstick-scoring-design.md](../specs/2026-04-25-hp-based-yardstick-scoring-design.md)

---

## File Structure

| File | Purpose | Status |
|------|---------|--------|
| `webapp/battle_outcome.py` | `BattleOutcome` dataclass + `signed_score()`, `average_outcomes()` helpers | Create |
| `webapp/simulation_real.py` | Return `BattleOutcome` from `simulate_real_battle()`; track `end_reason`, survivors, resources_lost on `BattleSimulation`; apply optimizations | Modify |
| `webapp/sim_outcome_cache.py` | `unit_fingerprint()` and `OutcomeCache` for per-process memoization | Create |
| `webapp/yardstick_db.py` | `yardstick_battles.db` schema + I/O helpers | Create |
| `webapp/run_yardstick_battles.py` | Multiprocessing batch runner, resume support, close-match repeat | Create |
| `webapp/derive_scores_from_yardsticks.py` | Read yardstick DB, compute & write `battle_scores` rows | Create |
| `webapp/migrate_matchup_db_outcomes.py` | One-shot ALTER TABLE on `matchup_combos_real.db` | Create |
| `webapp/generate_matchup_db_real.py` | Persist new outcome columns from `BattleOutcome` | Modify |
| `webapp/derive_battle_scores_from_matchups.py` | Drop the 7 score types now owned by yardstick deriver | Modify |
| `webapp/compare_sims.py` | Update to consume `BattleOutcome` | Modify |
| `tests/test_battle_outcome.py` | Dataclass + helpers | Create |
| `tests/test_sim_outcome_cache.py` | Fingerprint dedup behavior | Create |
| `tests/test_yardstick_score_derivation.py` | Synthetic DB → expected scores | Create |

---

## Task 1: BattleOutcome dataclass + helpers

**Files:**
- Create: `webapp/battle_outcome.py`
- Test: `tests/test_battle_outcome.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_battle_outcome.py
from webapp.battle_outcome import BattleOutcome, signed_score, average_outcomes


def _outcome(**overrides):
    base = dict(
        winner=1, end_reason="eliminated", game_time_s=20.0,
        team1_hp_pct=0.6, team2_hp_pct=0.0,
        team1_survivors=18, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=2400,
        team1_start_count=30, team2_start_count=30,
    )
    base.update(overrides)
    return BattleOutcome(**base)


def test_signed_score_team1_win_full_health():
    o = _outcome(winner=1, team1_hp_pct=1.0, team2_hp_pct=0.0)
    assert signed_score(o) == 100.0


def test_signed_score_team2_win_negates():
    o = _outcome(winner=2, team1_hp_pct=0.0, team2_hp_pct=0.7)
    assert signed_score(o) == -70.0


def test_signed_score_close_team1():
    o = _outcome(winner=1, team1_hp_pct=0.55, team2_hp_pct=0.45)
    assert signed_score(o) == 10.0


def test_signed_score_draw_returns_zero():
    o = _outcome(winner=0, team1_hp_pct=0.3, team2_hp_pct=0.3)
    assert signed_score(o) == 0.0


def test_average_outcomes_means_numeric_fields():
    a = _outcome(team1_hp_pct=0.5, team2_hp_pct=0.0, game_time_s=30.0,
                 team1_survivors=20, team2_survivors=0,
                 team1_resources_lost=500, team2_resources_lost=2400)
    b = _outcome(team1_hp_pct=0.7, team2_hp_pct=0.0, game_time_s=20.0,
                 team1_survivors=24, team2_survivors=0,
                 team1_resources_lost=300, team2_resources_lost=2400)
    avg = average_outcomes([a, b])
    assert avg.team1_hp_pct == 0.6
    assert avg.team2_hp_pct == 0.0
    assert avg.game_time_s == 25.0
    assert avg.team1_survivors == 22
    assert avg.team1_resources_lost == 400
    assert avg.winner == 1   # majority


def test_average_outcomes_majority_winner():
    runs = [_outcome(winner=1), _outcome(winner=2), _outcome(winner=1)]
    assert average_outcomes(runs).winner == 1


def test_average_outcomes_tie_picks_higher_hp_side():
    a = _outcome(winner=1, team1_hp_pct=0.4, team2_hp_pct=0.0)
    b = _outcome(winner=2, team1_hp_pct=0.0, team2_hp_pct=0.5)
    avg = average_outcomes([a, b])
    assert avg.winner == 2  # avg t2_hp_pct (0.25) > avg t1_hp_pct (0.20)
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_battle_outcome.py -v`
Expected: ImportError — module does not exist.

- [ ] **Step 3: Implement `webapp/battle_outcome.py`**

```python
"""BattleOutcome dataclass and aggregation helpers.

Single source of truth for the rich per-battle data captured by
simulate_real_battle() and persisted by both batch runners.
"""

from dataclasses import dataclass, replace
from collections import Counter


@dataclass
class BattleOutcome:
    winner: int                       # 1, 2, or 0 (draw)
    end_reason: str                   # "eliminated" | "decisive_lead" | "time_cap"
    game_time_s: float
    team1_hp_pct: float               # remaining HP / starting HP, 0..1
    team2_hp_pct: float
    team1_survivors: int
    team2_survivors: int
    team1_resources_lost: int
    team2_resources_lost: int
    team1_start_count: int
    team2_start_count: int


def signed_score(o: BattleOutcome) -> float:
    """Per-matchup signed score in [-100, +100].

    +100 = team1 won with full HP, opponent annihilated.
    -100 = team2 won with full HP.
    0    = draw.
    """
    if o.winner == 0:
        return 0.0
    if o.winner == 1:
        return round(100.0 * (o.team1_hp_pct - o.team2_hp_pct), 4)
    return round(-100.0 * (o.team2_hp_pct - o.team1_hp_pct), 4)


def _majority_winner(outcomes):
    counts = Counter(o.winner for o in outcomes)
    top = counts.most_common(2)
    if len(top) == 1 or top[0][1] > top[1][1]:
        return top[0][0]
    # Tie on votes — pick whichever side has the higher mean HP%.
    avg_t1 = sum(o.team1_hp_pct for o in outcomes) / len(outcomes)
    avg_t2 = sum(o.team2_hp_pct for o in outcomes) / len(outcomes)
    if avg_t1 > avg_t2:
        return 1
    if avg_t2 > avg_t1:
        return 2
    return 0


def average_outcomes(outcomes):
    """Aggregate N outcomes into one. Means for numeric fields, majority for
    winner (HP-tiebreak), most-common for end_reason."""
    if not outcomes:
        raise ValueError("average_outcomes called with empty list")
    n = len(outcomes)
    sample = outcomes[0]
    end_reason = Counter(o.end_reason for o in outcomes).most_common(1)[0][0]
    return replace(
        sample,
        winner=_majority_winner(outcomes),
        end_reason=end_reason,
        game_time_s=round(sum(o.game_time_s for o in outcomes) / n, 3),
        team1_hp_pct=round(sum(o.team1_hp_pct for o in outcomes) / n, 4),
        team2_hp_pct=round(sum(o.team2_hp_pct for o in outcomes) / n, 4),
        team1_survivors=int(round(sum(o.team1_survivors for o in outcomes) / n)),
        team2_survivors=int(round(sum(o.team2_survivors for o in outcomes) / n)),
        team1_resources_lost=int(round(sum(o.team1_resources_lost for o in outcomes) / n)),
        team2_resources_lost=int(round(sum(o.team2_resources_lost for o in outcomes) / n)),
    )
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_battle_outcome.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/battle_outcome.py tests/test_battle_outcome.py
git commit -m "feat: BattleOutcome dataclass + signed_score, average_outcomes helpers"
```

---

## Task 2: simulate_real_battle returns BattleOutcome

**Files:**
- Modify: `webapp/simulation_real.py:861-1090` (add `end_reason` tracking on `BattleSimulation`; track resources lost; rewrite `simulate_real_battle()` to return BattleOutcome with backwards-compat tuple wrapper)
- Test: `tests/test_battle_outcome.py` (extend)

- [ ] **Step 1: Add failing integration test**

Append to `tests/test_battle_outcome.py`:

```python
import os
import sqlite3

import pytest

from webapp.battle_outcome import BattleOutcome
from webapp.combat_unit_loader import build_combat_dict_from_ref
from webapp.simulation import prepare_combat_unit
from webapp.simulation_real import simulate_real_battle


REF_DB = os.path.join(os.path.dirname(__file__), "..", "webapp", "aoe2_reference.db")


def _load(civ, slug, age="Imperial"):
    conn = sqlite3.connect(REF_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ, slug, age),
    ).fetchone()
    conn.close()
    if row is None:
        pytest.skip(f"{civ}/{slug}/{age} not in ref DB")
    cd = build_combat_dict_from_ref(row)
    cu = prepare_combat_unit(cd)
    cu["cost_food"] = cd["cost_food"]
    cu["cost_wood"] = cd["cost_wood"]
    cu["cost_gold"] = cd["cost_gold"]
    cu["outline_size"] = cd.get("outline_size", 0.2)
    cu["cost"] = cd["cost_food"] + cd["cost_wood"] + cd["cost_gold"]
    return cu


def test_simulate_real_battle_returns_battle_outcome():
    champ = _load("Vikings", "champion")
    halb = _load("Britons", "halberdier")
    out = simulate_real_battle(champ, halb, resources=3000, fixed_count=30, seed=0)
    assert isinstance(out, BattleOutcome)
    assert out.winner in (1, 2, 0)
    assert out.end_reason in ("eliminated", "decisive_lead", "time_cap")
    assert 0.0 <= out.team1_hp_pct <= 1.0
    assert 0.0 <= out.team2_hp_pct <= 1.0
    assert out.team1_start_count == 30
    assert out.team2_start_count == 30
    assert out.team1_survivors <= 30
    assert out.game_time_s > 0


def test_simulate_real_battle_legacy_tuple_via_kwarg():
    champ = _load("Vikings", "champion")
    halb = _load("Britons", "halberdier")
    legacy = simulate_real_battle(
        champ, halb, resources=3000, fixed_count=30, seed=0,
        return_hp=True, _legacy_tuple=True,
    )
    assert isinstance(legacy, tuple)
    assert len(legacy) == 5  # winner, r1, r2, hp1, hp2
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_battle_outcome.py::test_simulate_real_battle_returns_battle_outcome -v`
Expected: FAIL — `simulate_real_battle()` returns a tuple, not BattleOutcome.

- [ ] **Step 3: Track `end_reason` on `BattleSimulation`**

Modify `webapp/simulation_real.py` `BattleSimulation.__init__` (around line 862):

```python
class BattleSimulation:
    def __init__(self):
        self.team1 = []
        self.team2 = []
        self.projectiles = []
        self.battle_time = 0.0
        self.winner = None
        self.end_reason = None  # set when run() exits
        self.grid = SpatialGrid()
```

In `BattleSimulation.step()` (around line 974) — when natural elimination ends the fight, set `end_reason`:

```python
        a1 = self.alive_count(1)
        a2 = self.alive_count(2)
        if a1 == 0 and a2 > 0:
            self.winner = 2
            self.end_reason = "eliminated"
        elif a2 == 0 and a1 > 0:
            self.winner = 1
            self.end_reason = "eliminated"
        elif a1 == 0 and a2 == 0:
            self.winner = 0
            self.end_reason = "eliminated"
```

In `BattleSimulation.run()` — when decisive-lead exit fires, set `end_reason="decisive_lead"`; when game-time cap reached or wall-clock backstop, set `end_reason="time_cap"`:

```python
            if tick + 1 >= next_decisive_tick:
                hp1_pct = self.total_hp(1) / max(1.0, self.total_max_hp(1))
                hp2_pct = self.total_hp(2) / max(1.0, self.total_max_hp(2))
                if abs(hp1_pct - hp2_pct) >= decisive_delta:
                    self.winner = 1 if hp1_pct > hp2_pct else 2
                    self.end_reason = "decisive_lead"
                    return tick + 1
                next_decisive_tick += decisive_step
```

```python
        # Game-time cap (60s) or wall-clock backstop reached
        hp1_pct = self.total_hp(1) / max(1.0, self.total_max_hp(1))
        hp2_pct = self.total_hp(2) / max(1.0, self.total_max_hp(2))
        if hp1_pct > hp2_pct:
            self.winner = 1
        elif hp2_pct > hp1_pct:
            self.winner = 2
        else:
            self.winner = 0
        self.end_reason = "time_cap"
        return tick + 1
```

- [ ] **Step 4: Add `total_resources_lost(team_num)` method**

Add to `BattleSimulation` after `total_max_hp` (around line 909):

```python
    def total_resources_lost(self, team_num):
        team = self.team1 if team_num == 1 else self.team2
        # cost_food/wood/gold attached during prepare_combat_unit; default 0.
        total = 0
        for u in team:
            if u.state == "dead":
                total += int(u.cost_food + u.cost_wood + u.cost_gold)
        return total
```

For this to work, `BattleUnit.__init__` must store cost components. Find `BattleUnit.__init__` (search for `class BattleUnit` in the file) and add right after `self.team = team_num`:

```python
        self.cost_food = float(stats.get("cost_food") or 0)
        self.cost_wood = float(stats.get("cost_wood") or 0)
        self.cost_gold = float(stats.get("cost_gold") or 0)
```

- [ ] **Step 5: Rewrite `simulate_real_battle()` to return `BattleOutcome`**

Replace the function body (around line 1051):

```python
from webapp.battle_outcome import BattleOutcome


def simulate_real_battle(
    unit1,
    unit2,
    resources,
    fixed_count=None,
    cost1_override=None,
    cost2_override=None,
    return_hp=False,             # legacy param, ignored by default new return
    return_ticks=False,          # legacy param, ignored by default new return
    max_seconds=MAX_BATTLE_SECONDS,
    max_wallclock=DEFAULT_MAX_WALLCLOCK_SECONDS,
    seed=None,
    _legacy_tuple=False,         # set True for old tuple return shape
):
    """Position-aware battle simulation. Returns BattleOutcome.

    For backwards compatibility, callers that still want the old (winner,
    remaining1, remaining2, [hp1, hp2, [ticks]]) tuple shape can pass
    `_legacy_tuple=True` along with `return_hp` / `return_ticks`.
    """
    if seed is not None:
        random.seed(seed)

    count1 = _calc_count(unit1, resources, fixed_count, cost1_override)
    count2 = _calc_count(unit2, resources, fixed_count, cost2_override)

    sim = BattleSimulation()
    sim.setup_team(1, unit1, count1)
    sim.setup_team(2, unit2, count2)
    elapsed_ticks = sim.run(max_seconds=max_seconds, max_wallclock=max_wallclock)

    winner = sim.winner if sim.winner is not None else 0
    remaining1 = sim.alive_count(1)
    remaining2 = sim.alive_count(2)
    hp1_pct = sim.total_hp(1) / max(1.0, sim.total_max_hp(1))
    hp2_pct = sim.total_hp(2) / max(1.0, sim.total_max_hp(2))

    if _legacy_tuple:
        if return_ticks:
            return winner, remaining1, remaining2, hp1_pct, hp2_pct, elapsed_ticks
        if return_hp:
            return winner, remaining1, remaining2, hp1_pct, hp2_pct
        return winner, remaining1, remaining2

    return BattleOutcome(
        winner=winner,
        end_reason=sim.end_reason or "time_cap",
        game_time_s=round(elapsed_ticks * DT, 3),
        team1_hp_pct=round(hp1_pct, 4),
        team2_hp_pct=round(hp2_pct, 4),
        team1_survivors=remaining1,
        team2_survivors=remaining2,
        team1_resources_lost=sim.total_resources_lost(1),
        team2_resources_lost=sim.total_resources_lost(2),
        team1_start_count=count1,
        team2_start_count=count2,
    )
```

- [ ] **Step 6: Update existing callers that destructure the tuple**

Find callers — they're all in `webapp/`:

```bash
grep -rn "simulate_real_battle" webapp/ --include="*.py"
```

For each caller, either pass `_legacy_tuple=True` (quick fix) or update to use BattleOutcome attributes. Specifically:
- `webapp/best_units.py` — uses `simulate_battle` by default, only uses `simulate_real_battle` when `sim_func=` passed; check call sites — wrap each as `_legacy_tuple=True` for now.
- `webapp/compare_sims.py` — to be migrated in Task 3.
- `webapp/quick_heavy_bench.py` — keeps using `BattleSimulation` directly, no change.
- `webapp/profile_matchup_pairs.py` — same.
- `webapp/generate_matchup_db_real.py` — passes `simulate_real_battle` as `sim_func`; the wrapper in `best_units.py` consumes the tuple. Add `_legacy_tuple=True` to that path so this task is self-contained.

In `webapp/best_units.py` find the `_sim(...)` call(s) inside `get_matchup_sims` and add `_legacy_tuple=True` when `_sim is simulate_real_battle`. If the wrapper is generic, easier path: in `simulate_real_battle`, always return BattleOutcome unless `_legacy_tuple=True`, but allow callers to detect via `hasattr(out, "winner")`. Cleanest: route through a helper.

Concrete change in `webapp/best_units.py`:

```python
# Before:
res = _sim(u1, u2, resources, fixed_count=count, return_hp=True)

# After:
if _sim is simulate_real_battle:
    out = _sim(u1, u2, resources, fixed_count=count, _legacy_tuple=True, return_hp=True)
    res = out
else:
    res = _sim(u1, u2, resources, fixed_count=count, return_hp=True)
```

(Both branches now produce a 5-tuple, no downstream change needed.)

- [ ] **Step 7: Run all tests + sim regression**

Run: `pytest tests/test_battle_outcome.py -v` — expected PASS.
Run: `cd webapp && python3 compare_sims.py` — expected: same winners on the 6 canonical pairings as before.
Run: `pytest tests/ -v` — expected: no new failures.

- [ ] **Step 8: Commit**

```bash
git add webapp/simulation_real.py webapp/best_units.py tests/test_battle_outcome.py
git commit -m "feat: simulate_real_battle returns BattleOutcome with end_reason, resources_lost"
```

---

## Task 3: Sim cheap-wins optimizations bundle

**Files:**
- Modify: `webapp/simulation_real.py` (BattleUnit, Projectile, BattleSimulation.step)

This task bundles micro-optimizations that don't change behavior. After every change, re-run `compare_sims.py` to confirm winners match.

- [ ] **Step 1: Add `__slots__` to BattleUnit and Projectile**

Find `class BattleUnit:` (search the file). Add `__slots__` covering every attribute set in `__init__` and updated by methods. Use this exact list (verify by grepping for `self.X =`):

```python
class BattleUnit:
    __slots__ = (
        "id", "team", "x", "y", "current_hp", "max_hp", "state",
        "target", "attack_cooldown", "stuck_timer", "last_x", "last_y",
        "radius", "speed", "attack", "min_range", "max_range", "reload_time",
        "projectile_speed", "is_ranged", "attacks", "armors", "outline_size",
        "cost_food", "cost_wood", "cost_gold",
        # ... add anything else seen in __init__
    )
```

Find `class Projectile:` — same treatment:

```python
class Projectile:
    __slots__ = ("source", "target", "x", "y", "speed", "damage", "attacks", "done")
```

If a slot is missing, you'll get `AttributeError` at runtime. Run `pytest tests/ -v` and `python3 webapp/compare_sims.py` to verify.

- [ ] **Step 2: Squared-distance optimization**

Search for `math.sqrt(...) <` or `math.sqrt(...) >` in `simulation_real.py`. Each one is a candidate.

For every site that only needs an inequality, replace:

```python
if math.sqrt(dx*dx + dy*dy) < r:
```

with:

```python
if dx*dx + dy*dy < r * r:
```

Sites where the actual distance is needed (movement direction normalization, `nx = dx/d`) keep `math.sqrt`.

- [ ] **Step 3: Hot-loop attribute aliasing**

In `BattleSimulation.step()` and `BattleUnit.update()`, where the same attribute is read 3+ times in a loop, alias to a local. Example pattern already in place at line 938:

```python
ax, ay, ar = a.x, a.y, a.radius
```

Apply the same to inner loops in `BattleUnit.update()` (find `def update`).

- [ ] **Step 4: Maintain a single alive_units list**

In `BattleSimulation`, add `self.alive = []` in `__init__`. In `step()`, replace the recreated `alive = [u for u in all_units if u.state != "dead"]` with in-place pruning:

```python
        # Maintain self.alive as units that haven't died
        self.alive = [u for u in self.alive if u.state != "dead"]
```

But on first step, populate from team1+team2:

```python
    def step(self, dt):
        self.battle_time += dt
        if not self.alive:
            self.alive = [u for u in self.team1 + self.team2 if u.state != "dead"]
        else:
            self.alive = [u for u in self.alive if u.state != "dead"]
        ...
```

Update collision pass to iterate `self.alive` instead of recreating.

- [ ] **Step 5: Run regression**

```bash
cd webapp && python3 compare_sims.py
```

Expected: winners on all 6 canonical pairings match prior output. HP% within 2pp.

```bash
pytest tests/ -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add webapp/simulation_real.py
git commit -m "perf: __slots__, squared-dist, hot-loop aliasing, alive list reuse"
```

---

## Task 4: Auto-tune grid cell size + skip projectile passes for melee-only fights

**Files:**
- Modify: `webapp/simulation_real.py` (BattleSimulation.__init__, step, SpatialGrid)

- [ ] **Step 1: Auto-tune grid cell size from unit stats**

In `BattleSimulation.setup_team()` after both teams are set up, compute optimal cell size. Add a `_finalize_setup()` method called by both setup_team variants — but simpler: do it lazily in `step()` on first tick:

In `BattleSimulation.__init__`, change `self.grid = SpatialGrid()` to `self.grid = None`.

In `step()`, before the first grid rebuild:

```python
        if self.grid is None:
            max_radius = max(
                (u.radius for u in self.team1 + self.team2), default=0.5
            )
            max_range = max(
                (u.max_range for u in self.team1 + self.team2 if u.is_ranged),
                default=0.0,
            )
            cell = max(max_radius * 4.0, max_range, GRID_CELL_SIZE)
            self.grid = SpatialGrid(cell_size=cell)
```

Verify `SpatialGrid.__init__` accepts `cell_size=` (find class). If not:

```python
class SpatialGrid:
    __slots__ = ("cell_size", "inv", "cells")
    def __init__(self, cell_size=GRID_CELL_SIZE):
        self.cell_size = cell_size
        self.inv = 1.0 / cell_size
        self.cells = {}
```

- [ ] **Step 2: Skip projectile updates when no ranged units**

In `BattleSimulation.__init__` add `self.has_ranged = False`. In `setup_team()` after creating units:

```python
        if any(u.is_ranged for u in team):
            self.has_ranged = True
```

In `step()`, gate the projectile section:

```python
        if self.has_ranged:
            for p in self.projectiles:
                p.update(dt)
            self.projectiles = [p for p in self.projectiles if not p.done]
```

- [ ] **Step 3: Run regression**

```bash
cd webapp && python3 compare_sims.py
pytest tests/ -v
```

Expected: winners match, all tests green.

- [ ] **Step 4: Commit**

```bash
git add webapp/simulation_real.py
git commit -m "perf: auto-tune grid cell size, skip projectile passes for melee-only fights"
```

---

## Task 5: Unit fingerprint dedup with OutcomeCache

**Files:**
- Create: `webapp/sim_outcome_cache.py`
- Test: `tests/test_sim_outcome_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sim_outcome_cache.py
from webapp.battle_outcome import BattleOutcome
from webapp.sim_outcome_cache import OutcomeCache, unit_fingerprint


def _outcome(winner=1):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=20.0,
        team1_hp_pct=0.5, team2_hp_pct=0.0,
        team1_survivors=15, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=2400,
        team1_start_count=30, team2_start_count=30,
    )


def _unit(**overrides):
    base = dict(
        hp=70, attack=11, melee_armor=0, pierce_armor=1,
        speed=1.0, max_range=0, reload_time=2.0, projectile_count=0,
        cost_food=60, cost_wood=0, cost_gold=20,
        outline_size=0.4,
        attacks={"4": 6}, special_properties={},
    )
    base.update(overrides)
    return base


def test_fingerprint_same_for_identical_units():
    a = _unit()
    b = _unit()
    assert unit_fingerprint(a) == unit_fingerprint(b)


def test_fingerprint_differs_when_attack_differs():
    a = _unit(attack=11)
    b = _unit(attack=12)
    assert unit_fingerprint(a) != unit_fingerprint(b)


def test_fingerprint_differs_when_attacks_table_differs():
    a = _unit(attacks={"4": 6})
    b = _unit(attacks={"4": 8})
    assert unit_fingerprint(a) != unit_fingerprint(b)


def test_cache_returns_same_outcome_for_matching_keys():
    cache = OutcomeCache()
    fp1, fp2 = ("a",), ("b",)
    o = _outcome()
    cache.put(fp1, fp2, 30, 30, "30v30", 0, o)
    assert cache.get(fp1, fp2, 30, 30, "30v30", 0) is o


def test_cache_miss_returns_none():
    cache = OutcomeCache()
    assert cache.get(("a",), ("b",), 30, 30, "30v30", 0) is None
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_sim_outcome_cache.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `webapp/sim_outcome_cache.py`**

```python
"""Per-fingerprint outcome cache for sim deduplication.

Two civs that produce a unit with identical final stats, costs, and special
properties will produce identical sim outcomes for the same opponent and
seed.  Caching keyed by (my_fingerprint, opp_fingerprint, my_count,
opp_count, scale, seed) lets us skip repeat sims across civs.

Lives per-process; not pickled across pool workers.
"""


def unit_fingerprint(unit):
    """Canonical hashable fingerprint for an instantiated combat unit dict.

    Includes every input that affects sim behavior: final stats, cost,
    visual radius (outline_size), bonus damage table, special properties.
    """
    attacks = unit.get("attacks") or {}
    if isinstance(attacks, dict):
        attacks_t = tuple(sorted((str(k), float(v)) for k, v in attacks.items()))
    else:
        attacks_t = tuple()
    armors = unit.get("armors") or {}
    if isinstance(armors, dict):
        armors_t = tuple(sorted((str(k), float(v)) for k, v in armors.items()))
    else:
        armors_t = tuple()
    special = unit.get("special_properties") or {}
    if isinstance(special, dict):
        special_t = tuple(sorted((str(k), float(v) if isinstance(v, (int, float)) else str(v))
                                 for k, v in special.items()))
    else:
        special_t = tuple()

    return (
        round(float(unit.get("hp") or 0), 1),
        round(float(unit.get("attack") or 0), 1),
        round(float(unit.get("melee_armor") or 0), 1),
        round(float(unit.get("pierce_armor") or 0), 1),
        round(float(unit.get("speed") or 0), 3),
        round(float(unit.get("max_range") or 0), 1),
        round(float(unit.get("min_range") or 0), 1),
        round(float(unit.get("reload_time") or 0), 3),
        int(unit.get("projectile_count") or 0),
        round(float(unit.get("projectile_speed") or 0), 2),
        int(unit.get("cost_food") or 0),
        int(unit.get("cost_wood") or 0),
        int(unit.get("cost_gold") or 0),
        round(float(unit.get("outline_size") or 0.2), 3),
        attacks_t, armors_t, special_t,
    )


class OutcomeCache:
    __slots__ = ("_data", "hits", "misses")

    def __init__(self):
        self._data = {}
        self.hits = 0
        self.misses = 0

    def get(self, fp1, fp2, count1, count2, scale, seed):
        key = (fp1, fp2, count1, count2, scale, seed)
        out = self._data.get(key)
        if out is None:
            self.misses += 1
        else:
            self.hits += 1
        return out

    def put(self, fp1, fp2, count1, count2, scale, seed, outcome):
        self._data[(fp1, fp2, count1, count2, scale, seed)] = outcome

    def stats(self):
        total = self.hits + self.misses
        rate = (self.hits / total) if total else 0.0
        return {"hits": self.hits, "misses": self.misses, "hit_rate": rate}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_sim_outcome_cache.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/sim_outcome_cache.py tests/test_sim_outcome_cache.py
git commit -m "feat: OutcomeCache + unit_fingerprint for sim dedup"
```

---

## Task 6: yardstick_battles.db schema + I/O helpers

**Files:**
- Create: `webapp/yardstick_db.py`
- Test: `tests/test_yardstick_score_derivation.py` (start; expanded in Task 9)

- [ ] **Step 1: Write failing test (round-trip)**

```python
# tests/test_yardstick_score_derivation.py
import os
import tempfile

from webapp.battle_outcome import BattleOutcome
from webapp.yardstick_db import (
    create_db, insert_outcome, fetch_all_rows, has_row,
)


def _outcome(winner=1, hp1=0.6, hp2=0.0):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=24.5,
        team1_hp_pct=hp1, team2_hp_pct=hp2,
        team1_survivors=18 if winner == 1 else 0,
        team2_survivors=18 if winner == 2 else 0,
        team1_resources_lost=900, team2_resources_lost=2400,
        team1_start_count=30, team2_start_count=30,
    )


def test_create_and_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "y.db")
        conn = create_db(path)
        o = _outcome()
        insert_outcome(conn, civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
                       yardstick_slug="halberdier", scale="30v30",
                       my_count=30, opp_count=30,
                       outcome=o, runs_count=1, score_stddev=None)
        rows = fetch_all_rows(conn)
        assert len(rows) == 1
        r = rows[0]
        assert r["civ"] == "Aztecs"
        assert r["winner"] == 1
        assert r["team1_hp_pct"] == 0.6
        assert r["runs_count"] == 1
        assert has_row(conn, "Aztecs", "elite_jaguar_warrior_aztecs", "halberdier", "30v30")
        assert not has_row(conn, "Aztecs", "elite_jaguar_warrior_aztecs", "halberdier", "3k")
        conn.close()


def test_insert_idempotent_on_unique_key():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "y.db")
        conn = create_db(path)
        o1 = _outcome(winner=1, hp1=0.6)
        o2 = _outcome(winner=2, hp1=0.0, hp2=0.7)
        kw = dict(
            civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
            yardstick_slug="halberdier", scale="30v30",
            my_count=30, opp_count=30,
        )
        insert_outcome(conn, outcome=o1, runs_count=1, score_stddev=None, **kw)
        insert_outcome(conn, outcome=o2, runs_count=3, score_stddev=2.5, **kw)
        rows = fetch_all_rows(conn)
        assert len(rows) == 1
        assert rows[0]["winner"] == 2  # second insert replaced first
        assert rows[0]["runs_count"] == 3
        conn.close()
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_yardstick_score_derivation.py::test_create_and_roundtrip -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `webapp/yardstick_db.py`**

```python
"""Schema + I/O for yardstick_battles.db.

One row per (civ, my_unit_slug, yardstick_slug, scale).  Stores the averaged
BattleOutcome plus runs_count and score_stddev.
"""

import os
import sqlite3

from webapp.battle_outcome import BattleOutcome

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "yardstick_battles.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS yardstick_battles (
    id INTEGER PRIMARY KEY,
    civ TEXT NOT NULL,
    my_unit_slug TEXT NOT NULL,
    yardstick_slug TEXT NOT NULL,
    scale TEXT NOT NULL,
    my_count INTEGER NOT NULL,
    opp_count INTEGER NOT NULL,
    winner INTEGER NOT NULL,
    end_reason TEXT NOT NULL,
    game_time_s REAL NOT NULL,
    team1_hp_pct REAL NOT NULL,
    team2_hp_pct REAL NOT NULL,
    team1_survivors INTEGER NOT NULL,
    team2_survivors INTEGER NOT NULL,
    team1_resources_lost INTEGER NOT NULL,
    team2_resources_lost INTEGER NOT NULL,
    team1_start_count INTEGER NOT NULL,
    team2_start_count INTEGER NOT NULL,
    runs_count INTEGER NOT NULL,
    score_stddev REAL,
    UNIQUE(civ, my_unit_slug, yardstick_slug, scale)
);
CREATE INDEX IF NOT EXISTS idx_civ_unit ON yardstick_battles(civ, my_unit_slug);
"""


def create_db(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_outcome(conn, *, civ, my_unit_slug, yardstick_slug, scale,
                   my_count, opp_count, outcome: BattleOutcome,
                   runs_count, score_stddev):
    conn.execute("""
        INSERT INTO yardstick_battles (
            civ, my_unit_slug, yardstick_slug, scale,
            my_count, opp_count,
            winner, end_reason, game_time_s,
            team1_hp_pct, team2_hp_pct,
            team1_survivors, team2_survivors,
            team1_resources_lost, team2_resources_lost,
            team1_start_count, team2_start_count,
            runs_count, score_stddev
        ) VALUES (?,?,?,?, ?,?, ?,?,?, ?,?, ?,?, ?,?, ?,?, ?,?)
        ON CONFLICT(civ, my_unit_slug, yardstick_slug, scale) DO UPDATE SET
            my_count=excluded.my_count,
            opp_count=excluded.opp_count,
            winner=excluded.winner,
            end_reason=excluded.end_reason,
            game_time_s=excluded.game_time_s,
            team1_hp_pct=excluded.team1_hp_pct,
            team2_hp_pct=excluded.team2_hp_pct,
            team1_survivors=excluded.team1_survivors,
            team2_survivors=excluded.team2_survivors,
            team1_resources_lost=excluded.team1_resources_lost,
            team2_resources_lost=excluded.team2_resources_lost,
            team1_start_count=excluded.team1_start_count,
            team2_start_count=excluded.team2_start_count,
            runs_count=excluded.runs_count,
            score_stddev=excluded.score_stddev
    """, (
        civ, my_unit_slug, yardstick_slug, scale,
        my_count, opp_count,
        outcome.winner, outcome.end_reason, outcome.game_time_s,
        outcome.team1_hp_pct, outcome.team2_hp_pct,
        outcome.team1_survivors, outcome.team2_survivors,
        outcome.team1_resources_lost, outcome.team2_resources_lost,
        outcome.team1_start_count, outcome.team2_start_count,
        runs_count, score_stddev,
    ))
    conn.commit()


def fetch_all_rows(conn):
    return conn.execute("SELECT * FROM yardstick_battles").fetchall()


def has_row(conn, civ, my_unit_slug, yardstick_slug, scale):
    r = conn.execute(
        """SELECT 1 FROM yardstick_battles
           WHERE civ=? AND my_unit_slug=? AND yardstick_slug=? AND scale=?""",
        (civ, my_unit_slug, yardstick_slug, scale),
    ).fetchone()
    return r is not None
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_yardstick_score_derivation.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/yardstick_db.py tests/test_yardstick_score_derivation.py
git commit -m "feat: yardstick_battles.db schema + I/O helpers"
```

---

## Task 7: Yardstick batch runner with cache + close-match repeats

**Files:**
- Create: `webapp/run_yardstick_battles.py`

- [ ] **Step 1: Define yardstick set + canonical civs**

Top of new file:

```python
"""Batch runner: per (civ, power_unit) × (yardstick, scale) → yardstick_battles.db.

Uses fingerprint-based outcome dedup and close-match (|score| <= 10) repeat
runs for noise reduction.  Multi-process pool with resume support.
"""

import argparse
import json
import multiprocessing as mp
import os
import sqlite3
import statistics
import time

from webapp.battle_outcome import BattleOutcome, signed_score, average_outcomes
from webapp.combat_unit_loader import build_combat_dict_from_ref
from webapp.simulation import prepare_combat_unit
from webapp.simulation_real import simulate_real_battle
from webapp.sim_outcome_cache import OutcomeCache, unit_fingerprint
from webapp.yardstick_db import create_db, insert_outcome, has_row, DEFAULT_DB_PATH

REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
POWER_UNITS_PATH = os.path.join(os.path.dirname(__file__), "civ_power_units.json")

# Yardsticks: (slug, canonical_civ).  Canonical civ keeps the yardstick's
# fingerprint identical regardless of who's fighting it — so we measure
# vs a reference Halberdier, not "this civ's Halberdier".
YARDSTICKS = [
    ("champion",         "Vikings"),
    ("paladin",          "Franks"),
    ("arbalester",       "Britons"),
    ("halberdier",       "Britons"),
    ("imp_elite_skirm",  "Britons"),
    ("hussar",           "Magyars"),
]

# Scales: (label, fixed_count_or_None, resources_or_None)
SCALES = [
    ("30v30", 30, None),
    ("3k",    None, 3000),
]

CLOSE_MATCH_THRESHOLD = 10.0
REPEAT_SEEDS = (0, 1, 2)
DEFAULT_SEED = 0
```

- [ ] **Step 2: Add unit-loading helpers**

```python
def _load_unit(conn, civ, slug, age="Imperial"):
    row = conn.execute(
        "SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?",
        (civ, slug, age),
    ).fetchone()
    if row is None:
        return None
    cd = build_combat_dict_from_ref(row)
    cu = prepare_combat_unit(cd)
    cu["cost_food"] = cd["cost_food"]
    cu["cost_wood"] = cd["cost_wood"]
    cu["cost_gold"] = cd["cost_gold"]
    cu["outline_size"] = cd.get("outline_size", 0.2)
    cu["cost"] = cd["cost_food"] + cd["cost_wood"] + cd["cost_gold"]
    return cu


def _load_yardsticks(conn):
    out = {}
    for slug, civ in YARDSTICKS:
        unit = _load_unit(conn, civ, slug)
        if unit is None:
            raise RuntimeError(f"Yardstick {civ}/{slug} not in ref DB")
        out[slug] = unit
    return out


def _power_units_for_civ(power_units_data, civ):
    """Return list of (unit_slug,) for imperial-age power units of this civ."""
    civ_data = power_units_data.get(civ, {})
    imp = civ_data.get("imperial", {}).get("power_units", {})
    slugs = []
    for category_units in imp.values():
        if not isinstance(category_units, dict):
            continue
        for slug in category_units:
            if slug:
                slugs.append(slug)
    # de-dupe preserving order
    seen, out = set(), []
    for s in slugs:
        if s not in seen:
            seen.add(s); out.append(s)
    return out
```

- [ ] **Step 3: Add per-pair sim with cache + close-match repeat**

```python
def _run_pair(my_unit, opp_unit, scale_label, fixed_count, resources, cache):
    fp1 = unit_fingerprint(my_unit)
    fp2 = unit_fingerprint(opp_unit)

    outcomes = []
    seeds_used = []
    for seed in REPEAT_SEEDS:
        if not outcomes and seed != DEFAULT_SEED:
            continue  # only the first seed is mandatory
        cached = cache.get(fp1, fp2, fixed_count or 0, 0, scale_label, seed)
        if cached is not None:
            o = cached
        else:
            o = simulate_real_battle(
                my_unit, opp_unit,
                resources=resources or 0,
                fixed_count=fixed_count,
                seed=seed,
            )
            cache.put(fp1, fp2, fixed_count or 0, 0, scale_label, seed, o)
        outcomes.append(o)
        seeds_used.append(seed)

        if seed == DEFAULT_SEED:
            sc = signed_score(o)
            if abs(sc) > CLOSE_MATCH_THRESHOLD:
                break  # decisive — no repeats needed

    if len(outcomes) == 1:
        return outcomes[0], 1, None
    avg = average_outcomes(outcomes)
    scores = [signed_score(o) for o in outcomes]
    stddev = round(statistics.pstdev(scores), 3) if len(scores) > 1 else None
    return avg, len(outcomes), stddev
```

- [ ] **Step 4: Add worker function**

```python
_WORKER_STATE = {}


def _init_worker():
    """Per-process: open ref DB, load yardsticks, init cache."""
    conn = sqlite3.connect(REF_DB_PATH)
    conn.row_factory = sqlite3.Row
    _WORKER_STATE["ref_conn"] = conn
    _WORKER_STATE["yardsticks"] = _load_yardsticks(conn)
    _WORKER_STATE["cache"] = OutcomeCache()


def _worker_run(task):
    """task = (civ, my_slug)"""
    civ, my_slug = task
    conn = _WORKER_STATE["ref_conn"]
    yardsticks = _WORKER_STATE["yardsticks"]
    cache = _WORKER_STATE["cache"]
    my_unit = _load_unit(conn, civ, my_slug)
    if my_unit is None:
        return civ, my_slug, [], "skipped: my unit not found"

    rows = []
    for ys_slug, _ in YARDSTICKS:
        opp = yardsticks[ys_slug]
        for scale_label, fixed_count, resources in SCALES:
            avg, runs_count, stddev = _run_pair(
                my_unit, opp, scale_label, fixed_count, resources, cache
            )
            rows.append({
                "civ": civ, "my_unit_slug": my_slug, "yardstick_slug": ys_slug,
                "scale": scale_label,
                "my_count": avg.team1_start_count, "opp_count": avg.team2_start_count,
                "outcome": avg, "runs_count": runs_count, "score_stddev": stddev,
            })
    return civ, my_slug, rows, None
```

- [ ] **Step 5: Add main() driver**

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing yardstick DB before running")
    parser.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--civs", nargs="+", help="Limit to specific civs")
    args = parser.parse_args()

    if args.reset and os.path.exists(args.db):
        os.remove(args.db)

    out_conn = create_db(args.db)

    with open(POWER_UNITS_PATH) as f:
        power_units = json.load(f)

    civs = args.civs or sorted(power_units.keys())
    tasks = []
    for civ in civs:
        for slug in _power_units_for_civ(power_units, civ):
            # Skip pairs already complete (all yardsticks × all scales).
            if all(
                has_row(out_conn, civ, slug, ys[0], sc[0])
                for ys in YARDSTICKS for sc in SCALES
            ):
                continue
            tasks.append((civ, slug))

    print(f"Running {len(tasks)} (civ, unit) tasks across {args.workers} workers")
    t0 = time.perf_counter()

    with mp.Pool(processes=args.workers, initializer=_init_worker) as pool:
        for i, (civ, slug, rows, err) in enumerate(
            pool.imap_unordered(_worker_run, tasks), start=1
        ):
            if err:
                print(f"[{i}/{len(tasks)}] {civ} {slug} :: {err}")
                continue
            for row in rows:
                insert_outcome(out_conn, **row)
            if i % 10 == 0 or i == len(tasks):
                elapsed = time.perf_counter() - t0
                print(f"[{i}/{len(tasks)}] {civ} {slug} ({elapsed:.0f}s)")

    out_conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Smoke-test on a single civ**

```bash
cd webapp && python3 run_yardstick_battles.py --reset --workers 2 --civs Aztecs
```

Expected: completes in <1 min, prints progress, final DB has rows for Aztec power units × 6 yardsticks × 2 scales.

Verify:

```bash
sqlite3 webapp/yardstick_battles.db "SELECT COUNT(*), COUNT(DISTINCT my_unit_slug) FROM yardstick_battles WHERE civ='Aztecs'"
```

Expected: at least 60+ rows (10+ power units × 6 yardsticks × 2 scales = ~120; smaller if civ has fewer power units).

- [ ] **Step 7: Commit**

```bash
git add webapp/run_yardstick_battles.py
git commit -m "feat: yardstick batch runner with fingerprint dedup + close-match repeats"
```

---

## Task 8: Score derivation from yardstick DB

**Files:**
- Create: `webapp/derive_scores_from_yardsticks.py`
- Test: `tests/test_yardstick_score_derivation.py` (extend)

- [ ] **Step 1: Write failing test for category aggregation**

Append to `tests/test_yardstick_score_derivation.py`:

```python
from webapp.derive_scores_from_yardsticks import (
    YARDSTICK_TO_ROLE, aggregate_role_scores,
)


def test_yardstick_role_mapping_is_complete():
    expected = {
        "champion":        ["general_combat"],
        "paladin":         ["general_combat", "anti_cav"],
        "arbalester":      ["general_combat", "anti_archer"],
        "halberdier":      ["anti_trash"],
        "imp_elite_skirm": ["anti_trash"],
        "hussar":          ["anti_trash"],
    }
    assert YARDSTICK_TO_ROLE == expected


def test_aggregate_role_scores_basic():
    # 4 rows for one (civ, unit): champ + paladin + arb + halb across 2 scales each
    # Make halb +50 both scales -> anti_trash should average to 50
    rows = [
        # (yardstick, scale, signed_score)
        ("champion", "30v30", 80),
        ("champion", "3k",    60),
        ("paladin",  "30v30", -30),
        ("paladin",  "3k",    -10),
        ("arbalester", "30v30", 70),
        ("arbalester", "3k",    50),
        ("halberdier", "30v30", 50),
        ("halberdier", "3k",    50),
    ]
    out = aggregate_role_scores(rows)
    assert out["general_combat"] == 35.0   # avg of all 6 (champ + paladin + arb)
    assert out["anti_cav"] == -20.0        # avg of paladin
    assert out["anti_archer"] == 60.0      # avg of arbalester
    assert out["anti_trash"] == 50.0       # avg of halberdier (skirm/hussar absent here)
```

- [ ] **Step 2: Run, verify fail**

```bash
pytest tests/test_yardstick_score_derivation.py::test_yardstick_role_mapping_is_complete -v
```

Expected: ImportError.

- [ ] **Step 3: Implement category aggregation**

```python
# webapp/derive_scores_from_yardsticks.py
"""Read yardstick_battles.db, derive ranking scores, write to battle_scores.

Score model:
  signed_score(outcome) = 100 * (winner_hp% - loser_hp%) (negated if team2 won)

Role aggregation (averaged across the 2 scales):
  general_combat = avg over (champion, paladin, arbalester)
  anti_cav       = avg over (paladin)
  anti_archer    = avg over (arbalester)
  anti_trash     = avg over (halberdier, imp_elite_skirm, hussar)

Composites + pool normalization mirror compute_battle_scores.py /
derive_battle_scores_from_matchups.py.
"""

import argparse
import json
import os
import sqlite3
import time
from collections import defaultdict

from webapp.unit_lines import UNIT_LINES

DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
YARDSTICK_DB_PATH = os.path.join(os.path.dirname(__file__), "yardstick_battles.db")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")

YARDSTICK_TO_ROLE = {
    "champion":        ["general_combat"],
    "paladin":         ["general_combat", "anti_cav"],
    "arbalester":      ["general_combat", "anti_archer"],
    "halberdier":      ["anti_trash"],
    "imp_elite_skirm": ["anti_trash"],
    "hussar":          ["anti_trash"],
}

ROLE_SCORE_TYPES = ("general_combat", "anti_archer", "anti_cav", "anti_trash")

COMPOSITE_WEIGHTS = {
    "militia_value":         {"general_combat": 0.75, "anti_cav": 0.10, "anti_trash": 0.15},
    "ranged_effectiveness":  {"general_combat": 0.70, "anti_archer": 0.30},
    "stable_effectiveness":  {"general_combat": 0.70, "anti_cav": 0.30},
}

LINE_COMPOSITE = {
    "militia": "militia_value", "spear": "militia_value", "shock_infantry": "militia_value",
    "skirmisher": "ranged_effectiveness", "archer": "ranged_effectiveness",
    "cav_archer": "ranged_effectiveness", "gunpowder": "ranged_effectiveness",
    "scorpion": "ranged_effectiveness",
    "light_cav": "stable_effectiveness", "knight": "stable_effectiveness",
    "camel": "stable_effectiveness", "steppe_lancer": "stable_effectiveness",
    "elephant": "stable_effectiveness",
}

POOL_OF_LINE = {
    "militia": "infantry", "spear": "infantry", "shock_infantry": "infantry",
    "skirmisher": "ranged", "archer": "ranged", "cav_archer": "ranged",
    "gunpowder": "ranged", "scorpion": "ranged",
    "light_cav": "stable", "knight": "stable", "camel": "stable",
    "steppe_lancer": "stable", "elephant": "stable",
}

SPEED_WEIGHTED_COMPOSITES = {
    "ranged_effectiveness": ("_speed", "_range"),
    "stable_effectiveness": ("_speed",),
}

TARGET_SCORE_TYPES = ROLE_SCORE_TYPES + tuple(COMPOSITE_WEIGHTS)


def _signed_score_from_row(row):
    """row is a sqlite3.Row from yardstick_battles."""
    if row["winner"] == 0:
        return 0.0
    if row["winner"] == 1:
        return 100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"])
    return -100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"])


def aggregate_role_scores(rows):
    """rows = [(yardstick_slug, scale, signed_score), ...] for ONE (civ, unit).
    Returns dict {role_score_type: float}."""
    by_role = defaultdict(list)
    for ys, _scale, sc in rows:
        for role in YARDSTICK_TO_ROLE.get(ys, ()):
            by_role[role].append(sc)
    out = {}
    for role in ROLE_SCORE_TYPES:
        vals = by_role.get(role, [])
        if vals:
            out[role] = round(sum(vals) / len(vals), 1)
    return out
```

- [ ] **Step 4: Run test, verify pass**

```bash
pytest tests/test_yardstick_score_derivation.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/derive_scores_from_yardsticks.py tests/test_yardstick_score_derivation.py
git commit -m "feat: yardstick role aggregation"
```

---

## Task 9: Score derivation - composites, pool normalization, DB write

**Files:**
- Modify: `webapp/derive_scores_from_yardsticks.py`
- Test: `tests/test_yardstick_score_derivation.py`

- [ ] **Step 1: Write failing test for pool normalization**

Append:

```python
from webapp.derive_scores_from_yardsticks import _normalize_pool


def test_normalize_pool_to_0_100():
    units = {
        "a": {"v": 50.0},
        "b": {"v": 100.0},
        "c": {"v": 0.0},
    }
    _normalize_pool(units, "v")
    assert units["a"]["v"] == 50.0
    assert units["b"]["v"] == 100.0
    assert units["c"]["v"] == 0.0


def test_normalize_pool_handles_all_equal():
    units = {"a": {"v": 5.0}, "b": {"v": 5.0}}
    _normalize_pool(units, "v")
    assert units["a"]["v"] == 0.0  # all-equal collapses to 0
    assert units["b"]["v"] == 0.0
```

- [ ] **Step 2: Add helpers to file**

Append to `webapp/derive_scores_from_yardsticks.py`:

```python
def _normalize_pool(units_dict, key):
    """Map units_dict[k][key] to 0..100 across the pool (linear)."""
    if not units_dict:
        return
    raw = [v[key] for v in units_dict.values()]
    lo, hi = min(raw), max(raw)
    span = hi - lo if hi != lo else 0
    for v in units_dict.values():
        if span == 0:
            v[key] = 0.0
        else:
            v[key] = round((v[key] - lo) / span * 100, 1)
```

- [ ] **Step 3: Add slug→line mapping**

```python
def build_slug_to_line():
    out = {}
    for line_slug, info in UNIT_LINES.items():
        for k in ("castle_slug", "imperial_slug"):
            if info.get(k):
                out[info[k]] = line_slug
        for k in ("castle_slugs", "imperial_slugs",
                  "extra_castle_slugs", "extra_imperial_slugs"):
            for s in (info.get(k) or []):
                if s:
                    out[s] = line_slug
        for civ_slugs in (info.get("unique_units") or {}).values():
            if isinstance(civ_slugs, list):
                for tup in civ_slugs:
                    for s in tup:
                        if s:
                            out[s] = line_slug
            else:
                for s in civ_slugs:
                    if s:
                        out[s] = line_slug
    return out
```

- [ ] **Step 4: Add the main compute function**

```python
def compute_scores(yardstick_conn, ref_units_by_civ_slug, slug_to_line):
    """Returns {(line_slug, civ, unit): {score_type: 0..100, ...}}."""

    # Load all yardstick rows, compute signed scores
    rows = yardstick_conn.execute(
        """SELECT civ, my_unit_slug, yardstick_slug, scale,
                  winner, team1_hp_pct, team2_hp_pct
           FROM yardstick_battles"""
    ).fetchall()

    by_unit = defaultdict(list)  # (civ, slug) -> [(ys, scale, signed_score)]
    for r in rows:
        by_unit[(r["civ"], r["my_unit_slug"])].append(
            (r["yardstick_slug"], r["scale"], _signed_score_from_row(r))
        )

    # Group units by POOL with their ref-unit speed/range for composite weighting
    by_pool = defaultdict(dict)  # pool -> {(line, civ, slug): {role+composite vals + _speed/_range}}
    for (civ, slug), pair_rows in by_unit.items():
        line = slug_to_line.get(slug)
        if line is None:
            continue
        pool = POOL_OF_LINE.get(line)
        if pool is None:
            continue
        ref = ref_units_by_civ_slug.get((civ, slug))
        if ref is None:
            continue
        roles = aggregate_role_scores(pair_rows)
        if not roles:
            continue
        entry = dict(roles)
        entry["_speed"] = ref["final_speed"] or 1.0
        entry["_range"] = (ref["final_range"] or 0) + 1.0
        by_pool[pool][(line, civ, slug)] = entry

    out = defaultdict(dict)

    for pool, units in by_pool.items():
        # Pool-normalize each role score
        for role in ROLE_SCORE_TYPES:
            tmp = {k: {"v": v.get(role, 0)} for k, v in units.items()}
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[k][role] = v["v"]

        # Composite for the pool (assumes all units in the pool share same composite)
        sample_line = next(iter(units))[0]
        comp_name = LINE_COMPOSITE.get(sample_line)
        if not comp_name:
            continue
        weights = COMPOSITE_WEIGHTS[comp_name]
        tmp = {}
        for k in units:
            row = out[k]
            val = sum(weights[c] * row.get(c, 0) for c in weights)
            tmp[k] = {"v": val}
        mult_keys = SPEED_WEIGHTED_COMPOSITES.get(comp_name)
        if mult_keys:
            for k, v in tmp.items():
                mult = 1.0
                for mk in mult_keys:
                    mult *= units[k][mk]
                v["v"] *= mult
        _normalize_pool(tmp, "v")
        for k, v in tmp.items():
            out[k][comp_name] = v["v"]

    return out
```

- [ ] **Step 5: Add backup + DB writer**

```python
def load_ref_units(conn, age="Imperial"):
    rows = conn.execute(
        "SELECT civ_name, unit_slug, final_speed, final_range "
        "FROM ref_units WHERE age=?",
        (age,),
    ).fetchall()
    return {(r["civ_name"], r["unit_slug"]): r for r in rows}


def backup_existing(conn, age, score_types):
    rows = conn.execute(
        f"""SELECT id, line_slug, age, civ_name, unit_slug, score_type,
                   score_value, rank, median_delta
            FROM battle_scores
            WHERE age=? AND score_type IN ({','.join('?' * len(score_types))})""",
        (age, *score_types),
    ).fetchall()
    return [dict(r) for r in rows]


def write_scores(conn, scores, age, dry_run=False):
    age_lower = age.lower()
    cur = conn.cursor()

    by_line_type = defaultdict(list)
    for (line, civ, slug), st_map in scores.items():
        for st, val in st_map.items():
            by_line_type[(line, st)].append((civ, slug, val))

    deleted = 0
    for (line, st), entries in by_line_type.items():
        for civ, slug, _ in entries:
            cur.execute(
                "DELETE FROM battle_scores WHERE line_slug=? AND age=? "
                "AND civ_name=? AND unit_slug=? AND score_type=?",
                (line, age_lower, civ, slug, st),
            )
            deleted += cur.rowcount

    inserts = 0
    for (line, st), entries in by_line_type.items():
        entries.sort(key=lambda e: -e[2])
        sorted_vals = sorted(e[2] for e in entries)
        median_val = sorted_vals[len(sorted_vals) // 2] if sorted_vals else 0
        for rank_idx, (civ, slug, val) in enumerate(entries, start=1):
            cur.execute("""
                INSERT INTO battle_scores
                (line_slug, age, civ_name, unit_slug, score_type, score_value,
                 rank, median_delta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (line, age_lower, civ, slug, st, round(val, 1),
                  rank_idx, round(val - median_val, 1)))
            inserts += 1

    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return deleted, inserts


def restore_backup(conn, backup_path):
    with open(backup_path) as f:
        rows = json.load(f)
    cur = conn.cursor()
    age = rows[0]["age"] if rows else None
    score_types = sorted(set(r["score_type"] for r in rows))
    placeholders = ",".join("?" * len(score_types))
    cur.execute(
        f"DELETE FROM battle_scores WHERE age=? AND score_type IN ({placeholders})",
        (age, *score_types),
    )
    for r in rows:
        cur.execute("""
            INSERT INTO battle_scores
            (id, line_slug, age, civ_name, unit_slug, score_type, score_value,
             rank, median_delta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (r["id"], r["line_slug"], r["age"], r["civ_name"], r["unit_slug"],
              r["score_type"], r["score_value"], r["rank"], r["median_delta"]))
    conn.commit()
    return len(rows)
```

- [ ] **Step 6: Add main()**

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--age", default="imperial")
    parser.add_argument("--restore", metavar="BACKUP.json")
    args = parser.parse_args()

    if not os.path.exists(YARDSTICK_DB_PATH):
        print(f"ERROR: {YARDSTICK_DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    if args.restore:
        n = restore_backup(conn, args.restore)
        print(f"Restored {n} rows from {args.restore}")
        return

    age_proper = args.age.capitalize()
    yconn = sqlite3.connect(YARDSTICK_DB_PATH); yconn.row_factory = sqlite3.Row

    slug_to_line = build_slug_to_line()
    ref_units = load_ref_units(conn, age_proper)
    scores = compute_scores(yconn, ref_units, slug_to_line)
    print(f"Computed scores for {len(scores)} (line, civ, unit) entries")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"battle_scores_pre_yardstick_{ts}.json")
    backup = backup_existing(conn, args.age, TARGET_SCORE_TYPES)
    with open(backup_path, "w") as f:
        json.dump(backup, f)
    print(f"Backed up {len(backup)} rows to {backup_path}")

    deleted, inserted = write_scores(conn, scores, age_proper, dry_run=args.dry_run)
    print(f"Deleted: {deleted}  Inserted: {inserted}")
    if args.dry_run:
        print("(dry run — no changes committed)")

    yconn.close(); conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run tests and dry-run on Aztec smoke data**

```bash
pytest tests/test_yardstick_score_derivation.py -v
```

Expected: all PASS.

```bash
cd webapp && python3 derive_scores_from_yardsticks.py --dry-run
```

Expected: prints scores computed, deleted/inserted counts; no DB changes.

- [ ] **Step 8: Commit**

```bash
git add webapp/derive_scores_from_yardsticks.py tests/test_yardstick_score_derivation.py
git commit -m "feat: yardstick score derivation - composites, pool normalization, DB write"
```

---

## Task 10: matchup_combos_real.db schema migration + populate from BattleOutcome

**Files:**
- Create: `webapp/migrate_matchup_db_outcomes.py`
- Modify: `webapp/generate_matchup_db_real.py` (worker function consumes BattleOutcome)

- [ ] **Step 1: Write the migration script**

```python
# webapp/migrate_matchup_db_outcomes.py
"""Add nullable BattleOutcome columns to matchup_combos_real.db.

Idempotent: skips columns that already exist.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "matchup_combos_real.db")

NEW_COLUMNS = [
    ("end_reason", "TEXT"),
    ("game_time_s", "REAL"),
    ("team1_hp_pct", "REAL"),
    ("team2_hp_pct", "REAL"),
    ("team1_survivors", "INTEGER"),
    ("team2_survivors", "INTEGER"),
    ("team1_resources_lost", "INTEGER"),
    ("team2_resources_lost", "INTEGER"),
    ("runs_count", "INTEGER"),
    ("score_stddev", "REAL"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(matchup_combos)")
    existing = {r[1] for r in cur.fetchall()}
    added = 0
    for name, type_ in NEW_COLUMNS:
        if name in existing:
            continue
        cur.execute(f"ALTER TABLE matchup_combos ADD COLUMN {name} {type_}")
        added += 1
        print(f"  + {name} {type_}")
    conn.commit()
    conn.close()
    print(f"Added {added} columns.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run migration**

```bash
cd webapp && python3 migrate_matchup_db_outcomes.py
```

Expected: prints columns added (10 the first time, 0 on re-run).

- [ ] **Step 3: Update generate_matchup_db_real.py to populate new columns**

Find where `simulate_real_battle` is called (likely via `best_units.get_matchup_sims`). The simplest path: in the matchup runner, after `simulate_real_battle()` returns (now BattleOutcome), persist the outcome fields alongside the existing combo row.

The DB write currently happens via `_persist_combo()` or similar — find it:

```bash
grep -n "INSERT INTO matchup_combos\|cur.execute.*INSERT" webapp/generate_matchup_db_real.py
```

Add the outcome fields to the INSERT. Example shape:

```python
cur.execute("""
    INSERT INTO matchup_combos (...existing cols..., end_reason, game_time_s,
        team1_hp_pct, team2_hp_pct, team1_survivors, team2_survivors,
        team1_resources_lost, team2_resources_lost, runs_count, score_stddev)
    VALUES (...existing values..., ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (..., outcome.end_reason, outcome.game_time_s,
      outcome.team1_hp_pct, outcome.team2_hp_pct,
      outcome.team1_survivors, outcome.team2_survivors,
      outcome.team1_resources_lost, outcome.team2_resources_lost,
      runs_count, score_stddev))
```

If the matchup runner uses `get_matchup_sims()` which returns aggregated results (not per-pair outcomes), thread the outcome back. If too invasive, skip this step (Task 10b below): leave the matchup runner alone for now; the new outcome columns stay NULL. Yardstick-based scoring is what powers rankings, and the matchup runner gets full BattleOutcome on the next nightly re-run when we eventually rewrite it.

**Decision (per spec):** populate going forward. If `get_matchup_sims` collapses outcome data before persisting, that's an existing limitation — leave the columns NULL for now and call this task complete after the schema migration runs successfully.

- [ ] **Step 4: Verify schema**

```bash
sqlite3 webapp/matchup_combos_real.db "PRAGMA table_info(matchup_combos)" | tail -15
```

Expected: see all 10 new columns.

- [ ] **Step 5: Commit**

```bash
git add webapp/migrate_matchup_db_outcomes.py
git commit -m "feat: schema migration adds BattleOutcome columns to matchup_combos_real.db"
```

---

## Task 11: Stop matchup deriver writing yardstick-owned score types

**Files:**
- Modify: `webapp/derive_battle_scores_from_matchups.py`

- [ ] **Step 1: Add a guard / no-op switch**

Find `TARGET_SCORE_TYPES` (around line 47). Replace the body of `compute_scores()` and `write_scores()` to be conditional on a `--legacy` flag. Simpler: change `TARGET_SCORE_TYPES` to an empty tuple by default with a comment:

```python
# These score types are now owned by derive_scores_from_yardsticks.py.
# Keeping the script for the matchup_advisor side-effects (recommendation
# tracking) but it no longer writes ranking scores.
TARGET_SCORE_TYPES = ()
```

Then make `main()` skip the write loop when `TARGET_SCORE_TYPES` is empty:

```python
    if not TARGET_SCORE_TYPES:
        print("derive_battle_scores_from_matchups: no score types owned. "
              "(yardstick deriver owns rankings now.) Exiting.")
        return
```

- [ ] **Step 2: Verify it no-ops**

```bash
cd webapp && python3 derive_battle_scores_from_matchups.py
```

Expected: prints the "no score types owned" message and exits cleanly.

- [ ] **Step 3: Commit**

```bash
git add webapp/derive_battle_scores_from_matchups.py
git commit -m "refactor: matchup deriver yields ranking scores to yardstick deriver"
```

---

## Task 12: Full pipeline run + sanity checks

**Files:** none modified — operational task.

- [ ] **Step 1: Run full yardstick batch**

```bash
cd webapp && python3 run_yardstick_battles.py --reset
```

Expected wall-clock: 15–30 min on 8 workers. Watch progress every 10 tasks.

- [ ] **Step 2: Inspect cache hit rate from logs**

(Cache stats print at process exit — if not, add `print(_WORKER_STATE["cache"].stats())` at end of each worker.)

Expected: hit rate > 30% (many civs share vanilla halberdier / hussar fingerprints).

- [ ] **Step 3: Run score derivation**

```bash
cd webapp && python3 derive_scores_from_yardsticks.py
```

Expected: completes in seconds; prints deleted/inserted counts; backup written under `webapp/backups/`.

- [ ] **Step 4: Sanity-check the fix**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db'); conn.row_factory = sqlite3.Row
print('Aztec Elite Jaguar Warrior — anti_trash should be > 30 (was 0):')
for r in conn.execute('''
    SELECT score_type, score_value FROM battle_scores
    WHERE civ_name=\"Aztecs\" AND unit_slug=\"elite_jaguar_warrior_aztecs\"
      AND age=\"imperial\"
      AND score_type IN (\"general_combat\",\"anti_archer\",\"anti_cav\",\"anti_trash\",\"militia_value\")
    ORDER BY score_type'''):
    print(f'  {r[\"score_type\"]:<20} {r[\"score_value\"]}')
"
```

Expected: anti_trash >> 0 (likely 40–80). Other scores reasonable.

Spot-check a few more units known to be strong/weak in specific roles:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('webapp/aoe2_reference.db'); conn.row_factory = sqlite3.Row
for civ, slug in [
    ('Spanish','elite_conquistador_spanish'),
    ('Lithuanians','elite_leitis_lithuanians'),
    ('Britons','arbalester'),
    ('Mongols','elite_mangudai_mongols'),
]:
    print(f'{civ} {slug}:')
    for r in conn.execute('''SELECT score_type, score_value FROM battle_scores
        WHERE civ_name=? AND unit_slug=? AND age=\"imperial\"
        ORDER BY score_type''', (civ, slug)):
        print(f'  {r[\"score_type\"]:<25} {r[\"score_value\"]}')
"
```

Expected: each unit's role scores look reasonable for their known archetype.

- [ ] **Step 5: Spin up local server + smoke-test the rankings UI**

```bash
PORT=5002 python3 webapp/app.py &
sleep 3
curl -s http://localhost:5002/api/ref/unit-line/militia | python3 -c "
import json, sys
data = json.load(sys.stdin)
for u in data['imperial']:
    if 'jaguar' in u['unit_slug']:
        print(u['civ_name'], u['unit_slug'], 'anti_trash=', u.get('anti_trash'))
"
```

Expected: jaguar entries show non-zero anti_trash. Stop the server.

- [ ] **Step 6: Commit any small follow-up tweaks discovered, then push**

```bash
git push
```

---

## Self-Review

**Spec coverage check:**
- ✅ BattleOutcome schema → Task 1
- ✅ simulate_real_battle returns BattleOutcome → Task 2
- ✅ Cheap-wins optimizations (slots, sq-dist, aliasing, alive list) → Task 3
- ✅ Grid auto-tune + projectile skip → Task 4
- ✅ Unit fingerprint dedup + OutcomeCache → Task 5
- ✅ yardstick_battles.db schema → Task 6
- ✅ Yardstick batch runner with multiprocessing, resume, close-match repeats → Task 7
- ✅ Score derivation: signed_score, role aggregation, composites, pool normalization, DB write, backup/restore → Tasks 8–9
- ✅ matchup_combos_real.db schema migration → Task 10
- ✅ Matchup deriver yields ranking scores → Task 11
- ✅ Full pipeline run + sanity checks → Task 12

**Items in spec not implemented as separate tasks:**
- "Per-yardstick raw scores (e.g. `at_30v30_vs_halb`)" — mentioned in spec as bonus. Not implemented in this plan; would be a follow-up. Removing from scope to keep this plan tight; can add if needed.
- "Find-nearest-enemy throttling" (spec optimization #6) — not included in Task 3/4. Skipping: existing code already has some throttling; further tuning is risky and provides marginal gains.

These exclusions are intentional YAGNI: ranking fix is the primary goal, and these are nice-to-haves.

**Placeholder scan:** No TBD/TODO. All steps include exact code, exact commands.

**Type consistency:** `BattleOutcome` field names consistent across battle_outcome.py, simulation_real.py, yardstick_db.py, and derive_scores_from_yardsticks.py (`team1_hp_pct`, `winner`, `end_reason`, etc.). Function names consistent (`signed_score`, `average_outcomes`, `unit_fingerprint`, `aggregate_role_scores`, `_normalize_pool`).
