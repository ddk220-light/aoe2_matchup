"""Read committed diagnostics without executing any battle or assigning an outcome."""
import argparse, gzip, hashlib, json, subprocess
from pathlib import Path
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = 'ff4d2a7be0ad780cbf04c626a7d19147da9761d9'
JOB = 'fv_5bc5ce13eed6d3668dda1e1c'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
def blob(p): return subprocess.check_output(['git','show',SOURCE+':'+p],cwd=ROOT)
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).parent);out=p.parse_args().output
 assert not (out/'REVIEW.json').exists(), 'Never overwrite a diagnosis'
 manifest=json.loads(blob(BASE+'/manifest.json'));policy=json.loads(blob(BASE+'/sampling-policy-v3.json'))
 job=next(x for x in map(json.loads,gzip.decompress(blob(BASE+'/jobs.jsonl.gz')).splitlines()) if x['id']==JOB)
 assert job['contextHash']==sha(json.dumps(job['context'],sort_keys=True,separators=(',',':')).encode())
 assert job['teamKeys']==['Italians|imp_elite_skirm','Byzantines|hussar'] and job['counts']==[27,23]
 frozen=blob(FROZEN);assert sha(frozen)==next(f['sha256'] for f in manifest['inputFiles'] if f['path']==FROZEN)
 names=[json.loads(frozen)['profiles'][k]['mechanics']['unit_name'] for k in job['teamKeys']]
 evidence=[x for x in map(json.loads,gzip.decompress(blob(BASE+'/original-evidence.jsonl.gz')).splitlines()) if x['evidenceId'] in job['evidenceIds']]
 journal=blob(BASE+'/attempts.jsonl');selected=[(n,raw,json.loads(raw)) for n,raw in enumerate(journal.splitlines(keepends=True),1) if json.loads(raw)['matchupId']==JOB]
 assert [a['attempt'] for _,_,a in selected]==[1,2,3,4]
 assert [a['limitSeconds'] for _,_,a in selected]==[180,600,1800,3600]
 assert [a['exhausted'] for _,_,a in selected]==[False,False,False,True]
 attempts=[]
 for n,raw,a in selected:
  assert a['seed']==0 and a['purpose']=='fresh_measurement' and a['watchdog'] and a['error'] is None
  timeline=blob(a['progressPath']);rows=list(map(json.loads,timeline.splitlines()));assert all(x['diagnosticOnly'] for x in rows)
  core=lambda r:{'byOwner':r['byOwner'],'positions':r['positions']}
  i=len(rows)-1
  while i and core(rows[i-1])==core(rows[-1]):i-=1
  deltas={k:rows[-1]['eventCounts'].get(k,0)-rows[i]['eventCounts'].get(k,0) for k in rows[-1]['eventCounts'] if rows[-1]['eventCounts'].get(k,0)!=rows[i]['eventCounts'].get(k,0)}
  attempts.append({'lastSavedCore':core(rows[-1]),'constantCoreSuffixSnapshots':len(rows)-i,'eventDeltasInSuffix':deltas,**a,'sourceLine':n,'sourceLineSha256':sha(raw),'progressSha256':sha(timeline),'savedSnapshots':len(rows),'lastSavedTick':rows[-1]['tick'],'lastSavedSimulationSeconds':rows[-1]['simulationSeconds']})
 assert attempts[-1]['lastSavedCore']==attempts[-2]['lastSavedCore']
 assert attempts[-1]['constantCoreSuffixSnapshots']==75 and attempts[-2]['constantCoreSuffixSnapshots']==11
 runs=blob(BASE+'/runs.jsonl');assert not any(x['matchupId']==JOB for x in map(json.loads,runs.splitlines()))
 assert not subprocess.check_output(['git','ls-tree',SOURCE,'--',BASE+'/pair-reviews/'+JOB+'.json'],cwd=ROOT)
 state=blob(BASE+'/state.json');assert JOB in json.loads(state)['blockedJobs']
 report={'version':1,'diagnosticOnly':True,'jobId':JOB,'sourceCommit':SOURCE,'campaignHash':manifest['campaignHash'],'samplingPolicyHash':policy['amendmentHash'],'job':job,'mechanicsUnitNames':names,'originalEvidence':evidence,'sourceHashes':{BASE+'/manifest.json':sha(blob(BASE+'/manifest.json')),BASE+'/sampling-policy-v3.json':sha(blob(BASE+'/sampling-policy-v3.json')),FROZEN:sha(frozen),BASE+'/attempts.jsonl':sha(journal),BASE+'/runs.jsonl':sha(runs),BASE+'/state.json':sha(state)},'attempts':attempts,'status':'blocked_needs_separate_recovery_review','assignedOutcome':None,'validNativeSeedReferences':[],'replayEvidence':{'required':False,'performed':False,'exact':None},'diagnosis':'Seed 0 exhausted all four normal watchdogs without completing. The two short attempts end earlier, with 21 and 19 Hussars remaining. The two long attempts reach identical fixed positions, HP, actions and targets: one Elite Skirmisher at 15 HP and three Hussars at 215 combined HP, all idle with null attack targets. Six reservation/pursuit/blocked counters grow while combat counters remain unchanged within the late suffixes (11 and 75 snapshots respectively). This establishes a late stall within the tested limits, not its exact contact/range/geometry/route cause or a winner or draw.','queueAction':'Preserve every failed attempt, leave blocked, continue ordinary queue. Separate recovery review required before any further retry.','noFurtherRetryAuthorized':True,'simulationExecutionsForDiagnosis':0,'physicsChanged':False,'nativeResultsAdded':False}
 out.mkdir(parents=True,exist_ok=True)
 with (out/'REVIEW.json').open('x') as f:f.write(json.dumps(report,sort_keys=True,indent=2)+'\n')
 with (out/'README.md').open('x') as f:f.write(f"""# Exhausted Italian Elite Skirmisher / Byzantine Hussar

Job `{JOB}`, counts 27 / 23, exhausted all four normal seed-0 watchdogs. No seed completed. The two longer attempts reach the same fixed late state: one Elite Skirmisher at 15 HP and three Hussars at 215 combined HP, all idle with null attack targets. Their constant-core suffixes contain 11 and 75 snapshots while six reservation/pursuit/blocked event counters increase. The shorter attempts end earlier, with 21 and 19 Hussars.

The precise contact/range/geometry/route cause and real-game result remain unknown. No winner, draw or correction is assigned. No simulation or replay was executed for this diagnosis. Leave this job blocked pending separate recovery review; no further retry or physics change is authorized. The ordinary queue continues.

Source `{SOURCE}`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce from the repository root into a new directory:

```sh
python {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>
```
""")
 print(json.dumps({'jobId':JOB,'attempts':len(attempts),'completedSeeds':0,'simulationExecutions':0,'assignedOutcome':None}))
if __name__=='__main__':main()
