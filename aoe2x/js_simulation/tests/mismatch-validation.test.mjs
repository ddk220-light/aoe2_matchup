import assert from 'node:assert/strict';
import test from 'node:test';
import {required,canonicalOutcome,exact} from '../node/civ-matchups/mismatch-validation-lib.mjs';
test('only complete seed sets classify and mixed initial winners require all ten',()=>{
 assert.deepEqual(required([]),[0,1,2]);
 const rows=[0,1,2].map(seed=>({seed,winnerOwner:2}));assert.deepEqual(required(rows),[]);
 rows[1].winnerOwner=3;assert.deepEqual(required(rows),[3,4,5,6,7,8,9]);
 const job={pairKey:'a|b',profileHashes:['b','a']};assert.throws(()=>canonicalOutcome(job,rows));
 for(let seed=3;seed<10;seed++)rows.push({seed,winnerOwner:2});assert.equal(canonicalOutcome(job,rows),'close_uncertain');
});
test('physical team order maps to canonical profile order without transferring orientation',()=>{
 const rows=[0,1,2].map(seed=>({seed,winnerOwner:2}));
 assert.equal(canonicalOutcome({pairKey:'a|b',profileHashes:['b','a']},rows),'b_win');
 assert.equal(canonicalOutcome({pairKey:'a|b',profileHashes:['a','b']},rows),'a_win');
});
test('an exact replay requires winner, ticks, final state and every event',()=>{
 const row={winnerOwner:2,ticks:25,finalStateHash:'state',eventLogHash:'events'};
 assert(exact({...row},row));for(const k of Object.keys(row))assert(!exact({...row,[k]:'changed'},row));
});
