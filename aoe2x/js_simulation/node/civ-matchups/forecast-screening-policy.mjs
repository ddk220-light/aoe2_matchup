// Research sampling amendment. This changes seed selection, never battle physics.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {existsSync,readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';

export const POLICY_FILE='sampling-policy-v2.json';
const OVERRIDES=[
 'aoe2x/js_simulation/node/civ-matchups/forecast-validation-lib.mjs',
 'aoe2x/js_simulation/node/civ-matchups/run-forecast-validation.mjs',
 'aoe2x/js_simulation/node/civ-matchups/export-forecast-reviews.mjs',
];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export function loadScreeningPolicy(dir){
 const path=resolve(dir,POLICY_FILE);return existsSync(path)?JSON.parse(readFileSync(path,'utf8')):null;
}
export function verifyPolicyInputs(manifest,root,dir){
 const policy=loadScreeningPolicy(dir);
 const overrides=new Map(policy?.sourceOverrides.map(r=>[r.path,r])??[]);
 if(policy){
  const {amendmentHash,...body}=policy;assert.equal(digest(body),amendmentHash,'sampling amendment hash');
  assert.equal(policy.version,'decisive-agreement-screen-v2');
  assert.equal(policy.baseCampaignHash,manifest.campaignHash);
  assert.equal(policy.baseManifestSha256,sha(readFileSync(resolve(dir,'manifest.json'))));
  assert.equal(policy.authorization.sourceRole,'user');assert(policy.authorization.sourceMessage);
  assert.equal(policy.minimumWinnerHpFraction,0.25);
  assert.equal(policy.independentExactReplayRequired,true);
  assert.deepEqual(policy.initialSeedsOnEscalation,[0,1,2]);
  assert.deepEqual(policy.extraSeedsOnMixedWinners,[3,4,5,6,7,8,9]);
  assert.deepEqual([...overrides.keys()].sort(),[...OVERRIDES].sort(),'only sampling source files may be amended');
  assert.equal(overrides.size,policy.sourceOverrides.length);
  assert.equal(new Set(policy.legacyInProgressJobs).size,policy.legacyInProgressJobs.length);
  assert.equal(policy.transition.journalSha256,sha(readFileSync(resolve(root,policy.transition.journalFile))));
  assert.equal(policy.transition.pairReviewHashes.length,policy.transition.reviewedJobs);
  for(const r of policy.transition.pairReviewHashes)assert.equal(sha(readFileSync(resolve(root,r.path))),r.sha256,'pre-amendment review changed');
  assert(policy.additionalSourceFiles.some(r=>r.path.endsWith('/forecast-screening-policy.mjs')));
  for(const r of policy.additionalSourceFiles)assert.equal(sha(readFileSync(resolve(root,r.path))),r.sha256,r.path);
 }
 // Runtime files are deliberately outside the override mechanism.
 for(const r of manifest.runtimeFiles)assert.equal(sha(readFileSync(resolve(root,r.path))),r.sha256,r.path);
 for(const r of manifest.inputFiles){
  const override=overrides.get(r.path);if(override)assert.equal(override.originalSha256,r.sha256);
  assert.equal(sha(readFileSync(resolve(root,r.path))),override?.sha256??r.sha256,r.path);
 }
 return policy;
}

function fullRequired(rows){
 const seeds=new Map(rows.map(r=>[r.seed,r]));
 const initial=[0,1,2].filter(s=>!seeds.has(s));if(initial.length)return initial;
 return new Set([0,1,2].map(s=>seeds.get(s).winnerOwner)).size>1?[3,4,5,6,7,8,9].filter(s=>!seeds.has(s)):[];
}
function physicalOutcome(job,owner){
 if(owner!==2&&owner!==3)return 'close_uncertain';
 return job.profileHashes[owner-2]===job.pairKey.split('|')[0]?'a_win':'b_win';
}
function terminalMargin(row){
 if(![2,3].includes(row.winnerOwner))return null;
 const win=row.winnerOwner===2?'unit':'opponent',lose=row.winnerOwner===2?'opponent':'unit';
 const start=row[win+'StartingHp'],remaining=row[win+'RemainingHp'];
 if(!Number.isFinite(start)||!Number.isFinite(remaining)||start<=0||remaining<=0||remaining>start)return null;
 if(!(row[win+'Survivors']>0)||row[lose+'Survivors']!==0||row[lose+'RemainingHp']!==0)return null;
 return remaining/start;
}
export function screeningDecision(job,rows,originalOutcomes,policy){
 assert(policy&&policy.minimumWinnerHpFraction===0.25);
 assert.equal(new Set(rows.map(r=>r.seed)).size,rows.length,'duplicate seed');
 assert(rows.every(r=>Number.isInteger(r.seed)&&r.seed>=0&&r.seed<=9),'unknown seed');
 const first=rows.find(r=>r.seed===0);
 if(!first)return {evidenceLevel:'multi_seed_validation',reason:'first_seed_required',requiredSeeds:[0]};
 const margin=terminalMargin(first),outcome=physicalOutcome(job,first.winnerOwner);
 const agrees=originalOutcomes.length>0&&originalOutcomes.every(x=>x===outcome)&&outcome!=='close_uncertain';
 const legacy=policy.legacyInProgressJobs.includes(job.id);
 const decisive=margin!==null&&margin>=policy.minimumWinnerHpFraction;
 const reason=legacy?'pre_amendment_in_progress':rows.length>1?'additional_seed_evidence':!agrees?'first_seed_disagrees':!decisive?'first_seed_close_or_not_decisive':'decisive_forecast_agreement';
 const single=!legacy&&rows.length===1&&agrees&&decisive;
 return {evidenceLevel:single?'single_seed_confirmation':'multi_seed_validation',reason,
  firstSeedOutcome:outcome,firstSeedAgrees:agrees,firstSeedWinnerHpFraction:margin,
  minimumWinnerHpFraction:policy.minimumWinnerHpFraction,requiredSeeds:single?[]:fullRequired(rows)};
}
export function screeningOutcome(job,rows,originalOutcomes,policy){
 assert.equal(screeningDecision(job,rows,originalOutcomes,policy).requiredSeeds.length,0,'incomplete sampling protocol');
 const winners=new Set(rows.map(r=>r.winnerOwner));
 return winners.size===1?physicalOutcome(job,[...winners][0]):'close_uncertain';
}
export function verifySamplingReview(job,rows,originalOutcomes,review,policy){
 assert(policy);assert.equal(review.samplingPolicyHash,policy.amendmentHash);
 const decision=screeningDecision(job,rows,originalOutcomes,policy);
 assert.equal(decision.requiredSeeds.length,0,'incomplete sampling protocol');
 assert.deepEqual(review.samplingDecision,decision);
 assert.equal(review.evidenceLevel,decision.evidenceLevel);
 assert.equal(review.seedCount,rows.length);
 assert.deepEqual(review.requiredSeeds,[]);
 assert.equal(review.exactReplay.exact,true,'exact replay is still required');
 assert.equal(review.outcome,screeningOutcome(job,rows,originalOutcomes,policy));
 return decision.evidenceLevel;
}
