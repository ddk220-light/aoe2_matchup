import fs from 'fs';
const MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt';
const {simulateFarms}=await import(MT+'/tools/farm-gathering-sim.mjs');
const specs=JSON.parse(fs.readFileSync(MT+'/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/eco-inputs.json'));
const get=c=>structuredClone(specs.find(x=>x.civ_name===c).jobs.food.fixture);
const D=+process.argv[2];
for(const civ of process.argv.slice(3)){const f=get(civ);
 // steady state: rate between t=1800 and t=D using snapshots
 const r=simulateFarms(f,{duration:D,seed:0,reseed:true});
 const a=r.snapshots.find(s=>Math.abs(s.t-1800)<1e-6), b=r.final;
 console.log(civ.padEnd(12),'0-1800:',(a.harvested/1800/10*60).toFixed(3),' 1800-'+D+':',((b.harvested-a.harvested)/(D-1800)/10*60).toFixed(3),' wood/food overall',(b.wood/b.harvested).toFixed(4));
}
