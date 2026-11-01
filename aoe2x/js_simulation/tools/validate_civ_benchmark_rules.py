#!/usr/bin/env python3
"""Validate a frozen common-benchmark rule version on a later reviewed phase."""

import argparse
import json
from pathlib import Path

import numpy as np

from evaluate_civ_prediction_coverage import (
    DEFINITION, load, outcome, phase_of, rank_fingerprints, records, sha,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--phase', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rules = load(args.rules)
    root = args.campaign / 'latest-inference'
    rows = [r for r in records(root / 'profile-matchups.jsonl.gz')
            if r['evidenceType'] == 'observed' and phase_of(r) == args.phase]
    variants = load(root / 'variant-profiles.json')
    hashes = sorted({v['profileHash'] for v in variants})
    index = {h: i for i, h in enumerate(hashes)}
    lines = {v['profileHash']: v['line'] for v in variants}
    definition = load(DEFINITION)
    standards, rank = rank_fingerprints(variants, definition, index)
    unit_class = {v['profileHash']: definition['profiles'][v['key']]['mechanics']['unit_class']
                  for v in variants}
    standard_index = {key: i for i, key in enumerate(standards)}
    by_family = {r['family']: r for r in rules['rules']}
    selected = []
    failures = []
    by_family_count = {}
    for row in rows:
        family = '|'.join(sorted(lines[h] for h in row['profiles']))
        rule = by_family.get(family)
        if not rule:
            continue
        if rule.get('subtypeFilter') == 'skirmisher.unit_class=0':
            skirmisher = next(h for h in row['profiles'] if lines[h] == 'skirmisher')
            if unit_class[skirmisher] != 0:
                continue
        a, b = [index[h] for h in row['profiles']]
        cols = [standard_index[key] for key in rule['benchmarks']]
        margin = rank[a, cols] - rank[b, cols]
        gap = rule['minimumHpMarginGap']
        predicted = 1 if np.all(margin >= gap) else -1 if np.all(margin <= -gap) else 0
        if not predicted:
            continue
        by_family_count[family] = by_family_count.get(family, 0) + 1
        record = {'pairKey': row['pairKey'], 'family': family,
                  'predicted': predicted, 'actual': outcome(row),
                  'marginGaps': [float(x) for x in margin]}
        selected.append(record)
        if predicted != outcome(row):
            failures.append(record)
    report = {'kind': 'independent next-phase validation of frozen benchmark rules',
              'ruleVersion': rules['ruleVersion'], 'phase': args.phase,
              'phaseRows': len(rows), 'selected': len(selected),
              'wrongOrClose': len(failures), 'selectedByFamily': by_family_count,
              'failures': failures,
              'sourceHashes': {'rules': sha(args.rules),
                               'profileMatchups': sha(root / 'profile-matchups.jsonl.gz'),
                               'variantProfiles': sha(root / 'variant-profiles.json')}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('phase', 'phaseRows', 'selected', 'wrongOrClose')}, indent=2))


if __name__ == '__main__':
    main()
