import assert from 'node:assert/strict';
import test from 'node:test';
import {gridReachability} from '../src/combat/grid-reachability.js';

test('diagonal movement cannot cut either blocked corner',()=>{
  const goals=Uint8Array.of(0,0,0,1);
  assert.equal(gridReachability(2,2,0,goals,(_,to)=>to===3).reachable,false);
  assert.equal(gridReachability(2,2,0,goals,()=>true).reachable,true);
});

test('crowd escape reachability preserves directed entry restrictions',()=>{
  const pressure=[2,1,0],canEnter=(a,b)=>pressure[b]<=pressure[a];
  assert.equal(gridReachability(3,1,0,Uint8Array.of(0,0,1),canEnter).reachable,true);
  assert.equal(gridReachability(3,1,2,Uint8Array.of(1,0,0),canEnter).reachable,false);
  assert.equal(gridReachability(3,1,0,Uint8Array.of(0,0,0),canEnter).reachable,false);
});
