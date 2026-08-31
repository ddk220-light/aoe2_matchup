import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";


const heavyCavArcher = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json",
  import.meta.url,
), "utf8"));
const eliteGbeto = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/elite_gbeto_malians_imperial.json",
  import.meta.url,
), "utf8"));


function unit({ referenceId, owner, x, y, mechanics }) {
  return createUnitState({
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics,
    actionTimers: { windup: 0, reload: 0, swing: 0, acquire: 0 },
  });
}


test("RvR AI target pressure prevents every equidistant shooter piling onto one unit", () => {
  const world = createWorld({
    ratio: "3v2-ranged-pressure-test",
    mapHash: "ranged-pressure-test-map",
    map: { width: 20, height: 20, obstacles: [] },
    rangedTargetPressureOwner: 3,
    units: [
      unit({ referenceId: 100, owner: 2, x: 4.8, y: 5, mechanics: heavyCavArcher }),
      unit({ referenceId: 101, owner: 2, x: 5.2, y: 5, mechanics: heavyCavArcher }),
      unit({ referenceId: 200, owner: 3, x: 4.6, y: 10, mechanics: eliteGbeto }),
      unit({ referenceId: 201, owner: 3, x: 5, y: 10, mechanics: eliteGbeto }),
      unit({ referenceId: 202, owner: 3, x: 5.4, y: 10, mechanics: eliteGbeto }),
    ],
  });

  const next = stepWorld(world);
  const targets = next.units
    .filter(({ owner }) => owner === 3)
    .map(({ pursuitTargetId }) => pursuitTargetId);

  assert.deepEqual(new Set(targets), new Set([100, 101]));
  assert.ok(Math.max(
    targets.filter((targetId) => targetId === 100).length,
    targets.filter((targetId) => targetId === 101).length,
  ) <= 2);
});


test("the manual RvR side fires at an in-range target instead of chasing a distant lock", () => {
  const world = createWorld({
    ratio: "1v2-ranged-opportunity-test",
    mapHash: "ranged-opportunity-test-map",
    map: { width: 20, height: 20, obstacles: [] },
    rangedOpportunityRetargetOwner: 2,
    units: [
      Object.freeze({
        ...unit({ referenceId: 100, owner: 2, x: 5, y: 5, mechanics: heavyCavArcher }),
        pursuitTargetId: 201,
      }),
      unit({ referenceId: 200, owner: 3, x: 5, y: 10, mechanics: eliteGbeto }),
      unit({ referenceId: 201, owner: 3, x: 16, y: 16, mechanics: eliteGbeto }),
    ],
  });

  const next = stepWorld(world);
  const shooter = next.units.find(({ referenceId }) => referenceId === 100);

  assert.equal(shooter.pursuitTargetId, 200);
  assert.equal(shooter.x, 5);
  assert.equal(shooter.y, 5);
});


test("the RvR AI side preserves an unreleased windup when its target dies", () => {
  const attacker = Object.freeze({
    ...unit({ referenceId: 200, owner: 3, x: 5, y: 10, mechanics: eliteGbeto }),
    pursuitTargetId: 100,
    engagedTargetId: 100,
    attackTargetId: 100,
    action: "attacking",
    actionTimers: Object.freeze({ windup: 30, reload: 0, swing: 30, acquire: 0 }),
  });
  let world = createWorld({
    ratio: "1v2-ranged-windup-retarget-test",
    mapHash: "ranged-windup-retarget-test-map",
    map: { width: 20, height: 20, obstacles: [] },
    rangedWindupRetargetOwner: 3,
    units: [
      unit({ referenceId: 100, owner: 2, x: 5, y: 5, mechanics: heavyCavArcher }),
      unit({ referenceId: 101, owner: 2, x: 5.5, y: 5, mechanics: heavyCavArcher }),
      attacker,
    ],
  });
  world = Object.freeze({
    ...world,
    units: Object.freeze(world.units.map((entry) => {
      if (entry.referenceId === 100) return Object.freeze({
        ...entry,
        hp: 0,
        alive: false,
        action: "dead",
        pursuitTargetId: null,
        engagedTargetId: null,
        attackTargetId: null,
        actionTimers: Object.freeze({ windup: 0, reload: 0, swing: 0, acquire: 0 }),
      });
      if (entry.referenceId === 200) return Object.freeze({
        ...entry,
        actionTimers: Object.freeze({ ...entry.actionTimers, reload: 90 }),
      });
      return entry;
    })),
  });

  const next = stepWorld(world);
  const retargeted = next.units.find(({ referenceId }) => referenceId === 200);

  assert.equal(retargeted.action, "attacking");
  assert.equal(retargeted.pursuitTargetId, 101);
  assert.equal(retargeted.attackTargetId, 101);
  assert.equal(retargeted.actionTimers.swing, 31);
  assert.equal(next.events.some(({ type, actorId, targetId }) => (
    type === "attack-retargeted" && actorId === 200 && targetId === 101
  )), true);
});


test("an isolated ranged pair compresses below its old one-lane DAT floor", () => {
  const world = createWorld({
    ratio: "2v1-ranged-ingress-test",
    mapHash: "ranged-ingress-test-map",
    map: { width: 20, height: 20, obstacles: [] },
    units: [
      unit({ referenceId: 100, owner: 2, x: 5, y: 4, mechanics: heavyCavArcher }),
      unit({ referenceId: 200, owner: 3, x: 5, y: 10.44, mechanics: eliteGbeto }),
      unit({ referenceId: 201, owner: 3, x: 5, y: 10.84, mechanics: eliteGbeto }),
    ],
  });

  let next = world;
  for (let tick = 0; tick < 10; tick += 1) {
    next = stepWorld(next);
  }
  const front = next.units.find(({ referenceId }) => referenceId === 200);
  const rear = next.units.find(({ referenceId }) => referenceId === 201);

  const separation = Math.abs(front.y - rear.y);
  assert.ok(separation < 0.4 - 1e-9, JSON.stringify({ front, rear, events: next.events }));
  assert.ok(separation >= 0.4 * 0.025 - 1e-9);
  assert.equal(next.pursuitRecoveryState.attempts.get(201) ?? 0, 0);
});
