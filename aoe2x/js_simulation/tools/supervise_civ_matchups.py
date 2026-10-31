"""Keep the resumable civ-matchup runner alive across transient process exits.

The Node runner owns seed journals, phase reviews and Git commits. This monitor
never launches a second runner while the first is live, and never overrides an
integrity failure. Remove the monitor's process (or write adaptive/.stop) to
stop automatic restarts.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31/adaptive"
RUNNER = ["node", "aoe2x/js_simulation/node/civ-matchups/run-adaptive.mjs"]
INTEGRITY_ERRORS = (
    "hash mismatch", "source changed", "duplicate saved seed", "exact replay failed",
    "coverage mismatch", "inventory hash mismatch", "environment changed",
    "campaign manifest hash", "phase has unaccounted missing seeds",
    "validate_civ_matchups_phase_one.py",
)


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
    failures = 0
    while not (DIR / ".stop").exists():
        state = read_json(DIR / "state.json")
        if state.get("status") == "complete" and not state.get("remotePending"):
            event("finished", savedSeeds=state.get("savedSeeds"))
            return
        if state.get("status") == "blocked_needs_review":
            event("blocked", pairs=state.get("blockedPairs"))
            return
        reason = state.get("failure", {}).get("message", "")
        if any(term in reason for term in INTEGRITY_ERRORS):
            event("integrityFailure", reason=reason)
            return
        pid = state.get("pid")
        if live(pid):
            failures = 0
            time.sleep(30)
            continue
        failures += 1
        if failures > 1:
            time.sleep(min(120, 15 * failures))
        event("resume", attempt=failures, lastStatus=state.get("status"), savedSeeds=state.get("savedSeeds"))
        with (DIR / "runner.log").open("a") as log:
            process = subprocess.Popen(RUNNER, cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        time.sleep(5)
        if process.poll() is not None:
            event("earlyExit", code=process.returncode)


if __name__ == "__main__":
    main()
