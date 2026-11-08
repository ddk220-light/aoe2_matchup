"""Read committed diagnostics without executing any battle or assigning an outcome."""
import argparse, gzip, hashlib, json, subprocess
from pathlib import Path
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = '819e95bb2ed89e3ff5619fcbcee8c5c75f868a92'
JOB = 'fv_0466e97c7d116241411573cc'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
def blob(p): return subprocess.check_output(['git','show',SOURCE+':'+p],cwd=ROOT)
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).parent);out=p.parse_args().output
 assert not (out/'REVIEW.json').exists(), 'Never overwrite a diagnosis'
 manifest=json.loads(blob(BASE+'/manifest.json'));policy=json.loads(blob(BASE+'/sampling-policy-v3.json'))
 job=next(x for x in map(json.loads,gzip.decompress(blob(BASE+'/jobs.jsonl.gz')).splitlines()) if x['id']==JOB)
 assert job['contextHash']==sha(json.dumps(job['context'],sort_keys=True,separators=(',',':')).encode())
 assert job['teamKeys']==['Cumans|imp_elite_skirm','Malay|hussar'] and job['counts']==[27,23]
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
  core=lambda r:{'byOwner':r['byOwner'],'units':[{k:u[k] for k in ['id','owner','hp']} for u in r['positions']]}
  i=len(rows)-1
  while i and core(rows[i-1])==core(rows[-1]):i-=1
  deltas={k:rows[-1]['eventCounts'].get(k,0)-rows[i]['eventCounts'].get(k,0) for k in rows[-1]['eventCounts'] if rows[-1]['eventCounts'].get(k,0)!=rows[i]['eventCounts'].get(k,0)}
  assert all(u['action']=='idle' and u['attackTargetId'] is None for row in rows[i:] for u in row['positions'])
  assert set(deltas)=={'move','pursuit-acquired','contact-reservation-acquired','contact-reservation-persisted','blocked','contact-reservation-released','contact-release-persisted','pursuit-route-planned','pursuit-route-invalidated','pursuit-retarget-requested','pursuit-route-advanced'}
  attempts.append({'uniquePositionActionTargetStatesInHpSuffix':len({json.dumps(row['positions'],sort_keys=True) for row in rows[i:]}),'lastSavedPositions':rows[-1]['positions'],'lastSavedHpCore':core(rows[-1]),'constantHpSuffixSnapshots':len(rows)-i,'eventDeltasInSuffix':deltas,**a,'sourceLine':n,'sourceLineSha256':sha(raw),'progressSha256':sha(timeline),'savedSnapshots':len(rows),'lastSavedTick':rows[-1]['tick'],'lastSavedSimulationSeconds':rows[-1]['simulationSeconds']})
 assert all(a['lastSavedHpCore']==attempts[-1]['lastSavedHpCore'] for a in attempts)
 assert [a['constantHpSuffixSnapshots'] for a in attempts]==[4,18,58,118]
 runs=blob(BASE+'/runs.jsonl');assert not any(x['matchupId']==JOB for x in map(json.loads,runs.splitlines()))
 assert not subprocess.check_output(['git','ls-tree',SOURCE,'--',BASE+'/pair-reviews/'+JOB+'.json'],cwd=ROOT)
 state=blob(BASE+'/state.json');assert JOB in json.loads(state)['blockedJobs']
 report={'version':1,'diagnosticOnly':True,'jobId':JOB,'sourceCommit':SOURCE,'campaignHash':manifest['campaignHash'],'samplingPolicyHash':policy['amendmentHash'],'job':job,'mechanicsUnitNames':names,'originalEvidence':evidence,'sourceHashes':{BASE+'/manifest.json':sha(blob(BASE+'/manifest.json')),BASE+'/sampling-policy-v3.json':sha(blob(BASE+'/sampling-policy-v3.json')),FROZEN:sha(frozen),BASE+'/attempts.jsonl':sha(journal),BASE+'/runs.jsonl':sha(runs),BASE+'/state.json':sha(state)},'attempts':attempts,'status':'blocked_needs_separate_recovery_review','assignedOutcome':None,'validNativeSeedReferences':[],'replayEvidence':{'required':False,'performed':False,'exact':None},'diagnosis':'Seed 0 exhausted all four normal watchdogs without completing. All four timelines have long suffixes with the same survivors and HP: one Elite Skirmisher at 11 HP and sixteen Light Cavalry at 777 combined HP. Those suffixes contain 4, 18, 58 and 118 snapshots. All sampled survivors are idle with null attack targets. Positions and pursuit targets continue varying, and eleven movement, pursuit, reservation and blocked counters grow while combat counters remain fixed. The longest suffix has 118 distinct sampled position/action/target states. This is continuing movement/replanning without HP progress, not a fixed-position stall. The exact contact/range/geometry/route cause and real-game outcome remain unknown.','queueAction':'Preserve every failed attempt, leave blocked, continue ordinary queue. Separate recovery review required before any further retry.','noFurtherRetryAuthorized':True,'simulationExecutionsForDiagnosis':0,'physicsChanged':False,'nativeResultsAdded':False}
 out.mkdir(parents=True,exist_ok=True)
 with (out/'REVIEW.json').open('x') as f:f.write(json.dumps(report,sort_keys=True,indent=2)+'\n')
 with (out/'README.md').open('x') as f:f.write(f"""# Exhausted Cuman Elite Skirmisher / Malay Light Cavalry

Job `{JOB}`, counts 27 / 23, exhausted all four normal seed-0 watchdogs. No seed completed. The frozen role key `Malay|hussar` retains the actual mechanics upgrade Light Cavalry. All four saved timelines have long suffixes with unchanged survivors and HP: one skirmisher at 11 HP and sixteen cavalry at 777 combined HP. The suffixes contain 4, 18, 58 and 118 snapshots respectively. Every sampled survivor is idle with a null attack target.

Positions and pursuit targets continue changing. Eleven movement/pursuit/reservation/blocked counters grow while combat counters stay fixed. The longest constant-HP suffix has 118 distinct sampled position/action/target states. This is continuing movement/replanning without HP progress; it is not a fixed-position diagnosis. The exact cause and real-game outcome remain unknown.

No native winner, draw, review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.

Source `{SOURCE}`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:

```sh
python {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>
```
""")
 print(json.dumps({'jobId':JOB,'attempts':len(attempts),'completedSeeds':0,'simulationExecutions':0,'assignedOutcome':None}))
if __name__=='__main__':main()
