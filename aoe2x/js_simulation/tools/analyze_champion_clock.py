"""Analyze recorder timestamps without treating them as simulation-clock proof."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


ENGINE_HYPOTHESIS_HZ = 60
ENGINE_HYPOTHESIS_CLAIM = "provisional_not_published"
TICK_CANDIDATES_HZ = (50, 60)


def analyze_clock(truth: dict) -> dict:
    """Return complete timestamp evidence and an explicit 60-Hz hypothesis.

    The evidence identifies recorder cadence and evaluates both integer-tick
    candidates.  It intentionally does not inspect combat outcomes or HP.
    """
    ratios_analyzed = list(truth["ratios"])
    run_inventory = {
        ratio: [run["tag"] for run in truth["ratios"][ratio]["runs"]]
        for ratio in ratios_analyzed
    }
    runs = [
        run
        for ratio in ratios_analyzed
        for run in truth["ratios"][ratio]["runs"]
    ]
    intervals = _same_attacker_intervals(runs)
    return {
        "archive": truth["archive"],
        "zip_sha256": truth["zip_sha256"],
        "ratios_analyzed": ratios_analyzed,
        "run_inventory": run_inventory,
        "runs_analyzed": len(runs),
        "recorder_stream_hz": _observed_rates(runs, "stream_hz"),
        "position_sample_hz": _observed_rates(runs, "position_sample_hz"),
        "same_attacker_intervals_s": _interval_summary(intervals),
        "equal_timestamp_attacks": _equal_timestamp_summary(runs),
        "tick_residuals_s": {
            str(hz): _tick_residuals(intervals, hz) for hz in TICK_CANDIDATES_HZ
        },
        "engine_hypothesis_hz": ENGINE_HYPOTHESIS_HZ,
        "claim": ENGINE_HYPOTHESIS_CLAIM,
        "selection_basis": (
            "60 Hz is a provisional simulation hypothesis; it is not selected "
            "from HP, winner, or outcome accuracy."
        ),
    }


def _observed_rates(runs: list[dict], field: str) -> list[float]:
    return sorted({float(run["metadata"][field]) for run in runs})


def _same_attacker_intervals(runs: list[dict]) -> list[float]:
    intervals = []
    for run in runs:
        previous_by_attacker = {}
        for event in run["damage_events"]:
            attacker = event["attacker"]
            timestamp = float(event["t"])
            if attacker in previous_by_attacker:
                intervals.append(round(timestamp - previous_by_attacker[attacker], 9))
            previous_by_attacker[attacker] = timestamp
    return intervals


def _interval_summary(intervals: list[float]) -> dict:
    if not intervals:
        raise ValueError("clock analysis requires same-attacker damage intervals")
    return {
        "count": len(intervals),
        "values": intervals,
        "min": min(intervals),
        "median": median(intervals),
        "max": max(intervals),
    }


def _equal_timestamp_summary(runs: list[dict]) -> dict:
    per_run = []
    total_attacks = 0
    total_timestamps = 0
    max_attacks = 0
    for run in runs:
        grouped = defaultdict(int)
        for event in run["damage_events"]:
            grouped[float(event["t"])] += 1
        equal_groups = [count for count in grouped.values() if count > 1]
        total_attacks += sum(equal_groups)
        total_timestamps += len(equal_groups)
        max_attacks = max(max_attacks, max(grouped.values(), default=0))
        per_run.append(
            {
                "tag": run["tag"],
                "timestamps_with_multiple_attacks": len(equal_groups),
                "attacks_at_equal_timestamps": sum(equal_groups),
            }
        )
    return {
        "timestamps_with_multiple_attacks": total_timestamps,
        "attacks_at_equal_timestamps": total_attacks,
        "max_attacks_at_one_timestamp": max_attacks,
        "per_run": per_run,
    }


def _tick_residuals(intervals: list[float], hz: int) -> dict:
    samples = []
    tick_counts = Counter()
    for interval in intervals:
        nearest_ticks = round(interval * hz)
        residual = round(interval - nearest_ticks / hz, 9)
        tick_counts[nearest_ticks] += 1
        samples.append(
            {
                "interval_s": interval,
                "nearest_ticks": nearest_ticks,
                "residual_s": residual,
            }
        )
    absolute_residuals = [abs(sample["residual_s"]) for sample in samples]
    return {
        "hz": hz,
        "count": len(samples),
        "nearest_tick_counts": {
            str(ticks): count for ticks, count in sorted(tick_counts.items())
        },
        "mean_absolute_residual_s": round(sum(absolute_residuals) / len(samples), 9),
        "max_absolute_residual_s": max(absolute_residuals),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    report = analyze_clock(truth)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
