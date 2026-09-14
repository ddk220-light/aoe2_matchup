"""Render reusable campaign-style pages and a paced, progressively revealed intro."""
import argparse
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw
from overlay.static_stats import GAME, GameFont
from overlay.ffutil import find_ffmpeg


def lines(font, text, size, width):
    result=[]
    for word in text.split():
        if not result or font.width(result[-1]+' '+word,size)>width:
            result.append(word)
        else:
            result[-1]+=' '+word
    return result


def build(plan_path, output, preview_only=False):
    plan_path=Path(plan_path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    plan=json.loads(plan_path.read_text())
    catalog=json.loads((plan_path.parent/'campaign_catalog.json').read_text())
    civ=plan['civilization'].upper()
    civ={'INDIANS':'HINDUSTANIS'}.get(civ,civ)
    theme=plan.get('backgroundTheme') or catalog['preferredByCivilization'].get(civ,catalog['fallback'])
    bg=Image.open(GAME/'widgetui'/theme['background']).convert('RGB').resize((2560,1080),Image.Resampling.LANCZOS).crop((320,0,2240,1080))
    art=Image.open(plan_path.parent/plan['art']).convert('RGBA')
    art.thumbnail(tuple(plan.get('artMaxSize', (340,510))),Image.Resampling.LANCZOS)
    # Multiply is the standard parchment compositor: white vanishes, ink remains.
    art_x,art_y=plan.get('artPosition', (510,310))
    box=(art_x,art_y,art_x+art.width,art_y+art.height)
    bg.paste(ImageChops.multiply(bg.crop(box),art.convert('RGB')),box,art.getchannel('A'))
    font=GameFont(GAME);entries=[];chapter=[];elapsed=0
    for index,slide in enumerate(plan['slides'],1):
        base=bg.convert('RGBA')
        text=Image.new('RGBA',base.size);y=320;glyphs=[]
        text_x=plan.get('textX',875);text_width=plan.get('textWidth',550)
        for para in slide['paragraphs']:
            for line in lines(font,para,30,text_width):
                x=text_x
                for char in line:
                    glyphs.append((x,y,char));x+=font.width(char,30)
                font.draw(text,(text_x,y),line,30);y+=39
            y+=25
        if y>795:raise ValueError(f'Slide {index} overflows parchment: {y}')
        final=Image.alpha_composite(base,text).convert('RGB')
        final.save(output/f'slide-{index:02}.png')
        chapter.append({'start':elapsed,'duration':slide['duration'],'characters':len(glyphs)})
        if not preview_only:
            # Pre-wrap the full text so letters never cause words to jump lines.
            # Exactly one character per reveal, quantized to two 30 fps frames.
            step=2/30
            reveal_times=[n*step for n in range(len(glyphs))]
            if slide.get('narrationAlignment'):
                timing=json.loads(Path(slide['narrationAlignment']).read_text())['alignment']
                source=timing['characters'];cursor=0;reveal_times=[]
                for _,_,char in glyphs:
                    # Wrapping removes whitespace at line breaks; all printed
                    # letters must match the actual synthesis alignment.
                    while cursor<len(source) and source[cursor].isspace() and source[cursor]!=char:
                        cursor+=1
                    if cursor>=len(source) or source[cursor]!=char:
                        raise ValueError('Unable to align rendered glyph with narration')
                    reveal_times.append(round((timing['character_start_times_seconds'][cursor]+slide.get('narrationLeadSeconds',0))*30)/30)
                    cursor+=1
            hold=slide['duration']-reveal_times[-1]
            if hold<1:raise ValueError('Allow time to read the complete page')
            frame=base.copy()
            if reveal_times[0]>0:
                blank=f'blank-{index:02}.png';frame.convert('RGB').save(output/blank)
                entries.append((blank,reveal_times[0]))
            for n,(x,y,char) in enumerate(glyphs):
                font.draw(frame,(x,y),char,30)
                duration=(reveal_times[n+1] if n+1<len(glyphs) else slide['duration'])-reveal_times[n]
                if duration<=0:continue
                name=f'letter-{index:02}-{n:03}.png';frame.convert('RGB').save(output/name,compress_level=1)
                entries.append((name,duration))
        elapsed+=slide['duration']
    (output/'manifest.json').write_text(json.dumps({'plan':str(plan_path.resolve()),'theme':theme,'duration':elapsed,'chapters':chapter,'audio':plan.get('music','none'),'narration':plan.get('narration')},indent=2))
    if preview_only:return
    concat=''.join(f"file '{name}'\nduration {seconds:.6f}\n" for name,seconds in entries)+f"file '{entries[-1][0]}'\n"
    (output/'frames.txt').write_text(concat)
    ff=find_ffmpeg()
    if not ff:raise FileNotFoundError('FFmpeg unavailable')
    audio=[]
    if plan.get('music'):
        audio=['-stream_loop','-1','-i',str(plan_path.parent/plan['music']['file'])]
    filters=[]
    if audio:
        filters=['-map','0:v:0','-map','1:a:0','-af',f'loudnorm=I=-25:TP=-3:LRA=7,afade=t=in:d=1.5,afade=t=out:st={elapsed-3}:d=3','-c:a','aac','-ar','48000','-b:a','192k']
    if plan.get('narration'):
        narration_index=2 if audio else 1
        audio+=['-i',str(plan_path.parent/plan['narration']['file'])]
        graph=f'[{narration_index}:a]loudnorm=I=-17:TP=-2:LRA=7[voice];'
        if narration_index==2:
            graph+=f'[1:a]loudnorm=I=-31:TP=-4:LRA=7,afade=t=in:d=1.5,afade=t=out:st={elapsed-3}:d=3[music];[voice][music]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89[mix]'
        else:
            graph+='[voice]anull[mix]'
        filters=['-filter_complex',graph,'-map','0:v:0','-map','[mix]','-c:a','aac','-ar','48000','-b:a','192k']
    with (output/'encode.log').open('w') as log:
        subprocess.run([ff,'-y','-v','warning','-f','concat','-safe','0','-i',str(output/'frames.txt'),*audio,*filters,'-vf','fps=30,format=yuv420p','-t',str(elapsed),'-c:v','libx264','-preset','fast','-crf','18','-threads','4','-movflags','+faststart',str(output/plan.get('videoFilename','tiger-cavalry-intro.mp4'))],check=True,stdout=log,stderr=log)
    print(output/plan.get('videoFilename','tiger-cavalry-intro.mp4'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',default='apps/video/intro/tiger-cavalry.json');p.add_argument('--output',default='aoe2x/js_simulation/calibration/lab/compilations/tiger-unique-units/intro-v2');p.add_argument('--preview-only',action='store_true');a=p.parse_args();build(a.plan,a.output,a.preview_only)
