#!/usr/bin/env node
// Targeted candidate-physics measurements; never compatible V2/V3 evidence.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,existsSync,mkdirSync,openSync,closeSync,
  appendFileSync,fsyncSync,renameSync,unlinkSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {execFileSync} from 'node:child_process';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';

const SIM=resolve(import.meta.dirname,'../..'),ROOT=resolve(SIM,'../..');
const NAME='civ-matchups-patrol-first-pass-2026-11-01';
const DIR=resolve(SIM,'calibration/campaigns',NAME);
const BRANCH='simulations/civ-matchups-patrol-repair-2026-11-01';
const PHYSICS='collision-repair-v2-patrol-candidate-v1';
const SOURCE='/workspace/aoe2_civ_first_pass_parallel/aoe2x/js_simulation/calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01';
const IDS=['cm_6827d25d70a06f758cc82ff9','cm_d9a8fa39591693259171e783'];
const FROZEN_PATH=resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json');
const CERT_PATH=resolve(SIM,'calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json');
const CANDIDATE_PATH=resolve(SIM,'calibration/reports/civ-matchups-patrol-repair-2026-11-01/CANDIDATE.json');
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
  command(['add','-f','--',...files]);
  if(command(['diff','--cached','--name-only']))command(['commit','-m',`Checkpoint targeted patrol recovery: ${label}`]);
  try{command(['push','origin',BRANCH]);state.lastPushedAt=now();delete state.publishError;}
  catch(e){state.publishError=String(e);}atomic(resolve(DIR,'state.json'),state);}
function prepare(){const path=resolve(DIR,'manifest.json');if(existsSync(path))return load(path);
  const source=load(resolve(SOURCE,'manifest.json')),cert=load(CERT_PATH),candidate=load(CANDIDATE_PATH);
  const jobs=load(resolve(SOURCE,'jobs.json')).filter(j=>IDS.includes(j.id));assert.equal(jobs.length,IDS.length);
  atomic(resolve(DIR,'jobs.json'),jobs);
  const runtimeFiles=[...cert.sharedRuntimeFiles,...cert.changedOutputFiles].map(f=>({
    path:f.path,sha256:sha(readFileSync(resolve(ROOT,f.path))),parentV2StreamSha256:f.streamSha256}));
  const changed=runtimeFiles.filter(f=>f.sha256!==f.parentV2StreamSha256);
  assert.deepEqual(changed.map(f=>f.path),['aoe2x/js_simulation/src/combat/world.js']);
  assert.equal(changed[0].sha256,candidate.changedPhysicsFiles[0].candidateSha256);
  const body={schemaVersion:1,name:NAME,createdAt:now(),physicsVersion:PHYSICS,
    sourceCommit:command(['rev-parse','HEAD']),nodeVersion:process.version,
    sourceInventoryCampaignHash:source.campaignHash,sourceJobsSha256:sha(readFileSync(resolve(SOURCE,'jobs.json'))),
    jobsSha256:sha(readFileSync(resolve(DIR,'jobs.json'))),frozenInputsSha256:sha(readFileSync(FROZEN_PATH)),
    parentCertificateSha256:sha(readFileSync(CERT_PATH)),candidateSha256:sha(readFileSync(CANDIDATE_PATH)),
    runtimeFiles,orchestrationFiles:['node/civ-matchups/recover-patrol-first-pass.mjs',
      'node/ranking-worker-pool.mjs','node/collision-validation-worker.mjs'].map(p=>({path:p,sha256:sha(readFileSync(resolve(SIM,p)))})),
    simulationEnvironment:cert.simulationEnvironment,compatibleSourceCampaigns:[],
    policy:{workers:1,initialSeeds:[0,1,2],extraSeedsOnDisagreement:[3,4,5,6,7,8,9],
      wallTimeoutSteps:[600,1800],maxTicks:Number.MAX_SAFE_INTEGER},
    fidelityStatus:'candidate_late_patrol_behavior_not_independently_game_validated',
    scope:'Only two diagnosed patrol endpoint pairs. All measurements recomputed here; no imported outcomes. First-pass use only as unvalidated cross-engine predictions, never V2 or V3 measurements.'};
  const m={...body,campaignHash:digest(body)};atomic(path,m);return m;}
function verify(m){const {campaignHash,...body}=m;assert.equal(digest(body),campaignHash);
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
  const lock=resolve(DIR,'.runner.lock');if(existsSync(lock)){assert(!live(readFileSync(lock,'utf8')),'patrol recovery already live');unlinkSync(lock);}
  writeFileSync(lock,String(process.pid),{flag:'wx'});let pool,stop=false;const stopping=()=>{stop=true;};
  process.on('SIGTERM',stopping);process.on('SIGINT',stopping);
  const statePath=resolve(DIR,'state.json');let state=existsSync(statePath)?load(statePath):{createdAt:now(),failedKeys:[],reviewedPairs:{}};
  try{const m=prepare();verify(m);const jobs=load(resolve(DIR,'jobs.json'));
    state={...state,pid:process.pid,status:'running',campaignHash:m.campaignHash};
    if(process.argv.includes('--prepare-only')){state.pid=null;state.status='prepared';checkpoint(state,'prepared');return;}
    if(process.argv.includes('--retry-failed'))state.failedKeys=[];
    pool=new RankingWorkerPool(1,{workerUrl:new URL('../collision-validation-worker.mjs',import.meta.url),maxTicks:m.policy.maxTicks});
    checkpoint(state,'started');
    for(const job of jobs){
      let records=saved(job,m);
      for(;;){verify(m);const seed=required(records).find(s=>!records.has(s)&&!state.failedKeys.includes(`${job.id}:${s}`));
        if(seed===undefined||stop)break;
        const key=`${job.id}:${seed}`;state.active=key;atomic(statePath,state);let ok=false;
        for(const wallLimit of m.policy.wallTimeoutSteps){const startedAt=now(),start=performance.now();
          const message=await pool.run(payload(job,seed),wallLimit),wallSeconds=(performance.now()-start)/1000,r=message.result;
          if(r&&['win','draw'].includes(r.outcome)){
            append(resolve(DIR,'runs.jsonl'),{campaignHash:m.campaignHash,physicsVersion:PHYSICS,
              matchupId:job.id,pairKey:job.pairKey,seed,counts:job.counts,profileHashes:job.profileHashes,
              scenarioHash:job.scenarioHash,startedAt,finishedAt:now(),wallSeconds,
              outcome:r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss',winnerOwner:r.winnerOwner,
              ticks:r.ticks,simulationSeconds:r.ticks/60,startingHpByOwner:r.startingHpByOwner,remainingByOwner:r.remainingByOwner,
              finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash});ok=true;break;}
          append(resolve(DIR,'attempts.jsonl'),{at:now(),matchupId:job.id,seed,wallLimit,wallSeconds,
            watchdog:message.watchdog??false,error:message.error??null,lastProgress:message.lastProgress??null});
          if(stop)break;}
        if(!ok&&!stop)state.failedKeys.push(key);state.active=null;records=saved(job,m);checkpoint(state,key);
      }
      if(stop)break;
      if(required(records).some(s=>!records.has(s)))continue;
      const references=[...records.values()].sort((a,b)=>a.record.seed-b.record.seed).map(({record:r,sourceReference})=>({
        seed:r.seed,campaignHash:r.campaignHash,outcome:r.outcome,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,sourceReference}));
      const inputHash=digest(references);if(state.reviewedPairs[job.id]?.inputHash===inputHash)continue;
      const r=[...records.values()].map(i=>i.record).sort((a,b)=>a.wallSeconds-b.wallSeconds)[0];
      state.active=`review:${job.id}:${r.seed}`;atomic(statePath,state);
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
      append(resolve(DIR,'pair-reviews.jsonl'),review);state.reviewedPairs[job.id]=review;state.active=null;checkpoint(state,`review ${job.id}`);
    }
    state.status=stop?'paused':Object.keys(state.reviewedPairs).length===jobs.length?'complete':'blocked';state.pid=null;state.active=null;
    state.savedSeeds=rows(resolve(DIR,'runs.jsonl')).length;checkpoint(state,state.status);
  }catch(e){state.status='failed';state.pid=null;state.failure={at:now(),message:String(e)};atomic(statePath,state);throw e;}
  finally{await pool?.close();unlinkSync(lock);process.off('SIGTERM',stopping);process.off('SIGINT',stopping);}}
await main();
