import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {legalSegment,route,simulate,windowSummary,distance} from './gold-mining-sim.mjs';
const fixture=JSON.parse(fs.readFileSync(new URL('../aoe2x/js_simulation/calibration/economy/gold-2026-11-09/fixture.json',import.meta.url)));
test('source upgrades and male/female checked during export',()=>{
  assert.deepEqual([...new Set(fixture.source.effects.map(e=>e.tech_id))].sort((a,b)=>a-b),[55,182,213,249]);
  assert.ok(Math.abs(fixture.worker.work_rate-.38*1.15*1.15)<1e-6);
  assert.ok(Math.abs(fixture.worker.speed-.8*1.1*1.1)<1e-6);
  assert.equal(fixture.worker.carry_capacity,20);
});
test('visibility route detours around rectangles and a stationary body',()=>{
  const box={x0:0,x1:2,y0:0,y1:2},target={x0:4,x1:6,y0:0,y1:2};
  const start={x:-1,y:1},discs=[{x:3,y:-.4,radius:.2}];
  assert.equal(legalSegment(start,{x:4,y:1},[box,target],discs,.2),false);
  const path=route(start,target,[box,target],discs,.2);assert.ok(path?.length>1);
  let p=start;for(const q of path){assert.ok(legalSegment(p,q,[box,target],discs,.2));p=q;}
});
test('first delivery occurs after a full load plus source-speed trip, with no forced flush',()=>{
  const r=simulate(fixture,{workers:1,duration:60,trace:true});
  const expected=20/fixture.worker.work_rate+.6/fixture.worker.speed;
  assert.ok(Math.abs(r.events[0].t-expected)<1e-6);
  assert.equal(r.final.banked,20);assert.ok(r.final.carried>0);
  assert.ok(Math.abs(r.final.banked+r.final.carried-r.final.extracted)<1e-8);
});
test('single worker completed cycles match the travel-and-carry equation',()=>{
  const r=simulate(fixture,{workers:1,duration:300,trace:true});
  const cycle=20/fixture.worker.work_rate+1.2/fixture.worker.speed;
  for(let i=1;i<r.events.length;i++)assert.ok(Math.abs(r.events[i].t-r.events[i-1].t-cycle)<1e-6);
});
test('crowd obeys speed, collision, time-budget and resource accounting',()=>{
  const r=simulate(fixture,{duration:180,trace:true});
  for(const w of r.final.agents)assert.ok(Math.abs(w.working+w.walking+w.blocked+w.idle-180)<1e-6);
  for(const [a,b] of [[0,60],[120,180]])assert.ok(Math.abs(windowSummary(r,a,b).conservation_error)<1e-6);
  assert.ok(r.checks.max_overlap<1e-6);assert.ok(r.checks.max_static_overlap<1e-6);assert.ok(r.checks.max_speed_error<1e-6);
  assert.ok(r.final.extracted<=10*fixture.worker.work_rate*180+1e-6);
  assert.ok(r.events.every(e=>e.gold<=fixture.worker.carry_capacity+1e-6));
});
test('deterministic baseline and walk-only diagnostic preserve inventories',()=>{
  const a=simulate(fixture,{duration:60}),b=simulate(fixture,{duration:60});
  assert.deepEqual(a.final,b.final);
  const c=simulate(fixture,{duration:60,collisions:false});
  assert.ok(c.final.extracted>a.final.extracted);
  assert.ok(c.final.agents.every(w=>w.blocked===0));
});
test('mines are finite; depletion retargets and eventually deposits residual loads',()=>{
  const small=structuredClone(fixture);small.gold.amount=3;
  const r=simulate(small,{workers:10,duration:180});
  assert.ok(Math.abs(r.final.banked-12)<1e-7);assert.ok(r.final.carried<1e-7);
  assert.ok(r.final.remaining.every(n=>n<1e-7));
});
