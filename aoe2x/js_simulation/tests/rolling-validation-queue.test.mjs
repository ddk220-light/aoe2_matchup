import assert from 'node:assert/strict';
import test from 'node:test';
import {runOrderedQueue} from '../node/civ-matchups/rolling-validation-queue.mjs';
const turn=()=>new Promise(resolve=>setImmediate(resolve));
test('a slow context cannot idle available workers behind a phase boundary',async()=>{
 let release;const stalled=new Promise(resolve=>{release=resolve;});const started=[],finished=[];let active=0,max=0;
 const jobs=Array.from({length:12},(_,id)=>({id}));
 const running=runOrderedQueue({jobs,workers:4,run:async j=>{
  started.push(j.id);max=Math.max(max,++active);if(j.id===0)await stalled;await turn();active--;
 },onSettled:j=>finished.push(j.id)});
 for(let i=0;i<10;i++)await turn();
 assert(started.includes(11),'later audit phases must get available slots');
 assert(!finished.includes(0));assert.equal(max,4);assert.equal(new Set(started).size,12);
 release();await running;assert.equal(finished.length,12);
});
test('resume skips reviewed and quarantined contexts without running them',async()=>{
 const started=[];await runOrderedQueue({jobs:[0,1,2,3].map(id=>({id})),workers:2,
  skip:j=>j.id===0||j.id===2,run:async j=>{started.push(j.id);}});
 assert.deepEqual(started,[1,3]);
});
test('stop drains active work without admitting additional jobs',async()=>{
 let stop=false;const started=[];
 await runOrderedQueue({jobs:[0,1,2,3,4].map(id=>({id})),workers:2,shouldStop:()=>stop,
  run:async j=>{started.push(j.id);stop=true;await turn();}});
 assert.deepEqual(started,[0]);
});
test('duplicate contexts are rejected before execution',async()=>{
 await assert.rejects(runOrderedQueue({jobs:[{id:1},{id:1}],workers:2,run:async()=>{throw Error('must not run');}}),/duplicate queued context/);
});
