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
      owner: unit.owner,
      stationary: proposed.dx === 0 && proposed.dy === 0,
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
      if (bodies[i].owner === bodies[j].owner) continue;
      const distance = Math.max(
        Math.abs(bodies[j].x - bodies[i].x),
        Math.abs(bodies[j].y - bodies[i].y),
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


function sweptDistanceFromOrigin(startX, startY, endX, endY) {
  const dx = endX - startX;
  const dy = endY - startY;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) return Math.hypot(startX, startY);
  const projection = Math.max(0, Math.min(1, -(
    startX * dx + startY * dy
  ) / lengthSquared));
  return Math.hypot(startX + projection * dx, startY + projection * dy);
}


function constrainObstacle(body, obstacle) {
  const startX = body.x - obstacle.x;
  const startY = body.y - obstacle.y;
  if (sweptDistanceFromOrigin(
    startX,
    startY,
    startX + body.dx,
    startY + body.dy,
  ) >= body.radius + obstacle.radius - EPSILON) return 0;
  const centerX = obstacle.x - body.x;
  const centerY = obstacle.y - body.y;
  const distance = Math.hypot(centerX, centerY);
  const gap = distance - body.radius - obstacle.radius;
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


// Genie unit obstruction is an axis-aligned box, not a disc: two units are clear
// of each other as soon as EITHER axis separates them by the summed half-extents.
// The authorized tapes show this directly -- enemy Champions bottom out at a
// Chebyshev separation of exactly 0.4000 tiles (0.2 + 0.2) whichever axis they
// meet on, which a Euclidean radius cannot produce. Resolution is the standard
// minimum-translation push along the axis that is closest to clearing.
function constrainPair(left, right) {
  // Ally separation only binds when BOTH units are trying to move. A unit that
  // has stopped -- because it reached attack range, or because its swing has it
  // rooted for the animation -- offers no resistance, so an ally walking into it
  // settles inside its box and stays there. Measured across all 15 tapes: ally
  // pairs breach the 0.4000-tile box in 1.9% of frames where both are moving,
  // 6.8% where one walks into a stopped ally (the deepest overlaps, down to
  // 0.2352), and 15.3% where both have stopped and nothing separates them again.
  // Enemy pairs breach it in none.
  if (left.owner === right.owner && (left.stationary || right.stationary)) return 0;
  const extent = left.radius + right.radius;
  const centerX = right.x - left.x;
  const centerY = right.y - left.y;
  if (Math.max(
    Math.abs(centerX + right.dx - left.dx),
    Math.abs(centerY + right.dy - left.dy),
  ) >= extent - EPSILON) return 0;

  const alongX = Math.abs(centerX) >= Math.abs(centerY);
  const axisCenter = alongX ? centerX : centerY;
  const sign = axisCenter < 0 ? -1 : 1;
  const nx = alongX ? sign : 0;
  const ny = alongX ? 0 : sign;
  const gap = Math.abs(axisCenter) - extent;
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
  let finalCorrection = Infinity;
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
    if (
      largestCorrection <= EPSILON
      && finalGeometryIsValid(bodies, obstacles, bounds)
    ) return;
    finalCorrection = largestCorrection;
  }

  // Ally separation is a soft constraint: a crowd can stay mutually unsatisfied
  // for as long as it likes, exactly as the tapes show. Spending the whole sweep
  // budget is therefore not an error provided the hard invariants -- enemy
  // separation, map bounds and static obstacles -- all hold.
  if (finalGeometryIsValid(bodies, obstacles, bounds)) return;

  throw new Error(
    `collision constraints did not converge after ${MAX_CONSTRAINT_SWEEPS} sweeps `
    + `(last correction ${finalCorrection}; `
    + `${finalGeometryViolation(bodies, obstacles, bounds) ?? "geometry valid"})`,
  );
}


function finalGeometryViolation(bodies, obstacles, bounds) {
  for (const body of bodies) {
    const x = body.x + body.dx;
    const y = body.y + body.dy;
    if (
      x < body.radius - EPSILON ||
      x > bounds.width - body.radius + EPSILON ||
      y < body.radius - EPSILON ||
      y > bounds.height - body.radius + EPSILON
    ) return `reference ${body.referenceId} outside bounds`;
    for (const obstacle of obstacles) {
      const gap = Math.hypot(obstacle.x - x, obstacle.y - y)
        - body.radius - obstacle.radius;
      if (gap < -EPSILON) {
        return `reference ${body.referenceId} overlaps obstacle ${obstacle.label} by ${-gap}`;
      }
    }
  }
  for (let i = 0; i < bodies.length; i += 1) {
    for (let j = i + 1; j < bodies.length; j += 1) {
      // Enemy separation is a hard invariant; ally separation is best effort.
      // Measured over all 15 tapes: enemy Champions never breach 0.4000 tiles of
      // Chebyshev separation, while ally pairs sit below it in 1.9% of frames
      // where both are moving, 6.8% where one is moving into a stopped ally, and
      // 15.3% where both have stopped -- crowding squeezes allies together and
      // nothing pushes them back apart once they stand still.
      if (bodies[i].owner === bodies[j].owner) continue;
      const gap = Math.max(
        Math.abs(bodies[j].x + bodies[j].dx - bodies[i].x - bodies[i].dx),
        Math.abs(bodies[j].y + bodies[j].dy - bodies[i].y - bodies[i].dy),
      ) - bodies[i].radius - bodies[j].radius;
      if (gap < -EPSILON) {
        return `references ${bodies[i].referenceId} and ${bodies[j].referenceId} `
          + `overlap by ${-gap}`;
      }
    }
  }
  return null;
}


function finalGeometryIsValid(bodies, obstacles, bounds) {
  return finalGeometryViolation(bodies, obstacles, bounds) === null;
}


function sweptContactFraction(leftBefore, rightBefore, leftAfter, rightAfter) {
  const startX = rightBefore.x - leftBefore.x;
  const startY = rightBefore.y - leftBefore.y;
  const relativeX = (rightAfter.x - rightBefore.x) - (leftAfter.x - leftBefore.x);
  const relativeY = (rightAfter.y - rightBefore.y) - (leftAfter.y - leftBefore.y);
  const radius = collisionRadius(leftBefore) + collisionRadius(rightBefore);
  const c = startX * startX + startY * startY - radius * radius;
  const finalGap = Math.hypot(
    rightAfter.x - leftAfter.x,
    rightAfter.y - leftAfter.y,
  ) - radius;
  if (c <= EPSILON) return finalGap <= EPSILON ? 0 : null;
  const a = relativeX * relativeX + relativeY * relativeY;
  if (a === 0) return null;
  const b = 2 * (startX * relativeX + startY * relativeY);
  const discriminant = b * b - 4 * a * c;
  if (discriminant < -EPSILON) return null;
  const root = Math.sqrt(Math.max(0, discriminant));
  const entering = (-b - root) / (2 * a);
  return entering >= -EPSILON && entering <= 1 + EPSILON
    ? Math.max(0, Math.min(1, entering))
    : null;
}


export function queryEnemyContactManifold(beforeSnapshot, afterSnapshot) {
  if (!Array.isArray(beforeSnapshot) || !Array.isArray(afterSnapshot)) {
    throw new TypeError("contact snapshots must be arrays");
  }
  const before = [...beforeSnapshot].sort(pairKey);
  const afterByReference = new Map();
  for (const unit of afterSnapshot) {
    requireReferenceId(unit?.referenceId);
    if (afterByReference.has(unit.referenceId)) {
      throw new Error(`duplicate unit reference ${unit.referenceId}`);
    }
    afterByReference.set(unit.referenceId, unit);
  }
  if (afterByReference.size !== before.length) {
    throw new Error("contact snapshots must contain the same units");
  }

  const contacts = [];
  for (let leftIndex = 0; leftIndex < before.length; leftIndex += 1) {
    const leftBefore = before[leftIndex];
    const leftAfter = afterByReference.get(leftBefore.referenceId);
    if (!leftAfter) throw new Error(`missing final unit ${leftBefore.referenceId}`);
    for (let rightIndex = leftIndex + 1; rightIndex < before.length; rightIndex += 1) {
      const rightBefore = before[rightIndex];
      const rightAfter = afterByReference.get(rightBefore.referenceId);
      if (!rightAfter) throw new Error(`missing final unit ${rightBefore.referenceId}`);
      if (
        leftBefore.alive === false
        || rightBefore.alive === false
        || leftAfter.alive === false
        || rightAfter.alive === false
        || leftBefore.owner === rightBefore.owner
      ) continue;
      const finalSurfaceGap = Math.hypot(
        rightAfter.x - leftAfter.x,
        rightAfter.y - leftAfter.y,
      ) - collisionRadius(leftAfter) - collisionRadius(rightAfter);
      let sweptToi = sweptContactFraction(
        leftBefore,
        rightBefore,
        leftAfter,
        rightAfter,
      );
      if (sweptToi === null && finalSurfaceGap <= EPSILON) sweptToi = 1;
      if (sweptToi === null) continue;
      contacts.push(Object.freeze({
        leftId: leftBefore.referenceId,
        rightId: rightBefore.referenceId,
        sweptToi,
        finalSurfaceGap,
      }));
    }
  }
  contacts.sort((left, right) => (
    left.sweptToi - right.sweptToi
    || left.finalSurfaceGap - right.finalSurfaceGap
    || left.leftId - right.leftId
    || left.rightId - right.rightId
  ));
  return Object.freeze(contacts);
}


export function resolveMovementProposals(snapshot, proposals, map) {
  const bodies = normalizeBodies(snapshot, proposals);
  const bounds = normalizeBounds(map, bodies);
  const obstacles = normalizeObstacles(map);
  validateStartingGeometry(bodies, obstacles, bounds);
  resolveConstraints(bodies, obstacles, bounds);
  if (!finalGeometryIsValid(bodies, obstacles, bounds)) {
    throw new Error("collision constraints produced invalid final geometry");
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
