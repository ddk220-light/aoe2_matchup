# Pool Ranking Redesign — DB Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new SQLite database (`webapp/pool_scores.db`) that stores six scores per combat unit (3 axes × 2 scales) plus shape descriptors, derived from `matchup_db.matchup_battles`. UI integration is out of scope for this stage.

**Architecture:** A pure-function library (`pool_scores_lib.py`) holds atomic per-battle scoring (HP, cost, speed), λ=2 loss aversion, line/pool lookup, and aggregation primitives. A thin orchestration script (`derive_pool_scores.py`) iterates `(civ, unit_slug, scale, axis)` over the matchup DB, calls the lib, and writes one row per combination to `pool_scores.db`. Existing `derived_data.db` and `derive_unit_rankings.py` are untouched.

**Tech Stack:** Python 3, SQLite (stdlib `sqlite3`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-28-pool-ranking-redesign-design.md`

---

## File Structure

| File | Status | Responsibility |
| --- | --- | --- |
| `webapp/pool_scores_lib.py` | Create | Pure functions: λ-transform, axis scores, line/pool lookup, aggregation, shape descriptors |
| `webapp/pool_scores_db.py` | Create | SQLite schema + row writer for `pool_scores.db` |
| `webapp/derive_pool_scores.py` | Create | CLI orchestration — reads matchup_db, writes pool_scores.db |
| `tests/test_pool_scores_lib.py` | Create | Unit tests for lib functions |
| `tests/test_pool_scores_db.py` | Create | Schema + writer tests |
| `tests/test_pool_scores_integration.py` | Create | End-to-end Berserker regression test against real `webapp/matchup_db.db` |
| `webapp/pool_scores.db` | Generated | Output artifact, not committed |

---

## Constants and Conventions Used Throughout

```python
LAMBDA = 2.0          # loss aversion multiplier
T_MAX_SECONDS = 120.0 # speed cap

POOL_ROLES = {
    "infantry": {
        "GC": ["militia", "knight", "archer"],
        "AC": ["knight", "camel", "steppe_lancer", "elephant"],
        "AT": ["spear", "skirmisher", "light_cav"],
    },
    "stable": {
        "GC": ["militia", "knight", "archer"],
        "AC": ["knight", "camel", "steppe_lancer", "elephant", "light_cav"],
    },
    "archer": {
        "GC": ["militia", "knight", "archer"],
        "AA": ["archer", "skirmisher", "cav_archer", "gunpowder"],
    },
}
POOL_WEIGHTS = {
    "infantry": {"GC": 0.70, "AC": 0.15, "AT": 0.15},
    "stable":   {"GC": 0.70, "AC": 0.30},
    "archer":   {"GC": 0.70, "AA": 0.30},
}
BUILDING_TO_POOL = {
    "Barracks": "infantry",
    "Stable": "stable",
    "Archery Range": "archer",
}
```

**`matchup_battles` row convention:** `team1` = my side, `team2` = opp side (verified in spec by sampling rows). `winner` is `1` if I won, `2` if I lost, `0` if tie/timeout.

---

## Task 1: Module scaffolding + loss aversion

**Files:**
- Create: `webapp/pool_scores_lib.py`
- Create: `tests/test_pool_scores_lib.py`

- [ ] **Step 1: Write failing tests for `apply_loss_aversion`**

`tests/test_pool_scores_lib.py`:
```python
"""Unit tests for webapp/pool_scores_lib.py."""
from pool_scores_lib import apply_loss_aversion


def test_loss_aversion_positive_unchanged():
    assert apply_loss_aversion(25.0) == 25.0
    assert apply_loss_aversion(100.0) == 100.0


def test_loss_aversion_zero_unchanged():
    assert apply_loss_aversion(0.0) == 0.0


def test_loss_aversion_negative_doubled_default():
    assert apply_loss_aversion(-25.0) == -50.0
    assert apply_loss_aversion(-100.0) == -200.0


def test_loss_aversion_custom_lambda():
    assert apply_loss_aversion(-25.0, lam=3.0) == -75.0
    assert apply_loss_aversion(+25.0, lam=3.0) == +25.0
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: FAIL with `ImportError: No module named 'pool_scores_lib'` (or similar).

- [ ] **Step 3: Create the module with the function**

`webapp/pool_scores_lib.py`:
```python
"""Pure functions for the pool-scores derivation pipeline.

No I/O: every function takes plain values or in-memory collections and
returns plain values. The orchestrator (derive_pool_scores.py) is
responsible for reading from matchup_db and writing to pool_scores.db.
"""

LAMBDA = 2.0
T_MAX_SECONDS = 120.0


def apply_loss_aversion(x: float, lam: float = LAMBDA) -> float:
    """Multiply negative values by `lam`; leave non-negative values unchanged.

    Locked-in design (see spec §"Loss aversion"). Asymmetric: widens the
    gap between losses and wins of the same magnitude, but preserves
    linearity on each side of zero so weighted aggregation works.
    """
    return x if x >= 0 else lam * x
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): scaffold lib module + loss-aversion transform"
```

---

## Task 2: HP-axis atomic score

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

- [ ] **Step 1: Append failing tests for `hp_score`**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import hp_score


def test_hp_score_my_decisive_win():
    # I (team1) end at 80%, opp dead. winner=1.
    assert hp_score(0.8, 0.0, 1) == 80.0


def test_hp_score_my_loss():
    # I die, opp at 50%. winner=2 -> negative for me.
    assert hp_score(0.0, 0.5, 2) == -50.0


def test_hp_score_tie_returns_zero():
    assert hp_score(0.3, 0.3, 0) == 0.0


def test_hp_score_marginal_win():
    # I edge out at 5%, opp dead. winner=1.
    assert hp_score(0.05, 0.0, 1) == 5.0
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py::test_hp_score_my_decisive_win -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `hp_score`**

Append to `webapp/pool_scores_lib.py`:
```python
def hp_score(team1_hp_pct: float, team2_hp_pct: float, winner: int) -> float:
    """Raw signed_score for a battle, signed from team1's perspective.

    +100 = team1 won at full HP with opp dead.
    -100 = team1 dead, opp at full HP.
       0 = tie / no decision.
    """
    if winner == 0:
        return 0.0
    if winner == 1:
        return 100.0 * (team1_hp_pct - team2_hp_pct)
    if winner == 2:
        return -100.0 * (team2_hp_pct - team1_hp_pct)
    raise ValueError(f"unexpected winner value: {winner!r}")
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): hp_score atomic axis function"
```

---

## Task 3: Resource cost atomic score + weighted_cost

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import weighted_cost, cost_score


def test_weighted_cost_champion_60f_20g():
    # Champion: 60 food, 20 gold -> 60 + 30 = 90
    assert weighted_cost(food=60, wood=0, gold=20) == 90.0


def test_weighted_cost_archer_25f_45w():
    # Generic crossbow: 25f + 45w -> 25 + 36 = 61
    assert weighted_cost(food=25, wood=45, gold=0) == 61.0


def test_weighted_cost_handles_none_inputs():
    # Some unit costs come back None for missing resources; treat as 0.
    assert weighted_cost(food=None, wood=None, gold=None) == 0.0


def test_cost_score_clean_win():
    # I won at 100% HP (lost nothing), opp dead. Cost = my_spent = 0.
    assert cost_score(t1_hp=1.0, t2_hp=0.0, winner=1,
                      my_total_cost=2850, opp_total_cost=2700) == 0.0


def test_cost_score_costly_win():
    # I won at 40% HP. Cost = my_total * (1-0.4) = 2850 * 0.6 = 1710.
    assert cost_score(t1_hp=0.4, t2_hp=0.0, winner=1,
                      my_total_cost=2850, opp_total_cost=2700) == pytest.approx(1710.0)


def test_cost_score_loss_takes_opp_to_30pct():
    # I lost; took opp to 30%. Cost = lambda * (my_total + opp_remaining)
    #   = 2 * (2850 + 2700*0.3) = 2 * (2850 + 810) = 7320.
    assert cost_score(t1_hp=0.0, t2_hp=0.3, winner=2,
                      my_total_cost=2850, opp_total_cost=2700) == pytest.approx(7320.0)


def test_cost_score_total_wipe_loss():
    # Wipe loss, opp at 100%. Cost = 2 * (2850 + 2700) = 11100.
    assert cost_score(t1_hp=0.0, t2_hp=1.0, winner=2,
                      my_total_cost=2850, opp_total_cost=2700) == pytest.approx(11100.0)


def test_cost_score_tie_no_lambda():
    # Tie: cost = my_spent + opp_remaining, no lambda multiplier.
    assert cost_score(t1_hp=0.5, t2_hp=0.5, winner=0,
                      my_total_cost=100, opp_total_cost=100) == pytest.approx(100.0)
```

Add `import pytest` at top of test file if not already present.

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v -k "weighted_cost or cost_score"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `weighted_cost` and `cost_score`**

Append to `webapp/pool_scores_lib.py`:
```python
def weighted_cost(food: float | None, wood: float | None, gold: float | None) -> float:
    """Resource cost with gold weighted higher.

    Mirrors `_calc_weighted_cost` in webapp/best_units.py:904 — same
    coefficients used by the existing 3k cost-matched scenarios.
    """
    return 0.8 * (wood or 0) + (food or 0) + 1.5 * (gold or 0)


def cost_score(t1_hp: float, t2_hp: float, winner: int,
               my_total_cost: float, opp_total_cost: float,
               lam: float = LAMBDA) -> float:
    """Per-battle resource cost from team1's perspective. Higher = worse.

    Cost framing per spec §"Resource cost axis":
      win:  cost = my_spent
      loss: cost = lam * (my_spent + opp_remaining)
      tie:  cost = my_spent + opp_remaining   (no lambda)
    """
    my_spent = my_total_cost * (1.0 - t1_hp)
    opp_remaining = opp_total_cost * t2_hp
    if winner == 1:
        return my_spent
    if winner == 2:
        return lam * (my_spent + opp_remaining)
    return my_spent + opp_remaining
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): weighted_cost + cost_score atomic axis"
```

---

## Task 4: Speed atomic score

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import speed_score


def test_speed_score_instant_win_max_score():
    # Win at 0s -> +100.
    assert speed_score(winner=1, game_time_s=0.0) == 100.0


def test_speed_score_60s_win_half_score():
    # Win at 60s with T_MAX=120 -> +100 * (1 - 60/120) = +50.
    assert speed_score(winner=1, game_time_s=60.0) == pytest.approx(50.0)


def test_speed_score_at_or_past_t_max_clipped_to_zero():
    assert speed_score(winner=1, game_time_s=120.0) == 0.0
    assert speed_score(winner=1, game_time_s=200.0) == 0.0


def test_speed_score_fast_loss_doubled_negative():
    # Loss at 0s -> -lambda*100 = -200.
    assert speed_score(winner=2, game_time_s=0.0) == -200.0


def test_speed_score_60s_loss():
    # Loss at 60s -> -2 * 100 * 0.5 = -100.
    assert speed_score(winner=2, game_time_s=60.0) == pytest.approx(-100.0)


def test_speed_score_tie_returns_zero():
    assert speed_score(winner=0, game_time_s=30.0) == 0.0
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v -k "speed_score"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `speed_score`**

Append to `webapp/pool_scores_lib.py`:
```python
def speed_score(winner: int, game_time_s: float,
                t_max: float = T_MAX_SECONDS,
                lam: float = LAMBDA) -> float:
    """Linear speed score signed by win/loss.

    Spec §"Speed-to-win axis":
      win:  +100 * max(0, 1 - t/T_MAX)
      loss: -lam * 100 * max(0, 1 - t/T_MAX)
      tie:  0
    """
    factor = max(0.0, 1.0 - game_time_s / t_max)
    if winner == 1:
        return 100.0 * factor
    if winner == 2:
        return -lam * 100.0 * factor
    return 0.0
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): speed_score atomic axis"
```

---

## Task 5: Line membership and pool lookup

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import line_imperial_slugs, unit_to_pool
from unit_lines import UNIT_LINES


def test_line_imperial_slugs_militia_includes_champion_and_uniques():
    slugs = line_imperial_slugs(UNIT_LINES, "militia")
    assert "champion" in slugs
    assert "elite_berserk_vikings" in slugs
    assert "elite_huskarl_goths" in slugs
    assert "elite_jaguar_warrior_aztecs" in slugs


def test_line_imperial_slugs_archer_includes_arbalester_and_plumed():
    slugs = line_imperial_slugs(UNIT_LINES, "archer")
    assert "arbalester" in slugs
    assert "elite_plumed_archer_mayans" in slugs


def test_line_imperial_slugs_elephant_includes_extra_imperial():
    # elephant line has extra_imperial_slugs = ['elite_ele_archer']
    slugs = line_imperial_slugs(UNIT_LINES, "elephant")
    assert "elite_elephant" in slugs
    assert "elite_ele_archer" in slugs


def test_unit_to_pool_champion_is_infantry():
    assert unit_to_pool(UNIT_LINES, "champion") == "infantry"


def test_unit_to_pool_berserker_is_infantry():
    assert unit_to_pool(UNIT_LINES, "elite_berserk_vikings") == "infantry"


def test_unit_to_pool_paladin_is_stable():
    assert unit_to_pool(UNIT_LINES, "paladin") == "stable"


def test_unit_to_pool_cataphract_is_stable():
    assert unit_to_pool(UNIT_LINES, "elite_cataphract_byzantines") == "stable"


def test_unit_to_pool_arbalester_is_archer():
    assert unit_to_pool(UNIT_LINES, "arbalester") == "archer"


def test_unit_to_pool_unknown_returns_none():
    assert unit_to_pool(UNIT_LINES, "trebuchet") is None
    assert unit_to_pool(UNIT_LINES, "totally_made_up_slug") is None
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v -k "line_imperial or unit_to_pool"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `line_imperial_slugs` and `unit_to_pool`**

Append to `webapp/pool_scores_lib.py`:
```python
BUILDING_TO_POOL = {
    "Barracks": "infantry",
    "Stable": "stable",
    "Archery Range": "archer",
}


def line_imperial_slugs(unit_lines: dict, line_key: str) -> set[str]:
    """All imperial-age slugs that map to a line, across all civs.

    Used to filter eligible OPPONENTS — who counts as 'in the militia
    line' when computing GC vs militia? Answer: champion + every elite
    unique unit listed under militia['unique_units'] + extra_imperial.
    """
    line = unit_lines[line_key]
    out: set[str] = set()
    if line.get("imperial_slug"):
        out.add(line["imperial_slug"])
    for s in line.get("extra_imperial_slugs") or []:
        out.add(s)
    for civ, val in (line.get("unique_units") or {}).items():
        if val is None:
            continue
        if isinstance(val, list):
            for pair in val:
                if pair and pair[1]:
                    out.add(pair[1])
        else:
            if val[1]:
                out.add(val[1])
    return {s for s in out if s}


def _all_line_slugs_including_castle(unit_lines: dict, line_key: str) -> set[str]:
    """Imperial slugs PLUS castle slugs and castle UU slugs.

    Used for unit_to_pool — a unit that only appears in matchup_db at
    its castle slug (e.g. cataphract_byzantines vs elite_cataphract_byzantines)
    still needs to be classifiable.
    """
    line = unit_lines[line_key]
    out: set[str] = set(line_imperial_slugs(unit_lines, line_key))
    if line.get("castle_slug"):
        out.add(line["castle_slug"])
    for s in line.get("extra_castle_slugs") or []:
        out.add(s)
    for civ, val in (line.get("unique_units") or {}).items():
        if val is None:
            continue
        if isinstance(val, list):
            for pair in val:
                if pair and pair[0]:
                    out.add(pair[0])
        else:
            if val[0]:
                out.add(val[0])
    return {s for s in out if s}


def unit_to_pool(unit_lines: dict, unit_slug: str) -> str | None:
    """Return 'infantry' / 'stable' / 'archer' / None for a unit slug.

    None is returned for siege/naval/monk/etc — units outside the three
    pools we score in this stage. Callers should skip such units.
    """
    for line_key, line in unit_lines.items():
        if unit_slug in _all_line_slugs_including_castle(unit_lines, line_key):
            return BUILDING_TO_POOL.get(line.get("building"))
    return None
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): line and pool lookup"
```

---

## Task 6: Within-line aggregation (dedup + mean)

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import dedup_mean


def test_dedup_mean_collapses_same_group():
    # Two values share group "G1"; first wins.
    values = [("G1", 80.0), ("G1", 100.0), ("G2", 50.0)]
    # G1 -> 80.0 (first seen), G2 -> 50.0; mean = 65.0
    assert dedup_mean(values) == pytest.approx(65.0)


def test_dedup_mean_empty_returns_none():
    assert dedup_mean([]) is None


def test_dedup_mean_all_same_group():
    values = [("G1", 10.0), ("G1", 20.0)]
    assert dedup_mean(values) == 10.0


def test_dedup_mean_unique_groups():
    values = [("a", 10.0), ("b", 20.0), ("c", 30.0)]
    assert dedup_mean(values) == 20.0
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v -k "dedup_mean"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `dedup_mean`**

Append to `webapp/pool_scores_lib.py`:
```python
def dedup_mean(group_value_pairs) -> float | None:
    """Collapse rows by dedup_group (first wins), return mean of survivors.

    `group_value_pairs` is an iterable of `(dedup_group, value)` tuples.
    Returns `None` if the input is empty.

    First-wins matches the existing fingerprint-dedup convention in
    `run_matchup_battles.py`; rows in the same group are simulator-
    identical so the choice is arbitrary.
    """
    by_group: dict[str, float] = {}
    for group, value in group_value_pairs:
        if group not in by_group:
            by_group[group] = value
    if not by_group:
        return None
    return sum(by_group.values()) / len(by_group)
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): dedup_mean aggregation primitive"
```

---

## Task 7: Pool-aware role weighting

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import (
    POOL_ROLES, POOL_WEIGHTS, final_score_for_pool,
)


def test_pool_roles_match_spec():
    assert set(POOL_ROLES) == {"infantry", "stable", "archer"}
    assert POOL_ROLES["infantry"]["AC"] == ["knight", "camel", "steppe_lancer", "elephant"]
    assert POOL_ROLES["stable"]["AC"] == ["knight", "camel", "steppe_lancer", "elephant", "light_cav"]
    assert POOL_ROLES["archer"]["AA"] == ["archer", "skirmisher", "cav_archer", "gunpowder"]


def test_pool_weights_sum_to_one():
    for pool, weights in POOL_WEIGHTS.items():
        assert abs(sum(weights.values()) - 1.0) < 1e-9, pool


def test_final_score_infantry():
    # 0.7*GC + 0.15*AC + 0.15*AT
    role_means = {"GC": -10.0, "AC": +50.0, "AT": +90.0}
    expected = 0.7 * -10.0 + 0.15 * 50.0 + 0.15 * 90.0  # = 14.0
    assert final_score_for_pool(role_means, "infantry") == pytest.approx(expected)


def test_final_score_stable():
    # 0.7*GC + 0.30*AC
    role_means = {"GC": +20.0, "AC": +40.0}
    expected = 0.7 * 20.0 + 0.30 * 40.0  # = 26.0
    assert final_score_for_pool(role_means, "stable") == pytest.approx(expected)


def test_final_score_archer():
    # 0.7*GC + 0.30*AA
    role_means = {"GC": +30.0, "AA": -10.0}
    expected = 0.7 * 30.0 + 0.30 * -10.0  # = 18.0
    assert final_score_for_pool(role_means, "archer") == pytest.approx(expected)


def test_final_score_missing_role_treated_as_zero():
    # If a role has no data, treat the role mean as 0 (don't reweight).
    role_means = {"GC": +50.0}  # missing AC
    expected = 0.7 * 50.0 + 0.30 * 0.0  # = 35.0
    assert final_score_for_pool(role_means, "stable") == pytest.approx(expected)
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v -k "pool_roles or pool_weights or final_score"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `POOL_ROLES`, `POOL_WEIGHTS`, `final_score_for_pool`**

Append to `webapp/pool_scores_lib.py`:
```python
POOL_ROLES = {
    "infantry": {
        "GC": ["militia", "knight", "archer"],
        "AC": ["knight", "camel", "steppe_lancer", "elephant"],
        "AT": ["spear", "skirmisher", "light_cav"],
    },
    "stable": {
        "GC": ["militia", "knight", "archer"],
        "AC": ["knight", "camel", "steppe_lancer", "elephant", "light_cav"],
    },
    "archer": {
        "GC": ["militia", "knight", "archer"],
        "AA": ["archer", "skirmisher", "cav_archer", "gunpowder"],
    },
}

POOL_WEIGHTS = {
    "infantry": {"GC": 0.70, "AC": 0.15, "AT": 0.15},
    "stable":   {"GC": 0.70, "AC": 0.30},
    "archer":   {"GC": 0.70, "AA": 0.30},
}


def final_score_for_pool(role_means: dict[str, float], pool: str) -> float:
    """Apply pool-specific role weights. Missing roles count as 0."""
    weights = POOL_WEIGHTS[pool]
    return sum(weights[r] * role_means.get(r, 0.0) for r in weights)
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): pool-aware role weighting"
```

---

## Task 8: Shape descriptors

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import compute_shape


def test_compute_shape_empty_input():
    s = compute_shape([])
    assert s == {"n": 0, "mean": 0.0, "stddev": 0.0,
                 "win_rate": 0.0, "decisive_win_rate": 0.0,
                 "big_win_rate": 0.0, "catastrophic_loss_rate": 0.0}


def test_compute_shape_basic():
    # 4 raw signed_scores: [+90, +60, +20, -70]
    # n=4, mean=25, win_rate=75% (>0), decisive=50% (>30),
    # big=50% (>50), cat_loss=25% (<-50)
    s = compute_shape([+90.0, +60.0, +20.0, -70.0])
    assert s["n"] == 4
    assert s["mean"] == pytest.approx(25.0)
    # population stddev: sqrt(mean of (x-25)^2) = sqrt((4225+1225+25+9025)/4)
    # = sqrt(14500/4) = sqrt(3625) ~= 60.21
    assert s["stddev"] == pytest.approx(60.2079, abs=1e-3)
    assert s["win_rate"] == pytest.approx(75.0)
    assert s["decisive_win_rate"] == pytest.approx(50.0)
    assert s["big_win_rate"] == pytest.approx(50.0)
    assert s["catastrophic_loss_rate"] == pytest.approx(25.0)


def test_compute_shape_all_wins():
    s = compute_shape([+10.0, +20.0, +30.0, +40.0])
    assert s["win_rate"] == 100.0
    assert s["catastrophic_loss_rate"] == 0.0


def test_compute_shape_all_catastrophic_losses():
    s = compute_shape([-90.0, -80.0])
    assert s["win_rate"] == 0.0
    assert s["catastrophic_loss_rate"] == 100.0
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v -k "compute_shape"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `compute_shape`**

Append to `webapp/pool_scores_lib.py`:
```python
def compute_shape(raw_signed_scores) -> dict:
    """Distribution descriptors over RAW signed_scores (not adjusted).

    Win/loss rates are computed from the raw HP-based signed_score so
    they describe the underlying battle outcomes regardless of which
    axis is being scored. Used to drive UI profile labels later.
    """
    values = list(raw_signed_scores)
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0.0, "stddev": 0.0,
                "win_rate": 0.0, "decisive_win_rate": 0.0,
                "big_win_rate": 0.0, "catastrophic_loss_rate": 0.0}
    mean_v = sum(values) / n
    var = sum((x - mean_v) ** 2 for x in values) / n
    return {
        "n": n,
        "mean": mean_v,
        "stddev": var ** 0.5,
        "win_rate": 100.0 * sum(1 for x in values if x > 0) / n,
        "decisive_win_rate": 100.0 * sum(1 for x in values if x > 30) / n,
        "big_win_rate": 100.0 * sum(1 for x in values if x > 50) / n,
        "catastrophic_loss_rate": 100.0 * sum(1 for x in values if x < -50) / n,
    }
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): shape descriptors over raw signed_scores"
```

---

## Task 9: DB schema and row writer

**Files:**
- Create: `webapp/pool_scores_db.py`
- Create: `tests/test_pool_scores_db.py`

- [ ] **Step 1: Write failing test for `create_db` schema**

`tests/test_pool_scores_db.py`:
```python
"""Tests for webapp/pool_scores_db.py."""
import sqlite3
from pool_scores_db import create_db, insert_score


def test_create_db_has_pool_scores_table(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    assert "pool_scores" in tables
    conn.close()


def test_pool_scores_columns_match_spec(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(pool_scores)")
    cols = {r[1]: r[2] for r in cur.fetchall()}
    expected = {
        "civ_name": "TEXT", "unit_slug": "TEXT", "pool": "TEXT",
        "scale": "TEXT", "axis": "TEXT",
        "final_score": "REAL", "gc": "REAL", "ac": "REAL",
        "at": "REAL", "aa": "REAL",
        "n": "INTEGER", "mean": "REAL", "stddev": "REAL",
        "win_rate": "REAL", "decisive_win_rate": "REAL",
        "big_win_rate": "REAL", "catastrophic_loss_rate": "REAL",
        "sim_version": "TEXT", "derived_at": "TEXT",
    }
    for col, ctype in expected.items():
        assert col in cols, f"missing column: {col}"
        assert cols[col] == ctype, f"{col}: expected {ctype}, got {cols[col]}"
    conn.close()


def test_insert_and_read_back(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    insert_score(conn, {
        "civ_name": "Vikings", "unit_slug": "elite_berserk_vikings",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 8.9, "gc": -6.8, "ac": -1.6, "at": 92.7, "aa": None,
        "n": 238, "mean": 35.2, "stddev": 59.5,
        "win_rate": 72.3, "decisive_win_rate": 64.3,
        "big_win_rate": 55.9, "catastrophic_loss_rate": 13.0,
        "sim_version": "ba893a3", "derived_at": "2026-04-28T00:00:00",
    })
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT final_score, gc, n FROM pool_scores WHERE unit_slug='elite_berserk_vikings'")
    row = cur.fetchone()
    assert row == (8.9, -6.8, 238)
    conn.close()


def test_insert_replaces_on_duplicate_key(tmp_path):
    db_path = tmp_path / "p.db"
    conn = create_db(str(db_path))
    payload = {
        "civ_name": "Vikings", "unit_slug": "elite_berserk_vikings",
        "pool": "infantry", "scale": "30v30", "axis": "hp",
        "final_score": 1.0, "gc": 0, "ac": 0, "at": 0, "aa": None,
        "n": 1, "mean": 0, "stddev": 0,
        "win_rate": 0, "decisive_win_rate": 0,
        "big_win_rate": 0, "catastrophic_loss_rate": 0,
        "sim_version": "v1", "derived_at": "t1",
    }
    insert_score(conn, payload)
    payload["final_score"] = 99.0
    insert_score(conn, payload)
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(final_score) FROM pool_scores")
    n, total = cur.fetchone()
    assert n == 1
    assert total == 99.0
    conn.close()
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_db.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Create `webapp/pool_scores_db.py`**

```python
"""SQLite schema + writer for the pool_scores derived database.

Single table: `pool_scores`, keyed by (civ_name, unit_slug, scale, axis).
Six rows per (civ, unit) — three axes × two scales.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS pool_scores (
    civ_name              TEXT NOT NULL,
    unit_slug             TEXT NOT NULL,
    pool                  TEXT NOT NULL,
    scale                 TEXT NOT NULL,
    axis                  TEXT NOT NULL,
    final_score           REAL NOT NULL,
    gc                    REAL,
    ac                    REAL,
    at                    REAL,
    aa                    REAL,
    n                     INTEGER NOT NULL,
    mean                  REAL NOT NULL,
    stddev                REAL NOT NULL,
    win_rate              REAL NOT NULL,
    decisive_win_rate     REAL NOT NULL,
    big_win_rate          REAL NOT NULL,
    catastrophic_loss_rate REAL NOT NULL,
    sim_version           TEXT,
    derived_at            TEXT NOT NULL,
    PRIMARY KEY (civ_name, unit_slug, scale, axis)
);

CREATE INDEX IF NOT EXISTS idx_pool_scores_pool_axis_scale
    ON pool_scores (pool, axis, scale);
"""


def create_db(path: str) -> sqlite3.Connection:
    """Open the DB at `path`, create the schema if it doesn't exist."""
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


_INSERT_SQL = """
INSERT OR REPLACE INTO pool_scores (
    civ_name, unit_slug, pool, scale, axis,
    final_score, gc, ac, at, aa,
    n, mean, stddev,
    win_rate, decisive_win_rate, big_win_rate, catastrophic_loss_rate,
    sim_version, derived_at
) VALUES (
    :civ_name, :unit_slug, :pool, :scale, :axis,
    :final_score, :gc, :ac, :at, :aa,
    :n, :mean, :stddev,
    :win_rate, :decisive_win_rate, :big_win_rate, :catastrophic_loss_rate,
    :sim_version, :derived_at
)
"""


def insert_score(conn: sqlite3.Connection, row: dict) -> None:
    """Upsert one row into pool_scores. Caller is responsible for commit."""
    conn.execute(_INSERT_SQL, row)
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_db.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_db.py tests/test_pool_scores_db.py
git commit -m "feat(pool-scores): pool_scores.db schema + writer"
```

---

## Task 10: Per-unit score derivation (pure-function entry point)

**Files:**
- Modify: `webapp/pool_scores_lib.py` (append)
- Modify: `tests/test_pool_scores_lib.py` (append)

This task wires the lib functions together into a single `derive_unit_scores` function that takes raw battle rows and returns the six output rows for a unit. Keeping it in the lib (vs. the orchestrator) keeps it test-friendly.

- [ ] **Step 1: Append failing test using synthetic rows**

Append to `tests/test_pool_scores_lib.py`:
```python
from pool_scores_lib import derive_unit_scores


def _row(opp_unit, winner=1, t1=0.8, t2=0.0, dedup="g",
         my_count=30, my_food=65, my_wood=0, my_gold=20,
         opp_count=30, opp_food=60, opp_wood=0, opp_gold=20,
         game_time=20.0):
    return {
        "opp_unit_slug": opp_unit, "winner": winner,
        "team1_hp_pct": t1, "team2_hp_pct": t2,
        "my_count": my_count, "my_cost_food": my_food,
        "my_cost_wood": my_wood, "my_cost_gold": my_gold,
        "opp_count": opp_count, "opp_cost_food": opp_food,
        "opp_cost_wood": opp_wood, "opp_cost_gold": opp_gold,
        "game_time_s": game_time, "dedup_group": dedup,
    }


def test_derive_unit_scores_synthetic_infantry():
    # Three deduped wins vs militia/knight/archer, one each.
    # All clean wins at 80% HP -> hp_score = +80, adjusted = +80.
    # GC mean = 80; AC and AT empty so means = 0.
    # final = 0.7*80 + 0.15*0 + 0.15*0 = 56.
    rows = [
        _row("champion", dedup="g1"),
        _row("paladin",  dedup="g2"),  # knight line
        _row("arbalester", dedup="g3"),
    ]
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=rows,
    )
    # Three axes -> three output rows for this scale.
    assert len(out) == 3
    by_axis = {r["axis"]: r for r in out}
    hp = by_axis["hp"]
    assert hp["pool"] == "infantry"
    assert hp["scale"] == "30v30"
    assert hp["gc"] == pytest.approx(80.0)
    assert hp["ac"] == pytest.approx(0.0)  # no AC opponents in input
    assert hp["at"] == pytest.approx(0.0)  # no AT opponents
    assert hp["aa"] is None  # archer-only
    assert hp["final_score"] == pytest.approx(0.7 * 80.0)
    assert hp["n"] == 3
    assert hp["win_rate"] == 100.0


def test_derive_unit_scores_dedup_collapses_duplicates():
    rows = [
        _row("champion", t1=0.8, dedup="g1"),
        _row("champion", t1=0.5, dedup="g1"),  # same group, ignored
        _row("champion", t1=0.0, winner=2, t2=0.5, dedup="g2"),
    ]
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=rows,
    )
    hp = next(r for r in out if r["axis"] == "hp")
    # Deduped to two raw HP scores: +80 (g1 first), -50 (g2).
    # Adjusted with lambda=2: +80 and -100. Militia-line mean = -10.
    # GC = avg of [militia=-10, knight=None, archer=None] = -10/1 = -10.
    # final = 0.7 * -10 + 0.15*0 + 0.15*0 = -7.
    assert hp["n"] == 2  # deduped count
    assert hp["gc"] == pytest.approx(-10.0)
    assert hp["final_score"] == pytest.approx(-7.0)


def test_derive_unit_scores_unknown_pool_returns_empty():
    # Unknown unit_slug -> not in any pool -> no rows produced.
    out = derive_unit_scores(
        civ="Whatever", unit_slug="totally_made_up",
        scale="30v30", rows=[_row("champion")],
    )
    assert out == []
```

- [ ] **Step 2: Run tests; verify failure**

Run: `pytest tests/test_pool_scores_lib.py -v -k "derive_unit_scores"`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `derive_unit_scores`**

Append to `webapp/pool_scores_lib.py`:
```python
import datetime
from collections import defaultdict
from unit_lines import UNIT_LINES


def _opponent_to_lines() -> dict[str, list[str]]:
    """Map every imperial-age opponent slug to the list of line keys it appears in.

    Cached on first call. Pre-computing avoids O(units × lines) scans
    inside the per-row hot loop.
    """
    out: dict[str, list[str]] = defaultdict(list)
    for line_key in UNIT_LINES:
        for slug in line_imperial_slugs(UNIT_LINES, line_key):
            out[slug].append(line_key)
    return dict(out)


_OPP_TO_LINES_CACHE: dict[str, list[str]] | None = None


def _opponent_lines(opp_slug: str) -> list[str]:
    global _OPP_TO_LINES_CACHE
    if _OPP_TO_LINES_CACHE is None:
        _OPP_TO_LINES_CACHE = _opponent_to_lines()
    return _OPP_TO_LINES_CACHE.get(opp_slug, [])


def derive_unit_scores(*, civ: str, unit_slug: str, scale: str,
                       rows: list[dict],
                       sim_version: str | None = None) -> list[dict]:
    """Derive 3 output rows (one per axis) for one (civ, unit, scale).

    `rows` is the list of matchup_battles rows for this unit at this
    scale. Each row must have the keys used by `_row()` in the tests.
    Returns an empty list if the unit's pool can't be determined
    (e.g. siege/naval/monk, out of scope for this stage).
    """
    pool = unit_to_pool(UNIT_LINES, unit_slug)
    if pool is None:
        return []

    role_def = POOL_ROLES[pool]
    # Bucket dedup_group -> per-axis value, per (line, role) pair.
    line_axis_values: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(
        lambda: {"hp": {}, "cost": {}, "speed": {}}
    )
    raw_signed_for_shape: dict[str, dict[str, float]] = {
        "hp": {}, "cost": {}, "speed": {},
    }

    for r in rows:
        opp_slug = r["opp_unit_slug"]
        opp_line_keys = _opponent_lines(opp_slug)
        if not opp_line_keys:
            continue

        my_total = r["my_count"] * weighted_cost(
            r["my_cost_food"], r["my_cost_wood"], r["my_cost_gold"])
        opp_total = r["opp_count"] * weighted_cost(
            r["opp_cost_food"], r["opp_cost_wood"], r["opp_cost_gold"])
        raw_hp = hp_score(r["team1_hp_pct"], r["team2_hp_pct"], r["winner"])
        adj_hp = apply_loss_aversion(raw_hp)
        cost = cost_score(r["team1_hp_pct"], r["team2_hp_pct"], r["winner"],
                          my_total, opp_total)
        speed = speed_score(r["winner"], r["game_time_s"])

        dedup = r["dedup_group"]

        # Track raw signed_score for shape descriptors (one per dedup group).
        for axis in ("hp", "cost", "speed"):
            raw_signed_for_shape[axis].setdefault(dedup, raw_hp)

        # Bucket per-axis adjusted value into every (line, role) it belongs to.
        for line_key in opp_line_keys:
            for role, lines in role_def.items():
                if line_key in lines:
                    line_axis_values[(line_key, role)]["hp"].setdefault(dedup, adj_hp)
                    line_axis_values[(line_key, role)]["cost"].setdefault(dedup, cost)
                    line_axis_values[(line_key, role)]["speed"].setdefault(dedup, speed)

    # Build per-axis output row.
    derived_at = datetime.datetime.utcnow().isoformat(timespec="seconds")
    out_rows = []
    for axis in ("hp", "cost", "speed"):
        # Per-line mean, then per-role mean across lines that had data.
        role_means: dict[str, float] = {}
        for role, lines in role_def.items():
            line_vals = []
            for line in lines:
                vals = line_axis_values.get((line, role), {}).get(axis, {})
                if vals:
                    line_vals.append(sum(vals.values()) / len(vals))
            if line_vals:
                role_means[role] = sum(line_vals) / len(line_vals)
            else:
                role_means[role] = 0.0

        final = final_score_for_pool(role_means, pool)
        # Shape over raw signed_scores (one per dedup group, all axes share).
        shape = compute_shape(raw_signed_for_shape[axis].values())

        out_rows.append({
            "civ_name": civ, "unit_slug": unit_slug,
            "pool": pool, "scale": scale, "axis": axis,
            "final_score": final,
            "gc": role_means.get("GC", 0.0) if "GC" in POOL_WEIGHTS[pool] else None,
            "ac": role_means.get("AC", 0.0) if "AC" in POOL_WEIGHTS[pool] else None,
            "at": role_means.get("AT", 0.0) if "AT" in POOL_WEIGHTS[pool] else None,
            "aa": role_means.get("AA", 0.0) if "AA" in POOL_WEIGHTS[pool] else None,
            "n": shape["n"], "mean": shape["mean"], "stddev": shape["stddev"],
            "win_rate": shape["win_rate"],
            "decisive_win_rate": shape["decisive_win_rate"],
            "big_win_rate": shape["big_win_rate"],
            "catastrophic_loss_rate": shape["catastrophic_loss_rate"],
            "sim_version": sim_version, "derived_at": derived_at,
        })
    return out_rows
```

- [ ] **Step 4: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_lib.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webapp/pool_scores_lib.py tests/test_pool_scores_lib.py
git commit -m "feat(pool-scores): derive_unit_scores wiring all axes/roles together"
```

---

## Task 11: Orchestration script

**Files:**
- Create: `webapp/derive_pool_scores.py`

- [ ] **Step 1: Implement orchestrator script**

`webapp/derive_pool_scores.py`:
```python
"""Derive pool scores for every (civ, unit_slug, scale) in matchup_db.

Run from the webapp/ directory (matches the project's existing
script-running convention — see CLAUDE.md):

    cd webapp && python derive_pool_scores.py

Or with explicit paths:

    cd webapp && python derive_pool_scores.py \\
        --matchup-db matchup_db.db --out pool_scores.db

For each combat unit in the three pools (infantry/stable/archer), writes
six rows to pool_scores.db: 3 axes (hp, cost, speed) × 2 scales (30v30, 3k).
Units outside those pools (siege, naval, monks) are skipped.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from collections import defaultdict

from pool_scores_lib import derive_unit_scores, unit_to_pool
from pool_scores_db import create_db, insert_score
from unit_lines import UNIT_LINES

_WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MATCHUP_DB = os.path.join(_WEBAPP_DIR, "matchup_db.db")
DEFAULT_OUT_DB = os.path.join(_WEBAPP_DIR, "pool_scores.db")

ROW_KEYS = (
    "opp_unit_slug", "winner", "team1_hp_pct", "team2_hp_pct",
    "my_count", "my_cost_food", "my_cost_wood", "my_cost_gold",
    "opp_count", "opp_cost_food", "opp_cost_wood", "opp_cost_gold",
    "game_time_s", "dedup_group",
)


def _fetch_unit_rows(matchup_conn: sqlite3.Connection,
                     civ: str, unit_slug: str, scale: str) -> list[dict]:
    cur = matchup_conn.cursor()
    cur.execute(f"""
        SELECT {", ".join(ROW_KEYS)}
        FROM matchup_battles
        WHERE my_civ = ? AND my_unit_slug = ? AND scale = ?
    """, (civ, unit_slug, scale))
    return [dict(zip(ROW_KEYS, r)) for r in cur.fetchall()]


def _list_unit_pairs(matchup_conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """All (civ, unit_slug) pairs that have at least one battle row."""
    cur = matchup_conn.cursor()
    cur.execute("""
        SELECT DISTINCT my_civ, my_unit_slug
        FROM matchup_battles
        ORDER BY my_civ, my_unit_slug
    """)
    return [(r[0], r[1]) for r in cur.fetchall()]


def _sim_version_for(matchup_conn: sqlite3.Connection,
                     civ: str, unit_slug: str) -> str | None:
    cur = matchup_conn.cursor()
    cur.execute("""
        SELECT sim_version FROM matchup_battles
        WHERE my_civ = ? AND my_unit_slug = ?
        LIMIT 1
    """, (civ, unit_slug))
    row = cur.fetchone()
    return row[0] if row else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--matchup-db", default=DEFAULT_MATCHUP_DB)
    p.add_argument("--out", default=DEFAULT_OUT_DB)
    args = p.parse_args(argv)

    matchup_conn = sqlite3.connect(args.matchup_db)
    out_conn = create_db(args.out)

    pairs = _list_unit_pairs(matchup_conn)
    written = 0
    skipped_no_pool = 0
    by_pool: dict[str, int] = defaultdict(int)

    for civ, unit_slug in pairs:
        if unit_to_pool(UNIT_LINES, unit_slug) is None:
            skipped_no_pool += 1
            continue
        sim_version = _sim_version_for(matchup_conn, civ, unit_slug)
        for scale in ("30v30", "3k"):
            rows = _fetch_unit_rows(matchup_conn, civ, unit_slug, scale)
            if not rows:
                continue
            out_rows = derive_unit_scores(
                civ=civ, unit_slug=unit_slug, scale=scale, rows=rows,
                sim_version=sim_version,
            )
            for row in out_rows:
                insert_score(out_conn, row)
                written += 1
                by_pool[row["pool"]] += 1
        out_conn.commit()

    matchup_conn.close()
    out_conn.close()

    print(f"Wrote {written} rows to {args.out}")
    print(f"  by pool: {dict(by_pool)}")
    print(f"  skipped (no pool): {skipped_no_pool} (civ, unit) pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-run on the real matchup_db**

Run: `cd D:/AI/aoe2-unit-analyzer/webapp && python derive_pool_scores.py`

Expected output similar to:
```
Wrote NNNN rows to webapp/pool_scores.db
  by pool: {'infantry': ..., 'stable': ..., 'archer': ...}
  skipped (no pool): NN (civ, unit) pairs
```

It must complete without exception. Row count is in the thousands; exact value depends on how many civs are batched.

- [ ] **Step 3: Sanity-check the output**

Run:
```bash
sqlite3 D:/AI/aoe2-unit-analyzer/webapp/pool_scores.db \
  "SELECT pool, axis, scale, COUNT(*) FROM pool_scores GROUP BY pool, axis, scale ORDER BY pool, axis, scale;"
```

Expected: each (pool, axis, scale) combination has roughly equal row counts (since every (civ, unit, scale) yields one row per axis). Three pools × three axes × two scales = 18 rows in this group-by output, all positive.

- [ ] **Step 4: Commit**

```bash
git add webapp/derive_pool_scores.py
git commit -m "feat(pool-scores): orchestration script writes pool_scores.db"
```

---

## Task 12: Berserker regression integration test

**Files:**
- Create: `tests/test_pool_scores_integration.py`

This test pins the locked-in reference values for Viking Elite Berserk against a small tolerance, so future changes to the lib or orchestrator are caught.

- [ ] **Step 1: Write the regression test**

`tests/test_pool_scores_integration.py`:
```python
"""End-to-end regression test: derived scores for Viking Elite Berserk
must match the locked-in reference values from the spec.

Reads the real `webapp/matchup_db.db` (large file, not in tests fixtures)
and is skipped if that file isn't present. This is the canonical guardrail
that future refactors must preserve.
"""
import os
import pytest
import sqlite3

from derive_pool_scores import _fetch_unit_rows
from pool_scores_lib import derive_unit_scores

MATCHUP_DB = os.path.join(
    os.path.dirname(__file__), "..", "webapp", "matchup_db.db",
)


@pytest.fixture(scope="module")
def berserker_rows_30v30():
    if not os.path.exists(MATCHUP_DB):
        pytest.skip(f"{MATCHUP_DB} not present")
    conn = sqlite3.connect(MATCHUP_DB)
    rows = _fetch_unit_rows(conn, "Vikings", "elite_berserk_vikings", "30v30")
    conn.close()
    return rows


@pytest.fixture(scope="module")
def berserker_rows_3k():
    if not os.path.exists(MATCHUP_DB):
        pytest.skip(f"{MATCHUP_DB} not present")
    conn = sqlite3.connect(MATCHUP_DB)
    rows = _fetch_unit_rows(conn, "Vikings", "elite_berserk_vikings", "3k")
    conn.close()
    return rows


def _by_axis(out_rows):
    return {r["axis"]: r for r in out_rows}


def test_berserker_pop_hp_score(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    assert hp["pool"] == "infantry"
    assert hp["final_score"] == pytest.approx(8.9, abs=0.5)
    assert hp["gc"] == pytest.approx(-6.8, abs=0.5)
    assert hp["ac"] == pytest.approx(-1.6, abs=0.5)
    assert hp["at"] == pytest.approx(92.7, abs=0.5)


def test_berserker_cost_hp_score(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    hp = _by_axis(out)["hp"]
    assert hp["final_score"] == pytest.approx(31.6, abs=0.5)
    assert hp["gc"] == pytest.approx(17.4, abs=0.5)
    assert hp["ac"] == pytest.approx(36.8, abs=0.5)
    assert hp["at"] == pytest.approx(92.9, abs=0.5)


def test_berserker_pop_cost_axis(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    cost = _by_axis(out)["cost"]
    assert cost["final_score"] == pytest.approx(3961.8, abs=10.0)


def test_berserker_cost_cost_axis(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    cost = _by_axis(out)["cost"]
    assert cost["final_score"] == pytest.approx(2506.9, abs=10.0)


def test_berserker_pop_speed_axis(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    sp = _by_axis(out)["speed"]
    assert sp["final_score"] == pytest.approx(1.20, abs=0.5)


def test_berserker_cost_speed_axis(berserker_rows_3k):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="3k", rows=berserker_rows_3k,
    )
    sp = _by_axis(out)["speed"]
    assert sp["final_score"] == pytest.approx(26.60, abs=0.5)


def test_berserker_shape_descriptors_pop(berserker_rows_30v30):
    out = derive_unit_scores(
        civ="Vikings", unit_slug="elite_berserk_vikings",
        scale="30v30", rows=berserker_rows_30v30,
    )
    hp = _by_axis(out)["hp"]
    # Spec reference: n=238, mean ~+35.2, win-rate ~72%, cat-loss ~13%.
    assert hp["n"] >= 200  # full population, exact n depends on dedup
    assert hp["win_rate"] == pytest.approx(72.3, abs=2.0)
    assert hp["catastrophic_loss_rate"] == pytest.approx(13.0, abs=2.0)
```

- [ ] **Step 2: Run tests; verify pass**

Run: `pytest tests/test_pool_scores_integration.py -v`
Expected: all PASS (or all SKIP if matchup_db.db is absent).

- [ ] **Step 3: Run full test suite to confirm nothing else broke**

Run: `pytest -q`
Expected: previously-passing tests still pass; new tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pool_scores_integration.py
git commit -m "test(pool-scores): pin Berserker reference values across all 6 scores"
```

---

## Task 13: Final verification — run pipeline end-to-end and inspect

**Files:** none modified.

This task is a manual check, not code. The goal is to confirm the produced DB looks right before declaring the stage done.

- [ ] **Step 1: Re-run the script after all earlier tasks are complete**

```bash
cd D:/AI/aoe2-unit-analyzer/webapp
rm -f pool_scores.db   # fresh DB
python derive_pool_scores.py
```

- [ ] **Step 2: Verify row counts per (pool, axis, scale)**

Run:
```bash
sqlite3 webapp/pool_scores.db \
  "SELECT pool, axis, scale, COUNT(*) FROM pool_scores GROUP BY pool, axis, scale ORDER BY pool, axis, scale;"
```

Expected: 18 rows, all positive. Within a pool, all (axis, scale) pairs should share the same row count (each unit produces one row per axis × scale). Different pools have different row counts because they have different numbers of units.

- [ ] **Step 3: Spot-check Berserker row in the DB**

Run:
```bash
sqlite3 webapp/pool_scores.db \
  "SELECT scale, axis, ROUND(final_score, 2), ROUND(gc, 2), ROUND(ac, 2), ROUND(at, 2), n
   FROM pool_scores
   WHERE civ_name='Vikings' AND unit_slug='elite_berserk_vikings'
   ORDER BY scale, axis;"
```

Expected (within ±0.5 due to dedup ordering):
```
30v30|cost|3961.8|...|...|...|238
30v30|hp|8.9|-6.8|-1.6|92.7|238
30v30|speed|1.2|...|...|...|238
3k|cost|2506.9|...|...|...|238
3k|hp|31.6|17.4|36.8|92.9|238
3k|speed|26.6|...|...|...|238
```

- [ ] **Step 4: Verify three-pool coverage**

Run:
```bash
sqlite3 webapp/pool_scores.db \
  "SELECT DISTINCT pool FROM pool_scores;"
```

Expected: three rows: `infantry`, `stable`, `archer`.

- [ ] **Step 5: Spot-check at least one unit per other pool**

For stable pool — pick a paladin unit:
```bash
sqlite3 webapp/pool_scores.db \
  "SELECT scale, axis, ROUND(final_score, 2), ROUND(gc, 2), ROUND(ac, 2), at, aa
   FROM pool_scores
   WHERE civ_name='Franks' AND unit_slug='paladin'
   ORDER BY scale, axis;"
```

Expected: `at` and `aa` are NULL (stable pool doesn't use them); `gc` and `ac` are populated.

For archer pool — pick an arbalester:
```bash
sqlite3 webapp/pool_scores.db \
  "SELECT scale, axis, ROUND(final_score, 2), ROUND(gc, 2), ac, ROUND(aa, 2), at
   FROM pool_scores
   WHERE civ_name='Britons' AND unit_slug='arbalester'
   ORDER BY scale, axis;"
```

Expected: `ac` and `at` are NULL; `gc` and `aa` are populated.

- [ ] **Step 6: No commit — this is a verification step**

If any of the above checks fail, file a bug as a follow-up issue in the same branch (don't proceed with merge).

---

## Self-review checklist

Run through this after the plan is fully written. Fix anything inline.

- **Spec coverage:**
  - ✅ Atomic HP score (Task 2)
  - ✅ Loss aversion λ=2 (Task 1, integrated in Task 10)
  - ✅ Two scales 30v30 / 3k (Task 11 orchestrator iterates both)
  - ✅ Three role components per pool (Task 7 + Task 10)
  - ✅ Line membership including extra_imperial + unique units (Task 5)
  - ✅ Within-line aggregation: dedup mean (Task 6)
  - ✅ Across-line aggregation: avg-of-line-means (Task 10)
  - ✅ Pool-aware final score formula (Task 7)
  - ✅ Resource cost axis (Task 3)
  - ✅ Speed-to-win axis with T_MAX=120 (Task 4)
  - ✅ Shape descriptors over raw signed_score (Task 8)
  - ✅ Storage: new pool_scores.db, pool_scores table (Task 9)
  - ✅ Pipeline: new derive_pool_scores.py (Task 11)
  - ✅ Reference unit validation (Task 12)
  - ⏸ Profile labels — explicitly deferred per spec ("computed at display time, not stored")
  - ⏸ Per-role shape descriptors — deferred (only overall shape stored in v1)
  - ⏸ UI integration — deferred per user direction

- **Placeholders:** none. All steps include concrete code or commands.

- **Type/name consistency:**
  - `apply_loss_aversion`, `hp_score`, `cost_score`, `speed_score`, `weighted_cost`, `dedup_mean`, `compute_shape`, `final_score_for_pool`, `derive_unit_scores`, `unit_to_pool`, `line_imperial_slugs` — all referenced consistently in tests, lib, and orchestrator.
  - DB schema column names match `derive_unit_scores` output keys exactly.
  - `winner` is consistently `int` (1/2/0) across atomic functions.
  - `team1_hp_pct` / `team2_hp_pct` naming matches `matchup_battles` schema.
