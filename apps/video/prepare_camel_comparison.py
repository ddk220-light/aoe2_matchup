"""Audit and freeze eight camel variants; record only, with opponent-interleaved jobs."""
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
OUT = ROOT/'data/local/camel-comparison'
SUBJECTS = ('Hindustanis', 'Gurjaras', 'Berbers', 'Byzantines', 'Ethiopians', 'Saracens', 'Khitans', 'Malians')
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
    dat=DatFile.parse(DAT);unit=dat.civs[1].units[330]
    pop=-sum(r.amount for r in unit.resource_storages if r.type==4)
    if pop!=1 or sum(r.amount for r in unit.resource_storages if r.type==11)!=pop:
        raise ValueError('Unexpected Heavy Camel Rider population')
    for path in paths:
        raw=path.read_bytes()
        dest=OUT/'provenance'/f'{path.stem}-{hashlib.sha256(raw).hexdigest()}.json'
        if not dest.exists():
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    module.OUTPUT_DIR=extracted;analyzer=module.UnitAnalyzer()
    base_unit=analyzer.get_unit(330)
    for civ in SUBJECTS[1:]:
        slug='heavy_camel_'+civ.lower();key=civ+'|'+slug
        stats=analyzer.get_base_stats(base_unit)
        resources=('food','wood','gold')
        base={r:getattr(stats,'cost_'+r) for r in resources}
        disabled=analyzer.get_disabled_techs(civ)
        stages=[analyzer.tech_effect_map[t] for t in sorted(analyzer.find_techs_affecting_unit(330,base_unit['class'],4)) if t not in disabled and t in analyzer.tech_effect_map]
        stages+=analyzer.get_civ_bonus_techs_for_unit(civ,330,base_unit['class'],4)
        stages+=analyzer.get_unique_techs_for_unit(civ,330,base_unit['class'],4)
        effects=[]
        for tech in stages:
            for cmd in tech.get('commands',[]):
                if cmd.get('c') not in (100,103,104,105):continue
                before={r:getattr(stats,'cost_'+r) for r in resources}
                analyzer.apply_effect_command(cmd,stats,330,base_unit['class'])
                after={r:getattr(stats,'cost_'+r) for r in resources}
                if before!=after:effects.append(dict(techId=tech['tech_id'],command=cmd,before=before,after=after))
        final={r:round(getattr(stats,'cost_'+r)) for r in resources}
        expected = {'food': 44 if civ=='Berbers' else 41 if civ in ('Gurjaras','Byzantines') else 55, 'wood':0, 'gold':48 if civ=='Berbers' else 45 if civ=='Byzantines' else 60}
        if final!=expected:
            raise ValueError(f'Unexpected audited price: {civ}: {final}')
        cost=dict(civ=civ,slug=slug,master=330,label='Heavy Camel Rider',baseCost=base,purchaseCost=final,unitsPerPurchase=1,
                  productionEvidence='One physical unit per purchase; population is not a cost divisor',effectiveCost=final,effects=effects)
        policy=dict(master=330,population=pop,sharedAcrossCivilizations=True,
                    classificationEvidence='Heavy Camel Rider is a shared Stable unit across these seven civilizations; comparison population is one per physical unit',
                    populationEvidence='Installed DAT resource_storages: negative resource 4, cross-checked resource 11')
        subject=dict(slug=slug,label='Heavy Camel Rider',civ=civ,master=330,**{'class':'melee'},baseCost=base,
                     scenarioKey='heavy_camel',websiteSlug='heavy_camel',costSource='Installed DAT master 330; own-civilization Imperial cost effects audited')
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
        key='camel-'+civ.lower()
        slug='imperial_camel_rider_hindustanis' if civ=='Hindustanis' else 'heavy_camel_'+civ.lower()
        _,files=episode_files(ROOT,key,slug)
        by_civ[civ]=json.loads(files[Path(f'aoe2lab.recorder.{key}-all-unique.json')])['matchups']
    roster=sorted(read(ROOT/'data/unique-unit-roster.json')['units'], key=lambda u:(u['civ'].casefold(),u['label'].casefold()))
    rows=[r for opponent in roster for c in SUBJECTS for r in by_civ[c] if r['side3']==opponent['slug']]
    save(OUT/'requested.json',dict(schemaVersion=1,matchups=rows))
    _,requests=_load_batch(OUT/'requested.json');cfg=load_config();evidence=[]
    for request in requests:
        plan=plan_matchup(cfg,request);validate_plan_costs(plan)
        save(OUT/'plans'/f'{plan["jobId"]}.json',plan)
        evidence.append(dict(jobId=plan['jobId'],counts=[plan[s]['count'] for s in ('side2','side3')],
                             comparison=[plan[s]['comparison'] for s in ('side2','side3')]))
    db=sqlite3.connect(f'file:{ROOT/"data/golden/aoe2_reference.db"}?mode=ro',uri=True);db.row_factory=sqlite3.Row
    stats=[dict(db.execute("SELECT * FROM ref_units WHERE unit_name IN ('Heavy Camel Rider','Imperial Camel Rider') AND age='Imperial' AND civ_name=?",(c,)).fetchone()) for c in SUBJECTS]
    save(OUT/'subject-stats.json',stats)
    save(OUT/'preflight.json',dict(state='PASSED',total=len(rows),byCivilization={c:len(v) for c,v in by_civ.items()},jobs=evidence,
                                 policy='geometric_shared_discount',resourceCeiling=None,cap=27,purpose='Raw gameplay plus gRPC frames; no publishing'))
    save(OUT/'manifest.json',dict(schemaVersion=1,matchups=rows))
    save(OUT/'pilot.json',dict(schemaVersion=1,matchups=rows[:8]))
    for name in ('recording-costs.json','recording-balance.json','recording-subjects.json'):
        save(OUT/'frozen-catalogs'/name, read(ROOT/'data'/name))
    print(json.dumps(dict(total=len(rows),manifest=str(OUT/'manifest.json'))))


if __name__=='__main__':main()
