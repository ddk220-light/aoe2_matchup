import assert from "node:assert/strict";
import test from "node:test";

import {
  createEnemyTransitState,
  separateInheritedContactProposals,
  updateEnemyTransit,
} from "../src/combat/enemy-transit.js";


function unit(referenceId, owner, x, y = 5, {
  alive = true,
  pursuitTargetId = null,
  attackRange = 0,
  ranged = false,
  radius = 0.25,
  action = "idle",
  engagedTargetId = null,
  attackTargetId = null,
  moveOrder = null,
} = {}) {
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    alive,
    pursuitTargetId,
    engagedTargetId,
    attackTargetId,
    action,
    moveOrder,
    mechanics: Object.freeze({
      attack_range_tiles: attackRange,
      min_collision_size_multiplier: 0.8,
      collision_size_tiles: Object.freeze({ x: radius, y: radius }),
      ...(ranged ? {
        ranged: Object.freeze({ min_range_tiles: 0 }),
      } : {}),
    }),
  });
}


function proposal(referenceId, dx, dy = 0) {
  return Object.freeze({ referenceId, dx, dy });
}


function update(units, proposals, state = createEnemyTransitState(), tick = 10) {
  return updateEnemyTransit({ state, units, proposals, tick });
}


function normalize(result) {
  return {
    reservations: [...result.state.reservations]
      .map(([key, value]) => [key, { ...value }]),
    inherited: [...result.state.inheritedContactExtents],
    transit: [...result.pairSnapshotData.enemyTransitPairs]
      .map(([key, value]) => [key, { ...value }]),
    swept: [...result.pairSnapshotData.sweptEnemyContactExtents],
    inheritedSnapshot: [...result.pairSnapshotData.inheritedEnemyContactExtents],
    diagnostics: result.diagnostics.map((entry) => ({ ...entry })),
  };
}


test("a progressing melee pursuer reserves the nearest non-target enemy in its corridor", () => {
  const chaser = unit(1, 3, 1, 5, { pursuitTargetId: 3 });
  const blocker = unit(2, 2, 1.51, 5.1);
  const target = unit(3, 2, 5, 5);

  const result = update(
    [chaser, blocker, target],
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
  );

  assert.deepEqual([...result.state.reservations.keys()], ["1:2"]);
  assert.deepEqual(result.state.reservations.get("1:2"), {
    chaserId: 1,
    blockerId: 2,
    pursuitTargetId: 3,
    mode: "melee-pursuit",
    acquisitionAxis: "x",
    acquisitionSign: 1,
    acquiredTick: 10,
  });
  assert.deepEqual(
    result.pairSnapshotData.enemyTransitPairs,
    result.state.reservations,
  );
});


test("corridor transit opens only inside a one-tick mechanics-derived contact window", () => {
  const chaser = unit(1, 3, 1, 5, { pursuitTargetId: 3 });
  const blocker = unit(2, 2, 2.2, 5.1);
  const target = unit(3, 2, 5, 5);

  const result = update(
    [chaser, blocker, target],
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
  );

  assert.equal(result.state.reservations.size, 0);
});


test("one-range melee uses the same transit rule while ranged movers cannot initiate it", () => {
  const blocker = unit(2, 2, 1.51, 5);
  const target = unit(3, 2, 5, 5);
  const reachMelee = unit(1, 3, 1, 5, {
    pursuitTargetId: 3,
    attackRange: 1,
  });
  const ranged = unit(4, 3, 1, 5.1, {
    pursuitTargetId: 3,
    attackRange: 4,
    ranged: true,
  });

  const result = update(
    [reachMelee, ranged, blocker, target],
    [proposal(1, 0.02), proposal(4, 0.02), proposal(2, 0), proposal(3, 0)],
  );

  assert.deepEqual([...result.state.reservations.keys()], ["1:2"]);
});


test("a moving ranged formation member can transit one engaged melee enemy", () => {
  const mover = unit(1, 2, 1, 5, {
    pursuitTargetId: 2,
    ranged: true,
    attackRange: 4,
    moveOrder: { x: 5, y: 5 },
  });
  const engagedMelee = unit(2, 3, 1.7, 5, {
    engagedTargetId: 3,
    action: "attacking",
  });
  const engagedTarget = unit(3, 2, 0, 5, { ranged: true, attackRange: 4 });
  const result = update(
    [mover, engagedMelee, engagedTarget],
    [proposal(1, 0, 0.02), proposal(2, 0), proposal(3, 0)],
  );

  assert.deepEqual([...result.state.reservations.keys()], ["1:2"]);
  assert.equal(result.state.reservations.get("1:2").chaserId, 1);
  assert.equal(result.state.reservations.get("1:2").mode, "formation-flow");
  assert.equal(result.diagnostics.at(-1).reason, "moving-through-engaged-enemy");
});


test("allies, dead units, idle movers, and off-corridor enemies stay hard", () => {
  const target = unit(3, 2, 5, 5);
  const cases = [
    {
      name: "ally",
      units: [
        unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
        unit(2, 3, 1.7, 5),
        target,
      ],
      proposals: [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
    },
    {
      name: "dead blocker",
      units: [
        unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
        unit(2, 2, 1.7, 5, { alive: false }),
        target,
      ],
      proposals: [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
    },
    {
      name: "idle chaser",
      units: [
        unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
        unit(2, 2, 1.7, 5),
        target,
      ],
      proposals: [proposal(1, 0), proposal(2, 0), proposal(3, 0)],
    },
    {
      name: "off corridor",
      units: [
        unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
        unit(2, 2, 1.7, 6),
        target,
      ],
      proposals: [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
    },
    {
      name: "moving away",
      units: [
        unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
        unit(2, 2, 1.7, 5),
        target,
      ],
      proposals: [proposal(1, -0.02), proposal(2, 0), proposal(3, 0)],
    },
  ];

  for (const entry of cases) {
    assert.equal(
      update(entry.units, entry.proposals).state.reservations.size,
      0,
      entry.name,
    );
  }
});


test("a melee pursuer tracks direct contact without spending a deep transit slot", () => {
  const chaser = unit(1, 3, 1, 5, { pursuitTargetId: 2 });
  const target = unit(2, 2, 1.51, 5);
  const result = update([chaser, target], [proposal(1, 0.02), proposal(2, 0)]);

  assert.deepEqual([...result.state.reservations.keys()], ["1:2"]);
  assert.equal(result.state.reservations.get("1:2").mode, "engagement-contact");

  const distantTarget = unit(2, 2, 1.7, 5);
  assert.equal(update(
    [chaser, distantTarget],
    [proposal(1, 0.02), proposal(2, 0)],
  ).state.reservations.size, 0);
});


test("a moving ranged direct target receives only an engagement contact", () => {
  const chaser = unit(1, 3, 1, 5, { pursuitTargetId: 2 });
  const target = unit(2, 2, 1.51, 5, { ranged: true, attackRange: 4 });
  const result = update(
    [chaser, target],
    [proposal(1, 0), proposal(2, -0.02)],
  );

  assert.deepEqual([...result.state.reservations.keys()], ["1:2"]);
  assert.equal(result.state.reservations.get("1:2").mode, "engagement-contact");
});


test("an untracked square-overlap is inherited even outside circular contact", () => {
  const left = unit(1, 2, 1, 5);
  const right = unit(2, 3, 1.49, 5.49);
  const result = update(
    [left, right],
    [proposal(1, 0), proposal(2, 0)],
  );

  assert.ok(Math.abs(result.state.inheritedContactExtents.get("1:2") - 0.49) < 1e-12);
  assert.equal(result.diagnostics.at(-1).reason, "published-square-overlap");
});


test("one chaser can hold a hard direct engagement and one deep corridor transit", () => {
  const chaser = unit(1, 3, 1, 5, { pursuitTargetId: 3 });
  const blocker = unit(2, 2, 1.51, 5);
  const target = unit(3, 2, 1.55, 5);
  const result = update(
    [chaser, blocker, target],
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
  );

  assert.deepEqual([...result.state.reservations.keys()].sort(), ["1:2", "1:3"]);
  assert.equal(result.state.reservations.get("1:2").mode, "melee-pursuit");
  assert.equal(result.state.reservations.get("1:3").mode, "engagement-contact");
});


test("a moving direct target upgrades hard engagement contact to formation transit", () => {
  const mover = unit(1, 2, 1, 5, {
    ranged: true,
    attackRange: 4,
    moveOrder: { x: 2, y: 5 },
  });
  const attacker = unit(2, 3, 1.51, 5, {
    pursuitTargetId: 1,
    engagedTargetId: 1,
    attackTargetId: 1,
    action: "attacking",
  });
  const initial = update(
    [mover, attacker],
    [proposal(1, 0), proposal(2, 0)],
  ).state;
  const result = update(
    [mover, attacker],
    [proposal(1, 0.02), proposal(2, 0)],
    initial,
    11,
  );

  assert.equal(result.state.reservations.get("1:2").mode, "formation-flow");
});


test("a blocked formation upgrade preserves its existing engagement contact", () => {
  const mover = unit(1, 2, 1, 5, {
    ranged: true,
    attackRange: 4,
    moveOrder: { x: 2, y: 5 },
  });
  const attacker = unit(2, 3, 1.51, 5, {
    pursuitTargetId: 1,
    engagedTargetId: 1,
    attackTargetId: 1,
    action: "attacking",
  });
  const otherBlocker = unit(3, 3, 1.8, 5, {
    engagedTargetId: 1,
    action: "attacking",
  });
  const state = Object.freeze({
    reservations: new Map([
      ["1:2", Object.freeze({
        chaserId: 2,
        blockerId: 1,
        pursuitTargetId: 1,
        mode: "engagement-contact",
        acquisitionAxis: "x",
        acquisitionSign: -1,
        acquiredTick: 9,
      })],
      ["1:3", Object.freeze({
        chaserId: 1,
        blockerId: 3,
        pursuitTargetId: 3,
        mode: "formation-flow",
        acquisitionAxis: "x",
        acquisitionSign: 1,
        acquiredTick: 9,
      })],
    ]),
    inheritedContactExtents: new Map(),
  });

  const result = update(
    [mover, attacker, otherBlocker],
    [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)],
    state,
    11,
  );

  assert.equal(result.state.reservations.get("1:2").mode, "engagement-contact");
  assert.equal(result.state.reservations.get("1:3").mode, "formation-flow");
});


test("deep enemy transit is a deterministic one-to-one matching", () => {
  const units = [
    unit(1, 3, 1, 4.95, { pursuitTargetId: 3 }),
    unit(4, 3, 1, 5.05, { pursuitTargetId: 3 }),
    unit(2, 2, 1.51, 5),
    unit(3, 2, 5, 5),
  ];
  const proposals = [
    proposal(1, 0.02),
    proposal(4, 0.02),
    proposal(2, 0),
    proposal(3, 0),
  ];

  const forward = update(units, proposals);
  const reversed = update([...units].reverse(), [...proposals].reverse());

  assert.equal(forward.state.reservations.size, 1);
  assert.deepEqual([...forward.state.reservations.keys()], ["1:2"]);
  assert.deepEqual(normalize(forward), normalize(reversed));
});


test("an eligible existing reservation persists instead of switching partners", () => {
  const prior = Object.freeze({
    chaserId: 1,
    blockerId: 2,
    pursuitTargetId: 3,
    acquisitionAxis: "x",
    acquisitionSign: 1,
    acquiredTick: 5,
  });
  const state = Object.freeze({
    reservations: new Map([["1:2", prior]]),
    inheritedContactExtents: new Map(),
  });
  const result = update([
    unit(1, 3, 1.2, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 1.8, 5),
    unit(4, 2, 1.7, 5.05),
    unit(3, 2, 5, 5),
  ], [
    proposal(1, 0.02),
    proposal(2, 0),
    proposal(4, 0),
    proposal(3, 0),
  ], state, 11);

  assert.equal(result.state.reservations.get("1:2"), prior);
  assert.equal(result.state.reservations.has("1:4"), false);
});


test("a crossed and separating reservation releases into inherited overlap", () => {
  const prior = Object.freeze({
    chaserId: 1,
    blockerId: 2,
    pursuitTargetId: 3,
    acquisitionAxis: "x",
    acquisitionSign: 1,
    acquiredTick: 5,
  });
  const state = Object.freeze({
    reservations: new Map([["1:2", prior]]),
    inheritedContactExtents: new Map(),
  });
  const result = update([
    unit(1, 3, 2.05, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 2, 5),
    unit(3, 2, 5, 5),
  ], [proposal(1, 0.02), proposal(2, 0), proposal(3, 0)], state, 20);

  assert.equal(result.state.reservations.size, 0);
  assert.ok(Math.abs(
    result.state.inheritedContactExtents.get("1:2") - 0.05,
  ) < 1e-12);
  assert.ok(Math.abs(
    result.pairSnapshotData.inheritedEnemyContactExtents.get("1:2") - 0.05,
  ) < 1e-12);
  assert.equal(result.diagnostics.at(-1).reason, "crossed-and-separating");
});


test("death and unrelated retargeting release reservations", () => {
  const prior = Object.freeze({
    chaserId: 1,
    blockerId: 2,
    pursuitTargetId: 3,
    acquisitionAxis: "x",
    acquisitionSign: 1,
    acquiredTick: 5,
  });
  const state = Object.freeze({
    reservations: new Map([["1:2", prior]]),
    inheritedContactExtents: new Map(),
  });
  const cases = [
    {
      reason: "target-missing",
      units: [unit(1, 3, 1.4, 5, { pursuitTargetId: 3 }), unit(2, 2, 1.7, 5)],
    },
    {
      reason: "target-changed",
      units: [
        unit(1, 3, 1.4, 5, { pursuitTargetId: 4 }),
        unit(2, 2, 1.7, 5),
        unit(3, 2, 5, 5),
        unit(4, 2, 0, 5),
      ],
    },
  ];

  for (const entry of cases) {
    const proposals = entry.units.map(({ referenceId }) => (
      proposal(referenceId, referenceId === 1 ? 0.02 : 0)
    ));
    const result = update(entry.units, proposals, state, 20);
    assert.equal(result.state.reservations.size, 0, entry.reason);
    assert.equal(result.diagnostics.at(-1).reason, entry.reason);
  }
});


test("a chase-captured blocker keeps its active contact reservation", () => {
  const prior = Object.freeze({
    chaserId: 1,
    blockerId: 2,
    pursuitTargetId: 3,
    acquisitionAxis: "x",
    acquisitionSign: 1,
    acquiredTick: 5,
  });
  const state = Object.freeze({
    reservations: new Map([["1:2", prior]]),
    inheritedContactExtents: new Map(),
  });
  const result = update([
    unit(1, 3, 1.4, 5, { pursuitTargetId: 2 }),
    unit(2, 2, 1.7, 5),
    unit(3, 2, 5, 5),
  ], [proposal(1, 0), proposal(2, 0), proposal(3, 0)], state, 20);

  assert.equal(result.state.reservations.size, 1);
  assert.equal(result.state.reservations.get("1:2").pursuitTargetId, 2);
  assert.equal(result.diagnostics.at(-1).type, "enemy-transit-persisted");
  assert.equal(result.diagnostics.at(-1).reason, "blocker-captured-in-contact");
});


test("an attack-locked blocker keeps contact across pursuit retargeting", () => {
  const prior = Object.freeze({
    chaserId: 1,
    blockerId: 2,
    pursuitTargetId: 3,
    mode: "melee-pursuit",
    acquisitionAxis: "x",
    acquisitionSign: 1,
    acquiredTick: 5,
  });
  const state = Object.freeze({
    reservations: new Map([["1:2", prior]]),
    inheritedContactExtents: new Map(),
  });
  const result = update([
    unit(1, 3, 1.4, 5, {
      pursuitTargetId: 4,
      engagedTargetId: 2,
      attackTargetId: 2,
      action: "attacking",
    }),
    unit(2, 2, 1.7, 5),
    unit(3, 2, 5, 5),
    unit(4, 2, 4, 5),
  ], [proposal(1, 0), proposal(2, 0), proposal(3, 0), proposal(4, 0)], state, 20);

  assert.equal(result.state.reservations.size, 1);
  assert.equal(result.state.reservations.get("1:2").pursuitTargetId, 2);
  assert.equal(result.diagnostics.at(-1).type, "enemy-transit-persisted");
  assert.equal(result.diagnostics.at(-1).reason, "blocker-captured-in-contact");
});


test("a near-contact reservation survives a temporary zero-step pursuit stall", () => {
  const prior = Object.freeze({
    chaserId: 1,
    blockerId: 2,
    pursuitTargetId: 3,
    acquisitionAxis: "x",
    acquisitionSign: 1,
    acquiredTick: 5,
  });
  const state = Object.freeze({
    reservations: new Map([["1:2", prior]]),
    inheritedContactExtents: new Map(),
  });
  const result = update([
    unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 1.7, 5),
    unit(3, 2, 5, 5),
  ], [proposal(1, 0), proposal(2, 0), proposal(3, 0)], state, 20);

  assert.equal(result.state.reservations.get("1:2"), prior);
  assert.equal(result.diagnostics.at(-1).reason, "near-contact-stall");
});


test("swept enemy contact derives a one-tick legal extent from relative motion", () => {
  const chaser = unit(1, 3, 1, 5, { pursuitTargetId: 3 });
  const crossing = unit(2, 2, 1.52, 5);
  const target = unit(3, 2, 1, 8);
  const result = update(
    [chaser, crossing, target],
    [proposal(1, 0, 0.02), proposal(2, -0.03), proposal(3, 0)],
  );

  assert.equal(result.state.reservations.size, 0);
  assert.ok(Math.abs(
    result.pairSnapshotData.sweptEnemyContactExtents.get("1:2") - 0.49,
  ) < 1e-12);
  assert.ok(Math.abs(result.state.inheritedContactExtents.get("1:2") - 0.49) < 1e-12);
});


test("ranged-ranged and idle boundary crossings do not create swept contact", () => {
  const target = unit(3, 2, 1, 8);
  const ranged = unit(1, 3, 1, 5, {
    pursuitTargetId: 3,
    attackRange: 4,
    ranged: true,
  });
  const crossing = unit(2, 2, 1.52, 5, { ranged: true, attackRange: 4 });
  const idleMelee = unit(4, 3, 1, 6, { pursuitTargetId: null });
  const idleCrossing = unit(5, 2, 1.52, 6);

  const result = update(
    [ranged, crossing, idleMelee, idleCrossing, target],
    [
      proposal(1, 0.03),
      proposal(2, 0),
      proposal(4, 0.03),
      proposal(5, 0),
      proposal(3, 0),
    ],
  );

  assert.equal(result.pairSnapshotData.sweptEnemyContactExtents.size, 0);
});


test("inherited contact tracks current separation and cannot deepen", () => {
  const state = Object.freeze({
    reservations: new Map(),
    inheritedContactExtents: new Map([["1:2", 0.3]]),
  });
  const target = unit(3, 2, 5, 5);
  const inward = update([
    unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 1.3, 5),
    target,
  ], [proposal(1, 0.02), proposal(2, -0.02), proposal(3, 0)], state);

  assert.ok(Math.abs(
    inward.pairSnapshotData.inheritedEnemyContactExtents.get("1:2") - 0.3,
  ) < 1e-12);

  const separated = update([
    unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 1.34, 5),
    target,
  ], [proposal(1, 0), proposal(2, 0.02), proposal(3, 0)], inward.state, 11);

  assert.ok(Math.abs(
    separated.pairSnapshotData.inheritedEnemyContactExtents.get("1:2") - 0.34,
  ) < 1e-12);

  const cleared = update([
    unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 1.5, 5),
    target,
  ], [proposal(1, 0), proposal(2, 0.02), proposal(3, 0)], separated.state, 12);

  assert.equal(cleared.state.inheritedContactExtents.has("1:2"), false);
});


test("an inherited overlap keeps both units out of new deep transit pairs", () => {
  const state = Object.freeze({
    reservations: new Map(),
    inheritedContactExtents: new Map([["1:2", 0.45]]),
  });
  const result = update([
    unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 1.45, 5),
    unit(4, 2, 1.51, 5.05),
    unit(3, 2, 5, 5),
  ], [
    proposal(1, 0.02),
    proposal(2, 0),
    proposal(4, 0),
    proposal(3, 0),
  ], state, 11);

  assert.equal(result.state.reservations.has("1:4"), false);
  assert.equal(result.state.inheritedContactExtents.has("1:2"), true);
});


test("a moving inherited pair spends its step clearing the collision normal", () => {
  const left = unit(1, 2, 1, 5);
  const right = unit(2, 3, 1.4, 5);
  const inheritedContactExtents = new Map([["1:2", 0.4]]);

  assert.deepEqual(separateInheritedContactProposals({
    units: [left, right],
    proposals: [proposal(1, 0.02), proposal(2, 0)],
    inheritedContactExtents,
    inheritedContactSources: new Map([["1:2", "melee-pursuit"]]),
  }), [proposal(1, -0.02), proposal(2, 0)]);

  assert.deepEqual(separateInheritedContactProposals({
    units: [left, right],
    proposals: [proposal(1, -0.02), proposal(2, 0)],
    inheritedContactExtents,
    inheritedContactSources: new Map([["1:2", "melee-pursuit"]]),
  }), [proposal(1, -0.02), proposal(2, 0)]);
});


test("released direct engagement also clears its collision normal when moving", () => {
  const left = unit(1, 2, 1, 5);
  const right = unit(2, 3, 1.4, 5);
  const proposals = [proposal(1, 0.02), proposal(2, 0)];

  assert.deepEqual(separateInheritedContactProposals({
    units: [left, right],
    proposals,
    inheritedContactExtents: new Map([["1:2", 0.4]]),
    inheritedContactSources: new Map([["1:2", "engagement-contact"]]),
  }), [proposal(1, -0.02), proposal(2, 0)]);
});


test("inherited direct engagement does not consume a deep transit slot", () => {
  const state = Object.freeze({
    reservations: new Map(),
    inheritedContactExtents: new Map([["1:2", 0.45]]),
    inheritedContactSources: new Map([["1:2", "engagement-contact"]]),
  });
  const result = update([
    unit(1, 3, 1, 5, { pursuitTargetId: 3 }),
    unit(2, 2, 1.45, 5),
    unit(4, 2, 1.51, 5.05),
    unit(3, 2, 5, 5),
  ], [
    proposal(1, 0.02),
    proposal(2, 0),
    proposal(4, 0),
    proposal(3, 0),
  ], state, 11);

  assert.equal(result.state.reservations.has("1:4"), true);
});


test("a published enemy-footprint overlap is inherited before the next collision solve", () => {
  const result = update(
    [unit(1, 3, 1, 5), unit(2, 2, 1.3, 5)],
    [proposal(1, 0), proposal(2, 0)],
  );

  assert.ok(Math.abs(result.state.inheritedContactExtents.get("1:2") - 0.3) < 1e-12);
  assert.equal(result.diagnostics.some(({ type, reason }) => (
    type === "enemy-transit-recovered" && reason === "published-square-overlap"
  )), true);
});
