"""``supervise``: keep one runner alive for a run until it is finished or told to stop.

Generalises RB ``tools/supervise_civ_forecast_validation.py`` /
``aoe2x/js_simulation/tools/supervise_civ_matchups.py`` (RB =
``origin/simulations/civ-forecast-recovery-2026-11-10``): an ``flock`` on
``<records>/.supervisor.lock`` (never two supervisors), restart the runner after
a crash, never start a second runner, stop for good on an integrity error, and
honour a stop file. Differences: restarts back off exponentially (5 s doubling
to 5 min, reset after 10 minutes of healthy running) and give up after
``max_failures`` consecutive crashes that saved no seed; there is no approval
gate file, no git and no network.

Files (all in ``<records>``):

* ``STOP``                - create it to stop: the runner is sent SIGTERM and the
                            supervisor exits. Remove it before restarting.
* ``supervisor.json``     - heartbeat/status a human can read (atomic rewrite every
                            ``heartbeat`` seconds): pid, runner pid, restarts, last
                            exit, run counts copied from ``state.json``.
* ``logs/supervisor.log`` - one line per event; the runner's own output goes to
                            ``logs/runner-console.log``.

A runner left alive by a killed supervisor is adopted: the new supervisor
sees the live ``.runner.lock`` owner, waits for it, and only then starts a
new runner.
"""
from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from aoe2x.matchups import journal as J
from aoe2x.matchups.runner import EXIT_DONE, EXIT_FAILED, EXIT_INTEGRITY, EXIT_LOCKED

BACKOFF_START, BACKOFF_MAX, HEALTHY_SECONDS = 5.0, 300.0, 600.0


class Supervisor:
    def __init__(self, config_path: Path, records: Path, *, runner_args: list[str] | None = None,
                 heartbeat: float = 30.0, max_failures: int = 5, python: str = sys.executable):
        self.config_path = str(config_path)
        self.R = Path(records)
        self.runner_args = list(runner_args or [])
        self.heartbeat = heartbeat
        self.max_failures = max_failures
        self.python = python
        self.stop_requested = None
        self.child = None
        self.status = {"schema": "aoe2-matchup-supervisor/v1", "pid": os.getpid(), "startedAt": J.now(),
                       "config": self.config_path, "records": str(self.R), "restarts": 0, "consecutiveFailures": 0,
                       "runnerPid": None, "lastExit": None, "status": "starting"}

    # ---------------------------------------------------------------- output
    def log(self, event: str, **fields) -> None:
        (self.R / "logs").mkdir(parents=True, exist_ok=True)
        line = json.dumps({"at": J.now(), "event": event, **fields})
        with open(self.R / "logs" / "supervisor.log", "a") as f:
            f.write(line + "\n")
        print(line, file=sys.stderr, flush=True)

    def beat(self, status: str | None = None) -> None:
        if status:
            self.status["status"] = status
        state = J.read_json(self.R / "state.json", {}) or {}
        self.status.update(heartbeatAt=J.now(), runStatus=state.get("status"), contexts=state.get("contexts"),
                           seeds=state.get("seeds"), blockedJobs=state.get("blockedJobs"))
        J.write_json_atomic(self.R / "supervisor.json", self.status)

    # ---------------------------------------------------------------- control
    def _signal(self, signum, _frame):
        self.stop_requested = signal.Signals(signum).name
        if self.child and self.child.poll() is None:
            self.child.send_signal(signal.SIGTERM)

    def _saved(self) -> int:
        return ((J.read_json(self.R / "state.json", {}) or {}).get("seeds") or {}).get("saved", 0)

    def _wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self.stop_requested and not (self.R / "STOP").exists():
            time.sleep(min(1.0, max(0.0, end - time.monotonic())))

    def _live_runner(self) -> dict | None:
        lock = J.RunnerLock(self.R / ".runner.lock")
        owner = lock.read()
        return owner if lock.owner_alive(owner) else None

    def run(self) -> int:
        self.R.mkdir(parents=True, exist_ok=True)
        lock_file = open(self.R / ".supervisor.lock", "a+")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"another supervisor holds {self.R / '.supervisor.lock'}", file=sys.stderr)
            return EXIT_LOCKED
        handlers = {s: signal.signal(s, self._signal) for s in (signal.SIGTERM, signal.SIGINT)}
        backoff = BACKOFF_START
        code = EXIT_FAILED
        try:
            self.log("supervisor-start", pid=os.getpid(), config=self.config_path)
            while True:
                if self.stop_requested or (self.R / "STOP").exists():
                    self.log("stop", reason=self.stop_requested or "STOP file")
                    self.beat("stopped")
                    return EXIT_DONE
                owner = self._live_runner()
                if owner:
                    # Adopt a runner left by a previous (killed) supervisor: wait for it to exit.
                    self.status["runnerPid"] = owner.get("pid")
                    self.log("adopt-runner", pid=owner.get("pid"))
                    while self._live_runner() and not self.stop_requested and not (self.R / "STOP").exists():
                        self.beat("waiting-for-adopted-runner")
                        self._wait(min(self.heartbeat, 5.0))
                    if self.stop_requested or (self.R / "STOP").exists():
                        if self._live_runner():
                            os.kill(owner["pid"], signal.SIGTERM)
                        continue
                    self.status["runnerPid"] = None
                    continue
                before = self._saved()
                started = time.monotonic()
                cmd = [self.python, "-m", "aoe2x.matchups", "run", self.config_path, *self.runner_args]
                (self.R / "logs").mkdir(parents=True, exist_ok=True)
                with open(self.R / "logs" / "runner-console.log", "ab") as console:
                    self.child = subprocess.Popen(cmd, stdout=console, stderr=console)
                    self.status["runnerPid"] = self.child.pid
                    self.log("runner-start", pid=self.child.pid, cmd=cmd[2:])
                    while self.child.poll() is None:
                        self.beat("running")
                        waited = 0.0
                        while waited < self.heartbeat and self.child.poll() is None:
                            if (self.R / "STOP").exists() and not self.stop_requested:
                                self.stop_requested = "STOP file"
                                self.child.send_signal(signal.SIGTERM)
                            time.sleep(0.5)
                            waited += 0.5
                    code = self.child.returncode
                self.child = None
                ran = time.monotonic() - started
                progressed = self._saved() > before
                self.status.update(runnerPid=None, lastExit={"code": code, "at": J.now(), "ranSeconds": round(ran, 1),
                                                             "progressed": progressed})
                self.log("runner-exit", code=code, ranSeconds=round(ran, 1), progressed=progressed)
                if code == EXIT_DONE:
                    self.beat("finished")
                    return EXIT_DONE
                if code == EXIT_INTEGRITY:
                    self.beat("stopped-integrity-error")
                    return EXIT_INTEGRITY
                if self.stop_requested or (self.R / "STOP").exists():
                    continue
                if code == EXIT_LOCKED:
                    self._wait(5.0)
                    continue
                # crash (or an external kill of the runner): restart with backoff
                if progressed or ran >= HEALTHY_SECONDS:
                    self.status["consecutiveFailures"] = 0
                    backoff = BACKOFF_START
                else:
                    self.status["consecutiveFailures"] += 1
                if self.status["consecutiveFailures"] >= self.max_failures:
                    self.log("give-up", consecutiveFailures=self.status["consecutiveFailures"])
                    self.beat("stopped-repeated-failures")
                    return EXIT_FAILED
                self.status["restarts"] += 1
                self.beat(f"restarting-in-{backoff:.0f}s")
                self._wait(backoff)
                backoff = min(BACKOFF_MAX, backoff * 2)
        finally:
            if self.child and self.child.poll() is None:
                self.child.send_signal(signal.SIGTERM)
                try:
                    self.child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.child.kill()
            for s, h in handlers.items():
                signal.signal(s, h)
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
