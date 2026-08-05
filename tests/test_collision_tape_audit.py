import pytest

from tools.simjs.collision_tape_audit import (
    canonical_matchup_family,
    matchup_family,
    nearest_neighbors_for_frame,
    summarize,
)


def test_matchup_family_removes_only_repeat_suffix():
    assert matchup_family("hand_cannoneer__vs__paladin_r10") == "hand_cannoneer__vs__paladin"
    assert matchup_family("hand_cannoneer__vs__paladin") == "hand_cannoneer__vs__paladin"
    assert canonical_matchup_family("champion__vs__hand_cannoneer_r3") == (
        "champion__vs__hand_cannoneer"
    )
    assert canonical_matchup_family("hand_cannoneer__vs__champion") == (
        "champion__vs__hand_cannoneer"
    )


def test_nearest_neighbors_use_same_owner_and_ignore_dead_or_single_units():
    frame = [
        {"id": 1, "owner": 2, "x": 0.0, "y": 0.0, "hp": 40},
        {"id": 2, "owner": 2, "x": 0.3, "y": 0.0, "hp": 40},
        {"id": 3, "owner": 2, "x": 1.0, "y": 0.0, "hp": 40},
        {"id": 4, "owner": 2, "x": 0.1, "y": 0.0, "hp": 0},
        {"id": 5, "owner": 3, "x": 0.0, "y": 0.0, "hp": 40},
    ]

    distances = nearest_neighbors_for_frame(frame)

    assert distances == pytest.approx({1: 0.3, 2: 0.3, 3: 0.7})


def test_spacing_summary_reports_nominal_and_multiplied_thresholds():
    result = summarize([0.2, 0.3, 0.4, 0.5], nominal=0.4, multiplied=0.32)

    assert result["p10_tiles"] == pytest.approx(0.23)
    assert result["median_tiles"] == pytest.approx(0.35)
    assert result["share_below_nominal_pct"] == pytest.approx(50.0)
    assert result["share_below_multiplied_pct"] == pytest.approx(50.0)
