import test from 'node:test';
import assert from 'node:assert/strict';
import {workerBudget, dispatchable} from './parallel-recovery-policy.mjs';
const policy={workersWhileMainActive:2,workersAfterMainStops:4};
test('workers grow only after ordinary gaps stop, accounting for prior worker',()=>{
  assert.equal(workerBudget(true,true,policy),1);
  assert.equal(workerBudget(true,false,policy),2);
  assert.equal(workerBudget(false,false,policy),4);
  assert.equal(workerBudget(false,true,policy),3);
});
test('handoff, active and failed seeds are never dispatched twice',()=>{
  const pending=[0,1,2,3,4,4,5].map(seed=>({job:{id:'j'},seed}));
  assert.deepEqual(dispatchable(pending,new Set(['j:0']),'j:1',['j:2'],4).map(x=>x.key),['j:3','j:4','j:5']);
  assert.deepEqual(dispatchable(pending,new Set(['j:0']),'j:1',['j:2'],2).map(x=>x.key),['j:3']);
});
test('lowering worker budget does not preempt active seed calculations',()=>{
  const pending=[{job:{id:'j'},seed:2}];
  assert.deepEqual(dispatchable(pending,new Set(['j:0','j:1']),null,[],1),[]);
});
