import { TICKS_PER_SECOND } from "../simulation-clock.js";


export const SOLO_NAVIGATION_VARIANTS = Object.freeze([
  "baseline",
  "per-unit-grid",
  "cohesive",
]);

const SLOT_SPACING_TILES = 0.48;
const GROUP_CLEARANCE_RADIUS_TILES = 1.18;
const ANCHOR_LEASH_TILES = 0.62;
const ANCHOR_REACHED_TILES = 0.18;
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


function compactSlots(count) {
  const width = Math.ceil(Math.sqrt(count));
  const height = Math.ceil(count / width);
  const candidates = [];
  for (let row = 0; row < height; row += 1) {
    for (let column = 0; column < width; column += 1) {
      candidates.push({
        x: (column - (width - 1) / 2) * SLOT_SPACING_TILES,
        y: (row - (height - 1) / 2) * SLOT_SPACING_TILES,
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


function assignStableSlots(units) {
  const own = centroid(units);
  const ordered = [...units].sort((a, b) => (
    a.y !== b.y ? a.y - b.y : (a.x !== b.x ? a.x - b.x : a.referenceId - b.referenceId)
  ));
  const slots = compactSlots(units.length);
  return new Map(ordered.map((unit, index) => [unit.referenceId, slots[index]]));
}


function stagingAnchor(units, map) {
  const own = centroid(units);
  // The source formation begins immediately below-left of the central Arena
  // obstruction. This nearby open point lets it compact before the anchor
  // starts its lap; no unit is teleported and every walker keeps DAT speed.
  return {
    x: Math.min(map.width - 2, Math.max(2, own.x - 0.95)),
    y: Math.min(map.height - 2, Math.max(2, own.y - 0.3)),
  };
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


function centralObstacleEnvelope(map) {
  const nominal = nominalRing(map);
  const central = (map.obstacles ?? []).filter((body) => (
    body.x >= nominal.loX && body.x <= nominal.hiX
    && body.y >= nominal.loY && body.y <= nominal.hiY
  ));
  if (central.length === 0) return nominal;
  const margin = GROUP_CLEARANCE_RADIUS_TILES + 0.07;
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
  const maximumError = units.reduce((maximum, unit) => {
    const slot = state.slots.get(unit.referenceId);
    if (!slot) return maximum;
    const goal = { x: state.anchor.x + slot.x, y: state.anchor.y + slot.y };
    return Math.max(maximum, Math.hypot(unit.x - goal.x, unit.y - goal.y));
  }, 0);
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

  if (maximumError > ANCHOR_LEASH_TILES || speed <= 0) return maximumError;
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
    aiWaypoint: Object.freeze({ ...state.aiWaypoint }),
    anchor: Object.freeze({ ...state.anchor }),
    routeWaypoint: Object.freeze({ ...state.routeWaypoint }),
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


export function createSoloNavigationState(variant, units, map) {
  requireSoloNavigationVariant(variant);
  const own = centroid(units);
  const anchor = variant === "cohesive" ? stagingAnchor(units, map) : own;
  const routeBounds = centralObstacleEnvelope(map);
  const state = {
    variant,
    anchor,
    aiWaypoint: { ...own },
    routeWaypoint: { ...anchor },
    nominalRing: nominalRing(map),
    routeBounds,
    routeArc: ringArc(routeBounds, anchor),
    targetRouteArc: null,
    slots: assignStableSlots(units),
    destinations: new Map(),
    replans: 0,
    lastStallReplanTick: -STALL_REPLAN_TICKS,
    lastAnchorMoveTick: 0,
    lastTick: 0,
    totalAnchorDistance: 0,
    diagnostics: null,
  };
  state.destinations = destinationsFor(state, units);
  state.diagnostics = buildDiagnostics(state, units);
  return state;
}


export function planSoloNavigation(state, units, map, tick) {
  state.lastTick = tick;
  state.aiWaypoint = orderCentroid(units, state.aiWaypoint);
  if (state.variant === "cohesive") routeAnchor(state, units, map, tick);
  else state.anchor = centroid(units);
  if (state.variant !== "cohesive") state.routeWaypoint = { ...state.aiWaypoint };
  state.destinations = destinationsFor(state, units);
  return state.destinations;
}


export function finishSoloNavigationTick(state, units, blockedIds) {
  state.diagnostics = buildDiagnostics(state, units, blockedIds?.size ?? 0);
  return state.diagnostics;
}


export function soloNavigationSnapshot(state) {
  return state?.diagnostics ?? null;
}
