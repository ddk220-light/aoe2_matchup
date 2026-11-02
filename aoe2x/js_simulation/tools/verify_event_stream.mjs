import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';
const sim=resolve(import.meta.dirname,'..'),root=resolve(sim,'../..');
const base='/workspace/aoe2_civ_first_pass_parallel/aoe2x/js_simulation';
const out=resolve(sim,'calibration/reports/civ-event-stream-2026-11-02');mkdirSync(out,{recursive:true});
const load=p=>JSON.parse(readFileSync(p,'utf8')),sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const campaign=resolve(base,'calibration/campaigns/civ-matchups-first-pass-parallel-2026-11-01');
const m=load(resolve(campaign,'manifest.json')),frozen=load(resolve(sim,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'));
const jobs=new Map(load(resolve(campaign,'jobs.json')).map(j=>[j.id,j]));
const rows=readFileSync(resolve(campaign,'runs.jsonl'),'utf8').trimEnd().split('\n').map(JSON.parse);
const candidateFiles=['src/canonical-json.js','src/fight.js','src/combat/world.js','src/combat/collision.js'];
const runtime=m.runtimeFiles.map(f=>{const suffix=f.path.replace('aoe2x/js_simulation/','');assert.equal(sha(resolve(base,suffix)),f.sha256);
 const candidateSha256=sha(resolve(sim,suffix));if(!candidateFiles.includes(suffix))assert.equal(candidateSha256,f.sha256);
 return {...f,candidateSha256};});
const bounded=load('/workspace/aoe2_civ_path_cache/aoe2x/js_simulation/calibration/reports/civ-no-route-cache-2026-11-02/baseline40.json');
const controls=[['cm_b49b88761f519d9bd7d20a07',1],['cm_b5c816c87bdc49ea72433cd3',0],['cm_6827d25d70a06f758cc82ff9',0],['cm_115e22a115c48482b4c4d05f',1]];
const cases=[{id:'cm_b49b88761f519d9bd7d20a07',seed:0,maxTicks:2400,expected:bounded.message.result,label:'kona-bounded40'},
 ...controls.map(([id,seed])=>{const expected=rows.find(r=>r.matchupId===id&&r.seed===seed);assert(expected);return {id,seed,maxTicks:9000,expected,label:id+'-'+seed};})];
const results=[];
for(const c of cases){const job=jobs.get(c.id),timelinePath=resolve(out,c.label+'.jsonl'),reportPath=resolve(out,c.label+'.json');assert(!existsSync(reportPath)&&!existsSync(timelinePath));
 const sourceState=load(resolve(campaign,'state.json'));assert(!sourceState.active?.includes(`${c.id}:${c.seed}`),'source seed is live');
 const pool=new RankingWorkerPool(1,{workerUrl:pathToFileURL(resolve(sim,'node/recovery-stream-diagnostic-worker.mjs')),maxTicks:c.maxTicks});
 const startedAt=new Date().toISOString(),start=performance.now();let message;
 try{message=await pool.run({jobId:job.id,seed:c.seed,teams:job.teamKeys.map((key,i)=>({mechanics:frozen.profiles[key].mechanics,count:job.counts[i]})),scenario:frozen.scenarios[job.scenarioHash],disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false,diagnostic:{timelinePath,sampleTicks:600}},300);}finally{await pool.close();}
 const r={diagnosticOnly:true,sourceCampaignHash:m.campaignHash,startedAt,wallSeconds:(performance.now()-start)/1000,matchupId:job.id,seed:c.seed,maxTicks:c.maxTicks,message};
 writeFileSync(reportPath,JSON.stringify(r,null,2)+'\n');assert(message.result,JSON.stringify(message));
 for(const field of ['winnerOwner','ticks','finalStateHash','eventLogHash'])assert.deepEqual(message.result[field],c.expected[field],c.label+':'+field);
 r.exactParity=true;writeFileSync(reportPath,JSON.stringify(r,null,2)+'\n');results.push({label:c.label,wallSeconds:r.wallSeconds,exactParity:true});console.log(JSON.stringify(results.at(-1)));
}
writeFileSync(resolve(out,'parity-summary.json'),JSON.stringify({diagnosticOnly:true,results,runtime},null,2)+'\n');
