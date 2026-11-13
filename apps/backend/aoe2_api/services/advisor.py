"""Read saved provisional matchup evidence. Never run fights or rank simulations.

Rows of ``/api/advisor-matchups/<civ>`` (``ROW_FIELDS``): the nine saved fields of the
advisor DB, oriented from the requested civilization's side, followed by the eco-aware
fields of the Revision 4 advisor from ``data/golden/advisor_cell_metrics.json.gz``
(built by ``tools/economy/advisor_eco/build_advisor_metrics.py``): both units' Revision 3
categories, the cell winner's remaining HP fraction and both armies' 60-second investment
in villager-minutes. Identity and close cells are ``close``; inferred (never simulated)
cells are ``pending``.
"""
from functools import lru_cache
import gzip
import json
import sqlite3
import zlib

from aoe2x.paths import GOLDEN_DIR
from .civilizations import load_civilization_supplement, civilization_page_analysis
from .catalog import presentation

DATASET = GOLDEN_DIR / 'civ_matchups_first_pass.db'
CELL_METRICS = GOLDEN_DIR / 'advisor_cell_metrics.json.gz'
ROW_FIELDS = ['a', 'b', 'outcome', 'evidence_type', 'count_a', 'count_b', 'tier', 'flags', 'evidence_id',
              'category_a', 'category_b', 'winner_hp', 'vm_a', 'vm_b']
CLOSE_OUTCOMES = ('equivalent', 'close_uncertain')


def connect():
    return sqlite3.connect(f'file:{DATASET}?mode=ro', uri=True)


@lru_cache(maxsize=1)
def cell_metrics():
    """{(a, b): (category_a, category_b, winner_hp, vm_a, vm_b)} in DB orientation, plus the header."""
    with gzip.open(CELL_METRICS, 'rb') as handle:
        artefact = json.loads(handle.read())
    if artefact['schemaVersion'] != 1:
        raise RuntimeError('Unsupported advisor cell metrics schema')
    cells = {(row[0], row[1]): tuple(row[2:]) for row in artefact.pop('cells')}
    return cells, artefact


def cell_fields(a, b, outcome, evidence, metrics, swapped):
    """Eco fields of one cell from a's side (Revision 4 row_info order: close first, then pending)."""
    found = metrics.get((b, a) if swapped else (a, b))
    vm = (None, None) if found is None else ((found[4], found[3]) if swapped else (found[3], found[4]))
    if outcome in CLOSE_OUTCOMES or evidence == 'identity':
        return ['close', 'close', None, *vm]
    if evidence == 'inferred':
        return ['pending', 'pending', None, None, None]
    if found is None or found[0] == 'close':
        raise RuntimeError(f'Advisor cell metrics are stale for cell {a}/{b}: rebuild advisor_cell_metrics.json.gz')
    category_a, category_b = (found[1], found[0]) if swapped else (found[0], found[1])
    return [category_a, category_b, found[2], *vm]


@lru_cache(maxsize=1)
def advisor_catalog():
    with connect() as db:
        units = [json.loads(row[0]) for row in db.execute('SELECT data FROM units ORDER BY id')]
        dataset = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
    names = sorted({u['civilization'] for u in units})
    _, metrics = cell_metrics()
    full = metrics['fullResearchVm']
    for unit in units:
        unit['full_research_vm'] = full.get(str(unit['id']))
    supplement = load_civilization_supplement()['civilizations']
    emblems = {c: supplement.get(c, {}).get('emblem_url') or
               f'https://backend.cdn.aoe2companion.com/public/aoe2/de/civilizations/{c.lower()}.png'
               for c in names}
    reference_units = {}
    for name in names:
        analysis = civilization_page_analysis(name)
        reference_units[name] = []
        for line in analysis.get('power_units', {}).get('siege', {}).values():
            for row in line or []:
                icon = presentation()['icon_names'].get(row['unit_name'])
                reference_units[name].append(dict(row, name=row['unit_name'], civilization=name,
                    icon=f'/static/img/units/{icon}.png' if icon else '',
                    costs={k: row.get('stats', {}).get(f'cost_{k}', 0) for k in ('food','wood','gold')}))
    eco = {key: metrics[key] for key in ('schemaVersion', 'thresholds', 'categories', 'rounding')}
    eco['row_fields'] = ROW_FIELDS
    return {'civilizations': names, 'units': units, 'emblems': emblems, 'dataset': dataset,
            'reference_units': reference_units, 'eco': eco}


@lru_cache(maxsize=56)
def advisor_matchups(civilization):
    catalog = advisor_catalog()
    if civilization not in catalog['civilizations']:
        raise LookupError(civilization)
    units = {u['id']: u for u in catalog['units']}
    own = {u['id'] for u in units.values() if u['civilization'] == civilization}
    placeholders = ','.join('?' for _ in own)
    with connect() as db:
        records = db.execute(f'SELECT * FROM cells WHERE a IN ({placeholders}) OR b IN ({placeholders}) ORDER BY a,b',
                             [*own, *own]).fetchall()
    metrics, _ = cell_metrics()
    opponents = {}
    inverse = {'a_win': 'b_win', 'b_win': 'a_win', 'equivalent': 'equivalent', 'close_uncertain': 'close_uncertain'}
    for a, b, outcome, evidence, ca, cb, tier, flags, eid in records:
        swapped = a not in own
        if swapped:
            a, b, ca, cb, outcome = b, a, cb, ca, inverse[outcome]
        opponents.setdefault(units[b]['civilization'], []).append(
            [a, b, outcome, evidence, ca, cb, tier, flags, eid, *cell_fields(a, b, outcome, evidence, metrics, swapped)])
    return {'civilization': civilization, 'opponents': opponents, 'row_fields': ROW_FIELDS,
            'source_commit': catalog['dataset']['source_commit']}


def advisor_evidence(identifier):
    with connect() as db:
        record = db.execute('SELECT data FROM evidence WHERE id=?', (identifier,)).fetchone()
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    if record is None:
        raise LookupError(identifier)
    return json.loads(zlib.decompressobj(zdict=dictionary).decompress(record[0]))
