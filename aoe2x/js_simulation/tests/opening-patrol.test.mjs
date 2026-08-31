import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const mechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json",
  import.meta.url,
), "utf8"));
const rangedMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/hand_cannoneer_spanish_imperial.json",
  import.meta.url,
), "utf8"));


function patrolWorld() {
  return createWorld({
    ratio: "patrol-test",
    map: { width: 10, height: 10, obstacles: [] },
    units: [
      createUnitState({
        referenceId: 1, owner: 2, x: 8, y: 2, facing: 0, mechanics,
        acquisitionRank: 0, acquisitionCount: 2,
      }),
      createUnitState({
        referenceId: 2, owner: 3, x: 2, y: 8, facing: 0, mechanics,
        acquisitionRank: 1, acquisitionCount: 2,
      }),
    ],
    openingPatrolByOwner: { 2: { x: 2, y: 8 }, 3: { x: 8, y: 2 } },
    disableAiOrders: true,
  });
}


function scenarioPatrolWorld(side2Mechanics, side3Mechanics) {
  const durable = (source) => ({ ...source, hp: 10_000 });
  return createWorld({
    ratio: "scenario-patrol-test",
    map: { width: 16, height: 16, obstacles: [] },
    units: [
      createUnitState({
        referenceId: 1, owner: 2, x: 12, y: 3, facing: 0,
        mechanics: durable(side2Mechanics), acquisitionRank: 0, acquisitionCount: 4,
      }),
      createUnitState({
        referenceId: 2, owner: 2, x: 12.5, y: 3, facing: 0,
        mechanics: durable(side2Mechanics), acquisitionRank: 1, acquisitionCount: 4,
      }),
      createUnitState({
        referenceId: 3, owner: 3, x: 3, y: 12, facing: 0,
        mechanics: durable(side3Mechanics), acquisitionRank: 2, acquisitionCount: 4,
      }),
      createUnitState({
        referenceId: 4, owner: 3, x: 3.5, y: 12, facing: 0,
        mechanics: durable(side3Mechanics), acquisitionRank: 3, acquisitionCount: 4,
      }),
    ],
    triggers: [{
      trigger_index: 0,
      name: "Starting",
      looping: false,
      conditions: [],
      effects: [
        {
          type: "patrol", owner: 2, x: 2, y: 13,
          area: { x1: 8, y1: 0, x2: 15, y2: 7 }, effect_index: 1,
        },
        {
          type: "patrol", owner: 3, x: 13, y: 2,
          area: { x1: 0, y1: 8, x2: 7, y2: 15 }, effect_index: 2,
        },
      ],
    }],
    disableAiOrders: true,
  });
}


function assertScenarioPatrolBecomesCombat(world) {
  assert.deepEqual(
    world.units.filter(({ owner }) => owner === 2).map(({ moveOrder }) => [moveOrder.x, moveOrder.y]),
    [[2, 13], [2, 13]],
  );
  assert.deepEqual(
    world.units.filter(({ owner }) => owner === 3).map(({ moveOrder }) => [moveOrder.x, moveOrder.y]),
    [[13, 2], [13, 2]],
  );
  for (let tick = 0; tick < 900; tick += 1) {
    world = stepWorld(world);
    if (world.units.every(({ pursuitTargetId }) => pursuitTargetId !== null)) break;
  }
  assert.equal(world.units.every(({ pursuitTargetId }) => pursuitTargetId !== null), true);
  assert.equal(world.units.every(({ moveOrder }) => moveOrder?.kind === "scenario-patrol"), true);
  assert.equal(world.units.every(({ patrolFormationTransit }) => (
    patrolFormationTransit === false
  )), true);
}


test("opening patrol moves at sourced speed without replay waypoint fields", () => {
  let world = patrolWorld();
  assert.equal(Object.hasOwn(world, "orderState"), false);
  assert.equal(world.units.every(({ moveOrder }) => moveOrder?.kind === "opening-patrol"), true);
  for (const { moveOrder } of world.units) {
    assert.equal("waypointUntilTick" in moveOrder, false);
    assert.equal("profileWaypoints" in moveOrder, false);
    assert.equal("profileAcquireTick" in moveOrder, false);
    assert.equal("profileTargetSlot" in moveOrder, false);
  }
  const initial = world.units.map(({ x, y }) => [x, y]);
  world = stepWorld(world);
  assert.notDeepEqual(world.units.map(({ x, y }) => [x, y]), initial);
});


test("ordinary acquisition ends each unit's opening patrol", () => {
  let world = patrolWorld();
  for (let tick = 0; tick < 600; tick += 1) {
    world = stepWorld(world);
    if (world.units.every(({ pursuitTargetId }) => pursuitTargetId !== null)) break;
  }
  assert.deepEqual(world.units.map(({ pursuitTargetId }) => pursuitTargetId), [2, 1]);
  assert.equal(world.units.every(({ moveOrder }) => moveOrder === undefined), true);
});


test("ranged-vs-ranged scenario patrol suspends its point during combat", () => {
  assertScenarioPatrolBecomesCombat(scenarioPatrolWorld(rangedMechanics, rangedMechanics));
});


test("ranged-vs-melee scenario patrol suspends its point during combat", () => {
  assertScenarioPatrolBecomesCombat(scenarioPatrolWorld(rangedMechanics, mechanics));
});
