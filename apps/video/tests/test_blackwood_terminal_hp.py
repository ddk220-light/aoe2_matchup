"""A last poison tick changes reported HP without changing the recorded winner."""
import pytest
from blackwood_five_hussars import terminal_hp_outcome


def test_residual_damage_uses_terminal_grpc_state():
    captured = {"framesSha256": "same-frames", "winnerOwner": 3, "winnerHp": 271,
                "winnerStartingHp": 1215, "winnerRemainingHpPercent": 271 / 1215 * 100}
    timeline = {"sourceSha256": "same-frames", "rows": [
        {"videoSeconds": 20, "sides": {"2": [{"hp": 0}], "3": [{"hp": 271}]}},
        {"videoSeconds": 21, "sides": {"2": [{"hp": 0}], "3": [{"hp": 267}]}}
    ]}
    result = terminal_hp_outcome(captured, timeline)
    assert result["winnerOwner"] == 3 and result["winnerHp"] == 267
    assert result["winnerRemainingHpPercent"] == pytest.approx(267 / 1215 * 100)
    assert result["signedRemainingHpPercent"] < 0
    assert captured["winnerHp"] == 271
    timeline["sourceSha256"] = "different-recording"
    with pytest.raises(AssertionError, match="different frames"):
        terminal_hp_outcome(captured, timeline)
