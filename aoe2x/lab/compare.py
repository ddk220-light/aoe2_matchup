"""Live-versus-engine comparison using remaining-HP percentage points."""

from __future__ import annotations

from .artifacts import Job
from .errors import ComparisonError
from .io import read_json, utc_now, write_json


def compare_job(job: Job, *, threshold_points: float = 10.0) -> dict:
    live_path = job.live_directory / "summary.json"
    simulation_path = job.simulation_directory / "summary.json"
    if not live_path.exists() or not simulation_path.exists():
        raise ComparisonError("comparison requires completed live and simulation summaries")
    live = read_json(live_path)
    simulation = read_json(simulation_path)
    live_score = float(live["meanSignedRemainingHpPercent"])
    simulation_score = float(simulation["meanSignedRemainingHpPercent"])
    live_winners = set(live["winnerOwners"])
    simulation_winners = set(simulation["winnerOwners"])
    wrong_winner_seeds = [
        row["seed"] for row in simulation.get("seeds", [])
        if row.get("winnerOwner") not in live_winners
    ]
    wrong_winner = bool(wrong_winner_seeds)
    delta = simulation_score - live_score
    seed_rows = simulation.get("seeds", [])
    if not seed_rows:
        raise ComparisonError("simulation summary has no completed seed rows")
    if wrong_winner_seeds:
        representative_seed = wrong_winner_seeds[0]
        representative_reason = "actual wrong-winner seed"
    else:
        representative = min(
            seed_rows,
            key=lambda row: abs(
                float(row["signedRemainingHpPercent"]) - simulation_score
            ),
        )
        representative_seed = int(representative["seed"])
        representative_reason = "completed seed closest to simulation mean"
    viewer_path = f"/?mode=lab&job={job.job_id}&seed={representative_seed}"
    report = {
        "schemaVersion": 1,
        "jobId": job.job_id,
        "generatedAt": utc_now(),
        "metric": "signed remaining HP percentage-point delta",
        "live": {
            "meanSignedRemainingHpPercent": live_score,
            "winnerOwners": sorted(live_winners),
            "repeats": live["repeatCount"],
        },
        "simulation": {
            "meanSignedRemainingHpPercent": simulation_score,
            "winnerOwners": sorted(simulation_winners),
            "seeds": simulation["seedCount"],
        },
        "deltaPoints": delta,
        "absoluteDeltaPoints": abs(delta),
        "wrongWinner": wrong_winner,
        "wrongWinnerSeeds": wrong_winner_seeds,
        "representativeSeed": representative_seed,
        "representativeReason": representative_reason,
        "viewerPath": viewer_path,
        "thresholdPoints": threshold_points,
        "accepted": not wrong_winner and abs(delta) <= threshold_points,
    }
    write_json(job.directory / "comparison.json", report)
    job.update_section("comparison", report="comparison.json", **report)
    job.update_section(
        "viewer",
        path=viewer_path,
        seed=representative_seed,
        reason=representative_reason,
    )
    job.transition("COMPLETE")
    return report
