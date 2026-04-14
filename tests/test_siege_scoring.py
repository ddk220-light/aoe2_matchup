import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import pytest
from compute_battle_scores import _simulate_siege_vs_castle, _effective_ttk, _get_siege_fixed_count


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


# ===== CASTLE_TARGETS tests =====

def test_castle_targets_length():
    from compute_battle_scores import CASTLE_TARGETS
    assert len(CASTLE_TARGETS) == 3


def test_castle_targets_names():
    from compute_battle_scores import CASTLE_TARGETS
    assert [c["name"] for c in CASTLE_TARGETS] == ["persian", "teuton", "byzantine"]


def test_castle_targets_hp_ordering():
    """Byzantine is hardest (civ HP bonus), then Persian, then Teuton (no Architecture)."""
    from compute_battle_scores import CASTLE_TARGETS
    by_name = {c["name"]: c["hp"] for c in CASTLE_TARGETS}
    assert by_name["byzantine"] > by_name["persian"] > by_name["teuton"]


def test_castle_targets_required_keys():
    from compute_battle_scores import CASTLE_TARGETS
    required = {"name", "hp", "armor", "arrows", "arrow_attack", "arrow_range", "reload", "arrow_bonus_attacks"}
    for entry in CASTLE_TARGETS:
        assert required == required & entry.keys(), f"{entry['name']} missing keys: {required - entry.keys()}"


def test_castle_targets_armor_classes():
    """Each castle armor dict must have all four building armor classes."""
    from compute_battle_scores import CASTLE_TARGETS
    for entry in CASTLE_TARGETS:
        assert set(entry["armor"].keys()) == {3, 4, 11, 21}, (
            f"{entry['name']} armor keys mismatch"
        )


def test_castle_targets_persian_arrow_bonus():
    """Persian Citadels grant bonus attacks vs Rams (17) and Infantry (1)."""
    from compute_battle_scores import CASTLE_TARGETS
    persian = next(c for c in CASTLE_TARGETS if c["name"] == "persian")
    assert persian["arrow_bonus_attacks"] == {17: 3, 1: 3}


def test_castle_targets_non_persian_no_arrow_bonus():
    """Teuton and Byzantine have no arrow bonus attacks."""
    from compute_battle_scores import CASTLE_TARGETS
    for entry in CASTLE_TARGETS:
        if entry["name"] != "persian":
            assert entry["arrow_bonus_attacks"] == {}, (
                f"{entry['name']} should have empty arrow_bonus_attacks"
            )


# ===== _effective_ttk tests =====

def test_effective_ttk_winner():
    assert _effective_ttk(120.0, 1.0, 150.0) == 120.0


def test_effective_ttk_loser_with_winners():
    # (100 + 200) / 0.5 = 600.0
    assert _effective_ttk(600.0, 0.5, 100.0) == 600.0


def test_effective_ttk_loser_no_winners():
    assert _effective_ttk(600.0, 0.3, None) == 600.0


def test_effective_ttk_loser_zero_damage():
    assert _effective_ttk(600.0, 0.0, 100.0) == 600.0


# ===== _get_siege_fixed_count tests =====

def test_get_siege_fixed_count_default():
    assert _get_siege_fixed_count("ram") == 5
    assert _get_siege_fixed_count("trebuchet") == 5
    assert _get_siege_fixed_count("bombard_cannon") == 5


def test_get_siege_fixed_count_special():
    assert _get_siege_fixed_count("fire_archer_wu") == 30
    assert _get_siege_fixed_count("tarkan") == 30
    assert _get_siege_fixed_count("tarkan_huns") == 30
