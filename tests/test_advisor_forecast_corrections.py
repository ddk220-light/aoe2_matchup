"""Synthetic import contracts; these fixtures never execute simulation seeds."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import zlib

import pytest

from scripts.apply_advisor_matchup_corrections import apply
from scripts.apply_advisor_forecast_corrections import NO_REPLAY, encode

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def forecast(tmp_path):
    baseline = ROOT / 'data/golden/civ_matchups_first_pass.db'
    db = sqlite3.connect(baseline)
    dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    for identifier, blob in db.execute("SELECT e.id,e.data FROM evidence e JOIN cells c ON c.evidence_id=e.id WHERE c.evidence_type='predicted_unvalidated' ORDER BY e.id"):
        original = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
        if original['outcome'] in ('a_win', 'b_win') and original['context']['profiles'][0] != original['pairKey'].split('|')[0]:
            break
    cells = db.execute('SELECT * FROM cells WHERE evidence_id=?', (identifier,)).fetchall()
    old_mismatch = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0]).get('mismatch_validation')
    db.close()
    winner_hash = original['pairKey'].split('|')[0 if original['outcome'] == 'a_win' else 1]
    owner = original['context']['profiles'].index(winner_hash) + 2
    review = dict(jobId='synthetic-forecast-import', campaignHash='synthetic', reviewedAt='synthetic', status='passed',
                  context=deepcopy(original['context']), contextHash='', pairKey=original['pairKey'], physicsVersion='frozen-civ-matchups-v3',
                  validationMode='single_seed_forecast_screen', samplingPolicyHash=NO_REPLAY, evidenceLevel='single_seed_confirmation',
                  samplingDecision={}, seedCount=1, requiredSeeds=[], seedResults=[], measuredRecords=[], outcome=original['outcome'],
                  originalEvidenceIds=[identifier], originalEvidence=[dict(evidenceId=identifier, evidence=original)],
                  originalOutcomes=[dict(evidenceId=identifier, outcome=original['outcome'], evidenceType='predicted_unvalidated')],
                  changed=False, displayedMismatchCells=len(cells), exactReplay=dict(required=False, performed=False, exact=None, samplingPolicyHash=NO_REPLAY),
                  reviewFile='synthetic.json', reviewFileSha256='synthetic', freshControlRecord=None)
    snapshot = tmp_path / 'snapshot'; snapshot.mkdir()

    def records(owners):
        review['measuredRecords'] = [dict(campaignHash='synthetic', matchupId=review['jobId'], pairKey=review['pairKey'],
            contextHash='', physicsVersion='frozen-civ-matchups-v3', executionVersion='lossless-event-stream-v1', seed=s,
            startedAt='synthetic', finishedAt='synthetic', purpose='fresh_measurement', counts=review['context']['counts'],
            profileHashes=review['context']['profiles'], scenarioHash=review['context']['scenarioHash'], winnerOwner=o,
            unitStartingHp=100, opponentStartingHp=100, unitRemainingHp=50 if o==2 else 0, opponentRemainingHp=50 if o==3 else 0,
            unitSurvivors=1 if o==2 else 0, opponentSurvivors=1 if o==3 else 0, ticks=60, finalStateHash=f'state-{s}', eventLogHash=f'events-{s}')
            for s, o in enumerate(owners)]
        review['seedCount'] = len(owners)
        unique = set(owners)
        review['outcome'] = ('a_win' if review['context']['profiles'][owners[0]-2] == review['pairKey'].split('|')[0] else 'b_win') if len(unique)==1 else 'close_uncertain'
        review['changed'] = review['outcome'] != original['outcome']

    def save():
        # Use the same pure canonical hash implementation as the stored reviews.
        script = """import{hashCanonicalJson as hash}from'./aoe2x/js_simulation/src/canonical-json.js';import{readFileSync}from'node:fs';
const r=JSON.parse(readFileSync(0,'utf8'));r.contextHash=hash(r.context);for(const m of r.measuredRecords)m.contextHash=r.contextHash;
r.seedResults=r.measuredRecords.map(m=>({seed:m.seed,winnerOwner:m.winnerOwner,ticks:m.ticks,finalStateHash:m.finalStateHash,eventLogHash:m.eventLogHash,recordHash:hash(m)}));
const{reviewFile,reviewFileSha256,measuredRecords,freshControlRecord,originalEvidence,reviewHash,...body}=r;r.reviewHash=hash(body);process.stdout.write(JSON.stringify(r));"""
        sealed = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', script], input=json.dumps(review).encode(), cwd=ROOT))
        review.update(sealed)
        data = gzip.compress((encode(review)+'\n').encode()); (snapshot/'reviewed-contexts.jsonl.gz').write_bytes(data)
        single = review['evidenceLevel']=='single_seed_confirmation'
        manifest = dict(version='civ-matchup-forecast-corrections-v3', physicsVersion='frozen-civ-matchups-v3', samplingPolicyHash=NO_REPLAY,
                        campaignHash='synthetic', sourceCommit='synthetic', originalDatabaseSha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
                        reviewedContexts=1, remainingValidationContexts=10, singleSeedConfirmations=int(single), multiSeedValidations=int(not single),
                        changedWinnerOrCloseContexts=int(review['changed']), exactReplayChecks=int(review['exactReplay'].get('exact') is True),
                        contextsWithoutReplay=int(review['exactReplay'].get('performed') is False), files={'reviewed-contexts.jsonl.gz':hashlib.sha256(data).hexdigest()})
        (snapshot/'manifest.json').write_text(encode(manifest))
    records([owner]); save()
    return dict(baseline=baseline, snapshot=snapshot, output=tmp_path/'corrected.db', review=review, original=original,
                identifier=identifier, dictionary=dictionary, cells=cells, old_mismatch=old_mismatch, owner=owner, records=records, save=save)


def test_single_confirmation_preserves_prior_releases_and_original_provenance(forecast):
    f=forecast; report=apply(f['baseline'], f['snapshot'], f['output'])
    assert report['single_seed_confirmations']==1 and report['multi_seed_validations']==0
    db=sqlite3.connect(f['output']); old=sqlite3.connect(f['baseline'])
    evidence=json.loads(zlib.decompressobj(zdict=f['dictionary']).decompress(db.execute('SELECT data FROM evidence WHERE id=?',(f['identifier'],)).fetchone()[0]))
    assert evidence['originalEvidence']==f['original'] and evidence['originalPrediction']==f['original']['originalPrediction']
    assert evidence['forecastValidation']['evidenceLevel']=='single_seed_confirmation'
    assert evidence['forecastValidation']['exactReplay']==f['review']['exactReplay']
    assert evidence['forecastValidation']['originalCellFlagsAndTiers']==[list(x) for x in sorted({(r[7],r[6]) for r in f['cells']})]
    assert json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])['mismatch_validation']==f['old_mismatch']
    assert db.execute('SELECT * FROM cells WHERE evidence_id!=? ORDER BY a,b LIMIT 20',(f['identifier'],)).fetchall()==old.execute('SELECT * FROM cells WHERE evidence_id!=? ORDER BY a,b LIMIT 20',(f['identifier'],)).fetchall()
    assert db.execute('SELECT outcome,evidence_type FROM cells WHERE evidence_id=?',(f['identifier'],)).fetchall()==[(r[2],'observed') for r in f['cells']]
    db.close();old.close()


@pytest.mark.parametrize('mixed',[False,True])
def test_multi_seed_disagreement_and_mixed_results_require_the_full_set(forecast,mixed):
    f=forecast; r=f['review']; r['evidenceLevel']='multi_seed_validation'
    f['records']([f['owner'],5-f['owner']]+[f['owner']]*8 if mixed else [5-f['owner']]*3); f['save']()
    report=apply(f['baseline'], f['snapshot'], f['output'])
    assert report['multi_seed_validations']==1 and report['changed_outcome_contexts']==1
    assert report['changed_outcome_cells']==len(f['cells'])


@pytest.mark.parametrize('invalid',['partial','weak_single','disagree_single','reversed_context','invented_replay'])
def test_invalid_evidence_does_not_replace_the_serving_database(forecast,invalid):
    f=forecast;r=f['review']
    if invalid=='partial':r['evidenceLevel']='multi_seed_validation';f['records']([f['owner']]*2)
    if invalid=='weak_single':r['measuredRecords'][0]['unitRemainingHp' if f['owner']==2 else 'opponentRemainingHp']=24
    if invalid=='disagree_single':f['records']([5-f['owner']])
    if invalid=='reversed_context':r['context']['profiles'].reverse();r['context']['counts'].reverse()
    if invalid=='invented_replay':r['exactReplay']['exact']=True
    f['save']()
    with pytest.raises((AssertionError,subprocess.CalledProcessError)):
        apply(f['baseline'], f['snapshot'], f['output'])
    assert not f['output'].exists()


def test_cumulative_forecast_releases_cannot_drop_prior_reviews(forecast):
    f=forecast;apply(f['baseline'],f['snapshot'],f['output']);before=f['output'].read_bytes()
    f['review']['jobId']='different-job';f['review']['measuredRecords'][0]['matchupId']='different-job';f['save']()
    with pytest.raises(AssertionError,match='remove released forecast corrections'):
        apply(f['baseline'],f['snapshot'],f['output'])
    assert f['output'].read_bytes()==before


def test_native_record_hash_cannot_be_replaced_by_only_rehashing_the_bundle(forecast):
    f=forecast;r=deepcopy(f['review']);r['measuredRecords'][0]['finishedAt']='tampered-after-review'
    data=gzip.compress((encode(r)+'\n').encode());(f['snapshot']/'reviewed-contexts.jsonl.gz').write_bytes(data)
    manifest=json.loads((f['snapshot']/'manifest.json').read_text());manifest['files']['reviewed-contexts.jsonl.gz']=hashlib.sha256(data).hexdigest()
    (f['snapshot']/'manifest.json').write_text(encode(manifest))
    with pytest.raises(subprocess.CalledProcessError):
        apply(f['baseline'],f['snapshot'],f['output'])
    assert not f['output'].exists()


def test_historical_replay_evidence_is_preserved_without_execution(forecast):
    f=forecast;r=f['review'];r['evidenceLevel']='multi_seed_validation';r['samplingPolicyHash']=None
    f['records']([f['owner']]*3)
    r['exactReplay']=dict(seed=0,exact=True,result={k:r['measuredRecords'][0][k] for k in ('ticks','winnerOwner','finalStateHash','eventLogHash')})
    f['save']();apply(f['baseline'],f['snapshot'],f['output'])
    db=sqlite3.connect(f['output']);blob=db.execute('SELECT data FROM evidence WHERE id=?',(f['identifier'],)).fetchone()[0];db.close()
    row=json.loads(zlib.decompressobj(zdict=f['dictionary']).decompress(blob))
    assert row['forecastValidation']['exactReplay']==r['exactReplay']
    assert row['forecastValidation']['samplingPolicyHash'] is None
