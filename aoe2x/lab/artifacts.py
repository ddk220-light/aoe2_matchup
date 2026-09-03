"""Durable job directories, lifecycle state, and resumable checkpoints."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import LabError
from .io import read_json, safe_slug, stable_id, utc_now, write_json


TERMINAL_STATES = frozenset({"COMPLETE", "FAILED"})


@dataclass(frozen=True)
class Job:
    root: Path
    job_id: str

    @property
    def directory(self) -> Path:
        return self.root / "runs" / self.job_id

    @property
    def manifest_path(self) -> Path:
        return self.directory / "manifest.json"

    @property
    def plan_path(self) -> Path:
        return self.directory / "plan.json"

    @property
    def request_path(self) -> Path:
        return self.directory / "request.json"

    @property
    def logs_directory(self) -> Path:
        return self.directory / "logs"

    @property
    def simulation_directory(self) -> Path:
        return self.directory / "simulation"

    @property
    def live_directory(self) -> Path:
        return self.directory / "live"

    def initialize(self, request: dict[str, Any], plan: dict[str, Any]) -> None:
        self.logs_directory.mkdir(parents=True, exist_ok=True)
        self.simulation_directory.mkdir(parents=True, exist_ok=True)
        self.live_directory.mkdir(parents=True, exist_ok=True)
        if self.manifest_path.exists():
            current = read_json(self.manifest_path)
            if current.get("planHash") != plan.get("planHash"):
                raise LabError(
                    f"job {self.job_id} already exists with a different plan",
                    hint="choose a different --job-id or resume with identical inputs",
                )
            return
        write_json(self.request_path, request)
        write_json(self.plan_path, plan)
        write_json(self.manifest_path, {
            "schemaVersion": 1,
            "jobId": self.job_id,
            "planHash": plan["planHash"],
            "matchupId": plan["matchupId"],
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
            "state": "PLANNED",
            "history": [{"state": "PLANNED", "at": utc_now()}],
            "simulation": {"requestedSeeds": 0, "completedSeeds": []},
            "live": {"requestedRepeats": 0, "completedRepeats": []},
            "viewer": {
                "path": f"/?mode=lab&job={self.job_id}&seed=1",
            },
        })

    def manifest(self) -> dict[str, Any]:
        return read_json(self.manifest_path)

    def transition(self, state: str, **updates: Any) -> None:
        manifest = self.manifest()
        if manifest.get("state") in TERMINAL_STATES and state not in TERMINAL_STATES:
            # A failed or previously complete job can be deliberately resumed.
            manifest["history"].append({"state": "RESUMED", "at": utc_now()})
        manifest.update(updates)
        manifest["state"] = state
        manifest["updatedAt"] = utc_now()
        manifest.setdefault("history", []).append({"state": state, "at": utc_now()})
        if state == "COMPLETE":
            manifest["completedAt"] = utc_now()
        elif state != "FAILED":
            manifest.pop("completedAt", None)
        write_json(self.manifest_path, manifest)

    def update_section(self, name: str, **updates: Any) -> None:
        manifest = self.manifest()
        section = dict(manifest.get(name, {}))
        section.update(updates)
        manifest[name] = section
        manifest["updatedAt"] = utc_now()
        write_json(self.manifest_path, manifest)

    def record_failure(self, error: BaseException, *, phase: str) -> None:
        diagnostic = {
            "phase": phase,
            "type": type(error).__name__,
            "code": getattr(error, "code", "UNEXPECTED_ERROR"),
            "message": str(error),
            "hint": getattr(error, "hint", None),
            "traceback": traceback.format_exc(),
            "at": utc_now(),
        }
        write_json(self.directory / "failure.json", diagnostic)
        self.transition("FAILED", failure=diagnostic)


def create_job(root: Path, job_id: str) -> Job:
    normalized = safe_slug(job_id)
    if normalized != job_id:
        raise ValueError("job id must contain only lowercase letters, numbers, and underscores")
    return Job(root=root, job_id=job_id)


@dataclass(frozen=True)
class Batch:
    root: Path
    batch_id: str

    @property
    def directory(self) -> Path:
        return self.root / "batches" / self.batch_id

    @property
    def manifest_path(self) -> Path:
        return self.directory / "manifest.json"

    def initialize(self, *, source: Path, requests: list[dict[str, Any]]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        write_json(self.directory / "requests.json", {
            "schemaVersion": 1,
            "source": str(source.resolve()),
            "requests": requests,
        })
        if self.manifest_path.exists():
            return
        now = utc_now()
        write_json(self.manifest_path, {
            "schemaVersion": 1,
            "batchId": self.batch_id,
            "source": str(source.resolve()),
            "createdAt": now,
            "updatedAt": now,
            "state": "PLANNED",
            "history": [{"state": "PLANNED", "at": now}],
            "jobs": {},
        })

    def manifest(self) -> dict[str, Any]:
        return read_json(self.manifest_path)

    def transition(self, state: str) -> None:
        manifest = self.manifest()
        manifest["state"] = state
        manifest["updatedAt"] = utc_now()
        manifest.setdefault("history", []).append({"state": state, "at": utc_now()})
        write_json(self.manifest_path, manifest)

    def update_job(self, key: str, **updates: Any) -> None:
        manifest = self.manifest()
        jobs = dict(manifest.get("jobs", {}))
        jobs[key] = {**jobs.get(key, {}), **updates, "updatedAt": utc_now()}
        manifest["jobs"] = jobs
        manifest["updatedAt"] = utc_now()
        write_json(self.manifest_path, manifest)


def create_batch(root: Path, source: Path, requests: list[dict[str, Any]]) -> Batch:
    batch_id = f"{safe_slug(source.stem)}_{stable_id(requests, 8)}"
    batch = Batch(root=root, batch_id=batch_id)
    batch.initialize(source=source, requests=requests)
    return batch
