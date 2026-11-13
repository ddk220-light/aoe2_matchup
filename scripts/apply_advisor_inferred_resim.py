"""Replace the advisor's 19,647 rule-inferred cells with the owner's PC re-simulation.

Input: the published run directory ``data/matchup_runs/inferred-2026-resim-pc`` of
branch ``matchup-runs`` (commit 72d55423f; extract it with
``git archive 72d55423f data/matchup_runs/inferred-2026-resim-pc | tar -x -C DIR``).
It holds 10,191 reviewed contexts (one-three-ten sampling, seed 0 first) plus, for
the two contexts whose seed 0 hit every watchdog step, the owner-requested seed-1
results in ``alternate-seed-1/`` (labelled ``owner_requested_alternate_seed``).

Every inferred evidence row (10,193 contexts) becomes ``observed``: the outcome is
recomputed from the per-seed records (unanimous winner -> a_win/b_win by the sorted
``pairKey``; mixed winners -> close_uncertain), the original inferred row is kept as
``originalEvidence`` and ``inferredResimValidation.seedResults`` carries each seed's
winner, winner HP fraction and both armies' starting/remaining HP and survivors
(owner 2 = ``context.profiles[0]``). Cells keep their units, counts and evidence id;
no other cell or evidence row may change (checked over the full grid).
No simulation is executed here.

Usage: python scripts/apply_advisor_inferred_resim.py --baseline OLD.db --snapshot RUN_DIR \
           --output data/golden/civ_matchups_first_pass.db --report REPORT.json
"""
import argparse
from collections import Counter
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zlib

RUN_ID = 'inferred-2026-resim-pc'
SNAPSHOT_HASH = '673d7f8a27bc5a1bc3fa38db70d293602cf3dd28f19766778a670ae1d0edbeca'
PUBLICATION_COMMIT = '72d55423ff2455f678acf91038eaabcf313f4b36'  # origin/matchup-runs
PUBLICATION_PATH = 'data/matchup_runs/inferred-2026-resim-pc'
PHYSICS = 'frozen-civ-matchups-v3'
RUN_SHORT = f'{RUN_ID}@{SNAPSHOT_HASH[:12]}'
COMMIT_SHORT = PUBLICATION_COMMIT[:9]
CONTEXTS, CELLS, SEEDS, ALTERNATES = 10193, 19647, 10550, 2
HP_FIELDS = ('unitStartingHp', 'opponentStartingHp', 'unitRemainingHp', 'opponentRemainingHp',
             'unitSurvivors', 'opponentSurvivors')


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsonl(path):
    raw = path.read_bytes()
    text = gzip.decompress(raw).decode() if path.suffix == '.gz' else raw.decode()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def outcome_of(records, pair_key, profiles):
    owners = {r['winnerOwner'] for r in records}
    if len(owners) != 1 or next(iter(owners)) not in (2, 3):
        return 'close_uncertain'
    return 'a_win' if profiles[next(iter(owners)) - 2] == pair_key.split('|')[0] else 'b_win'


def seed_result(record):
    owner = record['winnerOwner']
    side = {2: 'unit', 3: 'opponent'}.get(owner)
    fraction = record[side + 'RemainingHp'] / record[side + 'StartingHp'] if side else None
    # Hashes, timings and engine identity stay in the run journal (validationRunIds -> runs.jsonl.gz):
    # the serving DB must stay under GitHub's 100 MiB file limit.
    return dict({k: record[k] for k in ('seed', 'winnerOwner', 'ticks', *HP_FIELDS)}, winnerHpFraction=fraction)


def load_snapshot(snapshot):
    """Verified inputs: {jobId: (job, result-or-None, [run records], provenance)}."""
    publication = json.loads((snapshot / 'publication-manifest.json').read_text())
    assert publication['runId'] == RUN_ID and publication['originalSnapshotHash'] == SNAPSHOT_HASH
    for name, entry in publication['files'].items():
        assert sha(snapshot / name) == entry['sha256'], ('publication file hash mismatch', name)
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    assert manifest['snapshotHash'] == SNAPSHOT_HASH and manifest['runId'] == RUN_ID
    for name, entry in manifest['files'].items():
        assert sha(snapshot / name) == entry['sha256'], ('export file hash mismatch', name)
    assert manifest['counts']['contexts'] == CONTEXTS and manifest['counts']['seeds'] == SEEDS
    final = json.loads((snapshot / 'verification/final-verification.json').read_text())
    assert final['snapshotHash'] == SNAPSHOT_HASH and final['exportMatchesRawSeeds'] and final['exportHashesValid']
    assert final['displayedCells'] == CELLS and final['allContextsAccountedFor']
    coverage = json.loads((snapshot / 'alternate-seed-1/coverage-verification.json').read_text())
    assert coverage['totalObservedContexts'] == CONTEXTS and coverage['hpSurvivorsAndHashesMatchRawResults']

    fields = manifest['seedFields']
    jobs = {j['id']: j for j in jsonl(snapshot / 'evidence/jobs.jsonl.gz')}
    results = jsonl(snapshot / 'results.jsonl.gz')
    runs = jsonl(snapshot / 'evidence/runs.jsonl.gz')
    blocked = jsonl(snapshot / 'blocked.jsonl.gz')
    assert len(jobs) == CONTEXTS and len(runs) == SEEDS and len(results) + len(blocked) == CONTEXTS
    by_job = {}
    for run in runs:
        assert run['runId'] == RUN_ID and run['purpose'] == 'fresh_measurement' and run['finishedAt']
        assert run['physicsVersion'] == PHYSICS and run['executionVersion'] == 'lossless-event-stream-v1'
        key = (run['matchupId'], run['seed'])
        assert key not in by_job, 'duplicate seed'
        by_job[key] = run
    contexts = {}
    used = set()
    for row in results:
        job = jobs[row['jobId']]
        assert row['jobId'] not in contexts and row['orientation'] == 'same' and row['evidenceType'] == 'observed'
        assert row['contextHash'] == job['contextHash'] and row['pairKey'] == job['pairKey']
        records = []
        for compact in row['seeds']:
            seed = dict(zip(fields, compact))
            run = by_job[(row['jobId'], seed['seed'])]
            used.add((row['jobId'], seed['seed']))
            assert all(run[k] == seed[k] for k in fields), 'export differs from the run journal'
            records.append(run)
        seeds = {r['seed'] for r in records}
        if row['evidenceLevel'] == 'single_seed_confirmation':
            first = records[0]
            assert seeds == {0} and first['winnerOwner'] in (2, 3)
            win, lose = ('unit', 'opponent') if first['winnerOwner'] == 2 else ('opponent', 'unit')
            assert first[lose + 'Survivors'] == first[lose + 'RemainingHp'] == 0
            assert first[win + 'RemainingHp'] >= .25 * first[win + 'StartingHp'] > 0
        else:
            assert row['evidenceLevel'] == 'multi_seed_validation' and {0, 1, 2} <= seeds
            mixed = len({r['winnerOwner'] for r in records if r['seed'] < 3}) > 1
            assert seeds == (set(range(10)) if mixed else {0, 1, 2})
        assert outcome_of(records, job['pairKey'], job['profileHashes']) == row['outcome']
        contexts[row['jobId']] = (job, row, sorted(records, key=lambda r: r['seed']), 'original_campaign')
    assert used == set(by_job), 'run records outside the export'

    alt_runs = jsonl(snapshot / 'alternate-seed-1/runs.jsonl')
    alt_raw = {r['key']: r['result'] for r in jsonl(snapshot / 'alternate-seed-1/results.jsonl')}
    alt_jobs = {j['id']: j for j in json.loads((snapshot / 'alternate-seed-1/contexts.json').read_text())}
    assert {b['jobId'] for b in blocked} == {r['matchupId'] for r in alt_runs} == set(alt_jobs) and len(alt_runs) == ALTERNATES
    for run in alt_runs:
        job = jobs[run['matchupId']]
        assert alt_jobs[job['id']] == job and run['purpose'] == 'alternate_seed_probe' and run['seed'] == 1
        assert run['sourceRunId'] == RUN_ID and run['physicsVersion'] == PHYSICS
        assert run['contextHash'] == job['contextHash'] and run['profileHashes'] == job['profileHashes']
        assert run['counts'] == job['counts'] and run['teamKeys'] == job['teamKeys']
        raw = alt_raw[f"{job['id']}-seed1"]
        assert raw['winnerOwner'] == run['winnerOwner'] and raw['ticks'] == run['ticks']
        assert [raw['startingHpByOwner'][o] for o in '23'] == [run['unitStartingHp'], run['opponentStartingHp']]
        assert [raw['remainingByOwner'][o]['hp'] for o in '23'] == [run['unitRemainingHp'], run['opponentRemainingHp']]
        assert [raw['remainingByOwner'][o]['units'] for o in '23'] == [run['unitSurvivors'], run['opponentSurvivors']]
        assert raw['finalStateHash'] == run['finalStateHash'] and raw['eventLogHash'] == run['eventLogHash']
        assert job['id'] not in contexts
        contexts[job['id']] = (job, None, [run], 'owner_requested_alternate_seed')
    assert len(contexts) == CONTEXTS
    blocked = {b['jobId']: b for b in blocked}
    return contexts, blocked, manifest, publication


def apply(baseline, snapshot, output):
    contexts, blocked, manifest, publication = load_snapshot(snapshot)
    assert baseline.resolve() != output.resolve(), 'immutable baseline must be separate from output'
    counts = Counter(); changed_examples = []; affected = {}
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        pending = Path(directory) / 'inferred-resim.db'; shutil.copyfile(baseline, pending)
        with closing(sqlite3.connect(pending)) as db, closing(sqlite3.connect(f'file:{baseline}?mode=ro', uri=True)) as old:
            dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
            decode = lambda blob: json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            originals = {i: (blob, decode(blob)) for i, blob in db.execute('SELECT id,data FROM evidence')}
            units = {i: json.loads(data) for i, data in db.execute('SELECT id,data FROM units')}
            by_key = {u['key']: u for u in units.values()}
            by_context = {}
            for identifier, (_, row) in originals.items():
                if row['evidenceType'] == 'inferred':
                    ctx = row['context']
                    key = (row['pairKey'], tuple(ctx['profiles']), tuple(ctx['counts']), ctx['scenarioHash'])
                    assert key not in by_context, 'inferred context is not unique'
                    by_context[key] = identifier
            assert len(by_context) == CONTEXTS
            for job_id, (job, result, records, provenance) in sorted(contexts.items()):
                context = {k: job[k] for k in ('engineFamily', 'family', 'policy', 'scenarioHash', 'counts', 'weightedCosts')}
                context['profiles'] = job['profileHashes']
                identifier = by_context.pop((job['pairKey'], tuple(context['profiles']), tuple(context['counts']), context['scenarioHash']))
                original = originals[identifier][1]
                assert original['context'] == context and (result is None or result['context'] == context)
                for name, profile in zip(job['teamKeys'], job['profileHashes']):
                    assert by_key[name]['profileHash'] == profile, ('teamKeys do not match the profiles', name)
                cells = db.execute('SELECT * FROM cells WHERE evidence_id=? ORDER BY a,b', (identifier,)).fetchall()
                assert len(cells) == job['displayedCells'] and all(c[3] == 'inferred' for c in cells)
                outcome = outcome_of(records, job['pairKey'], job['profileHashes'])
                if result is not None:
                    assert result['priorOutcomes'] == [original['outcome']], 'prior is not the published inferred outcome'
                    assert result['changed'] == (outcome != original['outcome'])
                    level, decision, policy = result['evidenceLevel'], result['samplingDecision'], result['samplingPolicy']
                else:
                    level, decision, policy = 'single_alternate_seed', None, 'owner_requested_alternate_seed'
                    record = records[0]
                    win, lose = ('unit', 'opponent') if record['winnerOwner'] == 2 else ('opponent', 'unit')
                    assert record[lose + 'Survivors'] == record[lose + 'RemainingHp'] == 0
                assert {(c[7], c[6]) for c in cells} == {(0, '')}
                assert {r['nodeVersion'] for r in records} == {'v24.22.1'}
                # Compact per-row provenance; the run-level constants (full hashes, engine,
                # source branch/path) live once in metadata dataset.inferred_resim_validation.
                validation = dict(
                    status='simulation_checked', provenance=provenance, run=RUN_SHORT, sourceCommit=COMMIT_SHORT,
                    jobId=job_id, evidenceLevel=level, samplingReason=decision and decision['reason'],
                    priorOutcome=original['outcome'], seedResults=[seed_result(r) for r in records])
                if provenance == 'owner_requested_alternate_seed':
                    b = blocked[job_id]
                    validation['seed0'] = dict(status='blocked_watchdog', failedAttempts=b['failedAttempts'],
                                               lastLimitSeconds=b['lastLimitSeconds'])
                updated = dict(original, originalEvidence=original, inferredResimValidation=validation,
                               outcome=outcome, evidenceType='observed', needsValidation=False, verified=True,
                               validationRunIds=[f"{job_id}:{r['seed']}" for r in records])
                compressor = zlib.compressobj(9, zdict=dictionary)
                db.execute('UPDATE evidence SET data=? WHERE id=?', (compressor.compress(encode(updated).encode()) + compressor.flush(), identifier))
                affected[identifier] = job_id
                winner = job['pairKey'].split('|')[0 if outcome == 'a_win' else 1] if outcome in ('a_win', 'b_win') else None
                for a, b, before, _, ca, cb, _, _, _ in cells:
                    for unit, count in ((a, ca), (b, cb)):
                        assert count == job['counts'][job['profileHashes'].index(units[unit]['profileHash'])], 'count mismatch'
                    counts['teamKeyCellsChecked'] += {units[a]['key'], units[b]['key']} == set(job['teamKeys'])
                    cell = ('a_win' if units[a]['profileHash'] == winner else 'b_win') if winner else outcome
                    db.execute("UPDATE cells SET outcome=?,evidence_type='observed',tier='',flags=0 WHERE a=? AND b=?", (cell, a, b))
                    counts['reviewedCells'] += 1; counts['changedOutcomeCells'] += cell != before
                    counts[f'cellOutcome:{cell}'] += 1
                counts['reviewedContexts'] += 1; counts[f'provenance:{provenance}'] += 1
                counts[f'evidenceLevel:{level}'] += 1; counts[f'contextOutcome:{outcome}'] += 1
                counts['seedRecords'] += len(records)
                if outcome != original['outcome']:
                    counts['changedOutcomeContexts'] += 1
                    changed_examples.append(dict(evidenceId=identifier, jobId=job_id, teamKeys=job['teamKeys'],
                                                 prior=original['outcome'], outcome=outcome, cells=len(cells)))
            assert not by_context, 'inferred contexts without a result'
            # Full-grid comparison against the baseline.
            for identifier, blob in db.execute('SELECT id,data FROM evidence'):
                before_blob, before = originals[identifier]
                if identifier not in affected:
                    assert blob == before_blob
                    counts['untouchedEvidenceRowsByteIdentical'] += 1
                else:
                    row = decode(blob); assert row['originalEvidence'] == before
                    for key in before.keys() - {'outcome', 'evidenceType', 'needsValidation', 'verified'}:
                        assert row[key] == before[key]
            for before, after in zip(old.execute('SELECT * FROM cells ORDER BY a,b'), db.execute('SELECT * FROM cells ORDER BY a,b'), strict=True):
                if before[8] not in affected:
                    assert before == after; counts['untouchedCellsIdentical'] += 1
                else:
                    assert before[:2] == after[:2] and before[4:6] == after[4:6] and before[8] == after[8]
                    assert before[3] == 'inferred' and after[3] == 'observed' and after[6:8] == ('', 0)
            assert list(old.execute('SELECT * FROM units ORDER BY id')) == list(db.execute('SELECT * FROM units ORDER BY id'))
            assert counts['reviewedCells'] == CELLS and len(affected) == CONTEXTS
            assert counts['untouchedCellsIdentical'] == 151223 - CELLS
            evidence_counts = Counter(decode(blob)['evidenceType'] for (blob,) in db.execute('SELECT data FROM evidence'))
            assert 'inferred' not in evidence_counts
            report = dict(
                status='passed', description=('Owner PC re-simulation of the 10,193 rule-inferred contexts '
                    '(19,647 displayed cells): frozen-civ-matchups-v3 engine, frozen 2026 mechanics/scenarios/army '
                    'counts, one-three-ten sampling; the two contexts whose seed 0 exhausted every watchdog step use '
                    'the owner-requested seed-1 results (provenance owner_requested_alternate_seed).'),
                runId=RUN_ID, runHash=manifest['runHash'], snapshotHash=SNAPSHOT_HASH, sourceCommit=PUBLICATION_COMMIT,
                sourceBranch='matchup-runs', sourcePath=PUBLICATION_PATH, runSourceCommit=publication['sourceCommit'],
                physicsVersion=PHYSICS, engineId=manifest['engine']['engineId'],
                executionVersion=manifest['engine']['executionVersion'], nodeVersion='v24.22.1',
                alternateSeedSource=PUBLICATION_PATH + '/alternate-seed-1/runs.jsonl',
                rowFields=dict(run=f'{RUN_ID}@<snapshotHash[:12]>', sourceCommit='commit[:9]',
                               ownerOrientation='seedResults winnerOwner 2 = context.profiles[0], 3 = context.profiles[1]',
                               journal='validationRunIds <jobId>:<seed> -> evidence/runs.jsonl.gz (hashes, timings)',
                               originalCellFlagsAndTiers='all [0, ""]'),
                simulationExecutions=0, **dict(sorted(counts.items())),
                changedContexts=changed_examples)
            metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
            metadata.update(inferred_resim_validation=report, evidenceCounts=dict(sorted(evidence_counts.items())),
                displayedEvidenceCounts=dict(db.execute('SELECT evidence_type,COUNT(*) FROM cells GROUP BY evidence_type ORDER BY 1')),
                scope=metadata['scope'] + ' Since 2026-11-13 every non-identity cell is a frozen V3 measurement '
                      '(the former rule-inferred cells were re-simulated; see inferred_resim_validation).')
            db.execute("UPDATE metadata SET value=? WHERE key='dataset'", (encode(metadata),))
            db.commit(); assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            db.execute('PRAGMA page_size=32768'); db.execute('VACUUM')
        assert pending.stat().st_size < 100 * 1024 * 1024, ('serving DB must stay under GitHub 100 MiB', pending.stat().st_size)
        pending.replace(output)
    report.update(baselineDatabaseSha256=sha(baseline), servingDatabaseSha256=sha(output), servingDatabaseBytes=output.stat().st_size)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ('baseline', 'snapshot', 'output', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    assert not args.report.exists()
    result = apply(args.baseline, args.snapshot, args.output)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'changedContexts'}, indent=2))
