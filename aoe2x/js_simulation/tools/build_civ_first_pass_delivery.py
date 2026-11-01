#!/usr/bin/env python3
"""Package provisional V3 predictions with a separate repaired-engine ledger.

Repaired-engine observations are never called V3 observations. Their projection
into this first-pass table is an explicitly unvalidated prediction, linked to a
complete same-context repaired seed set and an exact replay review.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
from civ_prediction_first_pass import read_rows, write_rows, write_json, canonical, sha

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECOVERY = Path('/workspace/aoe2_civ_first_pass_parallel/aoe2x/js_simulation/calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01')


def read_json(path):
    return json.loads(path.read_bytes())


def validate_recovery_review(review, job, records):
    assert review['pairKey'] == job['pairKey']
    assert review['physicsVersion'] == 'collision-repair-v2'
    assert review['exactReplay']['passed'] is True
    assert review['inputHash'] == sha(canonical(review['seedReferences']))
    by_seed = {r['seed']: r for r in records}
    assert len(by_seed) == len(records)
    assert {0, 1, 2}.issubset(by_seed), 'missing initial repaired seed'
    if len({by_seed[i]['outcome'] for i in [0, 1, 2]}) > 1:
        assert set(range(10)).issubset(by_seed), 'missing disagreement repaired seed'
    assert review['exactReplay']['seed'] in by_seed
    for r in records:
        assert r['matchupId'] == job['id'] and r['pairKey'] == job['pairKey']
        assert r['counts'] == job['counts'] and r['profileHashes'] == job['profileHashes']
        assert r['scenarioHash'] == job['scenarioHash']
        assert r['outcome'] in ('win', 'loss', 'draw') and not r.get('error')
    outcomes = {r['outcome'] for r in records}
    expected = next(iter(outcomes)) if len(outcomes) == 1 and 'draw' not in outcomes else 'close_uncertain'
    assert review['outcome'] == expected, 'recovery review winner differs from saved seeds'
    return expected


def project(row, job, review):
    assert row['outcome'] == 'unresolved', 'do not overwrite an existing measurement or prediction'
    assert sorted(row['profiles']) == sorted(job['profileHashes'])
    outcome = review['outcome']
    winner = job['profileHashes'][0 if outcome == 'win' else 1] if outcome in ('win', 'loss') else None
    canonical_outcome = ('a_win' if winner == row['profiles'][0] else 'b_win') if winner else 'close_uncertain'
    result = dict(row, sourceOutcome=row['outcome'], sourceEvidenceType=row['evidenceType'],
        sourceContext=row.get('context'), outcome=canonical_outcome,
        evidenceType='predicted_unvalidated', verified=False, needsSim=False, needsValidation=True,
        predictionTier='repaired_engine_projection', targetPhysicsVersion='frozen-v3',
        context={'profiles':job['profileHashes'], 'counts':job['counts'],
            **{k:job[k] for k in ['weightedCosts','scenarioHash','family','engineFamily','policy']}},
        explanation='Unvalidated V3 projection of a completed repaired-engine fight. The supporting measurements use collision-repair V2 and are stored separately.',
        reasonCodes=['unvalidated_prediction','different_engine_projection'],
        recoveryProjection={'status':'predicted_unvalidated', 'verified':False,
            'measurementPhysicsVersion':'collision-repair-v2', 'targetPhysicsVersion':'frozen-v3',
            'ruleVersion':'first-pass-repaired-engine-projection-v1',
            'reviewSha256':sha(canonical(review)), 'seedReferences':review['seedReferences'],
            'exactRepairedReplay':review['exactReplay'],
            'validationStatus':'not_validated_under_target_engine'})
    return result


def build(campaign, prediction_dir, recovery, output, require_complete=False):
    source_manifest = read_json(prediction_dir/'manifest.json')
    for name, checksum in source_manifest['files'].items():
        assert sha((prediction_dir/name).read_bytes()) == checksum, f'prediction archive changed: {name}'
    source_summary = read_json(prediction_dir/'summary.json')
    phase = source_summary['sourcePhase']
    review_path = campaign/'adaptive/phases'/f'{phase:03d}-review.json'
    assert sha(review_path.read_bytes()) == source_summary['sourceReview']['phaseReview']
    variants_path = campaign/'latest-inference/variant-profiles.json'
    assert sha(variants_path.read_bytes()) == source_summary['sourceReview']['variantProfiles']
    variants = read_json(variants_path)
    variant_profiles = {v['key']:v['profileHash'] for v in variants}
    profiles = read_rows(prediction_dir/'profile-table.jsonl.gz')
    cells = read_rows(prediction_dir/'civilization-table.jsonl.gz')
    by_key = {r['pairKey']:r for r in profiles}
    assert len(by_key) == len(profiles) == 68916
    assert len(variants) == 555 and len(cells) == 151223
    assert len({tuple(sorted([r['civA'],r['civB']])) for r in cells}) == 1540
    assert len({(r['civA'],r['unitA'],r['civB'],r['unitB']) for r in cells}) == len(cells)
    ledger, projections, recovery_meta = {}, {}, None
    if (recovery/'manifest.json').exists() and (recovery/'pair-reviews.jsonl').exists():
        m = read_json(recovery/'manifest.json')
        assert m['physicsVersion'] == 'collision-repair-v2'
        assert sha(canonical({k:v for k,v in m.items() if k!='campaignHash'})) == m['campaignHash']
        repo = recovery.parents[4]
        cert_path = repo/'aoe2x/js_simulation/calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json'
        assert sha(cert_path.read_bytes()) == m['compatibilityCertificateSha256']
        assert read_json(cert_path)['campaignHash'] == m['compatibilityCertificateHash']
        for f in m['runtimeFiles']:
            assert sha((repo/f['path']).read_bytes()) == f['sha256'], 'repaired runtime changed'
        for source in m['compatibleSourceCampaigns']:
            sm = read_json(Path(source['path'])/'manifest.json')
            assert sm['campaignHash'] == source['campaignHash']
            assert sha(canonical({k:v for k,v in sm.items() if k!='campaignHash'})) == sm['campaignHash']
        jobs = {j['id']:j for j in read_json(recovery/'jobs.json')}
        assert sha((recovery/'jobs.json').read_bytes()) == m['jobsSha256']
        allowed = {m['campaignHash']} | {x['campaignHash'] for x in m['compatibleSourceCampaigns']}
        recovery_meta = {'manifestSha256':sha((recovery/'manifest.json').read_bytes()),
            'campaignHash':m['campaignHash'],'compatibilityCertificateHash':m['compatibilityCertificateHash']}
        raw = (recovery/'pair-reviews.jsonl').read_bytes()
        lines = raw.splitlines() if raw.endswith(b'\n') else raw.splitlines()[:-1]
        latest = {r['matchupId']:r for r in map(json.loads,lines)}
        cached_lines = {}
        for review in latest.values():
            job = jobs[review['matchupId']]
            assert review['compatibilityCertificateHash'] == m['compatibilityCertificateHash']
            saved = []
            for reference in review['seedReferences']:
                ref = reference['sourceReference'];path = Path(ref['path'])
                if path not in cached_lines:
                    cached_lines[path] = path.read_bytes().splitlines()
                text = cached_lines[path][ref['line']-1]
                assert sha(text) == ref['recordSha256'], 'supporting recovery record changed'
                record = json.loads(text)
                assert record['campaignHash'] == reference['campaignHash'] == ref['campaignHash']
                assert record['campaignHash'] in allowed, 'incompatible physics evidence'
                assert all(record[k] == reference[k] for k in ['seed','outcome','finalStateHash','eventLogHash'])
                saved.append(record)
                ledger[(record['campaignHash'],record['matchupId'],record['seed'])] = {
                    'physicsVersion':'collision-repair-v2','record':record,'sourceReference':ref}
            validate_recovery_review(review, job, saved)
            row = by_key[job['pairKey']]
            if row['outcome'] == 'unresolved':
                projections[row['pairKey']] = project(row, job, review)
    by_key.update(projections)
    for cell in cells:
        projection = projections.get(cell['pairKey'])
        if projection is None:
            continue
        profile_a = variant_profiles[cell['civA']+'|'+cell['unitA']]
        winner = (projection['profiles'][0 if projection['outcome']=='a_win' else 1]
                  if projection['outcome'] in ('a_win','b_win') else None)
        cell.update(sourceOutcome=cell['outcome'],sourceEvidenceType=cell['evidenceType'],
            sourceContext=cell.get('context'),context=projection['context'],
            outcome=('a_win' if profile_a==winner else 'b_win') if winner else 'close_uncertain',
            evidenceType='predicted_unvalidated',verified=False,needsSim=False,needsValidation=True,
            explanation=projection['explanation'],prediction=projection['recoveryProjection'])
    for cell in cells:
        row = by_key[cell['pairKey']]
        if row['outcome'] in ('a_win','b_win'):
            winner = row['profiles'][0 if row['outcome']=='a_win' else 1]
            actual = variant_profiles[cell['civA']+'|'+cell['unitA']]
            assert cell['outcome'] == ('a_win' if actual==winner else 'b_win'), 'display orientation mismatch'
        else:
            assert cell['outcome'] == row['outcome']
        if cell['evidenceType']=='predicted_unvalidated':
            assert cell['verified'] is False and cell['needsValidation'] is True
    counts = collections.Counter(r['evidenceType'] for r in by_key.values())
    unresolved = sum(r['outcome']=='unresolved' for r in by_key.values())
    summary = {'status':'provisional_first_pass_complete' if not unresolved else 'first_pass_in_progress',
        'fullyValidated':False,'sourcePhase':phase,'variants':len(variants),'civPairs':1540,
        'profilePairs':len(by_key),'displayedCells':len(cells),'evidenceCounts':dict(counts),
        'unresolvedPairs':unresolved,'repairedEngineProjections':len(projections),
        'remainingPredictionValidation':counts['predicted_unvalidated'],
        'predictionTiers':dict(collections.Counter(r.get('predictionTier','unspecified')
            for r in by_key.values() if r['evidenceType']=='predicted_unvalidated')),
        'predictionValidation':{k:source_summary.get(k) for k in ['screenedPredictions',
            'screenWrongOrClose','prospectivePredictions','prospectiveWrongOrClose','contestedPredictions']},
        'scope':'Frozen V3 measurements/inferences and unvalidated predictions. Supporting repaired-engine measurements are in a separate ledger; their projection into this table is not validated under V3.',
        'bulkEngineReplayRequiredForThisProvisionalExport':False}
    if require_complete:
        assert unresolved == 0, f'{unresolved} unresolved pairs remain'
    write_rows(output/'profile-table.jsonl.gz',list(by_key.values()))
    write_rows(output/'civilization-table.jsonl.gz',cells)
    write_rows(output/'repaired-evidence-ledger.jsonl.gz',[ledger[k] for k in sorted(ledger)])
    write_json(output/'variant-profiles.json',variants)
    write_json(output/'summary.json',summary)
    write_json(output/'manifest.json',{'version':'provisional-first-pass-delivery-v1',
        'predictionArchiveManifestSha256':sha((prediction_dir/'manifest.json').read_bytes()),
        'sourcePhaseReviewSha256':sha(review_path.read_bytes()),'recovery':recovery_meta,
        'builderSha256':sha(Path(__file__).read_bytes()),'files':{name:sha((output/name).read_bytes()) for name in
        ['profile-table.jsonl.gz','civilization-table.jsonl.gz','repaired-evidence-ledger.jsonl.gz','variant-profiles.json','summary.json']}})
    return summary


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--campaign',type=Path,required=True)
    p.add_argument('--prediction-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--recovery',type=Path,default=DEFAULT_RECOVERY);p.add_argument('--require-complete',action='store_true')
    args=p.parse_args();print(json.dumps(build(args.campaign,args.prediction_dir,args.recovery,args.output,args.require_complete)))
