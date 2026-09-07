import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { chargeProjectileDamage, chargeSpec } from "../src/combat/attacks.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const championMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url), "utf8"));
const paladinMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/paladin_spanish_imperial.json", import.meta.url), "utf8"));
const lancerMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/elite_fire_lancer_chinese_imperial.json", import.meta.url), "utf8"));


function spawn({ referenceId, owner, x, y, mechanics, rank, count }) {
  return createUnitState({
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics,
    acquisitionRank: rank,
    acquisitionCount: count,
  });
}


function runFight(units, ticks) {
  let world = createWorld({ ratio: "fire-lancer-test", units });
  for (let i = 0; i < ticks; i += 1) {
    world = stepWorld(world);
    const owners = new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner));
    if (owners.size <= 1) break;
  }
  return world;
}


test("the charge spec and flat class-matched damage come from the fixture", () => {
  const spec = chargeSpec(lancerMechanics);
  assert.equal(spec.projectileCount, 3);
  assert.equal(spec.windupTicks, 40);
  assert.equal(spec.animationTicks, 120);
  assert.equal(spec.projectileSpeed, 7.5);
  // Armor values are ignored: the champion (pierce armor 5) and the paladin
  // (pierce armor 7) both take exactly the projectile's class-3 amount.
  const champion = { mechanics: championMechanics };
  const paladin = { mechanics: paladinMechanics };
  assert.equal(chargeProjectileDamage(spec, champion), 3);
  assert.equal(chargeProjectileDamage(spec, paladin), 3);
});


test("the charge volley is the opening attack cycle, fired standing at range", () => {
  const world = runFight([
    spawn({ referenceId: 1, owner: 2, x: 4.5, y: 4, mechanics: championMechanics, rank: 0, count: 2 }),
    spawn({ referenceId: 2, owner: 3, x: 8.5, y: 4, mechanics: lancerMechanics, rank: 1, count: 2 }),
  ], 1800);

  const volleys = world.eventLog.filter((e) => e.type === "charge-volley");
  assert.equal(volleys.length, 1, "exactly one volley per fight");
  assert.equal(volleys[0].actorId, 2);

  const chargeStart = world.eventLog.find((e) => e.type === "attack-start" && e.kind === "charge");
  assert.ok(chargeStart, "the volley must run as an attack cycle");
  assert.equal(chargeStart.actorId, 2);
  // Released on charge-animation frame frame_delay: 0.6667 s -> 40 ticks.
  assert.equal(volleys[0].tick, chargeStart.tick + 40);
  // The lancer's FIRST attack cycle is the charge, before any melee swing.
  const lancerStarts = world.eventLog.filter((e) => e.type === "attack-start" && e.actorId === 2);
  assert.equal(lancerStarts[0].kind, "charge");

  // Fired standing at range: the lancer has not moved off its spawn when the
  // volley releases, and stays put through the 2.0 s charge animation.
  const animationEnd = chargeStart.tick + 120;
  for (const snapshot of world.snapshots) {
    if (snapshot.tick > animationEnd) break;
    const lancer = snapshot.units.find(({ referenceId }) => referenceId === 2);
    assert.equal(lancer.x, 8.5, `lancer moved before animation end at tick ${snapshot.tick}`);
  }
  const victimAtFire = world.snapshots
    .find(({ tick }) => tick === volleys[0].tick)
    .units.find(({ referenceId }) => referenceId === 1);
  assert.ok(Math.abs(victimAtFire.x - 8.5) > 1.0, "the volley must be fired from range");

  // Three projectiles, flat 3 damage each, landing after flight time.
  const hits = world.eventLog.filter((e) => e.type === "damage" && e.kind === "charge-projectile");
  assert.equal(hits.length, 3);
  for (const hit of hits) {
    assert.equal(hit.amount, 3);
    assert.equal(hit.targetId, 1);
    assert.ok(hit.tick > volleys[0].tick, "projectiles need flight time");
    assert.ok(hit.tick <= volleys[0].tick + 60, "flight time must fit the fire distance");
  }

  // Post-charge melee: 10 per hit on the champion (attack 14 - armor 4), and
  // the first melee swing waits out the reload that began at the charge swing.
  const meleeHits = world.eventLog.filter((e) => (
    e.type === "damage" && e.actorId === 2 && e.kind === undefined && e.amount > 0
  ));
  assert.ok(meleeHits.length > 0, "the lancer must reach melee");
  assert.equal(meleeHits[0].amount, 10);
  const firstMeleeStart = world.eventLog.find((e) => (
    e.type === "attack-start" && e.actorId === 2 && e.kind === undefined
  ));
  assert.ok(firstMeleeStart.tick >= chargeStart.tick + 120,
    "melee swing must respect the reload started at the charge swing");
});


test("charge damage ignores the victim's armor values", () => {
  const world = runFight([
    spawn({ referenceId: 1, owner: 2, x: 4.5, y: 4, mechanics: paladinMechanics, rank: 0, count: 2 }),
    spawn({ referenceId: 2, owner: 3, x: 8.5, y: 4, mechanics: lancerMechanics, rank: 1, count: 2 }),
  ], 1800);
  const hits = world.eventLog.filter((e) => e.type === "damage" && e.kind === "charge-projectile");
  assert.equal(hits.length, 3);
  for (const hit of hits) assert.equal(hit.amount, 3, "pierce armor 7 must not reduce the hit");
});


test("a projectile whose target dies mid-volley vanishes", () => {
  // Same fixture, 5 hp: the third projectile of the volley finds a corpse.
  const fragile = { ...championMechanics, hp: 5 };
  const world = runFight([
    spawn({ referenceId: 1, owner: 2, x: 4.5, y: 4, mechanics: fragile, rank: 0, count: 2 }),
    spawn({ referenceId: 2, owner: 3, x: 8.5, y: 4, mechanics: lancerMechanics, rank: 1, count: 2 }),
  ], 1800);
  const hits = world.eventLog.filter((e) => e.type === "damage" && e.kind === "charge-projectile");
  assert.equal(hits.length, 2, "the post-death projectile must vanish");
  assert.equal(hits[1].hpAfter, 0);
  const deaths = world.eventLog.filter((e) => e.type === "death");
  assert.equal(deaths.length, 1);
  assert.equal(deaths[0].targetId, 1);
});
