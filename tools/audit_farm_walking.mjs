// Source-backed speed checks, geometry checks, and paired routing regression.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {simulateFarms,farmWindow} from './farm-gathering-sim.mjs';
import {route,distance,legalSegment,pointRectDistance} from './gold-mining-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-walking-audit-2026-11-10');
const beforeDir=path.join(out,'baseline-engine');
const previous=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-refinement-2026-11-09');
const repeated=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-repeated-reference-2026-11-09');
const read=p=>JSON.parse(fs.readFileSync(p)),mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const baseline=(await import(pathToFileURL(path.join(beforeDir,'farm-gathering-sim.mjs')))).simulateFarms;
assert.equal(sha(path.join(beforeDir,'farm-gathering-sim.mjs')),read(path.join(repeated,'comparison.json')).engine_sha256);
const profile=n=>read(path.join(previous,`fixture-${n}.json`));
const length=(p,points)=>{let d=0;for(const q of points){d+=distance(p,q);p=q;}return d;};
const box={x0:0,y0:0,x1:4,y1:4},r=profile('none').worker.radius;
const p={x:6.5,y:.5},discs=[{x:6,y:.5,radius:r}];
const oldPath=route(p,box,[box],discs,r),newPath=route(p,box,[box],discs,r,{compareDetours:true});
const regression={start:p,mill:box,blockers:discs,radius:r,before_path:oldPath,after_path:newPath,
 before_distance:length(p,oldPath),after_distance:length(p,newPath)};
assert(regression.before_distance>3.9&&regression.after_distance<2.5);
let counterexamples=0,tested=0;
// Discrete geometry sweep, independent of food rates and benchmark outcomes.
for(const x of [4.5,5.5,6.5,7.5,8.5,9.5])for(const y of [.5,1.5,2.5])
for(const ox of [4.3,4.5,5,5.5,6,6.5,7])for(const oy of [.5,1,1.5,2,2.5,3]){
 const start={x,y},obstacles=[{x:ox,y:oy,radius:r}];
 if(distance(start,obstacles[0])<2*r)continue;
 const a=route(start,box,[box],obstacles,r),b=route(start,box,[box],obstacles,r,{compareDetours:true});
 if(!a||!b)continue;
 tested++;assert(length(start,b)<=length(start,a)+1e-6);
 if(length(start,a)-length(start,b)>1e-6)counterexamples++;
 let last=start;for(const q of b){assert(legalSegment(last,q,[box],obstacles,r));last=q;}
 assert(Math.abs(pointRectDistance(last,box)-r)<1e-6);
}
const offsets=profile('none').behavior.work_spot_offsets;
const spots=offsets.flatMap(x=>offsets.map(y=>({x,y})));
const internal=spots.flatMap((p,i)=>spots.filter((q,j)=>i!==j).map(q=>distance(p,q)));
assert.equal(internal.length,72);
const geometries=[];
for(const [name,mill,x,y] of [['TC near',box,4,0],['TC outer',box,7,0],['3x3 side',{x0:0,y0:0,x1:3,y1:3},3,0],['3x3 corner',{x0:0,y0:0,x1:3,y1:3},3,3]]){
 const points=spots.map(p=>({x:x+p.x,y:y+p.y}));
 const outgoing=points.map(p=>route(p,mill,[mill],[],r,{compareDetours:true}));
 const drops=outgoing.map(path=>path.at(-1));
 // All return endpoints are on the same side/corner, so straight paths are legal.
 const returning=points.flatMap((p,i)=>points.filter((q,j)=>i!==j).map(q=>{
  assert(legalSegment(drops[i],q,[mill],[],r));return distance(drops[i],q);
 }));
 geometries.push({name,mean_outbound_tiles:mean(outgoing.map((route,i)=>length(points[i],route))),
  mean_return_tiles_excluding_last_spot:mean(returning),mean_internal_move_tiles:mean(internal)});
}
const runs=[],groups=[];
const tcOptions={duration:1300,reseed:false,mill:box,farms:[{id:0,x0:4,x1:7,y0:0,y1:3},{id:1,x0:7,x1:10,y0:0,y1:3}]};
function slim(run){return {seconds:run.final.farms.map(f=>f.last_depleted_at),
 agents:run.final.agents.map(b=>Object.fromEntries(['id','distance','internal_walking','outbound_walking','return_walking','initial_walking','blocked'].map(k=>[k,b[k]]))),checks:run.checks};}
for(const [name,food,seconds] of [['none',175,[491,617]],['wheelbarrow',250,[663,779]],['full',375,[937,956]]]){
 const f=read(path.join(previous,`reference-fixture-${name}.json`));assert.equal(f.farm.food,food);
 const batch=[];
 for(let seed=0;seed<32;seed++){
  const a=baseline(f,{...tcOptions,seed}),b=simulateFarms(f,{...tcOptions,seed,trace:seed===0});
  const pair={scenario:'TC',profile:name,seed,before:slim(a),after:slim(b)};
  assert(pair.after.seconds.every(x=>x>0));batch.push(pair);runs.push(pair);
  if(seed===0)fs.writeFileSync(path.join(out,`trace-${name}-seed-0.json`),JSON.stringify({events:b.events,options:b.options,fixture:b.fixture,checks:b.checks})+'\n');
 }
 for(let id=0;id<2;id++){
  const reference=60*food/seconds[id],before=mean(batch.map(p=>60*food/p.before.seconds[id])),after=mean(batch.map(p=>60*food/p.after.seconds[id]));
  groups.push({scenario:'TC',profile:name,position:id?'outer':'near',reference,before,after,before_error_percent:100*(before/reference-1),after_error_percent:100*(after/reference-1),
   walking_before:mean(batch.map(p=>p.before.agents[id].distance)),walking_after:mean(batch.map(p=>p.after.agents[id].distance))});
 }
 console.log(`TC ${name}: ${JSON.stringify(groups.slice(-2))}`);
}
const observed=read(path.join(repeated,'published-observations.json'));
const folwark=read(path.join(repeated,'comparison.json')).scenario;
const batch=[];
for(let seed=0;seed<36;seed++){
 const options={duration:650,reseed:false,seed,mill:folwark.mill,farms:folwark.farms};
 const a=baseline(profile('none'),options),b=simulateFarms(profile('none'),options);
 const pair={scenario:'3x3 ring',profile:'none',seed,before:slim(a),after:slim(b)};
 assert(pair.after.seconds.every(x=>x>0));batch.push(pair);runs.push(pair);
 if(seed%12===11)console.log(`3x3 ring ${seed+1}/36 complete`);
}
for(const [position,ids] of [['side',[0,1,2,3]],['corner',[4,5,6,7]]]){
 const refTimes=observed.extra_seconds.flatMap(row=>ids.filter(i=>row[i]!==null).map(i=>row[i]+480));
 const reference=60*175/mean(refTimes),before=60*175/mean(batch.flatMap(p=>ids.map(i=>p.before.seconds[i]))),after=60*175/mean(batch.flatMap(p=>ids.map(i=>p.after.seconds[i])));
 groups.push({scenario:'3x3 ring',profile:'none',position,reference,before,after,before_error_percent:100*(before/reference-1),after_error_percent:100*(after/reference-1)});
}
const mill=[];
for(const name of ['none','full']){
 const batch=[];
 for(let seed=0;seed<5;seed++){
  const a=baseline(profile(name),{duration:600,seed,reseed:true}),b=simulateFarms(profile(name),{duration:600,seed,reseed:true});
  batch.push({seed,before:farmWindow(a,0,600),after:farmWindow(b,0,600),checks:b.checks});
 }
 mill.push({profile:name,before:mean(batch.map(p=>p.before.food_per_worker_minute)),after:mean(batch.map(p=>p.after.food_per_worker_minute)),runs:batch});
 console.log(`Ten-farm mill ${name} complete`);
}
const result={speeds:Object.fromEntries(['none','wheelbarrow','full'].map(n=>[n,profile(n).worker.speed])),
 regression,geometry_sweep:{tested,counterexamples},geometries,groups,runs,mill,
 note:'Rates remain empirical comparisons, not current-DE trajectory validation. Speed, work-point grid, collision radius, carry, resource generation and stop quota are unchanged. Only farm drop-off path selection changed.'};
fs.writeFileSync(path.join(out,'comparison.json'),JSON.stringify(result,null,2)+'\n');
const lines=['# Farming walking audit','',
 'A routing defect was reproduced independently of gather-rate benchmarks: a farther clear building contact could win over a shorter safe detour to a nearer contact. Farms now compare those alternatives on the existing visibility graph. Mining and wood keep their existing default routing behavior.','',
 `Example: ${regression.before_distance.toFixed(3)} tiles before, ${regression.after_distance.toFixed(3)} tiles after. ${counterexamples} of ${tested} valid static test arrangements admit a shorter route. These are synthetic geometry tests, not observed DE paths.`, '',
 '## Rates before and after','',
 '| Scenario | Upgrades | Position | Before difference | After difference |','|---|---|---|---:|---:|',
 ...groups.map(g=>`| ${g.scenario} | ${g.profile} | ${g.position} | ${g.before_error_percent.toFixed(3)}% | ${g.after_error_percent.toFixed(3)}% |`),'',
 'TC uses the same 32 seeds and mean-of-individual-rates estimator as the previous review. The 3×3 ring uses the same 36 seeds and reciprocal-mean-lifetime estimator as its published table. Every result remains visible. The 3×3 source does not explain how Folwark instant collection was excluded, so that comparison remains conditional.','',
 '## Distances implied by the current work-point policy','',
 '| Geometry | Outbound tiles | Return tiles | One internal move |','|---|---:|---:|---:|',
 ...geometries.map(g=>`| ${g.name} | ${g.mean_outbound_tiles.toFixed(3)} | ${g.mean_return_tiles_excluding_last_spot.toFixed(3)} | ${g.mean_internal_move_tiles.toFixed(3)} |`),'',
 'These enumerate all nine start points and all 72 distinct-point return/internal pairs, without other villagers. A return to a different random point need not equal the outbound distance. Rigid collision shapes, exact stop/return selection and contact geometry remain assumptions.','',
 '## Original ten-farm mill','',
 '| Profile | Before food/villager/min | After |','|---|---:|---:|',
 ...mill.map(g=>`| ${g.profile} | ${g.before.toFixed(4)} | ${g.after.toFixed(4)} |`),'',
 'Five seeds, 600 seconds, reseeding enabled; this is a model-to-model regression check, not a new live benchmark.','',
 '## Evidence and limits','',
 '- Walking speeds 0.800 / 0.880 / 0.968 tiles per game-second are replayed from the user DAT and Wheelbarrow/Hand Cart effects. No speed or collision-radius tuning was applied.',
 '- [Official update 50292](https://www.ageofempires.com/news/aoe2de-update-50292/) confirms centering farm work. It does not specify the exact current work-point selection algorithm.',
 '- [2020 community analysis](https://www.reddit.com/r/aoe2/comments/k3bxdp/the_universal_farming_equation/) describes random return points, but contains fitted pause assumptions and subsequent corrections. It is insufficient to establish a new stop-distance or delay parameter.',
 '- [Official update 185872](https://www.ageofempires.com/news/age-of-empires-ii-definitive-edition-update-185872/) documents changes to drop-off behavior. Historical game measurements cannot prove current path equivalence.',
 '- [TC benchmark](https://www.reddit.com/r/aoe2/comments/18l91t2/did_some_farm_testing_wheelbarrow_math/) and [repeated 3×3 reference](https://vixark.com/age-of-empires-ii/folwark) do not provide trajectories. Correct graph routing does not prove that DE chooses shortest paths.',
 '- Current run traces include cumulative travel distance and blocked time at each state change, allowing actual per-leg comparisons once a DE recording is available.',''];
fs.writeFileSync(path.join(out,'README.md'),lines.join('\n'));
const files=['tools/farm-gathering-sim.mjs','tools/gold-mining-sim.mjs','tools/farm-gathering-sim.test.mjs','tools/audit_farm_walking.mjs'];
fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify({code:Object.fromEntries(files.map(p=>[p,sha(path.join(root,p))])),before:Object.fromEntries(['farm-gathering-sim.mjs','gold-mining-sim.mjs'].map(p=>[p,sha(path.join(beforeDir,p))])),artifacts:Object.fromEntries(fs.readdirSync(out).filter(p=>!['manifest.json','run-log.txt'].includes(p)&&fs.statSync(path.join(out,p)).isFile()).map(p=>[p,sha(path.join(out,p))]))},null,2)+'\n');
console.log(JSON.stringify({groups,mill:mill.map(({runs,...rest})=>rest)},null,2));
