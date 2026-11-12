import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {simulateFarms} from './farm-gathering-sim.mjs';
import {simulateWood,woodWindow} from './wood-gathering-sim.mjs';
import {simulate,windowSummary} from './gold-mining-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out=process.env.ARMY_CONTEXT_OUT??path.join(root,'aoe2x/js_simulation/calibration/economy/army-context-2026-11-09');
const specs=JSON.parse(fs.readFileSync(path.join(out,'eco-inputs.json'))),cache=new Map(),rows=[];
const engineHashes=Object.fromEntries(['farm-gathering-sim.mjs','gold-mining-sim.mjs','wood-gathering-sim.mjs'].map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'tools',n))).digest('hex')]));
const provenancePath=path.join(out,'rate-cache-provenance.json');
if(fs.existsSync(provenancePath)&&JSON.stringify(JSON.parse(fs.readFileSync(provenancePath)))===JSON.stringify(engineHashes)){
 for(const [k,v] of Object.entries(JSON.parse(fs.readFileSync(path.join(out,'rate-cache.json')))))cache.set(k,v);
}
fs.writeFileSync(provenancePath,JSON.stringify(engineHashes));
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
for(const s of specs){
 for(const [resource,job] of Object.entries(s.jobs)){
  if(job.engine==='unsupported_pasture'){rows.push({civ_name:s.civ_name,resource,status:'unresolved_pasture',rate:null,runs:[],flags:s.flags});continue;}
  const f=structuredClone(job.fixture);delete f.source;delete f.name;delete f.assumptions;delete f.technology_ids;
  // Only physical inputs determine cache identity. Strip documentary fields.
  if(f.worker.carry_steps)delete f.worker.carry_steps;
  delete f.worker.unrounded_carry;delete f.upgrade_profile;
  const key=crypto.createHash('sha256').update(JSON.stringify({engine:job.engine,f})).digest('hex');
  if(!cache.has(key)){
   const runs=[];
   for(let seed=0;seed<3;seed++){
    if(job.engine==='farm'){
     const r=simulateFarms(f,{duration:1800,seed,reseed:true});
     runs.push({seed,rate:r.final.harvested/1800/10,banked_rate:r.final.banked/1800/10,wood_spent:r.final.wood,checks:r.checks});
    }else if(job.engine==='wood'){
     const r=simulateWood(f,{duration:600,seed});
     runs.push({seed,rate:(r.final.extracted-r.snapshots.find(x=>Math.abs(x.t-60)<1e-6).extracted)/540/10,checks:r.checks});
    }else{
     const r=simulate(f,{duration:240,seed});const w=windowSummary(r,60,240);
     runs.push({seed,rate:w.extracted_per_worker_minute/60,checks:r.checks});
    }
   }
   cache.set(key,{runs,rate:mean(runs.map(r=>r.rate)),min_rate:Math.min(...runs.map(r=>r.rate)),max_rate:Math.max(...runs.map(r=>r.rate))});
   fs.writeFileSync(path.join(out,'rate-cache.json'),JSON.stringify(Object.fromEntries(cache))+'\n');
  }
  rows.push({civ_name:s.civ_name,resource,status:'scenario_estimate',signature:key,...cache.get(key),flags:s.flags});
 }
 console.log(s.civ_name,rows.slice(-4).map(r=>`${r.resource}:${r.rate===null?'unresolved':(r.rate*60).toFixed(3)}`).join(' '));
 fs.writeFileSync(path.join(out,'gather-rates.json'),JSON.stringify(rows,null,2)+'\n');
}
console.log('Complete',rows.length,'civ/resource rows;',cache.size,'distinct scenarios');
