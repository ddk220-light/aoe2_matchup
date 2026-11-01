#!/usr/bin/env python3
"""Inspect exact calibration failures of the frozen granular HGB predictor.

This repeats only the already published HGB fit. It does not simulate fights
or promote model predictions to matchup evidence.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from evaluate_civ_prediction_coverage import (
    DEFINITION, RANK, features, load, make_edges, make_margin_edges, outcome,
    phase_of, rank_fingerprints, records, sha, stats_matrix,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--damage-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.campaign / 'latest-inference'
    rows = list(records(root / 'profile-matchups.jsonl.gz'))
    variants = load(root / 'variant-profiles.json')
    definition = load(DEFINITION)
    hashes = sorted({v['profileHash'] for v in variants})
    index = {h: i for i, h in enumerate(hashes)}
    lines = {v['profileHash']: v['line'] for v in variants}
    representative = {v['profileHash']: v['key'] for v in reversed(variants)}
    line_labels = {name: i for i, name in enumerate(sorted(set(lines.values())))}
    line_ids = np.asarray([line_labels[lines[h]] for h in hashes])
    standards, rank = rank_fingerprints(variants, definition, index)
    standard_indices = [index[next(v['profileHash'] for v in variants if v['key'] == key)]
                        for key in standards]
    stats = stats_matrix(variants, definition, index)
    damage_source = load(args.damage_source)
    assert damage_source['hashes'] == hashes and damage_source['exceptions'] == 0
    damage = np.asarray(damage_source['damage'], dtype=np.float32)
    observed = [r for r in rows if r['evidenceType'] == 'observed']
    train = [r for r in observed if phase_of(r) <= 20]
    calibration = [r for r in observed if 21 <= phase_of(r) <= 22]
    test = [r for r in observed if 23 <= phase_of(r) <= 24]
    graph = make_edges(train, index)
    margin_graph, margin_pairs = make_margin_edges(train, index,
        root / 'evidence-ledger.jsonl.gz')
    assert margin_pairs == 5190, margin_pairs
    def x(group):
        return features(group, index, rank, stats, line_ids, graph,
                        margin_graph, damage, standard_indices)
    print(f'fitting frozen HGB on {len(train)} observations', flush=True)
    model = HistGradientBoostingClassifier(max_iter=60, max_leaf_nodes=11,
        max_bins=63, learning_rate=0.05, l2_regularization=5, random_state=42)
    model.fit(x(train), np.asarray([outcome(r) for r in train]))
    assert list(model.classes_) == [-1, 0, 1]
    predictions = {}
    for name, group in (('calibration', calibration), ('test', test)):
        probability = model.predict_proba(x(group))
        output = []
        for row, p in zip(group, probability):
            decisive = 1 if p[2] >= p[0] else -1
            output.append({'pairKey': row['pairKey'],
                'units': [representative[h] for h in row['profiles']],
                'family': '|'.join(sorted(lines[h] for h in row['profiles'])),
                'phase': phase_of(row), 'actual': outcome(row),
                'predicted': decisive, 'confidence': float(max(p[0], p[2])),
                'closeProbability': float(p[1])})
        predictions[name] = output
    result = {'kind': 'frozen HGB calibration and held-out predictions; no accepted skips',
        'modelParameters': model.get_params(), 'predictions': predictions,
        'sourceHashes': {'profileMatchups': sha(root / 'profile-matchups.jsonl.gz'),
            'variantProfiles': sha(root / 'variant-profiles.json'),
            'rankingPredictiveFeatures': sha(RANK / 'runs.jsonl'),
            'damageFeatures': sha(args.damage_source)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    for name, group in predictions.items():
        for threshold in (.95, .96, .97, .98):
            bad = [r for r in group if r['confidence'] >= threshold
                   and r['predicted'] != r['actual']]
            print(name, threshold, 'selected', sum(r['confidence'] >= threshold for r in group),
                  'wrongOrClose', len(bad), flush=True)


if __name__ == '__main__':
    main()
