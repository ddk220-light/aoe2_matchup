import { createWorld, runWorld } from "../../src/combat/world.js";
import {
  hasDirectMeleeApproach,
  isWithinReach,
  meleeContactCapacity,
  openingMeleeContactCapacity,
  surfaceGap,
} from "../../src/combat/targeting.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";


const ROOT = new URL("../../", import.meta.url);
const ROW_ID = "elite_boyar_vs_heavy_cav_archer";
const SEED = 20260817;
const TICKS_PER_SECOND = 60;
const PRESSURE_LIMIT = 6;
const STALL_MIN_TICKS = 30;
const ZERO_STEP = 1e-9;


function eventCause(events, actorId, targetId) {
  const matching = events.filter((entry) => (
    entry.actorId === actorId
    && (entry.targetId === targetId || entry.targetId === null || entry.targetId === undefined)
  ));
  if (matching.some(({ type }) => type === "contact-capture")) return "contact-capture";
  if (matching.some(({ type }) => type === "pursuit-acquired")) return "pursuit-acquired";
  return matching.map(({ type }) => type).join("+") || "implicit/unchanged-state";
}


function closeInterval(activeByActor, actorId, endTick, stalls) {
  const interval = activeByActor.get(actorId);
  if (!interval) return;
  activeByActor.delete(actorId);
  const durationTicks = endTick - interval.startTick + 1;
  if (durationTicks < STALL_MIN_TICKS) return;
  stalls.push({
    ...interval,
    endTick,
    durationTicks,
    durationSeconds: durationTicks / TICKS_PER_SECOND,
    blockedShare: interval.blockedTicks / durationTicks,
    gapDelta: interval.endGap - interval.startGap,
    eventCounts: Object.fromEntries([...interval.eventCounts].sort()),
  });
}


function closePressureInterval(activeByTarget, targetId, endTick, intervals) {
  const interval = activeByTarget.get(targetId);
  if (!interval) return;
  activeByTarget.delete(targetId);
  const durationTicks = endTick - interval.startTick + 1;
  intervals.push({
    ...interval,
    endTick,
    durationTicks,
    durationSeconds: durationTicks / TICKS_PER_SECOND,
  });
}


const truth = await loadPhase2Batch1Truth(ROOT);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row) throw new Error(`missing ${ROW_ID}`);
const context = await loadPhase2Batch1Context(ROOT, truth);
const scenario = scenarioFromPhase2Batch1Row({
  row,
  sampleIndex: 0,
  seed: SEED,
  context,
});
const result = runWorld(createWorld(scenario), {
  maxTicks: PHASE2_MAX_TICKS,
  retainSnapshots: true,
});

const initial = result.snapshots[0];
const boyarIds = new Set(initial.units.filter(({ owner }) => owner === 3)
  .map(({ referenceId }) => referenceId));
const hcaIds = new Set(initial.units.filter(({ owner }) => owner === 2)
  .map(({ referenceId }) => referenceId));
const maxPressureByTarget = new Map([...hcaIds].map((id) => [id, 0]));
const pressureTicksByTarget = new Map([...hcaIds].map((id) => [id, 0]));
const pressureIntervals = [];
const activePressureByTarget = new Map();
const pressureEntryCauses = new Map();
const overloadEntries = [];
const pressureTimeline = [];
const stalls = [];
const activeStallByActor = new Map();
let globalMaxPressure = 0;
let globalMaxTick = 0;
let overloadedTicks = 0;
let previousById = new Map(initial.units.map((unit) => [unit.referenceId, unit]));
let previousTargetByActor = new Map([...boyarIds].map((id) => [id, null]));

for (const snapshot of result.snapshots.slice(1)) {
  const byId = new Map(snapshot.units.map((unit) => [unit.referenceId, unit]));
  const previousPressure = new Map();
  for (const actorId of boyarIds) {
    const actor = previousById.get(actorId);
    const target = previousById.get(actor?.pursuitTargetId);
    if (!actor?.alive || !target?.alive || !hcaIds.has(target.referenceId)) continue;
    previousPressure.set(
      target.referenceId,
      (previousPressure.get(target.referenceId) ?? 0) + 1,
    );
  }
  const pressure = new Map();
  for (const actorId of boyarIds) {
    const actor = byId.get(actorId);
    const target = byId.get(actor?.pursuitTargetId);
    if (!actor?.alive || !target?.alive || !hcaIds.has(target.referenceId)) continue;
    pressure.set(target.referenceId, (pressure.get(target.referenceId) ?? 0) + 1);
  }

  const tickMax = pressure.size === 0 ? 0 : Math.max(...pressure.values());
  if (tickMax > globalMaxPressure) {
    globalMaxPressure = tickMax;
    globalMaxTick = snapshot.tick;
  }
  const overloaded = [...pressure].filter(([, count]) => count > PRESSURE_LIMIT);
  if (overloaded.length > 0) {
    overloadedTicks += 1;
    pressureTimeline.push({
      tick: snapshot.tick,
      targets: Object.fromEntries(overloaded),
    });
  }

  for (const targetId of hcaIds) {
    const count = pressure.get(targetId) ?? 0;
    maxPressureByTarget.set(targetId, Math.max(maxPressureByTarget.get(targetId), count));
    if (count > PRESSURE_LIMIT) {
      pressureTicksByTarget.set(targetId, pressureTicksByTarget.get(targetId) + 1);
      const active = activePressureByTarget.get(targetId);
      if (!active) {
        activePressureByTarget.set(targetId, {
          targetId,
          startTick: snapshot.tick,
          maxCount: count,
        });
      } else {
        active.maxCount = Math.max(active.maxCount, count);
      }
    } else {
      closePressureInterval(
        activePressureByTarget,
        targetId,
        snapshot.tick - 1,
        pressureIntervals,
      );
    }
  }

  for (const actorId of boyarIds) {
    const actor = byId.get(actorId);
    const previous = previousById.get(actorId);
    const target = byId.get(actor?.pursuitTargetId);
    const previousTargetId = previousTargetByActor.get(actorId);
    if (actor?.alive && target?.alive && hcaIds.has(target.referenceId)
        && actor.pursuitTargetId !== previousTargetId
        && (pressure.get(target.referenceId) ?? 0) > PRESSURE_LIMIT) {
      const cause = eventCause(snapshot.events, actorId, target.referenceId);
      pressureEntryCauses.set(cause, (pressureEntryCauses.get(cause) ?? 0) + 1);
      const visibleTargets = snapshot.units.filter((candidate) => (
        candidate.alive
        && hcaIds.has(candidate.referenceId)
        && Math.hypot(candidate.x - actor.x, candidate.y - actor.y)
          <= actor.mechanics.line_of_sight_tiles
      ));
      const visibleWithRoom = visibleTargets.filter((candidate) => (
        (previousPressure.get(candidate.referenceId) ?? 0)
          < openingMeleeContactCapacity(actor, candidate, snapshot.units)
      ));
      const visibleWithDirectContactRoom = visibleTargets.filter((candidate) => (
        (previousPressure.get(candidate.referenceId) ?? 0)
          < meleeContactCapacity(actor, candidate, snapshot.units)
        && hasDirectMeleeApproach(actor, candidate, snapshot.units)
      ));
      overloadEntries.push({
        tick: snapshot.tick,
        seconds: snapshot.tick / TICKS_PER_SECOND,
        actorId,
        targetId: target.referenceId,
        previousTargetId,
        previousBlocked: previous?.experimentBlocked ?? null,
        meleeCapacityTargetId: actor.meleeCapacityTargetId ?? null,
        cause,
        loadBefore: previousPressure.get(target.referenceId) ?? 0,
        loadAfter: pressure.get(target.referenceId) ?? 0,
        selectedOpeningCapacity: openingMeleeContactCapacity(actor, target, snapshot.units),
        selectedFullContactCapacity: meleeContactCapacity(actor, target, snapshot.units),
        liveHcaCount: snapshot.units.filter((candidate) => (
          candidate.alive && hcaIds.has(candidate.referenceId)
        )).length,
        visibleHcaCount: visibleTargets.length,
        visibleTargetsWithRoom: visibleWithRoom.map(({ referenceId }) => referenceId),
        visibleTargetsWithDirectContactRoom: visibleWithDirectContactRoom
          .map(({ referenceId }) => referenceId),
      });
    }
    previousTargetByActor.set(actorId, actor?.pursuitTargetId ?? null);

    const displacement = actor?.alive && previous?.alive
      ? Math.hypot(actor.x - previous.x, actor.y - previous.y)
      : Infinity;
    const stalledNow = actor?.alive
      && target?.alive
      && hcaIds.has(target.referenceId)
      && actor.action !== "attacking"
      && !isWithinReach(actor, target)
      && displacement <= ZERO_STEP;
    const active = activeStallByActor.get(actorId);
    if (!stalledNow || (active && active.targetId !== target.referenceId)) {
      closeInterval(activeStallByActor, actorId, snapshot.tick - 1, stalls);
    }
    if (!stalledNow) continue;

    const gap = surfaceGap(actor, target);
    const actorEvents = snapshot.events.filter(({ actorId: eventActor }) => (
      eventActor === actorId
    ));
    const blocked = actorEvents.some(({ type }) => type === "blocked");
    if (!activeStallByActor.has(actorId)) {
      activeStallByActor.set(actorId, {
        actorId,
        targetId: target.referenceId,
        startTick: snapshot.tick,
        startGap: gap,
        endGap: gap,
        blockedTicks: Number(blocked),
        targetPressureMax: pressure.get(target.referenceId) ?? 0,
        contactCapacityMin: meleeContactCapacity(actor, target, snapshot.units),
        eventCounts: new Map(actorEvents.map(({ type }) => [type, 1])),
        eventSamples: actorEvents.filter(({ type }) => (
          type === "blocked"
          || type === "pursuit-route-invalidated"
          || type === "pursuit-route-deferred"
        )).slice(0, 4),
      });
    } else {
      const interval = activeStallByActor.get(actorId);
      interval.endGap = gap;
      interval.blockedTicks += Number(blocked);
      interval.targetPressureMax = Math.max(
        interval.targetPressureMax,
        pressure.get(target.referenceId) ?? 0,
      );
      interval.contactCapacityMin = Math.min(
        interval.contactCapacityMin,
        meleeContactCapacity(actor, target, snapshot.units),
      );
      for (const { type } of actorEvents) {
        interval.eventCounts.set(type, (interval.eventCounts.get(type) ?? 0) + 1);
      }
      if (interval.eventSamples.length < 12) {
        interval.eventSamples.push(...actorEvents.filter(({ type }) => (
          type === "blocked"
          || type === "pursuit-route-invalidated"
          || type === "pursuit-route-deferred"
        )).slice(0, 12 - interval.eventSamples.length));
      }
    }
  }
  previousById = byId;
}

const finalTick = result.snapshots.at(-1).tick;
for (const targetId of activePressureByTarget.keys()) {
  closePressureInterval(activePressureByTarget, targetId, finalTick, pressureIntervals);
}
for (const actorId of activeStallByActor.keys()) {
  closeInterval(activeStallByActor, actorId, finalTick, stalls);
}

const winnerHp = result.world.units.filter(({ alive }) => alive)
  .reduce((sum, unit) => sum + unit.hp, 0);
const pressureRows = [...hcaIds].map((targetId) => ({
  targetId,
  maxBoyarPursuers: maxPressureByTarget.get(targetId),
  ticksAboveLimit: pressureTicksByTarget.get(targetId),
  secondsAboveLimit: pressureTicksByTarget.get(targetId) / TICKS_PER_SECOND,
})).filter(({ maxBoyarPursuers }) => maxBoyarPursuers > 0)
  .sort((left, right) => right.maxBoyarPursuers - left.maxBoyarPursuers
    || right.ticksAboveLimit - left.ticksAboveLimit);
const topStalls = stalls.sort((left, right) => right.durationTicks - left.durationTicks)
  .slice(0, 20);
const snapshotByTick = new Map(result.snapshots.map((snapshot) => [snapshot.tick, snapshot]));
const stallContexts = topStalls.map((stall) => {
  const snapshot = snapshotByTick.get(stall.startTick);
  const previous = snapshotByTick.get(stall.startTick - 1);
  const byId = new Map(snapshot.units.map((unit) => [unit.referenceId, unit]));
  const previousById = new Map(previous.units.map((unit) => [unit.referenceId, unit]));
  const actor = byId.get(stall.actorId);
  const target = byId.get(stall.targetId);
  const nearby = snapshot.units.filter((unit) => (
    unit.alive
    && unit.referenceId !== actor.referenceId
    && Math.max(Math.abs(unit.x - actor.x), Math.abs(unit.y - actor.y)) <= 1.25
  )).map((unit) => {
    const prior = previousById.get(unit.referenceId);
    return {
      referenceId: unit.referenceId,
      owner: unit.owner,
      action: unit.action,
      pursuitTargetId: unit.pursuitTargetId,
      dx: unit.x - prior.x,
      dy: unit.y - prior.y,
      offsetX: unit.x - actor.x,
      offsetY: unit.y - actor.y,
    };
  }).sort((left, right) => (
    Math.hypot(left.offsetX, left.offsetY) - Math.hypot(right.offsetX, right.offsetY)
  ));
  return {
    actor: {
      referenceId: actor.referenceId,
      x: actor.x,
      y: actor.y,
      action: actor.action,
      pursuitTargetId: actor.pursuitTargetId,
    },
    target: {
      referenceId: target.referenceId,
      x: target.x,
      y: target.y,
      action: target.action,
    },
    nearby,
    mapObstacles: (scenario.map?.obstacles ?? []).filter((obstacle) => (
      Math.max(Math.abs(obstacle.x - actor.x), Math.abs(obstacle.y - actor.y)) <= 1.25
    )),
  };
});

process.stdout.write(`${JSON.stringify({
  rowId: ROW_ID,
  sampleIndex: 0,
  seed: SEED,
  result: {
    winnerOwner: result.winner,
    winnerHp,
    ticks: result.ticks,
    seconds: result.ticks / TICKS_PER_SECOND,
  },
  pursuitPressure: {
    limit: PRESSURE_LIMIT,
    globalMaxPressure,
    globalMaxTick,
    globalMaxSeconds: globalMaxTick / TICKS_PER_SECOND,
    overloadedTicks,
    overloadedSeconds: overloadedTicks / TICKS_PER_SECOND,
    entryCauses: Object.fromEntries([...pressureEntryCauses].sort()),
    overloadEntries,
    byTarget: pressureRows,
    intervals: pressureIntervals.sort((left, right) => left.startTick - right.startTick),
    firstTenOverloadedTicks: pressureTimeline.slice(0, 10),
  },
  stalls: {
    definition: `outside attack reach, not attacking, zero displacement for >=${STALL_MIN_TICKS} consecutive ticks`,
    count: stalls.length,
    totalTicks: stalls.reduce((sum, interval) => sum + interval.durationTicks, 0),
    totalSeconds: stalls.reduce((sum, interval) => sum + interval.durationSeconds, 0),
    top: topStalls,
    contexts: stallContexts,
  },
}, null, 2)}\n`);
