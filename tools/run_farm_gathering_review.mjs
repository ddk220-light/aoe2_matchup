import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {simulateFarms,farmWindow} from './farm-gathering-sim.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const out=path.resolve(process.argv[2]??path.join(root,'aoe2x/js_simulation/calibration/economy/farms-2026-11-09'));
const fixture=n=>JSON.parse(fs.readFileSync(path.join(out,`fixture-${n}.json`)));
const write=(n,v)=>fs.writeFileSync(path.join(out,n),JSON.stringify(v,null,2)+'\n');
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const trials=[];
function trial(name,profile,options,save=false){
 const r=simulateFarms(fixture(profile),options);
 const windows=[[0,60],[120,420],[0,r.options.duration]].filter(([a,b])=>b<=r.options.duration);
 const row={name,profile,options:r.options,checks:r.checks,windows:windows.map(([a,b])=>farmWindow(r,a,b))};trials.push(row);
 if(save)write(name+'.json',{...r,frames:r.frames.map(f=>({t:f.t,banked:f.banked,carried:f.carried,wood:f.wood,agents:f.agents.map(b=>({id:b.id,x:b.x,y:b.y,state:b.state,inventory:b.inventory})),farms:f.farms}))});
 console.log(name,row.windows.at(-1).food_per_worker_minute.toFixed(4));return row;
}
for(const p of ['none','wheelbarrow','wheelbarrow-plow','full'])for(let seed=0;seed<5;seed++){
 trial(`${p}-seed-${seed}`,p,{duration:600,seed,reseed:true,trace:seed===0&&(p==='none'||p==='full')},seed===0);
}
for(const p of ['none','full']){
 trial(p+'-sustained',p,{duration:1800,reseed:true},true);
 trial(p+'-no-collisions',p,{duration:600,reseed:true,collisions:false});
 trial(p+'-five-stops',p,{duration:600,reseed:true,spotsPerLoad:5});
 trial(p+'-full-initial-pool',p,{duration:600,reseed:true,initialPool:15});
 for(let seed=0;seed<5;seed++)trial(p+`-fine-step-${seed}`,p,{duration:600,reseed:true,dt:.00625,seed});
 trial(p+'-fine-no-collisions',p,{duration:600,reseed:true,dt:.00625,collisions:false});
}
const summaries=['none','wheelbarrow','wheelbarrow-plow','full'].map(p=>{
 const group=trials.filter(t=>t.profile===p&&/-seed-/.test(t.name));
 return {profile:p,seed_count:group.length,windows:group[0].windows.map((w,i)=>({start:w.start,end:w.end,
  food_per_worker_minute:mean(group.map(g=>g.windows[i].food_per_worker_minute)),
  banked_per_worker_minute:mean(group.map(g=>g.windows[i].banked_per_worker_minute)),
  min:Math.min(...group.map(g=>g.windows[i].food_per_worker_minute)),max:Math.max(...group.map(g=>g.windows[i].food_per_worker_minute)),
  per_farm:w.per_farm.map((f,j)=>Object.fromEntries(Object.keys(f).map(k=>[k,typeof f[k]==='number'?mean(group.map(g=>g.windows[i].per_farm[j][k])):f[k]])))}))};
});
const refs=[
 {url:'https://www.ageofempires.com/news/aoe2de-update-50292/',type:'official_patch',finding:'Farmers now work in the middle of farms; supersedes the old left-shifted work area.'},
 {url:'https://steamcommunity.com/sharedfiles/filedetails/?id=2169547705',type:'historical_mechanics',finding:'Centered 2x2 work area, roughly quarter-load work stops, sometimes a fifth stop. DAT does not encode exact stop selection or timing.'},
 {url:'https://www.reddit.com/r/aoe2/comments/kmj7wo/quantum_farming_equation_pilot_cycles_mayan/',type:'historical_observations_and_analysis',finding:'Reports nonuniform portions, extra moves, and inefficient deposit paths. Thus equal portions and shortest paths remain approximations, not established engine behavior.'},
 {url:'https://steamcommunity.com/sharedfiles/filedetails/?id=1932327114',type:'older_in_game_experiment',no_upgrades:20.3,wheelbarrow:22.78,wheelbarrow_plow:23.16,hand_cart_plow:24.4,
  limitations:'Eight farms around a TC, 10 minutes, old patch before centered work area; 5s warm-up, endpoint force-deposit, no normal reseed setup. Our ten farms around a mill differ in geometry and maintenance. Compare only broad scale, not exact error.'},
 {url:'https://www.reddit.com/r/aoe2/comments/1ipzw3v/nevermind_the_farming_cap_is_still_24_never/',type:'2025_multiplayer_experiment',generation_cap_per_minute:24,
  finding:'Author retracts above-cap single-player findings. Reports empty initial pool; occasional 20 vs 21 deliveries and slightly excess farm yield are unresolved engine details.'},
 {url:'https://aoebuddy.com/villager-calculator',type:'excluded_other_simulator',finding:'Explicitly reports measurements from its own game engine; not independent DE validation.'}
];
write('comparison.json',{summaries,trials,references:refs,status:'Generic prototype with explicit unresolved movement/rounding details; not validated for civilization comparisons.'});
const csv=['case,profile,start,end,banked,carried_start,carried_end,harvested,food_per_worker_minute,banked_per_worker_minute,reseed_wood'];
for(const t of trials)for(const w of t.windows)csv.push([t.name,t.profile,w.start,w.end,w.banked,w.carried_start,w.carried_end,w.harvested,w.food_per_worker_minute,w.banked_per_worker_minute,w.wood].join(','));
fs.writeFileSync(path.join(out,'results.csv'),csv.join('\n')+'\n');
