import { collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;
export const SIEGE_DEBRIS_SCATTER_RADIUS_TILES = 1.0;


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function compareReference(left, right) {
  const a = left?.referenceId;
  const b = right?.referenceId;
  if (a === b) return 0;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a) < String(b) ? -1 : 1;
}


// A failed accuracy roll displaces the aim point by the DAT dispersion. The
// radial draw is uniform in radius (not uniform in area): this is the launch
// geometry measured for Hand Cannoneer projectiles in the live tapes.
export function displacedAimPoint({
  aimX,
  aimY,
  dispersionTiles,
  radialRoll,
  angleRoll,
}) {
  requireFinite(aimX, "aim x");
  requireFinite(aimY, "aim y");
  const dispersion = requireFinite(dispersionTiles, "dispersion");
  const radiusDraw = requireFinite(radialRoll, "radial roll");
  const angleDraw = requireFinite(angleRoll, "angle roll");
  if (dispersion < 0) throw new RangeError("dispersion must be nonnegative");
  if (radiusDraw < 0 || radiusDraw >= 1 || angleDraw < 0 || angleDraw >= 1) {
    throw new RangeError("projectile rolls must be in [0, 1)");
  }
  const radius = dispersion * radiusDraw;
  const angle = angleDraw * 2 * Math.PI;
  return Object.freeze({
    x: aimX + radius * Math.cos(angle),
    y: aimY + radius * Math.sin(angle),
  });
}


// Landing-only projectile collision. The projectile's own DAT half width is
// part of the overlap window. If several bodies contain the landing point,
// the closest one wins; reference ID is the stable tie-breaker.
export function selectProjectileLandingVictim(candidates, x, y, halfWidth) {
  if (!Array.isArray(candidates)) throw new TypeError("candidates must be an array");
  requireFinite(x, "landing x");
  requireFinite(y, "landing y");
  const projectileRadius = requireFinite(halfWidth, "projectile half width");
  if (projectileRadius < 0) {
    throw new RangeError("projectile half width must be nonnegative");
  }
  let best = null;
  let bestDistanceSquared = Infinity;
  for (const candidate of candidates) {
    if (!candidate?.alive) continue;
    const dx = candidate.x - x;
    const dy = candidate.y - y;
    const distanceSquared = dx * dx + dy * dy;
    const reach = collisionRadius(candidate) + projectileRadius;
    if (distanceSquared > reach * reach + EPSILON) continue;
    if (distanceSquared < bestDistanceSquared - EPSILON
        || (Math.abs(distanceSquared - bestDistanceSquared) <= EPSILON
          && compareReference(candidate, best) < 0)) {
      best = candidate;
      bestDistanceSquared = distanceSquared;
    }
  }
  return best;
}


// Siege blast damage is full while the impact point lies inside the victim's
// collision body, then falls linearly to zero one DAT blast radius beyond the
// body edge. Null means the body is outside the blast entirely; zero is a body
// exactly on the edge and still receives the game's one-damage floor.
export function blastFalloffFraction(victim, impactX, impactY, blastRadius) {
  requireFinite(impactX, "impact x");
  requireFinite(impactY, "impact y");
  const radius = requireFinite(blastRadius, "blast radius");
  if (radius <= 0) throw new RangeError("blast radius must be positive");
  const centerDistance = Math.hypot(victim.x - impactX, victim.y - impactY);
  const edgeDistance = Math.max(0, centerDistance - collisionRadius(victim));
  if (edgeDistance > radius + EPSILON) return null;
  return Math.max(0, 1 - Math.min(1, edgeDistance / radius));
}


// Geometric factor for the hypothesis that a positive DAT projectile arc is a
// symmetric parabola whose apex is `arc * span`, with speed measured along the
// path. The engine deliberately does not apply this factor yet: raw arc is
// exported so fresh live flight tracks can decide that interpretation first.
export function projectileArcFlightFactor(projectileArc) {
  const arc = requireFinite(projectileArc, "projectile arc");
  if (arc < 0) throw new RangeError("projectile arc must be nonnegative");
  if (arc === 0) return 1;
  const k = 4 * arc;
  return Math.sqrt(1 + k * k) / 2 + Math.asinh(k) / (2 * k);
}


// One primary Onager stone spawns nine one-damage fragments. The live tracks
// form an isotropic, approximately one-tile disc. A heading-oriented golden
// spiral is a deterministic equal-area sample of that measured distribution;
// it does not consume the combat RNG stream or perturb later attacks.
export function siegeDebrisLandingPoints({
  impactX,
  impactY,
  shooterX,
  shooterY,
  count,
  scatterRadiusTiles = SIEGE_DEBRIS_SCATTER_RADIUS_TILES,
}) {
  for (const [value, name] of [
    [impactX, "impact x"],
    [impactY, "impact y"],
    [shooterX, "shooter x"],
    [shooterY, "shooter y"],
    [scatterRadiusTiles, "scatter radius"],
  ]) requireFinite(value, name);
  if (!Number.isSafeInteger(count) || count < 0) {
    throw new RangeError("debris count must be a nonnegative integer");
  }
  if (scatterRadiusTiles < 0) {
    throw new RangeError("scatter radius must be nonnegative");
  }
  const heading = Math.atan2(impactY - shooterY, impactX - shooterX);
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  return Object.freeze(Array.from({ length: count }, (_, index) => {
    const radius = scatterRadiusTiles * Math.sqrt((index + 0.5) / count);
    const angle = heading + index * goldenAngle;
    return Object.freeze({
      x: impactX + radius * Math.cos(angle),
      y: impactY + radius * Math.sin(angle),
      index,
    });
  }));
}
