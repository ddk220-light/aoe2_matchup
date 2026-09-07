import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { rangedSpec } from "../src/combat/attacks.js";
import { isWithinReach } from "../src/combat/targeting.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const scorpionMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/heavy_scorpion_japanese_imperial.json", import.meta.url), "utf8"));
const arbalesterMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/arbalester_chinese_imperial.json", import.meta.url), "utf8"));


function spawn({ referenceId, owner, x, y, mechanics, rank, count }) {
  return createUnitState({
    referenceId, owner, x, y, facing: 0, mechanics,
    acquisitionRank: rank, acquisitionCount: count,
  });
}


function run(units, ticks) {
  let world = createWorld({ ratio: "bolt-test", units });
  for (let i = 0; i < ticks; i += 1) {
    world = stepWorld(world);
    const owners = new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner));
    if (owners.size <= 1) break;
  }
  return world;
}


test("the bolt spec loads pass-through fields from the dat fixture", () => {
  const spec = rangedSpec(scorpionMechanics);
  assert.equal(spec.passThrough, true);
  assert.equal(spec.projectileHalfWidth, 0.1);
  assert.equal(spec.minRangeTiles, 2);
  assert.equal(rangedSpec(arbalesterMechanics).passThrough, false);
});


test("a target inside minimum range is not attackable", () => {
  const scorpion = spawn({ referenceId: 1, owner: 2, x: 4, y: 4, mechanics: scorpionMechanics, rank: 0, count: 2 });
  const near = spawn({ referenceId: 2, owner: 3, x: 5.5, y: 4, mechanics: arbalesterMechanics, rank: 1, count: 2 });
  const far = spawn({ referenceId: 3, owner: 3, x: 8, y: 4, mechanics: arbalesterMechanics, rank: 1, count: 2 });
  assert.equal(isWithinReach(scorpion, near), false, "1.5 tiles is inside min range 2");
  assert.equal(isWithinReach(scorpion, far), true);
});


test("one bolt passes through the line: full damage on the target, half beyond", () => {
  // Three arbalesters stacked along the firing line, target first. All are
  // acquisition-locked far from their own range gates by making them the
  // enemy side only; the scorpion fires down the column.
  const world = run([
    spawn({ referenceId: 1, owner: 2, x: 2, y: 4, mechanics: scorpionMechanics, rank: 0, count: 4 }),
    spawn({ referenceId: 2, owner: 3, x: 7, y: 4, mechanics: arbalesterMechanics, rank: 1, count: 4 }),
    spawn({ referenceId: 3, owner: 3, x: 8, y: 4, mechanics: arbalesterMechanics, rank: 2, count: 4 }),
    spawn({ referenceId: 4, owner: 3, x: 9, y: 4, mechanics: arbalesterMechanics, rank: 3, count: 4 }),
  ], 400);

  const boltHits = world.eventLog.filter((e) => (
    e.type === "damage" && e.actorId === 1 && e.kind === "bolt-projectile"));
  assert.ok(boltHits.length >= 3, "the first bolt must sweep the column");
  const first = boltHits.slice(0, 3);
  const target = world.eventLog.find((e) => e.type === "attack-start" && e.actorId === 1).targetId;
  for (const hit of first) {
    if (hit.targetId === target) {
      assert.equal(hit.amount, 11, "action target takes full 15-4");
    } else {
      assert.equal(hit.amount, 5.5, "pass victims take exactly half");
    }
  }
  // Victims are struck in line order as the bolt travels, each exactly once
  // per bolt.
  assert.deepEqual(first.map((e) => e.targetId), [2, 3, 4]);
  assert.ok(first[0].tick < first[1].tick && first[1].tick < first[2].tick,
    "hits land in flight order, not simultaneously");
});
