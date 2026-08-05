import { collisionRadius } from "./targeting.js";


// Numerical tolerance only. It does not change a unit's physical radius,
// speed, route length, or attack reach.
const EPSILON = 1e-12;


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireReferenceId(value, name = "reference ID") {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


function clampUnit(value) {
  return Math.max(-1, Math.min(1, value));
}


function positiveAngle(value) {
  const fullTurn = 2 * Math.PI;
  return ((value % fullTurn) + fullTurn) % fullTurn;
}


function freezeAvoidance(value) {
  if (value === null || value === undefined) return null;
  requireReferenceId(value.blockerReferenceId, "avoidance blocker reference ID");
  requireReferenceId(value.targetReferenceId, "avoidance target reference ID");
  if (value.side !== -1 && value.side !== 1) {
    throw new RangeError("avoidance side must be -1 or 1");
  }
  return Object.freeze({
    blockerReferenceId: value.blockerReferenceId,
    targetReferenceId: value.targetReferenceId,
    side: value.side,
  });
}


function attackGoalRadius(mover, target) {
  const range = requireFinite(mover?.mechanics?.attack_range_tiles, "attack range");
  if (range < 0) throw new RangeError("attack range must be nonnegative");
  return collisionRadius(mover) + collisionRadius(target) + range;
}


function contactGoal(mover, target) {
  const dx = mover.x - target.x;
  const dy = mover.y - target.y;
  const distance = Math.hypot(dx, dy);
  const radius = attackGoalRadius(mover, target);
  if (distance <= radius + EPSILON) {
    return { reached: true, radius, x: mover.x, y: mover.y };
  }
  return {
    reached: false,
    radius,
    x: target.x + dx / distance * radius,
    y: target.y + dy / distance * radius,
  };
}


function firstSegmentCircleIntersection(start, end, center, radius) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const fx = start.x - center.x;
  const fy = start.y - center.y;
  const a = dx * dx + dy * dy;
  if (a === 0) return null;
  const radiusSquared = radius * radius;
  const startOffset = fx * fx + fy * fy - radiusSquared;
  const inwardDerivative = fx * dx + fy * dy;
  if (
    startOffset < -EPSILON
    || (Math.abs(startOffset) <= EPSILON && inwardDerivative < -EPSILON)
  ) return 0;
  const b = 2 * (fx * dx + fy * dy);
  const c = startOffset;
  const discriminant = b * b - 4 * a * c;
  if (discriminant <= 0) return null;
  const root = Math.sqrt(discriminant);
  const candidates = [(-b - root) / (2 * a), (-b + root) / (2 * a)]
    .filter((value) => value > EPSILON && value <= 1 + EPSILON)
    .sort((left, right) => left - right);
  return candidates[0] ?? null;
}


function blockerIntersection(mover, goal, blocker) {
  const radius = collisionRadius(mover) + collisionRadius(blocker);
  return firstSegmentCircleIntersection(
    mover,
    goal,
    blocker,
    radius,
  );
}


function circleIntersections(first, firstRadius, second, secondRadius) {
  const dx = second.x - first.x;
  const dy = second.y - first.y;
  const distance = Math.hypot(dx, dy);
  if (
    distance <= EPSILON
    || distance > firstRadius + secondRadius + EPSILON
    || distance < Math.abs(firstRadius - secondRadius) - EPSILON
  ) return [];
  const along = (
    firstRadius ** 2 - secondRadius ** 2 + distance ** 2
  ) / (2 * distance);
  const height = Math.sqrt(Math.max(0, firstRadius ** 2 - along ** 2));
  const ux = dx / distance;
  const uy = dy / distance;
  const baseX = first.x + ux * along;
  const baseY = first.y + uy * along;
  if (height <= EPSILON) return [{ x: baseX, y: baseY }];
  return [
    { x: baseX - uy * height, y: baseY + ux * height },
    { x: baseX + uy * height, y: baseY - ux * height },
  ];
}


function entryTangent(mover, blocker, blockerRadius, side) {
  const dx = mover.x - blocker.x;
  const dy = mover.y - blocker.y;
  const distance = Math.hypot(dx, dy);
  if (distance < blockerRadius - EPSILON) return null;
  const fromAngle = Math.atan2(dy, dx);
  const offset = distance <= blockerRadius + EPSILON
    ? 0
    : Math.acos(clampUnit(blockerRadius / distance));
  const angle = fromAngle + side * offset;
  const point = {
    x: blocker.x + blockerRadius * Math.cos(angle),
    y: blocker.y + blockerRadius * Math.sin(angle),
  };
  const distanceToPoint = Math.hypot(point.x - mover.x, point.y - mover.y);
  const direction = distanceToPoint > EPSILON
    ? {
      x: (point.x - mover.x) / distanceToPoint,
      y: (point.y - mover.y) / distanceToPoint,
    }
    : { x: side * -Math.sin(angle), y: side * Math.cos(angle) };
  return { point, angle, distance: distanceToPoint, direction };
}


function firstIntersectionOnSide(intersections, blocker, entryAngle, side) {
  return intersections
    .map((point) => {
      const angle = Math.atan2(point.y - blocker.y, point.x - blocker.x);
      const arcAngle = side === 1
        ? positiveAngle(angle - entryAngle)
        : positiveAngle(entryAngle - angle);
      return { point, angle, arcAngle };
    })
    .sort((left, right) => left.arcAngle - right.arcAngle)[0] ?? null;
}


function routeToContact(mover, target, blocker, side) {
  const blockerRadius = collisionRadius(mover) + collisionRadius(blocker);
  const goalRadius = attackGoalRadius(mover, target);
  const entry = entryTangent(mover, blocker, blockerRadius, side);
  if (entry === null) return null;
  const centerDistance = Math.hypot(target.x - blocker.x, target.y - blocker.y);

  const intersections = circleIntersections(
    blocker,
    blockerRadius,
    target,
    goalRadius,
  );
  let exit;
  let goalPoint;
  let lineDistance;
  if (intersections.length > 0) {
    exit = firstIntersectionOnSide(intersections, blocker, entry.angle, side);
    goalPoint = exit.point;
    lineDistance = 0;
  } else {
    if (
      centerDistance <= EPSILON
      || centerDistance <= Math.abs(blockerRadius - goalRadius) + EPSILON
    ) return null;
    const ux = (target.x - blocker.x) / centerDistance;
    const uy = (target.y - blocker.y) / centerDistance;
    const px = -uy;
    const py = ux;
    const cosine = clampUnit((blockerRadius - goalRadius) / centerDistance);
    const sine = Math.sqrt(Math.max(0, 1 - cosine ** 2));
    const nx = ux * cosine - side * px * sine;
    const ny = uy * cosine - side * py * sine;
    const exitPoint = {
      x: blocker.x + blockerRadius * nx,
      y: blocker.y + blockerRadius * ny,
    };
    exit = {
      point: exitPoint,
      angle: Math.atan2(exitPoint.y - blocker.y, exitPoint.x - blocker.x),
    };
    exit.arcAngle = side === 1
      ? positiveAngle(exit.angle - entry.angle)
      : positiveAngle(entry.angle - exit.angle);
    goalPoint = {
      x: target.x + goalRadius * nx,
      y: target.y + goalRadius * ny,
    };
    lineDistance = Math.hypot(goalPoint.x - exit.point.x, goalPoint.y - exit.point.y);
  }

  return {
    side,
    blockerRadius,
    entry,
    exit,
    goalPoint,
    lineDistance,
    pathLength: entry.distance + blockerRadius * exit.arcAngle + lineDistance,
  };
}


function chooseRoute(mover, target, blocker) {
  const positive = routeToContact(mover, target, blocker, 1);
  const negative = routeToContact(mover, target, blocker, -1);
  if (positive === null) return negative;
  if (negative === null) return positive;
  if (positive.pathLength < negative.pathLength - EPSILON) return positive;
  if (negative.pathLength < positive.pathLength - EPSILON) return negative;

  if (!Number.isFinite(mover.facing)) return null;
  const facingX = Math.cos(mover.facing);
  const facingY = Math.sin(mover.facing);
  const positiveAlignment = facingX * positive.entry.direction.x
    + facingY * positive.entry.direction.y;
  const negativeAlignment = facingX * negative.entry.direction.x
    + facingY * negative.entry.direction.y;
  if (positiveAlignment > negativeAlignment + EPSILON) return positive;
  if (negativeAlignment > positiveAlignment + EPSILON) return negative;
  return null;
}


function advanceRoute(mover, blocker, route, budget) {
  let x = mover.x;
  let y = mover.y;
  let remaining = budget;
  if (route.entry.distance > EPSILON) {
    const travel = Math.min(remaining, route.entry.distance);
    x += route.entry.direction.x * travel;
    y += route.entry.direction.y * travel;
    remaining -= travel;
    if (remaining <= EPSILON) {
      return { dx: x - mover.x, dy: y - mover.y, complete: false };
    }
    x = route.entry.point.x;
    y = route.entry.point.y;
  }

  const currentAngle = Math.atan2(y - blocker.y, x - blocker.x);
  const arcAngle = route.side === 1
    ? positiveAngle(route.exit.angle - currentAngle)
    : positiveAngle(currentAngle - route.exit.angle);
  const arcLength = route.blockerRadius * arcAngle;
  if (remaining < arcLength - EPSILON) {
    const angle = currentAngle + route.side * remaining / route.blockerRadius;
    x = blocker.x + route.blockerRadius * Math.cos(angle);
    y = blocker.y + route.blockerRadius * Math.sin(angle);
    return { dx: x - mover.x, dy: y - mover.y, complete: false };
  }
  x = route.exit.point.x;
  y = route.exit.point.y;
  remaining -= arcLength;

  if (route.lineDistance > EPSILON) {
    const travel = Math.min(remaining, route.lineDistance);
    x += (route.goalPoint.x - route.exit.point.x) / route.lineDistance * travel;
    y += (route.goalPoint.y - route.exit.point.y) / route.lineDistance * travel;
    remaining -= travel;
    if (remaining <= EPSILON && travel < route.lineDistance - EPSILON) {
      return { dx: x - mover.x, dy: y - mover.y, complete: false };
    }
  }
  return {
    dx: route.goalPoint.x - mover.x,
    dy: route.goalPoint.y - mover.y,
    complete: true,
  };
}


function normalizeInputs(snapshot, proposals) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!Array.isArray(proposals)) throw new TypeError("proposals must be an array");
  const proposalByReference = new Map();
  for (const row of proposals) {
    const referenceId = requireReferenceId(row?.referenceId, "proposal reference ID");
    if (proposalByReference.has(referenceId)) {
      throw new Error(`duplicate movement proposal for reference ${referenceId}`);
    }
    proposalByReference.set(referenceId, Object.freeze({
      referenceId,
      dx: requireFinite(row.dx, "proposal dx"),
      dy: requireFinite(row.dy, "proposal dy"),
    }));
  }
  const seen = new Set();
  const units = snapshot.map((unit) => {
    const referenceId = requireReferenceId(unit?.referenceId);
    if (seen.has(referenceId)) throw new Error(`duplicate unit reference ${referenceId}`);
    seen.add(referenceId);
    return Object.freeze({ ...unit, avoidance: freezeAvoidance(unit.avoidance) });
  });
  for (const referenceId of proposalByReference.keys()) {
    if (!seen.has(referenceId)) throw new Error(`movement proposal references unknown unit ${referenceId}`);
  }
  return { units, proposalByReference };
}


export function planLocalAvoidance(snapshot, proposals) {
  const { units, proposalByReference } = normalizeInputs(snapshot, proposals);
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  const nextUnits = [];
  const nextProposals = [];
  const routes = [];

  for (const mover of units) {
    const original = proposalByReference.get(mover.referenceId)
      ?? Object.freeze({ referenceId: mover.referenceId, dx: 0, dy: 0 });
    const target = byReference.get(mover.targetId);
    const goal = target?.alive === false || !target ? null : contactGoal(mover, target);
    let avoidance = mover.avoidance;
    let route = null;
    let blocker = null;

    if (goal === null || goal.reached || mover.alive === false) {
      avoidance = null;
    } else if (avoidance !== null && avoidance.targetReferenceId === target.referenceId) {
      const candidate = byReference.get(avoidance.blockerReferenceId);
      if (
        candidate?.alive !== false
        && candidate?.referenceId !== target.referenceId
        && blockerIntersection(mover, goal, candidate) !== null
      ) {
        blocker = candidate;
        route = routeToContact(mover, target, blocker, avoidance.side);
      } else {
        avoidance = null;
      }
    } else {
      avoidance = null;
    }

    const budget = Math.hypot(original.dx, original.dy);
    if (goal !== null && !goal.reached && budget > EPSILON && route === null) {
      const candidate = units
        .filter((unit) => (
          unit.alive !== false
          && unit.referenceId !== mover.referenceId
          && unit.referenceId !== target.referenceId
        ))
        .map((unit) => ({ unit, intersection: blockerIntersection(mover, goal, unit) }))
        .filter(({ intersection }) => intersection !== null)
        .sort((left, right) => (
          left.intersection - right.intersection
          || left.unit.referenceId - right.unit.referenceId
        ))[0]?.unit ?? null;
      if (candidate !== null) {
        const selected = chooseRoute(mover, target, candidate);
        if (selected !== null) {
          blocker = candidate;
          route = selected;
          avoidance = freezeAvoidance({
            blockerReferenceId: candidate.referenceId,
            targetReferenceId: target.referenceId,
            side: selected.side,
          });
        }
      }
    }

    let nextProposal = original;
    if (route !== null && blocker !== null && budget > EPSILON) {
      const movement = advanceRoute(mover, blocker, route, budget);
      nextProposal = Object.freeze({
        referenceId: mover.referenceId,
        dx: movement.dx,
        dy: movement.dy,
      });
      const remainingPathLength = Math.max(0, route.pathLength - budget);
      routes.push(Object.freeze({
        referenceId: mover.referenceId,
        blockerReferenceId: blocker.referenceId,
        targetReferenceId: target.referenceId,
        side: route.side,
        remainingPathLength,
      }));
      if (movement.complete) avoidance = null;
    }

    nextUnits.push(Object.freeze({ ...mover, avoidance }));
    nextProposals.push(nextProposal);
  }

  return Object.freeze({
    units: Object.freeze(nextUnits),
    proposals: Object.freeze(nextProposals),
    routes: Object.freeze(routes.sort((left, right) => left.referenceId - right.referenceId)),
  });
}
