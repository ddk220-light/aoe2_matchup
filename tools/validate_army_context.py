#!/usr/bin/env python3
"""Independent source-to-output checks for the army economy review."""
import hashlib
import itertools
import json
import math
import os
import sqlite3
from pathlib import Path
from army_economics_paths import scratch_path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('ARMY_CONTEXT_OUT',str(ROOT / 'aoe2x/js_simulation/calibration/economy/army-context-2026-11-09')))
CAMPAIGN = ROOT / 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-consolidated-2026-10-29'
SOURCES = {
    'eco': scratch_path('economy-review/labor-inputs/labor-inputs.sqlite'),
    'production': scratch_path('economy-review/corrected-production/production-review.sqlite'),
    'research': Path(os.environ.get('ARMY_RESEARCH_DB',str(scratch_path('research-review/current-results/unit-upgrades.sqlite')))),
}
RESOURCES = ('food', 'wood', 'stone', 'gold')


def connect(path):
    c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def near(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8), (a, b)


def main():
    db = connect(OUT / 'army-context.sqlite')
    metadata = json.loads((OUT / 'summary.json').read_text())
    assert db.execute('pragma integrity_check').fetchone()[0] == 'ok'
    copied_tables = copied_rows = 0
    for prefix, path in SOURCES.items():
        assert digest(path) == metadata['source_hashes'][prefix]
        source = connect(path)
        for (name,) in source.execute("select name from sqlite_master where type='table'"):
            left = source.execute(f'SELECT * FROM "{name}"')
            right = db.execute(f'SELECT * FROM "{prefix}_{name}"')
            for original, copied in itertools.zip_longest(left, right):
                assert original is not None and copied is not None, name
                assert tuple(original) == tuple(copied), name
                copied_rows += 1
            copied_tables += 1
    assert digest(CAMPAIGN / 'runs.jsonl') == metadata['campaign_runs_sha256']
    original_runs = {}
    for line in (CAMPAIGN / 'runs.jsonl').open():
        run = json.loads(line)
        original_runs[run['matchupId'], run['seed']] = run
    assert len(original_runs) == db.execute('select count(*) from battle_runs').fetchone()[0]
    for row in db.execute('select * from battle_runs'):
        source = original_runs[row['source_matchup_id'], row['seed']]
        for stored, field in [('side2', 'side2'), ('side3', 'side3'), ('starting_hp', 'startingHpByOwner'), ('remaining', 'remainingByOwner')]:
            assert json.loads(row[stored]) == source['result'][field]
        assert json.loads(row['provenance']) == source['selectionProvenance']

    rates = {(r['civ_name'], r['resource']): r for r in db.execute('select * from gather_rates')}
    assert len(rates) == 56 * 4
    for row in rates.values():
        runs = json.loads(row['runs'])
        if row['rate'] is None:
            assert (row['civ_name'], row['resource']) == ('Khitans', 'food')
            continue
        assert len(runs) == 3 and {r['seed'] for r in runs} == {0, 1, 2}
        near(row['rate'], sum(r['rate'] for r in runs) / 3)
        assert all(abs(v) < 1e-5 for r in runs for v in r['checks'].values())

    units = {r['unit_key']: r for r in db.execute('select * from unit_economy')}
    specs = {s['civ_name']: s for s in json.loads((OUT / 'eco-inputs.json').read_text())}
    for unit in units.values():
        if unit['labor_seconds'] is None:
            assert unit['civ_name'] == 'Khitans' and unit['food'] > 0
            continue
        civ = unit['civ_name']
        expected = sum(unit[r] / rates[civ, r]['rate'] for r in RESOURCES if unit[r])
        s = specs[civ]
        if unit['food']:
            expected += unit['food'] * s['farm_wood'] / (s['farm_food'] * s['farm_yield'] * rates[civ, 'wood']['rate'])
        near(unit['labor_seconds'], expected)

    originals = {s['matchupId']: s for s in json.loads((CAMPAIGN / 'summary.json').read_text())}
    coverage = {r['matchup_id']: r for r in db.execute('select * from matchup_coverage')}
    assert set(originals) == set(coverage)
    for mid, row in coverage.items():
        for key, label in [('unit_key', 'unit'), ('opponent_key', 'opponent')]:
            unit = units[row[key]]
            assert f"{unit['civ_name']} {unit['unit_name']}" == originals[mid][label]

    checked_contexts = 0
    for row in db.execute('select * from close_battle_analysis'):
        source = original_runs[row['source_matchup_id'], row['seed']]
        winner = source['winnerOwner']
        loser = 5 - winner
        s = originals[row['matchup_id']]
        assert (s['unitCount'], s['opponentCount']) == (source['unitCount'], source['opponentCount'])
        remaining = source['result']['remainingByOwner']
        hp = remaining[str(winner)]['hp'] / source['result']['startingHpByOwner'][str(winner)]
        assert 0 < hp < 0.25
        near(row['winner_hp_fraction'], hp)
        for side, owner in [('winner', winner), ('loser', loser)]:
            count = source['unitCount' if owner == 2 else 'opponentCount']
            assert row[side + '_deaths'] == max(0, count - remaining[str(owner)]['units'])
            unit = units[row[side + '_unit_key']]
            key = 'unit_key' if owner == 2 else 'opponent_key'
            assert unit['unit_key'] == coverage[row['matchup_id']][key]
            if unit['labor_seconds'] is not None:
                near(row[side + '_replacement_labor'], row[side + '_deaths'] * unit['labor_seconds'])
        ratio = row['loser_to_winner_loss_labor_ratio']
        if ratio is not None:
            near(ratio, row['loser_replacement_labor'] / row['winner_replacement_labor'])
            assert bool(row['attrition_favors_loser']) == (ratio < 1)
        else:
            assert not row['attrition_favors_loser']
        buildings = row['loser_buildings_to_match_one_winner_building']
        if buildings:
            train = units[row['loser_unit_key']]['train_seconds']
            assert math.ceil(row['loser_deaths'] / buildings) * train <= row['winner_queue_seconds'] + 1e-8
            if buildings > 1:
                assert math.ceil(row['loser_deaths'] / (buildings - 1)) * train > row['winner_queue_seconds'] - 1e-8
        checked_contexts += 1

    research = {}
    for row in db.execute("select * from research_unit_upgrade_data where scope='direct'"):
        research.setdefault(row['unit_key'], {})[row['tech_id']] = row
    checked_comparisons = 0
    for row in db.execute('select * from upgrade_comparisons'):
        a, b = [research.get(units[row[side + '_unit_key']]['research_unit_key'], {}) for side in ['loser', 'winner']]
        common = set(json.loads(row['common_ids']))
        assert common == a.keys() & b.keys()
        assert set(json.loads(row['loser_exclusive_ids'])) == a.keys() - b.keys()
        assert set(json.loads(row['winner_exclusive_ids'])) == b.keys() - a.keys()
        for side, techs in [('loser', a), ('winner', b)]:
            for kind in ['common', 'exclusive']:
                ids = common if kind == 'common' else set(json.loads(row[side + '_exclusive_ids']))
                costs = json.loads(row[side + '_' + kind + '_cost'])
                for phase in ['upfront', 'reward', 'net']:
                    for resource in RESOURCES:
                        near(costs[phase][resource], sum(techs[t][phase + '_' + resource] for t in ids))
            times = [techs[t]['final_seconds'] for t in common]
            actual = row[side + '_common_seconds']
            if any(t is None for t in times):
                assert actual is None
            else:
                near(actual, sum(times))
            buildings = json.loads(row[side + '_research_buildings'])
            assert len(buildings) == len({b['building_id'] for b in buildings})
        checked_comparisons += 1

    report = {'status': 'passed', 'source_tables_compared_row_for_row': copied_tables,
              'source_rows_preserved': copied_rows, 'saved_battle_runs_preserved': len(original_runs),
              'civilizations': len(specs), 'unit_variants': len(units),
              'matchup_identities_checked': len(coverage), 'close_contexts_checked': checked_contexts,
              'common_and_exclusive_upgrade_comparisons_checked': checked_comparisons,
              'whole_unit_queue_capacity_checked': True, 'source_file_hashes_unchanged': True,
              'known_unmodeled_rate': 'Khitans food / pasture', 'combat_reversals_proven': False}
    (OUT / 'independent-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
