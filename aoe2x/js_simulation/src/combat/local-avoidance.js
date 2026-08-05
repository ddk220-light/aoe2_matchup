import { TICKS_PER_SECOND } from "../simulation-clock.js";
import { collisionRadius } from "./targeting.js";


// Floating-point comparison tolerance only; no physical value is adjusted.
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


function directedAngle(from, to, side) {
  return side === 1 ? positiveAngle(to - from) : positiveAngle(from - to);
}


function freezeAvoidance(value) {
  if (value === null || value === undefined) return null;
  requireReferenceId(value.targetReferenceId, "avoidance target reference ID");
  if (value.side !== -1 && value.side !== 1) {
    throw new RangeError("avoidance side must be -1 or 1");
  }
  if (value.blockerObstacleIndex !== undefined) {
    if (!Number.isSafeInteger(value.blockerObstacleIndex) || value.blockerObstacleIndex < 0) {
      throw new TypeError("avoidance blocker obstacle index must be a nonnegative integer");
    }
    return Object.freeze({
      blockerObstacleIndex: value.blockerObstacleIndex,
      targetReferenceId: value.targetReferenceId,
      side: value.side,
    });
  }
  requireReferenceId(value.blockerReferenceId, "avoidance blocker reference ID");
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
  const startOffset = fx * fx + fy * fy - radius * radius;
  const inwardDerivative = fx * dx + fy * dy;
  if (
    startOffset < -EPSILON
    || (Math.abs(startOffset) <= EPSILON && inwardDerivative < -EPSILON)
  ) return 0;
  const b = 2 * inwardDerivative;
  const discriminant = b * b - 4 * a * startOffset;
  if (discriminant <= 0) return null;
  const root = Math.sqrt(discriminant);
  return [(-b - root) / (2 * a), (-b + root) / (2 * a)]
    .filter((value) => value > EPSILON && value <= 1 + EPSILON)
    .sort((left, right) => left - right)[0] ?? null;
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


function entryTangent(mover, blocker, side) {
  const dx = mover.x - blocker.x;
  const dy = mover.y - blocker.y;
  const distance = Math.hypot(dx, dy);
  if (distance < blocker.radius - EPSILON) return null;
  const fromAngle = Math.atan2(dy, dx);
  const offset = distance <= blocker.radius + EPSILON
    ? 0
    : Math.acos(clampUnit(blocker.radius / distance));
  const angle = fromAngle + side * offset;
  const point = {
    x: blocker.x + blocker.radius * Math.cos(angle),
    y: blocker.y + blocker.radius * Math.sin(angle),
  };
  const pointDistance = Math.hypot(point.x - mover.x, point.y - mover.y);
  const direction = pointDistance > EPSILON
    ? { x: (point.x - mover.x) / pointDistance, y: (point.y - mover.y) / pointDistance }
    : { x: side * -Math.sin(angle), y: side * Math.cos(angle) };
  return { point, angle, distance: pointDistance, direction };
}


function firstIntersectionOnSide(intersections, blocker, entryAngle, side) {
  return intersections
    .map((point) => {
      const angle = Math.atan2(point.y - blocker.y, point.x - blocker.x);
      return { point, angle, arcAngle: directedAngle(entryAngle, angle, side) };
    })
    .sort((left, right) => left.arcAngle - right.arcAngle)[0] ?? null;
}


function routeToContact(mover, target, blocker, side) {
  const goalRadius = attackGoalRadius(mover, target);
  const entry = entryTangent(mover, blocker, side);
  if (entry === null) return null;
  const centerDistance = Math.hypot(target.x - blocker.x, target.y - blocker.y);
  const intersections = circleIntersections(blocker, blocker.radius, target, goalRadius);
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
      || centerDistance <= Math.abs(blocker.radius - goalRadius) + EPSILON
    ) return null;
    const ux = (target.x - blocker.x) / centerDistance;
    const uy = (target.y - blocker.y) / centerDistance;
    const px = -uy;
    const py = ux;
    const cosine = clampUnit((blocker.radius - goalRadius) / centerDistance);
    const sine = Math.sqrt(Math.max(0, 1 - cosine ** 2));
    const nx = ux * cosine - side * px * sine;
    const ny = uy * cosine - side * py * sine;
    const exitPoint = {
      x: blocker.x + blocker.radius * nx,
      y: blocker.y + blocker.radius * ny,
    };
    exit = {
      point: exitPoint,
      angle: Math.atan2(exitPoint.y - blocker.y, exitPoint.x - blocker.x),
    };
    exit.arcAngle = directedAngle(entry.angle, exit.angle, side);
    goalPoint = {
      x: target.x + goalRadius * nx,
      y: target.y + goalRadius * ny,
    };
    lineDistance = Math.hypot(goalPoint.x - exit.point.x, goalPoint.y - exit.point.y);
  }

  return {
    side,
    blocker,
    entry,
    exit,
    goalPoint,
    lineDistance,
    pathLength: entry.distance + blocker.radius * exit.arcAngle + lineDistance,
  };
}


function pointSegmentDistance(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return Math.hypot(point.x - start.x, point.y - start.y);
  const projection = Math.max(0, Math.min(1, (
    (point.x - start.x) * dx + (point.y - start.y) * dy
  ) / lengthSquared));
  return Math.hypot(
    point.x - start.x - projection * dx,
    point.y - start.y - projection * dy,
  );
}


function segmentClears(start, end, constraint) {
  return pointSegmentDistance(constraint, start, end) >= constraint.radius - EPSILON;
}


function arcClears(route, constraint) {
  const endpointDistance = Math.min(
    Math.hypot(constraint.x - route.entry.point.x, constraint.y - route.entry.point.y),
    Math.hypot(constraint.x - route.exit.point.x, constraint.y - route.exit.point.y),
  );
  const centerAngle = Math.atan2(
    constraint.y - route.blocker.y,
    constraint.x - route.blocker.x,
  );
  const angleWithinArc = directedAngle(route.entry.angle, centerAngle, route.side)
    <= route.exit.arcAngle + EPSILON;
  const radialDistance = Math.hypot(
    constraint.x - route.blocker.x,
    constraint.y - route.blocker.y,
  );
  const minimum = angleWithinArc
    ? Math.min(endpointDistance, Math.abs(radialDistance - route.blocker.radius))
    : endpointDistance;
  return minimum >= constraint.radius - EPSILON;
}


function pointInsideBounds(point, radius, bounds) {
  if (bounds === null) return true;
  return (
    point.x >= radius - EPSILON
    && point.x <= bounds.width - radius + EPSILON
    && point.y >= radius - EPSILON
    && point.y <= bounds.height - radius + EPSILON
  );
}


function arcInsideBounds(route, moverRadius, bounds) {
  if (bounds === null) return true;
  const points = [route.entry.point, route.exit.point];
  for (const angle of [0, Math.PI / 2, Math.PI, -Math.PI / 2]) {
    if (directedAngle(route.entry.angle, angle, route.side) <= route.exit.arcAngle + EPSILON) {
      points.push({
        x: route.blocker.x + route.blocker.radius * Math.cos(angle),
        y: route.blocker.y + route.blocker.radius * Math.sin(angle),
      });
    }
  }
  return points.every((point) => pointInsideBounds(point, moverRadius, bounds));
}


function routeClears(route, constraints, moverRadius, bounds) {
  if (
    !pointInsideBounds(route.entry.point, moverRadius, bounds)
    || !pointInsideBounds(route.goalPoint, moverRadius, bounds)
    || !arcInsideBounds(route, moverRadius, bounds)
  ) return false;
  return constraints.every((constraint) => (
    constraint.key === route.blocker.key
    || (
      segmentClears(route.entryStart, route.entry.point, constraint)
      && arcClears(route, constraint)
      && segmentClears(route.exit.point, route.goalPoint, constraint)
    )
  ));
}


function routeStep(mover, target, route, budget) {
  if (budget <= EPSILON) return { dx: 0, dy: 0, remainingPathLength: route.pathLength };
  const goalRadius = attackGoalRadius(mover, target);
  const towardTargetX = target.x - mover.x;
  const towardTargetY = target.y - mover.y;
  const projection = towardTargetX * route.entry.direction.x
    + towardTargetY * route.entry.direction.y;
  const perpendicularSquared = towardTargetX ** 2 + towardTargetY ** 2 - projection ** 2;
  const contactDistance = projection > EPSILON && perpendicularSquared <= goalRadius ** 2
    ? projection - Math.sqrt(Math.max(0, goalRadius ** 2 - perpendicularSquared))
    : null;
  const remainingPathLength = contactDistance !== null && contactDistance > EPSILON
    ? contactDistance
    : route.pathLength;
  const distance = Math.min(budget, remainingPathLength);
  const end = {
    x: mover.x + route.entry.direction.x * distance,
    y: mover.y + route.entry.direction.y * distance,
  };
  const contact = firstSegmentCircleIntersection(mover, end, target, goalRadius);
  const travel = contact === null ? distance : distance * contact;
  return {
    dx: route.entry.direction.x * travel,
    dy: route.entry.direction.y * travel,
    remainingPathLength: Math.max(0, remainingPathLength - travel),
  };
}


function stepClears(mover, movement, constraints, moverRadius, bounds) {
  const end = { x: mover.x + movement.dx, y: mover.y + movement.dy };
  return pointInsideBounds(end, moverRadius, bounds)
    && constraints.every((constraint) => segmentClears(mover, end, constraint));
}


function routeState(blocker, target, side) {
  return freezeAvoidance(blocker.kind === "unit" ? {
    blockerReferenceId: blocker.referenceId,
    targetReferenceId: target.referenceId,
    side,
  } : {
    blockerObstacleIndex: blocker.obstacleIndex,
    targetReferenceId: target.referenceId,
    side,
  });
}


function constraintForState(constraints, avoidance) {
  if (avoidance.blockerObstacleIndex !== undefined) {
    return constraints.find(({ kind, obstacleIndex }) => (
      kind === "map" && obstacleIndex === avoidance.blockerObstacleIndex
    ));
  }
  return constraints.find(({ kind, referenceId }) => (
    kind === "unit" && referenceId === avoidance.blockerReferenceId
  ));
}


function blockerIntersection(mover, goal, blocker) {
  return firstSegmentCircleIntersection(mover, goal, blocker, blocker.radius);
}


function routeCandidate(mover, target, blocker, side, constraints, mapInfo, budget) {
  const route = routeToContact(mover, target, blocker, side);
  if (route === null) return null;
  route.entryStart = mover;
  if (!routeClears(route, constraints, collisionRadius(mover), mapInfo.bounds)) return null;
  const movement = routeStep(mover, target, route, budget);
  if (!stepClears(mover, movement, constraints, collisionRadius(mover), mapInfo.bounds)) return null;
  return { route, movement };
}


function compareCandidates(left, right, mover) {
  if (left.route.pathLength < right.route.pathLength - EPSILON) return -1;
  if (right.route.pathLength < left.route.pathLength - EPSILON) return 1;
  const facingX = Math.cos(mover.facing);
  const facingY = Math.sin(mover.facing);
  const leftAlignment = facingX * left.route.entry.direction.x
    + facingY * left.route.entry.direction.y;
  const rightAlignment = facingX * right.route.entry.direction.x
    + facingY * right.route.entry.direction.y;
  if (leftAlignment > rightAlignment + EPSILON) return -1;
  if (rightAlignment > leftAlignment + EPSILON) return 1;
  return 0;
}


function selectRoute(mover, target, goal, constraints, mapInfo, budget) {
  const directBlockers = constraints
    .map((constraint) => ({
      constraint,
      intersection: blockerIntersection(mover, goal, constraint),
    }))
    .filter(({ intersection }) => intersection !== null)
    .sort((left, right) => (
      left.intersection - right.intersection
      || left.constraint.key.localeCompare(right.constraint.key)
    ));
  if (directBlockers.length === 0) return null;

  const directKeys = new Set(directBlockers.map(({ constraint }) => constraint.key));
  const blockers = [
    ...directBlockers.map(({ constraint }) => constraint),
    ...constraints
      .filter(({ key }) => !directKeys.has(key))
      .sort((left, right) => left.key.localeCompare(right.key)),
  ];
  const candidates = blockers.flatMap((blocker) => [-1, 1]
    .map((side) => routeCandidate(
      mover,
      target,
      blocker,
      side,
      constraints,
      mapInfo,
      budget,
    ))
    .filter((candidate) => candidate !== null));
  if (candidates.length === 0) return null;
  const ranked = candidates.sort((left, right) => compareCandidates(left, right, mover));
  return compareCandidates(ranked[0], ranked[1] ?? ranked[0], mover) === 0
    && ranked.length > 1
    ? null
    : ranked[0];
}


function normalizeMap(map, moverRadius) {
  if (map === undefined || map === null) return { bounds: null, obstacles: [] };
  const width = requireFinite(map.width, "map width");
  const height = requireFinite(map.height, "map height");
  if (width <= 0 || height <= 0) throw new RangeError("map dimensions must be positive");
  if (!Array.isArray(map.obstacles ?? [])) throw new TypeError("map obstacles must be an array");
  const obstacles = (map.obstacles ?? []).map((obstacle, obstacleIndex) => {
    const explicitRadius = obstacle.radius
      ?? obstacle.collisionRadius
      ?? obstacle.collision_radius;
    const radius = explicitRadius === undefined
      ? collisionRadius(obstacle)
      : requireFinite(explicitRadius, "map obstacle radius");
    if (radius <= 0) throw new RangeError("map obstacle radius must be positive");
    return {
      kind: "map",
      key: `map:${obstacleIndex.toString().padStart(10, "0")}`,
      obstacleIndex,
      x: requireFinite(obstacle.x, "map obstacle x"),
      y: requireFinite(obstacle.y, "map obstacle y"),
      radius: moverRadius + radius,
    };
  });
  return { bounds: { width, height }, obstacles };
}


function constraintsFor(mover, target, units, map) {
  const moverRadius = collisionRadius(mover);
  const mapInfo = normalizeMap(map, moverRadius);
  const bodies = units
    .filter((unit) => (
      unit.alive !== false
      && unit.referenceId !== mover.referenceId
      && unit.referenceId !== target.referenceId
      && unit.owner === mover.owner
    ))
    .map((unit) => ({
      kind: "unit",
      key: `unit:${unit.referenceId.toString().padStart(20, "0")}`,
      referenceId: unit.referenceId,
      x: unit.x,
      y: unit.y,
      radius: moverRadius + collisionRadius(unit),
    }));
  return { constraints: [...bodies, ...mapInfo.obstacles], mapInfo };
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


export function planLocalAvoidance(snapshot, proposals, map) {
  const { units, proposalByReference } = normalizeInputs(snapshot, proposals);
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  const nextUnits = [];
  const nextProposals = [];
  const routes = [];

  for (const mover of units) {
    const original = proposalByReference.get(mover.referenceId)
      ?? Object.freeze({ referenceId: mover.referenceId, dx: 0, dy: 0 });
    const originalBudget = Math.hypot(original.dx, original.dy);
    const target = byReference.get(mover.pursuitTargetId);
    const goal = target?.alive === false || !target ? null : contactGoal(mover, target);
    let avoidance = mover.avoidance;
    let selected = null;

    if (goal === null || goal.reached || mover.alive === false) {
      avoidance = null;
    } else {
      const speed = requireFinite(
        mover?.mechanics?.speed_tiles_per_second,
        "movement speed",
      );
      if (speed < 0) throw new RangeError("movement speed must be nonnegative");
      const budget = speed / TICKS_PER_SECOND;
      const { constraints, mapInfo } = constraintsFor(mover, target, units, map);
      if (avoidance !== null && avoidance.targetReferenceId === target.referenceId) {
        const blocker = constraintForState(constraints, avoidance);
        const blocksDirect = blocker !== undefined
          && blockerIntersection(mover, goal, blocker) !== null;
        if (blocksDirect) {
          if (originalBudget > EPSILON) {
            selected = routeCandidate(
              mover,
              target,
              blocker,
              avoidance.side,
              constraints,
              mapInfo,
              budget,
            );
          }
        }
        if (!blocksDirect) {
          avoidance = null;
        } else if (originalBudget > EPSILON && selected === null) {
          avoidance = null;
        }
      } else {
        avoidance = null;
      }
      if (selected === null && originalBudget > EPSILON) {
        selected = selectRoute(mover, target, goal, constraints, mapInfo, budget);
        if (selected !== null) {
          avoidance = routeState(selected.route.blocker, target, selected.route.side);
        }
      }
    }

    let nextProposal = original;
    if (selected !== null) {
      nextProposal = Object.freeze({
        referenceId: mover.referenceId,
        dx: selected.movement.dx,
        dy: selected.movement.dy,
      });
      routes.push(Object.freeze({
        referenceId: mover.referenceId,
        blockerReferenceId: selected.route.blocker.referenceId ?? null,
        blockerObstacleIndex: selected.route.blocker.obstacleIndex ?? null,
        targetReferenceId: target.referenceId,
        side: selected.route.side,
        remainingPathLength: Math.max(
          0,
          selected.movement.remainingPathLength,
        ),
      }));
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
