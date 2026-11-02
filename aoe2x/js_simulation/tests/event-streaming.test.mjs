import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createCanonicalJsonArrayHasher,hashCanonicalJson} from '../src/canonical-json.js';
import {createWorld,runWorld,stepWorld} from '../src/combat/world.js';

const mechanics=JSON.parse(readFileSync(new URL('../fixtures/unit_stats/champion_chinese_imperial.json',import.meta.url)));
const unit=(referenceId,owner,x)=>({referenceId,owner,x,y:5,facing:0,mechanics,unitMaster:mechanics.unit_master,
 hp:mechanics.hp,alive:true,pursuitTargetId:null,engagedTargetId:null,attackTargetId:null,avoidance:null,action:'idle',actionTimers:{windup:0,reload:0}});
const world=()=>createWorld({ratio:'stream-test',units:[unit(1,2,4),unit(2,3,5)],map:{width:10,height:10,obstacles:[]},mapHash:'test'});

test('incremental canonical array hash preserves arbitrary batch boundaries and sparse/unicode values',()=>{
 const values=[,null,{z:'🚀 é \\ "',a:[true,-0,1e-9]},,[1,2],false,{},];
 for(let split=0;split<=values.length;split++){
  const h=createCanonicalJsonArrayHasher();h.append([]);h.append(values.slice(0,split));h.append([]);h.append(values.slice(split));
  assert.equal(h.finish(),hashCanonicalJson(values));assert.throws(()=>h.append([]));assert.throws(()=>h.finish());
 }
 assert.equal(createCanonicalJsonArrayHasher().finish(),hashCanonicalJson([]));
 const cycle={};cycle.self=cycle;
 for(const value of [undefined,NaN,Infinity,1n,new Date(),cycle])assert.throws(()=>createCanonicalJsonArrayHasher().append([value]));
});

test('nonretaining event stream preserves initial history, all event order, outcomes, and final units',()=>{
 for(const startTicks of [0,3])for(const maxTicks of [0,2,1000]){
  let a=world(),b=world();for(let i=0;i<startTicks;i++){a=stepWorld(a);b=stepWorld(b);}
  const baseline=runWorld(a,{maxTicks,retainSnapshots:false}),hasher=createCanonicalJsonArrayHasher(),seen=[];
  const streamed=runWorld(b,{maxTicks,retainSnapshots:false,retainEvents:false,onEvents:events=>{hasher.append(events);seen.push(...events);}});
  assert.equal(hasher.finish(),hashCanonicalJson(baseline.events));assert.deepEqual(seen,baseline.events);
  for(const field of ['ticks','outcome','winner'])assert.equal(streamed[field],baseline[field]);
  assert.deepEqual(streamed.world.units,baseline.world.units);
  assert.deepEqual(streamed.events,[]);assert.deepEqual(streamed.world.eventLog,[]);assert.deepEqual(streamed.snapshots,[]);
 }
 assert.throws(()=>runWorld(world(),{retainEvents:false}));
 assert.throws(()=>runWorld(world(),{retainSnapshots:false,retainEvents:false}));
});

test('a million events are hashed under a 32-MiB heap without retaining them',()=>{
 const url=new URL('../src/canonical-json.js',import.meta.url).href;
 const script=`import assert from 'node:assert/strict';import {createHash} from 'node:crypto';
 import {createCanonicalJsonArrayHasher} from ${JSON.stringify(url)};
 const h=createCanonicalJsonArrayHasher(),expected=createHash('sha256');expected.update('[');
 for(let i=0;i<1000000;i++){h.append([{i,type:'move'}]);if(i)expected.update(',');expected.update('{"i":'+i+',"type":"move"}');}
 assert.equal(h.finish(),expected.update(']').digest('hex'));console.log(JSON.stringify({events:1000000,heapUsed:process.memoryUsage().heapUsed}));`;
 const child=spawnSync(process.execPath,['--max-old-space-size=32','--input-type=module','-e',script],{encoding:'utf8',timeout:60000});
 assert.equal(child.status,0,child.stderr);assert.equal(JSON.parse(child.stdout).events,1000000);
});
