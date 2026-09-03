"""AOE2 Lab command-line interface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .artifacts import Job, create_batch, create_job
from .compare import compare_job
from .config import LabConfig, load_config
from .doctor import run_doctor
from .errors import LabError
from .io import read_json
from .live import run_live
from .planner import load_matchup_file, make_request, plan_matchup
from .serve import serve
from .simulation import run_simulation, run_simulation_batch


def _matchup_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--matchup", type=Path, help="JSON or TOML matchup specification")
    parser.add_argument("--side2", help="Player 2 engine unit slug")
    parser.add_argument("--side3", help="Player 3 engine unit slug")
    parser.add_argument("--civ2", help="Player 2 live/display civilization")
    parser.add_argument("--civ3", help="Player 3 live/display civilization")
    parser.add_argument(
        "--balance",
        choices=("equal_resources", "equal_count", "explicit"),
        default="equal_resources",
    )
    parser.add_argument("--count", type=int, default=27)
    parser.add_argument("--n2", type=int)
    parser.add_argument("--n3", type=int)
    parser.add_argument("--cap", type=int, default=27)
    parser.add_argument("--food-weight", type=float, default=1.0)
    parser.add_argument("--wood-weight", type=float, default=1.0)
    parser.add_argument("--gold-weight", type=float, default=1.0)
    parser.add_argument("--job-id")


def _retention_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--retention",
        choices=("stats", "archive", "raw"),
        help=(
            "live artifact policy: stats deletes recordings/raw streams after "
            "validation; archive zips them; raw keeps them expanded"
        ),
    )


def _request_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.matchup:
        if args.side2 or args.side3:
            raise LabError("--matchup cannot be combined with --side2/--side3")
        return load_matchup_file(args.matchup)
    if not args.side2 or not args.side3:
        raise LabError("provide --matchup or both --side2 and --side3")
    return make_request(
        side2=args.side2,
        side3=args.side3,
        civ2=args.civ2,
        civ3=args.civ3,
        balance=args.balance,
        count=args.count,
        n2=args.n2,
        n3=args.n3,
        cap=args.cap,
        food_weight=args.food_weight,
        wood_weight=args.wood_weight,
        gold_weight=args.gold_weight,
        job_id=args.job_id,
    )


def _job(config: LabConfig, request: dict[str, Any]) -> tuple[Job, dict[str, Any]]:
    plan = plan_matchup(config, request)
    job = create_job(config.artifacts_root, plan["jobId"])
    job.initialize(request, plan)
    return job, plan


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _normalize_batch_row(row: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    if "request" in row:
        return row["request"]
    side2 = row.get("side2")
    side3 = row.get("side3")
    if isinstance(side2, str):
        side2 = {"slug": side2, **({"civ": row["civ2"]} if row.get("civ2") else {})}
    if isinstance(side3, str):
        side3 = {"slug": side3, **({"civ": row["civ3"]} if row.get("civ3") else {})}
    balance = row.get("balance", defaults.get("balance", {"mode": "equal_resources"}))
    if isinstance(balance, str):
        balance = {"mode": balance}
    balance = {
        "cap": defaults.get("cap", 27),
        "count": defaults.get("count", 27),
        "weights": defaults.get("weights", {"food": 1, "wood": 1, "gold": 1}),
        **balance,
    }
    return {
        "schemaVersion": 1,
        "side2": side2,
        "side3": side3,
        "balance": balance,
        **({"jobId": row["id"]} if row.get("id") else {}),
    }


def _load_batch(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    value = load_matchup_file(path)
    rows = value.get("matchups")
    if value.get("schemaVersion", value.get("schema_version")) != 1 or not isinstance(rows, list):
        raise LabError("batch file must have schemaVersion=1 and a matchups array")
    defaults = value.get("defaults", {})
    return defaults, [_normalize_batch_row(row, defaults) for row in rows]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aoe2lab",
        description="Portable AoE2 live capture, engine simulation, comparison, and viewer",
    )
    parser.add_argument("--config", type=Path, help="machine-local aoe2lab.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="validate this machine without mutating the game")
    doctor.add_argument("--live", action="store_true", help="include live-capture dependencies")
    doctor.add_argument("--ui", action="store_true", help="also inspect the current AoE2 screen")

    plan = sub.add_parser("plan", help="resolve and print one canonical matchup plan")
    _matchup_arguments(plan)

    simulation = sub.add_parser("simulate", aliases=["sim"], help="run engine seeds in parallel")
    _matchup_arguments(simulation)
    simulation.add_argument("--seeds", type=int)
    simulation.add_argument("--workers", type=int)

    live = sub.add_parser("live", help="run and capture the matchup in AoE2:DE")
    _matchup_arguments(live)
    _retention_argument(live)
    live.add_argument("--repeats", type=int, default=1)
    live.add_argument("--retries", type=int, default=1)

    full = sub.add_parser("run", help="run live, simulation, and comparison")
    _matchup_arguments(full)
    _retention_argument(full)
    full.add_argument("--live-repeats", type=int, default=1)
    full.add_argument("--sim-seeds", type=int)
    full.add_argument("--workers", type=int)
    full.add_argument("--retries", type=int, default=1)
    full.add_argument("--threshold", type=float, default=10.0)

    compare = sub.add_parser("compare", help="compare existing live and simulation artifacts")
    compare.add_argument("job_id")
    compare.add_argument("--threshold", type=float, default=10.0)

    batch = sub.add_parser("batch", help="run a resumable matchup queue")
    batch.add_argument("manifest", type=Path)
    batch.add_argument("--phase", choices=("simulate", "live", "full"), default="simulate")
    batch.add_argument("--seeds", type=int)
    batch.add_argument("--live-repeats", type=int, default=1)
    batch.add_argument("--workers", type=int)
    batch.add_argument("--retries", type=int, default=1)
    batch.add_argument("--threshold", type=float, default=10.0)
    _retention_argument(batch)

    status = sub.add_parser("status", help="show resumable job state")
    status.add_argument("job_id", nargs="?")

    viewer = sub.add_parser("serve", help="serve completed simulation artifacts")
    viewer.add_argument("--host")
    viewer.add_argument("--port", type=int)
    viewer.add_argument("--foreground", action="store_true")
    viewer.add_argument("--tailnet", action="store_true")
    return parser


def _run(args: argparse.Namespace, config: LabConfig) -> int:
    if args.command == "doctor":
        report = run_doctor(config, live=args.live, ui=args.ui)
        _print(report)
        return 0 if report["ok"] else 2
    if args.command == "plan":
        _print(plan_matchup(config, _request_from_args(args)))
        return 0
    if args.command in ("simulate", "sim"):
        job, plan = _job(config, _request_from_args(args))
        try:
            summary = run_simulation(
                config, job, seeds=args.seeds or config.simulation_seeds, workers=args.workers
            )
        except Exception as error:
            job.record_failure(error, phase="simulation")
            raise
        _print({
            "job": job.job_id,
            "plan": plan,
            "simulation": summary,
            "viewerPath": job.manifest()["viewer"]["path"],
        })
        return 0
    if args.command == "live":
        job, plan = _job(config, _request_from_args(args))
        try:
            summary = run_live(
                config,
                job,
                repeats=args.repeats,
                retries=args.retries,
                retention=args.retention,
            )
        except Exception as error:
            job.record_failure(error, phase="live")
            raise
        _print({"job": job.job_id, "plan": plan, "live": summary})
        return 0
    if args.command == "run":
        job, plan = _job(config, _request_from_args(args))
        phase = "live"
        try:
            live = run_live(
                config,
                job,
                repeats=args.live_repeats,
                retries=args.retries,
                retention=args.retention,
            )
            phase = "simulation"
            simulation = run_simulation(
                config,
                job,
                seeds=args.sim_seeds or config.simulation_seeds,
                workers=args.workers,
            )
            phase = "comparison"
            comparison = compare_job(job, threshold_points=args.threshold)
        except Exception as error:
            job.record_failure(error, phase=phase)
            raise
        _print({
            "job": job.job_id,
            "plan": plan,
            "live": live,
            "simulation": simulation,
            "comparison": comparison,
            "viewerPath": job.manifest()["viewer"]["path"],
        })
        return 0
    if args.command == "compare":
        job = create_job(config.artifacts_root, args.job_id)
        _print(compare_job(job, threshold_points=args.threshold))
        return 0
    if args.command == "batch":
        defaults, requests = _load_batch(args.manifest)
        batch_run = create_batch(config.artifacts_root, args.manifest, requests)
        batch_run.transition("PLANNING")
        jobs = []
        failures = {}
        for index, request in enumerate(requests, start=1):
            key = request.get("jobId") or f"request_{index:03d}"
            try:
                job = _job(config, request)[0]
                jobs.append(job)
                # A batch ID is deterministic, so a corrected manifest can reuse a
                # batch that previously failed during planning.  Clear the stale
                # diagnostic once this request plans successfully; otherwise the
                # completed batch misleadingly retains an old failure.
                batch_run.update_job(
                    key, jobId=job.job_id, state="PLANNED", failures=[]
                )
            except Exception as error:
                failures[key] = [{
                    "phase": "planning",
                    "type": type(error).__name__,
                    "code": getattr(error, "code", "UNEXPECTED_ERROR"),
                    "message": str(error),
                }]
                batch_run.update_job(key, state="FAILED", failures=failures[key])
        live_summaries = {}
        if args.phase in ("live", "full"):
            batch_run.transition("CAPTURING_LIVE")
            for job in jobs:
                try:
                    live_summaries[job.job_id] = run_live(
                        config,
                        job,
                        repeats=args.live_repeats,
                        retries=args.retries,
                        retention=args.retention,
                    )
                    batch_run.update_job(job.job_id, state="LIVE_COMPLETE")
                except Exception as error:
                    job.record_failure(error, phase="live")
                    failures[job.job_id] = [{
                        "phase": "live",
                        "type": type(error).__name__,
                        "code": getattr(error, "code", "UNEXPECTED_ERROR"),
                        "message": str(error),
                    }]
                    batch_run.update_job(
                        job.job_id, state="FAILED", failures=failures[job.job_id]
                    )
        simulation_summaries = {}
        if args.phase in ("simulate", "full"):
            batch_run.transition("SIMULATING")
            simulation_batch = run_simulation_batch(
                config,
                jobs,
                seeds=args.seeds or int(defaults.get("seeds", config.simulation_seeds)),
                workers=args.workers,
            )
            simulation_summaries = simulation_batch["summaries"]
            for job_id, rows in simulation_batch["failures"].items():
                failures.setdefault(job_id, []).extend(rows)
            for job_id in simulation_summaries:
                if job_id not in failures:
                    batch_run.update_job(job_id, state="SIMULATION_COMPLETE")
                else:
                    batch_run.update_job(job_id, simulationState="COMPLETE")
            for job_id, rows in simulation_batch["failures"].items():
                batch_run.update_job(job_id, state="FAILED", failures=rows)
        comparisons = {}
        if args.phase == "full":
            for job in jobs:
                if job.job_id in failures:
                    continue
                try:
                    comparisons[job.job_id] = compare_job(
                        job, threshold_points=args.threshold
                    )
                except Exception as error:
                    job.record_failure(error, phase="comparison")
                    failures[job.job_id] = [{
                        "phase": "comparison",
                        "type": type(error).__name__,
                        "code": getattr(error, "code", "UNEXPECTED_ERROR"),
                        "message": str(error),
                    }]
                    batch_run.update_job(
                        job.job_id, state="FAILED", failures=failures[job.job_id]
                    )
                else:
                    batch_run.update_job(job.job_id, state="COMPLETE")
        for job in jobs:
            if job.job_id in failures and job.manifest().get("state") != "FAILED":
                job.transition("FAILED")
        batch_run.transition("COMPLETE_WITH_FAILURES" if failures else "COMPLETE")
        _print({
            "batch": batch_run.batch_id,
            "manifest": str(batch_run.manifest_path),
            "jobs": [job.job_id for job in jobs],
            "live": live_summaries,
            "simulation": simulation_summaries,
            "comparisons": comparisons,
            "failures": failures,
        })
        return 2 if failures else 0
    if args.command == "status":
        if args.job_id:
            _print(create_job(config.artifacts_root, args.job_id).manifest())
            return 0
        runs = config.artifacts_root / "runs"
        manifests = []
        invalid = []
        if runs.exists():
            for path in sorted(runs.glob("*/manifest.json"), reverse=True):
                try:
                    manifests.append(read_json(path))
                except (OSError, ValueError) as error:
                    invalid.append({"path": str(path), "error": str(error)})
        _print({"jobs": manifests, "invalidManifests": invalid})
        return 0
    if args.command == "serve":
        state = serve(
            config,
            foreground=args.foreground,
            tailnet=args.tailnet,
            host=args.host,
            port=args.port,
        )
        if state.get("foreground"):
            return subprocess.call(state["command"], cwd=config.project_root)
        _print(state)
        return 0
    raise AssertionError(args.command)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        raise SystemExit(_run(args, config))
    except LabError as error:
        payload = {
            "error": {
                "code": getattr(error, "code", "LAB_ERROR"),
                "message": str(error),
                "hint": getattr(error, "hint", None),
            }
        }
        print(json.dumps(payload, indent=2), file=sys.stderr)
        raise SystemExit(2) from error
    except Exception as error:
        payload = {
            "error": {
                "code": "UNEXPECTED_ERROR",
                "type": type(error).__name__,
                "message": str(error),
                "hint": "inspect the relevant job failure.json and phase log",
            }
        }
        print(json.dumps(payload, indent=2), file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()
