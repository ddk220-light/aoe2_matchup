"""Opponent-specific prediction features rooted only in observed fights.

Shared-C comparisons and near-neighbor transfers are predictive features, not
proofs. Target edges are excluded from their own neighbor evidence.
"""
import collections
import math
import statistics

import numpy as np

from civ_prediction_first_pass import canonical
from evaluate_civ_prediction_coverage import make_margin_edges


def effect_signature(mechanics):
    return canonical({'effects': {k: v for k, v in (mechanics.get('effects') or {}).items()
                                  if k != 'base_accuracy'},
        'mode': mechanics['mode'], 'charge': mechanics.get('charge'),
        'melee_charge': mechanics.get('melee_charge'),
        'ranged': {k: (mechanics.get('ranged') or {}).get(k) for k in (
            'extra_projectile_count', 'pass_through', 'pass_through_count', 'secondary_projectile_count')}})


def observed_roots(rows):
    return [r for r in rows if r['evidenceType'] == 'observed'
            and r['outcome'] in ('a_win', 'b_win')]


def build_witnesses(targets, matrix, variants, definition, damage, ledger_path):
    by_key = {r['pairKey']: r for r in matrix}
    lines = {v['profileHash']: v['line'] for v in variants}
    mechanics = {v['profileHash']: definition['profiles'][v['key']]['mechanics'] for v in variants}
    hashes = sorted(lines)
    index = {h: i for i, h in enumerate(hashes)}
    assert hashes == damage['hashes'] and damage['exceptions'] == 0
    roots = observed_roots(matrix)
    margins, _ = make_margin_edges(roots, index, ledger_path)
    known = collections.defaultdict(list)
    for row in roots:
        for h in row['profiles']:
            known[h].append(row)
    signatures = {h: effect_signature(m) for h, m in mechanics.items()}
    vectors = {}

    def vector(h, opponent):
        key = (h, opponent)
        if key not in vectors:
            m = mechanics[h]
            vectors[key] = np.log(np.array([m['hp'], m['speed_tiles_per_second'], m['reload_seconds'],
                1 + m['attack_range_tiles'], 1 + damage['damage'][index[h]][index[opponent]],
                1 + damage['damage'][index[opponent]][index[h]],
                1 + (m.get('ranged') or {}).get('accuracy_percent', 100), .01 + m['collision_size_tiles']['x']]))
        return vectors[key]

    output = {}
    for target in targets:
        row = by_key[target['pairKey']]
        a, b = row['profiles']
        counts = dict(zip(row['context']['profiles'], row['context']['counts']))
        common, neighbors = [], []
        for c in hashes:
            if c in (a, b) or lines[c] not in (lines[a], lines[b]):
                continue
            am, bm = margins[index[a], index[c]], margins[index[b], index[c]]
            if not math.isfinite(am) or not math.isfinite(bm):
                continue
            common.append({'profileC': c, 'lineC': lines[c], 'aMargin': float(am), 'bMargin': float(bm),
                'gap': float(am - bm), 'aPairKey': '|'.join(sorted((a, c))),
                'bPairKey': '|'.join(sorted((b, c)))})
        for h, opponent in ((a, b), (b, a)):
            v = vector(h, opponent)
            for anchor in known[opponent]:
                if (anchor['pairKey'] == row['pairKey']
                        or anchor['context']['scenarioHash'] != row['context']['scenarioHash']
                        or anchor['context']['profiles'].index(opponent)
                            != row['context']['profiles'].index(opponent)):
                    continue
                replacement = next(x for x in anchor['profiles'] if x != opponent)
                if (lines[replacement] != lines[h]
                        or mechanics[replacement]['unit_class'] != mechanics[h]['unit_class']
                        or signatures[replacement] != signatures[h]):
                    continue
                anchor_counts = dict(zip(anchor['context']['profiles'], anchor['context']['counts']))
                if anchor_counts[opponent] != counts[opponent] or abs(anchor_counts[replacement] - counts[h]) > 1:
                    continue
                distance = float(np.sqrt(np.mean((v - vector(replacement, opponent)) ** 2)))
                if distance > .15:
                    continue
                winner = anchor['profiles'][0 if anchor['outcome'] == 'a_win' else 1]
                projected = opponent if winner == opponent else h
                neighbors.append({'anchorPairKey': anchor['pairKey'], 'replacementProfile': replacement,
                    'replaces': h, 'fixedOpponent': opponent, 'distance': distance,
                    'predictedOutcome': 'a_win' if projected == a else 'b_win',
                    'anchorOutcome': anchor['outcome'], 'anchorCounts': anchor['context']['counts']})
        median = statistics.median(c['gap'] for c in common) if common else 0
        output[row['pairKey']] = {'common': common, 'medianGap': median,
            'agreement': sum(c['gap'] * median > 0 for c in common) / len(common) if common else 0,
            'neighbors': sorted(neighbors, key=lambda n: (n['distance'], n['anchorPairKey']))[:5]}
    anchors = [{k: r[k] for k in ('pairKey', 'profiles', 'outcome', 'context', 'sourceRunIds')}
               for r in roots]
    return output, anchors


def witness_directions(witness):
    methods = {}
    if (len(witness.get('common', [])) >= 2 and abs(witness.get('medianGap', 0)) >= .1
            and witness.get('agreement', 0) >= 2 / 3):
        methods['observed_common_opponents'] = {
            'predictedOutcome': 'a_win' if witness['medianGap'] > 0 else 'b_win',
            'medianHpMarginGap': witness['medianGap'], 'agreement': witness['agreement'],
            'opponentCount': len(witness['common'])}
    neighbors = witness.get('neighbors', [])
    if len(neighbors) >= 2 and len({n['predictedOutcome'] for n in neighbors}) == 1:
        methods['observed_opponent_neighbors'] = {
            'predictedOutcome': neighbors[0]['predictedOutcome'],
            'anchorPairKeys': [n['anchorPairKey'] for n in neighbors],
            'maximumDistance': max(n['distance'] for n in neighbors)}
    return methods
