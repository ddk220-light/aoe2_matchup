import { secondsToTicksNearest } from "../simulation-clock.js";
import { unitByMaster } from "../unit-registry.js";
import { chargeSpec } from "./attacks.js";
import { acquisitionDelaySeconds } from "./targeting.js";


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
  behaviorFamily,
  actionTimers = null,
  acquisitionRank = 0,
  acquisitionCount = 1,
} = {}) {
  requireSafeInteger(referenceId, "reference ID");
  requireSafeInteger(owner, "owner");
  requireFinite(x, "x");
  requireFinite(y, "y");
  requireFinite(facing, "facing");
  if (!mechanics || typeof mechanics !== "object") {
    throw new TypeError("unit mechanics are required");
  }
  const versionedRuntimeProfile = mechanics.mechanics_schema_version !== undefined;
  if (versionedRuntimeProfile) {
    if (mechanics.mechanics_schema_version !== 1) {
      throw new RangeError(
        `unsupported unit mechanics schema ${mechanics.mechanics_schema_version}`,
      );
    }
  } else {
    for (const field of REQUIRED_PROVENANCE) {
      if (mechanics.provenance?.[field] === undefined) {
        throw new TypeError(`unit mechanics must carry provenance.${field}`);
      }
    }
  }

  const unitMaster = requireSafeInteger(mechanics.unit_master, "unit mechanics unit master");
  if (unitMaster <= 0) throw new RangeError("unit mechanics master must be positive");
  const resolvedBehaviorFamily = behaviorFamily ?? unitByMaster(unitMaster)?.behaviorFamily;
  if (resolvedBehaviorFamily !== undefined
      && (typeof resolvedBehaviorFamily !== "string" || resolvedBehaviorFamily.length === 0)) {
    throw new TypeError("behavior family must be a nonempty string");
  }
  const hp = requireFinite(mechanics.hp, "unit mechanics hp");
  if (hp <= 0) throw new RangeError("unit mechanics hp must be positive");

  const timers = actionTimers ?? {
    windup: 0,
    reload: 0,
    swing: 0,
    acquire: secondsToTicksNearest(
      acquisitionDelaySeconds(acquisitionRank, acquisitionCount),
    ),
  };
  // Charge-capable units (Fire Lancer family) carry their charge level in
  // unit state; every tape unit opens its first fight with a full charge.
  // Gated on the mechanics block so non-charge fixtures keep their exact
  // canonical unit shape (and therefore their golden state hashes).
  const charge = chargeSpec(mechanics);
  const hasSpecialEffects = (
    mechanics.effects
      && typeof mechanics.effects === "object"
      && Object.keys(mechanics.effects).length > 0
  ) || mechanics.dismount_form !== undefined || mechanics.melee_charge != null;
  return Object.freeze({
    referenceId,
    owner,
    x,
    y,
    facing,
    mechanics,
    ...(resolvedBehaviorFamily === undefined
      ? {}
      : { behaviorFamily: resolvedBehaviorFamily }),
    unitMaster,
    hp,
    ...(hasSpecialEffects ? {
      maxHp: hp,
      specialState: Object.freeze({
        baseMaxHp: hp,
        baseSpeed: mechanics.speed_tiles_per_second,
        transformed: false,
        dismounted: false,
        firstAttackUsed: false,
        killAttackBonus: 0,
        hpGainedFromKills: 0,
        armorStripped: 0,
        nearbyAttackBonus: 0,
        auraHpBonus: 0,
        rampHitTicks: Object.freeze([]),
        bleedDamagePerSecond: 0,
        bleedUntilTick: 0,
        slowUntilTick: 0,
        allyHealRemaining: 0,
        allyHealPerTick: 0,
        meleeChargeReadyTick: 0,
        chargedSpeedActive: false,
        chargedSpeedTargetId: null,
      }),
    } : {}),
    // Charge units also remember their own reaction-lag draw: completing the
    // charge cycle re-enters combat through the same acquisition gate (see
    // progressAttacks), and the tapes' post-charge first-melee-swing spread
    // (1.3 s across byte-identical repeats) carries the acquisition-roll
    // signature rather than any deterministic cycle rule.
    ...(charge ? { charge: charge.maxCharge, acquireDelayTicks: timers.acquire } : {}),
    alive: true,
    pursuitTargetId: null,
    engagedTargetId: null,
    attackTargetId: null,
    avoidance: null,
    action: "idle",
    actionTimers: freezeTimers(timers),
  });
}
