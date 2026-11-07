#!/usr/bin/env node
// Freeze execution inputs for the existing forecasts. Never edit their values.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync,readdirSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {gzipSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
import {ROOT,SIM,DIR,FROZEN,sha,load,gzlines,digest,json,scenario} from './forecast-validation-lib.mjs';

assert(!existsSync(resolve(DIR,'manifest.json')),'Inventory already frozen.');
const parentPath=resolve(SIM,'calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05/manifest.json');
const parent=load(parentPath),summary=load(resolve(DIR,'inventory-summary.json'));
for(const file of [...parent.runtimeFiles,...parent.inputFiles])
  assert.equal(sha(readFileSync(resolve(ROOT,file.path))),file.sha256,file.path);
const representative=new Map();
for(const [key,value] of Object.entries(FROZEN.profiles)){
  const hash=digest(Object.fromEntries(Object.entries(value.mechanics).filter(([k])=>k!=='civilization')));
  if(!representative.has(hash))representative.set(hash,key);
}
for(const unit of load(resolve(DIR,'sources/variant-profiles.json'))){
  assert(FROZEN.profiles[unit.key],unit.key);
  assert.equal(digest(Object.fromEntries(Object.entries(FROZEN.profiles[unit.key].mechanics).filter(([k])=>k!=='civilization'))),unit.profileHash);
}
const original=new Map(gzlines(resolve(DIR,'original-evidence.jsonl.gz')).map(r=>[r.evidenceId,r.evidence]));
const nativeJobs=new Map(gzlines(resolve(SIM,'calibration/campaigns/civ-matchups-campaign-2026-10-31/adaptive/inventory.jsonl.gz')).map(j=>[j.pairKey,j]));
const jobs=gzlines(resolve(DIR,'jobs.jsonl.gz'));
for(const job of jobs){
  assert.equal(job.contextHash,digest(job.context));
  assert.equal(original.get(job.evidenceIds[0]).evidenceType,'predicted_unvalidated');
  assert.deepEqual(original.get(job.evidenceIds[0]).context,job.context);
  job.teamKeys=job.profileHashes.map(h=>representative.get(h));assert(job.teamKeys.every(Boolean));
  assert.deepEqual(job.profileHashes,job.context.profiles);assert.deepEqual(job.counts,job.context.counts);
  scenario(job);job.nativeMatchupId=nativeJobs.get(job.pairKey)?.id??null;
}
writeFileSync(resolve(DIR,'jobs.jsonl.gz'),gzipSync(jobs.map(j=>JSON.stringify(j)).join('\n')+'\n',{mtime:0}));
const inputPaths=[];
function walk(dir){for(const entry of readdirSync(dir,{withFileTypes:true})){
  const path=resolve(dir,entry.name);if(entry.isDirectory())walk(path);else inputPaths.push(path);
}}
walk(DIR);
const scripts=['tools/prepare_civ_forecast_inventory.py','tools/supervise_civ_forecast_validation.py',
  'aoe2x/js_simulation/node/civ-matchups/forecast-validation-lib.mjs',
  'aoe2x/js_simulation/node/civ-matchups/prepare-forecast-validation.mjs',
  'aoe2x/js_simulation/node/civ-matchups/run-forecast-validation.mjs',
  'aoe2x/js_simulation/node/civ-matchups/export-forecast-reviews.mjs',
  'aoe2x/js_simulation/node/civ-matchups/verify-forecast-runtime.mjs',
  'aoe2x/js_simulation/node/civ-matchups/rolling-validation-queue.mjs',
  'aoe2x/js_simulation/tests/forecast-validation.test.mjs'];
const parentParity=resolve(SIM,'calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05/reviews/runtime-parity.json');
inputPaths.push(parentPath,parentParity,...scripts.map(path=>resolve(ROOT,path)),
  ...parent.inputFiles.map(file=>resolve(ROOT,file.path)));
const body={schemaVersion:1,campaignName:'civ-matchups-forecast-validation-2026-11-07',createdAt:new Date().toISOString(),
  sourceCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim(),nodeVersion:process.version,
  sourceWebsiteCommit:summary.sourceWebsiteCommit,originalDatabaseSha256:summary.currentDatabaseSha256,
  physicsVersion:parent.physicsVersion,executionVersion:parent.executionVersion,nativeCampaignHash:parent.nativeCampaignHash,
  simulationEnvironment:parent.simulationEnvironment,runtimeFiles:parent.runtimeFiles,
  inputFiles:[...new Set(inputPaths)].map(path=>({path:relative(ROOT,path),sha256:sha(readFileSync(path))})),
  changedOutputFiles:parent.changedOutputFiles,
  runtimeSource:{campaignHash:parent.campaignHash,manifest:relative(ROOT,parentPath),manifestSha256:sha(readFileSync(parentPath)),
    priorParity:relative(ROOT,parentParity),priorParitySha256:sha(readFileSync(parentParity)),byteIdenticalRuntime:true},
  policy:{...parent.policy,confidenceTierOrder:summary.queueTierOrder,
    priority:'Frozen forecast tier, then stable evidence ID; no retraining or probability calibration.',
    scope:'Only predictions remaining in the deployed c907cc236 dataset; fresh required seeds and independent exact replay.',
    held:'Known exhausted native contexts and repaired projections stay unfinished pending separate recovery review.',
    delivery:'Immutable research-only snapshots; no serving-data import, website build, UI/formula change or automatic release.'},
  totalForecastContexts:summary.totalForecastContexts,heldContexts:summary.heldContexts,
  jobs:jobs.length,measuredReplayJobs:0,freshSeedSetJobs:jobs.length};
const campaignHash=digest(body);json(resolve(DIR,'manifest.json'),{...body,campaignHash});
const controls={version:1,campaignHash,inventorySha256:sha(readFileSync(resolve(DIR,'jobs.jsonl.gz'))),
  schedulerVersion:'rolling-phase-queue-v2',
  schedulerFiles:scripts.filter(path=>/run-forecast-validation|rolling-validation-queue/.test(path)).map(path=>({path,sha256:sha(readFileSync(resolve(ROOT,path)))})),
  quarantinedContexts:[]};
json(resolve(DIR,'queue-controls.json'),{...controls,controlsHash:digest(controls)});
json(resolve(DIR,'launch-approval.json'),{durationApproved:false,status:'awaiting_explicit_duration_approval',
  reason:'AGENTS.md requires asking before work estimated beyond one hour. The full forecast campaign exceeds that duration.',
  requestedScope:'Keep running more matchups, the ones that are guesses. The eventual target is to validate all guesses. Start with the lowest confidence ones.'});
json(resolve(DIR,'state.json'),{createdAt:new Date().toISOString(),campaignHash,status:'prepared_awaiting_duration_approval',
  pid:null,completedPhases:[],reviewedJobs:0,savedFreshSeeds:0,changedJobs:0,active:[],blockedJobs:[],
  totalForecastContexts:summary.totalForecastContexts,runnableJobs:jobs.length,heldContexts:summary.heldContexts,
  remainingJobs:summary.totalForecastContexts,remainingRunnableJobs:jobs.length});
mkdirSync(resolve(DIR,'reviews'),{recursive:true});
console.log(JSON.stringify({campaignHash,total:summary.totalForecastContexts,runnable:jobs.length,held:summary.heldContexts}));
