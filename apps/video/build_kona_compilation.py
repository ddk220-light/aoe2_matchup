"""Assemble all archived Elite Kona overlays with the reviewed-format intro."""
import json,math,subprocess
from pathlib import Path
from overlay.ffutil import find_ffmpeg,find_ffprobe
from overlay.battle_end import terminal_row
LAB=Path('aoe2x/js_simulation/calibration/lab').resolve()
OUT=LAB/'compilations/kona-unique-units/final';OUT.mkdir(parents=True,exist_ok=True)
def probe(p):return json.loads(subprocess.check_output([find_ffprobe(),'-v','error','-show_format','-show_streams','-show_chapters','-of','json',str(p)]))
def stamp(s):
 n=int(s);return f'{n//3600}:{n//60%60:02}:{n%60:02}' if n>=3600 else f'{n//60:02}:{n%60:02}'
def main():
 ff=find_ffmpeg();state=json.loads((LAB/'campaigns/kona-all-unique-overlays/status.json').read_text());clips=[];results=[]
 intro=LAB/'compilations/kona-unique-units/intro-v1/kona-intro.mp4';normalized=OUT/'intro-1440p60.mp4'
 with (OUT/'render.log').open('w') as log:
  def call(cmd):subprocess.run([ff,'-y','-v','warning',*cmd],stdout=log,stderr=log,check=True)
  if not normalized.exists():call(['-i',str(intro),'-vf','scale=2560:1440:flags=lanczos,fps=60,format=yuv420p','-c:v','h264_nvenc','-preset','p4','-cq','18','-video_track_timescale','15360','-c:a','aac','-ar','48000','-ac','2','-b:a','192k',str(normalized)])
  cursor=float(probe(normalized)['format']['duration']);clips.append({'title':'Introduction','source':str(normalized),'startSeconds':0,'durationSeconds':cursor})
  for j in state['jobs']:
   run=LAB/'runs'/j['jobId']/'live/run_001';source=run/'unit-hp-overlay/battle-with-unit-hp.mp4';assert source.exists(),source
   rows=json.loads((run/'unit-hp-overlay/units.json').read_text())['rows']
   end=terminal_row(rows)
   if float(probe(source)['format']['duration']) > end['videoSeconds'] + .5:
    end=terminal_row(rows);duration=(math.ceil(end['videoSeconds']*60)+1)/60
    trimmed=OUT/(j['jobId']+'-battle-end.mp4')
    call(['-i',str(source),'-t',str(duration),'-map','0:v:0','-map','0:a:0','-c:v','h264_nvenc','-preset','p4','-cq','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(trimmed)]);source=trimmed
   duration=float(probe(source)['format']['duration']);last=terminal_row(rows);alive=[o for o in ('2','3') if any(u['hp']>0 for u in last['sides'][o])];winner=alive[0] if len(alive)==1 else None
   hp=sum(u['hp'] for u in last['sides'][winner]) if winner else 0;count=sum(u['hp']>0 for u in last['sides'][winner]) if winner else 0
   row={'jobId':j['jobId'],'title':j['civ']+' - '+j['unit'],'unit':j['unit'],'source':str(source),'startSeconds':cursor,'durationSeconds':duration,'timestamp':stamp(cursor),'result':'WIN' if winner=='2' else 'LOSS' if winner=='3' else 'DRAW','winnerHp':hp,'winnerSurvivors':count}
   results.append(row);clips.append(row);cursor+=duration
  assert len(results)==73
  (OUT/'concat.txt').write_text(''.join("file '"+Path(c['source']).as_posix()+"'\n" for c in clips),encoding='utf-8')
  meta=';FFMETADATA1\ntitle=Elite Kona vs 73 Unique Units\n'
  for c in clips:meta+=f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c['startSeconds']*1000)}\nEND={round((c['startSeconds']+c['durationSeconds'])*1000)}\ntitle={c['title']}\n"
  (OUT/'chapters.ffmeta').write_text(meta,encoding='utf-8')
  video=OUT/'kona-complete-with-intro.mp4'
  call(['-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-i',str(OUT/'chapters.ffmeta'),'-map','0:v:0','-map','0:a:0','-map_metadata','1','-map_chapters','1','-c:v','copy','-c:a','aac','-ar','48000','-b:a','192k','-af','aresample=async=1','-movflags','+faststart',str(video)])
  info=probe(video);assert abs(float(info['format']['duration'])-cursor)<2;assert len(info['chapters'])==74
  call(['-threads','2','-i',str(video),'-f','null','-'])
  (OUT/'manifest.json').write_text(json.dumps({'output':str(video),'matchups':73,'chapters':74,'expectedSeconds':cursor,'media':info,'fullDecode':'passed','reviewStatus':'Locally validated; authorized for private YouTube upload','results':results},indent=2))
  desc="Elite Kona vs 73 Unique Units | Age of Empires II DE\n\nRecorded in-game battles with live unit HP overlays. Equal resources, maximum 27 units per main army. Ranged units get a small front line of hussars when fighting melee units. Whole-unit rounding applies.\n\nTry your own matchup: https://aoe2matchup.com/?civ1=Mapuche&unit1=elite_kona_mapuche&age1=Imperial\n\nWIN/LOSS is from Elite Kona's perspective; HP is the winning army's remaining HP.\n\n00:00 Introduction\n"
  desc+='\n'.join(f"{r['timestamp']} {r['unit']} | {r['result']} | {round(r['winnerHp'])} HP" for r in results)
  desc+='\n\n#AoE2 #AoE2DE #Kona #Mapuche #RTS #BattleSimulation #UnitCounters #StrategyGaming\n'
  assert len(desc)<=5000; (OUT/'youtube-description.txt').write_text(desc,encoding='utf-8');print(json.dumps({'video':str(video),'seconds':cursor,'descriptionCharacters':len(desc)}),flush=True)
if __name__=='__main__':main()
