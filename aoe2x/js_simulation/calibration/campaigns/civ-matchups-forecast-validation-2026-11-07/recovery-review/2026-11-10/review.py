"""Review saved evidence only. No engine imports, executions, or result mutations."""
import argparse, collections, csv, datetime, gzip, hashlib, json, os, subprocess
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'aoe2x/js_simulation/calibration').is_dir())
BASE=Path('aoe2x/js_simulation/calibration/campaigns')
C=BASE/'civ-matchups-forecast-validation-2026-11-07'
OLD=BASE/'civ-matchups-mismatch-validation-2026-11-05'
SOURCE='7d53deb5df104989a9b2856f43832a492c09d44a'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return (ROOT/p).read_bytes()
def obj(p):return json.loads(read(p))
def rows(p):return list(map(json.loads,gzip.decompress(read(p)).splitlines()))
def stable(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
def suffix(rs,fn):
 i=len(rs)-1
 while i>0 and fn(rs[i-1])==fn(rs[-1]):i-=1
 return rs[i:]
def hp(r):return {'byOwner':r['byOwner'],'units':[{k:u[k] for k in ('id','owner','hp')}for u in r['positions']]}
def core(r):return {'byOwner':r['byOwner'],'positions':r['positions']}
def analyze():
 manifest=obj(C/'manifest.json');fixed=[]
 policy=obj(C/'sampling-policy-v3.json')
 assert sha(read(C/'manifest.json'))==policy['baseManifestSha256']
 assert sha(read(C/'sampling-policy-v2.json'))==policy['previousPolicyFileSha256']
 replacements={r['path']:r for r in policy['sourceOverrides']}
 for f in manifest['runtimeFiles']+manifest['inputFiles']:
  replacement=replacements.get(f['path'])
  if replacement:assert replacement['originalSha256']==f['sha256']
  assert sha(read(f['path']))==(replacement['sha256']if replacement else f['sha256']),f['path']
  fixed.append(f)
 held={r['id']:r for r in rows(C/'held-contexts.jsonl.gz')}
 inventory=rows(C/'closeout/2026-11-10/remaining-contexts.jsonl.gz')
 assert len(inventory)==36 and len({r['jobId']for r in inventory})==36
 variants=obj(C/'sources/variant-profiles.json');byprofile=collections.defaultdict(list)
 for v in variants:byprofile[v['profileHash']].append(v)
 frozen=obj(BASE/'unit-rankings-path-recovery-2026-10-29/manifest.json')
 original={r['evidenceId']:r['evidence']for r in rows(C/'original-evidence.jsonl.gz')}
 jobs={r['id']:r for r in rows(C/'jobs.jsonl.gz')}
 oldjobs={r['id']:r for r in rows(OLD/'jobs.jsonl.gz')}
 journals={};attempts={};sources={};cache={}
 def bind(p):
  p=str(p);b=read(p);sources[p]=sha(b);return b
 for base in (C,OLD):
  journal=base/'runs.jsonl';js=collections.defaultdict(list)
  for n,raw in enumerate(bind(journal).splitlines(keepends=True),1):
   r=json.loads(raw);js[r['matchupId']].append({'record':r,'path':str(journal),'line':n,'sha256IncludingNewline':sha(raw)})
  journals[str(base)]=js
  ats=collections.defaultdict(list);journal=base/'attempts.jsonl'
  for n,raw in enumerate(bind(journal).splitlines(keepends=True),1):
   r=json.loads(raw);ats[r['matchupId']].append({'record':r,'path':str(journal),'line':n,'sha256IncludingNewline':sha(raw)})
  attempts[str(base)]=ats
 for p in [C/'held-contexts.jsonl.gz',C/'closeout/2026-11-10/remaining-contexts.jsonl.gz',C/'original-evidence.jsonl.gz',C/'sampling-policy-v2.json',C/'sampling-policy-v3.json',C/'manifest.json',C/'sources/variant-profiles.json',C/'monitor-reporting.json',C/'state.json']:bind(p)
 cases=[];nativeRefs=0;projectionRefs=0;timelineCount=0;numericCandidates=[]
 for wrapper in inventory:
  x=wrapper['fullInventoryContext'];jid=x['id'];profiles=[[{'key':v['key'],'civilization':v['civilization'],'unit':frozen['profiles'][v['key']]['mechanics']['unit_name']}for v in byprofile[h]]for h in x['profileHashes']]
  assert all(profiles)
  representative=[p[0]for p in profiles]
  label=' / '.join(p['civilization']+' '+p['unit']for p in representative)
  evidence=[{'id':i,'record':original[i]}for i in x['evidenceIds']]
  assert all(e['record']['context']==x['context']for e in evidence)
  case={'jobId':jid,'label':label,'profilesAndAliases':profiles,'counts':x['counts'],'displayedCells':x['displayedCells'],'physicalContext':x['context'],'contextHash':x['contextHash'],'originalEvidence':evidence,'nativeEvidenceComplete':False,'assignedOutcome':None,'simulationExecutionsForThisReview':0,'newReplayEvidence':{'required':False,'performed':False,'exact':None},'status':'reviewed_still_unfinished','retryExecuted':False}
  h=held.get(jid)
  if h and 'recoveryProjection'in h:
   p=h['recoveryProjection'];refs=[]
   for s in p['seedReferences']:
    ref=s['sourceReference'];path=ref['path']
    if path not in cache:cache[path]=read(path).splitlines()
    raw=cache[path][ref['line']-1];r=json.loads(raw)
    assert sha(raw)==ref['recordSha256']
    for key in ('counts','profileHashes','scenarioHash','pairKey'):assert r[key]==x[key],(jid,key)
    for key in ('seed','outcome','eventLogHash','finalStateHash','campaignHash'):assert r[key]==s[key],(jid,key)
    assert r['physicsVersion']==p['measurementPhysicsVersion']!='frozen-civ-matchups-v3'
    refs.append({**ref,'recordHashConvention':'without trailing newline','record':r,'verifiedExactPhysicalContext':True})
   assert sorted(s['record']['seed']for s in refs)==[0,1,2]
   assert len({s['record']['winnerOwner']for s in refs})==1
   projectionRefs+=len(refs)
   case.update({'category':'cross_engine_projection','sourceGroup':'held_projection','projectionPhysicsVersion':p['measurementPhysicsVersion'],'projectionMetadataPreserved':p,'verifiedOtherEngineSeedReferences':refs,'frozenCampaignCompletedSeeds':[],'nextAction':'Assess the candidate engine change and its game-fidelity evidence; require separately versioned recovery approval before executing missing target-engine work. Do not import these winners or rerun these completed source-engine seeds.','finding':'Three saved seeds agree under the stated alternate engine. All exact source record hashes and oriented counts/profiles/scenario match; the target frozen engine is not validated.'})
  else:
   is_old=h is not None;base=OLD if is_old else C;localid=jid.replace('fv_','mv_')if is_old else jid
   job=(oldjobs if is_old else jobs)[localid]
   for key in ('counts','profileHashes','scenarioHash','contextHash'):assert job[key]==x[key]
   label=' / '.join(k.split('|')[0]+' '+frozen['profiles'][k]['mechanics']['unit_name']for k in job['teamKeys'])
   case.update({'label':label,'teamKeys':job['teamKeys'],'sourceGroup':'held_native_stall'if is_old else'exhausted_forecast'})
   diagpath=h['diagnosisPath']if is_old else wrapper['diagnosisFile'];diagnosis=json.loads(bind(diagpath))
   assert sources[diagpath]==(h['diagnosisSha256']if is_old else wrapper['diagnosisSha256'])
   at=attempts[str(base)][localid]
   first_quarantine=jid=='fv_5e1e0d268234acff1d6e9008'
   assert len(at)==(3 if first_quarantine else 4),(jid,len(at))
   assert [a['record']['limitSeconds']for a in at]==[180,600,1800,3600][:len(at)]
   assert [a['record']['attempt']for a in at]==list(range(1,len(at)+1))
   if first_quarantine:
    observation=diagnosis['observations'][-1];raw=bind(observation['file']);assert sha(raw)==observation['sha256']
    archived=list(map(json.loads,raw.splitlines()));assert len(archived)==26
    case['additionalUnclosedDiagnosticSnapshot']={'path':observation['file'],'sha256':sha(raw),'snapshots':len(archived),'stableCoreSuffixSnapshots':len(suffix(archived,core)),'nativeResult':False,'closedAttemptJournalRecordPresent':False,'note':'The fourth saved diagnostic timeline has no corresponding closed attempt entry; do not describe this context as four exhausted watchdogs.'}
   saved=journals[str(base)][localid]
   assert len({z['record']['seed']for z in saved})==len(saved)
   for z in saved:
    r=z['record'];assert r['physicsVersion']=='frozen-civ-matchups-v3'
    for key in ('counts','profileHashes','scenarioHash','pairKey'):assert r[key]==x[key]
   nativeRefs+=len(saved)
   timelines=[]
   def hashes(v):
    out=set()
    if isinstance(v,dict):
     for k,val in v.items():
      if isinstance(val,str)and ('sha256'in k.lower())and len(val)==64:out.add(val)
      out|=hashes(val)
    elif isinstance(v,list):
     for val in v:out|=hashes(val)
    return out
   expectedhashes=hashes(diagnosis)
   for a in at:
    r=a['record'];path=r['progressPath'];raw=bind(path);assert sha(raw)in expectedhashes,(jid,path)
    rs=list(map(json.loads,raw.splitlines()));assert all(z['diagnosticOnly']for z in rs)
    hs=suffix(rs,hp);cs=suffix(rs,core)
    eventdelta={k:v-hs[0]['eventCounts'].get(k,0)for k,v in rs[-1]['eventCounts'].items()if v!=hs[0]['eventCounts'].get(k,0)}
    coreDelta={k:v-cs[0]['eventCounts'].get(k,0)for k,v in rs[-1]['eventCounts'].items()if v!=cs[0]['eventCounts'].get(k,0)}
    timelines.append({**a,'progressPath':path,'progressSha256':sha(raw),'savedSnapshots':len(rs),'hpSuffixSnapshots':len(hs),'coreSuffixSnapshots':len(cs),'hpSuffixDurationSimulationSeconds':rs[-1]['simulationSeconds']-hs[0]['simulationSeconds'],'uniquePositionStatesInHpSuffix':len({stable([{k:u[k]for k in ('id','owner','x','y')}for u in z['positions']])for z in hs}),'eventDeltasInHpSuffix':eventdelta,'eventDeltasInCoreSuffix':coreDelta,'savedFinalByOwner':rs[-1]['byOwner'],'savedFinalPositions':rs[-1]['positions'],'lastSavedTick':rs[-1]['tick'],'lastReportedProgress':r.get('lastProgress')})
    timelineCount+=1
   final=timelines[-1]
   if any(a['record'].get('error')for a in at):
    category='collision_exception';finding=diagnosis['diagnosis'];nextaction='Investigate ranged-crowd reservation extent transitions before movement validation. The failure is mid-fight; preserve the geometry assertion rather than suppressing it or assigning a result.'
   elif final['coreSuffixSnapshots']>1:
    if not final['eventDeltasInCoreSuffix']:
     category='idle_patrol_endpoints';finding='Survivors sit at patrol endpoints with no targets, unchanged HP, positions and event counters while ticks advance.';nextaction='Inspect completed-patrol order state and target reacquisition against real-game behavior; do not fix by forcing engagement or selecting a winner.'
    else:
     category='fixed_position_pursuit';finding='Positions, HP and targets become fixed while pursuit/reservation/blocked counters continue. More elapsed time has not restored combat.';nextaction='Inspect attack-range/contact-surface agreement, terminal route candidates and forest-boundary reachability. Establish the cause with saved geometry before proposing a reusable, separately versioned mechanics change.'
   else:
    category='moving_without_combat';finding='Movement and pursuit continue through a long unchanged-survivor/HP suffix; this is not a fixed-position freeze.';nextaction='Inspect pursuit/retarget/minimum-range and reservation cycles. Determine why movement fails to reach attack-ready state before proposing a reusable, separately versioned change.'
   if len(saved)>=3 and len({z['record']['winnerOwner']for z in saved if z['record']['seed']<3})>1:required=list(range(10))
   else:required=[0,1,2]if saved else[0]
   # The historical minimum remains evidence of an incomplete protocol, not permission to discard known failed later seeds.
   completed=sorted(z['record']['seed']for z in saved)
   seed0=next((z['record']for z in saved if z['record']['seed']==0),None)
   screen=None
   if seed0:
    owner=seed0['winnerOwner'];canonical='a_win'if seed0['profileHashes'][owner-2]==seed0['pairKey'].split('|')[0]else'b_win'
    prefix='unit'if owner==2 else'opponent';loser='opponent'if owner==2 else'unit';fraction=seed0[prefix+'RemainingHp']/seed0[prefix+'StartingHp']
    screen={'originalForecast':evidence[0]['record']['outcome'],'seed0CanonicalOutcome':canonical,'winnerRetainedOwnHpFraction':fraction,'loserEliminated':seed0[loser+'Survivors']==0,'meetsNumericV3SingleSeedScreen':canonical==evidence[0]['record']['outcome']and fraction>=.25 and seed0[loser+'Survivors']==0,'reclassificationApplied':False,'reason':'Historical recorded multi-seed protocol and known later failure remain visible; no retroactive completion is inferred.'}
    if screen['meetsNumericV3SingleSeedScreen']:numericCandidates.append(jid)
   case.update({'category':category,'diagnosisReference':{'path':diagpath,'sha256':sources[diagpath]},'historicalDiagnosis':diagnosis.get('diagnosis',diagnosis.get('classification')),'ownerSuppliedWinnerNotImported':h.get('userSuppliedWinnerTeamKey')if h else None,'attempts':timelines,'nativeSeedReferences':saved,'completedSeedsInOriginalLedger':completed,'originalLedger':str(base/'runs.jsonl'),'knownRequiredMissingSeeds':[s for s in required if s not in completed],'seedRequirementNote':('Recorded multi-seed requirement remains incomplete.'if saved else'Seed 0 is missing; whether seeds 1..2 or 1..9 are required depends on its result and subsequent winner variation.'),'singleSeedNumericScreen':screen,'finding':finding,'nextAction':nextaction,'precisionLimit':'Snapshots are diagnostic observations before the last progress marker; they do not capture all transient state at failure or prove the exact cause.'})
  cases.append(case)
 groups={k:{'contexts':sum(r['category']==k for r in cases),'displayedCells':sum(r['displayedCells']for r in cases if r['category']==k)}for k in sorted({r['category']for r in cases})}
 assert sum(r['displayedCells']for r in cases)==220
 assert nativeRefs==13 and projectionRefs==57 and timelineCount==67
 assert len(numericCandidates)==4
 report={'schemaVersion':1,'reviewedAt':datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),'ownerRequest':'Ok review the 36','sourceCommit':SOURCE,'scope':'Read-only review of all remaining contexts; no recovery execution or result promotion.','contextCount':36,'displayedCells':220,'groups':groups,'verifiedNativeSeedRecordsInSeparateLedgers':nativeRefs,'verifiedOtherEngineSeedReferences':projectionRefs,'verifiedClosedAttemptTimelines':timelineCount,'verifiedAdditionalUnclosedDiagnosticTimeline':1,'runtimeAndInputFilesVerified':len(fixed),'sourceHashes':sources,'numericSingleSeedCandidatesNotPromoted':numericCandidates,'simulationsExecuted':0,'replaysExecuted':0,'nativeResultsAdded':0,'contextsPromoted':0,'buildsOrDeploymentsTriggered':0,'recurringTasksRemainStopped':True,'cases':cases}
 return report

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output
 assert not (out/'review.json').exists(),'Never overwrite a review'
 subprocess.run(['git','cat-file','-e',SOURCE+'^{commit}'],cwd=ROOT,check=True)
 report=analyze();out.mkdir(parents=True,exist_ok=True)
 with (out/'review.json').open('x')as f:json.dump(report,f,indent=2);f.write('\n')
 with (out/'cases.csv').open('x',newline='')as f:
  keys=['jobId','label','counts','category','displayedCells','completedSeeds','missingSeeds','finding','nextAction'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
  for r in report['cases']:w.writerow({'jobId':r['jobId'],'label':r['label'],'counts':'/'.join(map(str,r['counts'])),'category':r['category'],'displayedCells':r['displayedCells'],'completedSeeds':r.get('completedSeedsInOriginalLedger',[]),'missingSeeds':r.get('knownRequiredMissingSeeds','target-engine evidence not complete'),'finding':r['finding'],'nextAction':r['nextAction']})
 print(json.dumps({k:v for k,v in report.items()if k not in ['cases','sourceHashes']},indent=2))
if __name__=='__main__':main()
