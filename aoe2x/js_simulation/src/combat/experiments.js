// TEMPORARY experiment harness for the retargeting investigation.
//
// Everything here is OFF unless an environment variable sets it, so the default
// engine behaviour -- and therefore every locked gate and golden baseline -- is
// bit-identical to what it was before this file existed. Delete this module and
// its two call sites in world.js once the retargeting rule is settled.
//
// See docs/RETARGETING_INVESTIGATION.md for the matrix these flags implement.
//
//   AOE2X_EXP_ENGAGEMENT = "pursuit"
//       A unit engages the target it is PURSUING and nothing else, instead of
//       whatever enemy drifts into reach. Without this, moveUnits refuses to
//       move an "attacking" unit, so a unit en route is captured by the first
//       body it brushes past and never arrives.
//
//   AOE2X_EXP_PURSUIT = "tick" | "blocked" | "swing" | "blocked+swing"
//       When a unit re-evaluates a still-living pursuit target.
//       "blocked" fires on the engine's existing blocked condition (actual
//       movement differed from the proposal) -- a physics trigger, not a
//       tuned constant.

//   AOE2X_EXP_AVOID = "all"
//       Local avoidance routes around EVERY live body, not only allies. The
//       tapes show chasers keeping full speed around the enemy formation
//       (camel speed is bimodal: 46.1% stopped, 52.9% at the dat 1.595, 0.6%
//       in between), which an ally-only constraint set cannot produce.
//
//   AOE2X_EXP_STEP = "bimodal" | "steer"
//       "bimodal": a step the collision solver had to shorten becomes no step
//       at all. Genie units never grind along a body -- see the histogram
//       above and docs/CAMEL_CHASER_GEOMETRY_2026-08-06.md.
//       "steer": the same, plus a blocked unit first looks for a clear
//       full-speed heading near the one it wanted, so it walks AROUND the
//       body instead of stopping dead in front of it. Cancelling without
//       steering strands the kite formation (duty cycle 0.18 against the
//       tape's 0.79).

import { ENGINE_CONFIG } from "../engine-config.js";

const engagement = ENGINE_CONFIG.engagement;
const pursuit = ENGINE_CONFIG.pursuit;
const orders = ENGINE_CONFIG.orders ? "1" : "";
const avoid = ENGINE_CONFIG.avoid;
const step = ENGINE_CONFIG.step;
// AOE2X_EXP_MINRANGE=shooter -- minimum range holds the SHOOTER, not just the
// one target it aimed at: a kiter with any enemy inside min_range is not given
// a shot this beat. Measured on the camel tape (439 named shooters, 233 arrows
// away, 225 of them hits; firers' nearest chaser p50 2.2 tiles against holders'
// 1.0) with the min_range-0 arbalester column as a null control.
const minRange = ENGINE_CONFIG.minRange;
// AOE2X_EXP_KITE_ENGAGE=blocker -- a kited-world chaser that is physically
// blocked engages whatever enemy is stopping it, instead of holding out for
// its sticky pursuit target.
const kiteEngage = ENGINE_CONFIG.kiteEngage;

const VALID_ENGAGEMENT = new Set(["", "pursuit"]);
const VALID_PURSUIT = new Set(["", "tick", "blocked", "swing", "blocked+swing"]);
const VALID_AVOID = new Set(["", "all"]);
const VALID_STEP = new Set(["", "bimodal", "steer"]);
const VALID_MIN_RANGE = new Set(["", "shooter"]);
const VALID_KITE_ENGAGE = new Set(["", "blocker"]);

if (!VALID_ENGAGEMENT.has(engagement)) {
  throw new RangeError(`AOE2X_EXP_ENGAGEMENT must be one of "", "pursuit"`);
}
if (!VALID_PURSUIT.has(pursuit)) {
  throw new RangeError(
    `AOE2X_EXP_PURSUIT must be one of "", "tick", "blocked", "swing", "blocked+swing"`,
  );
}
if (!VALID_AVOID.has(avoid)) {
  throw new RangeError(`AOE2X_EXP_AVOID must be one of "", "all"`);
}
if (!VALID_STEP.has(step)) {
  throw new RangeError(`AOE2X_EXP_STEP must be one of "", "bimodal", "steer"`);
}
if (!VALID_MIN_RANGE.has(minRange)) {
  throw new RangeError(`AOE2X_EXP_MINRANGE must be one of "", "shooter"`);
}
if (!VALID_KITE_ENGAGE.has(kiteEngage)) {
  throw new RangeError(`AOE2X_EXP_KITE_ENGAGE must be one of "", "blocker"`);
}

export const ENGAGEMENT_FOLLOWS_PURSUIT = engagement === "pursuit";
export const REEVALUATE_EVERY_TICK = pursuit === "tick";
export const REEVALUATE_ON_BLOCKED = pursuit === "blocked" || pursuit === "blocked+swing";
export const REEVALUATE_ON_SWING = pursuit === "swing" || pursuit === "blocked+swing";
// AOE2X_EXP_ORDERS=1 enables the AI-player order layer (src/combat/ai-orders.js).
// It counts as an experiment so the blocked flag gets stamped for idle rescue.
export const AVOID_ALL_BODIES = avoid === "all";
export const BIMODAL_STEP = step === "bimodal" || step === "steer";
export const STEER_AROUND_BODIES = step === "steer";
export const MIN_RANGE_SUPPRESSES_SHOOTER = minRange === "shooter";
export const KITE_ENGAGE_BLOCKER = kiteEngage === "blocker";
export const ANY_EXPERIMENT = Boolean(
  engagement || pursuit || orders === "1" || avoid || step || minRange || kiteEngage,
);


// True when this unit should drop a still-living pursuit target this tick.
export function shouldReevaluatePursuit(unit) {
  if (REEVALUATE_EVERY_TICK) return true;
  if (REEVALUATE_ON_BLOCKED && unit.experimentBlocked === true) return true;
  if (REEVALUATE_ON_SWING && unit.experimentSwungThisTick === true) return true;
  return false;
}


export function describeExperiment() {
  if (!ANY_EXPERIMENT) return "baseline";
  return `engagement=${engagement || "free"} pursuit=${pursuit || "locked"}`;
}
