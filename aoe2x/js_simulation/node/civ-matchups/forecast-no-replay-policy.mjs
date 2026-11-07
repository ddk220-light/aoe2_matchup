// Owner-approved execution policy: 1, 3 or 10 distinct seeds; no same-seed replay.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {existsSync,readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';
import {screeningDecision,screeningOutcome,verifySamplingReview as verifyV2,verifyPolicyInputs as verifyV2Inputs} from './forecast-screening-policy.mjs';
export {screeningDecision,screeningOutcome};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=path=>JSON.parse(readFileSync(path,'utf8'));
const overridesAllowed=['forecast-validation-lib.mjs','run-forecast-validation.mjs','export-forecast-reviews.mjs'].map(n=>'aoe2x/js_simulation/node/civ-matchups/'+n);
export function loadScreeningPolicy(dir){
 const file=resolve(dir,'sampling-policy-v3.json');return read(existsSync(file)?file:resolve(dir,'sampling-policy-v2.json'));
}
export function loadReviewPolicy(dir,hash){
 for(const file of ['sampling-policy-v3.json','sampling-policy-v2.json']){
  if(existsSync(resolve(dir,file))){const p=read(resolve(dir,file));if(p.amendmentHash===hash)return p;}
 }
 throw new Error('Unknown review sampling policy: '+hash);
}
export function verifyPolicyInputs(manifest,root,dir){
 const p=loadScreeningPolicy(dir);if(p.version==='decisive-agreement-screen-v2')return verifyV2Inputs(manifest,root,dir);
 const {amendmentHash,...body}=p;assert.equal(digest(body),amendmentHash);
 assert.equal(p.version,'distinct-seeds-no-replay-v3');assert.equal(p.baseCampaignHash,manifest.campaignHash);
 assert.equal(p.baseManifestSha256,sha(readFileSync(resolve(dir,'manifest.json'))));
 assert.equal(p.authorization.sourceRole,'user');assert(p.authorization.sourceMessage);
 assert.equal(p.independentExactReplayRequired,false);assert.equal(p.minimumWinnerHpFraction,0.25);
 assert.deepEqual(p.initialSeedsOnEscalation,[0,1,2]);assert.deepEqual(p.extraSeedsOnMixedWinners,[3,4,5,6,7,8,9]);
 const old=read(resolve(dir,'sampling-policy-v2.json'));
 assert.equal(old.amendmentHash,p.previousPolicyHash);
 assert.equal(sha(readFileSync(resolve(dir,'sampling-policy-v2.json'))),p.previousPolicyFileSha256);
 const {amendmentHash:oldHash,...oldBody}=old;assert.equal(digest(oldBody),oldHash);
 for(const r of old.additionalSourceFiles)assert.equal(sha(readFileSync(resolve(root,r.path))),r.sha256,'historical policy source changed');
 assert.deepEqual(p.legacyInProgressJobs,old.legacyInProgressJobs);
 assert.equal(sha(readFileSync(resolve(root,p.transition.journalFile))),p.transition.journalSha256);
 assert.equal(p.transition.pairReviewHashes.length,p.transition.reviewedJobs);
 for(const r of p.transition.pairReviewHashes)assert.equal(sha(readFileSync(resolve(root,r.path))),r.sha256,'existing review changed');
 const replacements=new Map(p.sourceOverrides.map(r=>[r.path,r]));
 assert.equal(replacements.size,p.sourceOverrides.length);
 assert.deepEqual([...replacements.keys()].sort(),[...overridesAllowed].sort());
 for(const r of manifest.runtimeFiles)assert.equal(sha(readFileSync(resolve(root,r.path))),r.sha256,r.path);
 for(const r of manifest.inputFiles){const replace=replacements.get(r.path);if(replace)assert.equal(replace.originalSha256,r.sha256);
  assert.equal(sha(readFileSync(resolve(root,r.path))),replace?.sha256??r.sha256,r.path);}
 assert(p.additionalSourceFiles.some(r=>r.path.endsWith('/forecast-no-replay-policy.mjs')));
 for(const r of p.additionalSourceFiles)assert.equal(sha(readFileSync(resolve(root,r.path))),r.sha256,r.path);
 return p;
}
export function noReplayEvidence(policy){return {required:false,performed:false,exact:null,reason:'owner_removed_same_seed_replays',samplingPolicyHash:policy.amendmentHash};}
export function verifySamplingReview(job,rows,originalOutcomes,review,policy){
 if(policy.version==='decisive-agreement-screen-v2')return verifyV2(job,rows,originalOutcomes,review,policy);
 assert.equal(policy.version,'distinct-seeds-no-replay-v3');assert.equal(policy.independentExactReplayRequired,false);
 assert.equal(review.samplingPolicyHash,policy.amendmentHash);
 const decision=screeningDecision(job,rows,originalOutcomes,policy);
 assert.equal(decision.requiredSeeds.length,0,'incomplete distinct seed set');
 assert.deepEqual(review.samplingDecision,decision);assert.equal(review.evidenceLevel,decision.evidenceLevel);
 assert.equal(review.seedCount,rows.length);assert.deepEqual(review.requiredSeeds,[]);
 assert.deepEqual(review.exactReplay,noReplayEvidence(policy),'no replay must be recorded as unperformed');
 assert.equal(review.outcome,screeningOutcome(job,rows,originalOutcomes,policy));
 return decision.evidenceLevel;
}
