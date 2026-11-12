// Experimental farming mechanics; no reference rates or civ-specific tuning.
import {distance, pointRectDistance, legalSegment, route} from './gold-mining-sim.mjs';
const EPS=1e-8, sum=a=>a.reduce((s,x)=>s+x,0);
const point=(x,y)=>({x,y});

// Integrate reserve -> available pool -> farmer exactly between boundaries.
// A full pool pauses growth: ungenerated food is preserved, not discarded.
export function evolveFarm(f, seconds, harvestRate=0, limit=Infinity){
 let left=seconds, harvested=0, elapsed=0, guard=0;
 while(left>EPS && limit-harvested>EPS){
  // A gathering action ends when the resource empties, not at the end of
  // the caller's simulation step. Passive farm time still advances normally.
  if(harvestRate>0 && f.reserve+f.pool<EPS)break;
  if(guard++>12)throw new Error('Farm integration failed to converge');
  let g=f.reserve>EPS?f.generation_rate:0;
  let h=f.pool>EPS?harvestRate:Math.min(harvestRate,g);
  if(f.pool>=f.pool_capacity-EPS)g=Math.min(g,h);
  const net=g-h;
  let dt=left;
  if(g>EPS)dt=Math.min(dt,f.reserve/g);
  if(net>EPS)dt=Math.min(dt,(f.pool_capacity-f.pool)/net);
  if(net<-EPS)dt=Math.min(dt,f.pool/-net);
  if(h>EPS)dt=Math.min(dt,(limit-harvested)/h);
  if(dt<EPS)throw new Error('Zero-duration farm boundary');
  f.reserve=Math.max(0,f.reserve-g*dt);
  f.pool=Math.max(0,Math.min(f.pool_capacity,f.pool+net*dt));
  f.generated+=g*dt;f.harvested+=h*dt;
  harvested+=h*dt;elapsed+=dt;left-=dt;
 }
 return {harvested,elapsed};
}

function pathToPoint(start,goal,rects,discs,r){
 if(!legalSegment(goal,goal,rects,discs,r))return null;
 if(legalSegment(start,goal,rects,discs,r))return [goal];
 const nodes=[{x:start.x,y:start.y},goal];
 for(const box of rects)for(const x of [box.x0-r-1e-6,box.x1+r+1e-6])for(const y of [box.y0-r-1e-6,box.y1+r+1e-6]){
  const p=point(x,y);if(legalSegment(p,p,rects,discs,r))nodes.push(p);
 }
 for(const d of discs)for(let k=0;k<12;k++){
  const rr=(r+d.radius+1e-6)/Math.cos(Math.PI/12),p=point(d.x+rr*Math.cos(k*Math.PI/6),d.y+rr*Math.sin(k*Math.PI/6));
  if(legalSegment(p,p,rects,discs,r))nodes.push(p);
 }
 const costs=nodes.map(()=>Infinity),prev=nodes.map(()=>-1),seen=new Set();costs[0]=0;
 for(let n=0;n<nodes.length;n++){
  let i=-1;for(let j=0;j<nodes.length;j++)if(!seen.has(j)&&(i<0||costs[j]<costs[i]))i=j;
  if(i<0||!Number.isFinite(costs[i]))return null;
  if(i===1){const result=[];while(i>0){result.push(nodes[i]);i=prev[i];}return result.reverse();}
  seen.add(i);
  for(let j=1;j<nodes.length;j++)if(!seen.has(j)&&legalSegment(nodes[i],nodes[j],rects,discs,r)){
   const c=costs[i]+distance(nodes[i],nodes[j]);if(c<costs[j]){costs[j]=c;prev[j]=i;}
  }
 }
 return null;
}
function rng(seed){let x=(seed+1)>>>0;return ()=>{x=(Math.imul(x,1664525)+1013904223)>>>0;return x/4294967296;};}
export function simulateFarms(fixture,options={}){
 const {duration=600,dt=.0125,seed=0,collisions=true,trace=false,reseed=false,
  spotsPerLoad=fixture.behavior.spots_per_load,initialPool=fixture.farm.initial_pool,
  poolCapacity=fixture.farm.pool_capacity,depositSeconds=fixture.behavior.deposit_seconds,
  mill=fixture.mill,farms:layout=fixture.farms}=options;
 const {speed,carry_capacity:carry,work_rate:work,radius}=fixture.worker;
 if(!(duration>0&&dt>0&&speed>0&&carry>0&&work>0&&Number.isInteger(spotsPerLoad)&&spotsPerLoad>0&&poolCapacity>0&&initialPool>=0&&initialPool<=poolCapacity&&initialPool<=fixture.farm.food&&depositSeconds>=0&&layout.length))throw new Error('Invalid farm inputs');
 const overlaps=(a,b)=>Math.min(a.x1,b.x1)-Math.max(a.x0,b.x0)>EPS&&Math.min(a.y1,b.y1)-Math.max(a.y0,b.y0)>EPS;
 for(let i=0;i<layout.length;i++){
  if(overlaps(layout[i],mill)||layout.slice(i+1).some(f=>overlaps(f,layout[i])))throw new Error('Overlapping farm layout');
 }
 const resources=layout.map(f=>({...f,reserve:fixture.farm.food-initialPool,pool:initialPool,pool_capacity:poolCapacity,generation_rate:fixture.farm.generation_rate,
  generated:0,harvested:0,reseeds:0,wood:0,rebuilding:false,last_depleted_at:null}));
 const bodies=resources.map((f,id)=>({id,x:(f.x0+f.x1)/2,y:(f.y0+f.y1)/2,radius,random:rng(seed*997+id*101),
  spots:fixture.behavior.work_spot_offsets.flatMap(x=>fixture.behavior.work_spot_offsets.map(y=>point(f.x0+x,f.y0+y))),
  lastSpot:-1,goal:null,state:'initial_walk',path:null,retry:0,portion:0,portionLimit:carry/spotsPerLoad,
  inventory:0,banked:0,harvested:0,deposits:0,working:0,internal_walking:0,outbound_walking:0,return_walking:0,
  initial_walking:0,blocked:0,depositing:0,building:0,idle:0,distance:0,buildLeft:0,depositLeft:0,afterReturn:'gather'}));
 const frames=[],snapshots=[],events=[];let maxOverlap=0,maxStaticOverlap=0,maxSpeedError=0;
 function chooseSpot(b){
  const candidates=b.spots.map((p,i)=>i).filter(i=>i!==b.lastSpot);
  b.lastSpot=candidates[Math.floor(b.random()*candidates.length)];b.goal=b.spots[b.lastSpot];
 }
 for(const b of bodies)chooseSpot(b);
 function transition(b,state,t){
  if(trace)events.push({t,worker:b.id,event:'state',from:b.state,to:state,x:b.x,y:b.y,inventory:b.inventory,pool:resources[b.id].pool});
  b.state=state;b.path=null;b.retry=0;
 }
 function passive(b,seconds){const f=resources[b.id];if(!f.rebuilding)evolveFarm(f,seconds);}
 function process(b,t,step){
  const f=resources[b.id];let left=step,guard=0;
  const now=()=>t+step-left;
  while(left>EPS){
   if(guard++>30)throw new Error('Farm worker state loop');
   if(b.state==='gather'){
    if(f.reserve+f.pool<EPS){
     if(b.inventory>EPS)transition(b,'outbound',now());
     else if(reseed){f.rebuilding=true;f.wood+=fixture.farm.wood_cost;b.buildLeft=fixture.farm.build_seconds;transition(b,'build',now());}
     else transition(b,'idle',now());
     continue;
    }
    const desired=Math.min(carry-b.inventory,b.portionLimit-b.portion);
    const e=evolveFarm(f,left,work,desired);b.inventory+=e.harvested;b.harvested+=e.harvested;b.portion+=e.harvested;b.working+=e.elapsed;left-=e.elapsed;
    if(f.reserve+f.pool<EPS){
     f.last_depleted_at=now();
     if(trace)events.push({t:now(),worker:b.id,event:'depleted',harvested:f.harvested,inventory:b.inventory,reseeds:f.reseeds});
     // Resource exhaustion takes priority over both a quarter-load move
     // and a full-load cycle. Never walk to another spot on an empty farm.
     transition(b,'outbound',now());
    }
    else if(b.inventory>=carry-EPS)transition(b,'outbound',now());
    else if(b.portion>=b.portionLimit-EPS){b.portion=0;chooseSpot(b);transition(b,'internal',now());}
    continue;
   }
   if(b.state==='idle'){passive(b,left);b.idle+=left;left=0;continue;}
   if(b.state==='build'){
    const spent=Math.min(left,b.buildLeft);b.buildLeft-=spent;b.building+=spent;left-=spent;
    if(b.buildLeft<EPS){f.reserve=fixture.farm.food-initialPool;f.pool=initialPool;f.reseeds++;f.rebuilding=false;b.portion=0;chooseSpot(b);transition(b,'internal',now());}
    continue;
   }
   if(b.state==='deposit'){
    const spent=Math.min(left,b.depositLeft);passive(b,spent);b.depositLeft-=spent;b.depositing+=spent;left-=spent;
    if(b.depositLeft<EPS){
     if(trace)events.push({t:now(),worker:b.id,event:'deposit',food:b.inventory,x:b.x,y:b.y});
     b.banked+=b.inventory;b.inventory=0;b.portion=0;b.deposits++;
     if(f.reserve+f.pool<EPS){
      if(!reseed){transition(b,'idle',now());continue;}
      b.afterReturn='build';
     }else {b.afterReturn='gather';chooseSpot(b);}
     transition(b,'return',now());
    }
    continue;
   }
   const atGoal=b.state==='outbound'?pointRectDistance(b,mill)<=radius+EPS*8:distance(b,b.goal)<EPS*8;
   if(atGoal){
    if(b.state==='outbound'){b.depositLeft=depositSeconds;transition(b,'deposit',now());}
    else if(b.state==='return'&&b.afterReturn==='build'){
     f.rebuilding=true;f.wood+=fixture.farm.wood_cost;b.buildLeft=fixture.farm.build_seconds;transition(b,'build',now());
    }else transition(b,'gather',now());
    continue;
   }
   if(b.retry>EPS){const spent=Math.min(left,b.retry);passive(b,spent);b.retry-=spent;b.blocked+=spent;left-=spent;continue;}
   const others=collisions?bodies.filter(o=>o!==b):[],rects=[mill];
   if(!b.path?.length)b.path=b.state==='outbound'?route(b,mill,rects,others,radius):pathToPoint(b,b.goal,rects,others,radius);
   if(!b.path?.length){b.retry=fixture.behavior.blocked_retry_seconds;continue;}
   const p=b.path[0],dist=distance(b,p);
   if(dist<EPS){b.path.shift();continue;}
   const travel=Math.min(speed*left,dist),end=point(b.x+(p.x-b.x)*travel/dist,b.y+(p.y-b.y)*travel/dist);
   if(!legalSegment(b,end,rects,others,radius)){b.path=null;b.retry=fixture.behavior.blocked_retry_seconds;continue;}
   const spent=travel/speed;passive(b,spent);b.x=end.x;b.y=end.y;b.distance+=travel;
   b[({outbound:'outbound_walking',return:'return_walking',internal:'internal_walking',initial_walk:'initial_walking'})[b.state]]+=spent;
   left-=spent;if(travel>=dist-EPS)b.path.shift();
  }
 }
 const keys=['id','x','y','state','inventory','banked','harvested','deposits','working','internal_walking','outbound_walking','return_walking','initial_walking','blocked','depositing','building','idle','distance'];
 const view=t=>({t,banked:sum(bodies.map(b=>b.banked)),carried:sum(bodies.map(b=>b.inventory)),harvested:sum(bodies.map(b=>b.harvested)),wood:sum(resources.map(f=>f.wood)),
  agents:bodies.map(b=>Object.fromEntries(keys.map(k=>[k,b[k]]))),farms:resources.map(f=>({id:f.id,reserve:f.reserve,pool:f.pool,generated:f.generated,harvested:f.harvested,reseeds:f.reseeds,rebuilding:f.rebuilding,last_depleted_at:f.last_depleted_at}))});
 let nextSnapshot=0,nextFrame=0;
 for(let tick=0;tick*dt<duration-EPS;tick++){
  const t=tick*dt,step=Math.min(dt,duration-t);
  if(t>=nextSnapshot-EPS){snapshots.push(view(t));nextSnapshot+=1;}
  if(trace&&t>=nextFrame-EPS){frames.push(view(t));nextFrame+=.5;}
  const before=bodies.map(b=>point(b.x,b.y)),start=(Math.floor(t)+seed)%bodies.length;
  for(let i=0;i<bodies.length;i++)process(bodies[(i+start)%bodies.length],t,step);
  for(const b of bodies){
   maxSpeedError=Math.max(maxSpeedError,distance(b,before[b.id])-speed*step);
   maxStaticOverlap=Math.max(maxStaticOverlap,radius-pointRectDistance(b,mill));
   if(collisions)for(const o of bodies)if(o.id>b.id)maxOverlap=Math.max(maxOverlap,2*radius-distance(b,o));
  }
 }
 const final=view(duration);snapshots.push(final);if(trace)frames.push(final);
 const inventoryError=final.harvested-final.banked-final.carried;
 const resourceError=sum(resources.map(f=>fixture.farm.food*(1+f.reseeds)-f.reserve-f.pool-f.harvested));
 const timeKeys=['working','internal_walking','outbound_walking','return_walking','initial_walking','blocked','depositing','building','idle'];
 const timeError=Math.max(...bodies.map(b=>Math.abs(duration-sum(timeKeys.map(k=>b[k])))));
 if(Math.max(Math.abs(inventoryError),Math.abs(resourceError),timeError,maxOverlap,maxStaticOverlap,maxSpeedError)>1e-5)throw new Error(JSON.stringify({inventoryError,resourceError,timeError,maxOverlap,maxStaticOverlap,maxSpeedError}));
 return {fixture,options:{duration,dt,seed,collisions,reseed,spotsPerLoad,initialPool,poolCapacity,depositSeconds,workers:bodies.length,mill,farms:layout},final,snapshots,frames,events,
  checks:{inventory_error:inventoryError,resource_error:resourceError,time_error:timeError,max_overlap:maxOverlap,max_static_overlap:maxStaticOverlap,max_speed_error:maxSpeedError},
  status:'Experimental generic mechanics; current DE movement policy not validated'};
}
export function farmWindow(run,start,end){
 const a=run.snapshots.find(s=>Math.abs(s.t-start)<1e-6),b=run.snapshots.find(s=>Math.abs(s.t-end)<1e-6);
 if(!a||!b)throw new Error(`Missing farm window ${start}..${end}`);
 const perFarm=b.agents.map((w,i)=>{
  const old=a.agents[i],out={id:i,position:run.options.farms[i].position,banked:w.banked-old.banked,carried_start:old.inventory,carried_end:w.inventory};
  out.harvested=w.harvested-old.harvested;out.food_per_minute=out.harvested*60/(end-start);out.banked_per_minute=out.banked*60/(end-start);
  for(const k of ['working','internal_walking','outbound_walking','return_walking','initial_walking','blocked','depositing','building','idle','distance','deposits'])out[k]=w[k]-old[k];
  return out;
 });
 return {start,end,banked:b.banked-a.banked,carried_start:a.carried,carried_end:b.carried,harvested:b.harvested-a.harvested,
  food_per_worker_minute:(b.harvested-a.harvested)*60/(end-start)/perFarm.length,
  banked_per_worker_minute:(b.banked-a.banked)*60/(end-start)/perFarm.length,wood:b.wood-a.wood,per_farm:perFarm};
}
