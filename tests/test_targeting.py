"""Tests for melee engagement slot targeting functions."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from simulation import (
    _assign_targets_spread,
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
