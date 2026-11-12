import fs from 'fs';
const MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt';
const {simulateFarms}=await import(MT+'/tools/farm-gathering-sim.mjs');
const specs=JSON.parse(fs.readFileSync(MT+'/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/eco-inputs.json'));
for(const civ of process.argv.slice(2)){
 const s=specs.find(x=>x.civ_name===civ);const f=structuredClone(s.jobs.food.fixture);
 const r=simulateFarms(f,{duration:1800,seed:0,reseed:true});
 const a=r.final.agents; const sum=k=>a.reduce((s,x)=>s+(x[k]||0),0);
 console.log(civ, Object.keys(a[0]).join(','));
 console.log(['working','internal_walking','outbound_walking','return_walking','blocked','building','idle','harvested','banked'].map(k=>k+'='+(sum(k)/10).toFixed(1)).join(' '));
}
