import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';

test('read-only timeline worker preserves a saved fight result',async()=>{
  const sim=resolve(import.meta.dirname,'..');
  const source=JSON.parse(readFileSync(resolve(sim,
    'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
  const base=resolve(sim,'calibration/campaigns/civ-matchups-campaign-2026-10-31/pilot');
  const pilot=JSON.parse(readFileSync(resolve(base,'manifest.json')));
  const rows=readFileSync(resolve(base,'runs/00-pilot.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
  const row=rows.find(r=>r.seed===0&&r.outcome==='win'&&r.wallSeconds<30);
  assert(row,'fast recorded pilot seed');
  const job=pilot.matchups.find(m=>m.id===row.matchupId);
  assert(job);
  const scenario=source.scenarios[job.scenarioHash];assert(scenario);
  const pool=new RankingWorkerPool(1,{workerUrl:new URL('../node/slow-fight-diagnostic-worker.mjs',import.meta.url),
    maxTicks:Number.MAX_SAFE_INTEGER});
  try{
    const message=await pool.run({jobId:job.id,seed:row.seed,
      teams:job.teamKeys.map((key,index)=>({mechanics:source.profiles[key].mechanics,count:job.counts[index]})),
      scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,
      retainSnapshots:false},180);
    assert.equal(message.error,undefined);
    assert.equal(message.result?.finalStateHash,row.finalStateHash);
    assert.equal(message.result?.eventLogHash,row.eventLogHash);
    assert(message.diagnostic?.timeline?.length>0);
    assert(Object.keys(message.diagnostic.eventCounts).length>0);
  }finally{await pool.close();}
});
