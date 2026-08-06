// AI-player order layer, reverse-engineered from the 92-fight golden set.
//
// Every non-human AoE2 player has an AI issuing unit orders even with no
// scripted AI file, and the tapes show the melee being steered by it: 859
// `Command.AiOrder` records (orderType 700, immediate) whose loc sits exactly
// on a designated enemy unit 99% of the time, applied by the named units
// within 60 ms in 81% of cases. Unit-level AI is lock-until-death; the AI
// player is the only source of mid-fight target changes. Full derivation:
// docs/RETARGETING_INVESTIGATION.md sections 6-7.
//
// Measured policy implemented here:
//   * opening sweep starts at median 2.72 s; own units in DESCENDING reference
//     id; units already engaged are skipped (13% of recipients were attacking
//     vs 35% of the roster);
//   * early orders group 2-4 adjacent-id units and designate ONE enemy for the
//     group (the concentration mechanism); later orders are singles;
//   * each sweep order designates a DISTINCT enemy — greedy
//     nearest-unassigned, the best resolved approximation (28.8% rank-1
//     against an 18.1% unconditioned baseline);
//   * one order per ~0.2 s per side during the sweep;
//   * after the sweep, units idle for ~1 s are re-ordered (recipients of
//     mid-fight orders were idle 26.7% of the preceding second vs 7.1% for
//     other allies).
//
// Orders apply instantly: pursuit target set, engagement cleared. Gated by the
// experiment harness (AOE2X_EXP_ORDERS=1) until validated.

import { TICKS_PER_SECOND } from "../simulation-clock.js";
import { calculateDamage } from "./attacks.js";

export const ORDERS_ENABLED = process.env.AOE2X_EXP_ORDERS === "1";
// AOE2X_EXP_NO_RESCUE=1 disables the mid-fight idle rescue (probe flag: the
// tape issues ~1 late order per fight where the rescue loop issues dozens).
const RESCUE_DISABLED = process.env.AOE2X_EXP_NO_RESCUE === "1";

const SWEEP_START_TICK = Math.round(2.72 * TICKS_PER_SECOND);
const SWEEP_ORDER_INTERVAL = Math.round(0.2 * TICKS_PER_SECOND);
const IDLE_RESCUE_TICKS = Math.round(1.0 * TICKS_PER_SECOND);
// Mid-fight orders are sparse in the tape: the re-order sequences run at
// roughly one order per 1.2-1.5 s per side (20v18 P3: 8.4, 9.1, 10.8, 11.4,
// 11.6, 13.0 ...). Without this cap the rescue recycles every idle unit
// within a second and the attacking share overshoots the tape again.
const MID_ORDER_INTERVAL = Math.round(1.2 * TICKS_PER_SECOND);
const GROUP_ADJACENCY_TILES = 1.5;
const MAX_GROUP = 4;


export function createOrderState(units) {
  const owners = [...new Set(units.map(({ owner }) => owner))].sort((a, b) => a - b);
  return {
    perOwner: new Map(owners.map((owner) => [owner, {
      swept: new Set(),        // reference ids already ordered in the sweep
      designated: new Set(),   // enemy ids already designated this sweep
      nextOrderTick: SWEEP_START_TICK,
      sweepDone: false,
      nextMidOrderTick: 0,
    }])),
    idleSince: new Map(),      // reference id -> tick idling began
    // The sweep designation is computed against positions at sweep START --
    // measured as the better predictor of the tape's designations (rank<=2
    // 54.7% with start positions vs 41.9% at order time): the AI plans once
    // and the world moves while it issues.
    sweepPositions: null,      // reference id -> {x, y} frozen at first order
  };
}


function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}


function liveUnits(units, owner, same) {
  return units.filter((unit) => unit.alive && ((unit.owner === owner) === same));
}


// Nearest designation -- used by the mid-fight idle rescue, where the tape
// does not resolve the rule beyond "a live enemy".
function designate(recipient, enemies, designated) {
  const fresh = enemies.filter(({ referenceId }) => !designated.has(referenceId));
  const pool = fresh.length > 0 ? fresh : enemies;
  let best = null;
  let bestDistance = Infinity;
  for (const enemy of pool) {
    const gap = distance(recipient, enemy);
    if (gap < bestDistance || (gap === bestDistance && enemy.referenceId < best.referenceId)) {
      best = enemy;
      bestDistance = gap;
    }
  }
  return best;
}


// Sweep designation walks the ENEMY roster in ascending reference id, skipping
// enemies already designated -- the mirror of the descending-id recipient
// sweep, and the best single predictor of the tape's designations: rank-1 by
// id-ascending explains 37.8% of the 645 sweep orders with a steeply decaying
// tail (13.3% rank 2, 9.0% rank 3), against 28.8% for nearest-to-recipient.
// Geometry-blind id order is also what produces the tape's long cross-melee
// walks: median recipient-to-designation distance is 4.00 tiles where the
// nearest unassigned enemy sits at 3.00.
function designateSweep(enemies, designated) {
  const fresh = enemies.filter(({ referenceId }) => !designated.has(referenceId));
  const pool = fresh.length > 0 ? fresh : enemies;
  return pool.reduce((lowest, enemy) => (
    lowest === null || enemy.referenceId < lowest.referenceId ? enemy : lowest
  ), null);
}


function applyOrder(unit, target, tick, events, makeEvent) {
  unit.pursuitTargetId = target.referenceId;
  unit.avoidance = null;
  // Orders are immediate: an engaged unit abandons its current engagement and
  // walks (the tape shows named units switching mid-reload within 60 ms). An
  // unreleased windup is NOT preserved; a released swing has already dealt its
  // damage in this engine's model.
  if (unit.engagedTargetId !== null && unit.engagedTargetId !== target.referenceId) {
    unit.engagedTargetId = null;
  }
  if (unit.action === "attacking" && unit.attackTargetId !== target.referenceId) {
    unit.attackTargetId = null;
    unit.actionTimers.windup = 0;
    unit.actionTimers.swing = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
  }
  events.push(makeEvent(tick, "ai-order", unit.referenceId, target.referenceId));
}


function sweepOrder(state, units, owner, tick, events, makeEvent) {
  const side = state.perOwner.get(owner);
  if (!side || side.sweepDone || tick < side.nextOrderTick) return;
  if (state.sweepPositions === null) {
    state.sweepPositions = new Map(units.filter(({ alive }) => alive)
      .map((unit) => [unit.referenceId, { x: unit.x, y: unit.y }]));
  }
  const mine = liveUnits(units, owner, true)
    .filter((unit) => !side.swept.has(unit.referenceId))
    .sort((a, b) => b.referenceId - a.referenceId);
  const enemies = liveUnits(units, owner, false);
  if (enemies.length === 0 || mine.length === 0) {
    side.sweepDone = true;
    return;
  }
  // Skip units already fighting -- the sweep orders the ones not yet engaged.
  const recipient = mine.find((unit) => unit.action !== "attacking" && unit.engagedTargetId === null);
  if (!recipient) {
    side.sweepDone = true;
    return;
  }
  // Id-order designation is geometry-blind, so the frozen sweep-start
  // positions are no longer consulted here; they remain recorded for tooling.
  const target = designateSweep(enemies, side.designated);
  if (!target) return;
  // Group: unordered allies adjacent to the recipient (the tape groups 2-4
  // consecutive-id units, which spawn adjacent), all onto the SAME enemy.
  const group = [recipient];
  for (const ally of mine) {
    if (group.length >= MAX_GROUP) break;
    if (ally.referenceId === recipient.referenceId) continue;
    if (ally.action === "attacking" || ally.engagedTargetId !== null) continue;
    if (distance(ally, recipient) <= GROUP_ADJACENCY_TILES) group.push(ally);
  }
  for (const unit of group) {
    side.swept.add(unit.referenceId);
    applyOrder(unit, target, tick, events, makeEvent);
  }
  side.designated.add(target.referenceId);
  side.nextOrderTick = tick + SWEEP_ORDER_INTERVAL;
}


function idleRescue(state, units, tick, events, makeEvent) {
  for (const unit of units) {
    if (!unit.alive) {
      state.idleSince.delete(unit.referenceId);
      continue;
    }
    // Idle = blocked mid-walk, OR standing with no pursuit at all. The second
    // arm is what un-sticks ranged endgames: survivors can end up beyond
    // line of sight (LOS 10 vs a 40-unit spawn footprint), acquire nothing,
    // and stand blind — the tape AI orders them across the map anyway (its
    // designations are roster-wide, never LOS-gated). Pre-acquisition units
    // are excluded: their reaction lag has not run yet.
    const idle = unit.action !== "attacking"
      && unit.engagedTargetId === null
      && (unit.experimentBlocked === true
        || (unit.pursuitTargetId === null && unit.actionTimers.acquire === 0));
    if (!idle) {
      state.idleSince.delete(unit.referenceId);
      continue;
    }
    if (!state.idleSince.has(unit.referenceId)) {
      state.idleSince.set(unit.referenceId, tick);
      continue;
    }
    if (tick - state.idleSince.get(unit.referenceId) < IDLE_RESCUE_TICKS) continue;
    const side = state.perOwner.get(unit.owner);
    if (side && tick < side.nextMidOrderTick) continue;
    const enemies = liveUnits(units, unit.owner, false);
    if (enemies.length === 0) continue;
    // Re-designate: nearest enemy NOT already pursued, else nearest. The tape
    // does not resolve the mid-fight designation rule beyond "a live enemy";
    // avoiding the unit's own stuck target is the minimum that unsticks it.
    const pool = enemies.filter(({ referenceId }) => referenceId !== unit.pursuitTargetId);
    const target = designate(unit, pool.length ? pool : enemies, new Set());
    if (!target) continue;
    applyOrder(unit, target, tick, events, makeEvent);
    state.idleSince.delete(unit.referenceId);
    if (side) side.nextMidOrderTick = tick + MID_ORDER_INTERVAL;
  }
}


// Kiting controller, measured on the aoe2_golden_kiting_* archives (25
// arbalester-vs-champion fights; command streams decoded in full).
//
// The kited side is driven by a scripted shoot-and-scoot cycle, NOT unit AI:
//   * setup: a stop + stand-ground stance at 0.2 s — the group holds fire
//     and position until the first beat (no champion hp drop precedes the
//     first attack order in any of the 25 fights);
//   * ATTACK order(s) every 2.00 s (p10 1.99 / p90 2.01) from ~2.0 s: a
//     damage-bookkeeping assignment. Targets designated last beat and still
//     alive keep shooters first (in last beat's order); fresh targets are
//     picked nearest the group centroid (rank-1 in 352/406 fresh
//     designations). Each target gets floor(hp / per-shot damage) + 1
//     shooters — exactly enough to kill plus one insurance shot (per-shot
//     damage is 5.0 on all 3270 recorded champion hp-drop quanta, and the
//     n-vs-hp p10 column reproduces hp/5 + 1 at every n) — with the
//     remainder spilling to the next target, and any leftover piling onto
//     the last target (the tape's 15+5-on-one-champion endgame beats).
//     WHICH kiters go to which target is geometrically arbitrary in the tape
//     (nearest-own-target agreement ~50%, chance level), so the id-ordered
//     roster is sliced in assignment order.
//   * MOVE order exactly 0.67 s after each beat (p10 0.66 / p90 0.68), plus
//     one pre-fight move at ~1.3 s: a single shared waypoint + line
//     formation. All 357 recorded waypoints sit on the perimeter lattice of
//     the square ring centered on the map with half-size 3.0 and step 1.5
//     (a 16-tile map gives {5, 6.5, 8, 9.5, 11} on both axes), and every one
//     of the 25 fights walks the ring in one consistent rotational
//     direction, advancing 0-2 lattice steps per beat. Realized waypoint
//     leads over the group's own ring projection sit at p25 3.07 / p50 3.96
//     / p75 4.6 — reproduced by snapping (projection + 4.0) to the lattice
//     and never regressing. The line formation is replicated by translating
//     every unit by the shared centroid->waypoint vector (formFormation 2).
//   * kiters do not auto-fire: every one of the 3270 champion hp drops lands
//     0.38-1.5 s after a beat, none between — one shot per kiter per order.
//
// The melee side receives ONE wave of ai-orders at ~0.6 s (orderType 700,
// squads pointed at distinct spread-out enemy positions) and then fights on
// unit AI alone:
//   * the wave is modelled as champion i -> kiter (i mod nKiters), both
//     id-ordered — a deterministic spread;
//   * pursuit is sticky until the target dies: the pursued arb ranks OUTSIDE
//     the 5 nearest more often than not (7170 of 17884 heading samples are
//     rank 6+) with pursuit distances to 13 tiles, far beyond the 5-tile
//     line of sight, and champions idle >=1 s only 233 times across 25
//     fights — so a dead target is replaced by the NEAREST live kiter
//     immediately and LOS-blind;
//   * chasers do NOT opportunistically attack enemies they brush past — see
//     the kited-world engagement discipline in world.updateEngagements.
export const KITE_BEAT_TICKS = Math.round(2.0 * TICKS_PER_SECOND);
export const KITE_MOVE_OFFSET_TICKS = Math.round((2 / 3) * TICKS_PER_SECOND);
const KITE_FIRST_MOVE_TICK = Math.round((4 / 3) * TICKS_PER_SECOND);
const KITE_MELEE_ORDER_TICK = Math.round(0.6 * TICKS_PER_SECOND);
const KITE_RING_HALF_TILES = 3.0;
const KITE_RING_STEP_TILES = 1.5;
const KITE_WAYPOINT_LEAD_TILES = 4.0;
const KITE_MAP_MARGIN = 1.5;


export function createKiteState(kiteOwner) {
  return {
    owner: kiteOwner,
    nextBeat: KITE_BEAT_TICKS,
    meleeAssigned: false,
    meleeActive: null,      // ids of melee units that ever received an order
    lastTargetIds: [],
    ringDirection: 0,       // resolved once, at the first move order
    lastWaypointArc: null,
  };
}


function centroid(list) {
  const x = list.reduce((s, u) => s + u.x, 0) / list.length;
  const y = list.reduce((s, u) => s + u.y, 0) / list.length;
  return { x, y };
}


function ringBounds(map) {
  return {
    loX: map.width / 2 - KITE_RING_HALF_TILES,
    hiX: map.width / 2 + KITE_RING_HALF_TILES,
    loY: map.height / 2 - KITE_RING_HALF_TILES,
    hiY: map.height / 2 + KITE_RING_HALF_TILES,
  };
}


function ringPerimeter(bounds) {
  return 2 * ((bounds.hiX - bounds.loX) + (bounds.hiY - bounds.loY));
}


// Arc coordinate (0..perimeter) of the ring point nearest (x, y):
// bottom edge left->right, then right edge, top edge right->left, left edge.
function ringArc(bounds, x, y) {
  const width = bounds.hiX - bounds.loX;
  const height = bounds.hiY - bounds.loY;
  const cx = Math.min(Math.max(x, bounds.loX), bounds.hiX);
  const cy = Math.min(Math.max(y, bounds.loY), bounds.hiY);
  const sides = [
    [Math.abs(y - bounds.loY), cx - bounds.loX],
    [Math.abs(x - bounds.hiX), width + (cy - bounds.loY)],
    [Math.abs(y - bounds.hiY), width + height + (bounds.hiX - cx)],
    [Math.abs(x - bounds.loX), 2 * width + height + (bounds.hiY - cy)],
  ];
  let best = sides[0];
  for (const side of sides) {
    if (side[0] < best[0]) best = side;
  }
  const perimeter = ringPerimeter(bounds);
  return ((best[1] % perimeter) + perimeter) % perimeter;
}


function ringPoint(bounds, arc) {
  const width = bounds.hiX - bounds.loX;
  const height = bounds.hiY - bounds.loY;
  const perimeter = ringPerimeter(bounds);
  let a = ((arc % perimeter) + perimeter) % perimeter;
  if (a < width) return { x: bounds.loX + a, y: bounds.loY };
  a -= width;
  if (a < height) return { x: bounds.hiX, y: bounds.loY + a };
  a -= height;
  if (a < width) return { x: bounds.hiX - a, y: bounds.hiY };
  a -= width;
  return { x: bounds.loX, y: bounds.hiY - a };
}


function signedArcDelta(a, b, perimeter) {
  return ((((a - b) % perimeter) + perimeter + perimeter / 2) % perimeter)
    - perimeter / 2;
}


function kiteAttackBeat(state, kiters, enemies, tick, events, makeEvent) {
  const roster = [...kiters].sort((a, b) => a.referenceId - b.referenceId);
  const own = centroid(roster);
  // Assignment order: carried targets (previous beat's order) first, then
  // fresh targets nearest the group centroid.
  const remaining = new Map(enemies.map((enemy) => [enemy.referenceId, enemy]));
  const ordered = [];
  for (const id of state.lastTargetIds) {
    const carried = remaining.get(id);
    if (carried) {
      ordered.push(carried);
      remaining.delete(id);
    }
  }
  const fresh = [...remaining.values()].sort((a, b) => {
    const ga = Math.hypot(a.x - own.x, a.y - own.y);
    const gb = Math.hypot(b.x - own.x, b.y - own.y);
    return ga !== gb ? ga - gb : a.referenceId - b.referenceId;
  });
  ordered.push(...fresh);

  const assigned = [];
  let lastTarget = null;
  let cursor = 0;
  for (const target of ordered) {
    if (cursor >= roster.length) break;
    const perShot = Math.max(1, calculateDamage(roster[cursor], target));
    const wanted = Math.floor(target.hp / perShot) + 1;
    const count = Math.min(roster.length - cursor, wanted);
    for (const unit of roster.slice(cursor, cursor + count)) {
      delete unit.moveOrder;
      applyOrder(unit, target, tick, events, makeEvent);
    }
    assigned.push(target.referenceId);
    lastTarget = target;
    cursor += count;
  }
  // Leftover shooters pile onto the last designated target.
  if (lastTarget !== null) {
    for (const unit of roster.slice(cursor)) {
      delete unit.moveOrder;
      applyOrder(unit, lastTarget, tick, events, makeEvent);
    }
  }
  state.lastTargetIds = assigned;
}


function kiteMoveOrder(state, kiters, enemies, map, tick, events, makeEvent) {
  const bounds = ringBounds(map);
  const perimeter = ringPerimeter(bounds);
  const own = centroid(kiters);
  const foe = centroid(enemies);
  const arc = ringArc(bounds, own.x, own.y);
  if (state.ringDirection === 0) {
    // One-time direction choice: whichever way's first waypoint ends farther
    // from the chasing side. Every recorded fight runs a single consistent
    // direction picked at the start.
    const forward = ringPoint(bounds, arc + KITE_WAYPOINT_LEAD_TILES);
    const backward = ringPoint(bounds, arc - KITE_WAYPOINT_LEAD_TILES);
    const forwardAway = Math.hypot(forward.x - foe.x, forward.y - foe.y);
    const backwardAway = Math.hypot(backward.x - foe.x, backward.y - foe.y);
    state.ringDirection = forwardAway >= backwardAway ? 1 : -1;
  }
  let snapped = Math.round(
    (arc + state.ringDirection * KITE_WAYPOINT_LEAD_TILES) / KITE_RING_STEP_TILES,
  ) * KITE_RING_STEP_TILES;
  if (state.lastWaypointArc !== null
      && signedArcDelta(snapped, state.lastWaypointArc, perimeter)
        * state.ringDirection < 0) {
    snapped = state.lastWaypointArc;
  }
  state.lastWaypointArc = snapped;
  const waypoint = ringPoint(bounds, snapped);
  // Formation slots (formFormation 2 in the tape): the recorded group
  // converges into a compact grid — 20 units hold ~2.0 x 2.3 tiles with
  // nearest-neighbor spacing p50 0.29-0.43 — and REFORMS every cycle:
  // arrived units stop while stragglers keep walking (tape arb median
  // displacement 0.40 tiles/s against a 0.64 duty-cycle ceiling). A shared
  // per-unit translate cannot reform (laggards stay laggards and get picked
  // off), so each unit is ordered to its own absolute slot in a grid
  // centered on the waypoint: ~sqrt(n) columns across the travel
  // perpendicular, 0.5-tile spacing (collision diameter 0.4 + margin),
  // ranks trailing the waypoint. Units map to slots in matching (perp,
  // along) sort order so the formation never crosses itself.
  let tx = waypoint.x - own.x;
  let ty = waypoint.y - own.y;
  const norm = Math.hypot(tx, ty);
  if (norm > 1e-9) {
    tx /= norm;
    ty /= norm;
  } else {
    const ahead = ringPoint(bounds, snapped + state.ringDirection * 0.5);
    const tangent = Math.hypot(ahead.x - waypoint.x, ahead.y - waypoint.y);
    tx = tangent > 1e-9 ? (ahead.x - waypoint.x) / tangent : 1;
    ty = tangent > 1e-9 ? (ahead.y - waypoint.y) / tangent : 0;
  }
  const px = -ty;
  const py = tx;
  const count = kiters.length;
  const columns = Math.max(1, Math.ceil(Math.sqrt(count)));
  const spacing = 0.5;
  const slots = [];
  for (let index = 0; index < count; index += 1) {
    const column = index % columns;
    const row = Math.floor(index / columns);
    slots.push({
      perp: (column - (columns - 1) / 2) * spacing,
      along: -row * spacing,
    });
  }
  slots.sort((a, b) => (a.perp !== b.perp ? a.perp - b.perp : a.along - b.along));
  const orderedUnits = [...kiters].map((unit) => ({
    unit,
    perp: (unit.x - own.x) * px + (unit.y - own.y) * py,
    along: (unit.x - own.x) * tx + (unit.y - own.y) * ty,
  })).sort((a, b) => (
    a.perp !== b.perp ? a.perp - b.perp
      : (a.along !== b.along ? a.along - b.along
        : a.unit.referenceId - b.unit.referenceId)));
  const clampX = (value) => Math.min(map.width - KITE_MAP_MARGIN,
    Math.max(KITE_MAP_MARGIN, value));
  const clampY = (value) => Math.min(map.height - KITE_MAP_MARGIN,
    Math.max(KITE_MAP_MARGIN, value));
  orderedUnits.forEach(({ unit }, index) => {
    const slot = slots[index];
    unit.moveOrder = Object.freeze({
      x: clampX(waypoint.x + px * slot.perp + tx * slot.along),
      y: clampY(waypoint.y + py * slot.perp + ty * slot.along),
    });
    unit.engagedTargetId = null;
    // Cancel only an unreleased swing (windup still pending); a released
    // swing has already dealt its damage in this engine's model.
    if (unit.action === "attacking" && unit.actionTimers.windup > 0) {
      unit.attackTargetId = null;
      delete unit.attackKind;
      unit.actionTimers.windup = 0;
      unit.actionTimers.swing = 0;
      unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
    }
    events.push(makeEvent(tick, "kite-move", unit.referenceId, null, {
      x: unit.moveOrder.x,
      y: unit.moveOrder.y,
    }));
  });
}


export function issueKiteOrders(state, units, map, tick, events, makeEvent) {
  if (!state) return;
  const kiters = units.filter((unit) => unit.alive && unit.owner === state.owner);
  const enemies = units.filter((unit) => unit.alive && unit.owner !== state.owner);
  if (kiters.length === 0 || enemies.length === 0) return;

  // Pre-fight hold (the tape's stop + stand-ground at 0.2 s): anchor every
  // kiter to its spawn until the first move order so nobody drifts toward an
  // acquired target or fires before the first beat.
  if (tick === 1) {
    for (const unit of kiters) {
      unit.moveOrder = Object.freeze({ x: unit.x, y: unit.y });
    }
  }

  // Melee-side order wave at ~0.6 s. Coverage is measured and EXACT across
  // the four multi-champion fights: the wave orders all but the FOUR
  // lowest-id units (10 champions -> 6 ordered, 15 -> 11, 20 -> 16, the
  // unordered always being the lowest 4 ids), while a side of <= 5 gets one
  // platoon order covering everyone (10v5: a single recipient-only aiOrder,
  // all 5 move by 2.2 s). Unordered units are spawn pickets: they stand
  // until an enemy walks into their line of sight (engine acquisition), which
  // is what collapses the recorded 5v10 — two pickets first move at 15.0 s
  // and 19.1 s, exactly when the kiting lap reaches their corner.
  // Ordered chasers whose target has died re-designate the nearest live
  // kiter immediately and LOS-blind (chasers idle >= 1 s only 233 short
  // times across 25 fights).
  if (!state.meleeAssigned) {
    if (tick === KITE_MELEE_ORDER_TICK) {
      const melee = [...enemies].sort((a, b) => a.referenceId - b.referenceId);
      const wave = melee.length > 5 ? melee.slice(4) : melee;
      const spread = [...kiters].sort((a, b) => a.referenceId - b.referenceId);
      wave.forEach((unit, index) => {
        applyOrder(unit, spread[index % spread.length], tick, events, makeEvent);
      });
      state.meleeActive = new Set(wave.map(({ referenceId }) => referenceId));
      state.meleeAssigned = true;
    }
  } else {
    for (const unit of enemies) {
      if (unit.pursuitTargetId !== null && unit.pursuitTargetId !== undefined) {
        // A picket that acquired through line of sight joins the active set
        // and re-designates like any chaser from then on.
        state.meleeActive.add(unit.referenceId);
        continue;
      }
      if (!state.meleeActive.has(unit.referenceId)) continue;
      const target = designate(unit, kiters, new Set());
      if (target) applyOrder(unit, target, tick, events, makeEvent);
    }
  }

  if (tick === state.nextBeat) {
    kiteAttackBeat(state, kiters, enemies, tick, events, makeEvent);
    state.nextBeat = tick + KITE_BEAT_TICKS;
    return;
  }
  const moveTick = state.nextBeat - KITE_BEAT_TICKS + KITE_MOVE_OFFSET_TICKS;
  if (tick === KITE_FIRST_MOVE_TICK
      || (tick === moveTick && tick > KITE_BEAT_TICKS)) {
    kiteMoveOrder(state, kiters, enemies, map, tick, events, makeEvent);
  }
}


// Called once per tick from stepWorld, before movement. A kited side is
// driven exclusively by its beat controller: the sweep and the rescue skip
// it entirely.
export function issueOrders(state, units, tick, events, makeEvent, kiteOwner = null) {
  if (!ORDERS_ENABLED || !state) return;
  const owners = [...state.perOwner.keys()].filter((owner) => owner !== kiteOwner);
  for (const owner of owners) sweepOrder(state, units, owner, tick, events, makeEvent);
  if (RESCUE_DISABLED) return;
  const allSwept = owners.every((owner) => state.perOwner.get(owner).sweepDone);
  if (allSwept || tick > SWEEP_START_TICK + 20 * TICKS_PER_SECOND) {
    idleRescue(state, units.filter((unit) => unit.owner !== kiteOwner),
      tick, events, makeEvent);
  }
}
