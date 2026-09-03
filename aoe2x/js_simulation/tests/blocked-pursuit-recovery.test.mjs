import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createWorld, stepWorld } from "../src/combat/world.js";


const hcaMechanics = JSON.parse(await readFile(new URL(
  "../fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json",
  import.meta.url,
), "utf8"));
const stoppedHcaMechanics = Object.freeze({ ...hcaMechanics, speed_tiles_per_second: 0 });


function unit(referenceId, owner, x, y, {
  mechanics = hcaMechanics,
  pursuitTargetId = null,
} = {}) {
  return {
    referenceId,
    owner,
    x,
    y,
    facing: 0,
    mechanics,
    unitMaster: 474,
    hp: mechanics.hit_points,
    alive: true,
    pursuitTargetId,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
    action: "idle",
    actionTimers: { windup: 0, reload: 0, acquire: 0, swing: 0 },
  };
}


test("a ranged pursuer retries five blocked steps, then reacquires a new route", () => {
  let world = createWorld({
    ratio: "blocked-pursuit-recovery",
    map: {
      width: 14,
      height: 14,
      obstacles: [
        [1.5, 4.5], [2, 4.5], [2.5, 4.5],
        [1.5, 5], [2.5, 5],
        [1.5, 5.5], [2, 5.5], [2.5, 5.5],
      ].map(([x, y], index) => ({ referenceId: 900 + index, x, y, radius: 0.25 })),
    },
    units: [
      unit(1, 3, 2, 5, { pursuitTargetId: 100 }),
      unit(100, 2, 10, 5, { mechanics: stoppedHcaMechanics }),
      unit(101, 2, 2, 13.2, { mechanics: stoppedHcaMechanics }),
    ],
  });

  for (let tick = 1; tick <= 4; tick += 1) {
    world = stepWorld(world);
    assert.equal(world.units.find(({ referenceId }) => referenceId === 1).pursuitTargetId, 100);
  }

  world = stepWorld(world);
  assert.ok(world.events.some(({ type, actorId, failedAttempts }) => (
    (type === "pursuit-route-planned" || type === "pursuit-retarget-requested")
      && actorId === 1
      && failedAttempts === 5
  )));

  world = stepWorld(world);
  assert.equal(world.units.find(({ referenceId }) => referenceId === 1).pursuitTargetId, 101);
  assert.ok(world.events.some(({ type, actorId, targetId, reason }) => (
    type === "pursuit-acquired"
      && actorId === 1
      && targetId === 101
      && reason === "blocked-route-unavailable"
  )));
});


test("a ranged pair compresses through its allied lane without entering retry recovery", () => {
  let world = createWorld({
    ratio: "blocked-allied-ingress-recovery",
    map: { width: 14, height: 14, obstacles: [] },
    units: [
      unit(1, 3, 3.8, 5, { pursuitTargetId: 100 }),
      unit(2, 3, 4.3, 5, { pursuitTargetId: 100 }),
      unit(100, 2, 12, 5, { mechanics: stoppedHcaMechanics }),
    ],
  });

  // Pairwise ranged compression is compliant. A tangent is only required when
  // higher-order crowding makes forward movement expensive, so this isolated
  // rear unit must keep progressing without waiting for five failed steps.
  const initial = world.units.find(({ referenceId }) => referenceId === 1);
  for (let tick = 1; tick <= 13; tick += 1) world = stepWorld(world);

  const rear = world.units.find(({ referenceId }) => referenceId === 1);
  assert.ok(rear.x > initial.x, "the rear ranged unit must continue toward attack range");
  assert.equal(world.pursuitRecoveryState.routes.has(1), false);
  assert.equal(world.pursuitRecoveryState.attempts.get(1) ?? 0, 0);
});


test("a ranged crowd local minimum plans a committed route before moving backwards", () => {
  let world = createWorld({
    ratio: "ranged-crowd-local-minimum",
    map: { width: 14, height: 14, obstacles: [] },
    units: [
      unit(1, 3, 1, 5, { pursuitTargetId: 100 }),
      unit(2, 3, 1.05, 4.85, {
        mechanics: stoppedHcaMechanics,
        pursuitTargetId: 100,
      }),
      unit(3, 3, 1.05, 5.15, {
        mechanics: stoppedHcaMechanics,
        pursuitTargetId: 100,
      }),
      unit(100, 2, 10, 5, { mechanics: stoppedHcaMechanics }),
    ],
  });

  world = stepWorld(world);

  const routeEvent = world.events.find(({ type, actorId }) => (
    type === "pursuit-route-planned" && actorId === 1
  ));
  assert.ok(routeEvent, "the geometric local minimum must route on its first tick");
  assert.equal(routeEvent.reason, "ranged-crowd-local-minimum");
  assert.equal(world.pursuitRecoveryState.routes.has(1), true);
  const mover = world.units.find(({ referenceId }) => referenceId === 1);
  const route = world.pursuitRecoveryState.routes.get(1);
  const waypoint = route.waypoints[route.waypointIndex];
  const moved = { x: mover.x - 1, y: mover.y - 5 };
  const routeDirection = { x: waypoint.x - 1, y: waypoint.y - 5 };
  assert.ok(
    moved.x * routeDirection.x + moved.y * routeDirection.y > 0,
    "the same-tick step must follow the committed global route",
  );
});
