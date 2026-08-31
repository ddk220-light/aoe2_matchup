import assert from "node:assert/strict";
import test from "node:test";

import { isWithinStopRange } from "../src/combat/attacks.js";
import { resolveMovementProposals } from "../src/combat/collision.js";
import {
  createPairInteractionSnapshot,
  dynamicPairKey,
  resolvePairInteraction,
} from "../src/combat/pair-interactions.js";


const mechanics = Object.freeze({
  unit_master: 1,
  collision_size_tiles: Object.freeze({ x: 0.25, y: 0.25 }),
  outline_size_tiles: Object.freeze({ x: 0.25, y: 0.25 }),
  min_collision_size_multiplier: 0.5,
  attack_range_tiles: 1,
  ranged: null,
});


function unit(referenceId, owner, x, overrides = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y: 4,
    alive: true,
    action: "moving",
    mechanics,
    ...overrides,
  });
}


function reservation(overrides = {}) {
  return Object.freeze({
    leftId: 1,
    rightId: 2,
    kind: "engagement-contact",
    collisionExtent: 0.25,
    attackSurfaceExtent: 1.5,
    pathObstructs: true,
    mayDeepen: true,
    initiatorId: 1,
    targetId: 2,
    acquiredTick: 12,
    ...overrides,
  });
}


test("dynamic pair keys are canonical regardless of input order", () => {
  assert.equal(dynamicPairKey(2, 1), "1:2");
  assert.throws(() => dynamicPairKey(1, 1), /two references/);
});


test("ordinary pairs use their complete sourced collision extent", () => {
  const left = unit(1, 2, 4);
  const right = unit(2, 3, 5);
  const interaction = resolvePairInteraction(left, right);

  assert.equal(interaction.kind, "hard");
  assert.equal(interaction.collisionExtent, 0.5);
  assert.equal(interaction.attackSurfaceExtent, 0.5);
  assert.equal(interaction.pathObstructs, true);
  assert.equal(interaction.mayDeepen, false);
});


test("allied formation orders share a zero-obstruction transit surface", () => {
  const left = unit(1, 2, 4, { moveOrder: Object.freeze({ x: 8, y: 4 }) });
  const right = unit(2, 2, 4.5, { moveOrder: Object.freeze({ x: 8.5, y: 4 }) });
  const interaction = resolvePairInteraction(left, right);

  assert.deepEqual(interaction, {
    kind: "formation-transit",
    collisionExtent: 0,
    pathObstructs: false,
    attackSurfaceExtent: 0.5,
    mayDeepen: true,
    reason: "shared-allied-formation-order",
  });
});


test("scenario patrol transit ends when both allies complete first acquisition", () => {
  const patrol = Object.freeze({ kind: "scenario-patrol", x: 8, y: 4 });
  const beforeLeft = unit(1, 2, 4, { moveOrder: patrol });
  const beforeRight = unit(2, 2, 4.5, { moveOrder: patrol });
  const afterLeft = unit(1, 2, 4, {
    moveOrder: patrol,
    openingAcquisitionComplete: true,
  });
  const afterRight = unit(2, 2, 4.5, {
    moveOrder: patrol,
    openingAcquisitionComplete: true,
  });

  assert.equal(resolvePairInteraction(beforeLeft, beforeRight).kind, "formation-transit");
  assert.equal(resolvePairInteraction(afterLeft, afterRight).kind, "hard");
  assert.equal(resolvePairInteraction(afterLeft, afterRight).pathObstructs, true);
});


test("formation transit overrides a stale release until the shared order ends", () => {
  const snapshot = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", reservation({
      kind: "releasing",
      collisionExtent: 0.3,
      attackSurfaceExtent: 0.5,
      pathObstructs: true,
      mayDeepen: false,
      initiatorId: null,
      targetId: null,
    })]]),
  });
  const left = unit(1, 2, 4, { moveOrder: Object.freeze({ x: 8, y: 4 }) });
  const right = unit(2, 2, 4.3, { moveOrder: Object.freeze({ x: 8.5, y: 4 }) });

  assert.equal(resolvePairInteraction(left, right, snapshot).kind, "formation-transit");
  assert.equal(resolvePairInteraction(
    unit(1, 2, 4),
    unit(2, 2, 4.3),
    snapshot,
  ).kind, "releasing");
});


test("formation transit lets several ordered allies cross without a deep-slot cap", () => {
  const ordered = [
    unit(1, 2, 4, { moveOrder: Object.freeze({ x: 8, y: 4 }) }),
    unit(2, 2, 4.5, { moveOrder: Object.freeze({ x: 7.5, y: 4 }) }),
    unit(3, 2, 5, { moveOrder: Object.freeze({ x: 7, y: 4 }) }),
  ];
  const next = resolveMovementProposals(
    ordered,
    [
      Object.freeze({ referenceId: 1, dx: 0.5, dy: 0 }),
      Object.freeze({ referenceId: 2, dx: 0, dy: 0 }),
      Object.freeze({ referenceId: 3, dx: -0.5, dy: 0 }),
    ],
    Object.freeze({ width: 10, height: 10, obstacles: Object.freeze([]) }),
  );

  assert.deepEqual(next.map(({ x }) => x), [4.5, 4.5, 4.5]);
});


test("one unified reservation is authoritative for its pair", () => {
  const snapshot = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", reservation()]]),
  });
  const interaction = resolvePairInteraction(unit(2, 3, 5), unit(1, 2, 4), snapshot);

  assert.deepEqual(interaction, {
    kind: "engagement-contact",
    collisionExtent: 0.25,
    pathObstructs: true,
    attackSurfaceExtent: 1.5,
    mayDeepen: true,
    reason: "unified-contact-reservation",
  });
});


test("attack stopping and collision consume the same direct-contact surface", () => {
  const actor = unit(1, 2, 4);
  const target = unit(2, 3, 5.4);
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", reservation()]]),
  });

  assert.equal(isWithinStopRange(actor, target, { pairInteractions }), true);
  const next = resolveMovementProposals(
    [actor, target],
    [
      Object.freeze({ referenceId: 1, dx: 1.4, dy: 0 }),
      Object.freeze({ referenceId: 2, dx: 0, dy: 0 }),
    ],
    Object.freeze({ width: 10, height: 10, obstacles: Object.freeze([]) }),
    { pairInteractions },
  );
  const separation = Math.max(
    Math.abs(next[1].x - next[0].x),
    Math.abs(next[1].y - next[0].y),
  );

  assert.ok(separation >= 0.25 - 1e-12);
  assert.ok(separation < 0.5);
});


test("unified reservations reject malformed geometry", () => {
  assert.throws(
    () => createPairInteractionSnapshot({
      contactReservations: new Map([["1:2", reservation({
        collisionExtent: 0.6,
        attackSurfaceExtent: 0.5,
      })]]),
    }),
    /cannot exceed/,
  );
});


test("pair snapshots reject retired independent contact authorities", () => {
  for (const retired of [
    "allied" + "TransitPairs",
    "allied" + "ShrinkPairs",
    "allied" + "ShallowPairs",
    "enemy" + "TransitPairs",
    "enemy" + "OverlapDepthByMaster",
  ]) {
    assert.throws(
      () => createPairInteractionSnapshot({ [retired]: new Map() }),
      /unknown pair interaction option/,
      retired,
    );
  }
});
