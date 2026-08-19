import assert from "node:assert/strict";
import test from "node:test";

import { planChaseAim, planMoveAim } from "../src/combat/chase-path.js";
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
