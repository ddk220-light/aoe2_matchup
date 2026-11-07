import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
import test from 'node:test';
import {DIR,ROOT,load,gzlines,verifyManifest,payload,digest,required,canonicalOutcome} from '../node/civ-matchups/forecast-validation-lib.mjs';

test('frozen forecast queue is complete, confidence-ordered and disjoint from held failures',()=>{
  const manifest=verifyManifest(),jobs=gzlines(resolve(DIR,'jobs.jsonl.gz'));
  const all=gzlines(resolve(DIR,'all-forecast-contexts.jsonl.gz')),held=gzlines(resolve(DIR,'held-contexts.jsonl.gz'));
  assert.equal(all.length,39148);assert.equal(jobs.length,39124);assert.equal(held.length,24);
  const heldIds=new Set(held.map(j=>j.id));
  assert.equal(new Set(all.map(j=>j.contextHash)).size,39148);
  assert(jobs.every((j,i)=>!heldIds.has(j.id)&&(!i||jobs[i-1].priority<j.priority||jobs[i-1].priority===j.priority&&jobs[i-1].evidenceIds[0]<j.evidenceIds[0])));
  assert.equal(jobs[0].predictionTier,'predicted_close');
  assert.equal(jobs[1].predictionTier,'opponent_specific_forecast');
  assert.equal(jobs.at(-1).predictionTier,'stronger_support');
  assert.equal(held.filter(j=>j.reason.startsWith('owner_confirmed')).length,5);
  assert.equal(held.filter(j=>j.predictionTier==='repaired_engine_projection').length,19);
  assert.equal(manifest.totalForecastContexts,jobs.length+held.length);
});

test('original forecast values and every physical profile/count order are preserved',()=>{
  const original=new Map(gzlines(resolve(DIR,'original-evidence.jsonl.gz')).map(r=>[r.evidenceId,r.evidence]));
  for(const job of gzlines(resolve(DIR,'jobs.jsonl.gz'))){
    const ev=original.get(job.evidenceIds[0]);
    assert.equal(ev.evidenceType,'predicted_unvalidated');assert.equal(ev.predictionPolicy,'prediction-first-pass-v2');
    assert.deepEqual(ev.context,job.context);assert.equal(digest(job.context),job.contextHash);
    const p=payload(job,2);assert.equal(p.seed,2);assert.deepEqual(p.teams.map(t=>t.count),job.context.counts);
    assert(p.disableAiOrders&&p.disableKiting&&p.preserveOwnerOrientation);
  }
});

test('seed expansion and winner projection retain physical orientation',()=>{
  const job={profileHashes:['z','a'],pairKey:'a|z'};
  assert.deepEqual(required([{seed:0,winnerOwner:2}]),[1,2]);
  const stable=[0,1,2].map(seed=>({seed,winnerOwner:2}));
  assert.equal(canonicalOutcome(job,stable),'b_win');
  assert.deepEqual(required(stable.map((r,i)=>i===2?{...r,winnerOwner:3}:r)),[3,4,5,6,7,8,9]);
  assert.throws(()=>canonicalOutcome(job,stable.slice(0,2)),/incomplete/);
});

test('an unapproved long-running queue refuses to launch without changing state or creating a runner lock',
  {skip:load(resolve(DIR,'launch-approval.json')).durationApproved},()=>{
  const before=readFileSync(resolve(DIR,'state.json'));
  assert(!existsSync(resolve(DIR,'.runner.lock')));
  const result=spawnSync(process.execPath,['aoe2x/js_simulation/node/civ-matchups/run-forecast-validation.mjs'],{cwd:ROOT,encoding:'utf8'});
  assert.notEqual(result.status,0);
  assert.match(result.stderr,/Long-running launch needs the saved duration approval/);
  assert.deepEqual(readFileSync(resolve(DIR,'state.json')),before);
  assert(!existsSync(resolve(DIR,'.runner.lock')));
  assert(!existsSync(resolve(DIR,'runs.jsonl')));
});
