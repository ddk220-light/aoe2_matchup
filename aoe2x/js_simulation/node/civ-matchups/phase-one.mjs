// Inference-only build. Do not import a battle runner or advance combat here.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync, mkdirSync, renameSync, unlinkSync, existsSync, readdirSync} from 'node:fs';
import {gzipSync,gunzipSync} from 'node:zlib';
import {dirname, resolve, relative} from 'node:path';
import {fileURLToPath} from 'node:url';
import {combatProfileHash} from '../ranking-equivalence.mjs';
import {deriveRecordedBattleSetup} from '../../src/battle-setup.js';
import {calculateDamage, attackDelayTicks, reloadTicks} from '../../src/combat/attacks.js';
import {scenarioFamilyFor} from '../../src/lab-scenario.js';
import {resolveFamily} from '../../src/placement.js';
import {hashCanonicalJson} from '../../src/canonical-json.js';

const SIM = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const ROOT = resolve(SIM, '../..');
const SOURCE = resolve(SIM, 'calibration/campaigns/unit-rankings-consolidated-2026-10-29');
const DEFINITION = resolve(SIM, 'calibration/campaigns/unit-rankings-path-recovery-2026-10-29/manifest.json');
const SCORES = resolve(SIM, 'calibration/reports/unit-ranking-scores-final-2026-10-29/scores.json');
const RULE_VERSION = 'phase1-static-direction-and-tradeoff-v2';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const json = path => JSON.parse(readFileSync(path, 'utf8'));
const key2 = (a,b) => a <= b ? `${a}|${b}` : `${b}|${a}`;
const sign = (a,b) => a > b ? 1 : a < b ? -1 : 0;
const small = value => JSON.stringify(value);
const statusCount = (counter,key) => {counter[key]=(counter[key]??0)+1;};
const entity = mechanics => ({mechanics, hp:mechanics.hp, maxHp:mechanics.hp, specialState:{}});

function canonicalInputs() {
  const sourceManifest=json(resolve(SOURCE,'manifest.json'));
  const definition=json(DEFINITION);
  const scoring=json(SCORES);
  assert.equal(sourceManifest.datasetHash,'17a91c8fa14553abbce1f894cbeb4e637d9fe9a82977fc2da2b0bc824cfade3c');
  assert.equal(definition.campaignHash,'1ac49a6abf1f3a1a104c7bcf675a3a327b6939d49273ae49c51eb6157264693d');
  assert.equal(sourceManifest.roster.units.length,555);
  return {sourceManifest,definition,scoring};
}

function profilesAndPairs(sourceManifest,definition) {
  const variants=sourceManifest.roster.units.map((row,index)=>{
    const key=`${row.civilization}|${row.slug}`;
    const entry=definition.profiles[key];
    assert(entry,`missing mechanics: ${key}`);
    return {...row,index,key,profileHash:combatProfileHash(entry.mechanics)};
  });
  const profiles=new Map();
  for(const v of variants) {
    if(!profiles.has(v.profileHash)) profiles.set(v.profileHash,{hash:v.profileHash,mechanics:definition.profiles[v.key].mechanics,aliases:[],line:v.line,group:v.group});
    profiles.get(v.profileHash).aliases.push(v.key);
  }
  assert.equal(profiles.size,374);
  const scenarios=new Map();
  const scenarioByFamily=new Map();
  for(const [hash,scenario] of Object.entries(definition.scenarios)) {
    const key=`${scenario.family}|${scenario.engineFamily}`;
    assert(!scenarios.has(key));scenarios.set(key,hash);
    if(!scenarioByFamily.has(scenario.family)) scenarioByFamily.set(scenario.family,scenario);
  }
  function context(leftHash,rightHash) {
    const left=profiles.get(leftHash).mechanics,right=profiles.get(rightHash).mechanics;
    const side2={class:left.behavior_class,effectiveCost:left.cost};
    const side3={class:right.behavior_class,effectiveCost:right.cost};
    const setup=deriveRecordedBattleSetup(side2,side3,{cap:27});
    const family=scenarioFamilyFor(side2,side3);
    const engineFamily=resolveFamily({side2Class:side2.class,side3Class:side3.class});
    // The frozen campaign covered only five family/engine-family combinations.
    // Other combinations use the same authored family fixture with the generic
    // placement family's metadata changed, as loadLabScenario would construct.
    const scenarioHash=scenarios.get(`${family}|${engineFamily}`)
      ?? hashCanonicalJson({...scenarioByFamily.get(family),engineFamily});
    assert(scenarioHash,`missing scenario ${family}|${engineFamily}`);
    return {profiles:[leftHash,rightHash],counts:[setup.n2,setup.n3],scenarioHash,
      family,engineFamily,weightedCosts:[setup.cost2,setup.cost3],
      policy:'27-geometric-cost-v3; zero buffers; disableAiOrders; disableKiting; preserveOwnerOrientation'};
  }
  const pairs=new Map();let variantCells=0;const civPairs=new Set();
  for(let i=0;i<variants.length;i++) for(let j=i+1;j<variants.length;j++) {
    const a=variants[i],b=variants[j];
    if(a.civilization===b.civilization) continue;
    variantCells++;civPairs.add(key2(a.civilization,b.civilization));
    const key=key2(a.profileHash,b.profileHash);
    if(!pairs.has(key))pairs.set(key,{key,profiles:key.split('|'),aliases:[],contexts:[]});
    pairs.get(key).aliases.push([a.index,b.index]);
  }
  assert.equal(variantCells,151223);assert.equal(pairs.size,68916);assert.equal(civPairs.size,1540);
  return {variants,profiles,pairs,context,variantCells,civPairs:civPairs.size};
}

function sourceEvidence(definition,sourceManifest,profiles,pairs,context,extraCampaignDirectories=[]) {
  const byId=new Map(definition.matchups.map(m=>[m.id,m]));
  const runLedger=[];const groups=new Map();const sourceFiles=[];
  for(const file of ['runs.jsonl','additional-recorded-runs.jsonl']) {
    const path=resolve(SOURCE,file),raw=readFileSync(path);
    sourceFiles.push({path:relative(ROOT,path),sha256:sha(raw),records:raw.toString('utf8').trim().split('\n').length});
    let line=0;
    for(const value of raw.toString('utf8').trim().split('\n')) {
      line++;const r=JSON.parse(value),m=byId.get(r.matchupId);
      assert(m,`unknown source matchup ${r.matchupId}`);
      const expectedHashes=m.teamKeys.map(k=>definition.profiles[k].profileHash);
      assert.deepEqual(r.selectionProvenance.profileHashes,expectedHashes);
      assert.deepEqual([r.unitCount,r.opponentCount],m.counts);
      assert.equal(r.selectionProvenance.scenarioHash,m.scenarioHash);
      assert.equal(r.error,null);
      assert(['win','loss','draw'].includes(r.outcome));
      const h=m.teamKeys.map(k=>combatProfileHash(definition.profiles[k].mechanics));
      const expected=context(...h);
      assert.deepEqual(m.counts,expected.counts);
      assert.equal(m.scenarioHash,expected.scenarioHash);
      const p=r.selectionProvenance;
      const corrected=p.engineVersion==='corrected' && p.inputCampaignHash===definition.campaignHash;
      const normalized={matchupId:r.matchupId,seed:r.seed,outcome:r.outcome,winnerHash:r.outcome==='draw'?null:h[r.outcome==='win'?0:1],
        engineVersion:p.engineVersion,inputCampaignHash:p.inputCampaignHash,sourceKind:p.sourceKind,
        sourceFile:file,sourceLine:line,originFile:p.file,originLine:p.line,originRecordHash:p.recordSha256,
        scenarioHash:p.scenarioHash,profileHashes:h,fullProfileHashes:p.profileHashes,
        counts:m.counts,unitRemainingHp:r.unitRemainingHp,opponentRemainingHp:r.opponentRemainingHp,
        unitStartingHp:r.unitStartingHp,opponentStartingHp:r.opponentStartingHp,corrected};
      runLedger.push(normalized);
      if(!groups.has(r.matchupId))groups.set(r.matchupId,[]);
      groups.get(r.matchupId).push(normalized);
    }
  }
  assert(runLedger.length>=7677);
  const additionalCampaignHashes=[];
  for(const extraCampaignDirectory of extraCampaignDirectories) {
    const manifestPath=resolve(extraCampaignDirectory,'manifest.json');
    const campaign=json(manifestPath);
    const {campaignHash,...payload}=campaign;
    assert.equal(hashCanonicalJson(payload),campaignHash,'additional campaign manifest hash');
    assert.equal(campaign.engineBaseCommit,definition.sourceCommit);
    assert.equal(campaign.referenceDbSha256,definition.referenceDbSha256);
    for(const frozen of definition.runtimeFiles){
      const actual=campaign.runtimeFiles.find(x=>x.path===frozen.path);
      assert.equal(actual?.sha256,frozen.sha256,`additional engine mismatch: ${frozen.path}`);
    }
    additionalCampaignHashes.push(campaignHash);
    sourceFiles.push({path:relative(ROOT,manifestPath),sha256:sha(readFileSync(manifestPath))});
    let additionalMatchups=campaign.matchups;
    if(campaign.matchupInventory){
      const inventoryPath=resolve(extraCampaignDirectory,campaign.matchupInventory.file);
      const buffer=readFileSync(inventoryPath);
      assert.equal(sha(buffer),campaign.matchupInventory.sha256);
      sourceFiles.push({path:relative(ROOT,inventoryPath),sha256:sha(buffer)});
      additionalMatchups=gunzipSync(buffer).toString('utf8').trim().split('\n').map(JSON.parse);
    }
    for(const m of additionalMatchups){
      if(byId.has(m.id)){
        const old=byId.get(m.id);
        assert.deepEqual([m.teamKeys,m.counts,m.scenarioHash],[old.teamKeys,old.counts,old.scenarioHash]);
      }else byId.set(m.id,m);
    }
    const runDir=resolve(extraCampaignDirectory,'runs');
    for(const file of existsSync(runDir)?readdirSync(runDir).filter(x=>x.endsWith('.jsonl')).sort():[]) {
      const path=resolve(runDir,file),raw=readFileSync(path);
      sourceFiles.push({path:relative(ROOT,path),sha256:sha(raw),records:raw.toString('utf8').trim().split('\n').filter(Boolean).length});
      let line=0;
      for(const value of raw.toString('utf8').trim().split('\n').filter(Boolean)) {
        line++;const r=JSON.parse(value),m=byId.get(r.matchupId);
        assert(m&&r.campaignHash===campaignHash);
        assert.deepEqual([r.unitCount,r.opponentCount],m.counts);
        if(!['win','loss','draw'].includes(r.outcome)||r.error)continue;
        assert(r.finalStateHash&&r.eventLogHash);
        const hashes=m.teamKeys.map(k=>combatProfileHash(definition.profiles[k].mechanics));
        assert.equal(m.scenarioHash,context(...hashes).scenarioHash);
        const normalized={matchupId:r.matchupId,seed:r.seed,outcome:r.outcome,
          winnerHash:r.outcome==='draw'?null:hashes[r.outcome==='win'?0:1],
          engineVersion:'extended_duration',inputCampaignHash:campaignHash,sourceKind:'civ_matchup_campaign',
          sourceFile:relative(ROOT,path),sourceLine:line,originFile:relative(ROOT,path),originLine:line,
          originRecordHash:sha(Buffer.from(value)),scenarioHash:m.scenarioHash,profileHashes:hashes,
          fullProfileHashes:m.teamKeys.map(k=>definition.profiles[k].profileHash),counts:m.counts,
          unitRemainingHp:r.unitRemainingHp,opponentRemainingHp:r.opponentRemainingHp,
          unitStartingHp:r.unitStartingHp,opponentStartingHp:r.opponentStartingHp,corrected:true};
        runLedger.push(normalized);
        if(!groups.has(r.matchupId))groups.set(r.matchupId,[]);
        groups.get(r.matchupId).push(normalized);
      }
    }
  }
  const anchors=[];const prior=[];const sourceGroupCounts={};
  for(const [id,rows] of groups) {
    const m=byId.get(id);
    const hashes=m.teamKeys.map(k=>combatProfileHash(definition.profiles[k].mechanics));
    const pair=pairs.get(key2(...hashes));
    const corrected=rows.filter(r=>r.corrected);
    const original=rows.filter(r=>!r.corrected && r.engineVersion==='original');
    const evaluate=list=>{
      if(!list.length)return null;
      const seeds=new Map();
      for(const r of list){assert(!seeds.has(r.seed),`duplicate seed ${id}:${r.seed}`);seeds.set(r.seed,r);}
      const three=[0,1,2].every(n=>seeds.has(n));
      const ten=Array.from({length:10},(_,n)=>n).every(n=>seeds.has(n));
      const varied=new Set(list.map(r=>r.outcome)).size>1;
      const complete=three && (!varied || ten);
      const outcome=complete ? (varied || list[0].outcome==='draw' ? 'close_uncertain' : list[0].winnerHash) : null;
      return {matchupId:id,pairKey:key2(...hashes),profiles:hashes,counts:m.counts,scenarioHash:m.scenarioHash,
        seedOutcomes:list.sort((a,b)=>a.seed-b.seed).map(r=>[r.seed,r.outcome]),complete,outcome,seedSensitive:varied,
        close:outcome==='close_uncertain',selectedRunIds:list.map(r=>`${r.sourceFile}:${r.sourceLine}`),
        minWinnerHpFraction: outcome && outcome!=='close_uncertain' ? Math.min(...list.map(r=>{
          const owner=r.winnerHash===hashes[0]?0:1;
          return owner===0?r.unitRemainingHp/r.unitStartingHp:r.opponentRemainingHp/r.opponentStartingHp;
        })) : null};
    };
    const current=evaluate(corrected),old=evaluate(original);
    if(current){anchors.push({...current,evidenceType:'corrected'});statusCount(sourceGroupCounts,
      current.complete?current.close?'corrected_close':'corrected_complete':
        current.seedSensitive?'corrected_seed_sensitive_incomplete':'corrected_incomplete');}
    else statusCount(sourceGroupCounts,'no_corrected');
    if(old)prior.push({...old,evidenceType:'original'});
    if(pair){if(current)pair.contexts.push({...current,evidenceType:'corrected'});if(old)pair.contexts.push({...old,evidenceType:'original'});}
  }
  assert(groups.size>=2398);
  return {runLedger,anchors,prior,sourceFiles,sourceGroupCounts,additionalCampaignHashes};
}

function staticSafe(mechanics) {
  if(mechanics.charge || mechanics.melee_charge || mechanics.damage_reduction_by_attacker_category) return false;
  if(mechanics.blast?.width_tiles>0 || mechanics.ranged?.pass_through || mechanics.ranged?.extra_projectile_count>0
    || mechanics.ranged?.secondary_projectile_count>0 || mechanics.ranged?.impact_splash_radius_tiles>0
    || mechanics.ranged?.first_attack_extra_projectiles>0 || mechanics.ranged?.extra_projectile_attacks) return false;
  const ordinary=new Set(['base_accuracy','pass_through_count','splash_on_hit_fraction']);
  for(const [k,v] of Object.entries(mechanics.effects??{})) if(!ordinary.has(k) && v!==null && v!==0 && v!==false) return false;
  return true;
}
const same = (a,b) => small(a)===small(b);
function comparable(a,b) {
  if(!staticSafe(a)||!staticSafe(b))return false;
  if(a.unit_master!==b.unit_master || a.unit_slug!==b.unit_slug || a.mode!==b.mode || a.behavior_class!==b.behavior_class) return false;
  const variable=new Set(['civilization','unit_name','derived','hp','cost','attack_classes','armor_classes',
    'reload_seconds','attack_delay_seconds','ranged']);
  for(const k of new Set([...Object.keys(a),...Object.keys(b)])){
    if(variable.has(k))continue;
    if(!same(a[k],b[k]))return false;
  }
  const ra={...a.ranged},rb={...b.ranged};delete ra.accuracy_percent;delete rb.accuracy_percent;
  if(!same(ra,rb))return false;
  return a.speed_tiles_per_second===b.speed_tiles_per_second && a.attack_range_tiles===b.attack_range_tiles;
}
function relation(candidate,baseline,opponent,candidateContext,baselineContext,candidateIndex,baselineIndex) {
  const c=candidate.mechanics,b=baseline.mechanics,x=opponent.mechanics;
  if(!comparable(c,b)||!staticSafe(x)) return 0;
  if(candidateContext.scenarioHash!==baselineContext.scenarioHash || candidateIndex!==baselineIndex) return 0;
  const other=1-candidateIndex;
  const countMore=candidateContext.counts[candidateIndex]>=baselineContext.counts[baselineIndex];
  const countLess=candidateContext.counts[candidateIndex]<=baselineContext.counts[baselineIndex];
  const oppLess=candidateContext.counts[other]<=baselineContext.counts[other];
  const oppMore=candidateContext.counts[other]>=baselineContext.counts[other];
  let outC,outB,inC,inB;
  try {
    outC=calculateDamage(entity(c),entity(x));outB=calculateDamage(entity(b),entity(x));
    inC=calculateDamage(entity(x),entity(c));inB=calculateDamage(entity(x),entity(b));
  } catch {return 0;}
  const attackBetter=outC>=outB && attackDelayTicks(c)<=attackDelayTicks(b) && reloadTicks(c)<=reloadTicks(b)
    && (c.ranged?.accuracy_percent??100)>=(b.ranged?.accuracy_percent??100);
  const attackWorse=outC<=outB && attackDelayTicks(c)>=attackDelayTicks(b) && reloadTicks(c)>=reloadTicks(b)
    && (c.ranged?.accuracy_percent??100)<=(b.ranged?.accuracy_percent??100);
  const better=attackBetter && inC<=inB && c.hp>=b.hp && countMore && oppLess;
  const worse=attackWorse && inC>=inB && c.hp<=b.hp && countLess && oppMore;
  return better && !worse ? 1 : worse && !better ? -1 : 0;
}

function selectContext(pair,context) {
  const current=pair.contexts.filter(x=>x.evidenceType==='corrected'&&x.complete);
  if(current.length){
    const outcomes=new Set(current.map(x=>x.outcome));
    if(outcomes.size>1)return {conflict:true,contexts:current};
    const chosen=[...current].sort((a,b)=>a.matchupId.localeCompare(b.matchupId))[0];
    return {context:context(...chosen.profiles),direct:chosen,otherDirect:current};
  }
  const partial=pair.contexts.filter(x=>x.evidenceType==='corrected');
  const ordered=[...pair.profiles].sort();
  return {context:context(...ordered),partial};
}

function proposalFor(pair,selected,root,profiles,context) {
  const candidateHashes=selected.context.profiles,rootHashes=root.profiles;
  const unchanged=candidateHashes.filter(h=>rootHashes.includes(h));
  if(unchanged.length!==1)return null;
  const fixed=unchanged[0];
  const newHash=candidateHashes.find(h=>h!==fixed);
  const oldHash=rootHashes.find(h=>h!==fixed);
  const fixedCandidateIndex=candidateHashes.indexOf(fixed),fixedRootIndex=rootHashes.indexOf(fixed);
  if(fixedCandidateIndex!==fixedRootIndex)return null;
  if(root.outcome==='close_uncertain'||!root.complete)return null;
  const winnerFixed=root.outcome===fixed;
  const rel=relation(profiles.get(newHash),profiles.get(oldHash),profiles.get(fixed),selected.context,
    context(...rootHashes),1-fixedCandidateIndex,1-fixedRootIndex);
  const direction=winnerFixed?-1:1;
  if(rel===direction){
    return {targetPair:pair.key,rootId:root.matchupId,rootPair:root.pairKey,winnerHash:winnerFixed?fixed:newHash,
      fixedHash:fixed,oldHash,newHash,ruleId:'R1_STATIC_DIRECTION',ruleVersion:RULE_VERSION,
      family:`${profiles.get(newHash).line}_vs_${profiles.get(fixed).line}:${winnerFixed?'weaker_loser':'stronger_winner'}`,
      explanation:`${profiles.get(newHash).mechanics.unit_name} replaces ${profiles.get(oldHash).mechanics.unit_name} against ${profiles.get(fixed).mechanics.unit_name}; static attacks, defenses and cost-balanced counts change in the direction of the recorded ${winnerFixed?'winner':'loser'}.`};
  }
  return null;
}

function tradeoffFor(targetContext,root,profiles) {
  if(!root.complete||root.close||root.minWinnerHpFraction<0.5)return null;
  const common=targetContext.profiles.filter(h=>root.profiles.includes(h));
  if(common.length!==1)return null;
  const fixed=common[0],oldHash=root.profiles.find(h=>h!==fixed);
  const replacingWinner=root.outcome===oldHash;
  if(targetContext.profiles.indexOf(fixed)!==root.profiles.indexOf(fixed)
    ||targetContext.scenarioHash!==root.scenarioHash)return null;
  const newHash=targetContext.profiles.find(h=>h!==fixed);
  if(!newHash || newHash===oldHash)return null;
  const oldProfile=profiles.get(oldHash),newProfile=profiles.get(newHash);
  if(!oldProfile||!newProfile || oldProfile.group!==newProfile.group || oldProfile.line!==newProfile.line)return null;
  const previous=oldProfile.mechanics,replacement=newProfile.mechanics,enemy=profiles.get(fixed).mechanics;
  if(!staticSafe(previous)||!staticSafe(replacement)||!staticSafe(enemy))return null;
  const oldCount=root.counts[root.profiles.indexOf(oldHash)];
  const newCount=targetContext.counts[targetContext.profiles.indexOf(newHash)];
  if(replacingWinner) {
    if(replacement.attack_range_tiles<previous.attack_range_tiles
      ||replacement.speed_tiles_per_second<0.9*previous.speed_tiles_per_second
      ||replacement.hp<0.9*previous.hp
      ||attackDelayTicks(replacement)>attackDelayTicks(previous)+18
      ||newCount<0.9*oldCount)return null;
  } else if(replacement.attack_range_tiles>previous.attack_range_tiles
    ||replacement.speed_tiles_per_second>1.05*previous.speed_tiles_per_second
    ||replacement.hp>1.05*previous.hp
    ||attackDelayTicks(replacement)<attackDelayTicks(previous)-6
    ||newCount>1.05*oldCount)return null;
  let nominalRatio,defenseRatio;
  try {
    const oldDamage=calculateDamage(entity(previous),entity(enemy));
    const newDamage=calculateDamage(entity(replacement),entity(enemy));
    const oldIncoming=calculateDamage(entity(enemy),entity(previous));
    const newIncoming=calculateDamage(entity(enemy),entity(replacement));
    nominalRatio=(newDamage*newCount*(replacement.ranged?.accuracy_percent??100)/reloadTicks(replacement))
      /(oldDamage*oldCount*(previous.ranged?.accuracy_percent??100)/reloadTicks(previous));
    defenseRatio=(replacement.hp*newCount/newIncoming)/(previous.hp*oldCount/oldIncoming);
  } catch {return null;}
  if(replacingWinner ? nominalRatio<0.65 || defenseRatio<0.9
    : nominalRatio>1.05 || defenseRatio>1.05)return null;
  const mode=replacingWinner?'stronger_winner':'weaker_loser';
  return {rootId:root.matchupId,rootPair:root.pairKey,winnerHash:replacingWinner?newHash:fixed,fixedHash:fixed,mode,
    oldHash,newHash,nominalRatio,defenseRatio,
    ruleId:'R2_ROBUST_TRADEOFF',family:`${newProfile.line}_vs_${profiles.get(fixed).line}:${mode}`,
    explanation:`${oldProfile.mechanics.unit_name} ${replacingWinner?'wins':'loses'} decisively against ${enemy.unit_name}; ${replacement.unit_name} fields ${newCount} units, with nominal sustained-damage ratio ${nominalRatio.toFixed(2)} and durability ratio ${defenseRatio.toFixed(2)} against that opponent. This is a validated directional transfer, not a simulated fight.`};
}

function buildDecisions(inventory,evidence) {
  const {pairs,profiles,context}=inventory;
  const selected=new Map();
  for(const pair of pairs.values())selected.set(pair.key,selectContext(pair,context));
  const roots=evidence.anchors.filter(a=>a.complete && !a.close && pairs.has(a.pairKey)
    && selected.get(a.pairKey).direct?.matchupId===a.matchupId);
  const rootsByProfile=new Map();
  for(const root of roots)for(const hash of new Set(root.profiles)){
    if(!rootsByProfile.has(hash))rootsByProfile.set(hash,[]);
    rootsByProfile.get(hash).push(root);
  }
  // Choose an unmeasured orientation by mechanical proximity to an existing
  // anchor, without consulting the anchor's winner. This maximizes useful
  // same-setup comparisons and stays deterministic under input reordering.
  for(const pair of pairs.values()) {
    const s=selected.get(pair.key);
    if(s.direct||s.conflict||pair.profiles[0]===pair.profiles[1])continue;
    const candidates=[];
    const nearby=[...new Set(pair.profiles.flatMap(h=>rootsByProfile.get(h)??[]))];
    for(const root of nearby) {
      const common=pair.profiles.filter(h=>root.profiles.includes(h));
      if(common.length!==1)continue;
      const fixed=common[0],newHash=pair.profiles.find(h=>h!==fixed),oldHash=root.profiles.find(h=>h!==fixed);
      const n=profiles.get(newHash),o=profiles.get(oldHash);
      if(n.group!==o.group)continue;
      const priority=n.mechanics.unit_master===o.mechanics.unit_master?0:n.line===o.line?1:2;
      const ordered=root.profiles.map(h=>h===oldHash?newHash:h);
      const trial=context(...ordered);
      if(trial.scenarioHash!==root.scenarioHash)continue;
      candidates.push({priority,matchupId:root.matchupId,context:trial});
    }
    candidates.sort((a,b)=>a.priority-b.priority||a.matchupId.localeCompare(b.matchupId));
    if(candidates.length)s.context=candidates[0].context;
  }
  const index=new Map();
  for(const pair of pairs.values())for(const hash of new Set(pair.profiles)){
    if(!index.has(hash))index.set(hash,[]);index.get(hash).push(pair);
  }
  const proposals=new Map();
  const tradeoffCandidates=new Map();
  const boundaryCandidates=new Map();
  for(const root of roots) for(const fixed of root.profiles) for(const target of index.get(fixed)??[]) {
    if(target.key===root.pairKey || target.profiles[0]===target.profiles[1])continue;
    const s=selected.get(target.key);if(!s.context||s.direct||s.conflict)continue;
    const proposal=proposalFor(target,s,root,profiles,context);
    if(proposal){if(!proposals.has(target.key))proposals.set(target.key,[]);proposals.get(target.key).push(proposal);}
    const item=tradeoffFor(s.context,root,profiles);
    if(!item)continue;
    if(!tradeoffCandidates.has(target.key))tradeoffCandidates.set(target.key,[]);
    tradeoffCandidates.get(target.key).push(item);
  }
  for(const root of roots) for(const fixed of root.profiles) for(const target of index.get(fixed)??[]) {
    if(target.key===root.pairKey)continue;
    const s=selected.get(target.key);
    if(!s.context||s.direct||s.conflict)continue;
    const oldHash=root.profiles.find(h=>h!==fixed),newHash=s.context.profiles.find(h=>h!==fixed);
    if(!newHash||root.outcome!==fixed||s.context.profiles.indexOf(fixed)!==root.profiles.indexOf(fixed)
      ||s.context.scenarioHash!==root.scenarioHash)continue;
    if(profiles.get(oldHash).line!==profiles.get(newHash).line)continue;
    if(!boundaryCandidates.has(target.key))boundaryCandidates.set(target.key,[]);
    boundaryCandidates.get(target.key).push({rootId:root.matchupId});
  }
  // Hold out the target's complete result: no target seeds or aliases enter the proposed root.
  const validation={candidatePredictions:0,correct:0,wrong:0,closePredictedDecisively:0,rootPairs:new Set(),targetPairs:new Set(),families:new Map()};
  const directByPair=new Map();
  for(const pair of pairs.values()){
    const s=selected.get(pair.key);
    if(s.direct)directByPair.set(pair.key,s.direct);
  }
  // Test all observed targets by applying the same rule with their label hidden.
  for(const target of directByPair.values()){
    const pair=pairs.get(target.pairKey),s={context:context(...target.profiles)};
    for(const root of roots){
      if(root.pairKey===target.pairKey || !root.profiles.some(h=>target.profiles.includes(h)))continue;
      const candidate=proposalFor(pair,s,root,profiles,context);
      if(!candidate)continue;
      validation.candidatePredictions++;validation.rootPairs.add(root.pairKey);validation.targetPairs.add(target.pairKey);
      if(!validation.families.has(candidate.family))validation.families.set(candidate.family,{rootPairs:new Set(),targetPairs:new Set(),correct:0,wrong:0,closePredictedDecisively:0});
      const family=validation.families.get(candidate.family);
      family.rootPairs.add(root.pairKey);family.targetPairs.add(target.pairKey);
      if(target.close)validation.closePredictedDecisively++;
      else if(candidate.winnerHash===target.outcome)validation.correct++;
      else validation.wrong++;
      if(target.close)family.closePredictedDecisively++;
      else if(candidate.winnerHash===target.outcome)family.correct++;
      else family.wrong++;
    }
  }
  const familyValidation=Object.fromEntries([...validation.families].map(([name,f])=>[name,{
    heldOutTargetPairs:f.targetPairs.size,independentRootPairs:f.rootPairs.size,correct:f.correct,wrong:f.wrong,
    closePredictedDecisively:f.closePredictedDecisively,
    enabled:f.targetPairs.size>=3&&f.rootPairs.size>=2&&f.wrong===0&&f.closePredictedDecisively===0}]));
  const ruleValidation={ruleId:'R1_STATIC_DIRECTION',ruleVersion:RULE_VERSION,
    candidatePredictions:validation.candidatePredictions,independentRootPairs:validation.rootPairs.size,
    heldOutTargetPairs:validation.targetPairs.size,correct:validation.correct,wrong:validation.wrong,
    closePredictedDecisively:validation.closePredictedDecisively,families:familyValidation,
    requirement:'per family: at least 3 distinct held-out target pairs, 2 independent root pairs, zero wrong winners, zero decisive predictions of close fights'};
  const tradeoffCheck=new Map();
  for(const [engine,source] of [['corrected',evidence.anchors],['original',evidence.prior]]) {
    const complete=source.filter(x=>x.complete&&!x.close&&pairs.has(x.pairKey));
    const byHash=new Map();
    for(const root of complete)for(const h of new Set(root.profiles)){
      if(!byHash.has(h))byHash.set(h,[]);byHash.get(h).push(root);
    }
    for(const target of complete) {
      const targetContext=context(...target.profiles);
      for(const fixed of new Set(target.profiles))for(const root of byHash.get(fixed)??[]) {
        if(root.pairKey===target.pairKey)continue;
        const proposal=tradeoffFor(targetContext,root,profiles);
        if(!proposal)continue;
        const k=`${proposal.family}|${engine}`;
        if(!tradeoffCheck.has(k))tradeoffCheck.set(k,{rootPairs:new Set(),targets:new Map()});
        const entry=tradeoffCheck.get(k);
        entry.rootPairs.add(root.pairKey);
        if(!entry.targets.has(target.pairKey))entry.targets.set(target.pairKey,{actual:target.outcome,predictions:new Set()});
        entry.targets.get(target.pairKey).predictions.add(proposal.winnerHash);
      }
    }
  }
  const tradeoffFamilies={};
  for(const [key,entry] of tradeoffCheck) {
    const n=key.lastIndexOf('|'),family=key.slice(0,n),engine=key.slice(n+1);
    tradeoffFamilies[family]??={};
    const wrong=[...entry.targets.values()].filter(t=>t.predictions.size!==1||!t.predictions.has(t.actual)).length;
    tradeoffFamilies[family][engine]={targets:entry.targets.size,independentRoots:entry.rootPairs.size,
      correct:entry.targets.size-wrong,wrong};
  }
  const modes=['stronger_winner','weaker_loser'];
  const tradeoffModeStats=Object.fromEntries(modes.map(mode=>[mode,{
    targets:{corrected:new Set(),original:new Set()},roots:{corrected:new Set(),original:new Set()},wrong:0}]));
  for(const [key,entry] of tradeoffCheck) {
    const engine=key.slice(key.lastIndexOf('|')+1);
    const mode=key.includes(':weaker_loser|')?'weaker_loser':'stronger_winner';
    for(const id of entry.targets.keys())tradeoffModeStats[mode].targets[engine].add(id);
    for(const id of entry.rootPairs)tradeoffModeStats[mode].roots[engine].add(id);
  }
  for(const [family,tests] of Object.entries(tradeoffFamilies)) {
    const old=tests.original??{targets:0,wrong:0},current=tests.corrected??{targets:0,wrong:0};
    const mode=family.endsWith(':weaker_loser')?'weaker_loser':'stronger_winner';
    tradeoffModeStats[mode].wrong+=old.wrong+current.wrong;
  }
  const tradeoffModeValidation={};
  for(const [mode,stats] of Object.entries(tradeoffModeStats)) {
    tradeoffModeValidation[mode]={enabled:stats.targets.original.size>=50
      &&stats.targets.corrected.size>=5&&stats.wrong===0,
      originalTargets:stats.targets.original.size,correctedTargets:stats.targets.corrected.size,
      originalRoots:stats.roots.original.size,correctedRoots:stats.roots.corrected.size,wrong:stats.wrong};
  }
  for(const [family,tests] of Object.entries(tradeoffFamilies)) {
    const old=tests.original??{wrong:0},current=tests.corrected??{wrong:0};
    const mode=family.endsWith(':weaker_loser')?'weaker_loser':'stronger_winner';
    tests.mode=mode;
    tests.enabled=tradeoffModeValidation[mode].enabled&&old.wrong===0&&current.wrong===0;
  }
  const tradeoffValidation={ruleId:'R2_ROBUST_TRADEOFF',ruleVersion:RULE_VERSION,
    requirement:'per directional mode: at least 50 independent original-engine and 5 corrected-engine held-out targets, zero wrong predictions in either stratum; disable any family with a known counterexample',
    modes:tradeoffModeValidation,
    families:tradeoffFamilies};
  const decisions=[];const reasonCounts={};
  const priorByPair=new Map();for(const p of evidence.prior)if(pairs.has(p.pairKey)){
    if(!priorByPair.has(p.pairKey))priorByPair.set(p.pairKey,[]);priorByPair.get(p.pairKey).push(p);
  }
  for(const pair of pairs.values()) {
    const s=selected.get(pair.key),rootsHere=proposals.get(pair.key)??[];
    const tradeoffs=tradeoffCandidates.get(pair.key)??[];
    const boundaries=boundaryCandidates.get(pair.key)??[];
    const prior=priorByPair.get(pair.key)??[];
    const base={pairKey:pair.key,profiles:pair.profiles,context:s.context??null,aliases:pair.aliases.length,
      ruleVersion:RULE_VERSION};
    let decision;
    if(pair.profiles[0]===pair.profiles[1])decision={...base,outcome:'equivalent',evidenceType:'identity',needsSim:false,
      explanation:'Both sides have exactly the same mechanics profile; there is no intrinsic unit advantage.'};
    else if(s.conflict)decision={...base,outcome:'unresolved',evidenceType:'none',needsSim:true,reasonCodes:['orientation_conflict'],
      sourceMatchups:s.contexts.map(x=>x.matchupId),explanation:'Compatible completed source contexts disagree; retain each result separately.'};
    else if(s.direct)decision={...base,outcome:s.direct.close?'close_uncertain':s.direct.outcome,
      evidenceType:'observed',needsSim:false,sourceMatchups:s.otherDirect.map(x=>x.matchupId),
      sourceRunIds:s.direct.selectedRunIds,seedOutcomes:s.direct.seedOutcomes,
      explanation:s.direct.close?'Completed compatible seeds include different outcomes.':`Corrected-engine source ${s.direct.matchupId} has a completed compatible seed set.`};
    else {
      const predicted=new Set(rootsHere.map(x=>x.winnerHash));
      const tradeoffWinners=new Set(tradeoffs.map(x=>x.winnerHash));
      const priorWinners=new Set(prior.filter(x=>x.complete&&!x.close).map(x=>x.outcome));
      const candidateOutcome=predicted.size===1?[...predicted][0]:tradeoffWinners.size===1?[...tradeoffWinners][0]:
        priorWinners.size===1?[...priorWinners][0]:null;
      const validatedProposals=rootsHere.filter(x=>familyValidation[x.family]?.enabled);
      const validatedTradeoffs=tradeoffs.filter(x=>tradeoffModeValidation[x.mode]?.enabled
        &&tradeoffFamilies[x.family]?.enabled!==false);
      const eligibleWinners=new Set([...validatedProposals,...validatedTradeoffs].map(x=>x.winnerHash));
      const priorConflict=priorWinners.size && eligibleWinners.size===1 && !priorWinners.has([...eligibleWinners][0]);
      const reasonCodes=[];
      if(s.partial?.length)reasonCodes.push('incomplete_current_seeds');
      if(prior.length)reasonCodes.push('prior_engine_only');
      if(rootsHere.length && predicted.size>1)reasonCodes.push('conflicting_inferences');
      else if(rootsHere.length && !validatedProposals.length)reasonCodes.push('rule_needs_validation');
      if(tradeoffs.length && !validatedTradeoffs.length)reasonCodes.push('unvalidated_tradeoff');
      if(boundaries.length)reasonCodes.push('possible_win_boundary');
      if(priorConflict)reasonCodes.push('prior_engine_conflict');
      if(!rootsHere.length && !tradeoffs.length && !boundaries.length && !s.partial?.length && !prior.length)reasonCodes.push('no_eligible_anchor');
      if(pair.profiles.some(h=>!staticSafe(profiles.get(h).mechanics)))reasonCodes.push('unsupported_effect');
      if(!reasonCodes.length)reasonCodes.push('no_eligible_anchor');
      const allProposedWinners=new Set([...rootsHere,...tradeoffs].map(x=>x.winnerHash));
      const resolvable=eligibleWinners.size===1 && allProposedWinners.size===1 && !priorConflict && !s.partial?.length;
      decision={...base,outcome:resolvable?candidateOutcome:'unresolved',evidenceType:resolvable?'inferred':'none',
        needsSim:!resolvable,reasonCodes:resolvable?[]:reasonCodes,candidateOutcome:resolvable?null:candidateOutcome,
        ruleId:validatedProposals.length?'R1_STATIC_DIRECTION':validatedTradeoffs.length?'R2_ROBUST_TRADEOFF':
          rootsHere.length?'R1_STATIC_DIRECTION':tradeoffs.length?'R2_ROBUST_TRADEOFF':null,
        rootAnchorIds:[...new Set([...rootsHere.map(x=>x.rootId),...tradeoffs.map(x=>x.rootId),...boundaries.map(x=>x.rootId)])].sort(),
        tradeoffFamily:tradeoffs.length?tradeoffs[0].family:null,
        priorMatchups:prior.map(x=>x.matchupId).sort(),
        explanation:resolvable?(validatedProposals[0]??validatedTradeoffs[0]).explanation:
          rootsHere.length?`${rootsHere.length} static directional transfer(s) proposed; applicable family validation or evidence is insufficient.`:
          tradeoffs.length?tradeoffs[0].explanation:
          boundaries.length?'The benchmark opponent wins against a related unit; the replacement may cross the win boundary.':
          prior.length?'Only prior-engine ranking evidence or an unvalidated boundary is available.':'No validated direct anchor or transfer resolves this pair.'};
    }
    if(decision.outcome==='unresolved')for(const reason of decision.reasonCodes)statusCount(reasonCounts,reason);
    if(pair.profiles.includes(decision.outcome)) {
      decision.winnerProfileHash=decision.outcome;
      decision.outcome=decision.outcome===pair.profiles[0]?'a_win':'b_win';
    }
    if(decision.candidateOutcome && pair.profiles.includes(decision.candidateOutcome)) {
      decision.candidateWinnerProfileHash=decision.candidateOutcome;
      decision.candidateOutcome=decision.candidateOutcome===pair.profiles[0]?'a_win':'b_win';
    }
    decisions.push(decision);
  }
  return {decisions,proposals,ruleValidation,tradeoffValidation,reasonCounts,roots:roots.length};
}

function buildExports(inventory,evidence,results) {
  const {variants,pairs}=inventory;
  const decisionByPair=new Map(results.decisions.map(d=>[d.pairKey,d]));
  const cellRows=[],coverage={profiles:{},cells:{},byCiv:{},byGroup:{}};
  for(const d of results.decisions)statusCount(coverage.profiles,d.outcome);
  for(const pair of pairs.values()){
    const d=decisionByPair.get(pair.key);
    for(const [ai,bi] of pair.aliases){
      const a=variants[ai],b=variants[bi];
      const ordered=a.civilization<b.civilization?[a,b]:[b,a];
      const outcome=d.winnerProfileHash===a.profileHash?'a_win':d.winnerProfileHash===b.profileHash?'b_win':d.outcome;
      const cell={civA:ordered[0].civilization,unitA:ordered[0].slug,nameA:ordered[0].name,
        groupA:ordered[0].group,lineA:ordered[0].line,
        civB:ordered[1].civilization,unitB:ordered[1].slug,nameB:ordered[1].name,
        groupB:ordered[1].group,lineB:ordered[1].line,
        pairKey:pair.key,outcome:ordered[0]===a?outcome:outcome==='a_win'?'b_win':outcome==='b_win'?'a_win':outcome,
        evidenceType:d.evidenceType,needsSim:d.needsSim,reasonCodes:d.reasonCodes??[],
        candidateOutcome:d.candidateWinnerProfileHash?d.candidateWinnerProfileHash===ordered[0].profileHash?'a_win':'b_win':null,
        context:d.context,sourceMatchups:d.sourceMatchups??[],rootAnchorIds:d.rootAnchorIds??[],
        ruleId:d.ruleId??null,ruleVersion:d.ruleVersion,explanation:d.explanation};
      cellRows.push(cell);statusCount(coverage.cells,cell.outcome);
      for(const civ of [a.civilization,b.civilization]){
        coverage.byCiv[civ]??={};statusCount(coverage.byCiv[civ],cell.outcome);
      }
      for(const group of [a.group,b.group]){
        coverage.byGroup[group]??={};statusCount(coverage.byGroup[group],cell.outcome);
      }
    }
  }
  cellRows.sort((a,b)=>[a.civA,a.civB,a.unitA,a.unitB].join('|').localeCompare([b.civA,b.civB,b.unitA,b.unitB].join('|')));
  assert.equal(cellRows.length,151223);assert.equal(results.decisions.length,68916);
  const needsSim=results.decisions.filter(d=>d.needsSim).map(d=>({pairKey:d.pairKey,
    affectedCells:d.aliases,reasonCodes:d.reasonCodes,candidateOutcome:d.candidateOutcome??null,
    dependencies:d.rootAnchorIds??[],priorMatchups:d.priorMatchups??[],tradeoffFamily:d.tradeoffFamily??null}));
  const requirements=new Map();
  for(const item of needsSim) {
    const rule=item.reasonCodes.includes('rule_needs_validation') && item.dependencies.length;
    const id=rule?`validate:${RULE_VERSION}`:item.tradeoffFamily?`validate:R2:${item.tradeoffFamily}`:`direct:${item.pairKey}`;
    if(!requirements.has(id))requirements.set(id,{id,kind:rule?'rule_validation':'direct_pair',
      affectedProfilePairs:0,affectedCells:0,examplePairs:[]});
    const entry=requirements.get(id);
    entry.affectedProfilePairs++;entry.affectedCells+=item.affectedCells;
    if(entry.examplePairs.length<10)entry.examplePairs.push(item.pairKey);
  }
  const review={britonsAztecs:cellRows.filter(x=>x.civA==='Aztecs'&&x.civB==='Britons'
    && ['arbalester','elite_longbowman_britons'].includes(x.unitB)
    && ['halberdier','elite_eagle','champion'].includes(x.unitA)),
    conflicts:results.decisions.filter(d=>d.reasonCodes?.includes('orientation_conflict')).slice(0,20)};
  return {cellRows,coverage,needsSim,requirements:[...requirements.values()],review};
}

function atomic(path,value) {const tmp=`${path}.tmp`;writeFileSync(tmp,value);renameSync(tmp,path);}
export function buildPhaseOne(outputDirectory,{campaignDirectories=[]}={}) {
  const {sourceManifest,definition,scoring}=canonicalInputs();
  const inventory=profilesAndPairs(sourceManifest,definition);
  const evidence=sourceEvidence(definition,sourceManifest,inventory.profiles,inventory.pairs,inventory.context,campaignDirectories);
  const results=buildDecisions(inventory,evidence);
  const exports=buildExports(inventory,evidence,results);
  const sourceFiles=[...evidence.sourceFiles,...[DEFINITION,SCORES,resolve(SOURCE,'manifest.json'),fileURLToPath(import.meta.url),
    resolve(SIM,'node/build-civ-matchup-inference.mjs')]
    .map(path=>({path:relative(ROOT,path),sha256:sha(readFileSync(path))}))];
  const manifest={schemaVersion:1,phase:'infer-only',sourceDatasetHash:sourceManifest.datasetHash,
    correctedCampaignHash:definition.campaignHash,ruleVersion:RULE_VERSION,
    additionalCampaignHashes:evidence.additionalCampaignHashes,
    engineSourceCommit:definition.sourceCommit,engineRuntimeFiles:definition.runtimeFiles,
    engineConfig:definition.engineConfig,policy:definition.policy,sourceFiles,
    counts:{civilizations:56,civilizationPairs:inventory.civPairs,
      variants:inventory.variants.length,profiles:inventory.profiles.size,variantCells:inventory.variantCells,
      profilePairs:inventory.pairs.size,sourceRuns:evidence.runLedger.length},
    simulationJobsRun:0};
  mkdirSync(outputDirectory,{recursive:true});
  const lines=rows=>rows.map(x=>JSON.stringify(x)).join('\n')+'\n';
  const outputFiles=[];
  for(const [name,rows] of [
    ['profile-matchups',results.decisions],['civ-matchups',exports.cellRows],
    ['needs-sim',exports.needsSim],['requirements',exports.requirements],
    ['evidence-ledger',evidence.runLedger],
  ]) {
    const file=`${name}.jsonl.gz`,buffer=gzipSync(Buffer.from(lines(rows)));
    atomic(resolve(outputDirectory,file),buffer);
    outputFiles.push({file,rows:rows.length,sha256:sha(buffer)});
    const old=resolve(outputDirectory,`${name}.jsonl`);
    if(existsSync(old))unlinkSync(old);
  }
  const variantFile='variant-profiles.json';
  const variantContent=JSON.stringify(inventory.variants.map(v=>({key:v.key,profileHash:v.profileHash,
    civilization:v.civilization,slug:v.slug,name:v.name,line:v.line,group:v.group})),null,2)+'\n';
  atomic(resolve(outputDirectory,variantFile),variantContent);
  outputFiles.push({file:variantFile,rows:inventory.variants.length,sha256:sha(variantContent)});
  for(const [file,data] of [
    ['rule-validation.json',results.ruleValidation],['tradeoff-validation.json',results.tradeoffValidation],
    ['review.json',exports.review],
  ]) {
    const content=JSON.stringify(data,null,2)+'\n';
    atomic(resolve(outputDirectory,file),content);
    outputFiles.push({file,sha256:sha(content)});
  }
  manifest.outputs=outputFiles;
  manifest.buildHash=hashCanonicalJson(manifest);
  const summary={manifestHash:manifest.buildHash,coverage:exports.coverage,
    sourceGroupCounts:evidence.sourceGroupCounts,reasonCounts:results.reasonCounts,
    ruleValidation:results.ruleValidation,tradeoffValidation:results.tradeoffValidation,
    uniqueNeedsSim:exports.needsSim.length,
    groupedRequirements:exports.requirements.length,
    roots:results.roots,simulationJobsRun:0};
  atomic(resolve(outputDirectory,'summary.json'),JSON.stringify(summary,null,2)+'\n');
  const reviewLines=[
    '# Civilization matchups: phase-one inference',
    '',
    `Build hash: ${manifest.buildHash}`,
    `Distinct profile pairs: ${inventory.pairs.size}; expanded civ-unit cells: ${exports.cellRows.length}.`,
    `Observed: ${results.decisions.filter(d=>d.evidenceType==='observed').length}; inferred: ${results.decisions.filter(d=>d.evidenceType==='inferred').length}; equivalent: ${results.decisions.filter(d=>d.evidenceType==='identity').length}; unresolved: ${exports.needsSim.length}.`,
    `R1 held-out validation: ${results.ruleValidation.correct} correct predictions against ${results.ruleValidation.heldOutTargetPairs} distinct targets; ${results.ruleValidation.wrong} wrong; ${results.ruleValidation.closePredictedDecisively} close fights predicted decisively.`,
    `R2 stronger-winner validation: ${results.tradeoffValidation.modes.stronger_winner.originalTargets} original-engine and ${results.tradeoffValidation.modes.stronger_winner.correctedTargets} corrected-engine targets; ${results.tradeoffValidation.modes.stronger_winner.wrong} wrong.`,
    `R2 weaker-loser validation: ${results.tradeoffValidation.modes.weaker_loser.originalTargets} original-engine and ${results.tradeoffValidation.modes.weaker_loser.correctedTargets} corrected-engine targets; ${results.tradeoffValidation.modes.weaker_loser.wrong} wrong.`,
    '',
    '## Britons against Aztecs',
    '',
    '| Aztec unit | Briton unit | Result | Candidate | Reason |',
    '|---|---|---|---|---|',
    ...exports.review.britonsAztecs.map(r=>`| ${r.nameA} | ${r.nameB} | ${r.outcome} | ${r.candidateOutcome??'—'} | ${r.reasonCodes.join(', ')||'—'} |`),
    '',
    'A candidate is a prediction for prioritization, not a resolved matchup. Older-engine ranking fights are retained as prior evidence only.',
    'All saved runs were read. No simulation or replay was executed by this build.',
    '',
  ];
  atomic(resolve(outputDirectory,'review.md'),reviewLines.join('\n'));
  // Final manifest is written last, so an interrupted build is not presented as complete.
  atomic(resolve(outputDirectory,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  return summary;
}
