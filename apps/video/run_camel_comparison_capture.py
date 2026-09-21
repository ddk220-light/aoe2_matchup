"""Capture a frozen comparison batch, gating it on its declared HP/count pilots.

The standard recorder owns game input, verifies raw/frame bundles and writes
ten-match checkpoints. Its supervisor checks disk capacity and temperature.
Defaults to the original camel comparison; --work selects an isolated campaign.
No renderer, external-drive archiver, simulator, or upload worker is launched.
"""
import hashlib
import argparse
import json
import subprocess
import sys
from pathlib import Path

from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/camel-comparison'


def run(work):
    subprocess.run([sys.executable, '-u', str(ROOT/'apps/video/run_champi_comparison_capture.py'),
                    '--work', str(work)], cwd=ROOT, check=True)


def main():
    global WORK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=WORK)
    WORK = parser.parse_args().work.resolve()
    total = len(read(WORK/'manifest.json')['matchups'])
    for frozen in (WORK/'frozen-catalogs').glob('*.json'):
        if hashlib.sha256(frozen.read_bytes()).digest() != hashlib.sha256((ROOT/'data'/frozen.name).read_bytes()).digest():
            raise RuntimeError(f'Catalog changed after planning: {frozen.name}')
    pilot = WORK/'pilot-phase'
    save(pilot/'manifest.json', read(WORK/'pilot.json'))
    save(WORK/'supervisor.json', {'state':'PILOT', 'total':total, 'captureOnly':True})
    run(pilot)
    state = read(pilot/'capture/status.json')
    verified = {r['jobId']:r for r in state['results'] if r['status']=='verified'}
    expected = read(WORK/'pilot.json')['matchups']
    stats = {r['civ_name']:r for r in read(WORK/'subject-stats.json')}
    # Preserve the original reference snapshot. A reviewed game-data correction
    # is separately bound to the pilot's exact frame stream, never an unchecked
    # tolerance increase or a rewrite of the captured scenario.
    corrections_path = WORK/'capture-hp-expectations.json'
    corrections = read(corrections_path) if corrections_path.exists() else {}
    evidence = []
    for job in expected:
        if job['id'] not in verified:
            raise RuntimeError(f'Pilot not verified: {job["id"]}')
        directory = Path(verified[job['id']]['runDirectory'])
        bundle = read(directory/'recording.json')
        hp = read(directory/bundle['files']['hp']['path'])
        initial = hp['rows'][0]['side1']
        per_unit = initial['hp']/initial['count']
        expected_hp = stats[job['civ2']]['final_hp']
        correction = corrections.get(job['civ2'])
        if correction:
            if (correction['evidenceJobId'] != job['id'] or
                    correction['sourceFramesSha256'].lower() != bundle['files']['frames']['sha256'].lower()):
                raise RuntimeError('HP correction does not match the captured pilot evidence')
            expected_hp = correction['openingHpPerUnit']
        if abs(per_unit-expected_hp) > 0.1:
            raise RuntimeError(f'Opening HP mismatch for {job["civ2"]}: {per_unit} vs {expected_hp}')
        evidence.append({'civ':job['civ2'], 'jobId':job['id'], 'openingHpPerUnit':per_unit,
                         'referenceCorrection':correction,
                         'count':initial['count'], 'verified':True})
    save(WORK/'pilot-validation.json', {'state':'PASSED', 'pilots':evidence,
         'scope':'Verified game captures, starting army counts and HP. Special attack/regeneration mechanics are provided by the installed game and Post-Imperial scenario, not synthesized by a simulator.'})
    save(WORK/'capture/pass-pilot/status.json', state)
    save(WORK/'supervisor.json', {'state':'FULL_CAPTURE', 'total':total, 'captureOnly':True})
    run(WORK)
    final = read(WORK/'capture/status.json')
    if final.get('completed') != total or final.get('failed') or final.get('pendingExports'):
        raise RuntimeError('Capture pass ended without every requested bundle verified')
    save(WORK/'supervisor.json', {'state':'COMPLETE', 'total':total, 'captureOnly':True})


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        save(WORK/'supervisor.json', {'state':'NEEDS_ATTENTION', 'error':str(error), 'captureOnly':True})
        raise
