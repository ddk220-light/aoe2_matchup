import json
import os
import random

import pytest

from aoe2x.advisor.best_units import get_matchup_sims

GOLDEN_SEED = 20260411
BASELINE_PATH = os.path.join(os.path.dirname(__file__), "..", ".golden", "baseline.json")

MATCHUPS = [
    ("Aztecs", "Armenians"),
    ("Franks", "Britons"),
    ("Mongols", "Teutons"),
    ("Huns", "Byzantines"),
    ("Chinese", "Japanese"),
    ("Mayans", "Persians"),
    ("Vikings", "Goths"),
    ("Turks", "Saracens"),
    ("Celts", "Koreans"),
    ("Spanish", "Berbers"),
]
# Imperial-only data model (2026-06-11): the golden baseline carries only
# Imperial entries (10 pairs x 1 age).
AGES = ["imperial"]

SCHEMA_PAIRS = [
    (civ_a, civ_b, age)
    for civ_a, civ_b in MATCHUPS[:3]
    for age in AGES
]
GOLDEN_KEYS = [
    f"{civ_a}_vs_{civ_b}_{age}"
    for civ_a, civ_b in MATCHUPS
    for age in AGES
]


def _normalize(obj):
    if isinstance(obj, dict):
        return {
            k: _normalize(v)
            for k, v in sorted(obj.items())
            if k not in {"elapsed_ms", "timing", "generated_at"}
        }
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


# --- Sanity test ---

def test_baseline_exists_and_has_10_entries():
    assert os.path.exists(BASELINE_PATH), f"Baseline not found at {BASELINE_PATH}"
    with open(BASELINE_PATH) as f:
        data = json.load(f)
    assert len(data["matchup_sims"]) == 10


# --- Schema tests ---

@pytest.mark.parametrize("civ_a,civ_b,age", SCHEMA_PAIRS, ids=[
    f"{a.lower()}_vs_{b.lower()}_{age}"
    for a, b, age in SCHEMA_PAIRS
])
def test_matchup_sims_schema(civ_a, civ_b, age):
    random.seed(GOLDEN_SEED)
    result = get_matchup_sims(civ_a, civ_b, age)
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "left" in result and len(result["left"]) > 0
    assert "right" in result and len(result["right"]) > 0
    for side_key in ("left", "right"):
        for slug, unit_data in result[side_key].items():
            for field in ("wins", "pop_wins", "eco_wins", "losses"):
                assert field in unit_data, f"{side_key}/{slug} missing field '{field}'"
            assert isinstance(unit_data["wins"], list)
            assert isinstance(unit_data["losses"], list)


# --- Golden regression tests ---

@pytest.mark.parametrize("key", GOLDEN_KEYS, ids=GOLDEN_KEYS)
def test_golden_regression(key):
    with open(BASELINE_PATH) as f:
        baseline = json.load(f)["matchup_sims"]

    # Parse the key to get civ_a, civ_b, age
    # Key format: "{CivA}_vs_{CivB}_{age}"
    civ_a, rest = key.split("_vs_", 1)
    civ_b, age = rest.rsplit("_", 1)

    random.seed(GOLDEN_SEED)
    raw = get_matchup_sims(civ_a, civ_b, age)
    actual = _normalize(raw)

    expected = baseline[key]
    assert actual == expected, (
        f"Golden regression failed for {key}. "
        f"Re-run .golden/capture_baseline.py to regenerate if behavior change is intentional."
    )
