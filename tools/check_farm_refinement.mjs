// Paired-seed comparison of a mechanical bug fix, without parameter fitting.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {simulateFarms} from './farm-gathering-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const original=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-2026-11-09');
const out=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-refinement-2026-11-09');
const read=n=>JSON.parse(fs.readFileSync(path.join(original,n)));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const baselinePath=path.join(out,'baseline-engine/farm-gathering-sim.mjs');
if(sha(baselinePath)!==read('manifest.json').code['tools/farm-gathering-sim.mjs'])throw new Error('Baseline source changed');
const baseline=(await import(pathToFileURL(baselinePath))).simulateFarms;
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const stats=a=>{const m=mean(a),sd=Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/(a.length-1));return {mean:m,sd,se:sd/Math.sqrt(a.length),min:Math.min(...a),max:Math.max(...a)};};
const options={duration:1300,trace:true,reseed:false,mill:{x0:0,x1:4,y0:0,y1:4},farms:[{id:0,x0:4,x1:7,y0:0,y1:3},{id:1,x0:7,x1:10,y0:0,y1:3}]};
const groups=[],runs=[];
for(const [profile,food,seconds] of [['none',175,[491,617]],['wheelbarrow',250,[663,779]],['full',375,[937,956]]]){
 const f=read(`fixture-${profile}.json`);f.farm.food=food;
 const profiles=[];
 for(let seed=0;seed<32;seed++){
  const a=baseline(f,{...options,seed}),b=simulateFarms(f,{...options,seed});
  const pairs=[0,1].map(id=>{
   const old=a.events.filter(e=>e.worker===id&&e.from==='gather'&&e.to==='outbound').at(-1);
   const fixed=b.events.find(e=>e.worker===id&&e.event==='depleted');
   return {id,old_seconds:old.t,new_seconds:fixed.t,old_rate:60*food/old.t,new_rate:60*food/fixed.t};
  });
  if(profile==='none'&&seed===0)fs.writeFileSync(path.join(out,'depletion-trace-example.json'),JSON.stringify({
   before:a.events.filter(e=>e.worker===0&&e.t>500&&e.t<520),after:b.events.filter(e=>e.worker===0&&e.t>500&&e.t<520)},null,2)+'\n');
  profiles.push(pairs);runs.push({profile,seed,pairs,checks:b.checks});
 }
 for(let id=0;id<2;id++){
  const before=stats(profiles.map(r=>r[id].old_rate)),after=stats(profiles.map(r=>r[id].new_rate)),ref=60*food/seconds[id];
  groups.push({profile,position:id?'outer':'near',reference:ref,before,after,before_error_percent:(before.mean/ref-1)*100,after_error_percent:(after.mean/ref-1)*100});
 }
 console.log(profile,groups.slice(-2));
}
fs.writeFileSync(path.join(out,'paired-seed-validation.json'),JSON.stringify({seeds:32,
 before_engine_sha256:sha(baselinePath),after_engine_sha256:sha(path.join(root,'tools/farm-gathering-sim.mjs')),
 note:'Seed spread measures model randomness, not uncertainty of the single published game result. No parameter search or seed selection.',groups,runs},null,2)+'\n');
