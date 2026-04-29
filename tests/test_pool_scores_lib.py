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


from pool_scores_lib import speed_score


def test_speed_score_instant_win_max_score():
    # Win at 0s -> +100.
    assert speed_score(winner=1, game_time_s=0.0) == 100.0


def test_speed_score_60s_win_half_score():
    # Win at 60s with T_MAX=120 -> +100 * (1 - 60/120) = +50.
    assert speed_score(winner=1, game_time_s=60.0) == pytest.approx(50.0)


def test_speed_score_at_or_past_t_max_clipped_to_zero():
    assert speed_score(winner=1, game_time_s=120.0) == 0.0
    assert speed_score(winner=1, game_time_s=200.0) == 0.0


def test_speed_score_fast_loss_doubled_negative():
    # Loss at 0s -> -lambda*100 = -200.
    assert speed_score(winner=2, game_time_s=0.0) == -200.0


def test_speed_score_60s_loss():
    # Loss at 60s -> -2 * 100 * 0.5 = -100.
    assert speed_score(winner=2, game_time_s=60.0) == pytest.approx(-100.0)


def test_speed_score_tie_returns_zero():
    assert speed_score(winner=0, game_time_s=30.0) == 0.0


from pool_scores_lib import line_imperial_slugs, unit_to_pool
from unit_lines import UNIT_LINES


def test_line_imperial_slugs_militia_includes_champion_and_uniques():
    slugs = line_imperial_slugs(UNIT_LINES, "militia")
    assert "champion" in slugs
    assert "elite_berserk_vikings" in slugs
    assert "elite_huskarl_goths" in slugs
    assert "elite_jaguar_warrior_aztecs" in slugs


def test_line_imperial_slugs_archer_includes_arbalester_and_plumed():
    slugs = line_imperial_slugs(UNIT_LINES, "archer")
    assert "arbalester" in slugs
    assert "elite_plumed_archer_mayans" in slugs


def test_line_imperial_slugs_elephant_includes_extra_imperial():
    # elephant line has extra_imperial_slugs = ['elite_ele_archer']
    slugs = line_imperial_slugs(UNIT_LINES, "elephant")
    assert "elite_elephant" in slugs
    assert "elite_ele_archer" in slugs


def test_unit_to_pool_champion_is_infantry():
    assert unit_to_pool(UNIT_LINES, "champion") == "infantry"


def test_unit_to_pool_berserker_is_infantry():
    assert unit_to_pool(UNIT_LINES, "elite_berserk_vikings") == "infantry"


def test_unit_to_pool_paladin_is_stable():
    assert unit_to_pool(UNIT_LINES, "paladin") == "stable"


def test_unit_to_pool_cataphract_is_stable():
    assert unit_to_pool(UNIT_LINES, "elite_cataphract_byzantines") == "stable"


def test_unit_to_pool_arbalester_is_archer():
    assert unit_to_pool(UNIT_LINES, "arbalester") == "archer"


def test_unit_to_pool_unknown_returns_none():
    assert unit_to_pool(UNIT_LINES, "trebuchet") is None
    assert unit_to_pool(UNIT_LINES, "totally_made_up_slug") is None


from pool_scores_lib import dedup_mean


def test_dedup_mean_collapses_same_group():
    # Two values share group "G1"; first wins.
    values = [("G1", 80.0), ("G1", 100.0), ("G2", 50.0)]
    # G1 -> 80.0 (first seen), G2 -> 50.0; mean = 65.0
    assert dedup_mean(values) == pytest.approx(65.0)


def test_dedup_mean_empty_returns_none():
    assert dedup_mean([]) is None


def test_dedup_mean_all_same_group():
    values = [("G1", 10.0), ("G1", 20.0)]
    assert dedup_mean(values) == 10.0


def test_dedup_mean_unique_groups():
    values = [("a", 10.0), ("b", 20.0), ("c", 30.0)]
    assert dedup_mean(values) == 20.0


from pool_scores_lib import (
    POOL_ROLES, POOL_WEIGHTS, final_score_for_pool,
)


def test_pool_roles_match_spec():
    assert set(POOL_ROLES) == {"infantry", "stable", "archer"}
    assert POOL_ROLES["infantry"]["AC"] == ["knight", "camel", "steppe_lancer", "elephant"]
    assert POOL_ROLES["stable"]["AC"] == ["knight", "camel", "steppe_lancer", "elephant", "light_cav"]
    assert POOL_ROLES["archer"]["AA"] == ["archer", "skirmisher", "cav_archer", "gunpowder"]


def test_pool_weights_sum_to_one():
    for pool, weights in POOL_WEIGHTS.items():
        assert abs(sum(weights.values()) - 1.0) < 1e-9, pool


def test_final_score_infantry():
    # 0.7*GC + 0.15*AC + 0.15*AT
    role_means = {"GC": -10.0, "AC": +50.0, "AT": +90.0}
    expected = 0.7 * -10.0 + 0.15 * 50.0 + 0.15 * 90.0  # = 14.0
    assert final_score_for_pool(role_means, "infantry") == pytest.approx(expected)


def test_final_score_stable():
    # 0.7*GC + 0.30*AC
    role_means = {"GC": +20.0, "AC": +40.0}
    expected = 0.7 * 20.0 + 0.30 * 40.0  # = 26.0
    assert final_score_for_pool(role_means, "stable") == pytest.approx(expected)


def test_final_score_archer():
    # 0.7*GC + 0.30*AA
    role_means = {"GC": +30.0, "AA": -10.0}
    expected = 0.7 * 30.0 + 0.30 * -10.0  # = 18.0
    assert final_score_for_pool(role_means, "archer") == pytest.approx(expected)


def test_final_score_missing_role_treated_as_zero():
    # If a role has no data, treat the role mean as 0 (don't reweight).
    role_means = {"GC": +50.0}  # missing AC
    expected = 0.7 * 50.0 + 0.30 * 0.0  # = 35.0
    assert final_score_for_pool(role_means, "stable") == pytest.approx(expected)
