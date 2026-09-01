"""Compare live Heavy Camel vs Elite Battle Elephant opening geometry.

The analysis reads the five exact project-local frames.bin captures and a
current-engine comparison.  It is validation evidence only; no observation is
fed into the runtime.
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


MATCHUP = "elite_elephant_vs_heavy_camel"
FIRST_WINDOW_SECONDS = 20
FULL_WINDOW_SECONDS = 60
CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31" / MATCHUP
)
SIMULATION = (
    ROOT / "calibration" / "reports" / "heavy_camel_focus_2026-08-31"
    / "current_elephant_seed0.json"
)
OUTPUT = (
    ROOT / "calibration" / "reports" / "heavy_camel_focus_2026-08-31"
    / "elephant_live_opening_5x.json"
)


def rounded(value: float) -> float:
    return round(value, 4)


def target_load(rows: list[dict]) -> dict:
    counts = Counter(row["targetId"] for row in rows)
    return {
        "actors": len(rows),
        "uniqueTargets": len(counts),
        "maximumTargetLoad": max(counts.values(), default=0),
        "targetCounts": {
            str(target): count for target, count in sorted(counts.items())
        },
    }


def summarize_run(run: dict) -> dict:
    first = {
        str(owner): target_load([
            row for row in run["firstTargets"] if row["owner"] == owner
        ])
        for owner in (2, 3)
    }
    return {
        "repeat": run["repeat"],
        "framesBin": run["framesBin"],
        "firstDamageSeconds": run["firstDamageSeconds"],
        "damageByOwner": run["damageByOwner"],
        "firstTargetLoad": first,
        "firstTargets": run["firstTargets"],
        "attackStartsFirst20Seconds": {
            str(owner): sum(
                row["owner"] == owner and row["t"] < FIRST_WINDOW_SECONDS
                for row in run["attackStartRanges"]
            )
            for owner in (2, 3)
        },
        "uniqueAttackersFirst20Seconds": {
            str(owner): len({row["id"] for row in run["attackStartRanges"]
                             if row["owner"] == owner
                             and row["t"] < FIRST_WINDOW_SECONDS})
            for owner in (2, 3)
        },
        "attackStartRanges": run["attackStartRanges"],
        "formationPerSecond": run["formationPerSecond"],
        "targetLoadPerSecond": run["targetLoadPerSecond"],
        "perSecond": run["perSecond"],
    }


def main() -> None:
    live.MATCHUP_KEY = MATCHUP
    live.CAPTURE_ROOT = CAPTURE_ROOT
    live.EXPECTED = {2: (1134, 18), 3: (330, 27)}
    live.AUXILIARY_EXPECTED = {}
    live.group.EXPECTED = live.EXPECTED
    # This matchup diverges mostly after the opening twenty seconds. Decode
    # through every observed elimination (all five complete before 60 s) so
    # target redistribution and active-surface decay can be compared over the
    # whole fight. The compact opening counters below remain explicitly 0-20 s.
    live.WINDOW_SECONDS = FULL_WINDOW_SECONDS
    live.MECHANICS = {
        # DAT: the Elephant's outline/selection half-size is 0.50, but its
        # physical collision half-size is 0.25. Keep these distinct or ordinary
        # same-army spacing is falsely reported as deep Elephant overlap.
        2: {"range": 0.0, "min_range": 0.0, "outline": 0.5, "collision": 0.25},
        3: {"range": 0.0, "min_range": 0.0, "outline": 0.4, "collision": 0.25},
    }
    decoded = [live.decode_run(repeat) for repeat in range(1, 6)]
    runs = [summarize_run(run) for run in decoded]
    mean_per_second = live.mean_per_second(decoded)
    simulation = json.loads(SIMULATION.read_text(encoding="utf8"))["rows"][0]
    report = {
        "schemaVersion": 1,
        "matchup": MATCHUP,
        "sources": {
            "liveFrames": [run["framesBin"] for run in runs],
            "simulation": str(SIMULATION),
            "engine": str(ROOT / "src" / "combat" / "world.js"),
        },
        "liveRuns": runs,
        "liveMeanFirst20Seconds": {
            str(owner): {
                "attackStarts": rounded(statistics.fmean(
                    run["attackStartsFirst20Seconds"][str(owner)] for run in runs
                )),
                "uniqueAttackers": rounded(statistics.fmean(
                    run["uniqueAttackersFirst20Seconds"][str(owner)] for run in runs
                )),
                "damage": rounded(statistics.fmean(
                    run["damageByOwner"][str(owner)]["damage"] for run in runs
                )),
            }
            for owner in (2, 3)
        },
        "liveMeanPerSecond": mean_per_second,
        "simulationSeed0": simulation["simulation"][0],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
