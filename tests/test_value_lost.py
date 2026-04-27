import pytest
from simulation_real import BattleSimulation, BattleUnit


def _stats(hp=100, **kw):
    base = {
        "hp": hp, "attack": 5, "melee_armor": 0, "pierce_armor": 0,
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
