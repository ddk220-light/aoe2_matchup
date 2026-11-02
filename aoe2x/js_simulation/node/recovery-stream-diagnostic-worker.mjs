// Read-only snapshots persisted during execution, including before a watchdog.
import {parentPort} from 'node:worker_threads';
import {registerHooks} from 'node:module';
import {openSync,appendFileSync,fsyncSync,closeSync} from 'node:fs';

registerHooks({load(url,context,nextLoad){
  const result=nextLoad(url,context);
  if(url.endsWith('/src/fight.js')){
    const source=String(result.source),target='maxTicks: MAX_TICKS,';
    if(source.split(target).length!==2)throw new Error('fight duration hook changed');
    return {...result,source:source.replace(target,'maxTicks: globalThis.__recoveryDiagnosticMaxTicks ?? MAX_TICKS,')};
  }
  if(url.endsWith('/src/combat/world.js')){
    const source=String(result.source),target='  const publish = (current) => {';
    if(source.split(target).length!==2)throw new Error('world observation hook changed');
    return {...result,source:source.replace('const MAX_WORLD_TICKS = 9000;','const MAX_WORLD_TICKS = Number.MAX_SAFE_INTEGER;')
      .replace(target,target+'\n    globalThis.__recoveryDiagnosticSnapshot?.(current);')};
  }
  return result;
}});
const {runHeadlessJob}=await import('./run-job.mjs');
const {collisionRadius,outlineRadius,isWithinReach}=await import('../src/combat/targeting.js');
const chasePath=await import('../src/combat/chase-path.js');
parentPort.on('message',async({id,job,maxTicks})=>{
  const fd=openSync(job.diagnostic.timelinePath,'wx'),eventCounts={};
  const start=performance.now();let samples=0;
  globalThis.__recoveryDiagnosticMaxTicks=maxTicks;
  globalThis.__recoveryDiagnosticSnapshot=current=>{
    for(const e of current.events??[])eventCounts[e.type]=(eventCounts[e.type]??0)+1;
    if(current.tick%job.diagnostic.sampleTicks!==0)return;
    const live=current.units.filter(u=>u.alive),byId=new Map(live.map(u=>[u.referenceId,u])),byOwner={};
    const positions=live.map(u=>{
      byOwner[u.owner]??={units:0,hp:0};byOwner[u.owner].units++;byOwner[u.owner].hp+=u.hp;
      const targets=[...new Set([u.pursuitTargetId,u.engagedTargetId,u.attackTargetId])].map(i=>byId.get(i)).filter(Boolean);
      return {id:u.referenceId,owner:u.owner,hp:u.hp,x:u.x,y:u.y,action:u.action,
        actionTimers:u.actionTimers,pursuitTargetId:u.pursuitTargetId,engagedTargetId:u.engagedTargetId,
        attackTargetId:u.attackTargetId,moveOrder:u.moveOrder,avoidance:u.avoidance,
        radius:collisionRadius(u),outlineRadius:outlineRadius(u),range:u.mechanics.attack_range_tiles,
        minimumRange:u.mechanics.ranged?.min_range_tiles??0,
        targetGeometry:targets.map(t=>({id:t.referenceId,centerDistance:Math.hypot(t.x-u.x,t.y-u.y),
          physicalChebyshevGap:Math.max(Math.abs(t.x-u.x),Math.abs(t.y-u.y))-collisionRadius(u)-collisionRadius(t),
          outlineChebyshevGap:Math.max(Math.abs(t.x-u.x),Math.abs(t.y-u.y))-outlineRadius(u)-outlineRadius(t),
          withinAttackReach:isWithinReach(u,t)})),
        recoveryRoute:current.pursuitRecoveryState?.routes?.get(u.referenceId),
        recoveryAttempt:current.pursuitRecoveryState?.attempts?.get(u.referenceId),
        recoveryFailures:current.pursuitRecoveryState?.routeFailures?.get(u.referenceId)};
    });
    appendFileSync(fd,JSON.stringify({tick:current.tick,seconds:current.tick/60,
      wallSeconds:(performance.now()-start)/1000,byOwner,positions,eventCounts:{...eventCounts},
      cacheStatistics:chasePath.persistentNoRouteCacheStats?.()??null})+'\n');
    fsyncSync(fd);samples++;
    parentPort.postMessage({id,progress:{tick:current.tick,simulationSeconds:current.tick/60,samples}});
  };
  try{parentPort.postMessage({id,result:await runHeadlessJob(job),diagnostic:{samples,eventCounts}});}
  catch(e){parentPort.postMessage({id,error:{name:e.name,message:e.message,stack:e.stack},diagnostic:{samples,eventCounts}});}
  finally{closeSync(fd);}
});
