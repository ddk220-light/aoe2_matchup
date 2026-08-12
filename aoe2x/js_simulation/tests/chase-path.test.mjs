import assert from "node:assert/strict";
import test from "node:test";

import { planMoveAim } from "../src/combat/chase-path.js";

const map = Object.freeze({ width: 8, height: 8, obstacles: Object.freeze([]) });

function body(x, y, radius = 0.2) {
  return Object.freeze({
    x,
    y,
    mechanics: Object.freeze({
      collision_size_tiles: Object.freeze({ x: radius, y: radius }),
    }),
  });
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
