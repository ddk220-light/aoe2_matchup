"""Compose fixed comparison panels in FFmpeg and encode with NVENC.

Python writes only reusable static UI assets. Decoding, crop/scale, the result
holds and all per-frame composition stay in FFmpeg, avoiding a Python RGB pipe.
"""
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw
from overlay.ffutil import find_ffmpeg, find_ffprobe


def encode(video, jobs, headers, counts, before, after, duration, start, hold):
    folder=video.parent/'ui-assets';folder.mkdir(exist_ok=True)
    before.save(folder/'before.png')
    after.crop((0,960,2560,1440)).save(folder/'after.png')
    hud=Image.new('RGBA',(2560,1440))
    for i,header in enumerate(headers):hud.alpha_composite(header,(i*640,0))
    hud.alpha_composite(counts,(0,0))
    d=ImageDraw.Draw(hud)
    for x in (640,1280,1920):
        d.line((x,0,x,960),fill=(43,35,23),width=4)
        d.line((x+1,0,x+1,960),fill=(156,126,74),width=1)
    d.line((0,960,2560,960),fill=(163,129,74),width=3)
    hud.save(folder/'hud.png')
    for i,job in enumerate(jobs):job['result'].save(folder/f'result-{i}.png')
    cmd=[find_ffmpeg(),'-y','-v','warning','-filter_complex_threads','1']
    def png(path):cmd.extend(['-loop','1','-framerate','30','-t',str(duration+1),'-i',str(path)])
    png(folder/'before.png')
    filters=[]
    for i,job in enumerate(jobs):
        if job['run'] is None:
            cmd.extend(['-f','lavfi','-i',f'color=c=0x23201b:s=640x960:r=30:d={duration}'])
            filters.append(f'[{i+1}:v]setpts=PTS-STARTPTS[p{i}]')
        else:
            cmd.extend(['-threads','2','-i',str(job['run']/'battle.mp4')])
            filters.append(f'[{i+1}:v]trim=start={start}:end={job["endSource"]},'
                           f'setpts=PTS-STARTPTS,fps=30,crop=960:1440:890:0,'
                           f'scale=640:960:flags=lanczos,setsar=1,'
                           f'tpad=stop_mode=clone:stop_duration={duration}[p{i}]')
    png(folder/'after.png');png(folder/'hud.png')
    for i in range(4):png(folder/f'result-{i}.png')
    filters.append('[0:v]format=yuv420p[b0]')
    for i in range(4):filters.append(f'[b{i}][p{i}]overlay=x={i*640}:y=0[b{i+1}]')
    filters.append(f'[b4][5:v]overlay=x=0:y=960:enable=gte(t\\,{duration-hold})[b5]')
    filters.append('[b5][6:v]overlay=x=0:y=0[b6]')
    for i,job in enumerate(jobs):
        filters.append(f'[b{i+6}][{i+7}:v]overlay=x={i*640}:y=245:enable=gte(t\\,{job["end"]})[b{i+7}]')
    audio=max(range(4),key=lambda i:jobs[i]['end'])+1
    graph=folder/'filtergraph.txt';graph.write_text(';\n'.join(filters))
    temporary=video.with_suffix('.partial.mp4')
    silent=video.with_suffix('.video-only.mp4')
    cmd.extend(['-filter_complex_script',str(graph),'-map','[b10]','-an',
                '-t',str(duration),'-frames:v',str(math.ceil(duration*30)),'-c:v','h264_nvenc','-preset','p5','-cq','19','-b:v','0',
                '-pix_fmt','yuv420p','-video_track_timescale','15360','-movflags','+faststart',str(silent)])
    with (video.parent/'render.log').open('w') as log:
        subprocess.run(cmd,stdout=log,stderr=log,check=True,timeout=max(120,duration*6))
        # Keep soundtrack padding out of the multi-input video graph: FFmpeg
        # can deadlock at EOF when one demuxer's audio and trimmed video share
        # that graph. This stream-copy mux adds no video encoding work.
        subprocess.run([find_ffmpeg(),'-y','-v','warning','-i',str(silent),'-ss',str(start),
             '-i',str(jobs[audio-1]['run']/'battle.mp4'),'-map','0:v','-map','1:a:0',
             '-c:v','copy','-af',f'apad,afade=t=out:st={duration-1}:d=1',
             '-t',str(duration),'-c:a','aac','-ar','48000','-ac','2','-b:a','192k',
             '-movflags','+faststart',str(temporary)],stdout=log,stderr=log,check=True,timeout=90)
    data=json.loads(subprocess.check_output([find_ffprobe(),'-v','error','-show_format','-show_streams','-of','json',str(temporary)]))
    if abs(float(data['format']['duration'])-duration)>.15:
        raise ValueError('Encoded chapter duration mismatch')
    if {s['codec_type'] for s in data['streams']}!={'audio','video'}:
        raise ValueError('Encoded chapter is missing audio or video')
    temporary.replace(video)
    silent.unlink()
