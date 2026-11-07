#!/usr/bin/env node
// Validate remaining forecasts in frozen confidence order. Never resume old queues.
import assert from 'node:assert/strict';
import {readFileSync,readdirSync,existsSync,mkdirSync,openSync,closeSync,writeFileSync,unlinkSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {execFileSync} from 'node:child_process';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {runOrderedQueue} from './rolling-validation-queue.mjs';
import {SIM,ROOT,DIR,sha,load,lines,gzlines,now,json,append,verifyManifest,payload,required,canonicalOutcome,exact,digest} from './forecast-validation-lib.mjs';
import {loadScreeningPolicy,screeningDecision,screeningOutcome,verifySamplingReview} from './forecast-screening-policy.mjs';

const manifest=verifyManifest(),jobs=gzlines(resolve(DIR,'jobs.jsonl.gz'));
const samplingPolicy=loadScreeningPolicy(DIR);
const authorization=load(resolve(DIR,'launch-approval.json'));
assert(authorization.durationApproved===true,'Long-running launch needs the saved duration approval');
const parity=load(resolve(DIR,'reviews/runtime-parity.json'));
assert(parity.passed&&parity.physicsUnchanged);assert.equal(parity.campaignHash,manifest.campaignHash);
const expected=new Map(gzlines(resolve(DIR,'expected-native-records.jsonl.gz')).map(r=>[r.jobId,r.records]));
const original=new Map(gzlines(resolve(DIR,'original-evidence.jsonl.gz')).map(r=>[r.evidenceId,r.evidence]));
const statePath=resolve(DIR,'state.json'),lock=resolve(DIR,'.runner.lock');
const runPath=resolve(DIR,'runs.jsonl'),attemptPath=resolve(DIR,'attempts.jsonl');
const byJob=new Map(jobs.map(j=>[j.id,j]));
function alive(pid){try{process.kill(pid,0);return !/^State:\s*Z/m.test(readFileSync(`/proc/${pid}/status`,'utf8'));}catch{return false;}}
if(existsSync(lock)){
 const old=load(lock);assert(!alive(old.pid),`runner already live: ${old.pid}`);unlinkSync(lock);
}
const fd=openSync(lock,'wx');writeFileSync(fd,JSON.stringify({pid:process.pid,startedAt:now(),campaignHash:manifest.campaignHash}));closeSync(fd);
const state=existsSync(statePath)?load(statePath):{createdAt:now(),campaignHash:manifest.campaignHash,completedPhases:[]};
assert.equal(state.campaignHash,manifest.campaignHash);
const fresh=new Map();
if(existsSync(runPath))for(const r of lines(runPath)){
 assert.equal(r.campaignHash,manifest.campaignHash);const job=byJob.get(r.matchupId);assert(job);
 assert.equal(r.contextHash,job.contextHash);assert.deepEqual(r.profileHashes,job.profileHashes);assert.deepEqual(r.counts,job.counts);
 assert(['win','loss','draw'].includes(r.outcome));assert(r.finalStateHash&&r.eventLogHash);
 const key=`${job.id}:${r.seed}`;assert(!fresh.has(key),'duplicate fresh measurement');fresh.set(key,r);
}
const reviews=new Map();
mkdirSync(resolve(DIR,'pair-reviews'),{recursive:true});mkdirSync(resolve(DIR,'progress'),{recursive:true});
for(const file of readdirSync(resolve(DIR,'pair-reviews')).filter(f=>f.endsWith('.json'))){
 const r=load(resolve(DIR,'pair-reviews',file)),{reviewHash,...body}=r;assert.equal(reviewHash,digest(body));
 assert.equal(r.campaignHash,manifest.campaignHash);assert(byJob.has(r.jobId));reviews.set(r.jobId,r);
}
const failures=existsSync(attemptPath)?lines(attemptPath):[];
const blocked=new Set(failures.filter(r=>r.exhausted).map(r=>r.matchupId));
const controlsPath=resolve(DIR,'queue-controls.json');
const controls=existsSync(controlsPath)?load(controlsPath):null;
if(controls){
 const {controlsHash,...body}=controls;assert.equal(controlsHash,digest(body));assert.equal(controls.campaignHash,manifest.campaignHash);
 assert.equal(controls.inventorySha256,sha(readFileSync(resolve(DIR,'jobs.jsonl.gz'))));
 for(const f of controls.schedulerFiles){
  const override=samplingPolicy?.sourceOverrides.find(r=>r.path===f.path);
  if(override)assert.equal(override.originalSha256,f.sha256);
  assert.equal(sha(readFileSync(resolve(ROOT,f.path))),override?.sha256??f.sha256,'scheduler source changed');
 }
 for(const q of controls.quarantinedContexts){
  assert(byJob.has(q.jobId));assert.equal(q.status,'unfinished_not_a_result');
  assert.equal(sha(readFileSync(resolve(ROOT,q.diagnosisFile))),q.diagnosisSha256);
  if(!reviews.has(q.jobId))blocked.add(q.jobId);
 }
}
const active=new Map();let stopped=false,pool,lastCheckpoint=Date.now(),sinceCheckpoint=0;
function progress(){const terminal=Boolean(state.finishedAt);Object.assign(state,{status:terminal?state.status:stopped?'stopping':'running',pid:terminal?null:process.pid,updatedAt:now(),savedFreshSeeds:fresh.size,
 reviewedJobs:reviews.size,changedJobs:[...reviews.values()].filter(r=>r.changed).length,
 singleSeedConfirmedJobs:[...reviews.values()].filter(r=>r.evidenceLevel==='single_seed_confirmation').length,
 multiSeedValidatedJobs:[...reviews.values()].filter(r=>r.evidenceLevel!=='single_seed_confirmation').length,
 samplingPolicyHash:samplingPolicy?.amendmentHash??null,
 remainingJobs:manifest.totalForecastContexts-reviews.size,remainingRunnableJobs:jobs.length-reviews.size,
 totalForecastContexts:manifest.totalForecastContexts,runnableJobs:jobs.length,heldContexts:manifest.heldContexts,blockedJobs:[...blocked],active:[...active.values()],
 schedulerVersion:'rolling-phase-queue-v2',queueControlsHash:controls?.controlsHash??null});json(statePath,state);}
process.on('SIGTERM',()=>{stopped=true;progress();});process.on('SIGINT',()=>{stopped=true;progress();});
function git(args){const env={...process.env};delete env.GH_TOKEN;
 return execFileSync('git',['-c','http.extraHeader=','-c','credential.helper=',...args],{cwd:ROOT,env,encoding:'utf8',timeout:60000,maxBuffer:1024*1024,stdio:['ignore','pipe','pipe']}).trim();}
function checkpoint(label){
 progress();const branch='simulations/civ-forecast-validation-2026-11-07';assert.equal(git(['branch','--show-current']),branch);
 const prefix=relative(ROOT,DIR);assert(git(['diff','--cached','--name-only']).split('\n').every(p=>!p||p.startsWith(prefix+'/')));
 git(['add','--',prefix]);if(git(['diff','--cached','--name-only']))git(['commit','-m',`Checkpoint matchup forecast validation: ${label}`]);
 try{git(['push','origin',branch]);state.lastPushedAt=now();state.remotePending=false;state.lastPushError=null;}
 catch(error){state.remotePending=true;state.lastPushError=String(error);console.error(JSON.stringify({pushPending:String(error)}));}
 json(statePath,state);lastCheckpoint=Date.now();sinceCheckpoint=0;
}
function saved(job){return [...fresh.values()].filter(r=>r.matchupId===job.id);}
async function execute(job,seed,purpose){
 for(let attempt=0;attempt<manifest.policy.wallTimeoutSteps.length;attempt++){
  const limitSeconds=manifest.policy.wallTimeoutSteps[attempt],startedAt=now(),start=performance.now();
  active.set(job.id,{jobId:job.id,seed,purpose,attempt:attempt+1,startedAt,limitSeconds});progress();
  const diagnosticProgressPath=resolve(DIR,'progress',`${job.id}-${seed}-${purpose}-${Date.now()}.jsonl`);
  const result=await pool.run({...payload(job,seed),diagnosticProgressPath},limitSeconds);
  const wallSeconds=(performance.now()-start)/1000;
  if(result.result&&['win','draw'].includes(result.result.outcome))return {result:result.result,wallSeconds,startedAt,finishedAt:now(),purpose};
  const failure={campaignHash:manifest.campaignHash,matchupId:job.id,seed,purpose,attempt:attempt+1,startedAt,
   finishedAt:now(),wallSeconds,limitSeconds,watchdog:result.watchdog??false,error:result.error??null,
   lastProgress:result.lastProgress??null,exhausted:attempt===manifest.policy.wallTimeoutSteps.length-1,
   progressPath:relative(ROOT,diagnosticProgressPath)};
  append(attemptPath,failure);console.error(JSON.stringify({attemptFailed:failure}));
 }
 blocked.add(job.id);return null;
}
function record(job,seed,run){const r=run.result;
 const row={campaignHash:manifest.campaignHash,matchupId:job.id,pairKey:job.pairKey,contextHash:job.contextHash,
  physicsVersion:manifest.physicsVersion,executionVersion:manifest.executionVersion,seed,
  startedAt:run.startedAt,finishedAt:run.finishedAt,wallSeconds:run.wallSeconds,purpose:run.purpose,
  ...(samplingPolicy?{samplingPolicyHash:samplingPolicy.amendmentHash}:{}),
  counts:job.counts,profileHashes:job.profileHashes,scenarioHash:job.scenarioHash,
  outcome:r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss',winnerOwner:r.winnerOwner,
  unitStartingHp:r.startingHpByOwner[2],opponentStartingHp:r.startingHpByOwner[3],
  unitRemainingHp:r.remainingByOwner[2]?.hp??0,opponentRemainingHp:r.remainingByOwner[3]?.hp??0,
  unitSurvivors:r.remainingByOwner[2]?.units??0,opponentSurvivors:r.remainingByOwner[3]?.units??0,
  ticks:r.ticks,simulationSeconds:r.ticks/60,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash};
 assert(!fresh.has(`${job.id}:${seed}`));append(runPath,row);fresh.set(`${job.id}:${seed}`,row);sinceCheckpoint++;
 console.log(JSON.stringify({saved:`${job.id}:${seed}`,outcome:row.outcome,wallSeconds:row.wallSeconds}));return row;
}
async function reviewJob(job){
 let evidenceRows,control,check;
 const originalRows=job.evidenceIds.map(id=>({id,...original.get(id)}));
 const originalOutcomes=originalRows.map(r=>r.outcome);
 const decision=()=>screeningDecision(job,saved(job),originalOutcomes,samplingPolicy);
 const needed=()=>samplingPolicy?decision().requiredSeeds:required(saved(job));
 if(job.validationMode==='exact_replay_of_measured_seed_set'){
  evidenceRows=expected.get(job.id);assert(evidenceRows?.length);
  control=[...evidenceRows].sort((a,b)=>a.wallSeconds-b.wallSeconds||a.seed-b.seed)[0];
  let r=fresh.get(`${job.id}:${control.seed}`);
  if(!r){const run=await execute(job,control.seed,'native_exact_replay');if(!run)return; r=record(job,control.seed,run);}
  check={exact:exact(r,control),seed:control.seed,freshRecordHash:digest(r),expectedRecordHash:digest(control)};
 }else{
  while(needed().length){
   if(stopped)return;
   const seed=needed()[0],run=await execute(job,seed,'fresh_measurement');if(!run)return;record(job,seed,run);
  }
  if(stopped)return;
  evidenceRows=saved(job);control=[...evidenceRows].sort((a,b)=>a.wallSeconds-b.wallSeconds||a.seed-b.seed)[0];
  const run=await execute(job,control.seed,'independent_exact_replay');if(!run)return;
  check={exact:exact(run.result,control),seed:control.seed,expectedRecordHash:digest(control),
   result:run.result,wallSeconds:run.wallSeconds,startedAt:run.startedAt,finishedAt:run.finishedAt};
 }
 if(!check.exact){
  append(attemptPath,{campaignHash:manifest.campaignHash,matchupId:job.id,purpose:'exact_replay',exhausted:true,
   error:{name:'ExactReplayMismatch',message:'Same frozen context produced a different result; diagnosis required'},check,at:now()});
  blocked.add(job.id);return;
 }
 const sampling=samplingPolicy?screeningDecision(job,evidenceRows,originalOutcomes,samplingPolicy):null;
 assert.equal((sampling?.requiredSeeds??required(evidenceRows)).length,0);
 const outcome=originalRows.every(r=>r.evidenceType==='identity')?'equivalent':samplingPolicy?screeningOutcome(job,evidenceRows,originalOutcomes,samplingPolicy):canonicalOutcome(job,evidenceRows);
 const body={campaignHash:manifest.campaignHash,jobId:job.id,reviewedAt:now(),status:'passed',
  context:job.context,contextHash:job.contextHash,pairKey:job.pairKey,physicsVersion:manifest.physicsVersion,
  validationMode:sampling?.evidenceLevel==='single_seed_confirmation'?'single_seed_forecast_screen':job.validationMode,
  ...(sampling?{samplingPolicyHash:samplingPolicy.amendmentHash,evidenceLevel:sampling.evidenceLevel,samplingDecision:sampling}:{}),
  seedCount:evidenceRows.length,requiredSeeds:sampling?.requiredSeeds??required(evidenceRows),
  seedResults:evidenceRows.map(r=>({seed:r.seed,winnerOwner:r.winnerOwner,ticks:r.ticks,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,
   winnerHpFraction:Math.max(r.unitRemainingHp/r.unitStartingHp,r.opponentRemainingHp/r.opponentStartingHp),
   ...(r.sourceFile?{sourceFile:r.sourceFile,sourceLine:r.sourceLine,sourceLineSha256:r.sourceLineSha256}:{}),recordHash:digest(r)})),
  exactReplay:check,outcome,originalEvidenceIds:job.evidenceIds,
  originalOutcomes:originalRows.map(r=>({evidenceId:r.id,outcome:r.outcome,evidenceType:r.evidenceType})),
  changed:originalRows.some(r=>r.outcome!==outcome),displayedMismatchCells:job.displayedCells};
 const review={...body,reviewHash:digest(body)};
 if(samplingPolicy)verifySamplingReview(job,evidenceRows,originalOutcomes,review,samplingPolicy);
 json(resolve(DIR,'pair-reviews',job.id+'.json'),review);reviews.set(job.id,review);
 console.log(JSON.stringify({reviewed:job.id,outcome,changed:review.changed,completed:reviews.size,total:jobs.length}));
}
let checkpointTimer;
const finalizedPhases=new Set();
const phaseIndex=new Map(jobs.map((job,i)=>[job.id,Math.floor(i/manifest.policy.phaseJobs)]));
function finishPhase(index){
 const phase=String(index+1).padStart(3,'0');if(finalizedPhases.has(phase))return;
 const batch=jobs.slice(index*manifest.policy.phaseJobs,(index+1)*manifest.policy.phaseJobs);
 if(!batch.every(j=>reviews.has(j.id)||blocked.has(j.id)))return;
 const complete=batch.filter(j=>reviews.has(j.id));
 const path=resolve(DIR,'reviews',`${phase}.json`);
 if(existsSync(path)&&load(path).status==='passed'){
  const old=load(path);assert.equal(old.campaignHash,manifest.campaignHash);
  assert.equal(old.plannedJobs,batch.length);assert.equal(old.reviewHashes.length,batch.length);
  for(const r of old.reviewHashes)assert.equal(reviews.get(r.jobId)?.reviewHash,r.reviewHash);
  finalizedPhases.add(phase);return;
 }
 const report={phase,campaignHash:manifest.campaignHash,reviewedAt:now(),plannedJobs:batch.length,reviewedJobs:complete.length,
  samplingPolicyHash:samplingPolicy?.amendmentHash??null,
  singleSeedConfirmations:complete.filter(j=>reviews.get(j.id).evidenceLevel==='single_seed_confirmation').length,
  multiSeedValidations:complete.filter(j=>reviews.get(j.id).evidenceLevel!=='single_seed_confirmation').length,
  changedJobs:complete.filter(j=>reviews.get(j.id).changed).length,blockedJobs:batch.filter(j=>blocked.has(j.id)).map(j=>j.id),
  reviewHashes:complete.map(j=>({jobId:j.id,reviewHash:reviews.get(j.id).reviewHash})),
  schedulerVersion:'rolling-phase-queue-v2',queueControlsHash:controls?.controlsHash??null,
  status:complete.length===batch.length?'passed':'complete_with_blocked'};
 json(path,report);finalizedPhases.add(phase);
 if(report.status==='passed'&&!state.completedPhases.includes(phase))state.completedPhases.push(phase);
 checkpoint(`phase ${phase}: ${reviews.size}/${jobs.length} reviewed`);
}
try{
 delete state.finishedAt;state.status='running';
 progress();pool=new RankingWorkerPool(manifest.policy.workers,{workerUrl:new URL('../mismatch-validation-worker.mjs',import.meta.url),maxTicks:Number.MAX_SAFE_INTEGER});
 checkpointTimer=setInterval(()=>{if(Date.now()-lastCheckpoint>=600000)checkpoint(`${reviews.size}/${jobs.length} reviewed, partial`);},30000);
 for(let index=0;index<Math.ceil(jobs.length/manifest.policy.phaseJobs);index++)finishPhase(index);
 await runOrderedQueue({jobs,workers:manifest.policy.workers,
  skip:job=>reviews.has(job.id)||blocked.has(job.id),shouldStop:()=>stopped,run:reviewJob,
  onSettled:job=>{active.delete(job.id);progress();finishPhase(phaseIndex.get(job.id));}});
 state.status=stopped?'interrupted':reviews.size===jobs.length&&!manifest.heldContexts?'complete':'blocked_needs_diagnosis';
 state.finishedAt=now();state.active=[];state.pid=null;json(statePath,state);
 // Checkpoint must preserve terminal status instead of advertising a live queue.
 const terminal=state.status;checkpoint(`${terminal}: ${reviews.size}/${jobs.length}`);state.status=terminal;state.pid=null;state.active=[];json(statePath,state);
}finally{
 clearInterval(checkpointTimer);
 await pool?.close();if(existsSync(lock)&&load(lock).pid===process.pid)unlinkSync(lock);
}
