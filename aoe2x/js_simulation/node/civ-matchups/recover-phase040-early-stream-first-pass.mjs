#!/usr/bin/env node
// Targeted candidate-physics measurements; never compatible V2/V3 evidence.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,existsSync,mkdirSync,openSync,closeSync,
  appendFileSync,fsyncSync,renameSync,unlinkSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {gunzipSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';

const SIM=resolve(import.meta.dirname,'../..'),ROOT=resolve(SIM,'../..');
const NAME='civ-matchups-phase040-early-stream-first-pass-2026-11-02';
const DIR=resolve(SIM,'calibration/campaigns',NAME);
const BRANCH='simulations/civ-matchups-phase040-early-stream-2026-11-02';
const PHYSICS='collision-repair-v2-static-memo-event-stream-candidate-v1';
const SOURCE='/workspace/aoe2_path_recovery/aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31/adaptive';
const IDS=['cm_313d7b3bb1a75fbc0a90e70f'];
const FROZEN_PATH=resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json');
const CERT_PATH=resolve(SIM,'calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json');
const CANDIDATE_PATH=resolve(SIM,'calibration/reports/civ-event-stream-2026-11-02/CANDIDATE.json');
const load=p=>JSON.parse(readFileSync(p,'utf8'));
const sha=s=>createHash('sha256').update(s).digest('hex');
const now=()=>new Date().toISOString();
const FROZEN=load(FROZEN_PATH);
function live(pid){try{return !/^State:\s*Z/m.test(readFileSync(`/proc/${Number(pid)}/status`,'utf8'));}
  catch(e){if(e.code==='ENOENT')return false;throw e;}}
function atomic(p,value){const tmp=p+'.tmp',fd=openSync(tmp,'w');
  try{writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}renameSync(tmp,p);}
function append(p,value){const fd=openSync(p,'a');try{appendFileSync(fd,JSON.stringify(value)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
function command(args){const env={...process.env};if(args[0]==='push')delete env.GH_TOKEN;
  return execFileSync('git',args[0]==='push'?['-c','http.extraHeader=','-c','credential.helper=',...args]:args,
    {cwd:ROOT,env,encoding:'utf8',stdio:['ignore','pipe','inherit']}).trim();}
function rows(p){if(!existsSync(p))return[];const raw=readFileSync(p,'utf8');
  assert(!raw||raw.endsWith('\n'),'partial own journal');
  return raw.trim()?raw.trimEnd().split('\n').map((s,i)=>({record:JSON.parse(s),
    sourceReference:{path:p,line:i+1,recordSha256:sha(s)}})):[];}
function checkpoint(state,label){state.updatedAt=now();atomic(resolve(DIR,'state.json'),state);
  const prefix=relative(ROOT,DIR);
  assert(command(['diff','--cached','--name-only']).split('\n').every(x=>!x||x.startsWith(prefix+'/')),'unrelated staged work');
  const files=['manifest.json','jobs.json','state.json','runs.jsonl','attempts.jsonl','pair-reviews.jsonl']
    .map(f=>resolve(DIR,f)).filter(existsSync).map(f=>relative(ROOT,f));
  for(const n of ['runs.jsonl','attempts.jsonl'])for(const {record} of rows(resolve(DIR,n)))if(record.progressPath&&existsSync(record.progressPath))files.push(relative(ROOT,record.progressPath));
  command(['add','-f','--',...new Set(files)]);
  if(command(['diff','--cached','--name-only']))command(['commit','-m',`Checkpoint targeted event stream recovery: ${label}`]);
  try{command(['push','origin',BRANCH]);state.lastPushedAt=now();delete state.publishError;}
  catch(e){state.publishError=String(e);}atomic(resolve(DIR,'state.json'),state);}
function prepare(){const path=resolve(DIR,'manifest.json');if(existsSync(path))return load(path);
  const source=load(resolve(SOURCE,'manifest.json')),cert=load(CERT_PATH),candidate=load(CANDIDATE_PATH);
  const inventory=readFileSync(resolve(SOURCE,source.matchupInventory.file));
  assert.equal(sha(inventory),source.matchupInventory.sha256);
  const plan=load(resolve(SOURCE,'phases/040.json'));
  const failurePath=resolve(SOURCE,'attempts.jsonl');
  const failures=readFileSync(failurePath,'utf8').trimEnd().split('\n').map((text,i)=>({text,record:JSON.parse(text),line:i+1}));
  const sourceFailureReferences=IDS.map(id=>{
    const row=failures.findLast(r=>r.record.matchupId===id&&r.record.seed===0&&r.record.attempt===4
      &&r.record.error?.name==='RangeError'&&r.record.error?.message==='Invalid string length');
    assert(row,'only an exhausted final event-hash failure authorizes this inventory');
    return {path:failurePath,line:row.line,recordSha256:sha(row.text),matchupId:id,seed:0};
  });
  const jobs=gunzipSync(inventory).toString('utf8').trim().split('\n').map(JSON.parse).filter(j=>IDS.includes(j.id));
  assert.equal(jobs.length,IDS.length);assert(jobs.every(j=>plan.pairKeys.includes(j.pairKey)));
  atomic(resolve(DIR,'jobs.json'),jobs);
  const runtimeFiles=[...cert.sharedRuntimeFiles,...cert.changedOutputFiles].map(f=>({
    path:f.path,sha256:sha(readFileSync(resolve(ROOT,f.path))),parentV2StreamSha256:f.streamSha256}));
  const changed=runtimeFiles.filter(f=>f.sha256!==f.parentV2StreamSha256);
  assert.deepEqual(changed.map(f=>f.path).sort(),['src/canonical-json.js','src/fight.js','src/combat/world.js','src/combat/collision.js'].map(p=>'aoe2x/js_simulation/'+p).sort());
  assert.deepEqual(changed.map(f=>[f.path,f.sha256]).sort(),candidate.changedRuntimeFiles.map(f=>[f.path,f.candidateSha256]).sort());
  const body={schemaVersion:1,name:NAME,createdAt:now(),physicsVersion:PHYSICS,
    sourceCommit:command(['rev-parse','HEAD']),nodeVersion:process.version,
    sourceInventoryCampaignHash:source.campaignHash,sourceJobsSha256:sha(inventory),sourcePhasePlanReference:{path:resolve(SOURCE,'phases/040.json'),sha256:sha(readFileSync(resolve(SOURCE,'phases/040.json')))},sourceFailureReferences,
    jobsSha256:sha(readFileSync(resolve(DIR,'jobs.json'))),frozenInputsSha256:sha(readFileSync(FROZEN_PATH)),
    parentCertificateSha256:sha(readFileSync(CERT_PATH)),candidateSha256:sha(readFileSync(CANDIDATE_PATH)),
    runtimeFiles,orchestrationFiles:['node/civ-matchups/recover-phase040-early-stream-first-pass.mjs',
      'node/ranking-worker-pool.mjs','node/event-stream-recovery-worker.mjs'].map(p=>({path:p,sha256:sha(readFileSync(resolve(SIM,p)))})),
    simulationEnvironment:cert.simulationEnvironment,compatibleSourceCampaigns:[],
    policy:{workers:2,initialSeeds:[0,1,2],extraSeedsOnDisagreement:[3,4,5,6,7,8,9],
      wallTimeoutSteps:[7200],maxTicks:Number.MAX_SAFE_INTEGER},
    fidelityStatus:'collision_repair_forest_pocket_fidelity_unvalidated_exact_memoization_controls_passed',
    scope:'Only the phase040 Aztec Skirmisher/Lithuanian Hussar hard gap after seed0 exhausted all V3 retries with a final event-hash error. Phase040 may continue separately. Every required native seed is recomputed; no old outcomes imported. Unvalidated first-pass cross-engine projection only; no new physics or bulk replay.'};
  const m={...body,campaignHash:digest(body)};atomic(path,m);return m;}
function verify(m){const {campaignHash,...body}=m;assert.equal(digest(body),campaignHash);
  assert.equal(sha(readFileSync(m.sourcePhasePlanReference.path)),m.sourcePhasePlanReference.sha256);
  for(const ref of m.sourceFailureReferences){
    const text=readFileSync(ref.path,'utf8').split('\n')[ref.line-1];assert.equal(sha(text),ref.recordSha256);
    const r=JSON.parse(text);assert.equal(r.matchupId,ref.matchupId);assert.equal(r.seed,ref.seed);
    assert.equal(r.attempt,4);assert.equal(r.error?.name,'RangeError');assert.equal(r.error?.message,'Invalid string length');
  }
  assert.equal(m.physicsVersion,PHYSICS);assert.equal(m.nodeVersion,process.version);
  for(const [p,key] of [[FROZEN_PATH,'frozenInputsSha256'],[CERT_PATH,'parentCertificateSha256'],[CANDIDATE_PATH,'candidateSha256'],[resolve(DIR,'jobs.json'),'jobsSha256']])
    assert.equal(sha(readFileSync(p)),m[key]);
  for(const f of m.runtimeFiles)assert.equal(sha(readFileSync(resolve(ROOT,f.path))),f.sha256);
  for(const f of m.orchestrationFiles)assert.equal(sha(readFileSync(resolve(SIM,f.path))),f.sha256);
  assert.deepEqual(Object.fromEntries(Object.keys(process.env).filter(k=>k.startsWith('AOE2X_EXP_')).sort().map(k=>[k,process.env[k]])),m.simulationEnvironment);}
function saved(job,m){const result=new Map();for(const item of rows(resolve(DIR,'runs.jsonl'))){const r=item.record;
  assert.equal(r.campaignHash,m.campaignHash);assert.equal(r.physicsVersion,PHYSICS);
  if(r.matchupId!==job.id)continue;
  assert.equal(r.pairKey,job.pairKey);assert.deepEqual(r.counts,job.counts);assert.deepEqual(r.profileHashes,job.profileHashes);
  assert.equal(r.scenarioHash,job.scenarioHash);assert(['win','loss','draw'].includes(r.outcome));
  assert(Number.isSafeInteger(r.seed)&&r.seed>=0&&r.seed<10);assert(!result.has(r.seed),'duplicate seed');
  result.set(r.seed,{...item,sourceReference:{...item.sourceReference,campaignHash:m.campaignHash}});}
  return result;}
function required(records){const seeds=[0,1,2];if(seeds.every(s=>records.has(s))&&new Set(seeds.map(s=>records.get(s).record.outcome)).size>1)
  seeds.push(3,4,5,6,7,8,9);return seeds;}
function payload(job,seed){const scenario=FROZEN.scenarios[job.scenarioHash];assert(scenario);assert.equal(digest(scenario),job.scenarioHash);
  return {jobId:job.id,seed,teams:job.teamKeys.map((key,i)=>({mechanics:FROZEN.profiles[key].mechanics,count:job.counts[i]})),
    scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false};}
async function main(){assert.equal(command(['branch','--show-current']),BRANCH);mkdirSync(DIR,{recursive:true});
  const lock=resolve(DIR,'.runner.lock');if(existsSync(lock)){assert(!live(readFileSync(lock,'utf8')),'event stream recovery already live');unlinkSync(lock);}
  writeFileSync(lock,String(process.pid),{flag:'wx'});let pool,stop=false;const stopping=()=>{stop=true;};
  process.on('SIGTERM',stopping);process.on('SIGINT',stopping);
  const statePath=resolve(DIR,'state.json');let state=existsSync(statePath)?load(statePath):{createdAt:now(),failedKeys:[],reviewedPairs:{}};
  try{const m=prepare();verify(m);const jobs=load(resolve(DIR,'jobs.json'));
    state={...state,pid:process.pid,status:'running',active:[],campaignHash:m.campaignHash};
    if(process.argv.includes('--prepare-only')){state.pid=null;state.status='prepared';checkpoint(state,'prepared');return;}
    if(process.argv.includes('--retry-failed'))state.failedKeys=[];
    pool=new RankingWorkerPool(2,{workerUrl:new URL('../event-stream-recovery-worker.mjs',import.meta.url),maxTicks:m.policy.maxTicks});
    checkpoint(state,'started');
    const runOne=async(job)=>{
      let records=saved(job,m);
      for(;;){verify(m);const seed=required(records).find(s=>!records.has(s)&&!state.failedKeys.includes(`${job.id}:${s}`));
        if(seed===undefined||stop)break;
        const key=`${job.id}:${seed}`;const sourceState=load(resolve(SOURCE,'state.json'));
        assert(m.sourceFailureReferences.some(r=>r.matchupId===job.id),'job requires an exhausted source error');
        assert(!live(sourceState.pid)||!sourceState.active?.includes(key),'original recovery is executing this seed');
        state.active.push(key);atomic(statePath,state);let ok=false;
        for(const wallLimit of m.policy.wallTimeoutSteps){const startedAt=now(),start=performance.now();
          const progressDir=resolve(DIR,'progress');mkdirSync(progressDir,{recursive:true});
          const progressPath=resolve(progressDir,`${job.id}-${seed}-${Date.now()}.jsonl`);
          const message=await pool.run({...payload(job,seed),diagnosticProgressPath:progressPath},wallLimit),wallSeconds=(performance.now()-start)/1000,r=message.result;
          if(r&&['win','draw'].includes(r.outcome)){
            append(resolve(DIR,'runs.jsonl'),{campaignHash:m.campaignHash,physicsVersion:PHYSICS,
              matchupId:job.id,pairKey:job.pairKey,seed,counts:job.counts,profileHashes:job.profileHashes,
              scenarioHash:job.scenarioHash,startedAt,finishedAt:now(),wallSeconds,progressPath,
              outcome:r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss',winnerOwner:r.winnerOwner,
              ticks:r.ticks,simulationSeconds:r.ticks/60,startingHpByOwner:r.startingHpByOwner,remainingByOwner:r.remainingByOwner,
              finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash});ok=true;break;}
          append(resolve(DIR,'attempts.jsonl'),{at:now(),matchupId:job.id,seed,wallLimit,wallSeconds,progressPath,
            watchdog:message.watchdog??false,error:message.error??null,lastProgress:message.lastProgress??null});
          if(stop)break;}
        if(!ok&&!stop)state.failedKeys.push(key);state.active=state.active.filter(x=>x!==key);records=saved(job,m);checkpoint(state,key);
      }
      if(stop)return;
      if(required(records).some(s=>!records.has(s)))return;
      const references=[...records.values()].sort((a,b)=>a.record.seed-b.record.seed).map(({record:r,sourceReference})=>({
        seed:r.seed,campaignHash:r.campaignHash,outcome:r.outcome,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,sourceReference}));
      const inputHash=digest(references);if(state.reviewedPairs[job.id]?.inputHash===inputHash)return;
      const r=[...records.values()].map(i=>i.record).sort((a,b)=>a.wallSeconds-b.wallSeconds)[0];
      const reviewKey=`review:${job.id}:${r.seed}`;state.active.push(reviewKey);atomic(statePath,state);
      const message=await pool.run(payload(job,r.seed),Math.max(600,r.wallSeconds*2+120));
      assert.equal(message.result?.finalStateHash,r.finalStateHash,'exact replay state mismatch');
      assert.equal(message.result?.eventLogHash,r.eventLogHash,'exact replay events mismatch');
      assert.equal(message.result?.winnerOwner,r.winnerOwner,'exact replay winner mismatch');
      assert.equal(message.result?.ticks,r.ticks,'exact replay duration mismatch');
      const outcomes=new Set([...records.values()].map(i=>i.record.outcome));
      const review={at:now(),matchupId:job.id,pairKey:job.pairKey,physicsVersion:PHYSICS,profileHashes:job.profileHashes,
        counts:job.counts,scenarioHash:job.scenarioHash,inputHash,seedReferences:references,
        outcome:outcomes.size===1&&!outcomes.has('draw')?[...outcomes][0]:'close_uncertain',exactReplay:{seed:r.seed,passed:true},
        fidelityStatus:m.fidelityStatus};
      append(resolve(DIR,'pair-reviews.jsonl'),review);state.reviewedPairs[job.id]=review;state.active=state.active.filter(x=>x!==reviewKey);checkpoint(state,`review ${job.id}`);
    };
    await Promise.all(jobs.map(runOne));
    state.status=stop?'paused':Object.keys(state.reviewedPairs).length===jobs.length?'complete':'blocked';state.pid=null;state.active=[];
    state.savedSeeds=rows(resolve(DIR,'runs.jsonl')).length;checkpoint(state,state.status);
  }catch(e){state.status='failed';state.pid=null;state.failure={at:now(),message:String(e)};atomic(statePath,state);throw e;}
  finally{await pool?.close();unlinkSync(lock);process.off('SIGTERM',stopping);process.off('SIGINT',stopping);}}
await main();
