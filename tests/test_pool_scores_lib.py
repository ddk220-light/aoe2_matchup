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
