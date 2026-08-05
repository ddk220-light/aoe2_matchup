export const TICKS_PER_SECOND = 60;

export function secondsToTicksCeil(seconds) {
  assertFiniteNonnegative(seconds, "seconds");
  const ticks = Math.ceil(seconds * TICKS_PER_SECOND);
  if (!Number.isSafeInteger(ticks)) {
    throw new RangeError("seconds must convert to a safe integer tick count");
  }
  return ticks;
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
