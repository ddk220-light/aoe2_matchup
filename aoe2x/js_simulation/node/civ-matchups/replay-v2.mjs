#!/usr/bin/env node
// Re-run valid V3 seeds under the isolated collision repair. Never copy outcomes.
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
const DIR=resolve(SIM,'calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31');
const SOURCE_ROOT=resolve(process.env.CIV_V3_WORKTREE??'/workspace/aoe2_path_recovery');
const SOURCE=resolve(SOURCE_ROOT,'aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31');
const FROZEN=JSON.parse(readFileSync(resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const json=path=>JSON.parse(readFileSync(path,'utf8'));
const now=()=>new Date().toISOString();
const limitIndex=process.argv.indexOf('--limit');
const limit=limitIndex<0?Infinity:Number(process.argv[limitIndex+1]);
assert(limit===Infinity||Number.isSafeInteger(limit)&&limit>0);
function atomic(path,value){const tmp=`${path}.tmp`,fd=openSync(tmp,'w');
  try{writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}renameSync(tmp,path);}
function append(path,value){const fd=openSync(path,'a');
  try{appendFileSync(fd,JSON.stringify(value)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
function lines(path){if(!existsSync(path))return[];const raw=readFileSync(path,'utf8');
  const parts=raw.split('\n');if(!raw.endsWith('\n'))parts.pop();return parts.filter(Boolean).map(JSON.parse);}
function sourceLines(path){if(!existsSync(path))return[];const raw=readFileSync(path,'utf8');
  const parts=raw.split('\n');if(!raw.endsWith('\n'))parts.pop();
  return parts.map((text,index)=>({text,line:index+1})).filter(x=>x.text);}
function command(program,args){const env={...process.env};delete env.GH_TOKEN;
  return execFileSync(program,program==='git'&&args[0]==='push'
    ?['-c','http.extraHeader=','-c','credential.helper=',...args]:args,
  {cwd:ROOT,env,encoding:'utf8',stdio:['ignore','pipe','inherit']}).trim();}
function scenario(job){
  if(FROZEN.scenarios[job.scenarioHash])return FROZEN.scenarios[job.scenarioHash];
  const base=Object.values(FROZEN.scenarios).find(x=>x.family===job.family);
  assert(base,job.family);const result={...base,engineFamily:job.engineFamily};
  assert.equal(digest(result),job.scenarioHash);return result;
}
function payload(job,seed){return {jobId:job.id,seed,
  teams:job.teamKeys.map((key,i)=>({mechanics:FROZEN.profiles[key].mechanics,count:job.counts[i]})),
  scenario:scenario(job),disableAiOrders:true,disableKiting:true,
  preserveOwnerOrientation:true,retainSnapshots:false};}
function sources(){
  const pilot=json(resolve(SOURCE,'pilot/manifest.json'));
  const adaptive=json(resolve(SOURCE,'adaptive/manifest.json'));
  const jobs=new Map(pilot.matchups.map(x=>[x.id,x]));
  const inventory=gunzipSync(readFileSync(resolve(SOURCE,'adaptive/inventory.jsonl.gz')))
    .toString('utf8').trim().split('\n').map(JSON.parse);
  for(const job of inventory){
    const old=jobs.get(job.id);
    if(old)assert.deepEqual([old.teamKeys,old.counts,old.scenarioHash],
      [job.teamKeys,job.counts,job.scenarioHash]);
    jobs.set(job.id,job);
  }
  const candidates=[];
  for(const [area,manifest] of [['pilot',pilot],['adaptive',adaptive]]){
    const dir=resolve(SOURCE,area,'runs');
    for(const file of readdirSync(dir).filter(x=>x.endsWith('.jsonl')).sort()){
      for(const {text,line} of sourceLines(resolve(dir,file))){
        const row=JSON.parse(text);
        if(!['win','loss','draw'].includes(row.outcome)||row.error)continue;
        assert.equal(row.campaignHash,manifest.campaignHash);
        const job=jobs.get(row.matchupId);assert(job,row.matchupId);
        assert.deepEqual([row.unitCount,row.opponentCount],job.counts);
        candidates.push({row,job,sourceCampaignHash:manifest.campaignHash,
          sourcePath:`${area}/runs/${file}`,sourceLine:line,
          sourceRecordSha256:sha(Buffer.from(text))});
      }
    }
  }
  return {pilot,adaptive,candidates};
}
function frozenManifest(pilot,adaptive){
  const runtimeFiles=FROZEN.runtimeFiles.map(entry=>({path:entry.path,
    sha256:sha(readFileSync(resolve(ROOT,entry.path)))}));
  assert.equal(runtimeFiles.filter(x=>x.sha256!==FROZEN.runtimeFiles.find(y=>y.path===x.path).sha256).length,1);
  assert.equal(runtimeFiles.find(x=>x.path.endsWith('/ranged-crowding.js')).sha256,
    sha(readFileSync(resolve(SIM,'src/combat/ranged-crowding.js'))));
  const body={schemaVersion:1,campaignName:'civ-matchups-collision-repair-v2-2026-10-31',
    createdAt:now(),sourceCommit:command('git',['rev-parse','HEAD']),
    sourceCampaignHashes:[pilot.campaignHash,adaptive.campaignHash],
    referenceDbSha256:FROZEN.referenceDbSha256,engineConfig:FROZEN.engineConfig,
    simulationEnvironment:FROZEN.simulationEnvironment,runtimeFiles,
    policy:{...adaptive.policy,workers:1,wallTimeoutSteps:[180,600,1800,3600]},
    replaySource:'append-only valid V3 pilot and adaptive journals; replay every saved seed under repaired engine',
    publishBranch:'simulations/civ-matchups-collision-repair-2026-10-31'};
  return {...body,campaignHash:digest(body)};
}
function checkpoint(state,label){
  state.lastPushedAt=now();atomic(resolve(DIR,'state.json'),state);
  const prefix=relative(ROOT,DIR);
  command('git',['add','--',prefix]);
  if(command('git',['diff','--cached','--name-only']))command('git',['commit','-m',`Checkpoint collision repair replay: ${label}`]);
  command('git',['push','origin',state.publishBranch]);
}
async function main(){
  assert.equal(command('git',['branch','--show-current']),
    'simulations/civ-matchups-collision-repair-2026-10-31');
  mkdirSync(DIR,{recursive:true});
  const lock=resolve(DIR,'.runner.lock');
  if(existsSync(lock)){
    const pid=Number(readFileSync(lock,'utf8'));let alive=false;
    try{process.kill(pid,0);alive=!/^State:\s*Z/m.test(readFileSync(`/proc/${pid}/status`,'utf8'));}
    catch(error){if(error.code!=='ESRCH'&&error.code!=='ENOENT')throw error;}
    if(alive)throw new Error(`replay runner already active under PID ${pid}`);
    unlinkSync(lock);
  }
  writeFileSync(lock,String(process.pid),{flag:'wx'});
  let pool;
  try{
    const {pilot,adaptive,candidates}=sources();
    const manifestPath=resolve(DIR,'manifest.json');
    const manifest=existsSync(manifestPath)?json(manifestPath):frozenManifest(pilot,adaptive);
    if(!existsSync(manifestPath))atomic(manifestPath,manifest);
    const {campaignHash,...body}=manifest;assert.equal(digest(body),campaignHash);
    assert.deepEqual(manifest.sourceCampaignHashes,[pilot.campaignHash,adaptive.campaignHash]);
    for(const file of manifest.runtimeFiles)assert.equal(sha(readFileSync(resolve(ROOT,file.path))),file.sha256);
    const replayFile=resolve(DIR,'replays.jsonl'),saved=new Map();
    for(const row of lines(replayFile)){
      assert.equal(row.campaignHash,campaignHash);
      const key=`${row.sourceCampaignHash}:${row.matchupId}:${row.seed}`;
      assert(!saved.has(key),`duplicate replay ${key}`);saved.set(key,row);
    }
    const statePath=resolve(DIR,'state.json');
    const state=existsSync(statePath)?json(statePath):{createdAt:now(),savedReplays:0};
    state.status='running';state.pid=process.pid;state.publishBranch=manifest.publishBranch;
    state.sourceCandidates=candidates.length;state.savedReplays=saved.size;state.updatedAt=now();atomic(statePath,state);
    pool=new RankingWorkerPool(1,{workerUrl:new URL('../collision-validation-worker.mjs',import.meta.url),
      maxTicks:Number.MAX_SAFE_INTEGER});
    let completed=0,lastCheckpoint=Date.now();
    for(const item of candidates){
      const {row,job}=item,key=`${item.sourceCampaignHash}:${job.id}:${row.seed}`;
      const existing=saved.get(key);
      if(existing){assert.equal(existing.sourceRecordSha256,item.sourceRecordSha256);continue;}
      if(completed>=limit)break;
      let result=null;
      for(const [index,wallLimit] of manifest.policy.wallTimeoutSteps.entries()){
        const start=performance.now(),message=await pool.run(payload(job,row.seed),wallLimit);
        if(message.result&&['win','draw'].includes(message.result.outcome)){
          const r=message.result,outcome=r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss';
          result={campaignHash,sourceCampaignHash:item.sourceCampaignHash,
            matchupId:job.id,seed:row.seed,sourcePath:item.sourcePath,sourceLine:item.sourceLine,
            sourceRecordSha256:item.sourceRecordSha256,pairKey:job.pairKey??null,
            profileHashes:job.profileHashes??null,counts:job.counts,scenarioHash:job.scenarioHash,
            outcome,winnerOwner:r.winnerOwner,ticks:r.ticks,simulationSeconds:r.ticks/60,
            wallSeconds:(performance.now()-start)/1000,finalStateHash:r.finalStateHash,
            eventLogHash:r.eventLogHash,exactOldResult:outcome===row.outcome
              &&r.finalStateHash===row.finalStateHash&&r.eventLogHash===row.eventLogHash};
          break;
        }
        append(resolve(DIR,'attempts.jsonl'),{at:now(),matchupId:job.id,seed:row.seed,
          attempt:index+1,wallLimit,error:message.error??null,watchdog:message.watchdog??false,
          lastProgress:message.lastProgress??null});
      }
      if(!result){
        state.failedKeys=[...new Set([...(state.failedKeys??[]),key])];
        state.status='blocked';state.updatedAt=now();atomic(statePath,state);
        continue;
      }
      append(replayFile,result);saved.set(key,result);completed++;
      if(state.failedKeys)state.failedKeys=state.failedKeys.filter(x=>x!==key);
      state.savedReplays=saved.size;state.updatedAt=now();
      if(!result.exactOldResult)state.changedResults=(state.changedResults??0)+1;
      atomic(statePath,state);
      console.log(JSON.stringify({replayed:key,exact:result.exactOldResult,wallSeconds:result.wallSeconds}));
      if(completed%250===0||Date.now()-lastCheckpoint>=600000){checkpoint(state,`${saved.size} seeds`);lastCheckpoint=Date.now();}
    }
    state.sourceCandidates=candidates.length;
    state.remainingCandidates=candidates.length-saved.size;
    state.status=state.failedKeys?.length?'blocked':state.remainingCandidates?'paused_limit':'caught_up';
    state.updatedAt=now();state.savedReplays=saved.size;checkpoint(state,state.status);
  }finally{await pool?.close();unlinkSync(lock);}
}
await main();
