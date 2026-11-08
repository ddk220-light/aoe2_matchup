import assert from 'node:assert/strict';
import {parseArgs} from 'node:util';
const {values}=parseArgs({options:{output:{type:'string'}}});
assert(values.output,'Use --output <new immutable path>');
import {readFileSync,writeFileSync,readdirSync,existsSync,statSync,readlinkSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {execFileSync} from 'node:child_process';
import {DIR,ROOT,verifyManifest,load,gzlines,digest,sha,required,canonicalOutcome,exact} from '../aoe2x/js_simulation/node/civ-matchups/forecast-validation-lib.mjs';
import {loadScreeningPolicy,loadReviewPolicy,verifySamplingReview} from '../aoe2x/js_simulation/node/civ-matchups/forecast-no-replay-policy.mjs';
const m=verifyManifest(),policy=loadScreeningPolicy(DIR);
assert.equal(m.campaignHash,'d6c03bd7b04066005a7b9d12f9bd7e1f2264ddd64b0c2a9264ecdd66ba8cc123');
assert.equal(policy.amendmentHash,'4404ca505096341c2bcea03e1376ed5d7c27f7a1f6d6452bd92a9a526273c30c');
const approval=load(resolve(DIR,'launch-approval.json'));assert(approval.durationApproved&&approval.sourceRole==='user'&&approval.sourceMessage==='Yes start');
const jobsArr=gzlines(resolve(DIR,'jobs.jsonl.gz')),jobs=new Map(jobsArr.map(j=>[j.id,j]));assert.equal(jobs.size,39124);
const original=new Map(gzlines(resolve(DIR,'original-evidence.jsonl.gz')).map(e=>[e.evidenceId,e.evidence]));
const held=gzlines(resolve(DIR,'held-contexts.jsonl.gz'));assert.equal(held.length,24);
const phases=readdirSync(resolve(DIR,'reviews')).filter(f=>/^\d{3}\.json$/.test(f)).sort().map(f=>load(resolve(DIR,'reviews',f)));
const refs=[],reviews=new Map();
for(const f of readdirSync(resolve(DIR,'pair-reviews')).filter(f=>f.endsWith('.json')).sort()){
 const file=resolve(DIR,'pair-reviews',f),bytes=readFileSync(file),r=JSON.parse(bytes);assert(!reviews.has(r.jobId));reviews.set(r.jobId,r);
 refs.push({jobId:r.jobId,reviewHash:r.reviewHash,file:relative(ROOT,file),sha256:sha(bytes)});
}
const capturedAt=new Date().toISOString();
const raw=readFileSync(resolve(DIR,'runs.jsonl')),records=raw.toString().trim().split('\n').filter(Boolean).map(JSON.parse),native=new Map(),byJob=new Map();
for(const row of records){
 const key=row.matchupId+':'+row.seed;assert(!native.has(key),'duplicate native seed');native.set(key,row);
 const job=jobs.get(row.matchupId);assert(job);assert.equal(row.campaignHash,m.campaignHash);assert.equal(row.contextHash,job.contextHash);assert.equal(row.physicsVersion,m.physicsVersion);assert.equal(row.executionVersion,m.executionVersion);assert.equal(row.purpose,'fresh_measurement');
 assert.deepEqual(row.profileHashes,job.profileHashes);assert.deepEqual(row.counts,job.counts);assert.equal(row.scenarioHash,job.scenarioHash);assert.equal(row.pairKey,job.pairKey);
 if(!byJob.has(job.id))byJob.set(job.id,[]);byJob.get(job.id).push(row);
}
const counts={single:0,multi:0,changed:0,retained:0,historicalReplay:0,noReplay:0,mixedWinners:0,closeUncertain:0};
const categories={};
for(const [id,r] of reviews){
 const j=jobs.get(id),{reviewHash,...body}=r;assert(j);assert.equal(digest(body),reviewHash);assert.equal(r.status,'passed');assert.equal(r.campaignHash,m.campaignHash);assert.equal(r.physicsVersion,m.physicsVersion);assert.deepEqual(r.context,j.context);assert.equal(r.contextHash,j.contextHash);assert.equal(r.pairKey,j.pairKey);assert.deepEqual(r.originalEvidenceIds,j.evidenceIds);assert.deepEqual(r.requiredSeeds,[]);
 const measured=byJob.get(id)??[];assert.equal(measured.length,r.seedCount);assert.equal(measured.length,r.seedResults.length);
 const originalOutcomes=j.evidenceIds.map(i=>original.get(i).outcome);
 if(r.samplingPolicyHash)verifySamplingReview(j,measured,originalOutcomes,r,loadReviewPolicy(DIR,r.samplingPolicyHash));
 else {assert.equal(required(measured).length,0);assert.equal(r.outcome,canonicalOutcome(j,measured));}
 for(const s of r.seedResults){const row=native.get(id+':'+s.seed);assert(row);assert.equal(digest(row),s.recordHash);assert.equal(row.finalStateHash,s.finalStateHash);assert.equal(row.eventLogHash,s.eventLogHash);assert.equal(row.winnerOwner,s.winnerOwner);assert.equal(row.ticks,s.ticks);}
 assert.equal(r.changed,originalOutcomes.some(o=>o!==r.outcome));
 assert.deepEqual(r.originalOutcomes,j.evidenceIds.map(i=>({evidenceId:i,outcome:original.get(i).outcome,evidenceType:original.get(i).evidenceType})));
 const owners=new Set(measured.map(x=>x.winnerOwner));const owner=[...owners][0];const outcome=owners.size===1&&[2,3].includes(owner)?j.profileHashes[owner-2]===j.pairKey.split('|')[0]?'a_win':'b_win':'close_uncertain';assert.equal(r.outcome,outcome);
 counts[r.evidenceLevel==='single_seed_confirmation'?'single':'multi']++;counts[r.changed?'changed':'retained']++;
 if(owners.size>1)counts.mixedWinners++;if(r.outcome==='close_uncertain')counts.closeUncertain++;
 if(r.exactReplay.performed===false){assert.equal(r.exactReplay.required,false);assert.equal(r.exactReplay.exact,null);counts.noReplay++;}
 else {assert.equal(r.exactReplay.exact,true);const control=measured.find(x=>x.seed===r.exactReplay.seed);assert(control);assert(exact(r.exactReplay.result,control));counts.historicalReplay++;}
 categories[j.predictionTier]=(categories[j.predictionTier]??0)+1;
}
assert.equal(counts.historicalReplay,651);assert.equal(counts.single+counts.multi,reviews.size);assert.equal(counts.changed+counts.retained,reviews.size);
const phaseChecks=[];
for(const p of phases){
 assert.equal(p.campaignHash,m.campaignHash);assert.equal(p.reviewHashes.length,p.reviewedJobs);
 for(const ref of p.reviewHashes)assert.equal(reviews.get(ref.jobId)?.reviewHash,ref.reviewHash);
 if(p.status==='passed')assert.equal(p.reviewedJobs,p.plannedJobs);
 phaseChecks.push({phase:p.phase,status:p.status,reviewed:p.reviewedJobs,planned:p.plannedJobs});
}
const attempts=readFileSync(resolve(DIR,'attempts.jsonl'),'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const exhausted=[...new Set(attempts.filter(a=>a.exhausted).map(a=>a.matchupId))].sort();
for(const id of exhausted)assert(!reviews.has(id));
const attemptChecks=attempts.map(a=>{
 assert.equal(a.campaignHash,m.campaignHash);assert.equal(a.purpose,'fresh_measurement');assert(existsSync(resolve(ROOT,a.progressPath)));
 const bytes=readFileSync(resolve(ROOT,a.progressPath)),last=bytes.toString().trim().split('\n').at(-1),snapshot=JSON.parse(last);
 return {jobId:a.matchupId,seed:a.seed,attempt:a.attempt,exhausted:a.exhausted,progressPath:a.progressPath,progressSha256:sha(bytes),lastSnapshotTick:snapshot.tick,recordedLastProgress:a.lastProgress};
});
const state=load(resolve(DIR,'state.json')),runnerLock=load(resolve(DIR,'.runner.lock')),supervisorPid=Number(readFileSync(resolve(DIR,'.supervisor.lock'),'utf8').trim());
assert.equal(runnerLock.campaignHash,m.campaignHash);assert.equal(runnerLock.pid,state.pid);assert.equal(state.status,'running');assert.equal(state.samplingPolicyHash,policy.amendmentHash);assert.equal(state.independentExactReplayRequired,false);assert.equal(state.active.length,4);
function processHealth(pid,needle){const status=readFileSync('/proc/'+pid+'/status','utf8'),command=readFileSync('/proc/'+pid+'/cmdline').toString().replaceAll('\0',' ');assert(!/^State:\s+Z/m.test(status));assert(command.includes(needle));assert.equal(readlinkSync('/proc/'+pid+'/cwd'),ROOT);return {pid,live:true,command};}
const health={runner:processHealth(state.pid,'run-forecast-validation.mjs'),supervisor:processHealth(supervisorPid,'supervise_civ_forecast_validation.py'),activeWorkers:state.active.length,active:state.active};
for(const a of state.active){assert.equal(a.purpose,'fresh_measurement');assert(!exhausted.includes(a.jobId));}
const cutoff=new Date(policy.recordedAt).getTime();
const newReplayFiles=readdirSync(resolve(DIR,'progress')).filter(f=>f.includes('replay')&&statSync(resolve(DIR,'progress',f)).mtimeMs>=cutoff);assert.deepEqual(newReplayFiles,[]);
const baseline='36626bc0f74242de5482d98362695cec15226eb87cba8767371841a62bd231d5';assert.equal(sha(readFileSync(resolve(DIR,'sources/production-baseline.db'))),baseline);const releaseStatus=load(resolve(DIR,'website-release-status.json'));assert.equal(releaseStatus.frozenResearchBaseline.commit,m.sourceWebsiteCommit);assert.equal(releaseStatus.frozenResearchBaseline.databaseSha256,baseline);assert.equal(releaseStatus.dataOnlyMonitoring,true);assert.equal(releaseStatus.futureReleasesRequireExplicitApproval,true);const approved=releaseStatus.latestApprovedProduction;const receipt=load(resolve(DIR,approved.verification));assert.equal(receipt.status,'verified_live');assert.equal(receipt.commit,approved.commit);assert.equal(receipt.servingDatabaseSha256,approved.servingDatabaseSha256);assert.equal(sha(readFileSync('/workspace/aoe2_advisor_release/data/golden/civ_matchups_first_pass.db')),approved.servingDatabaseSha256);
const gitRefs=execFileSync('git',['ls-remote','origin','refs/heads/main','refs/heads/staging','refs/heads/simulations/civ-forecast-validation-2026-11-07'],{cwd:ROOT,encoding:'utf8'}).trim().split('\n').map(l=>l.split(/\s+/));
const branchRefs=Object.fromEntries(gitRefs.map(([sha,ref])=>[ref,sha]));assert.equal(branchRefs['refs/heads/main'],approved.commit);assert.equal(branchRefs['refs/heads/staging'],approved.commit);
const audit={status:'passed',capturedAt,verifiedAt:new Date().toISOString(),campaignHash:m.campaignHash,samplingPolicyHash:policy.amendmentHash,totalContexts:39148,reviewedContexts:reviews.size,completionPercent:Math.round(reviews.size/39148*1000)/10,singleSeedConfirmations:counts.single,multiSeedValidations:counts.multi,changedOutcomes:counts.changed,retainedForecasts:counts.retained,mixedWinners:counts.mixedWinners,closeUncertain:counts.closeUncertain,remainingContexts:39148-reviews.size,heldContexts:held.length,exhaustedContexts:exhausted.length,exhaustedJobIds:exhausted,originalConfidenceCategories:categories,evidenceCounts:counts,phaseChecks,attemptChecks,workerHealth:health,noReplayStatus:{enabled:false,newReplayFiles:0,historicalReplayEvidencePreserved:counts.historicalReplay},runtimeFilesVerified:m.runtimeFiles.length,originalInputFilesVerified:m.inputFiles.length,productionUnchanged:true,productionCommit:approved.commit,productionDatabaseSha256:approved.servingDatabaseSha256,frozenResearchBaselineCommit:m.sourceWebsiteCommit,frozenResearchBaselineDatabaseSha256:baseline,productionVerification:approved.verification,branchRefs,liveNativeRecords:records.length,liveNativeJournalSha256:sha(raw),reviewRefs:refs,liveReviewSetHash:digest(refs),simulationExecutionsForVerification:0};
const file=resolve(values.output);writeFileSync(file,JSON.stringify(audit,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({...audit,reviewRefs:refs.length,attemptChecks:attemptChecks.length,phaseChecks:phaseChecks.length,workerHealth:{runner:health.runner.pid,supervisor:health.supervisor.pid,activeWorkers:health.activeWorkers}},null,2));
