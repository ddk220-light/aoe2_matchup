"""Read committed diagnostic snapshots; never execute a battle or assign an outcome."""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = 'ebd992b430c44148967480228dd9d5ec6cfa3f29'
JOB = 'fv_5184d46798ee328659752ef9'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
DIAGNOSIS = (
    'Seed 0 exhausted all four normal watchdogs without completing. All four saved timelines '
    'have constant-survivor/HP suffixes: one Elite Skirmisher at 22 HP and eighteen Elite Kona '
    'at 2,460 combined HP. The suffixes contain 5, 19, 59 and 119 snapshots, each with distinct '
    'positions. All sampled survivors in those suffixes are idle with null attack targets, '
    'while positions and pursuit/engagement targets continue changing. There are 1, 2, 2 and '
    '2 distinct target states in the four suffixes. Twelve movement, pursuit, reservation and '
    'blocked counters grow while combat counters remain fixed. This is movement and '
    'replanning without HP progress. The precise contact/range/geometry/route cause and '
    'real-game outcome remain unknown.'
)


def blob(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).parent)
    out = parser.parse_args().output
    assert not (out / 'REVIEW.json').exists() and not (out / 'README.md').exists(), 'Never overwrite a diagnosis'
    assert subprocess.check_output(['git', 'cat-file', '-t', SOURCE], cwd=ROOT).strip() == b'commit'
    manifest = json.loads(blob(BASE + '/manifest.json'))
    policy = json.loads(blob(BASE + '/sampling-policy-v3.json'))
    job = next(j for j in map(json.loads, gzip.decompress(blob(BASE + '/jobs.jsonl.gz')).splitlines()) if j['id'] == JOB)
    assert job['contextHash'] == sha(json.dumps(job['context'], sort_keys=True, separators=(',', ':')).encode())
    assert job['teamKeys'] == ['Sicilians|imp_elite_skirm', 'Mapuche|elite_kona_mapuche'] and job['counts'] == [27, 19]
    frozen = blob(FROZEN)
    assert sha(frozen) == next(f['sha256'] for f in manifest['inputFiles'] if f['path'] == FROZEN)
    names = [json.loads(frozen)['profiles'][k]['mechanics']['unit_name'] for k in job['teamKeys']]
    assert names == ['Elite Skirmisher', 'Elite Kona']
    evidence = [e for e in map(json.loads, gzip.decompress(blob(BASE + '/original-evidence.jsonl.gz')).splitlines()) if e['evidenceId'] in job['evidenceIds']]
    assert {e['evidenceId'] for e in evidence} == set(job['evidenceIds'])
    journal = blob(BASE + '/attempts.jsonl')
    selected = [(n, raw, json.loads(raw)) for n, raw in enumerate(journal.splitlines(keepends=True), 1) if json.loads(raw)['matchupId'] == JOB]
    assert [a['attempt'] for _, _, a in selected] == [1, 2, 3, 4]
    assert [a['limitSeconds'] for _, _, a in selected] == [180, 600, 1800, 3600]
    assert [a['exhausted'] for _, _, a in selected] == [False, False, False, True]
    changing_counters = {'move', 'pursuit-acquired', 'contact-reservation-acquired', 'contact-reservation-persisted', 'blocked', 'contact-reservation-released', 'contact-release-persisted', 'pursuit-route-planned', 'pursuit-route-invalidated', 'pursuit-retarget-requested', 'pursuit-route-advanced', 'contact-release-published'}
    attempts = []
    for n, raw, attempt in selected:
        assert attempt['campaignHash'] == manifest['campaignHash']
        assert attempt['seed'] == 0 and attempt['purpose'] == 'fresh_measurement'
        assert attempt['watchdog'] and attempt['error'] is None and attempt['wallSeconds'] >= attempt['limitSeconds']
        timeline = blob(attempt['progressPath'])
        rows = list(map(json.loads, timeline.splitlines()))
        assert all(row['diagnosticOnly'] for row in rows)
        def core(row):
            return {'byOwner': row['byOwner'], 'units': [{k: u[k] for k in ['id', 'owner', 'hp']} for u in row['positions']]}
        i = len(rows) - 1
        while i and core(rows[i - 1]) == core(rows[-1]):
            i -= 1
        suffix = rows[i:]
        def distinct(keys):
            return len({json.dumps([{k: u[k] for k in keys} for u in row['positions']], sort_keys=True) for row in suffix})
        deltas = {k: v - rows[i]['eventCounts'].get(k, 0) for k, v in rows[-1]['eventCounts'].items() if v != rows[i]['eventCounts'].get(k, 0)}
        assert set(deltas) == changing_counters and all(value > 0 for value in deltas.values())
        assert all(u['action'] == 'idle' and u['attackTargetId'] is None for row in suffix for u in row['positions'])
        attempts.append({**attempt, 'sourceLine': n, 'sourceLineSha256': sha(raw), 'progressSha256': sha(timeline), 'savedSnapshots': len(rows), 'lastSavedTick': rows[-1]['tick'], 'lastSavedSimulationSeconds': rows[-1]['simulationSeconds'], 'lastSavedPositions': rows[-1]['positions'], 'lastSavedHpCore': core(rows[-1]), 'constantHpSuffixSnapshots': len(suffix), 'uniquePositionStatesInHpSuffix': distinct(['id', 'owner', 'x', 'y']), 'uniqueTargetStatesInHpSuffix': distinct(['id', 'pursuitTargetId', 'engagedTargetId', 'attackTargetId']), 'uniquePositionActionTargetStatesInHpSuffix': len({json.dumps(row['positions'], sort_keys=True) for row in suffix}), 'eventDeltasInSuffix': deltas})
    assert [a['savedSnapshots'] for a in attempts] == [6, 20, 60, 120]
    assert [a['constantHpSuffixSnapshots'] for a in attempts] == [5, 19, 59, 119]
    assert [a['uniquePositionStatesInHpSuffix'] for a in attempts] == [5, 19, 59, 119]
    assert [a['uniquePositionActionTargetStatesInHpSuffix'] for a in attempts] == [5, 19, 59, 119]
    assert [a['uniqueTargetStatesInHpSuffix'] for a in attempts] == [1, 2, 2, 2]
    assert all(a['lastSavedHpCore'] == attempts[-1]['lastSavedHpCore'] for a in attempts)
    assert attempts[-1]['lastSavedHpCore']['byOwner'] == {'2': {'units': 1, 'hp': 22}, '3': {'units': 18, 'hp': 2460}}
    assert [a['lastSavedTick'] for a in attempts] == [4792, 16167, 49424, 86211]
    assert [a['lastProgress']['tick'] for a in attempts] == [5408, 16873, 50201, 86849]
    assert attempts[-1]['finishedAt'] == '2026-11-10T07:51:50.115Z'
    runs = blob(BASE + '/runs.jsonl')
    assert not any(row['matchupId'] == JOB for row in map(json.loads, runs.splitlines()))
    assert not subprocess.check_output(['git', 'ls-tree', SOURCE, '--', BASE + '/pair-reviews/' + JOB + '.json'], cwd=ROOT)
    state = blob(BASE + '/state.json')
    assert JOB in json.loads(state)['blockedJobs']
    source_paths = [BASE + '/' + f for f in ['manifest.json', 'sampling-policy-v2.json', 'sampling-policy-v3.json', 'jobs.jsonl.gz', 'original-evidence.jsonl.gz', 'attempts.jsonl', 'runs.jsonl', 'state.json']] + [FROZEN]
    report = {'version': 1, 'diagnosticOnly': True, 'jobId': JOB, 'sourceCommit': SOURCE, 'sourceCommitVerifiedLocally': True, 'localOnlyResearch': True, 'diagnosedAtLocal': datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(), 'campaignHash': manifest['campaignHash'], 'samplingPolicyHash': policy['amendmentHash'], 'job': job, 'mechanicsUnitNames': names, 'originalEvidence': evidence, 'sourceHashes': {p: sha(blob(p)) for p in source_paths}, 'attempts': attempts, 'status': 'blocked_needs_separate_recovery_review', 'assignedOutcome': None, 'validNativeSeedReferences': [], 'replayEvidence': {'required': False, 'performed': False, 'exact': None}, 'diagnosis': DIAGNOSIS, 'snapshotTimingLimitation': 'Closed fsynced snapshots precede the attempt lastProgress markers; retain both original values and do not infer an intervening result.', 'queueAction': 'Preserve every failed attempt, leave blocked, continue ordinary queue. Separate recovery review required before any further retry.', 'noFurtherRetryAuthorized': True, 'simulationExecutionsForDiagnosis': 0, 'physicsChanged': False, 'nativeResultsAdded': False}
    readme = f'''# Exhausted Sicilian Elite Skirmisher / Mapuche Elite Kona

Job `{JOB}`, counts 27 / 19, exhausted its four normal seed-0 watchdogs on November 9, 2026, at 11:51:50.115 p.m. PST (America/Los_Angeles). No seed completed.

{DIAGNOSIS}

The final saved ticks are 4,792 / 16,167 / 49,424 / 86,211. The attempt records retain later lastProgress ticks of 5,408 / 16,873 / 50,201 / 86,849. These are distinct diagnostic observations, not native results.

No native winner, draw, pair review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review. No further retry, physics change or imported winner is authorized. The ordinary four-worker queue continues.

Local source `{SOURCE}`, the exact physical context, original evidence, all attempt-line hashes and closed progress-file hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>
```
'''
    out.mkdir(parents=True, exist_ok=True)
    for name, text in [('REVIEW.json', json.dumps(report, sort_keys=True, indent=2) + '\n'), ('README.md', readme)]:
        with (out / name).open('x') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
    fd = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps({'jobId': JOB, 'attempts': len(attempts), 'completedSeeds': 0, 'simulationExecutions': 0, 'assignedOutcome': None}))


if __name__ == '__main__':
    main()
