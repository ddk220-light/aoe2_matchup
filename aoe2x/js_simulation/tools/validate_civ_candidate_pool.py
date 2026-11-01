#!/usr/bin/env python3
"""Check provisional candidate winners against one later reviewed phase."""

import argparse
import collections
import json
from pathlib import Path

from evaluate_civ_prediction_coverage import phase_of, records, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--phase', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.campaign / 'latest-inference'
    predictions = {r['pairKey']: r for r in records(args.predictions)}
    observed = [r for r in records(root / 'profile-matchups.jsonl.gz')
                if r['evidenceType'] == 'observed' and phase_of(r) == args.phase]
    selected = []
    by_family = collections.Counter()
    by_method = collections.Counter()
    failures = []
    for row in observed:
        pred = predictions.get(row['pairKey'])
        if pred is None:
            continue
        selected.append(row['pairKey'])
        by_family[pred['family']] += 1
        for method in pred['supportingMethods']:
            by_method[method] += 1
        if pred['predictedOutcome'] != row['outcome']:
            failures.append({'pairKey': row['pairKey'], 'family': pred['family'],
                'predictedOutcome': pred['predictedOutcome'], 'actualOutcome': row['outcome'],
                'supportingMethods': pred['supportingMethods']})
    report = {'kind': 'reviewed-phase validation of provisional candidate pool',
        'phase': args.phase, 'phaseObservedRows': len(observed),
        'selected': len(selected), 'wrongOrClose': len(failures),
        'selectedByFamily': dict(sorted(by_family.items())),
        'selectedByMethod': dict(sorted(by_method.items())),
        'failures': failures,
        'sourceHashes': {'predictions': sha(args.predictions),
            'profileMatchups': sha(root / 'profile-matchups.jsonl.gz')}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('phase','phaseObservedRows','selected','wrongOrClose')}))


if __name__ == '__main__':
    main()
