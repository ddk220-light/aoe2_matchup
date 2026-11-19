"""Freeze a raw-only campaign for one Viking Sagas unique unit; never edit old runs.

Requires an isolated extraction at data/local/viking-sagas-research/extracted.
Prepare once, then resume with run_camel_comparison_capture.py --work <WORK>.
"""
import hashlib
import argparse
import json
from pathlib import Path

from aoe2x.dbgen.conditional_costs import has_max_saxon_foot_discount
from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.io import safe_slug
from aoe2x.lab.planner import plan_matchup
from run_champi_comparison_capture import read, save

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'data/local/jomsviking-capture'
EXTRACTED = ROOT / 'data/local/viking-sagas-research/extracted'
DAT = Path('C:/Program Files (x86)/Steam/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat')
NEW_UNITS = [
    ('Danes', 'elite_jomsviking_danes', 'Elite Jomsviking', 2712, 'melee', 'elite_jomsviking'),
    ('Saxons', 'elite_hearth_troop_saxons', 'Elite Hearth Troop', 2706, 'melee', 'elite_hearth_troop'),
    ('Varangians', 'elite_jarl_varangians', 'Elite Jarl', 2709, 'mobile_ranged', 'elite_jarl'),
]


def audited_price(analyzer, row):
    """Use the installed own-civilization cost chain; never infer cost from HP/pop."""
    unit = analyzer.get_unit(row['master'])
    stats = analyzer.get_base_stats(unit)
    resources = ('food', 'wood', 'gold')
    base = {r: getattr(stats, 'cost_' + r) for r in resources}
    disabled = analyzer.get_disabled_techs(row['civ'])
    # Starting civ-tree modifiers precede age/unique techs. In particular the
    # Mayan .90 factor must precede the Castle .89 and Imperial .88 factors.
    tree = analyzer.civ_tech_trees.get(row['civ'], {})
    tree_id = tree.get('tech_tree_effect_id')
    stages = [dict(tech_id='civ-tree:' + str(tree_id),
                   commands=analyzer.effects.get(tree_id, {}).get('commands', []))]
    stages += [analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(row['master'], unit['class'], 4))
              if t not in disabled and t in analyzer.tech_effect_map]
    stages += analyzer.get_civ_bonus_techs_for_unit(row['civ'], row['master'], unit['class'], 4)
    stages += analyzer.get_unique_techs_for_unit(row['civ'], row['master'], unit['class'], 4)
    effects = []
    for tech in stages:
        for cmd in tech.get('commands', []):
            if cmd.get('c') not in (100, 103, 104, 105):
                continue
            before = {r: getattr(stats, 'cost_' + r) for r in resources}
            analyzer.apply_effect_command(cmd, stats, row['master'], unit['class'])
            after = {r: getattr(stats, 'cost_' + r) for r in resources}
            if before != after:
                effects.append(dict(techId=tech['tech_id'], command=cmd, before=before, after=after))
    purchase = {r: round(getattr(stats, 'cost_' + r)) for r in resources}
    if has_max_saxon_foot_discount(row['civ'], row['master']):
        # The bonus is a building aura, not a direct price command. The installed
        # help 120209 specifies 5% per TC/Castle, capped at 20%; user requests max.
        purchase = {r: round(v * .8) for r, v in purchase.items()}
        effects.append(dict(techId=1469, conditional=True, assumedTownCentersAndCastles=4,
                            discountPercent=20, evidence='Installed English help 120209; maximum civilization discount requested'))
    batch = 2 if row['master'] in (2579, 2581) else 1
    return dict(civ=row['civ'], slug=row['slug'], master=row['master'], label=row['label'],
                baseCost=base, purchaseCost=purchase, unitsPerPurchase=batch,
                productionEvidence='Two physical units per purchase' if batch == 2 else 'One physical unit per purchase',
                effectiveCost={r: v / batch for r, v in purchase.items()}, effects=effects)


def main():
    global WORK
    import aoe2x.dbgen.unit_analyzer as module
    from build_run import unit_const

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject', choices=('jomsviking', 'jarl', 'hearth-troop'), default='jomsviking')
    args = parser.parse_args()
    WORK = ROOT / f'data/local/{args.subject}-capture'
    selected = NEW_UNITS[{'jomsviking': 0, 'hearth-troop': 1, 'jarl': 2}[args.subject]]

    if (WORK / 'manifest.json').exists():
        raise FileExistsError('Already frozen. Resume the campaign; do not reprepare it.')
    module.OUTPUT_DIR = EXTRACTED
    analyzer = module.UnitAnalyzer()
    paths = [ROOT/'data'/name for name in ('unique-unit-roster.json', 'recording-costs.json', 'recording-balance.json', 'recording-subjects.json')]
    for path in paths:
        target = WORK/'provenance'/path.name
        if not target.exists():
            save(target, read(path))
    roster, costs, balance, _ = map(read, paths)
    for civ, slug, label, master, unit_class, key in NEW_UNITS:
        assert unit_const(key) == master
        unit = analyzer.get_unit(master)
        assert unit and unit['name'] == label
        stat = analyzer.get_base_stats(unit)
        row = dict(civ=civ, slug=slug, label=label, master=master, **{'class':unit_class},
                   scenarioKey=key, baseCost={r:getattr(stat,'cost_'+r) for r in ('food','wood','gold')},
                   costSource='Installed Viking Sagas release DAT, 2026-09-22')
        existing = next((r for r in roster['units'] if r['slug'] == slug), None)
        if existing and existing != row:
            raise ValueError('Conflicting existing unit: '+slug)
        if not existing:
            roster['units'].append(row)
        balance['units'][civ+'|'+slug] = dict(master=master, population=1.0, sharedAcrossCivilizations=False,
            classificationEvidence='Civilization-exclusive castle unique unit; installed release identity',
            populationEvidence='Installed DAT; one comparison population per physical unit')
    roster['units'].sort(key=lambda r:(r['civ'],r['label']))
    assert len(roster['units']) == 77
    changes=[]
    for row in roster['units']:
        key=row['civ']+'|'+row['slug']
        price=audited_price(analyzer,row)
        old=costs['units'].get(key)
        if old and old['effectiveCost'] != price['effectiveCost']:
            changes.append(dict(identity=key,before=old['effectiveCost'],after=price['effectiveCost']))
        costs['units'][key]=price
    dat_hash=hashlib.sha256(DAT.read_bytes()).hexdigest()
    costs['releaseAudit'] = dict(datSha256=dat_hash, scope='77 approved unique units; other catalog identities retain previous provenance',
        extractionHashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in EXTRACTED.glob('*.json')})
    balance['datSha256']=dat_hash
    for path,value in zip(paths,(roster,costs,balance)):
        save(path,value)
    save(WORK/'release-cost-audit.json',dict(datSha256=dat_hash,changedExistingPrices=changes,
        newUnits={c+'|'+s:costs['units'][c+'|'+s] for c,s,*_ in NEW_UNITS}))
    subject=selected[1]
    opponents=[r for r in roster['units'] if r['slug'] != subject]
    rows=[dict(id=safe_slug(f'{args.subject}_v3_unique_{i:02}_'+r['slug']),side2=subject,civ2=selected[0],
               side3=r['slug'],civ3=r['civ'],balance=dict(mode='geometric_shared_discount',cap=27,
                   weights=dict(food=1,wood=.9,gold=1.1))) for i,r in enumerate(opponents,1)]
    save(WORK/'requested.json',dict(schemaVersion=1,matchups=rows))
    config=load_config();evidence=[]
    for request in _load_batch(WORK/'requested.json')[1]:
        plan=plan_matchup(config,request)
        validate_plan_costs(plan)
        save(WORK/'plans'/f'{plan["jobId"]}.json',plan)
        evidence.append(dict(jobId=plan['jobId'],opponent=plan['side3']['label'],
            counts=[plan[s]['count'] for s in ('side2','side3')],
            weightedCosts=[plan[s]['weightedCost'] for s in ('side2','side3')],scenario=plan['scenario']))
    for path in paths:
        save(WORK/'frozen-catalogs'/path.name,read(path))
    stat=analyzer.calculate_unique_unit_stats(selected[0],dict(base_id=selected[3],display_name=selected[2],
        unit_class=analyzer.get_unit(selected[3])['class']),4)['stats']
    save(WORK/'subject-stats.json',[dict(civ_name=selected[0],final_hp=stat.hp)])
    save(WORK/'pilot.json',dict(schemaVersion=1,matchups=rows[:1]))
    save(WORK/'preflight.json',dict(state='PASSED',total=len(rows),jobs=evidence))
    save(WORK/'manifest.json',dict(schemaVersion=1,matchups=rows))
    print(json.dumps(dict(total=len(rows),changedExistingPrices=changes,pilotHp=stat.hp,work=str(WORK)),indent=2))


if __name__ == '__main__':
    main()
