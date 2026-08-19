import assert from "node:assert/strict";
import test from "node:test";

import {
  createContactReservationState,
  updateContactReservations,
} from "../src/combat/contact-reservations.js";
import {
  createPairInteractionSnapshot,
  resolvePairInteraction,
} from "../src/combat/pair-interactions.js";

const mechanics = (radius, multiplier = 0.5, range = 0) => Object.freeze({
  collision_size_tiles: Object.freeze({ x: radius, y: radius }),
  min_collision_size_multiplier: multiplier,
  attack_range_tiles: range,
  ranged: null,
});

const rangedMechanics = (radius = 0.2, range = 5) => Object.freeze({
  collision_size_tiles: Object.freeze({ x: radius, y: radius }),
  outline_size_tiles: Object.freeze({ x: radius, y: radius }),
  min_collision_size_multiplier: 0.8,
  attack_range_tiles: range,
  ranged: Object.freeze({ projectile_speed_tiles_per_second: 7 }),
});

const unit = (referenceId, owner, x, overrides = {}) => Object.freeze({
  referenceId,
  owner,
  x,
  y: 4,
  alive: true,
  mechanics: mechanics(0.25),
  pursuitTargetId: null,
  engagedTargetId: null,
  attackTargetId: null,
  action: "moving",
  ...overrides,
});

const proposal = (referenceId, dx, dy = 0) => Object.freeze({ referenceId, dx, dy });

function sortedReservations(result) {
  return [...result.contactReservations]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => [key, value]);
}

test("a closing allied pair derives its floor from both sourced multipliers", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 10,
    units: [unit(1, 2, 4), unit(2, 2, 4.5)],
    proposals: [proposal(1, 0.1), proposal(2, -0.1)],
  });

  assert.equal(result.contactReservations.get("1:2").kind, "allied-transit");
  assert.equal(result.contactReservations.get("1:2").collisionExtent, 0.25);
  assert.equal(result.contactReservations.get("1:2").pathObstructs, false);
});

test("three-on-one convergence gives one allied lane and ordinary third-unit surfaces", () => {
  const units = [
    unit(1, 2, 4, { pursuitTargetId: 4 }),
    unit(2, 2, 4.5, { pursuitTargetId: 4 }),
    unit(3, 2, 4.25, { pursuitTargetId: 4 }),
    unit(4, 3, 7, { action: "idle" }),
  ];
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 10,
    units,
    proposals: [
      proposal(1, 0.1),
      proposal(2, -0.1),
      proposal(3, 0.05),
      proposal(4, 0),
    ],
  });
  const snapshot = createPairInteractionSnapshot({
    contactReservations: result.contactReservations,
  });
  const alliedPairs = [[units[0], units[1]], [units[0], units[2]], [units[1], units[2]]];
  const interactions = alliedPairs.map(([left, right]) => (
    resolvePairInteraction(left, right, snapshot)
  ));

  assert.equal(result.contactReservations.size, 1);
  assert.equal(interactions.filter(({ kind }) => kind === "allied-transit").length, 1);
  assert.equal(interactions.filter(({ kind }) => kind === "hard").length, 2);
});

test("stopped or attacking allies cannot newly acquire transit", () => {
  for (const action of ["idle", "attacking"]) {
    const units = [unit(1, 2, 4, { action }), unit(2, 2, 4.45, { action })];
    const result = updateContactReservations({
      state: createContactReservationState(),
      units,
      proposals: [proposal(1, 0), proposal(2, 0)],
      tick: 20,
    });
    assert.equal(
      [...result.contactReservations.values()].some(({ kind }) => kind === "allied-transit"),
      false,
      action,
    );
  }
});

test("an inherited pair releases monotonically without further deepening", () => {
  const state = Object.freeze({
    reservations: new Map(),
    inheritedExtents: new Map([["1:2", 0.3]]),
  });
  const result = updateContactReservations({
    state,
    tick: 20,
    units: [unit(1, 2, 4), unit(2, 2, 4.3)],
    proposals: [proposal(1, -0.05), proposal(2, 0.05)],
  });
  const release = result.contactReservations.get("1:2");

  assert.equal(release.kind, "releasing");
  assert.equal(release.collisionExtent, 0.3);
  assert.equal(release.mayDeepen, false);
  assert.equal(result.state.inheritedExtents.get("1:2"), 0.3);
});

test("direct melee target contact has an attack surface distinct from collision depth", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 30,
    units: [
      unit(1, 2, 4, {
        mechanics: mechanics(0.25, 0.5, 1),
        pursuitTargetId: 2,
      }),
      unit(2, 3, 4.6),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0)],
  });
  const contact = result.contactReservations.get("1:2");

  assert.equal(contact.kind, "engagement-contact");
  assert.equal(contact.collisionExtent, 0.25);
  assert.equal(contact.attackSurfaceExtent, 1.5);
  assert.equal(contact.pathObstructs, true);
  assert.equal(contact.initiatorId, 1);
  assert.equal(contact.targetId, 2);
});

test("an already-deep direct contact preserves its current extent without deepening", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 31,
    units: [
      unit(1, 2, 4, { pursuitTargetId: 2 }),
      unit(2, 3, 4.2),
    ],
    proposals: [proposal(1, 0), proposal(2, 0)],
  });
  const contact = result.contactReservations.get("1:2");

  assert.equal(contact.kind, "engagement-contact");
  assert.equal(contact.collisionExtent, 0.2);
  assert.equal(contact.mayDeepen, false);
});

test("range-one melee can reserve a non-target enemy in its pursuit corridor", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 40,
    units: [
      unit(1, 2, 4, {
        mechanics: mechanics(0.25, 0.5, 1),
        pursuitTargetId: 3,
      }),
      unit(2, 3, 4.5),
      unit(3, 3, 6),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0), proposal(3, 0)],
  });
  const contact = result.contactReservations.get("1:2");

  assert.equal(contact.kind, "enemy-transit");
  assert.equal(contact.initiatorId, 1);
  assert.equal(contact.targetId, 3);
  assert.equal(contact.pathObstructs, false);
});

test("range-one melee can pass one stopped ally while closing on its target", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 41,
    units: [
      unit(1, 2, 4, {
        mechanics: mechanics(0.25, 0.5, 1),
        pursuitTargetId: 3,
      }),
      unit(2, 2, 4.5, { action: "idle" }),
      unit(3, 3, 6, { action: "idle" }),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0), proposal(3, 0)],
  });

  assert.equal(result.contactReservations.get("1:2").kind, "allied-transit");
  assert.equal(result.contactReservations.get("1:2").pathObstructs, false);
});

test("ranged ingress admits one out-of-range rear shooter through a front ally", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 42,
    units: [
      unit(1, 2, 4, {
        mechanics: rangedMechanics(),
        pursuitTargetId: 3,
      }),
      unit(2, 2, 4.4, {
        mechanics: rangedMechanics(),
        pursuitTargetId: 3,
      }),
      unit(3, 3, 10, {
        mechanics: rangedMechanics(),
        action: "idle",
      }),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0), proposal(3, 0)],
  });
  const ingress = result.contactReservations.get("1:2");

  assert.equal(ingress.kind, "ranged-ingress");
  assert.equal(ingress.pathObstructs, false);
  assert.equal(ingress.collisionExtent, 0.32);
});

test("an untracked overlap is published as monotonic release geometry", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 43,
    units: [
      unit(1, 2, 4, { action: "idle" }),
      unit(2, 3, 4.3, { action: "idle" }),
    ],
    proposals: [proposal(1, 0), proposal(2, 0)],
  });
  const release = result.contactReservations.get("1:2");

  assert.equal(release.kind, "releasing");
  assert.equal(release.collisionExtent, 0.3);
  assert.equal(release.mayDeepen, false);
});

test("mixed radii use both sourced floors rather than a unit-specific override", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 50,
    units: [
      unit(1, 2, 4, { mechanics: mechanics(0.2, 0.5) }),
      unit(2, 2, 4.45, { mechanics: mechanics(0.25, 0.5) }),
    ],
    proposals: [proposal(1, 0.1), proposal(2, -0.1)],
  });

  assert.equal(result.contactReservations.get("1:2").collisionExtent, 0.225);
});

test("owner swaps and array reversal leave physical reservations unchanged", () => {
  const scene = {
    state: createContactReservationState(),
    tick: 60,
    units: [
      unit(1, 2, 4, { pursuitTargetId: 3 }),
      unit(2, 3, 4.5),
      unit(3, 3, 6),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0), proposal(3, 0)],
  };
  const baseline = updateContactReservations(scene);
  const swappedAndReversed = updateContactReservations({
    ...scene,
    units: scene.units.map((entry) => Object.freeze({
      ...entry,
      owner: entry.owner === 2 ? 3 : 2,
    })).reverse(),
    proposals: [...scene.proposals].reverse(),
  });

  assert.deepEqual(sortedReservations(swappedAndReversed), sortedReservations(baseline));
});

test("death removes an active reservation instead of leaking pair state", () => {
  const active = updateContactReservations({
    state: createContactReservationState(),
    tick: 70,
    units: [unit(1, 2, 4), unit(2, 2, 4.5)],
    proposals: [proposal(1, 0.1), proposal(2, -0.1)],
  });
  const afterDeath = updateContactReservations({
    state: active.state,
    tick: 71,
    units: [unit(1, 2, 4.1), unit(2, 2, 4.4, { alive: false, action: "dead" })],
    proposals: [proposal(1, 0), proposal(2, 0)],
  });

  assert.equal(afterDeath.contactReservations.size, 0);
  assert.equal(afterDeath.state.reservations.size, 0);
});
