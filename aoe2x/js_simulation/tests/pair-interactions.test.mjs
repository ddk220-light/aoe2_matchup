import assert from "node:assert/strict";
import test from "node:test";

import {
  createPairInteractionSnapshot,
  dynamicPairKey,
  resolvePairInteraction,
} from "../src/combat/pair-interactions.js";


function unit({
  referenceId,
  owner,
  x = 4,
  y = 4,
  radius = 0.2,
  unitMaster = 1,
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
    unitMaster,
    action,
    pursuitTargetId,
    engagedTargetId,
    attackTargetId,
    mechanics: Object.freeze({
      unit_master: unitMaster,
      min_collision_size_multiplier: 0.8,
      collision_size_tiles: Object.freeze({ x: radius, y: radius }),
    }),
  });
}


test("dynamic pair keys are independent of argument order", () => {
  assert.equal(dynamicPairKey(9, 2), "2:9");
  assert.equal(dynamicPairKey(2, 9), "2:9");
});


test("ordinary enemies use one hard physical pair extent for every purpose", () => {
  const left = unit({ referenceId: 1, owner: 2, radius: 0.2 });
  const right = unit({ referenceId: 2, owner: 3, radius: 0.3 });

  assert.deepEqual(
    resolvePairInteraction(left, right, createPairInteractionSnapshot()),
    {
      kind: "hard",
      collisionExtent: 0.5,
      pathObstructs: true,
      attackSurfaceExtent: 0.5,
      mayDeepen: false,
      reason: "hard-enemy-contact",
    },
  );
});


test("unified contact reservations are the authoritative pair surface", () => {
  const left = unit({ referenceId: 1, owner: 2, radius: 0.25 });
  const right = unit({ referenceId: 2, owner: 2, radius: 0.25 });
  const snapshot = createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", Object.freeze({
      leftId: 1,
      rightId: 2,
      kind: "allied-transit",
      collisionExtent: 0.25,
      attackSurfaceExtent: 0.5,
      pathObstructs: true,
      mayDeepen: true,
      initiatorId: 1,
      targetId: null,
      acquiredTick: 10,
    })]]),
  });

  assert.deepEqual(resolvePairInteraction(left, right, snapshot), {
    kind: "allied-transit",
    collisionExtent: 0.25,
    pathObstructs: true,
    attackSurfaceExtent: 0.5,
    mayDeepen: true,
    reason: "unified-contact-reservation",
  });
});


test("unified pair geometry is validated once for every consumer", () => {
  const reservation = (overrides = {}) => Object.freeze({
    leftId: 1,
    rightId: 2,
    kind: "enemy-transit",
    collisionExtent: 0.2,
    attackSurfaceExtent: 0.5,
    pathObstructs: false,
    mayDeepen: true,
    initiatorId: 1,
    targetId: 3,
    acquiredTick: 10,
    ...overrides,
  });

  assert.throws(() => createPairInteractionSnapshot({
    contactReservations: new Map([["2:1", reservation()]]),
  }), /canonical/);
  assert.throws(() => createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", reservation({ rightId: 3 })]]),
  }), /IDs must match/);
  assert.throws(() => createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", reservation({ collisionExtent: -0.1 })]]),
  }), /nonnegative/);
  assert.throws(() => createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", reservation({ kind: "calibrated" })]]),
  }), /unknown contact reservation kind/);
  assert.throws(() => createPairInteractionSnapshot({
    contactReservations: new Map([["1:2", reservation()]]),
    enemyTransitPairs: new Map([["1:2", Object.freeze({
      chaserId: 1,
      blockerId: 2,
      pursuitTargetId: 3,
      acquisitionAxis: "x",
      acquisitionSign: 1,
      acquiredTick: 10,
    })]]),
  }), /both unified and legacy/);
});


test("the shared experiment projects circular enemy contact into the movement axes", () => {
  const left = unit({ referenceId: 1, owner: 2, x: 4, y: 4, radius: 0.25 });
  const right = unit({ referenceId: 2, owner: 3, x: 5, y: 5, radius: 0.25 });
  const interaction = resolvePairInteraction(left, right, createPairInteractionSnapshot({
    circularEnemyContact: true,
  }));

  assert.equal(interaction.kind, "circular-contact");
  assert.ok(Math.abs(interaction.collisionExtent - Math.SQRT1_2 * 0.5) < 1e-12);
  assert.equal(interaction.pathObstructs, true);
  assert.ok(Math.abs(interaction.attackSurfaceExtent - Math.SQRT1_2 * 0.5) < 1e-12);
  assert.equal(interaction.mayDeepen, false);
});


test("circular enemy contact applies only to explicitly eligible initiators", () => {
  const eligible = unit({ referenceId: 1, owner: 3, x: 4, y: 4, radius: 0.25 });
  const reachMelee = unit({ referenceId: 2, owner: 3, x: 4, y: 4, radius: 0.25 });
  const target = unit({ referenceId: 3, owner: 2, x: 5, y: 5, radius: 0.25 });
  const snapshot = createPairInteractionSnapshot({
    circularEnemyContact: true,
    circularEnemyContactInitiatorIds: new Set([1]),
  });

  assert.equal(resolvePairInteraction(eligible, target, snapshot).kind, "circular-contact");
  assert.equal(resolvePairInteraction(reachMelee, target, snapshot).kind, "hard");
});


test("a reserved transit pair remains transparent under circular projection", () => {
  const left = unit({ referenceId: 1, owner: 3, x: 4, y: 4, radius: 0.25 });
  const right = unit({ referenceId: 2, owner: 2, x: 5, y: 5, radius: 0.25 });
  const snapshot = createPairInteractionSnapshot({
    circularEnemyContact: true,
    enemyTransitPairs: new Map([["1:2", Object.freeze({
      chaserId: 1,
      blockerId: 2,
      pursuitTargetId: 2,
      mode: "formation-flow",
      acquisitionAxis: "x",
      acquisitionSign: 1,
      acquiredTick: 10,
    })]]),
  });
  const interaction = resolvePairInteraction(left, right, snapshot);

  assert.equal(interaction.collisionExtent, 0);
  assert.equal(interaction.attackSurfaceExtent, 0);
});


test("a ranged-ingress pair compresses to half extent without becoming transparent", () => {
  const rear = unit({ referenceId: 1, owner: 3, x: 4, y: 4, radius: 0.2 });
  const front = unit({ referenceId: 2, owner: 3, x: 4, y: 4.4, radius: 0.2 });
  const snapshot = createPairInteractionSnapshot({
    alliedRangedIngressPairs: new Set(["1:2"]),
  });

  const resolved = resolvePairInteraction(rear, front, snapshot);

  assert.equal(resolved.kind, "allied-ranged-ingress");
  assert.equal(resolved.collisionExtent, 0.2);
  assert.equal(resolved.pathObstructs, true);
  assert.equal(resolved.attackSurfaceExtent, 0.4);
  assert.equal(resolved.mayDeepen, true);
});


test("active pursuit paths ignore non-target enemies without waiving their collision", () => {
  const chaser = unit({ referenceId: 1, owner: 3, x: 4, y: 4, radius: 0.25 });
  const blocker = unit({ referenceId: 2, owner: 2, x: 5, y: 5, radius: 0.25 });
  const target = unit({ referenceId: 3, owner: 2, x: 6, y: 6, radius: 0.25 });
  const snapshot = createPairInteractionSnapshot({
    circularEnemyContact: true,
    enemyPursuitTargets: new Map([[1, 3]]),
  });

  const corridor = resolvePairInteraction(chaser, blocker, snapshot);
  assert.equal(corridor.kind, "pursuit-corridor");
  assert.equal(corridor.pathObstructs, false);
  assert.ok(corridor.collisionExtent > 0);

  const direct = resolvePairInteraction(chaser, target, snapshot);
  assert.equal(direct.kind, "circular-contact");
  assert.equal(direct.pathObstructs, true);
});


test("snapshots reject malformed pair-state collections before movement", () => {
  assert.throws(
    () => createPairInteractionSnapshot({ enemyTransitPairs: new Set() }),
    /enemy transit pairs must be a Map/,
  );
  assert.throws(
    () => createPairInteractionSnapshot({
      inheritedEnemyContactExtents: new Map([["1:2", -0.1]]),
    }),
    /inherited enemy contact extent must be nonnegative/,
  );
});


test("ordinary pursuit transit uses DAT compression while unrelated enemies stay hard", () => {
  const left = unit({ referenceId: 1, owner: 3, radius: 0.25 });
  const right = unit({ referenceId: 2, owner: 2, radius: 0.3 });
  const snapshot = createPairInteractionSnapshot({
    enemyTransitPairs: new Map([["1:2", Object.freeze({
      chaserId: 1,
      blockerId: 2,
      pursuitTargetId: 3,
      acquisitionAxis: "x",
      acquisitionSign: 1,
      acquiredTick: 10,
    })]]),
  });

  assert.deepEqual(resolvePairInteraction(left, right, snapshot), {
    kind: "transit",
    collisionExtent: 0.5,
    pathObstructs: false,
    attackSurfaceExtent: 0.5,
    mayDeepen: true,
    reason: "reserved-pair-compression",
  });
});


test("engagement contact uses both bodies' DAT shrink allowances", () => {
  const left = unit({ referenceId: 1, owner: 3, radius: 0.25 });
  const right = unit({ referenceId: 2, owner: 2, radius: 0.25 });
  const snapshot = createPairInteractionSnapshot({
    enemyTransitPairs: new Map([["1:2", Object.freeze({
      chaserId: 1,
      blockerId: 2,
      pursuitTargetId: 2,
      mode: "engagement-contact",
      acquisitionAxis: "x",
      acquisitionSign: 1,
      acquiredTick: 10,
    })]]),
  });

  assert.equal(resolvePairInteraction(left, right, snapshot).collisionExtent, 0.4);
});


test("direct engagement cannot compress into a larger target footprint", () => {
  const chaser = unit({ referenceId: 1, owner: 3, x: 1, y: 1, radius: 0.25 });
  const largeTarget = unit({ referenceId: 2, owner: 2, x: 1.7, y: 1, radius: 0.4 });
  const snapshot = createPairInteractionSnapshot({
    enemyTransitPairs: new Map([["1:2", Object.freeze({
      chaserId: 1,
      blockerId: 2,
      pursuitTargetId: 2,
      mode: "engagement-contact",
      acquisitionAxis: "x",
      acquisitionSign: 1,
      acquiredTick: 10,
    })]]),
  });

  assert.equal(resolvePairInteraction(chaser, largeTarget, snapshot).collisionExtent, 0.65);
});


test("inherited enemy overlap preserves its current extent without allowing deepening", () => {
  const left = unit({ referenceId: 1, owner: 3, radius: 0.25 });
  const right = unit({ referenceId: 2, owner: 2, radius: 0.3 });
  const snapshot = createPairInteractionSnapshot({
    inheritedEnemyContactExtents: new Map([["1:2", 0.43]]),
  });

  assert.deepEqual(resolvePairInteraction(left, right, snapshot), {
    kind: "inherited",
    collisionExtent: 0.43,
    pathObstructs: true,
    attackSurfaceExtent: 0.55,
    mayDeepen: false,
    reason: "released-overlap",
  });
});


test("legacy overlap policies preserve all existing action modes", () => {
  const wagon = unit({
    referenceId: 1,
    owner: 2,
    x: 4,
    radius: 0.35,
    unitMaster: 829,
  });
  const opponent = (overrides = {}) => unit({
    referenceId: 2,
    owner: 3,
    x: 4.7,
    radius: 0.3,
    ...overrides,
  });
  const policy = (mode) => createPairInteractionSnapshot({
    legacyEnemyOverlapDepthByMaster: new Map([[829, { depth: 0.1, mode }]]),
  });

  assert.ok(Math.abs(
    resolvePairInteraction(wagon, opponent(), policy("always")).collisionExtent - 0.55,
  ) < 1e-12);
  assert.equal(
    resolvePairInteraction(wagon, opponent(), policy("attacking-any")).kind,
    "hard",
  );
  assert.equal(
    resolvePairInteraction(wagon, opponent({ action: "attacking" }),
      policy("attacking-any")).kind,
    "legacy",
  );
  assert.equal(
    resolvePairInteraction(wagon, opponent({
      action: "attacking",
      attackTargetId: 1,
    }), policy("attacking-target")).kind,
    "legacy",
  );
  assert.equal(
    resolvePairInteraction(wagon, opponent({
      action: "attacking",
      attackTargetId: 99,
    }), policy("attacking-other")).kind,
    "legacy",
  );
});


test("an already-overlapping legacy pair remains legal across its action transition", () => {
  const wagon = unit({
    referenceId: 1,
    owner: 2,
    x: 4,
    radius: 0.35,
    unitMaster: 829,
  });
  const opponent = unit({
    referenceId: 2,
    owner: 3,
    x: 4.6,
    radius: 0.3,
    action: "idle",
  });
  const snapshot = createPairInteractionSnapshot({
    legacyEnemyOverlapDepthByMaster: new Map([[
      829,
      { depth: 0.1, mode: "attacking-target" },
    ]]),
  });

  const interaction = resolvePairInteraction(wagon, opponent, snapshot);
  assert.equal(interaction.kind, "legacy");
  assert.ok(Math.abs(interaction.collisionExtent - 0.55) < 1e-12);
  assert.ok(Math.abs(interaction.attackSurfaceExtent - 0.55) < 1e-12);
});
