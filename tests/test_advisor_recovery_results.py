"""Release integrity contracts over saved evidence; never execute a battle."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sqlite3
import zlib

import pytest

from scripts.apply_advisor_recovery_results import validate

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data/validation/civ-matchups-forecast-recovery-2026-11-10/2026-11-11'
BUNDLE = json.loads(gzip.decompress((SNAPSHOT / 'release-bundle.json.gz').read_bytes()))


def test_all_published_recovery_sets_match_the_archived_measurements():
    for item in BUNDLE:
        validate(item)
    with sqlite3.connect(ROOT / 'data/golden/civ_matchups_first_pass.db') as db:
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
        recoveries = {}
        for identifier, blob in db.execute('SELECT id,data FROM evidence'):
            row = json.loads(zlib.decompressobj(zdict=dictionary).decompress(blob))
            if row.get('recoveryValidation'):
                recoveries[row['recoveryValidation']['jobId']] = row
        assert len(recoveries) == len(BUNDLE) == 36
        for item in BUNDLE:
            row = recoveries[item['job']['id']]; validation = row['recoveryValidation']
            assert row['outcome'] == item['summary']['outcome']
            assert row['context'] == item['job']['context']
            assert validation['review'] == item['review']
            assert validation['measuredRecords'] == item['runs']
            assert validation['physicsVersions'] == item['summary']['physicsVersions']
            assert row['originalEvidence']['evidenceType'] == 'predicted_unvalidated'
            assert validation['frozenCampaignResult'] is False
        assert sum(r['recoveryValidation']['mixedEngineVersions'] for r in recoveries.values()) == 6
        assert db.execute("SELECT COUNT(*) FROM cells WHERE evidence_type='predicted_unvalidated'").fetchone()[0] == 0
        metadata = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
        assert metadata['forecastCoverage']['totalContexts'] == 39148
        assert metadata['forecast_validation']['reviewedContexts'] == 39112
        assert metadata['recovery_validation']['reviewedContexts'] == 36


@pytest.mark.parametrize('failure', ['missing_seed', 'duplicate_seed', 'reversed_context', 'forced_winner', 'false_replay', 'erased_engine_version'])
def test_invalid_recovery_cannot_be_imported(failure):
    item = deepcopy(next(i for i in BUNDLE if len(i['runs']) == 3))
    if failure == 'missing_seed': item['runs'].pop()
    if failure == 'duplicate_seed': item['runs'][1] = deepcopy(item['runs'][0])
    if failure == 'reversed_context': item['runs'][0]['record']['profileHashes'].reverse()
    if failure == 'forced_winner': item['summary']['outcome'] = 'close_uncertain'
    if failure == 'false_replay': item['review']['exactReplay']['exact'] = True
    if failure == 'erased_engine_version': item['runs'][1]['record']['physicsVersion'] = 'frozen-civ-matchups-v3'
    with pytest.raises(AssertionError):
        validate(item)
