export const TICKS_PER_SECOND = 60;

export function secondsToTicksCeil(seconds) {
  assertFiniteNonnegative(seconds, "seconds");
  return Math.ceil(seconds * TICKS_PER_SECOND);
}

export function ticksToSeconds(ticks) {
  assertFiniteNonnegative(ticks, "ticks");
  if (!Number.isInteger(ticks)) {
    throw new RangeError("ticks must be an integer");
  }
  return ticks / TICKS_PER_SECOND;
}

function assertFiniteNonnegative(value, name) {
  if (!Number.isFinite(value) || value < 0) {
    throw new RangeError(`${name} must be finite and nonnegative`);
  }
}
