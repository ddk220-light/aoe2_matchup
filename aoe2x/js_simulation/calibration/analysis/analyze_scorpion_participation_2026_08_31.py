"""Focused live-vs-simulation participation analysis for Heavy Scorpion.

This is validation-only tape forensics.  It reuses the full-rate decoder and
records every exact frames.bin source in the output; no measured outcome is
fed back into the runtime.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import analyze_live_engagement_participation as live  # noqa: E402


MATCHUP = "heavy_scorpion_vs_hand_cannoneer"
CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "expanded_roster_5x_2026-08-31" / MATCHUP
)
SIMULATION = (
    ROOT / "calibration" / "reports" / "elite_skirm_diagnostics_2026-08-31"
    / "current_scorpion_vs_hand_cannoneer_timeline.json"
)
OUTPUT = (
    ROOT / "calibration" / "reports" / "scorpion_onager_diagnostics_2026-08-31"
    / "scorpion_vs_hand_cannoneer_participation.json"
)


def rounded(value: float) -> float:
    return round(value, 4)


def window_summary(rows: list[dict], seconds: int) -> dict:
    output = {}
    for owner in (2, 3):
        selected = [row[str(owner)] for row in rows[:seconds]]
        alive_seconds = sum(row["alive"] for row in selected)
        output[str(owner)] = {
            "meanAlive": rounded(statistics.fmean(row["alive"] for row in selected)),
            "meanFiring": rounded(statistics.fmean(row["firing"] for row in selected)),
            "firingShareOfAlive": rounded(
                sum(row["firing"] for row in selected) / max(alive_seconds, 1e-9)
            ),
            "meanActive": rounded(statistics.fmean(row["active"] for row in selected)),
            "activeShareOfAlive": rounded(
                sum(row["active"] for row in selected) / max(alive_seconds, 1e-9)
            ),
            "meanInRangeNotFiring": rounded(
                statistics.fmean(row["inRangeNotFiring"] for row in selected)
            ),
            "meanSeekingMoving": rounded(
                statistics.fmean(row["seekingMoving"] for row in selected)
            ),
            "meanSeekingStationary": rounded(
                statistics.fmean(row["seekingStationary"] for row in selected)
            ),
            "meanUntargetedStationary": rounded(
                statistics.fmean(row["untargetedStationary"] for row in selected)
            ),
            "shotStarts": rounded(sum(row["shotStarts"] for row in selected)),
            "damageHits": rounded(sum(row["damageHits"] for row in selected)),
        }
    return output


def scorpion_rank_summary(run: dict) -> dict:
    snapshot = run["openingSnapshots"][0]
    scorpions = [unit for unit in snapshot["units"] if unit["owner"] == 2]
    enemies = [unit for unit in snapshot["units"] if unit["owner"] == 3]
    sx = statistics.fmean(unit["x"] for unit in scorpions)
    sy = statistics.fmean(unit["y"] for unit in scorpions)
    ex = statistics.fmean(unit["x"] for unit in enemies)
    ey = statistics.fmean(unit["y"] for unit in enemies)
    length = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
    dx = (ex - sx) / length
    dy = (ey - sy) / length
    starts = Counter(
        event["id"] for event in run["attackStartRanges"]
        if event["owner"] == 2
    )
    ranked = sorted(({
        "id": unit["id"],
        "towardEnemyProjection": rounded((unit["x"] - sx) * dx + (unit["y"] - sy) * dy),
        "shotStartsFirst20s": starts[unit["id"]],
    } for unit in scorpions), key=lambda row: (-row["towardEnemyProjection"], row["id"]))
    split = (len(ranked) + 1) // 2
    for index, row in enumerate(ranked):
        row["frontToBackRank"] = index + 1
    def half(rows: list[dict]) -> dict:
        return {
            "units": len(rows),
            "unitsThatStartedShot": sum(row["shotStartsFirst20s"] > 0 for row in rows),
            "shotStartsFirst20s": sum(row["shotStartsFirst20s"] for row in rows),
        }
    return {
        "frontHalf": half(ranked[:split]),
        "backHalf": half(ranked[split:]),
        "units": ranked,
    }


def mean_target_load(runs: list[dict]) -> list[dict]:
    rows = []
    for second in range(20):
        row = {"second": second}
        for owner in (2, 3):
            assigned = [run["targetLoadPerSecond"][second][str(owner)]["assigned"]
                        for run in runs]
            attacking = [run["targetLoadPerSecond"][second][str(owner)]["attacking"]
                         for run in runs]
            row[str(owner)] = {
                "assignedActors": rounded(statistics.fmean(value["actors"] for value in assigned)),
                "assignedUniqueTargets": rounded(statistics.fmean(
                    value["uniqueTargets"] for value in assigned
                )),
                "assignedMaximumLoad": rounded(statistics.fmean(
                    value["maximumLoad"] for value in assigned
                )),
                "attackingActors": rounded(statistics.fmean(value["actors"] for value in attacking)),
                "attackingUniqueTargets": rounded(statistics.fmean(
                    value["uniqueTargets"] for value in attacking
                )),
                "attackingMaximumLoad": rounded(statistics.fmean(
                    value["maximumLoad"] for value in attacking
                )),
            }
        rows.append(row)
    return rows


def main() -> None:
    live.MATCHUP_KEY = MATCHUP
    live.CAPTURE_ROOT = CAPTURE_ROOT
    live.EXPECTED = {2: (542, 17), 3: (5, 27)}
    live.group.EXPECTED = live.EXPECTED
    live.MECHANICS = {
        2: {"range": 7.0, "min_range": 2.0, "outline": 0.5, "collision": 0.5},
        3: {"range": 7.0, "min_range": 0.0, "outline": 0.2, "collision": 0.2},
    }
    live_runs = [live.decode_run(repeat) for repeat in range(1, 6)]
    live_mean = live.mean_per_second(live_runs)
    live.MATCHUP_KEY = "heavy_scorpion_vs_heavy_cav_archer"
    live.CAPTURE_ROOT = (
        ROOT / "calibration" / "live_observations"
        / "expanded_roster_5x_2026-08-31" / live.MATCHUP_KEY
    )
    live.EXPECTED = {2: (542, 18), 3: (474, 27)}
    live.group.EXPECTED = live.EXPECTED
    live.MECHANICS = {
        2: {"range": 7.0, "min_range": 2.0, "outline": 0.5, "collision": 0.5},
        3: {"range": 7.0, "min_range": 0.0, "outline": 0.4, "collision": 0.25},
    }
    hca_live_runs = [live.decode_run(repeat) for repeat in range(1, 6)]
    hca_live_mean = live.mean_per_second(hca_live_runs)
    simulation = json.loads(SIMULATION.read_text(encoding="utf8"))
    simulation_mean = simulation["meanPerSecond"]
    report = {
        "schemaVersion": 1,
        "matchup": MATCHUP,
        "sources": {
            "liveFrames": [run["framesBin"] for run in live_runs],
            "simulation": str(SIMULATION),
            "engine": str(ROOT / "src" / "combat" / "world.js"),
        },
        "definitions": {
            "firing": "action state 7 (windup) with a resolved hostile target in range",
            "active": "firing or reloading with a resolved hostile target in range",
            "seekingStationary": "hostile target is out of range and speed <= 0.05 tiles/s",
        },
        "windows": {
            str(seconds): {
                "live": window_summary(live_mean, seconds),
                "simulation": window_summary(simulation_mean, seconds),
            }
            for seconds in (5, 10, 20)
        },
        "liveAttackStartRanges": live.summarize_range_events([
            event for run in live_runs for event in run["attackStartRanges"]
        ]),
        "simulationAttackStartRanges": live.summarize_range_events([
            event for run in simulation["runs"] for event in run["attackStartRanges"]
        ]),
        "liveRuns": [{
            "repeat": run["repeat"],
            "framesBin": run["framesBin"],
            "damageByOwner": run["damageByOwner"],
            "scorpionFormationRanks": scorpion_rank_summary(run),
            "firstTargets": run["firstTargets"],
            "attackStartRanges": run["attackStartRanges"],
            "targetLoadPerSecond": run["targetLoadPerSecond"],
        } for run in live_runs],
        "liveCrossCheckHeavyCavArcher": {
            "matchup": live.MATCHUP_KEY,
            "sources": [run["framesBin"] for run in hca_live_runs],
            "windows": {
                str(seconds): window_summary(hca_live_mean, seconds)
                for seconds in (5, 10, 20)
            },
            "runs": [{
                "repeat": run["repeat"],
                "framesBin": run["framesBin"],
                "scorpionFormationRanks": scorpion_rank_summary(run),
            } for run in hca_live_runs],
            "meanPerSecond": hca_live_mean,
        },
        "simulationRuns": [{
            "openingSeed": run["openingSeed"],
            "winnerOwner": run["winnerOwner"],
            "winnerHp": run["winnerHp"],
            "eventSummary": run["eventSummary"],
        } for run in simulation["runs"]],
        "liveMeanPerSecond": live_mean,
        "liveMeanTargetLoadPerSecond": mean_target_load(live_runs),
        "simulationMeanPerSecond": simulation_mean,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
