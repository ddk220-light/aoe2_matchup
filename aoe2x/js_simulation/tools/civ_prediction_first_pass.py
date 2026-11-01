#!/usr/bin/env python3
"""Versioned, explicitly provisional table and a small targeted validation queue.

No prediction is combat evidence. The source matrix and run journals are read
only. All predictions are frozen before their prospective test phase.
"""
import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path

from civ_reviewed_phase import load_reviewed_phase

VERSION = 'prediction-first-pass-v2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def load(path):
    return json.loads(path.read_bytes())


def read_rows(path):
    return [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b'\n')


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as out:
        for row in rows:
            out.write(canonical(row) + b'\n')


def direction(scores):
    return 'a_win' if scores['aWin'] > scores['bWin'] else 'b_win'


def choose(model, old, cavalry_guard=True):
    """A transparent forecast policy, not a calibrated probability or proof."""
    methods = dict(old.get('supportingMethods', {})) if old else {}
    if not cavalry_guard:
        methods.pop('two_benchmark_rule', None)
    h, e = model['histGradientBoostingProbabilities'], model['extraTreesProbabilities']
    hc, ec = max(h['aWin'], h['bWin']), max(e['aWin'], e['bWin'])
    if (direction(h) == direction(e) and (hc + ec) / 2 >= .775
            and min(hc, ec) >= .6 and max(h['close'], e['close']) <= .15):
        methods['model_agreement'] = {'predictedOutcome': direction(h),
            'meanModelScore': (hc + ec) / 2,
            'explanation': 'Two frozen models agree; mean score >=0.775, each >=0.60, close score <=0.15. Scores are not win probabilities.'}
    if not methods or len({x['predictedOutcome'] for x in methods.values()}) != 1:
        return None
    return {'predictedOutcome': next(iter(methods.values()))['predictedOutcome'],
            'supportingMethods': methods,
            'tier': 'stronger_support' if any(k != 'model_agreement' for k in methods) else 'broader_agreement'}


def choose_extended(model, old, witness, cavalry_guard=True):
    """Extend coverage without a percentage quota; retain every support tier."""
    from civ_prediction_witnesses import witness_directions
    base = choose(model, old, cavalry_guard)
    corroboration = witness_directions(witness)
    h, e = model['histGradientBoostingProbabilities'], model['extraTreesProbabilities']
    if base is not None:
        base['conflictingWitnessMethods'] = [name for name, item in corroboration.items()
            if item['predictedOutcome'] != base['predictedOutcome']]
        return base
    if (direction(h) == direction(e) and max(h['aWin'], h['bWin']) > h['close']
            and max(e['aWin'], e['bWin']) > e['close']):
        predicted = direction(h)
        return {'predictedOutcome': predicted, 'tier': 'weak_model_agreement',
            'supportingMethods': {'weak_model_agreement': {'predictedOutcome': predicted,
                'meanModelScore': (max(h['aWin'], h['bWin']) + max(e['aWin'], e['bWin'])) / 2,
                'explanation': 'Both models favor this winner over the other winner and close class; weaker forecast, not a validated result.'}},
            'conflictingWitnessMethods': [name for name, item in corroboration.items()
                if item['predictedOutcome'] != predicted]}
    directions = {m['predictedOutcome'] for m in corroboration.values()}
    if len(directions) == 1:
        return {'predictedOutcome': directions.pop(), 'tier': 'opponent_specific_forecast',
            'supportingMethods': corroboration, 'conflictingWitnessMethods': []}
    if (not directions and h['close'] > max(h['aWin'], h['bWin'])
            and e['close'] > max(e['aWin'], e['bWin'])):
        return {'predictedOutcome': 'close_uncertain', 'tier': 'predicted_close',
            'supportingMethods': {'close_agreement': {'predictedOutcome': 'close_uncertain',
                'explanation': 'Both models favor seed disagreement/close outcomes; unvalidated close forecast.'}},
            'conflictingWitnessMethods': []}
    return None


def phase_of(row):
    phases = [int(s.rsplit('/', 1)[1].split('.')[0]) for s in row.get('sourceRunIds', [])
              if '/adaptive/runs/' in s]
    return max(phases, default=0)


def context_key(row, pred, mechanics, lines):
    # This is a sampling/refinement stratum, never a license to transfer a win.
    ordered = sorted(row['profiles'], key=lambda h: (lines[h], mechanics[h]['unit_class'], h))
    return {'family': pred['family'], 'tier': pred['tier'],
        'scenarioHash': row['context']['scenarioHash'],
        'subtypes': [{'line': lines[h], 'class': mechanics[h]['unit_class'],
            'mode': mechanics[h]['mode'],
            'effectKeys': sorted((mechanics[h].get('effects') or {}).keys()),
            'armorClasses': sorted((mechanics[h].get('armor_classes') or {}).keys())}
            for h in ordered]}


def freeze(args):
    # Import the old-engine ranking HP values only as predictive features.
    from evaluate_civ_prediction_coverage import rank_fingerprints, DEFINITION
    _, variants, provenance = load_reviewed_phase(args.campaign, args.phase)
    root = args.campaign / 'latest-inference'
    matrix = {r['pairKey']: r for r in read_rows(root / 'profile-matchups.jsonl.gz')}
    definition = load(DEFINITION)
    hashes = sorted({v['profileHash'] for v in variants})
    index = {h: i for i, h in enumerate(hashes)}
    standards, rank = rank_fingerprints(variants, definition, index)
    lines = {v['profileHash']: v['line'] for v in variants}
    mechanics = {v['profileHash']: definition['profiles'][v['key']]['mechanics'] for v in variants}
    old = {r['pairKey']: r for r in read_rows(args.audit / 'fifty-percent-v2-candidate-guesses.jsonl.gz')}
    source = args.audit / 'granular-model-predictions.jsonl.gz'
    models = read_rows(source)
    from civ_prediction_witnesses import build_witnesses
    ledger_path = root / 'evidence-ledger.jsonl.gz'
    expected_ledger = next(r['sha256'] for r in load(root/'manifest.json')['outputs']
                           if r['file'] == ledger_path.name)
    assert sha(ledger_path.read_bytes()) == expected_ledger, 'witness ledger source hash mismatch'
    witnesses, anchors = build_witnesses(models, list(matrix.values()), variants, definition,
                                         load(args.audit/'static-damage.json'), ledger_path)
    predictions, revisions = [], []
    for model in models:
        key = model['pairKey']
        row = matrix[key]
        a, b = row['profiles']
        shared = [{'unitC': name, 'aHpMargin': float(rank[index[a], i]),
                   'bHpMargin': float(rank[index[b], i])} for i, name in enumerate(standards)
                  if math.isfinite(rank[index[a], i]) and math.isfinite(rank[index[b], i])]
        guard = True
        prior = old.get(key)
        if model['family'] == 'cav_archer|light_cav' and prior and 'two_benchmark_rule' in prior['supportingMethods']:
            melee = [c for c in shared if c['unitC'] in ('Spanish|champion', 'Turks|paladin')]
            sign = 1 if prior['predictedOutcome'] == 'a_win' else -1
            guard = bool(melee) and all(sign * (c['aHpMargin'] - c['bHpMargin']) >= .1 for c in melee)
            if not guard:
                revisions.append({'pairKey': key, 'reason': 'ranged benchmarks conflict with or lack confirming shared melee benchmarks', 'sharedC': shared})
        chosen = choose_extended(model, prior, witnesses[key], guard)
        if chosen is None:
            continue
        pred = {'pairKey': key, 'profiles': row['profiles'], 'family': model['family'],
                **chosen, 'status': 'predicted_unvalidated', 'verified': False,
                'contextHash': sha(canonical(row['context'])), 'context': row['context'],
                'rankingCommonC': shared, 'sourcePredictionHash': sha(canonical(model)),
                'opponentWitnesses': witnesses[key],
                'modelScores': {'hgb': model['histGradientBoostingProbabilities'],
                                'extraTrees': model['extraTreesProbabilities']}}
        stratum = context_key(row, pred, mechanics, lines)
        pred['stratum'] = stratum
        pred['ruleHash'] = sha(canonical({'policy': VERSION, 'context': stratum}))
        predictions.append(pred)
    if (args.output / 'manifest.json').exists():
        raise ValueError('freeze output already exists; use a separately versioned directory')
    write_rows(args.output / 'predictions.jsonl.gz', sorted(predictions, key=lambda r: r['pairKey']))
    write_json(args.output / 'revisions.json', revisions)
    (args.output / 'generator-source.py').write_bytes(Path(__file__).read_bytes())
    witness_source = Path(__file__).with_name('civ_prediction_witnesses.py')
    (args.output / 'witness-source.py').write_bytes(witness_source.read_bytes())
    write_rows(args.output / 'observed-witness-anchors.jsonl.gz', anchors)
    manifest = {'policyVersion': VERSION, 'introducedAfterPhase': args.first_untouched_phase - 1,
        'reviewedThroughPhase': args.phase, 'sourceReview': provenance,
        'predictionsSha256': sha((args.output / 'predictions.jsonl.gz').read_bytes()),
        'generatorSha256': sha(Path(__file__).read_bytes()),
        'witnessGeneratorSha256': sha(witness_source.read_bytes()),
        'observedWitnessAnchorsSha256': sha((args.output/'observed-witness-anchors.jsonl.gz').read_bytes()),
        'witnessLedgerSha256': expected_ledger,
        'staticDamageSha256': sha((args.audit/'static-damage.json').read_bytes()),
        'coveragePolicy': 'No percentage ceiling; preserve stronger calls, add explicitly weak model agreement, resolve disagreements with observed common opponents or close same-opponent neighbors, abstain on conflicting witness directions.',
        'modelPredictionsSha256': sha(source.read_bytes()),
        'parentPoolSha256': sha((args.audit / 'fifty-percent-v2-candidate-guesses.jsonl.gz').read_bytes()),
        'status': 'User-approved provisional first pass; deferred predictions are not validated or simulated results',
        'physicsBasis': 'Frozen V3; V2 physics compatibility is still pending. No V2 outcomes are mixed in.',
        'rankingUsage': 'Old-engine HP margins are features only, never measurements for this dataset',
        'validationSamplePerPhase': 32, 'predictionCount': len(predictions)}
    write_json(args.output / 'manifest.json', manifest)
    print(json.dumps({'frozenPredictions': len(predictions), 'firstUntouchedPhase': args.first_untouched_phase}))


def compare(predictions, observed, introduced):
    tests, failures = [], []
    for key, pred in predictions.items():
        row = observed.get(key)
        if not row or row['evidenceType'] != 'observed':
            continue
        if pred['contextHash'] != sha(canonical(row['context'])):
            continue
        phase = phase_of(row)
        test = {'pairKey': key, 'ruleHash': pred['ruleHash'], 'family': pred['family'],
                'phase': phase, 'independent': phase > introduced,
                'prediction': pred['predictedOutcome'], 'actual': row['outcome'],
                'correct': pred['predictedOutcome'] == row['outcome'],
                'sourceRunIds': row['sourceRunIds'], 'context': row['context'],
                'supportingMethods': pred['supportingMethods'], 'rankingCommonC': pred['rankingCommonC']}
        test['tier'] = pred.get('tier')
        test['opponentWitnesses'] = pred.get('opponentWitnesses', {})
        tests.append(test)
        if not test['correct']:
            failures.append(test)
    return tests, failures


def select_probes(candidates, tests, limit=32):
    """Half representative hash samples, half boundary/diversity probes."""
    pools = collections.defaultdict(list)
    history = collections.Counter(t['ruleHash'] for t in tests if t['independent'])
    failures = collections.Counter(t['ruleHash'] for t in tests if t['independent'] and not t['correct'])
    for item in candidates:
        pools[item['ruleHash']].append(item)
    used, profiles, selected = set(), set(), []
    for position in range(min(limit, len(candidates))):
        available = {k: [r for r in rows if r['pairKey'] not in used] for k, rows in pools.items()}
        available = {k: rows for k, rows in available.items() if rows}
        if not available:
            break
        rule = max(available, key=lambda k: (sum(r['aliases'] for r in available[k])
             * (2 if failures[k] else 1) / (1 + history[k])
             / max(1, sum(r['estimatedSeconds'] for r in available[k]) / len(available[k])), k))
        items = available[rule]
        if position % 2 == 0:
            chosen = min(items, key=lambda r: sha((VERSION + r['pairKey']).encode()))
            purpose = 'representative_sample'
        else:
            chosen = max(items, key=lambda r: (
                len(set(r['profiles']) - profiles),
                -max(r['modelScores']['hgb']['aWin'], r['modelScores']['hgb']['bWin']), r['pairKey']))
            purpose = 'boundary_and_new_profiles'
        used.add(chosen['pairKey']); profiles.update(chosen['profiles']); history[rule] += 1
        selected.append({'pairKey': chosen['pairKey'], 'family': chosen['family'],
                         'kind': 'prediction_validation_probe', 'ruleHash': rule,
                         'purpose': purpose, 'predictedOutcome': chosen['predictedOutcome']})
    return selected


def frozen_forecast_context(pred, row):
    """Keep an approved forecast's physical setup when derived suggestions flip.

    This does not transfer a winner to a reversed fight. The exported forecast
    retains its original context; only an exact-context observation can test it.
    Actual count/cost/settings changes still abstain.
    """
    context = pred.get('context', row['context'])
    if pred['contextHash'] != sha(canonical(context)):
        return None
    current = row['context']
    if context == current:
        return context
    if (context.get('family') == current.get('family') and
            context.get('scenarioHash') != current.get('scenarioHash')):
        return None
    reversed_context = dict(context)
    for key in ('profiles', 'counts', 'weightedCosts'):
        if key in context:
            reversed_context[key] = list(reversed(context[key]))
    for key in ('family', 'scenarioHash'):
        reversed_context[key] = current.get(key)
    if reversed_context != current:
        return None
    families = {context.get('family'), current.get('family')}
    if len(families) > 1 and families != {'melee_vs_ranged', 'ranged_vs_melee'}:
        return None
    return context


def plan(campaign, policy, phase, output, forbidden=()):
    _, variants, provenance = load_reviewed_phase(campaign, phase)
    root = campaign / 'latest-inference'
    manifest = load(policy / 'manifest.json')
    frozen = (policy / 'predictions.jsonl.gz').read_bytes()
    assert sha(frozen) == manifest['predictionsSha256'], 'prediction source hash mismatch'
    if manifest.get('observedWitnessAnchorsSha256'):
        assert sha((policy/'observed-witness-anchors.jsonl.gz').read_bytes()) == manifest[
            'observedWitnessAnchorsSha256'], 'observed witness source hash mismatch'
    assert manifest['policyVersion'] == VERSION
    matrix = read_rows(root / 'profile-matchups.jsonl.gz')
    by_key = {r['pairKey']: r for r in matrix}
    predictions = {r['pairKey']: r for r in map(json.loads, gzip.decompress(frozen).splitlines())}
    assert len(predictions) == manifest['predictionCount']
    inventory = {}
    inventory_path = campaign / 'adaptive/inventory.jsonl.gz'
    if inventory_path.exists():
        adaptive_manifest = load(campaign / 'adaptive/manifest.json')
        assert sha(inventory_path.read_bytes()) == adaptive_manifest['matchupInventory']['sha256']
        inventory = {r['pairKey']: r for r in read_rows(inventory_path)}
    tests, failures = compare(predictions, by_key, manifest['introducedAfterPhase'])
    # First-pass guesses remain explicitly unvalidated even after a related
    # counterexample. Mark the precise stratum contested and prioritize its
    # checks rather than silently deleting the whole family of forecasts.
    contested = {t['ruleHash'] for t in failures if t['independent']}
    blocked = set(load(campaign / 'adaptive/state.json')['blockedPairs'])
    forbidden = set(forbidden) | blocked
    costs = collections.defaultdict(list)
    for p in (campaign / 'adaptive/runs').glob('*.jsonl'):
        if int(p.stem) > phase:
            continue
        for raw in p.read_bytes().splitlines():
            run = json.loads(raw)
            costs[run['scenarioHash']].append(run['wallSeconds'])
    import statistics
    medians = {k: statistics.median(v) * 3 for k, v in costs.items()}
    eligible, overlay = [], []
    for row in matrix:
        pred = predictions.get(row['pairKey'])
        forecast_context = frozen_forecast_context(pred, row) if pred else None
        matches = forecast_context is not None
        guessed = row['outcome'] == 'unresolved' and matches and row['pairKey'] not in blocked
        result = dict(row, sourceOutcome=row['outcome'], sourceEvidenceType=row['evidenceType'])
        if guessed:
            result.update(outcome=pred['predictedOutcome'], evidenceType='predicted_unvalidated',
                context=forecast_context, sourceContext=row['context'],
                predictionContextPreserved=forecast_context != row['context'],
                contextPolicy='preserve-approved-forecast-context-v1',
                needsSim=False, needsValidation=True, verified=False,
                predictionPolicy=VERSION, predictionRuleHash=pred['ruleHash'],
                predictionTier=pred['tier'], predictionSourceSha256=manifest['predictionsSha256'],
                predictionConflicts=pred.get('conflictingWitnessMethods', []),
                predictionContested=pred['ruleHash'] in contested,
                explanation=('Low-support directional lean; either side may win. This is not a measured result.'
                    if pred['tier']=='weak_model_agreement' else
                    'Unvalidated forecast from frozen ranking/common-opponent/model features; requires later validation.'),
                sourceReasonCodes=row.get('reasonCodes', []), reasonCodes=['unvalidated_prediction'])
            job = inventory.get(row['pairKey'])
            probe_matches = (forecast_context == row['context'] if job is None else
                forecast_context['profiles'] == job['profileHashes'] and
                forecast_context['counts'] == job['counts'] and
                forecast_context['scenarioHash'] == job['scenarioHash'])
            if row['pairKey'] not in forbidden and probe_matches:
                eligible.append(dict(pred, aliases=row['aliases'],
                    estimatedSeconds=medians.get(row['context']['scenarioHash'], 60)))
        else:
            result['needsValidation'] = False
        if pred:
            result['originalPrediction'] = {'outcome': pred['predictedOutcome'],
                'contextHash': pred['contextHash'], 'ruleHash': pred['ruleHash'],
                'sourceSha256': manifest['predictionsSha256'],
                'validationStatus': ('different_context_not_validation'
                    if row['evidenceType'] == 'observed' and pred['contextHash'] != sha(canonical(row['context']))
                    else 'confirmed_by_observation' if row['evidenceType'] == 'observed' and row['outcome'] == pred['predictedOutcome']
                    else 'observed_close' if row['evidenceType'] == 'observed' and row['outcome'] == 'close_uncertain'
                    else 'wrong_winner' if row['evidenceType'] == 'observed' else 'not_observed')}
        overlay.append(result)
    # The first pass ends after the non-predicted gaps, not after validating
    # every deferred prediction. Stop sampling when only blocked recovery
    # cases remain, and scale down the sample in the final partial phase.
    direct_gaps = [r for r in overlay if r['outcome'] == 'unresolved']
    runnable_gaps = [r for r in direct_gaps if r['pairKey'] not in blocked]
    sample_budget = min(manifest['validationSamplePerPhase'],
                        (len(runnable_gaps) + 6) // 7)
    selected = select_probes(eligible, tests, sample_budget)
    probe_keys = {r['pairKey'] for r in selected}
    deferred = [r['pairKey'] for r in overlay if r['evidenceType'] == 'predicted_unvalidated'
                and r['pairKey'] not in probe_keys]
    counts = collections.Counter(r['evidenceType'] for r in overlay)
    source_unresolved = sum(r['outcome'] == 'unresolved' for r in matrix)
    predicted = counts['predicted_unvalidated']
    summary = {'policyVersion': VERSION, 'sourcePhase': phase,
        'status': 'provisional first pass; not a validated final dataset',
        'profiles': len(matrix), 'displayedCells': sum(r['aliases'] for r in matrix),
        'sourceUnresolved': source_unresolved, 'predictedPairs': predicted,
        'predictedCells': sum(r['aliases'] for r in overlay if r['evidenceType']=='predicted_unvalidated'),
        'predictionCoverageOfRemaining': predicted / source_unresolved if source_unresolved else 0,
        'remainingNeedsDirectResult': source_unresolved - predicted,
        'runnableDirectGaps': len(runnable_gaps),
        'selectionVersion': 'first-pass-completion-v1',
        'predictionSampleBudget': sample_budget,
        'completionState': ('running_gaps' if runnable_gaps else
            'waiting_blocked_recovery' if direct_gaps else 'ready_for_final_checks'),
        'blockedPairs': len(blocked), 'selectedValidationSamples': len(selected),
        'observedPairs': counts['observed'], 'inferredPairs': counts['inferred'],
        'predictedByTier': dict(collections.Counter(r['predictionTier'] for r in overlay
            if r['evidenceType']=='predicted_unvalidated')),
        'predictedWinnerPairs': sum(r['evidenceType']=='predicted_unvalidated'
            and r['outcome'] in ('a_win','b_win') for r in overlay),
        'predictedClosePairs': sum(r['evidenceType']=='predicted_unvalidated'
            and r['outcome']=='close_uncertain' for r in overlay),
        'contestedPredictions': sum(r.get('predictionContested', False) for r in overlay),
        'preservedForecastContexts': sum(r.get('predictionContextPreserved', False) for r in overlay),
        'screenByTier': {tier: {'checked':sum(t.get('tier')==tier and not t['independent'] for t in tests),
            'wrongOrClose':sum(t.get('tier')==tier and not t['independent'] and not t['correct'] for t in tests)}
            for tier in sorted({t.get('tier') for t in tests if t.get('tier')})},
        'screenedPredictions': sum(not t['independent'] for t in tests),
        'screenWrongOrClose': sum(not t['independent'] and not t['correct'] for t in tests),
        'prospectivePredictions': sum(t['independent'] for t in tests),
        'prospectiveWrongOrClose': sum(t['independent'] and not t['correct'] for t in tests),
        'contestedRuleHashes': sorted(contested), 'sourceReview': provenance,
        'predictionManifestSha256': sha((policy / 'manifest.json').read_bytes()),
        'plannerSha256': sha(Path(__file__).read_bytes())}
    write_rows(output / 'profile-table.jsonl.gz', overlay)
    overlay_by_key = {r['pairKey']: r for r in overlay}
    cell_path = root / 'civ-matchups.jsonl.gz'
    cells_bytes = cell_path.read_bytes()
    source_manifest = load(root / 'manifest.json')
    expected = next(x['sha256'] for x in source_manifest['outputs'] if x['file']==cell_path.name)
    assert sha(cells_bytes) == expected, 'displayed cells source hash mismatch'
    cells = [json.loads(raw) for raw in gzip.decompress(cells_bytes).splitlines()]
    profile_for_variant = {v['key']: v['profileHash'] for v in variants}
    # Cells retain their source orientation; the pair-level table is canonical.
    for cell in cells:
        pair = overlay_by_key[cell['pairKey']]
        if pair['evidenceType'] == 'predicted_unvalidated':
            source_outcome = cell['outcome']
            owner_a = profile_for_variant[cell['civA'] + '|' + cell['unitA']]
            winner = (pair['profiles'][0 if pair['outcome']=='a_win' else 1]
                      if pair['outcome'] in ('a_win','b_win') else None)
            cell.update(outcome=('a_win' if owner_a==winner else 'b_win') if winner else 'close_uncertain',
                context=pair['context'], sourceContext=pair['sourceContext'],
                sourceOutcome=source_outcome, sourceEvidenceType=cell['evidenceType'],
                evidenceType='predicted_unvalidated', needsSim=False,
                needsValidation=True, verified=False, explanation=pair['explanation'],
                prediction={'canonicalOutcome': pair['outcome'], 'canonicalProfiles': pair['profiles'],
                    'status': 'predicted_unvalidated', 'verified': False,
                    'tier': pair['predictionTier'], 'conflicts': pair.get('predictionConflicts', []),
                    'contested': pair.get('predictionContested', False),
                    'ruleHash': pair['predictionRuleHash']})
        else:
            cell['prediction'] = None
        cell['originalPrediction'] = pair.get('originalPrediction')
    write_rows(output / 'civilization-table.jsonl.gz', cells)
    write_json(output / 'summary.json', summary)
    write_json(output / 'validation.json', {'tests': tests, 'failures': failures,
        'warning': 'Screening results informed the policy; only post-introduction phases are prospective.'})
    write_json(output / 'selection.json', {'selected': selected, 'deferredPredictionKeys': deferred})
    write_json(output / 'manifest.json', {'policyVersion': VERSION, 'sourcePhase': phase,
        'files': {name:sha((output/name).read_bytes()) for name in ['profile-table.jsonl.gz',
          'civilization-table.jsonl.gz', 'summary.json', 'validation.json', 'selection.json']}})
    return {'selected': selected, 'deferredPredictionKeys': deferred, 'summary': summary,
            'manifestSha256': sha((output / 'manifest.json').read_bytes())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['freeze', 'plan'])
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--phase', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--first-untouched-phase', type=int)
    args = parser.parse_args()
    if args.mode == 'freeze':
        freeze(args)
    else:
        result = plan(args.campaign, args.policy, args.phase, args.output)
        print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
