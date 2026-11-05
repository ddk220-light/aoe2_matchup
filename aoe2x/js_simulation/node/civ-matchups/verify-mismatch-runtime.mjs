#!/usr/bin/env node
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {RankingWorkerPool} from '../ranking-worker-pool.mjs';
import {DIR,gzlines,verifyManifest,payload,exact,json,now} from './mismatch-validation-lib.mjs';
const manifest=verifyManifest(),jobs=new Map(gzlines(resolve(DIR,'jobs.jsonl.gz')).map(j=>[j.id,j]));
const controls=gzlines(resolve(DIR,'expected-native-records.jsonl.gz')).flatMap(x=>x.records.map(row=>({job:jobs.get(x.jobId),row})));
const selected=[];
for(const family of ['waves','kite','rvr','siege']){
 const c=controls.filter(c=>c.job.engineFamily===family).sort((a,b)=>a.row.wallSeconds-b.row.wallSeconds)[0];
 assert(c,family);selected.push(c);
}
for(const c of controls.filter(c=>c.job.categories.includes('opposite_winner')).sort((a,b)=>a.row.wallSeconds-b.row.wallSeconds)){
 if(selected.some(x=>x.job.id===c.job.id))continue;selected.push(c);if(selected.length===8)break;
}
const original=new RankingWorkerPool(1,{workerUrl:pathToFileURL('/workspace/aoe2_path_recovery/aoe2x/js_simulation/node/collision-validation-worker.mjs'),maxTicks:Number.MAX_SAFE_INTEGER});
const streamed=new RankingWorkerPool(1,{workerUrl:new URL('../mismatch-validation-worker.mjs',import.meta.url),maxTicks:Number.MAX_SAFE_INTEGER});
const rows=[];
try{
 for(const {job,row}of selected){
  const p=payload(job,row.seed),[a,b]=await Promise.all([original.run(p,180),streamed.run(p,180)]);
  assert(a.result,JSON.stringify(a));assert(b.result,JSON.stringify(b));
  assert(exact(a.result,row),'original control differs from frozen measurement');
  assert(exact(b.result,row),'event streaming changed the fight');
  rows.push({jobId:job.id,seed:row.seed,engineFamily:job.engineFamily,sourceFile:row.sourceFile,sourceLine:row.sourceLine,
   ticks:row.ticks,winnerOwner:row.winnerOwner,finalStateHash:row.finalStateHash,eventLogHash:row.eventLogHash,
   originalMatchesSaved:true,streamMatchesOriginal:true});
  console.log(JSON.stringify(rows.at(-1)));
 }
 const certificate={campaignHash:manifest.campaignHash,reviewedAt:now(),passed:true,physicsUnchanged:true,
  nativeCampaignHash:manifest.nativeCampaignHash,changedOutputFiles:manifest.changedOutputFiles,
  tests:'reviews/stream-tests.tap',exactControls:rows,
  qualification:'Only lossless canonical event serialization/storage differs. Combat, collision, pathing, scenarios, seeds, team orientation and arithmetic remain frozen V3.'};
 json(resolve(DIR,'reviews/runtime-parity.json'),certificate);
}finally{await original.close();await streamed.close();}
