"""Tests for melee engagement slot targeting functions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from simulation import (
    _assign_targets_spread,
    _assign_targets_melee_capped,
    _assign_targets_spread_capped,
    MELEE_ENGAGE_RATIO,
    MELEE_VS_MELEE_MAX,
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


def test_melee_capped_50pct_cap():
    """At most 50% of ranged targets are engageable."""
    my_alive = list(range(30))
    enemy_alive = list(range(30))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 15

    targets = list(result.values())
    assert len(set(targets)) == len(targets)


def test_melee_capped_1to1_strict():
    """Each engageable target gets exactly 1 melee attacker."""
    my_alive = list(range(20))
    enemy_alive = list(range(10))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 5
    targets = list(result.values())
    assert len(set(targets)) == len(targets)


def test_melee_capped_surplus_idles():
    """Surplus melee units get no target (not in result dict)."""
    my_alive = list(range(30))
    enemy_alive = list(range(10))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 5
    idle = [i for i in my_alive if i not in result]
    assert len(idle) == 25


def test_melee_capped_rotation():
    """Different ticks target different enemies (rotation)."""
    my_alive = list(range(10))
    enemy_alive = list(range(10))
    targets_tick0 = set(_assign_targets_melee_capped(my_alive, enemy_alive, tick=0).values())
    targets_tick1 = set(_assign_targets_melee_capped(my_alive, enemy_alive, tick=1).values())
    assert targets_tick0 != targets_tick1


def test_melee_capped_small_army():
    """Small armies: 2 melee vs 2 ranged."""
    my_alive = [0, 1]
    enemy_alive = [0, 1]
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 1


def test_melee_capped_single_enemy():
    """With 1 enemy, at least 1 melee can attack."""
    my_alive = list(range(10))
    enemy_alive = [0]
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 1
    assert result[my_alive[0]] == 0


def test_melee_capped_fewer_melee_than_slots():
    """When melee count < engageable slots, all melee get targets."""
    my_alive = [0, 1, 2]
    enemy_alive = list(range(20))
    result = _assign_targets_melee_capped(my_alive, enemy_alive, tick=0)
    assert len(result) == 3


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
    """When outnumbering 3:1, max 2 per target, surplus gets no target."""
    my_alive = list(range(15))
    enemy_alive = list(range(5))
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    # 5 enemies * 2 max = 10 slots, so 10 assigned, 5 idle
    assert len(result) == 10
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX


def test_spread_capped_small():
    """Small armies: 3v2, each enemy gets up to 2, all 3 fit."""
    my_alive = [0, 1, 2]
    enemy_alive = [0, 1]
    result = _assign_targets_spread_capped(my_alive, enemy_alive)
    # 2 enemies * 2 cap = 4 slots -> all 3 get targets
    assert len(result) == 3
    from collections import Counter
    target_counts = Counter(result.values())
    assert max(target_counts.values()) <= MELEE_VS_MELEE_MAX
