# Matchup DB Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate three matchup-related DBs into one raw-data `matchup_db.db`, with a separate `derived_data.db` for rankings + advisor recommendations, plus a resource-aware sim engine extension.

**Architecture:** `simulation_real.py` gains per-resource kill bonuses + HP-weighted value-lost computation. A new `run_matchup_battles.py` (PyPy-required) writes raw 1v1 outcomes to `matchup_db.db`. Two derivers (`derive_unit_rankings.py`, `derive_advisor_recs.py`) read from raw and write to `derived_data.db`. After verification, the three legacy DBs are deleted.

**Tech Stack:** Python 3.12 (main), PyPy 3 (sim workers), SQLite, multiprocessing.Pool, pytest.

**Spec:** [docs/superpowers/specs/2026-04-26-matchup-db-consolidation-design.md](../specs/2026-04-26-matchup-db-consolidation-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `webapp/simulation_real.py` | modify | Sim engine; gains `*_per_kill` props, accumulators, value_lost |
| `webapp/battle_outcome.py` | modify | Adds new fields to `BattleOutcome`; updates `average_outcomes` |
| `webapp/matchup_db.py` | **new** | Schema + I/O for `matchup_db.db` (replaces `yardstick_db.py`) |
| `webapp/sim_version.py` | **new** | Hash sim source files for incremental rebuild key |
| `webapp/run_matchup_battles.py` | **new** | Single batch runner (replaces `run_yardstick_battles.py` and `generate_matchup_db_real.py`) |
| `webapp/derive_unit_rankings.py` | **new** | Reads matchup_db, writes battle_scores (replaces `derive_scores_from_yardsticks.py`) |
| `webapp/derive_advisor_recs.py` | **new** | Reads matchup_db, writes advisor_recommendations |
| `webapp/derived_db.py` | **new** | Schema + I/O for `derived_data.db` |
| `webapp/unit_lines.py` | modify | Reclassify Tarkan → light_cav, Wu Fire Archer → archer |
| `webapp/app.py` | modify | Read battle_scores + advisor recs from `derived_data.db` |
| `analysis/config_combat.py` | modify | Mapuche mounted units `gold_per_kill: 3` |
| `webapp/yardstick_db.py` | **delete** | Replaced by `matchup_db.py` |
| `webapp/run_yardstick_battles.py` | **delete** | Replaced |
| `webapp/derive_scores_from_yardsticks.py` | **delete** | Replaced |
| `webapp/generate_matchup_db.py` | **delete** | Old fast-sim generator, no longer used |
| `webapp/generate_matchup_db_real.py` | **delete** | Replaced |
| `webapp/derive_battle_scores_from_matchups.py` | **delete** | TARGET_SCORE_TYPES is empty; functionality moved to advisor deriver |
| `webapp/compare_matchup_dbs.py` | **delete** | Compared two DBs we're removing |
| `webapp/migrate_matchup_db_outcomes.py` | **delete** | One-shot migration that's no longer relevant |
| `webapp/matchup_combos.db` | **delete** | After cutover |
| `webapp/matchup_combos_real.db` | **delete** | After cutover |
| `webapp/yardstick_battles.db` | **delete** | After cutover |
| `tests/test_resource_per_kill.py` | **new** | Sim test: kill bonus accrues correctly |
| `tests/test_value_lost.py` | **new** | Sim test: HP-weighted loss math |
| `tests/test_matchup_db.py` | **new** | Schema + insert/upsert + dedup_group |
| `tests/test_unit_ranking_derive.py` | **new** | Synthetic matchup_db → expected battle_scores |
| `tests/test_advisor_derive.py` | **new** | Synthetic matchup_db → expected advisor_recommendations |
| `tests/test_sim_version.py` | **new** | Hash stability + invalidation on file change |

---

## Task 1: Add per-resource kill bonus properties to `BattleUnit`

**Goal:** A unit can carry `food_per_kill`, `wood_per_kill`, `gold_per_kill` properties read from stats dict; these are awarded to the killing unit's TEAM each time the unit kills an enemy.

**Files:**
- Modify: `webapp/simulation_real.py` (around line 238 — `BattleUnit` class)
- Test: `tests/test_resource_per_kill.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resource_per_kill.py
import pytest
from webapp.simulation_real import BattleUnit


def _stats(**kwargs):
    base = {
        "max_hp": 100, "attack": 5, "melee_armor": 0, "pierce_armor": 0,
        "speed": 1.0, "attack_range": 0, "reload_time": 2.0,
        "cost_food": 0, "cost_wood": 0, "cost_gold": 0,
    }
    base.update(kwargs)
    return base


def test_battleunit_reads_per_resource_kill_bonuses():
    u = BattleUnit("test", 1, _stats(food_per_kill=2, wood_per_kill=1, gold_per_kill=3))
    assert u.food_per_kill == 2
    assert u.wood_per_kill == 1
    assert u.gold_per_kill == 3


def test_battleunit_defaults_kill_bonuses_to_zero():
    u = BattleUnit("test", 1, _stats())
    assert u.food_per_kill == 0
    assert u.wood_per_kill == 0
    assert u.gold_per_kill == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_per_kill.py::test_battleunit_reads_per_resource_kill_bonuses -v`
Expected: FAIL with `AttributeError: 'BattleUnit' object has no attribute 'food_per_kill'`

- [ ] **Step 3: Add the slots and init values to `BattleUnit`**

In `webapp/simulation_real.py`, modify `__slots__` (around line 256, in the line containing `attack_bonus_per_kill`):

```python
        "block_first_melee", "attack_bonus_per_kill",
        "food_per_kill", "wood_per_kill", "gold_per_kill",
```

Then in `BattleUnit.__init__` (after the existing `self.attack_bonus_per_kill = _to_int(stats.get("attack_bonus_per_kill"))` line near line 328), add:

```python
        self.food_per_kill = float(stats.get("food_per_kill") or 0)
        self.wood_per_kill = float(stats.get("wood_per_kill") or 0)
        self.gold_per_kill = float(stats.get("gold_per_kill") or 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_per_kill.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add webapp/simulation_real.py tests/test_resource_per_kill.py
git commit -m "feat(sim): add food/wood/gold per-kill properties to BattleUnit"
```

---

## Task 2: Add per-team resource accumulators to `BattleSimulation`

**Goal:** `BattleSimulation` carries six accumulators (`team{1,2}_{food,wood,gold}_gained`) initialized to 0.

**Files:**
- Modify: `webapp/simulation_real.py` (around line 924, `BattleSimulation.__init__`)
- Test: `tests/test_resource_per_kill.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_per_kill.py`:

```python
from webapp.simulation_real import BattleSimulation


def test_simulation_initializes_resource_accumulators():
    sim = BattleSimulation()
    assert sim.team1_food_gained == 0.0
    assert sim.team1_wood_gained == 0.0
    assert sim.team1_gold_gained == 0.0
    assert sim.team2_food_gained == 0.0
    assert sim.team2_wood_gained == 0.0
    assert sim.team2_gold_gained == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_per_kill.py::test_simulation_initializes_resource_accumulators -v`
Expected: FAIL with `AttributeError: 'BattleSimulation' object has no attribute 'team1_food_gained'`

- [ ] **Step 3: Add accumulators to `BattleSimulation.__init__`**

In `webapp/simulation_real.py`, in `BattleSimulation.__init__` (after `self.has_ranged = False` around line 934):

```python
        self.team1_food_gained = 0.0
        self.team1_wood_gained = 0.0
        self.team1_gold_gained = 0.0
        self.team2_food_gained = 0.0
        self.team2_wood_gained = 0.0
        self.team2_gold_gained = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resource_per_kill.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add webapp/simulation_real.py tests/test_resource_per_kill.py
git commit -m "feat(sim): add per-team resource accumulators"
```

---

## Task 3: Award resources to killer's team on kill

**Goal:** Every place in the sim where `target_was_alive and target.state == "dead"` (the existing kill-detection sites at lines ~655 and ~743), award the killer's `*_per_kill` values to the killer's team accumulators.

**Files:**
- Modify: `webapp/simulation_real.py` (around lines 655 and 743)
- Test: `tests/test_resource_per_kill.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_per_kill.py`:

```python
from webapp.simulation_real import simulate_real_battle, prepare_combat_unit


def _killer_unit(gold_per_kill=3):
    """A high-attack unit that one-shots its target."""
    return prepare_combat_unit({
        "max_hp": 1000, "attack": 1000, "melee_armor": 50, "pierce_armor": 50,
        "speed": 2.0, "attack_range": 0, "reload_time": 1.0,
        "cost_food": 50, "cost_wood": 0, "cost_gold": 50,
        "outline_size": 0.2,
        "gold_per_kill": gold_per_kill,
    })


def _victim_unit():
    return prepare_combat_unit({
        "max_hp": 50, "attack": 0, "melee_armor": 0, "pierce_armor": 0,
        "speed": 0.1, "attack_range": 0, "reload_time": 5.0,
        "cost_food": 30, "cost_wood": 0, "cost_gold": 20,
        "outline_size": 0.2,
    })


def test_team1_gold_accrues_per_kill():
    """30 killers vs 30 victims: team1 should gain 30 * gold_per_kill."""
    outcome = simulate_real_battle(
        _killer_unit(gold_per_kill=3), _victim_unit(),
        resources=0, fixed_count=30, seed=0,
    )
    # Expect team1 to win, gain 30 * 3 = 90 gold.
    assert outcome.winner == 1
    assert outcome.team1_gold_gained == pytest.approx(90.0)
    assert outcome.team2_gold_gained == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_resource_per_kill.py::test_team1_gold_accrues_per_kill -v`
Expected: FAIL with `AttributeError: 'BattleOutcome' object has no attribute 'team1_gold_gained'` (we'll add to BattleOutcome in Task 5; for now the test will keep failing differently each subtask).

- [ ] **Step 3: Wire kill bonuses in projectile `on_hit` (around line 655)**

In `webapp/simulation_real.py` `_create_projectile` function, in the `on_hit` closure, after the existing `attack_bonus_per_kill` block (line 657), add:

```python
            if (target_was_alive and target.state == "dead"
                    and (attacker.food_per_kill > 0 or attacker.wood_per_kill > 0
                         or attacker.gold_per_kill > 0)):
                if attacker.team == 1:
                    sim.team1_food_gained += attacker.food_per_kill
                    sim.team1_wood_gained += attacker.wood_per_kill
                    sim.team1_gold_gained += attacker.gold_per_kill
                else:
                    sim.team2_food_gained += attacker.food_per_kill
                    sim.team2_wood_gained += attacker.wood_per_kill
                    sim.team2_gold_gained += attacker.gold_per_kill
```

- [ ] **Step 4: Wire kill bonuses in melee `perform_attack_on` (around line 743)**

In `BattleUnit.perform_attack_on`, after the existing `attack_bonus_per_kill` block (line 745), add:

```python
        if (target_was_alive and target.state == "dead"
                and (self.food_per_kill > 0 or self.wood_per_kill > 0
                     or self.gold_per_kill > 0)):
            if self.team == 1:
                sim.team1_food_gained += self.food_per_kill
                sim.team1_wood_gained += self.wood_per_kill
                sim.team1_gold_gained += self.gold_per_kill
            else:
                sim.team2_food_gained += self.food_per_kill
                sim.team2_wood_gained += self.wood_per_kill
                sim.team2_gold_gained += self.gold_per_kill
```

- [ ] **Step 5: Don't run the test yet — Task 5 adds the BattleOutcome fields. Commit the wiring.**

```bash
git add webapp/simulation_real.py
git commit -m "feat(sim): award per-resource kill bonuses to killer's team"
```

---

## Task 4: Compute HP-weighted per-resource losses + value_lost

**Goal:** New `BattleSimulation` methods that return per-resource lost and aggregate value_lost for either team, using the formula:

```
team_resource_lost = sum(unit.cost_resource * (1 - unit.current_hp / unit.max_hp) for unit in team)
team_value_lost   = (food_lost + wood_lost + gold_lost) - (food_gained + wood_gained + gold_gained)
```

**Files:**
- Modify: `webapp/simulation_real.py` (around line 979, `total_resources_lost`)
- Test: `tests/test_value_lost.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_value_lost.py
import pytest
from webapp.simulation_real import BattleSimulation, BattleUnit


def _stats(hp=100, **kw):
    base = {
        "max_hp": hp, "attack": 5, "melee_armor": 0, "pierce_armor": 0,
        "speed": 1.0, "attack_range": 0, "reload_time": 2.0,
        "cost_food": 50, "cost_wood": 0, "cost_gold": 30,
    }
    base.update(kw)
    return base


def test_no_damage_means_zero_value_lost():
    sim = BattleSimulation()
    sim.setup_team(1, _stats(), 5)
    # All units full HP, none dead
    assert sim.total_food_lost(1) == 0
    assert sim.total_wood_lost(1) == 0
    assert sim.total_gold_lost(1) == 0
    assert sim.total_value_lost(1) == 0


def test_dead_unit_contributes_full_cost():
    sim = BattleSimulation()
    sim.setup_team(1, _stats(), 3)
    sim.team1[0].current_hp = 0
    sim.team1[0].state = "dead"
    # 1 dead unit at 50 food + 30 gold = 80 lost
    assert sim.total_food_lost(1) == pytest.approx(50.0)
    assert sim.total_gold_lost(1) == pytest.approx(30.0)
    assert sim.total_value_lost(1) == pytest.approx(80.0)


def test_partial_damage_partial_loss():
    sim = BattleSimulation()
    sim.setup_team(1, _stats(hp=100), 1)
    sim.team1[0].current_hp = 50  # 50% damaged
    # Lost = cost * (1 - 0.5) = 50% of 80 = 40
    assert sim.total_value_lost(1) == pytest.approx(40.0)


def test_value_lost_subtracts_gained():
    sim = BattleSimulation()
    sim.setup_team(1, _stats(), 1)
    sim.team1[0].current_hp = 0
    sim.team1[0].state = "dead"
    sim.team1_gold_gained = 25.0  # killed enough to gain 25 gold
    # Lost 80 - gained 25 = 55 net
    assert sim.total_value_lost(1) == pytest.approx(55.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_value_lost.py -v`
Expected: FAIL with `AttributeError: 'BattleSimulation' object has no attribute 'total_food_lost'`

- [ ] **Step 3: Add the methods**

In `webapp/simulation_real.py`, REPLACE the existing `total_resources_lost` method (around line 979) with:

```python
    def _resource_lost(self, team_num, attr):
        """HP-weighted resource loss: cost × (1 - current_hp / max_hp), summed."""
        team = self.team1 if team_num == 1 else self.team2
        total = 0.0
        for u in team:
            cost = float(getattr(u, attr) or 0)
            if cost == 0:
                continue
            if u.state == "dead":
                total += cost
            else:
                lost_fraction = 1.0 - (u.current_hp / u.max_hp)
                if lost_fraction > 0:
                    total += cost * lost_fraction
        return total

    def total_food_lost(self, team_num):
        return round(self._resource_lost(team_num, "cost_food"), 3)

    def total_wood_lost(self, team_num):
        return round(self._resource_lost(team_num, "cost_wood"), 3)

    def total_gold_lost(self, team_num):
        return round(self._resource_lost(team_num, "cost_gold"), 3)

    def total_resources_lost(self, team_num):
        """Legacy compat: integer sum of food + wood + gold lost (rounded)."""
        return int(round(
            self._resource_lost(team_num, "cost_food")
            + self._resource_lost(team_num, "cost_wood")
            + self._resource_lost(team_num, "cost_gold")
        ))

    def total_value_lost(self, team_num):
        """Net value lost = (food + wood + gold lost) - (food + wood + gold gained)."""
        if team_num == 1:
            gained = self.team1_food_gained + self.team1_wood_gained + self.team1_gold_gained
        else:
            gained = self.team2_food_gained + self.team2_wood_gained + self.team2_gold_gained
        lost = (self._resource_lost(team_num, "cost_food")
                + self._resource_lost(team_num, "cost_wood")
                + self._resource_lost(team_num, "cost_gold"))
        return round(lost - gained, 3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_value_lost.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add webapp/simulation_real.py tests/test_value_lost.py
git commit -m "feat(sim): HP-weighted per-resource loss + net value_lost"
```

---

## Task 5: Extend `BattleOutcome` with new fields and update `simulate_real_battle`

**Goal:** `BattleOutcome` carries the 14 new fields (per-team food/wood/gold lost+gained + value_lost, plus per-unit costs). `simulate_real_battle` populates them. `average_outcomes` averages them.

**Files:**
- Modify: `webapp/battle_outcome.py`
- Modify: `webapp/simulation_real.py` (around line 1183, the `BattleOutcome(...)` constructor in `simulate_real_battle`)
- Test: `tests/test_resource_per_kill.py` (the test from Task 3 will now pass)
- Test: `tests/test_battle_outcome.py` (extend if needed)

- [ ] **Step 1: Write the failing test for BattleOutcome shape**

Append to `tests/test_battle_outcome.py`:

```python
def test_battle_outcome_carries_per_resource_fields():
    o = BattleOutcome(
        winner=1, end_reason="eliminated", game_time_s=10.0,
        team1_hp_pct=1.0, team2_hp_pct=0.0,
        team1_survivors=30, team2_survivors=0,
        team1_resources_lost=0, team2_resources_lost=4500,
        team1_start_count=30, team2_start_count=30,
        team1_food_lost=0.0, team1_wood_lost=0.0, team1_gold_lost=0.0,
        team1_food_gained=90.0, team1_wood_gained=0.0, team1_gold_gained=0.0,
        team1_value_lost=-90.0,
        team2_food_lost=2250.0, team2_wood_lost=0.0, team2_gold_lost=2250.0,
        team2_food_gained=0.0, team2_wood_gained=0.0, team2_gold_gained=0.0,
        team2_value_lost=4500.0,
        my_cost_food=50, my_cost_wood=0, my_cost_gold=50,
        opp_cost_food=75, opp_cost_wood=0, opp_cost_gold=75,
    )
    assert o.team1_gold_gained == 90.0
    assert o.team2_value_lost == 4500.0
    assert o.my_cost_food == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_battle_outcome.py::test_battle_outcome_carries_per_resource_fields -v`
Expected: FAIL with `TypeError: BattleOutcome.__init__() got an unexpected keyword argument 'team1_food_lost'`

- [ ] **Step 3: Extend `BattleOutcome`**

REPLACE the entire `BattleOutcome` dataclass in `webapp/battle_outcome.py` with:

```python
@dataclass
class BattleOutcome:
    winner: int
    end_reason: str
    game_time_s: float
    team1_hp_pct: float
    team2_hp_pct: float
    team1_survivors: int
    team2_survivors: int
    team1_resources_lost: int        # legacy: integer sum of all 3 resources
    team2_resources_lost: int
    team1_start_count: int
    team2_start_count: int

    # Per-resource breakdown — HP-weighted loss
    team1_food_lost: float = 0.0
    team1_wood_lost: float = 0.0
    team1_gold_lost: float = 0.0
    team2_food_lost: float = 0.0
    team2_wood_lost: float = 0.0
    team2_gold_lost: float = 0.0

    # Resources gained from kill-bonus civ effects (e.g. Mapuche +3 gold/kill)
    team1_food_gained: float = 0.0
    team1_wood_gained: float = 0.0
    team1_gold_gained: float = 0.0
    team2_food_gained: float = 0.0
    team2_wood_gained: float = 0.0
    team2_gold_gained: float = 0.0

    # Net value lost = (food + wood + gold lost) - (food + wood + gold gained)
    team1_value_lost: float = 0.0
    team2_value_lost: float = 0.0

    # Per-unit cost (cached so downstream consumers don't need to re-lookup)
    my_cost_food: float = 0.0
    my_cost_wood: float = 0.0
    my_cost_gold: float = 0.0
    opp_cost_food: float = 0.0
    opp_cost_wood: float = 0.0
    opp_cost_gold: float = 0.0
```

- [ ] **Step 4: Update `average_outcomes` to include new fields**

REPLACE the `average_outcomes` function in `webapp/battle_outcome.py` with:

```python
def average_outcomes(outcomes):
    """Aggregate N outcomes into one. Means for numeric fields, majority for
    winner (HP-tiebreak), most-common for end_reason."""
    if not outcomes:
        raise ValueError("average_outcomes called with empty list")
    n = len(outcomes)
    sample = outcomes[0]
    end_reason = Counter(o.end_reason for o in outcomes).most_common(1)[0][0]

    def mean(attr):
        return round(sum(getattr(o, attr) for o in outcomes) / n, 4)

    def imean(attr):
        return int(round(sum(getattr(o, attr) for o in outcomes) / n))

    return replace(
        sample,
        winner=_majority_winner(outcomes),
        end_reason=end_reason,
        game_time_s=round(sum(o.game_time_s for o in outcomes) / n, 3),
        team1_hp_pct=mean("team1_hp_pct"),
        team2_hp_pct=mean("team2_hp_pct"),
        team1_survivors=imean("team1_survivors"),
        team2_survivors=imean("team2_survivors"),
        team1_resources_lost=imean("team1_resources_lost"),
        team2_resources_lost=imean("team2_resources_lost"),
        team1_food_lost=mean("team1_food_lost"),
        team1_wood_lost=mean("team1_wood_lost"),
        team1_gold_lost=mean("team1_gold_lost"),
        team2_food_lost=mean("team2_food_lost"),
        team2_wood_lost=mean("team2_wood_lost"),
        team2_gold_lost=mean("team2_gold_lost"),
        team1_food_gained=mean("team1_food_gained"),
        team1_wood_gained=mean("team1_wood_gained"),
        team1_gold_gained=mean("team1_gold_gained"),
        team2_food_gained=mean("team2_food_gained"),
        team2_wood_gained=mean("team2_wood_gained"),
        team2_gold_gained=mean("team2_gold_gained"),
        team1_value_lost=mean("team1_value_lost"),
        team2_value_lost=mean("team2_value_lost"),
    )
```

- [ ] **Step 5: Update `simulate_real_battle` to populate the new fields**

In `webapp/simulation_real.py`, REPLACE the `BattleOutcome(...)` block at the end of `simulate_real_battle` (around line 1183) with:

```python
    # Per-unit costs from the prepared combat dicts.
    u1_cost_food = float(unit1.get("cost_food") or 0)
    u1_cost_wood = float(unit1.get("cost_wood") or 0)
    u1_cost_gold = float(unit1.get("cost_gold") or 0)
    u2_cost_food = float(unit2.get("cost_food") or 0)
    u2_cost_wood = float(unit2.get("cost_wood") or 0)
    u2_cost_gold = float(unit2.get("cost_gold") or 0)

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
        team1_food_lost=sim.total_food_lost(1),
        team1_wood_lost=sim.total_wood_lost(1),
        team1_gold_lost=sim.total_gold_lost(1),
        team2_food_lost=sim.total_food_lost(2),
        team2_wood_lost=sim.total_wood_lost(2),
        team2_gold_lost=sim.total_gold_lost(2),
        team1_food_gained=round(sim.team1_food_gained, 3),
        team1_wood_gained=round(sim.team1_wood_gained, 3),
        team1_gold_gained=round(sim.team1_gold_gained, 3),
        team2_food_gained=round(sim.team2_food_gained, 3),
        team2_wood_gained=round(sim.team2_wood_gained, 3),
        team2_gold_gained=round(sim.team2_gold_gained, 3),
        team1_value_lost=sim.total_value_lost(1),
        team2_value_lost=sim.total_value_lost(2),
        my_cost_food=u1_cost_food,
        my_cost_wood=u1_cost_wood,
        my_cost_gold=u1_cost_gold,
        opp_cost_food=u2_cost_food,
        opp_cost_wood=u2_cost_wood,
        opp_cost_gold=u2_cost_gold,
    )
```

- [ ] **Step 6: Run all sim tests**

Run: `pytest tests/test_battle_outcome.py tests/test_resource_per_kill.py tests/test_value_lost.py tests/test_simulations.py -v`
Expected: ALL PASS, including the previously-failing `test_team1_gold_accrues_per_kill` from Task 3.

- [ ] **Step 7: Commit**

```bash
git add webapp/battle_outcome.py webapp/simulation_real.py tests/test_battle_outcome.py
git commit -m "feat(sim): BattleOutcome carries per-resource lost/gained/value_lost"
```

---

## Task 6: Add Mapuche `gold_per_kill: 3` to mounted-unit configs

**Goal:** The Mapuche civ bonus "Mounted units generate +3 gold per military unit killed" becomes a sim mechanic via `CIV_COMBAT_PROPERTIES`.

**Files:**
- Modify: `analysis/config_combat.py` (find the `CIV_COMBAT_PROPERTIES` dict)
- Test: end-to-end via the existing `test_team1_gold_accrues_per_kill` (Task 3)

- [ ] **Step 1: Find the config file pattern**

Run: `grep -n "CIV_COMBAT_PROPERTIES\|Mapuche" analysis/config_combat.py | head -20`
Expected: shows the dict and any existing Mapuche entries.

- [ ] **Step 2: Add Mapuche mounted gold-per-kill entries**

In `analysis/config_combat.py`'s `CIV_COMBAT_PROPERTIES` dict, add entries for every Mapuche stable unit and Bolas Rider:

```python
    ("Mapuche", "scout_cav"):              {"gold_per_kill": 3},
    ("Mapuche", "light_cav"):              {"gold_per_kill": 3},
    ("Mapuche", "hussar"):                 {"gold_per_kill": 3},
    ("Mapuche", "elite_bolas_rider_mapuche"): {"gold_per_kill": 3},
    ("Mapuche", "bolas_rider_mapuche"):    {"gold_per_kill": 3},
    ("Mapuche", "kona_mapuche"):           {"gold_per_kill": 3},
    ("Mapuche", "elite_kona_mapuche"):     {"gold_per_kill": 3},
```

(If the dict uses a different key style, mirror the existing Mapuche entries.)

- [ ] **Step 3: Regenerate the reference DB**

Run: `python3 -m analysis.generate_reference 2>&1 | tail -5`
Expected: completes without error, ~30s.

- [ ] **Step 4: Verify the property propagated**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('webapp/aoe2_reference.db')
c.row_factory = sqlite3.Row
for r in c.execute(\"SELECT unit_slug, gold_per_kill FROM ref_units WHERE civ_name='Mapuche' AND age='Imperial' AND gold_per_kill > 0\"):
    print(r['unit_slug'], r['gold_per_kill'])
"
```

Expected: Lists Mapuche mounted units with `gold_per_kill=3`. (Note: `ref_units` may not have a `gold_per_kill` column yet — see step 5.)

- [ ] **Step 5: If `ref_units` lacks the column, add it**

Run: `grep -n "hp_regen_in_combat\|food_per_kill" analysis/generate_reference.py analysis/generate_main_db.py webapp/combat_unit_loader.py 2>&1 | head -20`

For each file that lists special-property columns (mirror the pattern used for `hp_regen_in_combat`), add `food_per_kill`, `wood_per_kill`, `gold_per_kill`. Then re-run `python3 -m analysis.generate_reference && python3 -m analysis.generate_main_db`.

- [ ] **Step 6: Commit**

```bash
git add analysis/config_combat.py analysis/generate_reference.py analysis/generate_main_db.py webapp/combat_unit_loader.py webapp/aoe2_reference.db webapp/aoe2_units.db
git commit -m "feat(config): Mapuche mounted units gain 3 gold per kill"
```

---

## Task 7: Reclassify Tarkan and Wu Fire Archer in `unit_lines.py`

**Goal:** Tarkan moves from `ram` to `light_cav`. Wu Fire Archer moves from `bombard_cannon` to `archer`.

**Files:**
- Modify: `webapp/unit_lines.py`

- [ ] **Step 1: Find current placements**

Run: `grep -n "tarkan_huns\|elite_fire_archer_wu" webapp/unit_lines.py`
Expected: shows the existing entries.

- [ ] **Step 2: Move Tarkan**

In `webapp/unit_lines.py`, find the `ram` line entry that contains `tarkan_huns`. REMOVE Huns from its `unique_units` dict. Then in the `light_cav` line entry, ADD:

```python
            "Huns": ("tarkan_huns", "elite_tarkan_huns"),
```

If the `ram` line had a dedicated `tarkan` line entry instead, delete it and add to `light_cav` as above.

- [ ] **Step 3: Move Wu Fire Archer**

In `webapp/unit_lines.py`, find the `bombard_cannon` line entry that contains `elite_fire_archer_wu`. REMOVE Wu from its `unique_units` dict. Then in the `archer` line entry, ADD:

```python
            "Wu": ("fire_archer_wu", "elite_fire_archer_wu"),
```

(Use the actual Castle-tier slug — check `ref_units` table for the exact slug if `fire_archer_wu` doesn't exist; might be different.)

- [ ] **Step 4: Verify slug-to-line mapping**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from webapp.unit_lines import UNIT_LINES
slug_to_line = {}
for line, info in UNIT_LINES.items():
    for k in ('castle_slug','imperial_slug'):
        if info.get(k): slug_to_line[info[k]] = line
    for k in ('castle_slugs','imperial_slugs','extra_castle_slugs','extra_imperial_slugs'):
        for s in (info.get(k) or []): slug_to_line[s] = line
    for civ_slugs in (info.get('unique_units') or {}).values():
        if isinstance(civ_slugs, list):
            for tup in civ_slugs:
                for s in tup: slug_to_line[s] = line
        else:
            for s in civ_slugs: slug_to_line[s] = line
print('elite_tarkan_huns →', slug_to_line.get('elite_tarkan_huns'))
print('elite_fire_archer_wu →', slug_to_line.get('elite_fire_archer_wu'))
"
```

Expected:
```
elite_tarkan_huns → light_cav
elite_fire_archer_wu → archer
```

- [ ] **Step 5: Commit**

```bash
git add webapp/unit_lines.py
git commit -m "fix(lines): Tarkan moves to light_cav, Wu Fire Archer to archer"
```

---

## Task 8: Create `sim_version.py` — incremental rebuild key

**Goal:** A function `current_sim_version()` returns a stable hash prefix of the simulation source files. When any of those files changes, the hash changes, and rows in `matchup_db.db` with the old hash get re-simulated.

**Files:**
- Create: `webapp/sim_version.py`
- Test: `tests/test_sim_version.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_version.py
import os
import tempfile
import pytest
from webapp.sim_version import compute_sim_version


def test_returns_16_char_hex():
    v = compute_sim_version()
    assert isinstance(v, str)
    assert len(v) == 16
    int(v, 16)  # parses as hex


def test_changes_when_a_source_file_changes(tmp_path):
    f1 = tmp_path / "a.py"
    f1.write_text("x = 1\n")
    f2 = tmp_path / "b.py"
    f2.write_text("y = 2\n")
    v_before = compute_sim_version([str(f1), str(f2)])
    f1.write_text("x = 999\n")
    v_after = compute_sim_version([str(f1), str(f2)])
    assert v_before != v_after


def test_stable_when_files_unchanged(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("payload\n")
    assert compute_sim_version([str(f)]) == compute_sim_version([str(f)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sim_version.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.sim_version'`

- [ ] **Step 3: Implement**

```python
# webapp/sim_version.py
"""Hash sim source files into a 16-char version string.

Used as a row-level cache key in matchup_db: rows with a different
sim_version are re-simulated on the next run, others are skipped.
"""

import hashlib
import os

DEFAULT_FILES = [
    os.path.join(os.path.dirname(__file__), "simulation_real.py"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)),
                 "analysis", "config_combat.py"),
]


def compute_sim_version(file_paths=None):
    """Return 16-char hex SHA-256 prefix of the concatenated file contents.

    If `file_paths` is None, hashes the canonical sim files (simulation_real.py
    + config_combat.py).
    """
    if file_paths is None:
        file_paths = DEFAULT_FILES
    h = hashlib.sha256()
    for p in file_paths:
        with open(p, "rb") as f:
            h.update(f.read())
        h.update(b"\0")  # separator so concatenation can't collide
    return h.hexdigest()[:16]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sim_version.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add webapp/sim_version.py tests/test_sim_version.py
git commit -m "feat: sim_version hash for incremental rebuild key"
```

---

## Task 9: Create `matchup_db.py` — schema, insert/upsert, queries

**Goal:** A module that owns `matchup_db.db`. Provides `create_db(path)`, `insert_outcome(...)`, `has_row_with_version(...)`.

**Files:**
- Create: `webapp/matchup_db.py`
- Test: `tests/test_matchup_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_matchup_db.py
import os
import tempfile
import pytest
from webapp.battle_outcome import BattleOutcome
from webapp.matchup_db import (
    create_db, insert_outcome, has_row_with_version, fetch_all_rows, _short_hash,
)


def _outcome(**kw):
    base = dict(
        winner=1, end_reason="eliminated", game_time_s=10.0,
        team1_hp_pct=1.0, team2_hp_pct=0.0,
        team1_survivors=30, team2_survivors=0,
        team1_resources_lost=0, team2_resources_lost=4500,
        team1_start_count=30, team2_start_count=30,
    )
    base.update(kw)
    return BattleOutcome(**base)


def test_create_db_makes_table(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert any(r[0] == 'matchup_battles' for r in rows)


def test_insert_and_fetch(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    insert_outcome(
        conn,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Britons", opp_unit_slug="halberdier",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(),
        runs_count=1, score_stddev=None,
        dedup_group="abc1234567890def",
        sim_version="cafef00ddeadbeef",
    )
    rows = fetch_all_rows(conn)
    assert len(rows) == 1
    assert rows[0]["my_civ"] == "Aztecs"
    assert rows[0]["sim_version"] == "cafef00ddeadbeef"


def test_upsert_overwrites(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    args = dict(
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Britons", opp_unit_slug="halberdier",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(winner=1),
        runs_count=1, score_stddev=None, dedup_group="abc", sim_version="v1",
    )
    insert_outcome(conn, **args)
    args["outcome"] = _outcome(winner=2)
    args["sim_version"] = "v2"
    insert_outcome(conn, **args)
    rows = fetch_all_rows(conn)
    assert len(rows) == 1
    assert rows[0]["winner"] == 2
    assert rows[0]["sim_version"] == "v2"


def test_has_row_with_version(tmp_path):
    db_path = tmp_path / "matchup_test.db"
    conn = create_db(str(db_path))
    insert_outcome(
        conn,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Britons", opp_unit_slug="halberdier",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(),
        runs_count=1, score_stddev=None, dedup_group="abc", sim_version="v1",
    )
    assert has_row_with_version(conn, "Aztecs", "elite_jaguar_warrior_aztecs",
                                 "Britons", "halberdier", "30v30", "v1")
    assert not has_row_with_version(conn, "Aztecs", "elite_jaguar_warrior_aztecs",
                                     "Britons", "halberdier", "30v30", "v2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_matchup_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.matchup_db'`

- [ ] **Step 3: Implement the module**

```python
# webapp/matchup_db.py
"""Schema + I/O for matchup_db.db.

One row per (my_civ, my_unit, opp_civ, opp_unit, scale).  Stores raw
1v1 simulation outcomes including per-resource losses, gains, and
HP-weighted value_lost.

dedup_group is a stable 16-char hex string tagging every row sharing
the same sim result (identical fingerprint pair + scale).

sim_version is a hash of simulation source files; rows whose value
differs from current are re-simulated on the next run.
"""

import hashlib
import os
import sqlite3

from webapp.battle_outcome import BattleOutcome

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "matchup_db.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS matchup_battles (
    id INTEGER PRIMARY KEY,

    my_civ TEXT NOT NULL,
    my_unit_slug TEXT NOT NULL,
    opp_civ TEXT NOT NULL,
    opp_unit_slug TEXT NOT NULL,
    scale TEXT NOT NULL,
    my_count INTEGER NOT NULL,
    opp_count INTEGER NOT NULL,

    my_cost_food REAL NOT NULL,
    my_cost_wood REAL NOT NULL,
    my_cost_gold REAL NOT NULL,
    opp_cost_food REAL NOT NULL,
    opp_cost_wood REAL NOT NULL,
    opp_cost_gold REAL NOT NULL,

    winner INTEGER NOT NULL,
    end_reason TEXT NOT NULL,
    game_time_s REAL NOT NULL,

    team1_hp_pct REAL NOT NULL,
    team1_survivors INTEGER NOT NULL,
    team1_food_lost REAL NOT NULL,
    team1_wood_lost REAL NOT NULL,
    team1_gold_lost REAL NOT NULL,
    team1_food_gained REAL NOT NULL,
    team1_wood_gained REAL NOT NULL,
    team1_gold_gained REAL NOT NULL,
    team1_value_lost REAL NOT NULL,

    team2_hp_pct REAL NOT NULL,
    team2_survivors INTEGER NOT NULL,
    team2_food_lost REAL NOT NULL,
    team2_wood_lost REAL NOT NULL,
    team2_gold_lost REAL NOT NULL,
    team2_food_gained REAL NOT NULL,
    team2_wood_gained REAL NOT NULL,
    team2_gold_gained REAL NOT NULL,
    team2_value_lost REAL NOT NULL,

    team1_start_count INTEGER NOT NULL,
    team2_start_count INTEGER NOT NULL,

    runs_count INTEGER NOT NULL,
    score_stddev REAL,
    dedup_group TEXT NOT NULL,
    sim_version TEXT NOT NULL,

    UNIQUE(my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale)
);
CREATE INDEX IF NOT EXISTS idx_my  ON matchup_battles(my_civ, my_unit_slug);
CREATE INDEX IF NOT EXISTS idx_opp ON matchup_battles(opp_civ, opp_unit_slug);
CREATE INDEX IF NOT EXISTS idx_dedup ON matchup_battles(dedup_group);
CREATE INDEX IF NOT EXISTS idx_simver ON matchup_battles(sim_version);
"""


def _short_hash(t):
    """Stable 16-char hex prefix of a tuple — used as dedup_group label."""
    return hashlib.md5(repr(t).encode()).hexdigest()[:16]


def create_db(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_outcome(conn, *, my_civ, my_unit_slug, opp_civ, opp_unit_slug,
                   scale, my_count, opp_count,
                   outcome: BattleOutcome,
                   runs_count, score_stddev, dedup_group, sim_version):
    conn.execute("""
        INSERT INTO matchup_battles (
            my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
            my_count, opp_count,
            my_cost_food, my_cost_wood, my_cost_gold,
            opp_cost_food, opp_cost_wood, opp_cost_gold,
            winner, end_reason, game_time_s,
            team1_hp_pct, team1_survivors,
            team1_food_lost, team1_wood_lost, team1_gold_lost,
            team1_food_gained, team1_wood_gained, team1_gold_gained,
            team1_value_lost,
            team2_hp_pct, team2_survivors,
            team2_food_lost, team2_wood_lost, team2_gold_lost,
            team2_food_gained, team2_wood_gained, team2_gold_gained,
            team2_value_lost,
            team1_start_count, team2_start_count,
            runs_count, score_stddev, dedup_group, sim_version
        ) VALUES (?,?,?,?,?, ?,?, ?,?,?, ?,?,?, ?,?,?, ?,?, ?,?,?, ?,?,?, ?,
                  ?,?, ?,?,?, ?,?,?, ?, ?,?, ?,?,?,?)
        ON CONFLICT(my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale) DO UPDATE SET
            my_count=excluded.my_count, opp_count=excluded.opp_count,
            my_cost_food=excluded.my_cost_food, my_cost_wood=excluded.my_cost_wood, my_cost_gold=excluded.my_cost_gold,
            opp_cost_food=excluded.opp_cost_food, opp_cost_wood=excluded.opp_cost_wood, opp_cost_gold=excluded.opp_cost_gold,
            winner=excluded.winner, end_reason=excluded.end_reason, game_time_s=excluded.game_time_s,
            team1_hp_pct=excluded.team1_hp_pct, team1_survivors=excluded.team1_survivors,
            team1_food_lost=excluded.team1_food_lost, team1_wood_lost=excluded.team1_wood_lost, team1_gold_lost=excluded.team1_gold_lost,
            team1_food_gained=excluded.team1_food_gained, team1_wood_gained=excluded.team1_wood_gained, team1_gold_gained=excluded.team1_gold_gained,
            team1_value_lost=excluded.team1_value_lost,
            team2_hp_pct=excluded.team2_hp_pct, team2_survivors=excluded.team2_survivors,
            team2_food_lost=excluded.team2_food_lost, team2_wood_lost=excluded.team2_wood_lost, team2_gold_lost=excluded.team2_gold_lost,
            team2_food_gained=excluded.team2_food_gained, team2_wood_gained=excluded.team2_wood_gained, team2_gold_gained=excluded.team2_gold_gained,
            team2_value_lost=excluded.team2_value_lost,
            team1_start_count=excluded.team1_start_count, team2_start_count=excluded.team2_start_count,
            runs_count=excluded.runs_count, score_stddev=excluded.score_stddev,
            dedup_group=excluded.dedup_group, sim_version=excluded.sim_version
    """, (
        my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
        my_count, opp_count,
        outcome.my_cost_food, outcome.my_cost_wood, outcome.my_cost_gold,
        outcome.opp_cost_food, outcome.opp_cost_wood, outcome.opp_cost_gold,
        outcome.winner, outcome.end_reason, outcome.game_time_s,
        outcome.team1_hp_pct, outcome.team1_survivors,
        outcome.team1_food_lost, outcome.team1_wood_lost, outcome.team1_gold_lost,
        outcome.team1_food_gained, outcome.team1_wood_gained, outcome.team1_gold_gained,
        outcome.team1_value_lost,
        outcome.team2_hp_pct, outcome.team2_survivors,
        outcome.team2_food_lost, outcome.team2_wood_lost, outcome.team2_gold_lost,
        outcome.team2_food_gained, outcome.team2_wood_gained, outcome.team2_gold_gained,
        outcome.team2_value_lost,
        outcome.team1_start_count, outcome.team2_start_count,
        runs_count, score_stddev, dedup_group, sim_version,
    ))
    conn.commit()


def fetch_all_rows(conn):
    return conn.execute("SELECT * FROM matchup_battles").fetchall()


def has_row_with_version(conn, my_civ, my_unit_slug, opp_civ, opp_unit_slug,
                         scale, sim_version):
    r = conn.execute(
        """SELECT 1 FROM matchup_battles
           WHERE my_civ=? AND my_unit_slug=? AND opp_civ=? AND opp_unit_slug=?
             AND scale=? AND sim_version=?""",
        (my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, sim_version),
    ).fetchone()
    return r is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_matchup_db.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add webapp/matchup_db.py tests/test_matchup_db.py
git commit -m "feat: matchup_db schema + insert/upsert + version-aware lookups"
```

---

## Task 10: Build `run_matchup_battles.py` — coverage + dedup + symmetry

**Goal:** Single batch runner. Enumerates eligible (my_civ, my_unit) × (opp_civ, opp_unit) × scale tuples, applies fingerprint dedup, mirror symmetry, sim_version skip, and writes outcomes via `matchup_db.insert_outcome`.

**Files:**
- Create: `webapp/run_matchup_battles.py`

This task has no unit test — it's a pipeline script. End-to-end verification happens in Task 14.

- [ ] **Step 1: Implement the script**

```python
# webapp/run_matchup_battles.py
"""Single batch runner for matchup_db.db.

For each civ × eligible imperial unit, simulates 1v1 against every other
(civ, unit) at 30v30 and 3k-resource scales.  Mirror symmetry (A vs B
== B vs A from opposite sides) halves work; fingerprint dedup collapses
identical-stat units.

Hard requirement: PyPy 3.  Run with `pypy3 -m webapp.run_matchup_battles`.
"""

import argparse
import multiprocessing as mp
import os
import platform
import sqlite3
import statistics
import sys
import time
from collections import defaultdict

from webapp.battle_outcome import signed_score, average_outcomes
from webapp.combat_unit_loader import build_combat_dict_from_ref
from webapp.matchup_db import create_db, insert_outcome, has_row_with_version, _short_hash, DEFAULT_DB_PATH
from webapp.simulation import prepare_combat_unit
from webapp.simulation_real import simulate_real_battle
from webapp.sim_outcome_cache import unit_fingerprint
from webapp.sim_version import compute_sim_version
from webapp.unit_lines import UNIT_LINES, CIV_MISSING_UNITS

REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")

RANKED_LINES = frozenset({
    "militia", "spear", "shock_infantry",
    "skirmisher", "archer", "cav_archer", "gunpowder", "scorpion",
    "light_cav", "knight", "camel", "steppe_lancer", "elephant",
})

SCALES = [("30v30", 30, None), ("3k", None, 3000)]
CLOSE_MATCH_THRESHOLD = 5.0
REPEAT_SEEDS = (0, 1, 2)
DEFAULT_SEED = 0


def _require_pypy():
    if platform.python_implementation() != "PyPy":
        sys.stderr.write(
            "\nERROR: run_matchup_battles.py requires PyPy 3.\n"
            "  Install pypy3 from https://www.pypy.org/download.html\n"
            "  Then run: pypy3 -m webapp.run_matchup_battles\n\n"
        )
        sys.exit(2)


def _build_slug_to_line():
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


def _units_for_civ(ref_conn, civ, slug_to_line):
    rows = ref_conn.execute(
        "SELECT unit_slug FROM ref_units WHERE civ_name=? AND age='Imperial'",
        (civ,),
    ).fetchall()
    seen, out = set(), []
    for r in rows:
        slug = r["unit_slug"]
        if slug in seen:
            continue
        if slug_to_line.get(slug) not in RANKED_LINES:
            continue
        if (civ, slug) in CIV_MISSING_UNITS:
            continue
        seen.add(slug)
        out.append(slug)
    return out


def _run_group(my_unit, opp_unit, fixed_count, resources):
    """Run sims for one dedup group; close-match repeats apply."""
    outcomes = []
    for seed in REPEAT_SEEDS:
        if not outcomes and seed != DEFAULT_SEED:
            continue
        o = simulate_real_battle(
            my_unit, opp_unit,
            resources=resources or 0,
            fixed_count=fixed_count,
            seed=seed,
        )
        outcomes.append(o)
        if seed == DEFAULT_SEED:
            if abs(signed_score(o)) > CLOSE_MATCH_THRESHOLD:
                break

    if len(outcomes) == 1:
        return outcomes[0], 1, None
    avg = average_outcomes(outcomes)
    scores = [signed_score(o) for o in outcomes]
    stddev = round(statistics.pstdev(scores), 3) if len(scores) > 1 else None
    return avg, len(outcomes), stddev


def _worker_run(task):
    """task = (group_key, my_unit_dict, opp_unit_dict, fixed_count, resources)
    Returns (group_key, BattleOutcome, runs_count, score_stddev)."""
    group_key, my_unit, opp_unit, fixed_count, resources = task
    avg, runs_count, stddev = _run_group(my_unit, opp_unit, fixed_count, resources)
    return group_key, avg, runs_count, stddev


def main():
    _require_pypy()

    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing matchup DB before running")
    parser.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 1))
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--civs", nargs="+", help="Limit to specific civs")
    args = parser.parse_args()

    if args.reset and os.path.exists(args.db):
        os.remove(args.db)

    out_conn = create_db(args.db)
    sim_version = compute_sim_version()
    print(f"Sim version: {sim_version}")

    ref_conn = sqlite3.connect(REF_DB_PATH)
    ref_conn.row_factory = sqlite3.Row
    slug_to_line = _build_slug_to_line()

    if args.civs:
        civs = args.civs
    else:
        civs = sorted({r["civ_name"] for r in ref_conn.execute(
            "SELECT DISTINCT civ_name FROM ref_units"
        ).fetchall()})

    # Build the full (civ, unit) list
    all_units = []  # list of (civ, slug, combat_unit_dict, fingerprint)
    for civ in civs:
        for slug in _units_for_civ(ref_conn, civ, slug_to_line):
            cu = _load_unit(ref_conn, civ, slug)
            if cu is None:
                continue
            all_units.append((civ, slug, cu, unit_fingerprint(cu)))

    ref_conn.close()
    print(f"Eligible units: {len(all_units)} (civ, slug) pairs")

    # Build (my, opp) pairs with mirror-symmetry dedup.
    # Members carry their fingerprints so the insert step can detect
    # whether each row needs avg as-is (rep's direction) or flipped (mirror).
    groups = defaultdict(list)            # key -> list of (my_civ, my_slug, my_fp, opp_civ, opp_slug, opp_fp)
    representatives = {}                   # key -> (my_unit, opp_unit, my_fp, fixed, resources)

    total_slots = 0
    for i in range(len(all_units)):
        for j in range(i, len(all_units)):  # i == j allowed (mirror match)
            my_civ, my_slug, my_cu, my_fp = all_units[i]
            opp_civ, opp_slug, opp_cu, opp_fp = all_units[j]
            for scale_label, fixed_count, resources in SCALES:
                # 2 raw slots per pair (the (my, opp) and the mirror (opp, my))
                total_slots += 1 if i == j else 2
                # Dedup key: order-insensitive fingerprint pair + scale
                fp_key = tuple(sorted((my_fp, opp_fp)))
                key = (fp_key, scale_label)
                groups[key].append((my_civ, my_slug, my_fp, opp_civ, opp_slug, opp_fp))
                if i != j:
                    groups[key].append((opp_civ, opp_slug, opp_fp, my_civ, my_slug, my_fp))
                if key not in representatives:
                    representatives[key] = (my_cu, opp_cu, my_fp, fixed_count, resources)

    # Skip groups whose every member already has a row at the current sim_version.
    pending_keys = []
    skipped = 0
    for key, members in groups.items():
        scale_label = key[1]
        # member tuple = (my_civ, my_slug, my_fp, opp_civ, opp_slug, opp_fp)
        all_done = all(
            has_row_with_version(out_conn, m[0], m[1], m[3], m[4], scale_label, sim_version)
            for m in members
        )
        if all_done:
            skipped += len(members)
        else:
            pending_keys.append(key)

    print(f"Total raw slots:        {total_slots}")
    print(f"Unique dedup groups:    {len(groups)}")
    print(f"  Pending:              {len(pending_keys)}")
    print(f"  Skipped (cur ver):    {skipped} slots")

    if not pending_keys:
        print("All groups already complete at current sim_version.")
        out_conn.close()
        return

    # Worker task: (key, my_unit, opp_unit, fixed, resources)
    # — drop my_fp from the rep tuple before sending to the worker.
    tasks = []
    for key in pending_keys:
        my_unit, opp_unit, _rep_my_fp, fixed, resources = representatives[key]
        tasks.append((key, my_unit, opp_unit, fixed, resources))
    print(f"Dispatching {len(tasks)} group tasks across {args.workers} workers")
    t0 = time.perf_counter()

    with mp.Pool(processes=args.workers) as pool:
        for i, (group_key, avg, runs_count, stddev) in enumerate(
            pool.imap_unordered(_worker_run, tasks), start=1
        ):
            scale_label = group_key[1]
            members = groups[group_key]
            rep_my_fp = representatives[group_key][2]
            dg = _short_hash(group_key)
            for m_my_civ, m_my_slug, m_my_fp, m_opp_civ, m_opp_slug, m_opp_fp in members:
                # Direction detection by fingerprint:
                # if member's my_fp == rep's my_fp, the rep ran with this side
                # as team1; insert avg as-is.  Otherwise flip team1/team2.
                out = avg if m_my_fp == rep_my_fp else _flip_outcome(avg)
                insert_outcome(
                    out_conn,
                    my_civ=m_my_civ, my_unit_slug=m_my_slug,
                    opp_civ=m_opp_civ, opp_unit_slug=m_opp_slug,
                    scale=scale_label,
                    my_count=out.team1_start_count, opp_count=out.team2_start_count,
                    outcome=out, runs_count=runs_count, score_stddev=stddev,
                    dedup_group=dg, sim_version=sim_version,
                )
            if i % 20 == 0 or i == len(tasks):
                elapsed = time.perf_counter() - t0
                rep_civ, rep_slug, _, _, _, _ = members[0]
                print(f"[{i}/{len(tasks)}] {rep_civ}/{rep_slug} × {scale_label} "
                      f"(group has {len(members)} members) "
                      f"end={avg.end_reason} score={signed_score(avg):.1f}  "
                      f"({elapsed:.0f}s)")

    print(f"\nDone in {time.perf_counter() - t0:.0f}s.")
    out_conn.close()


def _flip_outcome(o):
    """Swap team1/team2 in a BattleOutcome (for mirrored row insertion)."""
    from dataclasses import replace
    flipped_winner = 0 if o.winner == 0 else (2 if o.winner == 1 else 1)
    return replace(
        o,
        winner=flipped_winner,
        team1_hp_pct=o.team2_hp_pct, team2_hp_pct=o.team1_hp_pct,
        team1_survivors=o.team2_survivors, team2_survivors=o.team1_survivors,
        team1_resources_lost=o.team2_resources_lost, team2_resources_lost=o.team1_resources_lost,
        team1_start_count=o.team2_start_count, team2_start_count=o.team1_start_count,
        team1_food_lost=o.team2_food_lost, team1_wood_lost=o.team2_wood_lost, team1_gold_lost=o.team2_gold_lost,
        team2_food_lost=o.team1_food_lost, team2_wood_lost=o.team1_wood_lost, team2_gold_lost=o.team1_gold_lost,
        team1_food_gained=o.team2_food_gained, team1_wood_gained=o.team2_wood_gained, team1_gold_gained=o.team2_gold_gained,
        team2_food_gained=o.team1_food_gained, team2_wood_gained=o.team1_wood_gained, team2_gold_gained=o.team1_gold_gained,
        team1_value_lost=o.team2_value_lost, team2_value_lost=o.team1_value_lost,
        my_cost_food=o.opp_cost_food, my_cost_wood=o.opp_cost_wood, my_cost_gold=o.opp_cost_gold,
        opp_cost_food=o.my_cost_food, opp_cost_wood=o.my_cost_wood, opp_cost_gold=o.my_cost_gold,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the dry path on a single civ (no full batch yet)**

Run: `pypy3 -m webapp.run_matchup_battles --civs Aztecs --workers 2 2>&1 | tail -10`

Expected: prints sim version, unit count, dispatches tasks, completes in <60s. Ends with "Done in Ns."

- [ ] **Step 3: Verify rows landed in DB**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('webapp/matchup_db.db')
print('Rows:', c.execute('SELECT COUNT(*) FROM matchup_battles').fetchone()[0])
for r in c.execute('SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale, winner, team1_value_lost, team2_value_lost FROM matchup_battles WHERE my_civ=\"Aztecs\" LIMIT 5'):
    print(r)
"
```

Expected: shows ~50–500 rows for Aztecs across opposing civs at both scales.

- [ ] **Step 4: Re-run to confirm sim_version skip**

Run: `pypy3 -m webapp.run_matchup_battles --civs Aztecs --workers 2 2>&1 | tail -5`
Expected: "All groups already complete at current sim_version." prints; runtime < 5s.

- [ ] **Step 5: Commit**

```bash
git add webapp/run_matchup_battles.py
git commit -m "feat: run_matchup_battles — single PyPy-required runner, mirror dedup"
```

---

## Task 11: Build `derived_db.py` — schema for `derived_data.db`

**Goal:** A new file `derived_data.db` that holds `battle_scores` (moved from `aoe2_reference.db`) and `advisor_recommendations` (new).

**Files:**
- Create: `webapp/derived_db.py`

- [ ] **Step 1: Implement**

```python
# webapp/derived_db.py
"""Schema + I/O for derived_data.db.

Holds analysis tables computed from matchup_db.db raw outcomes:
  - battle_scores:           ranking scores per (line, civ, unit, score_type)
  - advisor_recommendations: best top-unit + partner per (civ, opponent)

Reference data (units, techs, classes) stays in aoe2_reference.db; this
file only holds derivations that get rebuilt when the sim or scoring
formulas change.
"""

import os
import sqlite3

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS battle_scores (
    id INTEGER PRIMARY KEY,
    line_slug TEXT NOT NULL,
    age TEXT NOT NULL,
    civ_name TEXT NOT NULL,
    unit_slug TEXT NOT NULL,
    score_type TEXT NOT NULL,
    score_value REAL NOT NULL,
    rank INTEGER,
    median_delta REAL,
    UNIQUE(line_slug, age, civ_name, unit_slug, score_type)
);
CREATE INDEX IF NOT EXISTS idx_bs_line_age ON battle_scores(line_slug, age);
CREATE INDEX IF NOT EXISTS idx_bs_civ_unit ON battle_scores(civ_name, unit_slug, age);

CREATE TABLE IF NOT EXISTS advisor_recommendations (
    id INTEGER PRIMARY KEY,
    civ TEXT NOT NULL,
    opponent TEXT NOT NULL,
    rec_type TEXT NOT NULL,             -- 'top' | 'partner'
    rec_rank INTEGER NOT NULL,
    unit_slug TEXT NOT NULL,
    unit_name TEXT NOT NULL,
    score REAL NOT NULL,
    UNIQUE(civ, opponent, rec_type, rec_rank)
);
CREATE INDEX IF NOT EXISTS idx_ar ON advisor_recommendations(civ, opponent);
"""


def create_db(path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
```

- [ ] **Step 2: Smoke test**

```bash
python3 -c "
from webapp.derived_db import create_db
import os
test_path = '/tmp/test_derived.db'
if os.path.exists(test_path): os.remove(test_path)
c = create_db(test_path)
for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"):
    print(r[0])
"
```

Expected: prints `battle_scores` and `advisor_recommendations`.

- [ ] **Step 3: Commit**

```bash
git add webapp/derived_db.py
git commit -m "feat: derived_data.db schema (battle_scores + advisor_recommendations)"
```

---

## Task 12: Build `derive_unit_rankings.py` — rankings from matchup_db

**Goal:** Reads `matchup_db.matchup_battles`, computes ranking scores using the canonical yardstick subset, writes to `derived_data.battle_scores`. Mirrors today's `derive_scores_from_yardsticks.py` math.

**Files:**
- Create: `webapp/derive_unit_rankings.py`
- Test: `tests/test_unit_ranking_derive.py`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_unit_ranking_derive.py
import os
import sqlite3
import pytest

from webapp.battle_outcome import BattleOutcome
from webapp.matchup_db import create_db as create_matchup_db, insert_outcome
from webapp.derived_db import create_db as create_derived_db
from webapp.derive_unit_rankings import compute_and_write_rankings


def _outcome(winner=1, hp1=0.8, hp2=0.0):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=10.0,
        team1_hp_pct=hp1, team2_hp_pct=hp2,
        team1_survivors=24, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=4500,
        team1_start_count=30, team2_start_count=30,
    )


def test_derive_writes_role_and_composite_scores(tmp_path, monkeypatch):
    matchup_path = tmp_path / "matchup.db"
    derived_path = tmp_path / "derived.db"
    ref_path = tmp_path / "ref.db"

    # Build a minimal ref DB with one civ + one unit
    rc = sqlite3.connect(str(ref_path))
    rc.executescript("""
      CREATE TABLE ref_units (id INTEGER PRIMARY KEY, civ_name TEXT, unit_slug TEXT,
        age TEXT, final_speed REAL, final_range REAL);
      INSERT INTO ref_units (civ_name, unit_slug, age, final_speed, final_range)
        VALUES ('Aztecs', 'elite_jaguar_warrior_aztecs', 'Imperial', 1.0, 0);
    """)
    rc.commit(); rc.close()

    mc = create_matchup_db(str(matchup_path))
    # Insert one row vs the Vikings champion yardstick
    insert_outcome(mc,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Vikings", opp_unit_slug="champion",
        scale="30v30", my_count=30, opp_count=30,
        outcome=_outcome(winner=1, hp1=0.8, hp2=0.0),
        runs_count=1, score_stddev=None,
        dedup_group="abc", sim_version="v1",
    )
    insert_outcome(mc,
        my_civ="Aztecs", my_unit_slug="elite_jaguar_warrior_aztecs",
        opp_civ="Vikings", opp_unit_slug="champion",
        scale="3k", my_count=30, opp_count=30,
        outcome=_outcome(winner=1, hp1=0.7, hp2=0.0),
        runs_count=1, score_stddev=None,
        dedup_group="abc", sim_version="v1",
    )
    mc.close()

    dc = create_derived_db(str(derived_path))

    n = compute_and_write_rankings(
        matchup_db_path=str(matchup_path),
        ref_db_path=str(ref_path),
        derived_db_path=str(derived_path),
        age="Imperial",
    )
    assert n > 0

    rows = sqlite3.connect(str(derived_path)).execute(
        "SELECT score_type, score_value FROM battle_scores WHERE civ_name='Aztecs'"
    ).fetchall()
    score_types = {r[0] for r in rows}
    # Champion is part of general_combat aggregation
    assert "general_combat" in score_types
    # militia line gets militia_value composite
    assert "militia_value" in score_types
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_unit_ranking_derive.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.derive_unit_rankings'`

- [ ] **Step 3: Implement the deriver**

```python
# webapp/derive_unit_rankings.py
"""Read matchup_db.matchup_battles, write battle_scores to derived_data.db.

Score model: signed_score(outcome) = 100 * (winner_hp% - loser_hp%) (negated
if team2 won). Role aggregation, composites, pool normalization mirror the
prior derive_scores_from_yardsticks.py.
"""

import argparse
import os
import sqlite3
from collections import defaultdict

from webapp.derived_db import create_db as create_derived_db
from webapp.matchup_db import DEFAULT_DB_PATH as MATCHUP_DB_PATH
from webapp.unit_lines import UNIT_LINES, CIV_MISSING_UNITS

REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")
DERIVED_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")

YARDSTICKS = [
    ("Vikings", "champion"),
    ("Franks",  "paladin"),
    ("Britons", "arbalester"),
    ("Britons", "halberdier"),
    ("Britons", "imp_elite_skirm"),
    ("Magyars", "hussar"),
]

YARDSTICK_TO_ROLE = {
    "champion":        ["general_combat"],
    "paladin":         ["general_combat", "anti_cav"],
    "arbalester":      ["general_combat", "anti_archer"],
    "halberdier":      ["anti_trash"],
    "imp_elite_skirm": ["anti_trash"],
    "hussar":          ["anti_trash"],
}

ROLE_PREFIX = {"general_combat": "gc", "anti_cav": "ac",
               "anti_archer": "aa", "anti_trash": "at"}

YARDSTICK_LABEL = {
    "champion":        "champ",
    "paladin":         "paladin",
    "arbalester":      "arb",
    "halberdier":      "halb",
    "imp_elite_skirm": "elite_skirm",
    "hussar":          "hussar",
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


def sub_score_keys(role, ys_slug, scale):
    prefix = ROLE_PREFIX[role]
    label = YARDSTICK_LABEL[ys_slug]
    base = f"{prefix}_{scale}_vs_{label}"
    return base, f"{base}_raw"


def _signed_score(row):
    if row["winner"] == 0:
        return 0.0
    if row["winner"] == 1:
        return 100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"])
    return -100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"])


def _normalize_pool(units_dict, key):
    if not units_dict:
        return
    raw = [v[key] for v in units_dict.values()]
    lo, hi = min(raw), max(raw)
    span = hi - lo if hi != lo else 0
    for v in units_dict.values():
        v[key] = 0.0 if span == 0 else round((v[key] - lo) / span * 100, 1)


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


def compute_and_write_rankings(matchup_db_path=MATCHUP_DB_PATH,
                               ref_db_path=REF_DB_PATH,
                               derived_db_path=DERIVED_DB_PATH,
                               age="Imperial"):
    """Returns count of rows inserted into battle_scores."""
    mconn = sqlite3.connect(matchup_db_path)
    mconn.row_factory = sqlite3.Row
    rconn = sqlite3.connect(ref_db_path)
    rconn.row_factory = sqlite3.Row

    slug_to_line = build_slug_to_line()
    ref_units = {(r["civ_name"], r["unit_slug"]): r
                 for r in rconn.execute(
                     "SELECT civ_name, unit_slug, final_speed, final_range "
                     "FROM ref_units WHERE age=?", (age,)).fetchall()}

    # Pull only rows where opponent is a yardstick
    yardstick_civ_units = set(YARDSTICKS)
    rows = mconn.execute("""
        SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
               winner, team1_hp_pct, team2_hp_pct
        FROM matchup_battles
    """).fetchall()
    rows = [r for r in rows
            if (r["opp_civ"], r["opp_unit_slug"]) in yardstick_civ_units]

    # by_unit -> [(yardstick_slug, scale, signed_score)]
    by_unit = defaultdict(list)
    raw_subs = defaultdict(dict)  # (civ, slug) -> {sub_key: value}
    for r in rows:
        if (r["my_civ"], r["my_unit_slug"]) in CIV_MISSING_UNITS:
            continue
        sc = _signed_score(r)
        for role in YARDSTICK_TO_ROLE.get(r["opp_unit_slug"], ()):
            norm_key, raw_key = sub_score_keys(role, r["opp_unit_slug"], r["scale"])
            raw_subs[(r["my_civ"], r["my_unit_slug"])][raw_key] = round(sc, 1)
            raw_subs[(r["my_civ"], r["my_unit_slug"])][norm_key] = sc
        by_unit[(r["my_civ"], r["my_unit_slug"])].append(
            (r["opp_unit_slug"], r["scale"], sc)
        )

    # Aggregate roles per unit, classify by line/pool
    by_pool = defaultdict(dict)
    for (civ, slug), pair_rows in by_unit.items():
        line = slug_to_line.get(slug)
        if line is None:
            continue
        pool = POOL_OF_LINE.get(line)
        if pool is None:
            continue
        ref = ref_units.get((civ, slug))
        if ref is None:
            continue
        from collections import defaultdict as dd
        by_role = dd(list)
        for ys, _scale, sc in pair_rows:
            for role in YARDSTICK_TO_ROLE.get(ys, ()):
                by_role[role].append(sc)
        roles = {r: round(sum(v) / len(v), 1) for r, v in by_role.items() if v}
        if not roles:
            continue
        entry = dict(roles)
        entry["_speed"] = ref["final_speed"] or 1.0
        entry["_range"] = (ref["final_range"] or 0) + 1.0
        by_pool[pool][(line, civ, slug)] = entry

    # Build output dict
    out = defaultdict(dict)

    # Per-benchmark sub-scores: pool-normalize within each pool
    for pool, units in by_pool.items():
        sub_keys_in_pool = set()
        for (line, civ, slug) in units:
            for k in raw_subs[(civ, slug)]:
                if not k.endswith("_raw"):
                    sub_keys_in_pool.add(k)
        for sub_key in sub_keys_in_pool:
            tmp = {}
            for k in units:
                _, civ, slug = k
                tmp[k] = {"v": raw_subs[(civ, slug)].get(sub_key, 0)}
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[k][sub_key] = v["v"]
        for k in units:
            _, civ, slug = k
            for rkey, rval in raw_subs[(civ, slug)].items():
                if rkey.endswith("_raw"):
                    out[k][rkey] = rval

    # Role + composite scores
    for pool, units in by_pool.items():
        for role in ROLE_SCORE_TYPES:
            tmp = {k: {"v": v.get(role, 0)} for k, v in units.items()}
            _normalize_pool(tmp, "v")
            for k, v in tmp.items():
                out[k][role] = v["v"]

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

    # Write to derived_db.battle_scores
    dconn = sqlite3.connect(derived_db_path)
    age_lower = age.lower()
    by_line_type = defaultdict(list)
    for (line, civ, slug), st_map in out.items():
        for st, val in st_map.items():
            by_line_type[(line, st)].append((civ, slug, val))

    cur = dconn.cursor()
    inserts = 0
    for (line, st), entries in by_line_type.items():
        for civ, slug, _ in entries:
            cur.execute(
                "DELETE FROM battle_scores WHERE line_slug=? AND age=? "
                "AND civ_name=? AND unit_slug=? AND score_type=?",
                (line, age_lower, civ, slug, st),
            )
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

    dconn.commit()
    mconn.close(); rconn.close(); dconn.close()
    return inserts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--age", default="imperial")
    args = parser.parse_args()
    n = compute_and_write_rankings(age=args.age.capitalize())
    print(f"Inserted {n} rows into derived_data.battle_scores")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_unit_ranking_derive.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/derive_unit_rankings.py tests/test_unit_ranking_derive.py
git commit -m "feat: derive_unit_rankings reads matchup_db, writes derived_data.battle_scores"
```

---

## Task 13: Build `derive_advisor_recs.py` — civ-vs-civ recommendations

**Goal:** Reads `matchup_db.matchup_battles`, picks best top unit per (civ, opponent) by mean signed_score across opp_units, writes to `derived_data.advisor_recommendations`.

**Files:**
- Create: `webapp/derive_advisor_recs.py`
- Test: `tests/test_advisor_derive.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_advisor_derive.py
import sqlite3
import pytest

from webapp.battle_outcome import BattleOutcome
from webapp.matchup_db import create_db as create_matchup_db, insert_outcome
from webapp.derived_db import create_db as create_derived_db
from webapp.derive_advisor_recs import compute_and_write_recs


def _outcome(winner=1, hp1=0.8, hp2=0.0):
    return BattleOutcome(
        winner=winner, end_reason="eliminated", game_time_s=10.0,
        team1_hp_pct=hp1, team2_hp_pct=hp2,
        team1_survivors=24, team2_survivors=0,
        team1_resources_lost=900, team2_resources_lost=4500,
        team1_start_count=30, team2_start_count=30,
    )


def test_recommends_unit_with_highest_mean_score(tmp_path):
    matchup_path = tmp_path / "m.db"
    derived_path = tmp_path / "d.db"

    mc = create_matchup_db(str(matchup_path))
    # Aztecs has 2 candidate top units; Eagle wins big, Champion barely wins.
    for opp in ["arbalester", "halberdier", "champion"]:
        insert_outcome(mc, my_civ="Aztecs", my_unit_slug="elite_eagle",
            opp_civ="Britons", opp_unit_slug=opp, scale="30v30",
            my_count=30, opp_count=30,
            outcome=_outcome(winner=1, hp1=0.9, hp2=0.0),
            runs_count=1, score_stddev=None, dedup_group="x", sim_version="v1")
        insert_outcome(mc, my_civ="Aztecs", my_unit_slug="champion",
            opp_civ="Britons", opp_unit_slug=opp, scale="30v30",
            my_count=30, opp_count=30,
            outcome=_outcome(winner=1, hp1=0.2, hp2=0.0),
            runs_count=1, score_stddev=None, dedup_group="y", sim_version="v1")
    mc.close()

    create_derived_db(str(derived_path)).close()
    n = compute_and_write_recs(
        matchup_db_path=str(matchup_path),
        derived_db_path=str(derived_path),
    )
    assert n >= 2

    rows = sqlite3.connect(str(derived_path)).execute(
        "SELECT rec_rank, unit_slug, score FROM advisor_recommendations "
        "WHERE civ='Aztecs' AND opponent='Britons' AND rec_type='top' ORDER BY rec_rank"
    ).fetchall()
    assert rows[0][1] == "elite_eagle"   # rank 1 should be Eagle
    assert rows[1][1] == "champion"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_advisor_derive.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.derive_advisor_recs'`

- [ ] **Step 3: Implement**

```python
# webapp/derive_advisor_recs.py
"""Read matchup_db, write advisor recommendations to derived_data.db.

For each (my_civ, opp_civ) pair, finds the (my_unit) with the highest
mean signed_score against all (opp_civ) opp_units across both scales.
Writes top-2 candidates per pair as `rec_type='top'`.
"""

import argparse
import os
import sqlite3
from collections import defaultdict

from webapp.matchup_db import DEFAULT_DB_PATH as MATCHUP_DB_PATH

DERIVED_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")
REF_DB_PATH = os.path.join(os.path.dirname(__file__), "aoe2_reference.db")


def _signed(row):
    if row["winner"] == 0: return 0.0
    if row["winner"] == 1: return 100.0 * (row["team1_hp_pct"] - row["team2_hp_pct"])
    return -100.0 * (row["team2_hp_pct"] - row["team1_hp_pct"])


def compute_and_write_recs(matchup_db_path=MATCHUP_DB_PATH,
                           derived_db_path=DERIVED_DB_PATH,
                           ref_db_path=REF_DB_PATH,
                           top_n=2):
    mconn = sqlite3.connect(matchup_db_path)
    mconn.row_factory = sqlite3.Row

    # Pull all rows (already filtered by sim_version implicitly — just use what's there)
    rows = mconn.execute("""
        SELECT my_civ, my_unit_slug, opp_civ, opp_unit_slug, scale,
               winner, team1_hp_pct, team2_hp_pct
        FROM matchup_battles
    """).fetchall()

    # Aggregate: (my_civ, opp_civ, my_unit) -> list of signed scores
    bucket = defaultdict(list)
    for r in rows:
        bucket[(r["my_civ"], r["opp_civ"], r["my_unit_slug"])].append(_signed(r))

    # Per (my_civ, opp_civ): rank my_units by mean score
    by_pair = defaultdict(list)  # (civ, opp) -> [(unit, mean_score)]
    for (civ, opp, unit), scores in bucket.items():
        if not scores:
            continue
        by_pair[(civ, opp)].append((unit, sum(scores) / len(scores)))

    # Need unit_name; pull from ref DB
    rconn = sqlite3.connect(ref_db_path)
    rconn.row_factory = sqlite3.Row
    name_map = {}
    for r in rconn.execute(
        "SELECT civ_name, unit_slug, unit_name FROM ref_units WHERE age='Imperial'"
    ):
        name_map[(r["civ_name"], r["unit_slug"])] = r["unit_name"]
    rconn.close()
    mconn.close()

    dconn = sqlite3.connect(derived_db_path)
    cur = dconn.cursor()

    inserts = 0
    for (civ, opp), entries in by_pair.items():
        entries.sort(key=lambda e: -e[1])
        cur.execute("DELETE FROM advisor_recommendations WHERE civ=? AND opponent=? AND rec_type='top'",
                    (civ, opp))
        for rank, (unit_slug, score) in enumerate(entries[:top_n], start=1):
            unit_name = name_map.get((civ, unit_slug), unit_slug)
            cur.execute("""
                INSERT INTO advisor_recommendations
                (civ, opponent, rec_type, rec_rank, unit_slug, unit_name, score)
                VALUES (?, ?, 'top', ?, ?, ?, ?)
            """, (civ, opp, rank, unit_slug, unit_name, round(score, 2)))
            inserts += 1

    dconn.commit()
    dconn.close()
    return inserts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=2)
    args = parser.parse_args()
    n = compute_and_write_recs(top_n=args.top_n)
    print(f"Inserted {n} advisor recommendations")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_advisor_derive.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add webapp/derive_advisor_recs.py tests/test_advisor_derive.py
git commit -m "feat: derive_advisor_recs writes top-N units per (civ, opponent)"
```

---

## Task 14: First full PyPy batch run

**Goal:** Run `run_matchup_battles.py` over all eligible (civ, unit) pairs to populate the new `matchup_db.db` from scratch.

**Files:** none modified — execution step.

- [ ] **Step 1: Confirm PyPy is installed**

Run: `pypy3 --version`
Expected: PyPy 3.x version string. If missing, install from https://www.pypy.org/download.html and re-run.

- [ ] **Step 2: Reset and run**

On the dev machine (Ryzen 9 9900X / 12C-24T / 64 GB RAM), the default `--workers cpu_count-1 = 23` is correct. Each PyPy worker uses ~300 MB–1 GB; 23 × ~500 MB = ~12 GB peak, well within budget.

Run: `pypy3 -m webapp.run_matchup_battles --reset 2>&1 | tee /tmp/matchup_full_run.log | tail -20`
Expected: Pre-pass prints, dispatches ~130K group tasks. Runtime ~2–4 hours on this hardware. Final line: "Done in Ns."

If it errors midway, fix the error and re-run **without** `--reset` — sim_version skip will resume from where it left off.

- [ ] **Step 3: Verify row counts**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('webapp/matchup_db.db')
print('Rows:', c.execute('SELECT COUNT(*) FROM matchup_battles').fetchone()[0])
print('Distinct civs:', c.execute('SELECT COUNT(DISTINCT my_civ) FROM matchup_battles').fetchone()[0])
print('Distinct (civ, unit) pairs:', c.execute('SELECT COUNT(DISTINCT my_civ || \"|\" || my_unit_slug) FROM matchup_battles').fetchone()[0])
"
```

Expected: 53 civs, ~515 (civ, unit) pairs, ~265K rows (515² × 2 scales / 2 mirror = 265,225).

- [ ] **Step 4: Sanity-check Mapuche gold gain**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('webapp/matchup_db.db')
c.row_factory = sqlite3.Row
for r in c.execute(\"\"\"
  SELECT opp_civ, opp_unit_slug, team1_gold_gained
  FROM matchup_battles
  WHERE my_civ='Mapuche' AND my_unit_slug='elite_bolas_rider_mapuche'
    AND scale='30v30' AND winner=1
  ORDER BY team1_gold_gained DESC LIMIT 5
\"\"\"):
    print(dict(r))
"
```

Expected: Mapuche Bolas Rider wins typically show team1_gold_gained > 0 (3 × kills).

- [ ] **Step 5: No commit needed (data file commit happens in Task 16)**

---

## Task 15: Run derivers and verify output sanity

**Goal:** Both derivers produce expected output. Rankings match prior tier; advisor returns sensible recs.

**Files:** none modified — execution step.

- [ ] **Step 1: Run unit-rankings deriver**

Run: `python3 -m webapp.derive_unit_rankings 2>&1 | tail -3`
Expected: "Inserted N rows into derived_data.battle_scores" with N ≈ 19,000.

- [ ] **Step 2: Run advisor deriver**

Run: `python3 -m webapp.derive_advisor_recs 2>&1 | tail -3`
Expected: "Inserted N advisor recommendations" with N ≈ 5,500 (53 civs × 52 opp × 2 top recs).

- [ ] **Step 3: Sanity check ranking results**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('webapp/derived_data.db')
print('Top 5 stable_effectiveness (knight line):')
for r in c.execute(\"SELECT civ_name, unit_slug, score_value FROM battle_scores WHERE score_type='stable_effectiveness' AND age='imperial' AND line_slug='knight' ORDER BY score_value DESC LIMIT 5\"):
    print(' ', r)
print('Aztec Jaguar anti_trash:')
for r in c.execute(\"SELECT score_value FROM battle_scores WHERE civ_name='Aztecs' AND unit_slug='elite_jaguar_warrior_aztecs' AND score_type='anti_trash'\"):
    print(' ', r[0])
"
```

Expected: Lithuanian Leitis ≈ 100, Slav Boyar high. Aztec Jaguar anti_trash > 50.

- [ ] **Step 4: Sanity check advisor**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('webapp/derived_data.db')
for r in c.execute(\"SELECT rec_rank, unit_slug, score FROM advisor_recommendations WHERE civ='Aztecs' AND opponent='Britons' AND rec_type='top' ORDER BY rec_rank\"):
    print(r)
"
```

Expected: 2 rows, Eagle Warrior (or similar mobile counter) ranks high.

- [ ] **Step 5: No commit needed yet — wait until app.py cutover (Task 16) so we commit a working state**

---

## Task 16: Cut over `app.py` to read from `derived_data.db`

**Goal:** Wherever `app.py` queries `battle_scores`, point it at `derived_data.db` instead of `aoe2_reference.db`. Add a function returning advisor recommendations for the matchup advisor route.

**Files:**
- Modify: `webapp/app.py`

- [ ] **Step 1: Find current battle_scores reads**

Run: `grep -n "battle_scores\|get_ref_db\|MATCHUP_DB\|matchup_combos" webapp/app.py | head -30`

- [ ] **Step 2: Add a derived_db connection helper**

In `webapp/app.py`, near `get_ref_db()`, add:

```python
DERIVED_DB_PATH = os.path.join(os.path.dirname(__file__), "derived_data.db")

def get_derived_db():
    conn = sqlite3.connect(DERIVED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

- [ ] **Step 3: Repoint every `battle_scores` query**

For each occurrence of `battle_scores` in `app.py` (~5 locations near lines 580, 853, 867 per earlier grep), change the connection from `get_ref_db()` to `get_derived_db()`. The SQL itself stays identical — table name and columns are the same.

Specifically:
- Around `app.py:580` — `_db_role_scores` building loop
- Around `app.py:853` — `score_value, median_delta` lookup
- Around `app.py:867` — `FROM battle_scores bs` join

For the JOIN at line 867, `bs` joins against ref_units in the same SQL. SQLite can attach a second DB. Replace the join with a two-step lookup: fetch ref data first, then look up scores in derived_db, then merge in Python. (If the join is performance-critical, use `ATTACH DATABASE` instead.)

- [ ] **Step 4: Add advisor recommendation route (optional — only if there's an existing one to repoint)**

Run: `grep -n "matchup_combos\|advisor\|recommendations" webapp/app.py | head`

If there's a route like `/api/matchup-advisor/...`, repoint it to read from `advisor_recommendations` in `derived_data.db`. Schema: `(civ, opponent, rec_type, rec_rank, unit_slug, unit_name, score)`.

- [ ] **Step 5: Smoke-test the webapp**

Run: start the dev server and load `/units` in browser; check that rankings still display correctly. Use the existing preview server tool if available.

- [ ] **Step 6: Commit**

```bash
git add webapp/app.py webapp/matchup_db.db webapp/derived_data.db
git commit -m "feat(app): read battle_scores + advisor recs from derived_data.db"
```

---

## Task 17: Delete legacy DBs, scripts, and dead code

**Goal:** Remove the old `matchup_combos.db`, `matchup_combos_real.db`, `yardstick_battles.db`, plus all scripts that wrote to or read from them.

**Files:**
- Delete: `webapp/matchup_combos.db`, `webapp/matchup_combos_real.db`, `webapp/yardstick_battles.db`
- Delete: `webapp/yardstick_db.py`, `webapp/run_yardstick_battles.py`, `webapp/derive_scores_from_yardsticks.py`
- Delete: `webapp/generate_matchup_db.py`, `webapp/generate_matchup_db_real.py`
- Delete: `webapp/derive_battle_scores_from_matchups.py`, `webapp/compare_matchup_dbs.py`, `webapp/migrate_matchup_db_outcomes.py`
- Delete: `tests/test_yardstick_score_derivation.py` (replaced by `test_unit_ranking_derive.py`)
- Modify: `analysis/generate_main_db.py` if it referenced any of the deleted scripts (likely not — it writes `aoe2_units.db`)
- Modify: `CLAUDE.md` to update the build pipeline section

- [ ] **Step 1: Verify nothing live references the deleted scripts**

Run: `grep -rn "yardstick_db\|run_yardstick_battles\|derive_scores_from_yardsticks\|generate_matchup_db\|derive_battle_scores_from_matchups\|compare_matchup_dbs\|migrate_matchup_db_outcomes\|matchup_combos.db\|matchup_combos_real.db\|yardstick_battles.db" --include="*.py" --include="*.md" 2>&1 | grep -v "^docs/superpowers" | head -30`

Expected: only references in docs (specs/plans) and the files themselves. If any live `webapp/*.py` still references them, fix that before deleting.

- [ ] **Step 2: Delete the files**

```bash
rm webapp/matchup_combos.db webapp/matchup_combos_real.db webapp/yardstick_battles.db
rm webapp/yardstick_db.py webapp/run_yardstick_battles.py webapp/derive_scores_from_yardsticks.py
rm webapp/generate_matchup_db.py webapp/generate_matchup_db_real.py
rm webapp/derive_battle_scores_from_matchups.py webapp/compare_matchup_dbs.py webapp/migrate_matchup_db_outcomes.py
rm tests/test_yardstick_score_derivation.py
```

- [ ] **Step 3: Update CLAUDE.md build pipeline section**

In `CLAUDE.md`, find the "Build Pipeline" section and replace the relevant lines:

```markdown
## Build Pipeline (run in order when game data or configs change)

```bash
python3 -m extraction.run                      # ~10s — empires2_x2_p1.dat -> extraction/extracted_data/*.json
python3 -m analysis.generate_reference         # ~30s -> webapp/aoe2_reference.db (full audit trail)
python3 -m analysis.generate_main_db           # ~2s  -> webapp/aoe2_units.db   (flat unit_stats table)
pypy3 -m webapp.run_matchup_battles            # ~3.6h first run, seconds incremental -> webapp/matchup_db.db
python3 -m webapp.derive_unit_rankings         # ~30s -> derived_data.battle_scores
python3 -m webapp.derive_advisor_recs          # ~30s -> derived_data.advisor_recommendations
```
```

Also update the "Cross-File Sync Rules" section: remove the line about "Battle scores go stale after any simulation logic or stat change — rerun `compute_battle_scores.py`" (replace with mention of `run_matchup_battles.py`).

- [ ] **Step 4: Run all tests to confirm nothing broke**

Run: `pytest 2>&1 | tail -10`
Expected: ALL PASS (no missing modules, no broken imports).

- [ ] **Step 5: Smoke-test the webapp once more**

Load `/units` in browser; verify rankings still render correctly post-cleanup.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: delete legacy matchup DBs and scripts after consolidation"
```

---

## Task 18: Move `battle_scores` table out of `aoe2_reference.db`

**Goal:** Drop the `battle_scores` table from `aoe2_reference.db` so reference DB is purely reference data.

**Files:**
- Modify: `webapp/aoe2_reference.db` (drop table)
- Modify: `analysis/generate_reference.py` if it creates `battle_scores`

- [ ] **Step 1: Check if `generate_reference.py` creates the table**

Run: `grep -n "battle_scores" analysis/generate_reference.py`

If it does, REMOVE those lines (table creation, any inserts). The table now lives in `derived_data.db` and is owned by the derivers.

- [ ] **Step 2: Drop the legacy table from existing reference DB**

```bash
python3 -c "
import sqlite3
c = sqlite3.connect('webapp/aoe2_reference.db')
c.execute('DROP TABLE IF EXISTS battle_scores')
c.commit()
c.close()
print('Dropped battle_scores from aoe2_reference.db')
"
```

- [ ] **Step 3: Verify the webapp still works**

Reload `/units` in browser. All score columns should still populate (they read from `derived_data.db` now).

- [ ] **Step 4: Commit**

```bash
git add analysis/generate_reference.py webapp/aoe2_reference.db
git commit -m "chore: drop battle_scores from aoe2_reference.db (now in derived_data.db)"
```

---

## Done

After Task 18, the system has:

- **One raw-data DB** (`matchup_db.db`) with full per-resource sim outcomes for every eligible imperial unit pair × scale.
- **One derived-data DB** (`derived_data.db`) with `battle_scores` and `advisor_recommendations`, both rebuildable from raw in seconds.
- **One sim runner** (`run_matchup_battles.py`, PyPy-required) that supersedes both prior runners.
- **Two derivers** (`derive_unit_rankings.py`, `derive_advisor_recs.py`) replacing the prior fragmented logic.
- Sim engine extended to track per-resource losses, per-resource kill bonuses, and net value lost.
- Three legacy DBs and seven legacy scripts deleted.
- Mapuche mounted units' "+3 gold per kill" civ bonus correctly modeled.
- Tarkan and Wu Fire Archer correctly classified.

Routine refresh after a sim tweak:
```bash
pypy3 -m webapp.run_matchup_battles            # fast — only re-sims invalidated rows
python3 -m webapp.derive_unit_rankings         # seconds
python3 -m webapp.derive_advisor_recs          # seconds
```
