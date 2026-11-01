#!/usr/bin/env python3
"""Mine interpretable common-benchmark rules, using completed fights only.

Ranking HP margins are predictive features. A rule may only pass a pair when
multiple benchmark margins point the same way; this program never records a
fight result or promotes a guess into the live campaign.
"""

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

from evaluate_civ_prediction_coverage import (
    DEFINITION, RANK, load, outcome, phase_of, rank_fingerprints, records, sha,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--guesses-output', type=Path)
    args = parser.parse_args()
    root = args.campaign / 'latest-inference'
    rows = list(records(root / 'profile-matchups.jsonl.gz'))
    variants = load(root / 'variant-profiles.json')
    hashes = sorted({v['profileHash'] for v in variants})
    index = {h: i for i, h in enumerate(hashes)}
    lines = {v['profileHash']: v['line'] for v in variants}
    definition = load(DEFINITION)
    standards, rank = rank_fingerprints(variants, definition, index)
    unit_class = {v['profileHash']: definition['profiles'][v['key']]['mechanics']['unit_class']
                  for v in variants}
    def supported_context(row, family):
        if family == 'militia|skirmisher':
            skirmisher = next(h for h in row['profiles'] if lines[h] == 'skirmisher')
            return unit_class[skirmisher] == 0
        return True
    sets = {
        'train': [r for r in rows if r['evidenceType'] == 'observed' and phase_of(r) <= 20],
        'calibration': [r for r in rows if r['evidenceType'] == 'observed' and 21 <= phase_of(r) <= 22],
        'test': [r for r in rows if r['evidenceType'] == 'observed' and 23 <= phase_of(r) <= 24],
        'unresolved': [r for r in rows if r['outcome'] == 'unresolved'],
    }
    prepared = {}
    for name, group in sets.items():
        a = np.array([index[r['profiles'][0]] for r in group])
        b = np.array([index[r['profiles'][1]] for r in group])
        prepared[name] = {
            'rows': group, 'margin': rank[a] - rank[b],
            'family': np.array(['|'.join(sorted(lines[h] for h in r['profiles'])) for r in group]),
            'actual': np.array([outcome(r) for r in group]),
        }
    families = sorted(set(prepared['train']['family']))
    results = []
    selected = {name: np.zeros(len(data['rows']), dtype=np.int8) for name, data in prepared.items()}
    for family in families:
        masks = {name: np.array([
            row_family == family and supported_context(row, family)
            for row, row_family in zip(data['rows'], data['family'])])
            for name, data in prepared.items()}
        if masks['calibration'].sum() < 5:
            continue
        best = None
        for size in (2, 3):
            for columns in itertools.combinations(range(len(standards)), size):
                for gap in (0.10, 0.20, 0.30, 0.40):
                    signs = {}
                    scores = {}
                    for name in ('train', 'calibration', 'test'):
                        data = prepared[name]
                        d = data['margin'][masks[name]][:, columns]
                        predicted = np.where(np.all(d >= gap, axis=1), 1,
                            np.where(np.all(d <= -gap, axis=1), -1, 0))
                        truth = data['actual'][masks[name]]
                        chosen = predicted != 0
                        scores[name] = (int(chosen.sum()),
                                        int(np.sum(predicted[chosen] != truth[chosen])))
                        signs[name] = predicted
                    if scores['train'][0] < 20 or scores['train'][1] or scores['calibration'][0] < 5 or scores['calibration'][1]:
                        continue
                    quality = (scores['calibration'][0], scores['train'][0], -gap, -size)
                    if best is None or quality > best[0]:
                        best = (quality, columns, gap, scores, signs)
        if not best:
            continue
        _, columns, gap, scores, signs = best
        d = prepared['unresolved']['margin'][masks['unresolved']][:, columns]
        signs['unresolved'] = np.where(np.all(d >= gap, axis=1), 1,
            np.where(np.all(d <= -gap, axis=1), -1, 0))
        scores['unresolved'] = (int(np.count_nonzero(signs['unresolved'])), None)
        for name in prepared:
            selected[name][masks[name]] = signs[name]
        condition = {'family': family, 'benchmarks': [standards[c] for c in columns],
                     'subtypeFilter': 'skirmisher.unit_class=0' if family == 'militia|skirmisher' else None,
                     'minimumHpMarginGap': gap}
        condition['ruleHash'] = hashlib.sha256(json.dumps(condition, sort_keys=True,
            separators=(',', ':')).encode()).hexdigest()
        results.append({**condition,
                        'train': {'selected': scores['train'][0], 'wrongOrClose': scores['train'][1]},
                        'calibration': {'selected': scores['calibration'][0], 'wrongOrClose': scores['calibration'][1]},
                        'test': {'selected': scores['test'][0], 'wrongOrClose': scores['test'][1]},
                        'unresolvedCandidateGuesses': scores['unresolved'][0]})
    report = {'kind': 'exploratory, interpreted benchmark rules, no accepted skips',
              'selection': 'per-family benchmark set chosen using train and calibration; test held out',
              'rules': results, 'total': {},
              'sourceHashes': {
                  'profileMatchups': sha(root / 'profile-matchups.jsonl.gz'),
                  'variantProfiles': sha(root / 'variant-profiles.json'),
                  'originalRankingPredictiveFeatures': sha(RANK / 'runs.jsonl'),
                  'rankingDefinition': sha(DEFINITION),
              },
              'ruleVersion': hashlib.sha256(json.dumps([r['ruleHash'] for r in results], sort_keys=True,
                  separators=(',', ':')).encode()).hexdigest()}
    for name, data in prepared.items():
        chosen = selected[name] != 0
        report['total'][name] = {'rows': len(chosen), 'selected': int(chosen.sum()),
            'wrongOrClose': int(np.sum(selected[name][chosen] != data['actual'][chosen]))
                if name != 'unresolved' else None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    if args.guesses_output:
        by_family = {rule['family']: rule for rule in results}
        args.guesses_output.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(args.guesses_output, 'wt') as stream:
            for row, predicted in zip(sets['unresolved'], selected['unresolved']):
                if not predicted:
                    continue
                family = '|'.join(sorted(lines[h] for h in row['profiles']))
                rule = by_family[family]
                stream.write(json.dumps({'pairKey': row['pairKey'],
                    'profiles': row['profiles'],
                    'predictedOutcome': 'a_win' if predicted > 0 else 'b_win',
                    'family': family, 'benchmarkKeys': rule['benchmarks'],
                    'minimumHpMarginGap': rule['minimumHpMarginGap'],
                    'familyRuleHash': rule['ruleHash'],
                    'ruleVersion': report['ruleVersion'],
                    'status': 'prediction_only_not_an_observed_or_inferred_result'},
                    sort_keys=True) + '\n')
    print(json.dumps(report['total'], indent=2))


if __name__ == '__main__':
    main()
