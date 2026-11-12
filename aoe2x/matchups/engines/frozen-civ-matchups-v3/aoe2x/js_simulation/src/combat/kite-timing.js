import { TICKS_PER_SECOND } from "../simulation-clock.js";


export const KITE_ORDER_CLOCK_TICKS = 40;
export const KITE_MOVE_INTERVAL_TICKS = 2 * KITE_ORDER_CLOCK_TICKS;
const EMPTY_KITE_SCENARIO_POLICY = Object.freeze({});


function finite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function positiveInteger(value, name) {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new RangeError(`${name} must be a positive integer`);
  }
  return value;
}


function integerList(value, name) {
  if (!Array.isArray(value)
      || value.some((tick) => !Number.isSafeInteger(tick) || tick <= 0)) {
    throw new RangeError(`${name} must contain positive integers`);
  }
  return [...value];
}


function ceilToGrid(ticks, grid) {
  return Math.ceil(ticks / grid) * grid;
}


function mechanicsTicks(mechanics) {
  const reloadSeconds = finite(mechanics?.reload_seconds, "reload_seconds");
  const attackDelaySeconds = finite(
    mechanics?.attack_delay_seconds,
    "attack_delay_seconds",
  );
  if (reloadSeconds <= 0) throw new RangeError("reload_seconds must be positive");
  if (attackDelaySeconds < 0) {
    throw new RangeError("attack_delay_seconds must be non-negative");
  }
  return {
    reload: Math.ceil(reloadSeconds * TICKS_PER_SECOND - 1e-9),
    release: Math.round(attackDelaySeconds * TICKS_PER_SECOND),
  };
}


function recurringMoveOffsets(firstBeatTick, beatTicks, releaseTicks) {
  let firstOffset = ceilToGrid(releaseTicks, KITE_ORDER_CLOCK_TICKS);

  // An opening attack outside the ordinary 40-tick order grid (the measured
  // Hand Cannoneer tick-12 volley) rejoins the shared 80-tick movement lane.
  // This yields absolute movement orders at 80/160/240 without giving that
  // unit a separately calibrated recurring clock.
  if (firstBeatTick % KITE_ORDER_CLOCK_TICKS !== 0) {
    const readyTick = firstBeatTick + releaseTicks;
    firstOffset = ceilToGrid(readyTick, KITE_MOVE_INTERVAL_TICKS) - firstBeatTick;
  }
  if (firstOffset <= 0) firstOffset = KITE_ORDER_CLOCK_TICKS;

  const offsets = [];
  for (let offset = firstOffset; offset < beatTicks; offset += KITE_MOVE_INTERVAL_TICKS) {
    offsets.push(offset);
  }
  return offsets;
}


/**
 * Derive the recurring kiting schedule from unit mechanics.
 *
 * `policy` contains only AI choices that mechanics cannot answer: an unusual
 * opening attack phase, an optional bookkeeping top-up, and formation/action
 * policies. It never supplies the recurring reload beat or move offsets.
 */
export function deriveKiteProfile(mechanics, policy = {}) {
  const ticks = mechanicsTicks(mechanics);
  const beatTicks = ceilToGrid(ticks.reload, KITE_ORDER_CLOCK_TICKS);
  const firstBeatTick = policy.firstBeatTick === undefined
    ? beatTicks
    : positiveInteger(policy.firstBeatTick, "firstBeatTick");
  const topupOffsetTicks = policy.topupOffsetTicks === undefined
    ? []
    : integerList(policy.topupOffsetTicks, "topupOffsetTicks");
  if (topupOffsetTicks.some((tick) => tick >= beatTicks)) {
    throw new RangeError("topupOffsetTicks must fall inside the recurring beat");
  }

  const profile = {
    beatTicks,
    firstBeatTick,
    moveOffsetTicks: recurringMoveOffsets(firstBeatTick, beatTicks, ticks.release),
    topupOffsetTicks,
    preMoveTicks: firstBeatTick >= beatTicks
      ? Array.from(
        { length: Math.max(0, Math.ceil((firstBeatTick - KITE_MOVE_INTERVAL_TICKS)
          / KITE_MOVE_INTERVAL_TICKS)) },
        (_, index) => (index + 1) * KITE_MOVE_INTERVAL_TICKS,
      ).filter((tick) => tick < firstBeatTick)
      : [],
  };
  if (policy.openingVolleyTick !== undefined) {
    profile.openingVolleyTick = positiveInteger(
      policy.openingVolleyTick,
      "openingVolleyTick",
    );
  }
  for (const key of [
    "formationMotion",
    "volleyPursuit",
    "openingVolley",
    "kitedPath",
    "cohortMotion",
    "meleeWave",
  ]) {
    if (policy[key] !== undefined) profile[key] = policy[key];
  }
  if (Number.isFinite(policy.formationSpacingTiles)
      && policy.formationSpacingTiles > 0) {
    profile.formationSpacingTiles = policy.formationSpacingTiles;
  }
  return Object.freeze({
    ...profile,
    moveOffsetTicks: Object.freeze(profile.moveOffsetTicks),
    topupOffsetTicks: Object.freeze(profile.topupOffsetTicks),
    preMoveTicks: Object.freeze(profile.preMoveTicks),
  });
}


export const KITE_POLICIES = Object.freeze({
  elite_war_wagon: Object.freeze({
    // The 0.9-tile War Wagon bodies march on a 0.6-tile lattice in all eight
    // authorized Paladin/Champion recordings: conditional allied overlap
    // depth centers at ~0.30 tiles. Cohesive navigation consumes this same
    // profile value, so it no longer collapses them back onto the generic
    // 0.48-tile ranged lattice.
    formationSpacingTiles: 0.6,
  }),
  heavy_cav_archer: Object.freeze({
    firstBeatTick: 40,
    topupOffsetTicks: Object.freeze([40]),
  }),
  hand_cannoneer: Object.freeze({
    firstBeatTick: 12,
    formationMotion: "translated_offsets",
    volleyPursuit: "close_to_fire",
  }),
});


export function kitePolicyFor(slug) {
  return KITE_POLICIES[slug] ?? Object.freeze({});
}


export function warWagonChasePolicy(kiterSlug, chaserMechanics) {
  if (kiterSlug !== "elite_war_wagon") return EMPTY_KITE_SCENARIO_POLICY;
  const radiusX = finite(
    chaserMechanics?.collision_size_tiles?.x,
    "chaser collision size x",
  );
  const radiusY = finite(
    chaserMechanics?.collision_size_tiles?.y,
    "chaser collision size y",
  );
  if (radiusX <= 0 || radiusY <= 0 || radiusX !== radiusY) {
    throw new RangeError("War Wagon chase contact requires a positive square chaser body");
  }
  return Object.freeze({
    attackMoveTargetPressureTiles: 2 * radiusX,
    attackMoveStickyPursuit: true,
  });
}
