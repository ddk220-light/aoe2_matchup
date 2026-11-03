"""Build the advisor's read-only serving DB from the immutable first-pass bundle."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def rows(path):
    with gzip.open(path, 'rt') as source:
        yield from map(json.loads, source)


def build(source, output):
    manifest = json.loads((source / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected, name
    summary = json.loads((source / 'summary.json').read_text())
    assert summary['status'] == 'provisional_first_pass_complete' and summary['unresolvedPairs'] == 0
    variants = json.loads((source / 'variant-profiles.json').read_text())
    presentation = json.loads((ROOT / 'aoe2x/assets/presentation.json').read_text())
    reference = sqlite3.connect(ROOT / 'data/golden/aoe2_reference_simulation.db')
    reference.row_factory = sqlite3.Row
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix('.next.db')
    pending.unlink(missing_ok=True)
    db = sqlite3.connect(pending)
    db.executescript('''
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE units (id INTEGER PRIMARY KEY, key TEXT UNIQUE, civilization TEXT, data TEXT);
        CREATE INDEX units_civ ON units(civilization);
        CREATE TABLE evidence (id INTEGER PRIMARY KEY, data BLOB);
        CREATE TABLE cells (a INTEGER, b INTEGER, outcome TEXT, evidence_type TEXT,
            count_a INTEGER, count_b INTEGER, tier TEXT, flags INTEGER, evidence_id INTEGER,
            PRIMARY KEY(a,b));
        CREATE INDEX cells_b ON cells(b);
    ''')
    units = {}
    for index, unit in enumerate(sorted(variants, key=lambda u: u['key'])):
        ref = reference.execute('SELECT * FROM ref_units WHERE civ_name=? AND unit_slug=? AND age=?',
                                (unit['civilization'], unit['slug'], 'Imperial')).fetchone()
        assert ref is not None, ('missing reference unit', unit['key'])
        icon = presentation['icon_names'][unit['name']]
        assert (ROOT / f'apps/website/static/img/units/{icon}.png').is_file(), icon
        data = dict(unit, id=index, icon=f'/static/img/units/{icon}.png',
                    costs={name: ref[f'final_cost_{name}'] for name in ('food', 'wood', 'gold')})
        units[unit['key']] = data
        db.execute('INSERT INTO units VALUES (?,?,?,?)', (index, unit['key'], unit['civilization'], encode(data)))
    profiles = {}
    preserved = ('context', 'sourceContext', 'sourceOutcome', 'sourceEvidenceType', 'originalPrediction',
                 'predictionTier', 'predictionRuleHash', 'predictionSourceSha256', 'predictionPolicy',
                 'predictionConflicts', 'predictionContested', 'recoveryProjection', 'sourceRunIds',
                 'ruleId', 'ruleVersion', 'rootAnchorIds', 'reasonCodes', 'verified', 'needsValidation')
    dictionary = (','.join(sorted({u['profileHash'] for u in variants})) +
                  encode({k: None for k in preserved})).encode()[-32768:]
    db.execute('INSERT INTO metadata VALUES (?,?)', ('compression_dictionary', dictionary))
    for index, row in enumerate(rows(source / 'profile-table.jsonl.gz')):
        data = {k: row[k] for k in preserved if k in row}
        data.update(pairKey=row['pairKey'], outcome=row['outcome'], evidenceType=row['evidenceType'])
        compressor = zlib.compressobj(9, zdict=dictionary)
        compressed = compressor.compress(encode(data).encode()) + compressor.flush()
        db.execute('INSERT INTO evidence VALUES (?,?)', (index, compressed))
        flags = int(bool(row.get('predictionContested'))) | (2 if row.get('predictionTier') == 'weak_model_agreement' else 0)
        profiles[row['pairKey']] = (index, row.get('predictionTier', ''), flags)
    count = 0
    for cell in rows(source / 'civilization-table.jsonl.gz'):
        a, b = units[cell['civA'] + '|' + cell['unitA']], units[cell['civB'] + '|' + cell['unitB']]
        context = cell['context']
        counts = [context['counts'][context['profiles'].index(u['profileHash'])] for u in (a, b)]
        assert cell['outcome'] in ('a_win', 'b_win', 'close_uncertain', 'equivalent')
        evidence_id, tier, flags = profiles[cell['pairKey']]
        db.execute('INSERT INTO cells VALUES (?,?,?,?,?,?,?,?,?)',
                   (a['id'], b['id'], cell['outcome'], cell['evidenceType'], *counts,
                    tier, flags, evidence_id))
        count += 1
    assert count == 151223 and len(units) == 555 and len(profiles) == 68916
    metadata = dict(summary, source_commit='207c31283c70db1f6ebea4ae93535c98dfe86777',
                    source_url='https://github.com/ddk220-light/aoe2_matchup/tree/207c31283c70db1f6ebea4ae93535c98dfe86777/aoe2x/js_simulation/calibration/reports/civ-matchups-first-pass-provisional-2026-11-02',
                    source_files=manifest['files'])
    db.execute('INSERT INTO metadata VALUES (?,?)', ('dataset', encode(metadata)))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    db.execute('VACUUM')
    db.close()
    reference.close()
    pending.replace(output)
    print(encode({'units': len(units), 'cells': count, 'bytes': output.stat().st_size}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/golden/civ_matchups_first_pass.db')
    args = parser.parse_args()
    build(args.source, args.output)
