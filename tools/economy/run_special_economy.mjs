// Derived scenarios: retain the reviewed layouts and change only supported mechanics.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {simulateFarms} from './farm-gathering-sim.mjs';
import {simulateWood,woodWindow} from './wood-gathering-sim.mjs';
import {simulate,windowSummary} from './gold-mining-sim.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const out=process.env.ARMY_CONTEXT_OUT??path.join(here,'../../data/army_economics/sources/army-context-2026-11-10');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const fileHash=name=>hash(fs.readFileSync(name));
const inputs=path.join(out,'eco-inputs.json'), evidencePath=path.join(out,'online-mechanic-evidence.json');
const evidence=JSON.parse(fs.readFileSync(evidencePath));
const specs=JSON.parse(fs.readFileSync(inputs));
const result={sourceHashes:{inputs:fileHash(inputs),evidence:fileHash(evidencePath),runner:fileHash(fileURLToPath(import.meta.url)),
  ...Object.fromEntries(['farm-gathering-sim.mjs','wood-gathering-sim.mjs','gold-mining-sim.mjs'].map(n=>[n,fileHash(path.join(here,n))]))},rows:[]};
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
for(const civ of ['Burgundians','Vietnamese','Georgians']){
 const spec=specs.find(s=>s.civ_name===civ);
 const resources=civ==='Georgians'?['food','wood','gold','stone']:[civ==='Burgundians'?'food':'wood'];
 for(const resource of resources){
  const {engine,fixture}=structuredClone(spec.jobs[resource]);
  const aura=civ==='Georgians';
  if(aura){
   fixture.worker.work_rate*=evidence.interpretation.Georgians.workRateMultiplier;
   // Work-rate affects rebuilding too, under the user's full worker coverage assumption.
   if(engine==='farm')fixture.farm.build_seconds/=evidence.interpretation.Georgians.workRateMultiplier;
  }
  const runs=[];
  for(let seed=0;seed<3;seed++){
   let run,rate,activeFraction;
   if(engine==='farm'){
    run=simulateFarms(fixture,{duration:1800,seed,reseed:true});
    const total=1800*run.final.agents.length;
    rate=run.final.harvested/total;
    activeFraction=run.final.agents.reduce((s,a)=>s+a.working,0)/total;
   }else if(engine==='wood'){
    run=simulateWood(fixture,{duration:600,seed});
    const w=woodWindow(run,60,600);
    rate=(run.final.extracted-run.snapshots.find(s=>Math.abs(s.t-60)<1e-6).extracted)/540/run.final.agents.length;
    activeFraction=w.working_percent/100;
   }else{
    run=simulate(fixture,{duration:240,seed});
    const w=windowSummary(run,60,240);
    rate=w.extracted_per_worker_minute/60;activeFraction=w.working_percent/100;
   }
   if(!(activeFraction>=0&&activeFraction<=1))throw Error('Invalid active fraction');
   runs.push({seed,rate,activeFraction,checks:run.checks});
  }
  result.rows.push({civ,resource,engine,fixture,scenarioSignature:hash(JSON.stringify({engine,fixture,sourceHashes:result.sourceHashes})),
   status:'scenario_estimate',rate:mean(runs.map(r=>r.rate)),activeFraction:mean(runs.map(r=>r.activeFraction)),runs,
   auraApplied:aura,auraBuildingCostIncluded:false,validation:'Controlled game observations still required'});
  console.log(civ,resource,JSON.stringify({rate:result.rows.at(-1).rate,activeFraction:result.rows.at(-1).activeFraction}));
 }
}
// Poles Folwark (owner decision 2026-11-12): the reviewed 0-1800 s farm window credits each covered
// farm's instant 10% twice (at t=0 and at its single reseed). Measure a steady-state window instead,
// so the instant food is credited once per farm cycle. Folwark stays 10% (DAT), 8 of 10 farms
// covered, taken out of the farm; the fixture is unchanged, only the window differs.
const STEADY={start:1800,end:9000};
for(const civ of ['Poles']){
 const {engine,fixture}=structuredClone(specs.find(s=>s.civ_name===civ).jobs.food);
 if(engine!=='farm')throw Error(`${civ} food is not a farm scenario`);
 const runs=[];
 for(let seed=0;seed<3;seed++){
  const run=simulateFarms(fixture,{duration:STEADY.end,seed,reseed:true});
  const at=t=>run.snapshots.find(x=>Math.abs(x.t-t)<1e-6);
  const workers=run.final.agents.length,span=STEADY.end-STEADY.start;
  const harvested=at(STEADY.end).harvested-at(STEADY.start).harvested;
  const working=run.final.agents.reduce((s,a)=>s+a.working,0);
  runs.push({seed,rate:harvested/span/workers,windowRate0to1800:at(1800).harvested/1800/workers,
   reseeds:run.final.farms.map(f=>f.reseeds),activeFraction:working/(STEADY.end*workers),checks:run.checks});
 }
 result.rows.push({civ,resource:'food',engine,purpose:'steady_state_window',window:STEADY,fixture,
  scenarioSignature:hash(JSON.stringify({engine,fixture,window:STEADY,sourceHashes:result.sourceHashes})),
  status:'scenario_estimate',rate:mean(runs.map(r=>r.rate)),activeFraction:mean(runs.map(r=>r.activeFraction)),runs,
  auraApplied:false,auraBuildingCostIncluded:false,validation:'Controlled game observations still required'});
 console.log(civ,'food steady state',JSON.stringify({rate:result.rows.at(-1).rate*60,window0to1800:mean(runs.map(r=>r.windowRate0to1800))*60}));
}
fs.writeFileSync(path.join(out,'special-gather-rates.json'),JSON.stringify(result,null,2)+'\n');
