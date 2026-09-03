"""Truth-card extractor tests.

Two categories:

1. Real-tape assertions against the FINAL archive's own GROUND_TRUTH.md —
   tolerance 0.005s for swing intervals, 0.001 for accuracy, exact for integer
   counts. Where this source-agnostic extractor's swing-grouping definition
   differs from the archive report's per-unit/trample-aware interval summary,
   the expected value is called out beside the assertion.

2. Source-agnostic synthetic tests: extract_card must work on bare event
   dicts shaped like the ones a future sim recorder (Task 3+) would emit —
   no tape file paths, no tape-only fields.
"""
import gzip
import json
from pathlib import Path

import pytest

from aoe2x.calibration.paths import workspace_paths

REPO = Path(__file__).resolve().parents[1]
TAPES_DIR = workspace_paths().tapes_dir


def _load_jsonl_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_tape(run_id: str) -> tuple[list[dict], list[dict]]:
    run_dir = TAPES_DIR / run_id
    damage = _load_jsonl_gz(run_dir / f"{run_id}.damage.jsonl.gz")
    missiles = _load_jsonl_gz(run_dir / f"{run_id}.missiles.jsonl.gz")
    return damage, missiles


def test_build_truth_card_reads_only_explicit_workspace(tmp_path):
    """Catch extraction falling back to the historical external tape root."""
    from aoe2x.calibration.extract import build_truth_card

    paths = workspace_paths(tmp_path / "calibration")
    fight = {"run_id": "synthetic", "side1": {}, "side2": {}}

    with pytest.raises(FileNotFoundError) as exc_info:
        build_truth_card(fight, paths=paths)

    assert str(paths.tapes_dir) in str(exc_info.value)


def test_elite_steppe_vs_arbalester_matches_ground_truth():
    from aoe2x.calibration.extract import extract_card

    damage, missiles = _load_tape("elite_steppe__vs__arbalester")
    composition = {
        "side2": {"unit_name": "Arbalester", "count": 21},
        "side3": {"unit_name": "Elite Steppe Lancer", "count": 14},
    }
    card = extract_card(damage, missiles, composition)

    arb = card["sides"]["side2"]
    assert abs(arb["swing_interval_median"] - 1.990) < 0.005
    assert abs(arb["swing_interval_fastest"] - 1.572) < 0.005
    assert arb["projectiles_fired"] == 391
    assert arb["hits_landed"] == 350
    assert abs(arb["effective_accuracy"] - 0.895) < 0.001

    esl = card["sides"]["side3"]
    # FINAL publishes 2.412s as its median-of-units summary; extract_card's
    # source-agnostic event-gap definition intentionally yields 2.282s.
    assert abs(esl["swing_interval_median"] - 2.282) < 0.005
    assert abs(esl["swing_interval_fastest"] - 2.008) < 0.005
    assert esl["hits_landed"] == 70


def test_hand_cannoneer_vs_elite_elephant_matches_ground_truth():
    from aoe2x.calibration.extract import extract_card

    damage, missiles = _load_tape("hand_cannoneer__vs__elite_elephant")
    composition = {
        "side2": {"unit_name": "Hand Cannoneer", "count": 21},
        "side3": {"unit_name": "Elite Battle Elephant", "count": 12},
    }
    card = extract_card(damage, missiles, composition)

    hc = card["sides"]["side2"]
    assert abs(hc["swing_interval_median"] - 4.004) < 0.005
    assert abs(hc["swing_interval_fastest"] - 3.528) < 0.005
    assert hc["projectiles_fired"] == 338
    assert hc["hits_landed"] == 331
    assert abs(hc["effective_accuracy"] - 0.979) < 0.001

    elephant = card["sides"]["side3"]
    # FINAL's trample-aware report publishes 3.948s/0.000s; extract_card groups
    # one swing's multi-victim events before calculating gaps, intentionally
    # yielding 4.516s/2.012s for the sim-comparable event definition.
    assert abs(elephant["swing_interval_median"] - 4.516) < 0.005
    assert abs(elephant["swing_interval_fastest"] - 2.012) < 0.005
    assert elephant["hits_landed"] == 72


def test_extractor_is_source_agnostic():
    """The same function must accept synthetic sim-shaped events."""
    from aoe2x.calibration.extract import extract_card

    dmg = [{"t": 1.0, "attacker": 1, "victim": 9, "damage": 5.0, "victim_hp_after": 15.0,
            "kill": False, "attacker_owner": 2, "victim_owner": 3},
           {"t": 3.0, "attacker": 1, "victim": 9, "damage": 5.0, "victim_hp_after": 10.0,
            "kill": False, "attacker_owner": 2, "victim_owner": 3}]
    card = extract_card(dmg, [], {"side2": {"unit_name": "X", "count": 1},
                                  "side3": {"unit_name": "Y", "count": 1}})
    assert card["sides"]["side2"]["swing_interval_median"] == 2.0
    assert card["sides"]["side2"]["hits_landed"] == 2


def _multi_victim_swing(span: float) -> dict:
    """One attacker hitting two victims `span` seconds apart, extracted."""
    from aoe2x.calibration.extract import extract_card

    dmg = [{"t": 5.0, "attacker": 1, "victim": 9, "damage": 18.0, "victim_hp_after": 1.0,
            "kill": False, "attacker_owner": 3, "victim_owner": 2},
           {"t": 5.0 + span, "attacker": 1, "victim": 10, "damage": 4.5, "victim_hp_after": 1.0,
            "kill": False, "attacker_owner": 3, "victim_owner": 2}]
    card = extract_card(dmg, [], {"side3": {"unit_name": "E", "count": 1},
                                  "side2": {"unit_name": "H", "count": 2}})
    return card["sides"]["side3"]


def test_trample_multi_victim_detection():
    s = _multi_victim_swing(0.02)
    assert s["swing_count"] == 1, "same attacker within SWING_EPS is ONE swing"
    assert s["trample_multi_rate"] == 1.0
    assert s["trample_victims_max"] == 2


def test_swing_eps_covers_slow_projectile_spread():
    """SWING_EPS is 0.60s, not 0.15s — and this test pins that.

    A slow projectile (siege onager, heavy scorpion, elite fire lancer)
    delivers ONE shot's multi-victim damage spread over well more than
    0.15s of flight time. Under the old 0.15s value the extractor split
    that single shot into several "swings", manufacturing churn the engine
    was then blamed for (see docs/architecture/calibration-gap-analysis.md
    §3.3). A 0.40s spread must group as one multi-victim swing.
    """
    from aoe2x.calibration.extract import SWING_EPS

    assert SWING_EPS == 0.60

    s = _multi_victim_swing(0.40)
    assert s["swing_count"] == 1, "a 0.40s slow-projectile spread is ONE swing at 0.60s eps"
    assert s["trample_multi_rate"] == 1.0
    assert s["trample_victims_max"] == 2


def test_swing_eps_still_separates_genuinely_distinct_swings():
    """The widened eps must not swallow real reload cycles: two hits more
    than SWING_EPS apart are still two separate swings on one victim each,
    so nothing gets miscounted as trample.
    """
    s = _multi_victim_swing(0.80)
    assert s["swing_count"] == 2, "a 0.80s gap exceeds SWING_EPS — two swings"
    assert s["trample_multi_rate"] == 0.0
    assert s["trample_victims_max"] == 0


def test_same_timestamp_tie_break_picks_the_killing_event():
    """Regression test for a real bug found (and fixed) this task:
    `_side_outcome` originally picked a victim's "last" event with
    `max(events, key=lambda r: r["t"])`, which breaks ties by keeping the
    FIRST event with the max timestamp — not the true chronologically-last
    one. Two attackers can land hits on the same victim at the identical
    recorded `t` (common in a rounded ~60 Hz stream); if the non-killing
    event happens to come first in event order, the buggy code treated the
    victim as a "seen survivor" with nonzero hp_remaining, even though a
    kill=True event for that exact same victim existed in the same batch.

    Both sides get one victim with two same-`t` events, the second of
    which kills it. Under the bug, `hp_remaining` would be the FIRST
    event's victim_hp_after (nonzero) for both sides; under the fix
    (`sorted(events, key=lambda r: r["t"])[-1]`), the kill event wins the
    tie and hp_remaining is correctly 0.0.
    """
    from aoe2x.calibration.extract import extract_card

    dmg = [
        # side2's unit (victim id=100) dies to side3's attacker.
        {"t": 5.0, "attacker": 1, "victim": 100, "damage": 5.0, "victim_hp_after": 5.0,
         "kill": False, "attacker_owner": 3, "victim_owner": 2},
        {"t": 5.0, "attacker": 1, "victim": 100, "damage": 5.0, "victim_hp_after": 0.0,
         "kill": True, "attacker_owner": 3, "victim_owner": 2},
        # side3's unit (victim id=200) dies to side2's attacker.
        {"t": 7.0, "attacker": 2, "victim": 200, "damage": 3.0, "victim_hp_after": 3.0,
         "kill": False, "attacker_owner": 2, "victim_owner": 3},
        {"t": 7.0, "attacker": 2, "victim": 200, "damage": 3.0, "victim_hp_after": 0.0,
         "kill": True, "attacker_owner": 2, "victim_owner": 3},
    ]
    card = extract_card(dmg, [], {"side2": {"unit_name": "A", "count": 1},
                                  "side3": {"unit_name": "B", "count": 1}})

    assert card["sides"]["side2"]["survivors"] == 0
    assert card["sides"]["side2"]["hp_remaining"] == 0.0
    assert card["sides"]["side3"]["survivors"] == 0
    assert card["sides"]["side3"]["hp_remaining"] == 0.0


def test_hand_cannoneer_vs_elite_elephant_survivors_and_hp_remaining():
    """Pins FINAL's complete production truth-card path for winner HP.

    Bare ``extract_card(damage, missiles)`` cannot count untouched survivors;
    ``build_truth_card`` supplements combat events with unit-state rows and is
    the path calibration actually uses.
    """
    from aoe2x.calibration.extract import build_truth_card

    manifest = json.loads(workspace_paths().manifest.read_text(encoding="utf-8"))["fights"]
    fight = next(
        f for f in manifest if f["run_id"] == "hand_cannoneer__vs__elite_elephant"
    )
    card = build_truth_card(fight)

    hc = card["sides"]["side2"]
    assert hc["survivors"] == 0
    assert hc["hp_remaining"] == 0.0

    elephant = card["sides"]["side3"]
    assert elephant["survivors"] == 7
    assert elephant["hp_remaining"] == 1240.0
