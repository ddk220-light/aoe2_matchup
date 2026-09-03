"""Compare mixed-golden live HP/count trajectories with simulator exports.

The live recorder's ``hp.json`` clock is video time.  The game runs at 1.7x,
so rows are placed on the simulator/game clock by multiplying ``game_s`` by
the recorded ``game_speed``.  Captures remain validation evidence only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE_ROOTS = (
    ROOT / "calibration" / "live_observations" / "ranged_matrix_5x_2026-08-29",
    ROOT / "calibration" / "live_observations" / "remaining_six_fresh_5x_2026-08-31",
)
DEFAULT_SIM_ROOT = (
    ROOT / "calibration" / "reports" / "mixed_trajectory_candidate_2026-08-31"
)
DEFAULT_OUTPUT = DEFAULT_SIM_ROOT / "live_vs_sim_trajectory.json"


def interpolate(rows: list[dict], game_second: float, side: str) -> dict:
    timed = [
        (float(row["game_s"]) * float(row.get("game_speed", 1.0)), row[side])
        for row in rows
    ]
    if game_second <= timed[0][0]:
        return timed[0][1]
    if game_second >= timed[-1][0]:
        return timed[-1][1]
    for index in range(1, len(timed)):
        right_t, right = timed[index]
        if right_t < game_second:
            continue
        left_t, left = timed[index - 1]
        fraction = (game_second - left_t) / max(right_t - left_t, 1e-9)
        return {
            "count": left["count"] + (right["count"] - left["count"]) * fraction,
            "hp": left["hp"] + (right["hp"] - left["hp"]) * fraction,
        }
    raise AssertionError("unreachable interpolation interval")


def load_live(capture_roots: list[Path], key: str) -> list[dict]:
    runs = []
    for capture_root in capture_roots:
        manifest = json.loads(
            (capture_root / "capture_manifest.json").read_text(encoding="utf-8")
        )
        for row in manifest["runs"].get(key, []):
            repeat = int(row["repeat"])
            path = (
                capture_root / key / f"run_{repeat:03d}" / "raw recordings"
                / f"{key}.hp.json"
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            game_speed = float(payload.get("game_speed", 1.0))
            rows = [{**sample, "game_speed": game_speed} for sample in payload["rows"]]
            runs.append({
                "captureRoot": str(capture_root.resolve()),
                "repeat": repeat,
                "path": str(path.resolve()),
                "rows": rows,
            })
    return runs


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", action="append", type=Path)
    parser.add_argument("--simulation-root", type=Path, default=DEFAULT_SIM_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--matchup", action="append", default=[])
    args = parser.parse_args()

    capture_roots = [path.resolve() for path in (
        args.capture_root or list(DEFAULT_CAPTURE_ROOTS)
    )]
    simulation_root = args.simulation_root.resolve()
    trajectory_paths = sorted(simulation_root.glob("*_seed0.json"))
    selected = set(args.matchup)
    report = {
        "schemaVersion": 1,
        "clock": "game seconds; live hp.json video timestamps multiplied by its game_speed",
        "captureRoots": [str(path) for path in capture_roots],
        "simulationRoot": str(simulation_root),
        "matchups": {},
    }
    for simulation_path in trajectory_paths:
        key = simulation_path.name.removesuffix("_seed0.json")
        if selected and key not in selected:
            continue
        simulation = json.loads(simulation_path.read_text(encoding="utf-8"))[0]
        live_runs = load_live(capture_roots, key)
        sim_by_second = {
            int(row["seconds"]): row for row in simulation["combatSamples"]
        }
        maximum = min(
            max(sim_by_second),
            int(min(
                max(sample["game_s"] * sample.get("game_speed", 1.0)
                    for sample in run["rows"])
                for run in live_runs
            )),
        )
        rows = []
        for second in range(maximum + 1):
            sim = sim_by_second[second]["byOwner"]
            live = {}
            for owner, side in ((2, "side1"), (3, "side2")):
                samples = [interpolate(run["rows"], second, side) for run in live_runs]
                live[str(owner)] = {
                    "live": mean([sample["count"] for sample in samples]),
                    "hp": mean([sample["hp"] for sample in samples]),
                }
            rows.append({
                "second": second,
                "live": live,
                "simulation": {
                    owner: {field: sim[owner][field] for field in (
                        "live", "hp", "activeAgainstPrincipal", "attackStarts", "damageHits"
                    )}
                    for owner in ("2", "3")
                },
            })
        report["matchups"][key] = {
            "liveSources": [{
                "captureRoot": run["captureRoot"],
                "repeat": run["repeat"],
                "hpJson": run["path"],
            } for run in live_runs],
            "simulationSource": str(simulation_path.resolve()),
            "winnerOwner": simulation["winnerOwner"],
            "winnerHp": simulation["winnerHp"],
            "player4DefeatSeconds": simulation["player4DefeatSeconds"],
            "rows": rows,
        }
        checkpoints = [second for second in (10, 15, 20, 25, 30, 35, 40)
                       if second <= maximum]
        print(key)
        for second in checkpoints:
            row = rows[second]
            print(
                f"  {second:>2}s P2 hp live/sim "
                f"{row['live']['2']['hp']:.0f}/{row['simulation']['2']['hp']:.0f}; "
                f"P3 hp {row['live']['3']['hp']:.0f}/{row['simulation']['3']['hp']:.0f}; "
                f"active sim {row['simulation']['2']['activeAgainstPrincipal']}/"
                f"{row['simulation']['3']['activeAgainstPrincipal']}"
            )

    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
