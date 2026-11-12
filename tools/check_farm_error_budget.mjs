// Prespecified diagnostics for unresolved errors; never select a winning variant.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {simulateFarms} from './farm-gathering-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const base=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-refinement-2026-11-09');
const out=path.join(root,'aoe2x/js_simulation/calibration/economy/farms-repeated-reference-2026-11-09');
const read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const engineHash=sha(path.join(root,'tools/farm-gathering-sim.mjs'));
const groups=[],runs=[];
const variants=[['default',{}],['no_collisions',{collisions:false}],['full_starting_pool',{initialPool:15}]];
const options={duration:1300,reseed:false,mill:{x0:0,x1:4,y0:0,y1:4},farms:[{id:0,x0:4,x1:7,y0:0,y1:3},{id:1,x0:7,x1:10,y0:0,y1:3}]};
for(const [profile,food,seconds] of [['none',175,[491,617]],['wheelbarrow',250,[663,779]]]){
 const fixture=read(path.join(base,`reference-fixture-${profile}.json`));
 assert.equal(fixture.farm.food,food);
 for(const [name,overrides] of variants){
  const batch=[];
  for(let seed=0;seed<32;seed++){
   const r=simulateFarms(fixture,{...options,...overrides,seed});
   const rows=r.final.farms.map((f,i)=>{
    assert(f.last_depleted_at>0);
    const b=r.final.agents[i];
    return {seconds:f.last_depleted_at,rate:60*food/f.last_depleted_at,
     working:b.working,internal_walking:b.internal_walking,outbound_walking:b.outbound_walking,
     return_walking:b.return_walking,initial_walking:b.initial_walking,blocked:b.blocked};
   });
   batch.push(rows);runs.push({profile,variant:name,seed,rows,checks:r.checks});
  }
  for(let id=0;id<2;id++){
   const rate=mean(batch.map(r=>r[id].rate)),reference=60*food/seconds[id];
   groups.push({profile,position:id?'outer':'near',variant:name,rate,reference,difference_percent:100*(rate/reference-1),
    average_state_seconds:Object.fromEntries(Object.keys(batch[0][id]).filter(k=>!['rate','seconds'].includes(k)).map(k=>[k,mean(batch.map(r=>r[id][k]))]))});
  }
  console.log(`${profile}: ${name} complete`);
 }
}
assert.equal(engineHash,sha(path.join(root,'tools/farm-gathering-sim.mjs')));
const result={engine_sha256:engineHash,seeds:32,variants:Object.fromEntries(variants),groups,runs,
 caveat:'No-collision and full-pool runs are sensitivity diagnostics, not supported replacements for the default. State totals include the final partial-load deposit trip; rate endpoints stop at depletion.'};
fs.writeFileSync(path.join(out,'error-budget.json'),JSON.stringify(result,null,2)+'\n');
const lines=['# Farm discrepancy diagnostics','',
 'The same first 32 seeds were used for every condition. These diagnose uncertainty; neither alternative is adopted as game behavior.','',
 '| Profile | Farm | Default error | No collisions | Full initial buffer |',
 '|---|---|---:|---:|---:|',
 ...['none','wheelbarrow'].flatMap(profile=>['near','outer'].map(position=>{
  const values=variants.map(([variant])=>groups.find(g=>g.profile===profile&&g.position===position&&g.variant===variant).difference_percent);
  return `| ${profile} | ${position} | ${values.map(v=>v.toFixed(3)+'%').join(' | ')} |`;
 })), '',
 'Removing collisions reduces the baseline underestimate but increases the Wheelbarrow overestimate. A full initial buffer does not resolve either. Neither single change satisfies all cases.','',
 'Observed collision states, carry amounts at each work-stop, and drop-off/return trajectories are the next discriminating evidence. A rate-only benchmark does not establish which movement rule is wrong.',''];
fs.writeFileSync(path.join(out,'error-budget.md'),lines.join('\n'));
console.log(JSON.stringify(groups,null,2));
