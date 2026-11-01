"""Resume the versioned V2 replay as V3 adds valid source seeds.

This monitor does not run fights. The replay owns its lock, append-only journal,
source checks and Git checkpoints. A live replay process always takes priority.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[3]
CAMPAIGN = ROOT / "aoe2x/js_simulation/calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31"
SOURCE = Path("/workspace/aoe2_path_recovery/aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31/adaptive")
RUNNER = ["node", "aoe2x/js_simulation/node/civ-matchups/replay-v2.mjs"]
REPLAY_LOG = Path("/workspace/aoe2_civ_collision_replay_v2.log")
LOCK = CAMPAIGN / ".supervisor.lock"


def read_json(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def live(pid):
    if not pid:
        return False
    try:
        status = Path(f"/proc/{int(pid)}/status").read_text()
    except FileNotFoundError:
        return False
    return not any(line.startswith("State:") and line.split()[1] == "Z"
                   for line in status.splitlines())


def event(kind, **fields):
    print(json.dumps({"at": datetime.now(timezone.utc).isoformat(), kind: fields}), flush=True)


def main():
    if LOCK.exists():
        old = int(LOCK.read_text())
        if live(old):
            raise RuntimeError(f"V2 replay supervisor already live under PID {old}")
        LOCK.unlink()
    LOCK.write_text(str(os.getpid()))
    failures = 0
    last_saved = 0
    try:
        while not (CAMPAIGN / ".stop-supervisor").exists():
            state = read_json(CAMPAIGN / "state.json")
            source = read_json(SOURCE / "state.json")
            pid = state.get("pid")
            lock_pid = None
            if (CAMPAIGN / ".runner.lock").exists():
                lock_pid = int((CAMPAIGN / ".runner.lock").read_text())
            if live(pid) or live(lock_pid):
                if live(pid) and live(lock_pid) and pid != lock_pid:
                    event("conflictingLivePids", statePid=pid, lockPid=lock_pid)
                    return
                if state.get("savedReplays", 0) > last_saved:
                    failures = 0
                    last_saved = state["savedReplays"]
                time.sleep(60)
                continue
            if state.get("status") == "blocked" or state.get("failedKeys"):
                event("blocked", failedKeys=state.get("failedKeys"))
                return
            source_seeds = source.get("savedSeeds", 0)
            candidate_count = state.get("sourceCandidates", 0)
            if state.get("status") == "caught_up" and source_seeds <= candidate_count:
                if source.get("status") == "complete" and not source.get("remotePending"):
                    event("finished", savedReplays=state.get("savedReplays"))
                    return
                time.sleep(60)
                continue
            failures += 1
            if failures > 2:
                event("repeatedEarlyExit", failures=failures, status=state.get("status"))
                return
            event("resume", attempt=failures, previousStatus=state.get("status"),
                  savedReplays=state.get("savedReplays"), sourceSeeds=source_seeds)
            with REPLAY_LOG.open("a") as log:
                child = subprocess.Popen(RUNNER, cwd=ROOT, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True)
            time.sleep(10)
            if child.poll() is not None:
                event("earlyExit", code=child.returncode)
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
