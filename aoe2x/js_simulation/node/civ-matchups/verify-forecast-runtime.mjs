#!/usr/bin/env node
// Fast exact controls verify unchanged combat, hashing and physical orientation.
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {SIM,ROOT,DIR,gzlines,verifyManifest,payload,exact,json,now,load,sha} from './forecast-validation-lib.mjs';
const manifest=verifyManifest();
const prior=resolve(SIM,'calibration/campaigns/civ-matchups-mismatch-validation-2026-11-05');
const jobs=new Map(gzlines(resolve(prior,'jobs.jsonl.gz')).map(j=>[j.id,j]));
const controls=gzlines(resolve(prior,'expected-native-records.jsonl.gz')).flatMap(x=>x.records.map(row=>({job:jobs.get(x.jobId),row})));
const selected=[];
for(const family of ['waves','kite','rvr','siege']){
  const control=controls.filter(c=>c.job.engineFamily===family).sort((a,b)=>a.row.wallSeconds-b.row.wallSeconds)[0];
  assert(control,family);selected.push(control);
}
for(const control of controls.filter(c=>c.job.categories.includes('opposite_winner')).sort((a,b)=>a.row.wallSeconds-b.row.wallSeconds)){
  if(selected.some(x=>x.job.id===control.job.id))continue;
  selected.push(control);if(selected.length===8)break;
}
const original=new RankingWorkerPool(1,{workerUrl:pathToFileURL('/workspace/aoe2_path_recovery/aoe2x/js_simulation/node/collision-validation-worker.mjs'),maxTicks:Number.MAX_SAFE_INTEGER});
const streamed=new RankingWorkerPool(1,{workerUrl:new URL('../mismatch-validation-worker.mjs',import.meta.url),maxTicks:Number.MAX_SAFE_INTEGER});
const rows=[];
try{
  for(const {job,row} of selected){
    const p=payload(job,row.seed),[a,b]=await Promise.all([original.run(p,180),streamed.run(p,180)]);
    assert(a.result,JSON.stringify(a));assert(b.result,JSON.stringify(b));
    assert(exact(a.result,row),'original control differs from saved native result');
    assert(exact(b.result,row),'unchanged streamed runtime differs from saved native result');
    rows.push({sourceJobId:job.id,seed:row.seed,engineFamily:job.engineFamily,sourceFile:row.sourceFile,sourceLine:row.sourceLine,
      ticks:row.ticks,winnerOwner:row.winnerOwner,finalStateHash:row.finalStateHash,eventLogHash:row.eventLogHash,
      originalMatchesSaved:true,streamMatchesOriginal:true});
  }
  json(resolve(DIR,'reviews/runtime-parity.json'),{campaignHash:manifest.campaignHash,reviewedAt:now(),passed:true,
    physicsUnchanged:true,byteIdenticalRuntime:true,sourceCampaignHash:manifest.runtimeSource.campaignHash,
    nativeCampaignHash:manifest.nativeCampaignHash,exactControls:rows,
    qualification:'Parity controls only, not forecast measurements. The 62 combat runtime files and memory-safe worker are unchanged; no outcome, seed, count or context is imported into forecast runs.'});
  console.log(JSON.stringify({passed:true,exactControls:rows.length,campaignHash:manifest.campaignHash}));
}finally{await original.close();await streamed.close();}
