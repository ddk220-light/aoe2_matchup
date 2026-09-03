"""Compare large ranged-siege overlap in one exact live and simulated run.

The report is validation evidence only.  Both simulations use the literal
first-N cells from ``current_ranged_golden_formations.json``; no measured
overlap is fed back into a matchup-specific runtime parameter.
"""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import analyze_live_engagement_participation as live  # noqa: E402


CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31"
)
REPORT_ROOT = (
    ROOT / "calibration" / "reports"
    / "scorpion_onager_diagnostics_2026-08-31"
)
FORMATION_FIXTURE = ROOT / "fixtures" / "current_ranged_golden_formations.json"
OUTPUT = REPORT_ROOT / "siege_overlap_current_engine_2026-08-31.json"


CASES = (
    {
        "key": "heavy_scorpion_vs_hand_cannoneer",
        "family": "ranged_vs_ranged",
        "expected": {2: (542, 17), 3: (5, 27)},
        "auxiliary": {},
        "mechanics": {
            2: {"range": 7.0, "min_range": 2.0, "outline": 0.5, "collision": 0.5},
            3: {"range": 7.0, "min_range": 0.0, "outline": 0.2, "collision": 0.2},
        },
        "simulation": REPORT_ROOT / "candidate6_overlap_scorpion_vs_hc_seed0.json",
    },
    {
        "key": "siege_onager_vs_hussar",
        "family": "ranged_vs_melee",
        "expected": {2: (588, 7), 3: (441, 27)},
        "auxiliary": {4: (448, 9)},
        "mechanics": {
            2: {"range": 9.0, "min_range": 3.0, "outline": 0.5, "collision": 0.5},
            3: {"range": 0.0, "min_range": 0.0, "outline": 0.5, "collision": 0.25},
            4: {"range": 0.0, "min_range": 0.0, "outline": 0.5, "collision": 0.25},
        },
        "simulation": REPORT_ROOT / "candidate6_overlap_onager_vs_hussar_seed0.json",
    },
)


def rounded(value: float, digits: int = 4) -> float:
    return round(value, digits)


def window_summary(rows: list[dict], start: int, end: int, *, live_rows: bool) -> dict:
    selected = [row["2"] for row in rows[start:end]]
    pair_field = "meanBoxOverlapPairs" if live_rows else "meanOverlapPairs"
    units_field = "meanBoxOverlappedUnits" if live_rows else "meanOverlappedUnits"
    depth_field = "meanBoxOverlapDepth" if live_rows else "meanOverlapDepth"
    max_field = "maxBoxOverlapDepth" if live_rows else "maxOverlapDepth"
    pair_seconds = sum(row[pair_field] for row in selected)
    return {
        "seconds": f"{start}-{end}",
        "meanAlive": rounded(statistics.fmean(row["alive"] for row in selected)),
        "meanOverlapPairs": rounded(statistics.fmean(
            row[pair_field] for row in selected
        )),
        "meanOverlapPairShare": rounded(statistics.fmean(
            row[pair_field] / max(row["meanPossiblePairs"], 1e-12)
            for row in selected
        ), 6),
        "meanOverlappedUnits": rounded(statistics.fmean(
            row[units_field] for row in selected
        )),
        "meanOverlappedUnitShare": rounded(statistics.fmean(
            row[units_field] / max(row["alive"], 1e-12)
            for row in selected
        ), 6),
        "pairWeightedMeanDepthTiles": rounded(
            sum(row[pair_field] * row[depth_field] for row in selected)
            / max(pair_seconds, 1e-12),
            6,
        ),
        "maxDepthTiles": rounded(max(row[max_field] for row in selected), 6),
        "meanTripleStacks": rounded(statistics.fmean(
            row["meanTripleStacks"] for row in selected
        )),
        "meanFourStacks": rounded(statistics.fmean(
            row["meanFourStacks"] for row in selected
        )),
        "maxSharedTripleFraction": rounded(max(
            row["maxSharedTripleFraction"] for row in selected
        ), 6),
        "maxSharedFourFraction": rounded(max(
            row["maxSharedFourFraction"] for row in selected
        ), 6),
        "meanNearestFriendlyDistanceTiles": rounded(statistics.fmean(
            row["meanNearestFriendlyDistance"] for row in selected
        ), 6),
    }


def configure(case: dict) -> None:
    live.MATCHUP_KEY = case["key"]
    live.CAPTURE_ROOT = CAPTURE_ROOT / case["key"]
    live.EXPECTED = case["expected"]
    live.AUXILIARY_EXPECTED = case["auxiliary"]
    live.group.EXPECTED = case["expected"]
    live.MECHANICS = case["mechanics"]


def main() -> None:
    capture_manifest = json.loads(
        (CAPTURE_ROOT / "capture_manifest.json").read_text(encoding="utf8")
    )
    formations = json.loads(FORMATION_FIXTURE.read_text(encoding="utf8"))
    results = []
    for case in CASES:
        configure(case)
        live_run = live.decode_run(1)
        simulation = json.loads(case["simulation"].read_text(encoding="utf8"))
        sim_run = simulation["runs"][0]
        captured_matchup = capture_manifest["matchups"][case["key"]]
        formation_source = formations["families"][case["family"]]["source"]
        if captured_matchup["golden"]["sha256"] != formation_source["sha256"]:
            raise RuntimeError(
                f"{case['key']}: capture and formation fixture use different goldens"
            )
        live_rows = live_run["perSecond"]
        sim_rows = sim_run["perSecond"]
        results.append({
            "matchup": case["key"],
            "family": case["family"],
            "siegeOwner": 2,
            "siegeCount": case["expected"][2][1],
            "collisionRadiusTiles": case["mechanics"][2]["collision"],
            "sources": {
                "liveFrames": live_run["framesBin"],
                "simulation": str(case["simulation"]),
                "formationFixture": str(FORMATION_FIXTURE),
                "formationFamily": case["family"],
                "formationSelection": "literal first-N authored cells for each owner",
                "liveGoldenScenario": captured_matchup["golden"]["path"],
                "liveGoldenScenarioSha256": captured_matchup["golden"]["sha256"],
                "formationGoldenScenarioSha256": formation_source["sha256"],
                "goldenScenarioHashMatches": True,
                "liveRun": 1,
                "simulationSeed": sim_run["openingSeed"],
            },
            "outcome": {
                "simulationWinnerOwner": sim_run["winnerOwner"],
                "simulationWinnerHp": sim_run["winnerHp"],
            },
            "windows": {
                "opening0To5": {
                    "live": window_summary(live_rows, 0, 5, live_rows=True),
                    "simulation": window_summary(sim_rows, 0, 5, live_rows=False),
                },
                "engaged5To20": {
                    "live": window_summary(live_rows, 5, 20, live_rows=True),
                    "simulation": window_summary(sim_rows, 5, 20, live_rows=False),
                },
            },
            "perSecond": [{
                "second": second,
                "live": {
                    "overlapPairs": live_rows[second]["2"]["meanBoxOverlapPairs"],
                    "overlappedUnits": live_rows[second]["2"]["meanBoxOverlappedUnits"],
                    "meanDepthTiles": live_rows[second]["2"]["meanBoxOverlapDepth"],
                    "maxDepthTiles": live_rows[second]["2"]["maxBoxOverlapDepth"],
                    "tripleStacks": live_rows[second]["2"]["meanTripleStacks"],
                    "fourStacks": live_rows[second]["2"]["meanFourStacks"],
                },
                "simulation": {
                    "overlapPairs": sim_rows[second]["2"]["meanOverlapPairs"],
                    "overlappedUnits": sim_rows[second]["2"]["meanOverlappedUnits"],
                    "meanDepthTiles": sim_rows[second]["2"]["meanOverlapDepth"],
                    "maxDepthTiles": sim_rows[second]["2"]["maxOverlapDepth"],
                    "tripleStacks": sim_rows[second]["2"]["meanTripleStacks"],
                    "fourStacks": sim_rows[second]["2"]["meanFourStacks"],
                },
            } for second in range(20)],
        })

    report = {
        "schemaVersion": 1,
        "metric": (
            "Axis-aligned collision-box overlap: pair depth is the sum of DAT "
            "collision radii minus Chebyshev center separation."
        ),
        "formationRule": (
            "The current simulation is given the same golden family and literal "
            "first-N authored cells as the corresponding live scenario."
        ),
        "cases": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
