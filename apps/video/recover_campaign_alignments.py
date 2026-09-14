"""Retry failed HP timing fits with denser observations; retain the same quality gates."""
import argparse
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'aoe2x/js_simulation/calibration/lab'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('status', type=Path)
    parser.add_argument('--workers', type=int, choices=range(1, 4), default=2)
    args = parser.parse_args()
    state = json.loads(args.status.read_text())
    jobs = [j for j in state['jobs'] if j['overlay']['status'] == 'failed'
            and 'auto_alignment' in j['overlay'].get('error', '')]

    def recover(job):
        run = LAB / 'runs' / job['jobId'] / 'live/run_001'
        out = run / 'unit-hp-overlay'
        if (out / 'alignment.json').exists():
            return {'jobId': job['jobId'], 'state': 'already_aligned'}
        candidate = out / 'alignment-candidate.json'
        if candidate.exists():
            (out / 'alignment-before-dense.json').write_bytes(candidate.read_bytes())
        with (out / 'dense-recovery.log').open('w', encoding='utf-8') as log:
            result = subprocess.run([
                sys.executable, '-m', 'overlay.auto_alignment', str(run),
                '--sample-rate', '30', '--compact-bars', '--color-components',
            ], cwd=ROOT, stdout=log, stderr=log)
        return {'jobId': job['jobId'],
                'state': 'aligned' if result.returncode == 0 else 'needs_review'}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(recover, jobs))
    # Do not overwrite the active overlay worker's status. Its normal retry uses
    # these independently validated alignment files and cached rendered panels.
    (args.status.parent / 'dense-recovery.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results), flush=True)
    return int(any(r['state'] == 'needs_review' for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
