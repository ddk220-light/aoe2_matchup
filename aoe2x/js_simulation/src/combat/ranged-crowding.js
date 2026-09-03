import { areAllies } from "./diplomacy.js";
import { collisionRadius, isWithinReach } from "./targeting.js";


const EPSILON = 1e-12;
// Friendly ranged bodies are compliant rather than intangible. Pair pressure
// is deliberately weak; shared three-body area is the signal that turns an
// incoming unit around the crowd. These weights operate on dimensionless
// body fractions, so they do not name a unit, formation, or matchup.
const PAIR_GROWTH_WEIGHT = 0.75;
const TRIPLE_GROWTH_WEIGHT = 96;
const LARGE_BODY_PAIR_GROWTH_WEIGHT = 48;
const LARGE_BODY_TRIPLE_GROWTH_WEIGHT = 768;
const STANDARD_RANGED_BODY_RADIUS = 0.2;
const RANGED_TRANSIT_BODY_CORE_FRACTION = 0.025;
// A committed siege body is a path obstacle to later ingress. Classification
// comes from AoE2's own Siege Weapon armor class (20), not body radius: large
// mobile ranged units remain compliant, while every present and future siege
// unit carrying that DAT class receives the same rule.
const SIEGE_ARMOR_CLASS = "20";
// Local crowd steering owns only the forward half-plane. A backwards move can
// be correct when routing around a connected firing rank, but deciding that
// from one tick of local pressure creates a memoryless A<->B oscillation. A
// non-progressing local minimum is promoted to the persistent path planner,
// which may authorize a backwards leg as part of a complete route.
const CANDIDATE_ANGLES = Object.freeze([
  0, 30, -30, 60, -60, 90, -90,
]);


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireReferenceId(value) {
  if (!Number.isSafeInteger(value)) throw new TypeError("reference ID must be a safe integer");
  return value;
}


function isRanged(unit) {
  return unit?.mechanics?.ranged !== null && unit?.mechanics?.ranged !== undefined;
}


function isSiegeRanged(unit) {
  return isRanged(unit)
    && Object.hasOwn(unit?.mechanics?.armor_classes ?? {}, SIEGE_ARMOR_CLASS);
}


function combatMotion(unit) {
  return unit?.moveOrder?.kind === "scenario-patrol"
    || Number.isSafeInteger(unit?.pursuitTargetId)
    || Number.isSafeInteger(unit?.engagedTargetId)
    || Number.isSafeInteger(unit?.attackTargetId)
    || unit?.action === "attacking"
    || unit?.action === "reload";
}


function crowdMovementEligible(unit, proposal) {
  return combatMotion(unit) && proposal?.movementIntent !== "minimum-range-retreat";
}


function pairKey(leftId, rightId) {
  return leftId < rightId ? `${leftId}:${rightId}` : `${rightId}:${leftId}`;
}


function positionOf(unit, proposal = null) {
  return Object.freeze({
    x: requireFinite(unit.x, "unit x") + (proposal?.dx ?? 0),
    y: requireFinite(unit.y, "unit y") + (proposal?.dy ?? 0),
  });
}


function extentBetween(left, right) {
  return collisionRadius(left) + collisionRadius(right);
}


function separation(leftPosition, rightPosition) {
  return Math.max(
    Math.abs(rightPosition.x - leftPosition.x),
    Math.abs(rightPosition.y - leftPosition.y),
  );
}


export function normalizedRangedPenetration(left, leftPosition, right, rightPosition) {
  const extent = extentBetween(left, right);
  return Math.max(0, 1 - separation(leftPosition, rightPosition) / extent);
}


export function sharedRangedIntersectionFraction(entries) {
  if (!Array.isArray(entries) || entries.length < 2) {
    throw new TypeError("shared intersection requires at least two ranged bodies");
  }
  const left = Math.max(...entries.map(({ unit, position }) => (
    position.x - collisionRadius(unit)
  )));
  const right = Math.min(...entries.map(({ unit, position }) => (
    position.x + collisionRadius(unit)
  )));
  const bottom = Math.max(...entries.map(({ unit, position }) => (
    position.y - collisionRadius(unit)
  )));
  const top = Math.min(...entries.map(({ unit, position }) => (
    position.y + collisionRadius(unit)
  )));
  const area = Math.max(0, right - left) * Math.max(0, top - bottom);
  const smallestBodyArea = Math.min(...entries.map(({ unit }) => (
    (2 * collisionRadius(unit)) ** 2
  )));
  return area / smallestBodyArea;
}


function combinations(values, size) {
  const output = [];
  const choose = (start, selected) => {
    if (selected.length === size) {
      output.push(selected);
      return;
    }
    for (let index = start; index <= values.length - (size - selected.length); index += 1) {
      choose(index + 1, [...selected, values[index]]);
    }
  };
  choose(0, []);
  return output;
}


function crowdMetrics(mover, moverPosition, allies, positions) {
  const overlapping = [];
  let pairCost = 0;
  for (const ally of allies) {
    const allyPosition = positions.get(ally.referenceId);
    const penetration = normalizedRangedPenetration(
      mover,
      moverPosition,
      ally,
      allyPosition,
    );
    if (penetration <= EPSILON) continue;
    pairCost += penetration ** 2;
    overlapping.push(ally);
  }
  let tripleArea = 0;
  let maximumFourArea = 0;
  for (const pair of combinations(overlapping, 2)) {
    tripleArea += sharedRangedIntersectionFraction([
      { unit: mover, position: moverPosition },
      ...pair.map((unit) => ({ unit, position: positions.get(unit.referenceId) })),
    ]);
  }
  for (const triple of combinations(overlapping, 3)) {
    maximumFourArea = Math.max(
      maximumFourArea,
      sharedRangedIntersectionFraction([
        { unit: mover, position: moverPosition },
        ...triple.map((unit) => ({ unit, position: positions.get(unit.referenceId) })),
      ]),
    );
  }
  return Object.freeze({
    overlapCount: overlapping.length,
    pairCost,
    tripleArea,
    maximumFourArea,
  });
}


function rotateProposal(proposal, degrees) {
  if (degrees === 0) return proposal;
  const radians = degrees * Math.PI / 180;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  return Object.freeze({
    ...proposal,
    referenceId: proposal.referenceId,
    dx: proposal.dx * cosine - proposal.dy * sine,
    dy: proposal.dx * sine + proposal.dy * cosine,
  });
}


function movementPriority(unit, byReference) {
  const target = byReference.get(unit.pursuitTargetId)
    ?? byReference.get(unit.engagedTargetId)
    ?? byReference.get(unit.attackTargetId);
  const goal = target?.alive !== false ? target : unit.moveOrder;
  if (!goal || !Number.isFinite(goal.x) || !Number.isFinite(goal.y)) {
    return Number.POSITIVE_INFINITY;
  }
  return Math.hypot(goal.x - unit.x, goal.y - unit.y);
}


function livePursuitOutsideReach(unit, byReference) {
  const target = byReference.get(unit.pursuitTargetId);
  return Boolean(target && target.alive !== false && !isWithinReach(unit, target));
}


function candidateScore(
  candidate,
  desired,
  currentMetrics,
  candidateMetrics,
  preferredSign,
  pairGrowthWeight,
  tripleGrowthWeight,
) {
  if (candidateMetrics.maximumFourArea > currentMetrics.maximumFourArea + EPSILON) {
    return Number.POSITIVE_INFINITY;
  }
  const budgetSquared = desired.dx ** 2 + desired.dy ** 2;
  const progress = budgetSquared <= EPSILON
    ? 1
    : (candidate.dx * desired.dx + candidate.dy * desired.dy) / budgetSquared;
  const lostProgress = Math.max(0, 1 - progress);
  const pairGrowth = Math.max(0, candidateMetrics.pairCost - currentMetrics.pairCost);
  const tripleGrowth = Math.max(
    0,
    candidateMetrics.tripleArea - currentMetrics.tripleArea,
  );
  const cross = desired.dx * candidate.dy - desired.dy * candidate.dx;
  const tiePenalty = Math.abs(cross) <= EPSILON || Math.sign(cross) === preferredSign
    ? 0
    : 1e-9;
  return lostProgress
    + pairGrowthWeight * pairGrowth
    + tripleGrowthWeight * tripleGrowth
    + tiePenalty;
}


function crowdReservation(
  left,
  right,
  currentPosition,
  projectedPosition,
  tick,
) {
  const fullExtent = extentBetween(left, right);
  const current = separation(currentPosition.get(left.referenceId), currentPosition.get(right.referenceId));
  const projected = separation(
    projectedPosition.get(left.referenceId),
    projectedPosition.get(right.referenceId),
  );
  const committedSiegeBody = [left, right].some((unit) => (
    isSiegeRanged(unit) && (unit.action === "attacking" || unit.action === "reload")
  ));
  // Transit may consume this tick's compliant projection. Once either body
  // has committed, only overlap that already exists may be inherited; a later
  // row cannot manufacture fresh penetration through the established firing
  // rank. Publishing the exact inherited separation is also important: a
  // reservation cannot retroactively declare the current geometry invalid.
  const collisionExtent = committedSiegeBody
    ? Math.min(fullExtent, current)
    : Math.max(
      fullExtent * RANGED_TRANSIT_BODY_CORE_FRACTION,
      Math.min(fullExtent, current, projected),
    );
  const [leftId, rightId] = left.referenceId < right.referenceId
    ? [left.referenceId, right.referenceId]
    : [right.referenceId, left.referenceId];
  return Object.freeze({
    leftId,
    rightId,
    kind: "ranged-crowd",
    collisionExtent,
    attackSurfaceExtent: fullExtent,
    // Existing transit overlap may be inherited by a firing pair, but a
    // committed firing/reload rank is an obstacle to NEW ingress. This is the
    // distinction visible in the tapes: two or three already-stacked pairs
    // can remain motionless for many seconds, while later rows fan around
    // them instead of building a 20-body overlap chain.
    // Non-siege ranged bodies stay compliant regardless of their radius. A
    // committed Siege-class body obstructs fresh ingress and restores its
    // inherited separation, so transit compression cannot turn the rear siege
    // rank into an immediate second firing rank.
    pathObstructs: committedSiegeBody,
    mayDeepen: false,
    initiatorId: null,
    targetId: null,
    acquiredTick: tick,
  });
}


export function planRangedCrowding(units, proposals, tick, {
  authoritativeReferenceIds = new Set(),
} = {}) {
  if (!Array.isArray(units)) throw new TypeError("ranged crowd units must be an array");
  if (!Array.isArray(proposals)) throw new TypeError("ranged crowd proposals must be an array");
  if (!Number.isSafeInteger(tick) || tick < 0) {
    throw new TypeError("ranged crowd tick must be a nonnegative safe integer");
  }
  if (!(authoritativeReferenceIds instanceof Set)) {
    throw new TypeError("authoritative ranged crowd references must be a Set");
  }
  const live = units.filter((unit) => unit?.alive !== false);
  const byReference = new Map(live.map((unit) => [requireReferenceId(unit.referenceId), unit]));
  const proposalByReference = new Map(proposals.map((proposal) => [
    requireReferenceId(proposal.referenceId),
    Object.freeze({
      ...proposal,
      referenceId: proposal.referenceId,
      dx: requireFinite(proposal.dx, "proposal dx"),
      dy: requireFinite(proposal.dy, "proposal dy"),
    }),
  ]));
  if (proposalByReference.size !== proposals.length) {
    throw new Error("duplicate ranged crowd movement proposal");
  }
  const currentPositions = new Map(live.map((unit) => [unit.referenceId, positionOf(unit)]));
  const projectedPositions = new Map(currentPositions);
  const adjusted = new Map(proposalByReference);
  const movers = live.filter((unit) => {
    const proposal = proposalByReference.get(unit.referenceId);
    return !authoritativeReferenceIds.has(unit.referenceId)
      && isRanged(unit) && crowdMovementEligible(unit, proposal) && proposal
      && Math.hypot(proposal.dx, proposal.dy) > EPSILON;
  }).sort((left, right) => (
    movementPriority(left, byReference) - movementPriority(right, byReference)
      || left.referenceId - right.referenceId
  ));
  const steered = [];
  const routeRequests = [];

  for (const mover of movers) {
    const desired = proposalByReference.get(mover.referenceId);
    const allies = live.filter((other) => (
      other.referenceId !== mover.referenceId
      && isRanged(other)
      && areAllies(mover, other)
      && (combatMotion(mover) || combatMotion(other))
    ));
    if (allies.length === 0) {
      projectedPositions.set(mover.referenceId, positionOf(mover, desired));
      continue;
    }
    const currentMetrics = crowdMetrics(
      mover,
      currentPositions.get(mover.referenceId),
      allies,
      currentPositions,
    );
    const preferredSign = mover.referenceId % 2 === 0 ? 1 : -1;
    // Larger non-siege ranged bodies cannot pack through an infantry-width
    // firing rank with the same compliance as foot archers. Classification
    // comes solely from physical DAT body size; arrow count and unit identity
    // are irrelevant. Siege uses its separate committed-body obstruction.
    const largeMobileBody = !isSiegeRanged(mover)
      && collisionRadius(mover) > STANDARD_RANGED_BODY_RADIUS + EPSILON;
    const pairGrowthWeight = largeMobileBody
      ? LARGE_BODY_PAIR_GROWTH_WEIGHT
      : PAIR_GROWTH_WEIGHT;
    const tripleGrowthWeight = largeMobileBody
      ? LARGE_BODY_TRIPLE_GROWTH_WEIGHT
      : TRIPLE_GROWTH_WEIGHT;
    const candidates = CANDIDATE_ANGLES.map((degrees) => rotateProposal(desired, degrees));
    candidates.push(Object.freeze({ ...desired, dx: 0, dy: 0 }));
    const ranked = candidates.map((candidate, order) => {
      const candidatePosition = positionOf(mover, candidate);
      const metrics = crowdMetrics(mover, candidatePosition, allies, projectedPositions);
      return {
        candidate,
        metrics,
        order,
        score: candidateScore(candidate, desired, currentMetrics, metrics,
          preferredSign, pairGrowthWeight, tripleGrowthWeight),
      };
    }).sort((left, right) => left.score - right.score || left.order - right.order);
    let selected = ranked[0];
    const budgetSquared = desired.dx ** 2 + desired.dy ** 2;
    const progressFraction = budgetSquared <= EPSILON
      ? 1
      : (selected.candidate.dx * desired.dx + selected.candidate.dy * desired.dy)
        / budgetSquared;
    const target = byReference.get(mover.pursuitTargetId);
    const requiresRoute = livePursuitOutsideReach(mover, byReference)
      && progressFraction <= 1e-9;
    if (requiresRoute) {
      routeRequests.push(Object.freeze({
        referenceId: mover.referenceId,
        targetReferenceId: target.referenceId,
        wantedDx: desired.dx,
        wantedDy: desired.dy,
        reason: "ranged-crowd-local-minimum",
      }));
      // The caller replaces this hold with an authoritative route proposal on
      // the same tick. If the global planner proves there is no route, holding
      // is safer than inventing a backwards local heading with no commitment.
      selected = Object.freeze({
        candidate: Object.freeze({ ...desired, dx: 0, dy: 0 }),
        metrics: currentMetrics,
        order: CANDIDATE_ANGLES.length,
        score: selected.score,
      });
    }
    adjusted.set(mover.referenceId, selected.candidate);
    projectedPositions.set(mover.referenceId, positionOf(mover, selected.candidate));
    if (selected.order !== 0) {
      steered.push(Object.freeze({
        referenceId: mover.referenceId,
        candidateIndex: selected.order,
        pairCost: selected.metrics.pairCost,
        tripleArea: selected.metrics.tripleArea,
        maximumFourArea: selected.metrics.maximumFourArea,
        requiresRoute,
      }));
    }
  }

  for (const unit of live) {
    if (!projectedPositions.has(unit.referenceId)) {
      projectedPositions.set(
        unit.referenceId,
        positionOf(unit, adjusted.get(unit.referenceId)),
      );
    }
  }
  const contactReservations = new Map();
  for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
    const left = live[leftIndex];
    if (!isRanged(left)) continue;
    for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
      const right = live[rightIndex];
      if (!isRanged(right) || !areAllies(left, right)) continue;
      const leftProposal = adjusted.get(left.referenceId);
      const rightProposal = adjusted.get(right.referenceId);
      if (leftProposal?.movementIntent === "minimum-range-retreat"
          || rightProposal?.movementIntent === "minimum-range-retreat") continue;
      if (!crowdMovementEligible(left, leftProposal)
          && !crowdMovementEligible(right, rightProposal)) continue;
      const fullExtent = extentBetween(left, right);
      const current = separation(
        currentPositions.get(left.referenceId),
        currentPositions.get(right.referenceId),
      );
      const projected = separation(
        projectedPositions.get(left.referenceId),
        projectedPositions.get(right.referenceId),
      );
      if (current >= fullExtent - EPSILON && projected >= fullExtent - EPSILON) continue;
      contactReservations.set(
        pairKey(left.referenceId, right.referenceId),
        crowdReservation(left, right, currentPositions, projectedPositions, tick),
      );
    }
  }
  return Object.freeze({
    proposals: Object.freeze(proposals.map((proposal) => (
      adjusted.get(proposal.referenceId) ?? proposal
    ))),
    contactReservations,
    routeRequests: Object.freeze(routeRequests.sort((left, right) => (
      left.referenceId - right.referenceId
    ))),
    steered: Object.freeze(steered.sort((left, right) => left.referenceId - right.referenceId)),
  });
}
