#!/usr/bin/env node
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';

const sim=resolve(import.meta.dirname,'..');
const base='/workspace/aoe2_civ_first_pass_parallel/aoe2x/js_simulation';
const out=resolve(sim,'calibration/reports/civ-no-route-cache-2026-11-02');mkdirSync(out,{recursive:true});
const load=p=>JSON.parse(readFileSync(p,'utf8')),sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const campaign=resolve(base,'calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01');
const m=load(resolve(campaign,'manifest.json'));
const frozen=load(resolve(sim,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'));
const job=load(resolve(campaign,'jobs.json')).find(j=>j.id==='cm_b49b88761f519d9bd7d20a07');assert(job);
const state=load(resolve(campaign,'state.json'));assert(!state.active.includes(`${job.id}:0`));
for(const f of m.runtimeFiles){const suffix=f.path.replace('aoe2x/js_simulation/','');
  assert.equal(sha(resolve(base,suffix)),f.sha256);
  if(suffix!=='src/combat/chase-path.js')assert.equal(sha(resolve(sim,suffix)),f.sha256);}
const results=[];
for(const [label,engine,seed,maxTicks] of [['baseline40',base,0,2400],['candidate40',sim,0,2400],['candidate-control',sim,1,9000]]){
  const report=resolve(out,label+'.json'),timelinePath=resolve(out,label+'.jsonl');
  assert(!existsSync(report)&&!existsSync(timelinePath),'never overwrite benchmark evidence');
  const pool=new RankingWorkerPool(1,{workerUrl:pathToFileURL(resolve(engine,'node/recovery-stream-diagnostic-worker.mjs')),maxTicks});
  const start=performance.now();let message;
  try{message=await pool.run({jobId:job.id,seed,
    teams:job.teamKeys.map((key,i)=>({mechanics:frozen.profiles[key].mechanics,count:job.counts[i]})),
    scenario:frozen.scenarios[job.scenarioHash],disableAiOrders:true,disableKiting:true,
    preserveOwnerOrientation:true,retainSnapshots:false,diagnostic:{timelinePath,sampleTicks:600}},300);}
  finally{await pool.close();}
  const value={diagnosticOnly:true,label,seed,maxTicks,wallSeconds:(performance.now()-start)/1000,
    sourceCampaignHash:m.campaignHash,chasePathSha256:sha(resolve(engine,'src/combat/chase-path.js')),
    cacheSha256:engine===sim?sha(resolve(sim,'src/combat/no-route-cache.js')):null,
    workerSha256:sha(resolve(engine,'node/recovery-stream-diagnostic-worker.mjs')),message};
  writeFileSync(report,JSON.stringify(value,null,2)+'\n');results.push(value);
  console.log(JSON.stringify({label,wallSeconds:value.wallSeconds,ticks:message.result?.ticks,watchdog:message.watchdog??false,error:message.error??null}));
  assert(message.result,'bounded parity fight did not complete');
}
const fields=['outcome','winnerOwner','ticks','finalStateHash','eventLogHash'];
for(const field of fields)assert.deepEqual(results[0].message.result[field],results[1].message.result[field],`bounded parity ${field}`);
const saved=readFileSync(resolve(campaign,'runs.jsonl'),'utf8').trimEnd().split('\n').map(JSON.parse)
  .find(r=>r.matchupId===job.id&&r.seed===1);assert(saved);
for(const field of fields.filter(f=>f!=='outcome'))assert.deepEqual(results[2].message.result[field],saved[field],`full control parity ${field}`);
const summary={diagnosticOnly:true,boundedExactParity:true,completeControlExactParity:true,
  baselineWallSeconds:results[0].wallSeconds,candidateWallSeconds:results[1].wallSeconds,
  observedSpeedRatio:results[0].wallSeconds/results[1].wallSeconds,
  candidateLastSample:JSON.parse(readFileSync(resolve(out,'candidate40.jsonl'),'utf8').trimEnd().split('\n').at(-1))};
writeFileSync(resolve(out,'summary.json'),JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify({boundedExactParity:true,completeControlExactParity:true,observedSpeedRatio:summary.observedSpeedRatio,
  cacheStatistics:summary.candidateLastSample.cacheStatistics}));
