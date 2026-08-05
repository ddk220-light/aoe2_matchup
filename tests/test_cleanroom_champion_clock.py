import json
from importlib.util import find_spec
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TRUTH_FIXTURE = (
    REPO_ROOT
    / "aoe2x"
    / "js_simulation"
    / "calibration"
    / "fixtures"
    / "champion_basics.json"
)


def load_truth():
    return json.loads(TRUTH_FIXTURE.read_text(encoding="utf-8"))


def test_clock_report_separates_recorder_rate_from_engine_hypothesis():
    """Catches a report that substitutes a preferred engine rate for recorder evidence."""
    assert find_spec("aoe2x.js_simulation.tools.analyze_champion_clock")
    from aoe2x.js_simulation.tools.analyze_champion_clock import analyze_clock

    report = analyze_clock(load_truth())

    assert report["recorder_stream_hz"] == [59.4]
    assert report["position_sample_hz"] == [10.0]
    assert report["engine_hypothesis_hz"] == 60
    assert report["claim"] == "provisional_not_published"
    assert report["same_attacker_intervals_s"]["count"] > 0


def test_clock_report_keeps_both_tick_residual_candidates():
    """Catches an analysis that silently chooses 50 Hz or 60 Hz from outcome data."""
    assert find_spec("aoe2x.js_simulation.tools.analyze_champion_clock")
    from aoe2x.js_simulation.tools.analyze_champion_clock import analyze_clock

    report = analyze_clock(load_truth())

    assert set(report["tick_residuals_s"]) == {"50", "60"}
    assert all(
        candidate["count"] == report["same_attacker_intervals_s"]["count"]
        for candidate in report["tick_residuals_s"].values()
    )
