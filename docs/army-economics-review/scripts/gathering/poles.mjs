import fs from 'fs';
const MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt';
const {simulateFarms}=await import(MT+'/tools/farm-gathering-sim.mjs');
const specs=JSON.parse(fs.readFileSync(MT+'/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/eco-inputs.json'));
const get=c=>structuredClone(specs.find(x=>x.civ_name===c).jobs.food.fixture);
function run(f,label){let tot=0,wood=0,rs=[];for(let seed=0;seed<3;seed++){const r=simulateFarms(f,{duration:1800,seed,reseed:true});rs.push(r.final.harvested/1800/10*60);wood+=r.final.wood;}
 const m=rs.reduce((a,b)=>a+b)/3; console.log(label.padEnd(45),m.toFixed(3),'wood/3seeds',wood/3,'wood/food',(wood/3/(m*10*30)).toFixed(4));return m;}
const p=get('Poles'); run(p,'Poles as modeled (instant deducted)');
const p0=get('Poles'); p0.farms.forEach(f=>f.instant_food=0); run(p0,'Poles layout, no folwark bonus');
const b=get('Byzantines'); run(b,'Generic layout');
// extra-food interpretation: farm food 550 + instant (i.e. reserve=550, instant extra)
const pe=get('Poles'); pe.farm.food=605; run(pe,'Poles, instant EXTRA (farm 605, 55 instant)');
const pe8=get('Poles'); pe8.farms.forEach(f=>{if(f.instant_food)f.instant_food=44}); run(pe8,'Poles 8% deducted');
const d=get('Danes'); run(d,'Danes as modeled');
