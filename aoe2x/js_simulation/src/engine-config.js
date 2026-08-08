// The calibrated engine configuration, as committed defaults.
//
// These are the values every number in docs/ was measured under. They used to
// live only in environment variables, which meant a viewer started per the
// README ran a different engine than the corpus. Environment variables still
// override -- an explicitly-set variable (including an explicit empty
// string) always wins over the default; only a genuinely UNSET variable
// falls back to the calibrated value.
//
// This project's documented commands are PowerShell (see README.md), and
// `$env:AOE2X_EXP_ENGAGEMENT = ""` DELETES the variable rather than setting
// it empty, which would make the baseline (un-calibrated) engagement arm
// unreachable. AOE2X_EXP_ENGAGEMENT=free is accepted as an explicit sentinel
// for "" -- "free" is this project's existing name for that state, already
// printed by describeExperiment() in combat/experiments.js. The mapping
// happens here so experiments.js's own validation still only ever sees ""
// or "pursuit".
const DEFAULTS = Object.freeze({
  engagement: "pursuit",
  pursuit: "",
  orders: true,
  avoid: "",
  // "chaser": the kited-world chasing side steers around NON-target enemy
  // bodies at full speed or stops -- never the solver's partial slide. Landed
  // 2026-08-08 after the hcc 12v21 frames.bin forensics: corpus scoreboard
  // 444.0 -> 423.0 summed band error, wrong winners unchanged (both
  // pre-existing), every non-kited recorded ratio bit-identical. Set
  // AOE2X_EXP_STEP= (empty) for the pre-calibration solver. Full ladder of
  // measured variants: docs/HCC_CHASER_MOBILITY_2026-08-07.md.
  step: "chaser",
  minRange: "",
  kiteEngage: "",
});


function envString(name, fallback) {
  const value = process.env?.[name];
  return value === undefined ? fallback : value;
}


function envBoolean(name, fallback) {
  const value = process.env?.[name];
  return value === undefined ? fallback : value === "1";
}


const rawEngagement = envString("AOE2X_EXP_ENGAGEMENT", DEFAULTS.engagement);
// Same PowerShell problem as engagement's "free" sentinel above: now that
// "step" has a non-empty default, the baseline solver needs a reachable
// explicit sentinel. AOE2X_EXP_STEP=none maps to "".
const rawStep = envString("AOE2X_EXP_STEP", DEFAULTS.step);

export const ENGINE_CONFIG = Object.freeze({
  engagement: rawEngagement === "free" ? "" : rawEngagement,
  pursuit: envString("AOE2X_EXP_PURSUIT", DEFAULTS.pursuit),
  orders: envBoolean("AOE2X_EXP_ORDERS", DEFAULTS.orders),
  avoid: envString("AOE2X_EXP_AVOID", DEFAULTS.avoid),
  step: rawStep === "none" ? "" : rawStep,
  minRange: envString("AOE2X_EXP_MINRANGE", DEFAULTS.minRange),
  kiteEngage: envString("AOE2X_EXP_KITE_ENGAGE", DEFAULTS.kiteEngage),
});
