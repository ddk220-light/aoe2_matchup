import { collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;
const VALID_LEGACY_MODES = new Set([
  "always",
  "attacking-any",
  "attacking-target",
  "attacking-other",
]);
const VALID_CONTACT_RESERVATION_KINDS = new Set([
  "allied-transit",
  "enemy-transit",
  "engagement-contact",
  "releasing",
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


function requireBoolean(value, name) {
  if (typeof value !== "boolean") throw new TypeError(`${name} must be a boolean`);
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
    const mode = reservation.mode ?? "melee-pursuit";
    if (mode !== "melee-pursuit"
        && mode !== "formation-flow"
        && mode !== "engagement-contact") {
      throw new RangeError(`unknown enemy transit mode ${mode}`);
    }
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
      mode,
      acquisitionAxis: reservation.acquisitionAxis,
      acquisitionSign: reservation.acquisitionSign,
      acquiredTick: reservation.acquiredTick,
    }));
  }
  return result;
}


function normalizeContactReservations(value) {
  const result = new Map();
  for (const [key, reservation] of requireMap(value, "contact reservations")) {
    validateCanonicalPairKey(key, "contact reservation");
    if (!reservation || typeof reservation !== "object" || Array.isArray(reservation)) {
      throw new TypeError("contact reservation must be an object");
    }
    const leftId = requireReferenceId(reservation.leftId, "contact left ID");
    const rightId = requireReferenceId(reservation.rightId, "contact right ID");
    if (dynamicPairKey(leftId, rightId) !== key) {
      throw new TypeError("contact reservation IDs must match its pair key");
    }
    const kind = reservation.kind;
    if (!VALID_CONTACT_RESERVATION_KINDS.has(kind)) {
      throw new RangeError(`unknown contact reservation kind ${kind}`);
    }
    const collisionExtent = requireExtent(
      reservation.collisionExtent,
      "contact collision extent",
    );
    const attackSurfaceExtent = requireExtent(
      reservation.attackSurfaceExtent,
      "contact attack surface extent",
    );
    if (collisionExtent > attackSurfaceExtent + EPSILON) {
      throw new RangeError("contact collision extent cannot exceed its attack surface extent");
    }
    const initiatorId = reservation.initiatorId === null
      ? null
      : requireReferenceId(reservation.initiatorId, "contact initiator ID");
    const targetId = reservation.targetId === null
      ? null
      : requireReferenceId(reservation.targetId, "contact target ID");
    if (!Number.isSafeInteger(reservation.acquiredTick) || reservation.acquiredTick < 0) {
      throw new TypeError("contact acquired tick must be a nonnegative safe integer");
    }
    result.set(key, Object.freeze({
      leftId,
      rightId,
      kind,
      collisionExtent,
      attackSurfaceExtent,
      pathObstructs: requireBoolean(
        reservation.pathObstructs,
        "contact pathObstructs",
      ),
      mayDeepen: requireBoolean(reservation.mayDeepen, "contact mayDeepen"),
      initiatorId,
      targetId,
      acquiredTick: reservation.acquiredTick,
    }));
  }
  return result;
}


function rejectUnifiedLegacyDuplicates(contactReservations, collections) {
  for (const [name, collection] of collections) {
    for (const key of collection.keys()) {
      if (contactReservations.has(key)) {
        throw new Error(`pair ${key} exists in both unified and legacy ${name}`);
      }
    }
  }
}


function normalizePursuitTargets(value) {
  const result = new Map();
  for (const [chaserId, targetId] of requireMap(value, "enemy pursuit targets")) {
    const normalizedChaserId = requireReferenceId(chaserId, "pursuit chaser ID");
    const normalizedTargetId = requireReferenceId(targetId, "pursuit target ID");
    if (normalizedChaserId === normalizedTargetId) {
      throw new RangeError("a pursuit target must differ from its chaser");
    }
    result.set(normalizedChaserId, normalizedTargetId);
  }
  return result;
}


function normalizeOptionalReferenceScope(value, name) {
  if (value === null) return null;
  const result = new Set();
  for (const referenceId of requireSet(value, name)) {
    result.add(requireReferenceId(referenceId, `${name} reference ID`));
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


function shrinkAllowance(body) {
  const source = sourceUnit(body);
  const radius = Number.isFinite(body.radius) ? body.radius : collisionRadius(body);
  const multiplier = source?.mechanics?.min_collision_size_multiplier;
  if (!Number.isFinite(multiplier)) return 0;
  if (multiplier <= 0 || multiplier > 1) {
    throw new RangeError("minimum collision size multiplier must be within (0, 1]");
  }
  return radius * (1 - multiplier);
}


function reservedPairExtent(left, right, reservation) {
  if (reservation.mode === "formation-flow") return 0;
  const chaser = left.referenceId === reservation.chaserId ? left : right;
  if (reservation.mode === "melee-pursuit") {
    return Math.max(0, fullPairExtent(left, right) - shrinkAllowance(chaser));
  }
  const target = left.referenceId === reservation.blockerId ? left : right;
  const chaserRadius = Number.isFinite(chaser.radius)
    ? chaser.radius : collisionRadius(chaser);
  const targetRadius = Number.isFinite(target.radius)
    ? target.radius : collisionRadius(target);
  if (targetRadius > chaserRadius + EPSILON) return fullPairExtent(left, right);
  return Math.max(
    0,
    fullPairExtent(left, right) - shrinkAllowance(chaser) - shrinkAllowance(target),
  );
}


function circularProjectedExtent(left, right, extent) {
  const dx = Math.abs(right.x - left.x);
  const dy = Math.abs(right.y - left.y);
  const distance = Math.hypot(dx, dy);
  return distance <= Number.EPSILON
    ? extent
    : extent * Math.max(dx, dy) / distance;
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
  contactReservations = new Map(),
  alliedTransitPairs = new Set(),
  alliedRangedIngressPairs = new Set(),
  alliedShrinkPairs = new Set(),
  alliedShallowPairs = new Set(),
  alliedShrinkReservedIds = new Set(),
  exclusiveAlliedShrinkOwners = new Set(),
  legacyEnemyOverlapDepthByMaster = new Map(),
  enemyTransitPairs = new Map(),
  enemyPursuitTargets = new Map(),
  sweptEnemyContactExtents = new Map(),
  inheritedEnemyContactExtents = new Map(),
  circularEnemyContact = false,
  circularEnemyContactInitiatorIds = null,
} = {}) {
  if (typeof circularEnemyContact !== "boolean") {
    throw new TypeError("circular enemy contact must be a boolean");
  }
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
  const normalizedContactReservations = normalizeContactReservations(contactReservations);
  const normalizedAlliedTransitPairs = normalizePairSet(
    alliedTransitPairs,
    "allied transit pair",
  );
  const normalizedAlliedRangedIngressPairs = normalizePairSet(
    alliedRangedIngressPairs,
    "allied ranged-ingress pair",
  );
  const normalizedAlliedShrinkPairs = normalizePairSet(
    alliedShrinkPairs,
    "allied shrink pair",
  );
  const normalizedAlliedShallowPairs = normalizePairSet(
    alliedShallowPairs,
    "allied shallow pair",
  );
  const normalizedEnemyTransitPairs = normalizeTransitPairs(enemyTransitPairs);
  const normalizedSweptEnemyContactExtents = normalizeExtentMap(
    sweptEnemyContactExtents,
    "swept enemy contact",
  );
  const normalizedInheritedEnemyContactExtents = normalizeExtentMap(
    inheritedEnemyContactExtents,
    "inherited enemy contact",
  );
  rejectUnifiedLegacyDuplicates(normalizedContactReservations, [
    ["allied transit pairs", normalizedAlliedTransitPairs],
    ["allied ranged-ingress pairs", normalizedAlliedRangedIngressPairs],
    ["allied shrink pairs", normalizedAlliedShrinkPairs],
    ["allied shallow pairs", normalizedAlliedShallowPairs],
    ["enemy transit pairs", normalizedEnemyTransitPairs],
    ["swept enemy contacts", normalizedSweptEnemyContactExtents],
    ["inherited enemy contacts", normalizedInheritedEnemyContactExtents],
  ]);
  return Object.freeze({
    contactReservations: normalizedContactReservations,
    alliedTransitPairs: normalizedAlliedTransitPairs,
    alliedRangedIngressPairs: normalizedAlliedRangedIngressPairs,
    alliedShrinkPairs: normalizedAlliedShrinkPairs,
    alliedShallowPairs: normalizedAlliedShallowPairs,
    alliedShrinkReservedIds: normalizedReservedIds,
    exclusiveAlliedShrinkOwners: normalizedOwners,
    legacyEnemyOverlapDepthByMaster: normalizeLegacyPolicies(
      legacyEnemyOverlapDepthByMaster,
    ),
    enemyTransitPairs: normalizedEnemyTransitPairs,
    enemyPursuitTargets: normalizePursuitTargets(enemyPursuitTargets),
    sweptEnemyContactExtents: normalizedSweptEnemyContactExtents,
    inheritedEnemyContactExtents: normalizedInheritedEnemyContactExtents,
    circularEnemyContact,
    circularEnemyContactInitiatorIds: normalizeOptionalReferenceScope(
      circularEnemyContactInitiatorIds,
      "circular enemy contact initiator IDs",
    ),
  });
}


export function resolvePairInteraction(left, right,
  snapshot = createPairInteractionSnapshot()) {
  if (!snapshot || typeof snapshot !== "object") {
    throw new TypeError("pair interaction snapshot is required");
  }
  const extent = fullPairExtent(left, right);
  const unifiedReservations = snapshot.contactReservations instanceof Map
    ? snapshot.contactReservations
    : new Map();
  const unifiedKey = unifiedReservations.size > 0
    ? dynamicPairKey(left.referenceId, right.referenceId)
    : null;
  const unified = unifiedReservations.get(unifiedKey);
  if (unified) {
    return interaction(
      unified.kind,
      unified.collisionExtent,
      unified.pathObstructs,
      unified.attackSurfaceExtent,
      unified.mayDeepen,
      "unified-contact-reservation",
    );
  }

  if (left.owner === right.owner) {
    const alliedTransit = snapshot.alliedTransitPairs.size > 0
      && snapshot.alliedTransitPairs.has(dynamicPairKey(left.referenceId, right.referenceId));
    if (alliedTransit) {
      return interaction("allied-transit", 0, false, extent, true, "reserved-allied-transit");
    }
    const rangedIngress = snapshot.alliedRangedIngressPairs.size > 0
      && snapshot.alliedRangedIngressPairs.has(
        dynamicPairKey(left.referenceId, right.referenceId),
      );
    if (rangedIngress) {
      return interaction(
        "allied-ranged-ingress",
        0.5 * extent,
        true,
        extent,
        true,
        "reserved-ranged-ingress",
      );
    }
    return interaction("hard", extent, true, extent, false, "hard-allied-contact");
  }

  const circularEnemyContact = snapshot.circularEnemyContact
    && (snapshot.circularEnemyContactInitiatorIds === null
      || snapshot.circularEnemyContactInitiatorIds.has(left.referenceId)
      || snapshot.circularEnemyContactInitiatorIds.has(right.referenceId));

  const hasStatefulEnemyPairs = snapshot.enemyTransitPairs.size > 0
    || snapshot.sweptEnemyContactExtents.size > 0
    || snapshot.inheritedEnemyContactExtents.size > 0;
  const key = hasStatefulEnemyPairs
    ? dynamicPairKey(left.referenceId, right.referenceId)
    : null;
  if (snapshot.enemyTransitPairs.has(key)) {
    const reservation = snapshot.enemyTransitPairs.get(key);
    const compressedExtent = reservedPairExtent(left, right, reservation);
    const approachExtent = circularEnemyContact
      ? circularProjectedExtent(left, right, compressedExtent)
      : compressedExtent;
    return interaction(
      "transit",
      approachExtent,
      false,
      approachExtent,
      true,
      "reserved-pair-compression",
    );
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


  const leftPursuitTarget = snapshot.enemyPursuitTargets.get(left.referenceId);
  const rightPursuitTarget = snapshot.enemyPursuitTargets.get(right.referenceId);
  const pursuitCorridor = (leftPursuitTarget !== undefined
      && leftPursuitTarget !== right.referenceId)
    || (rightPursuitTarget !== undefined
      && rightPursuitTarget !== left.referenceId);
  if (pursuitCorridor) {
    const projectedExtent = circularEnemyContact
      ? circularProjectedExtent(left, right, extent)
      : extent;
    return interaction(
      "pursuit-corridor",
      projectedExtent,
      false,
      projectedExtent,
      false,
      "non-target-pursuit-path",
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
  if (circularEnemyContact) {
    const projectedExtent = circularProjectedExtent(left, right, extent);
    return interaction(
      "circular-contact",
      projectedExtent,
      true,
      projectedExtent,
      false,
      "circular-enemy-contact",
    );
  }
  return interaction("hard", extent, true, extent, false, "hard-enemy-contact");
}
