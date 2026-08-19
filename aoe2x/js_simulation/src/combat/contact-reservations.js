const EPSILON = 1e-12;

export function createContactReservationState() {
  return Object.freeze({
    reservations: new Map(),
    inheritedExtents: new Map(),
  });
}

export function updateContactReservations({ state, units, proposals, tick }) {
  requireInputs(state, units, proposals, tick);
  const live = units
    .filter((unit) => unit?.alive !== false)
    .slice()
    .sort((left, right) => left.referenceId - right.referenceId);
  const byReference = unitMap(live);
  const proposalByReference = proposalMap(proposals, byReference);
  const contactReservations = new Map();
  const reservations = new Map();
  const inheritedExtents = new Map();
  const reservedIds = new Set();
  const diagnostics = [];

  publishInheritedReleases({
    inherited: state.inheritedExtents,
    byReference,
    inheritedExtents,
    contactReservations,
    reservedIds,
    diagnostics,
    tick,
  });

  for (const [key, prior] of sortedEntries(state.reservations)) {
    const left = byReference.get(prior.leftId);
    const right = byReference.get(prior.rightId);
    if (!left || !right) {
      diagnostics.push(diagnostic("reservation-released", key, { reason: "unit-missing" }));
      continue;
    }
    if (reservationRemainsActive(prior, left, right, byReference, proposalByReference)) {
      if (reservedIds.has(prior.leftId) || reservedIds.has(prior.rightId)) {
        diagnostics.push(diagnostic("reservation-released", key, {
          reason: "deep-slot-conflict",
        }));
        inheritReleasedPair({
          key,
          left,
          right,
          inheritedExtents,
          contactReservations,
          reservedIds,
          diagnostics,
          tick,
        });
        continue;
      }
      reservations.set(key, prior);
      contactReservations.set(key, prior);
      reservedIds.add(prior.leftId);
      reservedIds.add(prior.rightId);
      diagnostics.push(diagnostic("reservation-persisted", key, { kind: prior.kind }));
      continue;
    }
    inheritReleasedPair({
      key,
      left,
      right,
      inheritedExtents,
      contactReservations,
      reservedIds,
      diagnostics,
      tick,
    });
  }

  const candidates = generateCandidates(live, byReference, proposalByReference, tick);
  for (const candidate of candidates) {
    if (contactReservations.has(candidate.key)
        || reservedIds.has(candidate.reservation.leftId)
        || reservedIds.has(candidate.reservation.rightId)) {
      continue;
    }
    reservations.set(candidate.key, candidate.reservation);
    contactReservations.set(candidate.key, candidate.reservation);
    reservedIds.add(candidate.reservation.leftId);
    reservedIds.add(candidate.reservation.rightId);
    diagnostics.push(diagnostic("reservation-acquired", candidate.key, {
      kind: candidate.reservation.kind,
      entryFraction: candidate.entryFraction,
      projectedNormalizedDepth: candidate.projectedNormalizedDepth,
      progress: candidate.progress,
    }));
  }

  const nextState = Object.freeze({ reservations, inheritedExtents });
  return Object.freeze({
    state: nextState,
    contactReservations,
    diagnostics: Object.freeze(diagnostics),
  });
}

function requireInputs(state, units, proposals, tick) {
  if (!state || !(state.reservations instanceof Map)
      || !(state.inheritedExtents instanceof Map)) {
    throw new TypeError("contact reservation state requires reservation and inherited maps");
  }
  if (!Array.isArray(units)) throw new TypeError("contact reservation units must be an array");
  if (!Array.isArray(proposals)) {
    throw new TypeError("contact reservation proposals must be an array");
  }
  if (!Number.isSafeInteger(tick) || tick < 0) {
    throw new RangeError("contact reservation tick must be a nonnegative safe integer");
  }
}

function unitMap(units) {
  const byReference = new Map();
  for (const unit of units) {
    const referenceId = requireReferenceId(unit?.referenceId);
    if (byReference.has(referenceId)) {
      throw new Error(`duplicate contact reservation unit ${referenceId}`);
    }
    requireFinite(unit.x, "unit x");
    requireFinite(unit.y, "unit y");
    collisionRadius(unit);
    minimumMultiplier(unit);
    byReference.set(referenceId, unit);
  }
  return byReference;
}

function proposalMap(proposals, byReference) {
  const result = new Map();
  for (const proposal of proposals) {
    const referenceId = requireReferenceId(proposal?.referenceId, "proposal reference ID");
    if (!byReference.has(referenceId)) continue;
    if (result.has(referenceId)) {
      throw new Error(`duplicate contact reservation proposal ${referenceId}`);
    }
    result.set(referenceId, Object.freeze({
      referenceId,
      dx: requireFinite(proposal.dx, "proposal dx"),
      dy: requireFinite(proposal.dy, "proposal dy"),
    }));
  }
  return result;
}

function publishInheritedReleases({
  inherited,
  byReference,
  inheritedExtents,
  contactReservations,
  reservedIds,
  diagnostics,
  tick,
}) {
  for (const [key, priorExtent] of sortedEntries(inherited)) {
    if (!Number.isFinite(priorExtent) || priorExtent < 0) {
      throw new RangeError("inherited contact extent must be finite and nonnegative");
    }
    const [leftId, rightId] = parsePairKey(key);
    const left = byReference.get(leftId);
    const right = byReference.get(rightId);
    if (!left || !right) continue;
    const fullExtent = pairFullExtent(left, right);
    const currentExtent = pairSeparation(left, right);
    if (currentExtent >= fullExtent - EPSILON) continue;
    if (reservedIds.has(leftId) || reservedIds.has(rightId)) {
      diagnostics.push(diagnostic("release-conflict", key, { priorExtent, currentExtent }));
      continue;
    }
    const publishedExtent = cleanNumber(Math.min(priorExtent, currentExtent));
    inheritedExtents.set(key, publishedExtent);
    contactReservations.set(key, releasingReservation({
      left,
      right,
      collisionExtent: publishedExtent,
      tick,
    }));
    reservedIds.add(leftId);
    reservedIds.add(rightId);
    diagnostics.push(diagnostic("release-persisted", key, {
      priorExtent,
      currentExtent,
      recoveredDeepening: currentExtent < priorExtent - EPSILON,
    }));
  }
}

function inheritReleasedPair({
  key,
  left,
  right,
  inheritedExtents,
  contactReservations,
  reservedIds,
  diagnostics,
  tick,
}) {
  const currentExtent = pairSeparation(left, right);
  if (currentExtent >= pairFullExtent(left, right) - EPSILON) {
    diagnostics.push(diagnostic("reservation-released", key, { reason: "full-separation" }));
    return;
  }
  if (reservedIds.has(left.referenceId) || reservedIds.has(right.referenceId)) {
    diagnostics.push(diagnostic("reservation-released", key, { reason: "release-slot-conflict" }));
    return;
  }
  const publishedExtent = cleanNumber(currentExtent);
  inheritedExtents.set(key, publishedExtent);
  contactReservations.set(key, releasingReservation({
    left,
    right,
    collisionExtent: publishedExtent,
    tick,
  }));
  reservedIds.add(left.referenceId);
  reservedIds.add(right.referenceId);
  diagnostics.push(diagnostic("reservation-released", key, {
    reason: "inherited-current-overlap",
    currentExtent: publishedExtent,
  }));
}

function generateCandidates(units, byReference, proposals, tick) {
  const candidates = [];
  for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
    const left = units[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
      const right = units[rightIndex];
      if (left.owner === right.owner) {
        const candidate = alliedCandidate(left, right, proposals, tick);
        if (candidate) candidates.push(candidate);
        continue;
      }
      const direct = directEngagementCandidate(left, right, proposals, tick);
      if (direct) candidates.push(direct);
      const leftCorridor = enemyCorridorCandidate(
        left,
        right,
        byReference,
        proposals,
        tick,
      );
      if (leftCorridor) candidates.push(leftCorridor);
      const rightCorridor = enemyCorridorCandidate(
        right,
        left,
        byReference,
        proposals,
        tick,
      );
      if (rightCorridor) candidates.push(rightCorridor);
    }
  }
  return candidates.sort(compareCandidates);
}

function alliedCandidate(left, right, proposals, tick) {
  if (left.action === "attacking" || right.action === "attacking") return null;
  const leftProposal = proposalFor(left, proposals);
  const rightProposal = proposalFor(right, proposals);
  if (!isMoving(leftProposal) && !isMoving(rightProposal)) return null;
  const current = pairSeparation(left, right);
  const projected = pairSeparation(left, right, leftProposal, rightProposal);
  if (projected >= current - EPSILON) return null;
  const fullExtent = pairFullExtent(left, right);
  const entryFraction = current < fullExtent - EPSILON
    ? 0
    : sweptEntryFraction(left, right, leftProposal, rightProposal, fullExtent);
  if (entryFraction === null) return null;
  const initiator = chooseInitiator(left, right, leftProposal, rightProposal);
  return makeCandidate({
    left,
    right,
    initiator,
    target: null,
    kind: "allied-transit",
    pathObstructs: false,
    entryFraction,
    projected,
    progress: stepLength(leftProposal) + stepLength(rightProposal),
    tick,
  });
}

function directEngagementCandidate(left, right, proposals, tick) {
  const directions = [
    [left, right],
    [right, left],
  ].filter(([initiator, target]) => isMelee(initiator) && directTarget(initiator, target));
  if (directions.length === 0) return null;
  directions.sort(([leftInitiator], [rightInitiator]) => (
    directTargetPriority(rightInitiator) - directTargetPriority(leftInitiator)
      || leftInitiator.referenceId - rightInitiator.referenceId
  ));
  const [initiator, target] = directions[0];
  const leftProposal = proposalFor(left, proposals);
  const rightProposal = proposalFor(right, proposals);
  const current = pairSeparation(left, right);
  const projected = pairSeparation(left, right, leftProposal, rightProposal);
  const fullExtent = pairFullExtent(left, right);
  const entryFraction = current < fullExtent - EPSILON
    ? 0
    : sweptEntryFraction(left, right, leftProposal, rightProposal, fullExtent);
  const closing = projected < current - EPSILON;
  if (entryFraction === null || (!closing && current > fullExtent + EPSILON)) return null;
  return makeCandidate({
    left,
    right,
    initiator,
    target,
    kind: "engagement-contact",
    pathObstructs: true,
    entryFraction,
    projected,
    progress: progressToward(initiator, target, proposalFor(initiator, proposals)),
    tick,
  });
}

function enemyCorridorCandidate(chaser, blocker, byReference, proposals, tick) {
  if (!isMelee(chaser)) return null;
  const target = directPursuitTarget(chaser, byReference);
  if (!target || target.referenceId === blocker.referenceId) return null;
  const chaserProposal = proposalFor(chaser, proposals);
  if (!isMoving(chaserProposal)) return null;
  const progress = progressToward(chaser, target, chaserProposal);
  if (progress <= EPSILON) return null;
  if (!insidePursuitCorridor(chaser, blocker, target)) return null;
  const blockerProposal = proposalFor(blocker, proposals);
  const current = pairSeparation(chaser, blocker);
  const projected = pairSeparation(chaser, blocker, chaserProposal, blockerProposal);
  if (projected >= current - EPSILON) return null;
  const fullExtent = pairFullExtent(chaser, blocker);
  const entryFraction = current < fullExtent - EPSILON
    ? 0
    : sweptEntryFraction(chaser, blocker, chaserProposal, blockerProposal, fullExtent);
  if (entryFraction === null) return null;
  return makeCandidate({
    left: chaser,
    right: blocker,
    initiator: chaser,
    target,
    kind: "enemy-transit",
    pathObstructs: false,
    entryFraction,
    projected,
    progress,
    tick,
  });
}

function makeCandidate({
  left,
  right,
  initiator,
  target,
  kind,
  pathObstructs,
  entryFraction,
  projected,
  progress,
  tick,
}) {
  const [canonicalLeft, canonicalRight] = left.referenceId < right.referenceId
    ? [left, right]
    : [right, left];
  const fullExtent = pairFullExtent(left, right);
  const configuredFloor = movingFloor(left, right);
  const currentExtent = pairSeparation(left, right);
  const collisionExtent = cleanNumber(Math.min(configuredFloor, currentExtent));
  const attackSurfaceExtent = kind === "engagement-contact"
    ? fullExtent + attackRange(initiator)
    : fullExtent;
  return Object.freeze({
    key: pairKey(left.referenceId, right.referenceId),
    entryFraction: cleanNumber(entryFraction),
    projectedNormalizedDepth: cleanNumber(Math.max(0, fullExtent - projected) / fullExtent),
    progress: cleanNumber(progress),
    reservation: Object.freeze({
      leftId: canonicalLeft.referenceId,
      rightId: canonicalRight.referenceId,
      kind,
      collisionExtent,
      attackSurfaceExtent: cleanNumber(attackSurfaceExtent),
      pathObstructs,
      mayDeepen: currentExtent >= configuredFloor - EPSILON,
      initiatorId: initiator.referenceId,
      targetId: target?.referenceId ?? null,
      acquiredTick: tick,
    }),
  });
}

function releasingReservation({ left, right, collisionExtent, tick }) {
  const [canonicalLeft, canonicalRight] = left.referenceId < right.referenceId
    ? [left, right]
    : [right, left];
  return Object.freeze({
    leftId: canonicalLeft.referenceId,
    rightId: canonicalRight.referenceId,
    kind: "releasing",
    collisionExtent,
    attackSurfaceExtent: pairFullExtent(left, right),
    pathObstructs: true,
    mayDeepen: false,
    initiatorId: null,
    targetId: null,
    acquiredTick: tick,
  });
}

function reservationRemainsActive(prior, left, right, byReference, proposals) {
  if (prior.kind === "allied-transit") {
    if (left.owner !== right.owner
        || left.action === "attacking"
        || right.action === "attacking") return false;
  } else if (left.owner === right.owner) {
    return false;
  }
  const current = pairSeparation(left, right);
  const projected = pairSeparation(
    left,
    right,
    proposalFor(left, proposals),
    proposalFor(right, proposals),
  );
  if (prior.kind === "engagement-contact") {
    const initiator = byReference.get(prior.initiatorId);
    const target = byReference.get(prior.targetId);
    return Boolean(initiator && target && isMelee(initiator)
      && directTarget(initiator, target)
      && current <= prior.attackSurfaceExtent + EPSILON);
  }
  if (prior.kind === "enemy-transit") {
    const initiator = byReference.get(prior.initiatorId);
    const target = byReference.get(prior.targetId);
    if (!initiator || !target || !isMelee(initiator)
        || !directTarget(initiator, target)) return false;
  }
  return (isMoving(proposalFor(left, proposals)) || isMoving(proposalFor(right, proposals)))
    && (projected < current - EPSILON || current < pairFullExtent(left, right) - EPSILON);
}

function compareCandidates(left, right) {
  return left.entryFraction - right.entryFraction
    || left.projectedNormalizedDepth - right.projectedNormalizedDepth
    || right.progress - left.progress
    || left.key.localeCompare(right.key)
    || left.reservation.initiatorId - right.reservation.initiatorId;
}

function directTarget(unit, target) {
  return unit.pursuitTargetId === target.referenceId
    || unit.engagedTargetId === target.referenceId
    || unit.attackTargetId === target.referenceId;
}

function directTargetPriority(unit) {
  if (Number.isSafeInteger(unit.attackTargetId)) return 3;
  if (Number.isSafeInteger(unit.engagedTargetId)) return 2;
  if (Number.isSafeInteger(unit.pursuitTargetId)) return 1;
  return 0;
}

function directPursuitTarget(unit, byReference) {
  for (const targetId of [unit.pursuitTargetId, unit.engagedTargetId, unit.attackTargetId]) {
    const target = byReference.get(targetId);
    if (target && target.owner !== unit.owner) return target;
  }
  return null;
}

function insidePursuitCorridor(chaser, blocker, target) {
  if (blocker.owner === chaser.owner) return false;
  const targetX = target.x - chaser.x;
  const targetY = target.y - chaser.y;
  const targetDistance = Math.hypot(targetX, targetY);
  if (targetDistance <= EPSILON) return false;
  const unitX = targetX / targetDistance;
  const unitY = targetY / targetDistance;
  const blockerX = blocker.x - chaser.x;
  const blockerY = blocker.y - chaser.y;
  const forward = blockerX * unitX + blockerY * unitY;
  const lateral = Math.abs(blockerX * unitY - blockerY * unitX);
  return forward > EPSILON
    && forward < targetDistance - EPSILON
    && lateral <= pairFullExtent(chaser, blocker) + EPSILON;
}

function progressToward(unit, target, proposal) {
  if (!proposal) return 0;
  const before = Math.hypot(target.x - unit.x, target.y - unit.y);
  const after = Math.hypot(
    target.x - unit.x - proposal.dx,
    target.y - unit.y - proposal.dy,
  );
  return Math.max(0, before - after);
}

function chooseInitiator(left, right, leftProposal, rightProposal) {
  const leftStep = stepLength(leftProposal);
  const rightStep = stepLength(rightProposal);
  if (leftStep > rightStep + EPSILON) return left;
  if (rightStep > leftStep + EPSILON) return right;
  return left.referenceId < right.referenceId ? left : right;
}

function proposalFor(unit, proposals) {
  return proposals.get(unit.referenceId)
    ?? Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
}

function pairSeparation(left, right, leftProposal = null, rightProposal = null) {
  return Math.max(
    Math.abs(
      right.x + (rightProposal?.dx ?? 0)
        - left.x - (leftProposal?.dx ?? 0),
    ),
    Math.abs(
      right.y + (rightProposal?.dy ?? 0)
        - left.y - (leftProposal?.dy ?? 0),
    ),
  );
}

function pairFullExtent(left, right) {
  return cleanNumber(collisionRadius(left) + collisionRadius(right));
}

function movingFloor(left, right) {
  return cleanNumber(
    collisionRadius(left) * minimumMultiplier(left)
      + collisionRadius(right) * minimumMultiplier(right),
  );
}

function collisionRadius(unit) {
  const radius = Math.max(
    unit?.mechanics?.collision_size_tiles?.x ?? NaN,
    unit?.mechanics?.collision_size_tiles?.y ?? NaN,
  );
  if (!Number.isFinite(radius) || radius < 0) {
    throw new RangeError("collision radius must be finite and nonnegative");
  }
  return radius;
}

function minimumMultiplier(unit) {
  const value = unit?.mechanics?.min_collision_size_multiplier;
  if (!Number.isFinite(value) || value <= 0 || value > 1) {
    throw new RangeError("minimum collision multiplier must be within (0, 1]");
  }
  return value;
}

function attackRange(unit) {
  const range = unit?.mechanics?.attack_range_tiles ?? 0;
  if (!Number.isFinite(range) || range < 0) {
    throw new RangeError("attack range must be finite and nonnegative");
  }
  return range;
}

function isMelee(unit) {
  return unit?.mechanics?.ranged === undefined || unit.mechanics.ranged === null;
}

function isMoving(proposal) {
  return stepLength(proposal) > EPSILON;
}

function stepLength(proposal) {
  return proposal ? Math.hypot(proposal.dx, proposal.dy) : 0;
}

function sweptEntryFraction(left, right, leftProposal, rightProposal, extent) {
  const x = axisContactInterval(
    right.x - left.x,
    rightProposal.dx - leftProposal.dx,
    extent,
  );
  const y = axisContactInterval(
    right.y - left.y,
    rightProposal.dy - leftProposal.dy,
    extent,
  );
  if (!x || !y) return null;
  const enter = Math.max(0, x.enter, y.enter);
  const exit = Math.min(1, x.exit, y.exit);
  return enter <= exit + EPSILON ? Math.max(0, Math.min(1, enter)) : null;
}

function axisContactInterval(start, velocity, extent) {
  if (Math.abs(velocity) <= EPSILON) {
    return Math.abs(start) <= extent + EPSILON
      ? { enter: Number.NEGATIVE_INFINITY, exit: Number.POSITIVE_INFINITY }
      : null;
  }
  const first = (-extent - start) / velocity;
  const second = (extent - start) / velocity;
  return { enter: Math.min(first, second), exit: Math.max(first, second) };
}

function pairKey(leftId, rightId) {
  return leftId < rightId ? `${leftId}:${rightId}` : `${rightId}:${leftId}`;
}

function parsePairKey(key) {
  const parts = String(key).split(":").map(Number);
  if (parts.length !== 2 || parts.some((value) => !Number.isSafeInteger(value))) {
    throw new Error(`invalid contact reservation pair key: ${key}`);
  }
  return parts;
}

function sortedEntries(map) {
  return [...map.entries()].sort(([left], [right]) => left.localeCompare(right));
}

function diagnostic(type, pair, fields = {}) {
  return Object.freeze({ type, pairKey: pair, ...fields });
}

function requireReferenceId(value, name = "unit reference ID") {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}

function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}

function cleanNumber(value) {
  return Object.is(value, -0) ? 0 : Math.round(value * 1e12) / 1e12;
}
