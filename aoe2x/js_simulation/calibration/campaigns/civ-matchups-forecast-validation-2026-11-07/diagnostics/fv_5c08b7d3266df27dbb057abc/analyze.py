"""Read-only diagnosis of an exhausted first seed from committed snapshots."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = next((p for p in Path(__file__).resolve().parents
             if (p / 'aoe2x/js_simulation/calibration').is_dir()), Path.cwd())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
SOURCE = 'd5144b0ac57335b017b6d7ca0fe2b3d2f8315e03'
JOB = 'fv_5c08b7d3266df27dbb057abc'
SHA = lambda b: hashlib.sha256(b).hexdigest()
CONTINUING = {'blocked', 'pursuit-route-planned', 'contact-reservation-persisted',
              'pursuit-retarget-requested', 'pursuit-route-invalidated'}


def blob(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def core(row):
    return {'byOwner': row['byOwner'], 'positions': row['positions']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    assert not (args.output / 'REVIEW.json').exists(), 'Never overwrite a diagnosis.'
    manifest = json.loads(blob(BASE + '/manifest.json'))
    policy = json.loads(blob(BASE + '/sampling-policy-v3.json'))
    assert policy['independentExactReplayRequired'] is False
    jobs = [json.loads(l) for l in gzip.decompress(blob(BASE + '/jobs.jsonl.gz')).splitlines()]
    job = next(j for j in jobs if j['id'] == JOB)
    assert job['contextHash'] == SHA(canonical(job['context']).encode())
    assert job['teamKeys'] == ['Incas|imp_elite_skirm', 'Poles|paladin']
    assert job['counts'] == [27, 19]
    frozen_bytes = blob(FROZEN)
    assert SHA(frozen_bytes) == next(f['sha256'] for f in manifest['inputFiles'] if f['path'] == FROZEN)
    profiles = json.loads(frozen_bytes)['profiles']
    unit_names = [profiles[key]['mechanics']['unit_name'] for key in job['teamKeys']]
    assert unit_names == ['Elite Skirmisher', 'Cavalier']
    evidence = [json.loads(l) for l in gzip.decompress(blob(BASE + '/original-evidence.jsonl.gz')).splitlines()]
    original = [e for e in evidence if e['evidenceId'] in job['evidenceIds']]
    attempt_bytes = blob(BASE + '/attempts.jsonl')
    selected = [(i, raw, json.loads(raw)) for i, raw in enumerate(attempt_bytes.splitlines(keepends=True), 1)
                if json.loads(raw)['matchupId'] == JOB]
    assert [a['limitSeconds'] for _, _, a in selected] == [180, 600, 1800, 3600]
    assert [a['attempt'] for _, _, a in selected] == [1, 2, 3, 4]
    assert [a['exhausted'] for _, _, a in selected] == [False, False, False, True]
    assert all(a['seed'] == 0 and a['watchdog'] and a['error'] is None
               and a['purpose'] == 'fresh_measurement' for _, _, a in selected)
    attempts, late_signatures = [], []
    for line, raw, a in selected:
        timeline_bytes = blob(a['progressPath'])
        assert timeline_bytes == (ROOT / a['progressPath']).read_bytes()
        timeline = [json.loads(l) for l in timeline_bytes.splitlines()]
        assert all(r['diagnosticOnly'] is True for r in timeline)
        assert all(x['tick'] < y['tick'] for x, y in zip(timeline, timeline[1:]))
        last = timeline[-1]
        start = len(timeline) - 1
        while start and core(timeline[start - 1]) == core(last):
            start -= 1
        suffix = timeline[start:]
        first = suffix[0]
        deltas = {k: last['eventCounts'].get(k, 0) - first['eventCounts'].get(k, 0)
                  for k in set(first['eventCounts']) | set(last['eventCounts'])}
        changed = {k: v for k, v in deltas.items() if v}
        if a['attempt'] == 1:
            assert len(suffix) == 1
            assert last['byOwner'] == {'2': {'units': 1, 'hp': 9}, '3': {'units': 14, 'hp': 1714}}
        else:
            assert len(suffix) > 1 and set(changed) == CONTINUING
            assert all(v > 0 for v in changed.values())
            assert last['byOwner'] == {'2': {'units': 1, 'hp': 9}, '3': {'units': 3, 'hp': 339}}
            assert all(p['action'] == 'idle' and p['attackTargetId'] is None for p in last['positions'])
            late_signatures.append(canonical(core(last)))
        attempts.append({'attempt': a['attempt'], 'seed': 0, 'limitSeconds': a['limitSeconds'],
                         'startedAt': a['startedAt'], 'finishedAt': a['finishedAt'], 'exhausted': a['exhausted'],
                         'sourceAttemptLine': line, 'sourceLineSha256IncludingNewline': SHA(raw),
                         'progressPath': a['progressPath'], 'progressSha256': SHA(timeline_bytes),
                         'snapshots': len(timeline), 'reportedLastProgress': a['lastProgress'],
                         'savedLastTick': last['tick'], 'savedLastSimulationSeconds': last['simulationSeconds'],
                         'constantCoreSuffixSnapshots': len(suffix), 'constantCoreSuffixFirstTick': first['tick'],
                         'constantCoreSuffixFirstSimulationSeconds': first['simulationSeconds'],
                         'constantCoreSuffixLastSimulationSeconds': last['simulationSeconds'],
                         'stablePositionsHpActionsAndTargetsAcrossMultipleSnapshots': len(suffix) > 1,
                         'continuingEventDeltas': changed, 'survivors': last['byOwner']})
    assert len(late_signatures) == 3 and len(set(late_signatures)) == 1
    run_bytes = blob(BASE + '/runs.jsonl')
    assert not [r for r in map(json.loads, run_bytes.splitlines()) if r['matchupId'] == JOB]
    pair_path = BASE + '/pair-reviews/' + JOB + '.json'
    assert not (ROOT / pair_path).exists()
    assert not subprocess.check_output(['git', 'ls-tree', SOURCE, '--', pair_path], cwd=ROOT)
    phase_bytes = blob(BASE + '/reviews/044.json')
    phase = json.loads(phase_bytes)
    assert phase['status'] == 'complete_with_blocked' and JOB in phase['blockedJobs']
    last_attempt = attempts[-1]
    report = {'version': 1, 'diagnosticOnly': True, 'campaignHash': manifest['campaignHash'],
              'sourceCommit': SOURCE, 'sourceManifestSha256': SHA(blob(BASE + '/manifest.json')),
              'samplingPolicyHash': policy['amendmentHash'],
              'samplingPolicyFileSha256': SHA(blob(BASE + '/sampling-policy-v3.json')),
              'jobId': JOB, 'nativeMatchupId': job['nativeMatchupId'], 'contextHash': job['contextHash'],
              'context': job['context'], 'teamKeys': job['teamKeys'], 'mechanicsUnitNames': unit_names,
              'sourceFrozenProfiles': FROZEN, 'sourceFrozenProfilesSha256': SHA(frozen_bytes),
              'counts': job['counts'], 'originalEvidence': original,
              'originalPredictionTier': job['predictionTier'], 'physicsVersion': manifest['physicsVersion'],
              'executionVersion': manifest['executionVersion'], 'sourceAttemptJournal': BASE + '/attempts.jsonl',
              'sourceAttemptJournalSha256': SHA(attempt_bytes), 'attempts': attempts,
              'sourceNativeJournal': BASE + '/runs.jsonl', 'sourceNativeJournalSha256': SHA(run_bytes),
              'phaseReview': BASE + '/reviews/044.json', 'phaseReviewSha256': SHA(phase_bytes),
              'identicalLateCoreStateAttempts': [2, 3, 4], 'firstAttemptReachedEarlierDifferentState': True,
              'lateState': json.loads(late_signatures[-1]), 'validNativeSeedReferences': [],
              'requiredFirstSeedNotCompleted': 0, 'laterSeedRequirementsDependOnCompletedFirstResult': True,
              'replayEvidence': {'required': False, 'performed': False, 'exact': None},
              'status': 'blocked_needs_separate_recovery_review', 'assignedOutcome': None,
              'diagnosis': 'The 180-second attempt ended earlier, with one skirmisher and fourteen cavalry survivors. The three longer attempts reach the same fixed positions, HP, actions and targets: one Elite Skirmisher at 9 HP and three Cavaliers at 339 combined HP, all idle with null attack targets. Five pursuit/contact/blocked counters continue increasing, but all combat counters are unchanged throughout each late constant suffix. The final saved suffix spans 106 snapshots. The precise contact, geometry, range or route/acquisition cause is not established.',
              'interpretation': 'The frozen runtime stalls within the tested watchdog limits; this is neither a draw nor a native winner. Seed 0 never completed. Survivor counts and HP do not authorize a correction. Frozen role keys are retained; mechanics unit names identify the actual simulated upgrades.',
              'queueAction': 'Retain all failures and leave this job blocked. Continue unrelated ordinary jobs using the existing healthy runner. No retry or restart is performed by this diagnosis.',
              'futureRecoveryGate': 'A separate reviewed recovery decision is needed before another retry. No physics change, cross-engine import or copied winner is authorized. The current distinct-seed/no-replay amendment remains in force.',
              'simulationExecutionsForDiagnosis': 0, 'physicsChanged': False,
              'forecastChanged': False, 'nativeResultsAdded': False}
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'REVIEW.json').open('x') as f:
        f.write(json.dumps(report, sort_keys=True, indent=2) + '\n')
    text = f'''# Exhausted Incan Elite Skirmisher / Polish Cavalier seed

Job `{JOB}`, original physical counts **27 / 19**, has no completed seed.
Frozen role keys are `Incas|imp_elite_skirm` and `Poles|paladin`; the unchanged
mechanics profiles name the actual upgrades **Elite Skirmisher / Cavalier**.

Seed 0 exhausted the 180/600/1800/3600-wall-second watchdogs. The first attempt
ended at an earlier state with one skirmisher and fourteen cavalry survivors.
The three longer attempts reach identical late positions, HP, actions and
targets: one skirmisher at **9 HP**, and three Cavaliers at **339 combined HP**.
All four are idle with null attack targets, although some pursuit/engagement
targets remain assigned. Five pursuit/contact/blocked counters continue growing;
other event counters, including combat, remain unchanged in each saved late suffix.

The final attempt ended at tick {last_attempt['reportedLastProgress']['tick']:,}.
Its last fsynced snapshot is earlier, at tick {last_attempt['savedLastTick']:,}.
Its constant core suffix contains **{last_attempt['constantCoreSuffixSnapshots']} snapshots**, from game second
{last_attempt['constantCoreSuffixFirstSimulationSeconds']} to {last_attempt['constantCoreSuffixLastSimulationSeconds']}.
The saved timelines establish a reproducible late stall within the tested limits,
not its exact contact/range/geometry/route cause or a real-game winner or draw.

No seed 0 measurement, pair review or correction is assigned. Later seed
requirements depend on a completed first result. No same-seed replay is required
or performed under the current v3 amendment. No simulation was executed for this
diagnosis, and no physics, forecasts, contexts, inventory order or queue controls changed.

The immutable source is `{SOURCE}`. `REVIEW.json` retains original context/profile
order, counts, evidence and flags, four attempt-line hashes and all progress hashes,
plus source manifest, frozen-profile, sampling-policy, journal and phase-review hashes.
The phase-044 `complete_with_blocked` status is not full completion. The ordinary
queue continues, and this job remains blocked pending a separate recovery review.

From the repository root, reproduce into a new directory:

```sh
python {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>
```
'''
    with (args.output / 'README.md').open('x') as f:
        f.write(text)
    print(json.dumps({'jobId': JOB, 'sourceCommit': SOURCE, 'diagnosedAttempts': len(attempts),
                      'identicalLateCoreStateAttempts': [2, 3, 4],
                      'finalConstantCoreSuffixSnapshots': last_attempt['constantCoreSuffixSnapshots'],
                      'completedSeeds': 0, 'outcomeAssigned': False, 'simulationExecutions': 0}))


if __name__ == '__main__':
    main()
