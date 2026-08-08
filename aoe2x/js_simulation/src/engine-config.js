// The calibrated engine configuration, as committed defaults.
//
// These are the values every number in docs/ was measured under. They used to
// live only in environment variables, which meant a viewer started per the
// README ran a different engine than the corpus. Environment variables still
// override, so experiment sweeps work exactly as before.
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
  return value === undefined || value === "" ? fallback : value;
}


function envBoolean(name, fallback) {
  const value = process.env?.[name];
  if (value === undefined || value === "") return fallback;
  return value === "1";
}


export const ENGINE_CONFIG = Object.freeze({
  engagement: envString("AOE2X_EXP_ENGAGEMENT", DEFAULTS.engagement),
  pursuit: envString("AOE2X_EXP_PURSUIT", DEFAULTS.pursuit),
  orders: envBoolean("AOE2X_EXP_ORDERS", DEFAULTS.orders),
  avoid: envString("AOE2X_EXP_AVOID", DEFAULTS.avoid),
  step: envString("AOE2X_EXP_STEP", DEFAULTS.step),
  minRange: envString("AOE2X_EXP_MINRANGE", DEFAULTS.minRange),
  kiteEngage: envString("AOE2X_EXP_KITE_ENGAGE", DEFAULTS.kiteEngage),
});
