import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {evolveFarm,simulateFarms,farmWindow} from './farm-gathering-sim.mjs';
import {pointRectDistance,route,distance,legalSegment} from './gold-mining-sim.mjs';
const profile=n=>JSON.parse(fs.readFileSync(new URL(`../aoe2x/js_simulation/calibration/economy/farms-2026-11-09/fixture-${n}.json`,import.meta.url)));
const close=(a,b,tol=1e-6)=>assert.ok(Math.abs(a-b)<tol,`${a} != ${b}`);
const resource=(pool=0)=>({pool,reserve:175-pool,pool_capacity:15,generation_rate:.4,generated:0,harvested:0});
test('source profiles include Heavy Plow carry and separate farm/worker work',()=>{
 const a=profile('none'),b=profile('full');
 assert.equal(a.worker.carry_capacity,10);assert.equal(b.worker.carry_capacity,21);
 close(b.worker.work_rate,.53);close(b.farm.generation_rate,.4);assert.equal(b.farm.food,550);
 assert.equal(b.farm.build_seconds,15);assert.equal(b.farm.wood_cost,60);
});
test('empty farm constrains fast worker; idle pool fills and pauses without losing food',()=>{
 const f=resource();close(evolveFarm(f,10,.53).harvested,4);close(f.pool,0);
 evolveFarm(f,100);close(f.pool,15);close(f.reserve,156);
 close(f.pool+f.reserve+f.harvested,175);
 const h=evolveFarm(f,10,.53);close(h.harvested,5.3);close(f.pool,13.7);
});
test('exact pool integration handles reserve exhaustion, carry boundary and time partitioning',()=>{
 const a=resource(5),b=resource(5);a.reserve=b.reserve=2;
 const result=evolveFarm(a,100,.53,6);close(result.harvested,6);close(result.elapsed,6/.53);
 for(let i=0;i<100;i++)evolveFarm(b,.1,.53);
 const c=resource(5);c.reserve=2;evolveFarm(c,10,.53);close(c.pool,b.pool);close(c.reserve,b.reserve);close(c.harvested,b.harvested);
 evolveFarm(a,100,.53);close(a.harvested,7);close(a.pool+a.reserve,0);
});
test('deposits occur only at mill contact, full loads except terminal depletion',()=>{
 const f=profile('none');f.farms=f.farms.slice(0,1);f.farm.food=17;
 const r=simulateFarms(f,{duration:140,trace:true});
 const drops=r.events.filter(e=>e.event==='deposit');assert.equal(drops.length,2);
 close(drops[0].food,10);close(drops[1].food,7);close(r.final.banked,17);
 for(const d of drops)assert.ok(pointRectDistance(d,f.mill)<=f.worker.radius+1e-6);
});
test('standing time follows gathered portion and available pool, with explicit internal walks',()=>{
 const f=profile('none');f.farms=f.farms.slice(0,1);
 const r=simulateFarms(f,{duration:100,trace:true});
 const exits=r.events.filter(e=>e.event==='state'&&e.from==='gather');assert.ok(exits.length>4);
 for(let i=0;i<3;i++)close(exits[i].inventory,(i+1)*2.5);
 assert.equal(exits[3].to,'outbound');close(exits[3].inventory,10);
 assert.ok(r.final.agents[0].internal_walking>0);
});
test('outer farm spends longer dropping off and produces less without changing rates',()=>{
 const f=profile('none');f.farm.food=10000;f.farms=f.farms.slice(3,4);
 const near=simulateFarms(f,{duration:600,collisions:false});
 f.farms=f.farms.map(r=>({...r,x0:r.x0+6,x1:r.x1+6}));
 const far=simulateFarms(f,{duration:600,collisions:false});
 assert.ok(far.final.agents[0].outbound_walking>near.final.agents[0].outbound_walking);
 assert.ok(far.final.harvested<near.final.harvested);
});
test('reseeding consumes wood and construction time, preserving food accounting',()=>{
 const f=profile('none');f.farm.food=4;f.farms=f.farms.slice(0,1);
 const r=simulateFarms(f,{duration:120,reseed:true});
 assert.ok(r.final.farms[0].reseeds>=2);assert.ok(r.final.wood>=120);assert.ok(r.final.agents[0].building>=30);
 assert.ok(Math.abs(r.checks.resource_error)<1e-6);
});
test('crowd conservation, speed/collision bounds, reproducibility and production ceiling',()=>{
 const f=profile('full'),a=simulateFarms(f,{duration:120}),b=simulateFarms(f,{duration:120});
 assert.deepEqual(a.final,b.final);
 assert.ok(a.final.harvested<=120*10*f.farm.generation_rate+1e-6);
 for(const v of Object.values(a.checks))assert.ok(Math.abs(v)<1e-6);
 const w=farmWindow(a,0,60);close(w.harvested,w.banked+w.carried_end-w.carried_start);
});
test('overlapping farm/building layouts are rejected',()=>{
 const f=profile('none');f.farms[0]={id:0,x0:0,y0:0,x1:3,y1:3};
 assert.throws(()=>simulateFarms(f),/Overlapping/);
});
test('harvest integration stops at the exact depletion time',()=>{
 const f=resource();f.reserve=.4;
 const r=evolveFarm(f,10,.53);
 close(r.harvested,.4);close(r.elapsed,1);
});
test('depletion at a quarter-load boundary never schedules an empty work spot',()=>{
 const f=profile('none');f.farm.food=5;f.farms=f.farms.slice(0,1);
 const r=simulateFarms(f,{duration:60,trace:true});
 assert.equal(r.events.filter(e=>e.from==='gather'&&e.to==='internal'&&e.inventory>=5-1e-6).length,0);
 const e=r.events.find(e=>e.event==='depleted');assert.ok(e);
 close(e.harvested,5);assert.ok(e.t<r.events.find(e=>e.event==='deposit').t);
});
test('drop-off compares a short detour with a long unobstructed contact',()=>{
 const start={x:6.5,y:.5},mill={x0:0,x1:4,y0:0,y1:4},discs=[{x:6,y:.5,radius:.2}];
 const path=route(start,mill,[mill],discs,.2,{compareDetours:true});
 let p=start,length=0;
 for(const q of path){assert.ok(legalSegment(p,q,[mill],discs,.2));length+=distance(p,q);p=q;}
 assert.ok(length<2.5,`A safe detour under 2.5 tiles exists, got ${length}`);
 close(pointRectDistance(p,mill),.2);
});
test('walking traces account for distance, travel time and blocked time independently',()=>{
 const f=profile('none'),r=simulateFarms(f,{duration:120,trace:true});
 for(const b of r.final.agents){
  const seconds=b.initial_walking+b.internal_walking+b.outbound_walking+b.return_walking;
  close(b.distance,seconds*f.worker.speed);
 }
 for(const b of r.final.agents){
  let previous=null;
  for(const e of r.events.filter(e=>e.worker===b.id&&e.event==='state')){
   if(previous){
    assert.ok(e.distance>=previous.distance-1e-8);
    if(['initial_walk','internal','outbound','return'].includes(e.from))
     close(e.distance-previous.distance,((e.t-previous.t)-(e.blocked-previous.blocked))*f.worker.speed);
   }
   previous=e;
  }
 }
});
