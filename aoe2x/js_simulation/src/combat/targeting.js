function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function centerDistance(a, b) {
  const dx = requireFinite(b?.x, "target x") - requireFinite(a?.x, "unit x");
  const dy = requireFinite(b?.y, "target y") - requireFinite(a?.y, "unit y");
  return Math.hypot(dx, dy);
}


export function collisionRadius(unit) {
  const collisionSize = unit?.mechanics?.collision_size_tiles;
  const x = requireFinite(collisionSize?.x, "collision size x");
  const y = requireFinite(collisionSize?.y, "collision size y");
  if (x <= 0 || y <= 0) {
    throw new RangeError("collision size must be positive");
  }
  if (x !== y) {
    throw new RangeError("deterministic circular collision requires equal x and y sizes");
  }
  return x;
}


export function surfaceGap(a, b) {
  return centerDistance(a, b) - collisionRadius(a) - collisionRadius(b);
}


function isLive(unit) {
  return unit?.alive !== false;
}


function isEnemy(unit, candidate) {
  return candidate.referenceId !== unit.referenceId && candidate.owner !== unit.owner;
}


export function selectTarget(unit, snapshot) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!isLive(unit)) return null;

  if (unit.targetId !== null && unit.targetId !== undefined) {
    const locked = snapshot.find(({ referenceId }) => referenceId === unit.targetId);
    if (locked && isLive(locked)) {
      if (!isEnemy(unit, locked)) {
        throw new Error(`unit ${unit.referenceId} has a live friendly target`);
      }
      return locked;
    }
  }

  const lineOfSight = requireFinite(
    unit?.mechanics?.line_of_sight_tiles,
    "line of sight",
  );
  if (lineOfSight < 0) throw new RangeError("line of sight must be nonnegative");

  let best = null;
  let bestGap = Infinity;
  for (const candidate of snapshot) {
    if (!isLive(candidate) || !isEnemy(unit, candidate)) continue;
    if (centerDistance(unit, candidate) > lineOfSight) continue;

    const gap = surfaceGap(unit, candidate);
    if (
      best === null ||
      gap < bestGap ||
      (gap === bestGap && candidate.referenceId < best.referenceId)
    ) {
      best = candidate;
      bestGap = gap;
    }
  }
  return best;
}
