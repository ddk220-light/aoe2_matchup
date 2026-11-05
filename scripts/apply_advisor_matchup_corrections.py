"""Apply an independently verified simulation snapshot to a copy of the advisor DB.

Frozen first-pass data and old predictions remain reconstructible. The public
rendering stays unchanged; only battle outcomes and internal evidence advance.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import zlib


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(baseline, snapshot, output):
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    for file, expected in manifest['files'].items():
        assert sha(snapshot / file) == expected, ('snapshot hash mismatch', file)
    assert manifest['version'] == 'civ-matchup-mismatch-corrections-v1'
    assert manifest['physicsVersion'] == 'frozen-civ-matchups-v3'
    assert sha(baseline) == manifest['originalDatabaseSha256'], 'baseline is not the frozen comparison input'
    with gzip.open(snapshot / 'reviewed-contexts.jsonl.gz', 'rt') as f:
        reviews = [json.loads(line) for line in f]
    assert len(reviews) == manifest['reviewedContexts']
    assert len({r['jobId'] for r in reviews}) == len(reviews)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = output.with_suffix('.metadata.json')
    serving_metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    pending = output.with_suffix('.next.db')
    pending.unlink(missing_ok=True)
    shutil.copyfile(baseline, pending)
    db = sqlite3.connect(pending)
    dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    units = {i: json.loads(data) for i, data in db.execute('SELECT id,data FROM units')}
    modified = collections.Counter()
    affected_evidence = set()
    for review in reviews:
        assert review['status'] == 'passed' and review['exactReplay']['exact']
        assert review['campaignHash'] == manifest['campaignHash']
        assert not review['requiredSeeds'] and review['seedCount'] in (3, 10)
        assert review['physicsVersion'] == manifest['physicsVersion']
        assert {s['seed'] for s in review['seedResults']} == set(range(review['seedCount']))
        assert set(review['context']['profiles']) == set(review['pairKey'].split('|'))
        expected_original = {x['evidenceId']: x['evidence'] for x in review['originalEvidence']}
        for evidence_id in review['originalEvidenceIds']:
            assert evidence_id not in affected_evidence, 'context applied twice'
            affected_evidence.add(evidence_id)
            blob = db.execute('SELECT data FROM evidence WHERE id=?', (evidence_id,)).fetchone()[0]
            original = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            assert original == expected_original[evidence_id], 'original evidence changed'
            assert original['context'] == review['context'], 'physical context mismatch'
            assert original['pairKey'] == review['pairKey']
            evidence_type = 'identity' if original['evidenceType'] == 'identity' else 'observed'
            assert (review['outcome'] == 'equivalent') == (evidence_type == 'identity')
            old_flags = db.execute('SELECT DISTINCT flags,tier FROM cells WHERE evidence_id=?', (evidence_id,)).fetchall()
            updated = dict(original, outcome=review['outcome'], evidenceType=evidence_type,
                           needsValidation=False, verified=True,
                           originalEvidence=original,
                           mismatchValidation=dict(status='simulation_checked', campaignHash=manifest['campaignHash'],
                               sourceCommit=manifest['sourceCommit'], physicsVersion=manifest['physicsVersion'],
                               jobId=review['jobId'], reviewHash=review['reviewHash'], reviewFile=review['reviewFile'],
                               reviewFileSha256=review['reviewFileSha256'], seedResults=review['seedResults'],
                               originalCellFlagsAndTiers=old_flags, exactReplay=review['exactReplay']))
            # Keep originalPrediction, sourceContext and sourceRunIds verbatim.
            # New measurement references are separate, never old-inference roots.
            updated['validationRunIds'] = [f"{review['jobId']}:{s['seed']}" for s in review['seedResults']]
            compressor = zlib.compressobj(9, zdict=dictionary)
            encoded = compressor.compress(encode(updated).encode()) + compressor.flush()
            db.execute('UPDATE evidence SET data=? WHERE id=?', (encoded, evidence_id))
            winner = review['pairKey'].split('|')[0 if review['outcome'] == 'a_win' else 1] if review['outcome'] in ('a_win', 'b_win') else None
            cells = db.execute('SELECT a,b,outcome,count_a,count_b FROM cells WHERE evidence_id=?', (evidence_id,)).fetchall()
            for a, b, old_outcome, count_a, count_b in cells:
                assert {units[a]['profileHash'], units[b]['profileHash']} == set(review['context']['profiles'])
                for unit_id, count in ((a, count_a), (b, count_b)):
                    assert count == review['context']['counts'][review['context']['profiles'].index(units[unit_id]['profileHash'])]
                outcome = ('a_win' if units[a]['profileHash'] == winner else 'b_win') if winner else review['outcome']
                modified['reviewed_cells'] += 1
                modified['changed_outcome_cells'] += old_outcome != outcome
                modified['newly_measured_cells'] += original['evidenceType'] not in ('observed', 'identity')
                db.execute('UPDATE cells SET outcome=?,evidence_type=?,tier=?,flags=? WHERE a=? AND b=?',
                           (outcome, evidence_type, '', 0, a, b))
    metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
    assert db.execute('SELECT COUNT(*) FROM cells').fetchone()[0] == 151223
    assert db.execute('SELECT COUNT(*) FROM units').fetchone()[0] == 555
    assert db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == 68916
    evidence_counts = collections.Counter()
    prediction_tiers = collections.Counter()
    for (blob,) in db.execute('SELECT data FROM evidence'):
        row = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
        evidence_counts[row['evidenceType']] += 1
        if row['evidenceType'] == 'predicted_unvalidated':
            prediction_tiers[row.get('predictionTier', '')] += 1
    original_summary = {k: metadata.get(k) for k in ('evidenceCounts', 'predictionTiers', 'remainingPredictionValidation')}
    displayed_counts = dict(db.execute('SELECT evidence_type,COUNT(*) FROM cells GROUP BY evidence_type'))
    metadata.update(mismatch_validation=dict(manifest, appliedEvidenceRows=len(affected_evidence), **modified),
                    originalFirstPassCounts=original_summary,
                    evidenceCounts=dict(evidence_counts), predictionTiers=dict(prediction_tiers),
                    displayedEvidenceCounts=displayed_counts,
                    remainingPredictionValidation=evidence_counts['predicted_unvalidated'])
    db.execute("UPDATE metadata SET value=? WHERE key='dataset'", (encode(metadata),))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    db.execute('VACUUM'); db.close()
    pending.replace(output)
    report = dict(campaign_hash=manifest['campaignHash'], validation_source_commit=manifest['sourceCommit'],
                  reviewed_contexts=len(reviews), remaining_validation_contexts=manifest['remainingValidationContexts'],
                  evidence_counts=dict(evidence_counts), serving_artifact_sha256=sha(output),
                  serving_artifact_bytes=output.stat().st_size, **modified)
    serving_metadata.update(variants=555, civilization_pairs=1540, displayed_cells=151223, profile_pairs=68916,
                            unresolved_pairs=0, provisional=True, schema_version=1,
                            evidence_counts=dict(evidence_counts),
                            serving_artifact_sha256=report['serving_artifact_sha256'],
                            serving_artifact_bytes=report['serving_artifact_bytes'], mismatch_validation=report)
    metadata_path.write_text(json.dumps(serving_metadata, indent=2, sort_keys=True) + '\n')
    output.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    apply(args.baseline, args.snapshot, args.output)
