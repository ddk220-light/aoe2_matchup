"""Append a Turkish baseline campaign without rewriting the eight completed sets."""
import copy
import hashlib
import sqlite3
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.planner import plan_matchup
from prepare_camel_comparison import DAT, ROOT
from run_champi_comparison_capture import read, save

WORK = ROOT/'data/local/camel-baseline'
ORIGINAL = ROOT/'data/local/camel-comparison'


def main():
    if (WORK/'manifest.json').exists():
        raise FileExistsError('Baseline already planned; resume its frozen manifest')
    names = ('recording-costs.json', 'recording-balance.json', 'recording-subjects.json')
    costs, balance, subjects = [read(ROOT/'data'/name) for name in names]
    if hashlib.sha256(DAT.read_bytes()).hexdigest() != balance['datSha256']:
        raise ValueError('Installed game data changed; audit before comparing to old captures')
    # Only additive identities are allowed; original catalog entries stay intact.
    for name in names:
        frozen = read(ORIGINAL/'frozen-catalogs'/name)['units']
        current = read(ROOT/'data'/name)['units']
        if isinstance(frozen, dict):
            assert all(current.get(k) == v for k, v in frozen.items()), name
        else:
            assert all(v in current for v in frozen), name
        save(WORK/'provenance'/name, read(ROOT/'data'/name))
    slug = 'heavy_camel_turks'
    key = 'Turks|' + slug
    price = copy.deepcopy(costs['units']['Turks|heavy_camel'])
    assert price['master'] == 330 and price['effectiveCost'] == {'food':55, 'wood':0, 'gold':60}
    assert price['effects'] == []
    price['slug'] = slug
    policy = copy.deepcopy(balance['units']['Malians|heavy_camel_malians'])
    subject = copy.deepcopy(next(u for u in subjects['units'] if u['slug']=='heavy_camel_malians'))
    subject.update(slug=slug, civ='Turks')
    for table, value in ((costs['units'], price), (balance['units'], policy)):
        if key in table and table[key] != value:
            raise ValueError('Conflicting baseline identity')
        table[key] = value
    if subject not in subjects['units']:
        subjects['units'].append(subject)
    for name, value in zip(names, (costs, balance, subjects)):
        save(ROOT/'data'/name, value)
        save(WORK/'frozen-catalogs'/name, value)
    # Reuse the actual frozen opponent list, including any per-match exceptions.
    rows = copy.deepcopy([r for r in read(ORIGINAL/'manifest.json')['matchups'] if r['civ2']=='Gurjaras'])
    assert len(rows) == 74
    for row in rows:
        row.update(id=row['id'].replace('camel_gurjaras_', 'camel_turks_', 1), side2=slug, civ2='Turks')
    save(WORK/'requested.json', dict(schemaVersion=1, matchups=rows))
    _, requests = _load_batch(WORK/'requested.json')
    evidence = []
    for request in requests:
        plan = plan_matchup(load_config(), request)
        validate_plan_costs(plan)
        assert plan['balance']['comparisonPolicy']=='geometric_shared_discount_unit_count_v2'
        assert 'maxResources' not in plan['balance']
        assert plan['side2']['weightedCost']==115
        save(WORK/'plans'/f'{plan["jobId"]}.json', plan)
        evidence.append(dict(jobId=plan['jobId'], counts=[plan[s]['count'] for s in ('side2','side3')]))
    db=sqlite3.connect(f'file:{ROOT/"data/golden/aoe2_reference.db"}?mode=ro', uri=True)
    db.row_factory=sqlite3.Row
    stats=dict(db.execute("SELECT * FROM ref_units WHERE civ_name='Turks' AND unit_name='Heavy Camel Rider' AND age='Imperial'").fetchone())
    assert [stats[k] for k in ('final_hp','final_attack','final_melee_armor','final_pierce_armor')]==[140,11,3,4]
    save(WORK/'subject-stats.json', [stats])
    save(WORK/'preflight.json', dict(state='PASSED', total=74, jobs=evidence, baseline='Turks', originalCaptures=591))
    save(WORK/'pilot.json', dict(schemaVersion=1, matchups=rows[:1]))
    save(WORK/'manifest.json', dict(schemaVersion=1, matchups=rows))
    queue=read(ROOT/'data/video-production-queue.json')
    queue['camelBaseline']=dict(state='READY_TO_CAPTURE', civilization='Turks', unit=slug, total=74,
        workDirectory=str(WORK), authorization='Capture raw video and frames for the same opponents; preserve the original eight sets.',
        comparisonRules=dict(better='Variant wins and Turks loses', worse='Variant loses and Turks wins',
                             baselineAlreadyWins='No special win highlight', draws='Report separately; never treat as loss'))
    save(ROOT/'data/video-production-queue.json', queue)
    print('74 baseline plans passed; first matchup is the HP/count pilot.', flush=True)


if __name__=='__main__':
    main()
