#!/usr/bin/env node
// Freeze the pilot inputs from the phase-one table. This script launches no fights.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {resolve,dirname,relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {hashCanonicalJson as digest} from '../../src/canonical-json.js';

const SIM=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const ROOT=resolve(SIM,'../..');
const CAMPAIGN=resolve(SIM,'calibration/campaigns/civ-matchups-campaign-2026-10-31');
const SOURCE=resolve(SIM,'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json');
const INFERENCE=resolve(SIM,'calibration/campaigns/civ-matchups-inference-phase1-2026-10-31');
const load=path=>JSON.parse(readFileSync(path,'utf8'));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const rows=path=>gunzipSync(readFileSync(path)).toString('utf8').trim().split('\n').map(JSON.parse);

const frozen=load(SOURCE),snapshot=load(resolve(INFERENCE,'manifest.json'));
assert.equal(snapshot.buildHash,'5274d7adbc6c425f337c2cc287f7a162a798a04ce54b7358258e8f1be1d40a5e');
for(const file of frozen.runtimeFiles)assert.equal(sha(readFileSync(resolve(ROOT,file.path))),file.sha256,file.path);
const profileKey=new Map();
for(const [key,value] of Object.entries(frozen.profiles)) {
  const hash=digest(Object.fromEntries(Object.entries(value.mechanics).filter(([k])=>k!=='civilization')));
  if(!profileKey.has(hash))profileKey.set(hash,key);
}
assert.equal(profileKey.size,374);
const variant=load(resolve(INFERENCE,'variant-profiles.json'));
const variantByKey=new Map(variant.map(v=>[v.key,v]));
const scenarios={...frozen.scenarios};
const baseByFamily=new Map(Object.values(frozen.scenarios).map(s=>[s.family,s]));
const sourcePairs=rows(resolve(INFERENCE,'profile-matchups.jsonl.gz'));
const unresolved=sourcePairs.filter(x=>x.outcome==='unresolved');
assert.equal(unresolved.length,68370);
const byGroup=new Map();
for(const p of unresolved) {
  assert(p.context && p.context.profiles.length===2,p.pairKey);
  const c=p.context;
  if(!scenarios[c.scenarioHash]) {
    const base=baseByFamily.get(c.family);
    assert(base,c.family);
    const cloned={...base,engineFamily:c.engineFamily};
    assert.equal(digest(cloned),c.scenarioHash);
    scenarios[c.scenarioHash]=cloned;
  }
  const a=frozen.profiles[profileKey.get(c.profiles[0])].mechanics;
  const b=frozen.profiles[profileKey.get(c.profiles[1])].mechanics;
  const group=`${a.behavior_class}|${b.behavior_class}`;
  if(!byGroup.has(group))byGroup.set(group,[]);
  byGroup.get(group).push(p);
}
// The pilot covers every behavior pairing before the adaptive scheduler starts.
// Candidate/alias reach breaks ties, while a hash-derived sort remains stable.
const score=p=>(p.candidateOutcome?1000:0)+p.aliases*5+(p.reasonCodes?.includes('unsupported_effect')?20:0);
for(const list of byGroup.values())list.sort((a,b)=>score(b)-score(a)||a.pairKey.localeCompare(b.pairKey));
const pilot=[];const used=new Set();
for(const group of [...byGroup.keys()].sort()) {
  for(const p of byGroup.get(group).slice(0,2))if(!used.has(p.pairKey)){pilot.push(p);used.add(p.pairKey);}
}
for(const p of [...unresolved].sort((a,b)=>score(b)-score(a)||a.pairKey.localeCompare(b.pairKey))) {
  if(pilot.length>=24)break;
  if(!used.has(p.pairKey)){pilot.push(p);used.add(p.pairKey);}
}
assert.equal(pilot.length,24);
const phaseId='00-pilot';
const matchups=pilot.map(p=>{
  const c=p.context,keys=c.profiles.map(h=>profileKey.get(h));
  const v=variantByKey.get(keys[0]);
  const id=`cm_${digest({profiles:c.profiles,counts:c.counts,scenarioHash:c.scenarioHash,policy:c.policy}).slice(0,24)}`;
  return {id,group:v.group,line:v.line,civilization:v.civilization,slug:v.slug,opponent:keys[1].split('|')[1],
    pairKey:p.pairKey,teamKeys:keys,counts:c.counts,weightedCosts:c.weightedCosts,scenarioHash:c.scenarioHash,
    canonicalMatchupId:id,phase:phaseId};
});
assert.equal(new Set(matchups.map(x=>x.id)).size,matchups.length);
const extraPath=resolve(SIM,'node/collision-validation-worker.mjs');
const runtimeFiles=[...frozen.runtimeFiles];
if(!runtimeFiles.some(x=>resolve(ROOT,x.path)===extraPath))
  runtimeFiles.push({path:relative(ROOT,extraPath),sha256:sha(readFileSync(extraPath))});
const definition={schemaVersion:3,campaignName:'civ-matchups-pilot-2026-10-31',
  createdAt:new Date().toISOString(),scope:'24 unresolved distinct mechanics pairs; seeds 0..2, plus 3..9 on mixed outcomes',
  sourceCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim(),
  engineBaseCommit:frozen.sourceCommit,nodeVersion:process.version,
  runtimeFiles,simulationEnvironment:frozen.simulationEnvironment,engineConfig:frozen.engineConfig,
  referenceDb:frozen.referenceDb,referenceDbSha256:frozen.referenceDbSha256,
  policy:{...frozen.policy,workers:4,chunkMatchups:24,wallTimeoutSeconds:180,
    maxSimulationTicks:Number.MAX_SAFE_INTEGER,reusePilotRuns:false,phasesAdvanceAutomatically:false},
  roster:frozen.roster,profiles:frozen.profiles,scenarios,matchups,
  phases:[{id:phaseId,label:'pilot',matchupIds:matchups.map(x=>x.id),minimumRuns:matchups.length*3}],
  equivalence:{distinctMatchups:matchups.length,distinctUnitProfiles:374,avoidedBaselineRuns:0},
  publishBranch:'simulations/civ-matchups-campaign-2026-10-31',
  inferenceSource:{buildHash:snapshot.buildHash,manifestPath:relative(ROOT,resolve(INFERENCE,'manifest.json'))}};
const manifest={...definition,campaignHash:digest(definition)};
const out=resolve(CAMPAIGN,'pilot');mkdirSync(out,{recursive:true});
if(existsSync(resolve(out,'manifest.json')))throw new Error('pilot manifest already exists');
writeFileSync(resolve(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
writeFileSync(resolve(out,'.gitignore'),'*.sqlite*\n*.tmp\n.runner.lock\n*.log\n*.pid\n');
console.log(JSON.stringify({campaignHash:manifest.campaignHash,pairs:matchups.length,minimumRuns:matchups.length*3,
  behaviorGroups:Object.fromEntries([...byGroup].map(([k,v])=>[k,v.length]))}));
