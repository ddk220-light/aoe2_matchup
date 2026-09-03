import { TICKS_PER_SECOND } from "../simulation-clock.js";


export const SOLO_NAVIGATION_VARIANTS = Object.freeze([
  "baseline",
  "per-unit-grid",
  "cohesive",
]);

const MIN_SLOT_SPACING_TILES = 0.48;
const MIN_ROUTE_CLEARANCE_TILES = 1.25;
const ROUTE_CLEARANCE_MARGIN_TILES = 0.07;
const ANCHOR_LEASH_TILES = 0.62;
const ANCHOR_REACHED_TILES = 0.18;
const FIRST_ORDER_DELTA_TILES = 0.25;
const STALL_REPLAN_TICKS = Math.round(1.25 * TICKS_PER_SECOND);
const ROUTE_LOOKAHEAD_TILES = 0.75;


export function requireSoloNavigationVariant(value) {
  if (!SOLO_NAVIGATION_VARIANTS.includes(value)) {
    throw new RangeError(
      `navigation must be one of ${SOLO_NAVIGATION_VARIANTS.join(", ")}, got ${value}`,
    );
  }
  return value;
}


function centroid(units) {
  if (units.length === 0) return { x: 0, y: 0 };
  return {
    x: units.reduce((sum, unit) => sum + unit.x, 0) / units.length,
    y: units.reduce((sum, unit) => sum + unit.y, 0) / units.length,
  };
}


function orderCentroid(units, fallback) {
  const ordered = units.filter(({ moveOrder }) => moveOrder);
  if (ordered.length === 0) return fallback;
  return {
    x: ordered.reduce((sum, unit) => sum + unit.moveOrder.x, 0) / ordered.length,
    y: ordered.reduce((sum, unit) => sum + unit.moveOrder.y, 0) / ordered.length,
  };
}


function maximumCollisionRadius(units) {
  return units.reduce((maximum, unit) => Math.max(
    maximum,
    unit.mechanics?.collision_size_tiles?.x ?? 0,
  ), 0);
}


function compactSlots(count, spacing) {
  const width = Math.ceil(Math.sqrt(count));
  const height = Math.ceil(count / width);
  const candidates = [];
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < width; column += 1) {
      candidates.push({
        x: (column - (width - 1) / 2) * spacing,
        y: (row - (height - 1) / 2) * spacing,
      });
    }
  }
  return candidates
    .sort((a, b) => {
      const da = a.x * a.x + a.y * a.y;
      const db = b.x * b.x + b.y * b.y;
      return da !== db ? da - db : (a.y !== b.y ? a.y - b.y : a.x - b.x);
    })
    .slice(0, count)
    .sort((a, b) => (a.y !== b.y ? a.y - b.y : a.x - b.x));
}


function assignStableSlots(units, { formationSpacingTiles } = {}) {
  const own = centroid(units);
  const ordered = [...units].sort((a, b) => (
    a.y !== b.y ? a.y - b.y : (a.x !== b.x ? a.x - b.x : a.referenceId - b.referenceId)
  ));
  // Formation orders are allowed to compress allied bodies: the movement
  // solver deliberately exempts two allies that both hold formation orders,
  // matching the recorded marching blocks. Most ranged units use the measured
  // half-tile lattice. A tape-measured profile may provide a wider lattice for
  // a large body; this has to reach cohesive navigation as well as the visible
  // kite order, otherwise the navigation layer silently compresses the group
  // back to 0.48 tiles on the next tick.
  const spacing = Number.isFinite(formationSpacingTiles) && formationSpacingTiles > 0
    ? formationSpacingTiles
    : MIN_SLOT_SPACING_TILES;
  const slots = compactSlots(units.length, spacing);
  return new Map(ordered.map((unit, index) => [unit.referenceId, slots[index]]));
}


function perimeter(bounds) {
  return 2 * ((bounds.hiX - bounds.loX) + (bounds.hiY - bounds.loY));
}


function ringArc(bounds, point) {
  const width = bounds.hiX - bounds.loX;
  const height = bounds.hiY - bounds.loY;
  const x = Math.min(bounds.hiX, Math.max(bounds.loX, point.x));
  const y = Math.min(bounds.hiY, Math.max(bounds.loY, point.y));
  const choices = [
    { gap: Math.abs(point.y - bounds.loY), arc: x - bounds.loX },
    { gap: Math.abs(point.x - bounds.hiX), arc: width + y - bounds.loY },
    { gap: Math.abs(point.y - bounds.hiY), arc: width + height + bounds.hiX - x },
    { gap: Math.abs(point.x - bounds.loX), arc: 2 * width + height + bounds.hiY - y },
  ];
  return choices.reduce((best, candidate) => candidate.gap < best.gap ? candidate : best).arc;
}


function ringPoint(bounds, arc) {
  const width = bounds.hiX - bounds.loX;
  const height = bounds.hiY - bounds.loY;
  let value = ((arc % perimeter(bounds)) + perimeter(bounds)) % perimeter(bounds);
  if (value < width) return { x: bounds.loX + value, y: bounds.loY };
  value -= width;
  if (value < height) return { x: bounds.hiX, y: bounds.loY + value };
  value -= height;
  if (value < width) return { x: bounds.hiX - value, y: bounds.hiY };
  value -= width;
  return { x: bounds.loX, y: bounds.hiY - value };
}


function nominalRing(map) {
  return {
    loX: map.width / 2 - 3,
    hiX: map.width / 2 + 3,
    loY: map.height / 2 - 3,
    hiY: map.height / 2 + 3,
  };
}


function centralObstacleEnvelope(map, slots, bodyRadius) {
  const nominal = nominalRing(map);
  const central = (map.obstacles ?? []).filter((body) => (
    body.x >= nominal.loX && body.x <= nominal.hiX
    && body.y >= nominal.loY && body.y <= nominal.hiY
  ));
  if (central.length === 0) return nominal;
  const slotReach = [...slots.values()].reduce((maximum, slot) => Math.max(
    maximum,
    Math.abs(slot.x),
    Math.abs(slot.y),
  ), 0);
  const margin = Math.max(
    MIN_ROUTE_CLEARANCE_TILES,
    slotReach + bodyRadius + ROUTE_CLEARANCE_MARGIN_TILES,
  );
  return {
    loX: Math.min(...central.map((body) => body.x - body.radius)) - margin,
    hiX: Math.max(...central.map((body) => body.x + body.radius)) + margin,
    loY: Math.min(...central.map((body) => body.y - body.radius)) - margin,
    hiY: Math.max(...central.map((body) => body.y + body.radius)) + margin,
  };
}


function mapAiWaypointToEnvelope(state) {
  const nominalArc = ringArc(state.nominalRing, state.aiWaypoint);
  const nominalPerimeter = perimeter(state.nominalRing);
  const routePerimeter = perimeter(state.routeBounds);
  const raw = (nominalArc / nominalPerimeter) * routePerimeter;
  let unwrapped = raw;
  if (state.targetRouteArc !== null) {
    while (unwrapped < state.targetRouteArc - routePerimeter / 2) {
      unwrapped += routePerimeter;
    }
    unwrapped = Math.max(unwrapped, state.targetRouteArc);
  }
  state.targetRouteArc = unwrapped;
}


function routeAnchor(state, units, map, tick) {
  const speed = units[0]?.mechanics?.speed_tiles_per_second ?? 0;
  // At a corner, static bodies can temporarily push one unit away from its
  // ideal slot. The formation must be elastic by at least one unit diameter
  // or large siege bodies can hold the entire anchor forever while trying to
  // occupy an obstructed slot. Ordinary ranged bodies retain the established
  // 0.62-tile leash; Scorpions derive a one-tile leash from their mechanics.
  const leash = Math.max(ANCHOR_LEASH_TILES, 2 * maximumCollisionRadius(units));
  const errors = units.map((unit) => {
    const slot = state.slots.get(unit.referenceId);
    if (!slot) return { referenceId: unit.referenceId, error: 0 };
    const goal = { x: state.anchor.x + slot.x, y: state.anchor.y + slot.y };
    return {
      referenceId: unit.referenceId,
      error: Math.hypot(unit.x - goal.x, unit.y - goal.y),
    };
  });
  const maximumError = errors.reduce((maximum, current) => (
    Math.max(maximum, current.error)
  ), 0);
  const mobileErrors = errors.filter(({ referenceId }) => (
    !state.blockedReferenceIds.has(referenceId)
  ));
  const strictMajority = Math.floor(units.length / 2) + 1;
  const leashError = mobileErrors.length >= strictMajority
    ? [...mobileErrors]
      .sort((left, right) => left.error - right.error)[strictMajority - 1].error
    : maximumError;
  if (state.phase === "forming-first-order") {
    if (leashError > leash || speed <= 0) return maximumError;
    state.phase = "routing";
    state.lastAnchorMoveTick = tick;
  }
  const reached = !state.routeWaypoint
    || Math.hypot(state.anchor.x - state.routeWaypoint.x,
      state.anchor.y - state.routeWaypoint.y) <= ANCHOR_REACHED_TILES;
  const stalled = tick - state.lastAnchorMoveTick >= STALL_REPLAN_TICKS;
  mapAiWaypointToEnvelope(state);
  if (reached) {
    state.routeArc = Math.min(
      state.targetRouteArc,
      state.routeArc + ROUTE_LOOKAHEAD_TILES,
    );
    state.routeWaypoint = ringPoint(state.routeBounds, state.routeArc);
  }
  if (stalled && tick - state.lastStallReplanTick >= STALL_REPLAN_TICKS) {
    state.lastStallReplanTick = tick;
    state.replans += 1;
    // Re-project to the next clockwise perimeter point. This handles an anchor
    // that was held while stragglers regrouped without reversing the lap.
    state.routeArc = Math.max(state.routeArc, ringArc(state.routeBounds, state.anchor));
    state.routeWaypoint = ringPoint(state.routeBounds, state.routeArc);
  }

  // The strict majority owns formation progress. A minority of physically
  // blocked or independently lagging units rejoins from its own destination;
  // it cannot freeze the shared ranged order. If the majority falls outside
  // the leash, the anchor still waits so the cohort does not dissolve.
  if (leashError > leash || speed <= 0) return maximumError;
  const dx = state.routeWaypoint.x - state.anchor.x;
  const dy = state.routeWaypoint.y - state.anchor.y;
  const distance = Math.hypot(dx, dy);
  if (distance <= 1e-12) return maximumError;
  const step = Math.min(distance, speed / TICKS_PER_SECOND);
  state.anchor.x += (dx / distance) * step;
  state.anchor.y += (dy / distance) * step;
  state.totalAnchorDistance += step;
  state.lastAnchorMoveTick = tick;
  return maximumError;
}


function destinationsFor(state, units) {
  const destinations = new Map();
  if (state.variant === "cohesive") {
    if (state.phase === "awaiting-first-order") {
      for (const unit of units) {
        destinations.set(unit.referenceId, { x: unit.x, y: unit.y });
      }
      return destinations;
    }
    for (const unit of units) {
      const slot = state.slots.get(unit.referenceId) ?? { x: 0, y: 0 };
      destinations.set(unit.referenceId, {
        x: state.anchor.x + slot.x,
        y: state.anchor.y + slot.y,
      });
    }
  } else {
    for (const unit of units) {
      destinations.set(unit.referenceId, unit.moveOrder
        ? { x: unit.moveOrder.x, y: unit.moveOrder.y }
        : { x: unit.x, y: unit.y });
    }
  }
  return destinations;
}


function buildDiagnostics(state, units, blockedCount = 0) {
  const own = centroid(units);
  const cohesionRadius = units.reduce((maximum, unit) => Math.max(
    maximum, Math.hypot(unit.x - own.x, unit.y - own.y),
  ), 0);
  const maxSlotError = units.reduce((maximum, unit) => {
    const goal = state.destinations.get(unit.referenceId);
    return goal ? Math.max(maximum, Math.hypot(unit.x - goal.x, unit.y - goal.y)) : maximum;
  }, 0);
  return Object.freeze({
    variant: state.variant,
    phase: state.phase,
    aiWaypoint: Object.freeze({ ...state.aiWaypoint }),
    anchor: Object.freeze({ ...state.anchor }),
    routeWaypoint: Object.freeze({ ...state.routeWaypoint }),
    firstFormationTarget: state.firstFormationTarget === null
      ? null
      : Object.freeze({ ...state.firstFormationTarget }),
    unitDestinations: Object.freeze([...state.destinations.entries()].map(
      ([referenceId, point]) => Object.freeze({ referenceId, x: point.x, y: point.y }),
    )),
    centroid: Object.freeze(own),
    cohesionRadius,
    maxSlotError,
    blockedCount,
    replans: state.replans,
    stalledTicks: state.lastTick - state.lastAnchorMoveTick,
    totalAnchorDistance: state.totalAnchorDistance,
  });
}


export function createSoloNavigationState(variant, units, map, formationProfile = {}) {
  requireSoloNavigationVariant(variant);
  const own = centroid(units);
  const anchor = { ...own };
  const slots = assignStableSlots(units, formationProfile);
  const routeBounds = centralObstacleEnvelope(
    map,
    slots,
    maximumCollisionRadius(units),
  );
  const state = {
    variant,
    phase: variant === "cohesive" ? "awaiting-first-order" : "direct",
    anchor,
    aiWaypoint: { ...own },
    initialAiWaypoint: { ...own },
    firstFormationTarget: null,
    routeWaypoint: { ...anchor },
    nominalRing: nominalRing(map),
    routeBounds,
    routeArc: ringArc(routeBounds, anchor),
    targetRouteArc: null,
    slots,
    destinations: new Map(),
    replans: 0,
    lastStallReplanTick: -STALL_REPLAN_TICKS,
    lastAnchorMoveTick: 0,
    lastTick: 0,
    totalAnchorDistance: 0,
    blockedReferenceIds: new Set(),
    diagnostics: null,
  };
  state.destinations = destinationsFor(state, units);
  state.diagnostics = buildDiagnostics(state, units);
  return state;
}


export function planSoloNavigation(state, units, map, tick) {
  state.lastTick = tick;
  state.aiWaypoint = orderCentroid(units, state.aiWaypoint);
  if (state.variant === "cohesive") {
    if (state.phase === "awaiting-first-order"
        && Math.hypot(
          state.aiWaypoint.x - state.initialAiWaypoint.x,
          state.aiWaypoint.y - state.initialAiWaypoint.y,
        ) > FIRST_ORDER_DELTA_TILES) {
      // The opening formation belongs to the first real AI right-click, not
      // to an invented staging point near spawn. Project that order onto the
      // body-aware obstacle envelope so every slot has a reachable, legal
      // destination; units then form while travelling there. Only after the
      // last stragglers enter the leash does the common anchor begin its lap.
      // The first target is the nearest body-safe point to the literal AI
      // order. Later orders use perimeter-progress mapping so their arc never
      // regresses, but applying that proportional remap here would rotate the
      // very first formation away from the right-click the user can see.
      state.routeArc = ringArc(state.routeBounds, state.aiWaypoint);
      state.targetRouteArc = state.routeArc;
      state.firstFormationTarget = ringPoint(state.routeBounds, state.routeArc);
      state.anchor = { ...state.firstFormationTarget };
      state.routeWaypoint = { ...state.firstFormationTarget };
      state.phase = "forming-first-order";
      state.lastAnchorMoveTick = tick;
    }
    if (state.phase !== "awaiting-first-order") routeAnchor(state, units, map, tick);
  }
  else state.anchor = centroid(units);
  if (state.variant !== "cohesive") state.routeWaypoint = { ...state.aiWaypoint };
  state.destinations = destinationsFor(state, units);
  return state.destinations;
}


export function finishSoloNavigationTick(state, units, blockedIds) {
  state.blockedReferenceIds = new Set(blockedIds ?? []);
  state.diagnostics = buildDiagnostics(state, units, blockedIds?.size ?? 0);
  return state.diagnostics;
}


export function soloNavigationSnapshot(state) {
  return state?.diagnostics ?? null;
}
