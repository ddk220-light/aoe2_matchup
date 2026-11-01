#!/usr/bin/env node
// Repaired-physics evidence only. Targeted first-pass recovery, not bulk replay.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,openSync,closeSync,fsyncSync,appendFileSync,
  existsSync,mkdirSync,readdirSync,renameSync,unlinkSync} from 'node:fs';
import {resolve,dirname,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';
import {remainingSeeds,validateRecord,decision} from './stream-recovery-policy.mjs';
import {workerBudget,dispatchable} from './parallel-recovery-policy.mjs';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..'),ROOT=resolve(SIM,'../..');
const NAME='civ-matchups-first-pass-parallel-2026-11-01';
const DIR=resolve(SIM,'calibration/campaigns',NAME);
const BRANCH='simulations/civ-matchups-first-pass-parallel-2026-11-01';
const SOURCE='/workspace/aoe2_path_recovery/aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31';
const REPLAY='/workspace/aoe2_civ_collision_repair/aoe2x/js_simulation/calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31';
const PRIOR='/workspace/aoe2_civ_stream_hash/aoe2x/js_simulation/calibration/campaigns/civ-matchups-blocked-v2-stream-2026-11-01';
const CERT=resolve(SIM,'calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json');
const FROZEN_PATH=resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json');
const FROZEN=JSON.parse(readFileSync(FROZEN_PATH));
const sha=v=>createHash('sha256').update(v).digest('hex');
const load=p=>JSON.parse(readFileSync(p,'utf8'));
const now=()=>new Date().toISOString();
function atomic(path,value){const tmp=path+'.tmp',fd=openSync(tmp,'w');
  try{writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}renameSync(tmp,path);}
function append(path,row){const fd=openSync(path,'a');
  try{appendFileSync(fd,JSON.stringify(row)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
function rows(path,own=false){if(!existsSync(path))return[];const text=readFileSync(path,'utf8');
  if(own)assert(!text||text.endsWith('\n'),'partial own journal tail');
  const lines=text.split('\n');lines.pop();return lines.flatMap((text,i)=>text?[{
    row:JSON.parse(text),ref:{path,line:i+1,recordSha256:sha(text)}}]:[]);}
function live(pid){if(!pid)return false;try{return !/^State:\s*Z/m.test(readFileSync(`/proc/${pid}/status`,'utf8'));}
  catch(e){if(e.code==='ENOENT')return false;throw e;}}
function command(program,args){const env={...process.env},push=program==='git'&&args[0]==='push';
  if(push)delete env.GH_TOKEN;return execFileSync(program,push?['-c','http.extraHeader=','-c','credential.helper=',...args]:args,
    {cwd:ROOT,env,encoding:'utf8',stdio:['ignore','pipe','inherit']}).trim();}
function assertBulkPaused(){const state=load(resolve(REPLAY,'state.json'));
  const lock=resolve(REPLAY,'.runner.lock');
  assert(!live(state.pid)&&(!existsSync(lock)||!live(Number(readFileSync(lock,'utf8')))),
    'bulk replay is live; targeted replay would duplicate reserved work');
  assert(existsSync(resolve(REPLAY,'.stop-supervisor')),'bulk replay supervisor not paused');}
function prepare(){const path=resolve(DIR,'manifest.json');if(existsSync(path))return load(path);
  const cert=load(CERT),prior=load(resolve(PRIOR,'manifest.json'));
  assert.equal(prior.compatibleReplayCampaignHash,cert.v2CampaignHash);
  const jobs=load(resolve(PRIOR,'jobs.json'));atomic(resolve(DIR,'jobs.json'),jobs);
  const state=load(resolve(PRIOR,'state.json'));
  const body={schemaVersion:1,name:NAME,createdAt:now(),sourceCommit:command('git',['rev-parse','HEAD']),
    physicsVersion:'collision-repair-v2',nodeVersion:process.version,
    compatibilityCertificateSha256:sha(readFileSync(CERT)),compatibilityCertificateHash:cert.campaignHash,
    frozenInputsSha256:sha(readFileSync(FROZEN_PATH)),jobs:jobs.length,jobsSha256:sha(readFileSync(resolve(DIR,'jobs.json'))),
    compatibleSourceCampaigns:[{path:REPLAY,campaignHash:cert.v2CampaignHash},{path:PRIOR,campaignHash:prior.campaignHash}],
    runtimeFiles:[...cert.sharedRuntimeFiles,...cert.changedOutputFiles].map(r=>({path:r.path,sha256:r.streamSha256})),
    orchestrationFiles:['node/civ-matchups/run-first-pass-recovery.mjs','node/civ-matchups/stream-recovery-policy.mjs','node/civ-matchups/parallel-recovery-policy.mjs',
      'node/ranking-worker-pool.mjs','node/collision-validation-worker.mjs'].map(p=>({path:p,sha256:sha(readFileSync(resolve(SIM,p)))})),
    simulationEnvironment:cert.simulationEnvironment,priorHandoff:{pid:state.pid,active:state.active??null},
    policy:{workersWhileMainActive:2,workersAfterMainStops:4,subtractPriorLiveWorker:true,
      initialSeeds:[0,1,2],extraSeedsOnDisagreement:[3,4,5,6,7,8,9],
      wallTimeoutSteps:[3600,7200],maxTicks:Number.MAX_SAFE_INTEGER},publishBranch:BRANCH,
    scope:'Targeted blocked pairs only. Previously saved repaired-engine records retain their source campaign hashes. V3 records reserve historical seeds and provide comparisons only; every missing result is computed anew.'};
  const m={...body,campaignHash:digest(body)};atomic(path,m);return m;
}
function verify(m){const {campaignHash,...body}=m;assert.equal(digest(body),campaignHash);
  assert.equal(m.nodeVersion,process.version);assert.equal(sha(readFileSync(CERT)),m.compatibilityCertificateSha256);
  assert.equal(sha(readFileSync(FROZEN_PATH)),m.frozenInputsSha256);
  assert.equal(sha(readFileSync(resolve(DIR,'jobs.json'))),m.jobsSha256);
  for(const f of m.runtimeFiles)assert.equal(sha(readFileSync(resolve(ROOT,f.path))),f.sha256,`runtime changed: ${f.path}`);
  for(const f of m.orchestrationFiles)assert.equal(sha(readFileSync(resolve(SIM,f.path))),f.sha256,`orchestration changed: ${f.path}`);
  const env=Object.fromEntries(Object.keys(process.env).filter(k=>k.startsWith('AOE2X_EXP_')).sort().map(k=>[k,process.env[k]]));
  assert.deepEqual(env,m.simulationEnvironment);
  for(const source of m.compatibleSourceCampaigns){const sm=load(resolve(source.path,'manifest.json'));
    const {campaignHash,...body}=sm;assert.equal(digest(body),campaignHash);assert.equal(campaignHash,source.campaignHash);}
}
function sources(jobs,m){
  assertBulkPaused();const index=new Map(jobs.map(j=>[j.id,j]));
  const records=new Map(jobs.map(j=>[j.id,new Map()])),legacy=new Map(jobs.map(j=>[j.id,new Map()]));
  const add=(item,campaignHash)=>{const {row,ref}=item,job=index.get(row.matchupId);if(!job)return;
    validateRecord(row,job,campaignHash);assert(!records.get(job.id).has(row.seed),`duplicate repaired seed ${job.id}:${row.seed}`);
    records.get(job.id).set(row.seed,{...row,sourceReference:{...ref,campaignHash}});};
  for(const item of rows(resolve(REPLAY,'replays.jsonl')))add(item,m.compatibleSourceCampaigns[0].campaignHash);
  for(const item of rows(resolve(PRIOR,'runs.jsonl')))add(item,m.compatibleSourceCampaigns[1].campaignHash);
  for(const item of rows(resolve(DIR,'runs.jsonl'),true))add(item,m.campaignHash);
  for(const area of ['pilot','adaptive']){const sm=load(resolve(SOURCE,area,'manifest.json'));
    for(const file of readdirSync(resolve(SOURCE,area,'runs')).filter(x=>x.endsWith('.jsonl')))
      for(const {row,ref} of rows(resolve(SOURCE,area,'runs',file))){const j=index.get(row.matchupId);if(!j)continue;
        assert.equal(row.campaignHash,sm.campaignHash);assert(['win','loss','draw'].includes(row.outcome)&&!row.error);
        assert.deepEqual([row.unitCount,row.opponentCount],j.counts);
        assert.equal(row.scenarioHash,j.scenarioHash);legacy.get(j.id).set(row.seed,{row,ref});}}
  const priorState=load(resolve(PRIOR,'state.json'));let held=null;
  if(live(priorState.pid)){
    assert.equal(priorState.pid,m.priorHandoff.pid,'unexpected prior runner');
    if(priorState.active)assert.deepEqual(priorState.active,m.priorHandoff.active,'prior runner scheduled work after handoff');
    held=m.priorHandoff.active?`${m.priorHandoff.active.matchupId}:${m.priorHandoff.active.seed}`:null;
  }
  const main=load(resolve(SOURCE,'adaptive/state.json'));
  return {records,legacy,held,mainRunning:live(main.pid)&&main.status==='running'};
}
function payload(job,seed){let scenario=FROZEN.scenarios[job.scenarioHash];
  if(!scenario)scenario={...Object.values(FROZEN.scenarios).find(s=>s.family===job.family),engineFamily:job.engineFamily};
  assert.equal(digest(scenario),job.scenarioHash);
  return {jobId:job.id,seed,teams:job.teamKeys.map((k,i)=>({mechanics:FROZEN.profiles[k].mechanics,count:job.counts[i]})),
    scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false};}
function checkpoint(state,label){state.updatedAt=now();atomic(resolve(DIR,'state.json'),state);
  const prefix=relative(ROOT,DIR),staged=command('git',['diff','--cached','--name-only']);
  assert(staged.split('\n').every(x=>!x||x.startsWith(prefix+'/')),'unrelated staged changes');
  const files=['manifest.json','jobs.json','state.json','runs.jsonl','attempts.jsonl','pair-reviews.jsonl','evidence-ledger.jsonl']
    .map(n=>resolve(DIR,n)).filter(existsSync).map(p=>relative(ROOT,p));
  command('git',['add','--',...files]);if(command('git',['diff','--cached','--name-only']))command('git',['commit','-m',`Checkpoint parallel first pass: ${label}`]);
  try{command('git',['push','origin',BRANCH]);state.lastPushedAt=now();delete state.publishError;}
  catch(e){state.publishError=String(e);}atomic(resolve(DIR,'state.json'),state);
}
async function runSeed(job,seed,old,m,pool,shouldStop){
  for(const wallLimit of m.policy.wallTimeoutSteps){const startedAt=now(),start=performance.now();
    const message=await pool.run(payload(job,seed),wallLimit),wallSeconds=(performance.now()-start)/1000;
    if(message.result&&['win','draw'].includes(message.result.outcome)){
      const r=message.result,row={campaignHash:m.campaignHash,physicsVersion:m.physicsVersion,
        compatibilityCertificateHash:m.compatibilityCertificateHash,matchupId:job.id,pairKey:job.pairKey,seed,
        counts:job.counts,profileHashes:job.profileHashes,scenarioHash:job.scenarioHash,startedAt,finishedAt:now(),wallSeconds,
        outcome:r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss',winnerOwner:r.winnerOwner,
        unitCount:job.counts[0],opponentCount:job.counts[1],unitStartingHp:r.startingHpByOwner[2],opponentStartingHp:r.startingHpByOwner[3],
        unitRemainingHp:r.remainingByOwner[2]?.hp??0,opponentRemainingHp:r.remainingByOwner[3]?.hp??0,
        unitSurvivors:r.remainingByOwner[2]?.units??0,opponentSurvivors:r.remainingByOwner[3]?.units??0,
        ticks:r.ticks,simulationSeconds:r.ticks/60,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,
        v3Comparison:old?{sourceReference:old.ref,sourceCampaignHash:old.row.campaignHash,
          exact:old.row.outcome===(r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss')
            &&old.row.finalStateHash===r.finalStateHash&&old.row.eventLogHash===r.eventLogHash}:null};
      validateRecord(row,job,m.campaignHash);append(resolve(DIR,'runs.jsonl'),row);
      console.log(JSON.stringify({saved:`${job.id}:${seed}`,outcome:row.outcome,wallSeconds,gameSeconds:row.simulationSeconds}));return true;
    }
    append(resolve(DIR,'attempts.jsonl'),{at:now(),matchupId:job.id,seed,wallLimit,wallSeconds,
      watchdog:message.watchdog??false,error:message.error??null,lastProgress:message.lastProgress??null});
    if(shouldStop())break;
  }
  return false;
}
async function main(){assert.equal(command('git',['branch','--show-current']),BRANCH);mkdirSync(DIR,{recursive:true});
  const lock=resolve(DIR,'.runner.lock');if(existsSync(lock)){assert(!live(Number(readFileSync(lock,'utf8'))),'parallel runner already live');unlinkSync(lock);}
  writeFileSync(lock,String(process.pid),{flag:'wx'});let pool,stop=false;const signal=()=>{stop=true;};process.on('SIGTERM',signal);process.on('SIGINT',signal);
  try{assertBulkPaused();const m=prepare();verify(m);const jobs=load(resolve(DIR,'jobs.json')),statePath=resolve(DIR,'state.json');
    const state=existsSync(statePath)?load(statePath):{createdAt:now(),failedKeys:[],reviewedPairs:{}};
    state.status='running';state.pid=process.pid;state.campaignHash=m.campaignHash;
    if(process.argv.includes('--prepare-only')){state.status='prepared';state.pid=null;checkpoint(state,'prepared');return;}
    if(process.argv.includes('--retry-failed'))state.failedKeys=[];
    pool=new RankingWorkerPool(4,{workerUrl:new URL('../collision-validation-worker.mjs',import.meta.url),maxTicks:m.policy.maxTicks});
    const active=new Map();checkpoint(state,'started');
    while(true){verify(m);const evidence=sources(jobs,m),{records,legacy,held,mainRunning}=evidence;
      const pending=jobs.flatMap(job=>remainingSeeds(records.get(job.id),legacy.get(job.id).keys()).map(seed=>({job,seed})));
      const slots=workerBudget(mainRunning,held,m.policy);
      state.savedSeeds=rows(resolve(DIR,'runs.jsonl'),true).length;state.missingSeeds=pending.length;
      state.allowedWorkers=slots;state.waitingPriorKey=held;state.completedPairs=jobs.length-new Set(pending.map(x=>x.job.id)).size;
      state.active=[...active.keys()];state.updatedAt=now();atomic(statePath,state);
      for(const {job,seed,key} of dispatchable(pending,new Set(active.keys()),held,state.failedKeys,stop?0:slots)){
        active.set(key,runSeed(job,seed,legacy.get(job.id).get(seed),m,pool,()=>stop).then(ok=>({key,ok})));
      }
      state.active=[...active.keys()];atomic(statePath,state);
      if(active.size){const result=await Promise.race(active.values());active.delete(result.key);
        if(!result.ok&&!stop)state.failedKeys.push(result.key);
        state.savedSeeds=rows(resolve(DIR,'runs.jsonl'),true).length;state.active=[...active.keys()];checkpoint(state,result.key);continue;}
      if(stop){state.status='paused';break;}
      // Do not spend workers repeating all seeds. One exact replay per complete
      // repaired pair checks output provenance; choose its cheapest saved seed.
      for(const job of jobs){const set=records.get(job.id);if(remainingSeeds(set,legacy.get(job.id).keys()).length)continue;
        const references=[...set.values()].sort((a,b)=>a.seed-b.seed).map(r=>({seed:r.seed,campaignHash:r.campaignHash,
          outcome:r.outcome,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,sourceReference:r.sourceReference}));
        const inputHash=digest(references);if(state.reviewedPairs[job.id]?.inputHash===inputHash)continue;
        const row=[...set.values()].sort((a,b)=>a.wallSeconds-b.wallSeconds||a.seed-b.seed)[0];
        const message=await pool.run(payload(job,row.seed),Math.max(600,Math.min(7200,row.wallSeconds*2+120)));
        assert(message.result?.finalStateHash===row.finalStateHash&&message.result?.eventLogHash===row.eventLogHash,`exact replay failed ${job.id}:${row.seed}`);
        const review={at:now(),pairKey:job.pairKey,matchupId:job.id,physicsVersion:m.physicsVersion,
          profileHashes:job.profileHashes,counts:job.counts,scenarioHash:job.scenarioHash,inputHash,
          outcome:decision(set,legacy.get(job.id).keys()),seedReferences:references,exactReplay:{seed:row.seed,passed:true},
          compatibilityCertificateHash:m.compatibilityCertificateHash};
        append(resolve(DIR,'pair-reviews.jsonl'),review);state.reviewedPairs[job.id]=review;checkpoint(state,`review ${job.id}`);
      }
      state.status=pending.length?(state.failedKeys.length?'blocked':'waiting_prior_handoff'):'complete';break;
    }
    state.pid=null;state.active=[];checkpoint(state,state.status);
  }catch(error){const p=resolve(DIR,'state.json'),state=existsSync(p)?load(p):{};
    state.status='failed';state.pid=null;state.failure={at:now(),message:String(error)};atomic(p,state);throw error;
  }finally{await pool?.close();unlinkSync(lock);process.off('SIGTERM',signal);process.off('SIGINT',signal);}
}
await main();
