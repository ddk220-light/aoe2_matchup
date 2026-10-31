import {parentPort} from 'node:worker_threads';
import {registerHooks} from 'node:module';

// The hooks change only the duration guard and expose read-only progress.
registerHooks({load(url,context,nextLoad){
  const result=nextLoad(url,context);
  if(url.endsWith('/src/fight.js')){
    const target='maxTicks: MAX_TICKS,';
    const source=String(result.source);
    if(source.split(target).length!==2)throw new Error('fight stop hook changed');
    return {...result,source:source.replace(target,
      'maxTicks: globalThis.__slowFightMaxTicks ?? MAX_TICKS,')};
  }
  if(url.endsWith('/src/combat/world.js')){
    let source=String(result.source);
    const target='  const publish = (current) => {';
    if(source.split(target).length!==2)throw new Error('world progress hook changed');
    source=source.replace('const MAX_WORLD_TICKS = 9000;',
      'const MAX_WORLD_TICKS = Number.MAX_SAFE_INTEGER;')
      .replace(target,target+'\n    globalThis.__slowFightProgress?.(current);');
    return {...result,source};
  }
  return result;
}});
const {runHeadlessJob}=await import('./run-job.mjs');
parentPort.on('message',async({id,job,maxTicks})=>{
  const eventCounts={},timeline=[];
  globalThis.__slowFightMaxTicks=maxTicks??Number.MAX_SAFE_INTEGER;
  globalThis.__slowFightProgress=current=>{
    for(const event of current.events??[])eventCounts[event.type]=(eventCounts[event.type]??0)+1;
    if(current.tick%6000!==0)return;
    const byOwner={};
    for(const unit of current.units){
      if(!unit.alive)continue;
      const owner=unit.owner;
      byOwner[owner]??={units:0,hp:0};
      byOwner[owner].units++;
      byOwner[owner].hp+=unit.hp;
    }
    timeline.push({tick:current.tick,seconds:current.tick/60,byOwner});
    parentPort.postMessage({id,progress:{tick:current.tick,simulationSeconds:current.tick/60}});
  };
  try{parentPort.postMessage({id,result:await runHeadlessJob(job),diagnostic:{timeline,eventCounts}});}
  catch(error){parentPort.postMessage({id,error:{name:error.name,message:error.message,stack:error.stack},
    diagnostic:{timeline,eventCounts}});}
});
