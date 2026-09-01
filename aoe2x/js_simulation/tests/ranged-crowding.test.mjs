import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizedRangedPenetration,
  planRangedCrowding,
  sharedRangedIntersectionFraction,
} from "../src/combat/ranged-crowding.js";
import {
  createPairInteractionSnapshot,
  resolvePairInteraction,
} from "../src/combat/pair-interactions.js";


const mechanics = Object.freeze({
  collision_size_tiles: Object.freeze({ x: 0.2, y: 0.2 }),
  outline_size_tiles: Object.freeze({ x: 0.2, y: 0.2 }),
  speed_tiles_per_second: 1.2,
  attack_range_tiles: 5,
  ranged: Object.freeze({ projectile_speed_tiles_per_second: 7 }),
});

const largeRangedMechanics = Object.freeze({
  ...mechanics,
  collision_size_tiles: Object.freeze({ x: 0.5, y: 0.5 }),
  outline_size_tiles: Object.freeze({ x: 0.5, y: 0.5 }),
});

const siegeRangedMechanics = Object.freeze({
  ...mechanics,
  armor_classes: Object.freeze({ 20: 0 }),
});


const unit = (referenceId, x, y, overrides = {}) => Object.freeze({
  referenceId,
  owner: 2,
  x,
  y,
  alive: true,
  action: "moving",
  mechanics,
  moveOrder: Object.freeze({ kind: "scenario-patrol", x: 10, y }),
  pursuitTargetId: null,
  engagedTargetId: null,
  attackTargetId: null,
  ...overrides,
});


const proposal = (referenceId, dx, dy = 0) => Object.freeze({ referenceId, dx, dy });


test("ranged penetration and shared area normalize by physical body size", () => {
  const left = unit(1, 1, 1);
  const right = unit(2, 1.3, 1.2);
  const leftPosition = { x: left.x, y: left.y };
  const rightPosition = { x: right.x, y: right.y };

  assert.ok(Math.abs(normalizedRangedPenetration(
    left, leftPosition, right, rightPosition,
  ) - 0.25) < 1e-12);
  assert.ok(Math.abs(sharedRangedIntersectionFraction([
    { unit: left, position: leftPosition },
    { unit: right, position: rightPosition },
  ]) - 0.125) < 1e-12);
});


test("an isolated ranged pair keeps its desired compliant compression step", () => {
  const units = [unit(1, 1, 1), unit(2, 1.39, 1)];
  const result = planRangedCrowding(
    units,
    [proposal(1, 0.02), proposal(2, 0)],
    10,
  );

  assert.deepEqual(result.proposals[0], proposal(1, 0.02));
  assert.equal(result.steered.length, 0);
  assert.equal(result.contactReservations.get("1:2").kind, "ranged-crowd");
  assert.ok(result.contactReservations.get("1:2").collisionExtent < 0.4);
});


test("three-body compression rotates the incoming ranged step laterally", () => {
  const units = [
    unit(1, 1, 1),
    unit(2, 1.25, 1),
    unit(3, 1.25, 1.1),
  ];
  const result = planRangedCrowding(
    units,
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
    11,
  );
  const selected = result.proposals[0];

  assert.ok(Math.abs(selected.dy) > 1e-9);
  assert.ok(selected.dx < 0.02);
  assert.deepEqual(result.steered.map(({ referenceId }) => referenceId), [1]);
});


test("a rear-line local minimum requests a committed route instead of reversing", () => {
  const units = [
    unit(1, 1, 1, { moveOrder: null, pursuitTargetId: 9 }),
    unit(2, 1.05, 0.85),
    unit(3, 1.05, 1.15),
    unit(9, 8, 1, { owner: 3, moveOrder: null }),
  ];
  const result = planRangedCrowding(
    units,
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0), proposal(9, 0)],
    11,
  );
  const selected = result.proposals[0];
  const diagnostic = result.steered.find(({ referenceId }) => referenceId === 1);

  assert.deepEqual(selected, proposal(1, 0));
  assert.deepEqual(result.routeRequests, [Object.freeze({
    referenceId: 1,
    targetReferenceId: 9,
    wantedDx: 0.02,
    wantedDy: 0,
    reason: "ranged-crowd-local-minimum",
  })]);
  assert.equal(diagnostic.requiresRoute, true);
  assert.equal(diagnostic.maximumFourArea, 0);
});


test("a persistent recovery corridor remains authoritative through crowd steering", () => {
  const units = [
    unit(1, 1, 1, { moveOrder: null, pursuitTargetId: 9 }),
    unit(2, 1.05, 0.85),
    unit(3, 1.05, 1.15),
    unit(9, 8, 1, { owner: 3, moveOrder: null }),
  ];
  const desired = proposal(1, 0.02);
  const result = planRangedCrowding(
    units,
    [desired, proposal(2, 0), proposal(3, 0), proposal(9, 0)],
    11,
    { authoritativeReferenceIds: new Set([1]) },
  );

  assert.deepEqual(result.proposals[0], desired);
  assert.equal(result.routeRequests.length, 0);
  assert.equal(result.steered.some(({ referenceId }) => referenceId === 1), false);
  assert.equal(result.contactReservations.get("1:2").kind, "ranged-crowd");
});


test("a fourth ranged body cannot deepen a common four-way intersection", () => {
  const units = [
    unit(1, 1, 1),
    unit(2, 1.24, 0.92),
    unit(3, 1.24, 1),
    unit(4, 1.24, 1.08),
  ];
  const before = sharedRangedIntersectionFraction(units.map((entry) => ({
    unit: entry,
    position: { x: entry.x, y: entry.y },
  })));
  const result = planRangedCrowding(
    units,
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0), proposal(4, 0)],
    12,
  );
  const afterPositions = new Map(units.map((entry, index) => [
    entry.referenceId,
    {
      x: entry.x + result.proposals[index].dx,
      y: entry.y + result.proposals[index].dy,
    },
  ]));
  const after = sharedRangedIntersectionFraction(units.map((entry) => ({
    unit: entry,
    position: afterPositions.get(entry.referenceId),
  })));

  assert.ok(after <= before + 1e-12);
  assert.notDeepEqual(result.proposals[0], proposal(1, 0.02));
});


test("a four-unit contact chain remains legal because it is not a four-body stack", () => {
  const units = [
    unit(1, 1, 1),
    unit(2, 1.35, 1),
    unit(3, 1.7, 1),
    unit(4, 2.05, 1),
  ];
  const proposals = units.map(({ referenceId }) => proposal(referenceId, 0.01));
  const result = planRangedCrowding(units, proposals, 13);

  assert.deepEqual(result.proposals, proposals);
  assert.equal(result.steered.length, 0);
  assert.equal(result.contactReservations.size, 3);
});


test("stationary firing ranged contacts persist and outrank formation phasing", () => {
  const units = [
    unit(1, 1, 1, { action: "attacking", attackTargetId: 9 }),
    unit(2, 1.3, 1, { action: "attacking", attackTargetId: 9 }),
  ];
  const result = planRangedCrowding(
    units,
    [proposal(1, 0), proposal(2, 0)],
    14,
  );
  const snapshot = createPairInteractionSnapshot({
    contactReservations: result.contactReservations,
  });
  const interaction = resolvePairInteraction(units[0], units[1], snapshot);

  assert.equal(interaction.kind, "ranged-crowd");
  // An inherited 0.30 separation must never contract merely because the pair
  // entered its firing state.
  assert.ok(Math.abs(interaction.collisionExtent - 0.3) < 1e-12);
  assert.equal(interaction.pathObstructs, false);
});


test("a committed ordinary ranged rank remains compliant to fresh ingress", () => {
  const units = [
    unit(1, 1, 1, { action: "reload", attackTargetId: 9 }),
    unit(2, 1.45, 1),
  ];
  const result = planRangedCrowding(
    units,
    [proposal(1, 0), proposal(2, -0.1)],
    15,
  );
  const interaction = result.contactReservations.get("1:2");

  assert.equal(interaction.kind, "ranged-crowd");
  assert.ok(interaction.collisionExtent < 0.4);
  assert.equal(interaction.pathObstructs, false);
});


test("a large mobile-ranged body remains compliant after committing", () => {
  const units = [
    unit(1, 1, 1, {
      mechanics: largeRangedMechanics,
      action: "reload",
      attackTargetId: 9,
    }),
    unit(2, 1.45, 1, { mechanics: largeRangedMechanics }),
  ];
  const result = planRangedCrowding(
    units,
    [proposal(1, 0), proposal(2, -0.1)],
    15,
  );
  const interaction = result.contactReservations.get("1:2");

  assert.equal(interaction.kind, "ranged-crowd");
  assert.ok(Math.abs(interaction.collisionExtent - 0.35) < 1e-12);
  assert.equal(interaction.pathObstructs, false);
});


test("a committed Siege-class body obstructs regardless of its radius", () => {
  const units = [
    unit(1, 1, 1, {
      mechanics: siegeRangedMechanics,
      action: "reload",
      attackTargetId: 9,
    }),
    unit(2, 1.3, 1, { mechanics: siegeRangedMechanics }),
  ];
  const result = planRangedCrowding(
    units,
    [proposal(1, 0), proposal(2, -0.05)],
    16,
  );
  const interaction = result.contactReservations.get("1:2");

  assert.ok(Math.abs(interaction.collisionExtent - 0.3) < 1e-12);
  assert.equal(interaction.pathObstructs, true);
});
