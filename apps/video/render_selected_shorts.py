import json,subprocess,sys,concurrent.futures,traceback,time,hashlib
from pathlib import Path
from build_vertical_short import build
from overlay.ffutil import find_ffmpeg,find_ffprobe
ROOT=Path('aoe2x/js_simulation/calibration/lab/shorts/selected-20')
def render(x):
 out=Path(x['output']);out.mkdir(parents=True,exist_ok=True)
 try:
  run=Path(x['run']);digest=hashlib.sha256()
  for source in [Path(__file__).with_name('build_vertical_short.py'),Path(__file__).parent/'overlay/battle_end.py',run/'recording.json',run/'unit-hp-overlay/units.json',run/'static-stats-overlay/panels.png',run/'static-stats-overlay/stats.json']:
   digest.update(source.read_bytes())
  fingerprint=digest.hexdigest()
  cached=json.loads((out/'validation.json').read_text()) if (out/'validation.json').exists() else {}
  if cached.get('fingerprint')!=fingerprint or not (out/'short.mp4').exists():
   build(Path(x['run']),out)
   video=out/'short.mp4'
   probe=json.loads(subprocess.check_output([find_ffprobe(),'-v','error','-show_streams','-show_format','-of','json',str(video)],text=True))
   v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
   assert (v['width'],v['height'])==(1080,1920)
   result=subprocess.run([find_ffmpeg(),'-v','error','-threads','2','-i',str(video),'-f','null','-'],capture_output=True,text=True)
   assert result.returncode==0 and not result.stderr,result.stderr
   (out/'validation.json').write_text(json.dumps({'status':'passed','fingerprint':fingerprint,'fullDecode':True,'audio':a['codec_name'],'durationSeconds':float(probe['format']['duration']),'bytes':video.stat().st_size},indent=2))
  return dict(jobId=x['jobId'],status='complete',output=str(out/'short.mp4'))
 except Exception as e:
  (out/'error.txt').write_text(traceback.format_exc());return dict(jobId=x['jobId'],status='failed',error=str(e))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Render and validate a persisted matchup Shorts selection.')
 parser.add_argument('--selection',type=Path,default=ROOT/'selection.json')
 parser.add_argument('--workers',type=int,default=2)
 args=parser.parse_args()
 if not 1<=args.workers<=8:parser.error('workers must be between 1 and 8')
 items=json.loads(args.selection.read_text())['items'];results=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
  for r in pool.map(render,items):
   results.append(r);print(json.dumps(r),flush=True)
   (args.selection.parent/'status.json').write_text(json.dumps({'state':'RUNNING','items':results},indent=2))
 (args.selection.parent/'status.json').write_text(json.dumps({'state':'COMPLETE' if all(r['status']=='complete' for r in results) else 'COMPLETE_WITH_ERRORS','completed':sum(r['status']=='complete' for r in results),'items':results},indent=2))
