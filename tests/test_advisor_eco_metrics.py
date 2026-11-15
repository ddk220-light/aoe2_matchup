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
    # 'Close' cells are scored by seed majority; only exact seed ties stay draws.
    assert header['counts'] == {'decided': 149777, 'closeScoredBySeedMajority': 4164,
                                'decidedWithoutSeedHp': 962, 'draw': 626}


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
                elif outcome == 'equivalent' or evidence == 'identity':
                    assert value == 0  # close_uncertain: either sign (seed majority) or 0 (exact tie)
                signs['win' if value > 0 else 'loss' if value < 0 else 'zero'] += 1
                assert abs(value) < 5
    assert signs['win'] == signs['loss'] > 0


def test_browser_parity_fixture_is_fresh():
    with gzip.open(ROOT / 'tests/advisor/fixtures/v5-plans.json.gz', 'rt') as handle:
        header = json.load(handle)['header']
    assert header['cellMetricsSha256'] == sha256(CELL_METRICS), \
        'stale fixture: python tools/economy/advisor_eco/build_advisor_parity_fixture.py'
    assert header['plans'] == 3080


def test_reference_plans_for_owner_reviewed_matchups():
    """Matchups the owner reviewed on 2026-11-15 (pair selection, strongest-threat support)."""
    sys.path.insert(0, str(ROOT / 'tools/economy/advisor_eco'))
    import advisor_model_v5
    units = {u['id']: u for u in advisor_catalog()['units']}
    name = lambda i: units[i]['name']  # noqa: E731

    siege = advisor_catalog()['siege']

    def pair(civ, enemy):
        p = advisor_model_v5.plan(advisor_matchups(civ)['opponents'][enemy], units, siege)
        return name(p['main']), name(p['support']), p
    assert pair('Slavs', 'Burgundians')[:2] == ('Elite Boyar', 'Halberdier')
    main, support, p = pair('Burgundians', 'Slavs')
    assert (main, support) == ('Elite Coustillier', 'Halberdier')
    assert [name(j) for j in p['unanswered']] == ['Elite Boyar']
    # The Champion scores best alone but nothing fixes its Jaguar loss; this pair beats all 7
    # (the Composite Bowman wins 9 of 10 seeds against the Aztec Champion).
    main, support, p = pair('Armenians', 'Aztecs')
    assert (main, support, p['pairWins']) == ('Elite Composite Bowman', 'Light Cavalry', 7)
    assert p['additions'] == [] and p['unanswered'] == []
    # Jaguar beats the Armenian Champion (strongest); Siege Onager takes the Composite Bowman and Heavy Scorpion.
    main, support, p = pair('Aztecs', 'Armenians')
    assert (main, support) == ('Elite Jaguar Warrior', 'Pikeman')
    assert (p['siege'], [name(j) for j in p['siegeCovers']]) == (['Siege Onager'], ['Elite Composite Bowman', 'Heavy Scorpion'])
    assert p['additions'] == [] and p['unanswered'] == []


@pytest.mark.skipif(not (Path(os.environ.get('ADVISOR_ECO_OUT', '/nonexistent')) / 'cells.csv.gz').is_file(),
                    reason='needs $ADVISOR_ECO_OUT/cells.csv.gz (tools/economy/advisor_eco/extract_cells.py)')
def test_metrics_rebuild_is_byte_identical():
    sys.path.insert(0, str(ROOT / 'tools/economy/advisor_eco'))
    import build_advisor_metrics
    data = gzip.compress(build_advisor_metrics.encode(build_advisor_metrics.build()), compresslevel=9, mtime=0)
    assert data == CELL_METRICS.read_bytes()
