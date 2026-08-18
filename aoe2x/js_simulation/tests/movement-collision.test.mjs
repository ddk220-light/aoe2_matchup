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
const paladinMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/paladin_spanish_imperial.json", import.meta.url),
  "utf8",
));
const warWagonMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/elite_war_wagon_koreans_imperial.json", import.meta.url),
  "utf8",
));
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


test("War Wagon pursuit keeps moving inside raw contact until its configured overlap limit", async () => {
  const { proposeMovement } = await loadMovement();
  const wagon = unit({
    referenceId: 1,
    x: 4,
    y: 4,
    unitMechanics: warWagonMechanics,
  });
  const champion = unit({ referenceId: 2, owner: 3, x: 4.6, y: 4 });

  const result = proposeMovement(wagon, champion, 60, {
    enemyOverlapDepthByMaster: new Map([[829, 0.1]]),
  });

  assert.ok(Math.abs(result.dx - warWagonMechanics.speed_tiles_per_second / 60) < 1e-12);
  assert.equal(result.dy, 0);
});


test("War Wagon overlap movement policy does not move an unrelated pair inside contact", async () => {
  const { proposeMovement } = await loadMovement();
  const mover = unit({ referenceId: 1, x: 4, y: 4 });
  const target = unit({ referenceId: 2, owner: 3, x: 4.35, y: 4 });

  const result = proposeMovement(mover, target, 60, {
    enemyOverlapDepthByMaster: new Map([[829, 0.1]]),
  });

  assert.equal(result.dx, 0);
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


test("a configured War Wagon pair may enter only its bounded enemy overlap depth", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const wagon = unit({
    referenceId: 1,
    x: 4,
    y: 4,
    unitMechanics: warWagonMechanics,
  });
  const champion = unit({ referenceId: 2, owner: 3, x: 4.67, y: 4 });

  const next = resolveMovementProposals(
    [wagon, champion],
    [proposal(1, 0.08, 0), proposal(2, -0.08, 0)],
    openMap,
    { enemyOverlapDepthByMaster: new Map([[829, 0.1]]) },
  );
  const separation = Math.abs(next[1].x - next[0].x);

  assert.ok(Math.abs(separation - 0.55) < 1e-12);
  assert.ok(Math.abs(surfaceGap(next[0], next[1]) + 0.1) < 1e-12);
});


test("an attacking-only War Wagon overlap policy opens during attack lock, not pursuit", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const wagon = unit({
    referenceId: 1,
    x: 4,
    y: 4,
    unitMechanics: warWagonMechanics,
  });
  const pursuing = unit({ referenceId: 2, owner: 3, x: 4.67, y: 4 });
  const attacking = unit({
    referenceId: 2,
    owner: 3,
    x: 4.67,
    y: 4,
    action: "attacking",
    pursuitTargetId: 1,
    engagedTargetId: 1,
    attackTargetId: 1,
  });
  const proposals = [proposal(1, 0.08, 0), proposal(2, -0.08, 0)];
  const options = {
    enemyOverlapDepthByMaster: new Map([[
      829,
      Object.freeze({ depth: 0.1, mode: "attacking-any" }),
    ]]),
  };

  const pursuitResult = resolveMovementProposals(
    [wagon, pursuing], proposals, openMap, options,
  );
  const attackResult = resolveMovementProposals(
    [wagon, attacking], proposals, openMap, options,
  );

  assert.ok(Math.abs(pursuitResult[1].x - pursuitResult[0].x - 0.65) < 1e-12);
  assert.ok(Math.abs(attackResult[1].x - attackResult[0].x - 0.55) < 1e-12);
});


test("attack-locked War Wagon overlap remains legal until the pair separates", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const wagon = unit({
    referenceId: 1,
    x: 4,
    y: 4,
    unitMechanics: warWagonMechanics,
  });
  const releasedChampion = unit({
    referenceId: 2,
    owner: 3,
    x: 4.58,
    y: 4,
    action: "idle",
  });
  const options = {
    enemyOverlapDepthByMaster: new Map([[
      829,
      Object.freeze({ depth: 0.1, mode: "attacking-any" }),
    ]]),
  };

  const next = resolveMovementProposals(
    [wagon, releasedChampion],
    [proposal(1, -0.02, 0), proposal(2, 0.02, 0)],
    openMap,
    options,
  );

  assert.ok(Math.abs(next[1].x - next[0].x - 0.62) < 1e-12);
});


test("a War Wagon overlap policy does not relax unrelated enemy pairs", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 1, x: 4, y: 4 });
  const right = unit({ referenceId: 2, owner: 3, x: 4.42, y: 4 });

  const next = resolveMovementProposals(
    [left, right],
    [proposal(1, 0.04, 0), proposal(2, -0.04, 0)],
    openMap,
    { enemyOverlapDepthByMaster: new Map([[829, 0.1]]) },
  );

  assert.ok(Math.abs(next[1].x - next[0].x - 0.4) < 1e-12);
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


test("an allied-transit reservation lets one pair cross while a third ally still obstructs", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const snapshot = [
    unit({ referenceId: 1, x: 4, y: 4 }),
    unit({ referenceId: 2, x: 4.38, y: 4 }),
    unit({ referenceId: 3, x: 4.76, y: 4 }),
  ];
  const proposals = [
    proposal(1, 0.04, 0),
    proposal(2, -0.04, 0),
    proposal(3, -0.12, 0),
  ];

  const ordinary = resolveMovementProposals(snapshot, proposals, openMap);
  const transit = resolveMovementProposals(snapshot, proposals, openMap, {
    alliedTransitPairs: new Set(["1:2"]),
  });
  const ordinaryById = new Map(ordinary.map((current) => [current.referenceId, current]));
  const transitById = new Map(transit.map((current) => [current.referenceId, current]));

  assert.ok(Math.abs(ordinaryById.get(2).x - ordinaryById.get(1).x) >= 0.32 - 1e-12);
  assert.ok(Math.abs(transitById.get(2).x - transitById.get(1).x) < 0.32);
  assert.ok(Math.abs(transitById.get(3).x - transitById.get(2).x) >= 0.32 - 1e-12);
});


test("exclusive allied shrink gives a third cavalry unit one shallow edge, never a triangle", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const snapshot = [
    unit({ referenceId: 1, owner: 3, x: 4, y: 4, unitMechanics: paladinMechanics }),
    unit({ referenceId: 2, owner: 3, x: 4.5, y: 4, unitMechanics: paladinMechanics }),
    unit({ referenceId: 3, owner: 3, x: 4.75, y: 4.5, unitMechanics: paladinMechanics }),
  ];
  const next = resolveMovementProposals(
    snapshot,
    [proposal(1, 0.2, 0), proposal(2, -0.2, 0), proposal(3, 0, -0.2)],
    openMap,
    {
      exclusiveAlliedShrinkOwners: new Set([3]),
      alliedShrinkPairs: new Set(["1:2"]),
      alliedShallowPairs: new Set(["2:3"]),
      alliedShrinkReservedIds: new Set([1, 2]),
    },
  );
  const byId = new Map(next.map((current) => [current.referenceId, current]));
  const separation = (leftId, rightId) => Math.max(
    Math.abs(byId.get(leftId).x - byId.get(rightId).x),
    Math.abs(byId.get(leftId).y - byId.get(rightId).y),
  );

  assert.ok(Math.abs(separation(1, 2) - 0.25) < 1e-12);
  assert.ok(separation(1, 3) >= 0.5 - 1e-12);
  assert.ok(separation(2, 3) >= 0.375 - 1e-12);
  assert.ok(separation(2, 3) < 0.5 - 1e-12);
});


test("allies that begin a tick overlapped may co-move without healing or deepening overlap", async () => {
  const { resolveMovementProposals } = await loadCollision();
  const left = unit({ referenceId: 1, x: 4, y: 4 });
  const right = unit({ referenceId: 2, x: 4.15, y: 4 });

  const next = resolveMovementProposals(
    [left, right],
    [proposal(1, 0.02, 0), proposal(2, 0.02, 0)],
    openMap,
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
