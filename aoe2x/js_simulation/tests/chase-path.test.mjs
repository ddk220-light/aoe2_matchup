import assert from "node:assert/strict";
import test from "node:test";

import {
  advancePersistentChaseRoute,
  planChaseAim,
  planMoveAim,
  planPersistentChaseRoute,
} from "../src/combat/chase-path.js";
import { createPairInteractionSnapshot } from "../src/combat/pair-interactions.js";

const map = Object.freeze({ width: 8, height: 8, obstacles: Object.freeze([]) });

function body(x, y, radius = 0.2, owner = undefined, unitMaster = undefined) {
  return Object.freeze({
    x,
    y,
    ...(owner === undefined ? {} : { owner }),
    ...(unitMaster === undefined ? {} : { unitMaster }),
    mechanics: Object.freeze({
      collision_size_tiles: Object.freeze({ x: radius, y: radius }),
    }),
  });
}

function dynamicBody(referenceId, x, y, radius, owner, unitMaster) {
  return Object.freeze({ referenceId, ...body(x, y, radius, owner, unitMaster) });
}

test("coordinate path keeps a clear move order on its exact direct route", () => {
  const mover = body(1, 1);
  const goal = Object.freeze({ x: 5, y: 1 });
  assert.equal(planMoveAim(mover, goal, [], map), null);
});

test("coordinate path deterministically routes around a blocking body", () => {
  const mover = body(1, 1);
  const goal = Object.freeze({ x: 5, y: 1 });
  const obstacle = body(3, 1, 0.3);
  const before = JSON.stringify({ mover, goal, obstacle });
  const first = planMoveAim(mover, goal, [obstacle], map);
  const second = planMoveAim(mover, goal, [obstacle], map);
  assert.deepEqual(first, second);
  assert.ok(first && first.stand !== true, "a reachable detour must produce a waypoint");
  assert.notEqual(first.y, 1, "the waypoint must leave the blocked direct row");
  assert.equal(JSON.stringify({ mover, goal, obstacle }), before, "planning must be pure");
});

test("coordinate path routes around a static map obstacle", () => {
  const mover = body(1, 1);
  const goal = Object.freeze({ x: 5, y: 1 });
  const obstacleMap = Object.freeze({
    width: 8,
    height: 8,
    obstacles: Object.freeze([
      Object.freeze({ referenceId: 9000, x: 3, y: 1, radius: 0.5 }),
    ]),
  });

  const waypoint = planMoveAim(mover, goal, [], obstacleMap);

  assert.ok(waypoint && waypoint.stand !== true, "a reachable detour must produce a waypoint");
  assert.notEqual(waypoint.y, 1, "the waypoint must leave the blocked direct row");
});

test("coordinate path stands when surrounding bodies leave no reachable progress", () => {
  const mover = body(1, 1);
  const goal = Object.freeze({ x: 5, y: 1 });
  const obstacles = [
    body(0.75, 0.75, 0.3), body(1, 0.75, 0.3), body(1.25, 0.75, 0.3),
    body(0.75, 1, 0.3), body(1.25, 1, 0.3),
    body(0.75, 1.25, 0.3), body(1, 1.25, 0.3), body(1.25, 1.25, 0.3),
  ];
  assert.deepEqual(planMoveAim(mover, goal, obstacles, map), { stand: true });
});


test("coordinate path keeps moving when only dynamic enemies temporarily box in the mover", () => {
  const mover = dynamicBody(1, 1, 1, 0.2, 2, 4);
  const goal = Object.freeze({ x: 5, y: 1 });
  const enemies = [
    dynamicBody(3, 0.75, 0.75, 0.3, 3, 75),
    dynamicBody(4, 1, 0.75, 0.3, 3, 75),
    dynamicBody(5, 1.25, 0.75, 0.3, 3, 75),
    dynamicBody(6, 0.75, 1, 0.3, 3, 75),
    dynamicBody(7, 1.25, 1, 0.3, 3, 75),
    dynamicBody(8, 0.75, 1.25, 0.3, 3, 75),
    dynamicBody(9, 1, 1.25, 0.3, 3, 75),
    dynamicBody(10, 1.25, 1.25, 0.3, 3, 75),
  ];

  assert.equal(planMoveAim(mover, goal, enemies, map), null);
});


test("chase path leaves friendly crowd bodies to the local collision layers", () => {
  const mover = body(1, 1, 0.2, 3);
  const target = body(5, 1, 0.2, 2);
  const allies = [
    body(0.75, 0.75, 0.3, 3), body(1, 0.75, 0.3, 3), body(1.25, 0.75, 0.3, 3),
    body(0.75, 1, 0.3, 3), body(1.25, 1, 0.3, 3),
    body(0.75, 1.25, 0.3, 3), body(1, 1.25, 0.3, 3), body(1.25, 1.25, 0.3, 3),
  ];

  assert.equal(planChaseAim(mover, target, allies, map), null);
});


test("chase path falls back to live pursuit when only dynamic enemies box in the mover", () => {
  const mover = dynamicBody(1, 1, 1, 0.2, 3, 75);
  const target = dynamicBody(2, 5, 1, 0.2, 2, 4);
  const enemies = [
    dynamicBody(3, 0.75, 0.75, 0.3, 2, 4),
    dynamicBody(4, 1, 0.75, 0.3, 2, 4),
    dynamicBody(5, 1.25, 0.75, 0.3, 2, 4),
    dynamicBody(6, 0.75, 1, 0.3, 2, 4),
    dynamicBody(7, 1.25, 1, 0.3, 2, 4),
    dynamicBody(8, 0.75, 1.25, 0.3, 2, 4),
    dynamicBody(9, 1, 1.25, 0.3, 2, 4),
    dynamicBody(10, 1.25, 1.25, 0.3, 2, 4),
  ];

  assert.equal(planChaseAim(mover, target, enemies, map), null);
});


test("chase path can leave a coarse start cell whose center is blocked but mover position is legal", () => {
  const obstacleMap = Object.freeze({
    width: 16,
    height: 16,
    obstacles: Object.freeze([
      Object.freeze({ referenceId: 1604, x: 9, y: 7, radius: 1.5 }),
      Object.freeze({ referenceId: 1579, x: 10.5, y: 6.5, radius: 0.5 }),
    ]),
  });
  const mover = body(10.722707518408344, 5.754245097763453, 0.2, 3);
  const target = body(11.769334713132302, 6.293161375204873, 0.2, 2);

  const plan = planChaseAim(mover, target, [], obstacleMap);

  assert.ok(plan === null || plan.stand !== true);
});


test("chase path omits only a reserved enemy-transit blocker", () => {
  const mover = dynamicBody(1, 1, 1, 0.2, 3, 75);
  const target = dynamicBody(3, 5, 1, 0.2, 2, 4);
  const reserved = dynamicBody(2, 3, 1, 0.2, 2, 4);
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", Object.freeze({
      leftId: 1,
      rightId: 2,
      kind: "enemy-transit",
      collisionExtent: 0.2,
      attackSurfaceExtent: 0.4,
      pathObstructs: false,
      mayDeepen: true,
      initiatorId: 1,
      targetId: 3,
      acquiredTick: 10,
    })]]),
  });

  assert.ok(planChaseAim(mover, target, [reserved], map));
  assert.equal(
    planChaseAim(mover, target, [reserved], map, { pairInteractions }),
    null,
  );
});


test("persistent chase route ends at clear egress and returns to live target tracking", () => {
  const mover = dynamicBody(1, 1, 4, 0.2, 3, 75);
  const target = dynamicBody(2, 6, 4, 0.2, 2, 4);
  const blocker = dynamicBody(3, 3.5, 4, 0.35, 2, 4);

  const route = planPersistentChaseRoute(mover, target, [blocker], map);

  assert.ok(route && route.waypoints.length >= 2);
  const egress = route.waypoints.at(-1);
  assert.ok(
    Math.max(Math.abs(egress.x - target.x), Math.abs(egress.y - target.y)) > 0.5,
    "the detour must end before the moving target's old stop envelope",
  );
  assert.ok(
    Math.abs(egress.y - blocker.y) >= 0.5,
    "the egress must clear the blocking body's inflated corridor",
  );
});


test("persistent chase keeps the direct line through one transit-eligible ally", () => {
  const mover = dynamicBody(1, 1, 4, 0.2, 3, 75);
  const target = dynamicBody(2, 6, 4, 0.2, 2, 4);
  const ally = dynamicBody(3, 3.25, 4, 0.2, 3, 75);

  assert.equal(planPersistentChaseRoute(mover, target, [ally], map), null);
});


test("persistent chase route accumulates geometric congestion across an allied pack", () => {
  const mover = dynamicBody(1, 1, 4, 0.2, 3, 75);
  const target = dynamicBody(2, 6, 4, 0.2, 2, 4);
  const single = [dynamicBody(3, 3.25, 4, 0.2, 3, 75)];
  const pack = [
    dynamicBody(3, 3.0, 3.75, 0.2, 3, 75),
    dynamicBody(4, 3.25, 4.0, 0.2, 3, 75),
    dynamicBody(5, 3.0, 4.25, 0.2, 3, 75),
  ];
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:3", Object.freeze({
      leftId: 1,
      rightId: 3,
      kind: "allied-transit",
      collisionExtent: 0,
      attackSurfaceExtent: 0.4,
      pathObstructs: false,
      mayDeepen: true,
      initiatorId: 1,
      targetId: 2,
      acquiredTick: 10,
    })]]),
  });

  const singleRoute = planPersistentChaseRoute(mover, target, single, map, {
    pairInteractions,
  });
  const packRoute = planPersistentChaseRoute(mover, target, pack, map);
  const lateralExtent = (route) => Math.max(
    0,
    ...(route?.waypoints ?? []).map(({ y }) => Math.abs(y - mover.y)),
  );

  assert.ok(packRoute, "a dense allied pack on the direct corridor must create a route");
  assert.ok(
    lateralExtent(packRoute) > lateralExtent(singleRoute),
    "the accumulated physical penetration cost must route farther around a pack",
  );
});


test("persistent chase route gives attacking and idle allies the same geometry", () => {
  const mover = dynamicBody(1, 1, 4, 0.2, 3, 75);
  const target = dynamicBody(2, 6, 4, 0.2, 2, 4);
  const idleBlocker = dynamicBody(3, 3.25, 4, 0.2, 3, 75);
  const attackingBlocker = Object.freeze({
    ...dynamicBody(3, 3.25, 4, 0.2, 3, 75),
    action: "attacking",
  });

  const idleRoute = planPersistentChaseRoute(mover, target, [idleBlocker], map);
  const attackingRoute = planPersistentChaseRoute(mover, target, [attackingBlocker], map);

  assert.deepEqual(attackingRoute, idleRoute);
});


test("persistent chase route respects the one-allied-transit slot while routing", () => {
  const mover = dynamicBody(1, 1, 4, 0.2, 3, 75);
  const target = dynamicBody(2, 6, 4, 0.2, 2, 4);
  const nextBlocker = dynamicBody(4, 3.25, 4, 0.2, 3, 75);
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:3", Object.freeze({
      leftId: 1,
      rightId: 3,
      kind: "allied-transit",
      collisionExtent: 0.2,
      attackSurfaceExtent: 0.4,
      pathObstructs: false,
      mayDeepen: true,
      initiatorId: 1,
      targetId: null,
      acquiredTick: 10,
    })]]),
  });

  const route = planPersistentChaseRoute(
    mover,
    target,
    [nextBlocker],
    map,
    { pairInteractions },
  );
  const routeWithoutOccupiedSlot = planPersistentChaseRoute(
    mover,
    target,
    [nextBlocker],
    map,
  );
  assert.ok(route);
  assert.notDeepEqual(route, routeWithoutOccupiedSlot);
  assert.ok(route.waypoints.every(({ x, y }) => (
    Math.max(Math.abs(x - nextBlocker.x), Math.abs(y - nextBlocker.y)) >= 0.4 - 1e-12
  )));
});


test("persistent chase routes are deterministic under a vertical mirror", () => {
  const mover = dynamicBody(1, 1.125, 3.125, 0.2, 3, 75);
  const target = dynamicBody(2, 6.125, 3.125, 0.2, 2, 4);
  const obstacles = [
    dynamicBody(3, 3.125, 2.875, 0.2, 3, 75),
    dynamicBody(4, 3.375, 3.125, 0.2, 3, 75),
    dynamicBody(5, 3.125, 3.375, 0.2, 3, 75),
    dynamicBody(6, 3.125, 2.375, 0.3, 3, 75),
    dynamicBody(7, 3.375, 2.625, 0.3, 3, 75),
  ];
  const mirror = (entry) => Object.freeze({ ...entry, y: map.height - entry.y });

  const route = planPersistentChaseRoute(mover, target, obstacles, map);
  const mirrored = planPersistentChaseRoute(
    mirror(mover), mirror(target), obstacles.map(mirror), map,
  );

  assert.deepEqual(
    mirrored.waypoints.map(({ x, y }) => ({ x, y: map.height - y })),
    route.waypoints,
  );
});


test("persistent chase route advances without returning to direct target aim", () => {
  const route = Object.freeze({
    targetReferenceId: 2,
    waypoints: Object.freeze([
      Object.freeze({ x: 2, y: 3 }),
      Object.freeze({ x: 4, y: 3 }),
      Object.freeze({ x: 5.5, y: 4 }),
    ]),
    waypointIndex: 0,
  });

  const advanced = advancePersistentChaseRoute({ x: 2, y: 3 }, route);

  assert.equal(advanced.waypointIndex, 1);
  assert.deepEqual(advanced.waypoints, route.waypoints);
  assert.deepEqual(advanced.waypoints[advanced.waypointIndex], { x: 4, y: 3 });
});


test("persistent route keeps a collision-layer sidestep instead of treating it as a stall", async () => {
  const { persistentRouteMotionStalled } = await import("../src/combat/chase-path.js");
  const before = Object.freeze({ x: 1, y: 1 });
  const waypoint = Object.freeze({ x: 2, y: 1 });

  assert.equal(
    persistentRouteMotionStalled(before, Object.freeze({ x: 1, y: 1.01 }), waypoint),
    false,
  );
  assert.equal(persistentRouteMotionStalled(before, before, waypoint), true);
});
