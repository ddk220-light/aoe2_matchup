"""Read-only full-grid audit of an imported forecast snapshot; runs no battles."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo
import zlib


def audit(baseline, serving, snapshot, previous_snapshot=None):
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    with gzip.open(snapshot / 'reviewed-contexts.jsonl.gz', 'rt') as stream:
        reviews = [json.loads(line) for line in stream if line.strip()]
    expected = {identifier: review for review in reviews for identifier in review['originalEvidenceIds']}
    assert len(expected) == len(reviews) == manifest['reviewedContexts']
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha(baseline) == manifest['originalDatabaseSha256']
    for name, digest in manifest['files'].items():
        assert sha(snapshot / name) == digest, name
    counts = Counter()
    if previous_snapshot:
        current_by_job = {review['jobId']: review for review in reviews}
        with gzip.open(previous_snapshot / 'reviewed-contexts.jsonl.gz', 'rt') as stream:
            for line in stream:
                if not line.strip():
                    continue
                previous = json.loads(line)
                assert current_by_job[previous['jobId']] == previous, ('released review changed or missing', previous['jobId'])
                counts['previousReleasedForecastReviewsPreserved'] += 1
    examples = []
    with closing(sqlite3.connect(f'file:{baseline}?mode=ro', uri=True)) as old, closing(sqlite3.connect(f'file:{serving}?mode=ro', uri=True)) as new:
        assert new.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        dictionary = old.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        assert dictionary == new.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        decode = lambda blob: json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
        units = dict((row[0], json.loads(row[3])) for row in old.execute('SELECT * FROM units'))
        assert list(old.execute('SELECT * FROM units ORDER BY id')) == list(new.execute('SELECT * FROM units ORDER BY id'))
        old_rows = dict(old.execute('SELECT id,data FROM evidence'))
        new_rows = dict(new.execute('SELECT id,data FROM evidence'))
        assert old_rows.keys() == new_rows.keys()
        flags_by_evidence = defaultdict(set)
        for identifier, flags, tier in old.execute('SELECT evidence_id,flags,tier FROM cells'):
            flags_by_evidence[identifier].add((flags, tier))
        for identifier, blob in old_rows.items():
            original, updated = decode(blob), decode(new_rows[identifier])
            counts['priorMismatchReviewsPreserved'] += bool(original.get('mismatchValidation'))
            if identifier not in expected:
                assert blob == new_rows[identifier], ('unreviewed evidence changed', identifier)
                counts['untouchedEvidenceRowsByteIdentical'] += 1
                counts['remainingForecastContexts'] += original['evidenceType'] == 'predicted_unvalidated'
                continue
            review = expected[identifier]
            assert updated['originalEvidence'] == original
            validation = updated['forecastValidation']
            for key in ('jobId', 'reviewHash', 'contextHash', 'seedResults', 'exactReplay'):
                assert validation[key] == review[key], (identifier, key)
            assert validation['sourceCommit'] == manifest['sourceCommit']
            assert updated['context'] == original['context'] == review['context']
            assert updated['outcome'] == review['outcome']
            assert updated['evidenceType'] == 'observed' and updated['verified'] is True and updated['needsValidation'] is False
            for key, value in original.items():
                if key not in ('outcome', 'evidenceType', 'verified', 'needsValidation', 'validationRunIds'):
                    assert updated[key] == value, (identifier, key)
            original_flags = sorted(flags_by_evidence[identifier])
            assert sorted(map(tuple, validation['originalCellFlagsAndTiers'])) == original_flags
        old_cells = {(row[0], row[1]): row for row in old.execute('SELECT * FROM cells')}
        new_cells = {(row[0], row[1]): row for row in new.execute('SELECT * FROM cells')}
        assert old_cells.keys() == new_cells.keys()
        for key, before in old_cells.items():
            after = new_cells[key]
            if before[8] not in expected:
                assert before == after, ('unreviewed cell changed', key)
                counts['unchangedUnreviewedCells'] += 1
                counts['remainingForecastCells'] += before[3] == 'predicted_unvalidated'
                continue
            review = expected[before[8]]
            assert before[:2] == after[:2] and before[4:6] == after[4:6] and before[8] == after[8]
            assert after[3] == 'observed' and after[6:8] == ('', 0)
            winner = review['pairKey'].split('|')[0 if review['outcome'] == 'a_win' else 1] if review['outcome'] in ('a_win', 'b_win') else None
            outcome = ('a_win' if units[before[0]]['profileHash'] == winner else 'b_win') if winner else review['outcome']
            assert after[2] == outcome
            counts['reviewedCells'] += 1
            counts['changedOutcomeCells'] += before[2] != after[2]
            if before[2] != after[2] and len(examples) < 4:
                examples.append(dict(a=before[0], b=before[1], evidenceId=before[8], originalOutcome=before[2], outcome=after[2], jobId=review['jobId']))
        counts['reviewedContexts'] = len(reviews)
        counts['singleSeedConfirmations'] = sum(row.get('evidenceLevel') == 'single_seed_confirmation' for row in reviews)
        counts['multiSeedValidations'] = len(reviews) - counts['singleSeedConfirmations']
        counts['changedOutcomeContexts'] = sum(row['changed'] for row in reviews)
        counts['retainedForecastContexts'] = len(reviews) - counts['changedOutcomeContexts']
        counts['mixedResultContexts'] = sum(len({seed['winnerOwner'] for seed in row['seedResults']}) > 1 for row in reviews)
        assert counts['remainingForecastContexts'] == manifest['remainingValidationContexts']
        return dict(status='passed', verifiedAt=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(), baselineDatabaseSha256=sha(baseline), servingDatabaseSha256=sha(serving), sourceCommit=manifest['sourceCommit'], campaignHash=manifest['campaignHash'], **counts, fullMatrix=dict(units=len(units), cells=len(new_cells), evidenceRows=len(new_rows)), allOriginalFlagsPredictionsSourcesAndPhysicalContextsPreserved=True, simulationExecutionsForVerification=0, representativeChangedCells=examples)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'serving', 'snapshot', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--previous-snapshot', type=Path)
    args = parser.parse_args()
    result = audit(args.baseline, args.serving, args.snapshot, args.previous_snapshot)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
