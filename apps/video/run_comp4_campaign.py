"""Resume the four-arena raw-only campaign through the existing AoE2 Lab driver.

There is only one game worker. Offline QA runs in one background thread while
the driver loads the next scenario. All attempts, full frames and raw media are
retained; failed validation is never silently promoted to a good recording.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, msvcrt, os, shutil, subprocess, sys, time
from pathlib import Path
from auto import orchestrate_matchup as nav
from aoe2x.lab.config import load_config
from build_comp4_scenario import ROOT

def save(path,value):
    tmp=path.with_suffix('.tmp.json');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(path)

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def qa(folder,plan):
    import cv2
    state=json.loads((folder/'status.json').read_text())
    if state['state']!='COMPLETE':raise ValueError(state['state'])
    if len(state['pairs'])!=4 or not state['initialVerified']:raise ValueError('Missing initial state or results')
    cap=cv2.VideoCapture(str(folder/'raw.mp4'))
    fps=cap.get(cv2.CAP_PROP_FPS);frames=cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if fps<20 or frames/fps<3:raise ValueError('Unreadable video')
    if (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))!=(2560,1440):raise ValueError('Unexpected capture resolution')
    if state['finishedEpoch']-max(r['endWallEpoch'] for r in state['pairs'].values())<3:raise ValueError('Final result hold is too short')
    # Decode first, middle and last frames. Detect the first arena frame using
    # the existing offline luma detector; this never drives the game UI.
    from overlay.video_extract import find_game_start
    start=find_game_start(folder/'raw.mp4',t_from=0,t_to=min(frames/fps,90))
    if start is None:raise ValueError('No loading-to-arena transition')
    for label,t in [('opening',start+.7),('middle',(start+frames/fps)/2),('ending',frames/fps-.2)]:
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,image=cap.read()
        if not ok:raise ValueError('Video decode failed: '+label)
        cv2.imwrite(str(folder/f'qa-{label}.jpg'),cv2.resize(image,(1280,720)))
    cap.release()
    # Audit the complete length-prefixed protobuf container, including the last
    # record. Retain the original bytes for future decoder/simulation work.
    import struct
    records=0
    with (folder/'frames.bin').open('rb') as f:
        while header:=f.read(4):
            if len(header)!=4:raise ValueError('Truncated frame header')
            size=struct.unpack('<I',header)[0]
            if len(f.read(size))!=size:raise ValueError('Truncated protobuf sequence')
            records+=1
    if records<10:raise ValueError('Insufficient gRPC sequences')
    result={'state':'VERIFIED','automaticQA':True,'visualQA':'CONTACT_FRAMES_READY',
            'scenarioSha256':plan['scenarioSha256'],'videoStartSeconds':start,
            'duration':frames/fps,'fps':fps,'grpcSequences':records,'pairs':state['pairs'],
            'files':{n:{'bytes':(folder/n).stat().st_size,'sha256':digest(folder/n)} for n in ['raw.mp4','frames.bin','timeline.jsonl']}}
    save(folder/'validation.json',result)
    return result

def run(args):
    manifest=json.loads(args.manifest.read_text());directory=args.manifest.parent
    status={'state':'STARTING','pid':os.getpid(),'total':len(manifest['jobs']),'completed':{},'failed':{},'active':None}
    pending=[];consecutive=0;last_thermal=0
    def checkpoint():
        status['updatedEpoch']=time.time();save(directory/'status.json',status)
    def harvest(wait=False):
        nonlocal consecutive
        for item in pending[:]:
            job,folder,future=item
            if wait or future.done():
                try:
                    result=future.result();status['completed'][job['id']]={'capture':str(folder),'pairs':result['pairs']};consecutive=0
                except Exception as error:
                    status['failed'][job['id']]={'capture':str(folder),'error':str(error)};consecutive+=1
                pending.remove(item);checkpoint()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        try:
            for job in manifest['jobs']:
                folder=Path(job['scenario']).parent;plan=json.loads(Path(job['plan']).read_text())
                good=[]
                for receipt in folder.glob('capture-*/validation.json'):
                    data=json.loads(receipt.read_text())
                    if data.get('state')=='VERIFIED' and data.get('scenarioSha256')==plan['scenarioSha256']:
                        if all((receipt.parent/name).exists() and (receipt.parent/name).stat().st_size==proof['bytes'] and digest(receipt.parent/name)==proof['sha256'] for name,proof in data['files'].items()):good.append(receipt.parent)
                if good:
                    status['completed'][job['id']]={'capture':str(good[-1]),'pairs':json.loads((good[-1]/'validation.json').read_text())['pairs']};continue
                harvest()
                if (directory/'PAUSE').exists():status['state']='PAUSED';break
                if consecutive>=3:raise RuntimeError('Three consecutive failures; investigation required')
                if shutil.disk_usage(directory).free<8*1024**3:raise RuntimeError('Less than 8 GiB available on capture drive')
                if time.time()-last_thermal>=900:
                    subprocess.run([sys.executable,str(ROOT/'apps/video/thermal_guard.py')],cwd=ROOT,timeout=60,check=True)
                    last_thermal=time.time()
                thermal=ROOT/'data/local/thermal/status.json'
                if thermal.exists() and json.loads(thermal.read_text()).get('state')=='PAUSED':raise RuntimeError('Thermal pause is active')
                if digest(Path(job['scenario']))!=plan['scenarioSha256']:raise ValueError('Scenario changed after preflight')
                attempt=len(list(folder.glob('capture-*')))+1;capture=folder/f'capture-{attempt:02}'
                status.update(state='NAVIGATING',active={'id':job['id'],'opponent':job['opponent'],'capture':str(capture)});checkpoint()
                logfile=folder/f'navigation-{attempt:02}.log'
                name=nav.stage_generated(job['scenario'],stage_name='Comp4 Matchup Run',logfile=logfile)
                st=nav.bring_game_to_front(logfile)
                if st not in ('editor','load_dialog','main_menu'):
                    if not nav.return_to_editor(logfile,completed_test=True):raise RuntimeError('Cannot return to scenario editor')
                    st='editor'
                if not nav.navigate_to_test_menu(st,name,logfile):raise RuntimeError('Cannot reach the staged scenario Test menu')
                with (folder/f'capture-{attempt:02}.log').open('w',encoding='utf-8') as log:
                    proc=subprocess.Popen([sys.executable,str(ROOT/'apps/video/capture_comp4_spike.py'),'--out',str(capture),'--plan',job['plan'],'--seconds',str(args.seconds)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                    deadline=time.monotonic()+20
                    while time.monotonic()<deadline and proc.poll() is None:
                        path=capture/'status.json'
                        if path.exists() and json.loads(path.read_text())['state']=='ARMED':break
                        time.sleep(.2)
                    else:raise RuntimeError('Recorder did not arm')
                    if not nav.find_and_click('Test',nav.R_TEST,logfile,'Test'):
                        (capture/'STOP').touch();proc.wait(timeout=20);raise RuntimeError('Test button not found')
                    nav._park_cursor(logfile)
                    status['state']='CAPTURING';status['capturePid']=proc.pid;checkpoint()
                    proc.wait(timeout=args.seconds+30)
                if proc.returncode:
                    result=json.loads((capture/'status.json').read_text())
                    status['failed'][job['id']]={'capture':str(capture),'error':result['state']};consecutive+=1;checkpoint()
                else:pending.append((job,capture,pool.submit(qa,capture,plan)))
                if args.limit and len(status['completed'])+len(status['failed'])+len(pending)>=args.limit:break
            harvest(wait=True)
            if status['state']!='PAUSED':status['state']='COMPLETE' if len(status['completed'])==len(manifest['jobs']) else 'NEEDS_REVIEW' if status['failed'] else 'PARTIAL'
            status['active']=None;checkpoint()
        except Exception as error:
            status.update(state='BLOCKED',error=f'{type(error).__name__}: {error}');checkpoint()
            harvest(wait=True)
            raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'data/local/comp4-champi-all-unique/manifest.json')
    parser.add_argument('--seconds',type=int,default=240)
    parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args()
    with (load_config().artifacts_root/'recorder-campaign.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        run(args)
