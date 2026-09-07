"""Parallel, checkpointed execution of engine seeds."""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

from .artifacts import Job
from .config import LabConfig
from .errors import SimulationError
from .io import read_json, utc_now, write_json


def worker_count(requested: int, tasks: int) -> int:
    available = os.cpu_count() or 1
    selected = available if requested == 0 else requested
    return max(1, min(tasks, selected))


def _valid_seed(path: Path, seed: int, plan_hash: str) -> bool:
    if not path.exists():
        return False
    try:
        value = read_json(path)
        return (
            value.get("mode") == "aoe2-lab"
            and value.get("openingSeed") == seed
            and value.get("lab", {}).get("planHash") == plan_hash
            and isinstance(value.get("snapshots"), list)
            and len(value["snapshots"]) > 1
        )
    except (OSError, ValueError):
        return False


def _run_seed(config: LabConfig, job: Job, seed: int) -> Path:
    output = job.simulation_directory / "seeds" / f"seed_{seed:03d}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    plan = read_json(job.plan_path)
    if _valid_seed(output, seed, plan["planHash"]):
        return output
    worker = (
        config.project_root
        / "aoe2x" / "js_simulation" / "tools" / "aoe2lab_worker.mjs"
    )
    log_path = job.logs_directory / f"simulation_seed_{seed:03d}.log"
    completed = subprocess.run(
        [
            config.node,
            str(worker),
            "run-seed",
            "--plan", str(job.plan_path),
            "--seed", str(seed),
            "--output", str(output),
        ],
        capture_output=True,
        text=True,
        cwd=config.project_root,
        timeout=600,
        check=False,
    )
    log_path.write_text(
        f"command: {completed.args!r}\nreturncode: {completed.returncode}\n"
        f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}\n",
        encoding="utf-8",
    )
    if completed.returncode != 0 or not _valid_seed(output, seed, plan["planHash"]):
        detail = (completed.stderr or completed.stdout).strip()
        raise SimulationError(f"seed {seed} failed: {detail}")
    return output


def _signed_score(result: dict) -> float:
    winner = result.get("winnerOwner")
    if winner not in (2, 3):
        return 0.0
    starting = result["startingHpByOwner"][str(winner)]
    sign = 1.0 if winner == 2 else -1.0
    return sign * float(result["winnerHp"]) / float(starting) * 100.0


def summarize_simulation(job: Job, seed_paths: Iterable[Path]) -> dict:
    rows = []
    for path in sorted(seed_paths):
        result = read_json(path)
        rows.append({
            "seed": result["openingSeed"],
            "winnerOwner": result["winnerOwner"],
            "winnerHp": result["winnerHp"],
            "winnerRemainingHpPercent": abs(_signed_score(result)),
            "signedRemainingHpPercent": _signed_score(result),
            "ticks": result["ticks"],
            "finalStateHash": result["finalStateHash"],
            "eventLogHash": result["eventLogHash"],
            "artifact": str(path.relative_to(job.directory)).replace("\\", "/"),
        })
    scores = [row["signedRemainingHpPercent"] for row in rows]
    owners = sorted({row["winnerOwner"] for row in rows})
    summary = {
        "schemaVersion": 1,
        "jobId": job.job_id,
        "generatedAt": utc_now(),
        "seedCount": len(rows),
        "winnerOwners": owners,
        "winnerFlippedAcrossSeeds": len(owners) > 1,
        "meanSignedRemainingHpPercent": sum(scores) / len(scores),
        "minSignedRemainingHpPercent": min(scores),
        "maxSignedRemainingHpPercent": max(scores),
        "seeds": rows,
    }
    write_json(job.simulation_directory / "summary.json", summary)
    return summary


def run_simulation(
    config: LabConfig,
    job: Job,
    *,
    seeds: int,
    workers: int | None = None,
) -> dict:
    if seeds < 1:
        raise SimulationError("seed count must be positive")
    selected_workers = worker_count(
        config.simulation_workers if workers is None else workers, seeds
    )
    job.transition("SIMULATING")
    job.update_section(
        "simulation",
        requestedSeeds=seeds,
        workers=selected_workers,
        startedAt=utc_now(),
    )
    paths: dict[int, Path] = {}
    with ThreadPoolExecutor(max_workers=selected_workers) as executor:
        future_by_seed = {
            executor.submit(_run_seed, config, job, seed): seed
            for seed in range(1, seeds + 1)
        }
        for future in as_completed(future_by_seed):
            seed = future_by_seed[future]
            paths[seed] = future.result()
            job.update_section(
                "simulation",
                completedSeeds=sorted(paths),
                lastCompletedSeed=seed,
            )
    summary = summarize_simulation(job, paths.values())
    job.update_section(
        "simulation",
        completedSeeds=sorted(paths),
        completedAt=utc_now(),
        summary="simulation/summary.json",
    )
    job.transition("SIMULATION_COMPLETE")
    return summary


def run_simulation_batch(
    config: LabConfig,
    jobs: list[Job],
    *,
    seeds: int,
    workers: int | None = None,
) -> dict[str, dict]:
    """Schedule every matchup/seed pair in one CPU-sized pool."""
    tasks = [(job, seed) for job in jobs for seed in range(1, seeds + 1)]
    selected_workers = worker_count(
        config.simulation_workers if workers is None else workers, len(tasks)
    )
    completed: dict[str, dict[int, Path]] = {job.job_id: {} for job in jobs}
    failures: dict[str, list[dict]] = {job.job_id: [] for job in jobs}
    for job in jobs:
        job.transition("SIMULATING")
        job.update_section(
            "simulation", requestedSeeds=seeds, workers=selected_workers, startedAt=utc_now()
        )
    with ThreadPoolExecutor(max_workers=selected_workers) as executor:
        future_by_task = {
            executor.submit(_run_seed, config, job, seed): (job, seed)
            for job, seed in tasks
        }
        for future in as_completed(future_by_task):
            job, seed = future_by_task[future]
            try:
                completed[job.job_id][seed] = future.result()
                job.update_section(
                    "simulation", completedSeeds=sorted(completed[job.job_id])
                )
            except Exception as error:
                row = {
                    "seed": seed,
                    "type": type(error).__name__,
                    "code": getattr(error, "code", "UNEXPECTED_ERROR"),
                    "message": str(error),
                }
                failures[job.job_id].append(row)
                job.update_section(
                    "simulation",
                    completedSeeds=sorted(completed[job.job_id]),
                    failedSeeds=sorted(item["seed"] for item in failures[job.job_id]),
                )
                if len(failures[job.job_id]) == 1:
                    job.record_failure(error, phase="simulation")
    summaries = {}
    for job in jobs:
        if failures[job.job_id]:
            continue
        summary = summarize_simulation(job, completed[job.job_id].values())
        summaries[job.job_id] = summary
        job.update_section(
            "simulation",
            completedSeeds=sorted(completed[job.job_id]),
            completedAt=utc_now(),
            summary="simulation/summary.json",
        )
        job.transition("SIMULATION_COMPLETE")
    return {
        "summaries": summaries,
        "failures": {job_id: rows for job_id, rows in failures.items() if rows},
    }
