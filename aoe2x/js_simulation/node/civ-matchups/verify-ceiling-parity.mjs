#!/usr/bin/env node
// Exact replay of finished corrected-engine seeds with the extended time guard.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const source=JSON.parse(readFileSync(resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const out=resolve(SIM,'calibration/campaigns/civ-matchups-campaign-2026-10-31/pilot/ceiling-parity.json');
const rows=readFileSync(resolve(SIM,'calibration/campaigns/unit-rankings-consolidated-2026-10-29/runs.jsonl'),'utf8')
  .trim().split('\n').map(JSON.parse)
  .filter(r=>r.seed===0&&r.selectionProvenance.engineVersion==='corrected'&&!r.error)
  .sort((a,b)=>a.wallSeconds-b.wallSeconds);
const byId=new Map(source.matchups.map(m=>[m.id,m]));
const picked=new Map();
for(const row of rows){
  const m=byId.get(row.matchupId),scenario=source.scenarios[m.scenarioHash];
  const family=`${scenario.family}|${scenario.engineFamily}`;
  if(!picked.has(family))picked.set(family,{row,m,scenario});
}
assert.equal(picked.size,Object.keys(source.scenarios).length);
const pool=new RankingWorkerPool(4,{workerUrl:new URL('../collision-validation-worker.mjs',import.meta.url),
  maxTicks:Number.MAX_SAFE_INTEGER});
try {
  const checks=await Promise.all([...picked.entries()].map(async([family,{row,m,scenario}])=>{
    const teams=m.teamKeys.map((k,i)=>({mechanics:source.profiles[k].mechanics,count:m.counts[i]}));
    const job={jobId:m.id,seed:row.seed,teams,scenario,disableAiOrders:true,disableKiting:true,
      preserveOwnerOrientation:true,retainSnapshots:false};
    const start=performance.now(),message=await pool.run(job,180);
    const result=message.result;
    const exact=result?.finalStateHash===row.finalStateHash&&result?.eventLogHash===row.eventLogHash
      &&result?.winnerOwner===row.winnerOwner;
    return {family,matchupId:m.id,seed:row.seed,originalTicks:row.ticks,replayTicks:result?.ticks??null,
      wallSeconds:(performance.now()-start)/1000,exact,error:message.error??null,watchdog:message.watchdog??false};
  }));
  writeFileSync(out,JSON.stringify({sourceCampaignHash:source.campaignHash,
    durationPolicy:'Number.MAX_SAFE_INTEGER game ticks; wall watchdog 180 seconds',checks},null,2)+'\n');
  assert(checks.every(x=>x.exact),`ceiling parity failed: ${JSON.stringify(checks.filter(x=>!x.exact))}`);
  console.log(JSON.stringify({exact:checks.length,families:checks.map(x=>x.family),maxReplayWallSeconds:Math.max(...checks.map(x=>x.wallSeconds))}));
} finally {await pool.close();}
