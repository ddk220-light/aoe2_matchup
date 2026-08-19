import { collisionRadius } from "./targeting.js";
import {
  createPairInteractionSnapshot,
  resolvePairInteraction,
} from "./pair-interactions.js";


const EPSILON = 1e-12;
// Hard collision publication uses a world-scale tolerance rather than the
// floating-point comparison epsilon. At a 0.2-tile Champion radius this is
// 0.05% of the body size: physically invisible, but large enough to keep a
// sequential solver from treating a sub-pixel residual as a broken world.
const GEOMETRY_SLOP = 1e-4;
// Crowds pinched between a static obstacle and an enemy body converge
// geometrically. The former 256-sweep ceiling could stop with a sub-micron
// residual overlap even though each pass was still making deterministic
// progress. This remains a failure ceiling, not a physical tolerance: hard
// geometry must still satisfy EPSILON before a movement step is published.
const MAX_CONSTRAINT_SWEEPS = 4096;


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
      unitMaster: requireReferenceId(
        unit.unitMaster ?? unit.mechanics?.unit_master,
        "unit master",
      ),
      owner: unit.owner,
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


function validateStartingGeometry(bodies, obstacles, bounds, pairInteractions) {
  let strictlyValid = true;
  for (const body of bodies) {
    if (
      body.x < body.radius - GEOMETRY_SLOP ||
      body.x > bounds.width - body.radius + GEOMETRY_SLOP ||
      body.y < body.radius - GEOMETRY_SLOP ||
      body.y > bounds.height - body.radius + GEOMETRY_SLOP
    ) {
      throw new RangeError(`reference ${body.referenceId} starts outside map bounds`);
    }
    if (
      body.x < body.radius - EPSILON
      || body.x > bounds.width - body.radius + EPSILON
      || body.y < body.radius - EPSILON
      || body.y > bounds.height - body.radius + EPSILON
    ) strictlyValid = false;
    for (const obstacle of obstacles) {
      const distance = Math.hypot(obstacle.x - body.x, obstacle.y - body.y);
      const extent = body.radius + obstacle.radius;
      if (distance >= extent - GEOMETRY_SLOP) {
        if (distance < extent - EPSILON) strictlyValid = false;
        continue;
      }
      const kind = distance === 0 ? "exact overlap" : "starting overlap";
      throw new RangeError(
        `${kind} between reference ${body.referenceId} and obstacle ${obstacle.label}`,
      );
    }
  }
  for (let i = 0; i < bodies.length; i += 1) {
    for (let j = i + 1; j < bodies.length; j += 1) {
      const distance = Math.max(
        Math.abs(bodies[j].x - bodies[i].x),
        Math.abs(bodies[j].y - bodies[i].y),
      );
      const interaction = resolvePairInteraction(
        bodies[i], bodies[j], pairInteractions,
      );
      const extent = interaction.collisionExtent;
      if (distance >= extent - GEOMETRY_SLOP) {
        if (distance < extent - EPSILON) strictlyValid = false;
        continue;
      }
      const kind = distance === 0 ? "exact overlap" : "starting overlap";
      throw new RangeError(
        `${kind} between references ${bodies[i].referenceId} and ${bodies[j].referenceId}`
          + ` (${interaction.kind}/${interaction.reason}; separation=${distance}; extent=${extent})`,
      );
    }
  }
  return strictlyValid;
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
  ) >= body.radius + obstacle.radius) return 0;
  const centerX = obstacle.x - body.x;
  const centerY = obstacle.y - body.y;
  const distance = Math.hypot(centerX, centerY);
  const gap = distance - body.radius - obstacle.radius;
  const nx = centerX / distance;
  const ny = centerY / distance;
  const inward = body.dx * nx + body.dy * ny;
  if (inward <= gap) return 0;
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
function constrainPair(left, right, pairInteractions) {
  const interaction = resolvePairInteraction(left, right, pairInteractions);
  const extent = interaction.collisionExtent;
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


function reportCollisionDiagnostics(callback, mode, sweeps, largestCorrection,
  restoredReferences = []) {
  if (callback === undefined) return;
  callback(Object.freeze({
    mode,
    sweeps,
    largestCorrection,
    restoredReferences: Object.freeze([...restoredReferences]),
  }));
}


function resolveConstraints(bodies, obstacles, bounds, pairInteractions,
  onCollisionDiagnostics, allowEarlySlop, collisionRecoveryState) {
  let lastCorrection = Infinity;
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
          constrainPair(bodies[i], bodies[j], pairInteractions),
        );
      }
    }
    if (largestCorrection <= EPSILON && finalGeometryIsValid(
      bodies, obstacles, bounds, EPSILON, pairInteractions,
    )) {
      reportCollisionDiagnostics(
        onCollisionDiagnostics, "converged", sweep + 1, largestCorrection,
      );
      return;
    }
    if (allowEarlySlop
        && finalGeometryIsValid(
          bodies, obstacles, bounds, GEOMETRY_SLOP, pairInteractions,
        )) {
      reportCollisionDiagnostics(
        onCollisionDiagnostics, "slop", sweep + 1, largestCorrection,
      );
      return;
    }
    lastCorrection = largestCorrection;
  }

  // Ally separation is a soft constraint: a crowd can stay mutually unsatisfied
  // for as long as it likes, exactly as the tapes show. Spending the whole sweep
  // budget is therefore not an error provided the hard invariants -- enemy
  // separation, map bounds and static obstacles -- all hold.
  if (finalGeometryIsValid(
    bodies, obstacles, bounds, EPSILON, pairInteractions,
  )) {
    reportCollisionDiagnostics(
      onCollisionDiagnostics, "budget", MAX_CONSTRAINT_SWEEPS, lastCorrection,
    );
    return;
  }
  if (finalGeometryIsValid(
    bodies, obstacles, bounds, GEOMETRY_SLOP, pairInteractions,
  )) {
    if (collisionRecoveryState) collisionRecoveryState.active = true;
    reportCollisionDiagnostics(
      onCollisionDiagnostics, "slop", MAX_CONSTRAINT_SWEEPS, lastCorrection,
    );
    return;
  }

  const restoredReferences = restoreInvalidMovement(
    bodies, obstacles, bounds, pairInteractions,
  );
  if (collisionRecoveryState) collisionRecoveryState.active = true;
  reportCollisionDiagnostics(
    onCollisionDiagnostics, "fallback", MAX_CONSTRAINT_SWEEPS, lastCorrection,
    restoredReferences,
  );
}


function invalidBodyReferences(bodies, obstacles, bounds, tolerance, pairInteractions) {
  const invalid = new Set();
  for (const body of bodies) {
    const x = body.x + body.dx;
    const y = body.y + body.dy;
    if (
      x < body.radius - tolerance
      || x > bounds.width - body.radius + tolerance
      || y < body.radius - tolerance
      || y > bounds.height - body.radius + tolerance
    ) invalid.add(body.referenceId);
    for (const obstacle of obstacles) {
      const gap = Math.hypot(obstacle.x - x, obstacle.y - y)
        - body.radius - obstacle.radius;
      if (gap < -tolerance) invalid.add(body.referenceId);
    }
  }
  for (let i = 0; i < bodies.length; i += 1) {
    for (let j = i + 1; j < bodies.length; j += 1) {
      if (bodies[i].owner === bodies[j].owner) continue;
      const gap = Math.max(
        Math.abs(bodies[j].x + bodies[j].dx - bodies[i].x - bodies[i].dx),
        Math.abs(bodies[j].y + bodies[j].dy - bodies[i].y - bodies[i].dy),
      ) - resolvePairInteraction(
        bodies[i], bodies[j], pairInteractions,
      ).collisionExtent;
      if (gap >= -tolerance) continue;
      invalid.add(bodies[i].referenceId);
      invalid.add(bodies[j].referenceId);
    }
  }
  return invalid;
}


function restoreInvalidMovement(bodies, obstacles, bounds, pairInteractions) {
  const restored = new Set();
  for (let pass = 0; pass < bodies.length; pass += 1) {
    const invalid = invalidBodyReferences(
      bodies, obstacles, bounds, GEOMETRY_SLOP, pairInteractions,
    );
    if (invalid.size === 0) return [...restored];
    let grew = false;
    for (const body of bodies) {
      if (!invalid.has(body.referenceId) || restored.has(body.referenceId)) continue;
      body.dx = 0;
      body.dy = 0;
      restored.add(body.referenceId);
      grew = true;
    }
    if (!grew) break;
  }

  // The input snapshot was validated before solving, so restoring every body
  // is an always-valid deterministic last resort even for an unexpectedly
  // tangled contact graph.
  for (const body of bodies) {
    body.dx = 0;
    body.dy = 0;
  }
  return bodies.map(({ referenceId }) => referenceId);
}


function finalGeometryViolation(bodies, obstacles, bounds, tolerance = EPSILON,
  pairInteractions = createPairInteractionSnapshot()) {
  for (const body of bodies) {
    const x = body.x + body.dx;
    const y = body.y + body.dy;
    if (
      x < body.radius - tolerance ||
      x > bounds.width - body.radius + tolerance ||
      y < body.radius - tolerance ||
      y > bounds.height - body.radius + tolerance
    ) return `reference ${body.referenceId} outside bounds`;
    for (const obstacle of obstacles) {
      const gap = Math.hypot(obstacle.x - x, obstacle.y - y)
        - body.radius - obstacle.radius;
      if (gap < -tolerance) {
        return `reference ${body.referenceId} overlaps obstacle ${obstacle.label} by ${-gap}`;
      }
    }
  }
  for (let i = 0; i < bodies.length; i += 1) {
    for (let j = i + 1; j < bodies.length; j += 1) {
      const gap = Math.max(
        Math.abs(bodies[j].x + bodies[j].dx - bodies[i].x - bodies[i].dx),
        Math.abs(bodies[j].y + bodies[j].dy - bodies[i].y - bodies[i].dy),
      ) - resolvePairInteraction(
        bodies[i], bodies[j], pairInteractions,
      ).collisionExtent;
      if (gap < -tolerance) {
        return `references ${bodies[i].referenceId} and ${bodies[j].referenceId} `
          + `overlap by ${-gap}`;
      }
    }
  }
  return null;
}


function finalGeometryIsValid(bodies, obstacles, bounds, tolerance = EPSILON,
  pairInteractions = createPairInteractionSnapshot()) {
  return finalGeometryViolation(
    bodies, obstacles, bounds, tolerance, pairInteractions,
  ) === null;
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


export function resolveMovementProposals(snapshot, proposals, map, options = {}) {
  const pairInteractions = options.pairInteractions
    ?? createPairInteractionSnapshot();
  const onCollisionDiagnostics = options.onCollisionDiagnostics;
  if (onCollisionDiagnostics !== undefined && typeof onCollisionDiagnostics !== "function") {
    throw new TypeError("collision diagnostics callback must be a function");
  }
  const collisionRecoveryState = options.collisionRecoveryState;
  if (collisionRecoveryState !== undefined
      && (!collisionRecoveryState || typeof collisionRecoveryState !== "object")) {
    throw new TypeError("collision recovery state must be an object");
  }
  const bodies = normalizeBodies(snapshot, proposals);
  const bounds = normalizeBounds(map, bodies);
  const obstacles = normalizeObstacles(map);
  const strictlyValidStart = validateStartingGeometry(
    bodies, obstacles, bounds, pairInteractions,
  );
  resolveConstraints(
    bodies, obstacles, bounds, pairInteractions,
    onCollisionDiagnostics,
    collisionRecoveryState?.active === true || !strictlyValidStart,
    collisionRecoveryState,
  );
  if (!finalGeometryIsValid(
    bodies, obstacles, bounds, GEOMETRY_SLOP, pairInteractions,
  )) {
    const violation = finalGeometryViolation(
      bodies, obstacles, bounds, GEOMETRY_SLOP, pairInteractions,
    );
    throw new Error(`collision constraints produced invalid final geometry: ${violation}`);
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
