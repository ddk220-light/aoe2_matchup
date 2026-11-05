"""Correction import contracts; synthetic review fixtures are never fight records."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib

import pytest

from scripts.apply_advisor_matchup_corrections import apply, encode

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def correction(tmp_path):
    baseline = ROOT / 'data/golden/civ_matchups_first_pass.db'
    db = sqlite3.connect(baseline)
    dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    for (identifier, blob) in db.execute("SELECT DISTINCT e.id,e.data FROM evidence e JOIN cells c ON c.evidence_id=e.id WHERE c.evidence_type='predicted_unvalidated'"):
        evidence = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
        if evidence['context']['profiles'][0] != evidence['pairKey'].split('|')[0] and evidence['outcome'] in ('a_win', 'b_win'):
            break
    else:
        raise AssertionError('no reversed physical-context fixture')
    cells = db.execute('SELECT a,b,outcome,count_a,count_b FROM cells WHERE evidence_id=?', (identifier,)).fetchall()
    units = {i: json.loads(data) for i, data in db.execute('SELECT id,data FROM units')}
    db.close()
    outcome = 'a_win' if evidence['outcome'] == 'b_win' else 'b_win'
    review = dict(jobId='synthetic-import-test', campaignHash='synthetic', status='passed', context=evidence['context'],
                  pairKey=evidence['pairKey'], requiredSeeds=[], seedCount=3, outcome=outcome,
                  physicsVersion='frozen-civ-matchups-v3', reviewHash='synthetic-review',
                  reviewFile='synthetic.json', reviewFileSha256='synthetic',
                  originalEvidenceIds=[identifier], originalEvidence=[dict(evidenceId=identifier, evidence=evidence)],
                  seedResults=[dict(seed=s) for s in range(3)], exactReplay=dict(exact=True))
    snapshot = tmp_path / 'snapshot'; snapshot.mkdir()

    def save():
        data = gzip.compress((encode(review) + '\n').encode())
        (snapshot / 'reviewed-contexts.jsonl.gz').write_bytes(data)
        manifest = dict(version='civ-matchup-mismatch-corrections-v1', physicsVersion='frozen-civ-matchups-v3',
                        originalDatabaseSha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
                        reviewedContexts=1, campaignHash='synthetic', sourceCommit='synthetic', remainingValidationContexts=10,
                        files={'reviewed-contexts.jsonl.gz': hashlib.sha256(data).hexdigest()})
        (snapshot / 'manifest.json').write_text(encode(manifest))
    save()
    return dict(baseline=baseline, snapshot=snapshot, output=tmp_path / 'corrected.db', review=review,
                evidence=evidence, identifier=identifier, cells=cells, units=units, dictionary=dictionary, save=save)


def test_reviewed_corrections_respect_physical_orientation_and_preserve_original_forecast(correction):
    f = correction
    report = apply(f['baseline'], f['snapshot'], f['output'])
    assert report['reviewed_contexts'] == 1
    assert report['changed_outcome_cells'] == len(f['cells'])
    db = sqlite3.connect(f['output'])
    winner = f['review']['pairKey'].split('|')[0 if f['review']['outcome'] == 'a_win' else 1]
    for a, b, _, count_a, count_b in f['cells']:
        row = db.execute('SELECT outcome,evidence_type,count_a,count_b,flags,tier FROM cells WHERE a=? AND b=?', (a, b)).fetchone()
        assert row == ('a_win' if f['units'][a]['profileHash'] == winner else 'b_win', 'observed', count_a, count_b, 0, '')
    blob = db.execute('SELECT data FROM evidence WHERE id=?', (f['identifier'],)).fetchone()[0]
    evidence = json.loads(zlib.decompressobj(zdict=f['dictionary']).decompress(blob))
    assert evidence['originalEvidence'] == f['evidence']
    assert evidence['originalPrediction'] == f['evidence']['originalPrediction']
    assert evidence['context'] == f['evidence']['context']
    assert evidence['mismatchValidation']['status'] == 'simulation_checked'
    assert evidence['verified'] and not evidence['needsValidation']
    original = sqlite3.connect(f['baseline'])
    other = original.execute('SELECT * FROM cells WHERE evidence_id!=? LIMIT 1', (f['identifier'],)).fetchone()
    assert db.execute('SELECT * FROM cells WHERE a=? AND b=?', other[:2]).fetchone() == other
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    original.close(); db.close()


def test_incomplete_seed_sets_never_replace_data(correction):
    f = correction; f['review']['requiredSeeds'] = [2]; f['save']()
    with pytest.raises(AssertionError):
        apply(f['baseline'], f['snapshot'], f['output'])
    assert not f['output'].exists()


def test_a_reversed_battle_context_is_not_a_correction_to_the_original(correction):
    f = correction
    f['review']['context'] = dict(f['review']['context'], profiles=f['review']['context']['profiles'][::-1])
    f['save']()
    with pytest.raises(AssertionError, match='physical context mismatch'):
        apply(f['baseline'], f['snapshot'], f['output'])
    assert not f['output'].exists()


def test_later_snapshots_cannot_remove_released_corrections(correction):
    f = correction
    apply(f['baseline'], f['snapshot'], f['output'])
    before = f['output'].read_bytes()
    f['review']['jobId'] = 'different-synthetic-job'; f['save']()
    with pytest.raises(AssertionError, match='remove released corrections'):
        apply(f['baseline'], f['snapshot'], f['output'])
    assert f['output'].read_bytes() == before
