"""The 10,193 formerly rule-inferred advisor contexts carry their PC re-simulation (2026-11-13).

Built by scripts/apply_advisor_inferred_resim.py from branch matchup-runs commit 72d55423f;
this checks the committed serving DB only (no run directory, no simulation).
"""
from collections import Counter
import json
import sqlite3
import zlib

from aoe2_api.services.advisor import DATASET

SNAPSHOT = '673d7f8a27bc5a1bc3fa38db70d293602cf3dd28f19766778a670ae1d0edbeca'


def test_resimulated_contexts_match_their_seed_records():
    with sqlite3.connect(DATASET) as db:
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
        units = {i: json.loads(data)['profileHash'] for i, data in db.execute('SELECT id,data FROM units')}
        cells = {}
        for a, b, outcome, evidence, ca, cb, tier, flags, eid in db.execute('SELECT * FROM cells'):
            cells.setdefault(eid, []).append((a, b, outcome, evidence, ca, cb, tier, flags))
        rows = {}
        for identifier, blob in db.execute('SELECT id,data FROM evidence'):
            row = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            if 'inferredResimValidation' in row:
                rows[identifier] = row
    report = metadata['inferred_resim_validation']
    assert report['snapshotHash'] == SNAPSHOT and report['sourceCommit'].startswith('72d55423f')
    assert (report['reviewedContexts'], report['reviewedCells'], report['seedRecords']) == (10193, 19647, 10552)
    assert (report['changedOutcomeContexts'], report['changedOutcomeCells']) == (4, 5)
    assert report['untouchedCellsIdentical'] == 151223 - 19647
    assert len(rows) == 10193
    counts = Counter()
    for identifier, row in rows.items():
        validation = row['inferredResimValidation']
        assert row['evidenceType'] == 'observed' and row['originalEvidence']['evidenceType'] == 'inferred'
        assert validation['run'] == 'inferred-2026-resim-pc@' + SNAPSHOT[:12]
        assert validation['priorOutcome'] == row['originalEvidence']['outcome']
        seeds = validation['seedResults']
        assert len({s['seed'] for s in seeds}) == len(seeds) >= 1
        assert row['validationRunIds'] == [f"{validation['jobId']}:{s['seed']}" for s in seeds]
        profiles, pair = row['context']['profiles'], row['pairKey'].split('|')
        owners = {s['winnerOwner'] for s in seeds}
        if len(owners) == 1 and owners <= {2, 3}:
            winner = profiles[owners.pop() - 2]
            assert row['outcome'] == ('a_win' if winner == pair[0] else 'b_win')
        else:
            winner = None
            assert row['outcome'] == 'close_uncertain'
        for s in seeds:
            side = {2: 'unit', 3: 'opponent'}[s['winnerOwner']]
            assert s['winnerHpFraction'] == s[side + 'RemainingHp'] / s[side + 'StartingHp']
            loser = 'opponent' if side == 'unit' else 'unit'
            assert s[loser + 'RemainingHp'] == 0
        counts[validation['provenance']] += 1
        for a, b, outcome, evidence, ca, cb, tier, flags in cells[identifier]:
            assert (evidence, tier, flags) == ('observed', '', 0)
            assert [ca, cb] == [row['context']['counts'][profiles.index(units[u])] for u in (a, b)]
            assert outcome == (('a_win' if units[a] == winner else 'b_win') if winner else 'close_uncertain')
            counts['cells'] += 1
    assert counts == {'original_campaign': 10191, 'owner_requested_alternate_seed': 2, 'cells': 19647}
