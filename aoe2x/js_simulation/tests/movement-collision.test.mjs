import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { surfaceGap } from "../src/combat/targeting.js";


const movementModuleUrl = new URL("../src/combat/movement.js", import.meta.url);
const collisionModuleUrl = new URL("../src/combat/collision.js", import.meta.url);
const mechanicsUrl = new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json",
  import.meta.url,
);
const mechanics = JSON.parse(await readFile(mechanicsUrl, "utf8"));
const openMap = Object.freeze({ width: 10, height: 10, obstacles: Object.freeze([]) });


function unit({ referenceId, x, y, owner = 2 } = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    alive: true,
    mechanics,
  });
}


function proposal(referenceId, dx, dy) {
  return Object.freeze({ referenceId, dx, dy });
}


async function loadMovement() {
  assert.equal(existsSync(fileURLToPath(movementModuleUrl)), true);
  return import(movementModuleUrl);
}


async function loadCollision() {
  assert.equal(existsSync(fileURLToPath(collisionModuleUrl)), true);
  return import(collisionModuleUrl);
}


function byReference(units) {
  return [...units]
    .sort((a, b) => a.referenceId - b.referenceId)
    .map(({ referenceId, x, y }) => ({ referenceId, x, y }));
}


function assertNonpenetrating(units) {
  for (let i = 0; i < units.length; i += 1) {
    for (let j = i + 1; j < units.length; j += 1) {
      assert.ok(
        surfaceGap(units[i], units[j]) >= -1e-12,
        `${units[i].referenceId} overlaps ${units[j].referenceId}`,
      );
    }
  }
}


test("unblocked pursuit moves exactly speed divided by 60", async () => {
  const { proposeMovement } = await loadMovement();
  const mover = unit({ referenceId: 1, x: 1, y: 1 });
  const target = unit({ referenceId: 2, owner: 3, x: 4, y: 5 });

  const result = proposeMovement(mover, target, 60);

  assert.equal(result.referenceId, 1);
  assert.ok(Math.abs(Math.hypot(result.dx, result.dy) - 1.06 / 60) < 1e-12);
  assert.ok(Math.abs(result.dx - 0.0106) < 1e-12);
  assert.ok(Math.abs(result.dy - 1.06 / 60 * 4 / 5) < 1e-12);
});


test("pursuit is clamped only by the remaining physical surface gap", async () => {
  const { proposeMovement } = await loadMovement();
  const mover = unit({ referenceId: 1, x: 1, y: 1 });
  const target = unit({ referenceId: 2, owner: 3, x: 1.405, y: 1 });

  const result = proposeMovement(mover, target, 60);

  assert.ok(Math.abs(result.dx - 0.005) < 1e-12);
  assert.equal(result.dy, 0);
});


test("head-on Champions split the available gap without penetrating", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 1, x: 4, y: 4 });
  const right = unit({ referenceId: 2, owner: 3, x: 4.42, y: 4 });
  const step = 1.06 / 60;

  const next = resolveMovementProposals(
    [left, right],
    [proposal(1, step, 0), proposal(2, -step, 0)],
    openMap,
  );

  assert.ok(Math.abs(next[0].x - 4.01) < 1e-12);
  assert.ok(Math.abs(next[1].x - 4.41) < 1e-12);
  assertNonpenetrating(next);
});


test("unequal head-on proposals receive an equal-mass normal correction", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 10, x: 4, y: 4 });
  const right = unit({ referenceId: 20, owner: 3, x: 4.42, y: 4 });
  const proposals = [proposal(10, 0.03, 0), proposal(20, -0.01, 0)];

  const forward = resolveMovementProposals([left, right], proposals, openMap);
  const reversed = resolveMovementProposals(
    [right, left],
    [...proposals].reverse(),
    openMap,
  );

  assert.ok(Math.abs(forward[0].x - 4.02) < 1e-12);
  assert.equal(forward[1].x, 4.42);
  assert.deepEqual(byReference(forward), byReference(reversed));
  assertNonpenetrating(forward);
});


test("equal-mass projection redistributes correction after one contributor caps", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 10, x: 4, y: 4 });
  const right = unit({ referenceId: 20, owner: 3, x: 4.41, y: 4 });

  const next = resolveMovementProposals(
    [left, right],
    [proposal(10, 0.04, 0), proposal(20, -0.005, 0)],
    openMap,
  );

  assert.ok(Math.abs(next[0].x - 4.01) < 1e-12);
  assert.equal(next[1].x, 4.41);
  assertNonpenetrating(next);
});


test("a moving Champion uses the available gap without moving a stationary body", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({ referenceId: 1, x: 4, y: 4 });
  const stationary = unit({ referenceId: 2, x: 4.41, y: 4 });

  const next = resolveMovementProposals(
    [mover, stationary],
    [proposal(1, 0.02, 0), proposal(2, 0, 0)],
    openMap,
  );

  assert.ok(Math.abs(next[0].x - 4.01) < 1e-12);
  assert.equal(next[1].x, stationary.x);
  assertNonpenetrating(next);
});


test("contact removes only the inward normal and keeps collision-free tangent", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({ referenceId: 1, x: 4, y: 4 });
  const blocker = unit({ referenceId: 2, x: 4.4, y: 4 });

  const next = resolveMovementProposals(
    [mover, blocker],
    [proposal(1, 0.01, 0.02), proposal(2, 0, 0)],
    openMap,
  );

  assert.equal(next[0].x, mover.x);
  assert.equal(next[0].y, 4.02);
  assert.equal(next[1].x, blocker.x);
  assertNonpenetrating(next);
});


test("a swept tangent from outside contact is not clipped by linear projection", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({
    referenceId: 1,
    x: 4.7403479276431675,
    y: 7.235735058903908,
  });
  const blocker = unit({ referenceId: 2, x: 4.35856, y: 7.358579 });
  const tangent = proposal(1, 0.004701209638722499, 0.0193425586453437);

  const next = resolveMovementProposals(
    [mover, blocker],
    [tangent, proposal(2, 0, 0)],
    openMap,
  );

  assert.ok(Math.abs(next[0].x - mover.x - tangent.dx) < 1e-12);
  assert.ok(Math.abs(next[0].y - mover.y - tangent.dy) < 1e-12);
  assertNonpenetrating(next);
});


test("frozen pair constraints are invariant to snapshot and proposal order", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const snapshot = [
    unit({ referenceId: 30, x: 4.82, y: 4 }),
    unit({ referenceId: 10, x: 4, y: 4 }),
    unit({ referenceId: 20, x: 4.41, y: 4 }),
  ];
  const proposals = [
    proposal(20, 0, 0),
    proposal(30, -0.02, 0),
    proposal(10, 0.02, 0),
  ];

  const forward = resolveMovementProposals(snapshot, proposals, openMap);
  const reversed = resolveMovementProposals(
    [...snapshot].reverse(),
    [...proposals].reverse(),
    openMap,
  );

  assert.deepEqual(byReference(forward), byReference(reversed));
  assertNonpenetrating(forward);
});


test("non-exact starting overlap is rejected as invalid snapshot geometry", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 1, x: 4, y: 4 });
  const right = unit({ referenceId: 2, x: 4.3, y: 4 });

  assert.throws(
    () => resolveMovementProposals(
      [left, right],
      [proposal(1, 0, 0), proposal(2, 0, 0)],
      openMap,
    ),
    /starting overlap.*1.*2/i,
  );
});


test("exactly coincident bodies fail instead of inventing a preferred direction", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const first = unit({ referenceId: 1, x: 4, y: 4 });
  const second = unit({ referenceId: 2, x: 4, y: 4 });

  assert.throws(
    () => resolveMovementProposals(
      [first, second],
      [proposal(1, 0, 0), proposal(2, 0, 0)],
      openMap,
    ),
    /exact overlap.*1.*2/i,
  );
});


test("multi-body contact remains nonpenetrating without a turn preference", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const snapshot = [
    unit({ referenceId: 1, x: 4, y: 4 }),
    unit({ referenceId: 2, x: 4.41, y: 4 }),
    unit({ referenceId: 3, x: 4.82, y: 4 }),
  ];

  const next = resolveMovementProposals(
    snapshot,
    [proposal(1, 0.02, 0), proposal(2, 0, 0), proposal(3, -0.02, 0)],
    openMap,
  );

  assert.ok(Math.abs(next[0].x - 4.01) < 1e-12);
  assert.equal(next[1].x, 4.41);
  assert.ok(Math.abs(next[2].x - 4.81) < 1e-12);
  assertNonpenetrating(next);
});


test("map bounds remove only the outward normal component", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({ referenceId: 1, x: 9.79, y: 4 });

  const next = resolveMovementProposals(
    [mover],
    [proposal(1, 0.02, 0.015)],
    openMap,
  );

  assert.ok(Math.abs(next[0].x - 9.8) < 1e-12);
  assert.equal(next[0].y, 4.015);
});


test("a circular static obstacle keeps collision-free tangential movement", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({ referenceId: 1, x: 4.29, y: 5 });
  const map = {
    width: 10,
    height: 10,
    obstacles: [{ referenceId: 9000, x: 5, y: 5, radius: 0.5 }],
  };

  const next = resolveMovementProposals(
    [mover],
    [proposal(1, 0.02, 0.01)],
    map,
  );

  assert.ok(Math.abs(next[0].x - 4.3) < 1e-12);
  assert.equal(next[0].y, 5.01);
  assert.ok(Math.hypot(next[0].x - 5, next[0].y - 5) >= 0.7 - 1e-12);
});


test("an exact overlap with a static obstacle is a deterministic error", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({ referenceId: 1, x: 5, y: 5 });
  const map = {
    width: 10,
    height: 10,
    obstacles: [{ referenceId: 9000, x: 5, y: 5, radius: 0.5 }],
  };

  assert.throws(
    () => resolveMovementProposals([mover], [proposal(1, 0, 0)], map),
    /exact overlap.*1.*9000/i,
  );
});
