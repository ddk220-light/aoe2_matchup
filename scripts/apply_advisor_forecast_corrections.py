"""Overlay complete forecast reviews on their immutable production baseline.

The legacy mismatch importer retains its separate protocol. No simulation is
executed here, including for the historical replay evidence.
"""
import collections
from contextlib import closing
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
NO_REPLAY = '4404ca505096341c2bcea03e1376ed5d7c27f7a1f6d6452bd92a9a526273c30c'
HISTORICAL_ADAPTIVE = '0760c8fd7ee4274728b2211cf765172daed25551eeb1d4495498a28663602b70'


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_review(review, manifest):
    assert review['status'] == 'passed' and not review['requiredSeeds'], 'incomplete review'
    assert review['campaignHash'] == manifest['campaignHash']
    assert review['physicsVersion'] == manifest['physicsVersion'] == 'frozen-civ-matchups-v3'
    assert set(review['context']['profiles']) == set(review['pairKey'].split('|'))
    policy = review.get('samplingPolicyHash')
    assert policy in (None, HISTORICAL_ADAPTIVE, NO_REPLAY), 'unknown sampling policy'
    measured = review['measuredRecords']
    seeds = {r['seed']: r for r in measured}
    assert len(seeds) == len(measured) == review['seedCount'] == len(review['seedResults']), 'duplicate or missing seed'
    originals = review['originalEvidence']
    assert len({x['evidenceId'] for x in originals}) == len(originals)
    assert [x['evidenceId'] for x in originals] == review['originalEvidenceIds']
    assert review['originalOutcomes'] == [dict(evidenceId=x['evidenceId'], outcome=x['evidence']['outcome'],
                                             evidenceType=x['evidence']['evidenceType']) for x in originals]
    for result in review['seedResults']:
        row = seeds[result['seed']]
        assert row['campaignHash'] == manifest['campaignHash'] and row['matchupId'] == review['jobId']
        assert row['purpose'] == 'fresh_measurement' and row['finishedAt'] and not row.get('watchdog'), 'not a completed measurement'
        assert row['physicsVersion'] == manifest['physicsVersion'] and row['executionVersion'] == 'lossless-event-stream-v1'
        assert row['contextHash'] == review['contextHash'] and row['pairKey'] == review['pairKey']
        assert row['profileHashes'] == review['context']['profiles'], 'physical orientation mismatch'
        assert row['counts'] == review['context']['counts'] and row['scenarioHash'] == review['context']['scenarioHash']
        assert all(result[k] == row[k] for k in ('winnerOwner', 'ticks', 'finalStateHash', 'eventLogHash'))
    single = review.get('evidenceLevel') == 'single_seed_confirmation'
    if single:
        assert policy in (HISTORICAL_ADAPTIVE, NO_REPLAY)
        assert set(seeds) == {0}, 'single confirmation must contain only seed zero'
        first = seeds[0]; owner = first['winnerOwner']; assert owner in (2, 3)
        winner, loser = ('unit', 'opponent') if owner == 2 else ('opponent', 'unit')
        assert first[loser + 'Survivors'] == first[loser + 'RemainingHp'] == 0
        assert first[winner + 'RemainingHp'] >= .25 * first[winner + 'StartingHp'] > 0, 'not decisive agreement'
    else:
        assert {0, 1, 2} <= set(seeds), 'incomplete initial seed set'
        expected = set(range(10)) if len({seeds[s]['winnerOwner'] for s in range(3)}) > 1 else {0, 1, 2}
        assert set(seeds) == expected, 'incomplete or extra seeds'
    owners = {r['winnerOwner'] for r in measured}
    owner = next(iter(owners))
    outcome = ('a_win' if review['context']['profiles'][owner - 2] == review['pairKey'].split('|')[0] else 'b_win') if len(owners) == 1 and owner in (2, 3) else 'close_uncertain'
    assert review['outcome'] == outcome, 'outcome does not match native records'
    assert review['changed'] == any(x['evidence']['outcome'] != outcome for x in originals)
    if single:
        assert not review['changed'], 'single seed disagrees with original forecast'
    replay = review['exactReplay']
    if policy == NO_REPLAY:
        assert replay['required'] is False and replay['performed'] is False and replay['exact'] is None, 'new replay is not permitted'
        assert replay['samplingPolicyHash'] == policy
    else:
        assert replay['exact'] is True, 'missing historical replay evidence'
        control = seeds[replay['seed']]
        assert all(replay['result'][k] == control[k] for k in ('ticks', 'winnerOwner', 'finalStateHash', 'eventLogHash'))


def apply_forecast(baseline, snapshot, output):
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    assert manifest['version'] == 'civ-matchup-forecast-corrections-v3'
    assert manifest['samplingPolicyHash'] == NO_REPLAY
    assert sha(baseline) == manifest['originalDatabaseSha256'], 'baseline is not the frozen forecast input'
    assert baseline.resolve() != output.resolve(), 'immutable baseline must be separate from output'
    for file, expected in manifest['files'].items():
        assert sha(snapshot / file) == expected, ('snapshot hash mismatch', file)
    with gzip.open(snapshot / 'reviewed-contexts.jsonl.gz', 'rt') as f:
        reviews = [json.loads(line) for line in f if line.strip()]
    assert len({r['jobId'] for r in reviews}) == len(reviews) == manifest['reviewedContexts']
    for review in reviews:
        validate_review(review, manifest)
    subprocess.run(['node', str(ROOT / 'scripts/verify_advisor_forecast_snapshot.mjs'), str(snapshot)], check=True)
    if output.exists():
        with closing(sqlite3.connect(f'file:{output}?mode=ro', uri=True)) as previous:
            dictionary = previous.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
            prior_jobs = {row['forecastValidation']['jobId'] for (blob,) in previous.execute('SELECT data FROM evidence')
                          if (row := json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))).get('forecastValidation')}
        assert prior_jobs <= {r['jobId'] for r in reviews}, 'snapshot would remove released forecast corrections'
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = output.with_suffix('.metadata.json')
    serving_metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    handle, pending_name = tempfile.mkstemp(prefix='.advisor-forecast-', suffix='.db', dir=output.parent)
    os.close(handle)
    pending = Path(pending_name)
    modified = collections.Counter(); affected = set()
    try:
        shutil.copyfile(baseline, pending)
        with closing(sqlite3.connect(pending)) as db:
            dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
            units = {i: json.loads(data) for i, data in db.execute('SELECT id,data FROM units')}
            metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
            for review in reviews:
                expected_original = {x['evidenceId']: x['evidence'] for x in review['originalEvidence']}
                for identifier in review['originalEvidenceIds']:
                    assert identifier not in affected, 'context applied twice'
                    affected.add(identifier)
                    blob = db.execute('SELECT data FROM evidence WHERE id=?', (identifier,)).fetchone()[0]
                    original = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
                    assert original == expected_original[identifier], 'original evidence changed'
                    assert original['evidenceType'] == 'predicted_unvalidated', 'only forecast evidence is eligible'
                    assert original['context'] == review['context'], 'physical context mismatch'
                    assert original['pairKey'] == review['pairKey']
                    flags = db.execute('SELECT DISTINCT flags,tier FROM cells WHERE evidence_id=?', (identifier,)).fetchall()
                    validation = {k: review[k] for k in ('jobId', 'reviewHash', 'reviewFile', 'reviewFileSha256', 'contextHash', 'seedResults', 'exactReplay')}
                    validation.update(status='simulation_checked', campaignHash=manifest['campaignHash'], sourceCommit=manifest['sourceCommit'],
                                      physicsVersion=manifest['physicsVersion'], evidenceLevel=review.get('evidenceLevel', 'multi_seed_validation'),
                                      samplingPolicyHash=review.get('samplingPolicyHash'), samplingDecision=review.get('samplingDecision'),
                                      originalCellFlagsAndTiers=flags)
                    updated = dict(original, outcome=review['outcome'], evidenceType='observed', needsValidation=False, verified=True,
                                   originalEvidence=original, forecastValidation=validation,
                                   validationRunIds=[f"{review['jobId']}:{s['seed']}" for s in review['seedResults']])
                    compressor = zlib.compressobj(9, zdict=dictionary)
                    db.execute('UPDATE evidence SET data=? WHERE id=?', (compressor.compress(encode(updated).encode()) + compressor.flush(), identifier))
                    winner = review['pairKey'].split('|')[0 if review['outcome'] == 'a_win' else 1] if review['outcome'] in ('a_win', 'b_win') else None
                    for a, b, old, ca, cb in db.execute('SELECT a,b,outcome,count_a,count_b FROM cells WHERE evidence_id=?', (identifier,)).fetchall():
                        assert {units[a]['profileHash'], units[b]['profileHash']} == set(review['context']['profiles'])
                        for unit, count in ((a, ca), (b, cb)):
                            assert count == review['context']['counts'][review['context']['profiles'].index(units[unit]['profileHash'])]
                        outcome = ('a_win' if units[a]['profileHash'] == winner else 'b_win') if winner else review['outcome']
                        modified['reviewed_cells'] += 1; modified['changed_outcome_cells'] += old != outcome
                        db.execute("UPDATE cells SET outcome=?,evidence_type='observed',tier='',flags=0 WHERE a=? AND b=?", (outcome, a, b))
            counts = collections.Counter(); tiers = collections.Counter()
            for (blob,) in db.execute('SELECT data FROM evidence'):
                row = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob)); counts[row['evidenceType']] += 1
                if row['evidenceType'] == 'predicted_unvalidated': tiers[row.get('predictionTier', '')] += 1
            single = sum(r.get('evidenceLevel') == 'single_seed_confirmation' for r in reviews)
            assert single == manifest['singleSeedConfirmations'] and len(reviews) - single == manifest['multiSeedValidations']
            assert sum(r['changed'] for r in reviews) == manifest['changedWinnerOrCloseContexts']
            assert sum(r['exactReplay'].get('exact') is True for r in reviews) == manifest['exactReplayChecks']
            assert sum(r['exactReplay'].get('performed') is False for r in reviews) == manifest['contextsWithoutReplay']
            metadata.update(forecast_validation=dict(manifest, appliedEvidenceRows=len(affected), **modified),
                            evidenceCounts=dict(counts), predictionTiers=dict(tiers),
                            displayedEvidenceCounts=dict(db.execute('SELECT evidence_type,COUNT(*) FROM cells GROUP BY evidence_type')),
                            remainingPredictionValidation=counts['predicted_unvalidated'])
            db.execute("UPDATE metadata SET value=? WHERE key='dataset'", (encode(metadata),))
            assert [db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('units', 'cells', 'evidence')] == [555, 151223, 68916]
            db.commit(); assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            # Larger pages pack the cumulative provenance blobs without the
            # substantial half-empty 4 KiB pages. No row/blob encoding changes;
            # the complete reviewed dataset must fit GitHub's 100 MiB limit.
            db.execute('PRAGMA page_size=32768')
            db.execute('VACUUM')
        pending.replace(output)
    finally:
        pending.unlink(missing_ok=True)
    report = dict(campaign_hash=manifest['campaignHash'], validation_source_commit=manifest['sourceCommit'], reviewed_contexts=len(reviews),
                  single_seed_confirmations=single, multi_seed_validations=len(reviews)-single,
                  changed_outcome_contexts=manifest['changedWinnerOrCloseContexts'], remaining_validation_contexts=manifest['remainingValidationContexts'],
                  applied_evidence_rows=len(affected), evidence_counts=dict(counts), serving_artifact_sha256=sha(output),
                  serving_artifact_bytes=output.stat().st_size, **modified)
    serving_metadata.update(forecast_validation=report, evidence_counts=dict(counts), serving_artifact_sha256=report['serving_artifact_sha256'],
                            serving_artifact_bytes=report['serving_artifact_bytes'])
    metadata_path.write_text(json.dumps(serving_metadata, indent=2, sort_keys=True) + '\n')
    output.with_suffix('.forecast-validation.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, indent=2))
    return report
