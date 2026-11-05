#!/usr/bin/env node
// Targeted legacy/current disagreement validation. Never resumes the old queue.
import assert from 'node:assert/strict';
import {readFileSync,readdirSync,existsSync,mkdirSync,openSync,closeSync,writeFileSync,unlinkSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {execFileSync} from 'node:child_process';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {SIM,ROOT,DIR,sha,load,lines,gzlines,now,json,append,verifyManifest,payload,required,canonicalOutcome,exact,digest} from './mismatch-validation-lib.mjs';

const manifest=verifyManifest(),jobs=gzlines(resolve(DIR,'jobs.jsonl.gz'));
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
const active=new Map();let stopped=false,pool,lastCheckpoint=Date.now(),sinceCheckpoint=0;
function progress(){const terminal=Boolean(state.finishedAt);Object.assign(state,{status:terminal?state.status:stopped?'stopping':'running',pid:terminal?null:process.pid,updatedAt:now(),savedFreshSeeds:fresh.size,
 reviewedJobs:reviews.size,changedJobs:[...reviews.values()].filter(r=>r.changed).length,
 remainingJobs:jobs.length-reviews.size,blockedJobs:[...blocked],active:[...active.values()]});json(statePath,state);}
process.on('SIGTERM',()=>{stopped=true;progress();});process.on('SIGINT',()=>{stopped=true;progress();});
function git(args){const env={...process.env};delete env.GH_TOKEN;
 return execFileSync('git',['-c','http.extraHeader=','-c','credential.helper=',...args],{cwd:ROOT,env,encoding:'utf8',timeout:60000,maxBuffer:1024*1024,stdio:['ignore','pipe','pipe']}).trim();}
function checkpoint(label){
 progress();const branch='simulations/civ-matchups-mismatch-validation-2026-11-05';assert.equal(git(['branch','--show-current']),branch);
 const prefix=relative(ROOT,DIR);assert(git(['diff','--cached','--name-only']).split('\n').every(p=>!p||p.startsWith(prefix+'/')));
 git(['add','--',prefix]);if(git(['diff','--cached','--name-only']))git(['commit','-m',`Checkpoint matchup disagreement validation: ${label}`]);
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
 if(job.validationMode==='exact_replay_of_measured_seed_set'){
  evidenceRows=expected.get(job.id);assert(evidenceRows?.length);
  control=[...evidenceRows].sort((a,b)=>a.wallSeconds-b.wallSeconds||a.seed-b.seed)[0];
  let r=fresh.get(`${job.id}:${control.seed}`);
  if(!r){const run=await execute(job,control.seed,'native_exact_replay');if(!run)return; r=record(job,control.seed,run);}
  check={exact:exact(r,control),seed:control.seed,freshRecordHash:digest(r),expectedRecordHash:digest(control)};
 }else{
  while(required(saved(job)).length){
   if(stopped)return;
   const seed=required(saved(job))[0],run=await execute(job,seed,'fresh_measurement');if(!run)return;record(job,seed,run);
  }
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
 assert.equal(required(evidenceRows).length,0);
 const originalRows=job.evidenceIds.map(id=>({id,...original.get(id)}));
 const outcome=originalRows.every(r=>r.evidenceType==='identity')?'equivalent':canonicalOutcome(job,evidenceRows);
 const body={campaignHash:manifest.campaignHash,jobId:job.id,reviewedAt:now(),status:'passed',
  context:job.context,contextHash:job.contextHash,pairKey:job.pairKey,physicsVersion:manifest.physicsVersion,
  validationMode:job.validationMode,seedCount:evidenceRows.length,requiredSeeds:required(evidenceRows),
  seedResults:evidenceRows.map(r=>({seed:r.seed,winnerOwner:r.winnerOwner,ticks:r.ticks,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,
   winnerHpFraction:Math.max(r.unitRemainingHp/r.unitStartingHp,r.opponentRemainingHp/r.opponentStartingHp),
   ...(r.sourceFile?{sourceFile:r.sourceFile,sourceLine:r.sourceLine,sourceLineSha256:r.sourceLineSha256}:{}),recordHash:digest(r)})),
  exactReplay:check,outcome,originalEvidenceIds:job.evidenceIds,
  originalOutcomes:originalRows.map(r=>({evidenceId:r.id,outcome:r.outcome,evidenceType:r.evidenceType})),
  changed:originalRows.some(r=>r.outcome!==outcome),displayedMismatchCells:job.displayedCells};
 const review={...body,reviewHash:digest(body)};json(resolve(DIR,'pair-reviews',job.id+'.json'),review);reviews.set(job.id,review);
 console.log(JSON.stringify({reviewed:job.id,outcome,changed:review.changed,completed:reviews.size,total:jobs.length}));
}
let checkpointTimer;
try{
 delete state.finishedAt;state.status='running';
 progress();pool=new RankingWorkerPool(manifest.policy.workers,{workerUrl:new URL('../mismatch-validation-worker.mjs',import.meta.url),maxTicks:Number.MAX_SAFE_INTEGER});
 checkpointTimer=setInterval(()=>{if(Date.now()-lastCheckpoint>=600000)checkpoint(`${reviews.size}/${jobs.length} reviewed, partial`);},30000);
 for(let start=0;start<jobs.length&&!stopped;start+=manifest.policy.phaseJobs){
  const phase=String(1+start/manifest.policy.phaseJobs).padStart(3,'0');
  const batch=jobs.slice(start,start+manifest.policy.phaseJobs),pending=batch.filter(j=>!reviews.has(j.id)&&!blocked.has(j.id));
  let cursor=0;
  await Promise.all(Array.from({length:manifest.policy.workers},async()=>{
   while(!stopped&&cursor<pending.length){const job=pending[cursor++];await reviewJob(job);active.delete(job.id);progress();}
  }));
  const complete=batch.filter(j=>reviews.has(j.id));
  const report={phase,campaignHash:manifest.campaignHash,reviewedAt:now(),plannedJobs:batch.length,reviewedJobs:complete.length,
   changedJobs:complete.filter(j=>reviews.get(j.id).changed).length,blockedJobs:batch.filter(j=>blocked.has(j.id)).map(j=>j.id),
   reviewHashes:complete.map(j=>({jobId:j.id,reviewHash:reviews.get(j.id).reviewHash})),status:complete.length===batch.length?'passed':stopped?'interrupted':'complete_with_blocked'};
  json(resolve(DIR,'reviews',`${phase}.json`),report);
  if(report.status==='passed'&&!state.completedPhases.includes(phase))state.completedPhases.push(phase);
  checkpoint(`phase ${phase}: ${reviews.size}/${jobs.length} reviewed`);
 }
 state.status=stopped?'interrupted':reviews.size===jobs.length?'complete':'blocked_needs_diagnosis';
 state.finishedAt=now();state.active=[];state.pid=null;json(statePath,state);
 // Checkpoint must preserve terminal status instead of advertising a live queue.
 const terminal=state.status;checkpoint(`${terminal}: ${reviews.size}/${jobs.length}`);state.status=terminal;state.pid=null;state.active=[];json(statePath,state);
}finally{
 clearInterval(checkpointTimer);
 await pool?.close();if(existsSync(lock)&&load(lock).pid===process.pid)unlinkSync(lock);
}
