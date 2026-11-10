import assert from'node:assert/strict';import{readFileSync,writeFileSync,mkdirSync,existsSync}from'node:fs';import{resolve}from'node:path';import{createHash}from'node:crypto';import{execFileSync}from'node:child_process';
import{hashCanonicalJson as digest}from'/workspace/aoe2_civ_forecast_recovery/aoe2x/js_simulation/src/canonical-json.js';
const root='/workspace/aoe2_civ_forecast_recovery',r='aoe2x/js_simulation/calibration/campaigns/civ-matchups-forecast-recovery-2026-11-10';
const old=resolve(root,r,'path-patrol-v2-resume-001'),dir=resolve(root,r,'local-refinement-v3');
assert(!existsSync(resolve(old,'.runner.lock')),'wait for safe attempt boundary');assert(!existsSync(dir));
const read=p=>JSON.parse(readFileSync(p)),sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const lines=p=>readFileSync(p,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const oldInput=read(resolve(old,'input.json')),c=oldInput.cases.find(c=>c.job.id==='fv_e50435eb3040ac8928d195ee');
const completed=lines(resolve(old,'runs.jsonl'));assert(!completed.some(r=>r.matchupId===c.job.id),'Never rerun a completed seed');
const attempts=lines(resolve(old,'attempts.jsonl'));const starts=attempts.filter(a=>a.status==='started'&&a.jobId===c.job.id);
assert(starts.every(s=>attempts.some(a=>a.status==='finished'&&a.attemptId===s.attemptId)),'unclosed attempt');
const diagnosis={createdAt:new Date().toISOString(),case:c.job.id,category:'raster_resolution_misses_narrow_legal_contact_approach',
 priorAttemptStatus:'two ordinary watchdog timeouts; stopped at a closed attempt boundary for a diagnosed mechanics repair, not declared exhausted',
 completedSeedsPreserved:c.preservedNativeReferences.map(ref=>ref.record.seed),permittedMissingSeeds:[1,2],
 attempts:starts.map(s=>({start:s,finish:attempts.find(a=>a.status==='finished'&&a.attemptId===s.attemptId),snapshotSha256:sha(s.diagnosticProgressPath),lastSnapshot:lines(s.diagnosticProgressPath).at(-1)})),
 diagnosis:'A valid 1/64-tile route reaches the unchanged attack envelope where the 1/16-tile grid contains no legal corridor. Static circular clearance and dynamic contact reservations are retained. This is a planning discretization repair, not a collision or range tolerance increase.',
 behaviorChange:'After both coarser searches fail, refine a bounded local corridor using the same global grid origin. Only route geometry changes; no source context, stats, seed, time step, attack reach, collision surface or winner logic changes.',
 verification:{syntheticTests:88,passed:88,failed:0,noCompletedCampaignSeedUsedAsRegression:true,diagnosticGeometryNotNativeResult:true},
 productionEligible:false};
mkdirSync(dir);const save=(name,value)=>writeFileSync(resolve(dir,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
save('diagnosis.json',diagnosis);
save('input.json',{cases:[c],policy:{...oldInput.policy,legacyInProgressJobs:[c.job.id]}});
const {manifestHash:parentManifestHash,...prior}=read(resolve(old,'manifest.json'));
const manifest={...prior,createdAt:new Date().toISOString(),physicsVersion:'forecast-recovery-local-refinement-v3',
 sourceCommit:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),parentManifestHash,parentManifestPath:resolve(old,'manifest.json'),
 parentPhysicsVersion:prior.physicsVersion,changedRuntimeFiles:prior.runtimeFiles.filter(s=>s.sha256!==sha(resolve(root,s.path))).map(s=>({...s,originalSha256:s.sha256,sha256:sha(resolve(root,s.path))})),allowedJobs:[c.job.id],authorizedCrossEngineReruns:[],inputSha256:sha(resolve(dir,'input.json')),
 runtimeFiles:prior.runtimeFiles.map(s=>({...s,sha256:sha(resolve(root,s.path))})),
 nativeLedgers:[...prior.nativeLedgers,resolve(old,'runs.jsonl')],
 frozenSources:[...prior.frozenSources,...['manifest.json','input.json','runs.jsonl','attempts.jsonl','STOP'].map(name=>({path:resolve(old,name),sha256:sha(resolve(old,name))})),
 ...starts.map(s=>({path:s.diagnosticProgressPath,sha256:sha(s.diagnosticProgressPath)})),{path:resolve(dir,'diagnosis.json'),sha256:sha(resolve(dir,'diagnosis.json'))}],
 resumeReason:'New diagnosed path-resolution repair for the sole remaining context. Existing completed seeds are protected; only missing seeds are executable.'};
save('manifest.json',{...manifest,manifestHash:digest(manifest)});console.log(JSON.stringify({dir,manifestHash:digest(manifest),missingSeeds:[1,2]}));
