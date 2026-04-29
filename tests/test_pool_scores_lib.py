"""Unit tests for webapp/pool_scores_lib.py."""
from pool_scores_lib import apply_loss_aversion, hp_score


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
