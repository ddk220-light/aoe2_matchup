import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {createUnitState} from '../src/combat/unit-state.js';
import {createWorld,stepWorld} from '../src/combat/world.js';

const fixture=async name=>JSON.parse(await readFile(new URL('../fixtures/unit_stats/'+name+'_imperial.json',import.meta.url)));
const shotel=await fixture('elite_shotel_warrior_ethiopians');
const tiger=await fixture('elite_tiger_cavalry_wei');
const spawn=(id,owner,x,y,mechanics)=>createUnitState({referenceId:id,owner,x,y,facing:0,mechanics,
  actionTimers:{windup:0,reload:0,swing:0,acquire:0}});

for (const [bystanderSwing, expectedReload] of [[60,58],[30,0]]) {
test(`a melee bystander at swing ${bystanderSwing} abandons another unit's kill with reload ${expectedReload}`,()=>{
  let world=structuredClone(createWorld({ratio:'bystander-recovery',map:{width:16,height:16,obstacles:[]},units:[
    spawn(1,2,4,4,shotel),spawn(2,2,4,4.8,shotel),
    spawn(3,3,4.5,4,{...tiger,effects:{non_attacking:true}}),
    spawn(4,3,7,4,{...tiger,effects:{non_attacking:true}}),
  ]}));
  world.units[2].hp=1;
  for(const [index,swing] of [[0,44],[1,bystanderSwing]]){
    const u=world.units[index];u.action='attacking';u.pursuitTargetId=3;
    u.engagedTargetId=3;u.attackTargetId=3;
    u.actionTimers={windup:Math.max(0,45-swing),reload:120-swing,swing,acquire:0};
  }
  world=stepWorld(world);
  assert.equal(world.units.find(u=>u.referenceId===3).killedById,1);
  world=stepWorld(world);
  const killer=world.units.find(u=>u.referenceId===1);
  const bystander=world.units.find(u=>u.referenceId===2);
  assert.equal(killer.action,'attacking','the actual killer retains its backswing');
  assert.equal(killer.attackTargetId,3);
  assert.notEqual(bystander.action,'attacking','another attacker can reacquire immediately');
  assert.equal(bystander.attackTargetId,null);
  assert.equal(bystander.actionTimers.reload,expectedReload,
    'only an unreleased attack may refund weapon reload');
  assert.ok(world.events.some(e=>e.type==='attack-canceled'&&e.actorId===2));
});
}
