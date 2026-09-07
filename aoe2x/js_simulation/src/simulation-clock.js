export const TICKS_PER_SECOND = 60;

export function secondsToTicksCeil(seconds) {
  assertFiniteNonnegative(seconds, "seconds");
  const ticks = Math.ceil(seconds * TICKS_PER_SECOND);
  if (!Number.isSafeInteger(ticks)) {
    throw new RangeError("seconds must convert to a safe integer tick count");
  }
  return ticks;
}

// Animation timings arrive as float32 frame durations promoted to float64, so
// 45 frames of 1/30 s reads as 1.5000000782 s. Ceil would spend a whole extra
// tick on that dust; nearest lands on the frame the game actually uses.
export function secondsToTicksNearest(seconds) {
  assertFiniteNonnegative(seconds, "seconds");
  const ticks = Math.round(seconds * TICKS_PER_SECOND);
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
