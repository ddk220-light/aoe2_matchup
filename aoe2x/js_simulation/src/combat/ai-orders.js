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
// Orders apply instantly: pursuit target set, engagement cleared.
// AOE2X_EXP_ORDERS is pinned on as the committed default (see
// ../engine-config.js); set AOE2X_EXP_ORDERS=0 to get the pre-calibration
// baseline engine back.

import { ENGINE_CONFIG } from "../engine-config.js";
import { TICKS_PER_SECOND } from "../simulation-clock.js";
import { calculateDamage } from "./attacks.js";
import { MIN_RANGE_SUPPRESSES_SHOOTER } from "./experiments.js";
import { isWithinReach } from "./targeting.js";

export const ORDERS_ENABLED = ENGINE_CONFIG.orders;
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


function applyApproachOrder(unit, waypoint, tick, events, makeEvent) {
  unit.pursuitTargetId = null;
  unit.engagedTargetId = null;
  unit.avoidance = null;
  if (unit.action === "attacking") {
    unit.attackTargetId = null;
    delete unit.attackKind;
    unit.actionTimers.windup = 0;
    unit.actionTimers.swing = 0;
    unit.action = unit.actionTimers.reload > 0 ? "reload" : "idle";
  }
  events.push(makeEvent(tick, "ai-location-order", unit.referenceId, null, {
    x: waypoint.x,
    y: waypoint.y,
  }));
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
// Pressure-split share, measured on the skirmisher and heavy-cav-archer
// archives: when even the whole roster cannot kill the first target this
// beat, a LARGE roster does not stack everyone on it — main groups run
// 14-16 of 20 and ~11 of 15 (esc/esp/hcp) with the remainder on the second
// target. Rosters of 10 or fewer stay all-on-one in every archive (kac,
// esc 10v5, hcp 10v5, the 5v10s). The hcc archive disambiguates the split
// from bookkeeping: with per-shot damage 6 its mains are exactly
// ceil(70/6)+1 = 13, not 15.
const KITE_PRESSURE_SHARE = 0.75;
const KITE_PRESSURE_MIN_ROSTER = 12;

// Script cycle profile. Every recorded archive runs the same 0.667 s order
// clock; the per-kiter cycle differs and is recorded in the truth fixture
// as `kiteProfile` (a property of the recorded scenario, like kiteOwner):
//   arbalester (kac/avp): beat 2.00 s, move +0.67 s, pre-fight move ~1.3 s;
//   elite skirm (esc/esp): beat 3.33 s (reload 3.0), moves +0.67 and
//     +2.00 s, pre-fight moves ~1.3/2.6 s;
//   heavy cav archer (hcc/hcp): first beat ~0.57 s (they open firing),
//     beat 2.00 s, finishing TOP-UP designations +0.67 s, move +1.33 s.
// The default is the arbalester profile (backwards compatible with kac, the
// one recorded kiting scenario whose fixture carries no explicit profile).
// Exported so the generated kite-profiles.js table can be pinned to it: its
// arbalester row and this must stay identical, which is what makes "that
// fixture ran on the default" a checkable claim rather than an assumption.
// Callers with a real kiter should pass its profile -- falling back to this
// runs three of the four kiters on a cadence that is not theirs.
export const DEFAULT_KITE_PROFILE = Object.freeze({
  beatTicks: KITE_BEAT_TICKS,
  firstBeatTick: KITE_BEAT_TICKS,
  moveOffsetTicks: Object.freeze([KITE_MOVE_OFFSET_TICKS]),
  topupOffsetTicks: Object.freeze([]),
  preMoveTicks: Object.freeze([KITE_FIRST_MOVE_TICK]),
});


export function createKiteState(kiteOwner, kiteProfile = null, chaseCapture = false,
  kitedEscape = false, soloMovement = false) {
  const profile = kiteProfile
    ? {
      beatTicks: kiteProfile.beatTicks,
      firstBeatTick: kiteProfile.firstBeatTick,
      moveOffsetTicks: [...kiteProfile.moveOffsetTicks],
      topupOffsetTicks: [...(kiteProfile.topupOffsetTicks ?? [])],
      preMoveTicks: [...(kiteProfile.preMoveTicks ?? [])],
      ...(kiteProfile.kitedPath === "clearance_grid" ? { kitedPath: "clearance_grid" } : {}),
      ...(kiteProfile.cohortMotion === "contact_heading"
        ? { cohortMotion: "contact_heading" }
        : {}),
      ...(Number.isFinite(kiteProfile.formationSpacingTiles)
          && kiteProfile.formationSpacingTiles > 0
        ? { formationSpacingTiles: kiteProfile.formationSpacingTiles }
        : {}),
      ...(kiteProfile.formationMotion === "translated_offsets"
        ? { formationMotion: "translated_offsets" }
        : {}),
      ...(kiteProfile.openingVolley === "close_to_fire"
        ? { openingVolley: "close_to_fire" }
        : {}),
      ...(kiteProfile.volleyPursuit === "close_to_fire"
        ? { volleyPursuit: "close_to_fire" }
        : {}),
      ...(kiteProfile.meleeWave === "half_roster"
        ? { meleeWave: "half_roster" }
        : {}),
      ...(kiteProfile.meleeWave === "location_approach"
        ? { meleeWave: "location_approach" }
        : {}),
    }
    : DEFAULT_KITE_PROFILE;
  return {
    owner: kiteOwner,
    profile,
    // Contact capture (see the block in world.updateEngagements) — a MEASURED
    // per-scenario property, like the profile: the rule itself shows in every
    // full-rate action decode, but it only stays truthful where the sim's
    // contact rate matches the tape's switch rate. Recorded ON for the
    // skirmisher and paladin chase archives; OFF where the sim still
    // manufactures contacts the tape's geometry prevents (kac, hcc).
    chaseCapture: chaseCapture === true,
    // Kited-side escape steer (see world.steerProposals) — per-scenario, like
    // chaseCapture: the caught kiter executes its scripted move THROUGH
    // attacker contact. ON where that closes the recorded matchup
    // (hcavarcher_vs_champion, the 12v21 forensics); OFF where the tape shows
    // the escape FAILING (kac 5v10's picket ambush, esc, hcp) until clearance
    // pathing can discriminate. AOE2X_EXP_STEP=kited forces it everywhere.
    kitedEscape: kitedEscape === true,
    ...(soloMovement === true ? { soloMovement: true } : {}),
    nextBeat: profile.firstBeatTick,
    lastBeatTick: null,
    meleeAssigned: false,
    meleeActive: null,      // ids of melee units that acquired a live target
    ...(profile.meleeWave === "location_approach"
      ? { meleeApproach: new Map() }
      : {}),
    lastTargetIds: [],
    // A real fight resolves direction away from its enemy. The enemy-free
    // movement viewer uses the same order engine with a fixed clockwise lap.
    ringDirection: soloMovement === true ? 1 : 0,
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
  // NOT MODELLED YET: minimum range suppresses the SHOOTER, not just the one
  // target it was aimed at. The tape's AI names every shooter here (439
  // assignments in the skirm-vs-camel fight) but only 233 arrows leave, and the
  // split is the shooter's own min_range: firers had their nearest chaser at
  // p50 2.2 tiles, holders at p50 1.0. Confirmed on esc 20v20 measured at
  // windup start (4.0% of launches begin with an enemy inside 1.0 vs 18.2% of
  // the alive population) with the arbalester column, min_range 0.0, as a
  // control that shows no depletion at all. Implementing it costs esc dearly
  // (band error 2.5 -> 13.5) because the rule's cost scales with how long a
  // chaser sits inside min_range of our shooters, and ours sit there 57.3% of
  // shooter-frames against the tape's 22.9%: blocked chasers grind at partial
  // speed instead of routing around, so the block engulfs them. Chaser
  // mobility has to come first. See docs/CAMEL_CHASER_GEOMETRY_2026-08-06.md.
  const shooters = MIN_RANGE_SUPPRESSES_SHOOTER
    ? kiters.filter((unit) => {
      const range = unit.mechanics?.ranged?.min_range_tiles ?? 0;
      if (!(range > 0)) return true;
      return !enemies.some((enemy) => Math.hypot(enemy.x - unit.x, enemy.y - unit.y) < range);
    })
    : kiters;
  const roster = [...shooters].sort((a, b) => a.referenceId - b.referenceId);
  if (roster.length === 0) return;
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

  // Only shooters that can actually deliver are assigned: 613/613 recorded
  // beat-targets land ~100% of their assigned damage, so the script never
  // spends shooters on a target beyond their reach (or inside their minimum
  // range). Without this gate a chaser grinding a straggler behind the
  // group soaks the whole volley out of range and survives 20-second
  // killing sprees no tape shows.
  const assigned = [];
  const directOpening = state.lastBeatTick === null
    && (state.profile.openingVolley === "close_to_fire"
      || state.profile.volleyPursuit === "close_to_fire");
  const closingBeat = directOpening || state.profile.volleyPursuit === "close_to_fire";
  let lastTarget = null;
  let pool = roster;
  let firstAssignment = true;
  let pressure = false;
  for (const target of ordered) {
    if (pool.length === 0) break;
    const eligible = [];
    const rest = [];
    for (const unit of pool) {
      const withinSight = Math.hypot(target.x - unit.x, target.y - unit.y)
        <= (unit.mechanics?.line_of_sight_tiles ?? 0) + 1e-12;
      (isWithinReach(unit, target) || (closingBeat && withinSight)
        ? eligible
        : rest).push(unit);
    }
    if (eligible.length === 0) continue;
    const perShot = Math.max(1, calculateDamage(eligible[0], target));
    let wanted = Math.floor(target.hp / perShot) + 1;
    if (firstAssignment) {
      // Pressure split (see KITE_PRESSURE_SHARE): when even the full pool
      // cannot kill the first shootable target, a large pool splits ~75/25
      // across the first two targets instead of stacking.
      pressure = wanted > pool.length
        && pool.length >= KITE_PRESSURE_MIN_ROSTER
        && ordered.length >= 2;
      firstAssignment = false;
      if (pressure) wanted = Math.ceil(pool.length * KITE_PRESSURE_SHARE);
    } else if (pressure) {
      wanted = pool.length;
    }
    const count = Math.min(eligible.length, wanted);
    for (const unit of eligible.slice(0, count)) {
      delete unit.moveOrder;
      if (directOpening) unit.actionTimers.acquire = 0;
      applyOrder(unit, target, tick, events, makeEvent);
    }
    assigned.push(target.referenceId);
    lastTarget = target;
    pool = eligible.slice(count).concat(rest);
  }
  // Leftover shooters pile onto the last designated target when they can
  // reach it; the rest keep their move order and stay with the formation.
  if (lastTarget !== null) {
    for (const unit of pool) {
      if (!isWithinReach(unit, lastTarget)) continue;
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
  const arc = ringArc(bounds, own.x, own.y);
  if (state.ringDirection === 0) {
    const foe = centroid(enemies);
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
  const spacing = state.profile.formationSpacingTiles ?? 0.5;
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
    const translatedOffsets = state.profile.formationMotion === "translated_offsets";
    unit.moveOrder = Object.freeze({
      x: clampX(translatedOffsets
        ? unit.x + waypoint.x - own.x
        : waypoint.x + px * slot.perp + tx * slot.along),
      y: clampY(translatedOffsets
        ? unit.y + waypoint.y - own.y
        : waypoint.y + py * slot.perp + ty * slot.along),
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
  const soloMovement = state.soloMovement === true && enemies.length === 0;
  if (kiters.length === 0 || (enemies.length === 0 && !soloMovement)) return;

  // Pre-fight hold (the tape's stop + stand-ground at 0.2 s): anchor every
  // kiter to its spawn until the first move order so nobody drifts toward an
  // acquired target or fires before the first beat.
  if (tick === 1) {
    for (const unit of kiters) {
      unit.moveOrder = Object.freeze({ x: unit.x, y: unit.y });
    }
  }

  // Enemy-free movement inspection: preserve the kiter's tape-derived order
  // clock and formation movement, but skip attack and melee designation. For
  // Hand Cannoneers this publishes a new movement order every 80 ticks.
  if (soloMovement) {
    const { profile } = state;
    if (tick === state.nextBeat) {
      state.lastBeatTick = tick;
      state.nextBeat = tick + profile.beatTicks;
      return;
    }
    if (state.lastBeatTick === null) {
      if (profile.preMoveTicks.includes(tick)) {
        kiteMoveOrder(state, kiters, enemies, map, tick, events, makeEvent);
      }
      return;
    }
    if (profile.moveOffsetTicks.includes(tick - state.lastBeatTick)) {
      kiteMoveOrder(state, kiters, enemies, map, tick, events, makeEvent);
    }
    return;
  }

  // Melee-side order wave at ~0.6 s. Coverage is measured and EXACT across
  // all six archives: the wave orders all but the FOUR lowest-id units
  // (10 champions -> 6 ordered, 15 -> 11, 20 -> 16, the unordered always
  // being the lowest 4 ids) — and a side of exactly 5 gets ONE aiOrder to
  // the single HIGHEST id, i.e. the same slice(4): the command streams
  // record recipient 1609, orderType 700, location = the kiter-group
  // centroid, in every 10v5 of every archive. The other four are spawn
  // pickets: they stand until an enemy walks into their line of sight
  // (engine acquisition) — the steppe 10v5 tapes show 1605/1608 frozen at
  // spawn for 20+ s while the lap stays clear (kac's pickets acquired
  // within ~2 s by spawn geometry, which is what the old covers-everyone
  // reading mistook for order coverage), and the recorded 5v10 collapses
  // when two pickets first move at 15.0 s and 19.1 s, exactly as the
  // kiting lap reaches their corner. A single-recipient wave aims at the
  // order's location — the kiter nearest the group centroid (1273 in
  // every recorded 10v5, matching designate's fresh pick); a multi-unit
  // wave keeps the measured deterministic spread. Ordered chasers whose
  // target has died re-designate the nearest live kiter immediately and
  // LOS-blind (chasers idle >= 1 s only 233 short times across 25 fights).
  if (!state.meleeAssigned) {
    if (tick === KITE_MELEE_ORDER_TICK) {
      const melee = [...enemies].sort((a, b) => a.referenceId - b.referenceId);
      const wave = melee.slice(state.profile.meleeWave === "half_roster"
        ? Math.ceil(melee.length / 2)
        : 4);
      const spread = [...kiters].sort((a, b) => a.referenceId - b.referenceId);
      if (state.profile.meleeWave === "location_approach") {
        wave.forEach((unit, index) => {
          const anchor = spread[index % spread.length];
          const waypoint = { x: anchor.x, y: anchor.y };
          state.meleeApproach.set(unit.referenceId, waypoint);
          applyApproachOrder(unit, waypoint, tick, events, makeEvent);
        });
      } else if (wave.length === 1) {
        // The recorded single order carries location = the kiter-group
        // centroid; the recipient's first pursuit is the kiter nearest it.
        const anchor = centroid(kiters);
        let target = null;
        let bestGap = Infinity;
        for (const kiter of kiters) {
          const gap = Math.hypot(kiter.x - anchor.x, kiter.y - anchor.y);
          if (gap < bestGap
            || (gap === bestGap && kiter.referenceId < target.referenceId)) {
            target = kiter;
            bestGap = gap;
          }
        }
        if (target) applyOrder(wave[0], target, tick, events, makeEvent);
      } else {
        wave.forEach((unit, index) => {
          applyOrder(unit, spread[index % spread.length], tick, events, makeEvent);
        });
      }
      state.meleeActive = new Set(state.profile.meleeWave === "location_approach"
        ? []
        : wave.map(({ referenceId }) => referenceId));
      state.meleeAssigned = true;
    }
  } else {
    for (const unit of enemies) {
      if (unit.pursuitTargetId !== null && unit.pursuitTargetId !== undefined) {
        // A picket that acquired through line of sight joins the active set
        // and re-designates like any chaser from then on.
        state.meleeApproach?.delete(unit.referenceId);
        state.meleeActive.add(unit.referenceId);
        continue;
      }
      if (state.meleeApproach?.has(unit.referenceId)) continue;
      if (!state.meleeActive.has(unit.referenceId)) continue;
      const target = designate(unit, kiters, new Set());
      if (target) applyOrder(unit, target, tick, events, makeEvent);
    }
  }

  const { profile } = state;
  if (tick === state.nextBeat) {
    kiteAttackBeat(state, kiters, enemies, tick, events, makeEvent);
    state.lastBeatTick = tick;
    state.nextBeat = tick + profile.beatTicks;
    return;
  }
  if (state.lastBeatTick === null) {
    if (profile.preMoveTicks.includes(tick)) {
      kiteMoveOrder(state, kiters, enemies, map, tick, events, makeEvent);
    }
    return;
  }
  const offset = tick - state.lastBeatTick;
  if (profile.topupOffsetTicks.includes(offset)) {
    // Finishing top-up: re-run the bookkeeping designation against current
    // hit points. Units already reloading keep their cycle; only shooters
    // that have not fired yet (still closing) change aim — the recorded
    // top-ups are 1-2 unit finishing commands.
    kiteAttackBeat(state, kiters, enemies, tick, events, makeEvent);
    return;
  }
  if (profile.moveOffsetTicks.includes(offset)) {
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
