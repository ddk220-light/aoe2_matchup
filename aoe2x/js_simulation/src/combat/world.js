import {
  queryEnemyContactManifold,
  resolveMovementProposals,
} from "./collision.js";
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
import { planChaseAim, planMoveAim } from "./chase-path.js";
import { planCohortContactMotion } from "./cohort-motion.js";
import { planLocalAvoidance } from "./local-avoidance.js";
import {
  planPreventiveContactSteering,
  PREVENTIVE_CONTACT_STEERING_STRENGTH,
} from "./contact-graph-steering.js";
import {
  alliedTransitPairKey,
  updateAlliedTransit,
} from "./allied-transit.js";
import { updateExclusiveAlliedOverlap } from "./allied-overlap.js";
import { proposeMovement } from "./movement.js";
import {
  createSoloNavigationState,
  finishSoloNavigationTick,
  planSoloNavigation,
  soloNavigationSnapshot,
} from "./solo-navigation.js";
import {
  chebyshevGap,
  isWithinReach,
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
  orderReadyAttacks,
  rangedSpec,
  reloadTicks,
  trampleSpec,
} from "./attacks.js";
import { allyCollisionRadius, collisionRadius } from "./targeting.js";


const DEFAULT_MAP = Object.freeze({
  width: 16,
  height: 16,
  obstacles: Object.freeze([]),
});
// Default runaway guard for a single fight, and the hard ceiling a caller may
// raise it to. 60 s covers every recorded melee fight with margin, but the
// ranged tapes' own 20v15 fights run 56.5-59.8 s and the sim legitimately
// needs more clock for max-range attrition endgames — callers pass maxTicks
// up to the ceiling for those.
const DEFAULT_WORLD_TICKS = 3600;
const MAX_WORLD_TICKS = 9000;


function freezeUnit(unit) {
  return Object.freeze({
    ...unit,
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
    avoidance: unit.avoidance === null ? null : { ...unit.avoidance },
    actionTimers: { ...unit.actionTimers },
  };
}


function freezeMap(map) {
  return immutableClone({ ...map, obstacles: [...(map.obstacles ?? [])] });
}


function createSnapshot(tick, units, events, navigation = null) {
  return Object.freeze({ tick, units, events, ...(navigation ? { navigation } : {}) });
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
    if (!target?.alive || target.owner === unit.owner) {
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
  const units = canonicalUnits(scenario.units, { cloneMechanics: true });
  validateInitialAttackState(units);
  const map = scenario.map ? freezeMap(scenario.map) : DEFAULT_MAP;
  const events = Object.freeze([]);
  const kiteState = Number.isSafeInteger(scenario.kiteOwner)
    ? createKiteState(
      scenario.kiteOwner,
      scenario.kiteProfile ?? null,
      scenario.chaseCapture === true,
      scenario.kitedEscape === true,
      scenario.soloMovement === true,
    )
    : null;
  const crowdState = Number.isSafeInteger(scenario.meleeCrowdOwner)
    ? {
      owner: scenario.meleeCrowdOwner,
      preventiveContactSteering: false,
      preventiveContactSteeringStrength: 0,
      preventiveContactSteeredSteps: 0,
      preventiveContactSteeredUnits: new Set(),
      alliedOverlap: { reservations: new Map() },
    }
    : null;
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
    );
  }
  if (kiteState && scenario.kiteMeleeOpeningOrder === "attack-move-all") {
    kiteState.meleeOpeningOrder = "attack-move-all";
    kiteState.meleeApproach = new Map();
  }
  if (scenario.preventiveContactSteering === true) {
    if (!crowdState) {
      throw new RangeError("preventive contact steering requires a melee crowd owner");
    }
    const strength = scenario.preventiveContactSteeringStrength
      ?? PREVENTIVE_CONTACT_STEERING_STRENGTH;
    if (!Number.isFinite(strength) || strength < 0 || strength > 1) {
      throw new RangeError("preventive contact steering strength must be between 0 and 1");
    }
    crowdState.preventiveContactSteering = true;
    crowdState.preventiveContactSteeringStrength = strength;
  }
  if (scenario.pairwiseAlliedTransit === true
      && scenario.reachMeleeWedgeTransit === true) {
    throw new RangeError("allied transit modes are mutually exclusive");
  }
  const alliedTransitMode = scenario.reachMeleeWedgeTransit === true
    ? "reach-wedge"
    : (scenario.pairwiseAlliedTransit === true ? "ordinary" : null);
  if (alliedTransitMode !== null) {
    if (!kiteState || scenario.kiteMeleeOpeningOrder !== "attack-move-all") {
      throw new RangeError(alliedTransitMode === "reach-wedge"
        ? "reach-melee wedge transit requires a kiting attack-move scenario"
        : "pairwise allied transit requires a kiting attack-move scenario");
    }
    kiteState.alliedTransit = {
      mode: alliedTransitMode,
      cohort: new Set(),
      reservations: new Map(),
      pairKeys: new Set(),
    };
  }
  const snapshot = createSnapshot(0, units, events,
    soloNavigationSnapshot(kiteState?.soloNavigationState));
  // Charge-projectile flight queue, present only when the roster can fire one
  // (Fire Lancer family) so worlds without charge units keep their exact
  // published shape.
  const anyCharge = units.some((unit) => (
    chargeSpec(unit.mechanics) !== null || rangedSpec(unit.mechanics) !== null
  ));
  return Object.freeze({
    // Experiment-only mutable AI-player state; absent in baseline so world
    // shape and hashes are unchanged (the object is frozen but Maps inside
    // stay mutable across ticks by design).
    ...(ORDERS_ENABLED ? { orderState: createOrderState(units) } : {}),
    // Kiting-side beat controller (see issueKiteOrders): present only when
    // the scenario names a kiting owner, so every other world keeps its
    // exact published shape.
    ...(kiteState ? { kiteState } : {}),
    ...(crowdState ? { crowdState } : {}),
    ...(anyCharge ? { projectiles: Object.freeze([]) } : {}),
    // Deterministic per-shot RNG, present only when a unit can miss or blast
    // (dat accuracy < 100 or blast width > 0 — nothing in the converged
    // corpus). Seeded with the golden constant; state lives OUTSIDE units so
    // no hash can move. Mutable by design across ticks, like kiteState.
    ...(units.some((unit) => {
      const spec = rangedSpec(unit.mechanics);
      return spec && (spec.accuracyPercent < 100
        || spec.blastRadius > 0 || spec.secondaryCount > 0);
    }) ? { shotRng: { state: 20260411 >>> 0 } } : {}),
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
      delete unit.moveOrder;
      unit.actionTimers = { windup: 0, reload: 0, swing: 0, acquire: 0 };
      continue;
    }
    if (unit.pursuitTargetId === null || unit.pursuitTargetId === undefined) continue;
    const target = byReference.get(unit.pursuitTargetId);
    if (target?.alive) {
      if (target.owner === unit.owner) {
        throw new Error(
          `unit ${unit.referenceId} has friendly pursuit target ${target.referenceId}`,
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
  }
}


function validateAttackTargets(units, tick, events) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  for (const unit of units) {
    if (!unit.alive || unit.action !== "attacking") continue;
    const target = byReference.get(unit.attackTargetId);
    if (target?.alive && target.owner !== unit.owner) continue;
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
      : attackDelayTicks(unit.mechanics);
    if (unit.actionTimers.swing >= releaseTicks) continue;
    events.push(createAttackCanceledEvent({
      tick,
      actorId: unit.referenceId,
      targetId: invalidTargetId,
      readyTick: tick + Math.max(0, releaseTicks - unit.actionTimers.swing),
      reason: !target?.alive ? "target-dead" : "target-invalidated",
    }));
    unit.attackTargetId = null;
    delete unit.attackKind;
    unit.actionTimers.windup = 0;
    unit.actionTimers.swing = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
  }
}


function acquirePursuitTargets(units, tick, events, kiteState = null) {
  const snapshot = Object.freeze(units.map(freezeUnit));
  for (const unit of units) {
    if (!unit.alive) continue;
    // Initial target-acquisition delay. Only the first acquisition waits; once a
    // unit has been in combat, re-acquisition is governed by its swing state.
    if (unit.actionTimers.acquire > 0) {
      unit.actionTimers.acquire -= 1;
      // Acquire on the very tick the delay expires, so no unit is ever briefly
      // idle with an expired timer and no target.
      if (unit.actionTimers.acquire > 0) continue;
    }
    // Experiment harness (docs/RETARGETING_INVESTIGATION.md). Off by default:
    // shouldReevaluatePursuit is false unless AOE2X_EXP_PURSUIT is set, so this
    // reduces to the original `if (pursuitTargetId !== null) continue`.
    const blockedAttackMover = kiteState?.meleeOpeningOrder === "attack-move-all"
      && unit.owner !== kiteState.owner
      && unit.experimentBlocked === true;
    const reevaluate = unit.pursuitTargetId !== null
      && (shouldReevaluatePursuit(unit) || blockedAttackMover);
    if (unit.pursuitTargetId !== null && !reevaluate) continue;
    const found = snapshot.find(({ referenceId }) => referenceId === unit.referenceId);
    // selectPursuitTarget short-circuits on a live locked target, so a
    // re-evaluation has to present the unit as unlocked to force a fresh scan.
    const candidate = reevaluate ? { ...found, pursuitTargetId: null } : found;
    const target = selectPursuitTarget(candidate, snapshot);
    if (target === null) continue;
    if (target.referenceId === unit.pursuitTargetId) continue;
    events.push(event(tick, "pursuit-acquired", unit.referenceId, target.referenceId));
    unit.pursuitTargetId = target.referenceId;
  }
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
  return distance <= unit.mechanics.line_of_sight_tiles;
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
  for (const other of live) {
    if (other.owner === unit.owner) continue;
    const distance = Math.hypot(other.x - unit.x, other.y - unit.y);
    if (distance < spec.min_range_tiles - 1e-9 && distance < nearestDistance) {
      nearest = other;
      nearestDistance = distance;
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


function stepClearsBodies(mover, dx, dy, live, proposalByReference, bounds,
  alliedTransitPairs) {
  const x = mover.x + dx;
  const y = mover.y + dy;
  const radius = collisionRadius(mover);
  if (x < radius - STEP_EPSILON || x > bounds.width - radius + STEP_EPSILON
    || y < radius - STEP_EPSILON || y > bounds.height - radius + STEP_EPSILON) return false;
  const moverProposal = proposalByReference.get(mover.referenceId);
  const moverMoving = moverProposal !== undefined
    && (moverProposal.dx !== 0 || moverProposal.dy !== 0);
  for (const other of live) {
    if (other.referenceId === mover.referenceId) continue;
    const allied = other.owner === mover.owner;
    if (allied && alliedTransitPairs.has(alliedTransitPairKey(
      mover.referenceId, other.referenceId,
    ))) continue;
    // Same three rules the constraint solver applies (see collision.js):
    // formation-mates ignore each other, a moving unit shrinks against a
    // friendly, enemies always hold the full box.
    if (allied && mover.moveOrder && other.moveOrder) continue;
    const otherProposal = proposalByReference.get(other.referenceId);
    const otherMoving = otherProposal !== undefined
      && (otherProposal.dx !== 0 || otherProposal.dy !== 0);
    const extent = allied
      ? (moverMoving ? allyCollisionRadius(mover) : radius)
        + (otherMoving ? allyCollisionRadius(other) : collisionRadius(other))
      : radius + collisionRadius(other);
    if (Math.max(Math.abs(x - other.x), Math.abs(y - other.y)) < extent - STEP_EPSILON) {
      return false;
    }
  }
  return true;
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
function stepHitsAnyEnemyBody(mover, dx, dy, live) {
  const x = mover.x + dx;
  const y = mover.y + dy;
  const radius = collisionRadius(mover);
  for (const other of live) {
    if (other.referenceId === mover.referenceId) continue;
    if (other.owner === mover.owner) continue;
    const extent = radius + collisionRadius(other);
    if (Math.max(Math.abs(x - other.x), Math.abs(y - other.y)) < extent - STEP_EPSILON) {
      return true;
    }
  }
  return false;
}


function stepHitsOtherEnemyBody(mover, dx, dy, live) {
  const x = mover.x + dx;
  const y = mover.y + dy;
  const radius = collisionRadius(mover);
  for (const other of live) {
    if (other.referenceId === mover.referenceId) continue;
    if (other.owner === mover.owner) continue;
    if (other.referenceId === mover.pursuitTargetId
      || other.referenceId === mover.engagedTargetId
      || other.referenceId === mover.attackTargetId) continue;
    const extent = radius + collisionRadius(other);
    if (Math.max(Math.abs(x - other.x), Math.abs(y - other.y)) < extent - STEP_EPSILON) {
      return true;
    }
  }
  return false;
}




function steerProposals(planned, map, chaserScopeOwner = null, kitedEscape = false,
  alliedTransitPairs = new Set()) {
  const hasMinimumRangeRetreat = planned.proposals.some(({ movementIntent }) => (
    movementIntent === "minimum-range-retreat"
  ));
  if (!STEER_AROUND_BODIES && chaserScopeOwner === null && !hasMinimumRangeRetreat) {
    return { proposals: planned.proposals, steered: null };
  }
  const escapeActive = KITED_SIDE_STEER || kitedEscape;
  const bounds = { width: map.width, height: map.height };
  const byReference = new Map(planned.units.map((unit) => [unit.referenceId, unit]));
  const proposalByReference = new Map(
    planned.proposals.map((proposal) => [proposal.referenceId, proposal]),
  );
  const steered = new Set();
  const proposals = planned.proposals.map((proposal) => {
    const distance = Math.hypot(proposal.dx, proposal.dy);
    if (distance <= ZERO_STEP_EPSILON) return proposal;
    const mover = byReference.get(proposal.referenceId);
    if (!mover) return proposal;
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
        if (!stepHitsAnyEnemyBody(mover, proposal.dx, proposal.dy, planned.units)) {
          return proposal;
        }
      } else {
        // Steer only when the wanted step runs into a NON-TARGET enemy body
        // (the ball surface). Ally blocks keep the baseline solver (the
        // tape's chaser-on-chaser stalls are real), and the mover's own
        // target is the catch. Wider triggers were measured and rejected --
        // see the ally-queue ladder in HCC_CHASER_MOBILITY_2026-08-07.md.
        if (!stepHitsOtherEnemyBody(mover, proposal.dx, proposal.dy, planned.units)) {
          return proposal;
        }
      }
    }
    if (stepClearsBodies(mover, proposal.dx, proposal.dy, planned.units,
      proposalByReference, bounds, alliedTransitPairs)) return proposal;
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
        if (stepClearsBodies(mover, dx, dy, planned.units, proposalByReference, bounds,
          alliedTransitPairs)) {
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
    movementOptions.alliedTransitPairs,
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


function moveUnits(units, map, tick, events, kiteState = null, crowdState = null) {
  const live = units.filter(({ alive }) => alive).map(freezeUnit);
  const byReference = new Map(live.map((unit) => [unit.referenceId, unit]));
  const soloDestinations = kiteState?.soloNavigationState
    ? planSoloNavigation(
      kiteState.soloNavigationState,
      live.filter((unit) => unit.owner === kiteState.owner),
      map,
      tick,
    )
    : null;
  if (kiteState && !kiteState.chaseWaypoints) kiteState.chaseWaypoints = new Map();
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
    if (!kiteState || unit.owner === kiteState.owner) return target;
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
        const obstacles = live.filter((other) => other.referenceId !== unit.referenceId
          && other.referenceId !== target.referenceId
          && other.referenceId !== unit.pursuitTargetId
          && other.referenceId !== unit.engagedTargetId
          && other.referenceId !== unit.attackTargetId);
        waypoint.plan = planChaseAim(unit, target, obstacles, map);
      }
      const plan = waypoint.plan;
      if (plan !== null) {
        if (plan.stand === true) return { ...target, x: unit.x, y: unit.y };
        return { ...target, x: plan.x, y: plan.y };
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
      const obstacles = live.filter((other) => other.owner !== unit.owner);
      waypoint = {
        orderX: goal.x,
        orderY: goal.y,
        plan: planMoveAim(unit, goal, obstacles, map),
      };
      waypoints.set(unit.referenceId, waypoint);
    }
    if (waypoint.plan === null) return goal;
    if (waypoint.plan.stand === true) return { x: unit.x, y: unit.y };
    return waypoint.plan;
  };
  let proposals = live.map((unit) => {
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
    if (unit.moveOrder
        && (unit.action !== "attacking" || unit.actionTimers.windup === 0)) {
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
        && engaged?.alive && engaged.owner !== unit.owner
        && isWithinReach(unit, engaged)) {
      return Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
    }
    const target = byReference.get(unit.pursuitTargetId);
    return target && unit.action !== "attacking" && !isWithinStopRange(unit, target)
      && !holdsForChargeVolley(unit, target)
      ? proposeMovement(unit, chaseAim(unit, target), TICKS_PER_SECOND)
      : Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
  });
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
        enemies: live.filter((unit) => unit.owner !== kiteState.owner),
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
  let alliedTransitPairs = new Set();
  if (kiteState?.alliedTransit) {
    const updatedTransit = updateAlliedTransit(kiteState.alliedTransit, live, proposals);
    kiteState.alliedTransit.reservations = updatedTransit.reservations;
    kiteState.alliedTransit.pairKeys = updatedTransit.pairKeys;
    alliedTransitPairs = updatedTransit.pairKeys;
  }
  let movementOptions = {
    alliedTransitPairs,
    ...(kiteState ? { collisionRecoveryState: kiteState.collisionRecoveryState } : {}),
  };
  let planned = planLocalAvoidance(live, proposals, map, movementOptions);
  if (crowdState?.preventiveContactSteering === true) {
    let contactProposals = planned.proposals;
    const contactPlan = planPreventiveContactSteering(
      planned.units,
      contactProposals,
      map,
      { owner: crowdState.owner, strength: crowdState.preventiveContactSteeringStrength },
    );
    contactProposals = contactPlan.proposals;
    crowdState.preventiveContactSteeredSteps += contactPlan.steered.length;
    for (const { referenceId } of contactPlan.steered) {
      crowdState.preventiveContactSteeredUnits.add(referenceId);
    }
    planned = Object.freeze({ ...planned, proposals: contactProposals });
  }
  if (crowdState) {
    const overlap = updateExclusiveAlliedOverlap(
      crowdState.alliedOverlap,
      planned.units,
      planned.proposals,
      crowdState.owner,
    );
    crowdState.alliedOverlap = { reservations: overlap.reservations };
    movementOptions = {
      ...movementOptions,
      exclusiveAlliedShrinkOwners: new Set([crowdState.owner]),
      alliedShrinkPairs: overlap.pairKeys,
      alliedShallowPairs: overlap.shallowPairKeys,
      alliedShrinkReservedIds: overlap.reservedIds,
    };
  }
  const moved = resolveMovement(planned, byReference, map, kiteState, movementOptions);
  const movedByReference = new Map(moved.map((unit) => [unit.referenceId, unit]));
  const proposalByReference = new Map(proposals.map((proposal) => [proposal.referenceId, proposal]));
  const moveEvents = [];
  const blockedEvents = [];
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
          if (other.owner === unit.owner || other.referenceId === unit.referenceId) continue;
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
  }
  events.push(...moveEvents, ...blockedEvents);
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


function updateEngagements(units, contacts, tick, events, blockedIds, kiteState = null) {
  const kiteOwner = kiteState ? kiteState.owner : null;
  if (kiteState && !kiteState.reachDwell) kiteState.reachDwell = new Map();
  const snapshot = Object.freeze(units.map(freezeUnit));
  for (const unit of units) {
    if (!unit.alive) {
      unit.engagedTargetId = null;
      continue;
    }
    // No engagement before first acquisition: the outline reach can span the
    // spawn bands (steppe-vs-elephant 1v1 spawns sit at exactly outline gap
    // 1.1), yet the tapes show no unit swinging before its acquisition delay
    // has run. Collision-based reach never spanned a spawn gap, so this gate
    // changes nothing for the recorded range-0 fixtures.
    if (unit.actionTimers.acquire > 0) {
      unit.engagedTargetId = null;
      continue;
    }
    // A kite move order suppresses engagement until the next attack beat
    // re-designates (the tape wraps each move in a no-attack stance toggle).
    if (unit.moveOrder) {
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
    if (kiteOwner !== null && unit.owner !== kiteOwner) {
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
          if (!candidate.alive || candidate.owner === unit.owner) continue;
          if (candidate.referenceId === unit.pursuitTargetId) continue;
          if (chebyshevGap(unit, candidate) > CONTACT_CAPTURE_EPSILON) continue;
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
      const gap = pursued && pursued.alive && pursued.owner !== unit.owner
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
    // Attack-action persistence (measured, three archives): a unit shoved out
    // of reach that TRIES to close and is fully blocked keeps its attack
    // cycle on its live target — a pve 5v3 paladin swings from collision gap
    // 0.523-0.575 for 25 straight seconds after the scrum separates the pair,
    // and steppe lancers land tail hits lagging their reach by exactly one
    // reload. A unit that CAN move chases instead (engagement drops below),
    // which is what keeps fleeing-target pursuit intact. Line of sight is the
    // outer sanity bound (dat-sourced); no swing was ever observed beyond
    // outline gap +0.24, all from deep scrums.
    if (
      previousTargetId !== null && previousTargetId !== undefined
      && blockedIds.has(unit.referenceId)
    ) {
      const engaged = snapshot.find(({ referenceId }) => referenceId === previousTargetId);
      if (engaged && engaged.alive && engaged.owner !== unit.owner) {
        const distance = Math.hypot(engaged.x - unit.x, engaged.y - unit.y);
        if (distance <= unit.mechanics.line_of_sight_tiles) continue;
      }
    }
    const self = snapshot.find(({ referenceId }) => referenceId === unit.referenceId);
    const selection = selectEngagementTarget(self, snapshot, contacts);
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
    const pursued = ENGAGEMENT_FOLLOWS_PURSUIT
      && unit.pursuitTargetId !== null && unit.pursuitTargetId !== undefined
      ? snapshot.find(({ referenceId }) => referenceId === unit.pursuitTargetId)
      : null;
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
    const pursuedClosed = pursued && pursued.alive && isWithinStopRange(self, pursued);
    const nextTargetId = pursuedClosed && isWithinReach(self, pursued)
      ? pursued.referenceId
      : (pursuedClosed && unit.mechanics?.ranged
        ? null
        : selection.target?.referenceId ?? null);
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
function releaseChargeVolley(unit, target, spec, tick, events, projectiles) {
  // The volley leaves the unit whether or not anything is left to aim at; an
  // unreleased cycle abandoned earlier (validateAttackTargets) keeps its
  // charge instead.
  unit.charge = 0;
  if (!target?.alive || target.owner === unit.owner) return;
  const distance = Math.hypot(target.x - unit.x, target.y - unit.y);
  const flight = Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed));
  const amount = chargeProjectileDamage(spec, target);
  for (let index = 0; index < spec.projectileCount; index += 1) {
    projectiles.push({
      actorId: unit.referenceId,
      targetId: target.referenceId,
      firedTick: tick,
      arrivalTick: tick + flight,
      index,
      amount,
    });
  }
  events.push(event(tick, "charge-volley", unit.referenceId, target.referenceId, {
    projectiles: spec.projectileCount,
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


function releaseRangedShot(unit, target, spec, tick, events, projectiles, velocities, shotRng) {
  if (!target?.alive || target.owner === unit.owner) return;
  let aim = (spec.smartMode & 1) === 1
    ? leadAimPoint(unit, target, spec, velocities)
    : { x: target.x, y: target.y };
  let distance = Math.hypot(aim.x - unit.x, aim.y - unit.y);
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
    const flight = Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed));
    projectiles.push({
      kind: "shell",
      actorId: unit.referenceId,
      actorOwner: unit.owner,
      actorMechanics: unit.mechanics,
      targetId: target.referenceId,
      aimX: aim.x,
      aimY: aim.y,
      blastRadius: spec.blastRadius,
      firedTick: tick,
      arrivalTick: tick + flight,
      index: 0,
    });
    for (let s = 0; s < spec.secondaryCount; s += 1) {
      const sx = (nextShotRoll(shotRng) - 0.5) * spec.spawnArea[0];
      const sy = (nextShotRoll(shotRng) - 0.5) * spec.spawnArea[1];
      projectiles.push({
        kind: "pebble",
        actorId: unit.referenceId,
        actorOwner: unit.owner,
        targetId: target.referenceId,
        aimX: aim.x + sx,
        aimY: aim.y + sy,
        firedTick: tick,
        arrivalTick: tick + flight,
        index: s + 1,
      });
    }
    return;
  }
  // Accuracy roll (dat accuracy_percent < 100 only — the hand cannoneer's
  // 75): a missed shot scatters uniformly within the dat dispersion
  // half-radius and becomes a STRAY that hits the first enemy whose box it
  // meets for HALF damage (tape full/half quanta pairs 22/11, 11/5.5, 8/4).
  if (spec.accuracyPercent < 100
      && nextShotRoll(shotRng) * 100 >= spec.accuracyPercent) {
    const radius = spec.dispersionTiles * Math.sqrt(nextShotRoll(shotRng));
    const angle = nextShotRoll(shotRng) * 2 * Math.PI;
    aim = { x: aim.x + radius * Math.cos(angle), y: aim.y + radius * Math.sin(angle) };
    distance = Math.hypot(aim.x - unit.x, aim.y - unit.y);
    if (distance <= 1e-9) return;
    projectiles.push({
      kind: "stray",
      actorId: unit.referenceId,
      actorOwner: unit.owner,
      actorMechanics: unit.mechanics,
      targetId: target.referenceId,
      x: unit.x,
      y: unit.y,
      stepX: ((aim.x - unit.x) / distance) * stepLength,
      stepY: ((aim.y - unit.y) / distance) * stepLength,
      stepLength,
      traveled: 0,
      totalDistance: distance,
      firedTick: tick,
      arrivalTick: tick + Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed)),
      index: 0,
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
      actorMechanics: unit.mechanics,
      targetId: target.referenceId,
      x: unit.x,
      y: unit.y,
      stepX: ((aim.x - unit.x) / distance) * stepLength,
      stepY: ((aim.y - unit.y) / distance) * stepLength,
      stepLength,
      traveled: 0,
      totalDistance: total,
      halfWidth: spec.projectileHalfWidth,
      firedTick: tick,
      arrivalTick: tick + Math.max(1, secondsToTicksCeil(total / spec.projectileSpeed)),
      index: 0,
      hitIds: [],
    });
    return;
  }
  projectiles.push({
    kind: "ranged",
    actorId: unit.referenceId,
    targetId: target.referenceId,
    x: unit.x,
    y: unit.y,
    stepX: ((aim.x - unit.x) / distance) * stepLength,
    stepY: ((aim.y - unit.y) / distance) * stepLength,
    stepLength,
    traveled: 0,
    totalDistance: distance,
    firedTick: tick,
    // The stepping loop below is the authority; arrivalTick is a cap so a
    // projectile can never outlive its aim distance.
    arrivalTick: tick + Math.max(1, secondsToTicksCeil(distance / spec.projectileSpeed)),
    index: 0,
    halfWidth: spec.projectileHalfWidth,
    amount: calculateDamage(unit, target),
  });
}


function progressAttacks(units, tick, events, movedIds, projectiles, velocities, shotRng) {
  const byReference = new Map(units.map((unit) => [unit.referenceId, unit]));
  const ready = [];
  for (const unit of units) {
    if (!unit.alive) continue;
    if (unit.actionTimers.reload > 0) unit.actionTimers.reload -= 1;
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
      const delay = charge ? charge.windupTicks : attackDelayTicks(unit.mechanics);
      const animation = charge
        ? charge.animationTicks
        : attackAnimationTicks(unit.mechanics);
      unit.actionTimers.swing += 1;
      unit.actionTimers.windup = Math.max(0, delay - unit.actionTimers.swing);
      if (unit.actionTimers.swing === delay) {
        const target = byReference.get(unit.attackTargetId);
        const ranged = rangedSpec(unit.mechanics);
        if (charge) {
          releaseChargeVolley(unit, target, charge, tick, events, projectiles);
        } else if (ranged) {
          releaseRangedShot(unit, target, ranged, tick, events, projectiles,
            velocities, shotRng);
        } else {
          ready.push({
            type: "attack-ready",
            readyTick: tick,
            actorId: unit.referenceId,
            targetId: unit.attackTargetId,
            amount: target ? calculateDamage(unit, target) : 0,
          });
        }
      }
      if (unit.actionTimers.swing >= animation) {
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
      if (chargeTarget?.alive && chargeTarget.owner !== unit.owner) {
        const distance = Math.hypot(chargeTarget.x - unit.x, chargeTarget.y - unit.y);
        if (distance <= unit.mechanics.line_of_sight_tiles) {
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
          unit.actionTimers.reload = reloadTicks(unit.mechanics);
          continue;
        }
      }
    }

    const target = byReference.get(unit.engagedTargetId);
    if (
      unit.actionTimers.reload !== 0 ||
      !target?.alive ||
      target.owner === unit.owner
    ) continue;
    if (!isWithinStopRange(unit, target) && movedIds.has(unit.referenceId)) continue;

    const delay = attackDelayTicks(unit.mechanics);
    const readyTick = tick + delay;
    events.push(createAttackStartEvent({
      tick,
      actorId: unit.referenceId,
      targetId: target.referenceId,
      readyTick,
    }));
    unit.action = "attacking";
    unit.attackTargetId = target.referenceId;
    unit.actionTimers.swing = 0;
    unit.actionTimers.windup = delay;
    unit.actionTimers.reload = reloadTicks(unit.mechanics);
    if (delay === 0) {
      ready.push({
        type: "attack-ready",
        readyTick,
        actorId: unit.referenceId,
        targetId: target.referenceId,
        amount: calculateDamage(unit, target),
      });
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
      || target.owner === actor.owner
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
      attack.readyTick, tick, events, null);

    // Trample: the committed hit also blasts every enemy whose collision box
    // intersects the attacker's blast circle (see trampleSpec for the sourced
    // rule). Victims are struck in unit order at this same instant, each for
    // its own post-armor fraction; a killing trample clamps at 0 like any hit.
    const blast = trampleSpec(actor.mechanics);
    if (blast) {
      for (const victim of units) {
        if (!victim.alive || victim.owner === actor.owner) continue;
        if (victim.referenceId === target.referenceId) continue;
        const reach = Math.hypot(
          Math.max(0, Math.abs(victim.x - actor.x) - collisionRadius(victim)),
          Math.max(0, Math.abs(victim.y - actor.y) - collisionRadius(victim)),
        );
        if (reach > blast.widthTiles + 1e-12) continue;
        applyCommittedDamage(units, attack.actorId, victim,
          blast.damageFraction * calculateDamage(actor, victim),
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
function processChargeProjectiles(units, projectiles, tick, events) {
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
    if (projectile.kind === "bolt") {
      // Pass-through flight: advance one step, damage every enemy whose
      // collision box (expanded by the bolt's half width) contains the
      // point, once per victim, never despawning on impact.
      projectile.x += projectile.stepX;
      projectile.y += projectile.stepY;
      projectile.traveled += projectile.stepLength;
      for (const victim of units) {
        if (!victim.alive || victim.owner === projectile.actorOwner) continue;
        if (projectile.hitIds.includes(victim.referenceId)) continue;
        const dx = Math.abs(victim.x - projectile.x);
        const dy = Math.abs(victim.y - projectile.y);
        const reach = collisionRadius(victim) + projectile.halfWidth;
        if (Math.max(dx, dy) > reach + 1e-9) continue;
        projectile.hitIds.push(victim.referenceId);
        const full = calculateDamage({ mechanics: projectile.actorMechanics }, victim);
        const amount = victim.referenceId === projectile.targetId
          ? full
          : PASS_THROUGH_DAMAGE_FRACTION * full;
        applyCommittedDamage(units, projectile.actorId, victim, amount,
          tick, tick, events,
          { kind: "bolt-projectile", projectileIndex: projectile.hitIds.length - 1 });
      }
      if (projectile.traveled < projectile.totalDistance - 1e-9) {
        remaining.push(projectile);
      }
      continue;
    }
    if (projectile.kind === "ranged") {
      // Physical point flight: advance one step along the line, hit the
      // moment the target's collision box contains the point. Steps (7/60 =
      // 0.117 tiles) are smaller than any collision box, so nothing tunnels.
      projectile.x += projectile.stepX;
      projectile.y += projectile.stepY;
      projectile.traveled += projectile.stepLength;
      const target = byReference.get(projectile.targetId);
      if (target?.alive) {
        const dx = Math.abs(target.x - projectile.x);
        const dy = Math.abs(target.y - projectile.y);
        // The arrow is a body too: it lands when its own dat half width
        // (projectile unit collision_size_x, 0.1 for every archer projectile in
        // the corpus) meets the victim's collision box -- the same rule the
        // scorpion bolt already used. Measured on impact geometry: recorded
        // arrows are last seen at a Chebyshev separation from the victim's
        // centre whose p97 is 0.310 against champions (collision 0.20 -> 0.30)
        // and 0.347 against heavy camels (collision 0.25 -> 0.35). The camel is
        // the first victim in the corpus whose collision box differs from its
        // outline, which is why a bare-collision rule survived this long.
        if (Math.max(dx, dy) <= collisionRadius(target) + projectile.halfWidth + 1e-9) {
          resolved.push(projectile);
          continue;
        }
      }
      // Expire at the aim point: the target died or left its box.
      if (projectile.traveled < projectile.totalDistance - 1e-9
          && tick < projectile.arrivalTick + 2) {
        remaining.push(projectile);
      }
      continue;
    }
    if (projectile.kind === "stray") {
      // Missed-accuracy shot: flies its scattered line and hits the FIRST
      // enemy whose collision box contains the point — for HALF the
      // per-victim class damage. Expires at the scattered aim point.
      projectile.x += projectile.stepX;
      projectile.y += projectile.stepY;
      projectile.traveled += projectile.stepLength;
      let struck = false;
      for (const victim of units) {
        if (!victim.alive || victim.owner === projectile.actorOwner) continue;
        const dx = Math.abs(victim.x - projectile.x);
        const dy = Math.abs(victim.y - projectile.y);
        if (Math.max(dx, dy) > collisionRadius(victim) + 1e-9) continue;
        const full = calculateDamage({ mechanics: projectile.actorMechanics }, victim);
        applyCommittedDamage(units, projectile.actorId, victim,
          Math.max(1, MISS_DAMAGE_FRACTION * full), tick, tick, events,
          { kind: "stray-projectile", projectileIndex: 0 });
        struck = true;
        break;
      }
      if (!struck && projectile.traveled < projectile.totalDistance - 1e-9
          && tick < projectile.arrivalTick + 2) {
        remaining.push(projectile);
      }
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
        const dx = Math.abs(victim.x - projectile.aimX);
        const dy = Math.abs(victim.y - projectile.aimY);
        const inBox = Math.max(dx, dy) <= collisionRadius(victim) + 1e-9;
        const centerDistance = Math.hypot(dx, dy);
        if (!inBox && centerDistance > projectile.blastRadius + 1e-9) continue;
        const fraction = inBox
          ? 1
          : Math.max(0, 1 - centerDistance / projectile.blastRadius);
        const full = calculateDamage({ mechanics: projectile.actorMechanics }, victim);
        applyCommittedDamage(units, projectile.actorId, victim,
          Math.max(1, fraction * full), tick, tick, events,
          { kind: "shell-projectile", projectileIndex: 0 });
      }
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
      for (const victim of units) {
        if (!victim.alive || victim.referenceId === projectile.actorId) continue;
        const dx = Math.abs(victim.x - projectile.aimX);
        const dy = Math.abs(victim.y - projectile.aimY);
        if (Math.max(dx, dy) > collisionRadius(victim) + 1e-9) continue;
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
      });
  }
  return remaining;
}


function applyCommittedDamage(units, actorId, target, amount, readyTick, tick, events, extra) {
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
  if (hpAfter > 0) return;

  target.alive = false;
  target.pursuitTargetId = null;
  target.engagedTargetId = null;
  target.attackTargetId = null;
  target.avoidance = null;
  target.action = "dead";
  target.actionTimers = { windup: 0, reload: 0, swing: 0, acquire: 0 };
  events.push(createDeathEvent({
    tick,
    actorId,
    targetId: target.referenceId,
    readyTick,
  }));
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
  validatePursuitTargets(units, tick, events);
  validateAttackTargets(units, tick, events);
  acquirePursuitTargets(units, tick, events, world.kiteState ?? null);
  issueKiteOrders(world.kiteState, units, world.map, tick, events, event);
  // Kiting tapes carry a SINGLE attack order for the melee side all fight —
  // none of the cvp-style sweep/rescue storm — so the ordinary order layer
  // stands down entirely when a beat controller is running; the melee side
  // fights on unit AI alone, exactly as recorded.
  if (!world.kiteState) {
    issueOrders(world.orderState, units, tick, events, event);
  }
  const { contacts, movedIds, blockedIds, velocities } = moveUnits(
    units, world.map, tick, events, world.kiteState ?? null, world.crowdState ?? null);
  updateEngagements(units, contacts, tick, events, blockedIds, world.kiteState ?? null);
  // Clone flight state: published projectiles are frozen, ranged shots
  // advance their position every tick, and a bolt's hit list must not alias
  // the previous tick's published array.
  const projectiles = world.projectiles
    ? world.projectiles.map((projectile) => ({
      ...projectile,
      ...(projectile.hitIds ? { hitIds: [...projectile.hitIds] } : {}),
    }))
    : null;
  const ready = progressAttacks(units, tick, events, movedIds, projectiles,
    velocities, world.shotRng ?? null);
  commitReadyAttacks(units, ready, tick, events);
  const remainingProjectiles = projectiles
    ? processChargeProjectiles(units, projectiles, tick, events)
    : null;

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
    ...(remainingProjectiles !== null
      ? { projectiles: Object.freeze(remainingProjectiles.map((p) => Object.freeze({ ...p }))) }
      : {}),
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
  if (liveOwners.size > 1) return null;
  const [winner] = liveOwners;
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
  { maxTicks = DEFAULT_WORLD_TICKS, retainSnapshots = true } = {},
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

  if (retainSnapshots) {
    let current = world;
    const initialOutcome = outcome(current);
    if (initialOutcome !== null) return initialOutcome;
    for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
      current = stepWorld(current);
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
  const initialOutcome = outcome(current);
  if (initialOutcome !== null) return compactResult(initialOutcome, current);
  current = compactWorld(current);
  for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
    current = stepWorld(current);
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
