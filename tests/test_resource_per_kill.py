import pytest
from simulation_real import BattleUnit


def _stats(**kwargs):
    base = {
        "hp": 100, "attack": 5, "melee_armor": 0, "pierce_armor": 0,
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


from simulation_real import BattleSimulation


def test_simulation_initializes_resource_accumulators():
    sim = BattleSimulation()
    assert sim.team1_food_gained == 0.0
    assert sim.team1_wood_gained == 0.0
    assert sim.team1_gold_gained == 0.0
    assert sim.team2_food_gained == 0.0
    assert sim.team2_wood_gained == 0.0
    assert sim.team2_gold_gained == 0.0
