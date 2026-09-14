"""Resumable offline overlay and five-seed comparison lanes for recorder bundles."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib
from .io import read_json, write_json, utc_now
from .planner import load_matchup_file

ROOT=Path(__file__).resolve().parents[2]


def source_hash():
    digest=hashlib.sha256()
    paths=list((ROOT/'aoe2x/js_simulation/src').rglob('*.js'))
    paths+=list((ROOT/'aoe2x/js_simulation/fixtures/unit_stats').glob('*.json'))
    paths+=list((ROOT/'apps/video/overlay').glob('*.py'))
    paths+=list((ROOT/'apps/video/overlay').glob('*.json'))
    paths+=[Path(__file__)]
    paths+=[ROOT/'aoe2x/js_simulation/tools/aoe2lab_worker.mjs']
    paths+=[ROOT/'aoe2x/grpc/redecode_hp.py']
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode());digest.update(path.read_bytes())
    return digest.hexdigest()


def simulation(run, output, revision):
    from overlay.unit_timeline import decode
    output.mkdir(parents=True,exist_ok=True)
    plan=run.parent.parent/'plan.json'
    raw=read_json(run/'recording.json')
    timeline=decode(run)
    rows=timeline['rows']
    start={o:sum(u['hp'] for u in rows[0]['sides'][o]) for o in ('2','3')}
    final={o:sum(u['hp'] for u in rows[-1]['sides'][o]) for o in ('2','3')}
    alive=[int(o) for o in ('2','3') if final[o]>0]
    winner=alive[0] if len(alive)==1 else None
    elimination=next((r['gameMs']/1000 for r in rows if any(
        not any(u['hp']>0 for u in r['sides'][o]) for o in ('2','3'))),None)
    signed=(1 if winner==2 else -1)*final[str(winner)]/start[str(winner)]*100 if winner else 0
    seeds=[]
    for seed in range(1,6):
        path=output/f'seed_{seed:03}.json'
        provenance=output/f'seed_{seed:03}.provenance.json'
        valid=path.exists() and provenance.exists() and read_json(provenance).get('sourceHash')==revision and read_json(provenance).get('planHash')==read_json(plan)['planHash']
        if not valid:
            with (output/f'seed_{seed:03}.log').open('w',encoding='utf-8') as log:
                subprocess.run(['node',str(ROOT/'aoe2x/js_simulation/tools/aoe2lab_worker.mjs'),
                    'run-seed','--plan',str(plan),'--seed',str(seed),'--output',str(path)],
                    cwd=ROOT,stdout=log,stderr=log,check=True,timeout=900)
            write_json(provenance,{'sourceHash':revision,'planHash':read_json(plan)['planHash']})
        result=read_json(path)
        if result.get('lab',{}).get('planHash')!=read_json(plan)['planHash']:
            raise ValueError('Simulation result does not belong to this persisted plan')
        sw=result['winnerOwner']
        score=(1 if sw==2 else -1)*result['winnerHp']/result['startingHpByOwner'][str(sw)]*100 if sw in (2,3) else 0
        seeds.append({'seed':seed,'winner':sw,'signedHpPercent':score,'winnerHp':result['winnerHp'],
                      'gameSeconds':result['ticks']/60,'artifact':str(path)})
    mean=sum(s['signedHpPercent'] for s in seeds)/5
    agreement=sum(s['winner']==winner for s in seeds)
    report={'status':'complete','sourceHash':revision,'generatedAt':utc_now(),
        'framesSha256':raw['files']['frames']['sha256'],'planHash':read_json(plan)['planHash'],
        'liveWinner':winner,'liveSignedHpPercent':signed,'liveEliminationGameSeconds':elimination,
        'liveStartingHp':start,'liveFinalHp':final,'seeds':seeds,'meanSignedHpPercent':mean,
        'deltaPoints':mean-signed,'winnerAgreement':agreement,'thresholdPoints':10,
        'verdict':('MATCH' if agreement==5 and abs(mean-signed)<=10 else 'MISMATCH') if winner else 'INCONCLUSIVE',
        'meanDurationDeltaGameSeconds':sum(s['gameSeconds'] for s in seeds)/5-elimination if elimination is not None else None}
    write_json(output/'comparison.json',report)
    return report


def overlay(run, output, revision):
    output.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'PYTHONPATH':str(ROOT/'apps/video')+os.pathsep+str(ROOT),'PYTHONIOENCODING':'utf-8'}
    with (output/'overlay.log').open('w',encoding='utf-8') as log:
        for module,extra in [('overlay.static_stats',['--panels-only']),('overlay.auto_alignment',[]),('overlay.unit_hp',[])]:
            subprocess.run([sys.executable,'-m',module,str(run),*extra],cwd=ROOT,env=env,
                stdout=log,stderr=log,check=True,timeout=1800)
    video=run/'unit-hp-overlay/battle-with-unit-hp.mp4'
    import cv2
    captures=[cv2.VideoCapture(str(p)) for p in [run/'battle.mp4',video]]
    sizes=[(c.get(3),c.get(4),c.get(cv2.CAP_PROP_FRAME_COUNT),c.get(cv2.CAP_PROP_FPS)) for c in captures]
    for c in captures:c.release()
    if sizes[0]!=sizes[1] or video.stat().st_size<10000:raise ValueError('Overlay media validation failed')
    return {'status':'complete','sourceHash':revision,'video':str(video),'mediaValidation':sizes[1],
            'alignment':read_json(run/'unit-hp-overlay/alignment.json')['method'] if 'method' in read_json(run/'unit-hp-overlay/alignment.json') else 'manual measured alignment'}


def report(directory,state):
    state['updatedAt']=utc_now();write_json(directory/'status.json',state)
    body=[]
    for row in state['jobs']:
        sim=row.get('simulation',{});ov=row.get('overlay',{})
        delta=sim.get('deltaPoints');video=ov.get('video')
        cells=[row['civ'],row['unit'],row.get('raw','pending'),ov.get('status','pending'),sim.get('verdict',sim.get('status','pending')),
               f'{delta:+.2f}' if delta is not None else '',str(sim.get('winnerAgreement',''))+'/5' if 'winnerAgreement' in sim else '']
        link=f'<a href="{html.escape(Path(video).as_uri(),quote=True)}">View video</a>' if video else html.escape(ov.get('error',''))
        if sim.get('error'):link+=' '+html.escape(sim['error'])
        body.append('<tr>'+''.join('<td>'+html.escape(c)+'</td>' for c in cells)+'<td>'+link+'</td></tr>')
    content='''<!doctype html><meta charset="utf-8"><title>Tiger Cavalry — recording and V3 comparison</title>
<style>body{font:16px system-ui;margin:32px;background:#f7f4ee;color:#252422}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ccc;text-align:left}th{position:sticky;top:0;background:#e9e1d2}h1{font-size:26px}a{color:#165880}</style>
<h1>Tiger Cavalry recordings and V3 comparisons</h1><p>Five deterministic seeds per matchup. MATCH means 5/5 winner agreement and mean signed remaining HP within 10 percentage points of the recorded game. Positive HP is Tiger Cavalry; negative HP is the opponent. This is an outcome comparison, not proof of all mechanics. Durations use game seconds from gRPC and 60 simulation ticks per second.</p>'''
    content=content.replace('Tiger Cavalry',html.escape(state.get('subjectLabel','Tiger Cavalry')))
    content+=f'<p>Updated {html.escape(state["updatedAt"])} — {html.escape(state["state"])}. Source revision {state["sourceHash"][:12]}</p>'
    content+='<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in ['Civilization','Opponent','Raw','Overlay','Simulation','HP delta (pp)','Winner','Video / details'])+'</tr></thead><tbody>'+''.join(body)+'</tbody></table>'
    (directory/'report.html').write_text(content,encoding='utf-8')
    failures = comparison_failures(state)
    write_json(directory/'failures-over20.json', {'updatedAt': state['updatedAt'],
        'thresholdPoints': 20, 'completedComparisons': sum(r.get('simulation',{}).get('status')=='complete' for r in state['jobs']),
        'rows': failures})
    lines = ['# Simulation failures: wrong winner or HP delta over 20 percentage points', '',
             'Only completed five-seed comparisons are included. HP delta is simulated minus recorded signed remaining HP; positive favors Tiger Cavalry, negative favors the opponent.', '',
             '| Civilization | Opponent | Recorded winner | Wrong winners | HP delta (pp) |',
             '|---|---|---|---:|---:|']
    for r in failures:
        lines.append(f"| {r['civ']} | {r['unit']} | {r['liveWinner']} | {r['wrongWinners']}/{r['seeds']} | {r['deltaPoints']:+.1f} |")
    (directory/'failures-over20.md').write_text(('\n'.join(lines)+'\n').replace('Tiger Cavalry',state.get('subjectLabel','Tiger Cavalry')), encoding='utf-8')



def can_schedule(active, row, lane, workers):
    """Bound independent Node processes; each matchup retains serial seed order."""
    if row.get(lane, {}).get('status') in ('complete', 'failed', 'running'):
        return False
    limit = workers if lane == 'simulation' else 1
    return sum(key[0] == lane for key in active) < limit


def comparison_failures(state, threshold=20):
    rows = []
    for row in state['jobs']:
        sim = row.get('simulation', {})
        if sim.get('status') != 'complete':
            continue
        wrong = len(sim['seeds']) - sim['winnerAgreement']
        if wrong or abs(sim['deltaPoints']) > threshold:
            rows.append({'jobId': row['jobId'], 'civ': row['civ'], 'unit': row['unit'],
                         'wrongWinners': wrong, 'seeds': len(sim['seeds']),
                         'liveWinner': state.get('subjectLabel','Tiger Cavalry') if sim['liveWinner'] == 2 else row['unit'] if sim['liveWinner'] == 3 else 'Inconclusive',
                         'deltaPoints': sim['deltaPoints']})
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--once',action='store_true')
    parser.add_argument('--simulation-workers', type=int, default=6)
    parser.add_argument('--manifest', type=Path, default=ROOT/'aoe2lab.recorder.all-unique.toml')
    parser.add_argument('--subject-label', default='Tiger Cavalry')
    parser.add_argument('--simulation-only', action='store_true', help='Use the separate overlay worker; only run five-seed comparisons here.')
    args=parser.parse_args()
    lanes = [('simulation', simulation)] if args.simulation_only else [('simulation', simulation), ('overlay', overlay)]
    if not 1 <= args.simulation_workers <= 16:
        parser.error('--simulation-workers must be between 1 and 16')
    args.output.mkdir(parents=True,exist_ok=True)
    subprocess.run(['node',str(ROOT/'aoe2x/js_simulation/tools/preflight_recorder_roster.mjs'),
        str(args.output/'preflight.json')],cwd=ROOT,check=True)
    with (args.output/'preflight-tests.log').open('w',encoding='utf-8') as log:
        subprocess.run(['node','--test',*[str(ROOT/'aoe2x/js_simulation/tests'/name) for name in
            ['recorder-roster-mechanics.test.mjs','unique-special-effects.test.mjs','aoe2lab-worker.test.mjs']]],
            cwd=ROOT,check=True,stdout=log,stderr=log)
    import msvcrt
    lock=(args.output/'worker.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    # Recent episodes use JSON; early Tiger/Xianbei manifests use TOML.
    # Both must reach the same five-seed lane without converting job identities.
    manifest=load_matchup_file(args.manifest)['matchups']
    roster={u['slug']:u for u in read_json(ROOT/'data/unique-unit-roster.json')['units']}
    revision=source_hash()
    state=read_json(args.output/'status.json') if (args.output/'status.json').exists() else {'jobs':[]}
    old={r['jobId']:r for r in state['jobs']}
    state.update(pid=os.getpid(),state='RUNNING',sourceHash=revision,simulationWorkers=args.simulation_workers,subjectLabel=args.subject_label,manifest=str(args.manifest.resolve()),jobs=[])
    for spec in manifest:
        unit=roster[spec['side3']];row=old.get(spec['id'],{'jobId':spec['id'],'civ':unit['civ'],'unit':unit['label']})
        for lane in ('simulation','overlay'):
            if row.get(lane,{}).get('sourceHash')!=revision:row.pop(lane,None)
            elif row.get(lane,{}).get('status')=='running':row.pop(lane)
        state['jobs'].append(row)
    active={}
    with ThreadPoolExecutor(max_workers=args.simulation_workers + 1) as pool:
        while True:
            if source_hash()!=revision:
                state['state']='STOPPED_SOURCE_CHANGED';report(args.output,state)
                break
            if not (args.campaign/'status.json').exists():
                report(args.output,state)
                time.sleep(5)
                continue
            raw=read_json(args.campaign/'status.json')
            verified={r['jobId']:r for r in raw['results'] if r['status']=='verified'}
            for key,(future,row) in list(active.items()):
                lane = key[0]
                if not future.done():continue
                try:row[lane]=future.result()
                except Exception as exc:row[lane]={'status':'failed','sourceHash':revision,'error':str(exc)}
                del active[key]
            for row in state['jobs']:
                row['raw']='verified' if row['jobId'] in verified else 'pending'
                if row['raw']!='verified':continue
                for lane,work in lanes:
                    if not can_schedule(active, row, lane, args.simulation_workers):continue
                    run=Path(verified[row['jobId']]['runDirectory']);output=args.output/row['jobId']
                    row[lane]={'status':'running','sourceHash':revision}
                    active[(lane, row['jobId'])]=(pool.submit(work,run,output,revision),row)
            done=all(r.get(l,{}).get('status') in ('complete','failed') for r in state['jobs'] for l, _ in lanes)
            if done or (args.once and not active):
                state['state']='COMPLETE_WITH_ERRORS' if any(r.get(l,{}).get('status')=='failed' for r in state['jobs'] for l, _ in lanes) else 'COMPLETE'
                if not done:state['state']='PARTIAL'
                report(args.output,state);break
            report(args.output,state)
            time.sleep(5)


if __name__=='__main__':main()
