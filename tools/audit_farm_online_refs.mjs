// Compare the unchanged model with published in-game observations.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {simulateFarms} from './farm-gathering-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out=path.resolve(process.argv[2]??path.join(root,'aoe2x/js_simulation/calibration/economy/farms-2026-11-09'));
const read=n=>JSON.parse(fs.readFileSync(path.join(out,n)));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const enginePath=path.join(root,'tools/farm-gathering-sim.mjs'),engineHash=sha(enginePath);
if(engineHash!==read('manifest.json').code['tools/farm-gathering-sim.mjs'])throw new Error('Engine differs from original review');
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const source='https://www.reddit.com/r/aoe2/comments/18l91t2/did_some_farm_testing_wheelbarrow_math/';
// TC physical/drop-contact approximation: 4x4 outer box from raw unit 109.
// Only its east face is used. Annex collision/passability is not reconstructed.
const mill={x0:0,x1:4,y0:0,y1:4};
const farms=[{id:0,x0:4,x1:7,y0:0,y1:3,position:'near'},
 {id:1,x0:7,x1:10,y0:0,y1:3,position:'outer'}];
const cases=[],rawRuns=[];
for(const [profile,food,times,ids] of [
 ['none',175,[491,617],[]],
 ['wheelbarrow',250,[663,779],[14,213]],
 ['full',375,[937,956],[14,213,13,249]],
]){
 const f=read(`fixture-${profile}.json`);
 const full=read('fixture-full.json');
 f.name=`reference-lifetime-${profile}`;f.technology_ids=ids;
 f.source.farm_capacity_effects=full.source.farm_capacity_effects.filter(e=>ids.includes(e.tech_id));
 const sourceFood=175+f.source.farm_capacity_effects.reduce((s,e)=>s+e.command.d,0);
 if(sourceFood!==food)throw new Error('Reference food budget does not match DAT effects');
 f.farm.food=food;
 f.source.scenario_override='Two farms on east side of approximate TC outer box; no bonus changes';
 fs.writeFileSync(path.join(out,`reference-fixture-${profile}.json`),JSON.stringify(f,null,2)+'\n');
 const results=[];
 for(let seed=0;seed<5;seed++){
  const r=simulateFarms(f,{duration:1300,mill,farms,trace:true,seed,reseed:false});
  const perFarm=[0,1].map(id=>{
   if(Math.abs(r.final.agents[id].harvested-food)>1e-6)throw new Error('Reference farm did not deplete');
   const end=r.events.find(e=>e.worker===id&&e.event==='depleted');
   const finalDeposit=r.events.filter(e=>e.worker===id&&e.event==='deposit').at(-1);
   return {id,depletion_seconds:end.t,final_deposit_seconds:finalDeposit.t,food_per_minute:food*60/end.t};
  });
  results.push(perFarm);
  rawRuns.push({profile,seed,options:r.options,per_farm:perFarm,checks:r.checks});
 }
 for(let id=0;id<2;id++){
  const observed=food*60/times[id],rates=results.map(r=>r[id].food_per_minute),predicted=mean(rates);
  cases.push({profile,position:id?'outer':'near',food,reference_seconds:times[id],reference_rate:observed,
   model_rate:predicted,model_seconds:mean(results.map(r=>r[id].depletion_seconds)),
   seed_min:Math.min(...rates),seed_max:Math.max(...rates),difference_percent:(predicted/observed-1)*100});
 }
 // Unknown source pre-task idle time may have filled the food pool. Keep this
 // separate instead of choosing whichever initial condition fits the source.
 const warm=simulateFarms(f,{duration:1300,mill,farms,trace:true,seed:0,reseed:false,initialPool:15});
 rawRuns.push({profile,seed:0,diagnostic:'initial_pool_15',options:warm.options,checks:warm.checks,
  per_farm:[0,1].map(id=>{const e=warm.events.find(e=>e.worker===id&&e.event==='depleted');return {id,depletion_seconds:e.t,food_per_minute:food*60/e.t};})});
}
const original=read('comparison.json');
const broad=original.summaries.map(s=>{
 const observed={none:20.3,wheelbarrow:22.78,'wheelbarrow-plow':23.16,full:24.4}[s.profile];
 const w=s.windows.find(w=>w.start===0&&w.end===600);
 return {profile:s.profile,reference:observed,model_harvested:w.food_per_worker_minute,
  model_banked:w.banked_per_worker_minute,difference_percent:(w.food_per_worker_minute/observed-1)*100};
});
const limitations=[
 'Reference is a single reported pair per upgrade level, not a published distribution or shared scenario.',
 'Exact farm alignment, initial villager positions, civilization, pre-task idle duration, and executable build are unspecified. Scenario Editor mode is reported.',
 'Our comparison uses east-side farms and the source TC outer box as a solid drop-contact proxy. TC annexes/passability and exact game deposit contact are not reconstructed.',
 'Default initial pool is zero; separate full-pool diagnostics expose sensitivity to pre-task idle time.',
 'Rates are recomputed from reported depletion times and standard DAT food budgets; some rounded rates in the post disagree with its times.',
 'Our endpoint is depletion, before final partial-load deposit, matching the stated measurement as closely as possible.',
 'The original ten-farm mill results remain unchanged. Similar output does not prove internal movement or civilization modifiers are correct.'
];
const result={engine_sha256:engineHash,source,cases,runs:rawRuns,broad_comparison:broad,limitations,
 independent_checks:[
  {url:'https://steamcommunity.com/sharedfiles/filedetails/?id=1932327114',kind:'2019/2020 DE experiment',conditions:'8 farms around TC, 10min, warm-up and forced endpoint deposit; older farm placement mechanics, no ordinary reseeding. Broad comparison only.'},
  {url:'https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/183',kind:'2025 reported game testing',farm_rates:{base:20.07,wheelbarrow_horse_collar:22.34,hand_cart_heavy_plow:23.62},conditions:'Measured over pasture lifecycle; farm layout, endpoint inventories, farm reseeding and generic civ not specified. Context only, not an exact match.'},
  {url:'https://www.reddit.com/r/aoe2/comments/1ipzw3v/nevermind_the_farming_cap_is_still_24_never/',kind:'2025 multiplayer follow-up',finding:'Supports approximately 24 food/min generic farm production cap; retracts higher single-player rates.'}
 ]};
if(sha(enginePath)!==engineHash)throw new Error('Engine changed during audit');
fs.writeFileSync(path.join(out,'online-validation.json'),JSON.stringify(result,null,2)+'\n');
const lines=['# Farm model comparison with actual online game tests','',
 'The model was rerun in a reference-shaped two-farm scenario without changing its mechanics or fitting parameters. These are partial replications because the source does not provide its scenario or exact initial conditions.','',
 `## Near versus outer farm: [December 2023 game test](${source})`,'',
 'One farm adjacent to a Town Center, another directly outside it. End measurement when each farm empties. Model values are means of five seeds. Food per farmer per game-minute.','',
 '| Upgrades | Farm | Published depletion time | Online rate, recomputed | Model rate | Difference |','|---|---|---:|---:|---:|---:|',
 ...cases.map(r=>`| ${{none:'None',wheelbarrow:'Wheelbarrow + Horse Collar',full:'Hand Cart + Heavy Plow'}[r.profile]} | ${r.position} | ${Math.floor(r.reference_seconds/60)}:${String(r.reference_seconds%60).padStart(2,'0')} | ${r.reference_rate.toFixed(2)} | ${r.model_rate.toFixed(2)} | ${r.difference_percent.toFixed(1)}% |`),'',
 ...limitations.map(s=>'- '+s),'',
 '## Original ten-farm mill versus older eight-farm TC benchmark','',
 '[The 2019/2020 Steam experiment](https://steamcommunity.com/sharedfiles/filedetails/?id=1932327114) is actual DE testing, but differs in geometry, initialization, reseeding and patch. These differences are not isolated simulation error.','',
 '| Profile | Published | Our harvested, first 10min | Our banked, first 10min | Harvested difference |','|---|---:|---:|---:|---:|',
 ...broad.map(r=>`| ${r.profile} | ${r.reference.toFixed(2)} | ${r.model_harvested.toFixed(2)} | ${r.model_banked.toFixed(2)} | ${r.difference_percent.toFixed(1)}% |`),'',
 'The source forces an endpoint deposit, so our harvested column is more comparable to its resource accounting than our unflushed banked column. Layout and maintenance still differ materially.','',
 '## Additional independent observations','',
 '[June 2025 forum tests](https://forums.ageofempires.com/t/how-to-nerf-khitans/275361/183) report farm rates of 20.07 base, 22.34 with Wheelbarrow + Horse Collar, and 23.62 with Hand Cart + Heavy Plow. The farm setup is insufficiently specified for matched error calculations. They support the general scale; they do not validate the ten-farm mill arrangement.','',
 '[February 2025 multiplayer testing](https://www.reddit.com/r/aoe2/comments/1ipzw3v/nevermind_the_farming_cap_is_still_24_never/) supports the roughly 24/min cap. Its author withdrew higher single-player results as a multiplayer benchmark. Other simulators such as AoEBuddy are excluded as independent DE measurements.','',
 'Conclusion: upgraded output and the reduction of the outer-farm penalty are supported by measured game results. The unupgraded discrepancy remains visible. No exact ten-farm mill recording was found; exact work-stop policy and collision/deposit behavior remain unvalidated.',''];
fs.writeFileSync(path.join(out,'online-validation.md'),lines.join('\n'));
console.log(JSON.stringify(cases,null,2));
