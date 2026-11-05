import { TICKS_PER_SECOND, secondsToTicksCeil } from "../simulation-clock.js";
import { DIPLOMACY, relationFrom } from "./diplomacy.js";

const PROJECTILE_DAMAGE = new Set([
  "ranged-projectile", "charge-projectile", "bolt-projectile", "stray-projectile",
  "shell-projectile", "pebble-projectile", "grenade-splash", "impact-splash",
]);

export function isMeleeWeaponDamage(details = {}) {
  return (!details.kind && details.triggersOnHit === true) || details.kind === "trample";
}

export function incomingDamageMultiplier(unit, actor) {
  return actor && relationFrom(unit, actor) === DIPLOMACY.ALLY
    ? unit.mechanics.effects?.friendly_fire_damage_multiplier ?? 1 : 1;
}

export function advanceDefenseCharge(unit) {
  const effects = unit.mechanics.effects ?? {};
  const maximum = effects.dodge_shield_max ?? 0;
  const fullRechargeSeconds = effects.dodge_shield_recharge ?? 0;
  if (maximum > 0 && fullRechargeSeconds > 0) {
    // The exported time is MaxCharge / RechargeRate: it refills the WHOLE
    // pool, not one charge. Fractional charge alone cannot block another hit.
    unit.specialState.dodgeShieldCharges = Math.min(maximum,
      unit.specialState.dodgeShieldCharges + maximum / fullRechargeSeconds / TICKS_PER_SECOND);
  }
}

export function consumeDamageBlock(unit, details, tick) {
  const effects = unit.mechanics.effects ?? {};
  const state = unit.specialState;
  if (!state) return null;
  if (PROJECTILE_DAMAGE.has(details?.kind) && (effects.dodge_shield_max ?? 0) > 0
      && state.dodgeShieldCharges >= 1 - 1e-12) {
    state.dodgeShieldCharges = Math.max(0, state.dodgeShieldCharges - 1);
    return "projectile-shield";
  }
  // Owner scope: ordinary direct melee only; charge, trample and explosions
  // bypass the shield. A combined strike is split by applyCommittedDamage.
  const ordinaryMelee = !details?.kind && details?.triggersOnHit === true;
  if (ordinaryMelee && effects.block_first_melee      && tick >= (state.meleeBlockReadyTick ?? 0)) {
    const seconds = effects.melee_block_recharge_seconds ?? 0;
    state.meleeBlockReadyTick = seconds > 0
      ? tick + secondsToTicksCeil(seconds) : Number.MAX_SAFE_INTEGER;
    return "melee-block";
  }
  return null;
}
