#!/usr/bin/env node
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,readdirSync,existsSync,mkdirSync,copyFileSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {gzipSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
import {SIM,ROOT,DIR,FROZEN,sha,load,gzlines,digest,json,scenario} from './mismatch-validation-lib.mjs';
assert(!existsSync(resolve(DIR,'manifest.json')),'already frozen');
const nativeDir=resolve(SIM,'calibration/campaigns/civ-matchups-campaign-2026-10-31/adaptive');
const native=load(resolve(nativeDir,'manifest.json'));
const pilotPath=resolve(nativeDir,'../pilot/manifest.json'),pilot=load(pilotPath);
const allowed=new Set(['aoe2x/js_simulation/src/canonical-json.js','aoe2x/js_simulation/src/fight.js','aoe2x/js_simulation/src/combat/world.js']);
const runtime=native.runtimeFiles.map(r=>({...r,sha256:sha(readFileSync(resolve(ROOT,r.path)))}));
const changes=runtime.filter((r,i)=>r.sha256!==native.runtimeFiles[i].sha256);
assert.deepEqual(changes.map(r=>r.path).sort(),[...allowed].sort(),'only lossless event serialization may differ from V3');
const representative=new Map();
for(const [key,value]of Object.entries(FROZEN.profiles)){
 const hash=digest(Object.fromEntries(Object.entries(value.mechanics).filter(([k])=>k!=='civilization')));
 if(!representative.has(hash))representative.set(hash,key);
}
const variants=load(resolve(SIM,'calibration/reports/civ-matchups-first-pass-provisional-2026-11-02/variant-profiles.json'));
for(const v of variants)assert.equal(digest(Object.fromEntries(Object.entries(FROZEN.profiles[v.key].mechanics).filter(([k])=>k!=='civilization'))),v.profileHash);
const nativeJobs=new Map(gzlines(resolve(nativeDir,'inventory.jsonl.gz')).map(j=>[j.pairKey,j]));
const jobs=gzlines(resolve(DIR,'jobs.jsonl.gz'));
const evidence=new Map(gzlines(resolve(DIR,'original-evidence.jsonl.gz')).map(r=>[r.evidenceId,r.evidence]));
const expected=[];
const sourceHashes={};
for(const job of jobs){
 job.teamKeys=job.profileHashes.map(h=>representative.get(h));assert(job.teamKeys.every(Boolean));scenario(job);
 const old=nativeJobs.get(job.pairKey);
 job.nativeMatchupId=old?.id??null;
 const measured=job.evidenceIds.map(id=>evidence.get(id)).find(e=>e.evidenceType==='observed');
 job.validationMode='fresh_seed_set';
 // Short source IDs belong to ranking-anchor ledgers, not the frozen V3
 // adaptive journals. Recompute those contexts instead of treating them as
 // exact V3 controls or guessing which worktree a relative name refers to.
 if(measured?.sourceRunIds?.length && measured.sourceRunIds.every(p=>p.startsWith('aoe2x/js_simulation/calibration/campaigns/civ-matchups-campaign-2026-10-31/'))){
  assert(old);for(const key of ['counts','profileHashes','scenarioHash','teamKeys'])assert.deepEqual(job[key],old[key]);
  const records=measured.sourceRunIds.map(id=>{
   const m=id.match(/^(.*):(\d+)$/);assert(m,id);const [_,file,line]=m;
   const path=resolve(ROOT,file),bytes=readFileSync(path);sourceHashes[file]??=sha(bytes);
   const raw=bytes.toString('utf8').trimEnd().split('\n')[Number(line)-1];assert(raw);
   const row=JSON.parse(raw);assert.equal(row.matchupId,old.id);assert(['win','loss','draw'].includes(row.outcome));
   if(row.campaignHash===pilot.campaignHash){
    const original=pilot.matchups.find(j=>j.id===old.id);assert(original);
    for(const key of ['counts','teamKeys','scenarioHash'])assert.deepEqual(original[key],job[key]);
    row.scenarioHash=original.scenarioHash;row.profileHashes=job.profileHashes;
   }else assert.equal(row.campaignHash,native.campaignHash);
   assert.equal(row.scenarioHash,job.scenarioHash);assert.deepEqual(row.profileHashes,job.profileHashes);
   assert.deepEqual(row.counts??[row.unitCount,row.opponentCount],job.counts);
   return {...row,sourceFile:file,sourceLine:Number(line),sourceLineSha256:sha(raw),sourceFileSha256:sourceHashes[file]};
  });
  const initial=[0,1,2].map(s=>records.find(r=>r.seed===s));assert(initial.every(Boolean));
  if(new Set(initial.map(r=>r.outcome)).size>1)assert([3,4,5,6,7,8,9].every(s=>records.some(r=>r.seed===s)));
  assert(new Set(records.map(r=>r.seed)).size===records.length);
  expected.push({jobId:job.id,records});job.validationMode='exact_replay_of_measured_seed_set';
 }
}
writeFileSync(resolve(DIR,'jobs.jsonl.gz'),gzipSync(jobs.map(j=>JSON.stringify(j)).join('\n')+'\n',{mtime:0}));
writeFileSync(resolve(DIR,'expected-native-records.jsonl.gz'),gzipSync(expected.map(r=>JSON.stringify(r)).join('\n')+'\n',{mtime:0}));
mkdirSync(resolve(DIR,'reviews'),{recursive:true});
copyFileSync('/workspace/aoe2_civ_mismatch_stream_tests.tap',resolve(DIR,'reviews/stream-tests.tap'));
const inputPaths=[];
function walk(dir){for(const entry of readdirSync(dir,{withFileTypes:true})){const path=resolve(dir,entry.name);if(entry.isDirectory())walk(path);else inputPaths.push(path);}}
walk(DIR);
inputPaths.push(resolve(nativeDir,'manifest.json'),pilotPath,resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json'));
inputPaths.push(...Object.keys(sourceHashes).map(p=>resolve(ROOT,p)));
const body={schemaVersion:1,campaignName:'civ-matchups-mismatch-validation-2026-11-05',createdAt:new Date().toISOString(),
 sourceCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim(),nodeVersion:process.version,
 physicsVersion:'frozen-civ-matchups-v3',executionVersion:'lossless-event-stream-v1',
 nativeCampaignHash:native.campaignHash,simulationEnvironment:native.simulationEnvironment,
 runtimeFiles:runtime,inputFiles:[...new Set(inputPaths)].map(p=>({path:relative(ROOT,p),sha256:sha(readFileSync(p))})),
 changedOutputFiles:changes.map(r=>({...r,frozenSha256:native.runtimeFiles.find(x=>x.path===r.path).sha256})),
 policy:{workers:4,initialSeeds:[0,1,2],extraSeeds:[3,4,5,6,7,8,9],expandOnMixedWinners:true,
 wallTimeoutSteps:[180,600,1800,3600],maxSimulationTicks:Number.MAX_SAFE_INTEGER,phaseJobs:128,
 measured:'fresh exact replay plus integrity review of the complete original seed set; original native rows remain native',
 predictedOrInferred:'fresh complete seed set plus independent exact replay of one completed seed',
 failures:'never measurements; diagnosis required after exhausted retries',
 corrections:'only complete reviewed contexts; retain original prediction/provenance; no reverse-context transfer; no ranking-score changes'},
 jobs:jobs.length,measuredReplayJobs:expected.length,freshSeedSetJobs:jobs.length-expected.length};
json(resolve(DIR,'manifest.json'),{...body,campaignHash:digest(body)});
console.log(JSON.stringify({jobs:body.jobs,measuredReplayJobs:body.measuredReplayJobs,freshSeedSetJobs:body.freshSeedSetJobs,campaignHash:digest(body)}));
