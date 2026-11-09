"""Read committed diagnostics without executing any battle or assigning an outcome."""
import argparse, gzip, hashlib, json, subprocess
from pathlib import Path
ROOT = next(p for p in Path(__file__).resolve().parents if (p/'aoe2x/js_simulation/calibration').is_dir())
BASE = 'aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07'
SOURCE = '191ff4a05b031a6f5989681bdf0afe0acdedfc2d'
JOB = 'fv_02521b013b039fe6f65c73ca'
FROZEN = 'aoe2x/js_simulation/calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'
def blob(p): return subprocess.check_output(['git','show',SOURCE+':'+p],cwd=ROOT)
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).parent);out=p.parse_args().output
 assert not (out/'REVIEW.json').exists(), 'Never overwrite a diagnosis'
 manifest=json.loads(blob(BASE+'/manifest.json'));policy=json.loads(blob(BASE+'/sampling-policy-v3.json'))
 job=next(x for x in map(json.loads,gzip.decompress(blob(BASE+'/jobs.jsonl.gz')).splitlines()) if x['id']==JOB)
 assert job['contextHash']==sha(json.dumps(job['context'],sort_keys=True,separators=(',',':')).encode())
 assert job['teamKeys']==['Burgundians|imp_elite_skirm','Mapuche|elite_kona_mapuche'] and job['counts']==[27,19]
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
  assert set(deltas)=={'move','pursuit-acquired','contact-reservation-acquired','contact-reservation-persisted','blocked','contact-reservation-released','contact-release-persisted','pursuit-route-planned','pursuit-route-invalidated','pursuit-retarget-requested','pursuit-route-advanced','contact-release-published'}
  attempts.append({'uniquePositionStatesInHpSuffix':len({json.dumps([{k:u[k] for k in ['id','owner','x','y']} for u in row['positions']],sort_keys=True) for row in rows[i:]}),'uniqueTargetStatesInHpSuffix':len({json.dumps([{k:u[k] for k in ['id','pursuitTargetId','engagedTargetId','attackTargetId']} for u in row['positions']],sort_keys=True) for row in rows[i:]}),'uniquePositionActionTargetStatesInHpSuffix':len({json.dumps(row['positions'],sort_keys=True) for row in rows[i:]}),'lastSavedPositions':rows[-1]['positions'],'lastSavedHpCore':core(rows[-1]),'constantHpSuffixSnapshots':len(rows)-i,'eventDeltasInSuffix':deltas,**a,'sourceLine':n,'sourceLineSha256':sha(raw),'progressSha256':sha(timeline),'savedSnapshots':len(rows),'lastSavedTick':rows[-1]['tick'],'lastSavedSimulationSeconds':rows[-1]['simulationSeconds']})
 assert all(a['lastSavedHpCore']==attempts[-1]['lastSavedHpCore'] for a in attempts)
 assert [a['constantHpSuffixSnapshots'] for a in attempts]==[5,19,59,119]
 assert [a['uniquePositionActionTargetStatesInHpSuffix'] for a in attempts]==[5,19,59,118]
 assert attempts[-1]['lastSavedHpCore']['byOwner']=={'2':{'units':1,'hp':22},'3':{'units':18,'hp':2460}}
 assert names==['Elite Skirmisher','Elite Kona']
 assert [a['uniquePositionStatesInHpSuffix'] for a in attempts]==[5,19,59,118]
 assert [a['uniqueTargetStatesInHpSuffix'] for a in attempts]==[2,2,2,2]
 runs=blob(BASE+'/runs.jsonl');assert not any(x['matchupId']==JOB for x in map(json.loads,runs.splitlines()))
 assert not subprocess.check_output(['git','ls-tree',SOURCE,'--',BASE+'/pair-reviews/'+JOB+'.json'],cwd=ROOT)
 state=blob(BASE+'/state.json');assert JOB in json.loads(state)['blockedJobs']
 report={'version':1,'diagnosticOnly':True,'jobId':JOB,'sourceCommit':SOURCE,'campaignHash':manifest['campaignHash'],'samplingPolicyHash':policy['amendmentHash'],'job':job,'mechanicsUnitNames':names,'originalEvidence':evidence,'sourceHashes':{BASE+'/manifest.json':sha(blob(BASE+'/manifest.json')),BASE+'/sampling-policy-v3.json':sha(blob(BASE+'/sampling-policy-v3.json')),FROZEN:sha(frozen),BASE+'/attempts.jsonl':sha(journal),BASE+'/runs.jsonl':sha(runs),BASE+'/state.json':sha(state)},'attempts':attempts,'status':'blocked_needs_separate_recovery_review','assignedOutcome':None,'validNativeSeedReferences':[],'replayEvidence':{'required':False,'performed':False,'exact':None},'diagnosis':"Seed 0 exhausted all four normal watchdogs without completing. All four timelines have constant-survivor/HP suffixes: one Elite Skirmisher at 22 HP and eighteen Elite Kona at 2,460 combined HP. Those suffixes contain 5, 19, 59 and 119 snapshots. All sampled survivors in those suffixes are idle with null attack targets, but positions and pursuit/engagement targets keep changing. The four suffixes have 5, 19, 59 and 118 distinct position states and two distinct target states each. Twelve movement/pursuit/reservation/blocked counters grow while combat counters remain fixed. This is continuing movement and replanning without HP progress, not a fixed-position diagnosis. The precise contact/range/geometry/route cause and real-game outcome remain unknown.",'queueAction':'Preserve every failed attempt, leave blocked, continue ordinary queue. Separate recovery review required before any further retry.','noFurtherRetryAuthorized':True,'simulationExecutionsForDiagnosis':0,'physicsChanged':False,'nativeResultsAdded':False}
 out.mkdir(parents=True,exist_ok=True)
 with (out/'REVIEW.json').open('x') as f:f.write(json.dumps(report,sort_keys=True,indent=2)+'\n')
 with (out/'README.md').open('x') as f:f.write(f'# Exhausted Burgundian Elite Skirmisher / Mapuche Elite Kona\n\nJob `{JOB}`, counts 27 / 19, exhausted all four normal seed-0 watchdogs at 2026-11-09T12:30:36.891Z. No seed completed.\n\nSeed 0 exhausted all four normal watchdogs without completing. All four timelines have constant-survivor/HP suffixes: one Elite Skirmisher at 22 HP and eighteen Elite Kona at 2,460 combined HP. Those suffixes contain 5, 19, 59 and 119 snapshots. All sampled survivors in those suffixes are idle with null attack targets, but positions and pursuit/engagement targets keep changing. The four suffixes have 5, 19, 59 and 118 distinct position states and two distinct target states each. Twelve movement/pursuit/reservation/blocked counters grow while combat counters remain fixed. This is continuing movement and replanning without HP progress, not a fixed-position diagnosis. The precise contact/range/geometry/route cause and real-game outcome remain unknown.\n\nNo native winner, draw, pair review or correction is assigned. No simulation or replay was executed for this diagnosis. Keep this case blocked pending separate recovery review; no further retry, physics change or imported winner is authorized. The ordinary queue continues.\n\nSource `{SOURCE}`, exact physical context, original evidence and all attempt-line/progress hashes are retained in `REVIEW.json`. Reproduce into a new directory:\n\n```sh\npython {BASE}/diagnostics/{JOB}/analyze.py --output <new-directory>\n```\n')
 print(json.dumps({'jobId':JOB,'attempts':len(attempts),'completedSeeds':0,'simulationExecutions':0,'assignedOutcome':None}))
if __name__=='__main__':main()
