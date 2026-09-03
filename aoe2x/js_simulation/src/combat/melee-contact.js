import { allyCollisionRadius, collisionRadius } from "./targeting.js";


const EPSILON = 1e-12;


export function isZeroRangeMelee(unit) {
  const range = unit?.mechanics?.attack_range_tiles;
  if (!Number.isFinite(range) || range < 0) {
    throw new RangeError("attack range must be finite and nonnegative");
  }
  const melee = unit.mechanics.ranged === undefined || unit.mechanics.ranged === null;
  return melee && range <= EPSILON;
}


export function occupiesZeroRangeMeleeContact(unit) {
  return unit?.alive !== false
    && unit?.action === "attacking"
    && isZeroRangeMelee(unit);
}


export function hasUnobstructedZeroRangeMeleeContact(actor, target, units) {
  if (!isZeroRangeMelee(actor)) return true;
  for (const ally of units) {
    if (ally.referenceId === actor.referenceId
        || ally.owner !== actor.owner
        || ally.alive === false) continue;
    const separation = Math.max(
      Math.abs(actor.x - ally.x),
      Math.abs(actor.y - ally.y),
    );
    if (separation < allyCollisionRadius(actor) + allyCollisionRadius(ally) - EPSILON) {
      return false;
    }
    if (!occupiesZeroRangeMeleeContact(ally)) continue;
    if (collisionSquaresOverlap(actor, ally)) return false;
    if (alliedBodyIntersectsAttackLine(actor, target, ally)) return false;
  }
  return true;
}


function collisionSquaresOverlap(left, right) {
  const extent = collisionRadius(left) + collisionRadius(right);
  return Math.max(
    Math.abs(left.x - right.x),
    Math.abs(left.y - right.y),
  ) < extent - EPSILON;
}


function alliedBodyIntersectsAttackLine(actor, target, ally) {
  const dx = target.x - actor.x;
  const dy = target.y - actor.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared <= EPSILON * EPSILON) return false;
  const centerProjection = ((ally.x - actor.x) * dx + (ally.y - actor.y) * dy)
    / lengthSquared;
  if (centerProjection <= EPSILON || centerProjection >= 1 - EPSILON) return false;
  return segmentIntersectsSquare(actor, target, ally, collisionRadius(ally));
}


function segmentIntersectsSquare(start, end, square, radius) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  let entry = 0;
  let exit = 1;
  for (const [origin, delta, minimum, maximum] of [
    [start.x, dx, square.x - radius, square.x + radius],
    [start.y, dy, square.y - radius, square.y + radius],
  ]) {
    if (Math.abs(delta) <= EPSILON) {
      if (origin < minimum - EPSILON || origin > maximum + EPSILON) return false;
      continue;
    }
    const first = (minimum - origin) / delta;
    const second = (maximum - origin) / delta;
    entry = Math.max(entry, Math.min(first, second));
    exit = Math.min(exit, Math.max(first, second));
    if (entry > exit + EPSILON) return false;
  }
  return exit > EPSILON && entry < 1 - EPSILON;
}
