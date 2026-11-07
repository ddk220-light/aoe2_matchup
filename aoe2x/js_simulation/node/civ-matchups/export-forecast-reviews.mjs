#!/usr/bin/env node
// Independent journal-to-review verification before any serving data changes.
import assert from 'node:assert/strict';
import {existsSync,readFileSync,readdirSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {gzipSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
import {DIR,ROOT,load,gzlines,lines,verifyManifest,sha,digest,required,canonicalOutcome,exact,json,now} from './forecast-validation-lib.mjs';
import {loadScreeningPolicy,loadReviewPolicy,screeningOutcome,verifySamplingReview} from './forecast-no-replay-policy.mjs';
const args=process.argv.slice(2),arg=name=>args.includes(name)?args[args.indexOf(name)+1]:null;
const output=arg('--output');assert(output,'--output required');const out=resolve(output);
assert(!existsSync(out),'snapshot already exists');
const manifest=verifyManifest(),jobs=new Map(gzlines(resolve(DIR,'jobs.jsonl.gz')).map(j=>[j.id,j]));
const samplingPolicy=loadScreeningPolicy(DIR);
const sourceCommit=execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim();
const expected=new Map(gzlines(resolve(DIR,'expected-native-records.jsonl.gz')).map(r=>[r.jobId,r.records]));
const original=new Map(gzlines(resolve(DIR,'original-evidence.jsonl.gz')).map(r=>[r.evidenceId,r.evidence]));
const reviewedOnly=args.includes('--reviewed-only');
const journalPath=relative(ROOT,resolve(DIR,'runs.jsonl'));
const records=reviewedOnly?execFileSync('git',['show',`${sourceCommit}:${journalPath}`],{cwd:ROOT,encoding:'utf8',maxBuffer:512*1024*1024}).trim().split('\n').filter(Boolean).map(JSON.parse):existsSync(resolve(DIR,'runs.jsonl'))?lines(resolve(DIR,'runs.jsonl')):[];
const fresh=new Map(),freshCounts=new Map();for(const r of records){const key=`${r.matchupId}:${r.seed}`;assert(!fresh.has(key));assert.equal(r.campaignHash,manifest.campaignHash);fresh.set(key,r);freshCounts.set(r.matchupId,(freshCounts.get(r.matchupId)??0)+1);}
const through=arg('--through-phase'),phases=readdirSync(resolve(DIR,'reviews')).filter(f=>/^\d{3}\.json$/.test(f)&&(!through||f.slice(0,3)<=through)).sort();
assert(phases.length||reviewedOnly,'no complete reviewed phase');
const ids=new Set(),phaseRefs=[],expectedReviewHashes=new Map();
if(reviewedOnly){
 const prefix=relative(ROOT,resolve(DIR,'pair-reviews'));
 // The full frozen review list exceeds Node's default 1 MiB output buffer.
 const committed=execFileSync('git',['ls-tree','-r','--name-only',sourceCommit,'--',prefix],{cwd:ROOT,encoding:'utf8',maxBuffer:16*1024*1024}).trim().split('\n').filter(Boolean);
 for(const path of committed){const r=load(resolve(ROOT,path));
  assert.equal(sha(readFileSync(resolve(ROOT,path))),sha(execFileSync('git',['show',`${sourceCommit}:${path}`],{cwd:ROOT})));
  ids.add(r.jobId);
 }
 assert(ids.size,'no committed reviewed contexts');
}
for(const f of reviewedOnly?[]:phases){const p=load(resolve(DIR,'reviews',f));assert.equal(p.status,'passed','cannot publish incomplete phase');
 assert.equal(p.campaignHash,manifest.campaignHash);assert.equal(p.plannedJobs,p.reviewedJobs);for(const r of p.reviewHashes){assert(!ids.has(r.jobId));ids.add(r.jobId);expectedReviewHashes.set(r.jobId,r.reviewHash);}
 phaseRefs.push({file:relative(ROOT,resolve(DIR,'reviews',f)),sha256:sha(readFileSync(resolve(DIR,'reviews',f)))});
}
if(!through&&!reviewedOnly)assert.equal(ids.size,manifest.totalForecastContexts,'remaining forecasts not reviewed; use explicit --through-phase for a reviewed checkpoint');
const reviews=[],changes=[];
for(const id of ids){
 const job=jobs.get(id);assert(job);const path=resolve(DIR,'pair-reviews',id+'.json'),r=load(path),{reviewHash,...body}=r;
 assert.equal(digest(body),reviewHash);assert.equal(r.campaignHash,manifest.campaignHash);assert.equal(r.status,'passed');
 if(expectedReviewHashes.has(id))assert.equal(reviewHash,expectedReviewHashes.get(id));
 assert.equal(r.contextHash,job.contextHash);assert.deepEqual(r.context,job.context);
 const reviewPolicy=r.samplingPolicyHash?loadReviewPolicy(DIR,r.samplingPolicyHash):null;
 if(reviewPolicy?.independentExactReplayRequired!==false)assert.equal(r.exactReplay.exact,true);
 let measured;
 if(job.validationMode==='exact_replay_of_measured_seed_set'){
  measured=expected.get(id);assert(measured);
  const actual=fresh.get(`${id}:${r.exactReplay.seed}`),control=measured.find(x=>x.seed===r.exactReplay.seed);
  assert(actual&&control);assert(exact(actual,control));assert.equal(digest(actual),r.exactReplay.freshRecordHash);
 }else{
  measured=r.seedResults.map(s=>fresh.get(`${id}:${s.seed}`));assert(measured.every(Boolean));
  if(reviewPolicy?.independentExactReplayRequired!==false){const control=measured.find(s=>s.seed===r.exactReplay.seed);assert(control);assert(exact(r.exactReplay.result,control));}
 }
 const originalOutcomes=job.evidenceIds.map(i=>original.get(i).outcome);
 if(r.samplingPolicyHash){
  assert(samplingPolicy,'review refers to a missing sampling amendment');
  verifySamplingReview(job,measured,originalOutcomes,r,reviewPolicy);
  assert.equal(measured.length,freshCounts.get(id),'review omitted collected seed evidence');
 }else assert.equal(required(measured).length,0);
 assert.equal(measured.length,r.seedResults.length);
 for(const s of r.seedResults){const row=measured.find(x=>x.seed===s.seed);assert(row);assert.equal(digest(row),s.recordHash);
  assert.equal(row.contextHash??job.contextHash,job.contextHash);assert.deepEqual(row.profileHashes,job.profileHashes);assert.deepEqual(row.counts??[row.unitCount,row.opponentCount],job.counts);
  assert.equal(row.scenarioHash,job.scenarioHash);assert.equal(row.finalStateHash,s.finalStateHash);assert.equal(row.eventLogHash,s.eventLogHash);
 }
 const outcome=job.evidenceIds.every(i=>original.get(i).evidenceType==='identity')?'equivalent':r.samplingPolicyHash?screeningOutcome(job,measured,originalOutcomes,reviewPolicy):canonicalOutcome(job,measured);
 assert.equal(outcome,r.outcome);
 const prior=job.evidenceIds.map(i=>original.get(i));assert.equal(r.changed,prior.some(p=>p.outcome!==outcome));
 const projected={...r,reviewFile:relative(ROOT,path),reviewFileSha256:sha(readFileSync(path)),
  measuredRecords:measured,freshControlRecord:job.validationMode==='exact_replay_of_measured_seed_set'?fresh.get(`${id}:${r.exactReplay.seed}`):null,
  originalEvidence:job.evidenceIds.map(i=>({evidenceId:i,evidence:original.get(i)}))};
 reviews.push(projected);if(r.changed)changes.push({jobId:id,outcome,originalOutcomes:r.originalOutcomes,context:r.context});
}
mkdirSync(out,{recursive:true});
for(const [file,rows]of [['reviewed-contexts.jsonl.gz',reviews],['changed-winners.jsonl.gz',changes]])writeFileSync(resolve(out,file),gzipSync(rows.map(r=>JSON.stringify(r)).join('\n')+'\n',{mtime:0}));
const singleSeedConfirmations=reviews.filter(r=>r.evidenceLevel==='single_seed_confirmation').length;
assert(reviews.filter(r=>r.evidenceLevel==='single_seed_confirmation').every(r=>!r.changed));
const summary={version:samplingPolicy?.independentExactReplayRequired===false?'civ-matchup-forecast-corrections-v3':samplingPolicy?'civ-matchup-forecast-corrections-v2':'civ-matchup-forecast-corrections-v1',createdAt:now(),campaignHash:manifest.campaignHash,
 campaignManifestSha256:sha(readFileSync(resolve(DIR,'manifest.json'))),sourceCommit,physicsVersion:manifest.physicsVersion,
 samplingPolicyHash:samplingPolicy?.amendmentHash??null,singleSeedConfirmations,multiSeedValidations:reviews.length-singleSeedConfirmations,
 methodology:'One distinct seed for decisive agreement, three for close/disagreeing results, ten if winners vary. No new same-seed replays. Historical replay evidence is retained. Agreement-dependent stopping cannot estimate unbiased global forecast accuracy.',
 originalDatabaseSha256:load(resolve(DIR,'inventory-summary.json')).currentDatabaseSha256,
 reviewedContexts:reviews.length,changedWinnerOrCloseContexts:changes.length,totalValidationContexts:manifest.totalForecastContexts,runnableContexts:jobs.size,heldContexts:manifest.heldContexts,
 remainingValidationContexts:manifest.totalForecastContexts-reviews.length,throughPhase:reviewedOnly?'committed_individually_reviewed_contexts':through??phases.at(-1).slice(0,3),phaseRefs,
 complete:reviews.length===manifest.totalForecastContexts,exactReplayChecks:reviews.filter(r=>r.exactReplay.exact===true).length,
 contextsWithoutReplay:reviews.filter(r=>r.exactReplay.performed===false).length};
json(resolve(out,'summary.json'),summary);
const files=Object.fromEntries(['reviewed-contexts.jsonl.gz','changed-winners.jsonl.gz','summary.json'].map(f=>[f,sha(readFileSync(resolve(out,f)))]));
json(resolve(out,'manifest.json'),{...summary,files});console.log(JSON.stringify(summary));
