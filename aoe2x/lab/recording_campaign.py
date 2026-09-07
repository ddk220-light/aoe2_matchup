"""Resumable serial recorder campaign with durable ten-match reports."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .cli import _job, _load_batch
from .config import load_config
from .io import read_json, utc_now, write_json
from .live import run_live
from .recording import validate_recording_bundle


def checkpoint(directory: Path, state: dict, *, report: bool = False) -> None:
    state["updatedAt"] = utc_now()
    state["completed"] = sum(row["status"] == "verified" for row in state["results"])
    state["failed"] = sum(row["status"] == "failed" for row in state["results"])
    write_json(directory / "status.json", state)
    if report:
        number = len(state["results"])
        write_json(directory / f"report_{number:03}.json", state)
        lines = [f"# Recorder report: {number}/{state['total']} matchups",
                 "", f"State: {state['state']}. Verified: {state['completed']}. Failed: {state['failed']}.",
                 "", "Verified means scenario, raw-file checksums, gRPC starting counts and elimination, and video export passed automated validation. It does not establish simulation accuracy or visual quality.",
                 "", "| Matchup | Status | Details |", "|---|---|---|"]
        for row in state["results"]:
            detail = row.get("error") or f"{row['durationSeconds']:.3f}s; {row['framesBytes']} gRPC bytes; {row['runDirectory']}"
            lines.append(f"| {row['jobId']} | {row['status']} | {str(detail).replace('|', '/').replace(chr(10), ' ')} |")
        (directory / f"report_{number:03}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(manifest: Path, directory: Path) -> int:
    config = load_config()
    _, requests = _load_batch(manifest)
    # Plan the complete queue before any game interaction.
    jobs = [_job(config, request)[0] for request in requests]
    state = {"schemaVersion": 1, "pid": os.getpid(), "manifest": str(manifest.resolve()),
             "startedAt": utc_now(), "state": "RUNNING", "total": len(jobs),
             "currentJob": None, "results": [], "retention": "raw",
             "purpose": "Preserve raw gameplay and gRPC frames for later overlays and comparison to simulation."}
    checkpoint(directory, state)
    consecutive_failures = 0
    for job in jobs:
        if (directory / "STOP").exists():
            state["state"] = "STOPPED"
            break
        state["currentJob"] = job.job_id
        checkpoint(directory, state)
        try:
            run_live(config, job, repeats=1, retries=0, retention="raw", mode="recorder")
            run_directory = job.live_directory / "run_001"
            bundle = validate_recording_bundle(run_directory, read_json(job.plan_path))
            state["results"].append({"jobId": job.job_id, "status": "verified",
                "runDirectory": str(run_directory),
                "durationSeconds": bundle["presentation"]["media"]["durationSeconds"],
                "framesBytes": bundle["files"]["frames"]["bytes"]})
            consecutive_failures = 0
        except Exception as error:
            job.record_failure(error, phase="recording_campaign")
            state["results"].append({"jobId": job.job_id, "status": "failed",
                                     "error": f"{type(error).__name__}: {error}"})
            consecutive_failures += 1
        checkpoint(directory, state, report=len(state["results"]) % 10 == 0 or consecutive_failures > 0)
        if consecutive_failures >= 3:
            state["state"] = "STOPPED_AFTER_ERRORS"
            break
    else:
        state["state"] = "COMPLETE_WITH_FAILURES" if state["failed"] else "COMPLETE"
    state["currentJob"] = None
    checkpoint(directory, state, report=True)
    return 0 if state["state"] == "COMPLETE" else 2


def main() -> None:
    import msvcrt
    import sys

    # Detached Windows processes otherwise inherit a legacy code page; the
    # scenario parser prints Unicode progress symbols even to redirected logs.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--reports", type=Path, required=True)
    args = parser.parse_args()
    args.reports.mkdir(parents=True, exist_ok=True)
    # A Windows process lock prevents two resumed campaigns driving the same game.
    with (load_config().artifacts_root / "recorder-campaign.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            raise SystemExit(run(args.manifest, args.reports))
        except Exception as error:
            path = args.reports / "status.json"
            state = read_json(path) if path.exists() else {"results": [], "total": 0}
            state.update(state="CRASHED", error=f"{type(error).__name__}: {error}")
            checkpoint(args.reports, state, report=True)
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    main()
