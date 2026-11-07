import assert from 'node:assert/strict';
import test from 'node:test';
import {screeningDecision as decide,screeningOutcome,verifySamplingReview} from '../node/civ-matchups/forecast-screening-policy.mjs';

const policy={minimumWinnerHpFraction:0.25,legacyInProgressJobs:[],amendmentHash:'approved-policy'};
const job={id:'fixture',profileHashes:['z','a'],pairKey:'a|z'};
function row(seed=0,owner=2,hp=50){return {seed,winnerOwner:owner,
 unitStartingHp:100,opponentStartingHp:200,
 unitRemainingHp:owner===2?hp:0,opponentRemainingHp:owner===3?hp:0,
 unitSurvivors:owner===2?3:0,opponentSurvivors:owner===3?4:0};}
const agrees=['b_win'];

test('only decisive agreeing seed zero may stop early, including exact threshold',()=>{
 for(const hp of [25,50,100]){
  const result=decide(job,[row(0,2,hp)],agrees,policy);
  assert.equal(result.evidenceLevel,'single_seed_confirmation');assert.deepEqual(result.requiredSeeds,[]);
  assert.equal(screeningOutcome(job,[row(0,2,hp)],agrees,policy),'b_win');
 }
 assert.deepEqual(decide(job,[],agrees,policy).requiredSeeds,[0]);
 assert.deepEqual(decide(job,[row(1)],agrees,policy).requiredSeeds,[0]);
});
test('close agreement, disagreement, close forecast and a draw require more independent seeds',()=>{
 for(const [rows,original] of [[[row(0,2,24.999)],agrees],[[row()],['a_win']],[[row()],['close_uncertain']],[[row(0,null)],agrees],[[row()],[]]]){
  const result=decide(job,rows,original,policy);assert.equal(result.evidenceLevel,'multi_seed_validation');
  assert.deepEqual(result.requiredSeeds,[1,2]);
 }
});
test('decisiveness uses winning physical side HP and requires complete elimination',()=>{
 assert.equal(decide(job,[row(0,3,50)],['a_win'],policy).evidenceLevel,'single_seed_confirmation');
 assert.equal(decide(job,[row(0,3,49)],['a_win'],policy).evidenceLevel,'multi_seed_validation');
 for(const change of [{opponentRemainingHp:1},{opponentSurvivors:1},{unitStartingHp:0},{unitRemainingHp:101},{unitRemainingHp:NaN},{unitSurvivors:0}]){
  assert.equal(decide(job,[{...row(),...change}],agrees,policy).evidenceLevel,'multi_seed_validation');
 }
});
test('already collected conflicting evidence and pre-amendment work are never discarded',()=>{
 const legacy={...policy,legacyInProgressJobs:['fixture']};
 assert.equal(decide(job,[row()],agrees,legacy).reason,'pre_amendment_in_progress');
 assert.deepEqual(decide(job,[row()],agrees,legacy).requiredSeeds,[1,2]);
 assert.deepEqual(decide(job,[row(),row(1,3)],agrees,policy).requiredSeeds,[2]);
 const mixed=[row(),row(1,3),row(2)];
 assert.deepEqual(decide(job,mixed,agrees,policy).requiredSeeds,[3,4,5,6,7,8,9]);
 assert.throws(()=>screeningOutcome(job,mixed,agrees,policy),/incomplete/);
 assert.equal(screeningOutcome(job,[...mixed,...[3,4,5,6,7,8,9].map(s=>row(s))],agrees,policy),'close_uncertain');
});
test('escalated stable outcomes can correct the forecast only after three seeds',()=>{
 const rows=[0,1,2].map(seed=>row(seed,3));
 assert.equal(decide(job,rows,agrees,policy).evidenceLevel,'multi_seed_validation');
 assert.deepEqual(decide(job,rows,agrees,policy).requiredSeeds,[]);
 assert.equal(screeningOutcome(job,rows,agrees,policy),'a_win');
 assert.throws(()=>screeningOutcome(job,rows.slice(0,2),agrees,policy),/incomplete/);
});
test('canonical display orientation maps physical profile hashes without transferring a winner',()=>{
 assert.equal(screeningOutcome(job,[row()],agrees,policy),'b_win');
 const reversedProfiles={...job,profileHashes:['a','z']};
 assert.equal(screeningOutcome(reversedProfiles,[row()],['a_win'],policy),'a_win');
 assert.equal(decide(reversedProfiles,[row()],agrees,policy).evidenceLevel,'multi_seed_validation');
});
test('review verification rejects missing replay, forged mode, altered margin and wrong policy',()=>{
 const rows=[row()],samplingDecision=decide(job,rows,agrees,policy);
 const review={samplingPolicyHash:policy.amendmentHash,samplingDecision,evidenceLevel:'single_seed_confirmation',seedCount:1,requiredSeeds:[],exactReplay:{exact:true},outcome:'b_win'};
 assert.equal(verifySamplingReview(job,rows,agrees,review,policy),'single_seed_confirmation');
 for(const changed of [{samplingPolicyHash:'other'},{evidenceLevel:'multi_seed_validation'},{seedCount:3},{exactReplay:{exact:false}},{outcome:'a_win'},
  {samplingDecision:{...samplingDecision,firstSeedWinnerHpFraction:1}}])assert.throws(()=>verifySamplingReview(job,rows,agrees,{...review,...changed},policy));
 assert.throws(()=>verifySamplingReview(job,[row(0,2,5)],agrees,review,policy),/incomplete/);
});
test('duplicate or out-of-range seeds fail rather than manufacturing complete evidence',()=>{
 assert.throws(()=>decide(job,[row(),row()],agrees,policy),/duplicate/);
 assert.throws(()=>decide(job,[row(10)],agrees,policy),/unknown seed/);
});
