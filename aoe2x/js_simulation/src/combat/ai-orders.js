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


// Called once per tick from stepWorld, before movement.
export function issueOrders(state, units, tick, events, makeEvent) {
  if (!ORDERS_ENABLED || !state) return;
  const owners = [...state.perOwner.keys()];
  for (const owner of owners) sweepOrder(state, units, owner, tick, events, makeEvent);
  if (RESCUE_DISABLED) return;
  const allSwept = owners.every((owner) => state.perOwner.get(owner).sweepDone);
  if (allSwept || tick > SWEEP_START_TICK + 20 * TICKS_PER_SECOND) {
    idleRescue(state, units, tick, events, makeEvent);
  }
}
