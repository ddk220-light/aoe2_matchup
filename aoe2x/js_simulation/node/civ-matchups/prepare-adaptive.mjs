#!/usr/bin/env node
// Freeze all possible physical pair inputs once; later phases only select jobs.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {resolve,dirname,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gzipSync,gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const ROOT=resolve(SIM,'../..');
const BASE=resolve(SIM,'calibration/campaigns/civ-matchups-campaign-2026-10-31');
const INFERENCE=resolve(SIM,'calibration/campaigns/civ-matchups-inference-phase1-2026-10-31');
const FROZEN=JSON.parse(readFileSync(resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json')));
const PILOT=JSON.parse(readFileSync(resolve(BASE,'pilot/manifest.json')));
const PILOT_PROGRESS=JSON.parse(readFileSync(resolve(BASE,'pilot/progress.json')));
assert.equal(PILOT_PROGRESS.status,'complete');assert.equal(PILOT_PROGRESS.pendingRuns,0);
const snapshot=JSON.parse(readFileSync(resolve(INFERENCE,'manifest.json')));
assert.equal(snapshot.buildHash,'5274d7adbc6c425f337c2cc287f7a162a798a04ce54b7358258e8f1be1d40a5e');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const profileKey=new Map();
for(const [key,value] of Object.entries(FROZEN.profiles)) {
  const hash=digest(Object.fromEntries(Object.entries(value.mechanics).filter(([k])=>k!=='civilization')));
  if(!profileKey.has(hash))profileKey.set(hash,key);
}
assert.equal(profileKey.size,374);
const sourcePath=resolve(INFERENCE,'profile-matchups.jsonl.gz');
const sourceBytes=readFileSync(sourcePath);
const pairs=gunzipSync(sourceBytes).toString('utf8').trim().split('\n').map(JSON.parse);
assert.equal(pairs.length,68916);
const jobs=[];
for(const pair of pairs){
  if(pair.outcome==='equivalent')continue;
  const c=pair.context;
  assert(c && c.profiles.length===2 && c.counts.length===2,pair.pairKey);
  const teamKeys=c.profiles.map(h=>profileKey.get(h));
  assert(teamKeys.every(Boolean));
  const id=`cm_${digest({profiles:c.profiles,counts:c.counts,scenarioHash:c.scenarioHash,policy:c.policy}).slice(0,24)}`;
  jobs.push({id,pairKey:pair.pairKey,teamKeys,profileHashes:c.profiles,counts:c.counts,
    weightedCosts:c.weightedCosts,scenarioHash:c.scenarioHash,family:c.family,
    engineFamily:c.engineFamily,policy:c.policy});
}
assert.equal(jobs.length,68871);assert.equal(new Set(jobs.map(x=>x.id)).size,jobs.length);
for(const pilot of PILOT.matchups){
  const found=jobs.find(x=>x.id===pilot.id);
  assert(found,`pilot job missing from inventory ${pilot.id}`);
  assert.deepEqual([found.teamKeys,found.counts,found.scenarioHash],
    [pilot.teamKeys,pilot.counts,pilot.scenarioHash]);
}
const directory=resolve(BASE,'adaptive');mkdirSync(directory,{recursive:true});
if(existsSync(resolve(directory,'manifest.json')))throw new Error('adaptive manifest already exists');
const inventoryBytes=gzipSync(Buffer.from(jobs.map(x=>JSON.stringify(x)).join('\n')+'\n'));
const inventoryFile='inventory.jsonl.gz';
writeFileSync(resolve(directory,inventoryFile),inventoryBytes);
const definition={schemaVersion:1,campaignName:'civ-matchups-adaptive-2026-10-31',
  createdAt:new Date().toISOString(),sourceCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim(),
  engineBaseCommit:FROZEN.sourceCommit,nodeVersion:process.version,
  runtimeFiles:PILOT.runtimeFiles,simulationEnvironment:FROZEN.simulationEnvironment,
  engineConfig:FROZEN.engineConfig,referenceDbSha256:FROZEN.referenceDbSha256,
  matchupInventory:{file:inventoryFile,sha256:sha(inventoryBytes),rows:jobs.length},
  phaseOneInput:{file:relative(ROOT,sourcePath),sha256:sha(sourceBytes),buildHash:snapshot.buildHash},
  pilotCampaignHash:PILOT.campaignHash,
  policy:{...FROZEN.policy,maxSimulationTicks:Number.MAX_SAFE_INTEGER,
    wallTimeoutSteps:[180,600,1800,3600],workers:4,phaseOnePairs:128,regularPhasePairs:256,
    bufferUnits:0,disableAiOrders:true,disableKiting:true},
  publishBranch:'simulations/civ-matchups-campaign-2026-10-31'};
const manifest={...definition,campaignHash:digest(definition)};
writeFileSync(resolve(directory,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
writeFileSync(resolve(directory,'.gitignore'),'*.tmp\n.runner.lock\n*.log\n*.pid\n');
console.log(JSON.stringify({campaignHash:manifest.campaignHash,physicalJobs:jobs.length,
  inventorySha256:manifest.matchupInventory.sha256,pilotCampaignHash:PILOT.campaignHash}));
