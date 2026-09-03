import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { resolveMovementProposals } from "../src/combat/collision.js";
import { planLocalAvoidance } from "../src/combat/local-avoidance.js";
import { createPairInteractionSnapshot } from "../src/combat/pair-interactions.js";


const mechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url),
  "utf8",
));
const STEP = mechanics.speed_tiles_per_second / 60;
const RADIUS = mechanics.collision_size_tiles.x;
const OPEN_MAP = Object.freeze({ width: 10, height: 10, obstacles: Object.freeze([]) });


function unit({
  referenceId,
  owner,
  x,
  y,
  facing = 0,
  pursuitTargetId = null,
  avoidance = null,
  alive = true,
  moveOrder = null,
  openingAcquisitionComplete = undefined,
} = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    facing,
    pursuitTargetId,
    avoidance,
    alive,
    moveOrder,
    openingAcquisitionComplete,
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


function pointToSegmentDistance(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return Math.hypot(point.x - start.x, point.y - start.y);
  const projection = Math.max(0, Math.min(1, (
    (point.x - start.x) * dx + (point.y - start.y) * dy
  ) / lengthSquared));
  return Math.hypot(
    point.x - start.x - projection * dx,
    point.y - start.y - projection * dy,
  );
}


test("a direct path creates no avoidance state", () => {
  const mover = unit({ referenceId: 1, owner: 2, x: 2, y: 5, pursuitTargetId: 3 });
  const offPath = unit({ referenceId: 2, owner: 3, x: 4, y: 6 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });
  const direct = proposal(1, STEP, 0);

  const result = planLocalAvoidance([mover, offPath, target], [direct]);

  assert.equal(result.units.find(({ referenceId }) => referenceId === 1).avoidance, null);
  assert.deepEqual(result.proposals.find(({ referenceId }) => referenceId === 1), direct);
  assert.deepEqual(result.routes, []);
});


test("scenario patrol starts pursuit avoidance only at an immediate allied-body block", () => {
  const patrol = Object.freeze({ kind: "scenario-patrol", x: 8, y: 5 });
  const blocker = unit({ referenceId: 2, owner: 2, x: 4, y: 5 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });
  const before = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    pursuitTargetId: 3,
    moveOrder: patrol,
    openingAcquisitionComplete: false,
  });
  const after = unit({
    referenceId: 1,
    owner: 2,
    x: 3.2,
    y: 5,
    pursuitTargetId: 3,
    moveOrder: patrol,
    openingAcquisitionComplete: true,
  });
  const direct = Object.freeze({
    ...proposal(1, STEP, 0),
    movementIntent: "pursuit",
  });

  const formationTransit = planLocalAvoidance([before, blocker, target], [direct]);
  const pursuit = planLocalAvoidance([after, blocker, target], [direct]);
  const pursuitUnit = pursuit.units.find(({ referenceId }) => referenceId === 1);
  const pursuitProposal = pursuit.proposals.find(({ referenceId }) => referenceId === 1);

  assert.deepEqual(formationTransit.proposals.find(({ referenceId }) => (
    referenceId === 1
  )), direct);
  assert.notEqual(pursuitUnit.avoidance, null);
  assert.notEqual(pursuitProposal.dy, 0);
});


test("true route symmetry uses sourced facing and mirrors without a global turn", () => {
  const blocker = unit({ referenceId: 2, owner: 2, x: 4, y: 5 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });
  const upper = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    pursuitTargetId: 3,
  });
  const lower = unit({
    referenceId: 4,
    owner: 2,
    x: 2,
    y: 5,
    facing: -Math.PI / 2,
    pursuitTargetId: 3,
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


test("an enemy body remains a collision contact instead of an avoidance blocker", () => {
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    pursuitTargetId: 3,
  });
  const enemyBlocker = unit({ referenceId: 2, owner: 3, x: 4, y: 5 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });

  const result = planLocalAvoidance(
    [mover, enemyBlocker, target],
    [proposal(1, STEP, 0)],
  );

  assert.equal(
    result.units.find(({ referenceId }) => referenceId === 1).avoidance,
    null,
  );
  assert.deepEqual(
    result.proposals.find(({ referenceId }) => referenceId === 1),
    proposal(1, STEP, 0),
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
    pursuitTargetId: 3,
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
      unit({ ...mover, referenceId: 1, owner: 2, x: 2, y: 5, pursuitTargetId: 3, avoidance: state }),
      unit({ referenceId: 2, owner: 2, x: 4, y: 6 }),
      target,
    ],
    [
      unit({ referenceId: 1, owner: 2, x: 2, y: 5, pursuitTargetId: 4, avoidance: state }),
      blocker,
      target,
    ],
    [
      mover,
      blocker,
      unit({ referenceId: 3, owner: 3, x: 6, y: 5, alive: false }),
    ],
    [
      unit({ referenceId: 1, owner: 2, x: 5.6, y: 5, pursuitTargetId: 3, avoidance: state }),
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


test("a removed or dead saved blocker clears without dereferencing stale state", () => {
  const state = { blockerReferenceId: 2, targetReferenceId: 3, side: 1 };
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    pursuitTargetId: 3,
    avoidance: state,
  });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });

  for (const snapshot of [
    [mover, target],
    [mover, unit({ referenceId: 2, owner: 2, x: 4, y: 5, alive: false }), target],
  ]) {
    const result = planLocalAvoidance(snapshot, [proposal(1, STEP, 0)], OPEN_MAP);
    assert.equal(
      result.units.find(({ referenceId }) => referenceId === 1).avoidance,
      null,
    );
  }
});


test("an active detour uses sourced full speed instead of the direct proposal clamp", () => {
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    pursuitTargetId: 3,
  });
  const blocker = unit({ referenceId: 2, owner: 2, x: 4, y: 5 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });

  const result = planLocalAvoidance(
    [mover, blocker, target],
    [proposal(1, STEP / 4, 0)],
    OPEN_MAP,
  );
  const move = result.proposals.find(({ referenceId }) => referenceId === 1);

  assert.ok(result.routes[0].remainingPathLength > STEP);
  assert.ok(Math.abs(Math.hypot(move.dx, move.dy) - STEP) < 1e-12);
});


test("unified contact lanes ignore only a mover's reserved allied-transit partner", () => {
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    pursuitTargetId: 4,
  });
  const partner = unit({ referenceId: 2, owner: 2, x: 4, y: 5 });
  const third = unit({ referenceId: 3, owner: 2, x: 4.1, y: 5 });
  const target = unit({ referenceId: 4, owner: 3, x: 6, y: 5 });
  const direct = proposal(1, STEP, 0);
  const options = {
    pairInteractions: createPairInteractionSnapshot({
      contactReservations: new Map([["1:2", Object.freeze({
        leftId: 1,
        rightId: 2,
        kind: "allied-transit",
        collisionExtent: 2 * RADIUS * mechanics.min_collision_size_multiplier,
        attackSurfaceExtent: 2 * RADIUS,
        pathObstructs: false,
        mayDeepen: true,
        initiatorId: 1,
        targetId: null,
        acquiredTick: 1,
      })]]),
    }),
  };

  const partnerOnly = planLocalAvoidance(
    [mover, partner, target],
    [direct],
    OPEN_MAP,
    options,
  );
  assert.equal(
    partnerOnly.units.find(({ referenceId }) => referenceId === 1).avoidance,
    null,
  );
  assert.deepEqual(
    partnerOnly.proposals.find(({ referenceId }) => referenceId === 1),
    direct,
  );

  const withThird = planLocalAvoidance(
    [mover, partner, third, target],
    [direct],
    OPEN_MAP,
    options,
  );
  assert.equal(
    withThird.units.find(({ referenceId }) => referenceId === 1)
      .avoidance.blockerReferenceId,
    3,
  );
});


test("an authoritative persistent route bypasses local tangent rewriting", () => {
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    pursuitTargetId: 3,
  });
  const blocker = unit({ referenceId: 2, owner: 2, x: 4, y: 5 });
  const target = unit({ referenceId: 3, owner: 3, x: 6, y: 5 });
  const routed = proposal(1, STEP / Math.SQRT2, STEP / Math.SQRT2);

  const result = planLocalAvoidance(
    [mover, blocker, target],
    [routed],
    OPEN_MAP,
    { authoritativeReferenceIds: new Set([1]) },
  );

  assert.deepEqual(result.proposals.find(({ referenceId }) => referenceId === 1), routed);
  assert.equal(result.units.find(({ referenceId }) => referenceId === 1).avoidance, null);
  assert.deepEqual(result.routes, []);
});


test("route selection rejects paths swept through a second body or map obstacle", () => {
  const mover = unit({
    referenceId: 1,
    owner: 2,
    x: 2,
    y: 5,
    facing: Math.PI / 2,
    pursuitTargetId: 4,
  });
  const directBlocker = unit({ referenceId: 2, owner: 2, x: 4, y: 5 });
  const upperBlocker = unit({ referenceId: 3, owner: 2, x: 3.5, y: 5.5 });
  const target = unit({ referenceId: 4, owner: 3, x: 6, y: 5 });
  const direct = proposal(1, STEP, 0);

  const bodyResult = planLocalAvoidance(
    [mover, directBlocker, upperBlocker, target],
    [direct],
    OPEN_MAP,
  );
  const bodyMove = bodyResult.proposals.find(({ referenceId }) => referenceId === 1);
  assert.ok(bodyMove.dy < 0);
  assert.ok(pointToSegmentDistance(
    upperBlocker,
    mover,
    { x: mover.x + bodyMove.dx, y: mover.y + bodyMove.dy },
  ) >= 2 * RADIUS - 1e-12);

  let current = mover;
  let reachedContact = false;
  for (let tick = 0; tick < 300; tick += 1) {
    const dx = target.x - current.x;
    const dy = target.y - current.y;
    const distance = Math.hypot(dx, dy);
    const gap = distance - 2 * RADIUS;
    const magnitude = Math.min(STEP, Math.max(0, gap));
    const result = planLocalAvoidance(
      [current, directBlocker, upperBlocker, target],
      [proposal(1, dx / distance * magnitude, dy / distance * magnitude)],
      OPEN_MAP,
    );
    const move = result.proposals.find(({ referenceId }) => referenceId === 1);
    const resolved = resolveMovementProposals(result.units, result.proposals, OPEN_MAP);
    const actual = resolved.find(({ referenceId }) => referenceId === 1);
    const actualDx = actual.x - current.x;
    const actualDy = actual.y - current.y;
    const next = unit({
      referenceId: 1,
      owner: 2,
      x: actual.x,
      y: actual.y,
      facing: actualDx === 0 && actualDy === 0
        ? current.facing
        : Math.atan2(actualDy, actualDx),
      pursuitTargetId: 4,
      avoidance: result.units.find(({ referenceId }) => referenceId === 1).avoidance,
    });
    assert.ok(Math.hypot(actualDx, actualDy) <= STEP + 1e-12);
    for (const blocker of [directBlocker, upperBlocker]) {
      assert.ok(
        pointToSegmentDistance(blocker, current, next) >= 2 * RADIUS - 1e-12,
        `tick ${tick} swept through blocker ${blocker.referenceId}`,
      );
    }
    current = next;
    if (Math.max(
      Math.abs(target.x - current.x),
      Math.abs(target.y - current.y),
    ) <= 2 * RADIUS + 1e-12) {
      reachedContact = true;
      break;
    }
  }
  assert.equal(reachedContact, true, `ended at ${current.x},${current.y}`);

  const obstacleMap = Object.freeze({
    width: 10,
    height: 10,
    obstacles: Object.freeze([
      Object.freeze({ referenceId: 9000, x: 3.5, y: 5.5, radius: RADIUS }),
    ]),
  });
  const mapResult = planLocalAvoidance(
    [mover, directBlocker, target],
    [direct],
    obstacleMap,
  );
  const mapMove = mapResult.proposals.find(({ referenceId }) => referenceId === 1);
  assert.ok(mapMove.dy < 0);
  assert.ok(pointToSegmentDistance(
    obstacleMap.obstacles[0],
    mover,
    { x: mover.x + mapMove.dx, y: mover.y + mapMove.dy },
  ) >= 2 * RADIUS - 1e-12);

  const directMapResult = planLocalAvoidance(
    [mover, target],
    [direct],
    Object.freeze({
      width: 10,
      height: 10,
      obstacles: Object.freeze([
        Object.freeze({ referenceId: 9001, x: 4, y: 5, radius: RADIUS }),
      ]),
    }),
  );
  assert.deepEqual(
    directMapResult.units.find(({ referenceId }) => referenceId === 1).avoidance,
    { blockerObstacleIndex: 0, targetReferenceId: 4, side: -1 },
  );
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
    pursuitTargetId: 3,
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
    const start = mover;
    mover = unit({
      ...mover,
      referenceId: 1,
      owner: 2,
      x: mover.x + move.dx,
      y: mover.y + move.dy,
      pursuitTargetId: 3,
      avoidance: result.units.find(({ referenceId }) => referenceId === 1).avoidance,
    });
    assert.ok(pointToSegmentDistance(blocker, start, mover) >= 2 * RADIUS - 1e-12);
    assert.ok(Math.hypot(mover.x - blocker.x, mover.y - blocker.y) >= 2 * RADIUS - 1e-12);
    assert.ok(Math.hypot(mover.x - target.x, mover.y - target.y) >= 2 * RADIUS - 1e-12);
    if (remaining === 0) {
      if (route) {
        assert.notEqual(
          result.units.find(({ referenceId }) => referenceId === 1).avoidance,
          null,
        );
      }
      break;
    }
    assert.ok(stepIndex <= Math.ceil(firstRemaining / STEP) + 1);
  }

  assert.ok(Math.abs(Math.hypot(mover.x - target.x, mover.y - target.y) - 2 * RADIUS) < 1e-12);
});


test("planning is invariant to snapshot and proposal reversal", () => {
  const snapshot = [
    unit({ referenceId: 1, owner: 2, x: 2, y: 5, facing: Math.PI / 2, pursuitTargetId: 3 }),
    unit({ referenceId: 2, owner: 2, x: 4, y: 5 }),
    unit({ referenceId: 3, owner: 3, x: 6, y: 5 }),
  ];
  const proposals = [proposal(1, STEP, 0), proposal(2, 0, 0), proposal(3, 0, 0)];

  const forward = planLocalAvoidance(snapshot, proposals);
  const reversed = planLocalAvoidance([...snapshot].reverse(), [...proposals].reverse());

  assert.deepEqual(normalized(forward), normalized(reversed));
});
