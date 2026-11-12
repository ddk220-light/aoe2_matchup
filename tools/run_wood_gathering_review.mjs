#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {simulateWood,woodWindow} from './wood-gathering-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out=path.resolve(process.argv[2]??path.join(root,'aoe2x/js_simulation/calibration/economy/wood-2026-11-09'));
const fixture=(w,c)=>JSON.parse(fs.readFileSync(path.join(out,`fixture-w${w}-c${c}.json`)));
const write=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2)+'\n');
const fmt=(v,n=2)=>Number(v).toFixed(n),mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const profiles=[],trials=[],runs={};
for(let w=0;w<4;w++)for(let c=0;c<3;c++){
 const f=fixture(w,c),r=simulateWood(f,{workers:1,duration:720});
 const row={wood_level:w,carry_level:c,source_work_rate:f.worker.work_rate,source_speed:f.worker.speed,
  source_carry:f.worker.carry_capacity,nominal_wood_per_minute:f.worker.work_rate*60,
  first:woodWindow(r,0,60),middle:woodWindow(r,120,420),late:woodWindow(r,420,720),checks:r.checks};
 profiles.push(row);console.log('profile',w,c,fmt(row.middle.inventory_adjusted_per_worker_minute));
}
const specs=[
 ['none-ten',0,0,{workers:10,trace:true}],['full-ten',3,2,{workers:10,trace:true}],
 ['none-ten-walking',0,0,{workers:10,collisions:false}],['full-ten-walking',3,2,{workers:10,collisions:false}],
 ['bow-saw-ten',2,2,{workers:10}],
 ['none-twelve-three-minutes',0,0,{workers:12,duration:180}],
 ['double-bit-four-adjacent',1,0,{workers:4,gap:0,duration:840}],
 ['full-four-adjacent',3,2,{workers:4,gap:0,duration:840,trace:true}],
 ['double-bit-four-gap-one',1,0,{workers:4,gap:1,duration:840}],
 ['full-four-gap-one',3,2,{workers:4,gap:1,duration:840}],
 ['full-ten-historical-felling',3,2,{workers:10,attackPeriod:1.5,firstHitDelay:.75}],
 ['full-ten-prefelled',3,2,{workers:10,preFelled:true}],
];
for(const [name,w,c,opts] of specs){
 const r=simulateWood(fixture(w,c),{duration:720,...opts});runs[name]=r;
 const windows=[[0,60],...(r.options.duration>=420?[[120,420]]:[]),...(r.options.duration>=720?[[420,720],[120,720]]:[]),[0,r.options.duration]];
 const row={name,options:r.options,profile:{wood_level:w,carry_level:c},checks:r.checks,
  windows:windows.map(([a,b])=>woodWindow(r,a,b))};
 trials.push(row);
 write(name+'.json',{...r,frames:r.frames.map(f=>({...f,agents:f.agents.map(w=>({id:w.id,x:w.x,y:w.y,state:w.state,inventory:w.inventory}))}))});
 console.log(name,fmt(row.windows.at(-1).inventory_adjusted_per_worker_minute));
}
const sensitivity=[];
for(const [w,c] of [[0,0],[3,2]])for(const dt of [.025,.0125,.00625]){
 const rates=[];
 for(let seed=0;seed<3;seed++){
  const r=dt===.0125&&seed===0?runs[w?'full-ten':'none-ten']:simulateWood(fixture(w,c),{duration:420,dt,seed});
  rates.push({seed,...woodWindow(r,120,420)});
 }
 sensitivity.push({wood_level:w,carry_level:c,dt,mean:mean(rates.map(r=>r.inventory_adjusted_per_worker_minute)),rates});
 console.log('timestep',w,dt,fmt(sensitivity.at(-1).mean,4));
}
const sources=[
 {title:'2025 wood gathering experiment',url:'https://www.reddit.com/r/aoe2/comments/1ilig6h/i_did_the_math_food_is_40_more_valuable_than_wood/',
  kind:'independent_in_game_measurement',workers:12,camps:3,minutes:14,double_bit_rate:23.5,full_rate:31.6,
  limitations:'Forest shape, initial gap, technology completion timing and final inventory handling not specified. Four workers/camp matches density, not exact geometry. Compare gross 31.6, not the derived 30.1 net of camp investments.'},
 {title:'2019 real wood gathering analysis',url:'https://www.reddit.com/r/aoe2/comments/fes2fb/real_wood_gathering_rate_analysis/',
  kind:'analytical_reference',full_rate:.507*60,no_two_man_saw_rate:.472*60,
  limitations:'Older analysis, light congestion, different/unspecified geometry and observation horizon; not an exact current DE test.'},
 {title:'2021 DE vs Voobly gathering experiment',url:'https://www.reddit.com/r/aoe2/comments/n3sb5f/vil_resource_pathing_is_better_on_de_than_voobly/',
  kind:'independent_in_game_measurement',workers:12,camps:1,seconds:180,total_wood:754,rate:754/12/3,
  limitations:'Exact woodline, upgrades and final carried-inventory handling not fully specified; no-upgrade branch is a diagnostic assumption.'},
 {title:'2021 DE Infosheet: felling mechanics',url:'https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705',
  kind:'historical_mechanics_measurement',felling_seconds:2.25,
  limitations:'Reports 1.5-second lumberjack attack animation. Current supplied DAT has 2-second animations and 2-second reload, so current impact timing is uncertain. Historical timing tested separately.'},
];
const numerical=sensitivity.filter(s=>s.dt===.0125).map(s=>{
 const fine=sensitivity.find(v=>v.wood_level===s.wood_level&&v.dt===.00625);
 return {wood_level:s.wood_level,mean_halving_step_change_percent:(fine.mean/s.mean-1)*100};
});
const comparison={profiles,trials,sensitivity,numerical,sources,status:'Source-backed prototype; actual current DE woodline behavior not validated.'};
write('comparison.json',comparison);
const csv=['case,workers,wood_level,carry_level,start,end,banked,carried_start,carried_end,extracted,wood_per_worker_minute,working_percent,felling_percent,walking_percent,blocked_percent,depleted_trees'];
for(const t of trials)for(const w of t.windows)csv.push([t.name,w.workers,t.profile.wood_level,t.profile.carry_level,w.start,w.end,w.banked,w.carried_start,w.carried_end,w.extracted,w.inventory_adjusted_per_worker_minute,w.working_percent,w.felling_percent,w.walking_percent,w.blocked_percent,w.depleted_trees].join(','));
fs.writeFileSync(path.join(out,'results.csv'),csv.join('\n')+'\n');
const get=(name,a,b)=>trials.find(t=>t.name===name).windows.find(w=>w.start===a&&w.end===b);
const lines=['# Wood gathering simulation and reference comparison','',
 '**Prototype model estimate; current-DE same-layout gathering has not been validated.**','',
 'Source is the supplied DAT (SHA-256 `'+fixture(0,0).source.game_source.sha256+'`). No civilization bonuses. Standard full upgrades are Double-Bit Axe, Bow Saw, Two-Man Saw, Wheelbarrow and Hand Cart; Sappers is excluded.','',
 'Default scenario: one 2×2 Lumber Camp, one empty tile from an eight-wide/six-deep forest of 48 oak trees. Each tree has source HP 20, 100 wood and a 1×1 footprint. Ten workers initially stand along the front edge. The camp stays fixed and depleted trees disappear, exposing deeper trees.','',
 '## Main results','',
 '| Profile | Active-work ceiling | First minute, adjusted | Minutes 2–7 | Minutes 7–12 |','|---|---:|---:|---:|---:|',
 ...[['No upgrades','none-ten',0,0],['All standard upgrades','full-ten',3,2]].map(([label,name,w,c])=>`| ${label} | ${fmt(fixture(w,c).worker.work_rate*60)} | ${fmt(get(name,0,60).inventory_adjusted_per_worker_minute)} | ${fmt(get(name,120,420).inventory_adjusted_per_worker_minute)} | ${fmt(get(name,420,720).inventory_adjusted_per_worker_minute)} |`),'',
 'Units: wood per worker per game-minute. Rates count banked wood plus changes in carried inventory; carried wood is not yet spendable. Active-work ceilings exclude felling and all movement and are not delivered-rate predictions.','',
 '| Profile, first minute | Banked wood | Still carried | Wood removed from trees |','|---|---:|---:|---:|',
 ...[['No upgrades','none-ten'],['All upgrades','full-ten']].map(([label,n])=>{const w=get(n,0,60);return `| ${label} | ${fmt(w.banked)} | ${fmt(w.carried_end)} | ${fmt(w.extracted)} |`;}),'',
 '## Crowding, felling and recession diagnostics','',
 '| Case | Minutes 2–7 | Minutes 7–12 |','|---|---:|---:|',
 ...trials.filter(t=>t.options.duration>=720).map(t=>`| ${t.name} | ${fmt(get(t.name,120,420).inventory_adjusted_per_worker_minute)} | ${fmt(get(t.name,420,720).inventory_adjusted_per_worker_minute)} |`),'',
 'Pre-felled trees and historical felling timing are labelled diagnostics. Felling lowers HP without harvesting; collecting depletes the separate wood store. Workers with partial loads keep them when moving to a new tree.','',
 'Current DAT attack: 15 total damage against armor-less trees, reload 2 seconds, animation 2 seconds, coded frame_delay 0. The default assumes the first hit at half animation (1s), then a second hit after reload (total 3s). The precise worker-task impact timing is unresolved. Historical 2.25s felling and no-felling runs show sensitivity rather than silently replacing current inputs.','',
 '## Published comparisons','',
 '| Reference | Published wood/worker/min | Our related case | Model value | Comparability |','|---|---:|---|---:|---|',
 `| [2025 test](${sources[0].url}), Double-Bit Axe | 23.50 | 4/camp, adjacent, 14min | ${fmt(get('double-bit-four-adjacent',0,840).inventory_adjusted_per_worker_minute)} | Density/horizon match; forest/gap/other upgrades unspecified |`,
 `| [2025 test](${sources[0].url}), fully upgraded | 31.60 | 4/camp, adjacent, 14min | ${fmt(get('full-four-adjacent',0,840).inventory_adjusted_per_worker_minute)} | Same limits; gross output comparison |`,
 `| [2025 test](${sources[0].url}), Double-Bit Axe | 23.50 | 4/camp, one-tile gap, 14min | ${fmt(get('double-bit-four-gap-one',0,840).inventory_adjusted_per_worker_minute)} | Camp gap is a scenario assumption, not specified by source |`,
 `| [2025 test](${sources[0].url}), fully upgraded | 31.60 | 4/camp, one-tile gap, 14min | ${fmt(get('full-four-gap-one',0,840).inventory_adjusted_per_worker_minute)} | Same limits |`,
 `| [2019 analysis](${sources[1].url}), fully upgraded | 30.42 | 10/camp, minutes 2–12 | ${fmt(get('full-ten',120,720).inventory_adjusted_per_worker_minute)} | Older light-congestion analytical estimate |`,
 `| [2019 analysis](${sources[1].url}), no Two-Man Saw | 28.32 | Bow Saw + Hand Cart, minutes 2–12 | ${fmt(get('bow-saw-ten',120,720).inventory_adjusted_per_worker_minute)} | Same limits |`,
 `| [2021 DE test](${sources[2].url}), 12/camp, 3min | ${fmt(sources[2].rate)} | 12/camp, 3min, assumed no upgrades | ${fmt(get('none-twelve-three-minutes',0,180).inventory_adjusted_per_worker_minute)} | Exact upgrades/layout/endpoint carry unspecified |`,'',
 'These are independent references, not matching DE scenarios. The four-worker one-tile-gap alternatives are exported too; changing camp placement changes the result. No work, movement, collision or delay parameter was adjusted to fit reference values.','',
 '## Twelve upgrade combinations: one worker','',
 '| Wood level | Carry level | Nominal | Minutes 2–7 | Minutes 7–12 |','|---|---|---:|---:|---:|',
 ...profiles.map(p=>`| ${p.wood_level} | ${p.carry_level} | ${fmt(p.nominal_wood_per_minute)} | ${fmt(p.middle.inventory_adjusted_per_worker_minute)} | ${fmt(p.late.inventory_adjusted_per_worker_minute)} |`),'',
 'Wood levels: 0 none, 1 Double-Bit Axe, 2 +Bow Saw, 3 +Two-Man Saw. Carry levels: 0 none, 1 Wheelbarrow, 2 +Hand Cart. Nominal gathering multiplies by 1.2, 1.2, 1.1; carry rounds after each selected upgrade.','',
 '## Numerical sensitivity','',
 '| Profile | Step | Mean over three update-order variants |','|---|---:|---:|',
 ...sensitivity.map(s=>`| ${s.wood_level===0?'No upgrades':'Full'} | ${s.dt} | ${fmt(s.mean,4)} |`),'',
 ...numerical.map(n=>`${n.wood_level===0?'No upgrades':'Full'}: mean change when halving 0.0125s to 0.00625s = ${fmt(n.mean_halving_step_change_percent,3)}%.`),'',
 'Checks enforce wood conservation, speed limits, rectangular obstacle exclusion and rigid worker non-overlap. Unit tests cover source upgrade values, felling before gathering, nominal collection, tree depletion, partial loads and deterministic behavior.','',
 '## Assumptions','',...fixture(0,0).assumptions.map(s=>'- '+s),'',
 '## Files and reproduction','',
 '`fixture-w*-c*.json` contain source technology evidence and raw inputs; `felling-source.json` includes the fresh DAT attack/animation subset. `comparison.json` and `results.csv` hold all results. Trace files record positions, tree HP/wood, inventories, swings, tree depletion and deposit events.','',
 '```sh','/workspace/scratch/production-effects-trace/.venv/bin/python tools/extract_wood_felling_source.py',
 'python tools/export_wood_gathering_fixtures.py','node tools/wood-gathering-sim.test.mjs','node tools/run_wood_gathering_review.mjs','```'];
fs.writeFileSync(path.join(out,'README.md'),lines.join('\n')+'\n');
write('manifest.json',{created_at:new Date().toISOString(),source:fixture(0,0).source.game_source,sources,
 assumptions:fixture(0,0).assumptions,code_sha256:Object.fromEntries(['tools/gold-mining-sim.mjs','tools/wood-gathering-sim.mjs',
 'tools/extract_wood_felling_source.py','tools/export_wood_gathering_fixtures.py','tools/run_wood_gathering_review.mjs','tools/wood-gathering-sim.test.mjs']
 .map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]))});
console.log('complete',numerical);
