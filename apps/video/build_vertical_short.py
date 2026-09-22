"""Compose a 9:16 matchup from raw gameplay and verified per-unit timing.

Does not modify source videos, timelines or the active campaign renderer.
"""
import argparse,json,subprocess,math
from pathlib import Path
from functools import lru_cache
import cv2
from PIL import Image,ImageDraw,ImageOps,ImageEnhance
from overlay.static_stats import GAME,GameFont,portrait_path
from overlay.unit_timeline import sample_at,ordered_units
from overlay.ffutil import find_ffmpeg
from overlay.battle_end import terminal_row
from aoe2x.lab.balance import balance_caption

W,H=1080,1920
GAME_Y=330
INK=(246,230,191,255)
BLUE=(88,140,255,255)
RED=(244,101,89,255)

def build(run,out,start=.2,crop_x=640,camera='fixed',enhance_model=None):
 out.mkdir(parents=True,exist_ok=True)
 data=json.loads((run/'unit-hp-overlay/units.json').read_text())
 if not data['mapping'].get('alignment'): raise ValueError('Verified HP alignment required')
 stats=json.loads((run/'static-stats-overlay/stats.json').read_text())
 font=GameFont(GAME)
 @lru_cache(maxsize=1024)
 def label(text,size,color=INK):
  im=Image.new('RGBA',(math.ceil(font.width(text,size))+8,size+18));font.draw(im,(2,0),text,size,color);return im
 def put(im,text,xy,size,color=INK,center=False):
  tile=label(text,size,color);x,y=xy
  if center:x-=tile.width//2
  im.alpha_composite(tile,(int(x),int(y)))
 base=Image.new('RGBA',(W,H),(24,22,20,255));d=ImageDraw.Draw(base)
 d.rectangle((18,18,1061,1901),outline=(120,97,57,255),width=2)
 d.line((32,314,1048,314),fill=(171,137,78,255),width=2)
 d.line((32,1422,1048,1422),fill=(171,137,78,255),width=2)
 panels=Image.open(run/'static-stats-overlay/panels.png').convert('RGBA')
 for i in range(2):
  half=panels.crop((i*1280,0,(i+1)*1280,1440));card=half.crop(half.getbbox());card.thumbnail((510,350),Image.Resampling.LANCZOS)
  base.alpha_composite(card,(20+i*530,1435))
 plan=json.loads((run.parent.parent/'plan.json').read_text())
 mixed=plan['scenario']['family'] in ('melee_vs_ranged','ranged_vs_melee')
 put(base,balance_caption(plan),(540,1790 if mixed else 1812),29,center=True)
 if mixed:
  rule='No extra frontline buffer' if plan['scenario'].get('player4Buffer')=='none' else 'Ranged units get a small front line of Hussars'
  put(base,rule,(540,1830),27,center=True)
 put(base,'aoe2matchup.com',(540,1872 if mixed else 1860),25,(184,160,116,255),center=True)
 base.save(out/'layout.png')
 rows=data['rows'];times=[r['videoSeconds'] for r in rows]
 # Entity identity persists when ownership changes through conversion.
 origins={}
 for row in rows:
  for i,o in enumerate(('2','3')):
   for u in row['sides'][o]:origins.setdefault(u['id'],i)
 capacity=max(27,max(sum(u['hp']>0 for u in r['sides'][o]) for r in rows for o in ('2','3')))
 columns=math.ceil(capacity/3);step=min(56,504//columns);tile_size=step-4
 portraits=[Image.open(portrait_path(u['unit'])).convert('RGBA').resize((48,48),Image.Resampling.LANCZOS) for u in stats['units']]
 dead=[ImageEnhance.Brightness(ImageOps.grayscale(im).convert('RGBA')).enhance(.35) for im in portraits]
 @lru_cache(maxsize=1024)
 def unit_tile(side,origin,hp,max_hp):
  im=Image.new('RGBA',(52,61),(18,17,15,255));dr=ImageDraw.Draw(im)
  im.alpha_composite(portraits[origin] if hp>0 else dead[origin],(2,2))
  dr.rectangle((0,0,51,51),outline=(192,162,104,255) if hp>0 else (74,71,66,255),width=2)
  dr.rectangle((1,53,50,59),fill=(42,39,32,255))
  if hp>0:
   width=max(1,round(48*min(1,hp/max(1,max_hp))))
   dr.rectangle((2,54,1+width,58),fill=BLUE if side==0 else RED)
  return im.resize((tile_size,round(61*tile_size/52)),Image.Resampling.LANCZOS)
 @lru_cache(maxsize=24)
 def portrait_queues(side2,side3):
  im=base.crop((0,0,W,320));dr=ImageDraw.Draw(im)
  dr.line((540,32,540,301),fill=(120,97,57,255),width=1)
  for side,units in enumerate((side2,side3)):
   x=28+530*side
   count=sum(hp>0 for _,hp,_ in units);hp=round(sum(hp for _,hp,_ in units))
   put(im,str(count),(x+2,33),54,INK)
   put(im,str(hp)+' HP',(x+113,51),29,INK)
   if count>columns*3:raise ValueError('Portrait queue exceeds computed capacity')
   for i,(entity_id,hp,max_hp) in enumerate(units[:columns*3]):
    row,col=divmod(i,columns)
    im.alpha_composite(unit_tile(side,origins[entity_id],hp,max_hp),(x+col*step,101+row*66))
  return im
 def dynamic(t):
  row=sample_at(rows,times,t+start)
  sides=[tuple((u['id'],u['hp'],u['maxHp']) for u in ordered_units(row['sides'][owner])) for owner in ('2','3')]
  return portrait_queues(*sides)
 cap=cv2.VideoCapture(str(run/'battle.mp4'));fps=cap.get(5);source_frames=int(cap.get(7));frames=source_frames-round(start*fps)
 # End on elimination, including complete conversion; retain one frame showing the result.
 end=terminal_row(rows)
 if end['videoSeconds']>=start:
  frames=min(frames,max(1,math.ceil((end['videoSeconds']-start)*fps)+1))
 battle_camera=None
 if camera in ('action','telemetry'):
  from overlay.battle_camera import analyze
  battle_camera=analyze(run/'battle.mp4',out/'camera.json',start,frames/fps,telemetry_run=run if camera=='telemetry' else None)
 enhancer=None
 if enhance_model:
  from overlay.video_enhance import LocalUpscaler
  enhancer=LocalUpscaler(enhance_model)
  (out/'enhancement.json').write_text(json.dumps(enhancer.metadata,indent=2))
 def gameplay(frame,seconds):
  if battle_camera:result=battle_camera.crop(frame,seconds)
  else:result=cv2.resize(frame[:,crop_x:crop_x+1440],(1080,1080),interpolation=cv2.INTER_LANCZOS4)
  if enhancer:result=enhancer(result)
  return Image.fromarray(cv2.cvtColor(result,cv2.COLOR_BGR2RGB))
 for sec in sorted({min(t,(frames-1)/fps) for t in [0,4,10,15,(frames-1)/fps]}):
  cap.set(cv2.CAP_PROP_POS_MSEC,(sec+start)*1000);ok,frame=cap.read();assert ok
  im=base.copy()
  if battle_camera or enhancer:crop=gameplay(frame,sec+start)
  else:crop=Image.fromarray(cv2.cvtColor(frame[:,crop_x:crop_x+1440],cv2.COLOR_BGR2RGB)).resize((1080,1080),Image.Resampling.LANCZOS)
  im.paste(crop,(0,GAME_Y));im.alpha_composite(dynamic(sec),(0,0));im.convert('RGB').save(out/f'preview-{sec:05.2f}.jpg',quality=90)
 cap.release()
 ff=find_ffmpeg();video=out/'short.mp4'
 if battle_camera or enhancer:
  # Render the moving gameplay crop below the original fixed overlays. A single
  # final encode avoids baking another lossy generation into the zoomed picture.
  cmd=[ff,'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate',str(fps),'-i','pipe:0','-ss',str(start),'-i',str(run/'battle.mp4'),'-map','0:v:0','-map','1:a?','-t',str(frames/fps),'-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-b:a','192k','-movflags','+faststart',str(video)]
  cap=cv2.VideoCapture(str(run/'battle.mp4'));cap.set(cv2.CAP_PROP_POS_FRAMES,round(start*fps))
  with (out/'render.log').open('w') as log:
   proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
   try:
    for f in range(frames):
     ok,frame=cap.read()
     if not ok:raise RuntimeError('Source footage ended before the planned Short')
     im=base.copy();im.paste(gameplay(frame,start+f/fps),(0,GAME_Y));im.alpha_composite(dynamic(f/fps),(0,0))
     proc.stdin.write(im.convert('RGB').tobytes())
     if f%120==0:print(f'Rendered {f+1}/{frames} frames',flush=True)
    proc.stdin.close()
    if proc.wait():raise RuntimeError('See render.log')
   except BaseException:proc.kill();proc.wait();raise
   finally:cap.release()
 else:
  render_fixed(ff,video,run,out,start,frames,fps,crop_x,dynamic)
 (out/'manifest.json').write_text(json.dumps({'source':str(run.resolve()),'video':str(video.resolve()),'resolution':[W,H],'fps':fps,'durationSeconds':frames/fps,'trimStartSeconds':start,'crop':None if battle_camera else [crop_x,0,1440,1440],'camera':camera,'cameraPath':'camera.json' if battle_camera else None,'gameViewport':[0,GAME_Y,1080,1080],'hpTiming':'Existing verified timeline sampled at output time + trimStartSeconds','portraitColumns':columns,'audio':'Original recorded game audio, AAC 192k, no added narration','layout':'Two adaptive-column by 3-row portrait queues above gameplay, count and total HP only, per-unit HP bars, survivors packed before dimmed casualties. Two approved stat panels below. Screen units excluded from main-army counters.','status':'draft_pending_review'},indent=2))
 print(video)

def render_fixed(ff,video,run,out,start,frames,fps,crop_x,dynamic):
 graph=f'[0:v]crop=1440:1440:{crop_x}:0,scale=1080:1080,setsar=1[game];[2:v][game]overlay=0:{GAME_Y}:shortest=1[base];[base][1:v]overlay=0:0:shortest=1,format=yuv420p[v]'
 cmd=[ff,'-y','-v','error','-threads','2','-ss',str(start),'-i',str(run/'battle.mp4'),'-f','rawvideo','-pixel_format','rgba','-video_size','1080x320','-framerate',str(fps),'-i','pipe:0','-loop','1','-framerate',str(fps),'-i',str(out/'layout.png'),'-filter_complex_threads','1','-filter_complex',graph,'-map','[v]','-map','0:a?','-t',str(frames/fps),'-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-c:a','aac','-ar','48000','-b:a','192k','-movflags','+faststart',str(video)]
 with (out/'render.log').open('w') as log:
  proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
  try:
   for f in range(frames):proc.stdin.write(dynamic(f/fps).tobytes())
   proc.stdin.close()
   if proc.wait():raise RuntimeError('See render.log')
  except BaseException:proc.kill();proc.wait();raise

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--start',type=float,default=.2);p.add_argument('--crop-x',type=int,default=640);p.add_argument('--camera',choices=('fixed','action','telemetry'),default='fixed');p.add_argument('--enhance-model',type=Path);a=p.parse_args();build(a.run,a.output,a.start,a.crop_x,a.camera,a.enhance_model)
