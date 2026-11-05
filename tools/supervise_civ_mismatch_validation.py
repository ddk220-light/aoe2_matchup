"""Monitor only the explicitly authorized mismatch inventory, never bulk replay."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05'
RUNNER = 'aoe2x/js_simulation/node/civ-matchups/run-mismatch-validation.mjs'


def live(pid):
    try:
        return '\nState:\tZ' not in Path(f'/proc/{pid}/status').read_text()
    except FileNotFoundError:
        return False


def main():
    with (CAMPAIGN / '.supervisor.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock.seek(0); lock.truncate(); lock.write(str(os.getpid())); lock.flush()
        while True:
            state = json.loads((CAMPAIGN / 'state.json').read_text()) if (CAMPAIGN / 'state.json').exists() else {}
            owner = json.loads((CAMPAIGN / '.runner.lock').read_text()) if (CAMPAIGN / '.runner.lock').exists() else {}
            if owner.get('pid') and live(owner['pid']):
                command = Path(f"/proc/{owner['pid']}/cmdline").read_bytes().replace(b'\0', b' ').decode()
                assert RUNNER in command, 'lock belongs to an unrelated live process; manual review required'
                time.sleep(30)
                continue
            if state.get('status') in ('complete', 'blocked_needs_diagnosis'):
                print(json.dumps({'supervisorStopped': state['status'], 'reviewedJobs': state.get('reviewedJobs')}), flush=True)
                break
            with Path('/workspace/aoe2_civ_mismatch_validation.log').open('a') as out:
                process = subprocess.Popen(['node', '--max-old-space-size=3072', RUNNER], cwd=ROOT,
                                           stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
                print(json.dumps({'startedRunner': process.pid}), flush=True)
                code = process.wait()
                print(json.dumps({'runnerExited': process.pid, 'code': code}), flush=True)
                if code:
                    # An invariant/source/hash failure is not a reason to loop
                    # blindly. A later task must inspect its log and diagnose.
                    break
            time.sleep(2)


if __name__ == '__main__':
    main()
