import assert from "node:assert/strict";
import test from "node:test";

import { planPreventiveContactSteering } from "../src/combat/contact-graph-steering.js";


const STEP = 0.9 / 60;
const MAP = Object.freeze({ width: 10, height: 10, obstacles: Object.freeze([]) });
const MECHANICS = Object.freeze({
  attack_range_tiles: 0,
  collision_size_tiles: Object.freeze({ x: 0.2, y: 0.2 }),
  min_collision_size_multiplier: 0.8,
  speed_tiles_per_second: 0.9,
});


function unit({
  referenceId,
  owner = 3,
  x,
  y,
  pursuitTargetId = 90,
  avoidance = null,
  attackRange = 0,
  speed = MECHANICS.speed_tiles_per_second,
  reload = 2,
}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    alive: true,
    pursuitTargetId,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance,
    mechanics: attackRange === 0 && speed === MECHANICS.speed_tiles_per_second
      ? MECHANICS : Object.freeze({
      ...MECHANICS,
      attack_range_tiles: attackRange,
      speed_tiles_per_second: speed,
      reload_seconds: reload,
    }),
  });
}


function proposal(referenceId, dx = 0, dy = 0) {
  return Object.freeze({ referenceId, dx, dy });
}


function byReference(result) {
  return new Map(result.proposals.map((row) => [row.referenceId, row]));
}


test("a clear step and a single edge admission preserve the direct pursuit heading", () => {
  const target = unit({ referenceId: 90, owner: 2, x: 8, y: 2, pursuitTargetId: null });
  const mover = unit({ referenceId: 1, x: 2, y: 2 });
  const oneFutureNeighbor = unit({ referenceId: 2, x: 2.7, y: 2, pursuitTargetId: null });
  const direct = proposal(1, STEP, 0);

  const clear = planPreventiveContactSteering(
    [mover, target],
    [direct, proposal(90)],
    MAP,
    { owner: 3 },
  );
  assert.deepEqual(byReference(clear).get(1), direct);
  assert.deepEqual(clear.steered, []);

  const edge = planPreventiveContactSteering(
    [mover, oneFutureNeighbor, target],
    [direct, proposal(2), proposal(90)],
    MAP,
    { owner: 3 },
  );
  assert.deepEqual(byReference(edge).get(1), direct);
  assert.deepEqual(edge.steered, []);
});


test("an isolated arrival takes a full-speed tangent instead of closing an allied triangle", () => {
  const target = unit({ referenceId: 90, owner: 2, x: 8, y: 2, pursuitTargetId: null });
  const mover = unit({ referenceId: 1, x: 2, y: 2 });
  const upper = unit({ referenceId: 2, x: 2.7, y: 1.85, pursuitTargetId: null });
  const lower = unit({ referenceId: 3, x: 2.7, y: 2.15, pursuitTargetId: null });

  const result = planPreventiveContactSteering(
    [mover, upper, lower, target],
    [proposal(1, STEP, 0), proposal(2), proposal(3), proposal(90)],
    MAP,
    { owner: 3 },
  );
  const movement = byReference(result).get(1);

  assert.ok(Math.abs(movement.dy) > 1e-12);
  assert.ok(movement.dx > 0);
  assert.ok(Math.abs(Math.hypot(movement.dx, movement.dy) - STEP) < 1e-12);
  assert.deepEqual(result.steered.map(({ referenceId, reason }) => ({ referenceId, reason })), [
    { referenceId: 1, reason: "compact-contact" },
  ]);
});


test("steering strength scales the same correction continuously without changing speed", () => {
  const target = unit({ referenceId: 90, owner: 2, x: 8, y: 2, pursuitTargetId: null });
  const mover = unit({ referenceId: 1, x: 2, y: 2 });
  const upper = unit({ referenceId: 2, x: 2.7, y: 1.85, pursuitTargetId: null });
  const lower = unit({ referenceId: 3, x: 2.7, y: 2.15, pursuitTargetId: null });
  const snapshot = [mover, upper, lower, target];
  const proposals = [proposal(1, STEP, 0), proposal(2), proposal(3), proposal(90)];

  const full = byReference(planPreventiveContactSteering(
    snapshot, proposals, MAP, { owner: 3, strength: 1 },
  )).get(1);
  const half = byReference(planPreventiveContactSteering(
    snapshot, proposals, MAP, { owner: 3, strength: 0.5 },
  )).get(1);
  const off = byReference(planPreventiveContactSteering(
    snapshot, proposals, MAP, { owner: 3, strength: 0 },
  )).get(1);
  const fullAngle = Math.atan2(full.dy, full.dx);
  const halfAngle = Math.atan2(half.dy, half.dx);

  assert.ok(Math.abs(fullAngle) > 1e-12);
  assert.ok(Math.abs(halfAngle - fullAngle * 0.5) < 1e-12);
  assert.ok(Math.abs(Math.hypot(half.dx, half.dy) - STEP) < 1e-12);
  assert.deepEqual(off, proposal(1, STEP, 0));
  assert.throws(() => planPreventiveContactSteering(
    snapshot, proposals, MAP, { owner: 3, strength: -0.01 },
  ), /steering strength must be between 0 and 1/);
  assert.throws(() => planPreventiveContactSteering(
    snapshot, proposals, MAP, { owner: 3, strength: 1.01 },
  ), /steering strength must be between 0 and 1/);
});


test("a direct four-unit compact admission is diverted without slowing the mover", () => {
  const target = unit({ referenceId: 90, owner: 2, x: 8, y: 2, pursuitTargetId: null });
  const mover = unit({ referenceId: 1, x: 2, y: 2 });
  const compact = [
    unit({ referenceId: 2, x: 2.7, y: 1.8, pursuitTargetId: null }),
    unit({ referenceId: 3, x: 2.7, y: 2.0, pursuitTargetId: null }),
    unit({ referenceId: 4, x: 2.7, y: 2.2, pursuitTargetId: null }),
  ];
  const direct = proposal(1, STEP, 0);

  const result = planPreventiveContactSteering(
    [mover, ...compact, target],
    [direct, ...compact.map(({ referenceId }) => proposal(referenceId)), proposal(90)],
    MAP,
    { owner: 3 },
  );
  const movement = byReference(result).get(1);

  assert.notDeepEqual(movement, direct);
  assert.ok(Math.abs(Math.hypot(movement.dx, movement.dy) - STEP) < 1e-12);
  assert.equal(result.steered[0].reason, "compact-contact");
});


test("reach melee near its target may form a two-deep wedge but not enter a three-ally stack", () => {
  const target = unit({ referenceId: 90, owner: 2, x: 3.8, y: 2, pursuitTargetId: null });
  const mover = unit({ referenceId: 1, x: 2, y: 2, attackRange: 1 });
  const upper = unit({ referenceId: 2, x: 2.7, y: 1.85, pursuitTargetId: null });
  const lower = unit({ referenceId: 3, x: 2.7, y: 2.15, pursuitTargetId: null });
  const direct = proposal(1, STEP, 0);

  const wedge = planPreventiveContactSteering(
    [mover, upper, lower, target],
    [direct, proposal(2), proposal(3), proposal(90)],
    MAP,
    { owner: 3 },
  );
  assert.deepEqual(byReference(wedge).get(1), direct);
  assert.deepEqual(wedge.steered, []);

  const middle = unit({ referenceId: 4, x: 2.7, y: 2, pursuitTargetId: null });
  const crowded = planPreventiveContactSteering(
    [mover, upper, middle, lower, target],
    [direct, proposal(2), proposal(4), proposal(3), proposal(90)],
    MAP,
    { owner: 3 },
  );
  assert.notDeepEqual(byReference(crowded).get(1), direct);
  assert.equal(crowded.steered[0].reason, "compact-contact");
});


test("reach melee still avoids forming a wedge while it is far from attack range", () => {
  const target = unit({ referenceId: 90, owner: 2, x: 8, y: 2, pursuitTargetId: null });
  const mover = unit({ referenceId: 1, x: 2, y: 2, attackRange: 1 });
  const upper = unit({ referenceId: 2, x: 2.7, y: 1.85, pursuitTargetId: null });
  const lower = unit({ referenceId: 3, x: 2.7, y: 2.15, pursuitTargetId: null });
  const direct = proposal(1, STEP, 0);

  const result = planPreventiveContactSteering(
    [mover, upper, lower, target],
    [direct, proposal(2), proposal(3), proposal(90)],
    MAP,
    { owner: 3 },
  );

  assert.notDeepEqual(byReference(result).get(1), direct);
  assert.equal(result.steered[0].reason, "compact-contact");
});


test("reach melee still steers when sourced closure per reload exceeds extra reach", () => {
  const target = unit({
    referenceId: 90, owner: 2, x: 3.8, y: 2, pursuitTargetId: null, speed: 0.9,
  });
  const mover = unit({
    referenceId: 1, x: 2, y: 2, attackRange: 1, speed: 1.6, reload: 2,
  });
  const upper = unit({ referenceId: 2, x: 2.7, y: 1.85, pursuitTargetId: null });
  const lower = unit({ referenceId: 3, x: 2.7, y: 2.15, pursuitTargetId: null });
  const direct = proposal(1, STEP, 0);

  const result = planPreventiveContactSteering(
    [mover, upper, lower, target],
    [direct, proposal(2), proposal(3), proposal(90)],
    MAP,
    { owner: 3 },
  );

  assert.notDeepEqual(byReference(result).get(1), direct);
  assert.equal(result.steered[0].reason, "compact-contact");
});


test("planning is invariant to snapshot and proposal order", () => {
  const snapshot = [
    unit({ referenceId: 1, x: 2, y: 2 }),
    unit({ referenceId: 2, x: 2.7, y: 1.85, pursuitTargetId: null }),
    unit({ referenceId: 3, x: 2.7, y: 2.15, pursuitTargetId: null }),
    unit({ referenceId: 90, owner: 2, x: 8, y: 2, pursuitTargetId: null }),
  ];
  const proposals = [
    proposal(1, STEP, 0), proposal(2), proposal(3), proposal(90),
  ];

  const forward = planPreventiveContactSteering(snapshot, proposals, MAP, { owner: 3 });
  const reversed = planPreventiveContactSteering(
    [...snapshot].reverse(),
    [...proposals].reverse(),
    MAP,
    { owner: 3 },
  );
  const normalize = (result) => ({
    proposals: [...result.proposals].sort((a, b) => a.referenceId - b.referenceId),
    steered: [...result.steered].sort((a, b) => a.referenceId - b.referenceId),
  });

  assert.deepEqual(normalize(forward), normalize(reversed));
});
