import { dynamicPairKey } from "./pair-interactions.js";
import {
  collisionRadius,
  MELEE_CONTACT_TOLERANCE_TILES,
} from "./targeting.js";


const EPSILON = 1e-12;


function requireReferenceId(value, name = "reference ID") {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireState(state) {
  if (!state || typeof state !== "object" || Array.isArray(state)) {
    throw new TypeError("enemy transit state must be an object");
  }
  if (!(state.reservations instanceof Map)) {
    throw new TypeError("enemy transit reservations must be a Map");
  }
  if (!(state.inheritedContactExtents instanceof Map)) {
    throw new TypeError("inherited enemy contact extents must be a Map");
  }
  if (state.inheritedContactSources !== undefined
      && !(state.inheritedContactSources instanceof Map)) {
    throw new TypeError("inherited enemy contact sources must be a Map");
  }
  return state;
}


function requireInputs(units, proposals, tick) {
  if (!Array.isArray(units)) throw new TypeError("enemy transit units must be an array");
  if (!Array.isArray(proposals)) {
    throw new TypeError("enemy transit proposals must be an array");
  }
  if (!Number.isSafeInteger(tick) || tick < 0) {
    throw new TypeError("enemy transit tick must be a nonnegative safe integer");
  }
}


function proposalMap(proposals, liveByReference) {
  const result = new Map();
  for (const proposal of proposals) {
    const referenceId = requireReferenceId(proposal?.referenceId, "proposal reference ID");
    if (!liveByReference.has(referenceId)) continue;
    if (result.has(referenceId)) {
      throw new Error(`duplicate enemy transit proposal for reference ${referenceId}`);
    }
    result.set(referenceId, Object.freeze({
      referenceId,
      dx: requireFinite(proposal.dx, "proposal dx"),
      dy: requireFinite(proposal.dy, "proposal dy"),
    }));
  }
  return result;
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


function pairExtent(left, right) {
  return collisionRadius(left) + collisionRadius(right);
}


function isMeleeMode(unit) {
  return unit?.mechanics?.ranged === undefined || unit.mechanics.ranged === null;
}


function distanceSquared(left, right, proposal = null) {
  const dx = right.x - left.x - (proposal?.dx ?? 0);
  const dy = right.y - left.y - (proposal?.dy ?? 0);
  return dx * dx + dy * dy;
}


function activePursuer(unit, byReference, proposals) {
  const intent = pursuitIntent(unit, byReference, proposals);
  if (!intent) return null;
  const { target, proposal } = intent;
  if (!proposal || Math.hypot(proposal.dx, proposal.dy) <= EPSILON) return null;
  if (distanceSquared(unit, target, proposal) >= distanceSquared(unit, target) - EPSILON) {
    return null;
  }
  return intent;
}


function pursuitIntent(unit, byReference, proposals) {
  if (!unit || unit.alive === false || !isMeleeMode(unit)) return null;
  const targetId = unit.pursuitTargetId;
  if (!Number.isSafeInteger(targetId)) return null;
  const target = byReference.get(targetId);
  if (!target || target.owner === unit.owner) return null;
  const proposal = proposals.get(unit.referenceId);
  return Object.freeze({ unit, target, proposal });
}


function pairClosing(left, right, proposals) {
  const current = pairSeparation(left, right);
  const projected = pairSeparation(
    left,
    right,
    proposals.get(left.referenceId),
    proposals.get(right.referenceId),
  );
  return projected < current - EPSILON;
}


function corridorCandidate(chaser, blocker, target) {
  if (!blocker || blocker.owner === chaser.owner
      || blocker.referenceId === target.referenceId) return null;
  const tx = target.x - chaser.x;
  const ty = target.y - chaser.y;
  const targetDistance = Math.hypot(tx, ty);
  if (targetDistance <= EPSILON) return null;
  const ux = tx / targetDistance;
  const uy = ty / targetDistance;
  const bx = blocker.x - chaser.x;
  const by = blocker.y - chaser.y;
  const forward = bx * ux + by * uy;
  if (forward <= EPSILON || forward >= targetDistance - EPSILON) return null;
  const lateral = Math.abs(bx * uy - by * ux);
  if (lateral > pairExtent(chaser, blocker) + EPSILON) return null;
  return Object.freeze({ forward, lateral });
}


function acquisitionDirection(chaser, target) {
  const dx = target.x - chaser.x;
  const dy = target.y - chaser.y;
  if (Math.abs(dx) >= Math.abs(dy)) {
    return { axis: "x", sign: dx < 0 ? -1 : 1 };
  }
  return { axis: "y", sign: dy < 0 ? -1 : 1 };
}


function reservation(chaser, blocker, target, tick, {
  mode = "melee-pursuit",
  direction = acquisitionDirection(chaser, target),
} = {}) {
  return Object.freeze({
    chaserId: chaser.referenceId,
    blockerId: blocker.referenceId,
    pursuitTargetId: target.referenceId,
    mode,
    acquisitionAxis: direction.axis,
    acquisitionSign: direction.sign,
    acquiredTick: tick,
  });
}


function inheritedEntry(pairKey, left, right) {
  return [pairKey, pairSeparation(left, right)];
}


function releaseReason(prior, byReference, proposals) {
  const chaser = byReference.get(prior.chaserId);
  const blocker = byReference.get(prior.blockerId);
  if (!chaser) return { reason: "chaser-missing", chaser, blocker, target: null };
  if (!blocker) return { reason: "blocker-missing", chaser, blocker, target: null };
  if (prior.mode === "formation-flow") {
    const axis = prior.acquisitionAxis;
    const signedOffset = (blocker[axis] - chaser[axis]) * prior.acquisitionSign;
    const chaserProposal = proposals.get(chaser.referenceId);
    const blockerProposal = proposals.get(blocker.referenceId);
    const currentSeparation = pairSeparation(chaser, blocker);
    const projectedSeparation = pairSeparation(
      chaser,
      blocker,
      chaserProposal,
      blockerProposal,
    );
    if (signedOffset <= EPSILON && projectedSeparation > currentSeparation + EPSILON) {
      return { reason: "crossed-and-separating", chaser, blocker, target: blocker };
    }
    const activeFlow = chaser.moveOrder
      && chaserProposal
      && Math.hypot(chaserProposal.dx, chaserProposal.dy) > EPSILON;
    if (!activeFlow) {
      return { reason: "flow-ended", chaser, blocker, target: blocker };
    }
    if (currentSeparation > 2 * pairExtent(chaser, blocker) + EPSILON) {
      return { reason: "flow-separated", chaser, blocker, target: blocker };
    }
    return {
      reason: null,
      chaser,
      blocker,
      target: blocker,
      reservation: prior,
      persistReason: "formation-flow-active",
    };
  }
  // Target acquisition and the attack animation update on different ticks.
  // Once combat has captured this blocker, keep the physical pair contact
  // even if pursuit selection has already moved on to a future target.
  const blockerCaptured = chaser.pursuitTargetId === blocker.referenceId
    || chaser.engagedTargetId === blocker.referenceId
    || chaser.attackTargetId === blocker.referenceId;
  const targetId = blockerCaptured ? blocker.referenceId : prior.pursuitTargetId;
  const target = byReference.get(targetId);
  if (!target) return { reason: "target-missing", chaser, blocker, target };
  if (!blockerCaptured && chaser.pursuitTargetId !== prior.pursuitTargetId) {
    return { reason: "target-changed", chaser, blocker, target };
  }
  const nextReservation = blockerCaptured && prior.pursuitTargetId !== blocker.referenceId
    ? Object.freeze({ ...prior, pursuitTargetId: blocker.referenceId })
    : prior;
  const axis = prior.acquisitionAxis;
  const signedOffset = (blocker[axis] - chaser[axis]) * prior.acquisitionSign;
  const chaserProposal = proposals.get(chaser.referenceId);
  const blockerProposal = proposals.get(blocker.referenceId);
  const currentSeparation = pairSeparation(chaser, blocker);
  const projectedSeparation = pairSeparation(
    chaser,
    blocker,
    chaserProposal,
    blockerProposal,
  );
  if (signedOffset <= EPSILON && projectedSeparation > currentSeparation + EPSILON) {
    return { reason: "crossed-and-separating", chaser, blocker, target };
  }
  const pursuit = activePursuer(chaser, byReference, proposals);
  if (!pursuit) {
    const physicalExtent = pairExtent(chaser, blocker);
    const remainsNearContact = currentSeparation <= 2 * physicalExtent + EPSILON;
    if (remainsNearContact) {
      return {
        reason: null,
        chaser,
        blocker,
        target,
        reservation: nextReservation,
        persistReason: blockerCaptured
          ? "blocker-captured-in-contact"
          : "near-contact-stall",
      };
    }
    return { reason: "pursuit-ended", chaser, blocker, target };
  }
  if (!blockerCaptured
      && currentSeparation >= pairExtent(chaser, blocker) - EPSILON
      && !corridorCandidate(chaser, blocker, target)) {
    return { reason: "corridor-exit", chaser, blocker, target };
  }
  return {
    reason: null,
    chaser,
    blocker,
    target,
    reservation: nextReservation,
    persistReason: blockerCaptured ? "blocker-captured" : "reservation-valid",
  };
}


function diagnostic(type, pairKey, fields = {}) {
  return Object.freeze({ type, pairKey, ...fields });
}


function consumesTransitSlot(reservation) {
  return reservation.mode !== "engagement-contact";
}


export function createEnemyTransitState() {
  return Object.freeze({
    reservations: new Map(),
    inheritedContactExtents: new Map(),
    inheritedContactSources: new Map(),
  });
}


export function separateInheritedContactProposals({
  units,
  proposals,
  inheritedContactExtents,
  inheritedContactSources = new Map(),
}) {
  if (!Array.isArray(units)) throw new TypeError("separation units must be an array");
  if (!Array.isArray(proposals)) throw new TypeError("separation proposals must be an array");
  if (!(inheritedContactExtents instanceof Map)) {
    throw new TypeError("inherited contact extents must be a Map");
  }
  if (!(inheritedContactSources instanceof Map)) {
    throw new TypeError("inherited contact sources must be a Map");
  }
  const byReference = new Map(units
    .filter((unit) => unit?.alive !== false)
    .map((unit) => [requireReferenceId(unit.referenceId), unit]));
  const nextByReference = proposalMap(proposals, byReference);
  const assigned = new Set();
  for (const [key] of [...inheritedContactExtents]
    .sort(([left], [right]) => left.localeCompare(right))) {
    const [leftId, rightId] = key.split(":").map(Number);
    if (assigned.has(leftId) || assigned.has(rightId)) continue;
    const left = byReference.get(leftId);
    const right = byReference.get(rightId);
    if (!left || !right || left.owner === right.owner) continue;
    const leftProposal = nextByReference.get(leftId);
    const rightProposal = nextByReference.get(rightId);
    const leftStep = Math.hypot(leftProposal?.dx ?? 0, leftProposal?.dy ?? 0);
    const rightStep = Math.hypot(rightProposal?.dx ?? 0, rightProposal?.dy ?? 0);
    if (leftStep <= EPSILON && rightStep <= EPSILON) continue;
    const offsetX = right.x - left.x;
    const offsetY = right.y - left.y;
    const axis = Math.abs(offsetX) >= Math.abs(offsetY) ? "x" : "y";
    const crossAxis = axis === "x" ? "y" : "x";
    const sign = (axis === "x" ? offsetX : offsetY) < 0 ? -1 : 1;
    const current = Math.abs(axis === "x" ? offsetX : offsetY);
    const projected = (
      right[axis] + (rightProposal?.[axis === "x" ? "dx" : "dy"] ?? 0)
      - left[axis] - (leftProposal?.[axis === "x" ? "dx" : "dy"] ?? 0)
    ) * sign;
    if (projected > current + EPSILON) continue;
    const outward = (proposal, step, direction) => {
      if (!proposal || step <= EPSILON) return proposal;
      return Object.freeze({
        ...proposal,
        [axis === "x" ? "dx" : "dy"]: direction * step,
        [crossAxis === "x" ? "dx" : "dy"]: 0,
      });
    };
    nextByReference.set(leftId, outward(leftProposal, leftStep, -sign));
    nextByReference.set(rightId, outward(rightProposal, rightStep, sign));
    assigned.add(leftId);
    assigned.add(rightId);
  }
  return Object.freeze(proposals.map((proposal) => (
    nextByReference.get(proposal.referenceId) ?? proposal
  )));
}


export function updateEnemyTransit({ state, units, proposals, tick }) {
  requireInputs(units, proposals, tick);
  const previous = requireState(state);
  const live = units
    .filter((unit) => unit?.alive !== false)
    .toSorted((left, right) => left.referenceId - right.referenceId);
  const byReference = new Map();
  for (const unit of live) {
    const referenceId = requireReferenceId(unit?.referenceId);
    if (byReference.has(referenceId)) throw new Error(`duplicate unit reference ${referenceId}`);
    requireFinite(unit.x, "unit x");
    requireFinite(unit.y, "unit y");
    byReference.set(referenceId, unit);
  }
  const proposalsByReference = proposalMap(proposals, byReference);
  const diagnostics = [];

  const inherited = new Map();
  const inheritedSources = new Map();
  for (const [key, priorExtent] of [...previous.inheritedContactExtents]
    .sort(([left], [right]) => left.localeCompare(right))) {
    if (!Number.isFinite(priorExtent) || priorExtent < 0) {
      throw new RangeError("inherited enemy contact extent must be nonnegative and finite");
    }
    const [leftId, rightId] = key.split(":").map(Number);
    const left = byReference.get(leftId);
    const right = byReference.get(rightId);
    if (!left || !right || left.owner === right.owner) continue;
    const fullExtent = pairExtent(left, right);
    const current = pairSeparation(left, right);
    if (current >= fullExtent - EPSILON) continue;
    inherited.set(key, current);
    inheritedSources.set(
      key,
      previous.inheritedContactSources?.get(key) ?? "recovered",
    );
    if (current < priorExtent - EPSILON) {
      diagnostics.push(diagnostic("enemy-transit-recovered", key, {
        reason: "inherited-contact-deepened",
        previousExtent: priorExtent,
        currentExtent: current,
      }));
    }
  }

  for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
    const left = live[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
      const right = live[rightIndex];
      if (left.owner === right.owner) continue;
      const key = dynamicPairKey(left.referenceId, right.referenceId);
      if (inherited.has(key)) continue;
      const current = pairSeparation(left, right);
      // The collision solver uses the engine's axis-aligned footprint extent,
      // so recovery must use the same geometry. A diagonal pair can be outside
      // a Euclidean circle while still overlapping those published footprints.
      if (current >= pairExtent(left, right) - EPSILON) continue;
      inherited.set(key, current);
      inheritedSources.set(key, "recovered");
      diagnostics.push(diagnostic("enemy-transit-recovered", key, {
        reason: "published-square-overlap",
        currentExtent: current,
      }));
    }
  }

  const reservedIds = new Set();
  for (const key of inherited.keys()) {
    if (inheritedSources.get(key) === "engagement-contact") continue;
    const [leftId, rightId] = key.split(":").map(Number);
    reservedIds.add(leftId);
    reservedIds.add(rightId);
  }
  const reservations = new Map();
  for (const [key, prior] of [...previous.reservations]
    .sort(([left], [right]) => left.localeCompare(right))) {
    const released = releaseReason(prior, byReference, proposalsByReference);
    if (released.reason === null) {
      reservations.set(key, released.reservation);
      if (consumesTransitSlot(released.reservation)) {
        reservedIds.add(prior.chaserId);
        reservedIds.add(prior.blockerId);
      }
      inherited.delete(key);
      inheritedSources.delete(key);
      diagnostics.push(diagnostic("enemy-transit-persisted", key, {
        chaserId: prior.chaserId,
        blockerId: prior.blockerId,
        pursuitTargetId: prior.pursuitTargetId,
        reason: released.persistReason,
      }));
      continue;
    }
    if (released.chaser && released.blocker) {
      const fullExtent = pairExtent(released.chaser, released.blocker);
      const current = pairSeparation(released.chaser, released.blocker);
      if (current < fullExtent - EPSILON) {
        inherited.set(key, inheritedEntry(
          key,
          released.chaser,
          released.blocker,
        )[1]);
        inheritedSources.set(key, prior.mode);
      }
    }
    diagnostics.push(diagnostic("enemy-transit-released", key, {
      chaserId: prior.chaserId,
      blockerId: prior.blockerId,
      pursuitTargetId: prior.pursuitTargetId,
      reason: released.reason,
    }));
  }

  const pursuits = live
    .map((unit) => activePursuer(unit, byReference, proposalsByReference))
    .filter(Boolean);
  const pursuitByReference = new Map(
    pursuits.map((entry) => [entry.unit.referenceId, entry]),
  );
  const candidates = [];
  const pursuitIntents = live
    .map((unit) => pursuitIntent(unit, byReference, proposalsByReference))
    .filter(Boolean);
  const enemyPursuitTargets = new Map(pursuitIntents.map((pursuit) => [
    pursuit.unit.referenceId,
    pursuit.target.referenceId,
  ]));
  for (const pursuit of pursuitIntents) {
    const chaser = pursuit.unit;
    const active = pursuitByReference.has(chaser.referenceId);
    const directTarget = pursuit.target;
    const directKey = dynamicPairKey(chaser.referenceId, directTarget.referenceId);
    const directExtent = pairExtent(chaser, directTarget);
    const directRelativeStep = Math.hypot(
      pursuit.proposal?.dx ?? 0,
      pursuit.proposal?.dy ?? 0,
    ) + Math.hypot(
      proposalsByReference.get(directTarget.referenceId)?.dx ?? 0,
      proposalsByReference.get(directTarget.referenceId)?.dy ?? 0,
    );
    const directContactWindow = directExtent + Math.max(
      directRelativeStep,
      MELEE_CONTACT_TOLERANCE_TILES,
    );
    const directSeparation = pairSeparation(chaser, directTarget);
    if (!reservations.has(directKey)
        && !inherited.has(directKey)
        && directSeparation <= directContactWindow + EPSILON
        && (active
          || pairClosing(chaser, directTarget, proposalsByReference)
          || directSeparation <= directExtent + EPSILON)) {
      candidates.push({
        key: directKey,
        chaser,
        blocker: directTarget,
        target: directTarget,
        forward: directSeparation,
        lateral: 0,
        reason: "direct-target-contact",
        contactWindow: directContactWindow,
        priority: 0,
        mode: "engagement-contact",
      });
    }
    if (reservedIds.has(chaser.referenceId)) continue;
    for (const blocker of live) {
      if (reservedIds.has(blocker.referenceId)) continue;
      const key = blocker.referenceId === chaser.referenceId
        ? null
        : dynamicPairKey(chaser.referenceId, blocker.referenceId);
      if (key === null || inherited.has(key)) continue;
      const corridor = corridorCandidate(chaser, blocker, pursuit.target);
      if (!corridor) continue;
      if (!active && !pairClosing(chaser, blocker, proposalsByReference)) continue;
      const physicalExtent = pairExtent(chaser, blocker);
      const relativeStep = Math.hypot(
        pursuit.proposal?.dx ?? 0,
        pursuit.proposal?.dy ?? 0,
      )
        + Math.hypot(
          proposalsByReference.get(blocker.referenceId)?.dx ?? 0,
          proposalsByReference.get(blocker.referenceId)?.dy ?? 0,
        );
      // Reserve only a pair that can reach its physical boundary on the next
      // relative step. Opening a whole body-width early captures unrelated
      // neighbors that the mover never touches and starves the true contact.
      const contactWindow = physicalExtent + relativeStep;
      if (pairSeparation(chaser, blocker) > contactWindow + EPSILON) continue;
      candidates.push({
        key,
        chaser,
        blocker,
        target: pursuit.target,
        forward: corridor.forward,
        lateral: corridor.lateral,
        reason: "non-target-corridor",
        contactWindow,
        priority: 1,
      });
    }
  }
  for (const mover of live) {
    if (!mover.moveOrder || reservedIds.has(mover.referenceId)) continue;
    const moverProposal = proposalsByReference.get(mover.referenceId);
    if (!moverProposal || Math.hypot(moverProposal.dx, moverProposal.dy) <= EPSILON) continue;
    for (const blocker of live) {
      if (blocker.owner === mover.owner || reservedIds.has(blocker.referenceId)) continue;
      if (!isMeleeMode(blocker)) continue;
      const blockerProposal = proposalsByReference.get(blocker.referenceId);
      if (blockerProposal && Math.hypot(blockerProposal.dx, blockerProposal.dy) > EPSILON) continue;
      const engaged = blocker.action === "attacking"
        || Number.isSafeInteger(blocker.engagedTargetId);
      if (!engaged) continue;
      const key = dynamicPairKey(mover.referenceId, blocker.referenceId);
      if (inherited.has(key)) continue;
      const physicalExtent = pairExtent(mover, blocker);
      const stepX = mover.moveOrder.x - mover.x;
      const stepY = mover.moveOrder.y - mover.y;
      const stepLength = Math.hypot(stepX, stepY);
      if (stepLength <= EPSILON) continue;
      const toBlockerX = blocker.x - mover.x;
      const toBlockerY = blocker.y - mover.y;
      const forward = (toBlockerX * stepX + toBlockerY * stepY) / stepLength;
      const lateral = Math.abs(toBlockerX * stepY - toBlockerY * stepX) / stepLength;
      // Formation movement needs the reservation before A* bends around the
      // enemy. Limit that look-ahead to one complete pair diameter and the
      // actual swept body corridor so off-path neighbors cannot claim slots.
      const contactWindow = 2 * physicalExtent;
      if (forward <= EPSILON || forward > contactWindow + EPSILON) continue;
      if (lateral > physicalExtent + EPSILON) continue;
      const alongX = Math.abs(stepX) >= Math.abs(stepY);
      candidates.push({
        key,
        chaser: mover,
        blocker,
        target: blocker,
        forward,
        lateral,
        reason: "moving-through-engaged-enemy",
        mode: "formation-flow",
        priority: 2,
        direction: {
          axis: alongX ? "x" : "y",
          sign: (alongX ? stepX : stepY) < 0 ? -1 : 1,
        },
        contactWindow,
      });
    }
  }
  candidates.sort((left, right) => (
    left.priority - right.priority
      || left.forward - right.forward
      || left.lateral - right.lateral
      || left.chaser.referenceId - right.chaser.referenceId
      || left.blocker.referenceId - right.blocker.referenceId
  ));
  for (const candidate of candidates) {
    const chaserId = candidate.chaser.referenceId;
    const blockerId = candidate.blocker.referenceId;
    const nextReservation = reservation(
      candidate.chaser,
      candidate.blocker,
      candidate.target,
      tick,
      { mode: candidate.mode, direction: candidate.direction },
    );
    const existing = reservations.get(candidate.key);
    if (existing) {
      if (consumesTransitSlot(existing) || !consumesTransitSlot(nextReservation)) continue;
      reservations.delete(candidate.key);
    }
    if (consumesTransitSlot(nextReservation)
        && (reservedIds.has(chaserId) || reservedIds.has(blockerId))) continue;
    reservations.set(candidate.key, nextReservation);
    if (consumesTransitSlot(nextReservation)) {
      reservedIds.add(chaserId);
      reservedIds.add(blockerId);
    }
    diagnostics.push(diagnostic("enemy-transit-acquired", candidate.key, {
      chaserId,
      blockerId,
      pursuitTargetId: candidate.target.referenceId,
      reason: candidate.reason,
      currentSeparation: pairSeparation(candidate.chaser, candidate.blocker),
      contactWindow: candidate.contactWindow,
      chaserStep: Math.hypot(
        proposalsByReference.get(chaserId)?.dx ?? 0,
        proposalsByReference.get(chaserId)?.dy ?? 0,
      ),
    }));
  }

  // Reservation arbitration can replace or reject a candidate after the
  // initial inherited-contact scan. Reconcile once more before publishing the
  // snapshot so every overlap that was legal at tick start remains legal long
  // enough to separate; otherwise the collision solver correctly sees an
  // impossible hard-contact starting state and aborts the battle.
  for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
    const left = live[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
      const right = live[rightIndex];
      if (left.owner === right.owner) continue;
      const key = dynamicPairKey(left.referenceId, right.referenceId);
      if (reservations.has(key) || inherited.has(key)) continue;
      const current = pairSeparation(left, right);
      if (current >= pairExtent(left, right) - EPSILON) continue;
      inherited.set(key, current);
      inheritedSources.set(key, "recovered");
      diagnostics.push(diagnostic("enemy-transit-recovered", key, {
        reason: "post-selection-square-overlap",
        currentExtent: current,
      }));
    }
  }

  const swept = new Map();
  for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
    const left = live[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
      const right = live[rightIndex];
      if (left.owner === right.owner) continue;
      const key = dynamicPairKey(left.referenceId, right.referenceId);
      if (reservations.has(key) || inherited.has(key)) continue;
      if (!pursuitByReference.has(left.referenceId)
          && !pursuitByReference.has(right.referenceId)) continue;
      const fullExtent = pairExtent(left, right);
      const current = pairSeparation(left, right);
      if (current < fullExtent - EPSILON) continue;
      const projected = pairSeparation(
        left,
        right,
        proposalsByReference.get(left.referenceId),
        proposalsByReference.get(right.referenceId),
      );
      if (projected >= fullExtent - EPSILON) continue;
      swept.set(key, projected);
      inherited.set(key, projected);
      inheritedSources.set(key, "swept");
      diagnostics.push(diagnostic("enemy-swept-contact", key, {
        reason: "relative-step-crossed-contact",
        fullExtent,
        projectedExtent: projected,
      }));
    }
  }

  const nextState = Object.freeze({
    reservations,
    inheritedContactExtents: inherited,
    inheritedContactSources: inheritedSources,
  });
  return Object.freeze({
    state: nextState,
    pairSnapshotData: Object.freeze({
      enemyTransitPairs: reservations,
      enemyPursuitTargets,
      sweptEnemyContactExtents: swept,
      inheritedEnemyContactExtents: inherited,
      circularEnemyContact: false,
    }),
    diagnostics: Object.freeze(diagnostics),
  });
}
