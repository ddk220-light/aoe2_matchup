"""Pure classification rules for the unit-analysis-video storyboard.

Boundary values pinned by the Temple Guard calibration + the DB-backed dry run
(docs/superpowers/specs/2026-07-05-etg-dbsource-dryrun.py).
"""
import pytest

from aoe2x.analysis.story_rules import (
    WIN_T, B_T, B_STRONG, E_T, OUTLIER_MARGIN, WEIGHTS, COUNTER_MIX,
    categorize, rps, bonus_gain, bonus_component, cost_component,
    expectation_from_components, classify, prefer_uniques, dedupe_line,
    pick_counter_mix, SORTS, PICK_FILTERS,
)


def R(S, B, E=0.0, ranged=False, kited=False, is_unique=True, slug="x", gold=50):
    """Minimal result row as produced by unit_video_story."""
    return {"S": S, "E": E, "factors": {"bonus": B, "rps": 0.0, "cost": 0.0},
            "ranged": ranged, "kited": kited, "is_unique": is_unique,
            "slug": slug, "gold": gold}


# --- constants ----------------------------------------------------------
def test_constants_match_calibration():
    assert (WIN_T, B_T, B_STRONG, E_T, OUTLIER_MARGIN) == (15.0, 0.2, 0.45, 0.15, 15.0)
    assert WEIGHTS == {"bonus": 0.5, "rps": 0.3, "cost": 0.2}


# --- categorize ---------------------------------------------------------
def test_categorize_gunpowder_keywords():
    assert categorize("elite_janissary_turks", "Infantry", True, 0.96) == "gunpowder"
    assert categorize("grenadier_jurchens", "Infantry", True, 0.9) == "gunpowder"


def test_categorize_ballista_elephant_is_siege():
    assert categorize("elite_ballista_elephant_khmer", "Cavalry", True, 0.8) == "siege"


def test_categorize_thrown_weapon_infantry_is_archer():
    # infantry unit_class + ranged -> plays like an archer (gbeto/chakram)
    assert categorize("elite_gbeto_malians", "Infantry", True, 1.0) == "archer"
    assert categorize("elite_chakram_thrower_gurjaras", "Infantry", True, 1.0) == "archer"


def test_categorize_slow_eagle_class_is_infantry():
    # Temple Guard: eagle-name armor class but 1.05 speed -> plays like infantry
    assert categorize("elite_temple_guard_muisca", "Infantry", False, 1.05) == "infantry"


def test_categorize_fast_eagle_stays_eagle():
    assert categorize("elite_eagle", "Infantry", False, 1.3) == "eagle"


def test_categorize_ranged_cavalry_is_cav_archer():
    assert categorize("elite_mangudai_mongols", "Cavalry", True, 1.4) == "cav_archer"


def test_categorize_melee_cavalry_is_cavalry():
    assert categorize("paladin", "Cavalry", False, 1.35) == "cavalry"


def test_categorize_shrivamsha_is_light_cav():
    assert categorize("elite_shrivamsha_rider_gurjaras", "Cavalry", False, 1.5) == "light_cav"


# --- rps ----------------------------------------------------------------
def test_rps_antisymmetric():
    assert rps("spear", "cavalry") == -rps("cavalry", "spear")
    assert rps("eagle", "archer") == -rps("archer", "eagle")


def test_rps_same_category_zero():
    assert rps("infantry", "infantry") == 0.0


def test_rps_unknown_pair_zero():
    assert rps("camel", "spear") == -rps("spear", "camel")  # antisymmetric fill
    assert rps("gunpowder", "gunpowder") == 0.0


# --- bonus_gain ---------------------------------------------------------
def test_bonus_gain_applies_class_bonus_minus_bonus_armor():
    # attacker 16 base, +8 vs class 8; defender class-8 bonus armor 0,
    # melee armor 2 -> base_eff = 16-2 = 14, gain = 8/14
    g = bonus_gain('{"4": 16, "8": 8}', 16, '{"4": 2, "3": 0, "8": 0}', False)
    assert g == pytest.approx(8 / 14)


def test_bonus_gain_zero_when_no_matching_class():
    assert bonus_gain('{"4": 16, "8": 8}', 16, '{"4": 0, "3": 0}', False) == 0.0


def test_bonus_gain_ranged_uses_pierce_base_armor():
    # ranged attacker: base armor is class 3 (pierce). 12 atk, +5 vs class 8;
    # defender pierce armor 2 -> base_eff = 10, gain = 5/10
    g = bonus_gain('{"3": 12, "8": 5}', 12, '{"3": 2, "8": 0}', True)
    assert g == pytest.approx(5 / 10)


def test_bonus_gain_ignores_bonus_swallowed_by_armor():
    # +4 vs class 8 but defender has 4 bonus armor -> net 0, no gain
    g = bonus_gain('{"4": 16, "8": 4}', 16, '{"4": 0, "8": 4}', False)
    assert g == 0.0


# --- component / expectation math ---------------------------------------
def test_bonus_component_is_tanh_of_difference():
    import math
    assert bonus_component(0.5, 0.1) == pytest.approx(math.tanh(0.4))


def test_cost_component_clamped_log3():
    import math
    assert cost_component(90, 30) == pytest.approx(math.log(3) / math.log(3))  # =1
    assert cost_component(9000, 1) == 1.0        # clamped
    assert cost_component(1, 9000) == -1.0       # clamped


def test_expectation_blend_weights():
    E = expectation_from_components(1.0, 1.0, 1.0)
    assert E == pytest.approx(1.0)               # 0.5+0.3+0.2, clamped at 1
    E2 = expectation_from_components(0.2, 0.0, 0.0)
    assert E2 == pytest.approx(0.1)


# --- classify: every row lands in exactly one of five categories --------
def test_even_band_edges():
    assert classify(R(S=15.0, B=0.9)) == "even"      # |S| == WIN_T -> even
    assert classify(R(S=-15.0, B=-0.9)) == "even"
    assert classify(R(S=14.9, B=0.9)) == "even"
    assert classify(R(S=-14.9, B=-0.9)) == "even"


def test_win_just_over_threshold_not_even():
    assert classify(R(S=15.1, B=0.3)) == "expected_win"
    assert classify(R(S=-15.1, B=-0.9)) == "expected_counter"


def test_expected_win_by_bonus_edge():
    assert classify(R(S=50, B=B_T)) == "expected_win"        # B == B_T
    assert classify(R(S=50, B=0.19)) in ("expected_win", "unexpected_win")


def test_no_bonus_win_split_by_prior():
    assert classify(R(S=50, B=0.0, E=0.1)) == "expected_win"
    assert classify(R(S=50, B=0.0, E=-0.1)) == "unexpected_win"
    assert classify(R(S=50, B=0.0, E=0.0)) == "expected_win"  # E>=0 boundary


def test_unexpected_win_their_bonus_edge():
    assert classify(R(S=20, B=-B_T)) == "unexpected_win"     # B == -B_T


def test_expected_counter_dedicated_bonus_edge():
    assert classify(R(S=-50, B=-B_STRONG)) == "expected_counter"   # B == -B_STRONG
    # just weaker than dedicated, melee, prior fine -> unexpected_counter
    assert classify(R(S=-50, B=-0.44, E=0.0)) == "unexpected_counter"


def test_expected_counter_kited():
    assert classify(R(S=-50, B=0.6, ranged=True, kited=True)) == "expected_counter"


def test_expected_counter_bad_prior_edge():
    assert classify(R(S=-50, B=0.0, E=-0.16)) == "expected_counter"   # E < -E_T
    assert classify(R(S=-50, B=0.0, E=-E_T)) == "unexpected_counter"  # E == -E_T not <


def test_unexpected_counter_melee_small_bonus():
    # obuch case: melee, incidental bonus, prior not clearly negative
    assert classify(R(S=-42, B=-0.32, E=-0.08)) == "unexpected_counter"


def test_ranged_no_bonus_loss_defaults_expected():
    assert classify(R(S=-50, B=0.0, ranged=True, kited=False, E=0.0)) == "expected_counter"


def test_classify_partitions_sorts_keys():
    for cat in ("expected_win", "unexpected_win", "expected_counter",
                "unexpected_counter", "even"):
        assert cat in SORTS


# --- prefer_uniques ------------------------------------------------------
def test_generic_needs_outlier_margin():
    items = [R(79.1, 0.4, is_unique=False, slug="heavy_camel"),
             R(60.4, 0.5, slug="shriv"),
             R(57.5, 0.6, slug="tiger"),
             R(51.3, 0.6, is_unique=False, slug="paladin"),
             R(48.0, 0.5, slug="kona")]
    picks = prefer_uniques(items)
    # camel beats shriv by 18.7 >= 15 -> stays; paladin (51.3 vs kona 48.0) doesn't
    assert [p["slug"] for p in picks] == ["heavy_camel", "shriv", "tiger"]


def test_generic_kept_when_no_unique_left():
    items = [R(50, 0.4, is_unique=False, slug="a"), R(40, 0.4, is_unique=False, slug="b")]
    assert [p["slug"] for p in prefer_uniques(items)] == ["a", "b"]


def test_prefer_uniques_caps_at_three():
    items = [R(90 - i, 0.4, slug=f"u{i}") for i in range(6)]
    assert len(prefer_uniques(items)) == 3


def test_prefer_uniques_margin_uses_abs_S():
    # losses (negative S): a big generic loss beats the next unique by |S| margin
    items = [R(-80, -0.4, is_unique=False, slug="gen"),
             R(-60, -0.4, slug="uni1"),
             R(-55, -0.4, slug="uni2")]
    picks = prefer_uniques(items)
    assert [p["slug"] for p in picks] == ["gen", "uni1", "uni2"]


# --- dedupe_line ---------------------------------------------------------
def test_ratha_forms_collapse():
    items = [R(34, 0.6, slug="elite_ratha_(melee)_bengalis"),
             R(20, 0.5, slug="elite_ratha_(ranged)_bengalis")]
    assert len(dedupe_line(items)) == 1
    assert dedupe_line(items)[0]["slug"] == "elite_ratha_(melee)_bengalis"


def test_dedupe_keeps_distinct_lines():
    items = [R(1, 0, slug="paladin"), R(2, 0, slug="hussar")]
    assert len(dedupe_line(items)) == 2


# --- expected_counter MIX rule ------------------------------------------
def test_counter_mix_curated_trio_when_all_present():
    items = [R(-100, -0.9, slug="grenadier_jurchens"),
             R(-94, -0.9, slug="elite_chakram_thrower_gurjaras"),
             R(-93, -0.9, slug="elite_chu_ko_nu_chinese"),
             R(-99, -0.9, slug="something_else_worse")]
    picks = pick_counter_mix(items)
    assert [p["slug"] for p in picks] == list(COUNTER_MIX)   # curated ORDER, not S sort


def test_counter_mix_falls_back_to_margin_sort_when_incomplete():
    # only 1 of the curated trio present -> fall back to prefer_uniques(dedupe)
    items = [R(-100, -0.9, slug="grenadier_jurchens"),
             R(-88, -0.9, slug="elite_kipchak_cumans"),
             R(-70, -0.9, slug="elite_conquistador_spanish")]
    picks = pick_counter_mix(items)
    assert [p["slug"] for p in picks] == [
        "grenadier_jurchens", "elite_kipchak_cumans", "elite_conquistador_spanish"]


# --- PICK_FILTERS sanity -------------------------------------------------
def test_expected_win_filter_requires_gold_and_bonus():
    assert PICK_FILTERS["expected_win"](R(50, 0.3, gold=45)) is True
    assert PICK_FILTERS["expected_win"](R(50, 0.3, gold=0)) is False   # trash unit
    assert PICK_FILTERS["expected_win"](R(50, 0.1, gold=45)) is False  # bonus too small


def test_unexpected_win_filter_requires_their_bonus():
    assert PICK_FILTERS["unexpected_win"](R(30, -0.3)) is True
    assert PICK_FILTERS["unexpected_win"](R(30, 0.1)) is False
