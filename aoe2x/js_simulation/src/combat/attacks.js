import { secondsToTicksCeil, secondsToTicksNearest } from "../simulation-clock.js";
import {
  MELEE_CONTACT_TOLERANCE_TILES,
  chebyshevGap,
  surfaceGap as euclideanCollisionGap,
} from "./targeting.js";
import { enemyOverlapDepthForPair } from "./collision.js";


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


function attackerHasCategory(mechanics, category) {
  const declared = mechanics?.combat_categories;
  if (declared !== undefined) {
    if (!Array.isArray(declared) || declared.some((value) => typeof value !== "string")) {
      throw new TypeError("combat categories must be an array of strings");
    }
    if (declared.includes(category)) return true;
  }
  // Build 177723 marks mounted attackers with a negative class-39 attack
  // entry. It covers cavalry, cavalry archers, Conquistador-class units and
  // Ballista Elephants without relying on a simulator-side unit-name list.
  if (category === "mounted") {
    const marker = classValue(mechanics?.attack_classes, "39", "attack");
    return marker !== undefined && marker < 0;
  }
  return false;
}


function conditionalDamageReduction(actor, target) {
  const reductions = target?.mechanics?.damage_reduction_by_attacker_category;
  if (reductions == null) return 0;
  if (typeof reductions !== "object" || Array.isArray(reductions)) {
    throw new TypeError("damage reduction by attacker category must be an object");
  }
  let total = 0;
  for (const [category, rawValue] of Object.entries(reductions)) {
    const value = requireFinite(rawValue, `${category} damage reduction`);
    if (value < 0) throw new RangeError(`${category} damage reduction must be nonnegative`);
    if (attackerHasCategory(actor?.mechanics, category)) total += value;
  }
  return total;
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
export function isWithinStopRange(actor, target, options = {}) {
  const range = requireFinite(actor?.mechanics?.attack_range_tiles, "attack range");
  if (range < 0) throw new RangeError("attack range must be nonnegative");
  const stop = Math.max(range, MELEE_CONTACT_TOLERANCE_TILES);
  const enemyOverlapDepthByMaster = options.enemyOverlapDepthByMaster;
  if (enemyOverlapDepthByMaster !== undefined
      && !(enemyOverlapDepthByMaster instanceof Map)) {
    throw new TypeError("enemy overlap depths by master must be a Map");
  }
  const overlapDepth = enemyOverlapDepthByMaster
    ? enemyOverlapDepthForPair(actor, target, enemyOverlapDepthByMaster)
    : 0;
  // Projectile units stop inside their Euclidean range circle (the same
  // metric as their reach — see isWithinReach); melee units keep the
  // Chebyshev collision-box rule measured on the steppe tapes.
  if (actor?.mechanics?.ranged) {
    return euclideanCollisionGap(actor, target) + overlapDepth <= stop + 1e-12;
  }
  return chebyshevGap(actor, target) + overlapDepth <= stop + 1e-12;
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

  // Melee units carry their base attack in class 4, ranged units in class 3
  // (archers have no class-4 attack at all); both resolve through the one
  // shared armor-class rule, then any matching bonus classes stack on top.
  const baseAttack = classValue(attacks, "4", "attack");
  const baseArmor = classValue(armors, "4", "armor");
  const pierceAttack = classValue(attacks, "3", "attack");
  const pierceArmor = classValue(armors, "3", "armor");
  if (
    (baseAttack === undefined || baseArmor === undefined)
    && (pierceAttack === undefined || pierceArmor === undefined)
  ) {
    throw new TypeError("attack and armor must share class 4 or class 3");
  }
  const term = (attackValue, armorValue) => (
    attackValue === undefined || armorValue === undefined
      ? 0
      : Math.max(0, attackValue - armorValue)
  );
  let damage = term(baseAttack, baseArmor) + term(pierceAttack, pierceArmor);
  for (const [classId, attack] of Object.entries(attacks)) {
    if (classId === "4" || classId === "3" || attack <= 0) continue;
    const armor = classValue(armors, classId, "armor");
    if (armor === undefined) continue;
    damage += Math.max(0, requireFinite(attack, `attack class ${classId}`) - armor);
  }
  return Math.max(1, damage - conditionalDamageReduction(actor, target));
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


// Ranged attack (projectile-armed units), measured on the authorized
// arbalester-vs-eliteskirm archive (25 fights, 6312 shots):
//   - the attack CYCLE is the ordinary cycle: same outline-box reach at
//     range + 0.1 (max observed fire distance 8.56 = 8 + 0.1 + two 0.2
//     outlines), same collision-box stop rule, same windup frame and reload
//     cadence — only the damage delivery differs;
//   - the shot flies at the projectile unit's dat speed to the target's
//     position at FIRE time (smart_mode 0: no leading), and on arrival hits
//     iff the target is alive and still within its own collision box of that
//     aim point. 5141/6312 tape shots hit; 1068 found a corpse (died
//     mid-flight), 23 found the target walked away (displacement >= 0.23 at
//     arrival while hits sit at p90 0.0), and 80 (1.27%) missed a live
//     stationary target — the accuracy-roll residue, which the deterministic
//     engine does not simulate (documented overshoot).
export function rangedSpec(mechanics) {
  const ranged = mechanics?.ranged;
  if (!ranged) return null;
  const speed = requireFinite(
    ranged.projectile_speed_tiles_per_second, "ranged projectile speed");
  if (speed <= 0) throw new RangeError("ranged projectile speed must be positive");
  const minRange = requireFinite(ranged.min_range_tiles ?? 0, "ranged min range");
  if (minRange < 0) throw new RangeError("ranged min range must be nonnegative");
  const passThrough = ranged.pass_through === true;
  const halfWidth = requireFinite(
    ranged.projectile_half_width_tiles ?? 0, "projectile half width");
  if (passThrough && halfWidth <= 0) {
    throw new RangeError("pass-through bolts need a positive projectile width");
  }
  // Dat attribute 19 bitfield on the projectile unit: bit 1 = ballistics
  // lead on moving targets (set by the Ballistics tech on its projectile
  // list), bit 2 = full damage on unintended targets. Absent on fixtures
  // exported before the attribute was sourced; those fly unled.
  const smartMode = requireFinite(ranged.smart_mode ?? 0, "ranged smart mode");
  // Accuracy (dat accuracy_percent < 100 gates the whole mechanic; every
  // converged-corpus archer is 100): an aim-true roll per shot; a missed
  // shot scatters within the dat dispersion half-radius and deals HALF
  // damage to whatever it hits (measured on the standard-units tapes:
  // hand-cannoneer quanta 22/11, 11/5.5 and 8/4 across four defender
  // armors are exact full/half pairs).
  const accuracy = requireFinite(ranged.accuracy_percent ?? 100, "ranged accuracy");
  const dispersion = requireFinite(
    ranged.accuracy_dispersion_tiles ?? 0, "ranged dispersion");
  // Mangonel-family blast: the FIRING unit's blast width is the area radius
  // at the primary projectile's impact point. Secondaries are visual-only
  // dat units with EMPTY attack lists — each lands scattered over the
  // spawning area for the floor 1 damage (the tapes' ubiquitous 1.0 hits).
  const blastRadius = ranged.pass_through
    ? 0
    : requireFinite(mechanics?.blast?.width_tiles ?? 0, "blast width");
  const secondaryCount = requireFinite(
    ranged.secondary_projectile_count ?? 0, "secondary projectile count");
  const spawnArea = Array.isArray(ranged.projectile_spawning_area)
    ? ranged.projectile_spawning_area
    : [0, 0];
  return {
    projectileSpeed: speed,
    minRangeTiles: minRange,
    passThrough,
    projectileHalfWidth: halfWidth,
    smartMode,
    accuracyPercent: accuracy,
    dispersionTiles: dispersion,
    blastRadius,
    secondaryCount,
    spawnArea,
  };
}


export const MISS_DAMAGE_FRACTION = 0.5;


// Pass-through bolt constants, measured on the scorpion archives (50 fights):
//   - every pass victim takes exactly HALF its own post-armor damage
//     (5407/5407 events: 5.5 on 11-damage arbalesters, 6.0 on 12-damage
//     champions; the firer's action target takes full damage, 577/577);
//   - the bolt expires ~3.0 tiles past its aim point (victim overshoot p95
//     plateaus at 2.97-3.00 across target distances 3-5 where the arena
//     leaves room, softening only where the map clips the line).
export const PASS_THROUGH_DAMAGE_FRACTION = 0.5;
export const BOLT_OVERSHOOT_TILES = 3.0;


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
