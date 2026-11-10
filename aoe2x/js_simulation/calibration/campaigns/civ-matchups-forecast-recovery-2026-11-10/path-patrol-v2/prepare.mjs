import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {FROZEN,payload,digest} from '/workspace/aoe2_civ_forecast_validation/aoe2x/js_simulation/node/civ-matchups/forecast-validation-lib.mjs';
const root='/workspace/aoe2_civ_forecast_recovery', baseRoot='/workspace/aoe2_civ_forecast_validation';
const r='aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-recovery-2026-11-10', c='aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-validation-2026-11-07';
const read=p=>JSON.parse(readFileSync(p));const sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const prior=read(resolve(root,r,'collision-core-v1/manifest.json'));for(const s of prior.frozenSources)assert.equal(sha(s.path),s.sha256,s.path);
for(const f of ['manifest.json','sampling-policy-v2.json','sampling-policy-v3.json']){
 const data=read(resolve(baseRoot,c,f));const {campaignHash,amendmentHash,...body}=data;assert.equal(digest(body),campaignHash??amendmentHash);
}
const review=read(resolve(baseRoot,c,'recovery-review/2026-11-10/review.json'));
const selected=review.cases.filter(c=>c.category!=='collision_exception').sort((a,b)=>(a.category==='cross_engine_projection')-(b.category==='cross_engine_projection'));
const v3=read(resolve(baseRoot,c,'sampling-policy-v3.json'));
const cases=selected.map(c=>{
 const context=c.physicalContext, evidence=c.originalEvidence[0].record;
 const keys=c.teamKeys??c.profilesAndAliases.map(aliases=>aliases[0].key);
 assert.deepEqual(keys.map(k=>digest(Object.fromEntries(Object.entries(FROZEN.profiles[k].mechanics).filter(([field])=>field!=="civilization")))),context.profiles);
 const job={id:c.jobId,context,contextHash:c.contextHash,counts:c.counts,engineFamily:context.engineFamily,family:context.family,
 profileHashes:context.profiles,scenarioHash:context.scenarioHash,pairKey:evidence.pairKey,teamKeys:keys,displayedCells:c.displayedCells};
 assert.equal(digest(context),c.contextHash);
 return {job,label:c.label,category:c.category,payload:payload(job,0),originalOutcomes:[...new Set(c.originalEvidence.map(e=>e.record.originalPrediction?.outcome??e.record.outcome))],
 preservedNativeReferences:(c.nativeSeedReferences??[]).map(ref=>({...ref,path:resolve(baseRoot,ref.path)})),
 historicalProjectionReferences:c.verifiedOtherEngineSeedReferences??[],
 originalReviewReference:{path:resolve(baseRoot,cPath()),jobId:c.jobId,sha256:sha(resolve(baseRoot,cPath()))}};
});
function cPath(){return c+'/recovery-review/2026-11-10/review.json';}
const dir=resolve(root,r,'path-patrol-v2');assert(!existsSync(dir));mkdirSync(dir);
const save=(name,data)=>writeFileSync(resolve(dir,name),JSON.stringify(data,null,2)+'\n',{flag:'wx'});
const policy={minimumWinnerHpFraction:0.25,independentExactReplayRequired:false,
 legacyInProgressJobs:cases.filter(c=>c.preservedNativeReferences.length||c.category==='cross_engine_projection').map(c=>c.job.id),
 baseAmendmentHash:v3.amendmentHash,extraSeedsOnMixedWinners:[3,4,5,6,7,8,9]};
save('input.json',{cases,policy});
const paths=[...prior.runtimeFiles.map(x=>x.path),'aoe2x/js_simulation/node/recovery-validation-worker.mjs','aoe2x/js_simulation/node/civ-matchups/run-recovery-batch.mjs'];
const runtimeFiles=paths.map(path=>({path,sha256:sha(resolve(root,path))}));
const authorization={sourceRole:'user',sourceMessage:"For the ones, the 19 that are completed runs and earlier engine versions, just rerun them again. 19 doesn't really matter, just rerun those. This main thing to fix is the 16 that have proceed or patrol failures. That's something that you may need to check in the way the engine works. That's causing this problem. Maybe you can change the seed or something. Just get it, you know, get some kind of a result. That's what matters.",
 interpretation:'Explicit exception permits rerunning the 19 older-engine projections under the repaired engine. The 16 diagnosed pursuit/patrol contexts have priority and only their missing seeds are executed. Original seeds are retained; no seed cherry-picking, outcome fabrication, exact replay or original ledger overwrite.',
 automaticPublicationAuthorized:false,productionReleaseAuthorized:false,recurringTasksRemainDisabled:true};
save('authorization.json',authorization);
const manifest={schemaVersion:1,kind:'explicit-forecast-recovery',createdAt:new Date().toISOString(),physicsVersion:'forecast-recovery-path-patrol-v2',
 baseCampaignHash:prior.baseCampaignHash,basePhysicsVersion:prior.basePhysicsVersion,sourceCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),
 nodeVersion:process.version,allowedJobs:cases.map(c=>c.job.id),authorizedCrossEngineReruns:cases.filter(c=>c.category==='cross_engine_projection').map(c=>c.job.id),
 workers:4,wallTimeoutSteps:[180,600,1800,3600],maxSimulationTicks:Number.MAX_SAFE_INTEGER,simulationEnvironment:{},
 samplingPolicyHash:v3.amendmentHash,inputSha256:sha(resolve(dir,'input.json')),authorizationSha256:sha(resolve(dir,'authorization.json')),
 runtimeFiles,frozenSources:prior.frozenSources,nativeLedgers:prior.nativeLedgers,authorization,
 changedRuntimeFiles:runtimeFiles.filter(f=>prior.runtimeFiles.some(s=>s.path===f.path&&s.sha256!==f.sha256)),
 exactReplay:{required:false,performed:false,exact:null}};
save('manifest.json',{...manifest,manifestHash:digest(manifest)});
save('preparation.json',{createdAt:new Date().toISOString(),nativeExecutionsDuringPreparation:0,baseManifestAndBothAmendmentsVerified:true,
 savedDiagnosticGeometry:resolve(root,r,'diagnosis/saved-geometry.json'),savedDiagnosticGeometrySha256:sha(resolve(root,r,'diagnosis/saved-geometry.json')),
 priorityCases:16,authorizedOlderEngineReruns:19,protectedNativeSeeds:cases.reduce((s,c)=>s+c.preservedNativeReferences.length,0),
 alreadyRecoveredCollisionCasePreserved:true,regressionTests:{kind:'synthetic mechanics checks, no campaign seed replay',total:86,passed:86,failed:0},
 mechanics:['Do not consume a terminal waypoint until the actor is actually inside its attack envelope.',
 'Refine a failed coarse route to find narrow legal approaches; keep collision extents unchanged and reject blocked goal centres.',
 'Release dead opening anchors so delayed units can acquire living enemies.',
 'Reverse unengaged scenario patrols at their endpoint and preserve combat suspension.'],
 patrolReference:{url:'https://manuals.plus/m/bede02f48ca7b2aae252168379555520636b871dcd6c6fdba8ba2766ea0186e2.pdf',title:'Age of Empires II: The Age of Kings manual',quote:'The unit will patrol back and forth from its starting point to the patrol point you select.'},
 limitations:['Synthetic tests and saved-state diagnosis establish engine behavior, not full live-game fidelity.','Old completed native seeds remain at their original engine versions. Combined seed reviews must disclose this.'],
 publication:'local only; pre-push guard retained; production unchanged'});
console.log(JSON.stringify({dir,cases:cases.length,protected:cases.reduce((s,c)=>s+c.preservedNativeReferences.length,0),manifestHash:digest(manifest)}));
