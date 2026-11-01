#!/usr/bin/env python3
"""Check provisional candidate winners against one later reviewed phase."""

import argparse
import collections
import json
from pathlib import Path

from evaluate_civ_prediction_coverage import records, sha
from civ_reviewed_phase import load_reviewed_phase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--phase', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inference-dir', type=Path,
                        help='Immutable inference snapshot matching the phase review')
    args = parser.parse_args()
    observed, _, provenance = load_reviewed_phase(args.campaign, args.phase, args.inference_dir)
    prediction_rows = list(records(args.predictions))
    predictions = {r['pairKey']: r for r in prediction_rows}
    if len(predictions) != len(prediction_rows):
        raise ValueError('duplicate predictions for a profile pair')
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
        'plannedCandidatePairs': len(selected) + sum(
            key in predictions for key in provenance['blockedPairs']),
        'blockedCandidatePairs': [key for key in provenance['blockedPairs'] if key in predictions],
        'completeForPlannedCandidates': not any(
            key in predictions for key in provenance['blockedPairs']),
        'selectedByFamily': dict(sorted(by_family.items())),
        'selectedByMethod': dict(sorted(by_method.items())),
        'failures': failures,
        'reviewedEvidence': provenance,
        'sourceHashes': {'predictions': sha(args.predictions),
            'profileMatchups': provenance['profileMatchups']}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('phase','phaseObservedRows','selected','wrongOrClose')}))


if __name__ == '__main__':
    main()
