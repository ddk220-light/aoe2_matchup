"""Advisor matchup values (data/golden/advisor_cell_metrics.json.gz, Revision 5) and their served rows."""
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from aoe2_api.services.advisor import (
    CELL_METRICS, DATASET, ROW_FIELDS, advisor_catalog, advisor_matchups, cell_metrics,
)

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def test_values_were_built_from_the_committed_advisor_dataset():
    _, header = cell_metrics()
    assert header['advisorDataset']['sha256'] == sha256(DATASET), \
        'advisor DB changed: rebuild with tools/economy/advisor_eco/build_advisor_metrics.py (runbooks: Advisor eco metrics)'
    assert header['schemaVersion'] == 2
    assert header['value'] == {'hpFull': 0.75, 'replenishExponent': 0.5, 'productionExponent': 0.25,
                               'speedExponent': 0.5, 'mixedSpeedFactor': 2.0, 'speedFloor': 0.3,
                               'villagerMinuteFloor': 1.0, 'noHpAssumed': 0.5, 'digits': 4}
    assert header['counts'] == {'decided': 145613, 'decidedWithoutSeedHp': 962, 'draw': 4790}


def test_every_served_row_carries_a_value_with_the_right_sign():
    catalog = advisor_catalog()
    assert catalog['eco']['row_fields'] == ROW_FIELDS and ROW_FIELDS[-1] == 'value'
    signs = Counter()
    for civilization in catalog['civilizations']:
        data = advisor_matchups(civilization)
        assert data['row_fields'] == ROW_FIELDS
        for rows in data['opponents'].values():
            for a, b, outcome, evidence, *_, value in rows:
                assert evidence in ('observed', 'identity')
                if outcome == 'a_win':
                    assert value >= 0
                elif outcome == 'b_win':
                    assert value <= 0
                else:
                    assert value == 0
                signs['win' if value > 0 else 'loss' if value < 0 else 'zero'] += 1
                assert abs(value) < 5
    assert signs['win'] == signs['loss'] > 0


def test_browser_parity_fixture_is_fresh():
    with gzip.open(ROOT / 'tests/advisor/fixtures/v5-plans.json.gz', 'rt') as handle:
        header = json.load(handle)['header']
    assert header['cellMetricsSha256'] == sha256(CELL_METRICS), \
        'stale fixture: python tools/economy/advisor_eco/build_advisor_parity_fixture.py'
    assert header['plans'] == 3080


def test_slavs_vs_burgundians_reference_plan():
    sys.path.insert(0, str(ROOT / 'tools/economy/advisor_eco'))
    import advisor_model_v5
    units = {u['id']: u for u in advisor_catalog()['units']}
    name = lambda i: units[i]['name']  # noqa: E731
    slavs = advisor_model_v5.plan(advisor_matchups('Slavs')['opponents']['Burgundians'], units)
    assert (name(slavs['main']), name(slavs['support'])) == ('Elite Boyar', 'Halberdier')
    burgundians = advisor_model_v5.plan(advisor_matchups('Burgundians')['opponents']['Slavs'], units)
    assert name(burgundians['main']) == 'Paladin'
    assert [name(i) for i in burgundians['unanswered']] == ['Elite Boyar']


@pytest.mark.skipif(not (Path(os.environ.get('ADVISOR_ECO_OUT', '/nonexistent')) / 'cells.csv.gz').is_file(),
                    reason='needs $ADVISOR_ECO_OUT/cells.csv.gz (tools/economy/advisor_eco/extract_cells.py)')
def test_metrics_rebuild_is_byte_identical():
    sys.path.insert(0, str(ROOT / 'tools/economy/advisor_eco'))
    import build_advisor_metrics
    data = gzip.compress(build_advisor_metrics.encode(build_advisor_metrics.build()), compresslevel=9, mtime=0)
    assert data == CELL_METRICS.read_bytes()
