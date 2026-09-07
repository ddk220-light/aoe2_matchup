import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { trampleSpec } from "../src/combat/attacks.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const championMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url), "utf8"));
const paladinMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/paladin_spanish_imperial.json", import.meta.url), "utf8"));
const elephantMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/elite_battle_elephant_burmese_imperial.json", import.meta.url), "utf8"));


function unit({ referenceId, owner, x, y, mechanics, hp = mechanics.hp }) {
  return {
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics,
    unitMaster: mechanics.unit_master,
    hp,
    alive: true,
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
    action: "idle",
    actionTimers: { windup: 0, reload: 0 },
  };
}


function stepUntilDamage(world, actorId, maxTicks = 240) {
  for (let i = 0; i < maxTicks; i += 1) {
    world = stepWorld(world);
    const events = world.eventLog.filter((event) => (
      event.type === "damage" && event.actorId === actorId
    ));
    if (events.length > 0) return { world, tick: events[0].tick };
  }
  throw new Error(`no damage from ${actorId} within ${maxTicks} ticks`);
}


test("trampleSpec gates on the dat blast fields", () => {
  const spec = trampleSpec(elephantMechanics);
  assert.ok(spec);
  assert.ok(Math.abs(spec.widthTiles - 0.4) < 1e-6);
  assert.equal(spec.damageFraction, 0.25);
  // Champion carries the dat's width-0 / damage -5.0 "no trample" sentinels.
  assert.equal(trampleSpec(championMechanics), null);
  assert.equal(trampleSpec(paladinMechanics), null);
});


test("an elephant hit tramples enemies in blast reach and nobody else", () => {
  // Target in contact to the west; bystander B within blast reach
  // (reach 0.55 - 0.25 = 0.30 <= 0.4); paladin C diagonal outside reach
  // (hypot(0.37, 0.37) = 0.52 > 0.4); allied elephant as close as B.
  const world = createWorld({
    ratio: "trample-test",
    units: [
      unit({ referenceId: 1, owner: 3, x: 5.0, y: 5.0, mechanics: elephantMechanics }),
      unit({ referenceId: 2, owner: 3, x: 5.0, y: 4.45, mechanics: elephantMechanics }),
      unit({ referenceId: 3, owner: 2, x: 4.5, y: 5.0, mechanics: paladinMechanics }),
      unit({ referenceId: 4, owner: 2, x: 5.0, y: 5.55, mechanics: paladinMechanics }),
      unit({ referenceId: 5, owner: 2, x: 5.62, y: 5.62, mechanics: paladinMechanics }),
    ],
  });
  const { world: after, tick } = stepUntilDamage(world, 1);
  const swing = after.eventLog.filter((event) => (
    event.type === "damage" && event.actorId === 1 && event.tick === tick
  ));
  const main = swing.filter((event) => event.kind === undefined);
  const tramples = swing.filter((event) => event.kind === "trample");
  assert.equal(main.length, 1);
  assert.equal(main[0].amount, 13);
  assert.equal(tramples.length, 1);
  assert.equal(tramples[0].targetId, 4);
  assert.equal(tramples[0].amount, 3.25);
  assert.ok(!swing.some((event) => event.targetId === 2), "ally must not be trampled");
  assert.ok(!swing.some((event) => event.targetId === 5), "out-of-reach must not be trampled");
});


test("a killing trample emits a death event", () => {
  const world = createWorld({
    ratio: "trample-kill-test",
    units: [
      unit({ referenceId: 1, owner: 3, x: 5.0, y: 5.0, mechanics: elephantMechanics }),
      unit({ referenceId: 3, owner: 2, x: 4.5, y: 5.0, mechanics: paladinMechanics }),
      unit({ referenceId: 4, owner: 2, x: 5.0, y: 5.55, mechanics: paladinMechanics, hp: 2 }),
    ],
  });
  const { world: after, tick } = stepUntilDamage(world, 1);
  const trample = after.eventLog.find((event) => (
    event.type === "damage" && event.actorId === 1 && event.tick === tick
    && event.kind === "trample" && event.targetId === 4
  ));
  assert.ok(trample, "bystander must be trampled");
  assert.equal(trample.hpAfter, 0);
  assert.ok(after.eventLog.some((event) => (
    event.type === "death" && event.targetId === 4 && event.tick === tick
  )), "trample kill must emit a death event");
});
