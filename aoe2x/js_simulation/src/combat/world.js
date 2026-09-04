import {
  queryEnemyContactManifold,
  resolveMovementProposals,
} from "./collision.js";
import {
  createPairInteractionSnapshot,
  resolvePairInteraction,
} from "./pair-interactions.js";
import {
  createContactReservationState,
  MAX_INCOMING_ENGAGEMENTS,
  updateContactReservations,
} from "./contact-reservations.js";
import {
  createKiteState,
  createOrderState,
  issueKiteOrders,
  issueOrders,
  ORDERS_ENABLED,
} from "./ai-orders.js";
import {
  ANY_EXPERIMENT,
  BIMODAL_STEP,
  CHASE_PATH_GRID,
  CHASER_BIMODAL_STEP,
  ENGAGEMENT_FOLLOWS_PURSUIT,
  KITE_ENGAGE_BLOCKER,
  KITED_SIDE_STEER,
  STEER_AROUND_BODIES,
  shouldReevaluatePursuit,
} from "./experiments.js";
import {
  advancePersistentChaseRoute,
  persistentRouteMotionStalled,
  planChaseAim,
  planMoveAim,
  planPersistentChaseRoute,
} from "./chase-path.js";
import { planCohortContactMotion } from "./cohort-motion.js";
import { planLocalAvoidance } from "./local-avoidance.js";
import { planRangedCrowding } from "./ranged-crowding.js";
import {
  planPreventiveContactSteering,
  PREVENTIVE_CONTACT_STEERING_STRENGTH,
} from "./contact-graph-steering.js";
import { proposeMovement, proposePointMovement } from "./movement.js";
import {
  createSoloNavigationState,
  finishSoloNavigationTick,
  planSoloNavigation,
  soloNavigationSnapshot,
} from "./solo-navigation.js";
import {
  chebyshevGap,
  isWithinReach,
  outlineChebyshevGap,
  selectEngagementTarget,
  selectPursuitTarget,
} from "./targeting.js";
import { TICKS_PER_SECOND, secondsToTicksCeil } from "../simulation-clock.js";
import {
  BOLT_OVERSHOOT_TILES,
  MISS_DAMAGE_FRACTION,
  PASS_THROUGH_DAMAGE_FRACTION,
  attackAnimationTicks,
  attackDelayTicks,
  calculateDamage,
  chargeProjectileDamage,
  chargeSpec,
  createAttackCanceledEvent,
  createAttackStartEvent,
  createDamageEvent,
  createDeathEvent,
  isWithinStopRange,
  meleeChargeSpec,
  orderReadyAttacks,
  rangedSpec,
  trampleSpec,
} from "./attacks.js";
import { collisionRadius } from "./targeting.js";
import {
  blastFalloffFraction,
  displacedAimPoint,
  selectProjectileLandingVictim,
  siegeDebrisLandingPoints,
} from "./projectile-mechanics.js";
import {
  areOpponents,
  changeDiplomacy,
  createDiplomacyByOwner,
  DIPLOMACY,
  isHostile,
  withDiplomacy,
} from "./diplomacy.js";


const DEFAULT_MAP = Object.freeze({
  width: 16,
  height: 16,
  obstacles: Object.freeze([]),
});
const PATROL_FIRST_SCAN_MIN_SECONDS = 1.60;
const AUXILIARY_PATROL_FIRST_SCAN_MIN_SECONDS = 1.48;
const PATROL_FIRST_SCAN_MAX_SECONDS = 1.66;
// An Onager-family cohort whose PATROL is issued while an enemy centre is
// already in shared LOS receives the game's early opening scan. This is
// intentionally a first-acquisition rule only: the 11-LOS Onager tapes expose
// their first lock at 0.69 s. Rocket Cart variants share the same behavior-
// family tag; Scorpions and ordinary ranged units remain on the normal scan.
const VISIBLE_ONAGER_PATROL_FIRST_SCAN_MIN_SECONDS = 0.66;
const VISIBLE_ONAGER_PATROL_FIRST_SCAN_MAX_SECONDS = 0.72;
const VISIBLE_ONAGER_PATROL_EARLY_SHARE = 1 / 3;
const PATROL_DETACHED_ONAGER_MEMBER_GAP_TILES = 2.0;
const DETACHED_ONAGER_PATROL_FIRST_SCAN_MIN_SECONDS = 5.5;
const DETACHED_ONAGER_PATROL_FIRST_SCAN_MEAN_TAIL_SECONDS = 12.0;
const ONAGER_PATROL_DEFERRED_SCAN_SHARE = 1 / 3;
const ONAGER_PATROL_LONG_TAIL_SHARE = 1 / 12;
const ONAGER_PATROL_LONG_TAIL_MIN_SECONDS = 4.0;
const ONAGER_PATROL_LONG_TAIL_MEAN_SECONDS = 8.0;
const PATROL_RESCAN_SECONDS = 0.8;
const PATROL_ORDER_REACTION_SECONDS = 1.0;
const PATROL_BLOCKER_CAPTURE_TICKS = Math.round(PATROL_RESCAN_SECONDS * TICKS_PER_SECOND);
// Generic blocked-pursuit recovery. A unit first gives the ordinary direct +
// local-avoidance solver five consecutive physical attempts. Only after all
// five produce less than 5% of the requested step does it promote the chase
// to a persistent obstacle route. This is roster- and matchup-independent.
const BLOCKED_PURSUIT_RETRY_LIMIT = 5;
const BLOCKED_PURSUIT_PROGRESS_FRACTION = 0.05;
// One diagonal lattice rank in the authored formations is sqrt(2) tiles
// deep.  The engine exposes roughly that first physical rank to a cohort
// PATROL instead of choosing anchors from arbitrary scenario roster order.
const PATROL_OPENING_FRONT_BAND_TILES = 1.5;
// A moving melee cohort exposes a shallow, bounded contact surface to an
// approaching PATROL. Full-rate captures across 14-27-body fronts show one to
// three first-lock lanes, all within one projected tile of the leading body.
// This classifies current geometry only; it does not alter movement or damage.
const PATROL_MELEE_CONTACT_FRONT_DEPTH_TILES = 1.0;
const PATROL_CONTACT_LANE_LIMIT = 3;
const EXPERIENCED_MELEE_RANGED_FRONT_LANE_LIMIT = 5;
const PATROL_FORMATION_RANK_GAP_TILES = 0.32;
const PATROL_FORMATION_DETACHED_LEAD_GAP_TILES = 0.50;
// Group PATROL names a principal lane; lateral lanes are fallbacks for cohort
// members sufficiently far from that axis. This measured opening-choice bias
// is spatial and ends at first acquisition.
const PATROL_OPENING_NEAR_FLANK_PENALTY_TILES = 0.25;
const PATROL_OPENING_FAR_FLANK_PENALTY_TILES = 0.25;
// The opening PATROL lock is intentionally allowed to concentrate. After a
// locked target dies, however, live 18- and 27-body ranged cohorts across
// Paladin, Steppe Lancer, Champion, and Heavy-Camel fronts retain a compact
// target-claim band despite very different HP and damage-per-shot. Full-rate
// mixed captures place the ordinary post-opening band around 9-14 claims; the
// previous value of eight dispersed a 27-body archer line immediately after
// its first kill, while the live line continued to transfer a roughly
// twelve-member lane together. This is a soft acquisition score, not a hard
// cap: geometry can still keep more actors on one target.
const PATROL_RETARGET_SOFT_CAPACITY = 12;
const ONAGER_OPENING_SOFT_TARGET_CAPACITY = 2;
const ONAGER_BEHAVIOR_FAMILY = "onager";
// Default runaway guard for a single fight, and the hard ceiling a caller may
// raise it to. 60 s covers every recorded melee fight with margin, but the
// ranged tapes' own 20v15 fights run 56.5-59.8 s and the sim legitimately
// needs more clock for max-range attrition endgames — callers pass maxTicks
// up to the ceiling for those.
const DEFAULT_WORLD_TICKS = 3600;
const MAX_WORLD_TICKS = 9000;


function hasMeleeMode(unit) {
  return unit?.mechanics?.ranged === undefined || unit.mechanics.ranged === null;
}


function unitEffects(unit) {
  return unit?.mechanics?.effects ?? {};
}


function delayedImpactExplosionSpec(unit, weaponMode = null) {
  const effects = unitEffects(unit);
  const requiredWeaponMode = effects.delayed_impact_weapon_mode ?? null;
  if (requiredWeaponMode !== null && requiredWeaponMode !== weaponMode) return null;
  const meleeAttack = effects.delayed_impact_melee_attack ?? 0;
  const radiusTiles = effects.delayed_impact_radius_tiles ?? 0;
  const delaySeconds = effects.delayed_impact_delay_seconds ?? 0;
  const repeatCount = effects.delayed_impact_repeat_count ?? 0;
  const repeatIntervalSeconds = effects.delayed_impact_repeat_interval_seconds
    ?? delaySeconds;
  if (!(meleeAttack > 0) || !(radiusTiles > 0)
      || !(delaySeconds > 0) || !(repeatCount > 0)) return null;
  if (!Number.isFinite(meleeAttack) || !Number.isFinite(radiusTiles)
      || !Number.isFinite(delaySeconds) || !Number.isFinite(repeatIntervalSeconds)) {
    throw new TypeError("delayed impact explosion parameters must be finite");
  }
  if (!Number.isSafeInteger(repeatCount) || repeatCount < 1) {
    throw new RangeError("delayed impact repeat count must be a positive safe integer");
  }
  if (repeatIntervalSeconds <= 0) {
    throw new RangeError("delayed impact repeat interval must be positive");
  }
  return {
    meleeAttack,
    radiusTiles,
    delayTicks: secondsToTicksCeil(delaySeconds),
    repeatCount,
    repeatIntervalTicks: secondsToTicksCeil(repeatIntervalSeconds),
  };
}


function effectiveUnitSpeed(unit, tick) {
  const effects = unitEffects(unit);
  let speed = unit?.specialState?.transformed
    && Number.isFinite(effects.transform_movement_speed)
    && effects.transform_movement_speed > 0
      ? effects.transform_movement_speed
      : (unit?.specialState?.baseSpeed ?? unit.mechanics.speed_tiles_per_second);
  if ((unit?.specialState?.slowUntilTick ?? 0) > tick) {
    speed *= unit.specialState.slowMultiplier ?? 1;
  }
  if (unit?.specialState?.chargedSpeedActive === true) {
    speed *= effects.charged_speed_multiplier ?? 1;
  }
  return speed;
}


function attackDelayTicksForUnit(unit) {
  const transformedDelay = unit?.specialState?.transformed
    ? unitEffects(unit).transform_attack_delay
    : null;
  return Number.isFinite(transformedDelay) && transformedDelay >= 0
    ? Math.round(transformedDelay * TICKS_PER_SECOND)
    : attackDelayTicks(unit.mechanics);
}


function reloadTicksForUnit(unit, tick) {
  const effects = unitEffects(unit);
  let seconds = unit.mechanics.reload_seconds;
  if (unit?.specialState?.transformed
      && Number.isFinite(effects.transform_attack_speed)
      && effects.transform_attack_speed > 0) {
    seconds = 1 / effects.transform_attack_speed;
  }
  const ramp = effects.attack_speed_ramp ?? 0;
  if (ramp > 0 && unit.specialState) {
    const cutoff = tick - 5 * TICKS_PER_SECOND;
    unit.specialState.rampHitTicks = unit.specialState.rampHitTicks
      .filter((hitTick) => hitTick > cutoff);
    seconds = Math.max(effects.attack_speed_min ?? 1,
      seconds - ramp * unit.specialState.rampHitTicks.length);
  }
  return secondsToTicksCeil(seconds);
}


function readyMeleeAreaCharge(unit, tick) {
  const charge = meleeChargeSpec(unit?.mechanics);
  return charge && (unit?.specialState?.meleeChargeReadyTick ?? 0) <= tick
    ? charge
    : null;
}


function isWithinActiveAttackReach(unit, target, tick) {
  if (isWithinReach(unit, target)) return true;
  const charge = readyMeleeAreaCharge(unit, tick);
  if (!charge) return false;
  // A charge-type-3 swing is the ranged use of the flexible sword: its
  // circular area reaches a target as soon as that target's physical body
  // intersects the authored blast radius. The ordinary attack remains a
  // range-zero melee weapon after the charge is spent.
  const dx = target.x - unit.x;
  const dy = target.y - unit.y;
  const victimRadius = collisionRadius(target);
  const physicalGap = Math.hypot(
    Math.max(0, Math.abs(dx) - victimRadius),
    Math.max(0, Math.abs(dy) - victimRadius),
  );
  return physicalGap <= charge.attackRangeTiles + 1e-12;
}


function meleeAttackAmount(actor, target, tick, options = {}) {
  let amount = calculateDamage(actor, target);
  const areaCharge = meleeChargeSpec(actor.mechanics);
  const chargeDamage = areaCharge?.attackBonus
    ?? unitEffects(actor).charge_attack_melee ?? 0;
  const charged = options.charged ?? (
    chargeDamage > 0
      && (actor?.specialState?.meleeChargeReadyTick ?? 0) <= tick
  );
  // Charge is bonus attack on the ordinary melee strike. Armor has already
  // been subtracted once by calculateDamage; do not subtract it a second time.
  if (charged) amount += chargeDamage;
  return { amount, charged, chargeDamage: charged ? chargeDamage : 0 };
}


function hasOnagerFamilyBehavior(unit) {
  return unit?.behaviorFamily === ONAGER_BEHAVIOR_FAMILY;
}


function selectedMinimumRangeThreat(unit, snapshot) {
  const minRange = unit?.mechanics?.ranged?.min_range_tiles ?? 0;
  if (!(minRange > 0) || !Number.isSafeInteger(unit?.pursuitTargetId)) return null;
  const target = snapshot.find(({ referenceId }) => (
    referenceId === unit.pursuitTargetId
  ));
  if (!target?.alive || !isHostile(unit, target)) return null;
  const distance = Math.hypot(target.x - unit.x, target.y - unit.y);
  return distance < minRange - 1e-9
    ? Object.freeze({ target, distance })
    : null;
}


function selectOnagerMinimumRangeAlternate(unit, snapshot) {
  const minRange = unit.mechanics.ranged.min_range_tiles;
  const candidates = snapshot.filter((candidate) => (
    candidate.alive
      && isHostile(unit, candidate)
      && candidate.referenceId !== unit.pursuitTargetId
      && Math.hypot(candidate.x - unit.x, candidate.y - unit.y)
        >= minRange - 1e-9
  ));
  if (candidates.length === 0) return null;
  // Prefer something the weapon can fire at immediately. If every legal
  // target is beyond maximum range, ordinary pursuit closes on the nearest
  // visible one instead.
  const shootable = candidates.filter((candidate) => isWithinReach(unit, candidate));
  return selectPursuitTarget(
    { ...unit, pursuitTargetId: null },
    shootable.length > 0 ? shootable : candidates,
  );
}


function onagerRetreatHeadingAvailable(unit, threat, snapshot, map, pairInteractions) {
  const distance = Math.hypot(unit.x - threat.x, unit.y - threat.y);
  if (distance <= ZERO_STEP_EPSILON) return false;
  const step = unit.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
  if (step <= ZERO_STEP_EPSILON) return false;
  const heading = Math.atan2(unit.y - threat.y, unit.x - threat.x);
  const sides = unit.referenceId % 2 === 0 ? [1, -1] : [-1, 1];
  const bounds = { width: map.width, height: map.height };
  for (let turn = 0; turn <= STEER_MAX_TURNS; turn += 1) {
    const turnSides = turn === 0 ? [0] : sides;
    for (const side of turnSides) {
      const angle = heading + side * turn * STEER_INCREMENT_RADIANS;
      const dx = Math.cos(angle) * step;
      const dy = Math.sin(angle) * step;
      if (stepClearsBodies(unit, dx, dy, snapshot, bounds, pairInteractions)
          && stepClearsMapObstacles(unit, dx, dy, map)) return true;
    }
  }
  return false;
}


function freezeUnit(unit) {
  return Object.freeze({
    ...unit,
    ...(unit.pendingVolley ? {
      pendingVolley: Object.freeze({ ...unit.pendingVolley }),
    } : {}),
    ...(unit.specialState ? {
      specialState: Object.freeze({
        ...unit.specialState,
        rampHitTicks: Object.freeze([...(unit.specialState.rampHitTicks ?? [])]),
        ...(unit.specialState.bleedStacks ? {
          bleedStacks: Object.freeze(unit.specialState.bleedStacks.map((stack) => (
            Object.freeze({ ...stack })
          ))),
        } : {}),
      }),
    } : {}),
    ...(unit.relationByOwner
      ? { relationByOwner: Object.freeze({ ...unit.relationByOwner }) }
      : {}),
    avoidance: unit.avoidance === null || unit.avoidance === undefined
      ? null
      : Object.freeze({ ...unit.avoidance }),
    actionTimers: Object.freeze({ ...unit.actionTimers }),
  });
}


function immutableClone(value) {
  if (!value || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    return Object.freeze(value.map(immutableClone));
  }
  return Object.freeze(Object.fromEntries(
    Object.entries(value).map(([name, child]) => [name, immutableClone(child)]),
  ));
}


function event(tick, type, actorId, targetId, details = {}) {
  const id = `${tick}:${type}:${actorId}:${targetId ?? "-"}`;
  return Object.freeze({
    id,
    eventId: id,
    type,
    tick,
    actorId,
    targetId,
    ...details,
  });
}


function canonicalUnits(units, { cloneMechanics = false } = {}) {
  if (!Array.isArray(units)) throw new TypeError("scenario units must be an array");
  const references = new Set();
  const result = units.map((unit) => {
    if (!Number.isSafeInteger(unit?.referenceId)) {
      throw new TypeError("unit reference ID must be a safe integer");
    }
    if (references.has(unit.referenceId)) {
      throw new Error(`duplicate unit reference ${unit.referenceId}`);
    }
    if (Object.hasOwn(unit, "targetId")) {
      throw new Error("legacy targetId is ambiguous; use explicit target state");
    }
    for (const name of ["pursuitTargetId", "engagedTargetId", "attackTargetId"]) {
      if (unit[name] !== null && !Number.isSafeInteger(unit[name])) {
        throw new TypeError(`${name} must be null or a safe integer`);
      }
    }
    references.add(unit.referenceId);
    return freezeUnit({
      ...unit,
      mechanics: cloneMechanics ? immutableClone(unit.mechanics) : unit.mechanics,
    });
  }).sort((a, b) => a.referenceId - b.referenceId);
  return Object.freeze(result);
}


function mutableUnit(unit) {
  return {
    ...unit,
    ...(unit.pendingVolley ? {
      pendingVolley: { ...unit.pendingVolley },
    } : {}),
    ...(unit.specialState ? {
      specialState: {
        ...unit.specialState,
        rampHitTicks: [...(unit.specialState.rampHitTicks ?? [])],
        ...(unit.specialState.bleedStacks ? {
          bleedStacks: unit.specialState.bleedStacks.map((stack) => ({ ...stack })),
        } : {}),
      },
    } : {}),
    ...(unit.relationByOwner
      ? { relationByOwner: Object.freeze({ ...unit.relationByOwner }) }
      : {}),
    avoidance: unit.avoidance === null ? null : { ...unit.avoidance },
    actionTimers: { ...unit.actionTimers },
  };
}


function ensureSpecialState(unit) {
  if (unit.specialState) return unit.specialState;
  unit.maxHp = unit.mechanics.hp;
  unit.specialState = {
    baseMaxHp: unit.mechanics.hp,
    baseSpeed: unit.mechanics.speed_tiles_per_second,
    transformed: false,
    firstAttackUsed: false,
    killAttackBonus: 0,
    hpGainedFromKills: 0,
    armorStripped: 0,
    nearbyAttackBonus: 0,
    auraHpBonus: 0,
    rampHitTicks: [],
    bleedDamagePerSecond: 0,
    bleedUntilTick: 0,
    bleedStacks: [],
    slowUntilTick: 0,
    allyHealRemaining: 0,
    allyHealPerTick: 0,
    meleeChargeReadyTick: 0,
  };
  return unit.specialState;
}


function nearbyAllies(unit, units, radiusTiles = 5) {
  return units.filter((candidate) => (
    candidate.alive
    && candidate.referenceId !== unit.referenceId
    && candidate.owner === unit.owner
    && Math.hypot(candidate.x - unit.x, candidate.y - unit.y) <= radiusTiles + 1e-12
  ));
}


function refreshNearbyAuras(units) {
  for (const unit of units) {
    if (!unit.alive || !unit.specialState) continue;
    const effects = unitEffects(unit);
    const allies = nearbyAllies(unit, units);
    const attackPerAlly = effects.attack_bonus_nearby ?? 0;
    unit.specialState.nearbyAttackBonus = attackPerAlly > 0
      ? attackPerAlly * Math.min(allies.length, effects.nearby_bonus_count ?? allies.length)
      : 0;
    const hpPercent = effects.hp_nearby_percent_per_unit ?? 0;
    if (hpPercent <= 0) continue;
    const qualifyingAllies = nearbyAllies(
      unit,
      units,
      effects.hp_nearby_radius_tiles ?? 15,
    ).filter((candidate) => (
      (unitEffects(candidate).hp_nearby_percent_per_unit ?? 0) > 0
    ));
    const count = Math.min(
      qualifyingAllies.length,
      effects.hp_nearby_max_units ?? qualifyingAllies.length,
    );
    const nextBonus = unit.specialState.baseMaxHp * (hpPercent / 100) * count;
    const previousMaxHp = unit.maxHp ?? (
      unit.specialState.baseMaxHp + unit.specialState.auraHpBonus
    );
    unit.specialState.auraHpBonus = nextBonus;
    unit.maxHp = unit.specialState.baseMaxHp + nextBonus;
    if (Math.abs(unit.maxHp - previousMaxHp) > 1e-12 && unit.hp > 0) {
      // Coiled Serpent Array preserves the unit's health percentage as its
      // formation-dependent ceiling changes. A shrinking formation therefore
      // reduces current HP proportionally, but cannot kill the unit outright.
      unit.hp = Math.min(
        unit.maxHp,
        Math.max(1, unit.hp * unit.maxHp / previousMaxHp),
      );
    }
  }
}


function initializeSpecialEffects(units) {
  refreshNearbyAuras(units);
}


function applyPendingDismounts(units, tick, events) {
  for (const unit of units) {
    const form = unit.mechanics?.dismount_form;
    if (unit.alive || !form || unit.specialState?.dismounted === true) continue;
    if (!Number.isFinite(form.hp) || form.hp <= 0) {
      throw new RangeError(`unit ${unit.referenceId} has an invalid dismount HP`);
    }

    const state = ensureSpecialState(unit);
    const spawnDelaySeconds = form.spawn_delay_seconds;
    if (!Number.isFinite(spawnDelaySeconds) || spawnDelaySeconds < 0) {
      throw new RangeError(
        `unit ${unit.referenceId} has an invalid dismount spawn delay`,
      );
    }
    if (!Number.isSafeInteger(state.dismountReadyTick)) {
      // A death-spawn replacement remains part of the command group that
      // owned its parent. Capture the authored order before the next tick's
      // dead-unit cleanup removes transient combat state. The replacement
      // must not inherit a dead target or an in-progress swing, but it does
      // inherit the player's durable move/patrol command so it can walk back
      // into vision instead of idling forever outside its private LOS.
      if (state.dismountInheritedMoveOrder === undefined
          && unit.moveOrder !== undefined && unit.moveOrder !== null) {
        state.dismountInheritedMoveOrder = unit.moveOrder;
      }
      state.dismountReadyTick = tick + secondsToTicksCeil(spawnDelaySeconds);
      events.push(event(tick, "unit-dismount-pending", unit.referenceId, null, {
        unitMaster: form.unit_master,
        readyTick: state.dismountReadyTick,
      }));
    }
    if (tick < state.dismountReadyTick) continue;

    // The mounted body completes its authored death/dismount animation before
    // the foot unit exists. During that interval it is dead and cannot be
    // targeted. Materializing only after the mounted form's complete DAT death
    // animation preserves the mounted death/on-kill event and prevents attacks
    // from focusing a unit that does not yet exist in the game.
    unit.mechanics = form;
    unit.unitMaster = form.unit_master;
    unit.hp = form.hp;
    unit.maxHp = form.hp;
    unit.alive = true;
    state.baseMaxHp = form.hp;
    state.baseSpeed = form.speed_tiles_per_second;
    state.transformed = false;
    state.dismounted = true;
    state.bleedDamagePerSecond = 0;
    state.bleedUntilTick = 0;
    state.bleedStacks = [];
    state.dismountCollisionRecovery = true;
    delete state.dismountReadyTick;
    unit.pursuitTargetId = null;
    unit.engagedTargetId = null;
    unit.attackTargetId = null;
    unit.avoidance = null;
    // The dismount animation is the recovery. Once the concrete foot unit has
    // spawned it starts idle and may acquire a target on the following tick;
    // no additional, invented weapon reload is appended to the three seconds.
    unit.action = "idle";
    unit.actionTimers = {
      windup: 0,
      reload: 0,
      swing: 0,
      acquire: 0,
    };
    delete unit.attackKind;
    delete unit.pendingVolley;
    delete unit.charge;
    if (state.dismountInheritedMoveOrder !== undefined) {
      unit.moveOrder = state.dismountInheritedMoveOrder;
      // Combat pursuit suspended the PATROL before the mounted body died.
      // With no inherited target, the replacement resumes transit toward the
      // same authored point and performs ordinary acquisition along the way.
      unit.patrolFormationTransit = unit.moveOrder.kind === "scenario-patrol";
      delete state.dismountInheritedMoveOrder;
    } else {
      delete unit.moveOrder;
      delete unit.patrolFormationTransit;
    }
    delete unit.patrolOpeningAttackStarted;
    events.push(event(tick, "unit-dismounted", unit.referenceId, null, {
      unitMaster: form.unit_master,
      hp: form.hp,
    }));
  }
}


function advanceSpecialEffects(units, tick, events) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const unit of units) {
    if (!unit.alive || !unit.specialState) continue;
    const effects = unitEffects(unit);
    const maxHp = unit.maxHp ?? unit.specialState.baseMaxHp;
    const passiveRegen = effects.hp_regen ?? 0;
    const combatRegen = effects.hp_regen_in_combat ?? 0;
    const recentlyAttacked = tick - (unit.specialState.lastAttackTick ?? -Infinity)
      <= 10 * TICKS_PER_SECOND;
    const regen = passiveRegen + (recentlyAttacked ? combatRegen : 0);
    if (regen > 0 && unit.hp < maxHp) {
      unit.hp = Math.min(maxHp, unit.hp + regen / 60 / TICKS_PER_SECOND);
    }
    if (unit.specialState.allyHealRemaining > 0 && unit.hp < maxHp) {
      const heal = Math.min(
        unit.specialState.allyHealRemaining,
        unit.specialState.allyHealPerTick,
      );
      unit.hp = Math.min(maxHp, unit.hp + heal);
      unit.specialState.allyHealRemaining -= heal;
    }
    if (Array.isArray(unit.specialState.bleedStacks)) {
      unit.specialState.bleedStacks = unit.specialState.bleedStacks
        .filter((stack) => stack.untilTick > tick);
      // Curare and other damage-over-time projectiles create one independent
      // stack per successful projectile. Group the active stacks by attacker
      // for this tick: it preserves source ownership and expiration while
      // avoiding one event allocation per historical projectile per tick.
      const damagePerSecondByActor = new Map();
      for (const stack of unit.specialState.bleedStacks) {
        damagePerSecondByActor.set(
          stack.actorId,
          (damagePerSecondByActor.get(stack.actorId) ?? 0) + stack.damagePerSecond,
        );
      }
      for (const [actorId, damagePerSecond] of damagePerSecondByActor) {
        applyCommittedDamage(
          units,
          actorId ?? unit.referenceId,
          unit,
          damagePerSecond / TICKS_PER_SECOND,
          tick,
          tick,
          events,
          { kind: "bleed" },
        );
        if (!unit.alive) break;
      }
      if (!unit.alive) continue;
    }
    const threshold = effects.hp_transform_threshold ?? 0;
    const reversibleTransform = effects.hp_transform_reversible === true;
    const untransformedMaxHp = unit.specialState.untransformedMaxHp
      ?? unit.specialState.baseMaxHp;
    const thresholdHp = untransformedMaxHp * threshold;
    // Jian's authored boundary is asymmetric: below 45 HP removes the
    // shield, while healing back to 45 HP restores it. Keeping the two
    // inequalities distinct prevents a one-tick form oscillation at exactly
    // the threshold.
    if (!unit.specialState.transformed && threshold > 0
        && unit.hp < thresholdHp - 1e-12) {
      if (reversibleTransform) {
        unit.specialState.untransformedMaxHp = unit.specialState.baseMaxHp;
      }
      unit.specialState.transformed = true;
      if ((effects.transform_hp ?? 0) > 0) {
        unit.specialState.baseMaxHp = effects.transform_hp;
        unit.maxHp = effects.transform_hp + unit.specialState.auraHpBonus;
        unit.hp = Math.min(unit.hp, unit.maxHp);
      }
      events.push(event(tick, "unit-transformed", unit.referenceId, null));
    } else if (unit.specialState.transformed && reversibleTransform
        && threshold > 0 && unit.hp >= thresholdHp - 1e-12) {
      unit.specialState.transformed = false;
      unit.specialState.baseMaxHp = untransformedMaxHp;
      unit.maxHp = untransformedMaxHp + unit.specialState.auraHpBonus;
      unit.hp = Math.min(unit.hp, unit.maxHp);
      delete unit.specialState.untransformedMaxHp;
      events.push(event(tick, "unit-form-restored", unit.referenceId, null));
    }
    const target = byReference.get(unit.pursuitTargetId)
      ?? byReference.get(unit.engagedTargetId);
    const chargeReady = (unit.specialState.meleeChargeReadyTick ?? 0) <= tick;
    const targetDistance = target?.alive
      ? Math.hypot(target.x - unit.x, target.y - unit.y)
      : Number.POSITIVE_INFINITY;
    const hasSpeedCharge = Number.isFinite(effects.charged_speed_multiplier);
    const targetId = target?.alive ? target.referenceId : null;
    if (!chargeReady || !hasSpeedCharge || targetId === null) {
      unit.specialState.chargedSpeedActive = false;
      unit.specialState.chargedSpeedTargetId = null;
    } else {
      // The speed-charge task is entered when a ready unit approaches its
      // target through the authored distance band. Crossing the band's lower
      // boundary does not cancel the task: the charge remains committed until
      // the strike lands (or that target ceases to be the active pursuit).
      if (unit.specialState.chargedSpeedTargetId !== targetId) {
        unit.specialState.chargedSpeedActive = false;
        unit.specialState.chargedSpeedTargetId = null;
      }
      if (!unit.specialState.chargedSpeedActive
          && targetDistance >= (effects.charged_speed_min_target_distance_tiles ?? 0)
          && targetDistance <= (effects.charged_speed_max_target_distance_tiles
            ?? Number.POSITIVE_INFINITY)) {
        unit.specialState.chargedSpeedActive = true;
        unit.specialState.chargedSpeedTargetId = targetId;
      }
    }
    const speed = effectiveUnitSpeed(unit, tick);
    if (unit.mechanics.speed_tiles_per_second !== speed) {
      unit.mechanics = Object.freeze({
        ...unit.mechanics,
        speed_tiles_per_second: speed,
      });
    }
  }
  refreshNearbyAuras(units);
}


function freezeMap(map) {
  return immutableClone({ ...map, obstacles: [...(map.obstacles ?? [])] });
}


function nextPursuitRecoveryState(previous = null) {
  return {
    attempts: new Map(previous?.attempts ?? []),
    routes: new Map(previous?.routes ?? []),
    retargetReady: new Set(previous?.retargetReady ?? []),
    nextRetargetScanTick: new Map(previous?.nextRetargetScanTick ?? []),
    routeFailures: new Map(previous?.routeFailures ?? []),
    failedTargets: new Map([...(previous?.failedTargets ?? [])].map(
      ([referenceId, targets]) => [referenceId, new Set(targets)],
    )),
  };
}


function recoveryOpportunityTarget(unit, snapshot) {
  return snapshot
    .filter((candidate) => (
      candidate.alive
      && isHostile(unit, candidate)
      && candidate.referenceId !== unit.pursuitTargetId
      && isWithinReach(unit, candidate)
    ))
    .sort((left, right) => (
      Math.hypot(left.x - unit.x, left.y - unit.y)
        - Math.hypot(right.x - unit.x, right.y - unit.y)
      || left.referenceId - right.referenceId
    ))[0] ?? null;
}


function recoveryAlternateTarget(unit, snapshot, pursuitRecoveryState, map,
  pairInteractions) {
  const failedTargets = pursuitRecoveryState.failedTargets.get(unit.referenceId)
    ?? new Set();
  const withoutCurrent = snapshot.filter(({ referenceId }) => (
    referenceId !== unit.pursuitTargetId
  ));
  let candidatePool = withoutCurrent.filter(({ referenceId }) => (
    referenceId !== unit.pursuitTargetId && !failedTargets.has(referenceId)
  ));
  const lineOfSight = unit.mechanics?.line_of_sight_tiles ?? 0;
  let visible = candidatePool.filter((candidate) => (
    candidate.alive
    && isHostile(unit, candidate)
    && Math.hypot(candidate.x - unit.x, candidate.y - unit.y) <= lineOfSight
  ));
  // Failed-target memory prevents immediate A/B thrashing, but it is not a
  // permanent blacklist. Once every other visible hostile has been tried,
  // reopen the ordinary candidate set using the unit's current geometry.
  if (visible.length === 0 && failedTargets.size > 0) {
    failedTargets.clear();
    pursuitRecoveryState.failedTargets.delete(unit.referenceId);
    candidatePool = withoutCurrent;
    visible = candidatePool.filter((candidate) => (
      candidate.alive
      && isHostile(unit, candidate)
      && Math.hypot(candidate.x - unit.x, candidate.y - unit.y) <= lineOfSight
    ));
  }
  const step = unit.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
  const bounds = { width: map.width, height: map.height };
  const directlyReachable = visible.filter((candidate) => {
    const targetDx = candidate.x - unit.x;
    const targetDy = candidate.y - unit.y;
    const distance = Math.hypot(targetDx, targetDy);
    if (distance <= ZERO_STEP_EPSILON) return true;
    const amount = Math.min(step, distance);
    const dx = targetDx / distance * amount;
    const dy = targetDy / distance * amount;
    // This selector runs only after repeated solver-rejected pursuit. A
    // non-obstructing reservation that still owns a collision extent is not
    // a directly reachable lane for recovery, even though ordinary pursuit
    // is allowed to try it before blockage has been demonstrated.
    return stepClearsBodies(
      unit,
      dx,
      dy,
      snapshot,
      bounds,
      pairInteractions,
      true,
    )
      && stepClearsMapObstacles(unit, dx, dy, map);
  });
  return selectPursuitTarget(
    { ...unit, pursuitTargetId: null },
    directlyReachable.length > 0 ? directlyReachable : visible,
  );
}


function applyOpeningPatrol(units, openingPatrolByOwner, map, openingSeed = 0) {
  if (openingPatrolByOwner === undefined) return units;
  if (!openingPatrolByOwner || typeof openingPatrolByOwner !== "object"
      || Array.isArray(openingPatrolByOwner)) {
    throw new TypeError("opening patrol by owner must be an object");
  }
  const owners = new Set(units.map(({ owner }) => owner));
  const destinations = new Map();
  for (const [ownerText, destination] of Object.entries(openingPatrolByOwner)) {
    const owner = Number(ownerText);
    if (!Number.isSafeInteger(owner) || !owners.has(owner)) {
      throw new RangeError("opening patrol owner must identify a scenario owner");
    }
    const x = destination?.x;
    const y = destination?.y;
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      throw new TypeError("opening patrol coordinates must be finite");
    }
    if (x < 0 || x >= map.width || y < 0 || y >= map.height) {
      throw new RangeError("opening patrol destination must be inside the map");
    }
    destinations.set(owner, Object.freeze({
      x,
      y,
      kind: "opening-patrol",
      // An authored PATROL command enters the same command-reaction phase
      // whether it was issued by an at-start trigger (the mixed scenarios) or
      // supplied directly by the melee golden scenario. Live melee formations
      // remain at their authored cells through the first ~1 s and begin their
      // patrol motion on the following AI beat; starting direct patrols on tick
      // zero moved fast units more than a tile before the game did.
      motionStartTick: Math.round(PATROL_ORDER_REACTION_SECONDS * TICKS_PER_SECOND),
    }));
  }
  if (destinations.size !== owners.size) {
    throw new RangeError("opening patrol must provide every scenario owner");
  }
  const origins = new Map([...owners].map((owner) => {
    const cohort = units.filter((unit) => unit.owner === owner);
    return [owner, {
      x: cohort.reduce((total, unit) => total + unit.x, 0) / cohort.length,
      y: cohort.reduce((total, unit) => total + unit.y, 0) / cohort.length,
    }];
  }));
  return units.map((unit) => {
    if (unit.moveOrder !== undefined && unit.moveOrder !== null) {
      throw new Error(`unit ${unit.referenceId} already has a move order`);
    }
    const destination = destinations.get(unit.owner);
    const origin = origins.get(unit.owner);
    return {
      ...unit,
      moveOrder: Object.freeze({
        ...destination,
        commandX: destination.x,
        commandY: destination.y,
        cohortOriginX: origin.x,
        cohortOriginY: origin.y,
        formationStartX: unit.x,
        formationStartY: unit.y,
        openingSeed,
      }),
    };
  });
}


function createSnapshot(tick, units, events, navigation = null) {
  return Object.freeze({ tick, units, events, ...(navigation ? { navigation } : {}) });
}


function openingHash(seed, owner, referenceId) {
  let value = (seed ^ Math.imul(owner, 0x9e3779b1) ^ referenceId) >>> 0;
  value ^= value >>> 16;
  value = Math.imul(value, 0x7feb352d) >>> 0;
  value ^= value >>> 15;
  value = Math.imul(value, 0x846ca68b) >>> 0;
  return (value ^ (value >>> 16)) >>> 0;
}


function selectPatrolOpeningTarget(unit, snapshot, order) {
  const directionX = (order.commandX ?? order.x) - order.cohortOriginX;
  const directionY = (order.commandY ?? order.y) - order.cohortOriginY;
  const length = Math.hypot(directionX, directionY);
  if (length <= 1e-12) return null;
  const candidates = snapshot.filter((candidate) => (
    candidate.alive
      && isHostile(unit, candidate)
      // Visibility reaches the near edge of the target obstruction, not only
      // its center. The first live Paladin lock is recorded at 5.236 center
      // tiles with LOS 5 and a 0.25 target collision half-extent.
      && Math.hypot(candidate.x - unit.x, candidate.y - unit.y)
        - collisionRadius(candidate)
        <= unit.mechanics.line_of_sight_tiles + 1e-12
  ));
  candidates.sort((left, right) => {
    const lateral = (candidate) => Math.abs(
      (candidate.x - order.cohortOriginX) * directionY
        - (candidate.y - order.cohortOriginY) * directionX,
    ) / length;
    return lateral(left) - lateral(right)
      || openingHash(order.openingSeed, unit.owner, left.referenceId)
        - openingHash(order.openingSeed, unit.owner, right.referenceId)
      || left.referenceId - right.referenceId;
  });
  return candidates[0] ?? null;
}


function selectCentralPatrolContactLanes(unit, snapshot, order, roster) {
  const cohort = snapshot.filter((candidate) => (
    candidate.alive && candidate.owner === unit.owner
  ));
  const originX = cohort.reduce((total, candidate) => total + candidate.x, 0)
    / cohort.length;
  const originY = cohort.reduce((total, candidate) => total + candidate.y, 0)
    / cohort.length;
  const directionX = (order.commandX ?? order.x) - originX;
  const directionY = (order.commandY ?? order.y) - originY;
  const length = Math.hypot(directionX, directionY);
  if (length <= 1e-12) return null;
  const projected = roster.map((candidate) => ({
    candidate,
    lateral: (
      (candidate.x - originX) * -directionY
        + (candidate.y - originY) * directionX
    ) / length,
  }));
  const negative = projected
    .filter(({ lateral }) => lateral < 0)
    .sort((left, right) => Math.abs(left.lateral) - Math.abs(right.lateral)
      || left.candidate.referenceId - right.candidate.referenceId)[0];
  const positive = projected
    .filter(({ lateral }) => lateral >= 0)
    .sort((left, right) => Math.abs(left.lateral) - Math.abs(right.lateral)
      || left.candidate.referenceId - right.candidate.referenceId)[0];
  const centralLanes = [negative, positive].filter(Boolean);
  if (centralLanes.length > 0) {
    return centralLanes.map(({ candidate }) => candidate);
  }
  return projected
    .sort((left, right) => Math.abs(left.lateral) - Math.abs(right.lateral)
      || left.candidate.referenceId - right.candidate.referenceId)
    .slice(0, Math.min(2, projected.length))
    .map(({ candidate }) => candidate);
}


function selectOpeningPatrolContactLanes(unit, snapshot, order, roster) {
  const lanes = selectCentralPatrolContactLanes(unit, snapshot, order, roster);
  if (!lanes || lanes.length < 2) return lanes;
  const directionX = (order.commandX ?? order.x) - order.cohortOriginX;
  const directionY = (order.commandY ?? order.y) - order.cohortOriginY;
  const length = Math.hypot(directionX, directionY);
  if (length <= 1e-12) return lanes;
  const lateral = (candidate) => Math.abs(
    (candidate.x - order.cohortOriginX) * -directionY
      + (candidate.y - order.cohortOriginY) * directionX,
  ) / length;
  return lanes.slice().sort((left, right) => (
    lateral(left) - lateral(right)
      || left.referenceId - right.referenceId
  ));
}


function selectPatrolFormationContactLanes(unit, snapshot, order, roster) {
  const directionX = (order.commandX ?? order.x) - order.cohortOriginX;
  const directionY = (order.commandY ?? order.y) - order.cohortOriginY;
  const length = Math.hypot(directionX, directionY);
  if (length <= 1e-12 || roster.length === 0) return null;
  const projected = roster.map((candidate) => {
    const x = candidate.moveOrder?.kind === "scenario-patrol"
        && Number.isFinite(candidate.moveOrder.formationStartX)
      ? candidate.moveOrder.formationStartX
      : candidate.x;
    const y = candidate.moveOrder?.kind === "scenario-patrol"
        && Number.isFinite(candidate.moveOrder.formationStartY)
      ? candidate.moveOrder.formationStartY
      : candidate.y;
    const relativeX = x - order.cohortOriginX;
    const relativeY = y - order.cohortOriginY;
    return {
      candidate,
      longitudinal: (relativeX * directionX + relativeY * directionY) / length,
      lateral: (relativeX * -directionY + relativeY * directionX) / length,
    };
  }).sort((left, right) => left.longitudinal - right.longitudinal
    || left.lateral - right.lateral
    || left.candidate.referenceId - right.candidate.referenceId);
  const ranks = [];
  for (const entry of projected) {
    const current = ranks.at(-1);
    if (!current
        || entry.longitudinal - current.at(-1).longitudinal
          > PATROL_FORMATION_RANK_GAP_TILES + 1e-12) {
      ranks.push([entry]);
    } else {
      current.push(entry);
    }
  }
  const front = ranks[0];
  const next = ranks[1] ?? null;
  const detachedFront = next !== null
    && next[0].longitudinal - front.at(-1).longitudinal
      >= PATROL_FORMATION_DETACHED_LEAD_GAP_TILES - 1e-12;
  const nearFront = ranks.filter((rank) => (
    rank[0].longitudinal
      <= front.at(-1).longitudinal + PATROL_MELEE_CONTACT_FRONT_DEPTH_TILES + 1e-12
  ));
  const selectedRank = detachedFront
    ? front
    : nearFront.slice().sort((left, right) => right.length - left.length
      || left[0].longitudinal - right[0].longitudinal
      || left[0].candidate.referenceId - right[0].candidate.referenceId)[0];
  const lateral = selectedRank.slice().sort((left, right) => left.lateral - right.lateral
    || left.longitudinal - right.longitudinal
    || left.candidate.referenceId - right.candidate.referenceId);
  const main = lateral[Math.floor((lateral.length - 1) / 2)];
  if (detachedFront) {
    if (unit.mechanics?.ranged && next?.length > 0) {
      // A detached melee leader is the ranged formation's principal first
      // target, but the adjacent rank remains a small fallback lane. In the
      // fresh tape 24 of 27 Arbalesters take the leader and three take that
      // adjacent body. Melee pursuers still collapse onto the detached body;
      // their physical contact-capture mechanic performs any redistribution.
      const adjacent = next.slice().sort((left, right) => (
        Math.abs(left.lateral - main.lateral)
          - Math.abs(right.lateral - main.lateral)
        || left.candidate.referenceId - right.candidate.referenceId
      ))[0];
      return [main.candidate, adjacent.candidate];
    }
    return [main.candidate];
  }
  if (lateral.length < 3) {
    if (unit.mechanics?.ranged && next?.length > 0) {
      const adjacent = next.slice().sort((left, right) => (
        Math.abs(left.lateral - main.lateral)
          - Math.abs(right.lateral - main.lateral)
        || left.candidate.referenceId - right.candidate.referenceId
      ))[0];
      return [main.candidate, adjacent.candidate];
    }
    return [main.candidate];
  }
  return [main, lateral[0], lateral.at(-1)]
    .filter((entry, index, entries) => entries.indexOf(entry) === index)
    .slice(0, PATROL_CONTACT_LANE_LIMIT)
    .map(({ candidate }) => candidate);
}


function selectGeometricPatrolLaneIndex(unit, snapshot, order, referenceIds) {
  const directionX = (order.commandX ?? order.x) - order.cohortOriginX;
  const directionY = (order.commandY ?? order.y) - order.cohortOriginY;
  const length = Math.hypot(directionX, directionY);
  if (length <= 1e-12) return 0;
  const lateral = (candidate) => (
    (candidate.x - order.cohortOriginX) * -directionY
      + (candidate.y - order.cohortOriginY) * directionX
  ) / length;
  const actorLateral = lateral(unit);
  const targets = referenceIds
    .map((referenceId, index) => ({
      index,
      candidate: snapshot.find((possible) => possible.referenceId === referenceId),
    }))
    .filter(({ candidate }) => candidate)
    .sort((left, right) => lateral(left.candidate) - lateral(right.candidate)
      || left.candidate.referenceId - right.candidate.referenceId);
  if (targets.length === 0) return 0;
  if (targets.length === 1) return targets[0].index;
  const cohortSize = snapshot.filter((candidate) => (
    candidate.alive && candidate.owner === unit.owner
  )).length;
  const hostileSize = snapshot.filter((candidate) => (
    candidate.alive && isHostile(unit, candidate)
  )).length;
  const severelyOutnumbered = cohortSize * 2 < hostileSize;
  const auxiliarySurface = targets.every(({ candidate }) => candidate.owner === 4);
  // An auxiliary screen exposes spatial contact lanes, not one global
  // principal body. Across the thirty current Onager/melee tapes, a 27-member
  // patrol normally divides its first locks roughly 9-18 across the two
  // central scouts (with only occasional locks on an adjacent scout). The
  // previous one-in-eight fallback forced 23/4 and collapsed the whole melee
  // formation into one shell-sized knot. Assign the nearest lateral lane from
  // current geometry; opening randomness remains only an exact-tie breaker.
  if (auxiliarySurface && targets.length === 2) {
    const lateralChoice = targets.slice().sort((left, right) => (
      Math.abs(lateral(left.candidate) - actorLateral)
        - Math.abs(lateral(right.candidate) - actorLateral)
        || openingHash(
          order.openingSeed ?? 0,
          unit.owner,
          left.candidate.referenceId ^ unit.referenceId,
        ) - openingHash(
          order.openingSeed ?? 0,
          unit.owner,
          right.candidate.referenceId ^ unit.referenceId,
        )
        || left.candidate.referenceId - right.candidate.referenceId
    ))[0];
    return lateralChoice.index;
  }
  const rangedScenarioPatrol = unit.moveOrder?.kind === "scenario-patrol"
    && unit.mechanics?.ranged === true;
  if ((unit.moveOrder?.kind === "opening-patrol" || rangedScenarioPatrol)
      && targets.length >= 2) {
    // Direct melee PATROLs overwhelmingly share the principal central body:
    // across the five 18v27 captures, only 0-2 Elephants and 1-6 Camels use
    // the second visible lane. Preserve that small fraction, but select its
    // members by lateral geometry so a seed cannot move one fallback lock
    // between unrelated formation rows and reorganize the entire collision
    // flow. No later target, path, attack time, damage, or outcome is assigned.
    const primary = targets.find(({ index }) => index === 0) ?? targets[0];
    const secondary = targets.find(({ index }) => index === 1) ?? targets[1];
    const cohort = snapshot.filter((candidate) => (
      candidate.alive && candidate.owner === unit.owner
    ));
    const secondaryCount = Math.max(1, Math.round(cohort.length / 8));
    const secondaryIds = new Set(cohort.map((candidate) => ({
      candidate,
      // Choose the members for whom the secondary lane is the smallest
      // lateral detour relative to the principal lane. Formation order breaks
      // exact geometric ties; a seed must not move a lane assignment between
      // unrelated rows of the authored formation.
      affinity: Math.abs(lateral(secondary.candidate) - lateral(candidate))
        - Math.abs(lateral(primary.candidate) - lateral(candidate)),
    })).sort((left, right) => left.affinity - right.affinity
      || left.candidate.referenceId - right.candidate.referenceId)
      .slice(0, secondaryCount)
      .map(({ candidate }) => candidate.referenceId));
    return secondaryIds.has(unit.referenceId) ? secondary.index : primary.index;
  }
  // Principal contact lanes are spatial: left, centre, and right members of
  // the approaching cohort acquire the corresponding visible front body.
  // Current geometry—not roster identity or desired outcome—therefore assigns
  // the lane. Opening hash is only an exact-tie breaker.
  const lanePenalty = ({ index }) => {
    // A small firing cohort facing a front more than twice its size has enough
    // exposed lateral surface for every member to retain its geometric lane.
    // The 7-vs-27 Onager repeats consistently split the six opening locks
    // across lower/upper bodies instead of collapsing onto the command-axis
    // principal. Comparable 17/18/27-body ranged fronts are not in this
    // regime and retain their measured principal-lane bias.
    if (severelyOutnumbered) return 0;
    if (index === 0) return 0;
    return index === 1
      ? PATROL_OPENING_NEAR_FLANK_PENALTY_TILES
      : PATROL_OPENING_FAR_FLANK_PENALTY_TILES;
  };
  return targets.slice().sort((left, right) => (
    Math.abs(lateral(left.candidate) - actorLateral)
      + lanePenalty(left)
      - Math.abs(lateral(right.candidate) - actorLateral)
      - lanePenalty(right)
    || openingHash(order.openingSeed ?? 0, unit.owner,
      left.candidate.referenceId ^ unit.referenceId)
      - openingHash(order.openingSeed ?? 0, unit.owner,
        right.candidate.referenceId ^ unit.referenceId)
    || left.candidate.referenceId - right.candidate.referenceId
  ))[0].index;
}


function selectPatrolCohortOpeningTargets(unit, snapshot, order) {
  // First confirm that shared player vision has exposed at least one hostile
  // body. The game's group decision then names a cohort anchor set, including
  // for members that do not individually see every anchor yet. Target choice
  // is the explicitly permitted opening stochastic boundary; roster order is stable
  // scenario input and is never consulted by subsequent retargeting.
  if (order.sharedVisionPrimed !== true
      && selectPatrolOpeningTarget(unit, snapshot, order) === null) return null;
  const roster = snapshot.filter((candidate) => candidate.alive && isHostile(unit, candidate));
  if (roster.length === 0) return null;
  const cohortSize = snapshot.filter((candidate) => (
    candidate.alive && candidate.owner === unit.owner
  )).length;
  const auxiliaryFront = roster.every(({ owner }) => owner === 4);
  if (auxiliaryFront) {
    // The live auxiliary screen exposes two central contact lanes: the scouts
    // immediately to either side of the approaching cohort's command axis.
    // Select those lanes from current geometry after shared vision confirms
    // contact. This generalizes to any placement, type, and army size without
    // encoding the golden scouts' IDs or an observed outcome.
    const lanes = selectCentralPatrolContactLanes(unit, snapshot, order, roster);
    // A cohort no more than twice the width of the auxiliary screen commits
    // its first lock to one central breach. Only a much larger cohort exposes
    // both central lanes. The fresh 15-v-9 Ratha capture assigns all fifteen
    // first locks to the same scout before physical contact redistributes
    // them; the existing 27-v-9 captures expose both lanes. This depends only
    // on current army sizes and still ends at first acquisition.
    return cohortSize <= 2 * roster.length ? lanes?.slice(0, 1) ?? null : lanes;
  }
  if (order.kind === "opening-patrol") {
    // The direct golden melee PATROL presents the two bodies immediately to
    // either side of the command axis as its shared opening contact surface.
    // Live 18v27 and 27v18 formations assign every first lock to those two
    // bodies (usually with a dominant principal lane), rather than letting
    // each unit independently choose a different nearest body. This is only
    // the explicitly permitted first-target boundary; later retargeting is
    // ordinary current-geometry AI.
    return selectOpeningPatrolContactLanes(unit, snapshot, order, roster);
  }
  const hostileFrontIsRanged = roster.every(({ mechanics }) => mechanics?.ranged);
  if (!hostileFrontIsRanged) {
    // A moving melee formation is acquired through its current leading contact
    // surface. The live 14/19/20/23/24/27-body fronts expose at most three such
    // lanes; detached leaders naturally collapse the set to one. This remains
    // strictly inside the permitted first-acquisition boundary.
    // Use the authored group lanes for both principal and auxiliary cohorts:
    // temporary compression before a delayed first scan must not rewrite the
    // patrol formation's contact surface.
    return selectPatrolFormationContactLanes(unit, snapshot, order, roster);
  }
  const directionX = (order.commandX ?? order.x) - order.cohortOriginX;
  const directionY = (order.commandY ?? order.y) - order.cohortOriginY;
  const length = Math.hypot(directionX, directionY);
  if (length <= 1e-12) return null;
  const projected = roster.map((candidate) => {
    const relativeX = candidate.x - order.cohortOriginX;
    const relativeY = candidate.y - order.cohortOriginY;
    return {
      candidate,
      longitudinal: (relativeX * directionX + relativeY * directionY) / length,
      lateral: (relativeX * -directionY + relativeY * directionX) / length,
    };
  });
  const leading = Math.min(...projected.map(({ longitudinal }) => longitudinal));
  const frontBand = projected
    .filter(({ longitudinal }) => (
      longitudinal <= leading + PATROL_OPENING_FRONT_BAND_TILES + 1e-12
    ))
    .sort((left, right) => left.lateral - right.lateral
      || left.longitudinal - right.longitudinal
      || left.candidate.referenceId - right.candidate.referenceId);
  // A ranged PATROL first names the body closest to its command axis. The
  // exposed lateral edges are bounded fallbacks for members that are already
  // far from that principal lane; they are not an evenly sampled assignment
  // pool. This is the permitted first-acquisition boundary only. Once a lock
  // dies, ordinary geometry/contact AI owns every subsequent choice.
  const principal = frontBand.slice().sort((left, right) => (
    Math.abs(left.lateral) - Math.abs(right.lateral)
      || left.longitudinal - right.longitudinal
      || left.candidate.referenceId - right.candidate.referenceId
  ))[0];
  if (order.kind === "scenario-patrol" && order.sharedVisionPrimed === true) {
    // A trigger-issued follow-up PATROL does not collapse an experienced
    // melee cohort onto the ranged front's single leading body. At the
    // diplomacy gate the player already has shared vision, and the game's
    // formation lanes stay distributed across the exposed firing rank. The
    // 2026-09-02 Ratha/Arbalester tape has twelve surviving melee units take
    // five distinct first post-gate locks (maximum load five); the ordinary
    // three-anchor opening policy often collapsed the simulator onto one.
    //
    // Sample at most five evenly spaced lateral lanes from the same geometric
    // front band used by every PATROL. This avoids the opposite error of
    // treating all deep ranged bodies as approach goals. No target ID, unit
    // type, elapsed time, or outcome is encoded here.
    const laneCount = Math.min(
      EXPERIENCED_MELEE_RANGED_FRONT_LANE_LIMIT,
      frontBand.length,
    );
    const lanes = [];
    for (let index = 0; index < laneCount; index += 1) {
      const position = laneCount === 1
        ? 0
        : Math.round(index * (frontBand.length - 1) / (laneCount - 1));
      lanes.push(frontBand[position]);
    }
    const middle = Math.floor((lanes.length - 1) / 2);
    lanes[middle] = principal;
    return lanes
      .filter((entry, index, entries) => entries.indexOf(entry) === index)
      .map(({ candidate }) => candidate);
  }
  const below = frontBand.filter(({ lateral, candidate }) => (
    candidate.referenceId !== principal.candidate.referenceId
      && lateral < principal.lateral
  ));
  const above = frontBand.filter(({ lateral, candidate }) => (
    candidate.referenceId !== principal.candidate.referenceId
      && lateral >= principal.lateral
  ));
  const lowerEdge = below[0] ?? null;
  const upperEdge = above.at(-1) ?? null;
  const actorLateral = (
    (unit.x - order.cohortOriginX) * -directionY
      + (unit.y - order.cohortOriginY) * directionX
  ) / length;
  const nearSideIsLower = actorLateral < principal.lateral
    || (Math.abs(actorLateral - principal.lateral) <= 1e-12
      && openingHash(order.openingSeed ?? 0, unit.owner, unit.referenceId) % 2 === 0);
  const nearFlank = nearSideIsLower ? lowerEdge ?? upperEdge : upperEdge ?? lowerEdge;
  const farFlank = nearFlank === lowerEdge ? upperEdge : lowerEdge;
  const anchorCount = Math.min(
    frontBand.length,
    cohortSize >= roster.length ? 2 : PATROL_CONTACT_LANE_LIMIT,
  );
  return [principal, nearFlank, farFlank]
    .filter((entry, index, entries) => entry !== null && entries.indexOf(entry) === index)
    .slice(0, anchorCount)
    .map(({ candidate }) => candidate);
}


function validateInitialAttackState(units) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const unit of units) {
    if (unit.action !== "attacking") {
      if (unit.attackTargetId !== null) {
        throw new Error(
          `${unit.action} unit ${unit.referenceId} must not retain attackTargetId`,
        );
      }
      continue;
    }
    const target = byReference.get(unit.attackTargetId);
    if (!target?.alive || !isHostile(unit, target)) {
      throw new Error(
        `attacking unit ${unit.referenceId} attackTargetId must reference a live enemy`,
      );
    }
    const windup = unit.actionTimers.windup;
    const maximumWindup = attackDelayTicks(unit.mechanics);
    if (
      !Number.isSafeInteger(windup)
      || windup <= 0
      || windup > maximumWindup
      || unit.actionTimers.reload !== 0
    ) {
      throw new Error(
        `attacking unit ${unit.referenceId} must have a coherent windup and zero reload`,
      );
    }
  }
}


export function createWorld(scenario) {
  if (!scenario || typeof scenario !== "object") {
    throw new TypeError("scenario is required");
  }
  const map = scenario.map ? freezeMap(scenario.map) : DEFAULT_MAP;
  if (scenario.disableAiOrders !== undefined && typeof scenario.disableAiOrders !== "boolean") {
    throw new TypeError("disable AI orders must be boolean");
  }
  const preparedUnits = applyOpeningPatrol(
    scenario.units,
    scenario.openingPatrolByOwner,
    map,
    scenario.openingSeed ?? 0,
  );
  const scenarioOwners = Object.freeze([...new Set(preparedUnits.map(({ owner }) => owner))]
    .sort((left, right) => left - right));
  let diplomacyByOwner = createDiplomacyByOwner(
    scenarioOwners,
    scenario.diplomacyByOwner,
  );
  let mutablePreparedUnits = preparedUnits.map((unit) => (
    withDiplomacy(mutableUnit(unit), diplomacyByOwner)
  ));
  const triggers = compileScenarioTriggers(scenario.triggers, scenarioOwners, map);
  if (scenario.openingSeed !== undefined
      && (!Number.isSafeInteger(scenario.openingSeed) || scenario.openingSeed < 0)) {
    throw new RangeError("opening seed must be a nonnegative safe integer");
  }
  let scenarioTriggerState = triggers.length === 0
    ? null
    : Object.freeze({
      triggers,
      firedTriggerIds: Object.freeze([]),
      defeatedOwners: Object.freeze([]),
      openingSeed: scenario.openingSeed ?? 0,
    });
  const creationEvents = [];
  if (scenarioTriggerState) {
    const initial = fireEligibleScenarioTriggers(
      mutablePreparedUnits,
      diplomacyByOwner,
      scenarioTriggerState,
      0,
      creationEvents,
    );
    diplomacyByOwner = initial.diplomacyByOwner;
    scenarioTriggerState = initial.triggerState;
  }
  initializeSpecialEffects(mutablePreparedUnits);
  const units = canonicalUnits(mutablePreparedUnits, { cloneMechanics: true });
  validateInitialAttackState(units);
  const victoryTeams = compileVictoryTeams(scenarioOwners, scenario.victoryTeams);
  const meleeOwners = [...new Set(units
    .filter(hasMeleeMode)
    .map(({ owner }) => owner))]
    .sort((left, right) => left - right);
  const contactReservationState = createContactReservationState({
    // Trigger-authored PATROL orders retain zero-obstruction formation
    // transit. Once a unit peels off to attack, its allies become
    // path-obstructing DAT bodies, matching the user's move-vs-attack
    // distinction in the current golden captures.
    alliedTransitPathObstructs: triggers.length > 0,
  });
  if (scenario.rangedTargetPressureOwner !== undefined
      && !Number.isSafeInteger(scenario.rangedTargetPressureOwner)) {
    throw new TypeError("ranged target pressure owner must be a safe integer");
  }
  if (Number.isSafeInteger(scenario.rangedTargetPressureOwner)
      && !units.some(({ owner }) => owner === scenario.rangedTargetPressureOwner)) {
    throw new RangeError("ranged target pressure owner must identify a scenario owner");
  }
  if (scenario.rangedWindupRetargetOwner !== undefined
      && !Number.isSafeInteger(scenario.rangedWindupRetargetOwner)) {
    throw new TypeError("ranged windup retarget owner must be a safe integer");
  }
  if (Number.isSafeInteger(scenario.rangedWindupRetargetOwner)
      && !units.some(({ owner }) => owner === scenario.rangedWindupRetargetOwner)) {
    throw new RangeError("ranged windup retarget owner must identify a scenario owner");
  }
  const events = Object.freeze(creationEvents);
  const aiOrderSweepStartSeconds = scenario.aiOrderSweepStartSeconds;
  if (aiOrderSweepStartSeconds !== undefined
      && (!Number.isFinite(aiOrderSweepStartSeconds) || aiOrderSweepStartSeconds < 0)) {
    throw new RangeError("AI order sweep start seconds must be nonnegative and finite");
  }
  const aiOrderSweepStartTick = aiOrderSweepStartSeconds === undefined
    ? undefined
    : Math.round(aiOrderSweepStartSeconds * TICKS_PER_SECOND);
  const kiteState = Number.isSafeInteger(scenario.kiteOwner)
    ? createKiteState(
      scenario.kiteOwner,
      scenario.kiteProfile ?? null,
      scenario.chaseCapture === true,
      scenario.kitedEscape === true,
      scenario.soloMovement === true,
    )
    : null;
  if (scenario.kiteOpponentMode !== undefined
      && scenario.kiteOpponentMode !== "ordinary-ranged") {
    throw new RangeError("kite opponent mode must be ordinary-ranged");
  }
  if (scenario.kiteOpponentMode === "ordinary-ranged") {
    if (!kiteState) {
      throw new RangeError("kite opponent mode requires a kiting owner");
    }
    kiteState.opponentMode = "ordinary-ranged";
  }
  if (scenario.persistentMeleePursuitRouting === true) {
    if (!kiteState) {
      throw new RangeError("persistent melee pursuit routing requires a kiting owner");
    }
    kiteState.persistentMeleePursuitRouting = true;
    kiteState.chaseRoutes = new Map();
  } else if (scenario.persistentMeleePursuitRouting !== undefined
      && scenario.persistentMeleePursuitRouting !== false) {
    throw new TypeError("persistent melee pursuit routing must be boolean");
  }
  let contactSteeringStates = null;
  if (kiteState) kiteState.collisionRecoveryState = { active: false };
  if (scenario.kiteChaseDwellTicks !== undefined) {
    if (!kiteState) {
      throw new RangeError("kite chase dwell requires a kiting owner");
    }
    if (!Number.isSafeInteger(scenario.kiteChaseDwellTicks)
        || scenario.kiteChaseDwellTicks < 0) {
      throw new RangeError("kite chase dwell must be a nonnegative integer");
    }
    kiteState.chaseDwellTicks = scenario.kiteChaseDwellTicks;
  }
  const navigationVariant = scenario.kiteNavigation
    ?? (kiteState?.soloMovement === true ? scenario.soloNavigation ?? "baseline" : null);
  if (kiteState && navigationVariant !== null) {
    kiteState.soloNavigationState = createSoloNavigationState(
      navigationVariant,
      units.filter((unit) => unit.owner === kiteState.owner),
      map,
      kiteState.profile,
    );
  }
  if (kiteState && scenario.kiteMeleeOpeningOrder === "attack-move-all") {
    kiteState.meleeOpeningOrder = "attack-move-all";
    kiteState.meleeApproach = new Map();
  }
  if (scenario.attackMoveTargetPressureTiles !== undefined) {
    if (!kiteState || scenario.kiteMeleeOpeningOrder !== "attack-move-all") {
      throw new RangeError("attack-move target pressure requires a kiting attack-move scenario");
    }
    if (!Number.isFinite(scenario.attackMoveTargetPressureTiles)
        || scenario.attackMoveTargetPressureTiles < 0) {
      throw new RangeError("attack-move target pressure must be nonnegative and finite");
    }
    kiteState.attackMoveTargetPressureTiles = scenario.attackMoveTargetPressureTiles;
  }
  if (scenario.attackMoveStickyPursuit === true) {
    if (!kiteState || scenario.kiteMeleeOpeningOrder !== "attack-move-all") {
      throw new RangeError("sticky attack-move pursuit requires a kiting attack-move scenario");
    }
    kiteState.attackMoveStickyPursuit = true;
  }
  if (scenario.preventiveContactSteering === true) {
    if (meleeOwners.length === 0) {
      throw new RangeError("preventive contact steering requires a melee unit");
    }
    const strength = scenario.preventiveContactSteeringStrength
      ?? PREVENTIVE_CONTACT_STEERING_STRENGTH;
    if (!Number.isFinite(strength) || strength < 0 || strength > 1) {
      throw new RangeError("preventive contact steering strength must be between 0 and 1");
    }
    contactSteeringStates = new Map(meleeOwners.map((owner) => [owner, {
      owner,
      strength,
      steeredSteps: 0,
      steeredUnits: new Set(),
    }]));
  }
  const snapshot = createSnapshot(0, units, events,
    soloNavigationSnapshot(kiteState?.soloNavigationState));
  // Charge-projectile flight queue, present only when the roster can fire one
  // (Fire Lancer family) so worlds without charge units keep their exact
  // published shape.
  const anyCharge = units.some((unit) => (
    chargeSpec(unit.mechanics) !== null || rangedSpec(unit.mechanics) !== null
  ));
  const anyHazard = units.some((unit) => (
    (unitEffects(unit).impact_hazard_radius_tiles ?? 0) > 0
  ));
  return Object.freeze({
    // Experiment-only mutable AI-player state; absent in baseline so world
    // shape and hashes are unchanged (the object is frozen but Maps inside
    // stay mutable across ticks by design).
    ...(ORDERS_ENABLED && scenario.disableAiOrders !== true ? {
      orderState: createOrderState(units, aiOrderSweepStartTick === undefined
        ? undefined
        : { sweepStartTick: aiOrderSweepStartTick }),
    } : {}),
    // Kiting-side beat controller (see issueKiteOrders): present only when
    // the scenario names a kiting owner, so every other world keeps its
    // exact published shape.
    ...(kiteState ? { kiteState } : {}),
    ...(Number.isSafeInteger(scenario.rangedTargetPressureOwner)
      ? { rangedTargetPressureOwner: scenario.rangedTargetPressureOwner }
      : {}),
    ...(Number.isSafeInteger(scenario.rangedWindupRetargetOwner)
      ? { rangedWindupRetargetOwner: scenario.rangedWindupRetargetOwner }
      : {}),
    scenarioOwners,
    diplomacyByOwner,
    victoryTeams,
    ...(scenarioTriggerState ? { scenarioTriggerState } : {}),
    ...(scenarioTriggerState || units.some(({ moveOrder }) => (
      moveOrder?.kind === "opening-patrol"
    )) ? { patrolOpeningTargetByOwner: new Map() } : {}),
    contactReservationState,
    contactReservationDiagnostics: Object.freeze([]),
    ...(contactSteeringStates ? { contactSteeringStates } : {}),
    ...(anyCharge ? { projectiles: Object.freeze([]) } : {}),
    ...(anyHazard ? { hazards: Object.freeze([]) } : {}),
    // Deterministic per-shot RNG, present only when a unit can miss or blast.
    // A simulation seed must reproduce one complete stochastic fight, so it
    // also selects the projectile-spread stream. Seed zero preserves the
    // historical stream; other seeds no longer replay identical scatter.
    // State lives outside units so no unit hash can move.
    ...(units.some((unit) => {
      const spec = rangedSpec(unit.mechanics);
      return spec && (spec.accuracyPercent < 100
        || spec.baseAccuracyPercent < 100
        || spec.blastRadius > 0 || spec.secondaryCount > 0
        || (spec.extraProjectileCount + spec.firstAttackExtraProjectiles > 0
          && spec.spawnArea.some((dimension) => dimension > 0)));
    }) ? { shotRng: { state: (20260411 ^ (scenario.openingSeed ?? 0)) >>> 0 } } : {}),
    tick: 0,
    ratio: scenario.ratio,
    mapHash: scenario.mapHash,
    map,
    units,
    events,
    eventLog: events,
    snapshots: Object.freeze([snapshot]),
  });
}


function validatePursuitTargets(units, tick, events) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const unit of units) {
    if (!unit.alive) {
      unit.pursuitTargetId = null;
      unit.engagedTargetId = null;
      unit.attackTargetId = null;
      unit.avoidance = null;
      unit.action = "dead";
      delete unit.attackKind;
      delete unit.pendingVolley;
      delete unit.moveOrder;
      unit.actionTimers = { windup: 0, reload: 0, swing: 0, acquire: 0 };
      continue;
    }
    if (unit.pursuitTargetId === null || unit.pursuitTargetId === undefined) continue;
    const target = byReference.get(unit.pursuitTargetId);
    if (target?.alive) {
      if (!isHostile(unit, target)) {
        throw new Error(
          `unit ${unit.referenceId} has friendly/non-hostile pursuit target ${target.referenceId}`,
        );
      }
      continue;
    }

    const invalidTargetId = unit.pursuitTargetId;
    events.push(event(
      tick,
      "pursuit-invalidated",
      unit.referenceId,
      invalidTargetId,
      { reason: "target-dead" },
    ));
    unit.pursuitTargetId = null;
    unit.avoidance = null;
    if (unit.moveOrder?.kind === "scenario-patrol") {
      unit.patrolFormationTransit = true;
    }
  }
}


function validateAttackTargets(units, tick, events, rangedWindupRetargetOwner = null) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const unit of units) {
    if (!unit.alive || unit.action !== "attacking") continue;
    const target = byReference.get(unit.attackTargetId);
    if (target?.alive && isHostile(unit, target)) continue;
    const invalidTargetId = unit.attackTargetId;
    if (!Number.isSafeInteger(invalidTargetId)) {
      throw new Error(`attacking unit ${unit.referenceId} has no captured attack target`);
    }
    // A swing that has already released its hit runs to the end of its animation
    // even though the target is gone -- that is what makes a killer slower to
    // pick a new target than the bystanders swinging at the same corpse. Only an
    // unreleased swing is abandoned on the spot. A charge cycle releases on its
    // own (later) frame; an abandoned unreleased charge keeps its charge.
    const releaseTicks = unit.attackKind === "charge"
      ? chargeSpec(unit.mechanics).windupTicks
      : unit.attackKind === "melee-charge"
        ? meleeChargeSpec(unit.mechanics).windupTicks
        : attackDelayTicksForUnit(unit);
    if (unit.actionTimers.swing >= releaseTicks) continue;
    if (unit.owner === rangedWindupRetargetOwner
        && rangedSpec(unit.mechanics) !== null
        && unit.attackKind !== "charge") {
      const replacement = selectPursuitTarget(
        { ...freezeUnit(unit), pursuitTargetId: null },
        Object.freeze(units
          .filter((candidate) => (
            !isHostile(unit, candidate)
            || (candidate.alive && isWithinReach(unit, candidate))
          ))
          .map(freezeUnit)),
      );
      if (replacement !== null) {
        unit.pursuitTargetId = replacement.referenceId;
        unit.engagedTargetId = replacement.referenceId;
        unit.attackTargetId = replacement.referenceId;
        unit.avoidance = null;
        events.push(event(
          tick,
          "attack-retargeted",
          unit.referenceId,
          replacement.referenceId,
          {
            fromTargetId: invalidTargetId,
            swingTick: unit.actionTimers.swing,
            releaseTicks,
            remainingWindupTicks: Math.max(0, releaseTicks - unit.actionTimers.swing),
          },
        ));
        continue;
      }
    }
    events.push(createAttackCanceledEvent({
      tick,
      actorId: unit.referenceId,
      targetId: invalidTargetId,
      readyTick: tick + Math.max(0, releaseTicks - unit.actionTimers.swing),
      reason: !target?.alive ? "target-dead" : "target-invalidated",
    }));
    unit.attackTargetId = null;
    const abandonedCharge = unit.attackKind === "charge";
    delete unit.attackKind;
    unit.actionTimers.windup = 0;
    unit.actionTimers.swing = 0;
    // Reload belongs to a released weapon cycle. Full-rate tapes show ranged
    // units whose victim dies during wind-up leave Action 7 for pursuit within
    // 0.02-0.07 s; they do not enter the weapon's full reload state. Refunding
    // an unreleased ordinary swing lets the unit acquire and aim again while
    // preserving a charge weapon's separately accumulated charge.
    if (!abandonedCharge) unit.actionTimers.reload = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
  }
}


function acquirePursuitTargets(
  units,
  tick,
  events,
  kiteState = null,
  rangedTargetPressureOwner = null,
  patrolOpeningTargetByOwner = null,
  pursuitRecoveryState = null,
  map = DEFAULT_MAP,
  pairInteractions = createPairInteractionSnapshot(),
) {
  const snapshot = Object.freeze(units.map(freezeUnit));
  const targetPressureTiles = kiteState?.attackMoveTargetPressureTiles ?? 0;
  // Once a ranged PATROL member has completed its seeded first acquisition,
  // every later acquisition is ordinary unit AI. Those simultaneous cohort
  // scans account for already claimed targets so a whole firing line does not
  // pile every replacement shot onto the same nearest body. This is a patrol
  // mechanic, not an outcome parameter; the opening assignment remains under
  // the explicit first-target exception above.
  const automaticPatrolPressure = (unit) => (
    !hasMeleeMode(unit)
      && unit.moveOrder?.kind === "scenario-patrol"
      && unit.openingAcquisitionComplete === true
      && snapshot.some((candidate) => (
        candidate.alive && isHostile(unit, candidate) && hasMeleeMode(candidate)
      ))
  );
  const automaticPatrolPressureActive = units.some((unit) => (
    unit.alive && automaticPatrolPressure(unit)
  ));
  const targetLoadById = targetPressureTiles > 0
      || Number.isSafeInteger(rangedTargetPressureOwner)
    ? new Map()
    : null;
  const automaticTargetCountById = automaticPatrolPressureActive ? new Map() : null;
  const onagerOpeningTargetCountById = new Map();
  for (const unit of units) {
    if (!unit.alive || !hasOnagerFamilyBehavior(unit)
        || unit.moveOrder?.kind !== "scenario-patrol"
        || unit.openingAcquisitionComplete !== true
        || !Number.isSafeInteger(unit.pursuitTargetId)) continue;
    const target = snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId);
    if (!target?.alive || !isHostile(unit, target)) continue;
    onagerOpeningTargetCountById.set(
      target.referenceId,
      (onagerOpeningTargetCountById.get(target.referenceId) ?? 0) + 1,
    );
  }
  if (targetLoadById || automaticTargetCountById) {
    for (const unit of units) {
      const kitePressureApplies = targetPressureTiles > 0
        && unit.owner !== kiteState.owner;
      const configuredRangedPressureApplies = unit.owner === rangedTargetPressureOwner;
      const automaticPressureApplies = automaticPatrolPressure(unit)
        && !kitePressureApplies && !configuredRangedPressureApplies;
      if (!unit.alive || (!kitePressureApplies
          && !configuredRangedPressureApplies && !automaticPressureApplies)) continue;
      if (unit.pursuitTargetId === null || unit.pursuitTargetId === undefined) continue;
      const load = automaticPressureApplies ? automaticTargetCountById : targetLoadById;
      load.set(
        unit.pursuitTargetId,
        (load.get(unit.pursuitTargetId) ?? 0) + 1,
      );
    }
  }
  // Vision is shared by a player. Before servicing this tick's opening wave,
  // let any member of the still-patrolling cohort reveal the opening anchor
  // set; then every unit whose AI slot is due receives its stable member of
  // that set.
  if (patrolOpeningTargetByOwner !== null) {
    const openingOwners = [...new Set(units
      .filter((unit) => unit.alive
        && (unit.moveOrder?.kind === "scenario-patrol"
          || unit.moveOrder?.kind === "opening-patrol")
        && unit.openingAcquisitionComplete !== true
        && (unit.moveOrder.kind === "scenario-patrol"
          ? tick >= unit.moveOrder.nextOpeningScanTick
          : unit.actionTimers.acquire <= 1))
      .map(({ owner }) => owner))]
      .sort((left, right) => left - right);
    for (const owner of openingOwners) {
      if (patrolOpeningTargetByOwner.has(owner)) continue;
      const detectors = units.filter((unit) => unit.alive && unit.owner === owner
        && (unit.moveOrder?.kind === "scenario-patrol"
          || unit.moveOrder?.kind === "opening-patrol")
        && unit.openingAcquisitionComplete !== true);
      for (const detector of detectors) {
        const targets = selectPatrolCohortOpeningTargets(
          detector,
          snapshot,
          detector.moveOrder,
        );
        if (targets === null) continue;
        patrolOpeningTargetByOwner.set(owner, Object.freeze(
          targets.map(({ referenceId }) => referenceId),
        ));
        break;
      }
    }
  }
  for (const unit of units) {
    if (!unit.alive) continue;
    const patrolOpeningOrder = (unit.moveOrder?.kind === "scenario-patrol"
      || unit.moveOrder?.kind === "opening-patrol")
      && unit.openingAcquisitionComplete !== true
      ? unit.moveOrder
      : null;
    const scenarioPatrolOrder = patrolOpeningOrder?.kind === "scenario-patrol"
      ? patrolOpeningOrder
      : null;
    // Initial target-acquisition delay. Only the first acquisition waits; once a
    // unit has been in combat, re-acquisition is governed by its swing state.
    // A group PATROL scans on the game AI's shared opening cadence. Units that
    // do not yet have line of sight remain in formation until the next scan;
    // they do not poll continuously on every render tick.
    if (scenarioPatrolOrder) {
      if (tick < scenarioPatrolOrder.nextOpeningScanTick) continue;
      unit.actionTimers.acquire = 0;
    } else if (unit.actionTimers.acquire > 0) {
      unit.actionTimers.acquire -= 1;
      // Acquire on the very tick the delay expires, so no unit is ever briefly
      // idle with an expired timer and no target.
      if (unit.actionTimers.acquire > 0) continue;
    }
    // Onager-family combat has one small minimum-range state machine. A legal
    // backward or side-backward step keeps the current lock and movement will
    // execute that retreat below. If the current body graph and map leave no
    // retreat heading, choose another visible target that is outside minimum
    // range. This is current geometry only: no elapsed-time or matchup rule is
    // involved, and Rocket Cart variants inherit it through behaviorFamily.
    const minimumRangeThreat = hasOnagerFamilyBehavior(unit)
        && unit.action !== "attacking"
      ? selectedMinimumRangeThreat(unit, snapshot)
      : null;
    if (minimumRangeThreat
        && !onagerRetreatHeadingAvailable(
          unit,
          minimumRangeThreat.target,
          snapshot,
          map,
          pairInteractions,
        )) {
      const alternate = selectOnagerMinimumRangeAlternate(unit, snapshot);
      if (alternate) {
        const previousTargetId = unit.pursuitTargetId;
        unit.pursuitTargetId = alternate.referenceId;
        unit.engagedTargetId = null;
        unit.attackTargetId = null;
        unit.avoidance = null;
        pursuitRecoveryState?.routes.delete(unit.referenceId);
        pursuitRecoveryState?.attempts.delete(unit.referenceId);
        pursuitRecoveryState?.retargetReady.delete(unit.referenceId);
        pursuitRecoveryState?.routeFailures.delete(unit.referenceId);
        pursuitRecoveryState?.failedTargets.delete(unit.referenceId);
        events.push(event(tick, "pursuit-acquired", unit.referenceId,
          alternate.referenceId, {
            reason: "minimum-range-retarget",
            previousTargetId,
          }));
        continue;
      }
    }
    // A ranged PATROL's first acquired body is a committed opening lock. In
    // the full-rate Onager traces every actor's first acquisition target is
    // also its first attack target, including actors that have to close for
    // more than a second. Path recovery may still steer toward that body, but
    // it must not replace the lock before the first attack begins. After that
    // boundary all ordinary opportunity and recovery retargeting resumes.
    if (!hasMeleeMode(unit)
        && unit.moveOrder?.kind === "scenario-patrol"
        && unit.openingAcquisitionComplete === true
        && unit.patrolOpeningAttackStarted !== true
        && Number.isSafeInteger(unit.pursuitTargetId)) {
      continue;
    }
    // A unit following a recovery detour may naturally reveal or enter range
    // of a different enemy. That is a real acquisition opportunity, not a
    // desired-output assignment: choose the nearest newly legal target using
    // only current geometry. If the route itself proved unavailable, perform
    // one ordinary line-of-sight acquisition excluding the blocked target.
    if (pursuitRecoveryState && unit.action !== "attacking") {
      const routeActive = pursuitRecoveryState.routes.has(unit.referenceId);
      const current = Number.isSafeInteger(unit.pursuitTargetId)
        ? snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId)
        : null;
      if (routeActive && current?.alive && isHostile(unit, current)
          && isWithinReach(unit, current)) {
        pursuitRecoveryState.routes.delete(unit.referenceId);
        pursuitRecoveryState.attempts.delete(unit.referenceId);
        pursuitRecoveryState.nextRetargetScanTick.delete(unit.referenceId);
        pursuitRecoveryState.routeFailures.delete(unit.referenceId);
        pursuitRecoveryState.failedTargets.delete(unit.referenceId);
      }
      const retargetReady = pursuitRecoveryState.retargetReady.has(unit.referenceId);
      // PATROL recovery scans for a newly reachable body on the same ordinary
      // AI rescan cadence as patrol acquisition. The motion/path itself still
      // advances every tick; only changing its selected pursuit target is an
      // AI decision. Polling this branch at 60 Hz made a blocked formation
      // churn through substantially more target IDs than the live group while
      // crossing the same body screen. Non-patrol pursuit keeps the immediate
      // recovery behavior.
      const nextRetargetScanTick = pursuitRecoveryState.nextRetargetScanTick
        .get(unit.referenceId) ?? 0;
      const scenarioPatrol = unit.moveOrder?.kind === "scenario-patrol";
      const recoveryScanDue = !scenarioPatrol
        || tick >= nextRetargetScanTick;
      const opportunity = recoveryScanDue && (routeActive || retargetReady)
          && current?.alive && !isWithinReach(unit, current)
        ? recoveryOpportunityTarget(unit, snapshot)
        : null;
      const alternate = opportunity ?? (
        recoveryScanDue && retargetReady
          ? recoveryAlternateTarget(
            unit,
            snapshot,
            pursuitRecoveryState,
            map,
            pairInteractions,
          )
          : null
      );
      if (recoveryScanDue && (routeActive || retargetReady)
          && scenarioPatrol) {
        pursuitRecoveryState.nextRetargetScanTick.set(
          unit.referenceId,
          tick + Math.round(PATROL_RESCAN_SECONDS * TICKS_PER_SECOND),
        );
      }
      if (alternate) {
        const previousTargetId = unit.pursuitTargetId;
        unit.pursuitTargetId = alternate.referenceId;
        unit.engagedTargetId = null;
        unit.avoidance = null;
        if (unit.moveOrder?.kind === "scenario-patrol") {
          unit.patrolFormationTransit = false;
        }
        pursuitRecoveryState.routes.delete(unit.referenceId);
        pursuitRecoveryState.attempts.delete(unit.referenceId);
        pursuitRecoveryState.retargetReady.delete(unit.referenceId);
        pursuitRecoveryState.routeFailures.delete(unit.referenceId);
        if (opportunity) pursuitRecoveryState.failedTargets.delete(unit.referenceId);
        if (alternate.referenceId !== previousTargetId) {
          events.push(event(tick, "pursuit-acquired", unit.referenceId,
            alternate.referenceId, {
              reason: opportunity
                ? "blocked-route-opportunity"
                : "blocked-route-unavailable",
              previousTargetId,
            }));
        }
        continue;
      }
      // A recovery request is a durable pathing state, not a one-frame event.
      // If this scan cannot yet see a reachable alternate, keep it armed for
      // the next AI scan instead of sending the unit back through five more
      // failed pushes against the same unreachable body screen.
    }
    // Experiment harness (docs/RETARGETING_INVESTIGATION.md). Off by default:
    // shouldReevaluatePursuit is false unless AOE2X_EXP_PURSUIT is set, so this
    // reduces to the original `if (pursuitTargetId !== null) continue`.
    const blockedAttackMover = kiteState?.meleeOpeningOrder === "attack-move-all"
      && unit.owner !== kiteState.owner
      && kiteState.attackMoveStickyPursuit !== true
      && unit.experimentBlocked === true;
    const pursued = unit.pursuitTargetId === null
      ? null
      : snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId);
    // Any ranged unit abandons an out-of-range pursuit when another hostile is
    // already inside its firing envelope. This is ordinary geometry-driven
    // target selection and therefore applies identically to every owner.
    const rangedOpportunity = !hasMeleeMode(unit)
      && !(unit.moveOrder?.kind === "scenario-patrol"
        && unit.openingAcquisitionComplete === true
        && unit.patrolOpeningAttackStarted !== true)
      && pursued?.alive === true
      && !isWithinReach(unit, pursued)
      && snapshot.some((candidate) => (
        candidate.alive
        && isHostile(unit, candidate)
        && isWithinReach(unit, candidate)
      ));
    const reevaluate = unit.pursuitTargetId !== null
      && (shouldReevaluatePursuit(unit) || blockedAttackMover || rangedOpportunity);
    if (unit.pursuitTargetId !== null && !reevaluate) continue;
    const kitePressureApplies = targetPressureTiles > 0
      && unit.owner !== kiteState.owner;
    const configuredRangedPressureApplies = unit.owner === rangedTargetPressureOwner;
    const automaticPressureApplies = automaticPatrolPressure(unit)
      && !kitePressureApplies && !configuredRangedPressureApplies;
    const pressureApplies = kitePressureApplies
      || configuredRangedPressureApplies || automaticPressureApplies;
    const pressureTiles = configuredRangedPressureApplies || automaticPressureApplies
      ? 2 * collisionRadius(unit)
      : targetPressureTiles;
    if (pressureApplies && reevaluate) {
      const load = automaticPressureApplies ? automaticTargetCountById : targetLoadById;
      const previousLoad = load.get(unit.pursuitTargetId) ?? 0;
      if (previousLoad <= 1) load.delete(unit.pursuitTargetId);
      else load.set(unit.pursuitTargetId, previousLoad - 1);
    }
    const effectiveTargetLoadById = automaticPressureApplies
      ? new Map(snapshot.filter((possible) => (
        possible.alive && isHostile(unit, possible) && hasMeleeMode(possible)
      )).map((possible) => {
        const assigned = automaticTargetCountById.get(possible.referenceId) ?? 0;
        return [
          possible.referenceId,
          Math.max(0, assigned - PATROL_RETARGET_SOFT_CAPACITY + 1),
        ];
      }))
      : targetLoadById;
    const found = snapshot.find(({ referenceId }) => referenceId === unit.referenceId);
    // selectPursuitTarget short-circuits on a live locked target, so a
    // re-evaluation has to present the unit as unlocked to force a fresh scan.
    const candidate = reevaluate ? { ...found, pursuitTargetId: null } : found;
    const scenarioPatrol = patrolOpeningOrder;
    const lockedPatrolTargetIds = scenarioPatrol
      ? patrolOpeningTargetByOwner?.get(unit.owner)
      : null;
    const hasLockedPatrolTarget = Array.isArray(lockedPatrolTargetIds)
      && lockedPatrolTargetIds.length > 0;
    const auxiliaryOpeningFront = hasLockedPatrolTarget
      && lockedPatrolTargetIds.every((referenceId) => (
        snapshot.find((possible) => possible.referenceId === referenceId)?.owner === 4
      ));
    // Patrol formation lanes are spatial assignments. Once shared vision has
    // exposed a contact surface, each cohort member keeps the best lateral
    // lane instead of being evenly hashed across the opposing front. Opening
    // randomness remains only as an exact-tie breaker.
    const geometricPatrolLanes = hasLockedPatrolTarget
      && lockedPatrolTargetIds.length > 1;
    const gateAnchorIndex = hasLockedPatrolTarget
      ? geometricPatrolLanes
        ? selectGeometricPatrolLaneIndex(
          unit, snapshot, scenarioPatrol, lockedPatrolTargetIds,
        )
        : openingHash(
          scenarioPatrol.openingSeed ?? 0,
          unit.owner,
          unit.referenceId,
        ) % lockedPatrolTargetIds.length
      : null;
    const gatePatrolTarget = hasLockedPatrolTarget
      ? snapshot.find((possible) => (
        possible.referenceId === lockedPatrolTargetIds[gateAnchorIndex]
          && possible.alive
          && isHostile(unit, possible)
          && (auxiliaryOpeningFront || scenarioPatrol.sharedVisionPrimed === true
            || Math.hypot(possible.x - unit.x, possible.y - unit.y)
              - collisionRadius(possible)
              <= unit.mechanics.line_of_sight_tiles + 1e-12)
      )) ?? null
      : null;
    const lockedPatrolTargetId = hasLockedPatrolTarget
      ? lockedPatrolTargetIds[gateAnchorIndex]
      : null;
    const lockedPatrolTarget = gatePatrolTarget
      ? snapshot.find((possible) => (
        possible.referenceId === lockedPatrolTargetId
          && possible.alive
          && isHostile(unit, possible)
      )) ?? null
      : null;
    const target = scenarioPatrol
      ? hasOnagerFamilyBehavior(unit)
        ? selectPursuitTarget(candidate, snapshot, {
          targetLoadById: new Map([...onagerOpeningTargetCountById].map(([
            referenceId,
            count,
          ]) => [
            referenceId,
            Math.max(0, count - ONAGER_OPENING_SOFT_TARGET_CAPACITY + 1),
          ])),
          targetLoadPenaltyTiles: collisionRadius(unit),
        })
        : hasLockedPatrolTarget
          ? lockedPatrolTarget
          : selectPatrolOpeningTarget(candidate, snapshot, scenarioPatrol)
      : selectPursuitTarget(candidate, snapshot, pressureApplies
        ? { targetLoadById: effectiveTargetLoadById, targetLoadPenaltyTiles: pressureTiles }
        : undefined);
    if (target === null) {
      if (scenarioPatrol) {
        unit.moveOrder = Object.freeze({
          ...scenarioPatrol,
          nextOpeningScanTick: tick + Math.round(PATROL_RESCAN_SECONDS * TICKS_PER_SECOND),
        });
      }
      if (pressureApplies && reevaluate) {
        const load = automaticPressureApplies ? automaticTargetCountById : targetLoadById;
        load.set(
          unit.pursuitTargetId,
          (load.get(unit.pursuitTargetId) ?? 0) + 1,
        );
      }
      continue;
    }
    if (pressureApplies) {
      const load = automaticPressureApplies ? automaticTargetCountById : targetLoadById;
      load.set(target.referenceId, (load.get(target.referenceId) ?? 0) + 1);
    }
    if (scenarioPatrol && hasOnagerFamilyBehavior(unit)) {
      onagerOpeningTargetCountById.set(
        target.referenceId,
        (onagerOpeningTargetCountById.get(target.referenceId) ?? 0) + 1,
      );
    }
    if (target.referenceId !== unit.pursuitTargetId) {
      events.push(event(tick, "pursuit-acquired", unit.referenceId, target.referenceId));
    }
    if (scenarioPatrol && patrolOpeningTargetByOwner !== null
        && !patrolOpeningTargetByOwner.has(unit.owner)) {
      patrolOpeningTargetByOwner.set(unit.owner, Object.freeze([target.referenceId]));
    }
    unit.pursuitTargetId = target.referenceId;
    unit.openingAcquisitionComplete = true;
    // A scenario PATROL is suspended—not destroyed—while combat pursuit owns
    // the unit. If that target is later lost outside shared vision, the unit
    // resumes toward the authored patrol point and keeps scanning. A plain
    // opening-patrol remains one-shot setup behavior.
    if (unit.moveOrder?.kind === "scenario-patrol") {
      unit.patrolFormationTransit = false;
    } else if (unit.moveOrder?.kind === "opening-patrol") {
      delete unit.moveOrder;
      delete unit.patrolFormationTransit;
    }
  }
}


function compileScenarioTriggers(rawTriggers, owners, map) {
  if (rawTriggers === undefined) return Object.freeze([]);
  if (!Array.isArray(rawTriggers)) throw new TypeError("scenario triggers must be an array");
  const ownerSet = new Set(owners);
  const ids = new Set();
  return Object.freeze(rawTriggers.map((raw, index) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      throw new TypeError("scenario trigger must be an object");
    }
    const id = raw.trigger_index ?? raw.id ?? index;
    if (!Number.isSafeInteger(id) || id < 0 || ids.has(id)) {
      throw new RangeError("scenario trigger IDs must be unique nonnegative integers");
    }
    ids.add(id);
    if (raw.looping === true) {
      throw new RangeError("looping scenario triggers are not implemented");
    }
    const conditions = raw.conditions ?? [];
    if (!Array.isArray(conditions)) throw new TypeError("trigger conditions must be an array");
    const compiledConditions = Object.freeze(conditions.map((condition) => {
      if (condition?.type !== "player_defeated") {
        throw new RangeError(`unknown scenario trigger condition ${condition?.type}`);
      }
      const sourceOwner = condition.source_player;
      if (!Number.isSafeInteger(sourceOwner) || !ownerSet.has(sourceOwner)) {
        throw new RangeError("player-defeated condition must identify a scenario owner");
      }
      return Object.freeze({ type: "player-defeated", sourceOwner });
    }));
    if (!Array.isArray(raw.effects) || raw.effects.length === 0) {
      throw new RangeError("scenario trigger must contain at least one effect");
    }
    const effects = Object.freeze(raw.effects.map((effect) => {
      if (effect?.type === "change_diplomacy") {
        const sourceOwner = effect.source_player;
        const targetOwner = effect.target_player;
        if (!Number.isSafeInteger(sourceOwner) || !ownerSet.has(sourceOwner)
            || !Number.isSafeInteger(targetOwner) || !ownerSet.has(targetOwner)
            || sourceOwner === targetOwner) {
          throw new RangeError("diplomacy effect must identify two scenario owners");
        }
        if (![DIPLOMACY.ALLY, DIPLOMACY.NEUTRAL, DIPLOMACY.ENEMY]
          .includes(effect.diplomacy)) {
          throw new RangeError("diplomacy effect has an invalid relation");
        }
        return Object.freeze({
          type: "change-diplomacy",
          sourceOwner,
          targetOwner,
          diplomacy: effect.diplomacy,
          mutual: effect.mutual === true,
        });
      }
      if (effect?.type === "patrol") {
        const owner = effect.owner;
        const x = effect.x;
        const y = effect.y;
        if (!Number.isSafeInteger(owner) || !ownerSet.has(owner)) {
          throw new RangeError("patrol effect owner must identify a scenario owner");
        }
        if (!Number.isFinite(x) || !Number.isFinite(y)
            || x < 0 || x >= map.width || y < 0 || y >= map.height) {
          throw new RangeError("patrol effect destination must be inside the map");
        }
        const area = effect.area ?? { x1: 0, y1: 0, x2: map.width, y2: map.height };
        for (const name of ["x1", "y1", "x2", "y2"]) {
          if (!Number.isFinite(area[name])) {
            throw new TypeError("patrol selection area coordinates must be finite");
          }
        }
        if (area.x1 > area.x2 || area.y1 > area.y2) {
          throw new RangeError("patrol selection area must be ordered");
        }
        return Object.freeze({
          type: "patrol",
          owner,
          x,
          y,
          area: Object.freeze({ ...area }),
        });
      }
      throw new RangeError(`unknown scenario trigger effect ${effect?.type}`);
    }));
    return Object.freeze({
      id,
      name: typeof raw.name === "string" ? raw.name : `Trigger ${id}`,
      conditions: compiledConditions,
      effects,
    });
  }));
}


function compileVictoryTeams(owners, rawTeams = undefined) {
  const orderedOwners = [...owners].sort((left, right) => left - right);
  const teams = rawTeams ?? orderedOwners.map((owner) => ({
    winnerOwner: owner,
    owners: [owner],
  }));
  if (!Array.isArray(teams) || teams.length === 0) {
    throw new TypeError("victory teams must be a nonempty array");
  }
  const seen = new Set();
  const ownerSet = new Set(orderedOwners);
  const compiled = teams.map((team) => {
    if (!team || typeof team !== "object" || !Array.isArray(team.owners)
        || team.owners.length === 0) {
      throw new TypeError("victory team must contain owners");
    }
    if (!Number.isSafeInteger(team.winnerOwner) || !team.owners.includes(team.winnerOwner)) {
      throw new RangeError("victory team winner must be one of its owners");
    }
    const members = [...team.owners].sort((left, right) => left - right);
    for (const owner of members) {
      if (!ownerSet.has(owner) || seen.has(owner)) {
        throw new RangeError("victory teams must partition the scenario owners");
      }
      seen.add(owner);
    }
    return Object.freeze({
      winnerOwner: team.winnerOwner,
      owners: Object.freeze(members),
    });
  });
  if (seen.size !== ownerSet.size) {
    throw new RangeError("victory teams must include every scenario owner");
  }
  return Object.freeze(compiled);
}


function triggerConditionsMet(trigger, defeatedOwners) {
  return trigger.conditions.every((condition) => (
    condition.type === "player-defeated" && defeatedOwners.has(condition.sourceOwner)
  ));
}


function unitInsideArea(unit, area) {
  return unit.x >= area.x1 && unit.x <= area.x2
    && unit.y >= area.y1 && unit.y <= area.y2;
}


function applyPatrolEffect(units, effect, trigger, tick, events) {
  const ownerOpeningHash = openingHash(trigger.openingSeed ?? 0, effect.owner, 0);
  const openingFraction = ownerOpeningHash / 0xffffffff;
  const cohort = units.filter((unit) => (
    unit.alive && unit.owner === effect.owner && unitInsideArea(unit, effect.area)
  ));
  // A seeded subset of already-visible members services the early shared-LOS
  // AI slots. Other visible members remain on the ordinary group scan. Across
  // the five seven-Onager repeats, 1-3 of the six non-detached members lock in
  // the 0.60-0.80 s wave (10/30 member-runs), with the rest predominantly on
  // the 1.51-1.61 s wave. This stays inside the explicitly stochastic
  // first-acquisition boundary and prescribes no later target, route, attack,
  // or outcome. Guaranteeing one detector avoids an empty early wave in a
  // small cohort while the per-member 1/3 draw preserves measured variance.
  const visibleRangedMembers = cohort.filter((unit) => (
    hasOnagerFamilyBehavior(unit)
      && Boolean(unit.mechanics?.ranged)
      && units.some((candidate) => (
        candidate.alive
          && isHostile(unit, candidate)
          && Math.hypot(candidate.x - unit.x, candidate.y - unit.y)
            <= unit.mechanics.line_of_sight_tiles + 1e-12
      ))
  ));
  const visibleByOpeningDraw = visibleRangedMembers.slice().sort((left, right) => (
    openingHash(trigger.openingSeed ?? 0, effect.owner, right.referenceId)
      - openingHash(trigger.openingSeed ?? 0, effect.owner, left.referenceId)
    || left.referenceId - right.referenceId
  ));
  const earlyVisibleDetectorIds = new Set(visibleByOpeningDraw.filter((unit) => (
    openingHash(trigger.openingSeed ?? 0, effect.owner, unit.referenceId) / 0xffffffff
      >= 1 - VISIBLE_ONAGER_PATROL_EARLY_SHARE
  )).map(({ referenceId }) => referenceId));
  if (earlyVisibleDetectorIds.size === 0 && visibleByOpeningDraw.length > 0) {
    earlyVisibleDetectorIds.add(visibleByOpeningDraw[0].referenceId);
  }
  // A genuinely detached ranged member is not serviced by the compact
  // formation's opening scan wave. In the five Onager repeats the isolated
  // seventh body (nearest friendly 2.83 tiles; formation spacing 1.41) first
  // locks at 6.18/16.38/17.58/33.36 s or not before the fight ends. Model
  // that generic first-acquisition latency with a seeded exponential tail.
  // This is the explicit first-target timing exception only: the member keeps
  // executing PATROL movement, and current visibility/geometry still chooses
  // the target when its AI slot is eventually serviced.
  const detachedFirstScanTickById = new Map();
  if (cohort.length >= 3) {
    for (const unit of cohort) {
      if (!hasOnagerFamilyBehavior(unit) || !unit.mechanics?.ranged) continue;
      const nearestFriendly = Math.min(...cohort
        .filter((other) => other.referenceId !== unit.referenceId)
        .map((other) => Math.hypot(other.x - unit.x, other.y - unit.y)));
      const seesHostileCentre = units.some((candidate) => (
        candidate.alive
          && isHostile(unit, candidate)
          && Math.hypot(candidate.x - unit.x, candidate.y - unit.y)
            <= unit.mechanics.line_of_sight_tiles + 1e-12
      ));
      if (nearestFriendly <= PATROL_DETACHED_ONAGER_MEMBER_GAP_TILES + 1e-12
          || seesHostileCentre) continue;
      const roll = openingHash(
        trigger.openingSeed ?? 0,
        effect.owner,
        unit.referenceId,
      ) / 4294967296;
      const seconds = DETACHED_ONAGER_PATROL_FIRST_SCAN_MIN_SECONDS
        - Math.log(1 - roll) * DETACHED_ONAGER_PATROL_FIRST_SCAN_MEAN_TAIL_SECONDS;
      detachedFirstScanTickById.set(
        unit.referenceId,
        tick + Math.round(seconds * TICKS_PER_SECOND),
      );
    }
  }
  const ordinaryFirstScanMinimum = effect.owner === 4
    ? AUXILIARY_PATROL_FIRST_SCAN_MIN_SECONDS
    : PATROL_FIRST_SCAN_MIN_SECONDS;
  const ordinaryFirstScanTick = tick + Math.round((
    ordinaryFirstScanMinimum
      + openingFraction * (PATROL_FIRST_SCAN_MAX_SECONDS - ordinaryFirstScanMinimum)
  ) * TICKS_PER_SECOND);
  const earlyFirstScanTick = tick + Math.round((
    VISIBLE_ONAGER_PATROL_FIRST_SCAN_MIN_SECONDS
      + openingFraction * (
        VISIBLE_ONAGER_PATROL_FIRST_SCAN_MAX_SECONDS
          - VISIBLE_ONAGER_PATROL_FIRST_SCAN_MIN_SECONDS
      )
  ) * TICKS_PER_SECOND);
  // Sparse Onager-family cohorts do not service every remaining member on one
  // shared scan. Across 30 live Onager/melee captures, first acquisitions are
  // distributed approximately 22% before 1 s, 45% at 1-2 s, 25% at 2-4 s,
  // and 8% in a longer tail. The early-visible subset above owns the first
  // band. Seed the other members into the ordinary wave, one/two 0.8-second
  // deferred rescans, or an exponential long tail. This is solely the allowed
  // first-acquisition timing policy; target choice remains current geometry
  // and no later movement, retarget, attack, damage, or outcome is prescribed.
  const onagerFirstScanTickById = new Map();
  for (const unit of cohort) {
    if (!hasOnagerFamilyBehavior(unit) || !unit.mechanics?.ranged
        || earlyVisibleDetectorIds.has(unit.referenceId)
        || detachedFirstScanTickById.has(unit.referenceId)) continue;
    const bandRoll = openingHash(
      trigger.openingSeed ?? 0,
      effect.owner,
      unit.referenceId ^ 0x5bd1e995,
    ) / 4294967296;
    if (bandRoll < ONAGER_PATROL_LONG_TAIL_SHARE) {
      const tailRoll = openingHash(
        trigger.openingSeed ?? 0,
        effect.owner,
        unit.referenceId ^ 0x27d4eb2d,
      ) / 4294967296;
      const seconds = ONAGER_PATROL_LONG_TAIL_MIN_SECONDS
        - Math.log(1 - tailRoll) * ONAGER_PATROL_LONG_TAIL_MEAN_SECONDS;
      onagerFirstScanTickById.set(
        unit.referenceId,
        tick + Math.round(seconds * TICKS_PER_SECOND),
      );
      continue;
    }
    if (bandRoll < ONAGER_PATROL_LONG_TAIL_SHARE
        + ONAGER_PATROL_DEFERRED_SCAN_SHARE) {
      const waves = 1 + openingHash(
        trigger.openingSeed ?? 0,
        effect.owner,
        unit.referenceId ^ 0x85ebca6b,
      ) % 2;
      onagerFirstScanTickById.set(
        unit.referenceId,
        ordinaryFirstScanTick
          + waves * Math.round(PATROL_RESCAN_SECONDS * TICKS_PER_SECOND),
      );
    }
  }
  const cohortOriginX = cohort.length === 0 ? effect.x : cohort.reduce(
    (total, unit) => total + unit.x, 0,
  ) / cohort.length;
  const cohortOriginY = cohort.length === 0 ? effect.y : cohort.reduce(
    (total, unit) => total + unit.y, 0,
  ) / cohort.length;
  for (const unit of cohort) {
    const combatExperienced = unit.openingAcquisitionComplete === true;
    unit.pursuitTargetId = null;
    unit.engagedTargetId = null;
    unit.attackTargetId = null;
    unit.avoidance = null;
    delete unit.attackKind;
    unit.actionTimers.windup = 0;
    unit.actionTimers.swing = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
    // Every authored PATROL command starts a new group-acquisition boundary.
    // The first command still pays the measured opening reaction delay. A
    // combat-experienced cohort that receives another patrol (for example
    // after a diplomacy trigger) already has its AI scan primed, so it shares
    // the newly visible hostile front on the next simulation tick instead of
    // dropping into per-unit private-LOS polling. Live mixed captures show
    // nearly every surviving melee unit holding a principal target within one
    // second of the Player-4 defeat, including members outside private LOS.
    unit.openingAcquisitionComplete = false;
    unit.patrolOpeningAttackStarted = false;
    unit.moveOrder = Object.freeze({
      kind: "scenario-patrol",
      // The scenario trigger issues one patrol destination to the selected
      // group. Individual combat pursuit takes over at first acquisition.
      x: effect.x,
      y: effect.y,
      commandX: effect.x,
      commandY: effect.y,
      cohortOriginX,
      cohortOriginY,
      formationStartX: unit.x,
      formationStartY: unit.y,
      issuedTick: tick,
      triggerId: trigger.id,
      openingSeed: trigger.openingSeed ?? 0,
      // A later patrol command is issued to a cohort that already participated
      // in the fight and therefore starts from player-shared contact knowledge.
      // This flag affects only that command's first target boundary; ordinary
      // post-acquisition pursuit and visibility remain unchanged.
      sharedVisionPrimed: combatExperienced,
      motionStartTick: tick + Math.round(PATROL_ORDER_REACTION_SECONDS * TICKS_PER_SECOND),
      nextOpeningScanTick: combatExperienced
        ? tick + 1
        : detachedFirstScanTickById.get(unit.referenceId)
          ?? onagerFirstScanTickById.get(unit.referenceId)
          ?? (earlyVisibleDetectorIds.has(unit.referenceId)
            ? earlyFirstScanTick
            : ordinaryFirstScanTick),
    });
  }
  events.push(event(tick, "patrol-issued", effect.owner, null, {
    owner: effect.owner,
    x: effect.x,
    y: effect.y,
    selected: cohort.length,
    triggerId: trigger.id,
  }));
}


function fireEligibleScenarioTriggers(
  units,
  diplomacyByOwner,
  triggerState,
  tick,
  events,
) {
  const fired = new Set(triggerState.firedTriggerIds);
  const defeated = new Set(triggerState.defeatedOwners);
  const patrolOwners = new Set();
  let diplomacy = diplomacyByOwner;
  for (const trigger of triggerState.triggers) {
    if (fired.has(trigger.id) || !triggerConditionsMet(trigger, defeated)) continue;
    fired.add(trigger.id);
    events.push(event(tick, "scenario-trigger-fired", trigger.id, null, {
      triggerId: trigger.id,
      name: trigger.name,
    }));
    for (const effect of trigger.effects) {
      if (effect.type === "change-diplomacy") {
        const prior = diplomacy[effect.sourceOwner][effect.targetOwner];
        diplomacy = changeDiplomacy(
          diplomacy,
          effect.sourceOwner,
          effect.targetOwner,
          effect.diplomacy,
          { mutual: effect.mutual },
        );
        for (let index = 0; index < units.length; index += 1) {
          units[index] = withDiplomacy(units[index], diplomacy);
        }
        events.push(event(tick, "diplomacy-changed", effect.sourceOwner, effect.targetOwner, {
          sourceOwner: effect.sourceOwner,
          targetOwner: effect.targetOwner,
          prior,
          diplomacy: effect.diplomacy,
          mutual: effect.mutual,
          triggerId: trigger.id,
        }));
      } else {
        patrolOwners.add(effect.owner);
        applyPatrolEffect(units, effect, {
          ...trigger,
          openingSeed: triggerState.openingSeed ?? 0,
        }, tick, events);
      }
    }
  }
  return {
    diplomacyByOwner: diplomacy,
    triggerState: Object.freeze({
      triggers: triggerState.triggers,
      firedTriggerIds: Object.freeze([...fired].sort((left, right) => left - right)),
      defeatedOwners: Object.freeze([...defeated].sort((left, right) => left - right)),
      openingSeed: triggerState.openingSeed ?? 0,
    }),
    patrolOwners: Object.freeze([...patrolOwners].sort((left, right) => left - right)),
  };
}


function advanceScenarioTriggers(world, units, tick, events) {
  if (!world.scenarioTriggerState) {
    return {
      diplomacyByOwner: world.diplomacyByOwner,
      triggerState: null,
      patrolOwners: Object.freeze([]),
    };
  }
  const defeated = new Set(world.scenarioTriggerState.defeatedOwners);
  for (const owner of world.scenarioOwners) {
    if (defeated.has(owner) || units.some((unit) => unit.alive && unit.owner === owner)) {
      continue;
    }
    defeated.add(owner);
    events.push(event(tick, "owner-defeated", owner, null, { owner }));
  }
  return fireEligibleScenarioTriggers(
    units,
    world.diplomacyByOwner,
    Object.freeze({
      ...world.scenarioTriggerState,
      defeatedOwners: Object.freeze([...defeated].sort((left, right) => left - right)),
      openingSeed: world.scenarioTriggerState.openingSeed ?? 0,
    }),
    tick,
    events,
  );
}


// A unit holding a FULL charge does not close on its target: all 265 tape
// volleys are fired from a standstill at the acquisition target, 1.5-5.2
// tiles out (line of sight is the bound), with the unit's first movement only
// after the charge animation completes. The charge cycle it is about to start
// (progressAttacks below) then pins it via `action === "attacking"`; once the
// charge is spent this returns false and normal pursuit resumes.
function holdsForChargeVolley(unit, target) {
  const spec = chargeSpec(unit.mechanics);
  if (!spec || !target) return false;
  if ((unit.charge ?? 0) + 1e-9 < spec.maxCharge) return false;
  if (unit.actionTimers.reload > 0) return false;
  const distance = Math.hypot(target.x - unit.x, target.y - unit.y);
  return distance <= spec.attackRangeTiles;
}


// Minimum-range retreat (scorpion family), measured on the svc tapes: a
// ranged unit with an enemy inside its dat min_range backs directly AWAY
// from the nearest such enemy in short bursts between shots — 545 recorded
// bursts trigger at nearest-champion p25 1.0 / p75 2.36 around the 2.0 min
// range, move-direction alignment with away-from-threat reaches 0.97 at p75,
// and the tape AI issues only ~2 orders per fight, so this is unit
// behaviour, not player micro. The chase still closes (champion 1.056 vs
// scorpion 0.65 tiles/s), which is what the recorded fights show.
function minRangeRetreat(unit, live) {
  const spec = unit.mechanics?.ranged;
  if (!spec || !(spec.min_range_tiles > 0)) return null;
  if (unit.action === "attacking") return null;
  let nearest = null;
  let nearestDistance = Infinity;
  if (hasOnagerFamilyBehavior(unit)) {
    // An Onager backs away from its SELECTED target. If that retreat is boxed
    // in, acquirePursuitTargets replaces the lock with another legal body and
    // this branch naturally stops retreating so the new shot can begin.
    const selected = selectedMinimumRangeThreat(unit, live);
    if (selected) {
      nearest = selected.target;
      nearestDistance = selected.distance;
    }
  } else {
    // Ordinary minimum-range ranged units react to the nearest pinner even
    // when they are currently aiming at somebody else.
    for (const other of live) {
      if (!isHostile(unit, other)) continue;
      const distance = Math.hypot(other.x - unit.x, other.y - unit.y);
      if (distance < spec.min_range_tiles - 1e-9 && distance < nearestDistance) {
        nearest = other;
        nearestDistance = distance;
      }
    }
  }
  if (!nearest || nearestDistance <= 1e-9) return null;
  const step = unit.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
  return Object.freeze({
    referenceId: unit.referenceId,
    dx: ((unit.x - nearest.x) / nearestDistance) * step,
    dy: ((unit.y - nearest.y) / nearestDistance) * step,
    movementIntent: "minimum-range-retreat",
  });
}


// Kited-world chase repath (measured, kac archives): the recorded chasers do
// not track their target's live position — their headings re-aim on a ~0.4-
// 0.5 s cadence and their realized speed is p50 0.89 of the 1.056 dat speed
// (path inefficiency), and their in-reach windows against a walking target
// last only ~0.7-1.4 s where frictionless per-tick tracking holds reach
// indefinitely (the sim glued tail produced 6-16 s windows the tape never
// shows). Chasers therefore walk toward their pursuit target's position as
// SAMPLED every repath interval, per-unit phased; the stop rule still tests
// the live target, so a chaser that genuinely closes still halts and swings.
const KITE_CHASE_REPATH_TICKS = Math.round(0.5 * TICKS_PER_SECOND);


// Genie movement is bimodal: a unit walks at its full dat speed or it stands
// still. Across the kiting tapes the heavy camel's per-frame speed is 46.1% at
// zero, 52.9% between 1.50 and 1.70 against a dat 1.595, and 0.6% anywhere in
// between -- there is no population that grinds along a body. The constraint
// solver manufactures one, because it resolves a blocked step by removing only
// its inward component and letting the remainder slide.
//
// A step the solver had to shorten is therefore taken as no step at all. It
// cannot be cancelled after the fact -- the solve is simultaneous, so a
// neighbour may have moved into the space this unit was going to vacate -- so
// the cancelled units are fed back in as stationary and the whole tick is
// re-solved until the set stops growing. Each pass only ever adds to that set,
// so it terminates, and the final pass is a normal solve with every invariant
// intact. See docs/CAMEL_CHASER_GEOMETRY_2026-08-06.md.
const MAX_BIMODAL_PASSES = 8;
// Floating-point tolerances only; no physical value is adjusted.
const STEP_EPSILON = 1e-9;
const ZERO_STEP_EPSILON = 1e-12;

// A blocked unit does not stop dead in front of the body: it walks around it,
// at full speed. Cancelling without this strands the kite formation the moment
// a chaser stands in its lane (duty cycle 0.18 against the tape's 0.79), and
// the tape shows no such stranding.
//
// The search is a discretization, not a physical constant: rotate the wanted
// heading in fixed increments and take the smallest turn whose full-speed step
// is clear, preferring the left-hand turn on a tie so the result stays
// deterministic. A unit that cannot clear its own body width within a quarter
// turn is genuinely walled in and stands, which is the tape's other mode.
const STEER_INCREMENT_RADIANS = Math.PI / 12;
const STEER_MAX_TURNS = 6;
const RECOVERY_STEER_MAX_TURNS = Math.round(Math.PI / STEER_INCREMENT_RADIANS);


function stepClearsBodies(mover, dx, dy, live, bounds, pairInteractions,
  includeNonObstructingContacts = false) {
  const x = mover.x + dx;
  const y = mover.y + dy;
  const radius = collisionRadius(mover);
  if (x < radius - STEP_EPSILON || x > bounds.width - radius + STEP_EPSILON
    || y < radius - STEP_EPSILON || y > bounds.height - radius + STEP_EPSILON) return false;
  for (const other of live) {
    if (other.referenceId === mover.referenceId) continue;
    const interaction = resolvePairInteraction(mover, other, pairInteractions);
    if (!interaction.pathObstructs && !includeNonObstructingContacts) continue;
    const extent = interaction.collisionExtent;
    if (Math.max(Math.abs(x - other.x), Math.abs(y - other.y)) < extent - STEP_EPSILON) {
      return false;
    }
  }
  return true;
}


function obstacleCollisionRadius(obstacle) {
  const radius = obstacle?.radius
    ?? obstacle?.collisionRadius
    ?? obstacle?.collision_radius;
  if (radius === undefined) return collisionRadius(obstacle);
  if (!Number.isFinite(radius) || radius <= 0) {
    throw new RangeError("map obstacle radius must be positive and finite");
  }
  return radius;
}


function stepClearsMapObstacles(mover, dx, dy, map) {
  const x = mover.x + dx;
  const y = mover.y + dy;
  const moverRadius = collisionRadius(mover);
  return (map.obstacles ?? []).every((obstacle) => (
    Math.max(Math.abs(x - obstacle.x), Math.abs(y - obstacle.y))
      >= moverRadius + obstacleCollisionRadius(obstacle) - STEP_EPSILON
  ));
}


function planBlockedPursuitEscape(mover, target, wantedDx, wantedDy, live, map,
  pairInteractions, recoveryAttempt = 0) {
  const stepLength = Math.hypot(wantedDx, wantedDy);
  if (stepLength <= ZERO_STEP_EPSILON) return null;
  const bounds = { width: map.width, height: map.height };
  const heading = Math.atan2(target.y - mover.y, target.x - mover.x);
  const preferPositive = (mover.referenceId + recoveryAttempt) % 2 === 0;
  const sides = preferPositive ? [1, -1] : [-1, 1];
  for (let turn = 1; turn <= RECOVERY_STEER_MAX_TURNS; turn += 1) {
    for (const side of sides) {
      const angle = heading + side * turn * STEER_INCREMENT_RADIANS;
      const dx = Math.cos(angle) * stepLength;
      const dy = Math.sin(angle) * stepLength;
      if (!stepClearsBodies(
        mover,
        dx,
        dy,
        live,
        bounds,
        pairInteractions,
        true,
      )
          || !stepClearsMapObstacles(mover, dx, dy, map)) continue;
      const escapeDistance = Math.max(
        collisionRadius(mover) * 2,
        stepLength + STEER_INCREMENT_RADIANS,
      );
      return Object.freeze({
        targetReferenceId: target.referenceId,
        targetX: target.x,
        targetY: target.y,
        waypoints: Object.freeze([Object.freeze({
          x: mover.x + Math.cos(angle) * escapeDistance,
          y: mover.y + Math.sin(angle) * escapeDistance,
        })]),
        waypointIndex: 0,
        recoveryKind: "local-escape",
      });
    }
  }
  return null;
}


// Does the wanted step hit at least one NON-TARGET enemy body? The chaser
// steer fires only then:
//   * ally blocks are a different regime -- KITER_FLOW measured real
//     chaser-on-chaser stalls in the tape (kac champions 13.2% stall rate);
//   * the mover's OWN pursuit/engagement target is the catch, not an
//     obstruction -- walking into it is how a chase ends, and deflecting
//     around it turns every would-be catch into an orbit (measured: with the
//     target counted as a blocker, every catching column flips -- kac 5v10,
//     esc 10v5, hcp 20v15, hcst 20v20 all lose their tape winner);
//   * a NON-target enemy body is the ball surface, which the camel forensics
//     show the chaser routing around at full speed.
function stepHitsAnyEnemyBody(mover, dx, dy, live, pairInteractions) {
  const x = mover.x + dx;
  const y = mover.y + dy;
  for (const other of live) {
    if (other.referenceId === mover.referenceId) continue;
    if (!areOpponents(mover, other)) continue;
    const interaction = resolvePairInteraction(mover, other, pairInteractions);
    if (!interaction.pathObstructs) continue;
    const extent = interaction.collisionExtent;
    if (Math.max(Math.abs(x - other.x), Math.abs(y - other.y)) < extent - STEP_EPSILON) {
      return true;
    }
  }
  return false;
}


function stepHitsOtherEnemyBody(mover, dx, dy, live, pairInteractions) {
  const x = mover.x + dx;
  const y = mover.y + dy;
  for (const other of live) {
    if (other.referenceId === mover.referenceId) continue;
    if (!areOpponents(mover, other)) continue;
    if (other.referenceId === mover.pursuitTargetId
      || other.referenceId === mover.engagedTargetId
      || other.referenceId === mover.attackTargetId) continue;
    const interaction = resolvePairInteraction(mover, other, pairInteractions);
    if (!interaction.pathObstructs) continue;
    const extent = interaction.collisionExtent;
    if (Math.max(Math.abs(x - other.x), Math.abs(y - other.y)) < extent - STEP_EPSILON) {
      return true;
    }
  }
  return false;
}




function steerProposals(planned, map, chaserScopeOwner = null, kitedEscape = false,
  movementOptions = {}) {
  const pairInteractions = movementOptions.pairInteractions
    ?? createPairInteractionSnapshot();
  const hasMinimumRangeRetreat = planned.proposals.some(({ movementIntent }) => (
    movementIntent === "minimum-range-retreat"
  ));
  if (!STEER_AROUND_BODIES && chaserScopeOwner === null && !hasMinimumRangeRetreat) {
    return { proposals: planned.proposals, steered: null };
  }
  const escapeActive = KITED_SIDE_STEER || kitedEscape;
  const bounds = { width: map.width, height: map.height };
  const byReference = new Map(planned.units.map((unit) => [unit.referenceId, unit]));
  const steered = new Set();
  const proposals = planned.proposals.map((proposal) => {
    const distance = Math.hypot(proposal.dx, proposal.dy);
    if (distance <= ZERO_STEP_EPSILON) return proposal;
    const mover = byReference.get(proposal.referenceId);
    if (!mover) return proposal;
    if (movementOptions.authoritativeReferenceIds?.has(mover.referenceId)) {
      return proposal;
    }
    const minimumRangeRetreat = proposal.movementIntent === "minimum-range-retreat";
    // "chaser" scope: only the chasing side of a kited scenario steers; the
    // kiting side (and every non-kited fight) keeps the baseline solver.
    // And only around NON-TARGET enemy bodies -- ally-blocked and
    // target-blocked chasers keep the baseline solver (the tape's stall and
    // catch regimes respectively).
    if (!minimumRangeRetreat && !STEER_AROUND_BODIES) {
      if (mover.owner === chaserScopeOwner) {
        // "kited": the kiting side's MOVE-ORDERED units steer around enemy
        // bodies too -- the tape's caught victim executes the scripted ball
        // move through attacker contact at the ball's own pace, where the
        // baseline solver grinds it on the pressing chaser's body. Units
        // without a move order (standing to shoot) keep the baseline. NO
        // target exclusion here: a kiter's target is who it SHOOTS -- most
        // often the very champion pressing it -- never a body it wants to
        // walk into.
        if (!escapeActive || !mover.moveOrder) return proposal;
        if (!stepHitsAnyEnemyBody(
          mover, proposal.dx, proposal.dy, planned.units, pairInteractions,
        )) {
          return proposal;
        }
      } else {
        // Steer only when the wanted step runs into a NON-TARGET enemy body
        // (the ball surface). Ally blocks keep the baseline solver (the
        // tape's chaser-on-chaser stalls are real), and the mover's own
        // target is the catch. Wider triggers were measured and rejected --
        // see the ally-queue ladder in HCC_CHASER_MOBILITY_2026-08-07.md.
        if (!stepHitsOtherEnemyBody(
          mover, proposal.dx, proposal.dy, planned.units, pairInteractions,
        )) {
          return proposal;
        }
      }
    }
    if (stepClearsBodies(mover, proposal.dx, proposal.dy, planned.units,
      bounds, pairInteractions)) return proposal;
    steered.add(proposal.referenceId);
    const heading = Math.atan2(proposal.dy, proposal.dx);
    // Retreaters keep a stable parity-selected side on symmetric choices.
    // This is deterministic per unit and avoids steering an entire siege
    // cohort into the same new queue. Recomputing around the current threat
    // heading each tick lets the route follow a moving pinner without a
    // calibrated turn timer.
    const sides = minimumRangeRetreat && mover.referenceId % 2 !== 0
      ? [-1, 1]
      : [1, -1];
    for (let turn = 1; turn <= STEER_MAX_TURNS; turn += 1) {
      for (const side of sides) {
        const angle = heading + side * turn * STEER_INCREMENT_RADIANS;
        const dx = Math.cos(angle) * distance;
        const dy = Math.sin(angle) * distance;
        if (stepClearsBodies(mover, dx, dy, planned.units, bounds,
          pairInteractions)) {
          return Object.freeze({ ...proposal, dx, dy });
        }
      }
    }
    return Object.freeze({ ...proposal, dx: 0, dy: 0 });
  });
  return { proposals, steered };
}


function resolveMovement(planned, byReference, map, kiteState = null, movementOptions = {}) {
  // "chaser" scope: steer-then-stop for the chasing side of a kited scenario
  // only. Without a kiteState (or for the kiting side) the solver is
  // untouched, so every non-kited fight stays bit-identical to baseline.
  const chaserScopeOwner = CHASER_BIMODAL_STEP && kiteState ? kiteState.owner : null;
  const { proposals: wantedProposals, steered } = steerProposals(
    planned,
    map,
    chaserScopeOwner,
    kiteState?.kitedEscape === true,
    movementOptions,
  );
  let moved = resolveMovementProposals(planned.units, wantedProposals, map, movementOptions);
  if (!BIMODAL_STEP && chaserScopeOwner === null) return moved;
  const eligible = (referenceId) => {
    if (BIMODAL_STEP) return true;
    // Scoped modes: cancellation applies only to steps the steer touched --
    // blocked by a (non-target) enemy body with no clear full-speed heading
    // nearby. The steered set only ever contains in-scope movers (chasers,
    // and under "kited" the move-ordered kiters too), so membership is the
    // whole test. Steps shortened by the mover's own target or by allies
    // keep the baseline partial resolve.
    return steered !== null && steered.has(referenceId);
  };
  const held = new Set();
  for (let pass = 0; pass < MAX_BIMODAL_PASSES; pass += 1) {
    const movedByReference = new Map(moved.map((unit) => [unit.referenceId, unit]));
    let grew = false;
    for (const proposal of wantedProposals) {
      if (held.has(proposal.referenceId)) continue;
      if (!eligible(proposal.referenceId)) continue;
      const wanted = Math.hypot(proposal.dx, proposal.dy);
      if (wanted <= ZERO_STEP_EPSILON) continue;
      const before = byReference.get(proposal.referenceId);
      const after = movedByReference.get(proposal.referenceId);
      if (!before || !after) continue;
      if (Math.hypot(after.x - before.x, after.y - before.y) < wanted - STEP_EPSILON) {
        held.add(proposal.referenceId);
        grew = true;
      }
    }
    if (!grew) return moved;
    moved = resolveMovementProposals(
      planned.units,
      wantedProposals.map((proposal) => (held.has(proposal.referenceId)
        ? Object.freeze({ referenceId: proposal.referenceId, dx: 0, dy: 0 })
        : proposal)),
      map,
      movementOptions,
    );
  }
  return moved;
}


function moveUnits(units, map, tick, events, kiteState = null,
  contactReservationState = null, contactSteeringStates = new Map(),
  pursuitRecoveryState = null) {
  const live = units.filter(({ alive }) => alive).map(freezeUnit);
  const allowedStartingOverlapReferenceIds = new Set(live.filter((unit) => (
    unit.specialState?.dismountCollisionRecovery === true
  )).map(({ referenceId }) => referenceId));
  const byReference = new Map(live.map((unit) => [unit.referenceId, unit]));
  let pairInteractions = createPairInteractionSnapshot({
    contactReservations: contactReservationState?.reservations ?? new Map(),
  });
  const soloDestinations = kiteState?.soloNavigationState
    ? planSoloNavigation(
      kiteState.soloNavigationState,
      live.filter((unit) => unit.owner === kiteState.owner),
      map,
      tick,
    )
    : null;
  if (kiteState && !kiteState.chaseWaypoints) kiteState.chaseWaypoints = new Map();
  if (kiteState?.persistentMeleePursuitRouting === true && !kiteState.chaseRoutes) {
    kiteState.chaseRoutes = new Map();
  }
  const authoritativeRouteReferenceIds = new Set();
  if (pursuitRecoveryState) {
    for (const referenceId of pursuitRecoveryState.routes.keys()) {
      const unit = byReference.get(referenceId);
      const target = byReference.get(unit?.pursuitTargetId);
      if (!unit?.alive || !target?.alive || !isHostile(unit, target)) {
        pursuitRecoveryState.routes.delete(referenceId);
        pursuitRecoveryState.attempts.delete(referenceId);
        pursuitRecoveryState.retargetReady.delete(referenceId);
        pursuitRecoveryState.routeFailures.delete(referenceId);
        pursuitRecoveryState.failedTargets.delete(referenceId);
      }
    }
  }
  if (kiteState?.chaseRoutes) {
    for (const referenceId of kiteState.chaseRoutes.keys()) {
      const unit = byReference.get(referenceId);
      const target = byReference.get(unit?.pursuitTargetId);
      if (!unit?.alive || unit.owner === kiteState.owner
          || !target?.alive || !isHostile(unit, target)) {
        kiteState.chaseRoutes.delete(referenceId);
      }
    }
  }
  const soloGridPath = kiteState?.soloNavigationState?.variant === "per-unit-grid"
    || kiteState?.soloNavigationState?.variant === "cohesive";
  if (kiteState?.profile?.kitedPath === "clearance_grid" || soloGridPath) {
    if (!kiteState.kitedWaypoints) kiteState.kitedWaypoints = new Map();
    for (const referenceId of kiteState.kitedWaypoints.keys()) {
      const unit = byReference.get(referenceId);
      if (!unit?.moveOrder || unit.owner !== kiteState.owner) {
        kiteState.kitedWaypoints.delete(referenceId);
      }
    }
  }
  const chaseAim = (unit, target) => {
    const recoveryRoutes = pursuitRecoveryState?.routes;
    let recoveryRoute = recoveryRoutes?.get(unit.referenceId) ?? null;
    if (recoveryRoute && recoveryRoute.targetReferenceId !== target.referenceId) {
      recoveryRoutes.delete(unit.referenceId);
      recoveryRoute = null;
    }
    if (recoveryRoute) {
      const advanced = advancePersistentChaseRoute(unit, recoveryRoute);
      if (advanced.waypointIndex !== recoveryRoute.waypointIndex) {
        events.push(event(tick, "pursuit-route-advanced", unit.referenceId,
          target.referenceId, {
            waypointIndex: advanced.waypointIndex,
            reason: "blocked-pursuit-recovery",
          }));
      }
      recoveryRoute = advanced;
      if (recoveryRoute.waypointIndex >= recoveryRoute.waypoints.length) {
        recoveryRoutes.delete(unit.referenceId);
        pursuitRecoveryState.routeFailures.delete(unit.referenceId);
        recoveryRoute = null;
      } else {
        recoveryRoutes.set(unit.referenceId, recoveryRoute);
      }
    }
    if (recoveryRoute) {
      authoritativeRouteReferenceIds.add(unit.referenceId);
      const waypoint = recoveryRoute.waypoints[recoveryRoute.waypointIndex];
      return Object.freeze({
        x: waypoint.x,
        y: waypoint.y,
        pathWaypoint: true,
        persistentRoute: true,
      });
    }
    // A direct two-army melee PATROL may plan around connected body geometry
    // before walking straight into its target front when it has enough surplus
    // pace to pay for the detour. Trigger-authored formation patrols instead
    // try direct pursuit first and receive the ordinary five-failed-step
    // recovery below; immediately solving their full body graph roughly
    // doubled the live firing-line access rate. A clear corridor still returns
    // null, while a blocked direct corridor supplies a stable tangent without
    // an oscillation detector or elapsed-time/output rule.
    if (hasMeleeMode(unit)
        && unit.openingAcquisitionComplete === true
        && unit.moveOrder?.kind !== "scenario-patrol"
        // Immediate full-route planning is a chase optimization: it applies
        // while the quarry is still executing a movement order. In a mutual
        // melee scrum, granting it solely to the faster unit lets that side
        // route perfectly from frame one while the slower side must use the
        // ordinary blocked-step recovery, creating a non-gameplay combat
        // advantage. Stationary/engaged targets therefore use the symmetric
        // five-failed-step recovery below.
        && kiteState
        && target.moveOrder
        && unit.mechanics.speed_tiles_per_second
          > target.mechanics.speed_tiles_per_second * 1.2
        && !isWithinReach(unit, target)) {
      const obstacles = live.filter((other) => (
        other.referenceId !== unit.referenceId
          && other.referenceId !== target.referenceId
      ));
      const plannedRoute = planPersistentChaseRoute(unit, target, obstacles, map, {
        pairInteractions,
      });
      if (plannedRoute && plannedRoute.stand !== true
          && plannedRoute.waypoints.length > 0) {
        recoveryRoutes.set(unit.referenceId, plannedRoute);
        authoritativeRouteReferenceIds.add(unit.referenceId);
        const waypoint = plannedRoute.waypoints[plannedRoute.waypointIndex];
        events.push(event(tick, "pursuit-route-planned", unit.referenceId,
          target.referenceId, {
            reason: "scenario-melee-obstruction",
            waypointCount: plannedRoute.waypoints.length,
            waypointIndex: plannedRoute.waypointIndex,
          }));
        return Object.freeze({
          x: waypoint.x,
          y: waypoint.y,
          pathWaypoint: true,
          persistentRoute: true,
        });
      }
    }
    if (!kiteState || unit.owner === kiteState.owner) return target;
    const obstacles = live.filter((other) => other.referenceId !== unit.referenceId
      && other.referenceId !== target.referenceId
      && other.referenceId !== unit.pursuitTargetId
      && other.referenceId !== unit.engagedTargetId
      && other.referenceId !== unit.attackTargetId);
    if (kiteState.persistentMeleePursuitRouting === true) {
      const routes = kiteState.chaseRoutes;
      let route = routes.get(unit.referenceId) ?? null;
      if (route && route.targetReferenceId !== target.referenceId) {
        routes.delete(unit.referenceId);
        events.push(event(tick, "pursuit-route-invalidated", unit.referenceId,
          route.targetReferenceId, { reason: "target-changed" }));
        route = null;
      }
      if (route) {
        const advanced = advancePersistentChaseRoute(unit, route);
        if (advanced.waypointIndex !== route.waypointIndex) {
          events.push(event(tick, "pursuit-route-advanced", unit.referenceId,
            target.referenceId, { waypointIndex: advanced.waypointIndex }));
        }
        route = advanced;
        if (route.waypointIndex >= route.waypoints.length) {
          routes.delete(unit.referenceId);
          route = null;
        } else {
          routes.set(unit.referenceId, route);
        }
      }
      if (!route) {
        route = planPersistentChaseRoute(unit, target, obstacles, map, {
          pairInteractions,
        });
        if (route?.stand === true) {
          return Object.freeze({ x: unit.x, y: unit.y, pathWaypoint: true });
        }
        if (route) {
          routes.set(unit.referenceId, route);
          events.push(event(tick, "pursuit-route-planned", unit.referenceId,
            target.referenceId, {
              waypointCount: route.waypoints.length,
              waypointIndex: route.waypointIndex,
            }));
        }
      }
      if (route) {
        authoritativeRouteReferenceIds.add(unit.referenceId);
        const waypoint = route.waypoints[route.waypointIndex];
        return Object.freeze({
          x: waypoint.x,
          y: waypoint.y,
          pathWaypoint: true,
          persistentRoute: true,
        });
      }
      return target;
    }
    const waypoints = kiteState.chaseWaypoints;
    let waypoint = waypoints.get(unit.referenceId);
    if (!waypoint || waypoint.targetId !== target.referenceId
        || tick % KITE_CHASE_REPATH_TICKS
          === ((unit.referenceId % KITE_CHASE_REPATH_TICKS) + KITE_CHASE_REPATH_TICKS)
            % KITE_CHASE_REPATH_TICKS) {
      waypoint = { targetId: target.referenceId, x: target.x, y: target.y };
      waypoints.set(unit.referenceId, waypoint);
    }
    if (CHASE_PATH_GRID) {
      // Plan on the repath cadence: the waypoint object is recreated by the
      // repath above, so a missing plan means this cycle has not planned yet.
      if (waypoint.plan === undefined) {
        waypoint.plan = planChaseAim(unit, target, obstacles, map, {
          pairInteractions,
        });
      }
      const plan = waypoint.plan;
      if (plan !== null) {
        if (plan.stand === true) {
          return Object.freeze({ x: unit.x, y: unit.y, pathWaypoint: true });
        }
        return Object.freeze({ x: plan.x, y: plan.y, pathWaypoint: true });
      }
    }
    return { ...target, x: waypoint.x, y: waypoint.y };
  };
  const kitedMoveAim = (unit) => {
    const goal = soloDestinations?.get(unit.referenceId) ?? unit.moveOrder;
    if (kiteState?.profile?.kitedPath !== "clearance_grid" && !soloGridPath
        || unit.owner !== kiteState.owner) return goal;
    const waypoints = kiteState.kitedWaypoints;
    let waypoint = waypoints.get(unit.referenceId);
    const repathTick = tick % KITE_CHASE_REPATH_TICKS
      === ((unit.referenceId % KITE_CHASE_REPATH_TICKS) + KITE_CHASE_REPATH_TICKS)
        % KITE_CHASE_REPATH_TICKS;
    const cohesiveGoalMoved = kiteState?.soloNavigationState?.variant === "cohesive"
      && waypoint
      && Math.hypot(waypoint.orderX - goal.x, waypoint.orderY - goal.y) > 0.5;
    if (!waypoint || cohesiveGoalMoved
        || (kiteState?.soloNavigationState?.variant !== "cohesive"
          && (waypoint.orderX !== goal.x || waypoint.orderY !== goal.y))
        || repathTick) {
      // The measured defect is enemy-contact capture. Friendly compression is
      // already handled by the ordinary collision layer (including its DAT
      // shrink rule), and treating allies as hard A* walls tears the kiting
      // ball apart and suppresses its volley. Plan only around enemy bodies;
      // execution still passes through the normal ally collision solver.
      const obstacles = live.filter((other) => isHostile(unit, other));
      waypoint = {
        orderX: goal.x,
        orderY: goal.y,
        plan: planMoveAim(unit, goal, obstacles, map, {
          pairInteractions,
        }),
      };
      waypoints.set(unit.referenceId, waypoint);
    }
    if (waypoint.plan === null) return goal;
    if (waypoint.plan.stand === true) return { x: unit.x, y: unit.y };
    return waypoint.plan;
  };
  const proposalForUnit = (unit) => {
    // A kite move order overrides everything: the tape's move-ordered units
    // walk their waypoint and do not fight until the next attack beat.
    //
    // A RELEASED swing does not hold the unit any more. The rest of the attack
    // animation is recovery, and the tape walks through it: of 4175 recorded
    // Elite Skirmisher shots, 39% leave the bow while the shooter is ALREADY
    // moving, the median release-to-movement gap is 0.05 s, and 89% are moving
    // within 0.25 s -- against the 0.693 s of leftover animation this engine
    // used to freeze them for (1.2 s animation, arrow away at 0.507 s). That
    // freeze was eating ~a third of every 3.335 s kite beat, which is what
    // starved the formation's flow.
    //
    // Recovery still governs RETARGETING (progressAttacks only frees the unit
    // at the end of the animation, which is the measured "killers retarget
    // half an animation after the kill" rule) -- this is movement only, and
    // only for a unit already holding a move order, so no melee fight in the
    // corpus can reach it. windup === 0 is exactly "the swing has been
    // released"; an unreleased swing was already cancelled when the order was
    // issued, and a unit holding a move order never starts a new attack.
    const suspendedScenarioPatrol = unit.moveOrder?.kind === "scenario-patrol"
      && (Number.isSafeInteger(unit.pursuitTargetId)
        || Number.isSafeInteger(unit.engagedTargetId)
        || Number.isSafeInteger(unit.attackTargetId));
    if (unit.moveOrder && !suspendedScenarioPatrol
        && (unit.action !== "attacking" || unit.actionTimers.windup === 0)) {
      if (Number.isSafeInteger(unit.moveOrder.motionStartTick)
          && tick < unit.moveOrder.motionStartTick) {
        return Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
      }
      const moveAim = kitedMoveAim(unit);
      const dx = moveAim.x - unit.x;
      const dy = moveAim.y - unit.y;
      const distance = Math.hypot(dx, dy);
      const step = unit.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
      if (distance > step) {
        return Object.freeze({
          referenceId: unit.referenceId,
          dx: (dx / distance) * step,
          dy: (dy / distance) * step,
        });
      }
      return Object.freeze({ referenceId: unit.referenceId, dx, dy });
    }
    const approach = kiteState?.meleeApproach?.get(unit.referenceId);
    if (approach && unit.owner !== kiteState.owner
        && (unit.pursuitTargetId === null || unit.pursuitTargetId === undefined)) {
      const dx = approach.x - unit.x;
      const dy = approach.y - unit.y;
      const distance = Math.hypot(dx, dy);
      const step = unit.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
      if (distance > step) {
        return Object.freeze({
          referenceId: unit.referenceId,
          dx: (dx / distance) * step,
          dy: (dy / distance) * step,
        });
      }
      return Object.freeze({ referenceId: unit.referenceId, dx, dy });
    }
    const retreat = minRangeRetreat(unit, live);
    if (retreat) return retreat;
    // In a kiting fight, engagement means the chaser has completed its catch.
    // Hold it for one stationary tick so an engagement in the wider outline
    // reach envelope can begin the ordinary attack windup instead of being
    // invalidated by another pursuit step. If the target leaves that envelope,
    // this branch immediately releases and normal pursuit resumes below.
    const engaged = byReference.get(unit.engagedTargetId);
    if (kiteState?.meleeOpeningOrder === "attack-move-all"
        && unit.owner !== kiteState.owner
        && engaged?.alive && isHostile(unit, engaged)
        && isWithinReach(unit, engaged)
        && isWithinStopRange(unit, engaged, { pairInteractions })) {
      return Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
    }
    const target = byReference.get(unit.pursuitTargetId);
    return target && unit.action !== "attacking" && !isWithinStopRange(
      unit, target, { pairInteractions },
    )
      && !holdsForChargeVolley(unit, target)
      ? (() => {
        const aim = chaseAim(unit, target);
        return aim.pathWaypoint
          ? proposePointMovement(unit, aim, TICKS_PER_SECOND)
          : proposeMovement(unit, aim, TICKS_PER_SECOND, { pairInteractions });
      })()
      : Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
  };
  let proposals = live.map(proposalForUnit);
  if (kiteState?.profile?.cohortMotion === "contact_heading") {
    const proposalByReference = new Map(
      proposals.map((proposal) => [proposal.referenceId, proposal]),
    );
    const cohort = live.filter((unit) => (
      unit.owner === kiteState.owner
      && unit.moveOrder
      && (unit.action !== "attacking" || unit.actionTimers.windup === 0)
    ));
    if (cohort.length >= 2) {
      const plannedCohort = planCohortContactMotion({
        units: cohort,
        proposals: cohort.map((unit) => proposalByReference.get(unit.referenceId)),
        enemies: live.filter((unit) => isHostile(cohort[0], unit)),
        map,
        preferredTurn: kiteState.ringDirection || 1,
      });
      const plannedByReference = new Map(
        plannedCohort.map((proposal) => [proposal.referenceId, proposal]),
      );
      proposals = proposals.map((proposal) => (
        plannedByReference.get(proposal.referenceId) ?? proposal
      ));
    }
  }
  const crowdInputProposals = proposals;
  let rangedCrowdPlan = planRangedCrowding(live, crowdInputProposals, tick, {
    authoritativeReferenceIds: authoritativeRouteReferenceIds,
  });
  proposals = rangedCrowdPlan.proposals;
  if (pursuitRecoveryState && rangedCrowdPlan.routeRequests.length > 0) {
    const provisionalReservations = new Map(pairInteractions.contactReservations);
    for (const [key, reservation] of rangedCrowdPlan.contactReservations) {
      provisionalReservations.set(key, reservation);
    }
    const routePairInteractions = createPairInteractionSnapshot({
      contactReservations: provisionalReservations,
    });
    const routeProposalByReference = new Map();
    for (const request of rangedCrowdPlan.routeRequests) {
      const unit = byReference.get(request.referenceId);
      const target = byReference.get(request.targetReferenceId);
      if (!unit?.alive || !target?.alive || !isHostile(unit, target)
          || isWithinReach(unit, target)) continue;
      const obstacles = live.filter((other) => (
        other.referenceId !== unit.referenceId
        && other.referenceId !== target.referenceId
      ));
      const persistentRoute = planPersistentChaseRoute(
        unit,
        target,
        obstacles,
        map,
        {
          pairInteractions: routePairInteractions,
          includeNonObstructingContacts: true,
        },
      );
      const route = persistentRoute && persistentRoute.stand !== true
        ? persistentRoute
        : planBlockedPursuitEscape(
          unit,
          target,
          request.wantedDx,
          request.wantedDy,
          live,
          map,
          routePairInteractions,
          pursuitRecoveryState.routeFailures.get(unit.referenceId) ?? 0,
        );
      if (!route || route.stand === true || route.waypoints.length === 0) {
        const failedTargets = pursuitRecoveryState.failedTargets.get(unit.referenceId)
          ?? new Set();
        failedTargets.add(target.referenceId);
        pursuitRecoveryState.failedTargets.set(unit.referenceId, failedTargets);
        pursuitRecoveryState.retargetReady.add(unit.referenceId);
        events.push(event(tick, "pursuit-retarget-requested", unit.referenceId,
          target.referenceId, {
            reason: "ranged-crowd-route-unavailable",
          }));
        continue;
      }
      pursuitRecoveryState.routes.set(unit.referenceId, route);
      pursuitRecoveryState.attempts.delete(unit.referenceId);
      pursuitRecoveryState.retargetReady.delete(unit.referenceId);
      authoritativeRouteReferenceIds.add(unit.referenceId);
      const waypoint = route.waypoints[route.waypointIndex];
      routeProposalByReference.set(
        unit.referenceId,
        proposePointMovement(unit, waypoint, TICKS_PER_SECOND),
      );
      events.push(event(tick, "pursuit-route-planned", unit.referenceId,
        target.referenceId, {
          reason: request.reason,
          waypointCount: route.waypoints.length,
          waypointIndex: route.waypointIndex,
          recoveryAttempt: pursuitRecoveryState.routeFailures.get(unit.referenceId) ?? 0,
          ...(route.recoveryKind ? { recoveryKind: route.recoveryKind } : {}),
        }));
    }
    if (routeProposalByReference.size > 0) {
      const routedInputs = crowdInputProposals.map((proposal) => (
        routeProposalByReference.get(proposal.referenceId) ?? proposal
      ));
      rangedCrowdPlan = planRangedCrowding(live, routedInputs, tick, {
        authoritativeReferenceIds: authoritativeRouteReferenceIds,
      });
      proposals = rangedCrowdPlan.proposals;
    }
  }
  const contactUpdate = contactReservationState
    ? updateContactReservations({
      state: contactReservationState,
      units: live,
      proposals,
      tick,
      externalReservations: rangedCrowdPlan.contactReservations,
      inheritedOverlapReferenceIds: allowedStartingOverlapReferenceIds,
    })
    : null;
  if (contactUpdate) {
    const combinedReservations = new Map(contactUpdate.contactReservations);
    for (const [key, reservation] of rangedCrowdPlan.contactReservations) {
      combinedReservations.set(key, reservation);
    }
    pairInteractions = createPairInteractionSnapshot({
      contactReservations: combinedReservations,
    });
    for (const diagnostic of contactUpdate.diagnostics) {
      const [leftId, rightId] = diagnostic.pairKey.split(":").map(Number);
      const { type, pairKey, ...details } = diagnostic;
      events.push(event(
        tick,
        `contact-${type}`,
        leftId,
        rightId,
        { pairKey, ...details },
      ));
    }
  }
  let movementOptions = {
    pairInteractions,
    ...(kiteState ? { collisionRecoveryState: kiteState.collisionRecoveryState } : {}),
    ...(authoritativeRouteReferenceIds.size > 0
      ? { authoritativeReferenceIds: authoritativeRouteReferenceIds }
      : {}),
  };
  let planned = planLocalAvoidance(live, proposals, map, movementOptions);
  for (const contactSteeringState of contactSteeringStates.values()) {
    const contactPlan = planPreventiveContactSteering(
      planned.units,
      planned.proposals,
      map,
      {
        owner: contactSteeringState.owner,
        strength: contactSteeringState.strength,
        authoritativeReferenceIds: authoritativeRouteReferenceIds,
      },
    );
    contactSteeringState.steeredSteps += contactPlan.steered.length;
    for (const { referenceId } of contactPlan.steered) {
      contactSteeringState.steeredUnits.add(referenceId);
    }
    planned = Object.freeze({ ...planned, proposals: contactPlan.proposals });
  }
  const moved = resolveMovement(planned, byReference, map, kiteState, movementOptions);
  const movedByReference = new Map(moved.map((unit) => [unit.referenceId, unit]));
  const proposalByReference = new Map(proposals.map((proposal) => [proposal.referenceId, proposal]));
  const moveEvents = [];
  const blockedEvents = [];
  const routeEvents = [];
  const recoveryPlanRequests = [];
  const recoveryRequestIds = new Set();
  const queueRecoveryPlan = (request) => {
    if (recoveryRequestIds.has(request.referenceId)) return;
    recoveryRequestIds.add(request.referenceId);
    recoveryPlanRequests.push(Object.freeze(request));
  };
  const movedIds = new Set();
  const blockedIds = new Set();
  // Per-tick displacement of every live unit, for ballistics lead (smart_mode
  // bit 1). Transient — never stamped on a unit, so it can't reach any hash.
  const velocities = new Map();
  for (const unit of units) {
    const before = byReference.get(unit.referenceId);
    if (!before) continue;
    const result = movedByReference.get(unit.referenceId);
    const dx = result.x - before.x;
    const dy = result.y - before.y;
    velocities.set(unit.referenceId, { dx, dy });
    unit.x = result.x;
    unit.y = result.y;
    unit.avoidance = result.avoidance;
    if (unit.specialState?.dismountCollisionRecovery === true) {
      delete unit.specialState.dismountCollisionRecovery;
    }
    if (dx !== 0 || dy !== 0) {
      movedIds.add(unit.referenceId);
      unit.facing = Math.atan2(dy, dx);
      moveEvents.push(event(
        tick,
        "move",
        unit.referenceId,
        unit.pursuitTargetId,
        { dx, dy },
      ));
    }
    const proposal = proposalByReference.get(unit.referenceId);
    const isBlocked = Math.abs(dx - proposal.dx) > 1e-12 || Math.abs(dy - proposal.dy) > 1e-12;
    const recoveryRoute = pursuitRecoveryState?.routes.get(unit.referenceId) ?? null;
    if (authoritativeRouteReferenceIds.has(unit.referenceId)) {
      const route = recoveryRoute ?? kiteState?.chaseRoutes?.get(unit.referenceId);
      const waypoint = route?.waypoints?.[route.waypointIndex];
      if (waypoint) {
        const routeWanted = Math.hypot(proposal.dx, proposal.dy);
        const routeActual = Math.hypot(dx, dy);
        const recoveryRouteStalled = recoveryRoute
          && routeWanted > ZERO_STEP_EPSILON
          && routeActual < routeWanted * BLOCKED_PURSUIT_PROGRESS_FRACTION;
        if (persistentRouteMotionStalled(before, result) || recoveryRouteStalled) {
          const proposedX = before.x + proposal.dx;
            const proposedY = before.y + proposal.dy;
            const blockingReferenceIds = live.filter((other) => {
              if (other.referenceId === unit.referenceId) return false;
              const interaction = resolvePairInteraction(
                before, other, movementOptions.pairInteractions,
              );
              return Math.max(
                  Math.abs(proposedX - other.x),
                  Math.abs(proposedY - other.y),
                ) < interaction.collisionExtent - STEP_EPSILON;
            }).map(({ referenceId }) => referenceId);
            if (recoveryRoute) {
              pursuitRecoveryState.routes.delete(unit.referenceId);
              pursuitRecoveryState.retargetReady.add(unit.referenceId);
              pursuitRecoveryState.routeFailures.set(
                unit.referenceId,
                (pursuitRecoveryState.routeFailures.get(unit.referenceId) ?? 0) + 1,
              );
              const failedTargets = pursuitRecoveryState.failedTargets.get(unit.referenceId)
                ?? new Set();
              failedTargets.add(route.targetReferenceId);
              pursuitRecoveryState.failedTargets.set(unit.referenceId, failedTargets);
            } else {
              kiteState.chaseRoutes.delete(unit.referenceId);
            }
            routeEvents.push(event(tick, "pursuit-route-invalidated", unit.referenceId,
              route.targetReferenceId, {
                reason: recoveryRouteStalled ? "insufficient-progress" : "no-progress",
                ...(recoveryRoute ? { recovery: true } : {}),
                waypointX: waypoint.x,
                waypointY: waypoint.y,
                beforeX: before.x,
                beforeY: before.y,
                proposedX,
                proposedY,
                afterX: result.x,
                afterY: result.y,
                blockingReferenceIds,
              }));
        }
      }
    }
    // Only stamp experiment state when an experiment is running: the canonical
    // unit record feeds finalStateHash, so an always-present field would change
    // every golden hash for no reason.
    if (ANY_EXPERIMENT) {
      unit.experimentBlocked = isBlocked
        && (proposal.dx !== 0 || proposal.dy !== 0);
      // Which body stopped it, if any: the enemy the unconstrained step would
      // have walked into. An ally block is a different situation entirely --
      // the unit is queued behind its own side, not stopped by the enemy in
      // front of it -- and conflating the two is what made the first version
      // of KITE_ENGAGE=blocker fire all over the kac corpus.
      unit.experimentBlockedByEnemyId = null;
      if (unit.experimentBlocked) {
        let nearest = null;
        let nearestGap = Infinity;
        const wantX = before.x + proposal.dx;
        const wantY = before.y + proposal.dy;
        for (const other of live) {
          if (!areOpponents(unit, other) || other.referenceId === unit.referenceId) continue;
          const extent = collisionRadius(before) + collisionRadius(other);
          const gap = Math.max(Math.abs(wantX - other.x), Math.abs(wantY - other.y));
          if (gap < extent - STEP_EPSILON && gap < nearestGap) {
            nearest = other.referenceId;
            nearestGap = gap;
          }
        }
        unit.experimentBlockedByEnemyId = nearest;
      }
    }
    if (isBlocked) {
      if (proposal.dx !== 0 || proposal.dy !== 0) {
        blockedIds.add(unit.referenceId);
      }
      blockedEvents.push(event(tick, "blocked", unit.referenceId, unit.pursuitTargetId, {
        proposedDx: proposal.dx,
        proposedDy: proposal.dy,
        actualDx: dx,
        actualDy: dy,
      }));
    }
    if (pursuitRecoveryState && !authoritativeRouteReferenceIds.has(unit.referenceId)) {
      const target = byReference.get(unit.pursuitTargetId);
      const wanted = Math.hypot(proposal.dx, proposal.dy);
      const actual = Math.hypot(dx, dy);
      const failedAttempt = target?.alive
        && isHostile(unit, target)
        && !isWithinReach(before, target)
        && wanted > ZERO_STEP_EPSILON
        && isBlocked
        && actual < wanted * BLOCKED_PURSUIT_PROGRESS_FRACTION;
      if (failedAttempt) {
        const previous = pursuitRecoveryState.attempts.get(unit.referenceId);
        const count = previous?.targetReferenceId === target.referenceId
          ? previous.count + 1
          : 1;
        if (count >= BLOCKED_PURSUIT_RETRY_LIMIT) {
          pursuitRecoveryState.attempts.delete(unit.referenceId);
          queueRecoveryPlan({
            referenceId: unit.referenceId,
            targetReferenceId: target.referenceId,
            wantedDx: proposal.dx,
            wantedDy: proposal.dy,
            reason: "blocked-pursuit-recovery",
            failedAttempts: BLOCKED_PURSUIT_RETRY_LIMIT,
          });
        } else {
          pursuitRecoveryState.attempts.set(unit.referenceId, Object.freeze({
            targetReferenceId: target.referenceId,
            count,
          }));
        }
      } else {
        pursuitRecoveryState.attempts.delete(unit.referenceId);
        if (actual >= wanted * BLOCKED_PURSUIT_PROGRESS_FRACTION
            && actual > ZERO_STEP_EPSILON) {
          pursuitRecoveryState.failedTargets.delete(unit.referenceId);
        }
      }

    }
  }
  if (pursuitRecoveryState && recoveryPlanRequests.length > 0) {
    const postMoveLive = units.filter(({ alive }) => alive).map(freezeUnit);
    const postMoveByReference = new Map(
      postMoveLive.map((unit) => [unit.referenceId, unit]),
    );
    for (const request of recoveryPlanRequests) {
      const unit = postMoveByReference.get(request.referenceId);
      const target = postMoveByReference.get(request.targetReferenceId);
      if (!unit?.alive || !target?.alive || !isHostile(unit, target)
          || isWithinReach(unit, target)) continue;
      const obstacles = postMoveLive.filter((other) => (
        other.referenceId !== unit.referenceId
        && other.referenceId !== target.referenceId
      ));
      const persistentRoute = planPersistentChaseRoute(unit, target, obstacles, map, {
        pairInteractions: movementOptions.pairInteractions,
        includeNonObstructingContacts: true,
      });
      const route = persistentRoute && persistentRoute.stand !== true
        ? persistentRoute
        : planBlockedPursuitEscape(
          unit,
          target,
          request.wantedDx,
          request.wantedDy,
          postMoveLive,
          map,
          movementOptions.pairInteractions,
          pursuitRecoveryState.routeFailures.get(unit.referenceId) ?? 0,
        );
      if (route && route.stand !== true && route.waypoints.length > 0) {
        pursuitRecoveryState.routes.set(unit.referenceId, route);
        routeEvents.push(event(tick, "pursuit-route-planned", unit.referenceId,
          target.referenceId, {
            reason: request.reason,
            ...(request.failedAttempts === undefined
              ? {}
              : { failedAttempts: request.failedAttempts }),
            waypointCount: route.waypoints.length,
            waypointIndex: route.waypointIndex,
            recoveryAttempt: pursuitRecoveryState.routeFailures.get(unit.referenceId) ?? 0,
            ...(route.recoveryKind ? { recoveryKind: route.recoveryKind } : {}),
          }));
      } else {
        const failedTargets = pursuitRecoveryState.failedTargets.get(unit.referenceId)
          ?? new Set();
        failedTargets.add(target.referenceId);
        pursuitRecoveryState.failedTargets.set(unit.referenceId, failedTargets);
        pursuitRecoveryState.retargetReady.add(unit.referenceId);
        routeEvents.push(event(tick, "pursuit-retarget-requested", unit.referenceId,
          target.referenceId, {
            reason: persistentRoute?.stand === true
              ? "blocked-route-unreachable"
              : "blocked-route-not-found",
            ...(request.failedAttempts === undefined
              ? {}
              : { failedAttempts: request.failedAttempts }),
          }));
      }
    }
  }
  events.push(...moveEvents, ...blockedEvents, ...routeEvents);
  if (kiteState?.soloNavigationState) {
    finishSoloNavigationTick(
      kiteState.soloNavigationState,
      units.filter((unit) => unit.alive && unit.owner === kiteState.owner),
      blockedIds,
    );
  }
  return {
    contacts: queryEnemyContactManifold(live, units.filter(({ alive }) => alive).map(freezeUnit)),
    movedIds,
    blockedIds,
    velocities,
    contactUpdate,
    pairInteractions: movementOptions.pairInteractions,
  };
}


// Kited-world swing-start dwell (measured, kac archives): a chaser adjacent
// to its own caught target does NOT swing immediately — 64% of sustained
// (>=0.5 s) adjacency windows produce no hit, and the window hit rate only
// crosses ~50% at ~1.75-2.0 s (0.17 at 0.5 s / 0.25 at 1.0 s / 0.46 at
// 1.5 s / 0.51 at 2.0 s, attribution-inflated upper bounds). With the 0.75 s
// windup inside those windows, the swing START needs ~1.0 s of continuous
// in-reach dwell on the pursuit target. A kiting target that stands only
// 0.67 s per beat therefore escapes most catches, while a blocked or
// cornered one (the 5v10 chain kills) is hit repeatedly — exactly the
// recorded contrast. Engagement, once started, persists while the target
// stays in reach, so reload-paced multi-hit catches still occur.
const KITE_CHASE_DWELL_TICKS = Math.round(1.0 * TICKS_PER_SECOND);
const KITE_DWELL_HOLD_RADIUS_TILES = 1.0;
// Body contact for contact capture: collision-box touch plus a float
// tolerance. The solver holds enemy pairs at exactly the summed half-extents
// when they press, so anything within 0.02 of the box IS a touch, and the
// recorded switch distances sit exactly on the contact band (see the capture
// comment in updateEngagements). A tolerance, not a physical constant.
const CONTACT_CAPTURE_EPSILON = 0.02;
// A body-blocked melee actor can retain a short tail of attack reach beyond
// the ordinary range+0.1 start envelope. Full-rate Paladin/Steppe captures
// bound those starts at outline gap <= attack range +0.24. This replaces both
// an unphysical line-of-sight-wide stale lock and an equally incorrect hard
// cutoff at +0.1.
const BLOCKED_MELEE_TAIL_TOLERANCE_TILES = 0.24;


function isWithinBlockedMeleeTailReach(unit, target) {
  if (unit.mechanics?.ranged) return false;
  return outlineChebyshevGap(unit, target)
    <= (unit.mechanics?.attack_range_tiles ?? 0)
      + BLOCKED_MELEE_TAIL_TOLERANCE_TILES + 1e-12;
}


function selectFrontalPatrolContactCapture(unit, snapshot, pairInteractions) {
  const pursued = Number.isSafeInteger(unit.pursuitTargetId)
    ? snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId)
    : null;
  if (!pursued?.alive || !isHostile(unit, pursued) || isWithinReach(unit, pursued)) {
    return null;
  }
  const frontX = pursued.x - unit.x;
  const frontY = pursued.y - unit.y;
  let touched = null;
  let touchedDistance = Infinity;
  for (const candidate of snapshot) {
    if (!candidate.alive || !isHostile(unit, candidate)
        || candidate.referenceId === pursued.referenceId) continue;
    const contactGap = Math.max(
      Math.abs(candidate.x - unit.x),
      Math.abs(candidate.y - unit.y),
    ) - resolvePairInteraction(
      unit,
      candidate,
      pairInteractions,
    ).attackSurfaceExtent;
    if (contactGap > CONTACT_CAPTURE_EPSILON) continue;
    const towardX = candidate.x - unit.x;
    const towardY = candidate.y - unit.y;
    if (frontX * towardX + frontY * towardY <= 0) continue;
    const distance = Math.hypot(towardX, towardY);
    if (distance < touchedDistance - 1e-12
        || (distance < touchedDistance + 1e-12
          && (touched === null || candidate.referenceId < touched.referenceId))) {
      touched = candidate;
      touchedDistance = distance;
    }
  }
  return touched;
}


function updateEngagements(units, contacts, tick, events, blockedIds, kiteState = null,
  pairInteractions = createPairInteractionSnapshot()) {
  const kiteOwner = kiteState ? kiteState.owner : null;
  if (kiteState && !kiteState.reachDwell) kiteState.reachDwell = new Map();
  const snapshot = Object.freeze(units.map(freezeUnit));
  const incomingMeleeEngagements = new Map();
  for (const unit of snapshot) {
    if (!unit.alive || unit.mechanics?.ranged) continue;
    if (!Number.isSafeInteger(unit.engagedTargetId)) continue;
    const target = snapshot.find(({ referenceId }) => referenceId === unit.engagedTargetId);
    if (!target?.alive || !isHostile(unit, target)) continue;
    incomingMeleeEngagements.set(
      target.referenceId,
      (incomingMeleeEngagements.get(target.referenceId) ?? 0) + 1,
    );
  }
  for (const unit of units) {
    if (!unit.alive) {
      unit.engagedTargetId = null;
      continue;
    }
    // No engagement before first acquisition. A scenario PATROL can be close
    // enough to an enemy before its next scheduled AI scan; ordinary contact
    // selection must not let it attack an enemy it has not acquired. That was
    // observable as an impossible attack-start preceding pursuit-acquired.
    // The numeric acquire timer remains the equivalent gate for non-scenario
    // orders (including the range-0 fixtures).
    const awaitingPatrolAcquisition = unit.moveOrder?.kind === "scenario-patrol"
      && unit.openingAcquisitionComplete !== true;
    if (awaitingPatrolAcquisition || unit.actionTimers.acquire > 0) {
      unit.engagedTargetId = null;
      continue;
    }
    // A kite move order suppresses engagement until the next attack beat
    // re-designates (the tape wraps each move in a no-attack stance toggle).
    if (unit.moveOrder && unit.moveOrder.kind !== "scenario-patrol") {
      unit.engagedTargetId = null;
      continue;
    }
    const previousTargetId = unit.engagedTargetId;
    // Kited-world chase discipline (measured, kac archives): a chaser engages
    // ONLY its sticky pursuit target. 64% of its sustained (>=0.5 s)
    // adjacency windows with OTHER enemies produce no swing at all, while its
    // own caught target is hit within the first second 63-80% of the time
    // (svc contrast). Hits land at up to 1.91 tiles center distance at the
    // damage frame, so release stays unconditional (commitReadyAttacks has no
    // distance check) — the discipline is entirely in the swing START.
    if (kiteOwner !== null && unit.owner !== kiteOwner
        && kiteState.opponentMode !== "ordinary-ranged") {
      // CONTACT CAPTURE (measured on the full-rate action decode, five
      // archives): a walking chaser that comes into BODY CONTACT with a live
      // enemy switches its pursuit to that enemy, old target dead or alive.
      // svcam camels: 64 alive-switches, distance to the NEW target at the
      // switch p25 0.49 / p50 0.54 / p75 0.59 — exactly the collision-contact
      // band (Chebyshev 0.45 spans Euclidean 0.45-0.64) — at full walking
      // speed (11% stopped), not under attack (1/64), no recent hp loss
      // (13/64). Same signature: esc champions (46, p50 0.50), avp paladins
      // (38, p50 0.58), esp paladins (43, p50 0.54), avst steppe (6, p50
      // 0.51). kac champions show only 9 alive-switches, 7/9 under attack at
      // p50 1.68 — those are the sparse mid-fight AI orders, and the rule
      // correctly almost never fires there because kac chasers rarely touch a
      // non-target body. The interactive attack-move viewer enables the same
      // physical rule for every supported ranged roster so a Champion that
      // reaches a different front-line body attacks it instead of continuing
      // to press through toward an obsolete sticky target. This is what keeps
      // chasers at the formation's EDGE:
      // the first body a chaser touches captures it, so it fights the
      // surface instead of wading in (tape victim rank r1 = 71-79%).
      //
      // The 64%-no-swing adjacency measurement that built the sticky
      // discipline used a 1-tile adjacency radius; contact capture needs
      // actual box contact, a strictly smaller trigger, so both hold.
      // The capture is FRONTAL: at the recorded switches the new target sits
      // in the chaser's direction of motion (cos p50 +0.76..+0.91; cos > 0 in
      // 81-92% across svcam/esc/avp/esp). A body pressed against the flank in
      // a chasing scrum does not capture — which is why kac, whose champions
      // touch arbs almost only laterally, records just 9 alive-switches. The
      // front is taken as the direction toward the current pursuit target
      // (what a walking chaser's motion approximates), so a unit with no
      // pursuit yet cannot be captured.
      // Capture is an EVENT, not a per-tick state: it fires while the chaser
      // is still WALKING toward a target beyond its reach (the recorded old
      // target sits p25 0.88 / p50 1.12 away at the switch), and once it
      // fires the new pursuit target is the body in contact, so the rule goes
      // quiet until the chaser is walking at something distant again. Without
      // the beyond-reach condition a chaser pressed against two bodies
      // ping-pongs between them every tick and its dwell never completes.
      const capturePursued = unit.pursuitTargetId === null || unit.pursuitTargetId === undefined
        ? null
        : snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId);
      if (kiteState.chaseCapture === true
        && unit.action !== "attacking" && unit.engagedTargetId === null
        && capturePursued && capturePursued.alive
        && !isWithinReach(unit, capturePursued)) {
        const frontX = capturePursued.x - unit.x;
        const frontY = capturePursued.y - unit.y;
        let touched = null;
        let touchedGap = Infinity;
        for (const candidate of snapshot) {
          if (!candidate.alive || !isHostile(unit, candidate)) continue;
          if (candidate.referenceId === unit.pursuitTargetId) continue;
          const contactGap = Math.max(
            Math.abs(candidate.x - unit.x),
            Math.abs(candidate.y - unit.y),
          ) - resolvePairInteraction(
            unit,
            candidate,
            pairInteractions,
          ).attackSurfaceExtent;
          if (contactGap > CONTACT_CAPTURE_EPSILON) continue;
          const towardX = candidate.x - unit.x;
          const towardY = candidate.y - unit.y;
          if (frontX * towardX + frontY * towardY <= 0) continue;
          const euclid = Math.hypot(towardX, towardY);
          if (euclid < touchedGap - 1e-12
            || (euclid < touchedGap + 1e-12
              && (touched === null || candidate.referenceId < touched.referenceId))) {
            touched = candidate;
            touchedGap = euclid;
          }
        }
        if (touched) {
          unit.pursuitTargetId = touched.referenceId;
          unit.avoidance = null;
          events.push(event(tick, "contact-capture", unit.referenceId, touched.referenceId));
        }
      }
      const pursued = unit.pursuitTargetId === null || unit.pursuitTargetId === undefined
        ? null
        : snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId);
      // Dwell counts continuous in-reach ticks on the current pursuit
      // target — EXCEPT that a chaser parked inside its target's own
      // MINIMUM RANGE keeps accumulating through reach flickers: the target
      // cannot shoot its pinner (dat type_50.min_range) and backpedals at
      // near-zero relative speed, which is the skirmisher tapes' steady
      // grind (hits within the first second of contact 37% of the time).
      // Against a min-range-0 kiter no pin exists, the chaser loses reach
      // for a full walk phase every cycle and resets — the arbalester
      // tapes' 0.09-0.17 conversion. Swing START still requires reach.
      const gap = pursued && pursued.alive && isHostile(unit, pursued)
        ? Math.hypot(pursued.x - unit.x, pursued.y - unit.y)
        : Infinity;
      // A REACH fighter (nonzero melee attack range: the Elite Steppe
      // Lancer's 1.0) converts on reach entry with no dwell at all — across
      // 3508 attributed kills in the three steppe kiting archives the median
      // continuous pre-swing dwell is 0.0 s at every radius up to 1.75 and
      // the median swing-start gap is 1.5 tiles, its exact outline reach.
      // The dwell gate and its contact hold radius are range-0 chaser
      // behavior (the champion/paladin conversion friction above).
      const reachTiles = unit.mechanics?.ranged
        ? 0
        : (unit.mechanics?.attack_range_tiles ?? 0);
      const reachFighter = reachTiles >= 1 - 1e-12;
      const chaseDwellTicks = kiteState.chaseDwellTicks ?? KITE_CHASE_DWELL_TICKS;
      const inReach = Number.isFinite(gap)
        && (reachFighter || gap <= KITE_DWELL_HOLD_RADIUS_TILES + 1e-12)
        && isWithinReach(unit, pursued);
      const pinned = gap < (pursued?.mechanics?.ranged?.min_range_tiles ?? 0) - 1e-12;
      const previous = kiteState.reachDwell.get(unit.referenceId);
      const carried = previous && previous.targetId === pursued?.referenceId
        ? previous.ticks
        : 0;
      const accumulating = inReach || pinned;
      if (accumulating) {
        kiteState.reachDwell.set(unit.referenceId,
          { targetId: pursued.referenceId, ticks: carried + 1 });
      } else {
        kiteState.reachDwell.delete(unit.referenceId);
      }
      let nextTargetId = inReach
        && (carried + 1 >= (reachFighter ? 1 : chaseDwellTicks)
          || previousTargetId === pursued.referenceId)
        ? pursued.referenceId
        : null;
      // A chaser that is physically BLOCKED cannot brush past anything -- it is
      // stopped against a body. The measured discipline (64% of sustained
      // adjacency windows with other enemies produce no swing) is about units
      // walking THROUGH a formation, and a blocked unit is not walking. Under
      // AOE2X_EXP_KITE_ENGAGE=blocker it fights whatever is stopping it, which
      // is what would hold a chaser at the formation's edge instead of letting
      // it wade into the middle.
      if (nextTargetId === null && KITE_ENGAGE_BLOCKER
        && unit.experimentBlockedByEnemyId !== null
        && unit.experimentBlockedByEnemyId !== undefined) {
        const blocker = snapshot.find(({ referenceId }) => (
          referenceId === unit.experimentBlockedByEnemyId));
        if (blocker && blocker.alive && isWithinReach(unit, blocker)) {
          nextTargetId = blocker.referenceId;
        }
      }
      if (nextTargetId === previousTargetId) continue;
      if (previousTargetId !== null && previousTargetId !== undefined) {
        events.push(event(tick, "engagement-ended", unit.referenceId, previousTargetId, {
          reason: snapshot.find(({ referenceId }) => referenceId === previousTargetId)?.alive
            ? "contact-lost"
            : "target-dead",
        }));
      }
      unit.engagedTargetId = nextTargetId;
      if (nextTargetId === null) continue;
      unit.avoidance = null;
      events.push(event(tick, "engagement-started", unit.referenceId, nextTargetId, {
        sweptToi: null,
        finalSurfaceGap: null,
      }));
      continue;
    }
    // The auxiliary screen is a physical contact surface. Live PATROLs begin
    // with a concentrated two-lane lock, then moving melee members that touch
    // another hostile body switch their pursuit to that body. This is the same
    // frontal contact-capture rule used by ordinary chasers: it is symmetric,
    // requires actual box contact, and becomes inert as soon as the captured
    // body is in reach, preventing target ping-pong.
    const currentPursuit = Number.isSafeInteger(unit.pursuitTargetId)
      ? snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId)
      : null;
    const auxiliaryPatrolContact = unit.moveOrder?.kind === "scenario-patrol"
      && hasMeleeMode(unit)
      && currentPursuit?.alive === true
      && (unit.owner === 4 || currentPursuit.owner === 4);
    if (auxiliaryPatrolContact) {
      const captured = selectFrontalPatrolContactCapture(
        unit,
        snapshot,
        pairInteractions,
      );
      if (captured) {
        const previousTargetId = unit.pursuitTargetId;
        unit.pursuitTargetId = captured.referenceId;
        unit.avoidance = null;
        delete unit.patrolBlockerId;
        delete unit.patrolBlockerTicks;
        events.push(event(tick, "pursuit-acquired", unit.referenceId,
          captured.referenceId, {
            reason: "frontal-contact-capture",
            previousTargetId,
          }));
      }
    }
    // Attack-action persistence (measured, three archives): a unit shoved out
    // of reach during an already-committed swing keeps that cycle on its live
    // target. Outside a committed swing, however, blocking must not preserve
    // an unreachable engagement indefinitely. The next swing has an ordinary
    // reach gate, so retaining that stale lock would leave the unit parked and
    // unable either to attack or to select the hostile body blocking it. An
    // in-reach blocked engagement may persist through reload; an out-of-reach
    // one is released for normal local engagement selection below.
    if (
      previousTargetId !== null && previousTargetId !== undefined
      && blockedIds.has(unit.referenceId)
    ) {
      const engaged = snapshot.find(({ referenceId }) => referenceId === previousTargetId);
      if (engaged && engaged.alive && isHostile(unit, engaged)) {
        const distance = Math.hypot(engaged.x - unit.x, engaged.y - unit.y);
        if (distance <= unit.mechanics.line_of_sight_tiles
            && (unit.action === "attacking"
              || isWithinActiveAttackReach(unit, engaged, tick)
              || isWithinBlockedMeleeTailReach(unit, engaged))) {
          continue;
        }
      }
    }
    const self = snapshot.find(({ referenceId }) => referenceId === unit.referenceId);
    const meleeReachRanks = unit.mechanics?.ranged
      ? 0
      : Math.max(0, Math.floor(unit.mechanics?.attack_range_tiles ?? 0));
    // The two-claimant reservation is a deep body-contact surface. A packed
    // ranged line exposes one additional lateral contact; a melee body that is
    // itself pressing through the scrum exposes both lateral sides. Across all
    // five live Camel/HCA captures, per-ranged-target attacking load never
    // exceeds three even though many more units hold pursuit claims. Direct
    // Camel/Elephant contact independently requires the four-sided melee
    // surface. Reach fighters may occupy one additional outline rank.
    // Engagement capacity is not overlap depth: actors can stand on distinct
    // sides while the contact solver still caps deep penetration.
    const incomingEngagementCapacity = (candidate) => MAX_INCOMING_ENGAGEMENTS
      + (candidate.mechanics?.ranged ? 1 : 2) + meleeReachRanks;
    const targetAvailable = (candidate) => (
      unit.mechanics?.ranged
      || candidate.referenceId === previousTargetId
      || (incomingMeleeEngagements.get(candidate.referenceId) ?? 0)
        < incomingEngagementCapacity(candidate)
    );
    const selection = selectEngagementTarget(self, snapshot, contacts, {
      targetAvailable,
      targetInReach: (candidate) => isWithinActiveAttackReach(self, candidate, tick),
    });
    // Experiment harness: engagement follows pursuit. Off by default.
    //
    // Priority, not exclusivity: a unit whose pursuit target is in reach
    // engages it over anything else, but a unit BLOCKED short of its pursuit
    // target fights whatever enemy is in reach instead of standing idle.
    // Aggressive-stance unit AI never sleeps next to an enemy; the strict
    // version of this rule starved crowded fights -- in 21v10 the surplus
    // champions parked idle waiting for rate-limited rescue orders (65.8
    // orders/fight vs the tape's 15, 38 after 15 s vs the tape's 1) and the
    // paladins won all 25 sampled runs where the tape flips.
    const pursuitTarget = unit.pursuitTargetId !== null
        && unit.pursuitTargetId !== undefined
      ? snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId)
      : null;
    const pursued = ENGAGEMENT_FOLLOWS_PURSUIT ? pursuitTarget : null;
    // The pursuit target takes priority only once the unit has CLOSED to its
    // movement stop range — the same distance at which the old collision-based
    // engine applied this rule for range-0 units, kept range-aware here.
    // Widening the priority to the outline envelope re-focused fire enough to
    // swing paladin_vs_elephant 5v3 from band error 0.4 to 10.7; blocked units
    // farther out fight through selectEngagementTarget's outline fallback
    // instead, which is what the steppe back line actually exercises.
    // The pursuit target must also be legally attackable: isWithinReach
    // carries the minimum-range gate (dat type_50.min_range; scorpion fire
    // distances bottom out at 2.19 vs its 2.0, and the skirmisher tapes
    // deliver less than half their theoretical beat output because chasers
    // glued inside 1.0 cannot be shot). For melee actors stop range implies
    // reach (collision gap >= outline gap), so this adds nothing there. A
    // ranged unit PINNED this way (pursuit target closed inside its minimum
    // range) does not freelance onto another target either — it holds fire
    // and min-range-retreats, target lock intact: letting it fall through
    // to selectEngagementTarget kept every pinned scorpion firing full
    // pass-through bolts at the rest of the pack and flipped svc 15v20 to a
    // scorpion win the tape refutes.
    const pursuedClosed = pursued && pursued.alive && isWithinStopRange(
      self,
      pursued,
      { pairInteractions },
    );
    // The auxiliary gate is a committed opening engagement: the melee army
    // and Player 4 keep their acquired opponent until contact, with a body
    // that physically blocks the route able to capture the engagement. Once
    // the trigger removes Player 4 and the two principal armies become
    // hostile, they use ordinary aggressive engagement selection.
    const auxiliaryPatrolPursuit = unit.owner === 4 || pursuitTarget?.owner === 4;
    const auxiliaryPatrolPursuitLocked = unit.moveOrder?.kind === "scenario-patrol"
      && pursuitTarget?.alive === true
      && auxiliaryPatrolPursuit;
    // PATROL target acquisition suspends point motion and enters attack mode
    // on that acquired target. A ranged member that cannot yet reach its lock
    // does not freelance onto another body merely because that body is closer;
    // it keeps closing/waiting until the lock dies or is invalidated. This is
    // the same patrol mechanic in RvR and both mixed orientations.
    const openingRangedPatrolLocked = unit.moveOrder?.kind === "scenario-patrol"
      && unit.mechanics?.ranged
      && pursuitTarget?.alive === true;
    const latchedPatrolBlocker = auxiliaryPatrolPursuitLocked
        && Number.isSafeInteger(previousTargetId)
        && previousTargetId !== pursuitTarget.referenceId
      ? snapshot.find(({ referenceId }) => referenceId === previousTargetId)
      : null;
    const observedPatrolBlocker = auxiliaryPatrolPursuitLocked
        && Number.isSafeInteger(unit.experimentBlockedByEnemyId)
      ? snapshot.find(({ referenceId }) => referenceId === unit.experimentBlockedByEnemyId)
      : null;
    if (observedPatrolBlocker?.alive && isHostile(self, observedPatrolBlocker)) {
      if (unit.patrolBlockerId === observedPatrolBlocker.referenceId) {
        unit.patrolBlockerTicks = (unit.patrolBlockerTicks ?? 0) + 1;
      } else {
        unit.patrolBlockerId = observedPatrolBlocker.referenceId;
        unit.patrolBlockerTicks = 1;
      }
    } else if (!latchedPatrolBlocker) {
      delete unit.patrolBlockerId;
      delete unit.patrolBlockerTicks;
    }
    const patrolBlocker = latchedPatrolBlocker?.alive
      ? latchedPatrolBlocker
      : (unit.patrolBlockerTicks ?? 0) >= PATROL_BLOCKER_CAPTURE_TICKS
        ? observedPatrolBlocker
        : null;
    const nextTargetId = openingRangedPatrolLocked
      ? (isWithinReach(self, pursuitTarget) && targetAvailable(pursuitTarget)
        ? pursuitTarget.referenceId
        : null)
      : auxiliaryPatrolPursuitLocked
      ? (isWithinStopRange(self, pursuitTarget, { pairInteractions })
          && isWithinReach(self, pursuitTarget) && targetAvailable(pursuitTarget)
        ? pursuitTarget.referenceId
        : patrolBlocker?.alive && isHostile(self, patrolBlocker)
            && isWithinReach(self, patrolBlocker) && targetAvailable(patrolBlocker)
          ? patrolBlocker.referenceId
          : null)
      : pursuedClosed && isWithinReach(self, pursued) && targetAvailable(pursued)
        ? pursued.referenceId
        : (pursuedClosed && unit.mechanics?.ranged
          ? null
          : selection.target?.referenceId ?? null);
    if (nextTargetId === previousTargetId) continue;
    if (previousTargetId !== null && previousTargetId !== undefined) {
      if (!unit.mechanics?.ranged) {
        const previousIncoming = incomingMeleeEngagements.get(previousTargetId) ?? 0;
        if (previousIncoming <= 1) incomingMeleeEngagements.delete(previousTargetId);
        else incomingMeleeEngagements.set(previousTargetId, previousIncoming - 1);
      }
      events.push(event(tick, "engagement-ended", unit.referenceId, previousTargetId, {
        reason: snapshot.find(({ referenceId }) => referenceId === previousTargetId)?.alive
          ? "contact-lost"
          : "target-dead",
      }));
    }
    unit.engagedTargetId = nextTargetId;
    if (nextTargetId === null) continue;
    if (!unit.mechanics?.ranged) {
      incomingMeleeEngagements.set(
        nextTargetId,
        (incomingMeleeEngagements.get(nextTargetId) ?? 0) + 1,
      );
    }
    unit.avoidance = null;
    events.push(event(tick, "engagement-started", unit.referenceId, nextTargetId, {
      sweptToi: selection.contact?.sweptToi ?? null,
      finalSurfaceGap: selection.contact?.finalSurfaceGap ?? null,
    }));
  }
}


// One attack cycle, matching the lifecycle the authorized tapes expose:
//
//   swing start ---- attackDelayTicks ----> hit ---- rest of animation ---->
//   animation end ---- remainder of the reload ----> next swing start
//
// The unit is committed for the whole animation (it neither moves nor retargets
// while `action === "attacking"`), the hit lands halfway through it, and the
// reload runs swing-start to swing-start so the cadence is exactly reload_seconds.
//
// A swing only STARTS from a standstill: either the movement stop rule is
// satisfied against the engaged target, or the unit did not move this tick
// (blocked, or already parked). The steppe tapes show approaching lancers
// never swinging mid-walk — they close to collision gap <= 1.0 first — while
// blocked back-line lancers swing from the wider outline envelope.
function releaseChargeVolley(unit, target, spec, tick, events, projectiles,
  velocities, shotRng) {
  // The volley leaves the unit whether or not anything is left to aim at; an
  // unreleased cycle abandoned earlier (validateAttackTargets) keeps its
  // charge instead.
  unit.charge = 0;
  if (!target?.alive || !isHostile(unit, target)) return;
  const distance = Math.hypot(target.x - unit.x, target.y - unit.y);
  const flight = Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed));
  const amount = chargeProjectileDamage(spec, target);
  const ordinaryRanged = rangedSpec(unit.mechanics);
  const accuracy = ordinaryRanged?.baseAccuracyPercent ?? 100;
  let aimedProjectiles = 0;
  for (let index = 0; index < spec.projectileCount; index += 1) {
    if (accuracy < 100 && nextShotRoll(shotRng) * 100 >= accuracy) continue;
    aimedProjectiles += 1;
    projectiles.push({
      kind: "charge",
      actorId: unit.referenceId,
      actorOwner: unit.owner,
      actorRelationByOwner: unit.relationByOwner,
      actorMechanics: unit.mechanics,
      targetId: target.referenceId,
      firedTick: tick,
      arrivalTick: tick + flight,
      index,
      amount,
    });
  }
  if (spec.addsToNormalAttack) {
    const ranged = rangedSpec(unit.mechanics);
    if (ranged) {
      releaseRangedShot(unit, target, ranged, tick, events, projectiles,
        velocities, shotRng, { projectileIndex: spec.projectileCount });
      if (unit.specialState
          && ranged.firstAttackExtraProjectiles === spec.projectileCount) {
        unit.specialState.firstAttackUsed = true;
      }
    }
  }
  events.push(event(tick, "charge-volley", unit.referenceId, target.referenceId, {
    projectiles: spec.projectileCount,
    aimedProjectiles,
    arrivalTick: tick + flight,
    amount,
  }));
}


// A ranged shot leaves the unit on its damage frame, aimed at the target's
// CURRENT position (smart_mode 0 in the dat: no leading). The projectile is a
// physical point flying the line at the projectile unit's dat speed: it hits
// the moment it meets the target's collision box (an APPROACHING target walks
// into it early — tape hits show displacement up to 1.04 toward the shooter),
// and expires at its aim point if the target left its box (walked-away misses
// start at displacement 0.23) or died mid-flight. Damage is the ordinary
// class rule, captured at fire.
// Ballistics lead (dat attribute 19 bit 1, set by tech 93 on its projectile
// list): the shot is aimed at the target's PREDICTED position — current
// position plus its current per-tick displacement times the flight time to
// the led point (two-pass fixed point). Measured on the kiting archives:
// every one of 3270 beat-assigned shots lands on champions running
// tangentially at 1.056 tiles/s (probe C, damage landed p50 = 100% of
// assigned), which aim-at-fire-position cannot produce; targets that CHANGE
// direction mid-flight still escape, which is what the avs walked-away
// residue shows for unled straight-line semantics.
function leadAimPoint(unit, target, spec, velocities) {
  const velocity = velocities?.get(target.referenceId);
  if (!velocity || (velocity.dx === 0 && velocity.dy === 0)) {
    return { x: target.x, y: target.y };
  }
  const stepLength = spec.projectileSpeed / TICKS_PER_SECOND;
  let aimX = target.x;
  let aimY = target.y;
  for (let pass = 0; pass < 2; pass += 1) {
    const flightTicks = Math.hypot(aimX - unit.x, aimY - unit.y) / stepLength;
    aimX = target.x + velocity.dx * flightTicks;
    aimY = target.y + velocity.dy * flightTicks;
  }
  return { x: aimX, y: aimY };
}


// Deterministic per-shot RNG (mulberry32 step over world.shotRng.state),
// consumed in the deterministic unit-loop order. Present only in worlds
// where a unit can miss or blast.
function nextShotRoll(shotRng) {
  const a = (shotRng.state + 0x6d2b79f5) >>> 0;
  shotRng.state = a;
  let t = Math.imul(a ^ (a >>> 15), 1 | a);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}


function releaseRangedShot(unit, target, spec, tick, events, projectiles, velocities, shotRng,
  options = {}) {
  if (!target?.alive || !isHostile(unit, target)) return;
  // A Mangonel-family unit can acquire and enter its attack animation while
  // the freshly issued PATROL command is still in its reaction phase.  The
  // live projectile keeps the command's ground destination in that boundary
  // state; once patrol motion is active, subsequent shells use the ordinary
  // target aim.  In every one of the five Onager/Paladin captures, shells
  // released at 0.58-0.79 s land at the authored (2, 13) patrol point, while
  // releases from 1.52 s onward land at their selected unit's fire position.
  // This is command-state projectile behavior shared by the Onager family,
  // not an outcome- or matchup-specific delay/waypoint.
  const patrolCommandAim = hasOnagerFamilyBehavior(unit)
    && unit.moveOrder?.kind === "scenario-patrol"
    && tick < (unit.moveOrder.motionStartTick ?? -Infinity)
    && Number.isFinite(unit.moveOrder.commandX)
    && Number.isFinite(unit.moveOrder.commandY);
  let aim = patrolCommandAim
    ? { x: unit.moveOrder.commandX, y: unit.moveOrder.commandY }
    : (spec.smartMode & 1) === 1
      ? leadAimPoint(unit, target, spec, velocities)
      : { x: target.x, y: target.y };
  let originX = unit.x;
  let originY = unit.y;
  const delayedImpactExplosion = delayedImpactExplosionSpec(unit, spec.weaponMode);
  const spawnArea = options.spawnArea;
  if (Array.isArray(spawnArea)
      && ((spawnArea[0] ?? 0) > 0 || (spawnArea[1] ?? 0) > 0)) {
    // DAT projectile-spawning area offsets secondary projectiles onto a
    // parallel line rather than re-aiming every extra at the victim's centre.
    // Width is lateral to the shot; length is along it. Moving both origin and
    // aim by the same offset preserves projectile velocity while naturally
    // allowing a displaced extra arrow to pass beside a small target.
    const dx = aim.x - originX;
    const dy = aim.y - originY;
    const length = Math.hypot(dx, dy);
    if (length > 1e-9) {
      const forwardX = dx / length;
      const forwardY = dy / length;
      const lateralX = -forwardY;
      const lateralY = forwardX;
      const lateral = (nextShotRoll(shotRng) - 0.5) * spawnArea[0];
      const longitudinal = (nextShotRoll(shotRng) - 0.5) * spawnArea[1];
      const offsetX = lateralX * lateral + forwardX * longitudinal;
      const offsetY = lateralY * lateral + forwardY * longitudinal;
      originX += offsetX;
      originY += offsetY;
      aim = { x: aim.x + offsetX, y: aim.y + offsetY };
    }
  }
  let distance = Math.hypot(aim.x - originX, aim.y - originY);
  if (distance <= 1e-9) return;
  const stepLength = spec.projectileSpeed / TICKS_PER_SECOND;
  // Mangonel-family shell: flies OVER intervening units to the aim point and
  // explodes there — blast radius = the firing unit's dat blast width, full
  // damage where the impact point is inside a victim's box, linear taper to
  // the edge (wiki/tape-corroborated), friendly fire on (dat 1.0). The 9
  // visual secondaries land scattered over the dat spawning area for the
  // floor 1 damage each (their dat attack lists are EMPTY — the tapes'
  // repeated 1.0 quanta).
  if (spec.blastRadius > 0) {
    // The raw projectile arc is exported for flight-time analysis, but the
    // current tape-backed rule still uses ground distance / DAT speed. A
    // parabola-length multiplier remains a hypothesis until the new live
    // Onager tracks independently establish it.
    const flight = Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed));
    projectiles.push({
      kind: "shell",
      actorId: unit.referenceId,
      actorOwner: unit.owner,
      actorRelationByOwner: unit.relationByOwner,
      actorMechanics: unit.mechanics,
      targetId: target.referenceId,
      aimX: aim.x,
      aimY: aim.y,
      blastRadius: spec.blastRadius,
      firedTick: tick,
      arrivalTick: tick + flight,
      index: 0,
      delayedImpactExplosion,
    });
    const debris = siegeDebrisLandingPoints({
      impactX: aim.x,
      impactY: aim.y,
      shooterX: originX,
      shooterY: originY,
      count: spec.secondaryCount,
    });
    for (const landing of debris) {
      projectiles.push({
        kind: "pebble",
        actorId: unit.referenceId,
        actorOwner: unit.owner,
        targetId: target.referenceId,
        aimX: landing.x,
        aimY: landing.y,
        halfWidth: spec.secondaryHalfWidth,
        firedTick: tick,
        arrivalTick: tick + flight,
        index: landing.index + 1,
      });
    }
    return;
  }
  // Accuracy roll (dat accuracy_percent < 100 only — the hand cannoneer's
  // 75): a missed shot scatters uniformly within the dat dispersion
  // half-radius and becomes a STRAY that hits the first enemy whose box it
  // meets for HALF damage (tape full/half quanta pairs 22/11, 11/5.5, 8/4).
  const accuracyPercent = options.accuracyPercent ?? spec.accuracyPercent;
  const projectileIndex = options.projectileIndex ?? 0;
  if (spec.impactSplashRadius > 0) {
    if (accuracyPercent < 100
        && nextShotRoll(shotRng) * 100 >= accuracyPercent) {
      aim = displacedAimPoint({
        aimX: aim.x,
        aimY: aim.y,
        dispersionTiles: spec.dispersionTiles,
        radialRoll: nextShotRoll(shotRng),
        angleRoll: nextShotRoll(shotRng),
      });
      distance = Math.hypot(aim.x - originX, aim.y - originY);
    }
    projectiles.push({
      kind: "grenade",
      actorId: unit.referenceId,
      actorOwner: unit.owner,
      actorRelationByOwner: unit.relationByOwner,
      actorMechanics: unit.mechanics,
      attackClasses: options.attackClasses ?? null,
      targetId: target.referenceId,
      aimX: aim.x,
      aimY: aim.y,
      blastRadius: spec.impactSplashRadius,
      damageFraction: spec.impactSplashDamageFraction,
      friendlyFireFraction: spec.impactSplashFriendlyFireFraction,
      firedTick: tick,
      arrivalTick: tick + Math.max(1,
        secondsToTicksCeil(distance / spec.projectileSpeed)),
      index: projectileIndex,
      delayedImpactExplosion,
    });
    return;
  }
  if (accuracyPercent < 100
      && nextShotRoll(shotRng) * 100 >= accuracyPercent) {
    aim = displacedAimPoint({
      aimX: aim.x,
      aimY: aim.y,
      dispersionTiles: spec.dispersionTiles,
      radialRoll: nextShotRoll(shotRng),
      angleRoll: nextShotRoll(shotRng),
    });
    distance = Math.hypot(aim.x - originX, aim.y - originY);
    if (distance <= 1e-9) return;
    projectiles.push({
      kind: "stray",
      actorId: unit.referenceId,
      actorOwner: unit.owner,
      actorRelationByOwner: unit.relationByOwner,
      actorMechanics: unit.mechanics,
      attackClasses: options.attackClasses ?? null,
      targetId: target.referenceId,
      aimX: aim.x,
      aimY: aim.y,
      x: originX,
      y: originY,
      stepX: ((aim.x - originX) / distance) * stepLength,
      stepY: ((aim.y - originY) / distance) * stepLength,
      stepLength,
      traveled: 0,
      totalDistance: distance,
      halfWidth: spec.projectileHalfWidth,
      damageFraction: spec.fullDamageOnUnintended ? 1 : MISS_DAMAGE_FRACTION,
      firedTick: tick,
      arrivalTick: tick + Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed)),
      index: projectileIndex,
      delayedImpactExplosion,
    });
    return;
  }
  if (spec.passThrough) {
    // Scorpion-family bolt: flies the line and damages every enemy whose
    // collision box crosses its width; the action target takes full damage,
    // everyone else half (see PASS_THROUGH_DAMAGE_FRACTION). Damage is
    // per-victim class rule, resolved at crossing time.
    const total = distance + BOLT_OVERSHOOT_TILES;
    projectiles.push({
      kind: "bolt",
      actorId: unit.referenceId,
      actorOwner: unit.owner,
      actorRelationByOwner: unit.relationByOwner,
      actorMechanics: unit.mechanics,
      attackClasses: options.attackClasses ?? null,
      targetId: target.referenceId,
      x: originX,
      y: originY,
      stepX: ((aim.x - originX) / distance) * stepLength,
      stepY: ((aim.y - originY) / distance) * stepLength,
      stepLength,
      traveled: 0,
      totalDistance: total,
      halfWidth: spec.projectileHalfWidth,
      passThroughDamageFraction: spec.passThroughDamageFraction,
      passThroughCount: spec.passThroughCount,
      firedTick: tick,
      arrivalTick: tick + Math.max(1, secondsToTicksCeil(total / spec.projectileSpeed)),
      index: projectileIndex,
      hitIds: [],
    });
    return;
  }
  projectiles.push({
    kind: "ranged",
    actorId: unit.referenceId,
    actorOwner: unit.owner,
    actorRelationByOwner: unit.relationByOwner,
    actorMechanics: unit.mechanics,
    attackClasses: options.attackClasses ?? null,
    targetId: target.referenceId,
    originalTargetId: target.referenceId,
    aimX: aim.x,
    aimY: aim.y,
    x: originX,
    y: originY,
    stepX: ((aim.x - originX) / distance) * stepLength,
    stepY: ((aim.y - originY) / distance) * stepLength,
    stepLength,
    traveled: 0,
    totalDistance: distance,
    firedTick: tick,
    // The stepping loop below is the authority; arrivalTick is a cap so a
    // projectile can never outlive its aim distance.
    arrivalTick: tick + Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed)),
    index: projectileIndex,
    halfWidth: spec.projectileHalfWidth,
    // Accurate projectiles obey the projectile unit's DAT hit mode. Mode 0
    // ignores every non-target body; missed-accuracy shots use the separate
    // `stray` path above and can still hit an unintended body for half damage.
    hitMode: options.projectileHitMode ?? spec.projectileHitMode,
    amount: calculateDamage(unit, target, {
      attackClasses: options.attackClasses ?? undefined,
    }),
    impactSplashRadius: spec.impactSplashRadius,
    impactSplashDamageFraction: spec.impactSplashDamageFraction,
    impactSplashFriendlyFireFraction: spec.impactSplashFriendlyFireFraction,
    impactHazard: unitEffects(unit).impact_hazard_radius_tiles > 0 ? {
      radiusTiles: unitEffects(unit).impact_hazard_radius_tiles,
      durationSeconds: unitEffects(unit).impact_hazard_duration_seconds,
      damagePerSecond: unitEffects(unit).impact_hazard_damage_per_second,
      stacks: unitEffects(unit).impact_hazard_stacks === true,
    } : null,
    delayedImpactExplosion,
  });
}


function rangedVolleyExtraCount(unit, spec) {
  const openingExtras = unit.specialState?.firstAttackUsed === false
    ? spec.firstAttackExtraProjectiles
    : 0;
  return spec.extraProjectileCount + openingExtras;
}


function releaseRangedExtraProjectile(unit, target, spec, tick, events,
  projectiles, velocities, shotRng, projectileIndex) {
  releaseRangedShot(unit, target, spec, tick, events, projectiles,
    velocities, shotRng, {
      projectileIndex,
      attackClasses: spec.extraProjectileAttacks ?? undefined,
      // Extra-arrow inaccuracy comes from its displaced DAT spawn lane. The
      // final attack accuracy is shared with the primary; do not add a second
      // independent base-accuracy scatter roll here.
      accuracyPercent: spec.accuracyPercent,
      spawnArea: spec.spawnArea,
      projectileHitMode: spec.secondaryProjectileHitMode,
    });
}


function reloadTicksAfterFinalProjectile(unit, tick) {
  // DAT reload is measured from the final projectile release to the next
  // release. The next attack's windup therefore occupies the tail of that
  // interval, just as an ordinary unit's windup sits inside its reload cycle.
  return Math.max(0,
    reloadTicksForUnit(unit, tick) - attackDelayTicksForUnit(unit));
}


function rangedVolleyReleaseSize(spec, remaining, shotRng) {
  if (remaining <= 1) return 1;
  if (spec.volleyDoubleReleasePercent > 0
      && nextShotRoll(shotRng) * 100 < spec.volleyDoubleReleasePercent) {
    return Math.min(2, remaining);
  }
  return Math.min(spec.volleyReleaseSize, remaining);
}


function pendingVolleyReplacementTarget(unit, units) {
  const candidates = Object.freeze(units
    .filter((candidate) => (
      !isHostile(unit, candidate)
      || (candidate.alive && isWithinReach(unit, candidate))
    ))
    .map(freezeUnit));
  return selectPursuitTarget(
    { ...freezeUnit(unit), pursuitTargetId: null },
    candidates,
  );
}


function releaseRangedVolley(unit, target, spec, tick, events, projectiles,
  velocities, shotRng) {
  releaseRangedShot(unit, target, spec, tick, events, projectiles,
    velocities, shotRng, { projectileIndex: 0 });
  const extraCount = rangedVolleyExtraCount(unit, spec);
  if (spec.reloadAfterFinalProjectile && spec.volleyIntervalTicks > 0
      && extraCount > 0) {
    const totalProjectiles = extraCount + 1;
    const firstReleaseCount = rangedVolleyReleaseSize(
      spec, totalProjectiles, shotRng);
    for (let index = 1; index < firstReleaseCount; index += 1) {
      releaseRangedExtraProjectile(unit, target, spec, tick, events,
        projectiles, velocities, shotRng, index);
    }
    if (firstReleaseCount < totalProjectiles) {
      unit.pendingVolley = {
        targetId: target.referenceId,
        nextProjectileIndex: firstReleaseCount,
        totalProjectiles,
        nextReleaseTick: tick + spec.volleyIntervalTicks,
      };
    } else {
      unit.actionTimers.reload = reloadTicksAfterFinalProjectile(unit, tick);
    }
    if (unit.specialState) unit.specialState.firstAttackUsed = true;
    events.push(event(tick, "ranged-volley", unit.referenceId, target.referenceId, {
      projectiles: totalProjectiles,
      projectilesPerRelease: spec.volleyReleaseSize,
      releaseIntervalTicks: spec.volleyIntervalTicks,
      weaponMode: spec.weaponMode,
    }));
    return;
  }
  for (let index = 0; index < extraCount; index += 1) {
    releaseRangedExtraProjectile(unit, target, spec, tick, events,
      projectiles, velocities, shotRng, index + 1);
  }
  if (unit.specialState) unit.specialState.firstAttackUsed = true;
  if (extraCount > 0) {
    events.push(event(tick, "ranged-volley", unit.referenceId, target?.referenceId, {
      projectiles: extraCount + 1,
    }));
  }
}


function finishPendingRangedVolley(unit, tick, events, reason) {
  const pending = unit.pendingVolley;
  if (!pending) return;
  delete unit.pendingVolley;
  unit.actionTimers.reload = reloadTicksAfterFinalProjectile(unit, tick);
  events.push(event(tick, "ranged-volley-ended", unit.referenceId,
    pending.targetId, {
      reason,
      releasedProjectiles: pending.nextProjectileIndex,
      projectiles: pending.totalProjectiles,
    }));
}


function progressPendingRangedVolley(unit, units, byReference, tick, events,
  projectiles, velocities, shotRng) {
  const pending = unit.pendingVolley;
  if (!pending) return;
  const spec = rangedSpec(unit.mechanics);
  if (!spec?.reloadAfterFinalProjectile || spec.volleyIntervalTicks <= 0) {
    throw new Error(`unit ${unit.referenceId} has invalid pending ranged volley`);
  }
  let target = byReference.get(pending.targetId);
  if (!target?.alive || !isHostile(unit, target)) {
    const invalidTargetId = pending.targetId;
    target = pendingVolleyReplacementTarget(unit, units);
    if (target === null) return;
    pending.targetId = target.referenceId;
    unit.attackTargetId = target.referenceId;
    unit.engagedTargetId = target.referenceId;
    unit.pursuitTargetId = target.referenceId;
    events.push(event(tick, "ranged-volley-retargeted", unit.referenceId,
      target.referenceId, {
        fromTargetId: invalidTargetId,
        nextProjectileIndex: pending.nextProjectileIndex,
        projectiles: pending.totalProjectiles,
      }));
  }
  if (tick < pending.nextReleaseTick) return;
  const releaseSize = rangedVolleyReleaseSize(
    spec,
    pending.totalProjectiles - pending.nextProjectileIndex,
    shotRng,
  );
  const endIndex = Math.min(pending.totalProjectiles,
    pending.nextProjectileIndex + releaseSize);
  for (let index = pending.nextProjectileIndex; index < endIndex; index += 1) {
    releaseRangedExtraProjectile(unit, target, spec, tick, events,
      projectiles, velocities, shotRng, index);
  }
  pending.nextProjectileIndex = endIndex;
  if (pending.nextProjectileIndex >= pending.totalProjectiles) {
    finishPendingRangedVolley(unit, tick, events, "complete");
    return;
  }
  pending.nextReleaseTick += spec.volleyIntervalTicks;
}


function progressAttacks(units, tick, events, movedIds, projectiles,
  velocities, shotRng) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  const ready = [];
  for (const unit of units) {
    if (!unit.alive) continue;
    if (unit.actionTimers.reload > 0) unit.actionTimers.reload -= 1;
    progressPendingRangedVolley(unit, units, byReference, tick, events,
      projectiles, velocities, shotRng);
    // Charge regeneration (dat recharge_rate per second). At the Fire
    // Lancer's 1/30 s no recorded fight lasts long enough for a refire, but
    // the rate is sourced and runs regardless.
    if (unit.charge !== undefined) {
      const spec = chargeSpec(unit.mechanics);
      unit.charge = Math.min(
        spec.maxCharge,
        unit.charge + spec.rechargeRate / TICKS_PER_SECOND,
      );
    }

    if (unit.action === "attacking") {
      // A charge cycle runs on the dat special_graphic animation with its own
      // (later) release frame; a melee cycle keeps the attack graphic timing.
      const charge = unit.attackKind === "charge" ? chargeSpec(unit.mechanics) : null;
      const areaCharge = unit.attackKind === "melee-charge"
        ? meleeChargeSpec(unit.mechanics) : null;
      const delay = charge
        ? charge.windupTicks
        : areaCharge?.windupTicks ?? attackDelayTicksForUnit(unit);
      const rawAnimation = charge
        ? charge.animationTicks
        : areaCharge?.animationTicks ?? attackAnimationTicks(unit.mechanics);
      // Ordinary attack graphics are playback-synchronised to the weapon
      // cycle. A long source graphic must not impose a second, slower reload
      // cap (most visibly, Elite Samurai's 1.60 s graphic versus its Japanese
      // 1.425 s reload). Preserve the release frame, but finish recovery when
      // the shorter weapon cycle has elapsed. Special charge animations keep
      // their authored duration.
      const animation = charge || areaCharge
        ? rawAnimation
        : Math.max(delay, Math.min(rawAnimation, reloadTicksForUnit(unit, tick)));
      unit.actionTimers.swing += 1;
      unit.actionTimers.windup = Math.max(0, delay - unit.actionTimers.swing);
      if (unit.actionTimers.swing === delay) {
        const target = byReference.get(unit.attackTargetId);
        const ranged = rangedSpec(unit.mechanics);
        if (charge) {
          releaseChargeVolley(unit, target, charge, tick, events, projectiles,
            velocities, shotRng);
        } else if (ranged) {
          releaseRangedVolley(unit, target, ranged, tick, events, projectiles,
            velocities, shotRng);
        } else {
          const strike = target ? meleeAttackAmount(
            unit,
            target,
            tick,
            areaCharge ? { charged: true } : {},
          ) : {
            amount: 0, charged: false, chargeDamage: 0,
          };
          ready.push({
            type: "attack-ready",
            readyTick: tick,
            actorId: unit.referenceId,
            targetId: unit.attackTargetId,
            amount: strike.amount,
            charged: strike.charged,
            chargeDamage: strike.chargeDamage,
          });
        }
      }
      if (unit.actionTimers.swing >= animation && !unit.pendingVolley) {
        // Animation finished: the unit is free to retarget again. A unit whose
        // target died mid-recovery only becomes available here, which is why the
        // tapes show killers retargeting ~half an animation after the kill while
        // bystanders (still winding up) retarget on the very next tick.
        unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
        unit.attackTargetId = null;
        if (charge) {
          // Completing the CHARGE cycle re-enters combat through the engine's
          // acquisition reaction lag (the unit's own measured draw): across
          // byte-identical tape repeats the first post-charge melee swing
          // varies by 1.3 s (cvf 1v1: 5.56/5.87/6.85 s) — the acquisition-roll
          // signature, not any deterministic cycle rule. The unit still WALKS
          // toward its pursuit target during the lag (fvs/fve tapes), it just
          // does not engage; without this the sim swings at the earliest edge
          // of every tape band and each lancer gains a full melee hit.
          unit.actionTimers.acquire = unit.acquireDelayTicks ?? 0;
        }
        delete unit.attackKind;
        unit.actionTimers.swing = 0;
      }
      continue;
    }

    if (unit.actionTimers.reload === 0 && unit.action === "reload") {
      unit.action = "idle";
    }

    // Charge volley: the unit's FIRST attack cycle whenever its charge is
    // full. It fires at the acquisition (or engaged) target from wherever it
    // stands -- 1.5-5.2 tiles out in the tapes, line of sight bounding -- with
    // no reach or standstill gate: holdsForChargeVolley pinned the unit this
    // tick, and every recorded volley leaves a standing unit.
    const spec = unit.charge !== undefined ? chargeSpec(unit.mechanics) : null;
    if (
      spec
      && unit.action === "idle"
      && unit.actionTimers.reload === 0
      && unit.charge + 1e-9 >= spec.maxCharge
    ) {
      const chargeTarget = byReference.get(unit.engagedTargetId)
        ?? byReference.get(unit.pursuitTargetId);
      if (chargeTarget?.alive && isHostile(unit, chargeTarget)) {
        const distance = Math.hypot(chargeTarget.x - unit.x, chargeTarget.y - unit.y);
        if (distance <= spec.attackRangeTiles) {
          events.push(createAttackStartEvent({
            tick,
            actorId: unit.referenceId,
            targetId: chargeTarget.referenceId,
            readyTick: tick + spec.windupTicks,
            kind: "charge",
          }));
          unit.action = "attacking";
          unit.attackKind = "charge";
          unit.attackTargetId = chargeTarget.referenceId;
          unit.actionTimers.swing = 0;
          unit.actionTimers.windup = spec.windupTicks;
          unit.actionTimers.reload = reloadTicksForUnit(unit, tick);
          continue;
        }
      }
    }

    const target = byReference.get(unit.engagedTargetId);
    if (
      unit.actionTimers.reload !== 0 ||
      !target?.alive ||
      !isHostile(unit, target)
    ) continue;
    // Blocking may preserve a live target lock, but it does not extend the
    // unit's weapon. A committed windup above is allowed to finish after its
    // target moves; every NEW swing must begin inside the ordinary DAT
    // outline attack envelope. Without this gate, a stationary crowd member
    // could repeatedly attack anything inside line of sight merely because
    // collision prevented it from moving.
    if (!isWithinActiveAttackReach(unit, target, tick)) continue;
    // A range-zero weapon begins a new cycle only on its physical stop
    // surface. Across the fresh Paladin/Champion mixed tapes, Euclidean start
    // maxima (0.732-0.806) are exactly the diagonal image of collision extents
    // plus the 0.1 melee stop tolerance, never the wider outline envelope.
    // Reach fighters retain outline reach so a Steppe Lancer can attack over
    // its front rank; an already-released swing above may still finish after
    // separation.
    const areaCharge = readyMeleeAreaCharge(unit, tick);
    if (!areaCharge && hasMeleeMode(unit)
        && (unit.mechanics.attack_range_tiles ?? 0) === 0
        && !isWithinStopRange(unit, target)) continue;
    if (!areaCharge
        && !isWithinStopRange(unit, target)
        && movedIds.has(unit.referenceId)) continue;

    const delay = areaCharge?.windupTicks ?? attackDelayTicksForUnit(unit);
    const readyTick = tick + delay;
    events.push(createAttackStartEvent({
      tick,
      actorId: unit.referenceId,
      targetId: target.referenceId,
      readyTick,
      ...(areaCharge ? { kind: "melee-charge" } : {}),
    }));
    unit.action = "attacking";
    if (areaCharge) unit.attackKind = "melee-charge";
    if (unit.moveOrder?.kind === "scenario-patrol") {
      unit.patrolOpeningAttackStarted = true;
    }
    unit.attackTargetId = target.referenceId;
    unit.actionTimers.swing = 0;
    unit.actionTimers.windup = delay;
    const ranged = rangedSpec(unit.mechanics);
    unit.actionTimers.reload = ranged?.reloadAfterFinalProjectile
      && ranged.volleyIntervalTicks > 0
      && rangedVolleyExtraCount(unit, ranged) > 0
      ? 0
      : reloadTicksForUnit(unit, tick);
    if (delay === 0) {
      if (ranged) {
        // A literal zero-frame projectile leaves on the swing-start tick. The
        // ordinary attacking-loop release condition is crossed only by a
        // positive windup, so service the zero boundary here rather than
        // misclassifying it as an immediate melee hit.
        releaseRangedVolley(unit, target, ranged, tick, events, projectiles,
          velocities, shotRng);
      } else {
        const strike = meleeAttackAmount(
          unit,
          target,
          tick,
          areaCharge ? { charged: true } : {},
        );
        ready.push({
          type: "attack-ready",
          readyTick,
          actorId: unit.referenceId,
          targetId: target.referenceId,
          amount: strike.amount,
          charged: strike.charged,
          chargeDamage: strike.chargeDamage,
        });
      }
    }
  }
  return ready;
}


function commitReadyAttacks(units, ready, tick, events) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const attack of orderReadyAttacks(ready)) {
    const actor = byReference.get(attack.actorId);
    const target = byReference.get(attack.targetId);
    if (!actor?.alive) {
      events.push(createAttackCanceledEvent({
        tick,
        actorId: attack.actorId,
        targetId: attack.targetId,
        readyTick: attack.readyTick,
        reason: "actor-dead",
      }));
      continue;
    }
    if (
      !target?.alive
      || !isHostile(actor, target)
      || actor.attackTargetId !== target.referenceId
    ) {
      actor.action = actor.actionTimers.reload > 0 ? "reload" : "idle";
      actor.attackTargetId = null;
      actor.actionTimers.windup = 0;
      events.push(createAttackCanceledEvent({
        tick,
        actorId: attack.actorId,
        targetId: attack.targetId,
        readyTick: attack.readyTick,
        reason: !target?.alive ? "target-dead" : "target-invalidated",
      }));
      continue;
    }

    // The hit lands mid-animation; the actor stays committed to the rest of its
    // swing. Its reload was started at swing start, so the cadence is unaffected.
    applyCommittedDamage(units, attack.actorId, target, attack.amount,
      attack.readyTick, tick, events, {
        triggersOnHit: true,
        charged: attack.charged === true,
      });
    if (attack.charged && actor.specialState) {
      const rechargeSeconds = meleeChargeSpec(actor.mechanics)?.rechargeSeconds
        ?? unitEffects(actor).charge_recharge_time ?? 0;
      actor.specialState.meleeChargeReadyTick = tick
        + secondsToTicksCeil(rechargeSeconds);
      actor.specialState.chargedSpeedActive = false;
      actor.specialState.chargedSpeedTargetId = null;
    }

    // Trample: the committed hit also blasts every enemy whose collision box
    // intersects the attacker's blast circle (see trampleSpec for the sourced
    // rule). Victims are struck in unit order at this same instant, each for
    // its own post-armor fraction; a killing trample clamps at 0 like any hit.
    const blast = trampleSpec(actor.mechanics);
    if (blast && (!blast.chargedOnly || attack.charged)) {
      const attackDx = target.x - actor.x;
      const attackDy = target.y - actor.y;
      const attackLength = Math.hypot(attackDx, attackDy) || 1;
      const forwardX = attackDx / attackLength;
      const forwardY = attackDy / attackLength;
      for (const victim of units) {
        if (!victim.alive || !isHostile(actor, victim)) continue;
        if (victim.referenceId === target.referenceId) continue;
        const victimRadius = collisionRadius(victim);
        const dx = victim.x - actor.x;
        const dy = victim.y - actor.y;
        if (blast.shape === "forward-cone") {
          // AoE2 blast mode 162 is a one-tile, 90-degree cone in the attack
          // direction. Unlike radial blast, the directional flag tests the
          // victim's position in the forward wedge; collision size does not
          // widen the cone (doing so turns a nominally narrow melee sweep into
          // near-radial damage in a packed formation).
          const forward = dx * forwardX + dy * forwardY;
          const lateral = Math.abs(dx * -forwardY + dy * forwardX);
          const sideSlope = Math.tan(blast.halfAngleRadians ?? Math.PI / 4);
          if (forward <= 0
              || forward > blast.widthTiles + 1e-12
              || lateral > forward * sideSlope + 1e-12) continue;
        } else {
          const reach = Math.hypot(
            Math.max(0, Math.abs(dx) - victimRadius),
            Math.max(0, Math.abs(dy) - victimRadius),
          );
          if (reach > blast.widthTiles + 1e-12) continue;
        }
        const splashBaseDamage = calculateDamage(actor, victim)
          + (attack.charged ? (attack.chargeDamage ?? 0) : 0);
        applyCommittedDamage(units, attack.actorId, victim,
          blast.damageFraction * splashBaseDamage,
          attack.readyTick, tick, events, { kind: "trample" });
      }
    }
  }
}


// Charge projectiles in flight land on their volley's target when their
// arrival tick comes up, after this tick's melee commits. A projectile whose
// target died mid-flight vanishes (the two no-damage tape volleys); the
// firer's own later death does not recall a projectile already in the air.
// The tapes' residual in-flight scatter (2.58 of 3 land on average, 88% on
// the target) is not resolvable at the recorder's 10 Hz missile sampling and
// is accepted as a documented overshoot, not modelled.
function addImpactHazard(projectile, x, y, tick, hazards, events) {
  if (!projectile.impactHazard || !hazards) return;
  const durationTicks = secondsToTicksCeil(
    projectile.impactHazard.durationSeconds ?? 0,
  );
  if (durationTicks <= 0 || !(projectile.impactHazard.damagePerSecond > 0)) return;
  hazards.push({
    id: `${projectile.actorId}:${projectile.firedTick}:${projectile.index}`,
    actorId: projectile.actorId,
    actorOwner: projectile.actorOwner,
    actorRelationByOwner: projectile.actorRelationByOwner,
    x,
    y,
    radiusTiles: projectile.impactHazard.radiusTiles,
    damagePerSecond: projectile.impactHazard.damagePerSecond,
    stacks: projectile.impactHazard.stacks === true,
    startTick: tick,
    endTick: tick + durationTicks,
  });
  events.push(event(tick, "impact-hazard-created", projectile.actorId,
    projectile.targetId, { x, y, endTick: tick + durationTicks }));
}


function queueDelayedImpactExplosions(projectile, x, y, tick, remaining) {
  const spec = projectile.delayedImpactExplosion;
  if (!spec) return;
  for (let index = 0; index < spec.repeatCount; index += 1) {
    remaining.push({
      kind: "delayed-impact-explosion",
      actorId: projectile.actorId,
      actorOwner: projectile.actorOwner,
      actorRelationByOwner: projectile.actorRelationByOwner,
      actorMechanics: projectile.actorMechanics,
      aimX: x,
      aimY: y,
      meleeAttack: spec.meleeAttack,
      blastRadius: spec.radiusTiles,
      firedTick: projectile.firedTick,
      arrivalTick: tick + spec.delayTicks + index * spec.repeatIntervalTicks,
      index,
    });
  }
}


function processChargeProjectiles(units, projectiles, tick, events, hazards = null) {
  const remaining = [];
  const resolved = [];
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  const ordered = [...projectiles].sort((left, right) => (
    left.actorId - right.actorId
    || left.targetId - right.targetId
    || left.firedTick - right.firedTick
    || left.index - right.index
  ));
  for (const projectile of ordered) {
    if (projectile.kind === "delayed-impact-explosion") {
      if (projectile.arrivalTick > tick) {
        remaining.push(projectile);
        continue;
      }
      const actor = {
        referenceId: projectile.actorId,
        owner: projectile.actorOwner,
        relationByOwner: projectile.actorRelationByOwner,
        mechanics: projectile.actorMechanics,
      };
      for (const victim of units) {
        if (!victim.alive || !isHostile(actor, victim)) continue;
        const reach = Math.hypot(
          victim.x - projectile.aimX,
          victim.y - projectile.aimY,
        ) - collisionRadius(victim);
        if (reach > projectile.blastRadius + 1e-12) continue;
        const amount = calculateDamage(actor, victim, {
          attackClasses: { 4: projectile.meleeAttack },
        });
        applyCommittedDamage(units, projectile.actorId, victim, amount,
          tick, tick, events, {
            kind: "delayed-impact-explosion",
            projectileIndex: projectile.index,
          });
      }
      continue;
    }
    if (projectile.kind === "bolt") {
      // Pass-through flight: advance one step, damage every enemy whose
      // collision box (expanded by the bolt's half width) contains the
      // point, once per victim, never despawning on impact.
      projectile.x += projectile.stepX;
      projectile.y += projectile.stepY;
      projectile.traveled += projectile.stepLength;
      for (const victim of units) {
        if (!victim.alive || !isHostile({
          referenceId: projectile.actorId,
          owner: projectile.actorOwner,
          relationByOwner: projectile.actorRelationByOwner,
        }, victim)) continue;
        if (projectile.hitIds.includes(victim.referenceId)) continue;
        const priorPassVictims = projectile.hitIds.filter((id) => (
          id !== projectile.targetId
        )).length;
        if (victim.referenceId !== projectile.targetId
            && projectile.passThroughCount > 0
            && priorPassVictims >= projectile.passThroughCount) continue;
        const dx = Math.abs(victim.x - projectile.x);
        const dy = Math.abs(victim.y - projectile.y);
        const reach = collisionRadius(victim) + projectile.halfWidth;
        if (Math.max(dx, dy) > reach + 1e-9) continue;
        projectile.hitIds.push(victim.referenceId);
        const full = calculateDamage({ mechanics: projectile.actorMechanics }, victim, {
          attackClasses: projectile.attackClasses ?? undefined,
        });
        const amount = victim.referenceId === projectile.targetId
          ? full
          : (projectile.passThroughDamageFraction
            ?? PASS_THROUGH_DAMAGE_FRACTION) * full;
        applyCommittedDamage(units, projectile.actorId, victim, amount,
          tick, tick, events,
          {
            kind: "bolt-projectile",
            projectileIndex: projectile.index * 100 + projectile.hitIds.length - 1,
            triggersOnHit: victim.referenceId === projectile.targetId,
          });
      }
      if (projectile.traveled < projectile.totalDistance - 1e-9) {
        remaining.push(projectile);
      }
      continue;
    }
    if (projectile.kind === "ranged") {
      // Physical point flight. DAT hit mode 0 checks only the assigned target,
      // so an accurate arrow passes through every other unit. Other hit modes
      // may be intercepted; those unintended hits take half damage (minimum
      // one). This is separate from accuracy misses, handled by `stray` below.
      projectile.x += projectile.stepX;
      projectile.y += projectile.stepY;
      projectile.traveled += projectile.stepLength;
      const actor = {
        referenceId: projectile.actorId,
        owner: projectile.actorOwner,
        relationByOwner: projectile.actorRelationByOwner,
      };
      const victim = units.filter((candidate) => {
        if (!candidate.alive || !isHostile(actor, candidate)) return false;
        if ((projectile.hitMode ?? 0) === 0
            && candidate.referenceId !== projectile.originalTargetId) return false;
        const dx = Math.abs(candidate.x - projectile.x);
        const dy = Math.abs(candidate.y - projectile.y);
        return Math.max(dx, dy)
          <= collisionRadius(candidate) + projectile.halfWidth + 1e-9;
      }).sort((left, right) => (
        Math.hypot(left.x - projectile.x, left.y - projectile.y)
          - Math.hypot(right.x - projectile.x, right.y - projectile.y)
        || left.referenceId - right.referenceId
      ))[0];
      if (victim) {
        const intended = victim.referenceId === projectile.originalTargetId;
        const full = calculateDamage(
          { mechanics: projectile.actorMechanics }, victim, {
            attackClasses: projectile.attackClasses ?? undefined,
          });
        projectile.targetId = victim.referenceId;
        projectile.amount = intended
          ? full
          : Math.max(1, MISS_DAMAGE_FRACTION * full);
        projectile.intendedHit = intended;
        resolved.push(projectile);
        continue;
      }
      // Expire at the aim point: the target died or left its box.
      if (projectile.traveled < projectile.totalDistance - 1e-9
          && tick < projectile.arrivalTick + 2) {
        remaining.push(projectile);
      } else {
        addImpactHazard(projectile, projectile.aimX, projectile.aimY,
          tick, hazards, events);
        queueDelayedImpactExplosions(
          projectile, projectile.aimX, projectile.aimY, tick, remaining);
      }
      continue;
    }
    if (projectile.kind === "stray") {
      // Missed-accuracy shot: follow the scattered physical trajectory and
      // deal half damage (minimum one) to the first hostile body it strikes.
      projectile.x += projectile.stepX;
      projectile.y += projectile.stepY;
      projectile.traveled += projectile.stepLength;
      const actor = {
        referenceId: projectile.actorId,
        owner: projectile.actorOwner,
        relationByOwner: projectile.actorRelationByOwner,
      };
      const crossing = units.filter((candidate) => {
        if (!candidate.alive || !isHostile(actor, candidate)) return false;
        const dx = Math.abs(candidate.x - projectile.x);
        const dy = Math.abs(candidate.y - projectile.y);
        return Math.max(dx, dy)
          <= collisionRadius(candidate) + projectile.halfWidth + 1e-9;
      }).sort((left, right) => (
        Math.hypot(left.x - projectile.x, left.y - projectile.y)
          - Math.hypot(right.x - projectile.x, right.y - projectile.y)
        || left.referenceId - right.referenceId
      ))[0];
      if (crossing) {
        const full = calculateDamage(
          { mechanics: projectile.actorMechanics }, crossing, {
            attackClasses: projectile.attackClasses ?? undefined,
          });
        applyCommittedDamage(units, projectile.actorId, crossing,
          Math.max(1, (projectile.damageFraction ?? MISS_DAMAGE_FRACTION) * full),
          tick, tick, events,
          { kind: "stray-projectile", projectileIndex: projectile.index });
        queueDelayedImpactExplosions(
          projectile, projectile.x, projectile.y, tick, remaining);
        continue;
      }
      if (projectile.traveled < projectile.totalDistance - 1e-9
          && tick < projectile.arrivalTick) {
        remaining.push(projectile);
        continue;
      }
      const victim = selectProjectileLandingVictim(
        units.filter((candidate) => candidate.alive && isHostile(actor, candidate)),
        projectile.aimX,
        projectile.aimY,
        projectile.halfWidth,
      );
      if (victim) {
        const full = calculateDamage({ mechanics: projectile.actorMechanics }, victim, {
          attackClasses: projectile.attackClasses ?? undefined,
        });
        applyCommittedDamage(units, projectile.actorId, victim,
          Math.max(1, (projectile.damageFraction ?? MISS_DAMAGE_FRACTION) * full),
          tick, tick, events,
          { kind: "stray-projectile", projectileIndex: projectile.index });
      }
      queueDelayedImpactExplosions(
        projectile, projectile.aimX, projectile.aimY, tick, remaining);
      continue;
    }
    if (projectile.kind === "grenade") {
      if (projectile.arrivalTick > tick) {
        remaining.push(projectile);
        continue;
      }
      const actor = {
        referenceId: projectile.actorId,
        owner: projectile.actorOwner,
        relationByOwner: projectile.actorRelationByOwner,
        mechanics: projectile.actorMechanics,
      };
      for (const victim of units) {
        if (!victim.alive || victim.referenceId === projectile.actorId) continue;
        const hostile = isHostile(actor, victim);
        if (!hostile && projectile.friendlyFireFraction <= 0) continue;
        const reach = Math.hypot(
          victim.x - projectile.aimX,
          victim.y - projectile.aimY,
        ) - collisionRadius(victim);
        if (reach > projectile.blastRadius + 1e-12) continue;
        const full = calculateDamage(actor, victim, {
          attackClasses: projectile.attackClasses ?? undefined,
        });
        const fraction = projectile.damageFraction
          * (hostile ? 1 : projectile.friendlyFireFraction);
        applyCommittedDamage(units, projectile.actorId, victim,
          Math.max(1, full * fraction), tick, tick, events, {
            kind: "grenade-splash",
            projectileIndex: projectile.index,
            triggersOnHit: victim.referenceId === projectile.targetId,
          });
      }
      queueDelayedImpactExplosions(
        projectile, projectile.aimX, projectile.aimY, tick, remaining);
      continue;
    }
    if (projectile.kind === "shell") {
      // Mangonel-family primary: arcs to the aim point and explodes on
      // arrival. Everything (BOTH owners — dat friendly_fire 1.0) inside the
      // blast radius takes the per-victim class damage, full when the impact
      // point is inside the victim's box, linearly tapered to the edge
      // otherwise, floored at 1.
      if (projectile.arrivalTick > tick) {
        remaining.push(projectile);
        continue;
      }
      for (const victim of units) {
        if (!victim.alive || victim.referenceId === projectile.actorId) continue;
        const fraction = blastFalloffFraction(
          victim, projectile.aimX, projectile.aimY, projectile.blastRadius);
        if (fraction === null) continue;
        const full = calculateDamage({ mechanics: projectile.actorMechanics }, victim);
        applyCommittedDamage(units, projectile.actorId, victim,
          Math.max(1, fraction * full), tick, tick, events,
          { kind: "shell-projectile", projectileIndex: 0 });
      }
      queueDelayedImpactExplosions(
        projectile, projectile.aimX, projectile.aimY, tick, remaining);
      continue;
    }
    if (projectile.kind === "pebble") {
      // Visual secondary (empty dat attack list): lands scattered over the
      // spawning area; anything whose box contains the landing point takes
      // the floor 1 damage.
      if (projectile.arrivalTick > tick) {
        remaining.push(projectile);
        continue;
      }
      const victim = selectProjectileLandingVictim(
        units.filter((candidate) => (
          candidate.alive && candidate.referenceId !== projectile.actorId
        )),
        projectile.aimX,
        projectile.aimY,
        projectile.halfWidth,
      );
      if (victim) {
        applyCommittedDamage(units, projectile.actorId, victim, 1,
          tick, tick, events,
          { kind: "pebble-projectile", projectileIndex: projectile.index });
      }
      continue;
    }
    if (projectile.arrivalTick > tick) {
      remaining.push(projectile);
      continue;
    }
    const target = byReference.get(projectile.targetId);
    if (!target?.alive) continue;
    resolved.push(projectile);
  }
  for (const projectile of resolved) {
    const target = byReference.get(projectile.targetId);
    if (!target?.alive) continue;
    applyCommittedDamage(units, projectile.actorId, target, projectile.amount,
      tick, tick, events, {
        kind: projectile.kind === "ranged" ? "ranged-projectile" : "charge-projectile",
        projectileIndex: projectile.index,
        triggersOnHit: projectile.intendedHit !== false,
        charge: projectile.kind === "charge",
      });
    addImpactHazard(projectile, projectile.x ?? target.x,
      projectile.y ?? target.y, tick, hazards, events);
    queueDelayedImpactExplosions(
      projectile,
      projectile.x ?? target.x,
      projectile.y ?? target.y,
      tick,
      remaining,
    );
    if (projectile.kind !== "ranged" || !(projectile.impactSplashRadius > 0)) continue;
    const actor = byReference.get(projectile.actorId)
      ?? { mechanics: projectile.actorMechanics };
    for (const victim of units) {
      if (!victim.alive || victim.referenceId === target.referenceId
          || victim.referenceId === projectile.actorId) continue;
      const hostile = isHostile({
        referenceId: projectile.actorId,
        owner: projectile.actorOwner,
        relationByOwner: projectile.actorRelationByOwner,
      }, victim);
      const friendlyFraction = projectile.impactSplashFriendlyFireFraction ?? 0;
      if (!hostile && friendlyFraction <= 0) continue;
      const reach = Math.hypot(victim.x - target.x, victim.y - target.y)
        - collisionRadius(victim);
      if (reach > projectile.impactSplashRadius + 1e-12) continue;
      const full = calculateDamage(actor, victim, {
        attackClasses: projectile.attackClasses ?? undefined,
      });
      const fraction = (projectile.impactSplashDamageFraction ?? 1)
        * (hostile ? 1 : friendlyFraction);
      applyCommittedDamage(units, projectile.actorId, victim,
        Math.max(1, full * fraction), tick, tick, events, {
          kind: "impact-splash",
          projectileIndex: projectile.index,
        });
    }
  }
  return remaining;
}


function processImpactHazards(units, hazards, tick, events) {
  if (!hazards) return null;
  const active = hazards.filter((hazard) => tick < hazard.endTick);
  for (const victim of units) {
    if (!victim.alive) continue;
    const touching = active.filter((hazard) => {
      const actor = {
        referenceId: hazard.actorId,
        owner: hazard.actorOwner,
        relationByOwner: hazard.actorRelationByOwner,
      };
      return isHostile(actor, victim)
        && Math.hypot(victim.x - hazard.x, victim.y - hazard.y)
          - collisionRadius(victim) <= hazard.radiusTiles + 1e-12;
    });
    if (touching.length === 0) continue;
    const selected = touching.some(({ stacks }) => stacks)
      ? touching
      : [touching.toSorted((left, right) => (
        right.damagePerSecond - left.damagePerSecond
          || left.actorId - right.actorId
      ))[0]];
    const damage = selected.reduce((total, hazard) => (
      total + hazard.damagePerSecond / TICKS_PER_SECOND
    ), 0);
    applyCommittedDamage(units, selected[0].actorId, victim, damage,
      tick, tick, events, { kind: "impact-hazard" });
  }
  return active;
}


function applyCommittedDamage(units, actorId, target, amount, readyTick, tick, events, extra) {
  const actor = units.find((unit) => unit.referenceId === actorId);
  const hpBefore = target.hp;
  const hpAfter = Math.max(0, hpBefore - amount);
  target.hp = hpAfter;
  events.push(createDamageEvent({
    tick,
    actorId,
    targetId: target.referenceId,
    readyTick,
    amount,
    hpBefore,
    hpAfter,
    ...(extra ?? {}),
  }));
  if (extra?.triggersOnHit && actor?.specialState) {
    const effects = unitEffects(actor);
    actor.specialState.lastAttackTick = tick;
    if ((effects.attack_speed_ramp ?? 0) > 0) {
      const cutoff = tick - 5 * TICKS_PER_SECOND;
      actor.specialState.rampHitTicks = actor.specialState.rampHitTicks
        .filter((hitTick) => hitTick > cutoff);
      actor.specialState.rampHitTicks.push(tick);
      actor.actionTimers.reload = Math.max(
        0,
        reloadTicksForUnit(actor, tick) - actor.actionTimers.swing,
      );
    }
    const strip = effects.armor_strip_per_hit ?? 0;
    if (strip > 0 && hpAfter > 0) {
      ensureSpecialState(target).armorStripped += strip;
    }
    const bleedDps = effects.bleed_dps ?? 0;
    if (bleedDps > 0 && hpAfter > 0) {
      const targetState = ensureSpecialState(target);
      const durationTicks = secondsToTicksCeil(effects.bleed_duration ?? 0);
      if (durationTicks > 0) {
        targetState.bleedStacks ??= [];
        targetState.bleedStacks.push({
          actorId,
          damagePerSecond: bleedDps,
          untilTick: tick + durationTicks,
        });
      }
    }
    const slowPercent = extra?.charge
      ? (effects.charge_slow_percent ?? 0)
      : (effects.on_hit_slow_percent ?? 0);
    const slowDuration = extra?.charge
      ? (effects.charge_slow_duration ?? 0)
      : (effects.on_hit_slow_duration_seconds ?? 0);
    const excludesSiege = effects.on_hit_slow_excludes_siege === true;
    const targetIsSiege = target.mechanics.armor_classes?.["20"] !== undefined;
    if (slowPercent > 0 && slowDuration > 0
        && !(excludesSiege && targetIsSiege)) {
      const targetState = ensureSpecialState(target);
      targetState.slowMultiplier = 1 - slowPercent;
      targetState.slowUntilTick = Math.max(
        targetState.slowUntilTick,
        tick + secondsToTicksCeil(slowDuration),
      );
    }
  }
  if (hpAfter > 0) return;

  // Capture a durable command at the death boundary itself. Most deaths are
  // followed by applyPendingDismounts later in this tick, but damage-over-time
  // can kill during the start-of-tick special-effects pass, before dead-unit
  // validation clears transient state. Taking the command here makes every
  // damage source obey the same replacement-order inheritance rule.
  if (target.mechanics?.dismount_form
      && target.specialState?.dismounted !== true
      && target.moveOrder !== undefined && target.moveOrder !== null) {
    ensureSpecialState(target).dismountInheritedMoveOrder = target.moveOrder;
  }

  if (actor?.alive && actor.specialState) {
    const effects = unitEffects(actor);
    const attackCap = effects.attack_bonus_per_kill ?? 0;
    if (attackCap > 0) {
      actor.specialState.killAttackBonus = Math.min(
        attackCap,
        actor.specialState.killAttackBonus + 1,
      );
    }
    const healPerKill = effects.hp_per_kill ?? 0;
    const healCap = effects.hp_per_kill_max ?? 0;
    if (healPerKill > 0 && actor.specialState.hpGainedFromKills < healCap) {
      const heal = Math.min(
        healPerKill,
        healCap - actor.specialState.hpGainedFromKills,
      );
      actor.hp = Math.min(actor.maxHp ?? actor.mechanics.hp, actor.hp + heal);
      actor.specialState.hpGainedFromKills += heal;
    }
  }

  target.alive = false;
  target.pursuitTargetId = null;
  target.engagedTargetId = null;
  target.attackTargetId = null;
  delete target.pendingVolley;
  target.avoidance = null;
  target.action = "dead";
  target.actionTimers = { windup: 0, reload: 0, swing: 0, acquire: 0 };
  events.push(createDeathEvent({
    tick,
    actorId,
    targetId: target.referenceId,
    readyTick,
  }));
  const deathEffects = unitEffects(target);
  const deathExplosionAttack = deathEffects.death_explosion_melee_attack ?? 0;
  const deathExplosionRadius = deathEffects.death_explosion_radius_tiles ?? 0;
  if (deathExplosionAttack > 0 && deathExplosionRadius > 0) {
    const deathActor = {
      referenceId: target.referenceId,
      owner: target.owner,
      relationByOwner: target.relationByOwner,
      mechanics: target.mechanics,
    };
    for (const victim of units) {
      if (!victim.alive || !isHostile(deathActor, victim)) continue;
      const reach = Math.hypot(victim.x - target.x, victim.y - target.y)
        - collisionRadius(victim);
      if (reach > deathExplosionRadius + 1e-12) continue;
      const explosionDamage = calculateDamage(deathActor, victim, {
        attackClasses: { 4: deathExplosionAttack },
      });
      applyCommittedDamage(
        units,
        target.referenceId,
        victim,
        explosionDamage,
        tick,
        tick,
        events,
        { kind: "death-explosion" },
      );
    }
  }
  for (const ally of units) {
    if (!ally.alive || ally.owner !== target.owner || !ally.specialState) continue;
    const effects = unitEffects(ally);
    const heal = effects.ally_death_heal ?? 0;
    if (heal <= 0 || Math.hypot(ally.x - target.x, ally.y - target.y) > 5 + 1e-12) {
      continue;
    }
    const duration = effects.ally_death_heal_duration ?? 0;
    ally.specialState.allyHealRemaining = heal;
    ally.specialState.allyHealPerTick = duration > 0
      ? heal / secondsToTicksCeil(duration)
      : heal;
  }
  for (const engaged of units) {
    if (!engaged.alive || engaged.engagedTargetId !== target.referenceId) continue;
    engaged.engagedTargetId = null;
    events.push(event(
      tick,
      "engagement-ended",
      engaged.referenceId,
      target.referenceId,
      { reason: "target-dead" },
    ));
  }
}


export function stepWorld(world) {
  if (!world || typeof world !== "object") throw new TypeError("world is required");
  const tick = world.tick + 1;
  const events = [];

  const snapshot = Object.freeze([...world.units]);
  const units = snapshot.map(mutableUnit);
  advanceSpecialEffects(units, tick, events);
  const pursuitRecoveryState = nextPursuitRecoveryState(
    world.pursuitRecoveryState ?? null,
  );
  const patrolOpeningTargetByOwner = world.patrolOpeningTargetByOwner
    ? new Map(world.patrolOpeningTargetByOwner)
    : null;
  const acquisitionPairInteractions = createPairInteractionSnapshot({
    contactReservations: world.contactReservationState?.reservations ?? new Map(),
  });
  validatePursuitTargets(units, tick, events);
  validateAttackTargets(
    units,
    tick,
    events,
    world.rangedWindupRetargetOwner ?? null,
  );
  acquirePursuitTargets(
    units,
    tick,
    events,
    world.kiteState ?? null,
    world.rangedTargetPressureOwner ?? null,
    patrolOpeningTargetByOwner,
    pursuitRecoveryState,
    world.map,
    acquisitionPairInteractions,
  );
  issueKiteOrders(world.kiteState, units, world.map, tick, events, event);
  // Melee chase tapes carry a single opening wave and then rely on unit AI,
  // so their ordinary player-order layer stays down. Ranged opponents retain
  // their ordinary AI orders while the commanded owner is excluded from that
  // layer and driven by the shoot-and-move controller.
  if (!world.kiteState || world.kiteState.opponentMode === "ordinary-ranged") {
    issueOrders(
      world.orderState,
      units,
      tick,
      events,
      event,
      world.kiteState?.owner ?? null,
    );
  }
  const {
    contacts,
    movedIds,
    blockedIds,
    velocities,
    contactUpdate,
    pairInteractions,
  } = moveUnits(
    units,
    world.map,
    tick,
    events,
    world.kiteState ?? null,
    world.contactReservationState ?? null,
    world.contactSteeringStates ?? new Map(),
    pursuitRecoveryState,
  );
  updateEngagements(
    units,
    contacts,
    tick,
    events,
    blockedIds,
    world.kiteState ?? null,
    pairInteractions,
  );
  // Clone flight state: published projectiles are frozen, ranged shots
  // advance their position every tick, and a bolt's hit list must not alias
  // the previous tick's published array.
  const projectiles = world.projectiles
    ? world.projectiles.map((projectile) => ({
      ...projectile,
      ...(projectile.hitIds ? { hitIds: [...projectile.hitIds] } : {}),
    }))
    : null;
  const hazards = world.hazards
    ? world.hazards.map((hazard) => ({ ...hazard }))
    : null;
  const ready = progressAttacks(units, tick, events, movedIds,
    projectiles, velocities, world.shotRng ?? null);
  commitReadyAttacks(units, ready, tick, events);
  const remainingProjectiles = projectiles
    ? processChargeProjectiles(units, projectiles, tick, events, hazards)
    : null;
  const remainingHazards = hazards
    ? processImpactHazards(units, hazards, tick, events)
    : null;
  applyPendingDismounts(units, tick, events);
  const scenarioUpdate = advanceScenarioTriggers(world, units, tick, events);
  for (const owner of scenarioUpdate.patrolOwners) {
    patrolOpeningTargetByOwner?.delete(owner);
  }

  const publishedUnits = canonicalUnits(units);
  const publishedEvents = Object.freeze(events);
  const eventLog = Object.freeze([...world.eventLog, ...publishedEvents]);
  const snapshots = Object.freeze([
    ...world.snapshots,
    createSnapshot(tick, publishedUnits, publishedEvents,
      soloNavigationSnapshot(world.kiteState?.soloNavigationState)),
  ]);
  return Object.freeze({
    ...world,
    pursuitRecoveryState,
    ...(contactUpdate ? {
      contactReservationState: contactUpdate.state,
      contactReservationDiagnostics: contactUpdate.diagnostics,
    } : {}),
    ...(remainingProjectiles !== null
      ? { projectiles: Object.freeze(remainingProjectiles.map((p) => Object.freeze({ ...p }))) }
      : {}),
    ...(remainingHazards !== null
      ? { hazards: Object.freeze(remainingHazards.map((hazard) => (
        Object.freeze({ ...hazard })
      ))) }
      : {}),
    ...(scenarioUpdate.triggerState
      ? { scenarioTriggerState: scenarioUpdate.triggerState }
      : {}),
    ...(patrolOpeningTargetByOwner
      ? { patrolOpeningTargetByOwner }
      : {}),
    diplomacyByOwner: scenarioUpdate.diplomacyByOwner,
    tick,
    units: publishedUnits,
    events: publishedEvents,
    eventLog,
    snapshots,
  });
}


function outcome(world) {
  const liveOwners = new Set(
    world.units.filter(({ alive }) => alive).map(({ owner }) => owner),
  );
  if (liveOwners.size === 0) {
    throw new Error(`invalid terminal world at tick ${world.tick}: no live owners`);
  }
  const liveTeams = world.victoryTeams.filter((team) => (
    team.owners.some((owner) => liveOwners.has(owner))
  ));
  if (liveTeams.length > 1) return null;
  if (liveTeams.length === 0) {
    throw new Error(`invalid terminal world at tick ${world.tick}: no live victory team`);
  }
  const winner = liveTeams[0].winnerOwner;
  return Object.freeze({
    outcome: "win",
    winner,
    ticks: world.tick,
    world,
    snapshots: world.snapshots,
    events: world.eventLog,
  });
}


export function runWorld(
  world,
  { maxTicks = DEFAULT_WORLD_TICKS, retainSnapshots = true, onSnapshot } = {},
) {
  if (!Number.isSafeInteger(maxTicks) || maxTicks < 0) {
    throw new RangeError("max ticks must be a nonnegative safe integer");
  }
  if (maxTicks > MAX_WORLD_TICKS) {
    throw new RangeError(`max ticks must not exceed ${MAX_WORLD_TICKS}`);
  }
  if (typeof retainSnapshots !== "boolean") {
    throw new TypeError("retainSnapshots must be a boolean");
  }
  if (onSnapshot !== undefined && typeof onSnapshot !== "function") {
    throw new TypeError("onSnapshot must be a function");
  }

  const publish = (current) => {
    if (!onSnapshot) return;
    const snapshot = current.snapshots.at(-1);
    if (snapshot) onSnapshot(snapshot);
  };

  if (retainSnapshots) {
    let current = world;
    publish(current);
    const initialOutcome = outcome(current);
    if (initialOutcome !== null) return initialOutcome;
    for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
      current = stepWorld(current);
      publish(current);
      const result = outcome(current);
      if (result !== null) return result;
    }
    const error = new Error(`world exceeded ${maxTicks} ticks`);
    error.world = current;
    throw error;
  }

  const collectedEvents = [...world.eventLog];
  const emptySnapshots = Object.freeze([]);
  const emptyEventLog = Object.freeze([]);
  const compactWorld = (current, eventLog = emptyEventLog) => Object.freeze({
    ...current,
    eventLog,
    snapshots: emptySnapshots,
  });
  const compactResult = (result, current) => {
    const eventLog = Object.freeze([...collectedEvents]);
    const publishedWorld = compactWorld(current, eventLog);
    return Object.freeze({
      ...result,
      world: publishedWorld,
      snapshots: emptySnapshots,
      events: eventLog,
    });
  };

  let current = world;
  publish(current);
  const initialOutcome = outcome(current);
  if (initialOutcome !== null) return compactResult(initialOutcome, current);
  current = compactWorld(current);
  for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
    current = stepWorld(current);
    publish(current);
    collectedEvents.push(...current.events);
    const result = outcome(current);
    if (result !== null) return compactResult(result, current);
    current = compactWorld(current);
  }
  const error = new Error(`world exceeded ${maxTicks} ticks`);
  error.events = Object.freeze([...collectedEvents]);
  error.world = compactWorld(current, error.events);
  throw error;
}
