"""Full-rate live diagnostics for the two remaining Heavy Scorpion matchups.

This is validation-only tape forensics.  It records every frames.bin source and
keeps all derived evidence under calibration/.  No observed result is imported
by the runtime engine.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import analyze_live_engagement_participation as live  # noqa: E402


CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31"
)
OUTPUT = (
    ROOT / "calibration" / "reports"
    / "scorpion_hca_hc_deep_dive_2026-09-01" / "live_full_rate.json"
)
WINDOW_SECONDS = 60

MATCHUPS = {
    "heavy_scorpion_vs_hand_cannoneer": {
        "expected": {2: (542, 17), 3: (5, 27)},
        "mechanics": {
            2: {"range": 7.0, "min_range": 2.0, "outline": 0.5, "collision": 0.5},
            3: {"range": 7.0, "min_range": 0.0, "outline": 0.2, "collision": 0.2},
        },
    },
    "heavy_scorpion_vs_heavy_cav_archer": {
        "expected": {2: (542, 18), 3: (474, 27)},
        "mechanics": {
            2: {"range": 7.0, "min_range": 2.0, "outline": 0.5, "collision": 0.5},
            3: {"range": 7.0, "min_range": 0.0, "outline": 0.4, "collision": 0.25},
        },
    },
}


def rounded(value: float) -> float:
    return round(value, 6)


def shot_summary(events: list[dict], owner: int) -> dict:
    selected = [event for event in events if event["owner"] == owner]
    first_by_actor = {}
    for event in sorted(selected, key=lambda row: (row["t"], row["id"])):
        first_by_actor.setdefault(event["id"], event)
    counts = Counter(
        event.get("targetId") for event in first_by_actor.values()
        if event.get("targetId") is not None
    )
    return {
        "starts": len(selected),
        "uniqueStarters": len({event["id"] for event in selected}),
        "firstShotActors": len(first_by_actor),
        "firstShotUniqueTargets": len(counts),
        "firstShotMaximumTargetLoad": max(counts.values(), default=0),
        "firstShotTargetCounts": {
            str(target): count for target, count in sorted(counts.items())
        },
    }


def window_pair_summary(per_second: list[dict], owner: int, start: int, end: int) -> dict:
    rows = [row[str(owner)] for row in per_second[start:end]]
    if not rows:
        return {}
    fields = (
        "meanOverlapPairs", "meanOverlapDepth", "maxOverlapDepth",
        "meanOverlappedUnits", "meanBoxOverlapPairs", "meanBoxOverlapDepth",
        "maxBoxOverlapDepth", "meanBoxOverlappedUnits", "meanTripleStacks",
        "meanFourStacks", "maxSharedTripleFraction", "maxSharedFourFraction",
        "meanNearestFriendlyDistance",
    )
    return {
        field: rounded(statistics.fmean(row[field] for row in rows))
        for field in fields
    }


def decode_matchup(key: str, config: dict) -> dict:
    live.MATCHUP_KEY = key
    live.CAPTURE_ROOT = CAPTURE_ROOT / key
    live.EXPECTED = config["expected"]
    live.group.EXPECTED = config["expected"]
    live.MECHANICS = config["mechanics"]
    live.WINDOW_SECONDS = WINDOW_SECONDS
    runs = [live.decode_run(repeat) for repeat in range(1, 6)]
    return {
        "runs": [{
            "repeat": run["repeat"],
            "framesBin": run["framesBin"],
            "framesBinBytes": run["framesBinBytes"],
            "firstFrameGameSeconds": run["firstFrameGameSeconds"],
            "firstDamageSeconds": run["firstDamageSeconds"],
            "damageByOwner": run["damageByOwner"],
            "shotsByOwner": {
                str(owner): shot_summary(run["attackStartRanges"], owner)
                for owner in (2, 3)
            },
            "windupTargetChanges": run["windupTargetChanges"],
            "targetReacquisitions": run["targetReacquisitions"],
            "overlapWindows": {
                label: {
                    str(owner): window_pair_summary(run["perSecond"], owner, start, end)
                    for owner in (2, 3)
                }
                for label, start, end in (
                    ("0-5", 0, 5), ("5-20", 5, 20), ("20-40", 20, 40)
                )
            },
            "perSecond": run["perSecond"],
            "formationPerSecond": run["formationPerSecond"],
        } for run in runs],
        "meanPerSecond": live.mean_per_second(runs),
    }


def main() -> None:
    requested_matchup = next((
        argument.split("=", 1)[1]
        for argument in sys.argv[1:]
        if argument.startswith("--matchup=")
    ), None)
    selected_matchups = (
        {requested_matchup: MATCHUPS[requested_matchup]}
        if requested_matchup in MATCHUPS else MATCHUPS
    )
    if requested_matchup is not None and requested_matchup not in MATCHUPS:
        raise SystemExit(f"unknown matchup: {requested_matchup}")
    report = {
        "schemaVersion": 1,
        "generatedBy": str(Path(__file__).resolve()),
        "definitions": {
            "euclideanOverlap": (
                "collision-radius sum minus center distance; positive values overlap"
            ),
            "boxOverlap": (
                "collision-radius sum minus Chebyshev center distance; matches the "
                "engine's axis-aligned obstruction boxes"
            ),
            "tripleOrFourStack": (
                "three or four same-owner collision boxes with a positive shared area"
            ),
        },
        "matchups": {
            key: decode_matchup(key, config)
            for key, config in selected_matchups.items()
        },
    }
    output = (
        OUTPUT.with_name(f"live_full_rate_{requested_matchup}.json")
        if requested_matchup is not None else OUTPUT
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(output)


if __name__ == "__main__":
    main()
