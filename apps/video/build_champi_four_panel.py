"""Four standard-map Champi captures, side by side, for review."""
import json, math, sqlite3, subprocess, shutil
from pathlib import Path
from functools import lru_cache
import cv2
from PIL import Image, ImageDraw, ImageOps
from overlay.static_stats import GAME, REPO, GameFont, resolve_stats, portrait_path, upgraded
from overlay.comp4 import champi_card, emblem
from overlay.unit_timeline import decode, sample_at, ordered_units
from overlay.battle_end import terminal_row
from overlay.auto_alignment import align
from overlay.ffutil import find_ffmpeg

CIVS=['Incas','Mapuche','Muisca','Tupi']
OUT=REPO/'data/local/champi-four-panel-review'

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 font=GameFont(GAME)
 @lru_cache(maxsize=4096)
 def label(text,size,color):
  im=Image.new('RGBA',(math.ceil(font.width(text,size))+8,size+18));font.draw(im,(3,0),text,size,color);return im
 def put(im,text,x,y,size=30,color=(244,229,197,255),center=False):
  tile=label(text,size,color);im.alpha_composite(tile,(round(x-tile.width/2 if center else x),y))
 db=sqlite3.connect(f'file:{REPO / "data/golden/aoe2_reference.db"}?mode=ro',uri=True);db.row_factory=sqlite3.Row
 enemy=resolve_stats(db,{'label':'Elite Composite Bowman','civ':'Armenians','slug':'elite_composite_bowman_armenians'})
 base=Image.new('RGBA',(2560,1440),(23,22,19,255));dr=ImageDraw.Draw(base)
 put(base,'Elite Champi Warrior vs Elite Composite Bowman',1280,18,44,center=True)
 put(base,'Armenians  |  HP 50  |  Attack '+upgraded(enemy,'attack')+'  |  Armour '+upgraded(enemy,'melee_armor')+' / '+upgraded(enemy,'pierce_armor'),1280,76,27,center=True)
 jobs=[]
 for i,civ in enumerate(CIVS):
  run=REPO/f'aoe2x/js_simulation/calibration/lab/runs/champi_standard_{civ.lower()}_01_elite_composite_bowman_armenians/live/run_001'
  if not (run/'battle.mp4').exists():
   from materialize_compact_recording import materialize
   original=run
   job=f'champi_standard_{civ.lower()}_01_elite_composite_bowman_armenians'
   workspace=OUT/'render-workspace'
   run=workspace/job/'live/run_001'
   if not (run/'battle.mp4').exists():
    run=materialize(Path(f'D:/AoE2 Renders/champi-standard-{civ.lower()}/run.json'),job,workspace)
   saved_alignment=original/'unit-hp-overlay/alignment.json'
   if saved_alignment.exists():
    (run/'unit-hp-overlay').mkdir(exist_ok=True)
    shutil.copyfile(saved_alignment,run/'unit-hp-overlay/alignment.json')
  print('Aligning',civ,flush=True);align(run)
  timeline=decode(run);rows=timeline['rows'];end=terminal_row(rows)
  endtime=max(0,end['videoSeconds'])
  initial={o:sum(u['hp'] for u in rows[0]['sides'][o]) for o in ('2','3')}
  hp={o:sum(u['hp'] for u in end['sides'][o]) for o in ('2','3')}
  winner='2' if hp['2']>0 else '3' if hp['3']>0 else None
  percent=100*hp[winner]/initial[winner] if winner else 0
  unit=resolve_stats(db,{'label':'Elite Champi Warrior','civ':civ,'slug':'elite_champi_warrior_'+civ.lower()})
  card=champi_card(unit,civ,(70,126,232,255),font);base.alpha_composite(card,(i*640+25,1095))
  badge=emblem(civ,50);base.alpha_composite(badge,(i*640+75,117));put(base,civ,i*640+335,119,36,center=True)
  dr.line((i*640,110,i*640,1430),fill=(132,108,67),width=3)
  cap=cv2.VideoCapture(str(run/'battle.mp4'))
  portraits=[Image.open(portrait_path(name)).convert('RGBA').resize((25,25)) for name in [unit['unit_name'],enemy['unit_name']]]
  jobs.append(dict(civ=civ,run=run,rows=rows,times=[r['videoSeconds'] for r in rows],end=endtime,winner=winner,percent=percent,gameEnd=end['gameMs']/1000,cap=cap,portraits=portraits,last=None,index=-1,fps=cap.get(5)))
 db.close()
 duration=max(j['end'] for j in jobs)+3
 ff=find_ffmpeg();video=OUT/'Champi_Four_Civilizations_vs_Armenian_Bowmen.mp4'
 log=(OUT/'render.log').open('w')
 cmd=[ff,'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','2560x1440','-framerate','30','-i','pipe:0','-i',str(jobs[0]['run']/'battle.mp4'),'-map','0:v','-map','1:a?','-af','apad','-t',str(duration),'-c:v','libx264','-threads','4','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(video)]
 proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
 for frame in range(math.ceil(duration*30)):
  t=frame/30;im=base.copy();draw=ImageDraw.Draw(im)
  for i,j in enumerate(jobs):
   x=i*640;sec=min(t,j['end']);cap=j['cap'];target=round(sec*j['fps'])
   while j['index']<target:
    ok,bgr=cap.read()
    if not ok:break
    j['last']=bgr;j['index']+=1
   if j['last'] is None:raise RuntimeError('Cannot decode source frame')
   crop=Image.fromarray(cv2.cvtColor(j['last'][:,1280:2560],cv2.COLOR_BGR2RGB)).resize((640,720),Image.Resampling.BILINEAR)
   im.paste(crop,(x,270))
   row=sample_at(j['rows'],j['times'],sec)
   for side,owner in enumerate(('2','3')):
    units=ordered_units(row['sides'][owner]);alive=sum(u['hp']>0 for u in units)
    put(im,str(alive),x+18+side*320,170,30)
    for n,u in enumerate(units[:27]):
     ux=x+60+side*320+(n%9)*28;uy=168+(n//9)*32
     tile=j['portraits'][side] if u['hp']>0 else ImageOps.grayscale(j['portraits'][side]).convert('RGBA')
     im.alpha_composite(tile,(ux,uy));draw.rectangle((ux,uy+26,ux+24,uy+29),fill=(48,45,40))
     if u['hp']>0:draw.rectangle((ux,uy+26,ux+max(1,round(24*min(1,u['hp']/max(1,u['maxHp'])))),uy+29),fill=(65,127,244) if side==0 else (238,75,65))
   if t>=j['end']:
    color=(101,220,130,255) if j['winner']=='2' else (248,106,96,255)
    put(im,'Victory' if j['winner']=='2' else 'Defeat',x+320,1001,40,color,True)
    put(im,f"Winner HP {j['percent']:.1f}%  |  {j['gameEnd']:.1f}s game time",x+320,1051,24,center=True)
   else:put(im,'Fighting',x+320,1016,31,center=True)
  if frame in (0,150,math.ceil(duration*30)-1):im.convert('RGB').save(OUT/f'preview-{frame}.jpg')
  proc.stdin.write(im.convert('RGB').tobytes())
  if frame%150==0:print('Rendered',frame,'/',math.ceil(duration*30),flush=True)
 proc.stdin.close();rc=proc.wait();log.close()
 if rc:raise RuntimeError('FFmpeg failed')
 for j in jobs:j['cap'].release()
 (OUT/'manifest.json').write_text(json.dumps(dict(video=str(video),duration=duration,layout='four portrait crops, raw audio from Incas',results=[{k:j[k] for k in ('civ','end','winner','percent','gameEnd')} for j in jobs]),indent=2))
 print(video,flush=True)

if __name__=='__main__':main()
