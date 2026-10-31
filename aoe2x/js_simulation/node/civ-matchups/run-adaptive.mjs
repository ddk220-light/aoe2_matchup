#!/usr/bin/env node
// Durable, adaptive civ-matchup collection. Combat is delegated unchanged to V3.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,openSync,closeSync,fsyncSync,appendFileSync,
  existsSync,mkdirSync,readdirSync,renameSync,unlinkSync} from 'node:fs';
import {resolve,dirname,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const ROOT=resolve(SIM,'../..');
const BASE=resolve(SIM,'calibration/campaigns/civ-matchups-campaign-2026-10-31');
const DIR=resolve(BASE,'adaptive');
const PILOT=resolve(BASE,'pilot');
const INFERENCE=resolve(BASE,'latest-inference');
const FROZEN=JSON.parse(readFileSync(resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const sha=value=>createHash('sha256').update(value).digest('hex');
const load=path=>JSON.parse(readFileSync(path,'utf8'));
const now=()=>new Date().toISOString();
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function atomic(path,text){mkdirSync(dirname(path),{recursive:true});const tmp=`${path}.tmp`;
  const fd=openSync(tmp,'w');try{writeFileSync(fd,text);fsyncSync(fd);}finally{closeSync(fd);}renameSync(tmp,path);}
function json(path,value){atomic(path,JSON.stringify(value,null,2)+'\n');}
function append(path,value){mkdirSync(dirname(path),{recursive:true});const fd=openSync(path,'a');
  try{appendFileSync(fd,JSON.stringify(value)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
function records(path){if(!existsSync(path))return[];const raw=readFileSync(path,'utf8');
  const lines=raw.split('\n');return lines.flatMap((s,i)=>{
    if(!s)return[];
    try{return[JSON.parse(s)];}
    catch(error){if(i===lines.length-1&&!raw.endsWith('\n'))return[];throw error;}
  });}
function command(program,args,{maxBuffer=16*1024*1024}={}){
  return execFileSync(program,args,{cwd:ROOT,encoding:'utf8',maxBuffer,stdio:['ignore','pipe','inherit']}).trim();
}
function loadManifest(){
  const manifest=load(resolve(DIR,'manifest.json'));
  const {campaignHash,...body}=manifest;
  assert.equal(digest(body),campaignHash,'campaign hash mismatch');
  assert.equal(manifest.nodeVersion,process.version);
  assert.equal(manifest.engineBaseCommit,FROZEN.sourceCommit);
  assert.equal(manifest.pilotCampaignHash,load(resolve(PILOT,'manifest.json')).campaignHash);
  for(const row of manifest.runtimeFiles)assert.equal(sha(readFileSync(resolve(ROOT,row.path))),row.sha256,`frozen source changed: ${row.path}`);
  const env=Object.fromEntries(Object.keys(process.env).filter(k=>k.startsWith('AOE2X_EXP_')).sort().map(k=>[k,process.env[k]]));
  assert.equal(digest(env),digest(manifest.simulationEnvironment));
  const bytes=readFileSync(resolve(DIR,manifest.matchupInventory.file));
  assert.equal(sha(bytes),manifest.matchupInventory.sha256,'inventory hash mismatch');
  const list=gunzipSync(bytes).toString('utf8').trim().split('\n').map(JSON.parse);
  assert.equal(list.length,manifest.matchupInventory.rows);
  return {manifest,jobs:new Map(list.map(x=>[x.pairKey,x]))};
}
function contextScenario(job){
  if(FROZEN.scenarios[job.scenarioHash])return FROZEN.scenarios[job.scenarioHash];
  const base=Object.values(FROZEN.scenarios).find(x=>x.family===job.family);
  assert(base,job.family);
  const scenario={...base,engineFamily:job.engineFamily};
  assert.equal(digest(scenario),job.scenarioHash);
  return scenario;
}
function jobPayload(job,seed){return {jobId:job.id,seed,
  teams:job.teamKeys.map((key,i)=>({mechanics:FROZEN.profiles[key].mechanics,count:job.counts[i]})),
  scenario:contextScenario(job),disableAiOrders:true,disableKiting:true,
  preserveOwnerOrientation:true,retainSnapshots:false};}
function validateSaved(row,job,campaignHash){
  assert.equal(row.campaignHash,campaignHash);assert.equal(row.matchupId,job.id);
  assert.equal(row.pairKey,job.pairKey);assert.deepEqual(row.profileHashes,job.profileHashes);
  assert.deepEqual(row.counts,job.counts);assert.equal(row.scenarioHash,job.scenarioHash);
  assert(Number.isSafeInteger(row.seed)&&row.seed>=0&&row.seed<=9);
  assert(['win','loss','draw'].includes(row.outcome));
  assert(row.finalStateHash&&row.eventLogHash&&Number.isFinite(row.ticks));
  assert(row.wallSeconds>=0&&row.simulationSeconds===row.ticks/60);
}
function loadSaved(manifest,jobs){
  const saved=new Map();
  const jobsById=new Map([...jobs.values()].map(job=>[job.id,job]));
  const add=(row,job)=>{
    const key=`${job.id}:${row.seed}`;
    assert(!saved.has(key),`duplicate saved seed ${key}`);saved.set(key,row);
  };
  const pilot=load(resolve(PILOT,'manifest.json'));
  for(const file of readdirSync(resolve(PILOT,'runs')).filter(x=>x.endsWith('.jsonl')).sort()){
    for(const row of records(resolve(PILOT,'runs',file))){
      if(!['win','loss','draw'].includes(row.outcome)||row.error)continue;
      const job=jobsById.get(row.matchupId);
      assert(job&&row.campaignHash===pilot.campaignHash);
      assert.deepEqual([row.unitCount,row.opponentCount],job.counts);
      add(row,job);
    }
  }
  const runDir=resolve(DIR,'runs');mkdirSync(runDir,{recursive:true});
  for(const file of readdirSync(runDir).filter(x=>x.endsWith('.jsonl')).sort()){
    for(const row of records(resolve(runDir,file))){
      const job=jobs.get(row.pairKey);assert(job);
      validateSaved(row,job,manifest.campaignHash);add(row,job);
    }
  }
  return saved;
}
function outcomeFor(row){return row.outcome==='draw'?'draw':row.outcome==='win'?'win':'loss';}
function required(job,saved){
  const first=[0,1,2].map(seed=>saved.get(`${job.id}:${seed}`));
  if(first.some(x=>!x))return [0,1,2].filter(seed=>!saved.has(`${job.id}:${seed}`));
  if(new Set(first.map(outcomeFor)).size<=1)return[];
  return [3,4,5,6,7,8,9].filter(seed=>!saved.has(`${job.id}:${seed}`));
}
function progress(state,saved,pending=0){
  state.updatedAt=now();
  state.savedSeeds=saved.size;state.pendingCurrentPhaseSeeds=pending;
  json(resolve(DIR,'state.json'),state);
}
function selectPhase(state,jobs,saved){
  const decisions=gunzipSync(readFileSync(resolve(INFERENCE,'profile-matchups.jsonl.gz')))
    .toString('utf8').trim().split('\n').map(JSON.parse);
  assert.equal(decisions.length,68916);
  const unresolved=decisions.filter(p=>p.outcome==='unresolved' && jobs.has(p.pairKey));
  const blocked=new Set(state.blockedPairs??[]);
  const degree=new Map();
  for(const p of unresolved)for(const h of p.profiles)degree.set(h,(degree.get(h)??0)+1);
  const candidates=unresolved.filter(p=>!blocked.has(p.pairKey)&&required(jobs.get(p.pairKey),saved).length).sort((a,b)=>{
    const value=p=>(p.candidateOutcome?100000:0)+(degree.get(p.profiles[0])??0)
      +(degree.get(p.profiles[1])??0)+p.aliases*10;
    return value(b)-value(a)||a.pairKey.localeCompare(b.pairKey);
  });
  if(!candidates.length)return {unresolved:unresolved.length,selected:[]};
  const size=state.completedPhases.length?256:128;
  const selected=candidates.slice(0,size).map(p=>p.pairKey);
  return {unresolved:unresolved.length,selected};
}
async function pushCheckpoint(state,saved,phaseLabel,{final=false}={}){
  const branch='simulations/civ-matchups-campaign-2026-10-31';
  assert.equal(command('git',['branch','--show-current']),branch);
  const prefix=relative(ROOT,BASE);
  const existing=command('git',['diff','--cached','--name-only']);
  assert(existing.split('\n').every(x=>!x||x.startsWith(`${prefix}/`)),'unrelated staged change');
  state.lastPushedAt=now();state.lastPushError=null;
  progress(state,saved,state.pendingCurrentPhaseSeeds??0);
  command('git',['add','--',prefix]);
  if(final)command('git',['add','-f','--',relative(ROOT,INFERENCE)]);
  if(command('git',['diff','--cached','--name-only']))command('git',['commit','-m',`Checkpoint civ matchups: ${phaseLabel}`]);
  let last;
  for(let attempt=0;attempt<6;attempt++){
    try {command('git',['push','origin',branch]);return;}
    catch(error){last=error;state.lastPushError=String(error);}
    // Process remains in this phase until its durable checkpoint reaches GitHub.
    await pause(Math.min(60000,5000*2**attempt));
  }
  throw new Error(`phase checkpoint push failed: ${last}`);
}
async function refreshInference(){
  command('node',['aoe2x/js_simulation/node/build-civ-matchup-inference.mjs','--phase','infer-only',
    '--output',INFERENCE,'--campaign-dir',PILOT,'--campaign-dir',DIR],{maxBuffer:64*1024*1024});
  command('python',['aoe2x/js_simulation/tools/validate_civ_matchups_phase_one.py',INFERENCE]);
  return load(resolve(INFERENCE,'summary.json'));
}
async function runPhase(plan,state,manifest,jobs,saved,pool,shouldStop){
  const phaseJobs=plan.pairKeys.map(k=>jobs.get(k));assert(phaseJobs.every(Boolean));
  const journal=resolve(DIR,'runs',`${plan.id}.jsonl`);
  const blocked=new Set();let lastProgress=0,lastCheckpoint=Date.now(),sinceCheckpoint=0;
  const active=new Map();
  const steps=manifest.policy.wallTimeoutSteps;
  const attempt=async(job,seed)=>{
    for(let i=0;i<steps.length;i++){
      const startedAt=now(),start=performance.now();
      const message=await pool.run(jobPayload(job,seed),steps[i]);
      const wallSeconds=(performance.now()-start)/1000;
      if(message.result&&['win','draw'].includes(message.result.outcome)){
        const r=message.result;
        const outcome=r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss';
        const row={campaignHash:manifest.campaignHash,matchupId:job.id,pairKey:job.pairKey,seed,
          startedAt,finishedAt:now(),wallSeconds,outcome,winnerOwner:r.winnerOwner,
          counts:job.counts,unitCount:job.counts[0],opponentCount:job.counts[1],
          profileHashes:job.profileHashes,scenarioHash:job.scenarioHash,
          unitStartingHp:r.startingHpByOwner[2],opponentStartingHp:r.startingHpByOwner[3],
          unitRemainingHp:r.remainingByOwner[2]?.hp??0,opponentRemainingHp:r.remainingByOwner[3]?.hp??0,
          unitSurvivors:r.remainingByOwner[2]?.units??0,opponentSurvivors:r.remainingByOwner[3]?.units??0,
          ticks:r.ticks,simulationSeconds:r.ticks/60,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash};
        validateSaved(row,job,manifest.campaignHash);
        append(journal,row);saved.set(`${job.id}:${seed}`,row);
        console.log(JSON.stringify({saved:`${job.id}:${seed}`,outcome,wallSeconds,gameSeconds:row.simulationSeconds,phase:plan.id}));
        return {job,seed,ok:true,row};
      }
      const failure={at:now(),phase:plan.id,matchupId:job.id,pairKey:job.pairKey,seed,attempt:i+1,
        wallSeconds,limitSeconds:steps[i],watchdog:message.watchdog??false,
        error:message.error??null,lastProgress:message.lastProgress??null,
        resultOutcome:message.result?.outcome??null};
      append(resolve(DIR,'attempts.jsonl'),failure);
      console.error(JSON.stringify({retry:failure}));
    }
    blocked.add(job.pairKey);return {job,seed,ok:false};
  };
  while(true){
    const keys=new Set(active.keys());
    const pending=phaseJobs.flatMap(job=>required(job,saved).map(seed=>({job,seed})))
      .filter(({job,seed})=>!blocked.has(job.pairKey)&&!keys.has(`${job.id}:${seed}`))
      .sort((a,b)=>a.seed-b.seed||a.job.id.localeCompare(b.job.id));
    while(!shouldStop()&&active.size<manifest.policy.workers&&pending.length){
      const {job,seed}=pending.shift(),key=`${job.id}:${seed}`;
      active.set(key,attempt(job,seed).then(result=>({key,...result})));
    }
    if(!active.size)break;
    const done=await Promise.race(active.values());active.delete(done.key);
    if(done.ok)sinceCheckpoint++;
    const at=Date.now();
    if(at-lastProgress>=30000){progress(state,saved,pending.length);lastProgress=at;}
    if(sinceCheckpoint>=250||at-lastCheckpoint>=600000){
      progress(state,saved,pending.length);await pushCheckpoint(state,saved,`${plan.id} partial`);
      sinceCheckpoint=0;lastCheckpoint=Date.now();
    }
  }
  progress(state,saved,0);
  if(shouldStop())return {stopped:true,blocked:[...blocked]};
  const missing=phaseJobs.flatMap(job=>required(job,saved).map(seed=>`${job.id}:${seed}`));
  assert(missing.every(x=>blocked.has(phaseJobs.find(j=>x.startsWith(j.id+':'))?.pairKey)),
    `phase has unaccounted missing seeds: ${missing.slice(0,5)}`);
  const row=[...saved.values()].find(r=>phaseJobs.some(j=>j.id===r.matchupId)&&r.campaignHash===manifest.campaignHash);
  let replay=null;
  if(row){
    const job=phaseJobs.find(j=>j.id===row.matchupId);
    const msg=await pool.run(jobPayload(job,row.seed),Math.max(180,Math.min(3600,Math.ceil(row.wallSeconds*3+60))));
    replay={matchupId:job.id,seed:row.seed,
      exact:msg.result?.finalStateHash===row.finalStateHash&&msg.result?.eventLogHash===row.eventLogHash,
      error:msg.error??null,watchdog:msg.watchdog??false};
    assert(replay.exact,`exact replay failed ${JSON.stringify(replay)}`);
  }
  const review={phase:plan.id,reviewedAt:now(),status:blocked.size?'complete_with_blocked':'passed',
    pairs:phaseJobs.length,validSeeds:[...saved.values()].filter(r=>phaseJobs.some(j=>j.id===r.matchupId)).length,
    missingSeeds:missing.length,blockedPairs:[...blocked],replay};
  json(resolve(DIR,'phases',`${plan.id}-review.json`),review);
  state.blockedPairs=[...new Set([...(state.blockedPairs??[]),...blocked])];
  return review;
}

async function main(){
  const lock=resolve(DIR,'.runner.lock');
  if(existsSync(lock)){
    const oldPid=Number(readFileSync(lock,'utf8'));
    try{process.kill(oldPid,0);throw new Error(`adaptive runner already active under PID ${oldPid}`);}
    catch(error){if(error.code!=='ESRCH')throw error;unlinkSync(lock);}
  }
  const lockFd=openSync(lock,'wx');writeFileSync(lockFd,String(process.pid));closeSync(lockFd);
  let pool;
  let stop=false;const signal=()=>{stop=true;};
  process.on('SIGTERM',signal);process.on('SIGINT',signal);
  try{
    const {manifest,jobs}=loadManifest();
    const saved=loadSaved(manifest,jobs);
    const statePath=resolve(DIR,'state.json');
    const state=existsSync(statePath)?load(statePath):{createdAt:now(),completedPhases:[],blockedPairs:[]};
    assert(Array.isArray(state.completedPhases));
    state.status='running';state.pid=process.pid;progress(state,saved,0);
    pool=new RankingWorkerPool(manifest.policy.workers,{workerUrl:new URL('../collision-validation-worker.mjs',import.meta.url),
      maxTicks:manifest.policy.maxSimulationTicks});
    // Rebuild this derived table from the journals after every restart. The
    // phase journals, not the large generated table, are the checkpoint source.
    await refreshInference();
    while(!stop){
      let plan;
      if(state.activePhase)plan=load(resolve(DIR,'phases',`${state.activePhase}.json`));
      else{
        const next=selectPhase(state,jobs,saved);
        if(!next.selected.length){
          const summary=load(resolve(INFERENCE,'summary.json'));
          state.status=summary.uniqueNeedsSim===0?'complete':'blocked_needs_review';
          state.completedAt=state.status==='complete'?now():null;
          progress(state,saved,0);await pushCheckpoint(state,saved,state.status,{final:state.status==='complete'});
          break;
        }
        const id=String(state.completedPhases.length+1).padStart(3,'0');
        plan={id,pairKeys:next.selected,selectedAt:now(),sourceInferenceHash:load(resolve(INFERENCE,'manifest.json')).buildHash,
          unresolvedBefore:next.unresolved};
        json(resolve(DIR,'phases',`${id}.json`),plan);
        state.activePhase=id;progress(state,saved,0);
      }
      console.log(JSON.stringify({phaseStarted:plan.id,pairs:plan.pairKeys.length,
        unresolvedBefore:plan.unresolvedBefore,savedSeeds:saved.size}));
      const review=await runPhase(plan,state,manifest,jobs,saved,pool,()=>stop);
      if(review.stopped){state.status='paused';progress(state,saved,0);break;}
      const inference=await refreshInference();
      review.inferenceHash=inference.manifestHash;
      review.unresolvedAfter=inference.uniqueNeedsSim;
      review.coverage=inference.coverage;
      json(resolve(DIR,'phases',`${plan.id}-review.json`),review);
      state.completedPhases.push(plan.id);state.activePhase=null;
      state.lastInferenceHash=inference.manifestHash;
      state.lastUnresolved=inference.uniqueNeedsSim;
      progress(state,saved,0);
      await pushCheckpoint(state,saved,plan.id);
      console.log(JSON.stringify({phaseCompleted:plan.id,review}));
    }
  }catch(error){
    console.error(error.stack??String(error));
    const statePath=resolve(DIR,'state.json');
    if(existsSync(statePath)){
      const state=load(statePath);state.status='failed';state.failure={at:now(),message:String(error)};
      json(statePath,state);
    }
    process.exitCode=1;
  }finally{
    await pool?.close();unlinkSync(lock);
    process.off('SIGTERM',signal);process.off('SIGINT',signal);
  }
}
await main();
