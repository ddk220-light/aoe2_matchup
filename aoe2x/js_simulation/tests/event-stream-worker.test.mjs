import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';

test('durable event-stream worker keeps exact saved output and emits observational progress only',async()=>{
 const base=new URL('../calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01/',import.meta.url);
 const load=url=>JSON.parse(readFileSync(url,'utf8'));
 const job=load(new URL('jobs.json',base)).find(j=>j.id==='cm_b49b88761f519d9bd7d20a07');
 const frozen=load(new URL('../calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json',import.meta.url));
 const expected=readFileSync(new URL('runs.jsonl',base),'utf8').trimEnd().split('\n').map(JSON.parse).find(r=>r.matchupId===job.id&&r.seed===1);assert(expected);
 const dir=mkdtempSync(join(tmpdir(),'aoe2-event-stream-')),progressPath=join(dir,'progress.jsonl');
 const pool=new RankingWorkerPool(1,{workerUrl:new URL('../node/event-stream-recovery-worker.mjs',import.meta.url),maxTicks:9000});
 try{
  const m=await pool.run({jobId:job.id,seed:1,teams:job.teamKeys.map((key,i)=>({mechanics:frozen.profiles[key].mechanics,count:job.counts[i]})),scenario:frozen.scenarios[job.scenarioHash],disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false,diagnosticProgressPath:progressPath},180);
  assert(m.result,JSON.stringify(m));
  for(const k of ['ticks','winnerOwner','finalStateHash','eventLogHash'])assert.equal(m.result[k],expected[k],k);
  const progress=readFileSync(progressPath,'utf8').trimEnd().split('\n').map(JSON.parse);assert(progress.length);assert(progress.every(p=>p.diagnosticOnly===true));assert(progress[0].memoryUsage.heapUsed>0);
 }finally{await pool.close();rmSync(dir,{recursive:true,force:true});}
});
