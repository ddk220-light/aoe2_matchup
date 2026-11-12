import {distance,pointRectDistance,legalSegment,route} from './gold-mining-sim.mjs';
const EPS=1e-8,sum=a=>a.reduce((s,x)=>s+x,0);
const point=(x,y)=>({x,y});
function rect(x,y,hx,hy,id){return {id,x0:x-hx,x1:x+hx,y0:y-hy,y1:y+hy};}
function contacts(r,radius){return [point((r.x0+r.x1)/2,r.y0-radius),point((r.x0+r.x1)/2,r.y1+radius),point(r.x0-radius,(r.y0+r.y1)/2),point(r.x1+radius,(r.y0+r.y1)/2)];}
function clear(p,rects,others,r){return rects.every(o=>pointRectDistance(p,o)>=r-EPS)&&others.every(o=>distance(p,o)>=2*r-EPS);}

export function simulateWood(fixture,options={}){
 const {workers=10,dt=.0125,duration=720,collisions=true,trace=false,seed=0,gap=fixture.camp.gap,
  preFelled=false,treeWood=fixture.tree.wood,attackPeriod=fixture.worker.attack_period,
  firstHitDelay=fixture.worker.first_hit_delay,damage=fixture.worker.damage_per_swing}=options;
 const forest=fixture.forest,radius=fixture.worker.radius,front=forest.y+forest.depth;
 const trees=[];
 for(let y=0;y<forest.depth;y++)for(let x=0;x<forest.width;x++)trees.push({
  ...rect(forest.x+x+.5,forest.y+y+.5,fixture.tree.half_width,fixture.tree.half_height,trees.length),
  remaining:treeWood,hp:preFelled?0:fixture.tree.hit_points});
 const camp=rect(fixture.camp.center[0],front+gap+fixture.camp.half_height,fixture.camp.half_width,fixture.camp.half_height,'camp');
 const starts=[];
 const initialRects=[...trees,camp];
 for(let id=0;id<workers;id++){
  const p=point(fixture.camp.center[0]+(id-(workers-1)/2)*.6,front+radius);
  if(clear(p,initialRects,starts,radius))starts.push(p);
 }
 const extra=[];
 for(let x=forest.x+.05;x<forest.x+forest.width;x+=.1)extra.push(point(x,front+radius));
 extra.sort((a,b)=>pointRectDistance(a,camp)-pointRectDistance(b,camp));
 for(const p of extra){if(starts.length>=workers)break;if(clear(p,initialRects,starts,radius))starts.push(p);}
 if(starts.length<workers)throw new Error('Not enough initial front-edge room');
 const bodies=starts.slice(0,workers).map((p,id)=>({id,...p,radius,
  state:'to_tree',target:null,path:null,retry:0,hitAt:null,inventory:0,banked:0,extracted:0,deposits:0,distance:0,
  working:0,felling:0,walking:0,blocked:0,idle:0,swings:0}));
 let rects=[],accessible=[];
 function refresh(){
  rects=[...trees.filter(t=>t.remaining>EPS),camp];
  accessible=trees.filter(t=>t.remaining>EPS&&contacts(t,radius).some(p=>clear(p,rects,[],radius)));
 }
 refresh();
 for(const b of bodies)if(!clear(b,rects,collisions?bodies.filter(o=>o!==b):[],radius))throw new Error('Initial wood scenario overlap');
 const frames=[],snapshots=[],events=[];
 let maxOverlap=0,maxStaticOverlap=0,maxSpeedError=0,nextFrame=0,nextSnapshot=0;
 const view=t=>({t,banked:sum(bodies.map(b=>b.banked)),carried:sum(bodies.map(b=>b.inventory)),
  extracted:sum(bodies.map(b=>b.extracted)),depleted:trees.filter(t=>t.remaining<EPS).length,felled:trees.filter(t=>t.hp<=0).length,
  remaining:trees.map(t=>t.remaining),tree_hp:trees.map(t=>t.hp),
  agents:bodies.map(b=>Object.fromEntries(['id','x','y','state','target','inventory','banked','working','felling','walking','blocked','idle','distance','deposits','swings'].map(k=>[k,b[k]])))});
 function state(b,s){b.state=s;b.path=null;b.retry=0;b.hitAt=null;}
 function choose(b,others,exclude=null){
  const candidates=accessible.filter(t=>t.id!==exclude).sort((a,z)=>pointRectDistance(b,a)-pointRectDistance(b,z)||((a.id+seed)%trees.length)-((z.id+seed)%trees.length));
  for(const target of candidates){const p=route(b,target,rects,others,radius);if(p){b.target=target.id;b.path=p;return true;}}
  return false;
 }
 function process(b,t,delta){
  let left=delta,guard=0;
  while(left>EPS&&guard++<24){
   const now=t+delta-left;
   if(b.state==='idle'){b.idle+=left;left=0;break;}
   const others=collisions?bodies.filter(o=>o!==b):[];
   if(b.state==='felling'){
    const target=trees[b.target];
    if(target.hp<=0){state(b,'gathering');continue;}
    if(b.hitAt===null)b.hitAt=now+firstHitDelay;
    const wait=Math.min(left,Math.max(0,b.hitAt-now));b.felling+=wait;left-=wait;
    if(t+delta-left+EPS>=b.hitAt){
     target.hp=Math.max(0,target.hp-damage);b.swings++;
     if(trace)events.push({type:'swing',t:t+delta-left,worker:b.id,tree:target.id,hp:target.hp});
     if(target.hp<=0)state(b,'gathering');else b.hitAt+=attackPeriod;
    }
    continue;
   }
   if(b.state==='gathering'){
    const target=trees[b.target];
    if(target.remaining<EPS){state(b,'to_tree');continue;}
    const amount=Math.min(fixture.worker.work_rate*left,fixture.worker.carry_capacity-b.inventory,target.remaining);
    const time=amount/fixture.worker.work_rate;b.working+=time;b.extracted+=amount;b.inventory+=amount;target.remaining-=amount;left-=time;
    if(target.remaining<EPS){target.remaining=0;refresh();if(trace)events.push({type:'depleted',t:t+delta-left,tree:target.id});}
    if(b.inventory>=fixture.worker.carry_capacity-EPS)state(b,'to_camp');
    else if(target.remaining<EPS)state(b,'to_tree');
    continue;
   }
   if(b.state==='to_tree'&&(b.target===null||trees[b.target].remaining<EPS)){
    if(!accessible.length){state(b,b.inventory>EPS?'to_camp':'idle');continue;}
    if(!choose(b,others)){b.blocked+=left;left=0;break;}
   }
   const target=b.state==='to_camp'?camp:trees[b.target];
   if(pointRectDistance(b,target)<=radius+EPS*8){
    if(b.state==='to_camp'){
     b.banked+=b.inventory;b.deposits++;
     if(trace)events.push({type:'deposit',t:now,worker:b.id,wood:b.inventory});
     b.inventory=0;state(b,'to_tree');
    }else state(b,target.hp>0?'felling':'gathering');
    continue;
   }
   if(b.retry>EPS){const wait=Math.min(b.retry,left);b.retry-=wait;b.blocked+=wait;left-=wait;continue;}
   if(!b.path?.length){
    b.path=route(b,target,rects,others,radius);
    if(!b.path){
     if(b.state==='to_tree'&&choose(b,others,target.id))continue;
     b.retry=.5;continue;
    }
   }
   const goal=b.path[0],d=distance(b,goal);
   if(d<EPS*8){b.path.shift();continue;}
   const travel=Math.min(d,fixture.worker.speed*left);
   const dest=point(b.x+(goal.x-b.x)*travel/d,b.y+(goal.y-b.y)*travel/d);
   if(!legalSegment(b,dest,rects,others,radius)){b.path=null;b.retry=.5;continue;}
   b.x=dest.x;b.y=dest.y;b.distance+=travel;const time=travel/fixture.worker.speed;b.walking+=time;left-=time;
   if(travel>=d-EPS)b.path.shift();
  }
  if(left>EPS)b.idle+=left;
 }
 const steps=Math.ceil(duration/dt);
 for(let tick=0;tick<steps;tick++){
  const t=tick*dt,delta=Math.min(dt,duration-t);
  if(t+EPS>=nextSnapshot){snapshots.push(view(t));nextSnapshot+=1;}
  if(trace&&t+EPS>=nextFrame){frames.push(view(t));nextFrame+=.5;}
  const before=bodies.map(b=>({...b})),start=(Math.floor(t)+seed)%workers;
  for(let j=0;j<workers;j++)process(bodies[(j+start)%workers],t,delta);
  for(const b of bodies){
   maxSpeedError=Math.max(maxSpeedError,distance(b,before[b.id])-fixture.worker.speed*delta);
   for(const r of rects)maxStaticOverlap=Math.max(maxStaticOverlap,radius-pointRectDistance(b,r));
   if(collisions)for(const o of bodies)if(o.id>b.id)maxOverlap=Math.max(maxOverlap,2*radius-distance(b,o));
  }
 }
 const final=view(duration);snapshots.push(final);if(trace)frames.push(final);
 const error=trees.length*treeWood-sum(trees.map(t=>t.remaining))-final.banked-final.carried;
 if(Math.abs(error)>1e-5||maxOverlap>1e-6||maxStaticOverlap>1e-6||maxSpeedError>1e-6)throw new Error(JSON.stringify({error,maxOverlap,maxStaticOverlap,maxSpeedError}));
 return {fixture,options:{workers,dt,duration,collisions,seed,gap,preFelled,treeWood,attackPeriod,firstHitDelay,damage},
  final,snapshots,frames,events,checks:{conservation_error:error,max_overlap:maxOverlap,max_static_overlap:maxStaticOverlap,max_speed_error:maxSpeedError},
  validation_status:'Model estimate; current DE wood gathering and felling timing not validated.'};
}

export function woodWindow(run,a,b){
 const first=run.snapshots.find(s=>Math.abs(s.t-a)<1e-6),last=run.snapshots.find(s=>Math.abs(s.t-b)<1e-6);
 if(!first||!last)throw new Error('Missing window endpoints');
 const banked=last.banked-first.banked,carriedDelta=last.carried-first.carried,extracted=last.extracted-first.extracted,T=b-a,n=run.options.workers;
 const result={start:a,end:b,workers:n,banked,carried_start:first.carried,carried_end:last.carried,extracted,
  banked_per_worker_minute:banked*60/T/n,inventory_adjusted_per_worker_minute:extracted*60/T/n,
  depleted_trees:last.depleted,depleted_in_window:last.depleted-first.depleted,conservation_error:extracted-banked-carriedDelta};
 for(const key of ['working','felling','walking','blocked','idle'])result[key+'_percent']=sum(last.agents.map((w,i)=>w[key]-first.agents[i][key]))/T/n*100;
 result.mean_walk_distance=sum(last.agents.map((w,i)=>w.distance-first.agents[i].distance))/n;
 return result;
}
