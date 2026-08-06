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

const engagement = process.env.AOE2X_EXP_ENGAGEMENT ?? "";
const pursuit = process.env.AOE2X_EXP_PURSUIT ?? "";

const VALID_ENGAGEMENT = new Set(["", "pursuit"]);
const VALID_PURSUIT = new Set(["", "tick", "blocked", "swing", "blocked+swing"]);

if (!VALID_ENGAGEMENT.has(engagement)) {
  throw new RangeError(`AOE2X_EXP_ENGAGEMENT must be one of "", "pursuit"`);
}
if (!VALID_PURSUIT.has(pursuit)) {
  throw new RangeError(
    `AOE2X_EXP_PURSUIT must be one of "", "tick", "blocked", "swing", "blocked+swing"`,
  );
}

export const ENGAGEMENT_FOLLOWS_PURSUIT = engagement === "pursuit";
export const REEVALUATE_EVERY_TICK = pursuit === "tick";
export const REEVALUATE_ON_BLOCKED = pursuit === "blocked" || pursuit === "blocked+swing";
export const REEVALUATE_ON_SWING = pursuit === "swing" || pursuit === "blocked+swing";
export const ANY_EXPERIMENT = Boolean(engagement || pursuit);


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
