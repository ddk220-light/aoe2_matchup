"""Resume an overlay-only campaign without rerunning simulations or recordings."""
import argparse, concurrent.futures, json, os, time, tomllib
from pathlib import Path
from aoe2x.lab.postprocess_campaign import overlay, source_hash
from aoe2x.lab.io import write_json

ROOT=Path(__file__).resolve().parents[2]
LAB=ROOT/'aoe2x/js_simulation/calibration/lab'

def capture_is_terminal(state):
    # STOPPED is a resumable operator pause, not evidence of failed captures.
    return state in ('COMPLETE','COMPLETE_WITH_FAILURES','STOPPED_AFTER_ERRORS','CRASHED','FAILED','NEEDS_ATTENTION')

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=3)
    p.add_argument('--recording-status',type=Path,help='Only schedule bundles verified by this active recorder campaign')
    a=p.parse_args()
    if not 1<=a.workers<=8:p.error('workers must be between 1 and 8')
    a.output.mkdir(parents=True,exist_ok=True)
    import msvcrt
    lock=(a.output/'worker.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    manifest_text=a.manifest.read_text(encoding='utf-8-sig')
    manifest=json.loads(manifest_text) if a.manifest.suffix.lower()=='.json' else tomllib.loads(manifest_text)
    specs=manifest['matchups'];roster={u['slug']:u for u in json.loads((ROOT/'data/unique-unit-roster.json').read_text())['units']}
    old=json.loads((a.output/'status.json').read_text()) if (a.output/'status.json').exists() else {'jobs':[]}
    previous={j['jobId']:j for j in old['jobs']};revision=source_hash();jobs=[]
    for s in specs:
        j=previous.get(s['id'],{'jobId':s['id'],'civ':roster[s['side3']]['civ'],'unit':roster[s['side3']]['label']})
        if j.get('overlay',{}).get('status')!='complete' or not Path(j.get('overlay',{}).get('video','missing')).is_file():j['overlay']={'status':'pending'}
        jobs.append(j)
    state={'state':'RUNNING','pid':os.getpid(),'sourceHash':revision,'jobs':jobs}
    def save():
        state['completed']=sum(j['overlay']['status']=='complete' for j in jobs);state['failed']=sum(j['overlay']['status']=='failed' for j in jobs);state['updatedAt']=time.time();write_json(a.output/'status.json',state)
    save()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        active={};pending=[j for j in jobs if j['overlay']['status']!='complete']
        while pending or active:
            capture=json.loads(a.recording_status.read_text()) if a.recording_status and a.recording_status.exists() else {}
            ready={r['jobId'] for r in capture.get('results',[]) if r['status']=='verified'}
            ended=capture_is_terminal(capture.get('state'))
            state['state']='WAITING_FOR_RECORDINGS' if capture.get('state')=='STOPPED' else 'RUNNING'
            for j in list(pending):
                if len(active)>=a.workers:break
                if a.recording_status and j['jobId'] not in ready:
                    if ended:
                        j['overlay']={'status':'failed','error':'Recording campaign ended without a verified raw bundle'};pending.remove(j);save()
                    continue
                pending.remove(j);j['overlay']={'status':'running'}
                active[pool.submit(overlay,LAB/'runs'/j['jobId']/'live/run_001',a.output/j['jobId'],revision)]=j
                save()
            if not active:
                if pending:save();time.sleep(10)
                continue
            done,_=concurrent.futures.wait(active,timeout=10,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                j=active.pop(future)
                try:j['overlay']=future.result()
                except Exception as e:j['overlay']={'status':'failed','error':repr(e)}
                save();print(json.dumps({'completed':state['completed'],'failed':state['failed'],'jobId':j['jobId'],'result':j['overlay']['status']}),flush=True)
    state['state']='COMPLETE' if not state['failed'] else 'NEEDS_ATTENTION';save()
if __name__=='__main__':main()
