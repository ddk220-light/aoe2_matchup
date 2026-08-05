import { collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;
const MAX_CONSTRAINT_SWEEPS = 256;


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireReferenceId(value, name = "reference ID") {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


function pairKey(a, b) {
  return a.referenceId - b.referenceId;
}


function obstacleRadius(obstacle) {
  const value = obstacle.radius ?? obstacle.collisionRadius ?? obstacle.collision_radius;
  const radius = value === undefined
    ? collisionRadius(obstacle)
    : requireFinite(value, "obstacle radius");
  if (radius <= 0) throw new RangeError("obstacle radius must be positive");
  return radius;
}


function normalizeObstacles(map) {
  if (map?.obstacles === undefined) return [];
  if (!Array.isArray(map.obstacles)) throw new TypeError("map obstacles must be an array");
  return map.obstacles.map((obstacle, index) => {
    const x = requireFinite(obstacle?.x, "obstacle x");
    const y = requireFinite(obstacle?.y, "obstacle y");
    const radius = obstacleRadius(obstacle);
    const referenceId = obstacle.referenceId ?? obstacle.reference_id ?? obstacle.id ?? null;
    if (referenceId !== null) requireReferenceId(referenceId, "obstacle reference ID");
    return {
      x,
      y,
      radius,
      referenceId,
      sortKey: referenceId === null
        ? `~${x.toPrecision(17)},${y.toPrecision(17)},${radius.toPrecision(17)},${index}`
        : `${referenceId.toString().padStart(20, "0")}`,
      label: referenceId ?? `at (${x}, ${y})`,
    };
  }).sort((a, b) => a.sortKey.localeCompare(b.sortKey));
}


function normalizeBodies(snapshot, proposals) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!Array.isArray(proposals)) throw new TypeError("proposals must be an array");

  const byReference = new Map();
  for (const proposal of proposals) {
    const referenceId = requireReferenceId(proposal?.referenceId, "proposal reference ID");
    if (byReference.has(referenceId)) {
      throw new Error(`duplicate movement proposal for reference ${referenceId}`);
    }
    byReference.set(referenceId, {
      dx: requireFinite(proposal.dx, "proposal dx"),
      dy: requireFinite(proposal.dy, "proposal dy"),
    });
  }

  const seen = new Set();
  const bodies = snapshot.map((unit, inputIndex) => {
    const referenceId = requireReferenceId(unit?.referenceId);
    if (seen.has(referenceId)) throw new Error(`duplicate unit reference ${referenceId}`);
    seen.add(referenceId);
    const proposed = byReference.get(referenceId) ?? { dx: 0, dy: 0 };
    return {
      unit,
      inputIndex,
      referenceId,
      x: requireFinite(unit.x, "unit x"),
      y: requireFinite(unit.y, "unit y"),
      radius: collisionRadius(unit),
      dx: proposed.dx,
      dy: proposed.dy,
    };
  });
  for (const referenceId of byReference.keys()) {
    if (!seen.has(referenceId)) {
      throw new Error(`movement proposal references unknown unit ${referenceId}`);
    }
  }
  return bodies.sort(pairKey);
}


function normalizeBounds(map, bodies) {
  if (!map || typeof map !== "object") throw new TypeError("map is required");
  const width = requireFinite(map.width, "map width");
  const height = requireFinite(map.height, "map height");
  if (width <= 0 || height <= 0) throw new RangeError("map dimensions must be positive");
  for (const body of bodies) {
    if (width < body.radius * 2 || height < body.radius * 2) {
      throw new RangeError(`map cannot contain reference ${body.referenceId}`);
    }
  }
  return { width, height };
}


function validateStartingGeometry(bodies, obstacles, bounds) {
  for (const body of bodies) {
    if (
      body.x < body.radius - EPSILON ||
      body.x > bounds.width - body.radius + EPSILON ||
      body.y < body.radius - EPSILON ||
      body.y > bounds.height - body.radius + EPSILON
    ) {
      throw new RangeError(`reference ${body.referenceId} starts outside map bounds`);
    }
    for (const obstacle of obstacles) {
      const distance = Math.hypot(obstacle.x - body.x, obstacle.y - body.y);
      if (distance >= body.radius + obstacle.radius - EPSILON) continue;
      const kind = distance === 0 ? "exact overlap" : "starting overlap";
      throw new RangeError(
        `${kind} between reference ${body.referenceId} and obstacle ${obstacle.label}`,
      );
    }
  }
  for (let i = 0; i < bodies.length; i += 1) {
    for (let j = i + 1; j < bodies.length; j += 1) {
      const distance = Math.hypot(
        bodies[j].x - bodies[i].x,
        bodies[j].y - bodies[i].y,
      );
      if (distance >= bodies[i].radius + bodies[j].radius - EPSILON) continue;
      const kind = distance === 0 ? "exact overlap" : "starting overlap";
      throw new RangeError(
        `${kind} between references ${bodies[i].referenceId} and ${bodies[j].referenceId}`,
      );
    }
  }
}


function constrainBounds(body, bounds) {
  let correction = 0;
  const nextX = body.x + body.dx;
  const nextY = body.y + body.dy;
  const minX = body.radius;
  const maxX = bounds.width - body.radius;
  const minY = body.radius;
  const maxY = bounds.height - body.radius;
  if (nextX < minX) {
    correction = Math.max(correction, minX - nextX);
    body.dx = minX - body.x;
  } else if (nextX > maxX) {
    correction = Math.max(correction, nextX - maxX);
    body.dx = maxX - body.x;
  }
  if (nextY < minY) {
    correction = Math.max(correction, minY - nextY);
    body.dy = minY - body.y;
  } else if (nextY > maxY) {
    correction = Math.max(correction, nextY - maxY);
    body.dy = maxY - body.y;
  }
  return correction;
}


function constrainObstacle(body, obstacle) {
  const centerX = obstacle.x - body.x;
  const centerY = obstacle.y - body.y;
  const distance = Math.hypot(centerX, centerY);
  const gap = Math.max(0, distance - body.radius - obstacle.radius);
  const nx = centerX / distance;
  const ny = centerY / distance;
  const inward = body.dx * nx + body.dy * ny;
  if (inward <= gap + EPSILON) return 0;
  const correction = inward - gap;
  body.dx -= nx * correction;
  body.dy -= ny * correction;
  return correction;
}


function distributeEqualMassRemoval(excess, available) {
  const removed = available.map(() => 0);
  let remaining = excess;
  let contributors = available
    .map((amount, index) => ({ amount, index }))
    .filter(({ amount }) => amount > 0)
    .map(({ index }) => index);

  while (remaining > EPSILON && contributors.length > 0) {
    const equalShare = remaining / contributors.length;
    let removedThisPass = 0;
    const uncapped = [];
    for (const index of contributors) {
      const capacity = available[index] - removed[index];
      const amount = Math.min(equalShare, capacity);
      removed[index] += amount;
      removedThisPass += amount;
      if (capacity - amount > EPSILON) uncapped.push(index);
    }
    remaining -= removedThisPass;
    contributors = uncapped;
  }
  return removed;
}


function constrainPair(left, right) {
  const centerX = right.x - left.x;
  const centerY = right.y - left.y;
  const distance = Math.hypot(centerX, centerY);
  const gap = Math.max(0, distance - left.radius - right.radius);
  const nx = centerX / distance;
  const ny = centerY / distance;
  const leftNormal = left.dx * nx + left.dy * ny;
  const rightNormal = right.dx * nx + right.dy * ny;
  const closure = leftNormal - rightNormal;
  if (closure <= gap + EPSILON) return 0;

  const excess = closure - gap;
  const leftInward = Math.max(0, leftNormal);
  const rightInward = Math.max(0, -rightNormal);
  const [removeLeft, removeRight] = distributeEqualMassRemoval(
    excess,
    [leftInward, rightInward],
  );
  left.dx -= nx * removeLeft;
  left.dy -= ny * removeLeft;
  right.dx += nx * removeRight;
  right.dy += ny * removeRight;
  return Math.max(removeLeft, removeRight);
}


function resolveConstraints(bodies, obstacles, bounds) {
  for (let sweep = 0; sweep < MAX_CONSTRAINT_SWEEPS; sweep += 1) {
    let largestCorrection = 0;
    for (const body of bodies) {
      largestCorrection = Math.max(largestCorrection, constrainBounds(body, bounds));
      for (const obstacle of obstacles) {
        largestCorrection = Math.max(
          largestCorrection,
          constrainObstacle(body, obstacle),
        );
      }
    }
    for (let i = 0; i < bodies.length; i += 1) {
      for (let j = i + 1; j < bodies.length; j += 1) {
        largestCorrection = Math.max(
          largestCorrection,
          constrainPair(bodies[i], bodies[j]),
        );
      }
    }
    if (largestCorrection <= EPSILON) return;
  }

  for (const body of bodies) {
    body.dx = 0;
    body.dy = 0;
  }
}


function finalGeometryIsValid(bodies, obstacles, bounds) {
  for (const body of bodies) {
    const x = body.x + body.dx;
    const y = body.y + body.dy;
    if (
      x < body.radius - EPSILON ||
      x > bounds.width - body.radius + EPSILON ||
      y < body.radius - EPSILON ||
      y > bounds.height - body.radius + EPSILON
    ) return false;
    for (const obstacle of obstacles) {
      if (
        Math.hypot(obstacle.x - x, obstacle.y - y) <
        body.radius + obstacle.radius - EPSILON
      ) return false;
    }
  }
  for (let i = 0; i < bodies.length; i += 1) {
    for (let j = i + 1; j < bodies.length; j += 1) {
      if (
        Math.hypot(
          bodies[j].x + bodies[j].dx - bodies[i].x - bodies[i].dx,
          bodies[j].y + bodies[j].dy - bodies[i].y - bodies[i].dy,
        ) < bodies[i].radius + bodies[j].radius - EPSILON
      ) return false;
    }
  }
  return true;
}


export function resolveMovementProposals(snapshot, proposals, map) {
  const bodies = normalizeBodies(snapshot, proposals);
  const bounds = normalizeBounds(map, bodies);
  const obstacles = normalizeObstacles(map);
  validateStartingGeometry(bodies, obstacles, bounds);
  resolveConstraints(bodies, obstacles, bounds);
  if (!finalGeometryIsValid(bodies, obstacles, bounds)) {
    for (const body of bodies) {
      body.dx = 0;
      body.dy = 0;
    }
  }

  const nextByIndex = new Array(snapshot.length);
  for (const body of bodies) {
    nextByIndex[body.inputIndex] = Object.freeze({
      ...body.unit,
      x: body.x + body.dx,
      y: body.y + body.dy,
    });
  }
  return Object.freeze(nextByIndex);
}
