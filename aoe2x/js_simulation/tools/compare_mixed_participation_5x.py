"""Compare five live mixed-golden runs with five simulator seeds.

The comparison is aligned independently to each run's Player 4 defeat signal.
It is diagnostic evidence only; none of the measured values are imported by the
runtime simulator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE_ROOT = (
    ROOT / "calibration" / "live_observations"
    / "remaining_six_fresh_5x_2026-08-31"
)
DEFAULT_LIVE_ROOT = (
    ROOT / "calibration" / "reports"
    / "mixed_live_participation_5x_2026-08-31"
)
DEFAULT_SIM_ROOT = (
    ROOT / "calibration" / "reports"
    / "mixed_sim_participation_5x_2026-08-31"
)
DEFAULT_OUTPUT = DEFAULT_SIM_ROOT / "live_vs_sim_participation.json"


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def selected_seconds(rows: list[dict], gate: float, start: int, end: int) -> list[dict]:
    return [
        row for row in rows
        if gate + start <= float(row.get("second", row.get("seconds"))) < gate + end
    ]


def summarize_live(rows: list[dict], owner: str) -> dict:
    sides = [row[owner] for row in rows]
    return {
        "seconds": len(rows),
        "meanAlive": mean([side["alive"] for side in sides]),
        "meanActive": mean([side["active"] for side in sides]),
        "meanNotFiring": mean([side["notFiring"] for side in sides]),
        "attackStarts": sum(side["shotStarts"] for side in sides),
        "damageHits": sum(side["damageHits"] for side in sides),
    }


def summarize_sim(rows: list[dict], owner: str) -> dict:
    sides = [row["byOwner"][owner] for row in rows]
    return {
        "seconds": len(rows),
        "meanAlive": mean([side["live"] for side in sides]),
        "meanActive": mean([
            side["activeAgainstPrincipal"] + side["activeAgainstPlayer4"]
            for side in sides
        ]),
        "meanNotFiring": mean([
            side["live"] - side["activeAgainstPrincipal"]
            - side["activeAgainstPlayer4"]
            for side in sides
        ]),
        "attackStarts": sum(side["attackStarts"] for side in sides),
        "damageHits": sum(side["damageHits"] for side in sides),
    }


def aggregate(run_rows: list[dict], system: str) -> dict:
    result: dict[str, dict] = {}
    for owner in ("2", "3"):
        owner_rows = [run["owners"][owner] for run in run_rows]
        result[owner] = {
            field: mean([float(row[field]) for row in owner_rows])
            for field in (
                "meanAlive", "meanActive", "meanNotFiring",
                "attackStarts", "damageHits",
            )
        }
    return {"system": system, "owners": result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--live-root", type=Path, default=DEFAULT_LIVE_ROOT)
    parser.add_argument("--simulation-root", type=Path, default=DEFAULT_SIM_ROOT)
    parser.add_argument("--window-start", type=int, default=5)
    parser.add_argument("--window-end", type=int, default=25)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    capture_root = args.capture_root.resolve()
    live_root = args.live_root.resolve()
    sim_root = args.simulation_root.resolve()
    gate_report_path = capture_root / "grpc_player4_gate_analysis.json"
    gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    report = {
        "schemaVersion": 1,
        "window": {
            "startSecondsAfterPlayer4Defeat": args.window_start,
            "endSecondsAfterPlayer4Defeat": args.window_end,
        },
        "sources": {
            "gateReport": str(gate_report_path),
            "liveRoot": str(live_root),
            "simulationRoot": str(sim_root),
        },
        "matchups": {},
    }

    for live_path in sorted(live_root.glob("*.json")):
        key = live_path.stem
        sim_path = sim_root / live_path.name
        if not sim_path.exists() or key not in gate_report["matchups"]:
            continue
        live = json.loads(live_path.read_text(encoding="utf-8"))
        sims = json.loads(sim_path.read_text(encoding="utf-8"))
        live_gates = {
            int(run["repeat"]): float(run["player4"]["defeat"]["time_game_seconds"])
            for run in gate_report["matchups"][key]["runs"]
        }
        live_runs = []
        for run in live["runs"]:
            repeat = int(run["repeat"])
            gate = live_gates[repeat]
            rows = selected_seconds(
                run["perSecond"], gate, args.window_start, args.window_end
            )
            live_runs.append({
                "repeat": repeat,
                "gateSeconds": gate,
                "owners": {
                    owner: summarize_live(rows, owner) for owner in ("2", "3")
                },
            })
        sim_runs = []
        for run in sims:
            gate = float(run["player4DefeatSeconds"])
            rows = selected_seconds(
                run["combatSamples"], gate, args.window_start, args.window_end
            )
            sim_runs.append({
                "openingSeed": int(run["openingSeed"]),
                "gateSeconds": gate,
                "winnerOwner": int(run["winnerOwner"]),
                "winnerHp": float(run["winnerHp"]),
                "owners": {
                    owner: summarize_sim(rows, owner) for owner in ("2", "3")
                },
            })
        live_mean = aggregate(live_runs, "live")
        sim_mean = aggregate(sim_runs, "simulation")
        delta = {
            owner: {
                field: sim_mean["owners"][owner][field]
                - live_mean["owners"][owner][field]
                for field in live_mean["owners"][owner]
            }
            for owner in ("2", "3")
        }
        report["matchups"][key] = {
            "liveSource": str(live_path),
            "simulationSource": str(sim_path),
            "liveRuns": live_runs,
            "simulationRuns": sim_runs,
            "liveMean": live_mean["owners"],
            "simulationMean": sim_mean["owners"],
            "simulationMinusLive": delta,
        }
        print(key)
        for owner in ("2", "3"):
            live_owner = live_mean["owners"][owner]
            sim_owner = sim_mean["owners"][owner]
            print(
                f"  P{owner}: active {live_owner['meanActive']:.1f}/"
                f"{sim_owner['meanActive']:.1f}, hits "
                f"{live_owner['damageHits']:.1f}/{sim_owner['damageHits']:.1f}, "
                f"starts {live_owner['attackStarts']:.1f}/"
                f"{sim_owner['attackStarts']:.1f} (live/sim)"
            )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
