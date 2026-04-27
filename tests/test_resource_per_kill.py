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


from simulation_real import simulate_real_battle, prepare_combat_unit


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
