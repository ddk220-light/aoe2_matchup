"""Advisor eco metrics (data/golden/advisor_cell_metrics.json.gz) and their served rows."""
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
WINS = {'dominance', 'kite', 'plain_win', 'power_win'}
LOSSES = {'eco_win', 'cheap_loss', 'plain_loss', 'kited_loss', 'outclassed_loss'}
MIRROR = {'dominance': {'outclassed_loss'}, 'kite': {'kited_loss'}, 'plain_win': {'plain_loss'},
          'power_win': {'eco_win', 'cheap_loss'}, 'close': {'close'}, 'pending': {'pending'}}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def test_metrics_were_built_from_the_committed_advisor_dataset():
    _, header = cell_metrics()
    assert header['advisorDataset']['sha256'] == sha256(DATASET), \
        'advisor DB changed: rebuild with tools/economy/advisor_eco/build_advisor_metrics.py (runbooks: Advisor eco metrics)'
    assert header['thresholds'] == {'winnerHpBelow': 0.5, 'cheaperArmyBy': 0.25, 'kiteMinRangeTiles': 3.0,
                                    'badgeResearchRatio': 0.5}


def test_every_served_row_carries_consistent_eco_fields():
    catalog = advisor_catalog()
    assert catalog['eco']['row_fields'] == ROW_FIELDS
    counts = Counter()
    for civilization in catalog['civilizations']:
        data = advisor_matchups(civilization)
        assert data['row_fields'] == ROW_FIELDS
        for rows in data['opponents'].values():
            for a, b, outcome, evidence, *_, cat_a, cat_b, hp, vm_a, vm_b in rows:
                counts[cat_a] += 1
                if cat_a in MIRROR:
                    assert cat_b in MIRROR[cat_a]
                else:
                    assert cat_a in MIRROR[cat_b]
                if cat_a == 'pending':
                    assert evidence == 'inferred' and hp is None and vm_a is None
                elif cat_a == 'close':
                    assert outcome in ('equivalent', 'close_uncertain') or evidence == 'identity'
                else:
                    assert evidence == 'observed' and vm_a > 0 and vm_b > 0
                    assert (cat_a in WINS) == (outcome == 'a_win') and (cat_a in LOSSES) == (outcome == 'b_win')
                    # Up to ~1.07: a few winners end above their starting HP (regeneration).
                    assert hp is None or 0 <= hp <= 1.1
    # Revision 3 cell counts (docs/army-economics/ADVISOR_ECO_DESIGN.md), both display sides.
    assert counts == {'plain_win': 91062, 'plain_loss': 91062, 'pending': 2 * 19647, 'power_win': 31231,
                      'cheap_loss': 22568, 'close': 2 * 5606, 'eco_win': 8663, 'dominance': 3580,
                      'outclassed_loss': 3580, 'kite': 97, 'kited_loss': 97}


def test_full_research_package_for_the_upgrade_badge():
    units = advisor_catalog()['units']
    missing = [u['key'] for u in units if u['full_research_vm'] is None]
    assert missing == ['Burgundians|flemish_militia']
    assert all(u['full_research_vm'] > 0 for u in units if u['full_research_vm'] is not None)


def test_browser_parity_fixture_is_fresh():
    with gzip.open(ROOT / 'tests/advisor/fixtures/rev4-plans.json.gz', 'rt') as handle:
        header = json.load(handle)['header']
    assert header['cellMetricsSha256'] == sha256(CELL_METRICS), \
        'stale fixture: python tools/economy/advisor_eco/build_advisor_parity_fixture.py'
    assert header['plans'] == 3080 and header['referenceDifferences'] == 0


@pytest.mark.skipif(not (Path(os.environ.get('ADVISOR_ECO_OUT', '/nonexistent')) / 'cells.csv.gz').is_file(),
                    reason='needs $ADVISOR_ECO_OUT/cells.csv.gz (tools/economy/advisor_eco/extract_cells.py)')
def test_metrics_rebuild_is_byte_identical():
    sys.path.insert(0, str(ROOT / 'tools/economy/advisor_eco'))
    import build_advisor_metrics
    data = gzip.compress(build_advisor_metrics.encode(build_advisor_metrics.build()), compresslevel=9, mtime=0)
    assert data == CELL_METRICS.read_bytes()
