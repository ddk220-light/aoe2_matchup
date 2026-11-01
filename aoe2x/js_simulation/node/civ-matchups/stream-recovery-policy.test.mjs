import test from 'node:test';
import assert from 'node:assert/strict';
import {remainingSeeds, decision, validateRecord} from './stream-recovery-policy.mjs';

test('missing seeds are not a result, and V3-reserved work cannot complete V2',()=>{
  const rows=new Map([[0,{outcome:'win'}],[1,{outcome:'win'}]]);
  assert.deepEqual(remainingSeeds(rows,[0,1,2,3]),[2,3]);
  assert.throws(()=>decision(rows,[0,1,2]),/missing required seed/);
});
test('initial disagreement requires seven extra repaired-engine seeds',()=>{
  const rows=new Map([0,1,2].map(i=>[i,{outcome:i===2?'loss':'win'}]));
  assert.deepEqual(remainingSeeds(rows),[3,4,5,6,7,8,9]);
  for(let seed=3;seed<10;seed++)rows.set(seed,{outcome:'win'});
  assert.equal(decision(rows),'close_uncertain');
});
test('all known seeds are included and any later variation stays close',()=>{
  const rows=new Map([0,1,2].map(i=>[i,{outcome:'win'}]));
  assert.equal(decision(rows),'win');rows.set(5,{outcome:'loss'});
  assert.equal(decision(rows),'close_uncertain');
});
test('records reject different versions, counts, timeouts and invalid hashes',()=>{
  const job={id:'j',pairKey:'a|b',counts:[27,17],profileHashes:['a','b'],scenarioHash:'s'};
  const row={...job,matchupId:'j',campaignHash:'v2',seed:0,outcome:'win',ticks:60,simulationSeconds:1,
    finalStateHash:'a'.repeat(64),eventLogHash:'b'.repeat(64)};
  validateRecord(row,job,'v2');
  for(const delta of [{campaignHash:'v3'},{counts:[27,18]},{outcome:'timeout'},{seed:10},{eventLogHash:''}])
    assert.throws(()=>validateRecord({...row,...delta},job,'v2'));
});
