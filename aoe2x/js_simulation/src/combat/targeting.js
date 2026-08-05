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


export function selectPursuitTarget(unit, snapshot) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!isLive(unit)) return null;

  if (unit.pursuitTargetId !== null && unit.pursuitTargetId !== undefined) {
    const locked = snapshot.find(({ referenceId }) => (
      referenceId === unit.pursuitTargetId
    ));
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


export function selectEngagementTarget(unit, snapshot, contacts) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!Array.isArray(contacts)) throw new TypeError("contacts must be an array");
  if (!isLive(unit)) return Object.freeze({ target: null, contact: null });
  const byReference = new Map(snapshot.map((candidate) => [candidate.referenceId, candidate]));
  if (unit.engagedTargetId !== null && unit.engagedTargetId !== undefined) {
    const engaged = byReference.get(unit.engagedTargetId);
    const range = requireFinite(unit?.mechanics?.attack_range_tiles, "attack range");
    if (range < 0) throw new RangeError("attack range must be nonnegative");
    if (
      engaged
      && isLive(engaged)
      && isEnemy(unit, engaged)
      && surfaceGap(unit, engaged) <= range + 1e-12
    ) {
      const contact = contacts.find(({ leftId, rightId }) => (
        (leftId === unit.referenceId && rightId === engaged.referenceId)
        || (rightId === unit.referenceId && leftId === engaged.referenceId)
      )) ?? null;
      return Object.freeze({ target: engaged, contact });
    }
  }

  const candidates = contacts
    .map((contact) => {
      let targetId = null;
      if (contact.leftId === unit.referenceId) targetId = contact.rightId;
      if (contact.rightId === unit.referenceId) targetId = contact.leftId;
      if (targetId === null) return null;
      const target = byReference.get(targetId);
      if (!target || !isLive(target) || !isEnemy(unit, target)) return null;
      return { target, contact };
    })
    .filter((candidate) => candidate !== null)
    .sort((left, right) => (
      left.contact.sweptToi - right.contact.sweptToi
      || left.contact.finalSurfaceGap - right.contact.finalSurfaceGap
      || left.target.referenceId - right.target.referenceId
    ));
  if (candidates.length === 0) return Object.freeze({ target: null, contact: null });
  return Object.freeze(candidates[0]);
}
