import assert from "node:assert/strict";
import test from "node:test";

import { planCohortContactMotion } from "../src/combat/cohort-motion.js";

const map = Object.freeze({ width: 8, height: 8, obstacles: Object.freeze([]) });

function unit(referenceId, owner, x, y, radius = 0.2) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    mechanics: Object.freeze({
      collision_size_tiles: Object.freeze({ x: radius, y: radius }),
    }),
  });
}

function proposal(referenceId, dx, dy) {
  return Object.freeze({ referenceId, dx, dy });
}

test("unblocked cohorts keep their original slot-seeking proposals", () => {
  const units = [unit(1, 2, 1, 1), unit(2, 2, 1, 1.5)];
  const proposals = [proposal(1, 0.1, 0), proposal(2, 0.08, 0.06)];
  const result = planCohortContactMotion({
    units,
    proposals,
    enemies: [unit(9, 3, 6, 6)],
    map,
    preferredTurn: 1,
  });
  assert.deepEqual(result, proposals);
});

test("a single mover is not granted formation escape", () => {
  const units = [unit(1, 2, 1, 1)];
  const proposals = [proposal(1, 0.1, 0)];
  const result = planCohortContactMotion({
    units,
    proposals,
    enemies: [unit(9, 3, 1.45, 1)],
    map,
    preferredTurn: 1,
  });
  assert.deepEqual(result, proposals);
});

test("a contacted cohort takes one preferred full-speed heading", () => {
  const units = [unit(1, 2, 1, 1), unit(2, 2, 1, 1.5), unit(3, 2, 0.8, 1.25)];
  const proposals = [proposal(1, 0.1, 0), proposal(2, 0.1, 0), proposal(3, 0, 0)];
  const before = JSON.stringify({ units, proposals });
  const result = planCohortContactMotion({
    units,
    proposals,
    enemies: [unit(9, 3, 1.45, 1.25)],
    map,
    preferredTurn: 1,
  });

  assert.ok(result[0].dx > 0 && result[0].dy > 0);
  assert.ok(Math.abs(result[0].dx - result[1].dx) < 1e-12);
  assert.ok(Math.abs(result[0].dy - result[1].dy) < 1e-12);
  assert.ok(Math.abs(Math.hypot(result[0].dx, result[0].dy) - 0.1) < 1e-12);
  assert.deepEqual(result[2], { referenceId: 3, dx: 0, dy: 0 });
  assert.equal(JSON.stringify({ units, proposals }), before, "planning must not mutate inputs");
});

test("ring direction resolves a symmetric detour without RNG", () => {
  const units = [unit(1, 2, 1, 1), unit(2, 2, 1, 1.5)];
  const proposals = [proposal(1, 0.1, 0), proposal(2, 0.1, 0)];
  const enemies = [unit(9, 3, 1.45, 1.25)];
  const left = planCohortContactMotion({
    units, proposals, enemies, map, preferredTurn: 1,
  });
  const right = planCohortContactMotion({
    units, proposals, enemies, map, preferredTurn: -1,
  });
  assert.ok(left[0].dy > 0);
  assert.ok(right[0].dy < 0);
  assert.ok(Math.abs(Math.hypot(left[0].dx, left[0].dy) - 0.1) < 1e-12);
  assert.ok(Math.abs(Math.hypot(right[0].dx, right[0].dy) - 0.1) < 1e-12);
});

test("fully enclosed cohorts still return a deterministic collision-layer input", () => {
  const units = [unit(1, 2, 1, 1), unit(2, 2, 1, 1.5)];
  const proposals = [proposal(1, 0.1, 0), proposal(2, 0.1, 0)];
  const enemies = [
    unit(9, 3, 1.35, 1.25, 0.6),
    unit(10, 3, 0.65, 1.25, 0.6),
  ];
  const first = planCohortContactMotion({
    units, proposals, enemies, map, preferredTurn: 1,
  });
  const second = planCohortContactMotion({
    units, proposals, enemies, map, preferredTurn: 1,
  });
  assert.deepEqual(second, first);
  assert.equal(first.length, proposals.length);
  assert.deepEqual(first.map(({ referenceId }) => referenceId), [1, 2]);
});
