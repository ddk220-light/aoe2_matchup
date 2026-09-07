import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { calculateDamage, rangedSpec } from "../src/combat/attacks.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const arbalesterMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/arbalester_chinese_imperial.json", import.meta.url), "utf8"));
const skirmisherMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/elite_skirmisher_chinese_imperial.json", import.meta.url), "utf8"));
const readChampion = await readFile(
  new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url), "utf8");


function spawn({ referenceId, owner, x, y, mechanics, rank = 0, count = 2 }) {
  return createUnitState({
    referenceId, owner, x, y, facing: 0, mechanics,
    acquisitionRank: rank, acquisitionCount: count,
  });
}


function run(units, ticks) {
  let world = createWorld({ ratio: "ranged-test", units });
  for (let i = 0; i < ticks; i += 1) {
    world = stepWorld(world);
    const owners = new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner));
    if (owners.size <= 1) break;
  }
  return world;
}


test("the class rule handles pure-pierce attackers and the ranged spec loads", () => {
  const arb = { mechanics: arbalesterMechanics };
  const skirm = { mechanics: skirmisherMechanics };
  // arb pierce 10 - skirm pierce armor 8 = 2; skirm 7 - 4 plus archer bonus 4.
  assert.equal(calculateDamage(arb, skirm), 2);
  assert.equal(calculateDamage(skirm, arb), 7);
  const spec = rangedSpec(arbalesterMechanics);
  assert.equal(spec.projectileSpeed, 7);
  assert.equal(rangedSpec(skirmisherMechanics).minRangeTiles, 1);
});


test("a standoff duel exchanges projectiles on reload cadence with flight time", () => {
  const world = run([
    spawn({ referenceId: 1, owner: 2, x: 2, y: 4, mechanics: arbalesterMechanics, rank: 0 }),
    spawn({ referenceId: 2, owner: 3, x: 9, y: 4, mechanics: skirmisherMechanics, rank: 1 }),
  ], 3600);

  const arbHits = world.eventLog.filter((e) => (
    e.type === "damage" && e.actorId === 1 && e.kind === "ranged-projectile"));
  const skirmHits = world.eventLog.filter((e) => (
    e.type === "damage" && e.actorId === 2 && e.kind === "ranged-projectile"));
  assert.ok(arbHits.length >= 5, "arbalester must land shots");
  assert.ok(skirmHits.length >= 3, "skirmisher must land shots");
  for (const hit of arbHits) assert.equal(hit.amount, 2);
  for (const hit of skirmHits) assert.equal(hit.amount, 7);

  // Nobody ever moves: 7 tiles of separation is inside both units' range 8.
  for (const snapshot of world.snapshots) {
    for (const unit of snapshot.units) {
      assert.equal(unit.x, unit.referenceId === 1 ? 2 : 9);
    }
  }

  // Cadence: arb attack starts 1.7 s apart (102 ticks), skirm 3.0 s (180).
  const starts = (id) => world.eventLog
    .filter((e) => e.type === "attack-start" && e.actorId === id)
    .map((e) => e.tick);
  const arbStarts = starts(1);
  assert.equal(arbStarts[1] - arbStarts[0], 102);
  const skirmStarts = starts(2);
  assert.equal(skirmStarts[1] - skirmStarts[0], 180);

  // Shots need flight time: damage lands about a second after the start
  // (7 tiles at 7 tiles/s, windup 0.342 s -> ~21 + 60 ticks).
  assert.ok(arbHits[0].tick > arbStarts[0] + 70);

  // The trash counter wins: 7 damage every 3.0 s beats 2 damage every 1.7 s,
  // so the arbalester (40 hp) falls on the skirmisher's 6th javelin.
  const deaths = world.eventLog.filter((e) => e.type === "death");
  assert.equal(deaths.length, 1);
  assert.equal(deaths[0].targetId, 1);
  assert.equal(skirmHits.length, 6);
  const survivor = world.units.find(({ referenceId }) => referenceId === 2);
  assert.equal(survivor.alive, true);
});


test("a projectile in flight vanishes when its target dies first", () => {
  // Two arbalesters focus the skirmisher. Effective damage (hp deltas) sums
  // to exactly its hp pool: any arrow that finds a corpse never lands.
  const world = run([
    spawn({ referenceId: 1, owner: 2, x: 2, y: 4, mechanics: arbalesterMechanics, rank: 0, count: 3 }),
    spawn({ referenceId: 2, owner: 2, x: 2, y: 6, mechanics: arbalesterMechanics, rank: 1, count: 3 }),
    spawn({ referenceId: 3, owner: 3, x: 9, y: 5, mechanics: skirmisherMechanics, rank: 2, count: 3 }),
  ], 3600);
  const onSkirm = world.eventLog.filter((e) => e.type === "damage" && e.targetId === 3);
  const effective = onSkirm.reduce((s, e) => s + (e.hpBefore - e.hpAfter), 0);
  assert.equal(effective, 35);
  assert.equal(world.units.find(({ referenceId }) => referenceId === 3).alive, false);
  const death = world.eventLog.find((e) => e.type === "death");
  assert.equal(world.eventLog.filter((e) => (
    e.type === "damage" && e.targetId === 3 && e.tick > death.tick)).length, 0,
  "no arrow lands after the death");
});


test("an approaching target walks into the arrow early; the aim point is the cap", () => {
  // A champion (LOS 5) marches head-on at a standing arbalester from just
  // inside mutual sight. Shots aimed at its fire-time position meet it EARLY
  // along the path — the projectile is a physical point, not a scheduled
  // arrival at the aim point.
  const championMechanics = JSON.parse(readChampion);
  const world = run([
    spawn({ referenceId: 1, owner: 2, x: 2, y: 4, mechanics: arbalesterMechanics, rank: 0, count: 2 }),
    spawn({ referenceId: 2, owner: 3, x: 6.9, y: 4, mechanics: championMechanics, rank: 1, count: 2 }),
  ], 1200);
  const hits = world.eventLog.filter((e) => (
    e.type === "damage" && e.actorId === 1 && e.kind === "ranged-projectile"));
  assert.ok(hits.length >= 2, "the walker must be hit during its approach");
  // The champion was MOVING when hit: the hit tick's snapshot places it well
  // short of the shot's aim distance, and the flight beat the aim-point time.
  const firstStart = world.eventLog.find((e) => (
    e.type === "attack-start" && e.actorId === 1));
  const release = firstStart.tick + 21;   // 0.342 s windup
  const aimTicks = Math.ceil((4.9 / 7.0) * 60);
  assert.ok(hits[0].tick - release < aimTicks,
    `first hit flight ${hits[0].tick - release} ticks should beat the ${aimTicks}-tick aim-point arrival`);
});
