import assert from 'node:assert/strict';

// Keep bounded concurrency across audit phase boundaries. Phase reviews still
// require every constituent context; an unfinished job never closes its phase.
export async function runOrderedQueue({jobs,workers,skip=()=>false,shouldStop=()=>false,run,onSettled=()=>{}}){
 assert(Number.isSafeInteger(workers)&&workers>0);
 assert.equal(new Set(jobs.map(j=>j.id)).size,jobs.length,'duplicate queued context');
 let cursor=0;
 await Promise.all(Array.from({length:workers},async()=>{
  while(!shouldStop()&&cursor<jobs.length){
   const job=jobs[cursor++];
   if(skip(job))continue;
   await run(job);await onSettled(job);
  }
 }));
}
