"""Preflight all approved Champi four-civilization recordings without using the UI."""
import json,sqlite3,hashlib
from pathlib import Path
from build_comp4_scenario import ROOT, audited_costs, generate
from overlay.static_stats import resolve_stats

DIRECTORY=ROOT/'data/local/comp4-champi-all-unique'

def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    cached=audited_costs()
    costs=json.loads((ROOT/'data/recording-costs.json').read_text())
    roster=json.loads((ROOT/'data/unique-unit-roster.json').read_text())['units']
    profiles=json.loads((ROOT/'apps/video/comp4_runtime_profiles.json').read_text())
    opponents=sorted((x for x in roster if x['master']!=2554),key=lambda x:(x['civ'].casefold(),x['label'].casefold()))
    db=sqlite3.connect(f'file:{ROOT / "data/golden/aoe2_reference.db"}?mode=ro',uri=True);db.row_factory=sqlite3.Row
    jobs=[]
    for i,u in enumerate(opponents,1):
        stats=resolve_stats(db,u)
        cost=costs['units'][u['civ']+'|'+u['slug']]
        total=sum(cost['effectiveCost'].values())
        evidence={**cost,'total':total}
        opponent={**u,'hp':stats['final_hp'],'costEvidence':evidence}
        adjustment=profiles['units'].get(u['slug'])
        if adjustment:
            opponent['hp']=adjustment.get('hp',opponent['hp'])
            opponent['runtimeAdjustment']={**adjustment,'gameVersion':profiles['gameVersion']}
        job_id=f'{i:02}_{u["slug"].replace("(","").replace(")","")}'
        folder=DIRECTORY/'jobs'/job_id
        version=f"-v{adjustment['scenarioVersion']}" if adjustment else ''
        scenario=folder/f'scenario{version}.aoe2scenario'
        if scenario.exists():
            plan=json.loads(scenario.with_suffix('.json').read_text())
            if plan['costs'][4]!=evidence or plan['opponent']['master']!=u['master']:
                raise ValueError(f'Existing plan differs: {job_id}')
        else:plan=generate(scenario,opponent,cached_costs=cached,quiet=True)
        if not all(1<=p['subjectCount']<=8 and 1<=len(p['opponentHP'])<=8 for p in plan['pairs']):raise ValueError(job_id)
        # Every reference army is below 5000; cheaper variants use the fixed
        # subject count and the explicitly approved 0.8 opponent HP factor.
        assert all(p['subjectCount']*p['subjectCost']<=5000 for p in plan['pairs'])
        jobs.append({'id':job_id,'scenario':str(scenario),'plan':str(scenario.with_suffix('.json')),'opponent':u,
                     'pairs':[{k:p[k] for k in ['civ','subjectCount','opponentHP','subjectCost','opponentCost']} for p in plan['pairs']]})
    db.close()
    manifest={'schemaVersion':1,'mode':'comp4_no_buffer','subject':'Elite Champi Warrior','total':len(jobs),
              'goldenSha256':jobs and plan['goldenSha256'],'jobs':jobs,
              'costCatalogSha256':hashlib.sha256((ROOT/'data/recording-costs.json').read_bytes()).hexdigest(),
              'policy':'All four variants in one video. Raw video and full gRPC frames only. No automatic overlays or uploads. Three real seconds after the final pair resolves.'}
    (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'prepared':len(jobs),'directory':str(DIRECTORY),'first':jobs[0]['pairs'],'last':jobs[-1]['opponent']['label']},indent=2))

if __name__=='__main__':main()
