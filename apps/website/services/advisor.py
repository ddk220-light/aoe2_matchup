"""Read saved provisional matchup evidence. Never run fights or rank simulations."""
from functools import lru_cache
import json
import sqlite3
import zlib

from aoe2x.paths import GOLDEN_DIR
from .civilizations import load_civilization_supplement, civilization_page_analysis
from .catalog import presentation

DATASET = GOLDEN_DIR / 'civ_matchups_first_pass.db'


def connect():
    return sqlite3.connect(f'file:{DATASET}?mode=ro', uri=True)


@lru_cache(maxsize=1)
def advisor_catalog():
    with connect() as db:
        units = [json.loads(row[0]) for row in db.execute('SELECT data FROM units ORDER BY id')]
        dataset = json.loads(db.execute("SELECT value FROM metadata WHERE key='dataset'").fetchone()[0])
    names = sorted({u['civilization'] for u in units})
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
    return {'civilizations': names, 'units': units, 'emblems': emblems, 'dataset': dataset,
            'reference_units': reference_units}


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
    opponents = {}
    inverse = {'a_win': 'b_win', 'b_win': 'a_win', 'equivalent': 'equivalent', 'close_uncertain': 'close_uncertain'}
    for a, b, outcome, evidence, ca, cb, tier, flags, eid in records:
        if a not in own:
            a, b, ca, cb, outcome = b, a, cb, ca, inverse[outcome]
        opponents.setdefault(units[b]['civilization'], []).append([a, b, outcome, evidence, ca, cb, tier, flags, eid])
    return {'civilization': civilization, 'opponents': opponents,
            'source_commit': catalog['dataset']['source_commit']}


def advisor_evidence(identifier):
    with connect() as db:
        record = db.execute('SELECT data FROM evidence WHERE id=?', (identifier,)).fetchone()
        dictionary = db.execute("SELECT value FROM metadata WHERE key='compression_dictionary'").fetchone()[0]
    if record is None:
        raise LookupError(identifier)
    return json.loads(zlib.decompressobj(zdict=dictionary).decompress(record[0]))
