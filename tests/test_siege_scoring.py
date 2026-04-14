import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import pytest
from compute_battle_scores import _simulate_siege_vs_castle


def test_winner_returns_actual_ttk_and_full_damage():
    """Castle destroyed → (actual_ttk, 1.0)"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=5, unit_hp=200, unit_dps=50,
        castle_hp=1000, castle_dps=0,
        unit_speed=1.0, unit_range=10, castle_range=8,
    )
    # 1000 hp / (5 * 50 dps) = 4.0 s
    assert dmg == 1.0
    assert abs(ttk - 4.0) < 0.2


def test_loser_returns_600_and_partial_damage():
    """Units die before castle → (600.0, partial_fraction)"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=1, unit_hp=10, unit_dps=1,
        castle_hp=100_000, castle_dps=100,  # castle kills unit instantly
        unit_speed=1.0, unit_range=10, castle_range=8,
    )
    assert ttk == 600.0
    assert 0.0 <= dmg < 1.0


def test_outranges_castle_always_wins():
    """Unit outranges castle → can never die, always wins"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=5, unit_hp=100, unit_dps=20,
        castle_hp=500, castle_dps=999,  # castle fires but can't reach
        unit_speed=1.0, unit_range=15, castle_range=8,
    )
    assert dmg == 1.0
    assert ttk < 600.0


def test_outranges_castle_slow_kill_returns_loss():
    """Unit outranges but takes too long → (600.0, damage_fraction)"""
    ttk, dmg = _simulate_siege_vs_castle(
        n_units=1, unit_hp=100, unit_dps=0.01,
        castle_hp=100_000, castle_dps=0,
        unit_speed=1.0, unit_range=15, castle_range=8,
    )
    assert ttk == 600.0
    assert 0.0 < dmg < 1.0


def test_tarkan_line_exists_in_unit_lines():
    from unit_lines import UNIT_LINES
    assert "tarkan" in UNIT_LINES, "tarkan must have a standalone UNIT_LINES entry"
    assert UNIT_LINES["tarkan"]["castle_slug"] == "tarkan_huns"
    assert UNIT_LINES["tarkan"]["imperial_slug"] == "elite_tarkan_huns"


def test_tarkan_line_in_siege_line_slugs():
    from compute_battle_scores import SIEGE_LINE_SLUGS
    assert "tarkan" in SIEGE_LINE_SLUGS
