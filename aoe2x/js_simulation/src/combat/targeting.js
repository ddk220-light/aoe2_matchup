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


// AoE2:DE lets a unit shrink its own obstruction when it bumps a FRIENDLY unit,
// so a crowd can close up instead of deadlocking. The shrink factor is a real
// per-unit dat field (DeadFish.min_collision_size_multiplier = 0.8 here), and
// the tapes show its three plateaus exactly: ally pairs pile up at 0.40 tiles
// (0.20 + 0.20, neither shrunk, n=9954), then 0.36 (0.16 + 0.20, one shrunk,
// n=2057), then 0.32 (0.16 + 0.16, both shrunk, n=195). Only 0.1% of samples
// fall below 0.32. Enemies never shrink -- they hold 0.40 without exception.
export function allyCollisionRadius(unit) {
  const multiplier = unit?.mechanics?.min_collision_size_multiplier;
  if (!Number.isFinite(multiplier) || multiplier <= 0 || multiplier > 1) {
    throw new RangeError("min collision size multiplier must be within (0, 1]");
  }
  return collisionRadius(unit) * multiplier;
}


// Genie obstruction is an axis-aligned box, not a circle. The authorized tapes
// confirm it directly: across all 15 recordings enemy Champions never close
// below a Chebyshev separation of 0.4000 tiles (= 0.2 + 0.2 half-extents), and
// they reach that separation on whichever axis they approach from, which a
// Euclidean radius cannot produce.
export function chebyshevGap(a, b) {
  const dx = Math.abs(requireFinite(b?.x, "target x") - requireFinite(a?.x, "unit x"));
  const dy = Math.abs(requireFinite(b?.y, "target y") - requireFinite(a?.y, "unit y"));
  return Math.max(dx, dy) - collisionRadius(a) - collisionRadius(b);
}


// Units do not act on the frame their order is issued. Pooled over the Champion
// and Paladin recordings (n = 162 acquisitions) the first target is acquired
// 0.952 s to 1.708 s after the start command, and the two units agree on the
// endpoints to within 4 ms (Champion 0.952/1.706, Paladin 0.956/1.708; stdev
// 0.221 vs 0.216). That makes this an ENGINE reaction lag, not a unit stat.
export const ACQUISITION_DELAY_SECONDS = Object.freeze({ min: 0.952, max: 1.708 });


// Within one fight the per-unit delays are the ORDER STATISTICS of that range,
// not one shared value: a 9-unit fight spans 0.968-1.684 s. Modelling every
// unit at the median collapsed a ~0.7 s stagger to zero, and because a fight
// ends when the LAST unit finishes, that biased every recorded fight early --
// 0.10-0.32 s in uncrowded ratios, up to 1.24 s in crowded ones, early in 9 of
// 9 Champion-vs-Paladin ratios and never late.
//
// The expected i-th of n uniforms is min + i/(n+1) * (max - min). There are NO
// free parameters here: the endpoints are measured and the rest is counting
// units. Checked against 53 real acquisitions across both pairs, mean error
// +0.032 s, mean absolute error 0.058 s.
//
// This is deterministic, and is NOT the per-unit random jitter rejected
// earlier. The one convention is WHICH unit takes which rank: the engine rolls
// for that and a deterministic simulator cannot reproduce the roll, so rank
// follows reference ID. The stagger is measured; the assignment is a choice.
export function acquisitionDelaySeconds(rank, count) {
  if (!Number.isSafeInteger(count) || count < 1) {
    throw new RangeError("acquisition count must be a positive safe integer");
  }
  if (!Number.isSafeInteger(rank) || rank < 0 || rank >= count) {
    throw new RangeError("acquisition rank must be within the roster");
  }
  const { min, max } = ACQUISITION_DELAY_SECONDS;
  return min + ((rank + 1) / (count + 1)) * (max - min);
}


// Melee units swing from slightly outside box contact. Measured across the
// authorized tapes: the attack envelope tops out at a Chebyshev separation of
// 0.4999 tiles against a 0.4000 box contact, i.e. 0.1 tiles of reach beyond
// touching. This is MEASURED, not sourced to a Genie field.
export const MELEE_CONTACT_TOLERANCE_TILES = 0.1;


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
      // Ties are effectively unreachable and this branch is near-dead code:
      // units acquire on a stagger, so by the time any unit picks a target the
      // others have been moving for a while and exact ties have dissolved.
      // Measured in champion_vs_paladin 6v3: spawn positions put champions 1628
      // and 1633 at an EXACT tie from paladin 1701 (2.2361 Euclidean, 2.0000
      // Chebyshev), but at 1701's actual acquisition moment the tape separates
      // them 2.236 vs 2.019 and the sim 1.560 vs 1.957. Flipping this to
      // highest-ID changed nothing anywhere, in either direction.
      //
      // What decides the target is ACQUISITION ORDER, not this tie-break.
      (gap === bestGap && candidate.referenceId < best.referenceId)
    ) {
      best = candidate;
      bestGap = gap;
    }
  }
  return best;
}


export function attackReach(unit) {
  const range = requireFinite(unit?.mechanics?.attack_range_tiles, "attack range");
  if (range < 0) throw new RangeError("attack range must be nonnegative");
  return range + MELEE_CONTACT_TOLERANCE_TILES;
}


export function isWithinReach(unit, target) {
  return chebyshevGap(unit, target) <= attackReach(unit) + 1e-12;
}


// A unit engages whatever enemy is inside its attack envelope, not whatever
// enemy its body happens to collide with: the tapes show units stopping and
// swinging from ~0.1 tiles outside box contact, so physical overlap is never
// required and usually never happens. Where the sweep solver did produce a
// contact for a pair it is preserved for ordering and reporting.
export function selectEngagementTarget(unit, snapshot, contacts) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!Array.isArray(contacts)) throw new TypeError("contacts must be an array");
  if (!isLive(unit)) return Object.freeze({ target: null, contact: null });
  const byReference = new Map(snapshot.map((candidate) => [candidate.referenceId, candidate]));
  const contactFor = (targetId) => contacts.find(({ leftId, rightId }) => (
    (leftId === unit.referenceId && rightId === targetId)
    || (rightId === unit.referenceId && leftId === targetId)
  )) ?? null;

  if (unit.engagedTargetId !== null && unit.engagedTargetId !== undefined) {
    const engaged = byReference.get(unit.engagedTargetId);
    if (engaged && isLive(engaged) && isEnemy(unit, engaged) && isWithinReach(unit, engaged)) {
      return Object.freeze({ target: engaged, contact: contactFor(engaged.referenceId) });
    }
  }

  const candidates = snapshot
    .filter((candidate) => (
      isLive(candidate) && isEnemy(unit, candidate) && isWithinReach(unit, candidate)
    ))
    .map((target) => ({
      target,
      contact: contactFor(target.referenceId),
      gap: chebyshevGap(unit, target),
    }))
    .sort((left, right) => (
      (left.contact?.sweptToi ?? Infinity) - (right.contact?.sweptToi ?? Infinity)
      || left.gap - right.gap
      || left.target.referenceId - right.target.referenceId
    ));
  if (candidates.length === 0) return Object.freeze({ target: null, contact: null });
  const { target, contact } = candidates[0];
  return Object.freeze({ target, contact });
}
