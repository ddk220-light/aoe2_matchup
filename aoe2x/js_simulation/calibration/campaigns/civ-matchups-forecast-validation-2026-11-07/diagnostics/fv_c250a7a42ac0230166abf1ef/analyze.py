"""Read committed diagnostic snapshots; never execute a battle or assign a result."""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = '0789456d2247747e840f1210293f9a536a580945'
JOB = 'fv_c250a7a42ac0230166abf1ef'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'


def blob(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def core(row):
    return {'byOwner': row['byOwner'], 'positions': row['positions']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).parent)
    out = parser.parse_args().output
    assert not (out / 'REVIEW.json').exists() and not (out / 'README.md').exists(), 'Never overwrite a diagnosis'
    manifest = json.loads(blob(BASE + '/manifest.json'))
    policy = json.loads(blob(BASE + '/sampling-policy-v3.json'))
    job = next(x for x in map(json.loads, gzip.decompress(blob(BASE + '/jobs.jsonl.gz')).splitlines()) if x['id'] == JOB)
    assert job['contextHash'] == sha(json.dumps(job['context'], sort_keys=True, separators=(',', ':')).encode())
    assert job['teamKeys'] == ['Vikings|hussar', 'Sicilians|imp_elite_skirm'] and job['counts'] == [23, 27]
    frozen = blob(FROZEN)
    assert sha(frozen) == next(f['sha256'] for f in manifest['inputFiles'] if f['path'] == FROZEN)
    names = [json.loads(frozen)['profiles'][k]['mechanics']['unit_name'] for k in job['teamKeys']]
    assert names == ['Light Cavalry', 'Elite Skirmisher']
    evidence = [x for x in map(json.loads, gzip.decompress(blob(BASE + '/original-evidence.jsonl.gz')).splitlines()) if x['evidenceId'] in job['evidenceIds']]
    journal = blob(BASE + '/attempts.jsonl')
    selected = [(n, raw, json.loads(raw)) for n, raw in enumerate(journal.splitlines(keepends=True), 1) if json.loads(raw)['matchupId'] == JOB]
    assert [a['attempt'] for _, _, a in selected] == [1, 2, 3, 4]
    assert [a['limitSeconds'] for _, _, a in selected] == [180, 600, 1800, 3600]
    assert [a['exhausted'] for _, _, a in selected] == [False, False, False, True]
    attempts = []
    for n, raw, attempt in selected:
        assert attempt['seed'] == 0 and attempt['purpose'] == 'fresh_measurement' and attempt['watchdog'] and attempt['error'] is None
        timeline = blob(attempt['progressPath'])
        rows = list(map(json.loads, timeline.splitlines()))
        assert rows and all(row['diagnosticOnly'] for row in rows)
        start = len(rows) - 1
        while start and core(rows[start - 1]) == core(rows[-1]):
            start -= 1
        deltas = {k: rows[-1]['eventCounts'].get(k, 0) - rows[start]['eventCounts'].get(k, 0) for k in rows[-1]['eventCounts'] if rows[-1]['eventCounts'].get(k, 0) != rows[start]['eventCounts'].get(k, 0)}
        if attempt['attempt'] > 1:
            assert rows[-1]['byOwner'] == {'2': {'units': 3, 'hp': 136.5}, '3': {'units': 1, 'hp': 8}}
            assert all(u['action'] == 'idle' and u['attackTargetId'] is None for row in rows[start:] for u in row['positions'])
            assert set(deltas) == {'contact-reservation-persisted', 'blocked', 'pursuit-retarget-requested', 'pursuit-route-planned', 'pursuit-route-invalidated'}
        else:
            assert rows[-1]['byOwner'] == {'2': {'units': 14, 'hp': 675}, '3': {'units': 1, 'hp': 8}}
            assert any(u['action'] == 'attacking' for u in rows[-1]['positions'])
        attempts.append({**attempt, 'sourceLine': n, 'sourceLineSha256': sha(raw), 'progressSha256': sha(timeline), 'savedSnapshots': len(rows), 'lastSavedTick': rows[-1]['tick'], 'lastSavedSimulationSeconds': rows[-1]['simulationSeconds'], 'lastSavedCore': core(rows[-1]), 'constantCoreSuffixSnapshots': len(rows) - start, 'eventDeltasInSuffix': deltas})
    assert [a['constantCoreSuffixSnapshots'] for a in attempts] == [1, 9, 52, 111]
    assert all(a['lastSavedCore'] == attempts[-1]['lastSavedCore'] for a in attempts[1:])
    runs = blob(BASE + '/runs.jsonl')
    assert not any(x['matchupId'] == JOB for x in map(json.loads, runs.splitlines()))
    assert not subprocess.check_output(['git', 'ls-tree', SOURCE, '--', BASE + '/pair-reviews/' + JOB + '.json'], cwd=ROOT)
    state = blob(BASE + '/state.json')
    assert JOB in json.loads(state)['blockedJobs']
    diagnosis = ('Seed 0 exhausted all four normal watchdogs without completing. The short first attempt stops earlier, with fourteen Light Cavalry at 675 combined HP and one Elite Skirmisher at 8 HP, still attacking. The three longer attempts reach identical fixed survivor positions, HP, actions and targets: three Light Cavalry at 136.5 combined HP and one Elite Skirmisher at 8 HP, all idle with null attack targets. Their constant-core suffixes contain 9, 52 and 111 snapshots. Five reservation/pursuit/blocked counters grow while combat counters remain fixed. The exact contact/range/geometry/route cause and real-game outcome remain unknown.')
    paths = [BASE + '/manifest.json', BASE + '/sampling-policy-v2.json', BASE + '/sampling-policy-v3.json', FROZEN, BASE + '/attempts.jsonl', BASE + '/runs.jsonl', BASE + '/state.json']
    report = {'version': 1, 'diagnosticOnly': True, 'jobId': JOB, 'sourceCommit': SOURCE, 'campaignHash': manifest['campaignHash'], 'samplingPolicyHash': policy['amendmentHash'], 'job': job, 'mechanicsUnitNames': names, 'originalEvidence': evidence, 'sourceHashes': {p: sha(blob(p)) for p in paths}, 'attempts': attempts, 'status': 'blocked_needs_separate_recovery_review', 'assignedOutcome': None, 'validNativeSeedReferences': [], 'replayEvidence': {'required': False, 'performed': False, 'exact': None}, 'diagnosis': diagnosis, 'queueAction': 'Preserve every failed attempt, leave blocked, continue ordinary queue. Separate recovery review required before any further retry.', 'noFurtherRetryAuthorized': True, 'simulationExecutionsForDiagnosis': 0, 'physicsChanged': False, 'nativeResultsAdded': False}
    text = f'''# Exhausted Viking Light Cavalry / Sicilian Elite Skirmisher

Job `{JOB}`, counts 23 / 27, exhausted all four normal seed-0 watchdogs at {attempts[-1]['finishedAt']}. No seed completed. The frozen role key `Vikings|hussar` retains the actual mechanics upgrade Light Cavalry.

{diagnosis}

No native winner, draw, pair review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.

Source `{SOURCE}`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>
```
'''
    out.mkdir(parents=True, exist_ok=True)
    for name, data in [('REVIEW.json', json.dumps(report, sort_keys=True, indent=2) + '\n'), ('README.md', text)]:
        with (out / name).open('x') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    print(json.dumps({'jobId': JOB, 'attempts': len(attempts), 'constantCoreSuffixSnapshots': [a['constantCoreSuffixSnapshots'] for a in attempts], 'completedSeeds': 0, 'simulationExecutions': 0, 'assignedOutcome': None}))


if __name__ == '__main__':
    main()
