#!/usr/bin/env node
// Isolated diagnosis: no campaign journal is read as an output or modified.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {gunzipSync} from 'node:zlib';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';
import {hashCanonicalJson} from '../src/canonical-json.js';

const sim=resolve(import.meta.dirname,'..');
const root=resolve(sim,'../..');
const sourceRoot=process.env.CIV_V3_WORKTREE??'/workspace/aoe2_path_recovery';
const source=resolve(sourceRoot,'aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31');
const frozen=JSON.parse(readFileSync(resolve(sim,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const oldCampaign=JSON.parse(readFileSync(resolve(source,'adaptive/manifest.json')));
const id=process.env.SLOW_PAIR_MATCHUP_ID??'cm_60c2234fc6c6b02543651544';
const seed=Number(process.env.SLOW_PAIR_SEED??0);
const maxTicks=Number(process.env.SLOW_PAIR_MAX_TICKS??Number.MAX_SAFE_INTEGER);
assert(Number.isSafeInteger(seed)&&seed>=0);
assert(Number.isSafeInteger(maxTicks)&&maxTicks>0);
const jobs=gunzipSync(readFileSync(resolve(source,'adaptive/inventory.jsonl.gz')))
  .toString('utf8').trim().split('\n').map(JSON.parse);
const job=jobs.find(row=>row.id===id);assert(job);
if(!process.env.SLOW_PAIR_MATCHUP_ID){
  assert.deepEqual(job.teamKeys,['Mapuche|imp_elite_skirm','Celts|paladin']);
  assert.deepEqual(job.counts,[27,17]);
}
const sha=path=>createHash('sha256').update(readFileSync(path)).digest('hex');
const scenario=frozen.scenarios[job.scenarioHash]??{
  ...Object.values(frozen.scenarios).find(value=>value.family===job.family),
  engineFamily:job.engineFamily,
};
assert.equal(hashCanonicalJson(scenario),job.scenarioHash);
const payload={jobId:id,seed,
  teams:job.teamKeys.map((key,index)=>({mechanics:frozen.profiles[key].mechanics,count:job.counts[index]})),
  scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false};
const timeline=process.env.SLOW_PAIR_TIMELINE==='1';
const pool=new RankingWorkerPool(1,{workerUrl:new URL(timeline
  ? '../node/slow-fight-diagnostic-worker.mjs'
  : '../node/collision-validation-worker.mjs',import.meta.url),
  maxTicks});
const startedAt=new Date().toISOString(),start=performance.now();
let message;
try{message=await pool.run(payload,Number(process.env.SLOW_PAIR_WALL_LIMIT??7200));}
finally{await pool.close();}
const report={startedAt,finishedAt:new Date().toISOString(),
  wallSeconds:(performance.now()-start)/1000,sourceCampaignHash:oldCampaign.campaignHash,
  rankingInputCampaignHash:frozen.campaignHash,matchupId:id,seed,teamKeys:job.teamKeys,
  counts:job.counts,scenarioHash:job.scenarioHash,maxTicks,
  runtimeSha256:Object.fromEntries(['src/combat/ranged-crowding.js','src/canonical-json.js','src/fight.js',
    timeline?'node/slow-fight-diagnostic-worker.mjs':'node/collision-validation-worker.mjs']
    .map(file=>[file,sha(resolve(sim,file))])),
  result:message.result??null,error:message.error??null,watchdog:message.watchdog??false,
  lastProgress:message.lastProgress??null,diagnostic:message.diagnostic??null};
const out=process.env.SLOW_PAIR_REPORT_PATH
  ? resolve(process.env.SLOW_PAIR_REPORT_PATH)
  : resolve(sim,'calibration/reports/civ-matchups-stream-hash-2026-10-31/slow-pair-seed0.json');
mkdirSync(dirname(out),{recursive:true});writeFileSync(out,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({out,wallSeconds:report.wallSeconds,outcome:report.result?.outcome??null,
  winnerOwner:report.result?.winnerOwner??null,ticks:report.result?.ticks??null,
  error:report.error?.message??null,watchdog:report.watchdog}));
