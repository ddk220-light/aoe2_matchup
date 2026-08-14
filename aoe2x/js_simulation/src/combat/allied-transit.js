import { collisionRadius, isWithinReach } from "./targeting.js";


const EPSILON = 1e-12;


export function alliedTransitPairKey(leftId, rightId) {
  return leftId < rightId ? `${leftId}:${rightId}` : `${rightId}:${leftId}`;
}


function isMoving(proposal) {
  return proposal !== undefined
    && Math.hypot(proposal.dx, proposal.dy) > EPSILON;
}


function chebyshevSeparation(left, right, leftProposal = null, rightProposal = null) {
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


function reachedPursuitTarget(unit, byReference) {
  const target = byReference.get(unit.pursuitTargetId);
  return target !== undefined
    && target.alive !== false
    && target.owner !== unit.owner
    && isWithinReach(unit, target);
}


function axisContactInterval(start, velocity, extent) {
  if (Math.abs(velocity) <= EPSILON) {
    return Math.abs(start) < extent - EPSILON
      ? { enter: Number.NEGATIVE_INFINITY, exit: Number.POSITIVE_INFINITY }
      : null;
  }
  const first = (-extent - start) / velocity;
  const second = (extent - start) / velocity;
  return { enter: Math.min(first, second), exit: Math.max(first, second) };
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
  if (x === null || y === null) return null;
  const enter = Math.max(0, x.enter, y.enter);
  const exit = Math.min(1, x.exit, y.exit);
  return enter <= exit + EPSILON ? Math.max(0, Math.min(1, enter)) : null;
}


function reservationFor(left, right) {
  const dx = right.x - left.x;
  const dy = right.y - left.y;
  const axis = Math.abs(dx) >= Math.abs(dy) ? "x" : "y";
  const relative = axis === "x" ? dx : dy;
  if (Math.abs(relative) <= EPSILON) return null;
  return Object.freeze({
    leftId: left.referenceId,
    rightId: right.referenceId,
    axis,
    sign: relative < 0 ? -1 : 1,
  });
}


function reservationRemainsActive(reservation, byReference, proposalByReference, cohort) {
  const left = byReference.get(reservation.leftId);
  const right = byReference.get(reservation.rightId);
  if (!left?.alive || !right?.alive || left.owner !== right.owner) return false;
  if (!cohort.has(left.referenceId) || !cohort.has(right.referenceId)) return false;
  if (reachedPursuitTarget(left, byReference)
      || reachedPursuitTarget(right, byReference)) return false;
  const leftProposal = proposalByReference.get(left.referenceId);
  const rightProposal = proposalByReference.get(right.referenceId);
  if (!isMoving(leftProposal) || !isMoving(rightProposal)) return false;
  const ordinaryExtent = collisionRadius(left) + collisionRadius(right);
  const currentSeparation = chebyshevSeparation(left, right);
  if (currentSeparation >= ordinaryExtent - EPSILON) return false;
  const relative = right[reservation.axis] - left[reservation.axis];
  if (Math.abs(relative) <= EPSILON
      || (relative < 0 ? -1 : 1) !== reservation.sign) return false;
  const projectedRelative = relative
    + rightProposal[reservation.axis] - leftProposal[reservation.axis];
  const crossesThisTick = Math.abs(projectedRelative) > EPSILON
    && (projectedRelative < 0 ? -1 : 1) !== reservation.sign;
  return crossesThisTick
    || chebyshevSeparation(left, right, leftProposal, rightProposal)
      < currentSeparation - EPSILON;
}


export function updateAlliedTransit(state, units, proposals) {
  const cohort = state?.cohort instanceof Set ? state.cohort : new Set();
  const previous = state?.reservations instanceof Map ? state.reservations : new Map();
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  const proposalByReference = new Map(
    proposals.map((proposal) => [proposal.referenceId, proposal]),
  );
  const reservations = new Map();
  const reservedIds = new Set();

  for (const [key, reservation] of [...previous].sort(([left], [right]) => (
    left.localeCompare(right)
  ))) {
    if (!reservationRemainsActive(
      reservation, byReference, proposalByReference, cohort,
    )) continue;
    reservations.set(key, reservation);
    reservedIds.add(reservation.leftId);
    reservedIds.add(reservation.rightId);
  }

  const candidates = [];
  const movers = units.filter((unit) => (
    unit.alive !== false
      && cohort.has(unit.referenceId)
      && isMoving(proposalByReference.get(unit.referenceId))
  )).sort((left, right) => left.referenceId - right.referenceId);
  for (let leftIndex = 0; leftIndex < movers.length; leftIndex += 1) {
    const left = movers[leftIndex];
    const leftProposal = proposalByReference.get(left.referenceId);
    for (let rightIndex = leftIndex + 1; rightIndex < movers.length; rightIndex += 1) {
      const right = movers[rightIndex];
      if (left.owner !== right.owner) continue;
      if (reachedPursuitTarget(left, byReference)
          || reachedPursuitTarget(right, byReference)) continue;
      const rightProposal = proposalByReference.get(right.referenceId);
      if (leftProposal.dx * rightProposal.dx + leftProposal.dy * rightProposal.dy <= EPSILON) {
        continue;
      }
      const currentSeparation = chebyshevSeparation(left, right);
      const finalSeparation = chebyshevSeparation(
        left, right, leftProposal, rightProposal,
      );
      if (finalSeparation >= currentSeparation - EPSILON) continue;
      const extent = collisionRadius(left) + collisionRadius(right);
      const entry = sweptEntryFraction(
        left, right, leftProposal, rightProposal, extent,
      );
      if (entry === null) continue;
      const reservation = reservationFor(left, right);
      if (reservation === null) continue;
      candidates.push({
        entry,
        finalSeparation,
        key: alliedTransitPairKey(left.referenceId, right.referenceId),
        reservation,
      });
    }
  }
  candidates.sort((left, right) => (
    left.entry - right.entry
      || left.finalSeparation - right.finalSeparation
      || left.reservation.leftId - right.reservation.leftId
      || left.reservation.rightId - right.reservation.rightId
  ));
  for (const candidate of candidates) {
    const { leftId, rightId } = candidate.reservation;
    if (reservedIds.has(leftId) || reservedIds.has(rightId)) continue;
    reservations.set(candidate.key, candidate.reservation);
    reservedIds.add(leftId);
    reservedIds.add(rightId);
  }

  return Object.freeze({
    reservations,
    pairKeys: new Set([...reservations.keys()].sort()),
  });
}
