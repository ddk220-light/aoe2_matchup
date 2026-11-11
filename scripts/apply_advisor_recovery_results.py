"""Publish separately versioned, complete recovery evidence; never run battles.

The frozen forecast importer deliberately remains strict. This additive import
preserves its reviews and records recovery provenance under a separate key.
"""
import argparse
from collections import Counter
from contextlib import closing
import gzip
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {'frozen-civ-matchups-v3', 'forecast-recovery-inherited-ranged-core-v1',
            'forecast-recovery-path-patrol-v2', 'forecast-recovery-local-refinement-v3'}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(item):
    summary, job, review = (item[k] for k in ('summary', 'job', 'review'))
    rows = [r['record'] for r in item['runs']]
    assert summary['complete'] and not summary.get('requiredSeeds', [])
    assert review['samplingDecision']['requiredSeeds'] == []
    assert review['status'] == 'candidate_protocol_complete'
    assert review['frozenCampaignResult'] is False
    assert review['exactReplay'] == dict(required=False, performed=False, exact=None)
    assert summary['jobId'] == job['id'] == review['jobId']
    assert review['contextHash'] == job['contextHash']
    seeds = {r['seed']: r for r in rows}
    assert len(seeds) == len(rows) == len(summary['seeds']), 'duplicate or missing seed'
    for row, reference in zip(rows, summary['seeds']):
        assert row['physicsVersion'] in VERSIONS
        assert row['contextHash'] == job['contextHash']
        assert row['profileHashes'] == job['context']['profiles']
        assert row['counts'] == job['context']['counts']
        assert row['scenarioHash'] == job['context']['scenarioHash']
        assert row['pairKey'] == job['pairKey']
        assert row['finishedAt'] and not row.get('watchdog')
        assert row['outcome'] in ('win', 'loss', 'draw')
        assert row['ticks'] > 0 and row['simulationSeconds'] == row['ticks'] / 60
        assert all(row[k] == reference[k] for k in ('seed', 'winnerOwner', 'physicsVersion'))
        for key in ('finalStateHash', 'eventLogHash'):
            assert re.fullmatch('[0-9a-f]{64}', row[key])
            if key in reference:
                assert row[key] == reference[key]
        assert [row[s + 'RemainingHp'] for s in ('unit', 'opponent')] == reference['hp']
        for side in ('unit', 'opponent'):
            hp, start = row[side + 'RemainingHp'], row[side + 'StartingHp']
            assert math.isfinite(hp) and 0 <= hp <= start and start > 0
            assert isinstance(row[side + 'Survivors'], int) and row[side + 'Survivors'] >= 0
        if row['winnerOwner'] in (2, 3):
            loser = 'opponent' if row['winnerOwner'] == 2 else 'unit'
            assert row[loser + 'Survivors'] == row[loser + 'RemainingHp'] == 0
        else:
            assert row['unitSurvivors'] == row['opponentSurvivors'] == 0
    assert set(summary['physicsVersions']) == {r['physicsVersion'] for r in rows}
    single = summary['evidenceLevel'] == 'single_seed_confirmation'
    if single:
        assert set(seeds) == {0}
        first = seeds[0]; assert first['winnerOwner'] in (2, 3)
        winner = 'unit' if first['winnerOwner'] == 2 else 'opponent'
        assert first[winner + 'RemainingHp'] >= .25 * first[winner + 'StartingHp']
        assert not summary['changed']
    else:
        assert {0, 1, 2} <= set(seeds)
        expected = set(range(10)) if len({seeds[s]['winnerOwner'] for s in range(3)}) > 1 else {0, 1, 2}
        assert set(seeds) == expected, 'incomplete or extra seeds'
    owners = {r['winnerOwner'] for r in rows}; owner = next(iter(owners))
    outcome = ('a_win' if job['context']['profiles'][owner - 2] == job['pairKey'].split('|')[0] else 'b_win') if len(owners) == 1 and owner in (2, 3) else 'close_uncertain'
    assert summary['outcome'] == review['outcome'] == outcome
    assert summary['changed'] == any(old != outcome for old in summary['originalOutcomes'])
    assert summary['mixedWinners'] == (len(owners) > 1)
    assert set(job['context']['profiles']) == set(job['pairKey'].split('|'))


def apply(baseline, snapshot, output):
    assert baseline.resolve() != output.resolve() and not output.exists()
    authorization = json.loads((snapshot / 'authorization.json').read_text())
    assert authorization['ownerInstruction'] == 'Push and deploy'
    assert sha(baseline) == authorization['baselineDatabaseSha256']
    assert sha(snapshot / 'release-bundle.json.gz') == authorization['bundleSha256']
    assert sha(snapshot / 'verification.json') == authorization['sourceVerificationSha256']
    verification = json.loads((snapshot / 'verification.json').read_text())
    for name, digest in verification['outputSha256'].items():
        assert sha(snapshot / name) == digest
    bundle = json.loads(gzip.decompress((snapshot / 'release-bundle.json.gz').read_bytes()))
    assert len({x['job']['id'] for x in bundle}) == len(bundle) == verification['contexts'] == 36
    assert [x['summary'] for x in bundle] == json.loads((snapshot / 'matchup-reviews.json').read_text())
    records = [json.loads(line) for line in gzip.decompress((snapshot / 'runs.jsonl.gz').read_bytes()).splitlines()]
    assert [r for x in bundle for r in x['runs']] == records
    for item in bundle:
        validate(item)
    assert sum(i['summary']['evidenceLevel'] == 'single_seed_confirmation' for i in bundle) == verification['singleSeedConfirmations'] == 11
    assert sum(i['summary']['changed'] for i in bundle) == verification['changed'] == 2
    assert sum(i['summary']['mixedWinners'] for i in bundle) == verification['mixedWinners'] == 1
    assert sum(len(i['summary']['physicsVersions']) > 1 for i in bundle) == verification['mixedEngineVersionSets'] == 6
    assert len(records) == verification['individualSeedRecords'] == 93
    # The engine's pure canonical serializer handles JS float representation;
    # importing it does not construct or execute a simulation.
    subprocess.run(['node', str(ROOT / 'scripts/verify_advisor_recovery_bundle.mjs'), str(snapshot / 'release-bundle.json.gz')], check=True)
    counts = Counter(); affected = {}; examples = []
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        pending = Path(directory) / 'recovery.db'; shutil.copyfile(baseline, pending)
        with closing(sqlite3.connect(pending)) as db, closing(sqlite3.connect(f'file:{baseline}?mode=ro', uri=True)) as old:
            dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
            decode = lambda blob: json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            originals = {i: (blob, decode(blob)) for i, blob in db.execute('SELECT id,data FROM evidence')}
            units = {i: json.loads(data) for i, data in db.execute('SELECT id,data FROM units')}
            for item in bundle:
                summary, job = item['summary'], item['job']
                matches = [(i, row) for i, (_, row) in originals.items() if row.get('context') == job['context'] and row.get('pairKey') == job['pairKey']]
                assert len(matches) == 1, 'physical context is not unique'
                identifier, original = matches[0]
                assert identifier not in affected and original['evidenceType'] == 'predicted_unvalidated'
                assert original['outcome'] in summary['originalOutcomes']
                affected[identifier] = item
                cells = db.execute('SELECT * FROM cells WHERE evidence_id=? ORDER BY a,b', (identifier,)).fetchall()
                assert len(cells) == summary['displayedCells']
                validation = dict(status='recovery_simulation_checked', jobId=job['id'], contextHash=job['contextHash'],
                    evidenceLevel=summary['evidenceLevel'], physicsVersions=summary['physicsVersions'],
                    mixedEngineVersions=len(summary['physicsVersions']) > 1, frozenCampaignResult=False,
                    sourceCommit=authorization['sourceResearchCommit'], sourceSnapshot=authorization['sourceSnapshot'],
                    releaseAuthorization=authorization, originalCellFlagsAndTiers=sorted({(c[7], c[6]) for c in cells}),
                    review=item['review'], reviewSource=item['reviewSource'], measuredRecords=item['runs'],
                    earlierEngineComparison=summary.get('earlierEngineComparison', []), exactReplay=item['review']['exactReplay'])
                updated = dict(original, originalEvidence=original, recoveryValidation=validation,
                    outcome=summary['outcome'], evidenceType='observed', needsValidation=False, verified=True,
                    validationRunIds=[f"{job['id']}:{r['record']['seed']}" for r in item['runs']])
                compressor = zlib.compressobj(9, zdict=dictionary)
                db.execute('UPDATE evidence SET data=? WHERE id=?', (compressor.compress(encode(updated).encode()) + compressor.flush(), identifier))
                winner = job['pairKey'].split('|')[0 if summary['outcome'] == 'a_win' else 1] if summary['outcome'] in ('a_win', 'b_win') else None
                for a, b, before, _, ca, cb, _, _, _ in cells:
                    for unit, count in ((a, ca), (b, cb)):
                        assert count == job['context']['counts'][job['context']['profiles'].index(units[unit]['profileHash'])]
                    outcome = ('a_win' if units[a]['profileHash'] == winner else 'b_win') if winner else summary['outcome']
                    db.execute("UPDATE cells SET outcome=?,evidence_type='observed',tier='',flags=0 WHERE a=? AND b=?", (outcome, a, b))
                    counts['reviewedCells'] += 1; counts['changedOutcomeCells'] += outcome != before
                examples.append(dict(evidenceId=identifier, jobId=job['id'], label=summary['label'], outcome=summary['outcome'], changed=summary['changed']))
            # Full-grid comparison, including every previously published blob.
            for identifier, blob in db.execute('SELECT id,data FROM evidence'):
                before_blob, before = originals[identifier]
                if identifier not in affected:
                    assert blob == before_blob
                    counts['untouchedEvidenceRowsByteIdentical'] += 1
                    counts['priorForecastReviewsPreserved'] += bool(before.get('forecastValidation'))
                    counts['priorMismatchReviewsPreserved'] += bool(before.get('mismatchValidation'))
                else:
                    row = decode(blob); assert row['originalEvidence'] == before
                    for key in before.keys() - {'outcome', 'evidenceType', 'needsValidation', 'verified', 'validationRunIds'}:
                        assert row[key] == before[key]
            for before, after in zip(old.execute('SELECT * FROM cells ORDER BY a,b'), db.execute('SELECT * FROM cells ORDER BY a,b')):
                if before[8] not in affected:
                    assert before == after; counts['untouchedCellsIdentical'] += 1
                else:
                    assert before[:2] == after[:2] and before[4:6] == after[4:6] and before[8] == after[8]
            assert list(old.execute('SELECT * FROM units ORDER BY id')) == list(db.execute('SELECT * FROM units ORDER BY id'))
            assert counts['reviewedCells'] == 220 and len(affected) == 36
            evidence_counts = Counter(decode(blob)['evidenceType'] for (blob,) in db.execute('SELECT data FROM evidence'))
            assert evidence_counts['predicted_unvalidated'] == 0
            report = dict(status='passed', sourceResearchCommit=authorization['sourceResearchCommit'],
                sourceSnapshot=authorization['sourceSnapshot'], reviewedContexts=36, singleSeedConfirmations=11,
                multiSeedValidations=25, changedOutcomeContexts=2, retainedForecasts=34, mixedWinnerContexts=1,
                mixedEngineVersionSets=6, individualSeedRecords=93, remainingForecastContexts=0,
                frozenCampaignUnchanged=True, simulationExecutions=0, **counts, contexts=examples)
            metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
            metadata.update(recovery_validation=report, remainingPredictionValidation=0, predictionTiers={},
                evidenceCounts=dict(evidence_counts), displayedEvidenceCounts=dict(db.execute('SELECT evidence_type,COUNT(*) FROM cells GROUP BY evidence_type')),
                forecastCoverage=dict(totalContexts=39148, frozenProtocolContexts=39112, recoveryContexts=36,
                    singleSeedConfirmations=31906, multiSeedValidations=7242, remainingContexts=0))
            db.execute("UPDATE metadata SET value=? WHERE key='dataset'", (encode(metadata),))
            db.commit(); assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            db.execute('PRAGMA page_size=32768'); db.execute('VACUUM')
        assert pending.stat().st_size < 100 * 1024 * 1024
        pending.replace(output)
    report.update(baselineDatabaseSha256=sha(baseline), servingDatabaseSha256=sha(output), servingDatabaseBytes=output.stat().st_size)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'snapshot', 'output', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    assert not args.report.exists()
    result = apply(args.baseline, args.snapshot, args.output)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'contexts'}, indent=2))
