"""Build a new local full video; preserve the original compilation and uploads."""
import json,math,subprocess
from pathlib import Path
from overlay.ffutil import find_ffmpeg,find_ffprobe
from overlay.battle_end import terminal_row
from aoe2x.lab.io import write_json
ROOT=Path(__file__).resolve().parents[2];LAB=ROOT/'aoe2x/js_simulation/calibration/lab'
OUT=LAB/'compilations/korean-war-wagon-unique-units/final-cost-v2'
def read(p):return json.loads(p.read_text())
def probe(p):return json.loads(subprocess.check_output([find_ffprobe(),'-v','error','-show_format','-show_streams','-show_chapters','-of','json',str(p)]))
def stamp(s):n=int(s);return f'{n//3600}:{n//60%60:02}:{n%60:02}' if n>=3600 else f'{n//60:02}:{n%60:02}'
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 repair=next(x for x in read(ROOT/'data/local/production-audit/repair-plan.json')['compilations'] if x['episode']=='korean-war-wagon-unique-units')
 old=read(LAB/'compilations/korean-war-wagon-unique-units/final/manifest.json');oldrows={r['jobId']:r for r in old['results']}
 overlays=read(LAB/'campaigns/korean-war-wagon-cost-v2-overlays/status.json');assert overlays['state']=='COMPLETE' and overlays['failed']==0
 with (OUT/'render.log').open('a') as log:
  def call(args):subprocess.run([find_ffmpeg(),'-y','-v','warning',*map(str,args)],stdout=log,stderr=log,check=True)
  encode=['-c:v','h264_nvenc','-preset','p4','-cq','18','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-b:a','192k']
  intro=LAB/'compilations/korean-war-wagon-unique-units/intro-v1/korean-war-wagon-intro.mp4';normalized=OUT/'intro-1440p60.mp4'
  if not normalized.exists():call(['-i',intro,'-vf','scale=2560:1440:flags=lanczos,fps=60,format=yuv420p',*encode,'-video_track_timescale','15360',normalized])
  cursor=float(probe(normalized)['format']['duration']);clips=[{'title':'Introduction','source':str(normalized),'startSeconds':0,'durationSeconds':cursor}];results=[]
  for chapter in repair['chapters']:
   original=chapter['jobId'];jid=chapter.get('replacementJobId') or original;run=LAB/'runs'/jid/'live/run_001'
   if chapter['costAction']=='RETAKE':
    source=run/'unit-hp-overlay/battle-with-unit-hp.mp4';assert source.exists()
    end=terminal_row(read(run/'unit-hp-overlay/units.json')['rows']);duration=(math.ceil(end['videoSeconds']*60)+1)/60
    if float(probe(source)['format']['duration'])>duration+.5:
     trimmed=OUT/(jid+'-end.mp4');call(['-i',source,'-t',duration,*encode,trimmed]);source=trimmed
   else:
    source=OUT/(original+'-reused.mp4')
    if not source.exists():call(['-ss',chapter['extractStartSeconds'],'-i',repair['fullVideo'],'-t',chapter['extractDurationSeconds'],*encode,source])
   duration=float(probe(source)['format']['duration']);capture=read(run/'manifest.json')['capture'];owner=capture.get('winnerOwner');oldrow=oldrows[original]
   row={'jobId':jid,'originalJobId':original,'title':oldrow['title'],'unit':oldrow['unit'],'source':str(source),'startSeconds':cursor,'durationSeconds':duration,'timestamp':stamp(cursor),'result':'WIN' if owner==2 else 'LOSS' if owner==3 else 'DRAW','winnerHp':capture.get('winnerHp',0),'winnerSurvivors':capture.get('survivors',0),'reuse':chapter['costAction']!='RETAKE'}
   results.append(row);clips.append(row);cursor+=duration
  assert len(results)==73
  (OUT/'concat.txt').write_text(''.join("file '"+Path(c['source']).as_posix()+"'\n" for c in clips))
  metadata=';FFMETADATA1\ntitle=Elite War Wagon vs 73 Unique Units - Corrected Costs\n'
  for c in clips:metadata+=f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c['startSeconds']*1000)}\nEND={round((c['startSeconds']+c['durationSeconds'])*1000)}\ntitle={c['title']}\n"
  (OUT/'chapters.ffmeta').write_text(metadata)
  video=OUT/'korean-war-wagon-complete-corrected-costs.mp4'
  call(['-f','concat','-safe','0','-i',OUT/'concat.txt','-i',OUT/'chapters.ffmeta','-map','0:v:0','-map','0:a:0','-map_metadata','1','-map_chapters','1','-c:v','copy','-c:a','aac','-b:a','192k','-af','aresample=async=1','-movflags','+faststart',video])
  info=probe(video);assert len(info['chapters'])==74 and abs(float(info['format']['duration'])-cursor)<2
  call(['-threads','2','-i',video,'-f','null','-'])
  write_json(OUT/'manifest.json',{'output':str(video),'matchups':73,'chapters':74,'media':info,'fullDecode':'passed','reviewStatus':'NEEDS_VISUAL_QA','results':results,'costBasis':'fully_upgraded_imperial_v1'})
  desc='Elite War Wagon vs 73 Unique Units | Age of Empires II DE\n\nEqual resources using civilization-specific Imperial costs per individual unit; maximum 27 units per main army. Ranged units get a small front line of hussars against melee units. Whole-unit rounding applies.\n\nTry your own matchup: https://aoe2matchup.com/?civ1=Koreans&unit1=elite_war_wagon_koreans&age1=Imperial\n\nWIN/LOSS is from the Elite War Wagon perspective; HP is the winning army remaining HP.\n\n00:00 Introduction\n'
  desc+='\n'.join(f"{r['timestamp']} {r['unit']} | {r['result']} | {round(r['winnerHp'])} HP" for r in results)
  desc+='\n\n#AoE2 #AoE2DE #Koreans #WarWagon #RTS #BattleSimulation #UnitCounters\n';assert len(desc)<=5000
  (OUT/'description-draft.txt').write_text(desc,encoding='utf-8')
if __name__=='__main__':main()
