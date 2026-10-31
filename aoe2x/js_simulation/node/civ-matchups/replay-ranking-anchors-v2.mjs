#!/usr/bin/env node
// Recompute corrected ranking anchors under the repaired collision engine.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,openSync,closeSync,fsyncSync,appendFileSync,
  existsSync,mkdirSync,renameSync,unlinkSync} from 'node:fs';
import {resolve,dirname,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {hashCanonicalJson} from '../../src/canonical-json.js';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const ROOT=resolve(SIM,'../..');
const SOURCE=resolve(SIM,'calibration/campaigns/unit-rankings-consolidated-2026-10-29');
const DIR=resolve(SIM,'calibration/campaigns/civ-matchups-ranking-anchors-v2-2026-10-31');
const FROZEN=JSON.parse(readFileSync(resolve(SIM,
  'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const readJson=path=>JSON.parse(readFileSync(path,'utf8'));
const now=()=>new Date().toISOString();
const limitAt=process.argv.indexOf('--limit');
const limit=limitAt<0?Infinity:Number(process.argv[limitAt+1]);
assert(limit===Infinity||Number.isSafeInteger(limit)&&limit>0);
function atomic(path,value){const temp=`${path}.tmp`,fd=openSync(temp,'w');
  try{writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}renameSync(temp,path);}
function append(path,value){const fd=openSync(path,'a');
  try{appendFileSync(fd,JSON.stringify(value)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
function command(args){const env={...process.env};delete env.GH_TOKEN;
  const argv=args[0]==='push'?['-c','http.extraHeader=','-c','credential.helper=',...args]:args;
  return execFileSync('git',argv,{cwd:ROOT,env,encoding:'utf8',stdio:['ignore','pipe','inherit']}).trim();}
function records(path){if(!existsSync(path))return[];
  const raw=readFileSync(path,'utf8'),parts=raw.split('\n');if(!raw.endsWith('\n'))parts.pop();
  return parts.map((line,index)=>({line,index:index+1})).filter(x=>x.line);}
function sourceRows(){
  const source=readJson(resolve(SOURCE,'manifest.json'));
  assert.equal(source.datasetHash,'17a91c8fa14553abbce1f894cbeb4e637d9fe9a82977fc2da2b0bc824cfade3c');
  assert.equal(FROZEN.campaignHash,'1ac49a6abf1f3a1a104c7bcf675a3a327b6939d49273ae49c51eb6157264693d');
  const jobs=new Map(FROZEN.matchups.map(m=>[m.id,m])),rows=[],sourceFiles=[];
  for(const name of ['runs.jsonl','additional-recorded-runs.jsonl']){
    const path=resolve(SOURCE,name),buffer=readFileSync(path);
    const listed=source.outputs.find(x=>x.path===name);
    assert.equal(sha(buffer),listed?.sha256,`consolidated source hash: ${name}`);
    sourceFiles.push({path:relative(ROOT,path),sha256:sha(buffer)});
    for(const {line,index} of records(path)){
      const row=JSON.parse(line),provenance=row.selectionProvenance;
      if(provenance?.engineVersion!=='corrected')continue;
      assert.equal(provenance.inputCampaignHash,FROZEN.campaignHash);
      assert.equal(row.error,null);
      assert(['win','loss','draw'].includes(row.outcome));
      const job=jobs.get(row.matchupId);assert(job,row.matchupId);
      assert.deepEqual([row.unitCount,row.opponentCount],job.counts);
      assert.equal(provenance.scenarioHash,job.scenarioHash);
      assert.deepEqual(provenance.profileHashes,job.teamKeys.map(k=>FROZEN.profiles[k].profileHash));
      rows.push({row,job,sourcePath:relative(ROOT,path),sourceLine:index,
        sourceRecordSha256:sha(Buffer.from(line))});
    }
  }
  assert.equal(rows.length,817,'corrected ranking source seed count');
  const keys=rows.map(({row})=>`${row.matchupId}:${row.seed}`);
  assert.equal(new Set(keys).size,keys.length,'duplicate corrected ranking seed');
  return {source,sourceFiles,rows};
}
function frozenManifest(source,sourceFiles){
  const runtimeFiles=FROZEN.runtimeFiles.map(file=>({path:file.path,
    sha256:sha(readFileSync(resolve(ROOT,file.path)))}));
  const changed=runtimeFiles.filter(x=>x.sha256!==FROZEN.runtimeFiles.find(y=>y.path===x.path).sha256);
  assert.deepEqual(changed.map(x=>x.path),['aoe2x/js_simulation/src/combat/ranged-crowding.js']);
  const body={schemaVersion:1,campaignName:'civ-matchups-ranking-anchors-v2-2026-10-31',
    createdAt:now(),sourceCommit:command(['rev-parse','HEAD']),
    rankingSourceDatasetHash:source.datasetHash,rankingSourceCampaignHash:FROZEN.campaignHash,
    referenceDbSha256:FROZEN.referenceDbSha256,sourceFiles,runtimeFiles,
    policy:{workers:1,wallTimeoutSteps:[180,600,1800,3600],maxTicks:Number.MAX_SAFE_INTEGER},
    publishBranch:'simulations/civ-matchups-anchor-replay-2026-10-31'};
  return {...body,campaignHash:hashCanonicalJson(body)};
}
function payload(job,seed){return {jobId:job.id,seed,
  teams:job.teamKeys.map((key,i)=>({mechanics:FROZEN.profiles[key].mechanics,count:job.counts[i]})),
  scenario:FROZEN.scenarios[job.scenarioHash],disableAiOrders:true,disableKiting:true,
  preserveOwnerOrientation:true,retainSnapshots:false};}
function checkpoint(state,label){
  state.lastPushedAt=now();atomic(resolve(DIR,'state.json'),state);
  const paths=['manifest.json','state.json','replays.jsonl','attempts.jsonl']
    .map(x=>resolve(DIR,x)).filter(existsSync).map(x=>relative(ROOT,x));
  command(['add','--',...paths]);
  if(command(['diff','--cached','--name-only']))command(['commit','-m',`Checkpoint ranking anchor replay: ${label}`]);
  command(['push','origin',state.publishBranch]);
}
async function main(){
  assert.equal(command(['branch','--show-current']),
    'simulations/civ-matchups-anchor-replay-2026-10-31');
  mkdirSync(DIR,{recursive:true});
  const lock=resolve(DIR,'.runner.lock');
  if(existsSync(lock)){
    const pid=Number(readFileSync(lock,'utf8'));let alive=false;
    try{process.kill(pid,0);alive=!/^State:\s*Z/m.test(readFileSync(`/proc/${pid}/status`,'utf8'));}
    catch(error){if(error.code!=='ESRCH'&&error.code!=='ENOENT')throw error;}
    if(alive)throw new Error(`ranking anchor replay already running: ${pid}`);
    unlinkSync(lock);
  }
  writeFileSync(lock,String(process.pid),{flag:'wx'});
  let pool;
  try{
    const {source,sourceFiles,rows}=sourceRows();
    const manifestPath=resolve(DIR,'manifest.json');
    const manifest=existsSync(manifestPath)?readJson(manifestPath):frozenManifest(source,sourceFiles);
    if(!existsSync(manifestPath))atomic(manifestPath,manifest);
    const {campaignHash,...body}=manifest;assert.equal(hashCanonicalJson(body),campaignHash);
    assert.equal(manifest.rankingSourceDatasetHash,source.datasetHash);
    assert.deepEqual(manifest.sourceFiles,sourceFiles);
    for(const file of manifest.runtimeFiles)assert.equal(sha(readFileSync(resolve(ROOT,file.path))),file.sha256);
    const journal=resolve(DIR,'replays.jsonl'),saved=new Map();
    for(const {line} of records(journal)){
      const row=JSON.parse(line),key=`${row.matchupId}:${row.seed}`;
      assert.equal(row.campaignHash,campaignHash);assert(!saved.has(key),key);saved.set(key,row);
    }
    const statePath=resolve(DIR,'state.json');
    const state=existsSync(statePath)?readJson(statePath):{createdAt:now(),savedReplays:0};
    state.status='running';state.pid=process.pid;state.publishBranch=manifest.publishBranch;
    state.sourceCandidates=rows.length;state.savedReplays=saved.size;state.updatedAt=now();atomic(statePath,state);
    pool=new RankingWorkerPool(1,{workerUrl:new URL('../collision-validation-worker.mjs',import.meta.url),
      maxTicks:Number.MAX_SAFE_INTEGER});
    let completed=0,lastCheckpoint=Date.now();
    for(const item of rows){
      const {row,job}=item,key=`${job.id}:${row.seed}`,existing=saved.get(key);
      if(existing){assert.equal(existing.sourceRecordSha256,item.sourceRecordSha256);continue;}
      if(completed>=limit)break;
      let result=null;
      for(const [index,wallLimit] of manifest.policy.wallTimeoutSteps.entries()){
        const start=performance.now(),message=await pool.run(payload(job,row.seed),wallLimit);
        if(message.result&&['win','draw'].includes(message.result.outcome)){
          const r=message.result,outcome=r.outcome==='draw'?'draw':r.winnerOwner===2?'win':'loss';
          result={campaignHash,matchupId:job.id,seed:row.seed,sourcePath:item.sourcePath,
            sourceLine:item.sourceLine,sourceRecordSha256:item.sourceRecordSha256,
            profileHashes:job.teamKeys.map(k=>FROZEN.profiles[k].profileHash),
            counts:job.counts,scenarioHash:job.scenarioHash,outcome,winnerOwner:r.winnerOwner,
            ticks:r.ticks,simulationSeconds:r.ticks/60,wallSeconds:(performance.now()-start)/1000,
            finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,
            exactOldResult:outcome===row.outcome&&r.finalStateHash===row.finalStateHash
              &&r.eventLogHash===row.eventLogHash};
          break;
        }
        append(resolve(DIR,'attempts.jsonl'),{at:now(),matchupId:job.id,seed:row.seed,
          attempt:index+1,wallLimit,error:message.error??null,watchdog:message.watchdog??false,
          lastProgress:message.lastProgress??null});
      }
      if(!result){state.failedKeys=[...new Set([...(state.failedKeys??[]),key])];
        state.status='blocked';state.updatedAt=now();atomic(statePath,state);continue;}
      append(journal,result);saved.set(key,result);completed++;
      if(state.failedKeys)state.failedKeys=state.failedKeys.filter(x=>x!==key);
      state.savedReplays=saved.size;state.updatedAt=now();
      if(!result.exactOldResult)state.changedResults=(state.changedResults??0)+1;
      atomic(statePath,state);
      console.log(JSON.stringify({replayed:key,exact:result.exactOldResult,wallSeconds:result.wallSeconds}));
      if(completed%100===0||Date.now()-lastCheckpoint>=600000){checkpoint(state,`${saved.size} seeds`);lastCheckpoint=Date.now();}
    }
    state.remainingCandidates=rows.length-saved.size;
    state.status=state.failedKeys?.length?'blocked':state.remainingCandidates?'paused_limit':'caught_up';
    state.pid=null;state.updatedAt=now();checkpoint(state,state.status);
  }finally{await pool?.close();unlinkSync(lock);}
}
await main();
