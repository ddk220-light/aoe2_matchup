"""Freeze the nine approved Paladin, Cavalier and Heavy Hei Guang campaigns."""
import copy
import hashlib
import json
import sqlite3

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.planner import plan_matchup
from prepare_camel_comparison import DAT, ROOT
from run_champi_comparison_capture import read, save

WORK = ROOT/'data/local/knight-expansion'
# Order is user-approved. Unit prices are per physical unit, not upgrade costs.
SUBJECTS = [
    ('Spanish','paladin',569,'Paladin',60,75),
    ('Burgundians','paladin',569,'Paladin',60,75),
    ('Celts','paladin',569,'Paladin',60,75),
    ('Khmer','cavalier',283,'Cavalier',60,75),
    ('Berbers','cavalier',283,'Cavalier',48,60),
    ('Malay','cavalier',283,'Cavalier',60,75),
    ('Wei','heavy_hei_guang_cavalry',1946,'Heavy Hei Guang Cavalry',65,65),
    ('Wu','heavy_hei_guang_cavalry',1946,'Heavy Hei Guang Cavalry',65,65),
    ('Shu','heavy_hei_guang_cavalry',1946,'Heavy Hei Guang Cavalry',65,65),
]


def main():
    import aoe2x.dbgen.unit_analyzer as module
    from genieutils.datfile import DatFile
    from build_run import unit_const

    if (WORK/'queue.json').exists():
        raise FileExistsError('Queue already prepared; resume, do not overwrite')
    paths=[ROOT/'data'/n for n in ('recording-costs.json','recording-balance.json','recording-subjects.json')]
    costs,balance,subjects=map(read,paths)
    extracted=ROOT/'data/local/cost-audit-extracted'
    if {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in extracted.glob('*.json')} != costs['extractionHashes']:
        raise ValueError('Audited extraction changed')
    if hashlib.sha256(DAT.read_bytes()).hexdigest()!=balance['datSha256']:
        raise ValueError('Installed DAT changed since the original comparison')
    dat=DatFile.parse(DAT)
    module.OUTPUT_DIR=extracted
    analyzer=module.UnitAnalyzer()
    db=sqlite3.connect(f'file:{ROOT/"data/golden/aoe2_reference.db"}?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    stats={}
    for p in paths:
        save(WORK/'provenance'/p.name,read(p))
    for civ,kind,master,label,food,gold in SUBJECTS:
        assert unit_const(kind)==master
        slug=kind+'_'+civ.lower();identity=civ+'|'+slug
        unit=analyzer.get_unit(master)
        stat=analyzer.get_base_stats(unit)
        resources=('food','wood','gold')
        base={r:getattr(stat,'cost_'+r) for r in resources}
        disabled=analyzer.get_disabled_techs(civ)
        stages=[analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(master,unit['class'],4)) if t not in disabled and t in analyzer.tech_effect_map]
        stages+=analyzer.get_civ_bonus_techs_for_unit(civ,master,unit['class'],4)
        stages+=analyzer.get_unique_techs_for_unit(civ,master,unit['class'],4)
        effects=[]
        for tech in stages:
            for cmd in tech.get('commands',[]):
                if cmd.get('c') not in (100,103,104,105):
                    continue
                before={r:getattr(stat,'cost_'+r) for r in resources}
                analyzer.apply_effect_command(cmd,stat,master,unit['class'])
                after={r:getattr(stat,'cost_'+r) for r in resources}
                if before!=after:
                    effects.append(dict(techId=tech['tech_id'],command=cmd,before=before,after=after))
        price={r:round(getattr(stat,'cost_'+r)) for r in resources}
        if price!={'food':food,'wood':0,'gold':gold}:
            raise ValueError(f'Unexpected price for {identity}: {price}')
        population=-sum(r.amount for r in dat.civs[1].units[master].resource_storages if r.type==4)
        if population!=1:
            raise ValueError('Unexpected physical unit population')
        cost=dict(civ=civ,slug=slug,master=master,label=label,baseCost=base,purchaseCost=price,
                  unitsPerPurchase=1,productionEvidence='One physical unit per purchase; population is not a cost divisor',effectiveCost=price,effects=effects)
        policy=dict(master=master,population=population,sharedAcrossCivilizations=True,
                    classificationEvidence='Shared Stable unit; food/wood discounts half-effective, gold fully effective',
                    populationEvidence='Installed DAT resource_storages; comparison counts one physical unit')
        subject=dict(slug=slug,label=label,civ=civ,master=master,**{'class':'melee'},baseCost=base,
                     scenarioKey=kind,websiteSlug='paladin' if master==1946 else kind,
                     costSource=f'Installed DAT master {master}; own-civilization Imperial cost effects audited')
        for table,value in ((costs['units'],cost),(balance['units'],policy)):
            if identity in table and table[identity]!=value:
                raise ValueError(f'Existing identity conflict: {identity}')
            table[identity]=value
        old=next((r for r in subjects['units'] if r['slug']==slug),None)
        if old and old!=subject:
            raise ValueError(f'Existing subject conflict: {slug}')
        if not old:
            subjects['units'].append(subject)
        row=db.execute("SELECT * FROM ref_units WHERE age='Imperial' AND civ_name=? AND unit_name=?",(civ,'Heavy Hei-Kuang Cavalry' if master==1946 else label)).fetchone()
        if not row:
            raise ValueError(f'Missing reference stats: {identity}')
        stats[civ]=dict(row)
    for path,value in zip(paths,(costs,balance,subjects)):
        save(path,value)
    opponents=read(ROOT/'data/local/camel-baseline/manifest.json')['matchups']
    if len(opponents)!=74:
        raise ValueError('Unexpected opponent list')
    queue=[]
    config=load_config()
    for civ,kind,master,label,food,gold in SUBJECTS:
        slug=kind+'_'+civ.lower();key=slug.replace('_','-');work=WORK/key
        rows=[]
        for original in opponents:
            row=copy.deepcopy(original)
            suffix=original['id'].removeprefix('camel_turks_unique_')
            row.update(id=f'knight_expansion_{slug}_unique_{suffix}',side2=slug,civ2=civ)
            rows.append(row)
        save(work/'requested.json',dict(schemaVersion=1,matchups=rows))
        _,requests=_load_batch(work/'requested.json');evidence=[]
        for request in requests:
            plan=plan_matchup(config,request);validate_plan_costs(plan)
            if plan['side2']['comparison']['population']!=1 or 'maxResources' in plan['balance']:
                raise ValueError('Unexpected count policy')
            save(work/'plans'/f'{plan["jobId"]}.json',plan)
            evidence.append(dict(jobId=plan['jobId'],counts=[plan[s]['count'] for s in ('side2','side3')],comparisonCost=plan['side2']['comparison']['comparisonCost']))
        for p in paths:
            save(work/'frozen-catalogs'/p.name,read(p))
        save(work/'subject-stats.json',[stats[civ]])
        save(work/'pilot.json',dict(schemaVersion=1,matchups=rows[:1]))
        save(work/'manifest.json',dict(schemaVersion=1,matchups=rows))
        save(work/'preflight.json',dict(state='PASSED',total=len(rows),jobs=evidence))
        queue.append(dict(key=key,civilization=civ,unit=label,slug=slug,workDirectory=str(work),total=len(rows)))
        print(f'{civ} {label}: {len(rows)} plans passed',flush=True)
    save(WORK/'queue.json',dict(state='READY',captureOnly=True,total=sum(r['total'] for r in queue),campaigns=queue,
        archiveRoot=str(ROOT/'data/local/AoE2 Renders'),authorization='Record the approved nine variants against the unchanged unique-unit roster; retain videos and frames.'))
    production=read(ROOT/'data/video-production-queue.json')
    production['knightBaselineExpansion']=dict(state='READY_TO_CAPTURE',automaticStart=True,queue=str(WORK/'queue.json'),total=666,subjects=queue)
    production['camelBaseline'].update(state='CAPTURE_COMPLETE',verified=74,failed=0)
    save(ROOT/'data/video-production-queue.json',production)


if __name__=='__main__':
    main()
