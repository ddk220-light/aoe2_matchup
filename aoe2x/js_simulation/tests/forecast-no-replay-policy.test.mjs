import assert from 'node:assert/strict';
import test from 'node:test';
import {screeningDecision,screeningOutcome,verifySamplingReview,noReplayEvidence} from '../node/civ-matchups/forecast-no-replay-policy.mjs';
const p={version:'distinct-seeds-no-replay-v3',amendmentHash:'v3-test',minimumWinnerHpFraction:0.25,independentExactReplayRequired:false,legacyInProgressJobs:[]};
const j={id:'test',profileHashes:['a','z'],pairKey:'a|z'};
const row=(seed,owner=2,hp=50)=>({seed,winnerOwner:owner,unitStartingHp:100,opponentStartingHp:100,unitRemainingHp:owner===2?hp:0,opponentRemainingHp:owner===3?hp:0,unitSurvivors:owner===2?1:0,opponentSurvivors:owner===3?1:0});
function review(rows,original=['a_win']){const decision=screeningDecision(j,rows,original,p);return {samplingPolicyHash:p.amendmentHash,samplingDecision:decision,evidenceLevel:decision.evidenceLevel,seedCount:rows.length,requiredSeeds:[],exactReplay:noReplayEvidence(p),outcome:screeningOutcome(j,rows,original,p)};}
test('clear forecast agreement is accepted after exactly one execution with no replay',()=>{
 const rows=[row(0)],r=review(rows);assert.equal(verifySamplingReview(j,rows,['a_win'],r,p),'single_seed_confirmation');
 assert.deepEqual(r.exactReplay,{required:false,performed:false,exact:null,reason:'owner_removed_same_seed_replays',samplingPolicyHash:'v3-test'});
});
test('close and disagreeing results require three distinct seeds, with no fourth replay',()=>{
 for(const original of [['a_win'],['b_win']]){
  const rows=[0,1,2].map(seed=>row(seed,2,10)),r=review(rows,original);
  assert.equal(verifySamplingReview(j,rows,original,r,p),'multi_seed_validation');assert.equal(r.seedCount,3);assert.equal(r.exactReplay.performed,false);
 }
 assert.throws(()=>review([row(0,2,10)]),/incomplete/);
});
test('mixed winners require ten distinct seeds and never an eleventh replay',()=>{
 const rows=[0,1,2,3,4,5,6,7,8,9].map(seed=>row(seed,seed===1?3:2));
 const r=review(rows);assert.equal(r.seedCount,10);assert.equal(r.outcome,'close_uncertain');
 assert.equal(verifySamplingReview(j,rows,['a_win'],r,p),'multi_seed_validation');
 assert.throws(()=>review(rows.slice(0,9)),/incomplete/);
});
test('replay success cannot be invented and already collected seed evidence cannot be dropped',()=>{
 const rows=[row(0)],r=review(rows);
 assert.throws(()=>verifySamplingReview(j,rows,['a_win'],{...r,exactReplay:{exact:true}},p));
 assert.throws(()=>verifySamplingReview(j,[...rows,row(1,3)],['a_win'],r,p),/incomplete/);
 assert.throws(()=>screeningDecision(j,[row(0),row(0)],['a_win'],p),/duplicate/);
});
test('historical v2 reviews retain their actual replay requirement',()=>{
 const old={...p,version:'decisive-agreement-screen-v2',amendmentHash:'v2-test',independentExactReplayRequired:true};
 const rows=[row(0)],r={...review(rows),samplingPolicyHash:old.amendmentHash};
 assert.throws(()=>verifySamplingReview(j,rows,['a_win'],r,old),/exact replay/);
 assert.equal(verifySamplingReview(j,rows,['a_win'],{...r,exactReplay:{exact:true}},old),'single_seed_confirmation');
});
