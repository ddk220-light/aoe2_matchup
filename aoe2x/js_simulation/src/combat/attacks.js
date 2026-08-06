import { secondsToTicksCeil, secondsToTicksNearest } from "../simulation-clock.js";
import { MELEE_CONTACT_TOLERANCE_TILES, chebyshevGap } from "./targeting.js";


function compareText(left, right) {
  const leftText = String(left ?? "");
  const rightText = String(right ?? "");
  if (leftText === rightText) return 0;
  return leftText < rightText ? -1 : 1;
}


function requireFinite(value, name) {
  if (!Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
  return value;
}


function requireReference(value, name) {
  if (!Number.isSafeInteger(value)) throw new TypeError(`${name} must be a safe integer`);
  return value;
}


function requireTick(value, name) {
  requireReference(value, name);
  if (value < 0) throw new RangeError(`${name} must be nonnegative`);
  return value;
}


function classValue(classes, classId, name) {
  const value = classes?.[classId];
  if (value === undefined) return undefined;
  return requireFinite(value, `${name} class ${classId}`);
}


function createEvent(type, details) {
  const tick = requireTick(details?.tick, "event tick");
  const actorId = requireReference(details?.actorId, "actor reference ID");
  const targetId = requireReference(details?.targetId, "target reference ID");
  const readyTick = requireTick(details?.readyTick, "ready tick");
  // A charge volley can land several projectiles on one victim in the same
  // tick; the index keeps their event ids distinct.
  const suffix = details?.projectileIndex !== undefined
    ? `:${details.projectileIndex}`
    : "";
  const id = `${tick}:${type}:${actorId}:${targetId}${suffix}`;
  return Object.freeze({
    id,
    eventId: id,
    type,
    ...details,
    tick,
    actorId,
    targetId,
    readyTick,
  });
}


export function attackDelayTicks(mechanics) {
  return secondsToTicksNearest(
    requireFinite(mechanics?.attack_delay_seconds, "attack delay seconds"),
  );
}


// Full attack animation: the unit is committed to its swing for this long, and
// the hit lands partway through it (attackDelayTicks). Sourced from the Genie
// attack graphic's frame_count x frame_duration.
export function attackAnimationTicks(mechanics) {
  const seconds = requireFinite(
    mechanics?.attack_animation?.seconds,
    "attack animation seconds",
  );
  if (seconds <= 0) throw new RangeError("attack animation must be positive");
  const ticks = secondsToTicksNearest(seconds);
  const delay = attackDelayTicks(mechanics);
  if (delay > ticks) {
    throw new RangeError("attack delay must not exceed the attack animation");
  }
  return ticks;
}


export function reloadTicks(mechanics) {
  return secondsToTicksCeil(
    requireFinite(mechanics?.reload_seconds, "reload seconds"),
  );
}


// Movement STOP rule: a unit pursues until its COLLISION-box Chebyshev gap to
// the target is at most max(range, 0.1). Measured on the steppe tapes: the
// range-1 lancer's approach stops are victim-invariant only in collision
// terms and pile up in [0.95, 1.00) against every victim type (p50 0.95,
// p90 0.995, nothing between 1.0 and 1.1), while range-0 units keep the
// long-established 0.1 stop. Units therefore walk INSIDE their outline
// attack envelope (isWithinReach) before stopping; eligibility and stopping
// are different rules with different boxes.
export function isWithinStopRange(actor, target) {
  const range = requireFinite(actor?.mechanics?.attack_range_tiles, "attack range");
  if (range < 0) throw new RangeError("attack range must be nonnegative");
  const stop = Math.max(range, MELEE_CONTACT_TOLERANCE_TILES);
  return chebyshevGap(actor, target) <= stop + 1e-12;
}


export function calculateDamage(actor, target) {
  const attacks = actor?.mechanics?.attack_classes;
  const armors = target?.mechanics?.armor_classes;
  if (!attacks || typeof attacks !== "object") {
    throw new TypeError("attacker classes are required");
  }
  if (!armors || typeof armors !== "object") {
    throw new TypeError("target armor classes are required");
  }

  const baseAttack = classValue(attacks, "4", "attack");
  const baseArmor = classValue(armors, "4", "armor");
  if (baseAttack === undefined || baseArmor === undefined) {
    throw new TypeError("attack and armor class 4 are required");
  }
  let damage = Math.max(0, baseAttack - baseArmor);
  for (const [classId, attack] of Object.entries(attacks)) {
    if (classId === "4" || attack <= 0) continue;
    const armor = classValue(armors, classId, "armor");
    if (armor === undefined) continue;
    damage += Math.max(0, requireFinite(attack, `attack class ${classId}`) - armor);
  }
  return Math.max(1, damage);
}


// Melee blast ("trample"), sourced from the Genie dat and measured on the
// authorized elephant tapes (54 fights): the blast is a circle of radius
// blast.width_tiles centred on the ATTACKER at the instant its hit lands, and
// it reaches every ENEMY unit whose collision box intersects the circle —
// 1694/1694 tape bystander samples separate cleanly on that rule (hits reach
// box-distance 0.396, misses start at 0.402, dat width 0.4). Each victim takes
// blast.damage_fraction x the post-armor damage against ITSELF (14 -> 3.5 on
// Champions, 13 -> 3.25 on Paladins). Allies are never hit despite the dat's
// level-2/friendly-fire flags, and the main target takes only the main hit.
// Gate mirrors the Python ability registry: blast_attack_level == 2 with a
// true fraction (the Champion carries width 0 / damage -5.0 sentinels).
export function trampleSpec(mechanics) {
  const blast = mechanics?.blast;
  if (!blast) return null;
  const width = requireFinite(blast.width_tiles, "blast width");
  const fraction = requireFinite(blast.damage_fraction, "blast damage fraction");
  if (blast.attack_level !== 2 || width <= 0 || fraction <= 0 || fraction >= 1) {
    return null;
  }
  return { widthTiles: width, damageFraction: fraction };
}


// Charge volley (Fire Lancer family), sourced from the Genie dat and measured
// on the four authorized firelancer archives (108 fights, 265 volleys):
//   - charge_type 6 fires `projectile_count` charge projectiles as the unit's
//     FIRST attack cycle. Units spawn with full charge; every tape volley is
//     the firer's opening attack and no unit ever refired (recharge takes 30 s
//     and no recorded fight leaves a unit in combat that long after firing).
//   - The charge cycle runs on the dat `special_graphic` animation (2.000 s
//     for the Elite Fire Lancer) with the volley released on animation frame
//     `frame_delay`: 10/30 -> 0.6667 s, tape floor 0.668 across 265 volleys.
//     The unit stands for the WHOLE animation (first post-volley movement at
//     anim end + the recorder's detection lag), and its regular reload runs
//     from the same swing start, so the next melee swing follows one reload
//     after the charge swing (tape minimum gap 2.016 s).
//   - It is fired from a standstill at the acquisition target, 1.5-5.2 tiles
//     out in the tapes, without closing first; line of sight is the bound.
//   - Each projectile deals the class-matched attack total with the victim's
//     armor VALUES ignored: champions (PA 5), paladins (PA 7), steppe lancers
//     (PA 6) and elephants (PA 9) all take exactly 3.0 -- 684/684 events.
//   - 88% of tape hits land on the volley's target and 2.58 of 3 projectiles
//     land on average, victim-size independent; the residual in-game scatter
//     is not resolvable at the recorder's 10 Hz missile sampling, so the
//     engine flies all three at the target and accepts the ~1 damage/volley
//     overshoot (documented in docs/FIRE_LANCER_CHARGE_2026-08-06.md).
export function chargeSpec(mechanics) {
  const charge = mechanics?.charge;
  if (!charge) return null;
  if (charge.charge_type !== 6) {
    throw new RangeError(`unsupported charge_type ${charge.charge_type}`);
  }
  const maxCharge = requireFinite(charge.max_charge, "max charge");
  const rechargeRate = requireFinite(charge.recharge_rate, "recharge rate");
  const projectileCount = charge.projectile_count;
  if (!Number.isSafeInteger(projectileCount) || projectileCount < 1) {
    throw new RangeError("charge projectile count must be a positive integer");
  }
  const speed = requireFinite(
    charge.projectile_speed_tiles_per_second, "charge projectile speed");
  if (maxCharge <= 0 || speed <= 0) {
    throw new RangeError("charge and projectile speed must be positive");
  }
  const windupTicks = secondsToTicksNearest(
    requireFinite(charge.windup_seconds, "charge windup seconds"));
  const animationTicks = secondsToTicksNearest(
    requireFinite(charge.charge_animation?.seconds, "charge animation seconds"));
  if (windupTicks <= 0 || windupTicks > animationTicks) {
    throw new RangeError("charge windup must sit inside the charge animation");
  }
  const attacks = charge.projectile_attacks;
  if (!attacks || typeof attacks !== "object" || !Object.keys(attacks).length) {
    throw new TypeError("charge projectile attacks are required");
  }
  return {
    maxCharge,
    rechargeRate,
    projectileCount,
    projectileSpeed: speed,
    projectileAttacks: attacks,
    windupTicks,
    animationTicks,
  };
}


// Charge projectile damage: standard armor-class matching, armor value IGNORED.
// The victim takes the projectile's attack amount for every bonus class it
// carries (min 1 like any hit). All four recorded victim types measure exactly
// the projectile's class-3 pierce amount, through pierce armor 5-9.
export function chargeProjectileDamage(spec, target) {
  const armors = target?.mechanics?.armor_classes;
  if (!armors || typeof armors !== "object") {
    throw new TypeError("target armor classes are required");
  }
  let damage = 0;
  for (const [classId, attack] of Object.entries(spec.projectileAttacks)) {
    if (attack <= 0) continue;
    if (classValue(armors, classId, "armor") === undefined) continue;
    damage += requireFinite(attack, `charge attack class ${classId}`);
  }
  return Math.max(1, damage);
}


export function createAttackStartEvent(details) {
  return createEvent("attack-start", details);
}


export function createDamageEvent(details) {
  return createEvent("damage", details);
}


export function createDeathEvent(details) {
  return createEvent("death", details);
}


export function createAttackCanceledEvent(details) {
  return createEvent("attack-canceled", details);
}


export function orderReadyAttacks(attacks) {
  if (!Array.isArray(attacks)) throw new TypeError("ready attacks must be an array");
  return [...attacks].sort((left, right) => (
    left.readyTick - right.readyTick ||
    left.actorId - right.actorId ||
    left.targetId - right.targetId ||
    compareText(left.type, right.type)
  ));
}
