import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {simulateWood,woodWindow} from '../../tools/economy/wood-gathering-sim.mjs';
const dir=new URL('./fixtures/wood/',import.meta.url);
const profile=(w,c)=>JSON.parse(fs.readFileSync(new URL(`fixture-w${w}-c${c}.json`,dir)));
test('raw work rates and selected source upgrades',()=>{
 const base=profile(0,0),full=profile(3,2);
 assert.deepEqual(base.source.effects,[]);assert.equal(base.worker.carry_capacity,10);
 assert.ok(Math.abs(base.worker.work_rate-.39)<1e-7);
 assert.ok(Math.abs(full.worker.work_rate-.39*1.2*1.2*1.1)<1e-7);
 assert.equal(full.worker.carry_capacity,20);assert.equal(full.tree.hit_points,20);
 assert.equal(full.worker.damage_per_swing,15);
});
test('no wood is gathered before standing tree is felled',()=>{
 const f=profile(0,0);f.forest={x:13.5,y:10,width:1,depth:1};
 const r=simulateWood(f,{workers:1,duration:10,trace:true});
 assert.equal(r.events.filter(e=>e.type==='swing').length,2);
 const swings=r.events.filter(e=>e.type==='swing');
 assert.ok(Math.abs(swings[0].t-1)<1e-6&&Math.abs(swings[1].t-3)<1e-6);
 assert.equal(r.snapshots.find(s=>s.t===2).extracted,0);
 assert.ok(r.snapshots.find(s=>s.t===4).extracted>0);
});
test('uninterrupted felled-tree collection reaches the source work rate',()=>{
 for(const [w,c] of [[0,0],[3,2]]){
  const f=profile(w,c);f.worker.carry_capacity=1000;
  const r=simulateWood(f,{workers:1,duration:60,preFelled:true});
  assert.ok(Math.abs(r.final.extracted-f.worker.work_rate*60)<1e-6);
  assert.equal(r.final.agents[0].felling,0);
 }
});
test('finite trees deplete, partial inventory is retained, and final wood is deposited',()=>{
 const f=profile(0,0);f.forest={x:13,y:10,width:2,depth:1};
 const r=simulateWood(f,{workers:1,duration:120,treeWood:2,trace:true});
 assert.equal(r.final.depleted,2);assert.ok(Math.abs(r.final.banked-4)<1e-6);
 assert.ok(r.final.carried<1e-6);
 assert.equal(r.events.filter(e=>e.type==='deposit').length,1);
});
test('crowd speed, overlap, time budget, accounting and reproducibility',()=>{
 const f=profile(3,2),a=simulateWood(f,{duration:180}),b=simulateWood(f,{duration:180});
 assert.deepEqual(a.final,b.final);
 for(const w of a.final.agents)assert.ok(Math.abs(w.working+w.felling+w.walking+w.blocked+w.idle-180)<1e-6);
 assert.ok(Math.abs(woodWindow(a,0,60).conservation_error)<1e-6);
 assert.ok(a.checks.max_overlap<1e-6&&a.checks.max_static_overlap<1e-6&&a.checks.max_speed_error<1e-6);
 assert.ok(a.final.extracted<=180*10*f.worker.work_rate+1e-6);
});
test('fully depleted trees expose deeper resource targets',()=>{
 const f=profile(0,0);f.forest={x:13.5,y:10,width:1,depth:2};
 const r=simulateWood(f,{workers:1,duration:120,treeWood:2,trace:true});
 const empty=r.events.filter(e=>e.type==='depleted');assert.equal(empty.length,2);
 assert.deepEqual(empty.map(e=>e.tree),[1,0]);
 assert.ok(r.final.agents[0].distance>2);
});
