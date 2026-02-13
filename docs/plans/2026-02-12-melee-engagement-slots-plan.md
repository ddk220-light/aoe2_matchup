# Melee Engagement Slot System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add melee engagement slot limits so melee units can't all attack ranged units simultaneously — at most 50% of ranged targets are engageable, 1 melee per target, surplus melee idles.

**Architecture:** Two new targeting functions (`_assign_targets_melee_capped` and `_assign_targets_spread_capped`) replace `_assign_targets_spread` in `simulate_battle()` and `_assign_mixed` in `simulate_mixed_battle()`. Three new constants control the behavior. No changes to damage calculation, opening volley, or Phase 3.

**Tech Stack:** Pure Python, pytest for testing, Flask webapp (no changes to app.py)

**Design doc:** `docs/plans/2026-02-12-melee-engagement-slots-design.md`

---

### Task 1: Install pytest and create test file

**Files:**
- Create: `tests/test_targeting.py`

**Step 1: Install pytest**

Run: `source venv/bin/activate && pip install pytest`
Expected: pytest installs successfully

**Step 2: Create test file with imports and a helper to build mock units**

```python
"""Tests for melee engagement slot targeting functions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from simulation import (
    _assign_targets_spread,
    _assign_targets_melee_capped,
    _assign_targets_spread_capped,
    MELEE_ENGAGE_RATIO,
)


def test_spread_unchanged():
    """Original spread targeting still works: all attackers get a target."""
    my_alive = [0, 1, 2, 3, 4]
    enemy_alive = [0, 1, 2]
    result = _assign_targets_spread(my_alive, enemy_alive)
    assert len(result) == 5
    for attacker in my_alive:
        assert attacker in result
        assert result[attacker] in enemy_alive
```

**Step 3: Run test to verify it passes (spread is already implemented)**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py::test_spread_unchanged -v`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/test_targeting.py
git commit -m "test: add targeting test file with spread baseline test"
```

---

### Task 2: Add `_assign_targets_melee_capped` function

**Files:**
- Modify: `webapp/simulation.py:14-23` (add constants after existing constants)
- Modify: `webapp/simulation.py:240` (add new function after `_assign_targets_spread`)
- Test: `tests/test_targeting.py`

**Step 1: Write failing tests for `_assign_targets_melee_capped`**

Add to `tests/test_targeting.py`:

```python
def test_melee_capped_50pct_cap():
    """At most 50% of ranged targets are engageable."""
    # 30 melee vs 30 ranged: only 15 engageable (30 // 2)
    my_alive = list(range(30))
    enemy_alive = list(range(30))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # Only 15 melee get targets (50% of 30 enemies, 1:1)
    assert len(result) == 15
    # Each target appears exactly once (1:1)
    targets = list(result.values())
    assert len(set(targets)) == len(targets)


def test_melee_capped_1to1_strict():
    """Each engageable target gets exactly 1 melee attacker."""
    my_alive = list(range(20))
    enemy_alive = list(range(10))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # 10 enemies -> 5 engageable -> 5 melee get targets
    assert len(result) == 5
    targets = list(result.values())
    assert len(set(targets)) == len(targets)


def test_melee_capped_surplus_idles():
    """Surplus melee units get no target (not in result dict)."""
    my_alive = list(range(30))
    enemy_alive = list(range(10))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # 10 enemies -> 5 engageable -> 5 assigned, 25 idle
    assert len(result) == 5
    idle = [i for i in my_alive if i not in result]
    assert len(idle) == 25


def test_melee_capped_rotation():
    """Different ticks target different enemies (rotation)."""
    my_alive = list(range(10))
    enemy_alive = list(range(10))
    targets_tick0 = set(_assign_targets_melee_capped(my_alive, enemy_alive, tick=0).values())
    targets_tick1 = set(_assign_targets_melee_capped(my_alive, enemy_alive, tick=1).values())
    # With 10 enemies, 5 engageable. Rotation should shift which 5 are picked.
    assert targets_tick0 != targets_tick1


def test_melee_capped_small_army():
    """Small armies: all can still engage (2 melee vs 2 ranged)."""
    my_alive = [0, 1]
    enemy_alive = [0, 1]
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # 2 enemies -> max(1, 2//2) = 1 engageable -> 1 assigned
    assert len(result) == 1


def test_melee_capped_single_enemy():
    """With 1 enemy, at least 1 melee can attack."""
    my_alive = list(range(10))
    enemy_alive = [0]
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # max(1, 1//2) = max(1, 0) = 1
    assert len(result) == 1
    assert result[my_alive[0]] == 0


def test_melee_capped_fewer_melee_than_slots():
    """When melee count < engageable slots, all melee get targets."""
    my_alive = [0, 1, 2]  # 3 melee
    enemy_alive = list(range(20))  # 20 ranged -> 10 engageable
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    # All 3 melee should get targets (3 < 10 engageable)
    assert len(result) == 3
```

**Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v -k "melee_capped"`
Expected: FAIL — ImportError, `_assign_targets_melee_capped` does not exist yet

**Step 3: Add constants to simulation.py**

In `webapp/simulation.py`, after line 22 (`TRAMPLE_HIT_CHANCE = 0.25`), add:

```python
MELEE_ENGAGE_RATIO = 0.5   # fraction of ranged units engageable by melee at once
MELEE_MAX_PER_TARGET = 1   # max melee attackers per ranged target
MELEE_VS_MELEE_MAX = 2     # soft cap for melee-vs-melee targeting
```

**Step 4: Add `_assign_targets_melee_capped` function**

In `webapp/simulation.py`, after `_assign_targets_spread` (after line 239), add:

```python
def _assign_targets_melee_capped(my_alive, enemy_alive, tick):
    """Assign melee attackers to ranged targets with engagement limits.

    Rules:
    - At most MELEE_ENGAGE_RATIO of enemy alive are targetable (the "engageable pool")
    - Each engageable target gets exactly MELEE_MAX_PER_TARGET attacker
    - Surplus melee units get no target (they idle that tick)
    - The engageable pool rotates each tick so different enemies are targeted
    """
    if not enemy_alive:
        return {}
    n_enemy = len(enemy_alive)
    engageable_count = max(1, int(n_enemy * MELEE_ENGAGE_RATIO))
    # Rotate which enemies are engageable each tick
    start = tick % n_enemy
    engageable = []
    for i in range(engageable_count):
        engageable.append(enemy_alive[(start + i) % n_enemy])
    # Assign 1 melee per engageable target, up to MELEE_MAX_PER_TARGET
    assignments = {}
    slots_used = {}  # target_idx -> count of attackers assigned
    slot_idx = 0
    for i in my_alive:
        if slot_idx >= len(engageable):
            break  # no more slots
        target = engageable[slot_idx]
        assignments[i] = target
        slots_used[target] = slots_used.get(target, 0) + 1
        if slots_used[target] >= MELEE_MAX_PER_TARGET:
            slot_idx += 1
    return assignments
```

**Step 5: Run tests to verify they pass**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v -k "melee_capped"`
Expected: All 7 tests PASS

**Step 6: Commit**

```bash
git add webapp/simulation.py tests/test_targeting.py
git commit -m "feat: add _assign_targets_melee_capped with 50% cap and 1:1 targeting"
```

---

### Task 3: Add `_assign_targets_spread_capped` function

**Files:**
- Modify: `webapp/simulation.py` (add function after `_assign_targets_melee_capped`)
- Test: `tests/test_targeting.py`

**Step 1: Write failing tests**

Add to `tests/test_targeting.py`:

```python
from simulation import _assign_targets_spread_capped, MELEE_VS_MELEE_MAX


def test_spread_capped_equal_numbers():
    """Equal melee armies: each enemy gets 1 attacker (under cap of 2)."""
    my_alive = list(range(10))
    enemy_alive = list(range(10))
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    assert len(result) == 10
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX


def test_spread_capped_outnumber():
    """When outnumbering 3:1, each enemy gets at most 2 attackers, surplus wraps."""
    my_alive = list(range(15))
    enemy_alive = list(range(5))
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    # All 15 get targets (wrapping around), but max 2 per enemy
    assert len(result) == 10  # 5 enemies * 2 max = 10 assigned
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX


def test_spread_capped_small():
    """Small armies: 3v2, each enemy gets 1, 1 surplus wraps to first."""
    my_alive = [0, 1, 2]
    enemy_alive = [0, 1]
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    # 2 enemies * 2 cap = 4 max -> all 3 get targets
    assert len(result) == 3
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX
```

**Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v -k "spread_capped"`
Expected: FAIL — ImportError

**Step 3: Implement `_assign_targets_spread_capped`**

In `webapp/simulation.py`, after `_assign_targets_melee_capped`, add:

```python
def _assign_targets_spread_capped(my_alive, enemy_alive):
    """Assign melee attackers spread across enemies with a per-target cap.

    Same as _assign_targets_spread but limits each enemy to MELEE_VS_MELEE_MAX
    attackers. Surplus melee units beyond the total cap get no target.
    """
    if not enemy_alive:
        return {}
    assignments = {}
    slots_used = {}  # target_idx -> count
    total_slots = len(enemy_alive) * MELEE_VS_MELEE_MAX
    n_en = len(enemy_alive)
    assigned = 0
    for li, i in enumerate(my_alive):
        if assigned >= total_slots:
            break
        # Spread: cycle through enemies, skip if at cap
        target_pos = li % n_en
        target = enemy_alive[target_pos]
        if slots_used.get(target, 0) >= MELEE_VS_MELEE_MAX:
            # Find next enemy with open slot
            found = False
            for offset in range(1, n_en):
                alt = enemy_alive[(target_pos + offset) % n_en]
                if slots_used.get(alt, 0) < MELEE_VS_MELEE_MAX:
                    target = alt
                    found = True
                    break
            if not found:
                break
        assignments[i] = target
        slots_used[target] = slots_used.get(target, 0) + 1
        assigned += 1
    return assignments
```

**Step 4: Run tests to verify they pass**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v -k "spread_capped"`
Expected: All 3 PASS

**Step 5: Commit**

```bash
git add webapp/simulation.py tests/test_targeting.py
git commit -m "feat: add _assign_targets_spread_capped with 2:1 melee-vs-melee cap"
```

---

### Task 4: Integrate into `simulate_battle()`

**Files:**
- Modify: `webapp/simulation.py:966-973` (target assignment in tick loop)
- Test: `tests/test_targeting.py`

**Step 1: Write integration test**

Add to `tests/test_targeting.py`:

```python
import json
from simulation import simulate_battle, prepare_combat_unit


def _make_unit(hp, attack, attack_speed, attack_range, melee_armor, pierce_armor,
               movement_speed=1.0, attacks=None, armors=None, **kwargs):
    """Build a minimal unit dict for testing simulate_battle."""
    if attacks is None:
        if attack_range >= 1.0:
            attacks = {3: attack}  # pierce
        else:
            attacks = {4: attack}  # melee
    if armors is None:
        armors = {3: pierce_armor, 4: melee_armor}
    base = {
        "hp": hp, "attack": attack, "attack_range": attack_range,
        "attack_speed": attack_speed, "attack_delay": 0,
        "melee_armor": melee_armor, "pierce_armor": pierce_armor,
        "movement_speed": movement_speed,
        "attacks_json": json.dumps({str(k): v for k, v in attacks.items()}),
        "armors_json": json.dumps({str(k): v for k, v in armors.items()}),
        "cost_food": 50, "cost_wood": 0, "cost_gold": 20,
        "min_attack_range": 0, "is_siege_projectile": 0,
        "splash_radius": 0, "projectile_speed": 7 if attack_range >= 1.0 else 0,
        "ignores_pierce_armor": 0, "ignores_melee_armor": 0,
        "trample_percent": 0, "trample_radius": 0, "trample_flat_damage": 0,
        "bonus_damage_reduction": 0, "extra_projectiles": 0,
        "extra_projectile_attacks_json": None,
        "splash_on_hit_radius": 0, "splash_on_hit_fraction": 1.0,
        "dodge_shield_max": 0, "dodge_shield_recharge": 0,
        "bleed_dps": 0, "bleed_duration": 0,
        "block_first_melee": 0, "attack_bonus_per_kill": 0,
        "first_attack_extra_projectiles": 0,
        "hp_regen": 0, "pass_through_percent": 0,
        "hp_transform_threshold": 0, "pop_space": 1.0,
        "armor_strip_per_hit": 0, "charge_attack_melee": 0,
        "charge_recharge_time": 0, "attack_bonus_nearby": 0,
        "nearby_bonus_count": 0, "damage_reflect_percent": 0,
        "bonus_hp_nearby": 0, "nearby_hp_bonus_count": 0,
        "slug": "test_unit", "unit_name": "Test Unit",
        "unit_category": "military", "paired_unit_slug": None,
        "dismount_hp": None,
    }
    base.update(kwargs)
    return prepare_combat_unit(base)


def test_simulate_melee_vs_ranged_engagement_slots():
    """30 melee vs 30 ranged: melee can't all attack at once, ranged does better."""
    # Champion-like: 70 HP, 18 atk, 0.5 aspd, melee, 4 MA, 6 PA
    champ = _make_unit(hp=70, attack=18, attack_speed=0.5, attack_range=0,
                       melee_armor=4, pierce_armor=6, movement_speed=1.06,
                       attacks={4: 18}, armors={4: 4, 3: 6})
    # Arbalester-like: 40 HP, 10 atk, 0.5 aspd, range 11, 3 MA, 4 PA
    arb = _make_unit(hp=40, attack=10, attack_speed=0.5, attack_range=11,
                     melee_armor=3, pierce_armor=4, movement_speed=0.96,
                     attacks={3: 10}, armors={4: 3, 3: 4})
    winner, remaining1, remaining2 = simulate_battle(champ, arb, 0, fixed_count=30)
    # With engagement slots, arbs should perform much better than before.
    # Before: champ wins with 30 remaining, 0.7 HP.
    # After: arbs should win or it should be very close.
    # We just assert arbs do significantly better (remaining2 > 0 or remaining1 < 20)
    assert remaining1 < 20 or remaining2 > 0, (
        f"Engagement slots should reduce melee dominance. "
        f"Got: champ={remaining1}, arb={remaining2}"
    )


def test_simulate_melee_vs_melee_similar():
    """Melee vs melee at equal numbers should be similar to before (2:1 cap minimal)."""
    knight = _make_unit(hp=120, attack=14, attack_speed=0.55, attack_range=0,
                        melee_armor=4, pierce_armor=4, movement_speed=1.35,
                        attacks={4: 14}, armors={4: 4, 3: 4})
    paladin = _make_unit(hp=160, attack=18, attack_speed=0.55, attack_range=0,
                         melee_armor=5, pierce_armor=5, movement_speed=1.35,
                         attacks={4: 18}, armors={4: 5, 3: 5})
    winner, rem1, rem2 = simulate_battle(knight, paladin, 0, fixed_count=20)
    # Paladin should still win. The 2:1 cap barely matters at 20v20.
    assert winner == 2


def test_simulate_small_battle_unchanged():
    """5v5 battle: small enough that all melee can engage, similar outcome."""
    champ = _make_unit(hp=70, attack=18, attack_speed=0.5, attack_range=0,
                       melee_armor=4, pierce_armor=6, movement_speed=1.06,
                       attacks={4: 18}, armors={4: 4, 3: 6})
    arb = _make_unit(hp=40, attack=10, attack_speed=0.5, attack_range=11,
                     melee_armor=3, pierce_armor=4, movement_speed=0.96,
                     attacks={3: 10}, armors={4: 3, 3: 4})
    winner, rem1, rem2 = simulate_battle(champ, arb, 0, fixed_count=5)
    # At 5v5, engageable = max(1, 5//2) = 2, so 2 melee engage.
    # Still a valid fight. Just check it completes without error.
    assert winner in (1, 2, 0)
```

**Step 2: Run integration tests to verify they fail**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v -k "simulate"`
Expected: `test_simulate_melee_vs_ranged_engagement_slots` FAILS (champ still wins with 30)

**Step 3: Modify target assignment in `simulate_battle()` tick loop**

In `webapp/simulation.py`, find lines 966-973 (the target assignment block inside the tick loop). Replace:

```python
        # Assign targets: ranged use focus fire, melee spread evenly
        if is_ranged1:
            targets1 = _assign_targets_focus(alive1, alive2, hp2, dmg1, 1 + extra_proj1)
        else:
            targets1 = _assign_targets_spread(alive1, alive2)
        if is_ranged2:
            targets2 = _assign_targets_focus(alive2, alive1, hp1, dmg2, 1 + extra_proj2)
        else:
            targets2 = _assign_targets_spread(alive2, alive1)
```

With:

```python
        # Assign targets: ranged focus fire, melee capped vs ranged, spread capped vs melee
        if is_ranged1:
            targets1 = _assign_targets_focus(alive1, alive2, hp2, dmg1, 1 + extra_proj1)
        elif is_ranged2:
            targets1 = _assign_targets_melee_capped(alive1, alive2, tick)
        else:
            targets1 = _assign_targets_spread_capped(alive1, alive2)
        if is_ranged2:
            targets2 = _assign_targets_focus(alive2, alive1, hp1, dmg2, 1 + extra_proj2)
        elif is_ranged1:
            targets2 = _assign_targets_melee_capped(alive2, alive1, tick)
        else:
            targets2 = _assign_targets_spread_capped(alive2, alive1)
```

**Step 4: Run all tests**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add webapp/simulation.py tests/test_targeting.py
git commit -m "feat: integrate engagement slots into simulate_battle tick loop"
```

---

### Task 5: Integrate into `simulate_mixed_battle()`

**Files:**
- Modify: `webapp/simulation.py:1968-2024` (`_assign_mixed` function)

**Step 1: Modify `_assign_mixed` to use melee caps**

In `webapp/simulation.py`, find the `_assign_mixed` inner function (around line 1971). The melee-on-ranged overflow section (lines 1998-2003) currently does uncapped spread. Change it to use the capped logic.

Replace lines 1984-2009 (the melee targeting section inside `_assign_mixed`):

```python
            # Melee targeting: engage enemy melee first (2 per enemy melee), overflow to ranged
            melee_capacity = (
                len(enemy_melee) * 2
            )  # each enemy melee can be engaged by up to 2
            melee_on_melee = my_melee[:melee_capacity]
            melee_overflow = my_melee[melee_capacity:]

            # Assign melee-on-melee (spread evenly among enemy melee)
            if enemy_melee and melee_on_melee:
                for li, i in enumerate(melee_on_melee):
                    targets[i] = enemy_melee[
                        li * len(enemy_melee) // len(melee_on_melee)
                    ]

            # Overflow melee engage enemy ranged (spread evenly)
            if enemy_ranged and melee_overflow:
                for li, i in enumerate(melee_overflow):
                    targets[i] = enemy_ranged[
                        li * len(enemy_ranged) // len(melee_overflow)
                    ]
            elif melee_overflow and enemy_melee:
                # No enemy ranged, put overflow on enemy melee
                for li, i in enumerate(melee_overflow):
                    targets[i] = enemy_melee[
                        li * len(enemy_melee) // len(melee_overflow)
                    ]
```

With:

```python
            # Melee targeting: engage enemy melee first (capped 2:1), overflow to ranged (capped)
            melee_capacity = len(enemy_melee) * MELEE_VS_MELEE_MAX
            melee_on_melee = my_melee[:melee_capacity]
            melee_overflow = my_melee[melee_capacity:]

            # Assign melee-on-melee (spread, capped at MELEE_VS_MELEE_MAX)
            if enemy_melee and melee_on_melee:
                slots_used = {}
                for li, i in enumerate(melee_on_melee):
                    t_pos = li % len(enemy_melee)
                    t = enemy_melee[t_pos]
                    if slots_used.get(t, 0) < MELEE_VS_MELEE_MAX:
                        targets[i] = t
                        slots_used[t] = slots_used.get(t, 0) + 1
                    else:
                        for offset in range(1, len(enemy_melee)):
                            alt = enemy_melee[(t_pos + offset) % len(enemy_melee)]
                            if slots_used.get(alt, 0) < MELEE_VS_MELEE_MAX:
                                targets[i] = alt
                                slots_used[alt] = slots_used.get(alt, 0) + 1
                                break

            # Overflow melee engage enemy ranged (capped: 50% engageable, 1:1)
            if enemy_ranged and melee_overflow:
                engageable_count = max(1, int(len(enemy_ranged) * MELEE_ENGAGE_RATIO))
                start = tick % len(enemy_ranged) if len(enemy_ranged) > 0 else 0
                engageable = [enemy_ranged[(start + j) % len(enemy_ranged)] for j in range(engageable_count)]
                for li, i in enumerate(melee_overflow):
                    if li >= len(engageable):
                        break  # surplus idles
                    targets[i] = engageable[li]
            elif melee_overflow and enemy_melee:
                # No enemy ranged, remaining melee idle (enemy melee already at cap)
                pass
```

Note: the `_assign_mixed` inner function needs access to `tick` from the enclosing scope. The `tick` variable is already available since `_assign_mixed` is defined inside the `for tick in range(MAX_TICKS):` loop.

**Step 2: Run full test suite**

Run: `source venv/bin/activate && python3 -m pytest tests/test_targeting.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add webapp/simulation.py
git commit -m "feat: integrate engagement slots into simulate_mixed_battle"
```

---

### Task 6: Run simulation sanity checks via webapp

**Files:** None changed (validation only)

**Step 1: Start Flask server and test 30 champ vs 30 arb**

Run: `source venv/bin/activate && cd webapp && python3 -c "
from simulation import prepare_combat_unit, simulate_battle
import sqlite3, json
db = sqlite3.connect('aoe2_units.db')
db.row_factory = sqlite3.Row
# Champion (Britons, Imperial)
row1 = db.execute(\"SELECT * FROM unit_stats WHERE slug='champion' AND civ_name='Britons' AND age='Imperial'\").fetchone()
row2 = db.execute(\"SELECT * FROM unit_stats WHERE slug='arbalester' AND civ_name='Britons' AND age='Imperial'\").fetchone()
u1 = prepare_combat_unit(row1)
u2 = prepare_combat_unit(row2)
w, r1, r2, hp1, hp2, ticks = simulate_battle(u1, u2, 0, fixed_count=30, return_hp=True, return_ticks=True)
print(f'Winner: {\"Champion\" if w==1 else \"Arbalester\" if w==2 else \"Draw\"}')
print(f'Champ remaining: {r1}, Arb remaining: {r2}')
print(f'HP: champ={hp1:.3f}, arb={hp2:.3f}, ticks={ticks}')
"`

Expected: Arbalester should do significantly better than before (before: champ won with 30 remaining, 0.7 HP total)

**Step 2: Test 5v5 to ensure small battles still work**

Run same script but with `fixed_count=5`. Should complete without error.

**Step 3: Test melee vs melee (knight vs paladin)**

Run same script for `slug='knight'` vs `slug='paladin'`, `fixed_count=20`. Paladin should still win.

**Step 4: Commit (no files, just verify)**

No commit needed — this is validation only.

---

### Task 7: Re-run battle scores

**Files:**
- Modified data: `webapp/aoe2_units.db` (battle_scores table rebuilt)

**Step 1: Re-run compute_battle_scores.py**

Run: `source venv/bin/activate && cd webapp && python3 compute_battle_scores.py`
Expected: Completes without error, outputs score summary

**Step 2: Spot-check a few matchups**

Run: `source venv/bin/activate && cd webapp && python3 -c "
import sqlite3
db = sqlite3.connect('aoe2_units.db')
# Check if arbalester battle score improved vs melee opponents
rows = db.execute(\"SELECT slug, civ_name, battle_score FROM unit_stats WHERE slug='arbalester' AND age='Imperial' ORDER BY battle_score DESC LIMIT 5\").fetchall()
for r in rows:
    print(f'{r[1]} {r[0]}: {r[2]}')
"`

**Step 3: Commit**

```bash
git add webapp/aoe2_units.db
git commit -m "rebuild: regenerate battle scores with melee engagement slots"
```
