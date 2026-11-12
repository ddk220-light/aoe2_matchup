#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {simulate,windowSummary} from './gold-mining-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output=path.resolve(process.argv[2]??path.join(root,'aoe2x/js_simulation/calibration/economy/gold-2026-11-09'));
fs.mkdirSync(output,{recursive:true});
const fixture=JSON.parse(fs.readFileSync(path.join(output,'fixture.json')));
const write=(name,data)=>fs.writeFileSync(path.join(output,name),JSON.stringify(data,null,2)+'\n');
const mean=a=>a.reduce((s,n)=>s+n,0)/a.length;
const pct=(a,b)=>(a/b-1)*100;
const fmt=(n,d=2)=>Number(n).toFixed(d);
const ref=fixture.reference.gold_per_worker_minute;
const trials=[
  ['uninterrupted',{workers:1,duration:60,carry:1000}],
  ['single-worker',{workers:1,trace:true}],
  ['ten-walk-only',{workers:10,collisions:false,trace:true}],
  ['ten-workers',{workers:10,trace:true}],
  ['five-workers',{workers:5}],['fifteen-workers',{workers:15}],
  ['gap-zero',{gap:0}],['gap-two',{gap:2}],
  ['fractional-carry',{carry:fixture.worker.unrounded_carry}],
];
const runs={},results=[];
for(const [name,opts] of trials){
  const run=simulate(fixture,opts);runs[name]=run;
  const windows=[[0,60],...(run.options.duration>=420?[[120,180],[120,420]]:[])].map(([a,b])=>windowSummary(run,a,b));
  let cycles=[];
  if(name==='single-worker')cycles=run.events.slice(1).map((e,i)=>e.t-run.events[i].t);
  const r={name,options:run.options,checks:run.checks,windows,
    completed_cycle_gold_per_worker_minute:cycles.length?fixture.worker.carry_capacity*60/mean(cycles):null};
  results.push(r);console.log(name,fmt(windows.at(-1).extracted_per_worker_minute));
  write(name+'.json',run.frames.length?run:{...run,frames:[],events:[]});
}
const sensitivity=[];
for(const dt of [.1,.05,.025,.0125,.00625]){
  const rates=[];
  for(let seed=0;seed<10;seed++){
    const run=dt===.0125&&seed===0?runs['ten-workers']:simulate(fixture,{dt,seed});
    const summary=windowSummary(run,120,420);
    rates.push({seed,rate:summary.extracted_per_worker_minute,banked_rate:summary.banked_per_worker_minute,checks:run.checks});
  }
  sensitivity.push({dt,rates,mean:mean(rates.map(r=>r.rate)),min:Math.min(...rates.map(r=>r.rate)),max:Math.max(...rates.map(r=>r.rate))});
  console.log('timestep',dt,fmt(sensitivity.at(-1).mean,4));
}
const coarse=sensitivity.at(-2),fine=sensitivity.at(-1);
const delta=pct(fine.mean,coarse.mean);
const maxSeedDelta=Math.max(...fine.rates.map((r,i)=>Math.abs(pct(r.rate,coarse.rates[i].rate))));
const compare={reference:fixture.reference,results,sensitivity,
  comparison:{single_cycle_rate:results.find(r=>r.name==='single-worker').completed_cycle_gold_per_worker_minute,
    single_cycle_difference_percent:pct(results.find(r=>r.name==='single-worker').completed_cycle_gold_per_worker_minute,ref),
    crowded_rate:windowSummary(runs['ten-workers'],120,420).extracted_per_worker_minute,
    crowded_difference_from_reference_percent:pct(windowSummary(runs['ten-workers'],120,420).extracted_per_worker_minute,ref),
    congestion_loss_percent:-pct(windowSummary(runs['ten-workers'],120,420).extracted_per_worker_minute,windowSummary(runs['ten-walk-only'],120,420).extracted_per_worker_minute)},
  numerical_checks:{fine_step_change_of_10_variant_mean_percent:delta,max_paired_variant_change_percent:maxSeedDelta,
    mean_convergence_below_one_percent:Math.abs(delta)<1,
    individual_variants_below_one_percent:maxSeedDelta<1},
  validation_status:'Reference plausibility comparison only; no matching current-DE capture.',
  assumptions:fixture.assumptions};
write('comparison.json',compare);
const csv=['trial,start_seconds,end_seconds,workers,banked_gold,carried_start,carried_end,extracted_gold,banked_per_worker_minute,inventory_adjusted_per_worker_minute,working_percent,walking_percent,blocked_percent,depleted_tiles'];
for(const r of results)for(const w of r.windows)csv.push([r.name,w.start,w.end,w.workers,w.banked,w.carried_start,w.carried_end,w.extracted,w.banked_per_worker_minute,w.extracted_per_worker_minute,w.working_percent,w.walking_percent,w.blocked_percent,w.depleted_tiles].join(','));
fs.writeFileSync(path.join(output,'results.csv'),csv.join('\n')+'\n');
const manifest={created_at:new Date().toISOString(),source:fixture.source.game_source,assumptions:fixture.assumptions,
  runtime:process.version,reproduce:['python tools/export_gold_mining_fixture.py','node tools/gold-mining-sim.test.mjs','node tools/run_gold_mining_review.mjs'],
  code_sha256:Object.fromEntries(['tools/gold-mining-sim.mjs','tools/run_gold_mining_review.mjs','tools/export_gold_mining_fixture.py','tools/gold-mining-sim.test.mjs'].map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]))};
write('manifest.json',manifest);
const single=results.find(r=>r.name==='single-worker'),crowd=windowSummary(runs['ten-workers'],120,420),cold=windowSummary(runs['ten-workers'],0,60);
const lines=['# Generic post-Imperial gold mining: first simulation','',
  '**Model estimate. No matching current-DE gathering capture has been validated.**','',
  'Ten villagers, four 800-gold tiles in a 2×2 square, one 2×2 Mining Camp separated by a one-tile gap, all standard mining/movement/carry upgrades. Source values are from the user-supplied DAT (SHA-256 `'+fixture.source.game_source.sha256+'`).','',
  '## Reference comparison','',
  'The [Forgotten Empires reference]('+fixture.reference.url+') gives 20.5 seconds per 10 gold, or **'+fmt(ref)+' gold per villager-minute**, one tile from the camp with Gold Shaft Mining and Hand Cart. It excludes bumping and does not identify its patch or precise geometry.','',
  '| Case | Gold/villager/minute | Difference from reference |',
  '|---|---:|---:|',
  '| Reference, no bumping | '+fmt(ref)+' | — |',
  '| One simulated worker, completed delivery cycles | '+fmt(single.completed_cycle_gold_per_worker_minute)+' | '+fmt(compare.comparison.single_cycle_difference_percent)+'% |',
  '| Ten workers, walking only, inventory-adjusted 120–420s | '+fmt(windowSummary(runs['ten-walk-only'],120,420).extracted_per_worker_minute)+' | '+fmt(pct(windowSummary(runs['ten-walk-only'],120,420).extracted_per_worker_minute,ref))+'% |',
  '| Ten workers, with rigid-body collisions, inventory-adjusted 120–420s | '+fmt(crowd.extracted_per_worker_minute)+' | '+fmt(pct(crowd.extracted_per_worker_minute,ref))+'% |','',
  'The single-worker cycle is derived from source work, rounded carry 20 and a 0.6-tile center travel each way at 0.968 tiles/second. There is no fitted rate multiplier. Agreement checks this model’s uncongested cycle; it does not validate DE crowd navigation. The four-tile setup adds walking around the patch and simulated congestion.','',
  '## Requested first minute','',
  '| Time window | Deposited | Carried at start | Carried at end | Gold extracted |','|---|---:|---:|---:|---:|',
  ...[[0,60],[120,180],[120,420]].map(([a,b])=>{const w=windowSummary(runs['ten-workers'],a,b);return `| ${a}–${b} seconds | ${fmt(w.banked)} | ${fmt(w.carried_start)} | ${fmt(w.carried_end)} | ${fmt(w.extracted)} |`;}),'',
  'For the 120–420s window, deposited gold alone gives '+fmt(crowd.banked_per_worker_minute)+' per worker-minute. Its carried inventory changes by '+fmt(crowd.carried_delta)+' gold, so the inventory-adjusted rate is '+fmt(crowd.extracted_per_worker_minute)+'. Both quantities are reported: carried gold is not spendable until deposited. The adjusted rate controls load-cycle endpoint bias; it is not the banked amount at a deadline.','',
  'Time shares for ten workers over 120–420s: working '+fmt(crowd.working_percent)+'%, walking '+fmt(crowd.walking_percent)+'%, blocked '+fmt(crowd.blocked_percent)+'%. Enabling collisions changes both path length and blocked time; the total reduction versus the walking-only run is '+fmt(compare.comparison.congestion_loss_percent)+'%.','',
  '## Diagnostics','',
  '| Case | Inventory-adjusted gold/villager/minute, 120–420s | Depleted tiles at end |','|---|---:|---:|',
  ...results.filter(r=>r.options.duration>=420).map(r=>{const w=r.windows.at(-1);return `| ${r.name} | ${fmt(w.extracted_per_worker_minute)} | ${w.depleted_tiles} |`;}),'',
  'The fifteen-worker trial includes depletion and retargeting, so its complete-window rate also reflects changed resource geometry. The gap-zero trial starts workers in legal positions around the accessible sides; initial geometry differs from the baseline.','',
  '## Numerical sensitivity','',
  '| Timestep (game seconds) | Mean over ten initial-order variants | Minimum | Maximum |','|---|---:|---:|---:|',
  ...sensitivity.map(s=>`| ${s.dt} | ${fmt(s.mean,4)} | ${fmt(s.min,4)} | ${fmt(s.max,4)} |`),'',
  'The default is 0.0125 seconds (80 Hz), selected after testing timestep sensitivity. Halving it changes the ten-variant mean by '+fmt(delta,3)+'%. The largest change within a paired variant is '+fmt(maxSeedDelta,3)+'%; individual path interactions remain sensitive. These variants change initial update order/target ties, not the assumed work rate or DE RNG.','',
  'Resource conservation, speed limits, static-obstacle exclusion, rigid-body non-overlap, full-load timing, deterministic replay, analytic single-worker cycle and finite-resource depletion are checked. Test output is in `test-results.txt`.','',
  '## Model assumptions and remaining fidelity limits','',
  ...fixture.assumptions.map(a=>'- '+a),'',
  'The [DE Infosheet](https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705) provides historical support for effective carry 20; current rounding still needs a matched capture. The [four-tile community test](https://www.reddit.com/r/aoe2/comments/1ibcnqu/where_to_place_your_mining_camp_and_how_many/) uses ten workers and a one-tile gap but explicitly no upgrades and no stated duration; it supplies no comparable rate.','',
  '## Files','',
  '- `playback.html`: standalone animation with timeline, worker states, inventory, reference table and diagnostic plots.',
  '- `fixture.json`: source-derived inputs, technology evidence, geometry and assumptions.',
  '- `ten-workers.json`, `single-worker.json`, `ten-walk-only.json`: sampled trajectories, bank/inventory histories and exact deposit events.',
  '- `comparison.json`, `results.csv`: full trial windows, numerical comparisons and checks.',
  '- `manifest.json`: source identity, code hashes and reproduction commands.','',
  'No battle-simulation code, serving database or advisor UI was changed.'];
fs.writeFileSync(path.join(output,'README.md'),lines.join('\n')+'\n');

// Standalone playback: all data embedded, no external scripts or runtime server.
const playback=Object.fromEntries(['ten-workers','ten-walk-only','single-worker'].map(name=>[name,{
  frames:runs[name].frames.map(f=>({t:f.t,banked:f.banked,carried:f.carried,remaining:f.remaining,
    agents:f.agents.map(w=>({id:w.id,x:w.x,y:w.y,state:w.state,inventory:w.inventory}))})),options:runs[name].options}]));
const html=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gold mining simulation review</title><style>
body{margin:0;background:#f3f5f7;color:#182635;font:16px system-ui,sans-serif}main{max-width:1120px;margin:28px auto;padding:0 20px}h1{font-size:26px}p{line-height:1.5}.note{background:#fff5d6;border-left:4px solid #c28a13;padding:12px 16px}.grid{display:grid;grid-template-columns:minmax(420px,1.2fr) minmax(320px,1fr);gap:22px}.panel{background:white;border:1px solid #dce2e8;border-radius:10px;padding:18px}canvas{width:100%;display:block}button,select{font:inherit;padding:7px 11px}input{width:100%;margin:18px 0}.stats{font-variant-numeric:tabular-nums;line-height:1.8}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;text-align:left;border-bottom:1px solid #dce2e8}small{color:#536476}a{color:#145ca5} @media(max-width:850px){.grid{grid-template-columns:1fr}}
</style><main><h1>Gold mining: ten villagers on four gold tiles</h1>
<p class="note">Prototype model using the supplied game data. Reference comparison only; current DE crowd behavior has not been validated.</p>
<div class="grid"><div class="panel"><select id="trial"><option value="ten-workers">Ten villagers · collisions enabled</option><option value="ten-walk-only">Ten villagers · walking only</option><option value="single-worker">One villager</option></select>
<canvas id="map" width="680" height="620"></canvas><button id="play">Play</button> <button id="reset">Reset</button> <select id="speed"><option value="1">1×</option><option value="5" selected>5×</option><option value="20">20×</option></select>
<input id="time" type="range" min="0" max="420" step=".2" value="0"><div class="stats" id="stats"></div><small>Green: mining · Blue: returning to gold · Orange: carrying to camp. Worker labels show ID and carried gold. Map grid is in tiles.</small></div>
<div class="panel"><h2>Reference and sustained rates</h2><table><tr><th>Case</th><th>Gold/villager/min</th></tr><tr><td><a href="${fixture.reference.url}">Forgotten Empires, no bumping</a></td><td>${fmt(ref)}</td></tr><tr><td>One worker, completed delivery cycles</td><td>${fmt(single.completed_cycle_gold_per_worker_minute)}</td></tr><tr><td>Ten workers, walking only</td><td>${fmt(windowSummary(runs['ten-walk-only'],120,420).extracted_per_worker_minute)}</td></tr><tr><td>Ten workers, collisions enabled</td><td>${fmt(crowd.extracted_per_worker_minute)}</td></tr></table>
<p>Ten-worker rates count deposited gold plus the change in carried gold over 120–420 seconds. The reference excludes crowding. Deposited gold at a deadline is shown separately.</p>
<canvas id="chart" width="600" height="300"></canvas><small>Blue: deposited gold · Gold: deposited plus carried. Vertical line marks the selected time.</small>
<p>Baseline inputs: work ${fmt(fixture.worker.work_rate,5)} gold/s; movement ${fmt(fixture.worker.speed,3)} tiles/s; radius ${fmt(fixture.worker.radius,2)} tiles; carry ${fixture.worker.carry_capacity}. One empty tile between gold and camp.</p>
<p>Explicit model choices: rigid villagers, visibility routing, immediate deposit at contact, continuous mining, and 0.5-second retries when blocked. No fitted congestion multiplier.</p></div></div></main>
<script>const DATA=${JSON.stringify(playback).replaceAll('<','\\u003c')};
const $=id=>document.getElementById(id),map=$('map'),ctx=map.getContext('2d'),chart=$('chart'),cg=chart.getContext('2d');
let playing=false,last=null,cursor=0;const colors={mining:'#238454',to_mine:'#2c71b8',to_camp:'#c06d1a',idle:'#777'};
function render(){const run=DATA[$('trial').value],t=+$('time').value,f=run.frames[Math.min(run.frames.length-1,Math.round(t/.2))];
 ctx.clearRect(0,0,map.width,map.height);const scale=72,xx=x=>40+(x-7)*scale,yy=y=>25+(y-8)*scale;
 ctx.strokeStyle='#e3e8ed';ctx.lineWidth=1;for(let i=7;i<=16;i++){ctx.beginPath();ctx.moveTo(xx(i),yy(8));ctx.lineTo(xx(i),yy(16));ctx.stroke();ctx.beginPath();ctx.moveTo(xx(7),yy(i));ctx.lineTo(xx(16),yy(i));ctx.stroke();}
 const gold=[[10,10],[11,10],[10,11],[11,11]];ctx.font='15px system-ui';ctx.textAlign='center';gold.forEach(([x,y],i)=>{if(f.remaining[i]<=0)return;ctx.fillStyle='#ebd28a';ctx.fillRect(xx(x),yy(y),scale,scale);ctx.strokeStyle='#99712c';ctx.strokeRect(xx(x),yy(y),scale,scale);ctx.fillStyle='#594319';ctx.fillText(f.remaining[i].toFixed(0),xx(x+.5),yy(y+.55));});
 ctx.fillStyle='#7895ad';ctx.fillRect(xx(10),yy(13),scale*2,scale*2);ctx.fillStyle='white';ctx.fillText('Mining Camp',xx(11),yy(14));
 f.agents.forEach(w=>{ctx.beginPath();ctx.fillStyle=colors[w.state];ctx.arc(xx(w.x),yy(w.y),.2*scale,0,2*Math.PI);ctx.fill();ctx.strokeStyle='white';ctx.stroke();ctx.fillStyle='#152a3b';ctx.font='12px system-ui';ctx.fillText((w.id+1)+': '+w.inventory.toFixed(1),xx(w.x),yy(w.y)-19);});
 $('stats').textContent='Time '+f.t.toFixed(1)+' s · Deposited '+f.banked.toFixed(2)+' · Carried '+f.carried.toFixed(2)+' · Extracted '+(f.banked+f.carried).toFixed(2);
 cg.clearRect(0,0,600,300);const max=Math.max(...run.frames.map(x=>x.banked+x.carried)),X=t=>42+t/420*535,Y=g=>265-g/(max||1)*235;
 cg.strokeStyle='#cbd5df';cg.beginPath();cg.moveTo(42,25);cg.lineTo(42,265);cg.lineTo(577,265);cg.stroke();
 for(const [color,key] of [['#2c71b8','banked'],['#ad7b12','total']]){cg.beginPath();cg.strokeStyle=color;run.frames.forEach((r,i)=>{const x=X(r.t),y=Y(key==='total'?r.banked+r.carried:r.banked);i?cg.lineTo(x,y):cg.moveTo(x,y);});cg.stroke();}
 cg.strokeStyle='#9b445b';cg.beginPath();cg.moveTo(X(f.t),25);cg.lineTo(X(f.t),265);cg.stroke();cg.fillStyle='#536476';cg.font='12px system-ui';cg.fillText('0 s',35,285);cg.fillText('420 s',540,285);cg.fillText(max.toFixed(0)+' gold',45,17);
}
$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'Pause':'Play';last=null;};$('reset').onclick=()=>{cursor=0;$('time').value=0;render();};$('time').oninput=()=>{cursor=+$('time').value;render();};$('trial').onchange=render;
function animate(now){if(playing&&last!==null){cursor=Math.min(420,cursor+(now-last)/1000*+$('speed').value);$('time').value=cursor;if(cursor>=420){playing=false;$('play').textContent='Play';}render();}last=now;requestAnimationFrame(animate);}render();requestAnimationFrame(animate);
</script></html>`;
fs.writeFileSync(path.join(output,'playback.html'),html);
console.log('complete',JSON.stringify(compare.comparison));
