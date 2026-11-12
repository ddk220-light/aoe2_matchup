// Isolated source-backed worker model. General geometry/behavior assumptions
// are exported with every run; this module contains no reference-rate targets.
const EPS=1e-8;
export const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
const sum=(a)=>a.reduce((s,x)=>s+x,0);
const point=(x,y)=>({x,y});
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function rect(center,hx,hy,id,amount=null){return {id,x0:center[0]-hx,x1:center[0]+hx,y0:center[1]-hy,y1:center[1]+hy,amount};}
export function pointRectDistance(p,r){return Math.hypot(Math.max(r.x0-p.x,0,p.x-r.x1),Math.max(r.y0-p.y,0,p.y-r.y1));}
function pointSegmentDistance(p,a,b){
  const dx=b.x-a.x,dy=b.y-a.y,d=dx*dx+dy*dy;
  const t=d?clamp(((p.x-a.x)*dx+(p.y-a.y)*dy)/d,0,1):0;
  return Math.hypot(p.x-a.x-t*dx,p.y-a.y-t*dy);
}
// Segment intersection with the open interior of a conservative Minkowski box.
function crossesExpandedRect(a,b,r,pad){
  let lo=0,hi=1;
  for(const [start,delta,min,max] of [[a.x,b.x-a.x,r.x0-pad+EPS,r.x1+pad-EPS],[a.y,b.y-a.y,r.y0-pad+EPS,r.y1+pad-EPS]]){
    if(Math.abs(delta)<EPS){if(start<=min||start>=max)return false;}
    else {const t0=(min-start)/delta,t1=(max-start)/delta;lo=Math.max(lo,Math.min(t0,t1));hi=Math.min(hi,Math.max(t0,t1));if(lo>hi)return false;}
  }
  return hi>=0&&lo<=1;
}
export function legalSegment(a,b,rects,discs,radius){
  return !rects.some(r=>crossesExpandedRect(a,b,r,radius)) &&
    !discs.some(d=>pointSegmentDistance(d,a,b)<radius+d.radius-EPS);
}
function legalPoint(p,rects,discs,radius){
  return !rects.some(r=>pointRectDistance(p,r)<radius-EPS) &&
    !discs.some(d=>distance(p,d)<radius+d.radius-EPS);
}
function contacts(r,radius,step=.1){
  const points=[];
  for(let x=r.x0+.05;x<r.x1;x+=step){points.push(point(x,r.y0-radius),point(x,r.y1+radius));}
  for(let y=r.y0+.05;y<r.y1;y+=step){points.push(point(r.x0-radius,y),point(r.x1+radius,y));}
  return points;
}
function closestContact(p,r,radius){
  return [point(clamp(p.x,r.x0,r.x1),r.y0-radius),point(clamp(p.x,r.x0,r.x1),r.y1+radius),
    point(r.x0-radius,clamp(p.y,r.y0,r.y1)),point(r.x1+radius,clamp(p.y,r.y0,r.y1))];
}
// Visibility path to an unoccupied target contact. Existing mining/wood reviews
// use the visible-contact-first heuristic. compareDetours additionally checks
// whether a detour to a nearer contact beats a farther unobstructed contact.
// Circumscribed polygons supply safe detours; no fixed worker slots.
export function route(start,target,rects,discs,radius,{compareDetours=false}={}){
  const goals=[...closestContact(start,target,radius),...contacts(target,radius)]
    .filter(p=>legalPoint(p,rects,discs,radius));
  if(!goals.length)return null;
  const direct=goals.filter(p=>legalSegment(start,p,rects,discs,radius)).sort((a,b)=>distance(start,a)-distance(start,b));
  // A direct path is proven shortest only when it attains the distance lower
  // bound over ALL candidate goals, including those obscured by a villager.
  if(direct.length&&(!compareDetours||distance(start,direct[0])<=Math.min(...goals.map(p=>distance(start,p)))+EPS))return [direct[0]];
  const nodes=[{...start},...goals];
  for(const r of rects)for(const x of [r.x0-radius-EPS*4,r.x1+radius+EPS*4])for(const y of [r.y0-radius-EPS*4,r.y1+radius+EPS*4]){
    const p=point(x,y);if(legalPoint(p,rects,discs,radius))nodes.push(p);
  }
  const sides=12;
  for(const d of discs){
    const rr=(radius+d.radius+EPS*4)/Math.cos(Math.PI/sides);
    for(let i=0;i<sides;i++){
      const p=point(d.x+rr*Math.cos(2*Math.PI*i/sides),d.y+rr*Math.sin(2*Math.PI*i/sides));
      if(legalPoint(p,rects,discs,radius))nodes.push(p);
    }
  }
  const costs=Array(nodes.length).fill(Infinity),prev=Array(nodes.length).fill(-1),seen=new Set();costs[0]=0;
  for(let count=0;count<nodes.length;count++){
    let i=-1;for(let k=0;k<nodes.length;k++)if(!seen.has(k)&&(i<0||costs[k]<costs[i]))i=k;
    if(i<0||!Number.isFinite(costs[i]))return null;
    if(i>0&&i<=goals.length){const path=[];while(i>0){path.push(nodes[i]);i=prev[i];}return path.reverse();}
    seen.add(i);
    for(let j=1;j<nodes.length;j++)if(!seen.has(j)){
      const candidate=costs[i]+distance(nodes[i],nodes[j]);
      if(candidate<costs[j]&&legalSegment(nodes[i],nodes[j],rects,discs,radius)){costs[j]=candidate;prev[j]=i;}
    }
  }
  return null;
}
function makePositions(fixture,n,gap){
  const mine={x0:10,x1:12,y0:10,y1:12};
  const camp=rect([11,13+gap],1,1,'camp');
  const points=fixture.starting_positions.map(([x,y])=>point(x,y))
    .filter(p=>legalPoint(p,[mine,camp],[],fixture.worker.radius)).slice(0,n);
  for(const offset of [0,.45,.9]){
    for(const p of contacts(mine,fixture.worker.radius+offset,.42)){
      if(points.length>=n)break;
      if(legalPoint(p,[mine,camp],points.map(p=>({...p,radius:fixture.worker.radius})),fixture.worker.radius))points.push(p);
    }
  }
  if(points.length<n)throw new Error('Not enough legal initial positions');return points;
}
export function simulate(fixture,options={}){
  const {workers=10,gap=1,dt=.0125,duration=420,collisions=true,trace=false,seed=0,
    carry=fixture.worker.carry_capacity,workRate=fixture.worker.work_rate}=options;
  if(!(dt>0&&duration>0&&carry>0&&workRate>0))throw new Error('Invalid simulation inputs');
  const mines=fixture.gold.centers.map((c,i)=>rect(c,fixture.gold.half_width,fixture.gold.half_height,i,fixture.gold.amount));
  const camp=rect([fixture.camp.center[0],12+gap+fixture.camp.half_height],fixture.camp.half_width,fixture.camp.half_height,'camp');
  const bodies=makePositions(fixture,workers,gap).map((p,i)=>({...p,id:i,radius:fixture.worker.radius,
    inventory:0,banked:0,extracted:0,distance:0,deposits:0,state:'to_mine',target:null,path:null,retry:0,
    working:0,walking:0,blocked:0,idle:0}));
  // Seed varies only initial stable order/target tie-breaking, not runtime
  // harvest rate or per-scenario movement corrections.
  for(const b of bodies){
    b.target=mines.slice().sort((a,z)=>pointRectDistance(b,a)-pointRectDistance(b,z)||((a.id+seed)%4)-((z.id+seed)%4))[0].id;
    if(!legalPoint(b,[...mines,camp],collisions?bodies.filter(x=>x!==b):[],b.radius))throw new Error('Initial overlap');
  }
  const frames=[],events=[],snapshots=[];let maxOverlap=0,maxStaticOverlap=0,maxSpeedError=0;
  let tick=0;let nextFrame=0,nextSnapshot=0;
  const view=(t)=>({t,banked:sum(bodies.map(b=>b.banked)),carried:sum(bodies.map(b=>b.inventory)),
    extracted:sum(bodies.map(b=>b.extracted)),remaining:mines.map(m=>m.amount),
    agents:bodies.map(b=>Object.fromEntries(['id','x','y','state','target','inventory','banked','working','walking','blocked','idle','distance','deposits'].map(k=>[k,b[k]])))});
  function setState(b,state){b.state=state;b.path=null;b.retry=0;}
  function process(b,t,delta){
    let left=delta,guard=0;
    while(left>EPS&&guard++<16){
      if(b.state==='mining'){
        const m=mines[b.target];
        if(m.amount<EPS){setState(b,b.inventory>EPS?'to_camp':'to_mine');continue;}
        const amount=Math.min(workRate*left,carry-b.inventory,m.amount);
        const spent=amount/workRate;b.inventory+=amount;b.extracted+=amount;m.amount-=amount;b.working+=spent;left-=spent;
        if(b.inventory>=carry-EPS)setState(b,'to_camp');
        else if(m.amount<EPS)setState(b,b.inventory>EPS?'to_camp':'to_mine');
        continue;
      }
      if(b.state==='idle'){b.idle+=left;left=0;break;}
      if(b.state==='to_mine'&&mines[b.target].amount<EPS){
        const available=mines.filter(m=>m.amount>EPS).sort((a,z)=>pointRectDistance(b,a)-pointRectDistance(b,z));
        if(!available.length){setState(b,b.inventory>EPS?'to_camp':'idle');continue;}
        b.target=available[0].id;b.path=null;
      }
      const target=b.state==='to_camp'?camp:mines[b.target];
      if(pointRectDistance(b,target)<=b.radius+EPS*8){
        if(b.state==='to_camp'){
          b.banked+=b.inventory;b.deposits++;
          if(trace)events.push({t:t+delta-left,worker:b.id,gold:b.inventory,banked:b.banked});
          b.inventory=0;setState(b,'to_mine');
        }else setState(b,'mining');
        continue;
      }
      const staticRects=[...mines.filter(m=>m.amount>EPS),camp];
      const others=collisions?bodies.filter(x=>x!==b):[];
      if(b.retry>EPS){const wait=Math.min(left,b.retry);b.retry-=wait;b.blocked+=wait;left-=wait;continue;}
      if(!b.path?.length){
        b.path=route(b,target,staticRects,others,b.radius);
        if(!b.path?.length){b.retry=.5;continue;}
      }
      const goal=b.path[0],dist=distance(b,goal);
      if(dist<EPS*8){b.path.shift();continue;}
      const travel=Math.min(dist,fixture.worker.speed*left),dest=point(b.x+(goal.x-b.x)*travel/dist,b.y+(goal.y-b.y)*travel/dist);
      if(!legalSegment(b,dest,staticRects,others,b.radius)){
        b.path=null;b.retry=.5;continue;
      }
      b.x=dest.x;b.y=dest.y;b.distance+=travel;
      const spent=travel/fixture.worker.speed;b.walking+=spent;left-=spent;
      if(travel>=dist-EPS)b.path.shift();
    }
    if(left>EPS){b.idle+=left;}
  }
  for(let t=0;t<duration-EPS;tick++){
    t=Math.min(duration,tick*dt);
    if(t>=duration-EPS)break;
    if(t>=nextSnapshot-EPS){snapshots.push(view(t));nextSnapshot+=1;}
    if(trace&&t>=nextFrame-EPS){frames.push(view(t));nextFrame+=.2;}
    const step=Math.min(dt,duration-t),start=(Math.floor(t)+seed)%workers;
    const before=bodies.map(b=>({...b}));
    for(let i=0;i<workers;i++)process(bodies[(i+start)%workers],t,step);
    for(const b of bodies){
      maxSpeedError=Math.max(maxSpeedError,distance(b,before[b.id])-fixture.worker.speed*step);
      for(const r of [...mines.filter(m=>m.amount>EPS),camp])maxStaticOverlap=Math.max(maxStaticOverlap,b.radius-pointRectDistance(b,r));
      if(collisions)for(const other of bodies)if(other.id>b.id)maxOverlap=Math.max(maxOverlap,b.radius+other.radius-distance(b,other));
    }
  }
  const final=view(duration);snapshots.push(final);if(trace)frames.push(final);
  const error=fixture.gold.amount*mines.length-sum(mines.map(m=>m.amount))-final.banked-final.carried;
  if(Math.abs(error)>1e-6||maxOverlap>1e-6||maxStaticOverlap>1e-6||maxSpeedError>1e-6)throw new Error(JSON.stringify({error,maxOverlap,maxStaticOverlap,maxSpeedError}));
  return {options:{workers,gap,dt,duration,collisions,seed,carry,workRate},fixture,final,snapshots,frames,events,
    checks:{conservation_error:error,max_overlap:maxOverlap,max_static_overlap:maxStaticOverlap,max_speed_error:maxSpeedError},
    validation_status:'unvalidated_model; external_reference_comparison_only'};
}
export function windowSummary(run,a,b){
  const first=run.snapshots.find(s=>Math.abs(s.t-a)<1e-6),last=run.snapshots.find(s=>Math.abs(s.t-b)<1e-6);
  if(!first||!last)throw new Error(`Missing endpoint ${a},${b}`);
  const n=run.options.workers,T=b-a,banked=last.banked-first.banked,carriedDelta=last.carried-first.carried;
  const extracted=last.extracted-first.extracted;
  const times={};for(const k of ['working','walking','blocked','idle'])times[k]=sum(last.agents.map((w,i)=>w[k]-first.agents[i][k]));
  return {start:a,end:b,workers:n,banked,carried_start:first.carried,carried_end:last.carried,carried_delta:carriedDelta,extracted,
    banked_per_worker_minute:banked*60/T/n,extracted_per_worker_minute:extracted*60/T/n,
    working_percent:times.working/T/n*100,walking_percent:times.walking/T/n*100,blocked_percent:times.blocked/T/n*100,idle_percent:times.idle/T/n*100,
    conservation_error:extracted-banked-carriedDelta,
    depleted_tiles:last.remaining.filter(x=>x<EPS).length,remaining:last.remaining};
}
