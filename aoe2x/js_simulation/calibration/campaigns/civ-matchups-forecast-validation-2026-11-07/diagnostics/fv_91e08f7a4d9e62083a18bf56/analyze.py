"""Read committed diagnostics without executing any battle or assigning an outcome."""
import argparse, gzip, hashlib, json, subprocess
from pathlib import Path
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = 'b8de7e6406df79cd0c99dd2f182ff7bb1fce7ffd'
JOB = 'fv_91e08f7a4d9e62083a18bf56'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
def blob(p): return subprocess.check_output(['git','show',SOURCE+':'+p],cwd=ROOT)
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).parent);out=p.parse_args().output
 assert not (out/'REVIEW.json').exists(), 'Never overwrite a diagnosis'
 manifest=json.loads(blob(BASE+'/manifest.json'));policy=json.loads(blob(BASE+'/sampling-policy-v3.json'))
 job=next(x for x in map(json.loads,gzip.decompress(blob(BASE+'/jobs.jsonl.gz')).splitlines()) if x['id']==JOB)
 assert job['contextHash']==sha(json.dumps(job['context'],sort_keys=True,separators=(',',':')).encode())
 assert job['teamKeys']==['Muisca|elite_guecha_warrior_muisca','Turks|paladin'] and job['counts']==[27,24]
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
 assert all(a['lastSavedCore']==attempts[-1]['lastSavedCore'] for a in attempts)
 assert [a['constantCoreSuffixSnapshots'] for a in attempts]==[1,15,56,115]
 runs=blob(BASE+'/runs.jsonl');assert not any(x['matchupId']==JOB for x in map(json.loads,runs.splitlines()))
 assert not subprocess.check_output(['git','ls-tree',SOURCE,'--',BASE+'/pair-reviews/'+JOB+'.json'],cwd=ROOT)
 state=blob(BASE+'/state.json');assert JOB in json.loads(state)['blockedJobs']
 report={'version':1,'diagnosticOnly':True,'jobId':JOB,'sourceCommit':SOURCE,'campaignHash':manifest['campaignHash'],'samplingPolicyHash':policy['amendmentHash'],'job':job,'mechanicsUnitNames':names,'originalEvidence':evidence,'sourceHashes':{BASE+'/manifest.json':sha(blob(BASE+'/manifest.json')),BASE+'/sampling-policy-v3.json':sha(blob(BASE+'/sampling-policy-v3.json')),FROZEN:sha(frozen),BASE+'/attempts.jsonl':sha(journal),BASE+'/runs.jsonl':sha(runs),BASE+'/state.json':sha(state)},'attempts':attempts,'status':'blocked_needs_separate_recovery_review','assignedOutcome':None,'validNativeSeedReferences':[],'replayEvidence':{'required':False,'performed':False,'exact':None},'diagnosis':'Seed 0 exhausted all four normal watchdogs without completing. All four attempts end in the same saved positions, HP, actions and targets: one Elite Guecha Warrior at 60 HP and three Cavaliers at 240 combined HP, all idle with null attack targets. The three longer attempts have constant-core suffixes of 15, 56 and 115 snapshots. Five reservation/pursuit/blocked event counters increase within those suffixes while combat counters remain unchanged. The first short attempt has only one snapshot in its final constant-core suffix. The precise contact/range/geometry/route cause and real-game winner or draw remain unknown.','queueAction':'Preserve every failed attempt, leave blocked, continue ordinary queue. Separate recovery review required before any further retry.','noFurtherRetryAuthorized':True,'simulationExecutionsForDiagnosis':0,'physicsChanged':False,'nativeResultsAdded':False}
 out.mkdir(parents=True,exist_ok=True)
 with (out/'REVIEW.json').open('x') as f:f.write(json.dumps(report,sort_keys=True,indent=2)+'\n')
 with (out/'README.md').open('x') as f:f.write(f"""# Exhausted Muisca Elite Guecha Warrior / Turkish Cavalier

Job `{JOB}`, counts 27 / 24, exhausted all four normal seed-0 watchdogs. None completed. Frozen role key `Turks|paladin` retains the actual mechanics upgrade Cavalier. All four attempts end in the same saved positions, HP, actions and targets: one Elite Guecha Warrior at 60 HP and three Cavaliers at 240 combined HP, all idle with null attack targets. The longer three timelines have constant-core suffixes of 15, 56 and 115 snapshots. Five reservation/pursuit/blocked counters increase while combat counters remain fixed in each suffix.

The exact cause and real-game outcome remain unknown. No native result, draw, pair review or correction is assigned. No simulation or replay was executed for this diagnosis. Leave this job blocked pending a separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.

Source `{SOURCE}`, physical context, original evidence and attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>
```
""")
 print(json.dumps({'jobId':JOB,'attempts':len(attempts),'completedSeeds':0,'simulationExecutions':0,'assignedOutcome':None}))
if __name__=='__main__':main()
