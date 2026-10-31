#!/usr/bin/env node
// Replay representative completed old-engine fights under the repair.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';

const root=resolve(import.meta.dirname,'../../..');
const sim=resolve(root,'aoe2x/js_simulation');
const source=JSON.parse(readFileSync(resolve(sim,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const rows=readFileSync(resolve(sim,'calibration/campaigns/unit-rankings-consolidated-2026-10-29/runs.jsonl'),'utf8')
  .trim().split('\n').map(JSON.parse)
  .filter(r=>r.seed===0&&r.selectionProvenance.engineVersion==='corrected'&&!r.error)
  .sort((a,b)=>a.wallSeconds-b.wallSeconds);
const byId=new Map(source.matchups.map(m=>[m.id,m]));
const picked=new Map();
for(const row of rows){
  const job=byId.get(row.matchupId),scenario=source.scenarios[job.scenarioHash];
  const family=`${scenario.family}|${scenario.engineFamily}`;
  if(!picked.has(family))picked.set(family,{row,job,scenario});
}
assert.equal(picked.size,Object.keys(source.scenarios).length);
const blockedId='cm_d01c0228f2df48ee3ffffe04';
const base=resolve(sim,'calibration/campaigns/civ-matchups-campaign-2026-10-31');
const blocker=readFileSync(resolve(base,'adaptive/runs/009.jsonl'),'utf8').trim().split('\n').map(JSON.parse)
  .find(r=>r.matchupId===blockedId&&r.seed===0);
assert(blocker);
const sha=path=>createHash('sha256').update(readFileSync(path)).digest('hex');
const pool=new RankingWorkerPool(4,{workerUrl:new URL('../node/collision-validation-worker.mjs',import.meta.url),
  maxTicks:Number.MAX_SAFE_INTEGER});
try{
  const checks=await Promise.all([...picked.entries()].map(async([family,{row,job,scenario}])=>{
    const message=await pool.run({jobId:job.id,seed:row.seed,
      teams:job.teamKeys.map((key,i)=>({mechanics:source.profiles[key].mechanics,count:job.counts[i]})),
      scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false},180);
    return {family,matchupId:job.id,seed:row.seed,
      exact:message.result?.finalStateHash===row.finalStateHash
        &&message.result?.eventLogHash===row.eventLogHash
        &&message.result?.winnerOwner===row.winnerOwner,
      error:message.error??null,watchdog:message.watchdog??false};
  }));
  const {gunzipSync}=await import('node:zlib');
  const jobs=gunzipSync(readFileSync(resolve(base,'adaptive/inventory.jsonl.gz')))
    .toString('utf8').trim().split('\n').map(JSON.parse);
  const job=jobs.find(x=>x.id===blockedId);assert(job);
  const scenario=source.scenarios[job.scenarioHash]??(()=>{
    const authored=Object.values(source.scenarios).find(x=>x.family===job.family);
    return {...authored,engineFamily:job.engineFamily};
  })();
  const message=await pool.run({jobId:job.id,seed:0,
    teams:job.teamKeys.map((key,i)=>({mechanics:source.profiles[key].mechanics,count:job.counts[i]})),
    scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false},180);
  checks.push({family:'ranged_vs_ranged|rvr',matchupId:blockedId,seed:0,
    exact:message.result?.finalStateHash===blocker.finalStateHash
      &&message.result?.eventLogHash===blocker.eventLogHash
      &&message.result?.winnerOwner===blocker.winnerOwner,
    error:message.error??null,watchdog:message.watchdog??false});
  const report={oldCrowdingSha256:source.runtimeFiles.find(x=>
      x.path.endsWith('/src/combat/ranged-crowding.js')).sha256,
    newCrowdingSha256:sha(resolve(sim,'src/combat/ranged-crowding.js')),
    sourceCampaignHash:source.campaignHash,checks};
  const out=resolve(sim,'calibration/reports/civ-matchups-collision-repair-2026-10-31/parity.json');
  mkdirSync(dirname(out),{recursive:true});writeFileSync(out,JSON.stringify(report,null,2)+'\n');
  assert(checks.every(x=>x.exact),JSON.stringify(checks.filter(x=>!x.exact)));
  console.log(JSON.stringify({exact:checks.length,families:checks.map(x=>x.family)}));
}finally{await pool.close();}
