"""Truth-card extractor tests.

Two categories:

1. Real-tape assertions against the four verified (side, metric) values from
   the drop's own GROUND_TRUTH.md (see task-2 brief) — tolerance 0.005s for
   swing intervals, 0.001 for accuracy, exact for integer counts. The one
   deliberate exception is the Elite Battle Elephant's swing_interval_median:
   we assert 6.246 (our definition, no idle-gap filtering), not the published
   5.672 (their extractor filters long idle gaps between real reload cycles;
   we do not copy that filtering because it must apply identically to sim
   events later, and sim events won't have "idle gap" semantics to filter).

2. Source-agnostic synthetic tests: extract_card must work on bare event
   dicts shaped like the ones a future sim recorder (Task 3+) would emit —
   no tape file paths, no tape-only fields.
"""
import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAPES_DIR = Path("D:/AI/aoe2_golden/tapes")


def _load_jsonl_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_tape(run_id: str) -> tuple[list[dict], list[dict]]:
    run_dir = TAPES_DIR / run_id
    damage = _load_jsonl_gz(run_dir / f"{run_id}.damage.jsonl.gz")
    missiles = _load_jsonl_gz(run_dir / f"{run_id}.missiles.jsonl.gz")
    return damage, missiles


def test_elite_steppe_vs_arbalester_matches_ground_truth():
    from aoe2x.calibration.extract import extract_card

    damage, missiles = _load_tape("elite_steppe__vs__arbalester")
    composition = {
        "side2": {"unit_name": "Arbalester", "count": 21},
        "side3": {"unit_name": "Elite Steppe Lancer", "count": 14},
    }
    card = extract_card(damage, missiles, composition)

    arb = card["sides"]["side2"]
    assert abs(arb["swing_interval_median"] - 1.974) < 0.005
    assert abs(arb["swing_interval_fastest"] - 1.582) < 0.005
    assert arb["projectiles_fired"] == 381
    assert arb["hits_landed"] == 350
    assert abs(arb["effective_accuracy"] - 0.919) < 0.001

    esl = card["sides"]["side3"]
    assert abs(esl["swing_interval_median"] - 2.284) < 0.005
    assert abs(esl["swing_interval_fastest"] - 2.006) < 0.005
    assert esl["hits_landed"] == 68


def test_hand_cannoneer_vs_elite_elephant_matches_ground_truth():
    from aoe2x.calibration.extract import extract_card

    damage, missiles = _load_tape("hand_cannoneer__vs__elite_elephant")
    composition = {
        "side2": {"unit_name": "Hand Cannoneer", "count": 21},
        "side3": {"unit_name": "Elite Battle Elephant", "count": 12},
    }
    card = extract_card(damage, missiles, composition)

    hc = card["sides"]["side2"]
    assert abs(hc["swing_interval_median"] - 4.000) < 0.005
    assert abs(hc["swing_interval_fastest"] - 3.510) < 0.005
    assert hc["projectiles_fired"] == 380
    assert hc["hits_landed"] == 368
    assert abs(hc["effective_accuracy"] - 0.968) < 0.001

    elephant = card["sides"]["side3"]
    # Deliberate exception: 6.246 is OUR definition (no idle-gap filtering).
    # The recording's own published GROUND_TRUTH.md says 5.672 because their
    # extractor filters long idle gaps (36.6s/25.6s/23.0s) out of this unit's
    # gap list before taking the median; we do not copy that filtering, so
    # ours is intentionally higher. Assert 6.246, not 5.672.
    assert abs(elephant["swing_interval_median"] - 6.246) < 0.005
    assert abs(elephant["swing_interval_fastest"] - 2.016) < 0.005
    assert elephant["hits_landed"] == 68


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


def test_trample_multi_victim_detection():
    from aoe2x.calibration.extract import extract_card

    dmg = [{"t": 5.0, "attacker": 1, "victim": 9, "damage": 18.0, "victim_hp_after": 1.0,
            "kill": False, "attacker_owner": 3, "victim_owner": 2},
           {"t": 5.02, "attacker": 1, "victim": 10, "damage": 4.5, "victim_hp_after": 1.0,
            "kill": False, "attacker_owner": 3, "victim_owner": 2}]
    card = extract_card(dmg, [], {"side3": {"unit_name": "E", "count": 1},
                                  "side2": {"unit_name": "H", "count": 2}})
    s = card["sides"]["side3"]
    assert s["swing_count"] == 1, "same attacker within SWING_EPS is ONE swing"
    assert s["trample_multi_rate"] == 1.0
    assert s["trample_victims_max"] == 2
