"""Read-only audit of archived scenarios, capture evidence and final compilations."""
import contextlib
import io
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'aoe2x/js_simulation/calibration/lab'
OUT=ROOT/'data/local/production-audit'

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
    from build_run import civ_enum, _ai_configuration
    from aoe2x.lab.live import GOLDENS, _camera_configuration, _player_runtime_configuration, _trigger_structure
    catalog=read(ROOT/'data/recording-costs.json')['units']
    cache={}
    def scenario(p):
        if str(p) not in cache:
            with contextlib.redirect_stdout(io.StringIO()): cache[str(p)]=AoE2DEScenario.from_file(str(p))
        return cache[str(p)]
    costs=read(OUT/'cost-audit.json');by_job={j['jobId']:j for j in costs['jobs']}
    checks=[]
    for i,j in enumerate(costs['jobs']):
        p=read(Path(j['plan']));family=p['scenario']['family']
        for rec in j['recordings']:
            rec=Path(rec);r=read(rec);flags=[];verified=[]
            try:
                s=scenario(rec.parent/r['files']['scenario']['path'])
                golden=scenario(ROOT/GOLDENS[family][0])
                players={int(x.player_id):x for x in s.player_manager.players}
                for owner,key in [(2,'side2'),(3,'side3')]:
                    side=p[key];master=catalog[side['civ']+'|'+side['slug']]['master']
                    units=s.unit_manager.get_player_units(owner)
                    if players[owner].civilization!=civ_enum(side['civ']):flags.append(f'P{owner}_CIV_MISMATCH')
                    if len(units)!=side['count'] or any(int(u.unit_const)!=master for u in units):flags.append(f'P{owner}_UNIT_OR_COUNT_MISMATCH')
                    expected=golden.unit_manager.get_player_units(owner)[:side['count']]
                    if [(u.x,u.y) for u in units]!=[(u.x,u.y) for u in expected]:flags.append(f'P{owner}_POSITION_MISMATCH')
                    if getattr(players[owner].starting_age, 'value', players[owner].starting_age)!=6:flags.append(f'P{owner}_NOT_POST_IMPERIAL')
                if players[1].civilization!=players[3].civilization:flags.append('SPECTATOR_CIV_MISMATCH')
                if _camera_configuration(s)!=_camera_configuration(golden):flags.append('CAMERA_MISMATCH')
                if _player_runtime_configuration(s)!=_player_runtime_configuration(golden):flags.append('DIPLOMACY_OR_RUNTIME_MISMATCH')
                if _trigger_structure(s)!=_trigger_structure(golden):flags.append('TRIGGER_MISMATCH')
                if _ai_configuration(s)!=_ai_configuration(golden):flags.append('AI_MISMATCH')
                p4=s.unit_manager.get_player_units(4)
                expected=[] if p['scenario'].get('player4Buffer')=='none' else golden.unit_manager.get_player_units(4)
                if [(u.unit_const,u.x,u.y) for u in p4]!=[(u.unit_const,u.x,u.y) for u in expected]:flags.append('BUFFER_MISMATCH')
                verified+=['scenario civ/identity/count/position','Post-Imperial starting age','Golden diplomacy/AI/triggers/camera/buffer']
            except Exception as e:flags.append('SCENARIO_CHECK_ERROR: '+str(e))
            mpath=rec.parent/'manifest.json'
            if mpath.exists():
                capture=read(mpath).get('capture',{})
                if capture.get('startCounts')!=j['oldCounts']:flags.append('GRPC_START_COUNT_MISMATCH')
            else:flags.append('MISSING_CAPTURE_MANIFEST')
            hp_path=rec.parent/r['files'].get('battleHp',r['files']['hp'])['path']
            if hp_path.exists():
                rows=read(hp_path).get('rows',[])
                if not rows: flags.append('EMPTY_HP_TIMELINE')
                elif any(rows[n]['game_s']>rows[n+1]['game_s'] for n in range(len(rows)-1)):flags.append('NONMONOTONIC_HP_TIME')
            else:flags.append('MISSING_HP_TIMELINE')
            if not (rec.parent/r['files']['frames']['path']).exists():flags.append('MISSING_FRAMES')
            alignment=rec.parent/'unit-hp-overlay/alignment.json'
            checks.append({'jobId':j['jobId'],'recording':str(rec),'flags':flags,'checksAttempted':verified,'alignmentReceiptAvailable':alignment.exists(),'gameVersion':r.get('gameVersion')})
        if i%100==0: print(json.dumps({'checkedJobs':i}),flush=True)
    compilations=[]
    for path in (LAB/'compilations').glob('*/final/manifest.json'):
        c=read(path);results=c.get('results',[])
        if not results and (path.parent.parent/'manifest.json').exists():
            legacy=read(path.parent.parent/'manifest.json')
            results=legacy.get('chapters',[]) if isinstance(legacy.get('chapters'),list) else []
        mapped=[]
        for row in results:
            job=row.get('jobId');audit=by_job.get(job)
            mapped.append({'jobId':job,'action':audit['action'] if audit else 'UNRESOLVED','startSeconds':row.get('startSeconds',row.get('start')),'durationSeconds':row.get('durationSeconds'),'timestamp':row.get('timestamp')})
        compilations.append({'manifest':str(path),'fullVideo':c.get('output'),'fullVideoExists':Path(c.get('output','missing')).exists(),'chapterCount':len(results),'actions':dict(Counter(x['action'] for x in mapped)),'chapters':mapped})
    report={'scope':'All locally archived recording.json bundles; all compilations/*/final/manifest.json chapters','recordingsChecked':len(checks),'flaggedRecordings':sum(bool(x['flags']) for x in checks),'flags':dict(Counter(f for x in checks for f in x['flags'])),'unverified':['Actual researched technology IDs and per-unit attack/armor/range versus installed data are NOT proven by Post-Imperial age or HP alone','No new full-frame visual or audio review of every historical video','Existing alignment receipts are inventoried, not independently remeasured','Historical runs from another game build need build-specific data before declaring unchanged mechanics','Cost count reuse does not establish outcome labels are correct; labels and Shorts rankings need regenerated evidence'],'recordings':checks,'compilations':compilations}
    (OUT/'setup-audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('recordings','compilations','unverified')}))

if __name__=='__main__':main()
