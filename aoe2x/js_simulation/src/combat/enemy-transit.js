import { dynamicPairKey } from "./pair-interactions.js";
import { collisionRadius } from "./targeting.js";


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
  if (!unit || unit.alive === false || !isMeleeMode(unit)) return null;
  const targetId = unit.pursuitTargetId;
  if (!Number.isSafeInteger(targetId)) return null;
  const target = byReference.get(targetId);
  if (!target || target.owner === unit.owner) return null;
  const proposal = proposals.get(unit.referenceId);
  if (!proposal || Math.hypot(proposal.dx, proposal.dy) <= EPSILON) return null;
  if (distanceSquared(unit, target, proposal) >= distanceSquared(unit, target) - EPSILON) {
    return null;
  }
  return Object.freeze({ unit, target, proposal });
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


function reservation(chaser, blocker, target, tick) {
  const direction = acquisitionDirection(chaser, target);
  return Object.freeze({
    chaserId: chaser.referenceId,
    blockerId: blocker.referenceId,
    pursuitTargetId: target.referenceId,
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
  const target = byReference.get(prior.pursuitTargetId);
  if (!target) return { reason: "target-missing", chaser, blocker, target };
  if (chaser.pursuitTargetId === blocker.referenceId) {
    return { reason: "blocker-became-target", chaser, blocker, target };
  }
  if (chaser.pursuitTargetId !== prior.pursuitTargetId) {
    return { reason: "target-changed", chaser, blocker, target };
  }
  const pursuit = activePursuer(chaser, byReference, proposals);
  if (!pursuit) return { reason: "pursuit-ended", chaser, blocker, target };
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
  if (!corridorCandidate(chaser, blocker, target)) {
    return { reason: "corridor-exit", chaser, blocker, target };
  }
  return { reason: null, chaser, blocker, target };
}


function diagnostic(type, pairKey, fields = {}) {
  return Object.freeze({ type, pairKey, ...fields });
}


export function createEnemyTransitState() {
  return Object.freeze({
    reservations: new Map(),
    inheritedContactExtents: new Map(),
  });
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
    if (current < priorExtent - EPSILON) {
      diagnostics.push(diagnostic("enemy-transit-recovered", key, {
        reason: "inherited-contact-deepened",
        previousExtent: priorExtent,
        currentExtent: current,
      }));
    }
  }

  const reservations = new Map();
  const reservedIds = new Set();
  for (const [key, prior] of [...previous.reservations]
    .sort(([left], [right]) => left.localeCompare(right))) {
    const released = releaseReason(prior, byReference, proposalsByReference);
    if (released.reason === null) {
      reservations.set(key, prior);
      reservedIds.add(prior.chaserId);
      reservedIds.add(prior.blockerId);
      inherited.delete(key);
      diagnostics.push(diagnostic("enemy-transit-persisted", key, {
        chaserId: prior.chaserId,
        blockerId: prior.blockerId,
        pursuitTargetId: prior.pursuitTargetId,
        reason: "reservation-valid",
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
  for (const pursuit of pursuits) {
    const chaser = pursuit.unit;
    if (reservedIds.has(chaser.referenceId)) continue;
    for (const blocker of live) {
      if (reservedIds.has(blocker.referenceId)) continue;
      const key = blocker.referenceId === chaser.referenceId
        ? null
        : dynamicPairKey(chaser.referenceId, blocker.referenceId);
      if (key === null || inherited.has(key)) continue;
      const corridor = corridorCandidate(chaser, blocker, pursuit.target);
      if (!corridor) continue;
      candidates.push({
        key,
        chaser,
        blocker,
        target: pursuit.target,
        forward: corridor.forward,
        lateral: corridor.lateral,
      });
    }
  }
  candidates.sort((left, right) => (
    left.forward - right.forward
      || left.lateral - right.lateral
      || left.chaser.referenceId - right.chaser.referenceId
      || left.blocker.referenceId - right.blocker.referenceId
  ));
  for (const candidate of candidates) {
    const chaserId = candidate.chaser.referenceId;
    const blockerId = candidate.blocker.referenceId;
    if (reservedIds.has(chaserId) || reservedIds.has(blockerId)) continue;
    const nextReservation = reservation(
      candidate.chaser,
      candidate.blocker,
      candidate.target,
      tick,
    );
    reservations.set(candidate.key, nextReservation);
    reservedIds.add(chaserId);
    reservedIds.add(blockerId);
    diagnostics.push(diagnostic("enemy-transit-acquired", candidate.key, {
      chaserId,
      blockerId,
      pursuitTargetId: candidate.target.referenceId,
      reason: "non-target-corridor",
    }));
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
  });
  return Object.freeze({
    state: nextState,
    pairSnapshotData: Object.freeze({
      enemyTransitPairs: reservations,
      sweptEnemyContactExtents: swept,
      inheritedEnemyContactExtents: inherited,
    }),
    diagnostics: Object.freeze(diagnostics),
  });
}
