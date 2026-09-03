import { readFile } from "node:fs/promises";

import { createWorld, runWorld, stepWorld } from "../../src/combat/world.js";
import { createPairInteractionSnapshot } from "../../src/combat/pair-interactions.js";
import { planPersistentChaseRoute } from "../../src/combat/chase-path.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";
import { TICKS_PER_SECOND } from "../../src/simulation-clock.js";
import { isWithinReach } from "../../src/combat/targeting.js";
import { isWithinStopRange } from "../../src/combat/attacks.js";


const ROOT = new URL("../../", import.meta.url);
const REPORT_URL = new URL(
  "../reports/phase2_batch1_ranged_ingress_current_engine_2026-08-19/results.json",
  import.meta.url,
);
const AUTHORIZED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const ROW_ID = "elite_conquistador_vs_champion";


const source = JSON.parse(await readFile(
  new URL("calibration/source/phase2_source.json", ROOT),
  "utf8",
));
if (source.authorized !== true || source.zip_sha256 !== AUTHORIZED_SHA256) {
  throw new Error(`unauthorized Phase 2 source ${source.zip_sha256}`);
}
const report = JSON.parse(await readFile(REPORT_URL, "utf8"));
if (report.source?.archive?.zip_sha256 !== AUTHORIZED_SHA256) {
  throw new Error(`report source mismatch ${report.source?.archive?.zip_sha256}`);
}
const truth = await loadPhase2Batch1Truth(ROOT);
const context = await loadPhase2Batch1Context(ROOT, truth);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row) throw new Error(`missing Phase 2 row ${ROW_ID}`);
const scenario = scenarioFromPhase2Batch1Row({
  row,
  sampleIndex: 0,
  seed: report.config.seed,
  context,
});
const result = runWorld(createWorld(scenario), {
  maxTicks: PHASE2_MAX_TICKS,
  retainSnapshots: true,
});

const championMaster = row.side3.master;
const championIds = new Set(scenario.units
  .filter(({ mechanics }) => mechanics.unit_master === championMaster)
  .map(({ referenceId }) => referenceId));
const eventsByActor = new Map();
for (const entry of result.events) {
  if (!championIds.has(entry.actorId)) continue;
  if (!eventsByActor.has(entry.actorId)) eventsByActor.set(entry.actorId, []);
  eventsByActor.get(entry.actorId).push(entry);
}

const stallCauses = classifyStallCauses();
const routeProbes = probeRepresentativeStalls(new Map([
  [1523, 1614],
  [1636, 1613],
  [1527, 1625],
  [922, 1623],
]));
const rows = [...championIds].map((referenceId) => ({
  ...diagnoseChampion(referenceId),
  stallCauses: stallCauses.get(referenceId),
}));
rows.sort((left, right) => right.silentStallTicks - left.silentStallTicks);
const chaseTotals = rows.reduce((summary, unit) => {
  for (const name of [
    "chaseTicks",
    "moveTicks",
    "progressTicks",
    "regressTicks",
    "stallTicks",
    "blockedStallTicks",
    "silentStallTicks",
    "attackTicks",
  ]) summary[name] += unit[name];
  return summary;
}, {
  chaseTicks: 0,
  moveTicks: 0,
  progressTicks: 0,
  regressTicks: 0,
  stallTicks: 0,
  blockedStallTicks: 0,
  silentStallTicks: 0,
  attackTicks: 0,
});

const timeline = buildTimeline();
const worstGroupSeconds = timeline
  .filter(({ chasing }) => chasing > 0)
  .sort((left, right) => right.silentStalled - left.silentStalled
    || right.stalled - left.stalled
    || left.second - right.second)
  .slice(0, 12)
  .sort((left, right) => left.second - right.second);
const output = {
  schemaVersion: 1,
  rowId: ROW_ID,
  sourceZipSha256: AUTHORIZED_SHA256,
  sampleIndex: 0,
  seed: report.config.seed,
  roster: {
    conquistadors: row.side2.count,
    champions: row.side3.count,
  },
  result: {
    ticks: result.ticks,
    seconds: round(result.ticks / TICKS_PER_SECOND),
    winnerOwner: result.winner,
    survivingChampions: result.world.units.filter((unit) => (
      championIds.has(unit.referenceId) && unit.alive
    )).length,
  },
  championChaseTotals: {
    ...chaseTotals,
    moveShare: share(chaseTotals.moveTicks, chaseTotals.chaseTicks),
    progressShare: share(chaseTotals.progressTicks, chaseTotals.chaseTicks),
    regressShare: share(chaseTotals.regressTicks, chaseTotals.chaseTicks),
    stallShare: share(chaseTotals.stallTicks, chaseTotals.chaseTicks),
    blockedStallShare: share(chaseTotals.blockedStallTicks, chaseTotals.chaseTicks),
    silentStallShare: share(chaseTotals.silentStallTicks, chaseTotals.chaseTicks),
  },
  eventTotals: countEvents(result.events.filter(({ actorId }) => championIds.has(actorId))),
  routeProbes,
  worstGroupSeconds,
  champions: rows,
};
process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);


function diagnoseChampion(referenceId) {
  const actorEvents = eventsByActor.get(referenceId) ?? [];
  const eventTicks = eventTickIndex(actorEvents);
  const summary = {
    referenceId,
    aliveTicks: 0,
    chaseTicks: 0,
    moveTicks: 0,
    progressTicks: 0,
    regressTicks: 0,
    neutralMoveTicks: 0,
    stallTicks: 0,
    blockedStallTicks: 0,
    silentStallTicks: 0,
    attackTicks: 0,
    maxStallTicks: 0,
    maxSilentStallTicks: 0,
    targetChanges: 0,
    damageEvents: actorEvents.filter(({ type }) => type === "damage").length,
    attackStarts: actorEvents.filter(({ type }) => type === "attack-start").length,
    routePlans: actorEvents.filter(({ type }) => type === "pursuit-route-planned").length,
    routeAdvances: actorEvents.filter(({ type }) => type === "pursuit-route-advanced").length,
    routeInvalidations: actorEvents
      .filter(({ type }) => type === "pursuit-route-invalidated").length,
    blockedEvents: actorEvents.filter(({ type }) => type === "blocked").length,
  };
  let stallRun = 0;
  let silentRun = 0;
  let priorTargetId = null;
  const silentWindows = [];
  let currentSilentWindow = null;
  for (let index = 1; index < result.snapshots.length; index += 1) {
    const before = result.snapshots[index - 1];
    const after = result.snapshots[index];
    const beforeById = new Map(before.units.map((unit) => [unit.referenceId, unit]));
    const afterById = new Map(after.units.map((unit) => [unit.referenceId, unit]));
    const unit = beforeById.get(referenceId);
    const next = afterById.get(referenceId);
    if (!unit?.alive || !next) continue;
    summary.aliveTicks += 1;
    if (unit.action === "attacking") summary.attackTicks += 1;
    const target = beforeById.get(unit.pursuitTargetId);
    const targetNext = afterById.get(unit.pursuitTargetId);
    const chasing = target?.alive && targetNext?.alive
      && unit.action !== "attacking"
      && !isWithinReach(unit, target);
    if (!chasing) {
      finishSilentWindow(after.tick - 1);
      stallRun = 0;
      silentRun = 0;
      continue;
    }
    summary.chaseTicks += 1;
    if (priorTargetId !== null && priorTargetId !== unit.pursuitTargetId) {
      summary.targetChanges += 1;
    }
    priorTargetId = unit.pursuitTargetId;
    const displacement = Math.hypot(next.x - unit.x, next.y - unit.y);
    const beforeDistance = Math.hypot(target.x - unit.x, target.y - unit.y);
    const afterDistance = Math.hypot(targetNext.x - next.x, targetNext.y - next.y);
    const progress = beforeDistance - afterDistance;
    const blocked = eventTicks.blocked.has(after.tick);
    if (displacement > 1e-10) {
      summary.moveTicks += 1;
      if (progress > 1e-8) summary.progressTicks += 1;
      else if (progress < -1e-8) summary.regressTicks += 1;
      else summary.neutralMoveTicks += 1;
      finishSilentWindow(after.tick - 1);
      stallRun = 0;
      silentRun = 0;
      continue;
    }
    summary.stallTicks += 1;
    stallRun += 1;
    summary.maxStallTicks = Math.max(summary.maxStallTicks, stallRun);
    if (blocked) {
      summary.blockedStallTicks += 1;
      finishSilentWindow(after.tick - 1);
      silentRun = 0;
      continue;
    }
    summary.silentStallTicks += 1;
    silentRun += 1;
    summary.maxSilentStallTicks = Math.max(summary.maxSilentStallTicks, silentRun);
    if (!currentSilentWindow) {
      currentSilentWindow = {
        startTick: after.tick,
        endTick: after.tick,
        targetReferenceId: unit.pursuitTargetId,
        startDistance: beforeDistance,
        endDistance: afterDistance,
      };
    } else {
      currentSilentWindow.endTick = after.tick;
      currentSilentWindow.endDistance = afterDistance;
    }
  }
  finishSilentWindow(result.ticks);
  const unitEvents = countEvents(actorEvents);
  return {
    ...summary,
    aliveSeconds: round(summary.aliveTicks / TICKS_PER_SECOND),
    moveShare: share(summary.moveTicks, summary.chaseTicks),
    progressShare: share(summary.progressTicks, summary.chaseTicks),
    regressShare: share(summary.regressTicks, summary.chaseTicks),
    stallShare: share(summary.stallTicks, summary.chaseTicks),
    blockedStallShare: share(summary.blockedStallTicks, summary.chaseTicks),
    silentStallShare: share(summary.silentStallTicks, summary.chaseTicks),
    maxStallSeconds: round(summary.maxStallTicks / TICKS_PER_SECOND),
    maxSilentStallSeconds: round(summary.maxSilentStallTicks / TICKS_PER_SECOND),
    routeInvalidationReasons: Object.fromEntries(Object.entries(unitEvents)
      .filter(([name]) => name.startsWith("pursuit-route-invalidated:"))),
    longestSilentWindows: silentWindows
      .sort((left, right) => right.ticks - left.ticks)
      .slice(0, 4),
  };

  function finishSilentWindow(endTick) {
    if (!currentSilentWindow) return;
    currentSilentWindow.endTick = Math.min(currentSilentWindow.endTick, endTick);
    currentSilentWindow.ticks = currentSilentWindow.endTick
      - currentSilentWindow.startTick + 1;
    currentSilentWindow.startSeconds = round(
      currentSilentWindow.startTick / TICKS_PER_SECOND,
    );
    currentSilentWindow.endSeconds = round(
      currentSilentWindow.endTick / TICKS_PER_SECOND,
    );
    currentSilentWindow.startDistance = round(currentSilentWindow.startDistance);
    currentSilentWindow.endDistance = round(currentSilentWindow.endDistance);
    silentWindows.push(currentSilentWindow);
    currentSilentWindow = null;
  }
}


function classifyStallCauses() {
  const causes = new Map([...championIds].map((referenceId) => [referenceId, {
    collisionRejectedTicks: 0,
    stopRangeHoldTicks: 0,
    activeRouteStallTicks: 0,
    plannerStandTicks: 0,
    unclassifiedTicks: 0,
  }]));
  let world = createWorld(scenario);
  for (let elapsed = 0; elapsed < result.ticks; elapsed += 1) {
    const beforeById = new Map(world.units.map((unit) => [unit.referenceId, unit]));
    const routeBefore = new Set(world.kiteState?.chaseRoutes?.keys() ?? []);
    const reservations = world.contactReservationState?.reservations ?? new Map();
    const pairInteractions = createPairInteractionSnapshot({
      contactReservations: reservations,
    });
    const stopRangeById = new Map();
    for (const referenceId of championIds) {
      const unit = beforeById.get(referenceId);
      const target = beforeById.get(unit?.pursuitTargetId);
      if (!unit?.alive || !target?.alive || unit.action === "attacking"
          || isWithinReach(unit, target)) continue;
      stopRangeById.set(referenceId, isWithinStopRange(unit, target, {
        pairInteractions,
      }));
    }
    const next = stepWorld(world);
    const afterById = new Map(next.units.map((unit) => [unit.referenceId, unit]));
    const routeAfter = new Set(next.kiteState?.chaseRoutes?.keys() ?? []);
    for (const [referenceId, withinStopRange] of stopRangeById) {
      const before = beforeById.get(referenceId);
      const after = afterById.get(referenceId);
      if (!after || Math.hypot(after.x - before.x, after.y - before.y) > 1e-10) continue;
      const unitCauses = causes.get(referenceId);
      const blocked = next.events.some((entry) => (
        entry.type === "blocked" && entry.actorId === referenceId
      ));
      if (blocked) unitCauses.collisionRejectedTicks += 1;
      else if (withinStopRange) unitCauses.stopRangeHoldTicks += 1;
      else if (routeBefore.has(referenceId) || routeAfter.has(referenceId)) {
        unitCauses.activeRouteStallTicks += 1;
      } else if (world.kiteState?.persistentMeleePursuitRouting === true) {
        unitCauses.plannerStandTicks += 1;
      } else unitCauses.unclassifiedTicks += 1;
    }
    world = next;
  }
  return causes;
}


function probeRepresentativeStalls(probeByTick) {
  const probes = [];
  let world = createWorld(scenario);
  for (let elapsed = 0; elapsed < result.ticks; elapsed += 1) {
    const tick = world.tick + 1;
    const referenceId = probeByTick.get(tick);
    if (referenceId !== undefined) {
      const live = world.units.filter(({ alive }) => alive);
      const mover = live.find((unit) => unit.referenceId === referenceId);
      const target = live.find((unit) => unit.referenceId === mover?.pursuitTargetId);
      if (!mover || !target) {
        world = stepWorld(world);
        continue;
      }
      const pairInteractions = createPairInteractionSnapshot({
        contactReservations: world.contactReservationState?.reservations ?? new Map(),
      });
      const obstacles = live.filter((other) => other.referenceId !== mover.referenceId
        && other.referenceId !== target.referenceId
        && other.referenceId !== mover.pursuitTargetId
        && other.referenceId !== mover.engagedTargetId
        && other.referenceId !== mover.attackTargetId);
      const plan = (bodies, map = world.map) => summarizeRoute(planPersistentChaseRoute(
        mover,
        target,
        bodies,
        map,
        { pairInteractions },
      ));
      probes.push({
        tick,
        seconds: round(tick / TICKS_PER_SECOND),
        referenceId,
        targetReferenceId: target.referenceId,
        targetDistance: round(Math.hypot(target.x - mover.x, target.y - mover.y)),
        activeRoute: world.kiteState?.chaseRoutes?.has(referenceId) ?? false,
        nearbyAllies: nearbyCount(mover, live, mover.owner, true),
        nearbyEnemies: nearbyCount(mover, live, mover.owner, false),
        full: plan(obstacles),
        withoutAllies: plan(obstacles.filter((body) => body.owner !== mover.owner)),
        withoutOtherEnemies: plan(obstacles.filter((body) => body.owner === mover.owner)),
        mapOnly: plan([]),
        dynamicOnly: plan(obstacles, { ...world.map, obstacles: [] }),
        empty: plan([], { ...world.map, obstacles: [] }),
      });
    }
    world = stepWorld(world);
  }
  return probes;
}


function summarizeRoute(route) {
  if (route === null) return { outcome: "direct" };
  if (route.stand === true) return { outcome: "stand" };
  return {
    outcome: "route",
    waypointCount: route.waypoints.length,
    firstWaypoint: route.waypoints[0],
  };
}


function nearbyCount(mover, units, owner, allied) {
  return units.filter((unit) => unit.referenceId !== mover.referenceId
    && (allied ? unit.owner === owner : unit.owner !== owner)
    && Math.hypot(unit.x - mover.x, unit.y - mover.y) <= 2).length;
}


function buildTimeline() {
  const buckets = new Map();
  for (let index = 1; index < result.snapshots.length; index += 1) {
    const before = result.snapshots[index - 1];
    const after = result.snapshots[index];
    const beforeById = new Map(before.units.map((unit) => [unit.referenceId, unit]));
    const afterById = new Map(after.units.map((unit) => [unit.referenceId, unit]));
    const second = Math.floor(after.tick / TICKS_PER_SECOND);
    if (!buckets.has(second)) buckets.set(second, {
      second,
      liveUnitTicks: 0,
      chasingUnitTicks: 0,
      movingUnitTicks: 0,
      progressUnitTicks: 0,
      stalledUnitTicks: 0,
      silentStalledUnitTicks: 0,
      attackingUnitTicks: 0,
    });
    const bucket = buckets.get(second);
    for (const referenceId of championIds) {
      const unit = beforeById.get(referenceId);
      const next = afterById.get(referenceId);
      if (!unit?.alive || !next) continue;
      bucket.liveUnitTicks += 1;
      if (unit.action === "attacking") bucket.attackingUnitTicks += 1;
      const target = beforeById.get(unit.pursuitTargetId);
      const targetNext = afterById.get(unit.pursuitTargetId);
      if (!target?.alive || !targetNext?.alive || unit.action === "attacking"
          || isWithinReach(unit, target)) continue;
      bucket.chasingUnitTicks += 1;
      const displacement = Math.hypot(next.x - unit.x, next.y - unit.y);
      if (displacement <= 1e-10) {
        bucket.stalledUnitTicks += 1;
        const wasBlocked = (eventsByActor.get(referenceId) ?? []).some((entry) => (
          entry.type === "blocked" && entry.tick === after.tick
        ));
        if (!wasBlocked) bucket.silentStalledUnitTicks += 1;
      } else {
        bucket.movingUnitTicks += 1;
        const beforeDistance = Math.hypot(target.x - unit.x, target.y - unit.y);
        const afterDistance = Math.hypot(targetNext.x - next.x, targetNext.y - next.y);
        if (afterDistance < beforeDistance - 1e-8) bucket.progressUnitTicks += 1;
      }
    }
  }
  return [...buckets.values()].map((bucket) => ({
    second: bucket.second,
    live: round(bucket.liveUnitTicks / TICKS_PER_SECOND),
    chasing: round(bucket.chasingUnitTicks / TICKS_PER_SECOND),
    moving: round(bucket.movingUnitTicks / TICKS_PER_SECOND),
    progressing: round(bucket.progressUnitTicks / TICKS_PER_SECOND),
    stalled: round(bucket.stalledUnitTicks / TICKS_PER_SECOND),
    silentStalled: round(bucket.silentStalledUnitTicks / TICKS_PER_SECOND),
    attacking: round(bucket.attackingUnitTicks / TICKS_PER_SECOND),
  }));
}


function eventTickIndex(events) {
  const blocked = new Set();
  for (const entry of events) {
    if (entry.type === "blocked") blocked.add(entry.tick);
  }
  return { blocked };
}


function countEvents(events) {
  const counts = {};
  for (const entry of events) {
    const name = entry.type === "pursuit-route-invalidated"
      ? `${entry.type}:${entry.reason ?? "unknown"}`
      : entry.type;
    counts[name] = (counts[name] ?? 0) + 1;
  }
  return counts;
}


function share(numerator, denominator) {
  return denominator === 0 ? null : round(numerator / denominator);
}


function round(value) {
  return Math.round(value * 10000) / 10000;
}
