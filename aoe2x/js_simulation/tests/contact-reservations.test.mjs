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
  speed_tiles_per_second: 1.2,
  ranged: null,
});

const rangedMechanics = (radius = 0.2, range = 5) => Object.freeze({
  collision_size_tiles: Object.freeze({ x: radius, y: radius }),
  outline_size_tiles: Object.freeze({ x: radius, y: radius }),
  min_collision_size_multiplier: 0.8,
  attack_range_tiles: range,
  speed_tiles_per_second: 1.2,
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

test("allied transit derives its floor from both sourced multipliers", () => {
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

test("shared formation orders clear stale pair state until the order ends", () => {
  const ordered = (x) => unit(1, 2, x, {
    moveOrder: Object.freeze({ x: 8, y: 4 }),
  });
  const orderedPeer = (x) => unit(2, 2, x, {
    moveOrder: Object.freeze({ x: 8.5, y: 4 }),
  });
  const stale = Object.freeze({
    reservations: new Map(),
    inheritedExtents: new Map([["1:2", 0.4]]),
  });
  const during = updateContactReservations({
    state: stale,
    tick: 11,
    units: [ordered(4), orderedPeer(4.25)],
    proposals: [proposal(1, 0.02), proposal(2, -0.02)],
  });

  assert.equal(during.contactReservations.size, 0);
  assert.equal(during.state.inheritedExtents.size, 0);
  assert.equal(during.state.reservations.size, 0);

  const after = updateContactReservations({
    state: during.state,
    tick: 12,
    units: [unit(1, 2, 4), unit(2, 2, 4.21)],
    proposals: [proposal(1, 0), proposal(2, 0)],
  });
  assert.equal(after.contactReservations.get("1:2").kind, "releasing");
  assert.equal(after.contactReservations.get("1:2").collisionExtent, 0.21);
});

test("allied convergence gives one deep lane without compounding shallow overlap", () => {
  const units = [
    unit(1, 2, 4, { pursuitTargetId: 4 }),
    unit(2, 2, 4.5, { pursuitTargetId: 4 }),
    unit(3, 2, 4, { pursuitTargetId: 4, y: 4.5 }),
    unit(4, 3, 7, { action: "idle" }),
  ];
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 10,
    units,
    proposals: [
      proposal(1, 0.03, 0.04),
      proposal(2, 0),
      proposal(3, 0),
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
  assert.equal(interactions.filter(({ kind }) => kind === "shallow-contact").length, 0);
  assert.equal(interactions.filter(({ kind }) => kind === "hard").length, 2);
});

test("one unit may hold one allied transit and one enemy engagement contact", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 10,
    units: [
      unit(1, 2, 4, { y: 4, pursuitTargetId: 3 }),
      unit(2, 2, 4.5, { y: 4, action: "idle" }),
      unit(3, 3, 4.5, { y: 4.5, action: "idle" }),
    ],
    proposals: [proposal(1, 0.03, 0.03), proposal(2, 0), proposal(3, 0)],
  });

  assert.equal(result.state.reservations.size, 2);
  assert.deepEqual(
    [...result.state.reservations.values()].map(({ kind }) => kind).sort(),
    ["allied-transit", "engagement-contact"],
  );
});

test("a target accepts two directed engagements and leaves a third transient", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 10,
    units: [
      unit(1, 2, 4, { y: 4, pursuitTargetId: 4 }),
      unit(2, 2, 4, { y: 4.5, pursuitTargetId: 4 }),
      unit(3, 2, 4.5, { y: 3.75, pursuitTargetId: 4 }),
      unit(4, 3, 4.5, { y: 4.25, action: "idle" }),
    ],
    proposals: [
      proposal(1, 0.03, 0.015),
      proposal(2, 0.03, -0.015),
      proposal(3, 0, 0.03),
      proposal(4, 0),
    ],
  });
  const engagements = [...result.state.reservations.values()]
    .filter(({ kind }) => kind === "engagement-contact");
  const shallow = [...result.contactReservations.values()]
    .filter(({ kind }) => kind === "shallow-contact");

  assert.equal(engagements.length, 2);
  assert.equal(shallow.length, 1);
  assert.ok(engagements.every(({ targetId }) => targetId === 4));
});

test("shallow contact depth is exactly one tick of sourced relative closure", () => {
  const units = [
    unit(1, 2, 4, { y: 4, pursuitTargetId: 4 }),
    unit(2, 2, 4, { y: 4.5, pursuitTargetId: 4 }),
    unit(3, 2, 4.5, { y: 3.75, pursuitTargetId: 4 }),
    unit(4, 3, 4.5, { y: 4.25, action: "idle" }),
  ];
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 11,
    units,
    proposals: [
      proposal(1, 0.03, 0.015),
      proposal(2, 0.03, -0.015),
      proposal(3, 0, 0.03),
      proposal(4, 0),
    ],
  });
  const shallow = [...result.contactReservations.values()]
    .find(({ kind }) => kind === "shallow-contact");

  assert.ok(shallow);
  assert.equal(shallow.collisionExtent, 0.47);
  assert.equal(shallow.mayDeepen, false);
  assert.equal(shallow.pathObstructs, false);
  assert.equal([...result.state.reservations.values()].some(
    ({ kind }) => kind === "shallow-contact",
  ), false);
});

test("shallow contact becomes a non-deep release surface until separation", () => {
  const first = updateContactReservations({
    state: createContactReservationState(),
    tick: 12,
    units: [
      unit(1, 2, 4, { y: 4, pursuitTargetId: 4 }),
      unit(2, 2, 4, { y: 4.5, pursuitTargetId: 4 }),
      unit(3, 2, 4.5, { y: 3.75, pursuitTargetId: 4 }),
      unit(4, 3, 4.5, { y: 4.25, action: "idle" }),
    ],
    proposals: [
      proposal(1, 0.03, 0.015),
      proposal(2, 0.03, -0.015),
      proposal(3, 0, 0.03),
      proposal(4, 0),
    ],
  });
  const shallowEntry = [...first.contactReservations.entries()]
    .find(([, { kind }]) => kind === "shallow-contact");
  assert.ok(shallowEntry);
  const [key, shallow] = shallowEntry;
  const [leftId, rightId] = key.split(":").map(Number);
  const positions = new Map([
    [1, { x: 4.03, y: 4.015 }],
    [2, { x: 4.03, y: 4.485 }],
    [3, { x: 4.5, y: 3.78 }],
    [4, { x: 4.5, y: 4.25 }],
  ]);
  const secondUnits = [
    unit(1, 2, positions.get(1).x, { y: positions.get(1).y, action: "idle" }),
    unit(2, 2, positions.get(2).x, { y: positions.get(2).y, action: "idle" }),
    unit(3, 2, positions.get(3).x, { y: positions.get(3).y, action: "idle" }),
    unit(4, 3, positions.get(4).x, { y: positions.get(4).y, action: "idle" }),
  ];
  const second = updateContactReservations({
    state: first.state,
    tick: 13,
    units: secondUnits,
    proposals: [proposal(1, 0), proposal(2, 0), proposal(3, 0), proposal(4, 0)],
  });
  const release = second.contactReservations.get(key);

  assert.ok([leftId, rightId].every((id) => positions.has(id)));
  assert.equal(release.kind, "releasing");
  assert.equal(release.collisionExtent, shallow.collisionExtent);
  assert.equal(release.mayDeepen, false);
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

test("unrelated closing enemies remain hard instead of gaining incidental shallow contact", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 19,
    units: [unit(1, 2, 4), unit(2, 3, 4.5)],
    proposals: [proposal(1, 0.03), proposal(2, -0.03)],
  });

  assert.equal(result.contactReservations.size, 0);
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

test("natural separation advances a release surface so recovered space stays recovered", () => {
  const state = Object.freeze({
    reservations: new Map(),
    inheritedExtents: new Map([["1:2", 0.3]]),
  });
  const result = updateContactReservations({
    state,
    tick: 21,
    units: [unit(1, 2, 4), unit(2, 2, 4.34)],
    proposals: [proposal(1, -0.02), proposal(2, 0.02)],
  });
  const release = result.contactReservations.get("1:2");

  assert.equal(release.kind, "releasing");
  assert.equal(release.collisionExtent, 0.34);
  assert.equal(result.state.inheritedExtents.get("1:2"), 0.34);
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

test("a moving chaser can pass one stationary attacking ally", () => {
  const result = updateContactReservations({
    state: createContactReservationState(),
    tick: 42,
    units: [
      unit(1, 2, 4, { pursuitTargetId: 3 }),
      unit(2, 2, 4.5, { action: "attacking", attackTargetId: 3 }),
      unit(3, 3, 6, { action: "idle" }),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0), proposal(3, 0)],
  });

  assert.equal(result.contactReservations.get("1:2").kind, "allied-transit");
  assert.equal(result.contactReservations.get("1:2").initiatorId, 1);
  assert.equal(result.contactReservations.get("1:2").pathObstructs, false);
});

test("allied transit past an attacker persists until the moving unit clears it", () => {
  const acquired = updateContactReservations({
    state: createContactReservationState(),
    tick: 43,
    units: [
      unit(1, 2, 4, { pursuitTargetId: 3 }),
      unit(2, 2, 4.5, { action: "attacking", attackTargetId: 3 }),
      unit(3, 3, 6, { action: "idle" }),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0), proposal(3, 0)],
  });
  const persisted = updateContactReservations({
    state: acquired.state,
    tick: 44,
    units: [
      unit(1, 2, 4.1, { pursuitTargetId: 3 }),
      unit(2, 2, 4.5, { action: "attacking", attackTargetId: 3 }),
      unit(3, 3, 6, { action: "idle" }),
    ],
    proposals: [proposal(1, 0.1), proposal(2, 0), proposal(3, 0)],
  });

  assert.equal(persisted.contactReservations.get("1:2").kind, "allied-transit");
  assert.equal(persisted.contactReservations.get("1:2").pathObstructs, false);
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

test("mixed-radius allied transit derives its floor from both bodies", () => {
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
