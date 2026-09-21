"""Refresh only UI on approved chapters, retaining the exact fight crop and timing.

The source is the previous verified comparison, never the output of this pass.
Replace its complete footer and add fixed opening counts below the existing
headers. Audio is copied. Original recordings and the previous master survive.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

from PIL import Image, ImageDraw
import build_champi_comparison_overlay as ui
from overlay.ffutil import find_ffmpeg, find_ffprobe

ROOT = ui.REPO
SOURCE = ROOT/'data/local/champi-comparison-full'
OUT = ROOT/'data/local/champi-overlay-v3'


def save(path, value):
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')


def main(preview=False):
    OUT.mkdir(parents=True,exist_ok=True)
    source = json.loads((SOURCE/'series-manifest.json').read_text())
    inputs = json.loads((SOURCE/'series-inputs.json').read_text())['chapters']
    font = ui.GameFont(ui.GAME)
    con = sqlite3.connect(f'file:{ROOT/"data/golden/aoe2_reference.db"}?mode=ro',uri=True)
    con.row_factory = sqlite3.Row
    tally = {c:[] for c in ui.CIVS}
    outputs=[]
    ff = find_ffmpeg()
    source_hash = hashlib.sha256(Path(ui.__file__).read_bytes()).hexdigest()
    for i,(chapter,data) in enumerate(zip(source['chapters'],inputs)):
        folder=OUT/f'{i+1:02}_{data["opponent"]["slug"]}'
        folder.mkdir(exist_ok=True)
        enemy = ui.resolve_stats(con,data['opponent'])
        featured = ui.resolve_stats(con,{'label':'Elite Champi Warrior','civ':'Incas','slug':'elite_champi_warrior_incas'})
        _, card = ui.panel(enemy,featured,font,ui.GAME,(232,58,49,255))
        base = ui.shared_footer(enemy,card['attackBonus'],font)
        before=base.copy();ui.draw_tally(before,tally,font)
        tally=ui.update_tally(tally,enemy['unit_name'],chapter['results'])
        if tally != chapter['tally']:
            raise ValueError('A UI-only refresh must not change credited victories')
        after=base.copy();ui.draw_tally(after,tally,font)
        # Preserve the original horizontal divider at the edge of the footage.
        for im,name in [(before,'before'),(after,'after')]:
            ImageDraw.Draw(im).line((0,ui.VIDEO_H,ui.W,ui.VIDEO_H),fill=(163,129,74),width=3)
            im.crop((0,ui.VIDEO_H,ui.W,ui.H)).save(folder/f'{name}.png')
        counts=[]
        for civ in ui.CIVS:
            recording=json.loads((Path(data['runs'][civ])/'recording.json').read_text())
            counts.append(tuple(recording['sides'][s]['count'] for s in ('side1','side2')))
        header=ui.starting_counts_layer(counts,font)
        header.save(folder/'counts.png')
        # Review beginning/end on representative ornate themes and a full tally.
        if i in (0,25,44,55,60,62,73):
            subprocess.run([ff,'-y','-v','error','-threads','2','-sseof','-0.2','-i',chapter['video'],
                            '-frames:v','1',str(folder/'source-end.png')],check=True)
            still=Image.open(folder/'source-end.png').convert('RGBA')
            still.paste(after.crop((0,ui.VIDEO_H,ui.W,ui.H)),(0,ui.VIDEO_H))
            still.alpha_composite(header,(0,0));still.convert('RGB').save(folder/'updated-end.jpg',quality=95)
        if preview:
            continue
        save(OUT/'status.json',dict(state='RENDERING',completed=i,total=len(inputs),opponent=enemy['unit_name'],updatedAt=time.time()))
        target=folder/'comparison.mp4'
        signature=hashlib.sha256(json.dumps(dict(renderer=source_hash,chapter=chapter,counts=counts,
            before=hashlib.sha256((folder/'before.png').read_bytes()).hexdigest(),
            after=hashlib.sha256((folder/'after.png').read_bytes()).hexdigest()),sort_keys=True).encode()).hexdigest()
        checkpoint=folder/'checkpoint.json'
        cached=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
        if not (target.exists() and cached.get('signature')==signature and cached.get('bytes')==target.stat().st_size):
            end=max(r['end'] for r in chapter['results'])
            # Overlay's repeatlast retains each single decoded PNG. Looping
            # the image demuxer would needlessly decode three PNGs every frame.
            graph=f'[0:v][1:v]overlay=0:960:repeatlast=1[a];[a][2:v]overlay=0:960:repeatlast=1:enable=gte(t\\,{end})[b];[b][3:v]overlay=0:0:repeatlast=1,format=yuv420p[v]'
            # Offline mode: let FFmpeg use the available CPU for decoding and
            # compositing while NVENC handles encoding. No capture is running.
            command=[ff,'-y','-v','warning','-threads','0','-filter_complex_threads','0','-i',chapter['video']]
            for png in ('before','after','counts'):
                command+=['-i',str(folder/f'{png}.png')]
            command+=['-filter_complex',graph,'-map','[v]','-map','0:a?','-t',str(chapter['durationSeconds']),
                      '-c:v','h264_nvenc','-preset','p5','-cq','18','-b:v','0','-pix_fmt','yuv420p',
                      '-r','30','-video_track_timescale','15360','-c:a','copy','-movflags','+faststart',str(target)]
            with (folder/'encode.log').open('w') as log:
                subprocess.run(command,check=True,stdout=log,stderr=log)
            subprocess.run([ff,'-v','error','-xerror','-threads','0','-i',str(target),'-f','null','-'],check=True)
            save(checkpoint,dict(signature=signature,bytes=target.stat().st_size))
        updated=dict(chapter,video=str(target),startingCounts=counts,
                     tallyRule='Transparent sprites enlarged 10%; sole winner soft glow',sourcePreviousVideo=chapter['video'])
        outputs.append(updated)
        save(OUT/'render-progress.json',dict(completed=i+1,total=len(inputs),chapters=outputs))
        print(f'Updated {i+1}/{len(inputs)}: {enemy["unit_name"]}',flush=True)
    con.close()
    if preview:
        print('Preview stills ready',flush=True)
        return
    concat=OUT/'concat.txt';concat.write_text(''.join(f"file '{Path(r['video']).as_posix()}'\n" for r in outputs))
    final=OUT/'Champi_Four_Civs_All_Unique_Units.mp4'
    subprocess.run([ff,'-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(final)],check=True)
    details=json.loads(subprocess.check_output([find_ffprobe(),'-v','error','-show_format','-show_streams','-of','json',str(final)]))
    if abs(float(details['format']['duration'])-float(source['probe']['format']['duration'])) > .5:
        raise ValueError('Refreshed video timing differs from approved original')
    save(OUT/'series-manifest.json',dict(video=str(final),chapters=outputs,tally=tally,probe=details))
    # Reuse existing bookends and preserve the narration state of both pages.
    import build_champi_comparison_bookends as bookends
    previous=json.loads((bookends.OUT/'assembly-manifest.json').read_text())
    bookends.SERIES=OUT
    bookends.assemble(previous['firstPageSeconds'],previous['narrationPage1'],previous.get('narrationPage2',False))
    save(OUT/'status.json',dict(state='COMPLETE',completed=len(outputs),total=len(outputs),
         video=str(OUT/'Champi_Four_Civs_Complete_With_Intro.mp4'),updatedAt=time.time()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-only',action='store_true')
    args=parser.parse_args()
    main(args.preview_only)
