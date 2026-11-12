#!/usr/bin/env node
// Test unchanged collection/movement rules across source-derived upgrade states.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {simulate,windowSummary} from './gold-mining-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out=path.resolve(process.argv[2]??path.join(root,'aoe2x/js_simulation/calibration/economy/gold-upgrade-comparison-2026-11-09'));
const read=name=>JSON.parse(fs.readFileSync(path.join(out,name)));
const write=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2)+'\n');
const mean=xs=>xs.reduce((s,n)=>s+n,0)/xs.length;
const fmt=(n,d=2)=>Number(n).toFixed(d);
const relative=(a,b)=>(a/b-1)*100;
const engineHash=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'tools/gold-mining-sim.mjs'))).digest('hex');
const prior=JSON.parse(fs.readFileSync(path.join(root,'aoe2x/js_simulation/calibration/economy/gold-2026-11-09/manifest.json')));
assert.equal(engineHash,prior.code_sha256['tools/gold-mining-sim.mjs'],'Comparison must use the unchanged engine');
const miningNames=['No mining upgrades','Gold Mining','Both mining upgrades'];
const carryNames=['No carry upgrades','Wheelbarrow','Wheelbarrow + Hand Cart'];
const grid=[],crowds=[],variations=[];const runs={};
for(let m=0;m<3;m++)for(let c=0;c<3;c++){
  const fixture=read(`fixture-m${m}-c${c}.json`);
  assert.deepEqual(fixture.upgrade_profile.tech_ids,[m>=1?55:null,m>=2?182:null,c>=1?213:null,c>=2?249:null].filter(x=>x!==null));
  const run=simulate(fixture,{workers:1,duration:300,trace:true});
  const intervals=run.events.slice(1).map((e,i)=>e.t-run.events[i].t);
  assert.ok(intervals.length>3);
  const rate=fixture.worker.carry_capacity*60/mean(intervals);
  const secondsPer10=600/rate;
  grid.push({mining_level:m,carry_level:c,mining:miningNames[m],carry:carryNames[c],
    tech_ids:fixture.upgrade_profile.tech_ids,source_work_rate:fixture.worker.work_rate,
    source_speed:fixture.worker.speed,source_capacity:fixture.worker.carry_capacity,
    reference_seconds_per_10:fixture.reference.seconds_per_10_gold,
    reference_rate:fixture.reference.gold_per_worker_minute,simulated_seconds_per_10:secondsPer10,
    simulated_cycle_rate:rate,rate_difference_percent:relative(rate,fixture.reference.gold_per_worker_minute),
    completed_cycles:intervals.length,checks:run.checks});
  console.log(`m${m}-c${c}`,fmt(rate),fmt(relative(rate,fixture.reference.gold_per_worker_minute),3)+'%');
  if(m===0&&c===0)runs['single-no-upgrades']=run;
}
const base=read('fixture-m0-c0.json');
assert.deepEqual(base.source.effects,[]);
assert.equal(base.worker.carry_capacity,10);
assert.ok(Math.abs(base.worker.speed-.8)<1e-6&&Math.abs(base.worker.work_rate-.38)<1e-6);
for(const [name,options] of [
  ['ten-no-upgrades-walk-only',{workers:10,collisions:false}],
  ['ten-no-upgrades',{workers:10}],['eight-no-upgrades',{workers:8}]]){
  const r=simulate(base,{duration:720,trace:true,...options});runs[name]=r;
  const windows=[[0,60],[120,420],[120,720]].map(([a,b])=>windowSummary(r,a,b));
  crowds.push({name,options:r.options,windows,checks:r.checks});
  // Export sampled logs and exact deposits for review without duplicating all
  // per-frame diagnostic counters in every trajectory record.
  write(name+'.json',{...r,frames:r.frames.map(f=>({t:f.t,banked:f.banked,carried:f.carried,remaining:f.remaining,
    agents:f.agents.map(w=>({id:w.id,x:w.x,y:w.y,state:w.state,inventory:w.inventory}))}))});
  console.log(name,fmt(windows[1].extracted_per_worker_minute),'(120–420s)');
}
write('single-no-upgrades.json',runs['single-no-upgrades']);
for(const dt of [.0125,.00625]){
  const rates=[];
  for(let seed=0;seed<10;seed++){
    const r=dt===.0125&&seed===0?runs['ten-no-upgrades']:simulate(base,{duration:420,dt,seed});
    rates.push({seed,...windowSummary(r,120,420)});
  }
  variations.push({dt,mean:mean(rates.map(r=>r.extracted_per_worker_minute)),
    min:Math.min(...rates.map(r=>r.extracted_per_worker_minute)),
    max:Math.max(...rates.map(r=>r.extracted_per_worker_minute)),rates});
}
const sources=[
  {title:'Forgotten Empires: Gold & Relics',url:base.reference.url,kind:'published_no_bumping_rate_table',
    usable_for:'Compare one-worker completed collection cycles across nine upgrade states.',
    limitation:'Patch unspecified; expressly excludes bumping; precise footprint/contact definition not specified.'},
  {title:'DE gold crowding test by akimbofmg9 (2020)',
    url:'https://www.reddit.com/r/aoe2/comments/hw06k7/villager_overcrowding_does_anyone_know_how_mining/',
    kind:'independent_in_game_measurement',workers:8,seconds:600,reported_rate_min:20,reported_rate_max:21.6,
    usable_for:'Independent qualitative crowding comparison: ten Arabia shapes plus a two-tile stress case; camp pre-built, workers pre-positioned.',
    limitation:'Layout differs; upgrade state and exact inventory-endpoint accounting are not explicit in the retrieved comment; rates are not a matched target for our square.'},
  {title:'Four-tile, ten-worker mining camp test (2025)',
    url:'https://www.reddit.com/r/aoe2/comments/1ibcnqu/where_to_place_your_mining_camp_and_how_many/',
    kind:'independent_in_game_measurement',workers:10,tiles:4,gap:1,reported_total:890,
    usable_for:'Confirms someone tested the same tile/worker counts and gap without mining/Wheelbarrow/Hand Cart upgrades.',
    limitation:'No duration or exact mine shape supplied. The 890-gold total cannot be converted to gold/minute.'},
  {title:'DE vs Voobly resource pathing test (2021)',
    url:'https://www.reddit.com/r/aoe2/comments/n3sb5f/vil_resource_pathing_is_better_on_de_than_voobly/',
    kind:'independent_in_game_measurement',workers:24,tiles:2,seconds:180,reported_total:836,
    normalized_rate:836/24/3,
    usable_for:'Additional severe-crowding observation, about 11.61 gold/worker-minute.',
    limitation:'Different worker count and patch geometry; camp count/placement and upgrades are not fully specified. Not simulated as a matched scenario.'},
];
const checks={source_base_parameters:true,all_nine_reference_cells:grid.length===9,
  all_reference_cycle_differences_under_one_percent:grid.every(g=>Math.abs(g.rate_difference_percent)<1),
  engine_unchanged_from_first_review:engineHash===prior.code_sha256['tools/gold-mining-sim.mjs'],
  all_conservation_checks_pass:[...grid,...crowds].every(r=>Math.abs(r.checks.conservation_error)<1e-6),
  all_collision_and_speed_checks_pass:[...grid,...crowds].every(r=>r.checks.max_overlap<1e-6&&r.checks.max_static_overlap<1e-6&&r.checks.max_speed_error<1e-6),
  mean_halving_step_change_percent:relative(variations[1].mean,variations[0].mean)};
checks.mean_convergence_under_one_percent=Math.abs(checks.mean_halving_step_change_percent)<1;
const comparison={source:base.source.game_source,engine_status:'Unchanged rigid-body prototype; external comparisons do not establish DE crowd fidelity.',
  grid,crowds,variations,sources,checks};
write('comparison.json',comparison);
const csv=['mining,carry,work_rate,speed,capacity,reference_gold_per_worker_minute,simulated_gold_per_worker_minute,difference_percent'];
for(const g of grid)csv.push([g.mining,g.carry,g.source_work_rate,g.source_speed,g.source_capacity,g.reference_rate,g.simulated_cycle_rate,g.rate_difference_percent].join(','));
fs.writeFileSync(path.join(out,'reference-grid.csv'),csv.join('\n')+'\n');
const cold=windowSummary(runs['ten-no-upgrades'],0,60);
const lines=['# Gold gathering without upgrades and reference comparisons','',
  'The engine is unchanged. Profile exports replay only selected source technology effects; no upgrades means 0.38 nominal gold/game-second, 0.8 tiles/game-second and carry 10. Civilization and team gathering bonuses are absent. Geometry/positions remain the same four-tile square and one-tile camp gap.','',
  '## Unupgraded results','',
  '| Case | Gold/worker/minute | Measurement |','|---|---:|---|',
  `| Forgotten Empires, no bumping | ${fmt(grid[0].reference_rate)} | 27.8 seconds per 10 gold |`,
  `| One worker | ${fmt(grid[0].simulated_cycle_rate)} | Completed deposit cycles |`,
  ...crowds.map(r=>`| ${r.name} | ${fmt(r.windows[1].extracted_per_worker_minute)} | Inventory-adjusted 120–420s |`),'',
  `The ten-worker first minute deposits **${fmt(cold.banked)} gold**, retains **${fmt(cold.carried_end)} gold carried**, and extracts **${fmt(cold.extracted)} gold**.`,``,
  '## All nine published upgrade combinations','',
  '[Forgotten Empires reference]('+base.reference.url+') supplies a 3×3 table of mining upgrades versus carry upgrades. Each row below is an independent one-worker simulation using the same engine and geometry; rates are computed from completed delivery cycles.','',
  '| Mining | Carry/movement | Reference | Simulation | Difference |','|---|---|---:|---:|---:|',
  ...grid.map(g=>`| ${g.mining} | ${g.carry} | ${fmt(g.reference_rate)} | ${fmt(g.simulated_cycle_rate)} | ${fmt(g.rate_difference_percent,3)}% |`),'',
  `Maximum absolute difference: **${fmt(Math.max(...grid.map(g=>Math.abs(g.rate_difference_percent))),3)}%**. This supports the mining/hauling arithmetic and contact-distance interpretation across upgrade states, rather than only at the fully upgraded point. The source is rounded to 0.1 second and its patch is unspecified; small differences should not be over-interpreted. It expressly excludes bumping.`,``,
  '## Independent measurements and comparability','',
  ...sources.slice(1).map(s=>`- [${s.title}](${s.url}): ${s.usable_for} **Limit:** ${s.limitation}`),'',
  `Our eight-worker square gives ${fmt(crowds.find(r=>r.name==='eight-no-upgrades').windows[1].extracted_per_worker_minute)} gold/worker-minute, below the independent 20–21.6 range. This is a warning that the current setup/model is more costly in walking and/or congestion. The layout, task assignments, game version and unspecified upgrade/endpoint details prevent assigning the entire difference to the collision model. No penalty, radius or work rate was adjusted to fit these reports.`,``,
  '## Longer window and timestep sensitivity','',
  '| Case | 120–420s, adjusted | 120–720s, adjusted | 120–720s, banked only | Depleted tiles at 720s |','|---|---:|---:|---:|---:|',
  ...crowds.map(r=>`| ${r.name} | ${fmt(r.windows[1].extracted_per_worker_minute)} | ${fmt(r.windows[2].extracted_per_worker_minute)} | ${fmt(r.windows[2].banked_per_worker_minute)} | ${r.windows[2].depleted_tiles} |`),'',
  '| Step | Ten-order-variant mean | Minimum | Maximum |','|---|---:|---:|---:|',
  ...variations.map(v=>`| ${v.dt}s | ${fmt(v.mean,4)} | ${fmt(v.min,4)} | ${fmt(v.max,4)} |`),'',
  `Halving the timestep changes the ten-variant mean by ${fmt(checks.mean_halving_step_change_percent,3)}%. This is a numerical-sensitivity check, not validation against DE. Resource conservation, speed limits and rigid-body non-overlap pass for these runs.`,``,
  '## Reproduce','',
  '```sh','python tools/export_gold_mining_fixture.py --grid-output aoe2x/js_simulation/calibration/economy/gold-upgrade-comparison-2026-11-09',
  'node tools/run_gold_upgrade_comparison.mjs','```','',
  'The folder includes nine frozen fixtures, the full reference grid, three crowd traces, the single-worker trace, comparisons and source metadata. The prior fully upgraded experiment remains at `../gold-2026-11-09/`.'];
fs.writeFileSync(path.join(out,'README.md'),lines.join('\n')+'\n');
write('manifest.json',{created_at:new Date().toISOString(),source:base.source.game_source,
  code_sha256:Object.fromEntries(['tools/gold-mining-sim.mjs','tools/export_gold_mining_fixture.py','tools/run_gold_upgrade_comparison.mjs'].map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')])),
  fixture_sha256:Object.fromEntries(grid.map(g=>{const name=`fixture-m${g.mining_level}-c${g.carry_level}.json`;return [name,crypto.createHash('sha256').update(fs.readFileSync(path.join(out,name))).digest('hex')];})),
  sources,engine_modified:false,assumptions:base.assumptions});
console.log(JSON.stringify(checks,null,2));
