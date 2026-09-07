const EPSILON = 1e-12;


export function hasLimitedClosurePerReload(mover, target) {
  const range = mover?.mechanics?.attack_range_tiles;
  const reload = mover?.mechanics?.reload_seconds;
  const moverSpeed = mover?.mechanics?.speed_tiles_per_second;
  const targetSpeed = target?.mechanics?.speed_tiles_per_second;
  if (!Number.isFinite(range) || range < 1 - EPSILON
      || !Number.isFinite(reload) || reload <= 0
      || !Number.isFinite(moverSpeed) || moverSpeed < 0
      || !Number.isFinite(targetSpeed) || targetSpeed < 0) return false;
  const closurePerReload = Math.max(0, moverSpeed - targetSpeed) * reload;
  return closurePerReload <= range + EPSILON;
}
