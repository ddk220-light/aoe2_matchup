#!/usr/bin/env node
// Never writes a campaign journal or changes frozen runtime source.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync,unlinkSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {parseArgs} from 'node:util';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';
import {hashCanonicalJson as digest} from '../src/canonical-json.js';

const {values:a}=parseArgs({options:{matchup:{type:'string'},seed:{type:'string',default:'0'},
  name:{type:'string'},ticks:{type:'string',default:'9000'},wall:{type:'string',default:'180'},
  'sample-ticks':{type:'string',default:'600'},profile:{type:'boolean',default:false},'completed-control':{type:'boolean',default:false}}});
const sim=resolve(import.meta.dirname,'..'),root=resolve(sim,'../..');
const campaign=resolve(sim,'calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01');
const out=resolve(sim,'calibration/reports/civ-recovery-stream-diagnostics-2026-11-02');
const load=p=>JSON.parse(readFileSync(p,'utf8')),sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const live=pid=>{try{return !/^State:\s*Z/m.test(readFileSync(`/proc/${Number(pid)}/status`,'utf8'));}catch(e){if(e.code==='ENOENT')return false;throw e;}};
const seed=Number(a.seed),maxTicks=Number(a.ticks),wall=Number(a.wall),sampleTicks=Number(a['sample-ticks']);
assert(Number.isSafeInteger(seed)&&seed>=0&&seed<10);
assert(Number.isSafeInteger(maxTicks)&&maxTicks>0&&maxTicks<=36000);
assert(Number.isSafeInteger(sampleTicks)&&sampleTicks>0&&sampleTicks<=maxTicks);
assert(wall>0&&wall<=600);
const m=load(resolve(campaign,'manifest.json'));const {campaignHash,...body}=m;assert.equal(digest(body),campaignHash);
for(const f of m.runtimeFiles)assert.equal(sha(resolve(root,f.path)),f.sha256,`frozen runtime changed: ${f.path}`);
const frozenPath=resolve(sim,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json');
assert.equal(sha(frozenPath),m.frozenInputsSha256);
assert.equal(sha(resolve(campaign,'jobs.json')),m.jobsSha256);
assert.deepEqual(Object.fromEntries(Object.keys(process.env).filter(k=>k.startsWith('AOE2X_EXP_')).sort().map(k=>[k,process.env[k]])),m.simulationEnvironment);
const job=load(resolve(campaign,'jobs.json')).find(j=>j.id===a.matchup);assert(job);
const key=`${job.id}:${seed}`,state=load(resolve(campaign,'state.json'));
assert(!live(state.pid)||!state.active.includes(key),'campaign seed is active');
const raw=readFileSync(resolve(campaign,'runs.jsonl'),'utf8');
const lines=raw.endsWith('\n')?raw.trimEnd().split('\n'):raw.split('\n').slice(0,-1);
const control=lines.filter(Boolean).map(JSON.parse).find(r=>r.matchupId===job.id&&r.seed===seed);
if(a['completed-control'])assert(control,'completed control record required');
else assert(state.failedKeys.includes(key),'diagnose exhausted failures only');
mkdirSync(out,{recursive:true});const lock=resolve(out,key+'.lock');
if(existsSync(lock)){assert(!live(readFileSync(lock,'utf8')),'diagnostic already live');unlinkSync(lock);}
writeFileSync(lock,String(process.pid),{flag:'wx'});
let pool;
try{
  const stem=a.name??`${job.id}-seed${seed}`;assert(/^[a-zA-Z0-9_-]+$/.test(stem));
  const timelinePath=resolve(out,stem+'.jsonl'),reportPath=resolve(out,stem+'.json');
  const profilePath=a.profile?resolve(out,stem+'.cpuprofile'):null;
  assert(!existsSync(timelinePath)&&!existsSync(reportPath),'never overwrite a diagnostic');
  const frozen=load(frozenPath),scenario=frozen.scenarios[job.scenarioHash];assert(scenario);
  assert.equal(digest(scenario),job.scenarioHash);
  pool=new RankingWorkerPool(1,{workerUrl:new URL('../node/recovery-stream-diagnostic-worker.mjs',import.meta.url),maxTicks});
  const startedAt=new Date().toISOString(),start=performance.now();
  const message=await pool.run({jobId:job.id,seed,teams:job.teamKeys.map((k,i)=>({mechanics:frozen.profiles[k].mechanics,count:job.counts[i]})),
    scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false,
    diagnostic:{timelinePath,sampleTicks,profilePath}},wall);
  await pool.close();pool=null;
  const timeline=existsSync(timelinePath)?readFileSync(timelinePath,'utf8'):'';
  const samples=timeline.trim()?timeline.trimEnd().split('\n').map(JSON.parse):[];
  const parity=control&&message.result?['finalStateHash','eventLogHash','ticks','winnerOwner'].every(k=>control[k]===message.result[k]):null;
  const report={diagnosticOnly:true,startedAt,finishedAt:new Date().toISOString(),wallSeconds:(performance.now()-start)/1000,
    sourceCampaignHash:campaignHash,physicsVersion:m.physicsVersion,sourceManifestSha256:sha(resolve(campaign,'manifest.json')),
    runtimeFiles:m.runtimeFiles,toolSha256:sha(resolve(sim,'tools/diagnose_recovery_stream.mjs')),
    workerSha256:sha(resolve(sim,'node/recovery-stream-diagnostic-worker.mjs')),
    matchupId:job.id,seed,teamKeys:job.teamKeys,counts:job.counts,scenarioHash:job.scenarioHash,
    maxTicks,sampleTicks,wallLimit:wall,timelinePath,timelineSha256:existsSync(timelinePath)?sha(timelinePath):null,
    samples:samples.length,lastSample:samples.at(-1)?.seconds??null,message,exactControlParity:parity};
  report.profilePath=profilePath;report.profileSha256=profilePath&&existsSync(profilePath)?sha(profilePath):null;
  writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({reportPath,samples:report.samples,lastSample:report.lastSample,
    watchdog:message.watchdog??false,error:message.error??null,exactControlParity:parity}));
  if(a['completed-control'])assert.equal(parity,true,'read-only observer changed fight output');
}finally{await pool?.close();unlinkSync(lock);}
