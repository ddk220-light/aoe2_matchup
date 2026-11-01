import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {RankingWorkerPool} from '../node/ranking-worker-pool.mjs';
import {hashCanonicalJson as digest} from '../src/canonical-json.js';
const source='/workspace/aoe2_path_recovery/aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31';
const frozen=JSON.parse(readFileSync(new URL('../calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json',import.meta.url)));
const jobs=new Map(gunzipSync(readFileSync(source+'/adaptive/inventory.jsonl.gz')).toString().trim().split('\n').map(JSON.parse).map(j=>[j.id,j]));
const rows=readFileSync('/workspace/aoe2_civ_collision_repair/aoe2x/js_simulation/calibration/campaigns/civ-matchups-collision-repair-v2-2026-10-31/replays.jsonl','utf8').trim().split('\n').map(JSON.parse);
const samples=[],families=new Set();
for(const r of rows){const j=jobs.get(r.matchupId);if(!j||r.wallSeconds>5||families.has(j.family))continue;samples.push({j,r});families.add(j.family);if(samples.length===3)break;}
assert.equal(samples.length,3);const pool=new RankingWorkerPool(3,{workerUrl:new URL('../node/collision-validation-worker.mjs',import.meta.url),maxTicks:Number.MAX_SAFE_INTEGER});
try{const tests=await Promise.all(samples.map(async({j,r})=>{
  let scenario=frozen.scenarios[j.scenarioHash];if(!scenario)scenario={...Object.values(frozen.scenarios).find(s=>s.family===j.family),engineFamily:j.engineFamily};
  assert.equal(digest(scenario),j.scenarioHash);
  const result=await pool.run({jobId:j.id,seed:r.seed,teams:j.teamKeys.map((key,i)=>({mechanics:frozen.profiles[key].mechanics,count:j.counts[i]})),
    scenario,disableAiOrders:true,disableKiting:true,preserveOwnerOrientation:true,retainSnapshots:false},180);
  assert.equal(result.result?.finalStateHash,r.finalStateHash);assert.equal(result.result?.eventLogHash,r.eventLogHash);assert.equal(result.result?.ticks,r.ticks);
  const outcome=result.result.outcome==='draw'?'draw':result.result.winnerOwner===2?'win':'loss';assert.equal(outcome,r.outcome);
  return {matchupId:j.id,seed:r.seed,family:j.family,sourceCampaignHash:r.campaignHash,finalStateHash:r.finalStateHash,eventLogHash:r.eventLogHash,exact:true};
}));const dir=new URL('../calibration/reports/civ-first-pass-parallel-2026-11-01/',import.meta.url);mkdirSync(dir,{recursive:true});
writeFileSync(new URL('worker-parity.json',dir),JSON.stringify({status:'passed',parallelWorkers:3,tests},null,2)+'\n');console.log(JSON.stringify({passed:tests.length,parallelWorkers:3}));
}finally{await pool.close();}
