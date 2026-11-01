#!/usr/bin/env python3
"""Recount frozen model errors after narrow contextual abstentions."""

import argparse
import collections
import json
from pathlib import Path

from build_civ_candidate_pool import hgb_supported
from evaluate_civ_prediction_coverage import DEFINITION, RANK, load, rank_fingerprints, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validation-predictions', type=Path, required=True)
    parser.add_argument('--variant-profiles', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = load(args.validation_predictions)
    variants = load(args.variant_profiles)
    definition = load(DEFINITION)
    hashes = sorted({v['profileHash'] for v in variants})
    index = {h: i for i, h in enumerate(hashes)}
    by_key = {v['key']: v['profileHash'] for v in variants}
    lines = {v['profileHash']: v['line'] for v in variants}
    mechanics = {v['profileHash']: definition['profiles'][v['key']]['mechanics']
                 for v in variants}
    _, rank = rank_fingerprints(variants, definition, index)
    result = {'kind': 'post-hoc guard screen; not prospective validation',
        'sourceHashes': {'validationPredictions': sha(args.validation_predictions),
            'variantProfiles': sha(args.variant_profiles),
            'rankingDefinition': sha(DEFINITION), 'rankingPredictiveFeatures': sha(RANK / 'runs.jsonl')},
        'splits': {}}
    for name, group in source['predictions'].items():
        selected = []
        original_errors = []
        excluded_errors = []
        for record in group:
            if record['confidence'] < .95:
                continue
            profiles = [by_key[key] for key in record['units']]
            row = {'profiles': profiles, 'family': record['family']}
            wrong = record['predicted'] != record['actual']
            if wrong:
                original_errors.append(record)
            if hgb_supported(row, index, rank, lines, mechanics):
                selected.append(record)
            elif wrong:
                excluded_errors.append(record)
        errors = [r for r in selected if r['predicted'] != r['actual']]
        result['splits'][name] = {
            'originalSelectedAt95': sum(r['confidence'] >= .95 for r in group),
            'originalWrongOrClose': len(original_errors),
            'selectedAfterGuards': len(selected),
            'wrongOrCloseAfterGuards': len(errors),
            'excludedErrors': excluded_errors, 'remainingErrors': errors,
            'selectedByFamily': dict(sorted(collections.Counter(r['family'] for r in selected).items()))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({name: {k: v[k] for k in ('selectedAfterGuards','wrongOrCloseAfterGuards')}
                      for name, v in result['splits'].items()}))


if __name__ == '__main__':
    main()
