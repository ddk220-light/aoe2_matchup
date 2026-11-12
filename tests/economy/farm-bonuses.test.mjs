import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {simulateFarms} from '../../tools/economy/farm-gathering-sim.mjs';
const base=()=>JSON.parse(fs.readFileSync(new URL('./fixtures/farms-refinement/fixture-full.json',import.meta.url)));
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);
test('resource yield credits extra food without creating natural farm resources',()=>{
 const f=base();f.farm.food=20;f.farms=f.farms.slice(0,1);f.worker.task_output_multiplier=1.15;
 const r=simulateFarms(f,{duration:200});close(r.final.harvested,23);close(r.final.farms[0].harvested,20);close(r.checks.resource_error,0);
});
test('auto-deposit retains work cycles but removes all delivery trips',()=>{
 const f=base();f.behavior.auto_deposit=true;f.farm.food=35;f.farms=f.farms.slice(0,1);
 const r=simulateFarms(f,{duration:200});close(r.final.harvested,35);close(r.final.banked,35);close(r.final.carried,0);
 close(r.final.agents[0].outbound_walking,0);close(r.final.agents[0].return_walking,0);assert.ok(r.final.agents[0].internal_walking>0);
});
test('instant collection transfers farm food exactly once per creation/reseed',()=>{
 const f=base();f.farm.food=20;f.farms=f.farms.slice(0,1);f.farms[0].instant_food=2;
 const a=simulateFarms(f,{duration:1});assert.ok(a.final.banked>=2);close(a.snapshots[0].harvested,2);
 const b=simulateFarms(f,{duration:400,reseed:true});assert.ok(b.final.farms[0].reseeds>0);close(b.checks.resource_error,0);close(b.checks.inventory_error,0);
});
test('no bonus preserves the prior generic trajectory',async()=>{
 const {simulateFarms:before}=await import('./fixtures/baseline-engine/farm-gathering-sim.mjs');
 const f=base();const a=before(f,{duration:120}),b=simulateFarms(f,{duration:120});assert.deepEqual(a.final,b.final);
});
