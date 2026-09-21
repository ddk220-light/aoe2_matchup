"""Audit and freeze the approved four-Cavalier campaign before game access."""
import hashlib
import json
import sqlite3
from pathlib import Path

from aoe2x.lab.cli import _load_batch
from aoe2x.lab.config import load_config
from aoe2x.lab.costs import validate_plan_costs
from aoe2x.lab.planner import plan_matchup
from scaffold_video_episode import episode_files
from report_champi_geometric import read, save

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/local/cavalier-comparison'
SUBJECTS = ('Bulgarians', 'Poles', 'Burmese', 'Sicilians')
DAT = Path('C:/Program Files (x86)/Steam/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat')


def register():
    import aoe2x.dbgen.unit_analyzer as module
    from genieutils.datfile import DatFile
    paths = [ROOT/'data'/name for name in ('recording-costs.json','recording-balance.json','recording-subjects.json')]
    costs, balance, subjects = map(read, paths)
    extracted=ROOT/'data/local/cost-audit-extracted'
    if {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in extracted.glob('*.json')} != costs['extractionHashes']:
        raise ValueError('Audited extraction changed')
    if hashlib.sha256(DAT.read_bytes()).hexdigest()!=balance['datSha256']:
        raise ValueError('Installed DAT changed since the cost audit')
    dat=DatFile.parse(DAT);unit=dat.civs[1].units[283]
    pop=-sum(r.amount for r in unit.resource_storages if r.type==4)
    if pop!=1 or sum(r.amount for r in unit.resource_storages if r.type==11)!=pop:
        raise ValueError('Unexpected Cavalier population')
    for path in paths:
        raw=path.read_bytes()
        dest=OUT/'provenance'/f'{path.stem}-{hashlib.sha256(raw).hexdigest()}.json'
        if not dest.exists():
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    module.OUTPUT_DIR=extracted;analyzer=module.UnitAnalyzer()
    base_unit=analyzer.get_unit(283)
    for civ in SUBJECTS:
        slug='cavalier_'+civ.lower();key=civ+'|'+slug
        stats=analyzer.get_base_stats(base_unit)
        resources=('food','wood','gold')
        base={r:getattr(stats,'cost_'+r) for r in resources}
        disabled=analyzer.get_disabled_techs(civ)
        stages=[analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(283,base_unit['class'],4)) if t not in disabled and t in analyzer.tech_effect_map]
        stages+=analyzer.get_civ_bonus_techs_for_unit(civ,283,base_unit['class'],4)
        stages+=analyzer.get_unique_techs_for_unit(civ,283,base_unit['class'],4)
        effects=[]
        for tech in stages:
            for cmd in tech.get('commands',[]):
                if cmd.get('c') not in (100,103,104,105):continue
                before={r:getattr(stats,'cost_'+r) for r in resources}
                analyzer.apply_effect_command(cmd,stats,283,base_unit['class'])
                after={r:getattr(stats,'cost_'+r) for r in resources}
                if before!=after:effects.append(dict(techId=tech['tech_id'],command=cmd,before=before,after=after))
        final={r:round(getattr(stats,'cost_'+r)) for r in resources}
        if final!={'food':60,'wood':0,'gold':30 if civ=='Poles' else 75}:
            raise ValueError(f'Unexpected audited price: {civ}: {final}')
        cost=dict(civ=civ,slug=slug,master=283,label='Cavalier',baseCost=base,purchaseCost=final,unitsPerPurchase=1,
                  productionEvidence='One physical unit per purchase; population is not a cost divisor',effectiveCost=final,effects=effects)
        policy=dict(master=283,population=pop,sharedAcrossCivilizations=True,
                    classificationEvidence='Cavalier is a shared Stable upgrade; selected civilizations have no population-changing Cavalier technologies',
                    populationEvidence='Installed DAT resource_storages: negative resource 4, cross-checked resource 11')
        subject=dict(slug=slug,label='Cavalier',civ=civ,master=283,**{'class':'melee'},baseCost=base,
                     scenarioKey='cavalier',websiteSlug='cavalier',costSource='Installed DAT master 283; own-civilization Imperial cost effects audited')
        for table,value in ((costs['units'],cost),(balance['units'],policy)):
            if key in table and table[key]!=value:raise ValueError(f'Refusing to overwrite {key}')
            table[key]=value
        existing=next((r for r in subjects['units'] if r['slug']==slug),None)
        if existing and existing!=subject:raise ValueError(f'Conflicting subject {slug}')
        if not existing:subjects['units'].append(subject)
    for path,value in zip(paths,(costs,balance,subjects)):save(path,value)


def main():
    if (OUT/'manifest.json').exists():raise FileExistsError('Resume the frozen campaign; do not prepare it again')
    register()
    by_civ={}
    for civ in SUBJECTS:
        key='cavalier-'+civ.lower()
        _,files=episode_files(ROOT,key,'cavalier_'+civ.lower())
        by_civ[civ]=json.loads(files[Path(f'aoe2lab.recorder.{key}-all-unique.json')])['matchups']
    rows=[by_civ[c][i] for i in range(len(by_civ[SUBJECTS[0]])) for c in SUBJECTS]
    save(OUT/'requested.json',dict(schemaVersion=1,matchups=rows))
    _,requests=_load_batch(OUT/'requested.json');cfg=load_config();evidence=[]
    for request in requests:
        plan=plan_matchup(cfg,request);validate_plan_costs(plan)
        save(OUT/'plans'/f'{plan["jobId"]}.json',plan)
        evidence.append(dict(jobId=plan['jobId'],counts=[plan[s]['count'] for s in ('side2','side3')],
                             comparison=[plan[s]['comparison'] for s in ('side2','side3')]))
    db=sqlite3.connect(f'file:{ROOT/"data/golden/aoe2_reference.db"}?mode=ro',uri=True);db.row_factory=sqlite3.Row
    stats=[dict(db.execute("SELECT * FROM ref_units WHERE unit_name='Cavalier' AND age='Imperial' AND civ_name=?",(c,)).fetchone()) for c in SUBJECTS]
    save(OUT/'subject-stats.json',stats)
    save(OUT/'preflight.json',dict(state='PASSED',total=len(rows),byCivilization={c:len(v) for c,v in by_civ.items()},jobs=evidence,
                                 policy='geometric_shared_discount',resourceCeiling=None,cap=27,purpose='Raw gameplay plus gRPC frames; no publishing'))
    save(OUT/'manifest.json',dict(schemaVersion=1,matchups=rows))
    print(json.dumps(dict(total=len(rows),manifest=str(OUT/'manifest.json'))))


if __name__=='__main__':main()
