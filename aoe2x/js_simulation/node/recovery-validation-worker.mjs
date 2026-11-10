import { parentPort, workerData } from 'node:worker_threads';
import {openSync,appendFileSync,fsyncSync,closeSync} from 'node:fs';
import { registerHooks } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

// Recovery diagnostics only; the versioned engine is imported without behavioral hooks.
registerHooks({
  load(url, context, nextLoad) {
    const result = nextLoad(url, context);
    if (url.endsWith('/src/fight.js')) {
      const source = String(result.source);
      const target = 'maxTicks: MAX_TICKS,';
      if (source.split(target).length !== 2) throw new Error('fight stop hook changed');
      return { ...result, source: source.replace(target,
        'maxTicks: globalThis.__collisionValidationMaxTicks ?? MAX_TICKS,') };
    }
    if (url.endsWith('/src/combat/world.js')) {
      let source = String(result.source);
      const target = '  const publish = (current) => {';
      if (source.split(target).length !== 2) throw new Error('world progress hook changed');
      source = source.replace('const MAX_WORLD_TICKS = 9000;', 'const MAX_WORLD_TICKS = Number.MAX_SAFE_INTEGER;')
        .replace(target, target + '\n    globalThis.__collisionValidationProgress?.(current);');
      return { ...result, source };
    }
    return result;
  },
});
const { runHeadlessJob } = await import(workerData?.runtimeRoot
  ? pathToFileURL(resolve(workerData.runtimeRoot, 'aoe2x/js_simulation/node/run-job.mjs')).href
  : './run-job.mjs');
parentPort.on('message', async ({ id, job, maxTicks }) => {
  let last = -Infinity, lastWritten = -Infinity;
  const fd=job.diagnosticProgressPath ? openSync(job.diagnosticProgressPath,'wx') : null;
  const eventCounts={};
  globalThis.__collisionValidationMaxTicks = maxTicks ?? 9000;
  globalThis.__collisionValidationProgress = current => {
    const tick=current.tick;
    if(fd!==null){
      for(const e of current.events)eventCounts[e.type]=(eventCounts[e.type]??0)+1;
      if(performance.now()-lastWritten>=30000){
        lastWritten=performance.now();
        const alive=current.units.filter(u=>u.alive),byOwner={};
        for(const u of alive){byOwner[u.owner]??={units:0,hp:0};byOwner[u.owner].units++;byOwner[u.owner].hp+=u.hp;}
        appendFileSync(fd,JSON.stringify({at:new Date().toISOString(),diagnosticOnly:true,tick,simulationSeconds:tick/60,
          memoryUsage:process.memoryUsage(),byOwner,eventCounts,
          positions:alive.map(u=>({id:u.referenceId,owner:u.owner,hp:u.hp,x:u.x,y:u.y,action:u.action,
            pursuitTargetId:u.pursuitTargetId,engagedTargetId:u.engagedTargetId,attackTargetId:u.attackTargetId,
            moveOrder:u.moveOrder,openingAcquisitionComplete:u.openingAcquisitionComplete,
            actionTimers:u.actionTimers,avoidance:u.avoidance})),
          pursuitRecoveryState:current.pursuitRecoveryState,
          patrolOpeningTargetByOwner:current.patrolOpeningTargetByOwner,
          contactReservationState:current.contactReservationState},
          (_key,value)=>value instanceof Map ? {mapEntries:[...value]} : value instanceof Set ? {setValues:[...value]} : value)+'\n');
        fsyncSync(fd);
      }
    }
    if (performance.now() - last >= 1000) {
      last = performance.now(); parentPort.postMessage({ id, progress: { tick, simulationSeconds: tick / 60 } });
    }
  };
  try { parentPort.postMessage({ id, result: await runHeadlessJob(job) }); }
  catch (error) { parentPort.postMessage({ id, error: { name: error.name, message: error.message, stack: error.stack } }); }
  finally {if(fd!==null)closeSync(fd);}
});
