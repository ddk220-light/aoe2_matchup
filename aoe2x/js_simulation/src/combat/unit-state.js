import { secondsToTicksNearest } from "../simulation-clock.js";
import { INITIAL_ACQUISITION_DELAY_SECONDS } from "./targeting.js";


// Mechanics fixtures must be machine-generated from the Genie .dat and the
// reference DB (tools/export_unit_mechanics.py), never hand-written. The guard
// is on PROVENANCE, not on which unit it is: pinning this to the Champion's
// master/HP was what stopped the engine from running any second unit, and the
// Paladin tapes confirm every sourced field generalizes unchanged.
const REQUIRED_PROVENANCE = ["dat_sha256", "reference_db_sha256", "fields"];


function freezeTimers(timers) {
  const result = {};
  for (const [name, value] of Object.entries(timers)) {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new RangeError(`action timer ${name} must be a nonnegative safe integer`);
    }
    result[name] = value;
  }
  return Object.freeze(result);
}


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireSafeInteger(value, name) {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


export function createUnitState({
  referenceId,
  owner,
  x,
  y,
  facing,
  mechanics,
  actionTimers = null,
} = {}) {
  requireSafeInteger(referenceId, "reference ID");
  requireSafeInteger(owner, "owner");
  requireFinite(x, "x");
  requireFinite(y, "y");
  requireFinite(facing, "facing");
  if (!mechanics || typeof mechanics !== "object") {
    throw new TypeError("unit mechanics are required");
  }
  for (const field of REQUIRED_PROVENANCE) {
    if (mechanics.provenance?.[field] === undefined) {
      throw new TypeError(`unit mechanics must carry provenance.${field}`);
    }
  }

  const unitMaster = requireSafeInteger(mechanics.unit_master, "unit mechanics unit master");
  if (unitMaster <= 0) throw new RangeError("unit mechanics master must be positive");
  const hp = requireFinite(mechanics.hp, "unit mechanics hp");
  if (hp <= 0) throw new RangeError("unit mechanics hp must be positive");

  const timers = actionTimers ?? {
    windup: 0,
    reload: 0,
    swing: 0,
    acquire: secondsToTicksNearest(INITIAL_ACQUISITION_DELAY_SECONDS),
  };
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    facing,
    mechanics,
    unitMaster,
    hp,
    alive: true,
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
    action: "idle",
    actionTimers: freezeTimers(timers),
  });
}
