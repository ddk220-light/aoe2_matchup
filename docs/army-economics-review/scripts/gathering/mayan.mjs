import fs from 'fs';
const MT='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt';
const {simulateFarms}=await import(MT+'/tools/farm-gathering-sim.mjs');
const specs=JSON.parse(fs.readFileSync(MT+'/aoe2x/js_simulation/calibration/economy/army-context-2026-11-10/eco-inputs.json'));
for(const civ of process.argv.slice(2)){
 const s=specs.find(x=>x.civ_name===civ);const f=structuredClone(s.jobs.food.fixture);
 const r=simulateFarms(f,{duration:1800,seed:0,reseed:true});
 const g=f.farm.generation_rate;
 console.log(civ,'gen',g,'work',f.worker.work_rate,'yield',f.worker.task_output_multiplier,'harvested/min',(r.final.harvested/1800/10*60).toFixed(3),'wood',r.final.wood);
}
