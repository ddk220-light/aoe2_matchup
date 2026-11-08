"""Read committed diagnostics without executing any battle or assigning an outcome."""
import argparse, gzip, hashlib, json, subprocess
from pathlib import Path
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = '80c66d94fdfedccd255ff21ae3a1428f0f67add9'
JOB = 'fv_d94fee4147c5053486b13687'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
def blob(p): return subprocess.check_output(['git','show',SOURCE+':'+p],cwd=ROOT)
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).parent);out=p.parse_args().output
 assert not (out/'REVIEW.json').exists(), 'Never overwrite a diagnosis'
 manifest=json.loads(blob(BASE+'/manifest.json'));policy=json.loads(blob(BASE+'/sampling-policy-v3.json'))
 job=next(x for x in map(json.loads,gzip.decompress(blob(BASE+'/jobs.jsonl.gz')).splitlines()) if x['id']==JOB)
 assert job['contextHash']==sha(json.dumps(job['context'],sort_keys=True,separators=(',',':')).encode())
 assert job['teamKeys']==['Chinese|heavy_scorpion','Poles|heavy_mounted_crossbowman'] and job['counts']==[23,27]
 frozen=blob(FROZEN);assert sha(frozen)==next(f['sha256'] for f in manifest['inputFiles'] if f['path']==FROZEN)
 names=[json.loads(frozen)['profiles'][k]['mechanics']['unit_name'] for k in job['teamKeys']]
 evidence=[x for x in map(json.loads,gzip.decompress(blob(BASE+'/original-evidence.jsonl.gz')).splitlines()) if x['evidenceId'] in job['evidenceIds']]
 journal=blob(BASE+'/attempts.jsonl');selected=[(n,raw,json.loads(raw)) for n,raw in enumerate(journal.splitlines(keepends=True),1) if json.loads(raw)['matchupId']==JOB]
 assert [a['attempt'] for _,_,a in selected]==[1,2,3,4]
 assert [a['limitSeconds'] for _,_,a in selected]==[180,600,1800,3600]
 assert [a['exhausted'] for _,_,a in selected]==[False,False,False,True]
 assert len({a['error']['message'] for _,_,a in selected})==1
 attempts=[]
 for n,raw,a in selected:
  assert a['seed']==0 and a['purpose']=='fresh_measurement' and not a['watchdog'] and a['error']['name']=='RangeError'
  assert 'resolveMovementProposals' in a['error']['stack'] and 'stepWorld' in a['error']['stack']
  timeline=blob(a['progressPath']);rows=list(map(json.loads,timeline.splitlines()));assert all(x['diagnosticOnly'] for x in rows)
  attempts.append({**a,'sourceLine':n,'sourceLineSha256':sha(raw),'progressSha256':sha(timeline),'savedSnapshots':len(rows),'lastSavedTick':rows[-1]['tick'],'lastSavedSimulationSeconds':rows[-1]['simulationSeconds']})
 runs=blob(BASE+'/runs.jsonl');assert not any(x['matchupId']==JOB for x in map(json.loads,runs.splitlines()))
 assert not subprocess.check_output(['git','ls-tree',SOURCE,'--',BASE+'/pair-reviews/'+JOB+'.json'],cwd=ROOT)
 state=blob(BASE+'/state.json');assert JOB in json.loads(state)['blockedJobs']
 report={'version':1,'diagnosticOnly':True,'jobId':JOB,'sourceCommit':SOURCE,'campaignHash':manifest['campaignHash'],'samplingPolicyHash':policy['amendmentHash'],'job':job,'mechanicsUnitNames':names,'originalEvidence':evidence,'sourceHashes':{BASE+'/manifest.json':sha(blob(BASE+'/manifest.json')),BASE+'/sampling-policy-v3.json':sha(blob(BASE+'/sampling-policy-v3.json')),FROZEN:sha(frozen),BASE+'/attempts.jsonl':sha(journal),BASE+'/runs.jsonl':sha(runs),BASE+'/state.json':sha(state)},'attempts':attempts,'status':'blocked_needs_separate_recovery_review','assignedOutcome':None,'validNativeSeedReferences':[],'replayEvidence':{'required':False,'performed':False,'exact':None},'diagnosis':'All four unfinished seed-0 attempts fail with the same ranged-crowd reservation geometry RangeError during movement resolution. The reported separation 0.02350274216190229 is below extent 0.025 for references 9000/9011. This is a mid-fight movement validation failure, not evidence of an initial army spawn overlap. The coarse fsynced snapshots precede the failing step and do not establish its full instantaneous state or the root mechanism. No watchdog or native seed completed.','queueAction':'Preserve every failed attempt, leave blocked, continue ordinary queue. Separate recovery review required before any further retry.','noFurtherRetryAuthorized':True,'simulationExecutionsForDiagnosis':0,'physicsChanged':False,'nativeResultsAdded':False}
 out.mkdir(parents=True,exist_ok=True)
 with (out/'REVIEW.json').open('x') as f:f.write(json.dumps(report,sort_keys=True,indent=2)+'\n')
 with (out/'README.md').open('x') as f:f.write(f'''# Exhausted Chinese Heavy Scorpion / Polish Heavy Mounted Crossbowman\n\nJob `{JOB}`, counts 23 / 27, failed all four normal seed-0 attempts with the same ranged-crowd reservation geometry RangeError during movement resolution. None completed. The error reports separation 0.02350274216190229 versus extent 0.025 for references 9000/9011. Saved diagnostic snapshots precede the failing step; they do not establish the full failing state, exact cause or a winner.\n\nNo result, draw, review or correction is assigned. No new simulation, replay, physics change or further retry was performed or authorized. The ordinary queue continues with this case blocked pending separate recovery review. Source `{SOURCE}` and all journal-line/progress hashes are retained in `REVIEW.json`.\n\nReproduce from the repository root into a new directory:\n\n```sh\npython {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>\n```\n''')
 print(json.dumps({'jobId':JOB,'attempts':len(attempts),'completedSeeds':0,'simulationExecutions':0,'assignedOutcome':None}))
if __name__=='__main__':main()
