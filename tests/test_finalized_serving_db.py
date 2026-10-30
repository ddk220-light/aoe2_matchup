"""The finalized serving build must be reproducible and preserve historical consumers."""
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from aoe2x.rank.build_finalized_serving_db import build

GOLDEN = Path(__file__).resolve().parents[1] / 'data/golden'


def rows(path, table):
    with sqlite3.connect(path) as conn:
        return conn.execute(f'SELECT * FROM {table} ORDER BY 1,2').fetchall()


def test_rebuild_keeps_scores_roster_and_all_historical_rows(tmp_path):
    db, metadata = tmp_path / 'serving.db', tmp_path / 'metadata.json'
    shutil.copyfile(GOLDEN / 'derived_data_v3.db', db)
    shutil.copyfile(GOLDEN / 'derived_data_v3.metadata.json', metadata)
    original_scores = rows(db, 'battle_scores')
    original_roster = rows(db, 'ranking_roster')
    original_metadata = json.loads(metadata.read_text())
    build(GOLDEN / 'unit_rankings_final.json', GOLDEN / 'aoe2_reference_rankings.db', db, metadata)
    assert rows(db, 'battle_scores') == original_scores
    assert rows(db, 'ranking_roster') == original_roster
    updated = json.loads(metadata.read_text())
    assert updated['dataset_hash'] == original_metadata['dataset_hash']
    assert updated['retained_source_metadata'] == original_metadata['retained_source_metadata']
    assert updated['source_summary'] == {'variants': 555, 'categories': 10, 'opponent_rows': 3591, 'distinct_matchups': 2398, 'runs': 7600, 'unresolved': 0}


def test_wrong_reference_is_rejected_before_mutating_serving_artifacts(tmp_path):
    with pytest.raises(AssertionError, match='reference does not match'):
        build(GOLDEN / 'unit_rankings_final.json', GOLDEN / 'aoe2_reference.db', tmp_path / 'serving.db', tmp_path / 'metadata.json')
    assert not (tmp_path / 'serving.db').exists()
