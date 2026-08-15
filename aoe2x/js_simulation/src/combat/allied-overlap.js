import { alliedTransitPairKey } from "./allied-transit.js";
import { collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;


function isMoving(proposal) {
  return proposal !== undefined
    && Math.hypot(proposal.dx, proposal.dy) > EPSILON;
}


function separation(left, right, leftProposal = null, rightProposal = null) {
  return Math.max(
    Math.abs(right.x + (rightProposal?.dx ?? 0) - left.x - (leftProposal?.dx ?? 0)),
    Math.abs(right.y + (rightProposal?.dy ?? 0) - left.y - (leftProposal?.dy ?? 0)),
  );
}


function reservation(leftId, rightId) {
  return Object.freeze({
    leftId: Math.min(leftId, rightId),
    rightId: Math.max(leftId, rightId),
  });
}


export function updateExclusiveAlliedOverlap(state, units, proposals, owner) {
  if (!Number.isSafeInteger(owner)) throw new TypeError("allied-overlap owner is required");
  const live = units
    .filter((unit) => unit.alive !== false && unit.owner === owner)
    .toSorted((left, right) => left.referenceId - right.referenceId);
  const byReference = new Map(live.map((unit) => [unit.referenceId, unit]));
  const proposalByReference = new Map(
    proposals.map((proposal) => [proposal.referenceId, proposal]),
  );
  const qualifies = (left, right) => {
    const leftProposal = proposalByReference.get(left.referenceId);
    const rightProposal = proposalByReference.get(right.referenceId);
    if (!isMoving(leftProposal) && !isMoving(rightProposal)) return false;
    const extent = collisionRadius(left) + collisionRadius(right);
    return Math.min(
      separation(left, right),
      separation(left, right, leftProposal, rightProposal),
    ) < extent - EPSILON;
  };
  const remainsActive = (left, right) => (
    separation(left, right) < collisionRadius(left) + collisionRadius(right) - EPSILON
      || qualifies(left, right)
  );

  const reservations = new Map();
  const reservedIds = new Set();
  const previous = state?.reservations instanceof Map ? state.reservations : new Map();
  for (const [key, prior] of [...previous].sort(([left], [right]) => left.localeCompare(right))) {
    const left = byReference.get(prior.leftId);
    const right = byReference.get(prior.rightId);
    if (!left || !right || !remainsActive(left, right)) continue;
    reservations.set(key, reservation(left.referenceId, right.referenceId));
    reservedIds.add(left.referenceId);
    reservedIds.add(right.referenceId);
  }

  const candidates = [];
  for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
    const left = live[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
      const right = live[rightIndex];
      if (!qualifies(left, right)) continue;
      const leftProposal = proposalByReference.get(left.referenceId);
      const rightProposal = proposalByReference.get(right.referenceId);
      candidates.push({
        key: alliedTransitPairKey(left.referenceId, right.referenceId),
        reservation: reservation(left.referenceId, right.referenceId),
        projectedSeparation: separation(left, right, leftProposal, rightProposal),
        currentSeparation: separation(left, right),
      });
    }
  }
  candidates.sort((left, right) => (
    left.projectedSeparation - right.projectedSeparation
      || left.currentSeparation - right.currentSeparation
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

  // Keep ordinary crowd compression available as a sparse contact graph, not
  // as an all-pairs permission. A shallow edge may attach an unreserved mover
  // to one member of a deep pair, but adding an edge that closes a triangle is
  // rejected. This lets a line or arc of melee units keep flowing around the
  // front without turning three adjacent bodies into a persistent compact
  // stack. Degree four matches the largest local contact fan observed in the
  // authorized Paladin tape while the triangle rule controls multiplicity.
  const adjacency = new Map(live.map(({ referenceId }) => [referenceId, new Set()]));
  for (const { leftId, rightId } of reservations.values()) {
    adjacency.get(leftId).add(rightId);
    adjacency.get(rightId).add(leftId);
  }
  const shallowPairKeys = new Set();
  for (const candidate of candidates) {
    if (reservations.has(candidate.key)) continue;
    const { leftId, rightId } = candidate.reservation;
    if (reservedIds.has(leftId) && reservedIds.has(rightId)) continue;
    const leftNeighbors = adjacency.get(leftId);
    const rightNeighbors = adjacency.get(rightId);
    if (leftNeighbors.size >= 4 || rightNeighbors.size >= 4) continue;
    if ([...leftNeighbors].some((neighbor) => rightNeighbors.has(neighbor))) continue;
    shallowPairKeys.add(candidate.key);
    leftNeighbors.add(rightId);
    rightNeighbors.add(leftId);
  }

  return Object.freeze({
    reservations,
    pairKeys: new Set([...reservations.keys()].sort()),
    shallowPairKeys: new Set([...shallowPairKeys].sort()),
    reservedIds: new Set([...reservedIds].sort((left, right) => left - right)),
  });
}
