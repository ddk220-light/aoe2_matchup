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


test("reserved enemy transit waives non-target obstruction but not attack geometry", () => {
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
    collisionExtent: 0,
    pathObstructs: false,
    attackSurfaceExtent: 0.55,
    mayDeepen: true,
    reason: "non-target-corridor",
  });
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
