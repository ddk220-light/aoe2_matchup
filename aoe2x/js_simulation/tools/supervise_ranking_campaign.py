"""Resume a long campaign after process failures; phase gates remain in Node."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    directory = Path(args.campaign).resolve()
    root = Path(__file__).resolve().parents[3]
    command = ["node", "aoe2x/js_simulation/node/full-ranking-campaign.mjs", "run",
               "--campaign", str(directory), "--workers", str(args.workers), "--publish", "true"]
    # A deterministic data-integrity failure must not be silently waived.
    # Three automatic restarts handle transient process failures, using saved
    # per-run records rather than repeating completed work.
    for attempt in range(4):
        print(json.dumps({"supervisorAttempt": attempt + 1,
                          "at": datetime.now(timezone.utc).isoformat()}), flush=True)
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode == 0:
            return
        state_path = directory / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if any(term in state.get("failure", {}).get("message", "") for term in
               ("hash mismatch", "source changed", "environment changed", "phase replay failed",
                "SQLite integrity", "coverage mismatch", "identity mismatch")):
            raise SystemExit("Campaign stopped at a data-integrity gate; recorded results are preserved.")
        if attempt < 3:
            time.sleep(15 * (attempt + 1))
    raise SystemExit("Campaign failed after four resumable attempts; inspect runner.log and state.json.")


if __name__ == "__main__":
    main()
