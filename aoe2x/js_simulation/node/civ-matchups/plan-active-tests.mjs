// Offline planning only. This never imports a fight runner or records an outcome.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {canonicalInputs,profilesAndPairs,proposalFor,tradeoffFor,twoSidedFor} from './phase-one.mjs';

const sim=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const output=resolve(process.argv[2]??resolve(sim,'calibration/campaigns/civ-matchups-inference-two-sided-audit-2026-11-01'));
const report=resolve(process.argv[3]??resolve(sim,'calibration/reports/civ-matchups-inference-audit-2026-10-31/test-priority.json'));
const sha=buffer=>createHash('sha256').update(buffer).digest('hex');
const read=path=>readFileSync(resolve(output,path));
const decisions=gunzipSync(read('profile-matchups.jsonl.gz')).toString('utf8').trim().split('\n').map(JSON.parse);
const validation=JSON.parse(read('rule-validation.json'));
const tradeoffValidation=JSON.parse(read('tradeoff-validation.json'));
const jointValidation=JSON.parse(read('two-sided-validation.json'));
const {sourceManifest,definition,scoring}=canonicalInputs();
const inventory=profilesAndPairs(sourceManifest,definition);
const scoreByVariant=new Map(scoring.map(x=>[`${x.civilization}|${x.unitSlug}`,x.score]));
const profileScore=new Map([...inventory.profiles].map(([hash,profile])=>{
  const valid=profile.aliases.map(key=>scoreByVariant.get(key)).filter(Number.isFinite);
  return [hash,valid.length?valid.reduce((a,b)=>a+b,0)/valid.length:null];
}));
const unresolved=decisions.filter(d=>d.outcome==='unresolved'&&d.context&&d.profiles[0]!==d.profiles[1]);
const master=hash=>inventory.profiles.get(hash).mechanics.unit_master;
const index=new Map();
const masterIndex=new Map();
for(const d of unresolved)for(const fixed of d.profiles){
  const other=d.profiles.find(h=>h!==fixed);
  const key=`${fixed}|${master(other)}`;
  if(!index.has(key))index.set(key,[]);
  index.get(key).push(d);
}
for(const d of unresolved){
  const key=d.profiles.map(master).sort().join('|');
  if(!masterIndex.has(key))masterIndex.set(key,[]);
  masterIndex.get(key).push(d);
}
function neighbors(d){
  const out=new Map();
  for(const fixed of d.profiles){
    const other=d.profiles.find(h=>h!==fixed);
    for(const target of index.get(`${fixed}|${master(other)}`)??[]){
      if(target.pairKey!==d.pairKey)out.set(target.pairKey,target);
    }
  }
  return [...out.values()];
}
const sameMasters=d=>masterIndex.get(d.profiles.map(master).sort().join('|'))??[];
const candidateBounds=unresolved.map(d=>{
  const nearby=neighbors(d);
  const joint=sameMasters(d).filter(x=>x.pairKey!==d.pairKey
    &&!nearby.some(y=>y.pairKey===x.pairKey));
  return {d,upperBoundPairs:nearby.length+joint.length,
    upperBoundCells:[...nearby,...joint].reduce((n,x)=>n+x.aliases,0)};
}).sort((a,b)=>b.upperBoundPairs-a.upperBoundPairs||b.upperBoundCells-a.upperBoundCells||a.d.pairKey.localeCompare(b.d.pairKey));
// Evaluate enough mechanically promising candidates to find the strongest
// tests. The remaining candidates retain an explicit upper bound.
const limit=Number(process.env.CIV_TEST_PLAN_LIMIT??3000);
const evaluated=[];
const veto=new Set(['incomplete_current_seeds','prior_engine_conflict','orientation_conflict','conflicting_inferences']);
for(const item of candidateBounds.slice(0,limit)){
  const d=item.d,targets=neighbors(d),jointTargets=sameMasters(d);
  const byWinner=[];
  for(const winnerHash of d.context.profiles){
    const hypothetical={profiles:d.context.profiles,counts:d.context.counts,
      scenarioHash:d.context.scenarioHash,pairKey:d.pairKey,matchupId:`prospective:${d.pairKey}`,
      complete:true,close:false,outcome:winnerHash,minWinnerHpFraction:0.5};
    let pairs=0,cells=0,tradeoffPairs=0,tradeoffCells=0,jointPairs=0,jointCells=0;
    const targetPairKeys=[];
    const examples=[];
    for(const target of targets){
      if(target.reasonCodes?.some(code=>veto.has(code)))continue;
      const proposal=proposalFor(inventory.pairs.get(target.pairKey),
        {context:target.context},hypothetical,inventory.profiles,inventory.context);
      const r1=proposal&&validation.families[proposal.family]?.enabled?proposal:null;
      const tradeoff=tradeoffFor(target.context,hypothetical,inventory.profiles);
      let r2=null;
      if(tradeoff && tradeoffValidation.modes[tradeoff.mode]?.enabled
        &&tradeoffValidation.families[tradeoff.family]?.enabled!==false){
        const newEffect=[tradeoff.fixedHash,tradeoff.oldHash,tradeoff.newHash].some(h=>{
          const e=inventory.profiles.get(h)?.mechanics.effects??{};
          return Boolean(e.speed_attack_aura_recipient||e.combat_gold_per_animation_second
            ||e.gold_per_kill||e.death_resource_refund_fraction);
        });
        const heldOut=tradeoffValidation.families[tradeoff.family]?.corrected;
        if(!newEffect||((heldOut?.targets??0)>=3&&(heldOut?.independentRoots??0)>=2))r2=tradeoff;
      }
      const winners=new Set([r1,r2].filter(Boolean).map(x=>x.winnerHash));
      if(winners.size!==1)continue;
      const winner=[...winners][0];
      if(target.candidateOutcome && target.candidateOutcome!==winner)continue;
      if(r1){pairs++;cells+=target.aliases;}
      else {tradeoffPairs++;tradeoffCells+=target.aliases;}
      targetPairKeys.push(target.pairKey);
      if(examples.length<5)examples.push({pairKey:target.pairKey,winnerHash:winner,
        ruleFamily:(r1??r2).family});
    }
    for(const target of jointTargets){
      if(target.pairKey===d.pairKey||target.reasonCodes?.some(code=>veto.has(code)))continue;
      const proposal=twoSidedFor(target.context,hypothetical,inventory.profiles,inventory.context);
      if(!proposal||!jointValidation.families[proposal.family]?.enabled)continue;
      if(target.candidateOutcome && target.candidateOutcome!==proposal.winnerHash)continue;
      jointPairs++;jointCells+=target.aliases;targetPairKeys.push(target.pairKey);
    }
    byWinner.push({winnerHash,profilePairs:pairs+tradeoffPairs+jointPairs,
      displayedCells:cells+tradeoffCells+jointCells,
      r1Pairs:pairs,r3PairsIfWinnerHpAtLeast25Percent:jointPairs,
      r2PairsIfWinnerHpAtLeast50Percent:tradeoffPairs,
      r1Cells:cells,r3CellsIfWinnerHpAtLeast25Percent:jointCells,
      r2CellsIfWinnerHpAtLeast50Percent:tradeoffCells,
      targetPairKeys,examples});
  }
  const a=inventory.profiles.get(d.context.profiles[0]);
  const b=inventory.profiles.get(d.context.profiles[1]);
  const representative=inventory.pairs.get(d.pairKey).aliases[0].map(i=>inventory.variants[i]);
  const scoreGapSameLine=a.line===b.line && profileScore.get(a.hash)!==null && profileScore.get(b.hash)!==null
    ?Math.abs(profileScore.get(a.hash)-profileScore.get(b.hash)):null;
  evaluated.push({pairKey:d.pairKey,profiles:d.context.profiles,
    units:d.context.profiles.map(h=>({unit:representative.find(v=>v.profileHash===h).name,
      civilization:representative.find(v=>v.profileHash===h).civilization,
      aliases:inventory.profiles.get(h).aliases.length})),
    counts:d.context.counts,scenarioHash:d.context.scenarioHash,aliases:d.aliases,
    linePair:[a.line,b.line],scoreGapSameLine,
    upperBoundPairs:item.upperBoundPairs,upperBoundCells:item.upperBoundCells,
    possibleByWinner:byWinner,
    worstCasePairs:Math.min(...byWinner.map(x=>x.profilePairs)),
    meanPairs:byWinner.reduce((n,x)=>n+x.profilePairs,0)/2,
    worstCaseCells:Math.min(...byWinner.map(x=>x.displayedCells)),
    meanCells:byWinner.reduce((n,x)=>n+x.displayedCells,0)/2});
}
evaluated.sort((a,b)=>b.worstCasePairs-a.worstCasePairs||b.meanPairs-a.meanPairs||b.worstCaseCells-a.worstCaseCells||a.pairKey.localeCompare(b.pairKey));
const selectedTargets=new Set(),familyQuota=new Map(),recommended=[];
const pool=evaluated.slice(0,1500);
for(let slot=0;slot<20;slot++){
  const options=pool.filter(d=>!recommended.some(x=>x.pairKey===d.pairKey)
    &&!(d.scoreGapSameLine!==null&&d.scoreGapSameLine<5)
    &&(familyQuota.get(d.linePair.slice().sort().join('|'))??0)<3)
    .map(d=>{
      const marginal=d.possibleByWinner.map(x=>x.targetPairKeys.filter(k=>!selectedTargets.has(k)).length);
      return {d,marginal,worst:Math.min(...marginal),mean:marginal.reduce((a,b)=>a+b,0)/2};
    }).sort((a,b)=>b.worst-a.worst||b.mean-a.mean||b.d.aliases-a.d.aliases||a.d.pairKey.localeCompare(b.d.pairKey));
  const best=options[0];if(!best||best.worst===0)break;
  recommended.push({...best.d,marginalIfEitherWinner:best.marginal});
  for(const side of best.d.possibleByWinner)for(const key of side.targetPairKeys)selectedTargets.add(key);
  const family=best.d.linePair.slice().sort().join('|');familyQuota.set(family,(familyQuota.get(family)??0)+1);
}
const result={kind:'offline prospective R1/R2/R3 test prioritization',inferenceBuildManifestHash:JSON.parse(read('summary.json')).manifestHash,
  decisionsSha256:sha(read('profile-matchups.jsonl.gz')),validationSha256:sha(read('rule-validation.json')),
  totalUnresolved:unresolved.length,evaluatedCandidates:evaluated.length,
  unevaluatedCandidates:Math.max(0,candidateBounds.length-evaluated.length),
  largestUnevaluatedUpperBoundPairs:candidateBounds[evaluated.length]?.upperBoundPairs??0,
  recommendationPolicy:'Greedy marginal profile-pair coverage across both possible decisive winners; at most 3 tests per unit-line pair; same-line ranking-score gaps under 5 are deferred as close-risk candidates. Ranking scores affect scheduling only, never an inferred outcome.',
  note:'Each number is a conditional upper bound on extra unresolved pairs that a decisive result could transfer via currently validated R1, R2, and R3 rules. R2 requires at least 50% winner HP and R3 at least 25% in every valid seed. A close fight transfers zero; conflicting evidence, later seed disagreement, or changed V2 physics can reduce it. No outcome is predicted, no simulation was run, and no journal was changed.',
  recommendations:recommended,top:evaluated.slice(0,100)};
mkdirSync(dirname(report),{recursive:true});writeFileSync(report,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({report,totalUnresolved:result.totalUnresolved,evaluatedCandidates:result.evaluatedCandidates,
  largestUnevaluatedUpperBoundPairs:result.largestUnevaluatedUpperBoundPairs,top:result.top.slice(0,10).map(x=>({units:x.units.map(y=>y.unit),counts:x.counts,aliases:x.aliases,worstCasePairs:x.worstCasePairs,meanPairs:x.meanPairs,possibleByWinner:x.possibleByWinner.map(y=>y.profilePairs)}))},null,2));
