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


// Attack REACH is measured over the Genie OUTLINE box, not the collision box.
// The two coincide for the Champion (0.2/0.2) but not for the Paladin
// (0.25 collision / 0.4 outline), the Battle Elephant (0.25/0.5), or the
// Steppe Lancer (0.25/0.4), and the steppe tapes separate the two directly:
// stationary units land swings from collision-box gaps far beyond
// range + 0.1 (lancers at 1.33, an elephant at 0.48), yet across all 2158
// stationary swings in the three steppe archives the OUTLINE-box Chebyshev
// gap never exceeds range + 0.1 (envelope tops: 1.0850 of 1.1 for the
// range-1 lancer, -0.05 of 0.1 for the Champion). Euclidean is refuted by
// 30 diagonal-contact swings whose outline Euclidean gap exceeds the
// threshold while the Chebyshev gap is inside it.
export function outlineRadius(unit) {
  const outlineSize = unit?.mechanics?.outline_size_tiles;
  const x = requireFinite(outlineSize?.x, "outline size x");
  const y = requireFinite(outlineSize?.y, "outline size y");
  if (x <= 0 || y <= 0) {
    throw new RangeError("outline size must be positive");
  }
  if (x !== y) {
    throw new RangeError("deterministic reach requires equal outline x and y sizes");
  }
  return x;
}


export function outlineChebyshevGap(a, b) {
  const dx = Math.abs(requireFinite(b?.x, "target x") - requireFinite(a?.x, "unit x"));
  const dy = Math.abs(requireFinite(b?.y, "target y") - requireFinite(a?.y, "unit y"));
  return Math.max(dx, dy) - outlineRadius(a) - outlineRadius(b);
}


function isLive(unit) {
  return unit?.alive !== false;
}


function isEnemy(unit, candidate) {
  return candidate.referenceId !== unit.referenceId && candidate.owner !== unit.owner;
}


export function selectPursuitTarget(unit, snapshot, {
  targetLoadById = null,
  targetLoadPenaltyTiles = 0,
} = {}) {
  if (!Array.isArray(snapshot)) throw new TypeError("snapshot must be an array");
  if (!isLive(unit)) return null;
  if (targetLoadById !== null && !(targetLoadById instanceof Map)) {
    throw new TypeError("target load must be a Map");
  }
  if (!Number.isFinite(targetLoadPenaltyTiles) || targetLoadPenaltyTiles < 0) {
    throw new RangeError("target load penalty must be nonnegative and finite");
  }

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
  let bestScore = Infinity;
  for (const candidate of snapshot) {
    if (!isLive(candidate) || !isEnemy(unit, candidate)) continue;
    if (centerDistance(unit, candidate) > lineOfSight) continue;

    const gap = surfaceGap(unit, candidate);
    const targetLoad = targetLoadById?.get(candidate.referenceId) ?? 0;
    const score = gap + targetLoad * targetLoadPenaltyTiles;
    if (
      best === null ||
      score < bestScore ||
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
      (score === bestScore && candidate.referenceId < best.referenceId)
    ) {
      best = candidate;
      bestScore = score;
    }
  }
  return best;
}


export function attackReach(unit) {
  const range = requireFinite(unit?.mechanics?.attack_range_tiles, "attack range");
  if (range < 0) throw new RangeError("attack range must be nonnegative");
  return range + MELEE_CONTACT_TOLERANCE_TILES;
}


// Attack ELIGIBILITY: outline boxes, range + 0.1 (see outlineRadius). This is
// deliberately wider than the movement stop rule (collision boxes,
// max(range, 0.1) — isWithinStopRange in attacks.js): the tapes show units
// walking well inside their own attack envelope before they stop, and only
// blocked or already-stopped units swinging from the outer envelope. That
// split is what lets back-line Steppe Lancers fight over their front line.
//
// The distance METRIC splits on attack type. MELEE reach (range 0-1) is
// Chebyshev over the outline boxes — 30 diagonal-contact steppe swings sit at
// outline-Euclidean 1.235 > 1.1 while Chebyshev is inside. PROJECTILE reach
// is a Euclidean circle: across 6312 arbalester/skirmisher shots the maximum
// fire distance is 8.56 = range 8 + 0.1 + both 0.2 outlines with formations
// full of diagonal geometry — a Chebyshev rule at range 8 would show fire
// distances beyond 11, and none exist. (Box adjacency for arms' reach, a
// range circle for shots.)
export function isWithinReach(unit, target) {
  if (unit?.mechanics?.ranged) {
    const distance = centerDistance(unit, target);
    // Minimum range (dat type_50.min_range): the scorpion tapes bottom out
    // at fire distance 2.19 against its 2.0 -- center-to-center metric. A
    // target inside it cannot be attacked (and is not an engagement
    // candidate), which is what pushes the unit to prefer targets it can
    // actually shoot.
    const minRange = unit.mechanics.ranged.min_range_tiles ?? 0;
    if (minRange > 0 && distance < minRange - 1e-12) return false;
    const gap = distance - outlineRadius(unit) - outlineRadius(target);
    return gap <= attackReach(unit) + 1e-12;
  }
  return outlineChebyshevGap(unit, target) <= attackReach(unit) + 1e-12;
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
