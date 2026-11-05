// Inventory and provenance audit only. Never launches a simulation or changes source results.
import assert from 'node:assert/strict';
import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve, dirname} from 'node:path';
import {createHash} from 'node:crypto';
import {combatProfileHash} from '../../../node/ranking-equivalence.mjs';
const here=dirname(fileURLToPath(import.meta.url));
const campaigns=resolve(here,'../../campaigns');
const sourceDir=resolve(campaigns,'unit-rankings-consolidated-2026-10-29');
const definitionPath=resolve(campaigns,'unit-rankings-path-recovery-2026-10-29/manifest.json');
const load=p=>JSON.parse(readFileSync(p,'utf8'));
const manifest=load(resolve(sourceDir,'manifest.json'));
const definition=load(definitionPath);
const runs=readFileSync(resolve(sourceDir,'runs.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
const profiles=definition.profiles;
const profileHash=Object.fromEntries(Object.entries(profiles).map(([k,v])=>[k,combatProfileHash(v.mechanics)]));
const keys=manifest.roster.units.map(u=>`${u.civilization}|${u.slug}`);
assert.equal(keys.length,555);assert.equal(new Set(keys).size,555);
assert.equal(new Set(Object.values(profileHash)).size,374);
const pairKey=(a,b)=>JSON.stringify([a,b].sort());
const crossPairs=new Set();let variantPairs=0;
for(let i=0;i<keys.length;i++)for(let j=i+1;j<keys.length;j++){
  if(keys[i].split('|')[0]===keys[j].split('|')[0])continue;
  variantPairs++;crossPairs.add(pairKey(profileHash[keys[i]],profileHash[keys[j]]));
}
const byRun=new Map();const seen=new Set();
for(const r of runs){
  assert(['win','loss','draw'].includes(r.outcome));assert.equal(r.error,null);
  const key=`${r.matchupId}:${r.seed}`;assert(!seen.has(key));seen.add(key);
  if(!byRun.has(r.matchupId))byRun.set(r.matchupId,[]);byRun.get(r.matchupId).push(r);
}
const canonical=new Map();for(const m of manifest.matchups)if(m.id===m.canonicalMatchupId)canonical.set(m.id,m);
assert.equal(canonical.size,2398);assert.equal(byRun.size,2398);
const resultGroups=[];const byPair=new Map();
for(const [id,m] of canonical){
  const selected=byRun.get(id);const initial=selected.filter(r=>r.seed<3);
  assert.equal(initial.length,3);
  const needsTen=new Set(initial.map(r=>r.outcome)).size>1;
  assert.deepEqual(selected.map(r=>r.seed).sort((a,b)=>a-b),Array.from({length:needsTen?10:3},(_,i)=>i));
  const hashes=m.teamKeys.map(k=>profileHash[k]);const key=pairKey(...hashes);const sorted=JSON.parse(key);
  const counter={first:0,second:0,draw:0};const engines={original:0,corrected:0};
  for(const r of selected){
    assert.deepEqual([r.unitCount,r.opponentCount],m.counts);
    assert.equal(r.selectionProvenance.scenarioHash,m.scenarioHash);
    assert.deepEqual(r.selectionProvenance.profileHashes,m.teamKeys.map(k=>profiles[k].profileHash));
    if(r.outcome==='draw')counter.draw++;
    else {const owner=r.outcome==='win'?0:1;assert.equal(r.winnerOwner,owner+2);counter[hashes[owner]===sorted[0]?'first':'second']++;}
    engines[r.selectionProvenance.engineVersion]++;
  }
  const winner=counter.first>counter.second?'first':counter.second>counter.first?'second':'tied';
  const group={id,teams:m.teamKeys,counts:m.counts,scenarioHash:m.scenarioHash,profileHashes:hashes,
    requiredRuns:selected.length,normalizedOutcomes:counter,majority:winner,seedSensitive:new Set(selected.map(r=>r.outcome)).size>1,engines};
  resultGroups.push(group);
  if(!crossPairs.has(key))continue;
  if(!byPair.has(key))byPair.set(key,[]);byPair.get(key).push(group);
}
const duplicated=[...byPair.entries()].filter(([,g])=>g.length>1);
const overlapping=duplicated.map(([pair,g])=>({pair:JSON.parse(pair),groups:g,majorityDisagreement:new Set(g.map(x=>x.majority)).size>1}));
const summary={schemaVersion:1,scope:'Planning only; no new simulations, classifications or UI changes',
  approved:{variants:555,civilizations:56,countPolicy:manifest.policy.countFormula,cap:27,weights:manifest.policy.weights,bufferUnits:0,disableKiting:true,allowCloseUncertain:true},
  sourceDatasetHash:manifest.datasetHash,sourceManifestSha256:createHash('sha256').update(readFileSync(resolve(sourceDir,'manifest.json'))).digest('hex'),
  variantPairs,distinctProfiles:374,distinctCrossCivProfilePairs:crossPairs.size,
  crossCivIdenticalProfilePairs:[...crossPairs].filter(k=>{const [a,b]=JSON.parse(k);return a===b}).length,
  historicalCrossCivPairsWithRecords:byPair.size,
  acceptedHistoricalProfilePairs:0,profilePairsPendingBeforeFreshInference:crossPairs.size,
  historicalDataPolicy:'Exclude old Advisor outcomes. Use current unit-ranking opponent results as anchor evidence after per-run engine, setup and input checks. No blanket acceptance of the mixed-engine dataset; revalidate only incompatible anchors that are needed.',
  selectedRuns:runs.length,canonicalSourceGroups:canonical.size,
  canonicalCrossCivGroups:[...byPair.values()].reduce((n,g)=>n+g.length,0),
  sourceGroupsWithSeedVariation:resultGroups.filter(g=>g.seedSensitive).length,
  crossCivPairsWithSeedVariation:[...byPair.values()].filter(g=>g.some(x=>x.seedSensitive)).length,
  overlappingCrossCivPairs:overlapping.length,overlappingMajorityDisagreements:overlapping.filter(g=>g.majorityDisagreement).length,
  engineCounts:runs.reduce((a,r)=>(a[r.selectionProvenance.engineVersion]++,a),{original:0,corrected:0}),
  requirements:['Do not automatically accept historical pairs. Audit current ranking records as possible inference anchors; exclude legacy Advisor outcomes.',
    'Share newly generated or independently eligible ranking results only with exact mechanics, scenario, orientation, counts, seed and engine identity.',
    'One newly generated orientation can define both UI views; that does not prove physical side-swap invariance.',
    'Overlapping orientations and seed-sensitive pairs need explicit reconciliation before assigning a single table verdict.',
    'Identical-profile fights have no profile-level advantage; do not convert a particular seeded victory into a civ advantage.',
    'Inference is not yet validated. Unknown, timeout and error remain distinct from close/uncertain.'],
  validation:{allSelectedSeedSetsComplete:true,allSelectedCountsMatch:true,allSelectedScenarioHashesMatch:true,allSelectedProfileHashesMatch:true,duplicateSelectedRuns:0,newSimulationsRun:0}};
writeFileSync(resolve(here,'audit.json'),JSON.stringify(summary,null,2)+'\n');
writeFileSync(resolve(here,'overlapping-results.json'),JSON.stringify(overlapping,null,2)+'\n');
console.log(JSON.stringify(summary,null,2));
console.log('Disagreements',JSON.stringify(overlapping.filter(g=>g.majorityDisagreement).map(x=>x.groups.map(g=>({teams:g.teams,counts:g.counts,outcomes:g.normalizedOutcomes,engines:g.engines}))),null,2));
