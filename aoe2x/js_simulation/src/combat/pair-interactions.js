import { collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;
const VALID_LEGACY_MODES = new Set([
  "always",
  "attacking-any",
  "attacking-target",
  "attacking-other",
]);


function requireReferenceId(value, name = "reference ID") {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


function requireMap(value, name) {
  if (!(value instanceof Map)) throw new TypeError(`${name} must be a Map`);
  return value;
}


function requireSet(value, name) {
  if (!(value instanceof Set)) throw new TypeError(`${name} must be a Set`);
  return value;
}


function requireExtent(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  if (value < 0) throw new RangeError(`${name} must be nonnegative`);
  return value;
}


function validateCanonicalPairKey(key, name) {
  if (typeof key !== "string") throw new TypeError(`${name} key must be a string`);
  const match = /^(\d+):(\d+)$/.exec(key);
  if (!match) throw new TypeError(`${name} key must be canonical`);
  const left = Number(match[1]);
  const right = Number(match[2]);
  requireReferenceId(left, `${name} left reference ID`);
  requireReferenceId(right, `${name} right reference ID`);
  if (left >= right || dynamicPairKey(left, right) !== key) {
    throw new TypeError(`${name} key must be canonical`);
  }
}


function normalizePairSet(value, name) {
  const result = new Set();
  for (const key of requireSet(value, name)) {
    validateCanonicalPairKey(key, name);
    result.add(key);
  }
  return result;
}


function normalizeExtentMap(value, name) {
  const result = new Map();
  for (const [key, extent] of requireMap(value, `${name}s`)) {
    validateCanonicalPairKey(key, name);
    result.set(key, requireExtent(extent, `${name} extent`));
  }
  return result;
}


function normalizeTransitPairs(value) {
  const result = new Map();
  for (const [key, reservation] of requireMap(value, "enemy transit pairs")) {
    validateCanonicalPairKey(key, "enemy transit pair");
    if (!reservation || typeof reservation !== "object" || Array.isArray(reservation)) {
      throw new TypeError("enemy transit reservation must be an object");
    }
    const chaserId = requireReferenceId(reservation.chaserId, "transit chaser ID");
    const blockerId = requireReferenceId(reservation.blockerId, "transit blocker ID");
    const pursuitTargetId = requireReferenceId(
      reservation.pursuitTargetId,
      "transit pursuit target ID",
    );
    if (dynamicPairKey(chaserId, blockerId) !== key) {
      throw new TypeError("enemy transit reservation IDs must match its pair key");
    }
    if (!Number.isSafeInteger(reservation.acquiredTick) || reservation.acquiredTick < 0) {
      throw new TypeError("transit acquired tick must be a nonnegative safe integer");
    }
    if (reservation.acquisitionAxis !== "x" && reservation.acquisitionAxis !== "y") {
      throw new RangeError("transit acquisition axis must be x or y");
    }
    if (reservation.acquisitionSign !== -1 && reservation.acquisitionSign !== 1) {
      throw new RangeError("transit acquisition sign must be -1 or 1");
    }
    result.set(key, Object.freeze({
      chaserId,
      blockerId,
      pursuitTargetId,
      acquisitionAxis: reservation.acquisitionAxis,
      acquisitionSign: reservation.acquisitionSign,
      acquiredTick: reservation.acquiredTick,
    }));
  }
  return result;
}


function normalizeLegacyPolicies(value) {
  const result = new Map();
  for (const [master, rawPolicy] of requireMap(
    value,
    "legacy enemy overlap depths by master",
  )) {
    requireReferenceId(master, "legacy enemy overlap unit master");
    const policy = typeof rawPolicy === "number"
      ? { depth: rawPolicy, mode: "always" }
      : rawPolicy;
    if (!policy || typeof policy !== "object" || Array.isArray(policy)) {
      throw new TypeError("legacy enemy overlap policy must be a depth or policy object");
    }
    const depth = requireExtent(policy.depth, "legacy enemy overlap depth");
    const mode = policy.mode ?? "always";
    if (!VALID_LEGACY_MODES.has(mode)) {
      throw new RangeError(`unknown legacy enemy overlap mode ${mode}`);
    }
    result.set(master, Object.freeze({ depth, mode }));
  }
  return result;
}


function sourceUnit(body) {
  return body.unit ?? body;
}


function fullPairExtent(left, right) {
  const leftRadius = Number.isFinite(left.radius) ? left.radius : collisionRadius(left);
  const rightRadius = Number.isFinite(right.radius) ? right.radius : collisionRadius(right);
  return leftRadius + rightRadius;
}


function legacyPolicyApplies(configuredBody, opponentBody, mode) {
  if (mode === "always") return true;
  const configured = sourceUnit(configuredBody);
  const opponent = sourceUnit(opponentBody);
  const fullExtent = fullPairExtent(configuredBody, opponentBody);
  const alreadyOverlapping = Math.max(
    Math.abs(configuredBody.x - opponentBody.x),
    Math.abs(configuredBody.y - opponentBody.y),
  ) < fullExtent - EPSILON;
  if (alreadyOverlapping) return true;
  if (opponent.action !== "attacking") return false;
  if (mode === "attacking-any") return true;
  const targetId = opponent.attackTargetId
    ?? opponent.engagedTargetId
    ?? opponent.pursuitTargetId
    ?? null;
  const directTarget = targetId === configured.referenceId;
  return mode === "attacking-target" ? directTarget : !directTarget;
}


function legacyOverlapDepth(left, right, policies) {
  if (left.owner === right.owner) return 0;
  const leftMaster = left.unitMaster ?? left.mechanics?.unit_master;
  const rightMaster = right.unitMaster ?? right.mechanics?.unit_master;
  let depth = 0;
  for (const [configured, opponent, master] of [
    [left, right, leftMaster],
    [right, left, rightMaster],
  ]) {
    const policy = policies.get(master);
    if (policy && legacyPolicyApplies(configured, opponent, policy.mode)) {
      depth = Math.max(depth, policy.depth);
    }
  }
  return depth;
}


function interaction(kind, collisionExtent, pathObstructs,
  attackSurfaceExtent, mayDeepen, reason) {
  return Object.freeze({
    kind,
    collisionExtent,
    pathObstructs,
    attackSurfaceExtent,
    mayDeepen,
    reason,
  });
}


export function dynamicPairKey(leftId, rightId) {
  requireReferenceId(leftId, "left reference ID");
  requireReferenceId(rightId, "right reference ID");
  if (leftId === rightId) throw new RangeError("a dynamic pair requires two references");
  return leftId < rightId ? `${leftId}:${rightId}` : `${rightId}:${leftId}`;
}


export function createPairInteractionSnapshot({
  alliedTransitPairs = new Set(),
  alliedShrinkPairs = new Set(),
  alliedShallowPairs = new Set(),
  alliedShrinkReservedIds = new Set(),
  exclusiveAlliedShrinkOwners = new Set(),
  legacyEnemyOverlapDepthByMaster = new Map(),
  enemyTransitPairs = new Map(),
  sweptEnemyContactExtents = new Map(),
  inheritedEnemyContactExtents = new Map(),
} = {}) {
  const normalizedReservedIds = new Set();
  for (const referenceId of requireSet(
    alliedShrinkReservedIds,
    "allied shrink reserved IDs",
  )) {
    normalizedReservedIds.add(requireReferenceId(referenceId, "allied shrink reserved ID"));
  }
  const normalizedOwners = new Set();
  for (const owner of requireSet(
    exclusiveAlliedShrinkOwners,
    "exclusive allied shrink owners",
  )) {
    normalizedOwners.add(requireReferenceId(owner, "exclusive allied shrink owner"));
  }
  return Object.freeze({
    alliedTransitPairs: normalizePairSet(alliedTransitPairs, "allied transit pair"),
    alliedShrinkPairs: normalizePairSet(alliedShrinkPairs, "allied shrink pair"),
    alliedShallowPairs: normalizePairSet(alliedShallowPairs, "allied shallow pair"),
    alliedShrinkReservedIds: normalizedReservedIds,
    exclusiveAlliedShrinkOwners: normalizedOwners,
    legacyEnemyOverlapDepthByMaster: normalizeLegacyPolicies(
      legacyEnemyOverlapDepthByMaster,
    ),
    enemyTransitPairs: normalizeTransitPairs(enemyTransitPairs),
    sweptEnemyContactExtents: normalizeExtentMap(
      sweptEnemyContactExtents,
      "swept enemy contact",
    ),
    inheritedEnemyContactExtents: normalizeExtentMap(
      inheritedEnemyContactExtents,
      "inherited enemy contact",
    ),
  });
}


export function resolvePairInteraction(left, right,
  snapshot = createPairInteractionSnapshot()) {
  if (!snapshot || typeof snapshot !== "object") {
    throw new TypeError("pair interaction snapshot is required");
  }
  const extent = fullPairExtent(left, right);

  if (left.owner === right.owner) {
    const alliedTransit = snapshot.alliedTransitPairs.size > 0
      && snapshot.alliedTransitPairs.has(dynamicPairKey(left.referenceId, right.referenceId));
    if (alliedTransit) {
      return interaction("allied-transit", 0, false, extent, true, "reserved-allied-transit");
    }
    return interaction("hard", extent, true, extent, false, "hard-allied-contact");
  }

  const hasStatefulEnemyPairs = snapshot.enemyTransitPairs.size > 0
    || snapshot.sweptEnemyContactExtents.size > 0
    || snapshot.inheritedEnemyContactExtents.size > 0;
  const key = hasStatefulEnemyPairs
    ? dynamicPairKey(left.referenceId, right.referenceId)
    : null;
  if (snapshot.enemyTransitPairs.has(key)) {
    return interaction("transit", 0, false, extent, true, "non-target-corridor");
  }
  if (snapshot.sweptEnemyContactExtents.has(key)) {
    const sweptExtent = snapshot.sweptEnemyContactExtents.get(key);
    if (sweptExtent >= extent) {
      return interaction("hard", extent, true, extent, false, "hard-enemy-contact");
    }
    return interaction("swept", sweptExtent, true, extent, false, "swept-contact");
  }
  if (snapshot.inheritedEnemyContactExtents.has(key)) {
    const inheritedExtent = snapshot.inheritedEnemyContactExtents.get(key);
    if (inheritedExtent >= extent) {
      return interaction("hard", extent, true, extent, false, "hard-enemy-contact");
    }
    return interaction(
      "inherited",
      inheritedExtent,
      true,
      extent,
      false,
      "released-overlap",
    );
  }

  const legacyDepth = legacyOverlapDepth(
    left,
    right,
    snapshot.legacyEnemyOverlapDepthByMaster,
  );
  if (legacyDepth > 0) {
    if (legacyDepth >= extent) {
      throw new RangeError(
        `enemy overlap depth ${legacyDepth} must be smaller than pair extent ${extent}`,
      );
    }
    return interaction(
      "legacy",
      extent - legacyDepth,
      true,
      extent - legacyDepth,
      true,
      "legacy-unit-policy",
    );
  }
  return interaction("hard", extent, true, extent, false, "hard-enemy-contact");
}
