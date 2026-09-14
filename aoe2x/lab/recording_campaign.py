"""Resumable serial recorder campaign with durable ten-match reports."""
from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .cli import _job, _load_batch
from .config import load_config
from .io import read_json, utc_now, write_json
from .live import run_live, _summarize_live
from .battle_clip import prepare_battle_clip
from .recording import validate_recording_bundle


def checkpoint(directory: Path, state: dict, *, report: bool = False) -> None:
    state["updatedAt"] = utc_now()
    state["completed"] = sum(row["status"] == "verified" for row in state["results"])
    state["failed"] = sum(row["status"] == "failed" for row in state["results"])
    state["pendingExports"] = sum(row["status"] == "finalizing" for row in state["results"])
    state["captured"] = sum("captureWallSeconds" in row for row in state["results"])
    write_json(directory / "status.json", state)
    if report:
        number = len(state["results"])
        write_json(directory / f"report_{number:03}.json", state)
        lines = [f"# Recorder report: {number}/{state['total']} matchups",
                 "", f"State: {state['state']}. Verified: {state['completed']}. Failed: {state['failed']}.",
                 "", "Verified means scenario, raw-file checksums, gRPC starting counts and elimination, and video export passed automated validation. It does not establish simulation accuracy or visual quality.",
                 "", "| Matchup | Status | Details |", "|---|---|---|"]
        for row in state["results"]:
            detail = row.get("error") or ("Raw capture saved; finishing video in background" if row["status"] == "finalizing" else f"{row['durationSeconds']:.3f}s; {row['framesBytes']} gRPC bytes; {row['runDirectory']}")
            lines.append(f"| {row['jobId']} | {row['status']} | {str(detail).replace('|', '/').replace(chr(10), ' ')} |")
        (directory / f"report_{number:03}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def finalize_recording(job) -> dict:
    """Resume-safe offline lane; publish verified only after export and validation."""
    started = time.monotonic()
    directory = job.live_directory / "run_001"
    plan = read_json(job.plan_path)
    clip = prepare_battle_clip(directory, plan)
    manifest = read_json(directory / "manifest.json")
    manifest["battleVideo"] = clip["video"]
    write_json(directory / "manifest.json", manifest)
    bundle = validate_recording_bundle(directory, plan)
    _summarize_live(job, 1)
    return {"durationSeconds": bundle["presentation"]["media"]["durationSeconds"],
            "framesBytes": bundle["files"]["frames"]["bytes"],
            "finalizationWallSeconds": round(time.monotonic() - started, 3)}


def run(manifest: Path, directory: Path, *, release_capture=None) -> int:
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
    pending = {}

    def collect():
        for future, (job, row) in list(pending.items()):
            if not future.done():
                continue
            del pending[future]
            try:
                row.update(future.result(), status="verified")
            except Exception as error:
                job.record_failure(error, phase="recording_finalization")
                row.update(status="failed", error=f"{type(error).__name__}: {error}")
            checkpoint(directory, state, report=True)
            if row["status"] == "verified" and state["completed"] % 10 == 0:
                write_json(directory / f"verified_{state['completed']:03}.json", state)

    # Only this thread drives the game. Encoding/checksums use a single bounded
    # CPU worker and independent run directories; captures are durable first.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="recorder-finalize") as pool:
        for job in jobs:
            collect()
            if (directory / "STOP").exists():
                state["state"] = "STOPPED"
                break
            state["currentJob"] = job.job_id
            checkpoint(directory, state)
            started = time.monotonic()
            try:
                run_live(config, job, repeats=1, retries=0, retention="raw",
                         mode="recorder", defer_clip=True)
                row = {"jobId": job.job_id, "status": "finalizing",
                       "runDirectory": str(job.live_directory / "run_001"),
                       "captureWallSeconds": round(time.monotonic() - started, 3)}
                state["results"].append(row)
                pending[pool.submit(finalize_recording, job)] = (job, row)
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
            state["state"] = "FINALIZING"
        state["currentJob"] = None
        if state["state"] == "FINALIZING" and release_capture is not None:
            release_capture()
            state["captureReleased"] = True
            checkpoint(directory, state)
        while pending:
            collect()
            checkpoint(directory, state)
            if pending:
                time.sleep(0.25)
    if state["state"] == "FINALIZING":
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
        released = False

        def release_capture():
            nonlocal released
            if not released:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                released = True

        try:
            raise SystemExit(run(args.manifest, args.reports, release_capture=release_capture))
        except Exception as error:
            path = args.reports / "status.json"
            state = read_json(path) if path.exists() else {"results": [], "total": 0}
            state.update(state="CRASHED", error=f"{type(error).__name__}: {error}")
            checkpoint(args.reports, state, report=True)
            raise
        finally:
            release_capture()


if __name__ == "__main__":
    main()
