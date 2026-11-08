"""Diagnose an exhausted forecast from committed snapshots; execute no battles."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = next((p for p in Path(__file__).resolve().parents
             if (p / 'aoe2x/js_simulation/calibration').is_dir()), Path.cwd())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = 'cded99b0b044a7bcfe108bc7a80453a193eeee63'
JOB = 'fv_9c07f592c61760a424b461f4'
SHA = lambda b: hashlib.sha256(b).hexdigest()


def blob(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def signature(row):
    return canonical({k: row[k] for k in ['byOwner', 'positions', 'eventCounts']})


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
    assert job['teamKeys'] == ['Danes|elite_jomsviking_danes', 'Muisca|elite_guecha_warrior_muisca']
    assert job['counts'] == [27, 23]
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
    attempts, signatures = [], []
    for line, raw, attempt in selected:
        timeline_bytes = blob(attempt['progressPath'])
        assert timeline_bytes == (ROOT / attempt['progressPath']).read_bytes()
        timeline = [json.loads(l) for l in timeline_bytes.splitlines()]
        assert all(r['diagnosticOnly'] is True for r in timeline)
        assert all(a['tick'] < b['tick'] for a, b in zip(timeline, timeline[1:]))
        last = timeline[-1]
        start = len(timeline) - 1
        while start and signature(timeline[start - 1]) == signature(last):
            start -= 1
        suffix = timeline[start:]
        assert len(suffix) > 1
        assert all(p['action'] == 'idle' and p['pursuitTargetId'] is None
                   and p['engagedTargetId'] is None and p['attackTargetId'] is None
                   for p in last['positions'])
        assert {(p['x'], p['y']) for p in last['positions'] if p['owner'] == 2} == {(2, 13)}
        assert {(p['x'], p['y']) for p in last['positions'] if p['owner'] == 3} == {(13, 2)}
        assert last['byOwner'] == {'2': {'units': 12, 'hp': 666},
                                   '3': {'units': 1, 'hp': 16.027777777777807}}
        signatures.append(signature(last))
        attempts.append({'attempt': attempt['attempt'], 'seed': 0,
                         'limitSeconds': attempt['limitSeconds'], 'startedAt': attempt['startedAt'],
                         'finishedAt': attempt['finishedAt'], 'exhausted': attempt['exhausted'],
                         'sourceAttemptLine': line, 'sourceLineSha256IncludingNewline': SHA(raw),
                         'progressPath': attempt['progressPath'], 'progressSha256': SHA(timeline_bytes),
                         'snapshots': len(timeline), 'reportedLastProgress': attempt['lastProgress'],
                         'savedLastTick': last['tick'], 'savedLastSimulationSeconds': last['simulationSeconds'],
                         'constantSuffixSnapshots': len(suffix),
                         'constantSuffixFirstTick': suffix[0]['tick'],
                         'constantSuffixFirstSimulationSeconds': suffix[0]['simulationSeconds'],
                         'constantSuffixLastSimulationSeconds': last['simulationSeconds'],
                         'stablePositionsHpActionsAndTargets': True, 'allEventCountersUnchanged': True,
                         'survivors': last['byOwner']})
    assert len(set(signatures)) == 1
    run_bytes = blob(BASE + '/runs.jsonl')
    assert not [r for r in map(json.loads, run_bytes.splitlines()) if r['matchupId'] == JOB]
    assert not (ROOT / BASE / 'pair-reviews' / (JOB + '.json')).exists()
    phase_bytes = blob(BASE + '/reviews/030.json')
    phase = json.loads(phase_bytes)
    assert phase['status'] == 'complete_with_blocked' and JOB in phase['blockedJobs']
    last = attempts[-1]
    report = {'version': 1, 'diagnosticOnly': True, 'campaignHash': manifest['campaignHash'],
              'sourceCommit': SOURCE, 'sourceManifestSha256': SHA(blob(BASE + '/manifest.json')),
              'samplingPolicyHash': policy['amendmentHash'],
              'samplingPolicyFileSha256': SHA(blob(BASE + '/sampling-policy-v3.json')),
              'jobId': JOB, 'nativeMatchupId': job['nativeMatchupId'], 'contextHash': job['contextHash'],
              'context': job['context'], 'teamKeys': job['teamKeys'], 'counts': job['counts'],
              'originalEvidence': original, 'originalPredictionTier': job['predictionTier'],
              'physicsVersion': manifest['physicsVersion'], 'executionVersion': manifest['executionVersion'],
              'sourceAttemptJournal': BASE + '/attempts.jsonl',
              'sourceAttemptJournalSha256': SHA(attempt_bytes), 'attempts': attempts,
              'sourceNativeJournal': BASE + '/runs.jsonl', 'sourceNativeJournalSha256': SHA(run_bytes),
              'phaseReview': BASE + '/reviews/030.json', 'phaseReviewSha256': SHA(phase_bytes),
              'identicalLateStateAcrossAllFourAttempts': True, 'lateState': json.loads(signatures[-1]),
              'validNativeSeedReferences': [], 'requiredFirstSeedNotCompleted': 0,
              'laterSeedRequirementsDependOnCompletedFirstResult': True,
              'replayEvidence': {'required': False, 'performed': False, 'exact': None},
              'status': 'blocked_needs_separate_recovery_review', 'assignedOutcome': None,
              'diagnosis': 'All four watchdog attempts reproduce twelve idle Elite Jomsvikings at (2,13), 666 combined HP, and one idle Elite Guecha Warrior at (13,2), 16.027777777777807 HP. All thirteen have null pursuit, engagement and attack targets. Positions, HP, actions, targets and every event counter remain constant throughout each saved late suffix while ticks advance. The precise mechanism that put the survivors in these corners and prevented further combat is not established by these snapshots.',
              'interpretation': 'This is frozen-runtime nontermination, not a draw or a native winner. Seed 0 never completed. No native result or correction can be assigned, regardless of the surviving HP totals or original forecast.',
              'queueAction': 'Retain all failures, leave this job blocked, and continue unrelated ordinary contexts with the healthy existing runner. No retry or restart is performed by this diagnosis.',
              'futureRecoveryGate': 'A separate reviewed recovery decision is needed before another retry. No physics change, cross-engine result import or copied winner is authorized. The current distinct-seed/no-replay amendment remains in force.',
              'simulationExecutionsForDiagnosis': 0, 'physicsChanged': False,
              'forecastChanged': False, 'nativeResultsAdded': False}
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'REVIEW.json').open('x') as f:
        f.write(json.dumps(report, sort_keys=True, indent=2) + '\n')
    text = f'''# Exhausted Danish Elite Jomsviking / Muisca Elite Guecha Warrior seed

Job `{JOB}`, original counts **27 / 23**, has no completed seed.
Seed 0 exhausted the 180/600/1800/3600-wall-second watchdogs. The final attempt
ended at tick {last['reportedLastProgress']['tick']:,}; its last fsynced snapshot
is earlier, at tick {last['savedLastTick']:,}.

All four attempts reproduce twelve idle Jomsvikings at **(2,13)** with **666 HP**
combined and one idle Guecha Warrior at **(13,2)** with **16.027777777777807 HP**.
All thirteen survivors have null pursuit, engagement and attack targets. Their
positions, HP, actions, targets and every event counter remain constant in each
late suffix. The final attempt has **{last['constantSuffixSnapshots']}** such consecutive snapshots,
from game second {last['constantSuffixFirstSimulationSeconds']} to
{last['constantSuffixLastSimulationSeconds']}, while the simulation ticks advance.
The snapshots establish nontermination in the frozen runtime; they do not explain
precisely how these idle corner states arose or establish a real-game winner.

No seed 0 measurement, pair review, native outcome, draw or correction is assigned.
Additional seed requirements remain conditional on a completed first result.
Same-seed replays are not required and were not performed under the current v3
amendment. No simulation was executed for this diagnosis.

The immutable source is `{SOURCE}`. `REVIEW.json` retains physical profile order,
counts, original evidence and flags, four attempt-line hashes and all progress
hashes, plus the source manifest, sampling policy, journal and phase-review hashes.
The phase-030 `complete_with_blocked` status is not full completion.

No physics, forecasts, inventory order or queue controls changed. The existing
four-worker ordinary queue continues; this job stays blocked. A separate recovery
review is required before another retry. No old or cross-engine winner is imported.

From the repository root, reproduce with:

```sh
python {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>
```
'''
    with (args.output / 'README.md').open('x') as f:
        f.write(text)
    print(json.dumps({'jobId': JOB, 'sourceCommit': SOURCE, 'diagnosedAttempts': len(attempts),
                      'finalConstantSuffixSnapshots': last['constantSuffixSnapshots'],
                      'completedSeeds': 0, 'outcomeAssigned': False, 'simulationExecutions': 0}))


if __name__ == '__main__':
    main()
