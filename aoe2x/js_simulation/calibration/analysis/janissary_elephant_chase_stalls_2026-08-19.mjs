import { readFile, mkdir, writeFile } from "node:fs/promises";

import { createWorld, stepWorld } from "../../src/combat/world.js";
import {
  createPairInteractionSnapshot,
  resolvePairInteraction,
} from "../../src/combat/pair-interactions.js";
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
const ROW_ID = "elite_janissary_vs_elite_elephant";
const AUTHORIZED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const REPORT_URL = new URL(
  "../reports/phase2_batch1_ranged_ingress_current_engine_2026-08-19/results.json",
  import.meta.url,
);
const OUTPUT_URL = new URL(
  "../reports/janissary_elephant_chase_stalls_2026-08-19/report.json",
  import.meta.url,
);
const STALL_STEP_SHARE = 0.1;
const DIRECTION_STEP_SHARE = 0.25;


const source = JSON.parse(await readFile(
  new URL("calibration/source/phase2_source.json", ROOT),
  "utf8",
));
if (source.authorized !== true || source.zip_sha256 !== AUTHORIZED_SHA256) {
  throw new Error(`unauthorized Phase 2 source ${source.zip_sha256}`);
}
const priorReport = JSON.parse(await readFile(REPORT_URL, "utf8"));
if (priorReport.source?.archive?.zip_sha256 !== AUTHORIZED_SHA256) {
  throw new Error(`report source mismatch ${priorReport.source?.archive?.zip_sha256}`);
}
const truth = await loadPhase2Batch1Truth(ROOT);
if (truth.archive?.zip_sha256 !== AUTHORIZED_SHA256) {
  throw new Error(`truth source mismatch ${truth.archive?.zip_sha256}`);
}
const context = await loadPhase2Batch1Context(ROOT, truth);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row) throw new Error(`missing Phase 2 row ${ROW_ID}`);
const scenario = scenarioFromPhase2Batch1Row({
  row,
  sampleIndex: 0,
  seed: priorReport.config.seed,
  context,
});
const elephantIds = new Set(scenario.units
  .filter(({ owner, mechanics }) => (
    owner === 3 && mechanics.unit_master === row.side3.master
  ))
  .map(({ referenceId }) => referenceId));
const perElephant = new Map([...elephantIds].map((referenceId) => [referenceId, accumulator()]));
const perSecond = new Map();
const allEvents = [];
let world = createWorld(scenario);

for (let elapsed = 0; elapsed < PHASE2_MAX_TICKS; elapsed += 1) {
  const before = world;
  const beforeById = new Map(before.units.map((unit) => [unit.referenceId, unit]));
  const reservations = before.contactReservationState?.reservations ?? new Map();
  const pairInteractions = createPairInteractionSnapshot({
    contactReservations: reservations,
  });
  const routeBefore = before.kiteState?.chaseRoutes ?? new Map();
  const next = stepWorld(before);
  allEvents.push(...next.events);
  const afterById = new Map(next.units.map((unit) => [unit.referenceId, unit]));
  const eventsByActor = indexEvents(next.events);
  const second = Math.floor(next.tick / TICKS_PER_SECOND);
  const secondBucket = getSecondBucket(second);

  for (const referenceId of elephantIds) {
    const unit = beforeById.get(referenceId);
    const after = afterById.get(referenceId);
    if (!unit?.alive || !after) continue;
    const summary = perElephant.get(referenceId);
    summary.aliveTicks += 1;
    const target = beforeById.get(unit.pursuitTargetId);
    const targetAfter = afterById.get(unit.pursuitTargetId);
    if (!target?.alive || !targetAfter?.alive || target.owner === unit.owner) {
      finishStallWindow(summary, next.tick - 1);
      continue;
    }
    const attackHold = unit.action === "attacking" || isWithinReach(unit, target);
    const chasing = !attackHold;
    if (!chasing) {
      summary.attackOrReachTicks += 1;
      secondBucket.attackOrReachTicks += 1;
      finishStallWindow(summary, next.tick - 1);
      continue;
    }

    summary.chaseTicks += 1;
    secondBucket.chaseTicks += 1;
    const events = eventsByActor.get(referenceId) ?? [];
    const blockedEvent = events.find(({ type }) => type === "blocked") ?? null;
    const displacement = Math.hypot(after.x - unit.x, after.y - unit.y);
    const nominalStep = unit.mechanics.speed_tiles_per_second / TICKS_PER_SECOND;
    const movementShare = nominalStep > 0 ? displacement / nominalStep : 0;
    const beforeDistance = Math.hypot(target.x - unit.x, target.y - unit.y);
    const afterDistance = Math.hypot(targetAfter.x - after.x, targetAfter.y - after.y);
    const progress = beforeDistance - afterDistance;
    const route = routeBefore.get(referenceId) ?? null;
    const withinStopRange = isWithinStopRange(unit, target, { pairInteractions });
    const blockers = blockedEvent
      ? projectedBlockers(unit, blockedEvent, before.units, pairInteractions)
      : [];
    const mapBlockers = blockedEvent
      ? projectedMapBlockers(unit, blockedEvent, before.map)
      : [];
    const direction = tangentialDirection(unit, after, before.map);
    const resolvedContacts = resolvedConstraintContacts(
      after,
      next.units,
      pairInteractions,
    );

    if (movementShare >= DIRECTION_STEP_SHARE && direction !== 0) {
      summary.directionSamples.push({
        tick: next.tick,
        second: round(next.tick / TICKS_PER_SECOND),
        direction,
        distance: afterDistance,
        targetReferenceId: target.referenceId,
        routeActive: route !== null,
        routeProgressive: route?.progressive === true,
        routeTargetDrift: route
          ? Math.hypot(target.x - route.targetX, target.y - route.targetY)
          : 0,
      });
      secondBucket.directionScore += direction * displacement;
      secondBucket.directionTravel += displacement;
    }
    if (movementShare >= STALL_STEP_SHARE) {
      summary.moveTicks += 1;
      secondBucket.moveTicks += 1;
      if (progress > 1e-8) {
        summary.progressTicks += 1;
        secondBucket.progressTicks += 1;
      } else if (progress < -1e-8) {
        summary.regressTicks += 1;
        secondBucket.regressTicks += 1;
      } else {
        summary.neutralTicks += 1;
      }
      finishStallWindow(summary, next.tick - 1);
      continue;
    }

    summary.stallTicks += 1;
    secondBucket.stallTicks += 1;
    if (blockedEvent) {
      summary.causeCounts.collisionRejected += 1;
      secondBucket.collisionRejected += 1;
    } else if (withinStopRange) {
      summary.causeCounts.stopRangeHold += 1;
      secondBucket.stopRangeHold += 1;
    } else if (route) {
      summary.causeCounts.activeRouteNoProgress += 1;
      secondBucket.activeRouteNoProgress += 1;
    } else {
      summary.causeCounts.noProposalOrPlannerDeferral += 1;
      secondBucket.noProposalOrPlannerDeferral += 1;
    }
    for (const blocker of blockers) {
      const key = `${blocker.owner === unit.owner ? "ally" : "enemy"}:${blocker.referenceId}`
        + `:${blocker.interactionKind}`;
      summary.blockerCounts.set(key, (summary.blockerCounts.get(key) ?? 0) + 1);
    }
    extendStallWindow(summary, {
      tick: next.tick,
      targetReferenceId: target.referenceId,
      startDistance: beforeDistance,
      endDistance: afterDistance,
      blocked: blockedEvent !== null,
      withinStopRange,
      activeRoute: route !== null,
      routeProgressive: route?.progressive === true,
      blockerKeys: blockers.map((blocker) => (
        `${blocker.owner === unit.owner ? "ally" : "enemy"}:${blocker.referenceId}`
          + `:${blocker.interactionKind}`
      )),
      mapBlockerKeys: mapBlockers.map(({ referenceId }) => String(referenceId)),
      resolvedContactKeys: resolvedContacts.map(({ referenceId, owner, interactionKind }) => (
        `${owner === unit.owner ? "ally" : "enemy"}:${referenceId}:${interactionKind}`
      )),
      reservationKinds: reservationsFor(referenceId, reservations),
    });
  }

  world = next;
  if (new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner)).size <= 1) {
    break;
  }
}

for (const summary of perElephant.values()) finishStallWindow(summary, world.tick);
const elephantRows = [...perElephant.entries()].map(([referenceId, summary]) => ({
  referenceId,
  aliveSeconds: round(summary.aliveTicks / TICKS_PER_SECOND),
  chaseSeconds: round(summary.chaseTicks / TICKS_PER_SECOND),
  chaseMoveShare: share(summary.moveTicks, summary.chaseTicks),
  chaseProgressShare: share(summary.progressTicks, summary.chaseTicks),
  chaseRegressShare: share(summary.regressTicks, summary.chaseTicks),
  chaseStallShare: share(summary.stallTicks, summary.chaseTicks),
  longestStallSeconds: round(summary.longestStallTicks / TICKS_PER_SECOND),
  causeCounts: summary.causeCounts,
  blockerCounts: Object.fromEntries([...summary.blockerCounts]
    .sort((left, right) => right[1] - left[1])),
  directionSwitches: summarizeDirectionSwitches(summary.directionSamples),
  longestStallWindows: summary.stallWindows
    .sort((left, right) => right.ticks - left.ticks)
    .slice(0, 8),
})).sort((left, right) => right.chaseStallShare - left.chaseStallShare
  || right.longestStallSeconds - left.longestStallSeconds);

const totals = elephantRows.reduce((value, unit) => {
  const raw = perElephant.get(unit.referenceId);
  value.chaseTicks += raw.chaseTicks;
  value.moveTicks += raw.moveTicks;
  value.progressTicks += raw.progressTicks;
  value.regressTicks += raw.regressTicks;
  value.stallTicks += raw.stallTicks;
  for (const [name, count] of Object.entries(raw.causeCounts)) value.causeCounts[name] += count;
  return value;
}, {
  chaseTicks: 0,
  moveTicks: 0,
  progressTicks: 0,
  regressTicks: 0,
  stallTicks: 0,
  causeCounts: {
    collisionRejected: 0,
    stopRangeHold: 0,
    activeRouteNoProgress: 0,
    noProposalOrPlannerDeferral: 0,
  },
});
const timeline = [...perSecond.values()].map((bucket) => ({
  second: bucket.second,
  chaseUnitSeconds: round(bucket.chaseTicks / TICKS_PER_SECOND),
  movingUnitSeconds: round(bucket.moveTicks / TICKS_PER_SECOND),
  progressingUnitSeconds: round(bucket.progressTicks / TICKS_PER_SECOND),
  regressingUnitSeconds: round(bucket.regressTicks / TICKS_PER_SECOND),
  stalledUnitSeconds: round(bucket.stallTicks / TICKS_PER_SECOND),
  collisionRejectedUnitSeconds: round(bucket.collisionRejected / TICKS_PER_SECOND),
  activeRouteNoProgressUnitSeconds: round(bucket.activeRouteNoProgress / TICKS_PER_SECOND),
  direction: bucket.directionTravel <= 1e-12
    ? "none"
    : bucket.directionScore > 0 ? "counter-clockwise" : "clockwise",
}));
const groupDirectionSwitches = [];
let priorDirection = null;
for (const bucket of timeline) {
  if (bucket.direction === "none") continue;
  if (priorDirection && priorDirection.direction !== bucket.direction) {
    groupDirectionSwitches.push({
      second: bucket.second,
      from: priorDirection.direction,
      to: bucket.direction,
      precedingSecond: priorDirection.second,
      stalledUnitSeconds: bucket.stalledUnitSeconds,
      collisionRejectedUnitSeconds: bucket.collisionRejectedUnitSeconds,
    });
  }
  priorDirection = bucket;
}
const eventTotals = countEvents(allEvents.filter(({ actorId }) => elephantIds.has(actorId)));
const live = world.units.filter(({ alive }) => alive);
const output = {
  schemaVersion: 1,
  rowId: ROW_ID,
  sourceZipSha256: AUTHORIZED_SHA256,
  sampleIndex: 0,
  seed: priorReport.config.seed,
  roster: { janissaries: row.side2.count, elephants: row.side3.count },
  result: {
    ticks: world.tick,
    seconds: round(world.tick / TICKS_PER_SECOND),
    winnerOwner: new Set(live.map(({ owner }) => owner)).size === 1 ? live[0].owner : null,
    survivorsByOwner: Object.fromEntries([2, 3].map((owner) => [
      owner,
      live.filter((unit) => unit.owner === owner).length,
    ])),
  },
  elephantChaseTotals: {
    ...totals,
    moveShare: share(totals.moveTicks, totals.chaseTicks),
    progressShare: share(totals.progressTicks, totals.chaseTicks),
    regressShare: share(totals.regressTicks, totals.chaseTicks),
    stallShare: share(totals.stallTicks, totals.chaseTicks),
  },
  eventTotals,
  groupDirectionSwitches,
  requestedWindows: timeline.filter(({ second }) => (
    second >= 15 && second <= 21 || second >= 42 && second <= 57
  )),
  worstSeconds: [...timeline]
    .sort((left, right) => right.stalledUnitSeconds - left.stalledUnitSeconds
      || right.regressingUnitSeconds - left.regressingUnitSeconds)
    .slice(0, 20),
  elephants: elephantRows,
};

await mkdir(new URL("../reports/janissary_elephant_chase_stalls_2026-08-19/", import.meta.url), {
  recursive: true,
});
await writeFile(OUTPUT_URL, `${JSON.stringify(output, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);


function accumulator() {
  return {
    aliveTicks: 0,
    chaseTicks: 0,
    moveTicks: 0,
    progressTicks: 0,
    regressTicks: 0,
    neutralTicks: 0,
    stallTicks: 0,
    attackOrReachTicks: 0,
    longestStallTicks: 0,
    currentStallWindow: null,
    stallWindows: [],
    directionSamples: [],
    causeCounts: {
      collisionRejected: 0,
      stopRangeHold: 0,
      activeRouteNoProgress: 0,
      noProposalOrPlannerDeferral: 0,
    },
    blockerCounts: new Map(),
  };
}


function getSecondBucket(second) {
  if (!perSecond.has(second)) perSecond.set(second, {
    second,
    chaseTicks: 0,
    moveTicks: 0,
    progressTicks: 0,
    regressTicks: 0,
    stallTicks: 0,
    attackOrReachTicks: 0,
    collisionRejected: 0,
    stopRangeHold: 0,
    activeRouteNoProgress: 0,
    noProposalOrPlannerDeferral: 0,
    directionScore: 0,
    directionTravel: 0,
  });
  return perSecond.get(second);
}


function indexEvents(events) {
  const result = new Map();
  for (const entry of events) {
    if (!result.has(entry.actorId)) result.set(entry.actorId, []);
    result.get(entry.actorId).push(entry);
  }
  return result;
}


function projectedBlockers(unit, blockedEvent, units, pairInteractions) {
  const proposedX = unit.x + blockedEvent.proposedDx;
  const proposedY = unit.y + blockedEvent.proposedDy;
  return units.filter((other) => other.alive && other.referenceId !== unit.referenceId)
    .map((other) => ({
      other,
      interaction: resolvePairInteraction(unit, other, pairInteractions),
    }))
    .filter(({ other, interaction }) => interaction.pathObstructs
      && Math.max(
        Math.abs(proposedX - other.x),
        Math.abs(proposedY - other.y),
      ) < interaction.collisionExtent - 1e-12)
    .map(({ other, interaction }) => ({
      referenceId: other.referenceId,
      owner: other.owner,
      interactionKind: interaction.kind,
      collisionExtent: round(interaction.collisionExtent),
    }));
}


function projectedMapBlockers(unit, blockedEvent, map) {
  const radius = Math.max(
    unit.mechanics.collision_size_tiles.x,
    unit.mechanics.collision_size_tiles.y,
  );
  return (map.obstacles ?? []).filter((obstacle) => {
    const startX = unit.x - obstacle.x;
    const startY = unit.y - obstacle.y;
    const dx = blockedEvent.proposedDx;
    const dy = blockedEvent.proposedDy;
    const lengthSquared = dx * dx + dy * dy;
    const projection = lengthSquared === 0
      ? 0
      : Math.max(0, Math.min(1, -(startX * dx + startY * dy) / lengthSquared));
    const distance = Math.hypot(
      startX + projection * dx,
      startY + projection * dy,
    );
    return distance < radius + obstacle.radius - 1e-12;
  }).map(({ referenceId }) => ({ referenceId }));
}


function resolvedConstraintContacts(unit, units, pairInteractions) {
  return units.filter((other) => other.alive && other.referenceId !== unit.referenceId)
    .map((other) => ({
      other,
      interaction: resolvePairInteraction(unit, other, pairInteractions),
    }))
    .filter(({ other, interaction }) => interaction.pathObstructs
      && Math.max(
        Math.abs(unit.x - other.x),
        Math.abs(unit.y - other.y),
      ) <= interaction.collisionExtent + 1e-7)
    .map(({ other, interaction }) => ({
      referenceId: other.referenceId,
      owner: other.owner,
      interactionKind: interaction.kind,
    }));
}


function reservationsFor(referenceId, reservations) {
  return [...reservations.values()]
    .filter(({ leftId, rightId }) => leftId === referenceId || rightId === referenceId)
    .map(({ leftId, rightId, kind }) => ({
      otherReferenceId: leftId === referenceId ? rightId : leftId,
      kind,
    }));
}


function extendStallWindow(summary, state) {
  if (!summary.currentStallWindow) {
    summary.currentStallWindow = {
      startTick: state.tick,
      endTick: state.tick,
      targetReferenceId: state.targetReferenceId,
      startDistance: state.startDistance,
      endDistance: state.endDistance,
      blockedTicks: 0,
      stopRangeTicks: 0,
      activeRouteTicks: 0,
      progressiveRouteTicks: 0,
      blockerCounts: new Map(),
      mapBlockerCounts: new Map(),
      resolvedContactCounts: new Map(),
      reservationKindCounts: new Map(),
      reservationPairCounts: new Map(),
    };
  }
  const window = summary.currentStallWindow;
  window.endTick = state.tick;
  window.endDistance = state.endDistance;
  if (state.blocked) window.blockedTicks += 1;
  if (state.withinStopRange) window.stopRangeTicks += 1;
  if (state.activeRoute) window.activeRouteTicks += 1;
  if (state.routeProgressive) window.progressiveRouteTicks += 1;
  for (const key of state.blockerKeys) {
    window.blockerCounts.set(key, (window.blockerCounts.get(key) ?? 0) + 1);
  }
  for (const key of state.mapBlockerKeys) {
    window.mapBlockerCounts.set(key, (window.mapBlockerCounts.get(key) ?? 0) + 1);
  }
  for (const key of state.resolvedContactKeys) {
    window.resolvedContactCounts.set(key, (window.resolvedContactCounts.get(key) ?? 0) + 1);
  }
  for (const { kind, otherReferenceId } of state.reservationKinds) {
    window.reservationKindCounts.set(kind, (window.reservationKindCounts.get(kind) ?? 0) + 1);
    const key = `${kind}:${otherReferenceId}`;
    window.reservationPairCounts.set(key, (window.reservationPairCounts.get(key) ?? 0) + 1);
  }
}


function finishStallWindow(summary, endTick) {
  const window = summary.currentStallWindow;
  if (!window) return;
  window.endTick = Math.min(window.endTick, endTick);
  window.ticks = window.endTick - window.startTick + 1;
  summary.longestStallTicks = Math.max(summary.longestStallTicks, window.ticks);
  summary.stallWindows.push({
    startSeconds: round(window.startTick / TICKS_PER_SECOND),
    endSeconds: round(window.endTick / TICKS_PER_SECOND),
    seconds: round(window.ticks / TICKS_PER_SECOND),
    targetReferenceId: window.targetReferenceId,
    startDistance: round(window.startDistance),
    endDistance: round(window.endDistance),
    blockedShare: share(window.blockedTicks, window.ticks),
    stopRangeShare: share(window.stopRangeTicks, window.ticks),
    activeRouteShare: share(window.activeRouteTicks, window.ticks),
    progressiveRouteShare: share(window.progressiveRouteTicks, window.ticks),
    blockerCounts: Object.fromEntries([...window.blockerCounts]
      .sort((left, right) => right[1] - left[1])),
    mapBlockerCounts: Object.fromEntries([...window.mapBlockerCounts]
      .sort((left, right) => right[1] - left[1])),
    resolvedContactCounts: Object.fromEntries([...window.resolvedContactCounts]
      .sort((left, right) => right[1] - left[1])),
    reservationKindCounts: Object.fromEntries([...window.reservationKindCounts]
      .sort((left, right) => right[1] - left[1])),
    reservationPairCounts: Object.fromEntries([...window.reservationPairCounts]
      .sort((left, right) => right[1] - left[1])),
  });
  summary.currentStallWindow = null;
}


function tangentialDirection(before, after, map) {
  const centerX = map.width / 2;
  const centerY = map.height / 2;
  const rx = before.x - centerX;
  const ry = before.y - centerY;
  const dx = after.x - before.x;
  const dy = after.y - before.y;
  const cross = rx * dy - ry * dx;
  if (Math.abs(cross) <= 1e-12) return 0;
  return cross > 0 ? 1 : -1;
}


function summarizeDirectionSwitches(samples) {
  const bySecond = new Map();
  for (const sample of samples) {
    const second = Math.floor(sample.tick / TICKS_PER_SECOND);
    if (!bySecond.has(second)) bySecond.set(second, {
      score: 0,
      count: 0,
      distance: 0,
      routeActive: 0,
      routeProgressive: 0,
      routeTargetDrift: 0,
      targets: new Map(),
    });
    const bucket = bySecond.get(second);
    bucket.score += sample.direction;
    bucket.count += 1;
    bucket.distance += sample.distance;
    if (sample.routeActive) bucket.routeActive += 1;
    if (sample.routeProgressive) bucket.routeProgressive += 1;
    bucket.routeTargetDrift += sample.routeTargetDrift;
    bucket.targets.set(
      sample.targetReferenceId,
      (bucket.targets.get(sample.targetReferenceId) ?? 0) + 1,
    );
  }
  const switches = [];
  let prior = null;
  for (const [second, bucket] of bySecond) {
    const direction = bucket.score > 0 ? 1 : bucket.score < 0 ? -1 : 0;
    if (direction === 0) continue;
    if (prior && prior.direction !== direction) {
      const targetReferenceId = [...bucket.targets]
        .sort((left, right) => right[1] - left[1])[0]?.[0] ?? null;
      switches.push({
        second,
        from: prior.direction > 0 ? "counter-clockwise" : "clockwise",
        to: direction > 0 ? "counter-clockwise" : "clockwise",
        targetDistance: round(bucket.distance / bucket.count),
        fromTargetReferenceId: prior.targetReferenceId,
        targetReferenceId,
        targetChanged: prior.targetReferenceId !== targetReferenceId,
        activeRouteShare: share(bucket.routeActive, bucket.count),
        progressiveRouteShare: share(bucket.routeProgressive, bucket.count),
        meanRouteTargetDrift: round(bucket.routeTargetDrift / bucket.count),
      });
    }
    const targetReferenceId = [...bucket.targets]
      .sort((left, right) => right[1] - left[1])[0]?.[0] ?? null;
    prior = { second, direction, targetReferenceId };
  }
  return switches;
}


function countEvents(events) {
  const result = {};
  for (const entry of events) {
    const key = entry.type === "pursuit-route-invalidated"
      ? `${entry.type}:${entry.reason ?? "unknown"}`
      : entry.type;
    result[key] = (result[key] ?? 0) + 1;
  }
  return result;
}


function share(numerator, denominator) {
  return denominator ? round(numerator / denominator) : null;
}


function round(value) {
  return Math.round(value * 10000) / 10000;
}
