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


function principalRangedPatrolWorld() {
  const durable = { ...rangedMechanics, hp: 10_000 };
  const units = [];
  for (let index = 0; index < 7; index += 1) {
    units.push(createUnitState({
      referenceId: index + 1,
      owner: 2,
      x: 4,
      y: 4 + index,
      facing: 0,
      mechanics: durable,
      acquisitionRank: index,
      acquisitionCount: 7,
    }));
  }
  for (let index = 0; index < 3; index += 1) {
    units.push(createUnitState({
      referenceId: 101 + index,
      owner: 3,
      x: 16,
      y: 5 + 2 * index,
      facing: Math.PI,
      mechanics: durable,
      acquisitionRank: index,
      acquisitionCount: 3,
    }));
  }
  return createWorld({
    ratio: "principal-ranged-patrol-test",
    map: { width: 24, height: 16, obstacles: [] },
    units,
    triggers: [{
      trigger_index: 0,
      name: "Starting",
      looping: false,
      conditions: [],
      effects: [{
        type: "patrol",
        owner: 2,
        x: 20,
        y: 7,
        area: { x1: 2, y1: 2, x2: 6, y2: 12 },
        effect_index: 1,
      }],
    }],
    disableAiOrders: true,
  });
}


function visibilityCadenceWorld(targetX, cohortCount = 1, behaviorFamily = "onager") {
  const durable = { ...rangedMechanics, hp: 10_000 };
  const patrolUnits = Array.from({ length: cohortCount }, (_, index) => (
    createUnitState({
      referenceId: index + 1,
      owner: 2,
      x: 4,
      y: 8 + index * 0.25,
      facing: 0,
      mechanics: durable,
      ...(behaviorFamily === null ? {} : { behaviorFamily }),
      acquisitionRank: index,
      acquisitionCount: cohortCount,
    })
  ));
  return createWorld({
    ratio: "visibility-cadence-test",
    map: { width: 24, height: 16, obstacles: [] },
    units: [
      ...patrolUnits,
      createUnitState({
        referenceId: 100,
        owner: 3,
        x: targetX,
        y: 8,
        facing: Math.PI,
        mechanics: durable,
        acquisitionRank: 0,
        acquisitionCount: 1,
      }),
    ],
    triggers: [{
      trigger_index: 0,
      name: "Starting",
      looping: false,
      conditions: [],
      effects: [{
        type: "patrol",
        owner: 2,
        x: 20,
        y: 8,
        area: { x1: 2, y1: 6, x2: 6, y2: 10 },
        effect_index: 1,
      }],
    }],
    disableAiOrders: true,
  });
}


function detachedCadenceWorld(behaviorFamily = "onager") {
  const durable = { ...rangedMechanics, hp: 10_000 };
  const patrolUnits = [
    [1, 4, 5],
    [2, 4, 5.5],
    [3, 4, 9],
  ].map(([referenceId, x, y], index) => createUnitState({
    referenceId,
    owner: 2,
    x,
    y,
    facing: 0,
    mechanics: durable,
    ...(behaviorFamily === null ? {} : { behaviorFamily }),
    acquisitionRank: index,
    acquisitionCount: 3,
  }));
  return createWorld({
    ratio: "detached-cadence-test",
    map: { width: 32, height: 16, obstacles: [] },
    units: [
      ...patrolUnits,
      createUnitState({
        referenceId: 100,
        owner: 3,
        x: 22,
        y: 5,
        facing: Math.PI,
        mechanics: durable,
        acquisitionRank: 0,
        acquisitionCount: 1,
      }),
    ],
    triggers: [{
      trigger_index: 0,
      name: "Starting",
      looping: false,
      conditions: [],
      effects: [{
        type: "patrol",
        owner: 2,
        x: 28,
        y: 7,
        area: { x1: 2, y1: 2, x2: 6, y2: 12 },
        effect_index: 1,
      }],
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


test("opening patrol honors command reaction then moves at sourced speed", () => {
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
  for (let tick = 0; tick < 59; tick += 1) {
    world = stepWorld(world);
    assert.deepEqual(world.units.map(({ x, y }) => [x, y]), initial);
  }
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


test("ranged patrol opens on a principal central lane with bounded flank fallback", () => {
  let world = principalRangedPatrolWorld();
  const firstTargetByActor = new Map();
  for (let tick = 0; tick < 900 && firstTargetByActor.size < 7; tick += 1) {
    world = stepWorld(world);
    for (const current of world.events) {
      if (current.type !== "pursuit-acquired"
          || current.actorId > 7
          || firstTargetByActor.has(current.actorId)) continue;
      firstTargetByActor.set(current.actorId, current.targetId);
    }
  }
  assert.equal(firstTargetByActor.size, 7);
  const targetCounts = new Map();
  for (const targetId of firstTargetByActor.values()) {
    targetCounts.set(targetId, (targetCounts.get(targetId) ?? 0) + 1);
  }
  const centralCount = targetCounts.get(102) ?? 0;
  const largestFallback = Math.max(
    targetCounts.get(101) ?? 0,
    targetCounts.get(103) ?? 0,
  );
  assert.ok(
    centralCount > largestFallback,
    `central lane should dominate the opening locks: ${JSON.stringify([...targetCounts])}`,
  );
  assert.ok(targetCounts.size <= 2, "opening fallback must remain a bounded lane");
});


test("an Onager-family patrol scans sooner when a hostile is already in shared LOS", () => {
  const visible = visibilityCadenceWorld(12);
  const hidden = visibilityCadenceWorld(14);
  const visibleScan = visible.units.find(({ referenceId }) => referenceId === 1)
    .moveOrder.nextOpeningScanTick;
  const hiddenScan = hidden.units.find(({ referenceId }) => referenceId === 1)
    .moveOrder.nextOpeningScanTick;
  assert.ok(visibleScan >= 0.66 * 60 && visibleScan <= 0.72 * 60);
  assert.ok(hiddenScan >= 1.60 * 60 && hiddenScan <= 1.66 * 60);
  assert.ok(visibleScan < hiddenScan);
});


test("a seeded Onager-family subset services the early shared-LOS scan", () => {
  const world = visibilityCadenceWorld(12, 3);
  const scans = world.units.filter(({ owner }) => owner === 2)
    .map(({ moveOrder }) => moveOrder.nextOpeningScanTick);
  assert.equal(scans.filter((tick) => tick < 1.60 * 60).length, 1);
  assert.equal(scans.filter((tick) => tick >= 1.60 * 60).length, 2);
});


test("ordinary ranged units do not inherit the Onager-family opening scan", () => {
  const world = visibilityCadenceWorld(12, 1, null);
  const scan = world.units.find(({ referenceId }) => referenceId === 1)
    .moveOrder.nextOpeningScanTick;
  assert.ok(scan >= 1.60 * 60 && scan <= 1.66 * 60);
});


test("only detached Onager-family members receive the long first-scan tail", () => {
  const onagerFamily = detachedCadenceWorld();
  const ordinaryRanged = detachedCadenceWorld(null);
  const onagerScan = onagerFamily.units.find(({ referenceId }) => referenceId === 3)
    .moveOrder.nextOpeningScanTick;
  const ordinaryScan = ordinaryRanged.units.find(({ referenceId }) => referenceId === 3)
    .moveOrder.nextOpeningScanTick;
  assert.ok(onagerScan >= 5.5 * 60);
  assert.ok(ordinaryScan >= 1.60 * 60 && ordinaryScan <= 1.66 * 60);
});


test("ranged-vs-melee scenario patrol suspends its point during combat", () => {
  assertScenarioPatrolBecomesCombat(scenarioPatrolWorld(rangedMechanics, mechanics));
});
