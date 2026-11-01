#!/usr/bin/env python3
"""Combine provisional common-C and granular-model winner guesses.

This writes a prediction artifact only. It cannot mark an observed result,
verify a rule, or tell the campaign runner to skip a fight.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from evaluate_civ_prediction_coverage import DEFINITION, RANK, load, rank_fingerprints


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with gzip.open(path, 'rt') as source:
        yield from map(json.loads, source)


def hgb_supported(row, index, rank, lines, mechanics):
    family = row['family']
    if 'scorpion' in family or family == 'archer|gunpowder':
        return False
    a, b = row['profiles']
    if family == 'militia|militia':
        return bool(np.any(np.isfinite(rank[index[a]]) & np.isfinite(rank[index[b]])))
    if family == 'archer|skirmisher':
        archer = next(h for h in (a, b) if lines[h] == 'archer')
        unit = mechanics[archer]
        if (unit['armor_classes'].get('3', 0) >= 10
                and unit['speed_tiles_per_second'] >= 1.1):
            return False
    if family == 'archer|light_cav':
        cavalry = next(h for h in (a, b) if lines[h] == 'light_cav')
        if mechanics[cavalry]['hp'] >= 95:
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-predictions', type=Path, required=True)
    parser.add_argument('--benchmark-predictions', type=Path, required=True)
    parser.add_argument('--variant-profiles', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    variants = load(args.variant_profiles)
    definition = load(DEFINITION)
    hashes = sorted({v['profileHash'] for v in variants})
    index = {h: i for i, h in enumerate(hashes)}
    lines = {v['profileHash']: v['line'] for v in variants}
    mechanics = {v['profileHash']: definition['profiles'][v['key']]['mechanics']
                 for v in variants}
    _, rank = rank_fingerprints(variants, definition, index)
    benchmarks = {r['pairKey']: r for r in rows(args.benchmark_predictions)}
    counts = {'modelRows': 0, 'selected': 0, 'conflicts': 0,
              'selectedByMethod': {'hist_gradient_boosting': 0,
                                   'extra_trees': 0, 'two_benchmark_rule': 0}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as out:
        for row in rows(args.model_predictions):
            counts['modelRows'] += 1
            key, family = row['pairKey'], row['family']
            methods = {}
            h = row['histGradientBoostingProbabilities']
            h_conf = max(h['aWin'], h['bWin'])
            if h_conf >= .95 and hgb_supported(row, index, rank, lines, mechanics):
                methods['hist_gradient_boosting'] = {
                    'predictedOutcome': 'a_win' if h['aWin'] >= h['bWin'] else 'b_win',
                    'confidence': h_conf}
            e = row['extraTreesProbabilities']
            e_conf = max(e['aWin'], e['bWin'])
            if e_conf >= .95:
                methods['extra_trees'] = {
                    'predictedOutcome': 'a_win' if e['aWin'] >= e['bWin'] else 'b_win',
                    'confidence': e_conf}
            if key in benchmarks:
                b = benchmarks[key]
                methods['two_benchmark_rule'] = {
                    'predictedOutcome': b['predictedOutcome'],
                    'familyRuleHash': b['familyRuleHash'],
                    'benchmarkKeys': b['benchmarkKeys'],
                    'minimumHpMarginGap': b['minimumHpMarginGap']}
            if not methods:
                continue
            directions = {v['predictedOutcome'] for v in methods.values()}
            if len(directions) != 1:
                counts['conflicts'] += 1
                continue
            counts['selected'] += 1
            for method in methods:
                counts['selectedByMethod'][method] += 1
            out.write((json.dumps({
                'pairKey': key, 'profiles': row['profiles'], 'family': family,
                'predictedOutcome': directions.pop(), 'supportingMethods': methods,
                'status': 'provisional_prediction_not_observed_or_validated_inference',
            }, sort_keys=True) + '\n').encode())
    summary = {'kind': 'provisional 50-percent candidate pool; not a skip list',
               'policyVersion': 'granular-candidate-v2',
               'policy': 'HGB>=0.95 with Scorpion and archer-gunpowder abstention, no-common-C militia mirror abstention, fast high-pierce-armor archer vs skirmisher abstention, and >=95-HP light cavalry vs archer abstention; ExtraTrees>=0.95; family two-benchmark rule; abstain on conflicting winners',
               'counts': counts,
               'coverage': counts['selected'] / counts['modelRows'],
               'validationLimit': 'The context guards were chosen after inspecting phase-21/22 calibration and later test/screen errors. The zero-error recount is therefore a screen. Phase-26 is the first untouched prospective check. Compatible V2 replay is incomplete. Do not skip fights from this file.',
               'sourceHashes': {'modelPredictions': sha(args.model_predictions),
                                'benchmarkPredictions': sha(args.benchmark_predictions),
                                'variantProfiles': sha(args.variant_profiles),
                                'rankingDefinition': sha(DEFINITION),
                                'rankingPredictiveFeatures': sha(RANK / 'runs.jsonl'),
                                'candidatePool': sha(args.output)}}
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'selected': counts['selected'], 'total': counts['modelRows'],
                      'coverage': summary['coverage'], 'conflicts': counts['conflicts']}))


if __name__ == '__main__':
    main()
