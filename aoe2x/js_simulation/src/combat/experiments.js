// TEMPORARY experiment harness for the retargeting investigation.
//
// AOE2X_EXP_ENGAGEMENT and AOE2X_EXP_ORDERS are pinned to their calibrated
// values ("pursuit" and on) as the committed default -- see
// ../engine-config.js. Every locked gate and golden baseline measured under
// that engine is what "default" now means. The other flags below remain OFF
// by default. To get the pre-calibration baseline engine back, set
// AOE2X_EXP_ENGAGEMENT=free (engine-config.js maps that sentinel to "", since
// PowerShell's `$env:X = ""` deletes rather than sets) and
// AOE2X_EXP_ORDERS=0. Delete this module and its two call sites in world.js
// once the retargeting rule is settled.
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
//   AOE2X_EXP_STEP = "bimodal" | "steer" | "chaser"
//       "bimodal": a step the collision solver had to shorten becomes no step
//       at all. Genie units never grind along a body -- see the histogram
//       above and docs/CAMEL_CHASER_GEOMETRY_2026-08-06.md.
//       "steer": the same, plus a blocked unit first looks for a clear
//       full-speed heading near the one it wanted, so it walks AROUND the
//       body instead of stopping dead in front of it. Cancelling without
//       steering strands the kite formation (duty cycle 0.18 against the
//       tape's 0.79).
//       "chaser": bimodal cancellation applied ONLY to the chasing side of a
//       kited scenario (world.kiteState present, unit not on the kiting
//       side). The blanket modes above each fail for a measured reason --
//       bimodal strands the kite block, steer lets it escape forever, and
//       both perturb every melee fight. The 12v21 hcc forensics
//       (STANDARD_UNITS_SUMMARY_2026-08-07) show the defect only DECIDES
//       kited chases: sim chasers grind along the ball at partial speed
//       (7.5-15.4% of approach-band frames vs the tape's 0.6-0.8%), pinning
//       the median chaser-to-kiter gap at 0.75 tiles vs the tape's 1.6.
//       Scoping to kited chasers leaves every non-kited fight bit-identical.

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
// AOE2X_EXP_CHASE_PATH=grid -- per-unit obstacle-aware pursuit pathing
// (src/combat/chase-path.js): each kited-world chaser plans a coarse A* route
// to its own target around the actual unit bodies before walking. This is the
// plan step the 12v21 forensics called for -- the tape's chasers hold a
// 1.4-2.1 tile median gap at full speed, which no local per-step rule
// reproduces without stranding a catching column (the measured ladder in
// docs/HCC_CHASER_MOBILITY_2026-08-07.md). A tangent-disc variant ("ball")
// was measured and rejected: it flips hcavarcher_vs_paladin 20v15 (corpus
// 576.3 / 3 wrong winners vs grid's 522.7 / 1).
const chasePath = ENGINE_CONFIG.chasePath;

const VALID_ENGAGEMENT = new Set(["", "pursuit"]);
const VALID_PURSUIT = new Set(["", "tick", "blocked", "swing", "blocked+swing"]);
const VALID_AVOID = new Set(["", "all"]);
const VALID_STEP = new Set(["", "bimodal", "steer", "chaser", "kited"]);
const VALID_MIN_RANGE = new Set(["", "shooter"]);
const VALID_KITE_ENGAGE = new Set(["", "blocker"]);
const VALID_CHASE_PATH = new Set(["", "grid"]);

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
  throw new RangeError(
    `AOE2X_EXP_STEP must be one of "", "bimodal", "steer", "chaser", "kited"`,
  );
}
if (!VALID_MIN_RANGE.has(minRange)) {
  throw new RangeError(`AOE2X_EXP_MINRANGE must be one of "", "shooter"`);
}
if (!VALID_KITE_ENGAGE.has(kiteEngage)) {
  throw new RangeError(`AOE2X_EXP_KITE_ENGAGE must be one of "", "blocker"`);
}
if (!VALID_CHASE_PATH.has(chasePath)) {
  throw new RangeError(`AOE2X_EXP_CHASE_PATH must be one of "", "grid"`);
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
export const CHASER_BIMODAL_STEP = step === "chaser" || step === "kited";
// "kited" extends the chaser rule to the KITING side's move-ordered units:
// the 12v21 victim forensics show the caught kiter executing its scripted
// ball move THROUGH attacker contact at the ball's own pace (victim 1 s
// displacement 0.50-0.67 vs ball-mates 0.55-0.66), where the sim's kiter
// grinds on the pressing champion's body (0.13-0.39, below even its mates).
export const KITED_SIDE_STEER = step === "kited";
export const MIN_RANGE_SUPPRESSES_SHOOTER = minRange === "shooter";
export const KITE_ENGAGE_BLOCKER = kiteEngage === "blocker";
export const CHASE_PATH_GRID = chasePath === "grid";
export const ANY_EXPERIMENT = Boolean(
  engagement || pursuit || orders === "1" || avoid || step || minRange || kiteEngage
  || chasePath,
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
