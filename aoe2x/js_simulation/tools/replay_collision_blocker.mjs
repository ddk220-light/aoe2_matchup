#!/usr/bin/env node
// Diagnostic only: no campaign journal writes or outcome overrides.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {gunzipSync} from 'node:zlib';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';
import {hashCanonicalJson as digest} from '../src/canonical-json.js';

const root=resolve(import.meta.dirname,'../../..');
const base=resolve(root,'aoe2x/js_simulation/calibration/campaigns');
const frozen=JSON.parse(readFileSync(resolve(base,'unit-rankings-path-recovery-2026-10-29/manifest.json')));
const inventory=gunzipSync(readFileSync(resolve(base,
  'civ-matchups-campaign-2026-10-31/adaptive/inventory.jsonl.gz')))
  .toString('utf8').trim().split('\n').map(JSON.parse);
const job=inventory.find(x=>x.id==='cm_d01c0228f2df48ee3ffffe04');
assert(job);
const scenario=frozen.scenarios[job.scenarioHash] ?? (()=>{
  const source=Object.values(frozen.scenarios).find(x=>x.family===job.family);
  assert(source);
  const variant={...source,engineFamily:job.engineFamily};
  assert.equal(digest(variant),job.scenarioHash);
  return variant;
})();
const seed=Number(process.argv[2]);
assert(Number.isInteger(seed)&&seed>=0&&seed<=9);
const pool=new RankingWorkerPool(1,{workerUrl:new URL('../node/collision-validation-worker.mjs',import.meta.url),
  maxTicks:Number.MAX_SAFE_INTEGER});
try{
  const result=await pool.run({jobId:job.id,seed,
    teams:job.teamKeys.map((key,i)=>({mechanics:frozen.profiles[key].mechanics,count:job.counts[i]})),
    scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false},600);
  console.log(JSON.stringify({seed,error:result.error??null,watchdog:result.watchdog??false,
    lastProgress:result.lastProgress??null,result:result.result&&{
      outcome:result.result.outcome,winnerOwner:result.result.winnerOwner,
      ticks:result.result.ticks,finalStateHash:result.result.finalStateHash,
      eventLogHash:result.result.eventLogHash,
    }}));
  if(result.error||result.watchdog)process.exitCode=1;
}finally{await pool.close();}
