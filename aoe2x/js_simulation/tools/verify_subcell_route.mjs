import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';
const sim=resolve(import.meta.dirname,'..'),out=resolve(sim,'calibration/reports/civ-subcell-route-2026-11-02/v3');mkdirSync(out,{recursive:true});
const load=p=>JSON.parse(readFileSync(p,'utf8'));
const source='/workspace/aoe2_civ_event_stream/aoe2x/js_simulation/calibration/campaigns/civ-matchups-event-stream-first-pass-2026-11-02';
const old='/workspace/aoe2_civ_first_pass_parallel/aoe2x/js_simulation/calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01';
const frozen=load(resolve(sim,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'));
const jobs=new Map(load(resolve(old,'jobs.json')).map(j=>[j.id,j]));
const records=readFileSync(resolve(source,'runs.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
const cases=[['cm_b49b88761f519d9bd7d20a07',0,9000],['cm_b49b88761f519d9bd7d20a07',1,9000],['cm_b5c816c87bdc49ea72433cd3',0,9000]];
const results=[];
for(const [id,seed,maxTicks] of cases){
 const state=load(resolve(source,'state.json'));assert(!state.pid&&!state.active.includes(`${id}:${seed}`));
 const job=jobs.get(id),path=resolve(out,`${id}-${seed}.json`);assert(!existsSync(path));
 const pool=new RankingWorkerPool(1,{workerUrl:pathToFileURL(resolve(sim,'node/event-stream-recovery-worker.mjs')),maxTicks});
 const start=performance.now();let message;
 try{message=await pool.run({jobId:id,seed,teams:job.teamKeys.map((key,i)=>({mechanics:frozen.profiles[key].mechanics,count:job.counts[i]})),scenario:frozen.scenarios[job.scenarioHash],disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false,diagnosticProgressPath:resolve(out,`${id}-${seed}.jsonl`)},180);}finally{await pool.close();}
 const expected=records.find(r=>r.matchupId===id&&r.seed===seed);
 const comparison=expected&&message.result?Object.fromEntries(['winnerOwner','ticks','finalStateHash','eventLogHash'].map(k=>[k,message.result[k]===expected[k]])):null;
 const report={diagnosticOnly:true,matchupId:id,seed,maxTicks,wallSeconds:(performance.now()-start)/1000,message,comparison};
 writeFileSync(path,JSON.stringify(report,null,2)+'\n');results.push(report);console.log(JSON.stringify({id,seed,wallSeconds:report.wallSeconds,outcome:message.result?.outcome,ticks:message.result?.ticks,comparison}));
}
writeFileSync(resolve(out,'probe-summary.json'),JSON.stringify({diagnosticOnly:true,results},null,2)+'\n');
