#!/usr/bin/env python3
"""
Capture a deterministic golden baseline of matchup-sims output.

tests/test_simulations.py asserts current output matches .golden/baseline.json,
so refactors of the abstract engine path (simulation.py / best_units.py) can't
silently change behavior. Deliberately does NOT print timing — it produces
stable, byte-comparable JSON.

Coverage: 10 civ pairs (Imperial only — the data model dropped Castle on
2026-06-11) of get_matchup_sims (top/sidekick sections) — a wide-but-cheap
oracle (~15s total runtime). After any INTENDED sim-behavior change,
regenerate and commit on staging:  python .golden/capture_baseline.py
"""
import json
import os
import random
import sys

# Make webapp importable
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "webapp"))

from best_units import get_matchup_sims  # noqa: E402

# Seed BEFORE any sim call so borderline matchups give a reproducible
# answer. The simulation uses the `random` module's global state via
# `random.random()` / `random.choice()`, so seeding here deterministically
# pins every subsequent roll. Production code path is unchanged — this
# seed only exists in the baseline capture and the golden test fixture.
GOLDEN_SEED = 20260411


def _reseed():
    random.seed(GOLDEN_SEED)


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
AGES = ["imperial"]


def _normalize(obj):
    """Drop non-deterministic fields (timing, floats with epsilon wiggle)."""
    if isinstance(obj, dict):
        return {
            k: _normalize(v)
            for k, v in sorted(obj.items())
            if k not in {"elapsed_ms", "timing", "generated_at"}
        }
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    if isinstance(obj, float):
        # Round to 6 decimal places to absorb any ULP-level float drift
        return round(obj, 6)
    return obj


def capture_matchup_sims():
    """Snapshot get_matchup_sims() for 10 civ pairs (Imperial only)."""
    results = {}
    for civ_a, civ_b in MATCHUPS:
        for age in AGES:
            key = f"{civ_a}_vs_{civ_b}_{age}"
            # Reseed before each matchup so the snapshot is insensitive
            # to matchup ordering — any refactor that rearranges the
            # iteration order will still reproduce each entry identically.
            _reseed()
            raw = get_matchup_sims(civ_a, civ_b, age)
            results[key] = _normalize(raw)
    return results


def main():
    baseline = {"matchup_sims": capture_matchup_sims()}
    out_path = os.path.join(HERE, "baseline.json")
    with open(out_path, "w") as f:
        json.dump(baseline, f, indent=2, sort_keys=True, default=str)
    print(f"Wrote {out_path}")
    print(f"  matchup_sims entries: {len(baseline['matchup_sims'])}")


if __name__ == "__main__":
    main()
