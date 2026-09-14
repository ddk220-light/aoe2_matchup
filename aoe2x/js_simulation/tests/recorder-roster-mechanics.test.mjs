import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { calculateDamage, trampleSpec } from '../src/combat/attacks.js';
import { createUnitState } from '../src/combat/unit-state.js';
import { createWorld, stepWorld } from '../src/combat/world.js';
import { unitBySlug } from '../src/unit-registry.js';

async function fixture(slug) {
  return JSON.parse(await readFile(new URL(`../fixtures/unit_stats/${slug}_imperial.json`, import.meta.url)));
}

test('every canonical roster entry has an executable source-backed profile', async () => {
  const roster = JSON.parse(await readFile(new URL('../../../data/unique-unit-roster.json', import.meta.url)));
  const tiger = await fixture('elite_tiger_cavalry_wei');
  for (const unit of roster.units) {
    const registered = unitBySlug(unit.slug);
    assert.ok(registered, `${unit.slug}: missing registry entry`);
    const profile = JSON.parse(await readFile(new URL(`../fixtures/unit_stats/${registered.fixture}`, import.meta.url)));
    assert.equal(profile.unit_master, unit.master);
    assert.equal(profile.civilization, unit.civ);
    assert.match(profile.provenance.dat_sha256, /^[a-f0-9]{64}$/i);
    const spawn = (id,owner,x,mechanics) => createUnitState({referenceId:id,owner,x,y:4,facing:0,mechanics,
      actionTimers:{windup:0,reload:0,swing:0,acquire:0}});
    let world = createWorld({ratio:'roster-preflight',units:[spawn(1,2,4,tiger),spawn(2,3,4.6,profile)]});
    for (let i=0;i<180;i++) world=stepWorld(world);
    for (const body of world.units) assert.ok(Number.isFinite(body.hp), `${unit.slug}: invalid HP`);
  }
});

test('Missionary patrol does not invent a damaging weapon', async () => {
  const missionary = await fixture('missionary_spanish');
  assert.equal(missionary.effects.non_attacking,true);
  assert.deepEqual(missionary.attack_classes,{});
  assert.equal(calculateDamage({mechanics:missionary},{mechanics:await fixture('elite_tiger_cavalry_wei')}),0);
});

test('Flaming Camel explodes once and removes its own body', async () => {
  const camel = await fixture('flaming_camel_tatars');
  const tiger = {...await fixture('elite_tiger_cavalry_wei'), hp:1000, speed_tiles_per_second:0,
    effects:{non_attacking:true}};
  assert.equal(camel.attack_classes['11'],280,'unsigned Siege Engineers multiplier');
  const spawn = (id,owner,x,mechanics) => createUnitState({referenceId:id,owner,x,y:4,facing:0,mechanics,
    actionTimers:{windup:0,reload:0,swing:0,acquire:0}});
  let world=createWorld({ratio:'suicide-test',units:[spawn(1,2,4,camel),spawn(2,3,4.4,tiger)]});
  for(let i=0;i<180;i++) world=stepWorld(world);
  assert.equal(world.units.find(u=>u.referenceId===1).alive,false);
  assert.equal(world.eventLog.filter(e=>e.kind==='suicide-explosion'&&e.targetId===2).length,1);
});

test('Sicilian resistance reduces only the matching bonus damage', async () => {
  const tiger = await fixture('elite_tiger_cavalry_wei');
  const defender = await fixture('elite_serjeant_sicilians');
  const actor = { mechanics: { ...tiger, attack_classes: { 4: 17, 1: 10 } } };
  const target = { mechanics: { ...defender, armor_classes: {4: 6, 1: 2} } };
  assert.equal(calculateDamage(actor, target), 11 + 8 * .6);
  target.mechanics.armor_classes[1] = 20;
  assert.equal(calculateDamage(actor, target), 11);
});

test('Cataphract flat trample and elephant proportional trample remain distinct', async () => {
  const cat = trampleSpec(await fixture('elite_cataphract_byzantines'));
  const elephant = trampleSpec(await fixture('elite_war_elephant_persians'));
  assert.equal(cat.flatDamage, 5);
  assert.equal(cat.widthTiles, .5);
  assert.equal(elephant.damageFraction, .5);
  assert.equal(elephant.flatDamage, undefined);
});

test('Iron Pagoda blocks its first melee hit and takes the next hit', async () => {
  const tiger = await fixture('elite_tiger_cavalry_wei');
  const pagoda = await fixture('elite_iron_pagoda_jurchens');
  const spawn = (id, owner, x, mechanics) => createUnitState({referenceId:id,owner,x,y:4,facing:0,
    mechanics,actionTimers:{windup:0,reload:0,swing:0,acquire:0}});
  const fastTiger = {...tiger,speed_tiles_per_second:0,attack_delay_seconds:0,
    reload_seconds:.2,attack_animation:{...tiger.attack_animation,seconds:.1}};
  let world = createWorld({ratio:'block-test',units:[spawn(1,2,4,fastTiger),spawn(2,3,4.4,pagoda)]});
  for(let i=0;i<120;i++) world=stepWorld(world);
  assert.equal(world.eventLog.filter(e=>e.type==='melee-blocked'&&e.actorId===2).length,1);
  assert.ok(world.eventLog.some(e=>e.type==='damage'&&e.targetId===2));
});

test('Monaspa aura crosses seven-body thresholds and falls when an ally dies', async () => {
  const mechanics = await fixture('elite_monaspa_georgians');
  const units=Array.from({length:14},(_,i)=>createUnitState({referenceId:i+1,owner:2,x:4+i*.5,y:4,facing:0,
    mechanics,actionTimers:{windup:0,reload:0,swing:0,acquire:0}}));
  let world=stepWorld(createWorld({ratio:'aura-threshold',units}));
  assert.equal(world.units[0].specialState.nearbyAttackBonus,2);
  world=structuredClone(world);world.units[13].alive=false;world.units[13].hp=0;
  world=stepWorld(world);
  assert.equal(world.units[0].specialState.nearbyAttackBonus,1);
});

test('Iron Pagoda shield recharges over thirty game seconds', async () => {
  const mechanics=await fixture('elite_iron_pagoda_jurchens');
  const unit=createUnitState({referenceId:1,owner:2,x:4,y:4,facing:0,mechanics,
    actionTimers:{windup:0,reload:0,swing:0,acquire:0}});
  let world=stepWorld(createWorld({ratio:'shield-recharge',units:[unit]}));
  world=structuredClone(world);world.units[0].specialState.melee_block=0;
  for(let i=0;i<900;i++) world=stepWorld(world);
  assert.ok(Math.abs(world.units[0].specialState.melee_block-.5)<.001);
  for(let i=0;i<900;i++) world=stepWorld(world);
  assert.ok(Math.abs(world.units[0].specialState.melee_block-1)<.001);
});
