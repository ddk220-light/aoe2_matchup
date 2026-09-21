"""Prepare and render the first N archived geometric Champi comparisons.

Two bounded offline alignment workers; encoding is sequential. Does not touch
the recorder or archive inputs. Each chapter inherits the previous tally.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import hashlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from build_champi_comparison_overlay import build, CIVS, OUT as PILOT, REPO
from materialize_compact_recording import materialize
from overlay.auto_alignment import align
from overlay.unit_timeline import decode
from overlay.ffutil import find_ffmpeg, find_ffprobe

OUT = REPO/'data/local/champi-comparison-first-five'
REVIEW = OUT


def save(path, value):
    temporary=path.with_suffix('.tmp.json')
    temporary.write_text(json.dumps(value,indent=2),encoding='utf-8')
    temporary.replace(path)


def status(state, **details):
    save(OUT/'status.json',dict(state=state,pid=os.getpid(),updatedAt=time.time(),**details))


def thermal_monitor(stop):
    """Keep the existing temperature guard active during long offline renders."""
    while not stop.is_set():
        with (OUT/'thermal.log').open('a',encoding='utf-8') as log:
            subprocess.run([sys.executable,str(REPO/'apps/video/thermal_guard.py')],stdout=log,stderr=log)
        stop.wait(900)


def prepare(count, start=0):
    OUT.mkdir(parents=True,exist_ok=True)
    catalogs={c:json.loads(Path(f'D:/AoE2 Renders/champi-geometric-{c.lower()}/run.json').read_text()) for c in CIVS}
    chapters=[]
    tasks=[]
    if count > min(len(c['matchups']) for c in catalogs.values()):
        raise ValueError('Requested more opponents than are archived')
    for index in range(start,count):
        rows={c:catalogs[c]['matchups'][index] for c in CIVS}
        side=rows['Incas']['plan']['side3']
        if any(r['plan']['side3']['slug']!=side['slug'] for r in rows.values()):
            raise ValueError('Archive ordering differs between civilizations')
        chapter=dict(index=index+1,opponent=side,runs={})
        for civ,row in rows.items():
            tasks.append((civ,row,index,chapter))
        chapters.append(chapter)

    def one(civ,row,index,chapter):
        job=row['jobId']
        pilot=PILOT/'render-workspace'/job/'live/run_001'
        review=REVIEW/'render-workspace'/job/'live/run_001'
        run=next((p for p in (pilot,review) if (p/'timeline.json').exists()),
                 OUT/'render-workspace'/job/'live/run_001')
        if not (run/'battle.mp4').exists():
            run=materialize(Path(f'D:/AoE2 Renders/champi-geometric-{civ.lower()}/run.json'),job,OUT/'render-workspace')
        if not (run/'timeline.json').exists():
            print(f'Aligning {index+1}: {civ} vs {chapter["opponent"]["label"]}',flush=True)
            try:
                align(run)
            except ValueError as exc:
                if 'Ambiguous HP/video alignment' not in str(exc):raise
                align(run,sample_rate=6,color_components=True)
            (run/'timeline.json').write_text(json.dumps(decode(run)),encoding='utf-8')
        return civ,index,str(run)

    errors=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(one,*t) for t in tasks]
        for future in as_completed(futures):
            try:
                civ,index,run=future.result();chapters[index-start]['runs'][civ]=run
                print(f'Prepared {index+1} {civ}',flush=True)
            except Exception as exc:
                errors.append(str(exc));print('PREPARATION ERROR:',exc,flush=True)
    save(OUT/'preparation.json',dict(chapters=chapters,errors=errors))
    if errors:raise RuntimeError('Some alignments need review; see series-inputs.json')
    return chapters


def render(chapters,stills=False,final_name='Champi_Four_Civs_First_Five_Matchups.mp4',count=None):
    tally={c:[] for c in CIVS};outputs=[]
    inputs=[]
    renderer_hash=hashlib.sha256((REPO/'apps/video/build_champi_comparison_overlay.py').read_bytes()).hexdigest()
    for index in range(count if count is not None else len(chapters)):
        if shutil.disk_usage(OUT).free < 8*2**30:
            raise RuntimeError('Less than 8 GiB free; sources retained, rendering stopped')
        if (REPO/'data/local/thermal/PAUSED.json').exists():
            raise RuntimeError('Thermal pause is active; sources retained')
        status('PREPARING',completed=len(outputs),total=count or len(chapters),chapter=index+1)
        ch=prepare(index+1,start=index)[0] if count is not None else chapters[index]
        inputs.append(ch)
        save(OUT/'series-inputs.json',dict(chapters=inputs))
        folder=OUT/f'{ch["index"]:02d}_{ch["opponent"]["slug"]}'
        status('RENDERING',completed=len(outputs),total=count or len(chapters),chapter=index+1,opponent=ch['opponent']['label'])
        print('BUILD',folder.name,flush=True)
        signature=hashlib.sha256(json.dumps(dict(renderer=renderer_hash,chapter=ch,tally=tally),sort_keys=True).encode()).hexdigest()
        checkpoint=folder/'series-checkpoint.json'
        cached=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
        result=cached.get('result',{})
        video=Path(result.get('video',''))
        if not stills and cached.get('signature')==signature and video.is_file() and video.stat().st_size==cached.get('videoBytes'):
            print('Reusing verified chapter',index+1,flush=True)
        else:
            result=build(folder,stills_only=stills,opponent=ch['opponent'],run_paths=ch['runs'],prior_tally=tally)
            if not stills:
                # Decode each chapter before accepting it for resume/concatenation.
                subprocess.run([find_ffmpeg(),'-v','error','-xerror','-i',result['video'],'-f','null','-'],check=True)
                save(checkpoint,dict(signature=signature,result=result,videoBytes=Path(result['video']).stat().st_size))
        tally=result['tally'];outputs.append(result)
        save(OUT/'render-progress.json',dict(completed=len(outputs),chapters=outputs,tally=tally))
    if stills:return
    ff=find_ffmpeg();probe=find_ffprobe()
    concat=OUT/'concat.txt'
    concat.write_text('\n'.join("file '"+r['video'].replace('\\','/')+"'" for r in outputs),encoding='utf-8')
    status('STITCHING',completed=len(outputs),total=len(outputs))
    final=OUT/final_name
    subprocess.run([ff,'-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(final)],check=True)
    details=json.loads(subprocess.check_output([probe,'-v','error','-show_format','-show_streams','-of','json',str(final)]))
    expected=sum(r['durationSeconds'] for r in outputs)
    if abs(float(details['format']['duration'])-expected)>1:
        raise ValueError('Combined duration differs from chapters')
    manifest=dict(video=str(final),chapters=outputs,tally=tally,probe=details)
    (OUT/'series-manifest.json').write_text(json.dumps(manifest,indent=2))
    status('COMPLETE',completed=len(outputs),total=len(outputs),video=str(final),durationSeconds=float(details['format']['duration']))
    print('FINISHED',final,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--count',type=int,default=5)
    p.add_argument('--all',action='store_true',help='Render every archived opponent in order')
    p.add_argument('--output',type=Path,default=OUT)
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--stills-only',action='store_true')
    a=p.parse_args()
    OUT=a.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
    count=len(json.loads(Path('D:/AoE2 Renders/champi-geometric-incas/run.json').read_text())['matchups']) if a.all else a.count
    stop=threading.Event()
    monitor=threading.Thread(target=thermal_monitor,args=(stop,),daemon=True)
    monitor.start()
    try:
        if a.prepare_only:prepare(count)
        else:render([],a.stills_only,'Champi_Four_Civs_All_Unique_Units.mp4' if a.all else 'Champi_Four_Civs_First_Five_Matchups.mp4',count=count)
    except BaseException as exc:
        status('NEEDS_ATTENTION',error=str(exc))
        raise
    finally:
        stop.set()
