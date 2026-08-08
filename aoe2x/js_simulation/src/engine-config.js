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
  step: "",
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

export const ENGINE_CONFIG = Object.freeze({
  engagement: rawEngagement === "free" ? "" : rawEngagement,
  pursuit: envString("AOE2X_EXP_PURSUIT", DEFAULTS.pursuit),
  orders: envBoolean("AOE2X_EXP_ORDERS", DEFAULTS.orders),
  avoid: envString("AOE2X_EXP_AVOID", DEFAULTS.avoid),
  step: envString("AOE2X_EXP_STEP", DEFAULTS.step),
  minRange: envString("AOE2X_EXP_MINRANGE", DEFAULTS.minRange),
  kiteEngage: envString("AOE2X_EXP_KITE_ENGAGE", DEFAULTS.kiteEngage),
});
