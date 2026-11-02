#!/usr/bin/env python3
"""Package provisional V3 predictions with a separate repaired-engine ledger.

Repaired-engine observations are never called V3 observations. Their projection
into this first-pass table is an explicitly unvalidated prediction, linked to a
complete same-context repaired seed set and an exact replay review.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
from civ_prediction_first_pass import read_rows, write_rows, write_json, canonical, sha

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECOVERY = Path('/workspace/aoe2_civ_first_pass_parallel/aoe2x/js_simulation/calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01')
DEFAULT_PATROL_RECOVERY = Path('/workspace/aoe2_civ_patrol_repair/aoe2x/js_simulation/calibration/campaigns/civ-matchups-patrol-first-pass-2026-11-01')
PATROL_PHYSICS = 'collision-repair-v2-patrol-candidate-v1'
STATIC_MEMO_PHYSICS = 'collision-repair-v2-static-memo-candidate-v1'
EVENT_STREAM_PHYSICS = 'collision-repair-v2-static-memo-event-stream-candidate-v1'
TERMINAL_GOAL_PHYSICS = 'collision-repair-v2-terminal-goal-candidate-v1'
DEFAULT_TERMINAL_GOAL_RECOVERY = Path('/workspace/aoe2_civ_subcell_route/aoe2x/js_simulation/calibration/campaigns/civ-matchups-terminal-goal-first-pass-2026-11-02')
DEFAULT_EVENT_STREAM_RECOVERY = Path('/workspace/aoe2_civ_event_stream/aoe2x/js_simulation/calibration/campaigns/civ-matchups-event-stream-first-pass-2026-11-02')
DEFAULT_EXTRA_EVENT_STREAM_RECOVERIES = (
    Path('/workspace/aoe2_civ_phase038_stream/aoe2x/js_simulation/calibration/campaigns/civ-matchups-phase038-stream-first-pass-2026-11-02'),
    Path('/workspace/aoe2_civ_phase039_stream/aoe2x/js_simulation/calibration/campaigns/civ-matchups-phase039-stream-first-pass-2026-11-02'),
    Path('/workspace/aoe2_civ_phase040_early_stream/aoe2x/js_simulation/calibration/campaigns/civ-matchups-phase040-early-stream-first-pass-2026-11-02'),
    Path('/workspace/aoe2_civ_phase040_stream/aoe2x/js_simulation/calibration/campaigns/civ-matchups-phase040-stream-first-pass-2026-11-02'),
)
DEFAULT_STATIC_MEMO_RECOVERY = Path('/workspace/aoe2_civ_path_cache/aoe2x/js_simulation/calibration/campaigns/civ-matchups-static-memo-first-pass-2026-11-02')
SUPPORTED_PHYSICS = {'collision-repair-v2', PATROL_PHYSICS, STATIC_MEMO_PHYSICS, EVENT_STREAM_PHYSICS, TERMINAL_GOAL_PHYSICS}


def read_json(path):
    return json.loads(path.read_bytes())


def validate_recovery_review(review, job, records, physics_version='collision-repair-v2'):
    assert review['pairKey'] == job['pairKey']
    assert physics_version in SUPPORTED_PHYSICS
    assert review['physicsVersion'] == physics_version
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
    physics = review['physicsVersion']
    assert physics in SUPPORTED_PHYSICS
    result = dict(row, sourceOutcome=row['outcome'], sourceEvidenceType=row['evidenceType'],
        sourceContext=row.get('context'), outcome=canonical_outcome,
        evidenceType='predicted_unvalidated', verified=False, needsSim=False, needsValidation=True,
        predictionTier='repaired_engine_projection', targetPhysicsVersion='frozen-v3',
        context={'profiles':job['profileHashes'], 'counts':job['counts'],
            **{k:job[k] for k in ['weightedCosts','scenarioHash','family','engineFamily','policy']}},
        explanation=f'Unvalidated V3 projection of a completed {physics} fight. Supporting measurements are stored in a separate ledger for their own physics version.',
        reasonCodes=['unvalidated_prediction','different_engine_projection'],
        recoveryProjection={'status':'predicted_unvalidated', 'verified':False,
            'measurementPhysicsVersion':physics, 'targetPhysicsVersion':'frozen-v3',
            'ruleVersion':'first-pass-repaired-engine-projection-v1',
            'reviewSha256':sha(canonical(review)), 'seedReferences':review['seedReferences'],
            'exactRepairedReplay':review['exactReplay'],
            'validationStatus':'not_validated_under_target_engine',
            **({'fidelityStatus':review['fidelityStatus']} if physics in (PATROL_PHYSICS, STATIC_MEMO_PHYSICS, EVENT_STREAM_PHYSICS, TERMINAL_GOAL_PHYSICS) else {})})
    return result



def validate_exhausted_hash_failure(reference, jobs):
    raw=Path(reference['path']).read_bytes().splitlines()
    line=reference['line']
    assert isinstance(line,int) and 0 < line <= len(raw), 'missing source failure line'
    text=raw[line-1]
    assert sha(text)==reference['recordSha256'], 'source failure changed'
    record=json.loads(text);error=record.get('error') or {}
    assert record['matchupId']==reference['matchupId'] and record['matchupId'] in jobs
    assert record['seed']==reference['seed'] and record['attempt']==4
    assert record.get('watchdog') is False and record.get('resultOutcome') is None
    assert error.get('name')=='RangeError' and error.get('message')=='Invalid string length'
    assert 'hashCanonicalJson' in error.get('stack',''), 'not the diagnosed final hashing failure'
    return record


def validate_early_source(manifest, jobs):
    reference=manifest.get('sourcePhasePlanReference')
    if reference is None:
        return
    path=Path(reference['path']);raw=path.read_bytes()
    assert sha(raw)==reference['sha256'], 'source phase plan changed'
    plan=json.loads(raw);source=path.parent.parent
    parent=read_json(source/'manifest.json')
    assert parent['campaignHash']==manifest['sourceInventoryCampaignHash']
    assert sha(canonical({k:v for k,v in parent.items() if k!='campaignHash'}))==parent['campaignHash']
    inventory=(source/parent['matchupInventory']['file']).read_bytes()
    assert sha(inventory)==manifest['sourceJobsSha256']==parent['matchupInventory']['sha256']
    source_jobs={j['id']:j for j in map(json.loads,gzip.decompress(inventory).splitlines())}
    for job in jobs.values():
        assert job==source_jobs[job['id']] and job['pairKey'] in plan['pairKeys']
    references=manifest.get('sourceFailureReferences',[])
    assert {r['matchupId'] for r in references}==set(jobs), 'unaccounted early recovery job'
    for item in references:
        validate_exhausted_hash_failure(item,jobs)


def load_candidate(recovery, physics, candidate_report, changed_file, changed_field):
    """Read only complete, reviewed own-engine seeds; diagnostics are ineligible."""
    if not (recovery/'manifest.json').exists() or not (recovery/'pair-reviews.jsonl').exists():
        return [], [], None
    m=read_json(recovery/'manifest.json');repo=recovery.parents[4]
    assert m['physicsVersion']==physics
    assert sha(canonical({k:v for k,v in m.items() if k!='campaignHash'}))==m['campaignHash']
    assert m['compatibleSourceCampaigns']==[], 'candidate cannot import older physics results'
    assert m['policy']['initialSeeds']==[0,1,2]
    assert m['policy']['extraSeedsOnDisagreement']==list(range(3,10))
    assert sha((recovery/'jobs.json').read_bytes())==m['jobsSha256']
    sim=repo/'aoe2x/js_simulation'
    fixed=[(sim/'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json','frozenInputsSha256'),
        (sim/'calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json','parentCertificateSha256'),
        (sim/candidate_report,'candidateSha256')]
    for path,key in fixed:assert sha(path.read_bytes())==m[key], f'candidate source changed: {path}'
    cert=read_json(fixed[1][0]);candidate=read_json(fixed[2][0])
    parent_files={f['path']:f['streamSha256'] for f in cert['sharedRuntimeFiles']+cert['changedOutputFiles']}
    assert {f['path']:f['parentV2StreamSha256'] for f in m['runtimeFiles']}==parent_files
    for f in m['runtimeFiles']:assert sha((repo/f['path']).read_bytes())==f['sha256']
    for f in m['orchestrationFiles']:assert sha((sim/f['path']).read_bytes())==f['sha256']
    expected_changes=[changed_file] if isinstance(changed_file,str) else changed_file
    actual_changes={f['path']:f['sha256'] for f in m['runtimeFiles'] if f['sha256']!=f['parentV2StreamSha256']}
    assert set(actual_changes)==set(expected_changes)
    assert actual_changes=={f['path']:f['candidateSha256'] for f in candidate[changed_field]}
    jobs={j['id']:j for j in read_json(recovery/'jobs.json')}
    validate_early_source(m,jobs)
    raw=(recovery/'runs.jsonl').read_bytes();assert raw.endswith(b'\n')
    lines=raw.splitlines();all_records=[json.loads(line) for line in lines]
    assert len({(r['matchupId'],r['seed']) for r in all_records})==len(all_records), 'duplicate candidate seed'
    for r in all_records:
        assert r['campaignHash']==m['campaignHash'] and r['physicsVersion']==physics
        assert r['matchupId'] in jobs
    raw=(recovery/'pair-reviews.jsonl').read_bytes();assert raw.endswith(b'\n')
    reviews={r['matchupId']:r for r in map(json.loads,raw.splitlines())}
    entries=[];ledger=[]
    for review in reviews.values():
        job=jobs[review['matchupId']];saved=[]
        assert review['fidelityStatus']==m['fidelityStatus']
        for reference in review['seedReferences']:
            ref=reference['sourceReference'];assert Path(ref['path'])==recovery/'runs.jsonl', 'diagnostic/imported reference forbidden'
            text=lines[ref['line']-1];assert sha(text)==ref['recordSha256']
            record=json.loads(text)
            assert record['campaignHash']==reference['campaignHash']==ref['campaignHash']==m['campaignHash']
            assert all(record[k]==reference[k] for k in ['seed','outcome','finalStateHash','eventLogHash'])
            saved.append(record);ledger.append({'physicsVersion':physics,'record':record,'sourceReference':ref})
        assert {r['seed'] for r in saved}=={r['seed'] for r in all_records if r['matchupId']==job['id']}, 'review omits saved seed'
        validate_recovery_review(review,job,saved,physics)
        entries.append((job,review))
    return entries,ledger,{'manifestSha256':sha((recovery/'manifest.json').read_bytes()),
        'campaignHash':m['campaignHash'],'physicsVersion':physics,'fidelityStatus':m['fidelityStatus']}

def load_patrol_candidate(recovery):
    return load_candidate(recovery, PATROL_PHYSICS,
        'calibration/reports/civ-matchups-patrol-repair-2026-11-01/CANDIDATE.json',
        'aoe2x/js_simulation/src/combat/world.js', 'changedPhysicsFiles')


def load_static_memo_candidate(recovery):
    return load_candidate(recovery, STATIC_MEMO_PHYSICS,
        'calibration/reports/civ-static-geometry-cache-2026-11-02/CANDIDATE.json',
        'aoe2x/js_simulation/src/combat/collision.js', 'changedRuntimeFiles')


def load_event_stream_candidate(recovery):
    return load_candidate(recovery, EVENT_STREAM_PHYSICS,
        'calibration/reports/civ-event-stream-2026-11-02/CANDIDATE.json',
        ['aoe2x/js_simulation/'+p for p in ['src/combat/collision.js','src/combat/world.js','src/fight.js','src/canonical-json.js']],
        'changedRuntimeFiles')



def load_terminal_goal_candidate(recovery):
    return load_candidate(recovery, TERMINAL_GOAL_PHYSICS,
        'calibration/reports/civ-subcell-route-2026-11-02/CANDIDATE.json',
        ['aoe2x/js_simulation/'+p for p in ['src/combat/collision.js','src/combat/world.js',
          'src/fight.js','src/canonical-json.js','src/combat/chase-path.js']],
        'changedRuntimeFiles')


def merge_candidate_batches(batches):
    """Keep source campaigns distinct and reject conflicting complete evidence."""
    entries,ledger,metadata=[],[],[]
    pair_contexts={};seed_keys=set();campaigns=set()
    for batch_entries,batch_ledger,meta in batches:
        if meta is not None:
            assert meta['campaignHash'] not in campaigns, 'duplicate candidate campaign'
            campaigns.add(meta['campaignHash']);metadata.append(meta)
        for job,review in batch_entries:
            context=(job['profileHashes'],job['counts'],job['scenarioHash'],review['physicsVersion'],review['outcome'])
            if job['pairKey'] in pair_contexts:
                assert pair_contexts[job['pairKey']]==context, 'conflicting candidate contexts or outcomes'
            else:
                pair_contexts[job['pairKey']]=context;entries.append((job,review))
        for row in batch_ledger:
            r=row['record'];key=(row['physicsVersion'],r['campaignHash'],r['matchupId'],r['seed'])
            assert key not in seed_keys, 'duplicate candidate seed provenance'
            seed_keys.add(key);ledger.append(row)
    return entries,ledger,metadata


def build(campaign, prediction_dir, recovery, output, require_complete=False, patrol_recovery=DEFAULT_PATROL_RECOVERY, static_memo_recovery=DEFAULT_STATIC_MEMO_RECOVERY, event_stream_recovery=DEFAULT_EVENT_STREAM_RECOVERY, extra_event_stream_recoveries=DEFAULT_EXTRA_EVENT_STREAM_RECOVERIES, terminal_goal_recovery=DEFAULT_TERMINAL_GOAL_RECOVERY):
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
    patrol_entries,patrol_ledger,patrol_meta=load_patrol_candidate(patrol_recovery)
    memo_entries,memo_ledger,memo_meta=load_static_memo_candidate(static_memo_recovery)
    stream_entries,stream_ledger,stream_metadata=merge_candidate_batches([
        load_event_stream_candidate(path)
        for path in (event_stream_recovery, *extra_event_stream_recoveries)])
    terminal_entries,terminal_ledger,terminal_meta=load_terminal_goal_candidate(terminal_goal_recovery)
    for job,review in patrol_entries+memo_entries+stream_entries+terminal_entries:
        row=by_key[job['pairKey']]
        # Never overwrite an observed result, approved forecast or completed V2 projection.
        if row['outcome']=='unresolved' and row['pairKey'] not in projections:
            projections[row['pairKey']]=project(row,job,review)
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
        'repairedProjectionPhysicsCounts':dict(collections.Counter(r['recoveryProjection']['measurementPhysicsVersion'] for r in projections.values())),
        'remainingPredictionValidation':counts['predicted_unvalidated'],
        'predictionTiers':dict(collections.Counter(r.get('predictionTier','unspecified')
            for r in by_key.values() if r['evidenceType']=='predicted_unvalidated')),
        'predictionValidation':{k:source_summary.get(k) for k in ['screenedPredictions',
            'screenWrongOrClose','prospectivePredictions','prospectiveWrongOrClose','contestedPredictions']},
        'scope':'Frozen V3 measurements/inferences and unvalidated predictions. Supporting repaired-engine measurements remain in separate physics-specific ledgers; their projections are not V3 measurements. Candidate projections retain explicit independent game-fidelity validation gaps.',
        'bulkEngineReplayRequiredForThisProvisionalExport':False}
    if require_complete:
        assert unresolved == 0, f'{unresolved} unresolved pairs remain'
    write_rows(output/'profile-table.jsonl.gz',list(by_key.values()))
    write_rows(output/'civilization-table.jsonl.gz',cells)
    write_rows(output/'repaired-evidence-ledger.jsonl.gz',[ledger[k] for k in sorted(ledger)])
    write_rows(output/'patrol-candidate-evidence-ledger.jsonl.gz',patrol_ledger)
    write_rows(output/'static-memo-candidate-evidence-ledger.jsonl.gz',memo_ledger)
    write_rows(output/'event-stream-candidate-evidence-ledger.jsonl.gz',stream_ledger)
    write_rows(output/'terminal-goal-candidate-evidence-ledger.jsonl.gz',terminal_ledger)
    write_json(output/'variant-profiles.json',variants)
    write_json(output/'summary.json',summary)
    write_json(output/'manifest.json',{'version':'provisional-first-pass-delivery-v6',
        'predictionArchiveManifestSha256':sha((prediction_dir/'manifest.json').read_bytes()),
        'sourcePhaseReviewSha256':sha(review_path.read_bytes()),'recovery':recovery_meta,'patrolRecovery':patrol_meta,'staticMemoRecovery':memo_meta,'eventStreamRecoveries':stream_metadata,'terminalGoalRecovery':terminal_meta,
        'builderSha256':sha(Path(__file__).read_bytes()),'files':{name:sha((output/name).read_bytes()) for name in
        ['profile-table.jsonl.gz','civilization-table.jsonl.gz','repaired-evidence-ledger.jsonl.gz','patrol-candidate-evidence-ledger.jsonl.gz','static-memo-candidate-evidence-ledger.jsonl.gz','event-stream-candidate-evidence-ledger.jsonl.gz','terminal-goal-candidate-evidence-ledger.jsonl.gz','variant-profiles.json','summary.json']}})
    return summary


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--campaign',type=Path,required=True)
    p.add_argument('--prediction-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--recovery',type=Path,default=DEFAULT_RECOVERY);p.add_argument('--require-complete',action='store_true')
    p.add_argument('--patrol-recovery',type=Path,default=DEFAULT_PATROL_RECOVERY)
    p.add_argument('--static-memo-recovery',type=Path,default=DEFAULT_STATIC_MEMO_RECOVERY)
    p.add_argument('--event-stream-recovery',type=Path,default=DEFAULT_EVENT_STREAM_RECOVERY)
    p.add_argument('--extra-event-stream-recovery',type=Path,action='append',default=None)
    p.add_argument('--terminal-goal-recovery',type=Path,default=DEFAULT_TERMINAL_GOAL_RECOVERY)
    args=p.parse_args();print(json.dumps(build(args.campaign,args.prediction_dir,args.recovery,args.output,args.require_complete,args.patrol_recovery,args.static_memo_recovery,args.event_stream_recovery,DEFAULT_EXTRA_EVENT_STREAM_RECOVERIES if args.extra_event_stream_recovery is None else tuple(args.extra_event_stream_recovery),args.terminal_goal_recovery)))
