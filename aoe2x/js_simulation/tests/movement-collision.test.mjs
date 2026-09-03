import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { surfaceGap } from "../src/combat/targeting.js";
import { createPairInteractionSnapshot } from "../src/combat/pair-interactions.js";


const movementModuleUrl = new URL("../src/combat/movement.js", import.meta.url);
const collisionModuleUrl = new URL("../src/combat/collision.js", import.meta.url);
const mechanicsUrl = new URL(
  "../fixtures/unit_stats/champion_chinese_imperial.json",
  import.meta.url,
);
const mechanics = JSON.parse(await readFile(mechanicsUrl, "utf8"));
const openMap = Object.freeze({ width: 10, height: 10, obstacles: Object.freeze([]) });


function unit({
  referenceId,
  x,
  y,
  owner = 2,
  unitMechanics = mechanics,
  action = "idle",
  pursuitTargetId = null,
  engagedTargetId = null,
  attackTargetId = null,
} = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    alive: true,
    action,
    pursuitTargetId,
    engagedTargetId,
    attackTargetId,
    mechanics: unitMechanics,
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
  assert.ok(Math.abs(
    Math.hypot(result.dx, result.dy) - mechanics.speed_tiles_per_second / 60,
  ) < 1e-12);
  assert.ok(Math.abs(result.dx - mechanics.speed_tiles_per_second / 60 * 3 / 5) < 1e-12);
  assert.ok(Math.abs(result.dy - mechanics.speed_tiles_per_second / 60 * 4 / 5) < 1e-12);
});


test("pursuit is clamped only by the remaining physical surface gap", async () => {
  const { proposeMovement } = await loadMovement();
  const mover = unit({ referenceId: 1, x: 1, y: 1 });
  const target = unit({ referenceId: 2, owner: 3, x: 1.405, y: 1 });

  const result = proposeMovement(mover, target, 60);

  assert.ok(Math.abs(result.dx - 0.005) < 1e-12);
  assert.equal(result.dy, 0);
});


test("path waypoint movement reaches the point without subtracting a target body", async () => {
  const { proposePointMovement } = await loadMovement();
  const mover = unit({ referenceId: 1, x: 1, y: 1 });
  const waypoint = Object.freeze({ x: 1.1, y: 1 });

  const result = proposePointMovement(mover, waypoint, 60);

  assert.ok(Math.abs(
    result.dx - mechanics.speed_tiles_per_second / 60,
  ) < 1e-12);
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


test("a reserved enemy-transit pair can cross while an unrelated enemy remains hard", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const chaser = unit({ referenceId: 1, owner: 3, x: 4, y: 4 });
  const blocker = unit({ referenceId: 2, owner: 2, x: 4.5, y: 4 });
  const third = unit({ referenceId: 3, owner: 2, x: 4.9, y: 4 });
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

  const next = resolveMovementProposals(
    [chaser, blocker, third],
    [proposal(1, 0.5, 0), proposal(2, 0, 0), proposal(3, 0, 0)],
    openMap,
    { pairInteractions },
  );
  const moved = next.find(({ referenceId }) => referenceId === 1);

  assert.ok(moved.x > 4.1, "the reserved blocker must not stop the chaser");
  assert.ok(moved.x <= 4.5 + 1e-12, "the unrelated enemy must remain hard");
});


test("inherited enemy overlap is accepted but cannot deepen", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 1, owner: 3, x: 4, y: 4 });
  const right = unit({ referenceId: 2, owner: 2, x: 4.3, y: 4 });
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", Object.freeze({
      leftId: 1,
      rightId: 2,
      kind: "releasing",
      collisionExtent: 0.3,
      attackSurfaceExtent: 0.4,
      pathObstructs: true,
      mayDeepen: false,
      initiatorId: null,
      targetId: null,
      acquiredTick: 10,
    })]]),
  });

  const next = resolveMovementProposals(
    [left, right],
    [proposal(1, 0.02, 0), proposal(2, -0.02, 0)],
    openMap,
    { pairInteractions },
  );
  const separation = Math.abs(next[1].x - next[0].x);

  assert.ok(separation >= 0.3 - 1e-12);
  assert.ok(separation < 0.4);
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


test("an allied-transit reservation lets one pair cross while a third ally still obstructs", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const snapshot = [
    unit({ referenceId: 1, x: 4, y: 4 }),
    unit({ referenceId: 2, x: 4.4, y: 4 }),
    unit({ referenceId: 3, x: 4.8, y: 4 }),
  ];
  const proposals = [
    proposal(1, 0.04, 0),
    proposal(2, -0.04, 0),
    proposal(3, -0.12, 0),
  ];

  const ordinary = resolveMovementProposals(snapshot, proposals, openMap);
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", Object.freeze({
      leftId: 1,
      rightId: 2,
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
  const transit = resolveMovementProposals(snapshot, proposals, openMap, {
    pairInteractions,
  });
  const ordinaryById = new Map(ordinary.map((current) => [current.referenceId, current]));
  const transitById = new Map(transit.map((current) => [current.referenceId, current]));

  assert.ok(Math.abs(ordinaryById.get(2).x - ordinaryById.get(1).x) >= 0.4 - 1e-12);
  assert.ok(Math.abs(transitById.get(2).x - transitById.get(1).x) < 0.4);
  assert.ok(Math.abs(transitById.get(3).x - transitById.get(2).x) >= 0.4 - 1e-12);
});


test("allies that begin a tick overlapped may co-move without healing or deepening overlap", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 1, x: 4, y: 4 });
  const right = unit({ referenceId: 2, x: 4.15, y: 4 });
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", Object.freeze({
      leftId: 1,
      rightId: 2,
      kind: "releasing",
      collisionExtent: 0.15,
      attackSurfaceExtent: 0.4,
      pathObstructs: true,
      mayDeepen: false,
      initiatorId: null,
      targetId: null,
      acquiredTick: 10,
    })]]),
  });

  const next = resolveMovementProposals(
    [left, right],
    [proposal(1, 0.02, 0), proposal(2, 0.02, 0)],
    openMap,
    { pairInteractions },
  );

  assert.ok(Math.abs(next[0].x - 4.02) < 1e-12);
  assert.ok(Math.abs(next[1].x - 4.17) < 1e-12);
  assert.ok(Math.abs(next[1].x - next[0].x - 0.15) < 1e-12);
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


test("a swept tangent on a releasing contact is not clipped by linear projection", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({
    referenceId: 1,
    x: 4.7403479276431675,
    y: 7.235735058903908,
  });
  const blocker = unit({ referenceId: 2, x: 4.35856, y: 7.358579 });
  const tangent = proposal(1, 0.004701209638722499, 0.0193425586453437);
  const currentExtent = Math.max(
    Math.abs(mover.x - blocker.x),
    Math.abs(mover.y - blocker.y),
  );
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", Object.freeze({
      leftId: 1,
      rightId: 2,
      kind: "releasing",
      collisionExtent: currentExtent,
      attackSurfaceExtent: 0.4,
      pathObstructs: true,
      mayDeepen: false,
      initiatorId: null,
      targetId: null,
      acquiredTick: 10,
    })]]),
  });

  const next = resolveMovementProposals(
    [mover, blocker],
    [tangent, proposal(2, 0, 0)],
    openMap,
    { pairInteractions },
  );

  assert.ok(Math.abs(next[0].x - mover.x - tangent.dx) < 1e-12);
  assert.ok(Math.abs(next[0].y - mover.y - tangent.dy) < 1e-12);
  assert.ok(Math.max(
    Math.abs(next[0].x - next[1].x),
    Math.abs(next[0].y - next[1].y),
  ) >= currentExtent - 1e-12);
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


test("a prepared movement snapshot produces the ordinary result for repeated solves", async () => {
  const collision = await loadCollision();
  assert.equal(typeof collision.prepareMovementResolution, "function");
  assert.equal(typeof collision.resolvePreparedMovementProposals, "function");
  const snapshot = [
    unit({ referenceId: 30, x: 4.82, y: 4 }),
    unit({ referenceId: 10, x: 4, y: 4 }),
    unit({ referenceId: 20, owner: 3, x: 4.41, y: 4 }),
  ];
  const firstProposals = [
    proposal(20, 0, 0),
    proposal(30, -0.02, 0),
    proposal(10, 0.02, 0),
  ];
  const secondProposals = [
    proposal(10, 0, 0.015),
    proposal(20, 0, 0),
    proposal(30, -0.015, 0),
  ];

  const prepared = collision.prepareMovementResolution(snapshot, openMap);
  const first = collision.resolvePreparedMovementProposals(prepared, firstProposals);
  const second = collision.resolvePreparedMovementProposals(prepared, secondProposals);

  assert.deepEqual(
    byReference(first),
    byReference(collision.resolveMovementProposals(snapshot, firstProposals, openMap)),
  );
  assert.deepEqual(
    byReference(second),
    byReference(collision.resolveMovementProposals(snapshot, secondProposals, openMap)),
  );
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


test("a legal near-contact deficit cannot accumulate across a tiny inward step", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 1, x: 4, y: 4 });
  const right = unit({
    referenceId: 2,
    owner: 3,
    x: 4.4 - 0.75e-12,
    y: 4,
  });

  const next = resolveMovementProposals(
    [left, right],
    [proposal(1, 0.5e-12, 0), proposal(2, 0, 0)],
    openMap,
  );

  assertNonpenetrating(next);
  assert.equal(next[0].x, left.x);
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


test("distant static obstacles cannot change an unobstructed movement result", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({ referenceId: 1, x: 1, y: 1 });
  const wanted = [proposal(1, 0.02, 0.015)];
  const distantMap = {
    width: 10,
    height: 10,
    obstacles: Array.from({ length: 64 }, (_, index) => ({
      referenceId: 9100 + index,
      x: 7 + index % 8 * 0.25,
      y: 7 + Math.floor(index / 8) * 0.25,
      radius: 0.1,
    })),
  };

  assert.deepEqual(
    resolveMovementProposals([mover], wanted, distantMap),
    resolveMovementProposals([mover], wanted, openMap),
  );
});


test("a legal static-obstacle near-contact deficit cannot accumulate", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const mover = unit({ referenceId: 1, x: 4.3 + 0.75e-12, y: 5 });
  const map = {
    width: 10,
    height: 10,
    obstacles: [{ referenceId: 9000, x: 5, y: 5, radius: 0.5 }],
  };

  const [next] = resolveMovementProposals(
    [mover],
    [proposal(1, 0.5e-12, 0)],
    map,
  );

  assert.ok(Math.hypot(next.x - 5, next.y - 5) >= 0.7 - 1e-15);
  assert.ok(next.x < mover.x);
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
