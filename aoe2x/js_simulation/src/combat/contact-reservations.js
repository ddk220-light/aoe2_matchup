import { isWithinReach } from "./targeting.js";
import { areAllies, areOpponents, isHostile } from "./diplomacy.js";
import { formationTransitActive } from "./pair-interactions.js";


const EPSILON = 1e-12;
const MAX_DEEP_CONTACT_DEGREE = 2;
// A contact surface admits two deep melee claimants at once. The engagement
// layer uses the same capacity so units that are still inside the attack
// envelope cannot bypass the physical reservation surface merely because
// they have not yet made body contact.
export const MAX_INCOMING_ENGAGEMENTS = 2;

export function createContactReservationState({ alliedTransitPathObstructs = false } = {}) {
  if (typeof alliedTransitPathObstructs !== "boolean") {
    throw new TypeError("allied transit path obstruction must be boolean");
  }
  return Object.freeze({
    reservations: new Map(),
    inheritedExtents: new Map(),
    formationPairs: new Map(),
    alliedTransitPathObstructs,
  });
}

export function updateContactReservations({
  state,
  units,
  proposals,
  tick,
  externalReservations = new Map(),
  inheritedOverlapReferenceIds = new Set(),
}) {
  requireInputs(state, units, proposals, tick);
  if (!(externalReservations instanceof Map)) {
    throw new TypeError("external contact reservations must be a Map");
  }
  if (!(inheritedOverlapReferenceIds instanceof Set)) {
    throw new TypeError("inherited overlap references must be a Set");
  }
  const live = units
    .filter((unit) => unit?.alive !== false)
    .slice()
    .sort((left, right) => left.referenceId - right.referenceId);
  const byReference = unitMap(live);
  const proposalByReference = proposalMap(proposals, byReference);
  const contactReservations = new Map(externalReservations);
  const reservations = new Map();
  const inheritedExtents = new Map();
  const seededInheritedExtents = new Map(state.inheritedExtents);
  for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
      const left = live[leftIndex];
      const right = live[rightIndex];
      if (!inheritedOverlapReferenceIds.has(left.referenceId)
          && !inheritedOverlapReferenceIds.has(right.referenceId)) continue;
      const current = pairSeparation(left, right);
      if (current >= pairFullExtent(left, right) - EPSILON) continue;
      const key = pairKey(left.referenceId, right.referenceId);
      seededInheritedExtents.set(
        key,
        cleanNumber(Math.max(seededInheritedExtents.get(key) ?? 0, current)),
      );
    }
  }
  const contactSlots = createContactSlots();
  const diagnostics = [];

  // Shared formation orders temporarily own zero-obstruction geometry. Keep
  // the pair's existence (not only its depth) so that when either unit peels
  // off the order, every current overlap receives an exact, monotonically
  // releasing surface. Without this handoff a dense formation can become an
  // invalid hard/hard starting overlap on the acquisition tick.
  for (const [key] of sortedEntries(state.formationPairs ?? new Map())) {
    if (externalReservations.has(key)) continue;
    const [leftId, rightId] = parsePairKey(key);
    const left = byReference.get(leftId);
    const right = byReference.get(rightId);
    if (!left || !right || sharedFormationOrder(left, right)) continue;
    const current = pairSeparation(left, right);
    if (current >= pairFullExtent(left, right) - EPSILON) continue;
    const extent = cleanNumber(current);
    inheritedExtents.set(key, extent);
    contactReservations.set(key, releasingReservation({
      left,
      right,
      collisionExtent: extent,
      tick,
    }));
    diagnostics.push(diagnostic("release-published", key, {
      collisionExtent: extent,
      reason: "formation-order-ended",
    }));
  }

  publishInheritedReleases({
    inherited: seededInheritedExtents,
    byReference,
    inheritedExtents,
    contactReservations,
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
    if (externalReservations.has(key)) {
      diagnostics.push(diagnostic("reservation-released", key, {
        reason: "external-contact-authority",
      }));
      continue;
    }
    if (sharedFormationOrder(left, right)) {
      diagnostics.push(diagnostic("reservation-released", key, {
        reason: "shared-formation-order",
      }));
      continue;
    }
    if (reservationRemainsActive(prior, left, right, byReference, proposalByReference)) {
      if (!contactSlotsAvailable(prior, left, right, contactSlots)) {
        diagnostics.push(diagnostic("reservation-released", key, {
          reason: "deep-slot-conflict",
        }));
        inheritReleasedPair({
          key,
          left,
          right,
          inheritedExtents,
          contactReservations,
          diagnostics,
          tick,
        });
        continue;
      }
      reservations.set(key, prior);
      contactReservations.set(key, prior);
      occupyContactSlots(prior, left, right, contactSlots);
      diagnostics.push(diagnostic("reservation-persisted", key, { kind: prior.kind }));
      continue;
    }
    inheritReleasedPair({
      key,
      left,
      right,
      inheritedExtents,
      contactReservations,
      diagnostics,
      tick,
    });
  }

  const candidates = generateCandidates(
    live,
    byReference,
    proposalByReference,
    tick,
    state.alliedTransitPathObstructs === true,
  );
  const admissibleShallowPairs = new Set(candidates
    .filter(({ reservation }) => reservation.kind !== "releasing")
    .map(({ key }) => key));
  for (const candidate of candidates) {
    if (contactReservations.has(candidate.key)) continue;
    if (candidate.reservation.kind === "releasing") {
      inheritedExtents.set(candidate.key, candidate.reservation.collisionExtent);
      contactReservations.set(candidate.key, candidate.reservation);
      diagnostics.push(diagnostic("release-published", candidate.key, {
        collisionExtent: candidate.reservation.collisionExtent,
      }));
      continue;
    }
    const left = byReference.get(candidate.reservation.leftId);
    const right = byReference.get(candidate.reservation.rightId);
    if (!contactSlotsAvailable(candidate.reservation, left, right, contactSlots)) continue;
    reservations.set(candidate.key, candidate.reservation);
    contactReservations.set(candidate.key, candidate.reservation);
    occupyContactSlots(candidate.reservation, left, right, contactSlots);
    diagnostics.push(diagnostic("reservation-acquired", candidate.key, {
      kind: candidate.reservation.kind,
      entryFraction: candidate.entryFraction,
      projectedNormalizedDepth: candidate.projectedNormalizedDepth,
      progress: candidate.progress,
    }));
  }

  publishShallowContacts({
    units: live,
    proposals: proposalByReference,
    contactReservations,
    inheritedExtents,
    admissiblePairs: admissibleShallowPairs,
    diagnostics,
    tick,
  });

  const formationPairs = new Map();
  for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
      const left = live[leftIndex];
      const right = live[rightIndex];
      const key = pairKey(left.referenceId, right.referenceId);
      if (sharedFormationOrder(left, right) && !externalReservations.has(key)) {
        formationPairs.set(key,
          cleanNumber(pairSeparation(left, right)));
      }
    }
  }
  const nextState = Object.freeze({
    reservations,
    inheritedExtents,
    formationPairs,
    alliedTransitPathObstructs: state.alliedTransitPathObstructs === true,
  });
  return Object.freeze({
    state: nextState,
    contactReservations,
    diagnostics: Object.freeze(diagnostics),
  });
}

function createContactSlots() {
  return {
    allied: new Set(),
    enemyTransit: new Set(),
    engagementOutgoing: new Set(),
    engagementIncoming: new Map(),
    deepDegree: new Map(),
  };
}

function contactSlotsAvailable(reservation, left, right, slots) {
  if (!left || !right) throw new Error("contact slot pair must reference live units");
  if ((slots.deepDegree.get(left.referenceId) ?? 0) >= MAX_DEEP_CONTACT_DEGREE
      || (slots.deepDegree.get(right.referenceId) ?? 0) >= MAX_DEEP_CONTACT_DEGREE) {
    return false;
  }
  if (areAllies(left, right)) {
    return !slots.allied.has(left.referenceId) && !slots.allied.has(right.referenceId);
  }
  if (reservation.kind === "engagement-contact") {
    return engagementDirections(reservation, left, right).every(([initiator, target]) => (
      !slots.engagementOutgoing.has(initiator.referenceId)
        && (slots.engagementIncoming.get(target.referenceId) ?? 0)
          < MAX_INCOMING_ENGAGEMENTS
    ));
  }
  return !slots.enemyTransit.has(left.referenceId)
    && !slots.enemyTransit.has(right.referenceId);
}

function occupyContactSlots(reservation, left, right, slots) {
  slots.deepDegree.set(
    left.referenceId,
    (slots.deepDegree.get(left.referenceId) ?? 0) + 1,
  );
  slots.deepDegree.set(
    right.referenceId,
    (slots.deepDegree.get(right.referenceId) ?? 0) + 1,
  );
  if (areAllies(left, right)) {
    slots.allied.add(left.referenceId);
    slots.allied.add(right.referenceId);
    return;
  }
  if (reservation.kind === "engagement-contact") {
    for (const [initiator, target] of engagementDirections(reservation, left, right)) {
      slots.engagementOutgoing.add(initiator.referenceId);
      slots.engagementIncoming.set(
        target.referenceId,
        (slots.engagementIncoming.get(target.referenceId) ?? 0) + 1,
      );
    }
    return;
  }
  slots.enemyTransit.add(left.referenceId);
  slots.enemyTransit.add(right.referenceId);
}

function engagementDirections(reservation, left, right) {
  const byReference = new Map([
    [left.referenceId, left],
    [right.referenceId, right],
  ]);
  const initiator = byReference.get(reservation.initiatorId);
  const target = byReference.get(reservation.targetId);
  if (!initiator || !target) {
    throw new Error("engagement contact must identify its pair direction");
  }
  const directions = [[initiator, target]];
  if (directTarget(target, initiator)) directions.push([target, initiator]);
  return directions;
}

function publishShallowContacts({
  units,
  proposals,
  contactReservations,
  inheritedExtents,
  admissiblePairs,
  diagnostics,
  tick,
}) {
  for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
    const left = units[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
      const right = units[rightIndex];
      // A unit may make one deep allied transit reservation. Additional allied
      // lanes remain ordinary hard bodies so a moving formation does not
      // collapse into a multi-unit knot. Shallow secondary contact is for
      // several enemies sharing the same engagement boundary.
      if (!areOpponents(left, right)) continue;
      const key = pairKey(left.referenceId, right.referenceId);
      if (contactReservations.has(key) || !admissiblePairs.has(key)) continue;
      const leftProposal = proposalFor(left, proposals);
      const rightProposal = proposalFor(right, proposals);
      const current = pairSeparation(left, right);
      const projected = pairSeparation(left, right, leftProposal, rightProposal);
      const relativeClosure = current - projected;
      if (relativeClosure <= EPSILON) continue;
      const fullExtent = pairFullExtent(left, right);
      if (sweptEntryFraction(
        left,
        right,
        leftProposal,
        rightProposal,
        fullExtent,
      ) === null) continue;
      const oneTickSurface = Math.max(
        movingFloor(left, right),
        fullExtent - relativeClosure,
      );
      const collisionExtent = cleanNumber(Math.min(current, oneTickSurface));
      const [canonicalLeft, canonicalRight] = left.referenceId < right.referenceId
        ? [left, right]
        : [right, left];
      contactReservations.set(key, Object.freeze({
        leftId: canonicalLeft.referenceId,
        rightId: canonicalRight.referenceId,
        kind: "shallow-contact",
        collisionExtent,
        attackSurfaceExtent: fullExtent,
        pathObstructs: false,
        mayDeepen: false,
        initiatorId: chooseInitiator(left, right, leftProposal, rightProposal).referenceId,
        targetId: null,
        acquiredTick: tick,
      }));
      inheritedExtents.set(key, collisionExtent);
      diagnostics.push(diagnostic("shallow-contact-published", key, {
        collisionExtent,
        relativeClosure: cleanNumber(relativeClosure),
      }));
    }
  }
}

function requireInputs(state, units, proposals, tick) {
  if (!state || !(state.reservations instanceof Map)
      || !(state.inheritedExtents instanceof Map)
      || (state.formationPairs !== undefined && !(state.formationPairs instanceof Map))
      || (state.alliedTransitPathObstructs !== undefined
        && typeof state.alliedTransitPathObstructs !== "boolean")) {
    throw new TypeError(
      "contact reservation state requires reservation, inherited, and formation maps",
    );
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
  diagnostics,
  tick,
}) {
  for (const [key, priorExtent] of sortedEntries(inherited)) {
    if (contactReservations.has(key)) continue;
    if (!Number.isFinite(priorExtent) || priorExtent < 0) {
      throw new RangeError("inherited contact extent must be finite and nonnegative");
    }
    const [leftId, rightId] = parsePairKey(key);
    const left = byReference.get(leftId);
    const right = byReference.get(rightId);
    if (!left || !right) continue;
    if (sharedFormationOrder(left, right)) {
      diagnostics.push(diagnostic("release-cleared", key, {
        reason: "shared-formation-order",
      }));
      continue;
    }
    const fullExtent = pairFullExtent(left, right);
    const currentExtent = pairSeparation(left, right);
    if (currentExtent >= fullExtent - EPSILON) continue;
    const publishedExtent = cleanNumber(Math.max(priorExtent, currentExtent));
    inheritedExtents.set(key, publishedExtent);
    contactReservations.set(key, releasingReservation({
      left,
      right,
      collisionExtent: publishedExtent,
      tick,
    }));
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
  diagnostics,
  tick,
}) {
  const currentExtent = pairSeparation(left, right);
  if (currentExtent >= pairFullExtent(left, right) - EPSILON) {
    diagnostics.push(diagnostic("reservation-released", key, { reason: "full-separation" }));
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
  diagnostics.push(diagnostic("reservation-released", key, {
    reason: "inherited-current-overlap",
    currentExtent: publishedExtent,
  }));
}

function generateCandidates(units, byReference, proposals, tick,
  alliedTransitPathObstructs) {
  const candidates = [];
  for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
    const left = units[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
      const right = units[rightIndex];
      if (areAllies(left, right)) {
        // Formation cohorts own zero-obstruction pair geometry in the shared
        // interaction resolver. Do not leave a deeper reservation behind:
        // when either order ends, an exact current-shape release is created.
        if (sharedFormationOrder(left, right)) continue;
        const candidate = isRanged(left) && isRanged(right)
          ? rangedIngressCandidate(left, right, byReference, proposals, tick)
          : alliedCandidate(
            left,
            right,
            proposals,
            tick,
            alliedTransitPathObstructs,
          );
        if (candidate) candidates.push(candidate);
        else if (pairSeparation(left, right) < pairFullExtent(left, right) - EPSILON) {
          candidates.push(untrackedReleaseCandidate(left, right, tick));
        }
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
      if (!direct && !leftCorridor && !rightCorridor
          && pairSeparation(left, right) < pairFullExtent(left, right) - EPSILON) {
        candidates.push(untrackedReleaseCandidate(left, right, tick));
      }
    }
  }
  return candidates.sort(compareCandidates);
}

function rangedIngressCandidate(left, right, byReference, proposals, tick) {
  const directions = [[left, right], [right, left]]
    .filter(([mover, front]) => rangedIngressQualifies(
      mover,
      front,
      byReference,
      proposals,
    ));
  if (directions.length === 0) return null;
  directions.sort(([leftMover], [rightMover]) => (
    leftMover.referenceId - rightMover.referenceId
  ));
  const [mover] = directions[0];
  const leftProposal = proposalFor(left, proposals);
  const rightProposal = proposalFor(right, proposals);
  const current = pairSeparation(left, right);
  const projected = pairSeparation(left, right, leftProposal, rightProposal);
  const fullExtent = pairFullExtent(left, right);
  const entryFraction = current < fullExtent - EPSILON
    ? 0
    : sweptEntryFraction(left, right, leftProposal, rightProposal, fullExtent);
  if (entryFraction === null) return null;
  return makeCandidate({
    left,
    right,
    initiator: mover,
    target: null,
    kind: "ranged-ingress",
    pathObstructs: false,
    entryFraction,
    projected,
    progress: stepLength(proposalFor(mover, proposals)),
    tick,
  });
}

function rangedIngressQualifies(mover, front, byReference, proposals) {
  const moverProposal = proposalFor(mover, proposals);
  if (!isMoving(moverProposal)) return false;
  const target = directPursuitTarget(mover, byReference);
  if (!target || isWithinReach(mover, target)) return false;
  const currentTargetDistance = euclideanDistance(mover, target);
  if (euclideanDistance(mover, target, moverProposal) >= currentTargetDistance - EPSILON) {
    return false;
  }
  if (euclideanDistance(front, target) >= currentTargetDistance - EPSILON) return false;
  const frontProposal = proposalFor(front, proposals);
  const current = pairSeparation(mover, front);
  const projected = pairSeparation(mover, front, moverProposal, frontProposal);
  return projected < pairFullExtent(mover, front) - EPSILON
    && projected < current - EPSILON;
}

function euclideanDistance(unit, target, proposal = null) {
  return Math.hypot(
    target.x - unit.x - (proposal?.dx ?? 0),
    target.y - unit.y - (proposal?.dy ?? 0),
  );
}

function untrackedReleaseCandidate(left, right, tick) {
  const currentExtent = cleanNumber(pairSeparation(left, right));
  return Object.freeze({
    key: pairKey(left.referenceId, right.referenceId),
    entryFraction: -1,
    projectedNormalizedDepth: cleanNumber(
      Math.max(0, pairFullExtent(left, right) - currentExtent)
        / pairFullExtent(left, right),
    ),
    progress: 0,
    reservation: releasingReservation({
      left,
      right,
      collisionExtent: currentExtent,
      tick,
    }),
  });
}

function alliedCandidate(left, right, proposals, tick, pathObstructs) {
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
    pathObstructs,
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
  const currentExtent = pairSeparation(left, right);
  const configuredFloor = movingFloor(left, right);
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
    if (!areAllies(left, right)) return false;
  } else if (prior.kind === "ranged-ingress") {
    if (!areAllies(left, right) || !isRanged(left) || !isRanged(right)) return false;
    return pairSeparation(left, right) < pairFullExtent(left, right) - EPSILON
      || rangedIngressQualifies(left, right, byReference, proposals)
      || rangedIngressQualifies(right, left, byReference, proposals);
  } else if (!areOpponents(left, right)) {
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
    if (target && isHostile(unit, target)) return target;
  }
  return null;
}

function insidePursuitCorridor(chaser, blocker, target) {
  if (!areOpponents(chaser, blocker)) return false;
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

function isRanged(unit) {
  return !isMelee(unit);
}

function isMoving(proposal) {
  return stepLength(proposal) > EPSILON;
}

function sharedFormationOrder(left, right) {
  return areAllies(left, right)
    && formationTransitActive(left)
    && formationTransitActive(right);
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
