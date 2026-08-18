import { createPairInteractionSnapshot, resolvePairInteraction } from "./pair-interactions.js";


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


export function proposeMovement(unit, target, ticksPerSecond, options = {}) {
  const ticks = requireFinite(ticksPerSecond, "ticks per second");
  if (ticks <= 0) throw new RangeError("ticks per second must be positive");

  const speed = requireFinite(
    unit?.mechanics?.speed_tiles_per_second,
    "movement speed",
  );
  if (speed < 0) throw new RangeError("movement speed must be nonnegative");

  const dx = requireFinite(target?.x, "target x") - requireFinite(unit?.x, "unit x");
  const dy = requireFinite(target?.y, "target y") - requireFinite(unit?.y, "unit y");
  const centerDistance = Math.hypot(dx, dy);
  const pairInteractions = options.pairInteractions
    ?? createPairInteractionSnapshot({
      legacyEnemyOverlapDepthByMaster: options.enemyOverlapDepthByMaster ?? new Map(),
    });
  const gap = centerDistance
    - resolvePairInteraction(unit, target, pairInteractions).attackSurfaceExtent;
  if (centerDistance === 0 || gap <= 0 || speed === 0) {
    return Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
  }

  const magnitude = Math.min(speed / ticks, gap);
  return Object.freeze({
    referenceId: unit.referenceId,
    dx: dx / centerDistance * magnitude,
    dy: dy / centerDistance * magnitude,
  });
}
