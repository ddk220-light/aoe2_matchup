"""Unit tests for webapp/pool_scores_lib.py."""
import pytest
from pool_scores_lib import apply_loss_aversion, hp_score, weighted_cost, cost_score


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
