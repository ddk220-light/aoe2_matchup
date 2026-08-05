import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { planLocalAvoidance } from "../src/combat/local-avoidance.js";


const mechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url),
  "utf8",
));
const STEP = mechanics.speed_tiles_per_second / 60;
const RADIUS = mechanics.collision_size_tiles.x;


function unit({
  referenceId,
  owner,
  x,
  y,
  facing = 0,
  targetId = null,
  avoidance = null,
  alive = true,
} = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    facing,
    targetId,
    avoidance,
    alive,
    mechanics,
  });
}


function proposal(referenceId, dx, dy) {
  return Object.freeze({ referenceId, dx, dy });
}


function normalized(result) {
  const proposals = new Map(result.proposals.map((row) => [row.referenceId, row]));
  return [...result.units]
    .sort((left, right) => left.referenceId - right.referenceId)
    .map((row) => ({
      referenceId: row.referenceId,
      avoidance: row.avoidance,
      proposal: proposals.get(row.referenceId),
    }));
}


test("a direct path creates no avoidance state", () => {
  const mover = unit({ referenceId: 1, owner: 2, x: 2, y: 5, targetId: 3 });
  const offPath = unit({ referenceId: 2, owner: 3, x: 4, y: 6 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });
  const direct = proposal(1, STEP, 0);

  const result = planLocalAvoidance([mover, offPath, target], [direct]);

  assert.equal(result.units.find(({ referenceId }) => referenceId === 1).avoidance, null);
  assert.deepEqual(result.proposals.find(({ referenceId }) => referenceId === 1), direct);
  assert.deepEqual(result.routes, []);
});


test("true route symmetry uses sourced facing and mirrors without a global turn", () => {
  const blocker = unit({ referenceId: 2, owner: 3, x: 4, y: 5 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });
  const upper = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    targetId: 3,
  });
  const lower = unit({
    referenceId: 4,
    owner: 2,
    x: 2,
    y: 5,
    facing: -Math.PI / 2,
    targetId: 3,
  });

  const upperResult = planLocalAvoidance(
    [upper, blocker, target],
    [proposal(1, STEP, 0)],
  );
  const lowerResult = planLocalAvoidance(
    [lower, blocker, target],
    [proposal(4, STEP, 0)],
  );
  const upperMove = upperResult.proposals.find(({ referenceId }) => referenceId === 1);
  const lowerMove = lowerResult.proposals.find(({ referenceId }) => referenceId === 4);

  assert.ok(upperMove.dy > 0);
  assert.ok(lowerMove.dy < 0);
  assert.ok(Math.abs(upperMove.dx - lowerMove.dx) < 1e-12);
  assert.ok(Math.abs(upperMove.dy + lowerMove.dy) < 1e-12);
  assert.ok(Math.hypot(upperMove.dx, upperMove.dy) <= STEP + 1e-12);
  assert.ok(Math.hypot(lowerMove.dx, lowerMove.dy) <= STEP + 1e-12);
  assert.equal(
    upperResult.units.find(({ referenceId }) => referenceId === 1).avoidance.side,
    -lowerResult.units.find(({ referenceId }) => referenceId === 4).avoidance.side,
  );
});


test("every live non-target body can be an occluding blocker", () => {
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    targetId: 3,
  });
  const enemyBlocker = unit({ referenceId: 2, owner: 3, x: 4, y: 5 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });

  const result = planLocalAvoidance(
    [mover, enemyBlocker, target],
    [proposal(1, STEP, 0)],
  );

  assert.equal(
    result.units.find(({ referenceId }) => referenceId === 1)
      .avoidance.blockerReferenceId,
    2,
  );
});


test("route state persists and clears only from geometry or target lifecycle", () => {
  const state = { blockerReferenceId: 2, targetReferenceId: 3, side: 1 };
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });
  const blocker = unit({ referenceId: 2, owner: 2, x: 4, y: 5 });
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: -Math.PI / 2,
    targetId: 3,
    avoidance: state,
  });
  const persisted = planLocalAvoidance(
    [mover, blocker, target],
    [proposal(1, STEP, 0)],
  );
  assert.deepEqual(
    persisted.units.find(({ referenceId }) => referenceId === 1).avoidance,
    state,
  );

  const cases = [
    [
      unit({ ...mover, referenceId: 1, owner: 2, x: 2, y: 5, targetId: 3, avoidance: state }),
      unit({ referenceId: 2, owner: 2, x: 4, y: 6 }),
      target,
    ],
    [
      unit({ referenceId: 1, owner: 2, x: 2, y: 5, targetId: 4, avoidance: state }),
      blocker,
      target,
    ],
    [
      mover,
      blocker,
      unit({ referenceId: 3, owner: 3, x: 6, y: 5, alive: false }),
    ],
    [
      unit({ referenceId: 1, owner: 2, x: 5.6, y: 5, targetId: 3, avoidance: state }),
      blocker,
      target,
    ],
  ];
  for (const units of cases) {
    const result = planLocalAvoidance(units, [proposal(1, 0, 0)]);
    assert.equal(
      result.units.find(({ referenceId }) => referenceId === 1).avoidance,
      null,
    );
  }
});


test("overlapping blocker and goal discs terminate at legal first contact without creep", () => {
  const blocker = unit({ referenceId: 2, owner: 2, x: 4.358579, y: 7.358579 });
  const target = unit({ referenceId: 3, owner: 3, x: 4.641421, y: 7.641421 });
  let mover = unit({
    referenceId: 1,
    owner: 2,
    x: 3.509,
    y: 6.181,
    facing: -3 * Math.PI / 8,
    targetId: 3,
  });
  let previousRemaining = Number.POSITIVE_INFINITY;
  let firstRemaining = null;

  for (let stepIndex = 0; ; stepIndex += 1) {
    const dx = target.x - mover.x;
    const dy = target.y - mover.y;
    const distance = Math.hypot(dx, dy);
    const direct = proposal(1, dx / distance * STEP, dy / distance * STEP);
    const result = planLocalAvoidance([mover, blocker, target], [direct]);
    const move = result.proposals.find(({ referenceId }) => referenceId === 1);
    const route = result.routes.find(({ referenceId }) => referenceId === 1);
    const remaining = route?.remainingPathLength ?? 0;
    if (firstRemaining === null) firstRemaining = remaining;
    assert.ok(remaining < previousRemaining - 1e-12 || remaining === 0);
    assert.ok(Math.hypot(move.dx, move.dy) <= STEP + 1e-12);
    mover = unit({
      ...mover,
      referenceId: 1,
      owner: 2,
      x: mover.x + move.dx,
      y: mover.y + move.dy,
      targetId: 3,
      avoidance: result.units.find(({ referenceId }) => referenceId === 1).avoidance,
    });
    assert.ok(Math.hypot(mover.x - blocker.x, mover.y - blocker.y) >= 2 * RADIUS - 1e-12);
    assert.ok(Math.hypot(mover.x - target.x, mover.y - target.y) >= 2 * RADIUS - 1e-12);
    if (remaining === 0) break;
    assert.ok(stepIndex <= Math.ceil(firstRemaining / STEP) + 1);
  }

  assert.ok(Math.abs(Math.hypot(mover.x - target.x, mover.y - target.y) - 2 * RADIUS) < 1e-12);
});


test("planning is invariant to snapshot and proposal reversal", () => {
  const snapshot = [
    unit({ referenceId: 1, owner: 2, x: 2, y: 5, facing: Math.PI / 2, targetId: 3 }),
    unit({ referenceId: 2, owner: 2, x: 4, y: 5 }),
    unit({ referenceId: 3, owner: 3, x: 6, y: 5 }),
  ];
  const proposals = [proposal(1, STEP, 0), proposal(2, 0, 0), proposal(3, 0, 0)];

  const forward = planLocalAvoidance(snapshot, proposals);
  const reversed = planLocalAvoidance([...snapshot].reverse(), [...proposals].reverse());

  assert.deepEqual(normalized(forward), normalized(reversed));
});
