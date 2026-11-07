"""Read-only diagnosis of an exhausted seed from immutable Git snapshots."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = '43f129b7852722b4d6c8f87928104b34c98e447f'
JOB = 'fv_c553e033f98149a99dc0ffcf'
SHA = lambda data: hashlib.sha256(data).hexdigest()


def blob(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def signature(row):
    # Positions also retain HP, action and target IDs; only these two retry
    # counters continue changing in the otherwise fixed late snapshots.
    return canonical({'byOwner': row['byOwner'], 'positions': row['positions'],
                      'eventCounts': {k: v for k, v in row['eventCounts'].items()
                                      if k not in ['blocked', 'pursuit-route-planned']}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    assert not (args.output / 'REVIEW.json').exists(), 'Never overwrite an existing diagnosis.'
    jobs = [json.loads(x) for x in gzip.decompress(blob(BASE + '/jobs.jsonl.gz')).splitlines()]
    job = next(j for j in jobs if j['id'] == JOB)
    manifest = json.loads(blob(BASE + '/manifest.json'))
    assert job['contextHash'] == SHA(canonical(job['context']).encode())
    attempt_bytes = blob(BASE + '/attempts.jsonl')
    selected = [(line, raw, json.loads(raw)) for line, raw in enumerate(attempt_bytes.splitlines(keepends=True), 1)
                if json.loads(raw)['matchupId'] == JOB]
    assert [a['limitSeconds'] for _, _, a in selected] == [180, 600, 1800, 3600]
    assert all(a['watchdog'] and a['error'] is None and a['seed'] == 1 for _, _, a in selected)
    assert [a['exhausted'] for _, _, a in selected] == [False, False, False, True]
    attempts, late_signatures = [], []
    for line, raw, a in selected:
        timeline_bytes = blob(a['progressPath'])
        assert timeline_bytes == (ROOT / a['progressPath']).read_bytes()
        timeline = [json.loads(x) for x in timeline_bytes.splitlines()]
        assert all(r['diagnosticOnly'] is True for r in timeline)
        assert all(b['tick'] > a['tick'] for a, b in zip(timeline, timeline[1:]))
        last = timeline[-1]
        start = len(timeline) - 1
        while start and signature(timeline[start - 1]) == signature(last):
            start -= 1
        suffix = timeline[start:]
        assert len(suffix) > 1
        late_signatures.append(signature(last))
        first = suffix[0]
        deltas = {key: last['eventCounts'].get(key, 0) - first['eventCounts'].get(key, 0)
                  for key in set(first['eventCounts']) | set(last['eventCounts'])}
        changed = {k: v for k, v in deltas.items() if v}
        assert set(changed) == {'blocked', 'pursuit-route-planned'}
        assert all(v > 0 for v in changed.values())
        attempts.append({'attempt': a['attempt'], 'seed': a['seed'], 'limitSeconds': a['limitSeconds'],
                         'finishedAt': a['finishedAt'], 'exhausted': a['exhausted'],
                         'sourceAttemptLine': line, 'sourceLineSha256IncludingNewline': SHA(raw),
                         'progressPath': a['progressPath'], 'progressSha256': SHA(timeline_bytes),
                         'snapshots': len(timeline), 'reportedLastProgress': a['lastProgress'],
                         'savedLastTick': last['tick'], 'savedLastSimulationSeconds': last['simulationSeconds'],
                         'constantSuffixSnapshots': len(suffix), 'constantSuffixFirstTick': first['tick'],
                         'constantSuffixFirstSimulationSeconds': first['simulationSeconds'],
                         'constantSuffixLastSimulationSeconds': last['simulationSeconds'],
                         'stablePositionsHpActionsAndTargets': True, 'stableCombatCounters': True,
                         'continuingEventDeltas': changed, 'survivors': last['byOwner']})
    assert len(set(late_signatures)) == 1
    run_bytes = blob(BASE + '/runs.jsonl')
    partial = [(line, raw, json.loads(raw)) for line, raw in enumerate(run_bytes.splitlines(keepends=True), 1)
               if json.loads(raw)['matchupId'] == JOB]
    assert [r['seed'] for _, _, r in partial] == [0]
    assert not (ROOT / BASE / 'pair-reviews' / (JOB + '.json')).exists()
    phase = json.loads(blob(BASE + '/reviews/001.json'))
    assert phase['status'] == 'complete_with_blocked' and JOB in phase['blockedJobs']
    report = {'version': 1, 'diagnosticOnly': True, 'campaignHash': manifest['campaignHash'],
              'sourceCommit': SOURCE, 'sourceManifestSha256': SHA(blob(BASE + '/manifest.json')),
              'jobId': JOB, 'nativeMatchupId': job['nativeMatchupId'], 'contextHash': job['contextHash'],
              'context': job['context'], 'teamKeys': job['teamKeys'], 'counts': job['counts'],
              'originalEvidenceIds': job['evidenceIds'], 'originalPredictionTier': job['predictionTier'],
              'physicsVersion': manifest['physicsVersion'], 'executionVersion': manifest['executionVersion'],
              'sourceAttemptJournal': BASE + '/attempts.jsonl', 'sourceAttemptJournalSha256': SHA(attempt_bytes),
              'attempts': attempts, 'identicalLateStateAcrossAllFourAttempts': True,
              'lateState': json.loads(late_signatures[-1]),
              'validPartialSeedReferences': [{'seed': r['seed'], 'sourceLine': line,
                                               'sourceLineSha256IncludingNewline': SHA(raw)} for line, raw, r in partial],
              'missingRequiredSeeds': [1, 2], 'exactReplayMissing': True,
              'status': 'blocked_needs_separate_recovery_review', 'assignedOutcome': None,
              'diagnosis': 'Deterministic nontermination after combat: one Hussite Wagon and eight Mounted Trebuchets retain fixed positions, HP, actions and targets while blocked and pursuit-route-planned counters continue increasing. No additional combat occurs in the saved constant suffixes. The precise acquisition, range, geometry or routing cause is not established by these snapshots.',
              'interpretation': 'A watchdog and static survivors are not a draw or winner. The partial seed set contributes no correction. Repeatedly extending the same attempt is not authorized.',
              'queueAction': 'Preserve the exhausted records and keep this job blocked. Continue all unrelated ordinary jobs without restarting or replacing the live runner.',
              'futureRecoveryGate': 'A separate reviewed recovery decision is needed before retrying. Any physics change needs explicit approval, its own version, native seed set and exact replay; do not import cross-engine or old winners.',
              'physicsChanged': False, 'forecastChanged': False, 'measurementsAdded': False}
    args.output.mkdir(exist_ok=True, parents=True)
    (args.output / 'REVIEW.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    last = attempts[-1]
    text = f'''# Exhausted Bohemian Hussite Wagon / Khitan Mounted Trebuchet seed

Job `{JOB}`, seed 1, original counts **27 / 19**, remains unfinished.
The 180/600/1800/3600-wall-second attempts all ended at their watchdogs.
The final attempt ended at tick {last['reportedLastProgress']['tick']:,}; its
last fsynced snapshot is earlier, at tick {last['savedLastTick']:,}.

All four attempts reproduce the same late positions, HP, actions and targets:
one Hussite Wagon at 62.233333333337754 HP and eight Mounted Trebuchets at
570 combined HP. The final timeline has {last['constantSuffixSnapshots']} consecutive
unchanged combat/position snapshots, from game second
{last['constantSuffixFirstSimulationSeconds']} to {last['constantSuffixLastSimulationSeconds']}.
Only blocked and pursuit-route-planned event counters increase over those
suffixes. Their exact deltas and all source hashes are in `REVIEW.json`.

This establishes nontermination in the frozen runtime. It does not establish
the precise acquisition/range/routing cause or an actual AoE2 winner or draw.
Only seed 0 was saved; required seeds 1 and 2 and a pair exact replay remain
missing. No partial outcome or diagnostic is imported as a correction.

The source is Git commit `{SOURCE}`. Attempt lines, progress timelines,
original context/profile order and counts are bound by exact hashes. No physics,
forecast, inventory, queue control or runtime file was changed. No retry or
campaign restart was performed; the ordinary queue continues with this job
blocked by its exhausted journal record.

Reproduce into a new directory with `python analyze.py --output <new-directory>`.
A separately reviewed recovery decision is required before retrying this case.
'''
    (args.output / 'README.md').write_text(text)
    print(json.dumps({'jobId': JOB, 'diagnosedAttempts': len(attempts), 'sourceCommit': SOURCE,
                      'finalConstantSuffixSnapshots': last['constantSuffixSnapshots'],
                      'missingSeeds': [1, 2], 'outcomeAssigned': False}))


if __name__ == '__main__':
    main()
