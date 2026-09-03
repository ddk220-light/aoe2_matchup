"""Decode first target and attack-start geometry for all five Onager captures."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import analyze_live_engagement_participation as live  # noqa: E402


MATCHUP = "siege_onager_vs_hussar"
CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31" / MATCHUP
)
OUTPUT = (
    ROOT / "calibration" / "reports" / "scorpion_onager_diagnostics_2026-08-31"
    / "onager_vs_hussar_opening_5x.json"
)


def main() -> None:
    live.MATCHUP_KEY = MATCHUP
    live.CAPTURE_ROOT = CAPTURE_ROOT
    live.EXPECTED = {2: (588, 7), 3: (441, 27)}
    live.AUXILIARY_EXPECTED = {4: (448, 9)}
    live.group.EXPECTED = live.EXPECTED
    live.MECHANICS = {
        2: {"range": 9.0, "min_range": 3.0, "outline": 0.5, "collision": 0.5},
        3: {"range": 0.0, "min_range": 0.0, "outline": 0.5, "collision": 0.25},
        4: {"range": 0.0, "min_range": 0.0, "outline": 0.5, "collision": 0.25},
    }
    runs = [live.decode_run(repeat) for repeat in range(1, 6)]
    report = {
        "schemaVersion": 1,
        "matchup": MATCHUP,
        "sources": [run["framesBin"] for run in runs],
        "runs": [{
            "repeat": run["repeat"],
            "framesBin": run["framesBin"],
            "firstTargets": run["firstTargets"],
            "attackStartRanges": run["attackStartRanges"],
            "formationPerSecond": run["formationPerSecond"],
        } for run in runs],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
