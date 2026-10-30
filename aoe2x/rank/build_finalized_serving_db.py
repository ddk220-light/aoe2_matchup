"""Publish the approved score table without recomputing battles or scores."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from statistics import mean, median

from aoe2x.rank.derived_db import create_db
from aoe2x.sim.unit_lines import UNIT_LINES

LAND_LINES = {'militia', 'spear', 'archer', 'skirmisher', 'cav_archer', 'scorpion',
              'gunpowder', 'knight', 'light_cav', 'camel'}
GROUP_TYPES = {'Infantry': 'militia_value', 'Ranged': 'ranged_effectiveness', 'Cavalry': 'stable_effectiveness'}
GROUP_POOLS = {
    'Infantry': ['champion', 'hussar', 'arbalester', 'paladin', 'cavalier'],
    'Ranged': ['champion', 'arbalester', 'cavalier', 'hca', 'hand_cannoneer', 'hussar', 'skirmisher'],
    'Cavalry': ['champion', 'arbalester', 'paladin', 'halberdier', 'camel', 'cavalier', 'hca'],
}
LABELS = {'champion': 'Spanish Champion', 'hussar': 'Spanish Hussar', 'arbalester': 'Chinese Arbalester',
          'paladin': 'Spanish Paladin', 'cavalier': 'Turkish Cavalier', 'hca': 'Saracen Heavy Cavalry Archer',
          'hand_cannoneer': 'Saracen Hand Cannoneer', 'skirmisher': 'Spanish Elite Skirmisher',
          'halberdier': 'Spanish Halberdier', 'camel': 'Turkish Heavy Camel Rider'}


def build(source_path, reference_path, serving_path, metadata_path):
    source_path, reference_path, serving_path, metadata_path = map(Path, [source_path, reference_path, serving_path, metadata_path])
    bundle = json.loads(source_path.read_text())
    reference_sha = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    assert reference_sha == bundle['reference_sha256'], 'ranking reference does not match the approved source'
    scores, matchups = bundle['scores'], bundle['matchups']
    assert bundle['validation']['status'] == 'passed'
    assert len(scores) == len({(r['civilization'], r['unitSlug']) for r in scores}) == 555
    assert len(matchups) == 3591 and all(r['state'] == 'complete' and r['undecided'] == 0 for r in matchups)
    assert set(r['category'] for r in scores) == LAND_LINES
    by_unit = defaultdict(list)
    for row in matchups:
        by_unit[row['civilization'], row['slug']].append(row)
    reference = sqlite3.connect(f'file:{reference_path}?mode=ro', uri=True)
    reference.row_factory = sqlite3.Row
    unique_slugs = set()
    for line in UNIT_LINES.values():
        for entries in line.get('unique_units', {}).values():
            for pair in entries if isinstance(entries, list) else [entries]:
                unique_slugs.update(slug for slug in pair if slug)
    unique_slugs.update({'elite_varangian_guard', 'elite_jomsviking_danes', 'elite_hearth_troop_saxons', 'elite_jarl_varangians'})
    metadata = json.loads(metadata_path.read_text())
    retained_metadata = metadata.get('retained_source_metadata', {k: metadata.get(k) for k in
        ['game_build', 'engine_revision', 'mechanics_build', 'generated_at', 'source_summary']})
    dataset = bundle['score_manifest']['datasetHash']
    build_key = 'rankings:' + dataset[:16]
    conn = create_db(str(serving_path))
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS ranking_roster (
            civ_name TEXT NOT NULL, unit_slug TEXT NOT NULL, line_slug TEXT NOT NULL,
            source_line TEXT NOT NULL, group_name TEXT NOT NULL, ref_unit_id INTEGER NOT NULL,
            is_unique INTEGER NOT NULL, original_engine_runs INTEGER NOT NULL,
            corrected_engine_runs INTEGER NOT NULL, PRIMARY KEY(civ_name,unit_slug));
        CREATE TABLE IF NOT EXISTS ranking_dataset (key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
    ''')
    # Other consumers still request the historical game build. Keep those rows
    # intact; only the rankings table selects this independently versioned dataset.
    legacy = [tuple(r) for r in conn.execute("SELECT line_slug,age,civ_name,unit_slug,score_type,score_value,rank,median_delta,build_number FROM battle_scores")
              if r['build_number'] != build_key]
    conn.execute('DELETE FROM battle_scores WHERE build_number=?', (build_key,))
    conn.execute('DELETE FROM ranking_roster')
    medians = {line: median(r['score'] for r in scores if r['category'] == line) for line in LAND_LINES}
    for row in scores:
        civ, slug, category = row['civilization'], row['unitSlug'], row['category']
        unit = reference.execute("SELECT id,unit_name FROM ref_units WHERE civ_name=? AND unit_slug=? AND age='Imperial'", (civ, slug)).fetchall()
        assert len(unit) == 1 and unit[0]['unit_name'] == row['unit'], (civ, slug)
        matches = by_unit[civ, slug]
        assert set(r['opponentKey'] for r in matches) == set(GROUP_POOLS[row['group']])
        expected = 50 + mean(r['meanUnitHpPercentDecided'] - r['meanOpponentHpPercentDecided'] for r in matches) / 2
        assert abs(expected - row['score']) < 1e-10
        conn.execute('INSERT INTO ranking_roster VALUES(?,?,?,?,?,?,?,?,?)', (civ, slug, category, row['sourceLine'], row['group'],
                     unit[0]['id'], int(slug in unique_slugs), row['originalEngineRuns'], row['correctedEngineRuns']))
        values = [(GROUP_TYPES[row['group']], row['score'], row['categoryRank'], row['score'] - medians[category])]
        for matchup in matches:
            margin = matchup['meanUnitHpPercentDecided'] - matchup['meanOpponentHpPercentDecided']
            values.append(('versus_' + matchup['opponentKey'], 50 + margin / 2, None, None))
        for score_type, value, rank, delta in values:
            conn.execute('INSERT INTO battle_scores(line_slug,age,civ_name,unit_slug,score_type,score_value,rank,median_delta,build_number) VALUES(?,?,?,?,?,?,?,?,?)',
                         (category, 'imperial', civ, slug, score_type, value, rank, delta, build_key))
    conn.execute('INSERT OR REPLACE INTO ranking_dataset VALUES(?,?)', ('build_key', json.dumps(build_key)))
    conn.execute('INSERT OR REPLACE INTO ranking_dataset VALUES(?,?)', ('dataset_hash', json.dumps(dataset)))
    conn.commit()
    assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert conn.execute('SELECT COUNT(*) FROM ranking_roster').fetchone()[0] == 555
    assert conn.execute('SELECT COUNT(*) FROM battle_scores WHERE build_number=?', (build_key,)).fetchone()[0] == 555 + 3591
    retained = [tuple(r) for r in conn.execute("SELECT line_slug,age,civ_name,unit_slug,score_type,score_value,rank,median_delta,build_number FROM battle_scores") if r['build_number'] != build_key]
    assert sorted(legacy) == sorted(retained), 'historical score rows changed'
    conn.close(); reference.close()
    methods = metadata['methodology']
    methods['schema_version'] = 2
    for group, key in [('Infantry', 'infantry'), ('Ranged', 'archery'), ('Cavalry', 'stable')]:
        methods['methods'][key] = {
            'title': group + ' score',
            'setting': 'Full Imperial upgrades · 27 units on the cheaper side · opposing count balances population and resource cost · food 1, wood 0.9, gold 1.1 · zero buffers.',
            'formula': [(f'1/{len(GROUP_POOLS[group])}', LABELS[k]) for k in GROUP_POOLS[group]],
            'result': 'A win contributes your surviving HP percentage, a loss the negative enemy surviving HP percentage, and a draw zero. Average three seeded runs per matchup; use ten when the first three outcomes differ.',
            'finish': 'Give every listed opponent equal weight. Score = 50 + half the average signed HP percentage. 50 is neutral. No additional speed, range or cost multiplier.',
            'source_engine': 'simulationv3',
        }
    metadata.update({'schema_version': 2, 'generated_at': datetime.now(timezone.utc).isoformat(),
                     'engine_revision': 'mixed:original+corrected', 'mechanics_build': reference_sha,
                     'seed_count': None, 'seed_policy': {'initial': [0, 1, 2], 'extra_when_outcomes_differ': list(range(3, 10))},
                     'resource_weights': {'food': 1, 'wood': .9, 'gold': 1.1}, 'unit_cap': 27,
                     'dataset_hash': dataset, 'ranking_build_key': build_key,
                     'v3_source': source_path.name,
                     'source_bundle_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
                     'source_commit': bundle['source_commit'],
                     'source_summary': {'variants': 555, 'categories': 10, 'opponent_rows': 3591, 'distinct_matchups': 2398, 'runs': 7600, 'unresolved': 0},
                     'engine_versions': bundle['engine_versions'], 'engine_run_counts': {'original': 6768, 'corrected': 832},
                     'retained_source_metadata': retained_metadata, 'published_rows': len(retained) + 4146,
                     'category_merges': {'shock_infantry': 'militia', 'elephant': 'knight', 'steppe_lancer': 'knight'},
                     'methodology': methods})
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata['source_summary']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='data/golden/unit_rankings_final.json')
    parser.add_argument('--reference', default='data/golden/aoe2_reference_rankings.db')
    parser.add_argument('--serving', default='data/golden/derived_data_v3.db')
    parser.add_argument('--metadata', default='data/golden/derived_data_v3.metadata.json')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.reference, args.serving, args.metadata)))
