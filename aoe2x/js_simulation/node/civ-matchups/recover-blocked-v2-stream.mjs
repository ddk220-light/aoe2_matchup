#!/usr/bin/env node
// Separate repaired-engine campaign. Never writes to V3 or replay journals.
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
import {remainingSeeds, validateRecord, decision} from './stream-recovery-policy.mjs';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const ROOT=resolve(SIM,'../..');
const NAME='civ-matchups-blocked-v2-stream-2026-11-01';
const DIR=resolve(SIM,'calibration/campaigns',NAME);
const SOURCE_ROOT='/workspace/aoe2_path_recovery';
const SOURCE=resolve(SOURCE_ROOT,'aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31');
const REPLAY=resolve('/workspace/aoe2_civ_collision_repair/aoe2x/js_simulation/calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31');
const CERT=resolve(SIM,'calibration/campaigns/civ-matchups-v2-stream-compatibility-2026-11-01/manifest.json');
const FROZEN_PATH=resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json');
const FROZEN=JSON.parse(readFileSync(FROZEN_PATH));
const BRANCH='simulations/civ-matchups-stream-hash-2026-10-31';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const load=path=>JSON.parse(readFileSync(path,'utf8'));
const now=()=>new Date().toISOString();
function atomic(path,value){const tmp=path+'.tmp',fd=openSync(tmp,'w');
  try{writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}renameSync(tmp,path);}
function append(path,row){const fd=openSync(path,'a');
  try{appendFileSync(fd,JSON.stringify(row)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
function lines(path, own=false){if(!existsSync(path))return[];
  const text=readFileSync(path,'utf8');
  // Incomplete external tails can be an in-flight append. An incomplete own
  // journal requires explicit repair; never append beyond a damaged line.
  if(own)assert(!text||text.endsWith('\n'),'partial recovery journal tail');
  const rows=text.split('\n');rows.pop();return rows.filter(Boolean).map(JSON.parse);}
function command(program,args){const env={...process.env};
  const pushing=program==='git'&&args[0]==='push';if(pushing)delete env.GH_TOKEN;
  return execFileSync(program,pushing?['-c','http.extraHeader=','-c','credential.helper=',...args]:args,
    {cwd:ROOT,env,encoding:'utf8',stdio:['ignore','pipe','inherit']}).trim();}
function live(pid){try{return !/^State:\s*Z/m.test(readFileSync(`/proc/${pid}/status`,'utf8'));}
  catch(e){if(e.code==='ENOENT')return false;throw e;}}
function verifySource(manifest){
  const {campaignHash,...body}=manifest;assert.equal(digest(body),campaignHash);
  assert.equal(process.version,manifest.nodeVersion);
  assert.equal(sha(readFileSync(CERT)),manifest.compatibilityCertificateSha256);
  assert.equal(sha(readFileSync(FROZEN_PATH)),manifest.frozenInputsSha256);
  assert.equal(sha(readFileSync(resolve(DIR,'jobs.json'))),manifest.jobsSha256);
  assert.equal(sha(readFileSync(resolve(DIR,'source-state.json'))),manifest.sourceStateSha256);
  for(const f of manifest.runtimeFiles)assert.equal(sha(readFileSync(resolve(ROOT,f.path))),f.sha256,`source changed: ${f.path}`);
  for(const f of manifest.orchestrationFiles)assert.equal(sha(readFileSync(resolve(SIM,f.path))),f.sha256,`orchestration changed: ${f.path}`);
  const env=Object.fromEntries(Object.keys(process.env).filter(k=>k.startsWith('AOE2X_EXP_')).sort().map(k=>[k,process.env[k]]));
  assert.deepEqual(env,manifest.simulationEnvironment);
}
function prepare(){
  const path=resolve(DIR,'manifest.json');if(existsSync(path))return load(path);
  const state=load(resolve(SOURCE,'adaptive/state.json'));
  const adaptive=load(resolve(SOURCE,'adaptive/manifest.json'));
  const bytes=readFileSync(resolve(SOURCE,'adaptive/inventory.jsonl.gz'));
  assert.equal(sha(bytes),adaptive.matchupInventory.sha256);
  const all=gunzipSync(bytes).toString('utf8').trim().split('\n').map(JSON.parse);
  const jobs=all.filter(j=>state.blockedPairs.includes(j.pairKey));
  assert.equal(jobs.length,state.blockedPairs.length);
  if(state.activePhase){const active=load(resolve(SOURCE,'adaptive/phases',state.activePhase+'.json'));
    assert(jobs.every(j=>!active.pairKeys.includes(j.pairKey)),'blocked job is still active in V3');}
  jobs.sort((a,b)=>(a.family==='ranged_vs_ranged'?-1:1)-(b.family==='ranged_vs_ranged'?-1:1)||a.id.localeCompare(b.id));
  atomic(resolve(DIR,'source-state.json'),state);atomic(resolve(DIR,'jobs.json'),jobs);
  const cert=load(CERT),runtimeFiles=[...cert.sharedRuntimeFiles,...cert.changedOutputFiles]
    .map(x=>({path:x.path,sha256:x.streamSha256}));
  const replayManifest=load(resolve(REPLAY,'manifest.json'));
  assert.equal(replayManifest.campaignHash,cert.v2CampaignHash);
  const body={schemaVersion:1,name:NAME,createdAt:now(),sourceCommit:command('git',['rev-parse','HEAD']),
    nodeVersion:process.version,physicsVersion:'collision-repair-v2',
    compatibilityCertificateSha256:sha(readFileSync(CERT)),compatibilityCertificateHash:cert.campaignHash,
    compatibleReplayCampaignHash:cert.v2CampaignHash,frozenInputsSha256:sha(readFileSync(FROZEN_PATH)),
    sourceAdaptiveCampaignHash:adaptive.campaignHash,sourceInventorySha256:sha(bytes),
    sourceStateSha256:sha(readFileSync(resolve(DIR,'source-state.json'))),
    jobsSha256:sha(readFileSync(resolve(DIR,'jobs.json'))),jobs:jobs.length,
    runtimeFiles,simulationEnvironment:cert.simulationEnvironment,
    orchestrationFiles:['node/civ-matchups/recover-blocked-v2-stream.mjs','node/civ-matchups/stream-recovery-policy.mjs',
      'node/collision-validation-worker.mjs','node/ranking-worker-pool.mjs'].map(p=>({path:p,sha256:sha(readFileSync(resolve(SIM,p)))})),
    policy:{workers:1,initialSeeds:[0,1,2],extraSeedsOnDisagreement:[3,4,5,6,7,8,9],
      wallTimeoutSteps:[3600,7200],maxTicks:Number.MAX_SAFE_INTEGER},publishBranch:BRANCH,
    scope:'Only missing seeds for frozen blocked pairs; eligible V3 seeds belong to the separate V2 replay runner. No V3 or diagnostic outcomes are measurements here.'};
  const manifest={...body,campaignHash:digest(body)};atomic(path,manifest);return manifest;
}
function payload(job,seed){let scenario=FROZEN.scenarios[job.scenarioHash];
  if(!scenario)scenario={...Object.values(FROZEN.scenarios).find(x=>x.family===job.family),engineFamily:job.engineFamily};
  assert.equal(digest(scenario),job.scenarioHash);
  return {jobId:job.id,seed,teams:job.teamKeys.map((k,i)=>({mechanics:FROZEN.profiles[k].mechanics,count:job.counts[i]})),
    scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false};}
function evidence(jobs,manifest){
  const byId=new Map(jobs.map(j=>[j.id,j]));
  const records=new Map(jobs.map(j=>[j.id,new Map()]));
  const reserved=new Map(jobs.map(j=>[j.id,new Set()]));
  for(const area of ['pilot','adaptive']){
    const sourceManifest=load(resolve(SOURCE,area,'manifest.json'));
    for(const name of readdirSync(resolve(SOURCE,area,'runs')).filter(x=>x.endsWith('.jsonl')))
      for(const row of lines(resolve(SOURCE,area,'runs',name))){const job=byId.get(row.matchupId);if(!job)continue;
        assert.equal(row.campaignHash,sourceManifest.campaignHash);
        assert(['win','loss','draw'].includes(row.outcome)&&!row.error);
        assert.deepEqual([row.unitCount,row.opponentCount],job.counts);
        reserved.get(job.id).add(row.seed);
      }
  }
  const add=(row,hash,source)=>{const job=byId.get(row.matchupId);if(!job)return;
    validateRecord(row,job,hash);const map=records.get(job.id);
    assert(!map.has(row.seed),`duplicate repaired seed ${job.id}:${row.seed}`);
    map.set(row.seed,{...row,evidenceSource:source});};
  for(const row of lines(resolve(REPLAY,'replays.jsonl')))add(row,manifest.compatibleReplayCampaignHash,'v2-replay');
  for(const row of lines(resolve(DIR,'runs.jsonl'),true))add(row,manifest.campaignHash,'v2-stream-recovery');
  return {records,reserved};
}
function checkpoint(state,label){state.updatedAt=now();atomic(resolve(DIR,'state.json'),state);
  const prefix=relative(ROOT,DIR);const staged=command('git',['diff','--cached','--name-only']);
  assert(staged.split('\n').every(x=>!x||x.startsWith(prefix+'/')),'unrelated staged changes');
  const files=['manifest.json','jobs.json','source-state.json','state.json','runs.jsonl','attempts.jsonl']
    .map(name=>resolve(DIR,name)).filter(existsSync).map(path=>relative(ROOT,path));
  command('git',['add','--',...files]);
  if(command('git',['diff','--cached','--name-only']))command('git',['commit','-m',`Checkpoint blocked V2 stream recovery: ${label}`]);
  try{command('git',['push','origin',BRANCH]);state.lastPushedAt=now();delete state.publishError;}
  catch(e){state.publishError=String(e);}
  atomic(resolve(DIR,'state.json'),state);
}
async function main(){
  assert.equal(command('git',['branch','--show-current']),BRANCH);mkdirSync(DIR,{recursive:true});
  const lock=resolve(DIR,'.runner.lock');
  if(existsSync(lock)){const pid=Number(readFileSync(lock,'utf8'));assert(!live(pid),`recovery runner already active: ${pid}`);unlinkSync(lock);}
  writeFileSync(lock,String(process.pid),{flag:'wx'});
  let pool,stop=false;const signal=()=>{stop=true;};process.on('SIGTERM',signal);process.on('SIGINT',signal);
  try{
    command('node',['aoe2x/js_simulation/node/civ-matchups/certify-v2-stream-compatibility.mjs','--verify']);
    const manifest=prepare();verifySource(manifest);
    const jobs=load(resolve(DIR,'jobs.json'));assert.equal(jobs.length,manifest.jobs);
    const statePath=resolve(DIR,'state.json');const state=existsSync(statePath)?load(statePath):{createdAt:now(),failedKeys:[],reviews:{}};
    state.status='running';state.pid=process.pid;state.campaignHash=manifest.campaignHash;
    if(process.argv.includes('--prepare-only')){state.status='prepared';state.pid=null;checkpoint(state,'prepared');return;}
    if(process.argv.includes('--retry-failed'))state.failedKeys=[];
    pool=new RankingWorkerPool(1,{workerUrl:new URL('../collision-validation-worker.mjs',import.meta.url),maxTicks:manifest.policy.maxTicks});
    checkpoint(state,'started');
    while(!stop){
      verifySource(manifest);const {records,reserved}=evidence(jobs,manifest);
      const pending=jobs.flatMap(job=>remainingSeeds(records.get(job.id),reserved.get(job.id)).map(seed=>({job,seed})));
      state.savedSeeds=lines(resolve(DIR,'runs.jsonl'),true).length;
      state.missingSeeds=pending.length;state.completedPairs=jobs.filter(j=>!remainingSeeds(records.get(j.id),reserved.get(j.id)).length).length;
      state.waitingForReplay=pending.filter(x=>reserved.get(x.job.id).has(x.seed)).length;
      const next=pending.find(x=>!reserved.get(x.job.id).has(x.seed)&&!state.failedKeys.includes(`${x.job.id}:${x.seed}`));
      if(!next){
        // Exact replay one seed per completed pair, with its original hashes.
        for(const job of jobs){const rows=records.get(job.id);
          if(remainingSeeds(rows,reserved.get(job.id)).length)continue;
          const hashes=[...rows.values()].sort((a,b)=>a.seed-b.seed).map(r=>[r.seed,r.campaignHash,r.finalStateHash,r.eventLogHash]);
          const inputHash=digest(hashes);if(state.reviews[job.id]?.inputHash===inputHash)continue;
          const row=rows.get(0),message=await pool.run(payload(job,0),Math.max(600,Math.min(7200,row.wallSeconds*2+120)));
          assert(message.result?.finalStateHash===row.finalStateHash&&message.result?.eventLogHash===row.eventLogHash,`exact recovery replay failed: ${job.id}`);
          state.reviews[job.id]={at:now(),inputHash,seeds:hashes,outcome:decision(rows,reserved.get(job.id)),exactReplay:true};
          checkpoint(state,`reviewed ${job.id}`);
        }
        state.status=pending.length?(state.failedKeys.length?'blocked':'waiting_existing_v2_replays'):'complete';
        state.pid=null;checkpoint(state,state.status);break;
      }
      const {job,seed}=next,key=`${job.id}:${seed}`;state.active={matchupId:job.id,seed};atomic(statePath,state);
      let saved=false;
      for(const wallLimit of manifest.policy.wallTimeoutSteps){
        const startedAt=now(),start=performance.now(),message=await pool.run(payload(job,seed),wallLimit);
        const wallSeconds=(performance.now()-start)/1000;
        if(message.result&&['win','draw'].includes(message.result.outcome)){
          const r=message.result,row={campaignHash:manifest.campaignHash,physicsVersion:manifest.physicsVersion,
            compatibilityCertificateHash:manifest.compatibilityCertificateHash,matchupId:job.id,pairKey:job.pairKey,seed,
            counts:job.counts,profileHashes:job.profileHashes,scenarioHash:job.scenarioHash,startedAt,finishedAt:now(),wallSeconds,
            outcome:r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss',winnerOwner:r.winnerOwner,
            unitCount:job.counts[0],opponentCount:job.counts[1],unitStartingHp:r.startingHpByOwner[2],opponentStartingHp:r.startingHpByOwner[3],
            unitRemainingHp:r.remainingByOwner[2]?.hp??0,opponentRemainingHp:r.remainingByOwner[3]?.hp??0,
            unitSurvivors:r.remainingByOwner[2]?.units??0,opponentSurvivors:r.remainingByOwner[3]?.units??0,
            ticks:r.ticks,simulationSeconds:r.ticks/60,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash};
          validateRecord(row,job,manifest.campaignHash);append(resolve(DIR,'runs.jsonl'),row);saved=true;
          console.log(JSON.stringify({saved:key,outcome:row.outcome,wallSeconds,gameSeconds:row.simulationSeconds}));break;
        }
        append(resolve(DIR,'attempts.jsonl'),{at:now(),matchupId:job.id,seed,wallLimit,wallSeconds,
          watchdog:message.watchdog??false,error:message.error??null,lastProgress:message.lastProgress??null});
        if(stop)break;
      }
      if(!saved&&!stop)state.failedKeys.push(key);
      delete state.active;state.savedSeeds=lines(resolve(DIR,'runs.jsonl'),true).length;checkpoint(state,key);
    }
    if(stop){state.status='paused';state.pid=null;checkpoint(state,'paused');}
  }catch(error){const path=resolve(DIR,'state.json');const state=existsSync(path)?load(path):{};
    state.status='failed';state.pid=null;state.failure={at:now(),message:String(error)};atomic(path,state);throw error;
  }finally{await pool?.close();unlinkSync(lock);process.off('SIGTERM',signal);process.off('SIGINT',signal);}
}
await main();
