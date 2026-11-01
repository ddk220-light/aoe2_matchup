#!/usr/bin/env python3
"""Collect bounded, read-only timelines only after named recovery retries fail.

No campaign record or frozen runtime is modified. A diagnostic reaching its
600-game-second ceiling is not a matchup result. Never run alongside the same
active campaign seed. This one-shot watcher does not restart campaign workers.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

SIM = Path(__file__).resolve().parents[1]
ROOT = SIM.parents[1]
CAMPAIGN = SIM/'calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01'
OUT = SIM/'calibration/reports/civ-first-pass-recovery-diagnostics-2026-11-01'
TARGETS = ['cm_6827d25d70a06f758cc82ff9:2', 'cm_b49b88761f519d9bd7d20a07:0']


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2)+'\n')
    tmp.replace(path)


def live(pid):
    try:
        status = Path(f'/proc/{int(pid)}/status').read_text()
    except (FileNotFoundError, ValueError, TypeError):
        return False
    return not any(x.startswith('State:') and x.split()[1] == 'Z' for x in status.splitlines())


def saved_keys():
    p = CAMPAIGN/'runs.jsonl'
    raw = p.read_bytes() if p.exists() else b''
    lines = raw.splitlines() if raw.endswith(b'\n') else raw.splitlines()[:-1]
    return {f"{r['matchupId']}:{r['seed']}" for r in map(json.loads, lines)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch-seconds', type=int, default=14400)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT/'.diagnostic.lock'
    if lock.exists():
        assert not live(lock.read_text()), 'diagnostic watcher already live'
        lock.unlink()
    with lock.open('x') as f:
        f.write(str(os.getpid()))
    status_path = OUT/'state.json'
    status = {'startedAt':now(), 'pid':os.getpid(), 'status':'watching_failed_retries',
              'targets':TARGETS, 'diagnosticOnly':True, 'results':{}}
    save(status_path, status)
    deadline = time.monotonic()+args.watch_seconds
    try:
        pending = set(TARGETS)
        while pending and time.monotonic()<deadline:
            state = load(CAMPAIGN/'state.json')
            active = set(state.get('active', [])) if live(state.get('pid')) else set()
            completed = saved_keys()
            for key in sorted(pending):
                if key in completed:
                    status['results'][key] = {'status':'campaign_seed_completed_no_diagnostic_needed'}
                    pending.remove(key)
                    continue
                if key in active or key not in state.get('failedKeys', []):
                    continue
                matchup, seed = key.split(':')
                report = OUT/f'{matchup}-seed{seed}-first600s.json'
                if report.exists():
                    status['results'][key] = {'status':'existing_diagnostic', 'report':report.name}
                    pending.remove(key)
                    continue
                # Recheck immediately before dispatch: a resumed campaign owns
                # priority over diagnostics, even after its earlier failure.
                current = load(CAMPAIGN/'state.json')
                if live(current.get('pid')) and key in current.get('active', []):
                    continue
                assert key in current.get('failedKeys', [])
                status.update(status='collecting_diagnostic', active=key, updatedAt=now())
                save(status_path, status)
                env = dict(os.environ, SLOW_PAIR_MATCHUP_ID=matchup, SLOW_PAIR_SEED=seed,
                    SLOW_PAIR_MAX_TICKS='36000', SLOW_PAIR_TIMELINE='1',
                    SLOW_PAIR_WALL_LIMIT='300', SLOW_PAIR_REPORT_PATH=str(report))
                with (OUT/f'{matchup}-seed{seed}.log').open('a') as log:
                    result = subprocess.run(['node','--max-old-space-size=3072',
                        'aoe2x/js_simulation/tools/diagnose_slow_civ_pair.mjs'],
                        cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log,
                        stderr=subprocess.STDOUT, timeout=360)
                status['results'][key] = {'status':'diagnostic_only', 'returnCode':result.returncode,
                    'report':report.name if report.exists() else None,
                    'reportSha256':hashlib.sha256(report.read_bytes()).hexdigest() if report.exists() else None,
                    'trigger':'campaign wall retries exhausted; not an outcome', 'finishedAt':now()}
                pending.remove(key)
                status.pop('active', None)
                status['status']='watching_failed_retries'
                save(status_path, status)
            status.update(updatedAt=now(), pending=sorted(pending))
            save(status_path, status)
            if pending:
                time.sleep(30)
        status.update(status='finished' if not pending else 'watch_window_ended', pid=None,
                      updatedAt=now(), pending=sorted(pending))
        save(status_path, status)
    except BaseException as error:
        status.update(status='failed', pid=None, error=str(error), updatedAt=now())
        save(status_path, status)
        raise
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
