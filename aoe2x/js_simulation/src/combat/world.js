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
  ENGAGEMENT_FOLLOWS_PURSUIT,
  shouldReevaluatePursuit,
} from "./experiments.js";
import { planLocalAvoidance } from "./local-avoidance.js";
import { proposeMovement } from "./movement.js";
import {
  isWithinReach,
  selectEngagementTarget,
  selectPursuitTarget,
} from "./targeting.js";
import { TICKS_PER_SECOND, secondsToTicksCeil } from "../simulation-clock.js";
import {
  BOLT_OVERSHOOT_TILES,
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
import { collisionRadius } from "./targeting.js";


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


function createSnapshot(tick, units, events) {
  return Object.freeze({ tick, units, events });
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
  const events = Object.freeze([]);
  const snapshot = createSnapshot(0, units, events);
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
    ...(Number.isSafeInteger(scenario.kiteOwner)
      ? { kiteState: createKiteState(scenario.kiteOwner, scenario.kiteProfile ?? null) }
      : {}),
    ...(anyCharge ? { projectiles: Object.freeze([]) } : {}),
    tick: 0,
    ratio: scenario.ratio,
    mapHash: scenario.mapHash,
    map: scenario.map ? freezeMap(scenario.map) : DEFAULT_MAP,
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


function acquirePursuitTargets(units, tick, events) {
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
    const reevaluate = unit.pursuitTargetId !== null && shouldReevaluatePursuit(unit);
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


function moveUnits(units, map, tick, events, kiteState = null) {
  const live = units.filter(({ alive }) => alive).map(freezeUnit);
  const byReference = new Map(live.map((unit) => [unit.referenceId, unit]));
  if (kiteState && !kiteState.chaseWaypoints) kiteState.chaseWaypoints = new Map();
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
    return { ...target, x: waypoint.x, y: waypoint.y };
  };
  const proposals = live.map((unit) => {
    // A kite move order overrides everything: the tape's move-ordered units
    // walk their waypoint and do not fight until the next attack beat.
    if (unit.moveOrder && unit.action !== "attacking") {
      const dx = unit.moveOrder.x - unit.x;
      const dy = unit.moveOrder.y - unit.y;
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
    const target = byReference.get(unit.pursuitTargetId);
    return target && unit.action !== "attacking" && !isWithinStopRange(unit, target)
      && !holdsForChargeVolley(unit, target)
      ? proposeMovement(unit, chaseAim(unit, target), TICKS_PER_SECOND)
      : Object.freeze({ referenceId: unit.referenceId, dx: 0, dy: 0 });
  });
  const planned = planLocalAvoidance(live, proposals, map);
  const moved = resolveMovementProposals(planned.units, planned.proposals, map);
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
      const inReach = gap <= KITE_DWELL_HOLD_RADIUS_TILES + 1e-12
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
      const nextTargetId = inReach
        && (carried + 1 >= KITE_CHASE_DWELL_TICKS
          || previousTargetId === pursued.referenceId)
        ? pursued.referenceId
        : null;
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


function releaseRangedShot(unit, target, spec, tick, events, projectiles, velocities) {
  if (!target?.alive || target.owner === unit.owner) return;
  const aim = (spec.smartMode & 1) === 1
    ? leadAimPoint(unit, target, spec, velocities)
    : { x: target.x, y: target.y };
  const distance = Math.hypot(aim.x - unit.x, aim.y - unit.y);
  if (distance <= 1e-9) return;
  const stepLength = spec.projectileSpeed / TICKS_PER_SECOND;
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
    amount: calculateDamage(unit, target),
  });
}


function progressAttacks(units, tick, events, movedIds, projectiles, velocities) {
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
          releaseRangedShot(unit, target, ranged, tick, events, projectiles, velocities);
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
        if (Math.max(dx, dy) <= collisionRadius(target) + 1e-9) {
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
  acquirePursuitTargets(units, tick, events);
  issueKiteOrders(world.kiteState, units, world.map, tick, events, event);
  // Kiting tapes carry a SINGLE attack order for the melee side all fight —
  // none of the cvp-style sweep/rescue storm — so the ordinary order layer
  // stands down entirely when a beat controller is running; the melee side
  // fights on unit AI alone, exactly as recorded.
  if (!world.kiteState) {
    issueOrders(world.orderState, units, tick, events, event);
  }
  const { contacts, movedIds, blockedIds, velocities } = moveUnits(
    units, world.map, tick, events, world.kiteState ?? null);
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
  const ready = progressAttacks(units, tick, events, movedIds, projectiles, velocities);
  commitReadyAttacks(units, ready, tick, events);
  const remainingProjectiles = projectiles
    ? processChargeProjectiles(units, projectiles, tick, events)
    : null;

  const publishedUnits = canonicalUnits(units);
  const publishedEvents = Object.freeze(events);
  const eventLog = Object.freeze([...world.eventLog, ...publishedEvents]);
  const snapshots = Object.freeze([
    ...world.snapshots,
    createSnapshot(tick, publishedUnits, publishedEvents),
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


export function runWorld(world, { maxTicks = DEFAULT_WORLD_TICKS } = {}) {
  if (!Number.isSafeInteger(maxTicks) || maxTicks < 0) {
    throw new RangeError("max ticks must be a nonnegative safe integer");
  }
  if (maxTicks > MAX_WORLD_TICKS) {
    throw new RangeError(`max ticks must not exceed ${MAX_WORLD_TICKS}`);
  }
  let current = world;
  const initialOutcome = outcome(current);
  if (initialOutcome !== null) return initialOutcome;
  for (let elapsed = 0; elapsed < maxTicks; elapsed += 1) {
    current = stepWorld(current);
    const result = outcome(current);
    if (result !== null) return result;
  }
  throw new Error(`world exceeded ${maxTicks} ticks`);
}
