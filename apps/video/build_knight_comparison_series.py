"""Build the approved Paladin/Cavalier comparisons from compact archives.

One video chapter is encoded at a time. Four input decodes run concurrently;
full-resolution telemetry determines outcomes, while result timing follows the
owner's accepted approximate-placement policy. Original archives are read-only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from build_champi_comparison_overlay import build, REPO
from materialize_compact_recording import materialize
from overlay.unit_timeline import decode
from overlay.battle_end import terminal_row
from overlay.ffutil import find_ffmpeg, find_ffprobe


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp.json');tmp.write_text(json.dumps(value,indent=2));tmp.replace(p)


def catalog(profile):
    catalogs={};order=[]
    for column in profile['columns']:
        index=Path(column['archive']);entries=read(index)['matchups']
        rows={r['plan']['side3']['slug']:(index,r) for r in entries}
        for override in column.get('overrideArchives',[]):
            override=Path(override)
            for row in read(override)['matchups']:
                rows[row['plan']['side3']['slug']]=(override,row)
        catalogs[column['civ']]=rows
        for row in entries:
            slug=row['plan']['side3']['slug']
            if slug not in order:order.append(slug)
    return catalogs,order


def prepare_input(index,row,out):
    jid=row['jobId'];run=out/'render-workspace'/jid/'live/run_001'
    if not (run/'recording.json').exists():run=materialize(index,jid,out/'render-workspace')
    if (run/'timeline.json').exists():return str(run)
    recording=read(run/'recording.json')
    timeline=decode(run)
    end=terminal_row(timeline['rows'])
    hp=[sum(u['hp'] for u in end['sides'][o]) for o in ('2','3')]
    if min(hp)>0:raise ValueError(f'{jid}: stream does not contain a completed fight')
    alignment_path=run/'unit-hp-overlay/alignment.json'
    if not alignment_path.exists():
        # Result cards only: no per-unit HP animation is being synchronized.
        # The reviewed capture examples establish speed 2 and a short initial
        # camera/load offset. Bound the estimate inside the saved video, and
        # preserve its approximate status instead of calling it measured.
        duration=recording['presentation']['media']['durationSeconds']
        speed=2.0;offset=-.75
        estimated=end['gameMs']/1000/speed+offset
        clamped=min(max(estimated,.5),max(.5,duration-.5))
        offset+=clamped-estimated
        save(alignment_path,dict(videoSha256=recording['files']['battleVideo']['sha256'],
             gameSpeed=speed,videoOffsetSeconds=offset,estimated=True,
             method='Approximate result placement accepted by owner on 2026-09-15',
             intendedUse='End-result card only; not synchronized HP animation'))
        timeline=decode(run)
        timeline['mapping']['precision']='Approximate result timing; owner accepts a few seconds tolerance.'
    save(run/'timeline.json',timeline)
    return str(run)


def require_available_media(catalogs, order):
    """Stop before rendering if a retained result has no reconstructible footage."""
    missing=[]
    for civ, rows in catalogs.items():
        for slug in order:
            if slug not in rows:  # Self-matches are handled by the series builder.
                continue
            index,row=rows[slug]
            files=row.get('files',{})
            if (row.get('metadataOnly') or row.get('mediaAvailable') is False
                    or any(name not in files or not (index.parent/files[name]['path']).is_file()
                           for name in ('battle.mp4','frames.bin'))):
                missing.append(f'{civ} vs {slug}')
    if missing:
        raise FileNotFoundError(f'{len(missing)} requested battles lack raw video/frame pairs: '
            + '; '.join(missing[:5]) + '. Locate the original files; do not automatically recapture.')


def run(plan_path,out,count=None):
    profile=read(plan_path);out.mkdir(parents=True,exist_ok=True)
    catalogs,order=catalog(profile);order=order[:count] if count else order
    require_available_media(catalogs,order)
    civs=[c['civ'] for c in profile['columns']]
    tally={c:[] for c in civs};outputs=[];chapters=[]
    source_hash=hashlib.sha256(b''.join((REPO/'apps/video'/p).read_bytes() for p in
                ['build_champi_comparison_overlay.py','encode_comparison_fast.py',Path(__file__).name])).hexdigest()
    def status(state,**extra):save(out/'status.json',dict(state=state,pid=os.getpid(),updatedAt=time.time(),completed=len(outputs),total=len(order),**extra))
    stop=threading.Event()
    def thermal():
        while not stop.is_set():
            with (out/'thermal.log').open('a') as log:
                subprocess.run([os.sys.executable,str(REPO/'apps/video/thermal_guard.py')],stdout=log,stderr=log)
            stop.wait(900)
    threading.Thread(target=thermal,daemon=True).start()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for n,slug in enumerate(order,1):
                if (REPO/'data/local/thermal/PAUSED.json').exists():raise RuntimeError('Thermal pause active')
                if shutil.disk_usage(out).free<8*2**30:raise RuntimeError('Disk reserve reached')
                rows={c:catalogs[c].get(slug) for c in civs}
                opponent=next(v[1]['plan']['side3'] for v in rows.values() if v)
                for col in profile['columns']:
                    if rows[col['civ']] is None and col['side']['slug']!=slug:
                        raise ValueError(f'Missing capture: {col["civ"]} vs {slug}')
                folder=out/f'{n:02}_{slug}';checkpoint=folder/'series-checkpoint.json'
                sig=hashlib.sha256(json.dumps(dict(profile=profile,renderer=source_hash,slug=slug,tally=tally,
                   sources={c: v[1]['files'] if v else None for c,v in rows.items()}),sort_keys=True).encode()).hexdigest()
                cached=read(checkpoint) if checkpoint.exists() else {}
                result=cached.get('result',{});video=Path(result.get('video',''))
                if cached.get('signature')==sig and video.is_file() and video.stat().st_size==cached.get('videoBytes'):
                    print('REUSE',n,slug,flush=True)
                    chapter=cached['chapter']
                else:
                    status('PREPARING',chapter=n,opponent=opponent['label'])
                    futures={c:pool.submit(prepare_input,*v,out) for c,v in rows.items() if v}
                    paths={c:futures[c].result() if c in futures else None for c in civs}
                    chapter=dict(index=n,opponent=opponent,runs=paths)
                    status('RENDERING',chapter=n,opponent=opponent['label'])
                    print('RENDER',n,slug,flush=True)
                    result=build(folder,opponent=opponent,run_paths=paths,prior_tally=tally,profile=profile)
                    save(checkpoint,dict(signature=sig,result=result,chapter=chapter,videoBytes=Path(result['video']).stat().st_size))
                tally=result['tally'];outputs.append(result);chapters.append(chapter)
                save(out/'render-progress.json',dict(completed=len(outputs),chapters=outputs,tally=tally))
                save(out/'series-inputs.json',dict(chapters=chapters))
                status('CHAPTER_COMPLETE',chapter=n)
        status('STITCHING')
        listing=out/'concat.txt';listing.write_text('\n'.join("file '"+r['video'].replace('\\','/')+"'" for r in outputs))
        video=out/(profile['unit']+'_Four_Civs_All_Unique_Units.mp4')
        subprocess.run([find_ffmpeg(),'-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(video)],check=True)
        probe=read_probe(video)
        if abs(float(probe['format']['duration'])-sum(r['durationSeconds'] for r in outputs))>1:raise ValueError('Compilation duration mismatch')
        save(out/'series-manifest.json',dict(video=str(video),chapters=outputs,tally=tally,probe=probe,profile=str(plan_path)))
        status('COMPLETE',video=str(video));print('COMPLETE',video,flush=True)
    except BaseException as e:
        status('NEEDS_ATTENTION',error=str(e));raise
    finally:stop.set()


def read_probe(video):
    return json.loads(subprocess.check_output([find_ffprobe(),'-v','error','-show_format','-show_streams','-of','json',str(video)]))


def serialized_run(plan,out,count=None):
    """Allow an early render while the upload queue waits, without two writers.

    Windows releases the byte-range lock even if a worker crashes. A queued
    invocation waits, then reuses the normal verified chapter checkpoints.
    """
    import msvcrt
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.render.lock').open('a+b') as lock:
        if lock.tell()==0:
            lock.write(b'0');lock.flush()
        deadline=time.monotonic()+12*3600
        waiting=False
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                break
            except OSError:
                if time.monotonic()>deadline:raise TimeoutError('Another renderer still owns this episode')
                if not waiting:print('WAIT: this episode is already rendering',flush=True);waiting=True
                time.sleep(10)
        try:run(plan,out,count)
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--count',type=int)
    a=p.parse_args();serialized_run(a.plan.resolve(),a.output.resolve(),a.count)
