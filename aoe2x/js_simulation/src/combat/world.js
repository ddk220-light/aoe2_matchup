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
import { collisionRadius } from "./targeting.js";
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


function freezeUnit(unit) {
  return Object.freeze({
    ...unit,
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
    ...(unit.relationByOwner
      ? { relationByOwner: Object.freeze({ ...unit.relationByOwner }) }
      : {}),
    avoidance: unit.avoidance === null ? null : { ...unit.avoidance },
    actionTimers: { ...unit.actionTimers },
  };
}


function freezeMap(map) {
  return immutableClone({ ...map, obstacles: [...(map.obstacles ?? [])] });
}


function nextPursuitRecoveryState(previous = null) {
  return {
    attempts: new Map(previous?.attempts ?? []),
    routes: new Map(previous?.routes ?? []),
    retargetReady: new Set(previous?.retargetReady ?? []),
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


function applyOpeningPatrol(units, openingPatrolByOwner, map) {
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
    destinations.set(owner, Object.freeze({ x, y, kind: "opening-patrol" }));
  }
  if (destinations.size !== owners.size) {
    throw new RangeError("opening patrol must provide every scenario owner");
  }
  return units.map((unit) => {
    if (unit.moveOrder !== undefined && unit.moveOrder !== null) {
      throw new Error(`unit ${unit.referenceId} already has a move order`);
    }
    const destination = destinations.get(unit.owner);
    return {
      ...unit,
      moveOrder: destination,
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


function selectPatrolCohortOpeningTargets(unit, snapshot, order) {
  // First confirm that shared player vision has exposed at least one hostile
  // body. The game's group decision then names a cohort anchor set, including
  // for members that do not individually see every anchor yet. Target choice
  // is the explicitly permitted opening stochastic boundary; roster order is stable
  // scenario input and is never consulted by subsequent retargeting.
  if (selectPatrolOpeningTarget(unit, snapshot, order) === null) return null;
  const roster = snapshot.filter((candidate) => candidate.alive && isHostile(unit, candidate));
  if (roster.length === 0) return null;
  const cohortSize = snapshot.filter((candidate) => (
    candidate.alive && candidate.owner === unit.owner
  )).length;
  const hostileFrontIsRanged = roster.every(({ mechanics }) => mechanics?.ranged);
  if (!hostileFrontIsRanged || unit.owner === 4) {
    // A melee roster presents one advancing contact surface. The scenario's
    // stable creation order is also the game's group roster order: across the
    // mixed captures its roughly 80%-depth member receives 60-100% of first
    // locks, with fan-out only when the ranged cohort is outnumbered. Keep
    // this explicitly inside the permitted first-target boundary; no later
    // retarget or damage decision can inspect roster order.
    const ordered = roster.slice().sort((left, right) => (
      left.referenceId - right.referenceId
    ));
    const anchorCount = unit.owner === 4 || cohortSize >= ordered.length
      ? 1
      : Math.max(2, Math.floor(ordered.length / 4));
    const defaultAnchor = Math.min(
      ordered.length - 1,
      Math.floor(ordered.length * 0.8),
    );
    const seedRoll = (order.openingSeed ?? 0) === 0
      ? 2
      : openingHash(order.openingSeed, unit.owner, ordered.length) % 5;
    const center = Math.max(0, Math.min(
      ordered.length - 1,
      defaultAnchor + [-2, -1, 0, 1, 2][seedRoll],
    ));
    const first = Math.max(0, Math.min(
      ordered.length - anchorCount,
      center - Math.floor(anchorCount / 2),
    ));
    return ordered.slice(first, first + anchorCount);
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
  // Player 4 is one committed auxiliary group. A principal cohort that is at
  // least as large as the opposing roster names both exposed flanks; an
  // outnumbered cohort samples the whole visible front rank. This is still
  // only the explicitly permitted first-target boundary. Subsequent targeting
  // is ordinary distance/contact AI and never consults formation membership.
  const anchorCount = cohortSize >= roster.length
    ? Math.min(2, frontBand.length)
    : frontBand.length;
  if (anchorCount >= frontBand.length) {
    return frontBand.map(({ candidate }) => candidate);
  }
  if (anchorCount === 1) {
    return [frontBand[Math.floor(frontBand.length / 2)].candidate];
  }
  const selected = [];
  for (let index = 0; index < anchorCount; index += 1) {
    const frontIndex = Math.round(index * (frontBand.length - 1) / (anchorCount - 1));
    selected.push(frontBand[frontIndex].candidate);
  }
  return selected;
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
  if (scenario.rangedOpportunityRetargetOwner !== undefined
      && !Number.isSafeInteger(scenario.rangedOpportunityRetargetOwner)) {
    throw new TypeError("ranged opportunity retarget owner must be a safe integer");
  }
  if (Number.isSafeInteger(scenario.rangedOpportunityRetargetOwner)
      && !units.some(({ owner }) => owner === scenario.rangedOpportunityRetargetOwner)) {
    throw new RangeError("ranged opportunity retarget owner must identify a scenario owner");
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
    ...(Number.isSafeInteger(scenario.rangedOpportunityRetargetOwner)
      ? { rangedOpportunityRetargetOwner: scenario.rangedOpportunityRetargetOwner }
      : {}),
    ...(Number.isSafeInteger(scenario.rangedWindupRetargetOwner)
      ? { rangedWindupRetargetOwner: scenario.rangedWindupRetargetOwner }
      : {}),
    scenarioOwners,
    diplomacyByOwner,
    victoryTeams,
    ...(scenarioTriggerState ? { scenarioTriggerState } : {}),
    ...(scenarioTriggerState ? { patrolOpeningTargetByOwner: new Map() } : {}),
    contactReservationState,
    contactReservationDiagnostics: Object.freeze([]),
    ...(contactSteeringStates ? { contactSteeringStates } : {}),
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
      : attackDelayTicks(unit.mechanics);
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
          { fromTargetId: invalidTargetId },
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
    delete unit.attackKind;
    unit.actionTimers.windup = 0;
    unit.actionTimers.swing = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
  }
}


function acquirePursuitTargets(
  units,
  tick,
  events,
  kiteState = null,
  rangedTargetPressureOwner = null,
  rangedOpportunityRetargetOwner = null,
  patrolOpeningTargetByOwner = null,
  pursuitRecoveryState = null,
  map = DEFAULT_MAP,
  pairInteractions = createPairInteractionSnapshot(),
) {
  const snapshot = Object.freeze(units.map(freezeUnit));
  const targetPressureTiles = kiteState?.attackMoveTargetPressureTiles ?? 0;
  const targetLoadById = targetPressureTiles > 0
      || Number.isSafeInteger(rangedTargetPressureOwner)
    ? new Map()
    : null;
  if (targetLoadById) {
    for (const unit of units) {
      const kitePressureApplies = targetPressureTiles > 0
        && unit.owner !== kiteState.owner;
      const rangedPressureApplies = unit.owner === rangedTargetPressureOwner;
      if (!unit.alive || (!kitePressureApplies && !rangedPressureApplies)) continue;
      if (unit.pursuitTargetId === null || unit.pursuitTargetId === undefined) continue;
      targetLoadById.set(
        unit.pursuitTargetId,
        (targetLoadById.get(unit.pursuitTargetId) ?? 0) + 1,
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
        && unit.moveOrder?.kind === "scenario-patrol"
        && unit.openingAcquisitionComplete !== true
        && tick >= unit.moveOrder.nextOpeningScanTick)
      .map(({ owner }) => owner))]
      .sort((left, right) => left - right);
    for (const owner of openingOwners) {
      if (patrolOpeningTargetByOwner.has(owner)) continue;
      const detectors = units.filter((unit) => unit.alive && unit.owner === owner
        && unit.moveOrder?.kind === "scenario-patrol"
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
    const openingPatrolOrder = unit.moveOrder?.kind === "scenario-patrol"
      && unit.openingAcquisitionComplete !== true
      ? unit.moveOrder
      : null;
    // Initial target-acquisition delay. Only the first acquisition waits; once a
    // unit has been in combat, re-acquisition is governed by its swing state.
    // A group PATROL scans on the game AI's shared opening cadence. Units that
    // do not yet have line of sight remain in formation until the next scan;
    // they do not poll continuously on every render tick.
    if (openingPatrolOrder) {
      if (tick < openingPatrolOrder.nextOpeningScanTick) continue;
      unit.actionTimers.acquire = 0;
    } else if (unit.actionTimers.acquire > 0) {
      unit.actionTimers.acquire -= 1;
      // Acquire on the very tick the delay expires, so no unit is ever briefly
      // idle with an expired timer and no target.
      if (unit.actionTimers.acquire > 0) continue;
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
        pursuitRecoveryState.routeFailures.delete(unit.referenceId);
        pursuitRecoveryState.failedTargets.delete(unit.referenceId);
      }
      const retargetReady = pursuitRecoveryState.retargetReady.has(unit.referenceId);
      const opportunity = (routeActive || retargetReady)
          && current?.alive && !isWithinReach(unit, current)
        ? recoveryOpportunityTarget(unit, snapshot)
        : null;
      const alternate = opportunity ?? (
        retargetReady
          ? recoveryAlternateTarget(
            unit,
            snapshot,
            pursuitRecoveryState,
            map,
            pairInteractions,
          )
          : null
      );
      pursuitRecoveryState.retargetReady.delete(unit.referenceId);
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
    const rangedOpportunity = unit.owner === rangedOpportunityRetargetOwner
      && unit.mechanics?.ranged !== undefined
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
    const rangedPressureApplies = unit.owner === rangedTargetPressureOwner;
    const pressureApplies = targetLoadById !== null
      && (kitePressureApplies || rangedPressureApplies);
    const pressureTiles = rangedPressureApplies
      ? 2 * collisionRadius(unit)
      : targetPressureTiles;
    if (pressureApplies && reevaluate) {
      const previousLoad = targetLoadById.get(unit.pursuitTargetId) ?? 0;
      if (previousLoad <= 1) targetLoadById.delete(unit.pursuitTargetId);
      else targetLoadById.set(unit.pursuitTargetId, previousLoad - 1);
    }
    const found = snapshot.find(({ referenceId }) => referenceId === unit.referenceId);
    // selectPursuitTarget short-circuits on a live locked target, so a
    // re-evaluation has to present the unit as unlocked to force a fresh scan.
    const candidate = reevaluate ? { ...found, pursuitTargetId: null } : found;
    const scenarioPatrol = openingPatrolOrder;
    const lockedPatrolTargetIds = scenarioPatrol
      ? patrolOpeningTargetByOwner?.get(unit.owner)
      : null;
    const hasLockedPatrolTarget = Array.isArray(lockedPatrolTargetIds)
      && lockedPatrolTargetIds.length > 0;
    const gateAnchorIndex = hasLockedPatrolTarget
      ? openingHash(
        scenarioPatrol.openingSeed ?? 0,
        unit.owner,
        unit.referenceId,
      ) % lockedPatrolTargetIds.length
      : null;
    const rangedOpeningFront = hasLockedPatrolTarget
      && lockedPatrolTargetIds.every((referenceId) => (
        snapshot.find((possible) => possible.referenceId === referenceId)
          ?.mechanics?.ranged
      ));
    const gatePatrolTarget = hasLockedPatrolTarget
      ? snapshot.find((possible) => (
        possible.referenceId === lockedPatrolTargetIds[gateAnchorIndex]
          && possible.alive
          && isHostile(unit, possible)
          && Math.hypot(possible.x - unit.x, possible.y - unit.y)
            - collisionRadius(possible)
            <= unit.mechanics.line_of_sight_tiles + 1e-12
      )) ?? null
      : null;
    const rangedAssignmentTargets = rangedOpeningFront
      ? lockedPatrolTargetIds
        .map((referenceId) => snapshot.find((possible) => (
          possible.referenceId === referenceId
            && possible.alive
            && isHostile(unit, possible)
        )) ?? null)
        .filter((possible) => possible !== null)
      : [];
    const opposingRange = rangedAssignmentTargets.reduce((maximum, possible) => (
      Math.max(maximum, possible.mechanics?.attack_range_tiles ?? 0)
    ), 0);
    const rangeDisadvantage = Math.max(
      0,
      opposingRange - (unit.mechanics?.attack_range_tiles ?? 0),
    );
    const outsideFiringEnvelope = rangedAssignmentTargets.filter((possible) => (
      Math.hypot(possible.x - unit.x, possible.y - unit.y)
        > collisionRadius(unit) + collisionRadius(possible)
          + unit.mechanics.attack_range_tiles + rangeDisadvantage
    ));
    const nonGateOutside = outsideFiringEnvelope.filter((possible) => (
      possible.referenceId !== gatePatrolTarget?.referenceId
    ));
    const assignmentPool = nonGateOutside.length > 0
      ? nonGateOutside
      : outsideFiringEnvelope.length > 0
        ? outsideFiringEnvelope
        : rangedAssignmentTargets;
    const assignmentIndex = assignmentPool.length > 0
      ? openingHash(
        (scenarioPatrol.openingSeed ?? 0) ^ 0x6d2b79f5,
        unit.owner,
        unit.referenceId,
      ) % assignmentPool.length
      : null;
    const lockedPatrolTargetId = rangedOpeningFront
      ? assignmentIndex === null ? null : assignmentPool[assignmentIndex].referenceId
      : hasLockedPatrolTarget
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
      ? hasLockedPatrolTarget
        ? lockedPatrolTarget
        : selectPatrolOpeningTarget(candidate, snapshot, scenarioPatrol)
      : selectPursuitTarget(candidate, snapshot, pressureApplies
        ? { targetLoadById, targetLoadPenaltyTiles: pressureTiles }
        : undefined);
    if (target === null) {
      if (scenarioPatrol) {
        unit.moveOrder = Object.freeze({
          ...scenarioPatrol,
          nextOpeningScanTick: tick + Math.round(PATROL_RESCAN_SECONDS * TICKS_PER_SECOND),
        });
      }
      if (pressureApplies && reevaluate) {
        targetLoadById.set(
          unit.pursuitTargetId,
          (targetLoadById.get(unit.pursuitTargetId) ?? 0) + 1,
        );
      }
      continue;
    }
    if (pressureApplies) {
      targetLoadById.set(target.referenceId, (targetLoadById.get(target.referenceId) ?? 0) + 1);
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
  const firstScanMinimum = effect.owner === 4
    ? AUXILIARY_PATROL_FIRST_SCAN_MIN_SECONDS
    : PATROL_FIRST_SCAN_MIN_SECONDS;
  const firstScanTick = tick + Math.round((
    firstScanMinimum
      + openingFraction * (PATROL_FIRST_SCAN_MAX_SECONDS - firstScanMinimum)
  ) * TICKS_PER_SECOND);
  let selected = 0;
  for (const unit of units) {
    if (!unit.alive || unit.owner !== effect.owner || !unitInsideArea(unit, effect.area)) {
      continue;
    }
    selected += 1;
    unit.pursuitTargetId = null;
    unit.engagedTargetId = null;
    unit.attackTargetId = null;
    unit.avoidance = null;
    delete unit.attackKind;
    unit.actionTimers.windup = 0;
    unit.actionTimers.swing = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
    unit.moveOrder = Object.freeze({
      kind: "scenario-patrol",
      // The scenario trigger issues one patrol destination to the selected
      // group. Individual combat pursuit takes over at first acquisition.
      x: effect.x,
      y: effect.y,
      commandX: effect.x,
      commandY: effect.y,
      issuedTick: tick,
      triggerId: trigger.id,
      openingSeed: trigger.openingSeed ?? 0,
      motionStartTick: tick + Math.round(PATROL_ORDER_REACTION_SECONDS * TICKS_PER_SECOND),
      nextOpeningScanTick: firstScanTick,
    });
  }
  events.push(event(tick, "patrol-issued", effect.owner, null, {
    owner: effect.owner,
    x: effect.x,
    y: effect.y,
    selected,
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
  };
}


function advanceScenarioTriggers(world, units, tick, events) {
  if (!world.scenarioTriggerState) {
    return {
      diplomacyByOwner: world.diplomacyByOwner,
      triggerState: null,
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
    if (!isHostile(unit, other)) continue;
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
      if (unit.moveOrder.kind === "scenario-patrol"
          && Number.isSafeInteger(unit.moveOrder.motionStartTick)
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
      if (engaged && engaged.alive && isHostile(unit, engaged)) {
        const distance = Math.hypot(engaged.x - unit.x, engaged.y - unit.y);
        if (distance <= unit.mechanics.line_of_sight_tiles) continue;
      }
    }
    const self = snapshot.find(({ referenceId }) => referenceId === unit.referenceId);
    const meleeReachRanks = unit.mechanics?.ranged
      ? 0
      : Math.max(0, Math.floor(unit.mechanics?.attack_range_tiles ?? 0));
    // The two-claimant reservation is a body-contact surface. A reach fighter
    // can occupy additional outline-reach ranks behind that surface without
    // claiming another deep collision slot. Scale the engagement capacity by
    // physical reach ranks; range-zero behavior remains exactly two.
    const incomingEngagementCapacity = MAX_INCOMING_ENGAGEMENTS
      + meleeReachRanks;
    const targetAvailable = (candidate) => (
      unit.mechanics?.ranged
      || candidate.referenceId === previousTargetId
      || (incomingMeleeEngagements.get(candidate.referenceId) ?? 0)
        < incomingEngagementCapacity
    );
    const selection = selectEngagementTarget(self, snapshot, contacts, { targetAvailable });
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
    const auxiliaryPatrolPursuit = unit.owner === 4 || pursued?.owner === 4;
    const auxiliaryPatrolPursuitLocked = unit.moveOrder?.kind === "scenario-patrol"
      && pursued?.alive === true
      && auxiliaryPatrolPursuit;
    const openingRangedPatrolLocked = false;
    const latchedPatrolBlocker = auxiliaryPatrolPursuitLocked
        && Number.isSafeInteger(previousTargetId)
        && previousTargetId !== pursued.referenceId
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
      ? (pursuedClosed && isWithinReach(self, pursued) && targetAvailable(pursued)
        ? pursued.referenceId
        : null)
      : auxiliaryPatrolPursuitLocked
      ? (pursuedClosed && isWithinReach(self, pursued) && targetAvailable(pursued)
        ? pursued.referenceId
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
function releaseChargeVolley(unit, target, spec, tick, events, projectiles) {
  // The volley leaves the unit whether or not anything is left to aim at; an
  // unreleased cycle abandoned earlier (validateAttackTargets) keeps its
  // charge instead.
  unit.charge = 0;
  if (!target?.alive || !isHostile(unit, target)) return;
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
  if (!target?.alive || !isHostile(unit, target)) return;
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
      actorRelationByOwner: unit.relationByOwner,
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
      actorRelationByOwner: unit.relationByOwner,
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
      if (chargeTarget?.alive && isHostile(unit, chargeTarget)) {
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
      !isHostile(unit, target)
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
      attack.readyTick, tick, events, null);

    // Trample: the committed hit also blasts every enemy whose collision box
    // intersects the attacker's blast circle (see trampleSpec for the sourced
    // rule). Victims are struck in unit order at this same instant, each for
    // its own post-armor fraction; a killing trample clamps at 0 like any hit.
    const blast = trampleSpec(actor.mechanics);
    if (blast) {
      for (const victim of units) {
        if (!victim.alive || !isHostile(actor, victim)) continue;
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
        if (!victim.alive || !isHostile({
          referenceId: projectile.actorId,
          owner: projectile.actorOwner,
          relationByOwner: projectile.actorRelationByOwner,
        }, victim)) continue;
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
        if (!victim.alive || !isHostile({
          referenceId: projectile.actorId,
          owner: projectile.actorOwner,
          relationByOwner: projectile.actorRelationByOwner,
        }, victim)) continue;
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
  const pursuitRecoveryState = nextPursuitRecoveryState(
    world.pursuitRecoveryState ?? null,
  );
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
    world.rangedOpportunityRetargetOwner ?? null,
    world.patrolOpeningTargetByOwner ?? null,
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
  const ready = progressAttacks(units, tick, events, movedIds, projectiles,
    velocities, world.shotRng ?? null);
  commitReadyAttacks(units, ready, tick, events);
  const remainingProjectiles = projectiles
    ? processChargeProjectiles(units, projectiles, tick, events)
    : null;
  const scenarioUpdate = advanceScenarioTriggers(world, units, tick, events);

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
    ...(scenarioUpdate.triggerState
      ? { scenarioTriggerState: scenarioUpdate.triggerState }
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
