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
  const id = `${tick}:${type}:${actorId}:${targetId}`;
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


export function isInAttackRange(actor, target) {
  const range = requireFinite(actor?.mechanics?.attack_range_tiles, "attack range");
  if (range < 0) throw new RangeError("attack range must be nonnegative");
  return chebyshevGap(actor, target) <= range + MELEE_CONTACT_TOLERANCE_TILES + 1e-12;
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
