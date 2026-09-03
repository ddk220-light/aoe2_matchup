// Analysis-only trace for the current 27 Chinese Arbalester vs 18 Saracen
// Heavy Cavalry Archer simulation. This script does not alter engine state or
// feed matchup-specific values back into runtime mechanics.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { isWithinStopRange } from "../src/combat/attacks.js";
import { createUnitState } from "../src/combat/unit-state.js";
import { createWorld, stepWorld } from "../src/combat/world.js";
import { collisionRadius, isWithinReach } from "../src/combat/targeting.js";
import {
  createPairInteractionSnapshot,
  resolvePairInteraction,
} from "../src/combat/pair-interactions.js";


const REPORT_DIR = new URL(
  "../calibration/reports/arbalester_hca_participation_2026-08-30/",
  import.meta.url,
);
const OUTPUT = new URL(
  process.env.AOE2X_DIAGNOSTIC_OUTPUT ?? "hca_stationary_intent_diagnostic.json",
  REPORT_DIR,
);
const START_TICK = 5 * 60;
const END_TICK = Number.parseInt(
  process.env.AOE2X_DIAGNOSTIC_END_TICK ?? "9000",
  10,
);
const OWNER_HCA = 3;
const SEEDS = Object.freeze(
  (process.env.AOE2X_DIAGNOSTIC_SEEDS ?? "0,1,2,3,4")
    .split(",")
    .map(Number),
);
const REFERENCE_BASE = Object.freeze({ 2: 9000, 3: 9500 });
const STATIONARY_SPEED_TPS = 0.05;
const EPSILON = 1e-12;


function round(value, digits = 4) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}


function targetFor(unit, byReference) {
  const targetId = unit.attackTargetId ?? unit.engagedTargetId ?? unit.pursuitTargetId;
  const target = Number.isSafeInteger(targetId) ? byReference.get(targetId) : null;
  return target?.alive && target.owner !== unit.owner ? target : null;
}


function targetSummary(unit, byReference) {
  const summarize = (targetId) => {
    const target = Number.isSafeInteger(targetId) ? byReference.get(targetId) : null;
    if (!target) return null;
    const distance = Math.hypot(target.x - unit.x, target.y - unit.y);
    return {
      targetId,
      owner: target.owner,
      alive: target.alive,
      distance: round(distance, 5),
      inReach: target.alive && target.owner !== unit.owner
        ? isWithinReach(unit, target)
        : false,
      inStopRange: target.alive && target.owner !== unit.owner
        ? isWithinStopRange(unit, target)
        : false,
    };
  };
  return {
    pursuit: summarize(unit.pursuitTargetId),
    engaged: summarize(unit.engagedTargetId),
    attack: summarize(unit.attackTargetId),
  };
}


function nearest(unit, live, predicate) {
  let best = null;
  for (const other of live) {
    if (other.referenceId === unit.referenceId || !predicate(other)) continue;
    const distance = Math.hypot(other.x - unit.x, other.y - unit.y);
    if (best === null || distance < best.distance - EPSILON
        || (Math.abs(distance - best.distance) <= EPSILON
          && other.referenceId < best.referenceId)) {
      best = { referenceId: other.referenceId, owner: other.owner, distance };
    }
  }
  return best ? { ...best, distance: round(best.distance, 5) } : null;
}


function candidateBlockers(unit, beforeByReference, blockedEvent, pairInteractions) {
  if (!blockedEvent || Math.hypot(blockedEvent.proposedDx, blockedEvent.proposedDy) <= EPSILON) {
    return [];
  }
  const before = beforeByReference.get(unit.referenceId);
  if (!before) return [];
  const proposedX = before.x + blockedEvent.proposedDx;
  const proposedY = before.y + blockedEvent.proposedDy;
  const candidates = [];
  for (const other of beforeByReference.values()) {
    if (!other.alive || other.referenceId === unit.referenceId) continue;
    const interaction = resolvePairInteraction(before, other, pairInteractions);
    const extent = interaction.collisionExtent;
    const chebyshev = Math.max(
      Math.abs(proposedX - other.x),
      Math.abs(proposedY - other.y),
    );
    if (chebyshev < extent + 1e-9) {
      candidates.push({
        referenceId: other.referenceId,
        owner: other.owner,
        relation: other.owner === unit.owner ? "ally" : "enemy",
        interactionKind: interaction.kind,
        pathObstructs: interaction.pathObstructs,
        interactionReason: interaction.reason,
        chebyshev: round(chebyshev, 5),
        collisionExtent: round(extent, 5),
      });
    }
  }
  return candidates.sort((left, right) => (
    left.chebyshev - right.chebyshev || left.referenceId - right.referenceId
  ));
}


function candidateMapBlockers(unit, map, beforeByReference, blockedEvent) {
  if (!blockedEvent || Math.hypot(blockedEvent.proposedDx, blockedEvent.proposedDy) <= EPSILON) {
    return [];
  }
  const before = beforeByReference.get(unit.referenceId);
  if (!before) return [];
  const proposedX = before.x + blockedEvent.proposedDx;
  const proposedY = before.y + blockedEvent.proposedDy;
  return (map.obstacles ?? []).map((obstacle, obstacleIndex) => {
    const distance = Math.hypot(proposedX - obstacle.x, proposedY - obstacle.y);
    const collisionExtent = collisionRadius(before) + obstacle.radius;
    return {
      obstacleIndex,
      referenceId: obstacle.referenceId ?? null,
      x: obstacle.x,
      y: obstacle.y,
      distance,
      collisionExtent,
    };
  }).filter(({ distance, collisionExtent }) => distance < collisionExtent + 1e-9)
    .map((row) => ({
      ...row,
      distance: round(row.distance, 5),
      collisionExtent: round(row.collisionExtent, 5),
    }))
    .sort((left, right) => left.distance - right.distance
      || left.obstacleIndex - right.obstacleIndex);
}


function causeFor(unit, target, targets, blockedEvent, displacement, movementOrder) {
  const attempted = blockedEvent
    ? Math.hypot(blockedEvent.proposedDx, blockedEvent.proposedDy)
    : 0;
  const actual = blockedEvent
    ? Math.hypot(blockedEvent.actualDx, blockedEvent.actualDy)
    : displacement;
  if (attempted > EPSILON && actual <= STATIONARY_SPEED_TPS / 60 + EPSILON) {
    return "movement_solver_rejected_attempt";
  }
  if (attempted > EPSILON) return "movement_attempt_shortened_below_threshold";
  if (unit.action === "attacking") {
    return unit.actionTimers.windup > 0
      ? "attack_windup_holds_position"
      : "post_release_attack_animation_holds_position";
  }
  if (movementOrder?.kind === "scenario-patrol"
      && Number.isSafeInteger(movementOrder.motionStartTick)) {
    return "scenario_patrol_order_hold";
  }
  if (targets.pursuit?.alive && targets.pursuit.inStopRange) {
    return target?.referenceId === targets.pursuit.targetId
      ? "pursuit_target_inside_stop_range_metric_edge"
      : "different_pursuit_target_inside_stop_range";
  }
  if (!targets.pursuit?.alive) return "no_live_pursuit_target";
  return "zero_proposal_unexplained";
}


function episodeKey(row) {
  return [row.seed, row.unitId, row.cause, row.metricTargetId,
    row.targets.pursuit?.targetId ?? "-"].join(":");
}


function buildEpisodes(rows) {
  const episodes = [];
  const active = new Map();
  for (const row of rows) {
    const key = episodeKey(row);
    const previous = active.get(row.unitId);
    if (!previous || previous.key !== key || row.tick !== previous.endTick + 1) {
      if (previous) episodes.push(previous);
      active.set(row.unitId, {
        key,
        seed: row.seed,
        unitId: row.unitId,
        cause: row.cause,
        metricTargetId: row.metricTargetId,
        pursuitTargetId: row.targets.pursuit?.targetId ?? null,
        startTick: row.tick,
        endTick: row.tick,
        tickCount: 1,
        rangeExcessSum: row.rangeExcess,
        maxRangeExcess: row.rangeExcess,
        blockerRelations: {},
        blockerIds: {},
        actions: { [row.action]: 1 },
      });
    } else {
      previous.endTick = row.tick;
      previous.tickCount += 1;
      previous.rangeExcessSum += row.rangeExcess;
      previous.maxRangeExcess = Math.max(previous.maxRangeExcess, row.rangeExcess);
      previous.actions[row.action] = (previous.actions[row.action] ?? 0) + 1;
    }
    const episode = active.get(row.unitId);
    for (const blocker of row.candidateBlockers) {
      episode.blockerRelations[blocker.relation]
        = (episode.blockerRelations[blocker.relation] ?? 0) + 1;
      episode.blockerIds[blocker.referenceId]
        = (episode.blockerIds[blocker.referenceId] ?? 0) + 1;
    }
  }
  episodes.push(...active.values());
  return episodes.map(({ key, rangeExcessSum, ...episode }) => ({
    ...episode,
    startSecond: round(episode.startTick / 60, 3),
    endSecond: round(episode.endTick / 60, 3),
    durationSeconds: round(episode.tickCount / 60, 3),
    meanRangeExcess: round(rangeExcessSum / episode.tickCount, 4),
    maxRangeExcess: round(episode.maxRangeExcess, 4),
    topBlockerIds: Object.entries(episode.blockerIds)
      .map(([referenceId, ticks]) => ({ referenceId: Number(referenceId), ticks }))
      .sort((left, right) => right.ticks - left.ticks || left.referenceId - right.referenceId)
      .slice(0, 3),
  })).sort((left, right) => (
    right.tickCount - left.tickCount
      || left.seed - right.seed
      || left.unitId - right.unitId
      || left.startTick - right.startTick
  ));
}


function aggregate(rows, field) {
  const counts = {};
  for (const row of rows) {
    const value = row[field];
    counts[value] = (counts[value] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([value, ticks]) => ({ value, ticks, unitSeconds: round(ticks / 60, 4) }))
    .sort((left, right) => right.ticks - left.ticks || left.value.localeCompare(right.value));
}


function perSecond(rows, endTick) {
  const causes = [...new Set(rows.map(({ cause }) => cause))].sort();
  const bucketCount = Math.max(0, Math.ceil(endTick / 60) - 5);
  return Array.from({ length: bucketCount }, (_, offset) => {
    const second = offset + 5;
    const bucket = rows.filter(({ tick }) => tick >= second * 60 && tick < (second + 1) * 60);
    return {
      second,
      meanStationaryHca: round(bucket.length / 60 / SEEDS.length, 4),
      causes: Object.fromEntries(causes.map((cause) => [
        cause,
        round(bucket.filter((row) => row.cause === cause).length / 60 / SEEDS.length, 4),
      ])),
    };
  });
}


function perUnit(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = `${row.seed}:${row.unitId}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return [...groups.entries()].map(([key, unitRows]) => {
    const [seed, unitId] = key.split(":").map(Number);
    return {
      seed,
      unitId,
      stationarySeconds: round(unitRows.length / 60, 3),
      firstSecond: round(unitRows[0].tick / 60, 3),
      lastSecond: round(unitRows.at(-1).tick / 60, 3),
      dominantCause: aggregate(unitRows, "cause")[0]?.value ?? null,
      targetCount: new Set(unitRows.map(({ metricTargetId }) => metricTargetId)).size,
      meanRangeExcess: round(
        unitRows.reduce((total, row) => total + row.rangeExcess, 0) / unitRows.length,
        4,
      ),
    };
  }).sort((left, right) => (
    right.stationarySeconds - left.stationarySeconds
      || left.seed - right.seed
      || left.unitId - right.unitId
  ));
}


async function loadScenario() {
  const [formations, mapFixture, arbalester, hca] = await Promise.all([
    readFile(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/golden_map.json", import.meta.url), "utf8").then(JSON.parse),
    readFile(new URL("../fixtures/unit_stats/arbalester_chinese_imperial.json", import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json", import.meta.url), "utf8")
      .then(JSON.parse),
  ]);
  const formation = formations.families.ranged_vs_ranged;
  const cells = {
    2: formation.sides["2"].slice(0, 27).map(({ position }) => position),
    3: formation.sides["3"].slice(0, 18).map(({ position }) => position),
  };
  const roster = [
    ...cells[2].map((cell, index) => ({ owner: 2, index, cell, mechanics: arbalester })),
    ...cells[3].map((cell, index) => ({ owner: 3, index, cell, mechanics: hca })),
  ];
  const units = roster.map(({ owner, index, cell, mechanics }, rank) => createUnitState({
    referenceId: REFERENCE_BASE[owner] + index,
    owner,
    x: cell.x,
    y: cell.y,
    facing: 0,
    mechanics,
    acquisitionRank: rank,
    acquisitionCount: roster.length,
  }));
  return {
    units,
    map: buildArenaPhysicsMap(mapFixture),
    diplomacyByOwner: formation.initial_diplomacy,
    triggers: formation.triggers,
    mechanics: { arbalester, hca },
  };
}


async function main() {
  const scenario = await loadScenario();
  const rows = [];
  const allStationaryIdleRows = [];
  const seedSummaries = [];
  for (const seed of SEEDS) {
    let world = createWorld({
      ratio: "27v18",
      units: scenario.units,
      map: scenario.map,
      openingSeed: seed,
      disableAiOrders: true,
      diplomacyByOwner: scenario.diplomacyByOwner,
      triggers: scenario.triggers,
    });
    let seedStationaryTicks = 0;
    let terminalTick = null;
    const hcaAliveTicksAfterFive = new Map();
    const hcaAttackStartsAfterFive = new Map();
    for (let tick = 1; tick < END_TICK; tick += 1) {
      const before = world;
      world = stepWorld(world);
      if (world.tick < START_TICK) continue;
      const beforeByReference = new Map(before.units.map((unit) => [unit.referenceId, unit]));
      const byReference = new Map(world.units.map((unit) => [unit.referenceId, unit]));
      const live = world.units.filter(({ alive }) => alive);
      for (const current of live.filter(({ owner }) => owner === OWNER_HCA)) {
        hcaAliveTicksAfterFive.set(
          current.referenceId,
          (hcaAliveTicksAfterFive.get(current.referenceId) ?? 0) + 1,
        );
      }
      for (const current of world.events.filter(({ type, actorId }) => (
        type === "attack-start" && byReference.get(actorId)?.owner === OWNER_HCA
      ))) {
        hcaAttackStartsAfterFive.set(
          current.actorId,
          (hcaAttackStartsAfterFive.get(current.actorId) ?? 0) + 1,
        );
      }
      const pursuitLoads = new Map();
      for (const current of live) {
        if (!Number.isSafeInteger(current.pursuitTargetId)) continue;
        pursuitLoads.set(
          current.pursuitTargetId,
          (pursuitLoads.get(current.pursuitTargetId) ?? 0) + 1,
        );
      }
      const blockedByActor = new Map(world.events
        .filter(({ type }) => type === "blocked")
        .map((entry) => [entry.actorId, entry]));
      const pairInteractions = createPairInteractionSnapshot({
        contactReservations: world.contactReservationState?.reservations ?? new Map(),
      });
      for (const unit of world.units) {
        if (!unit.alive || unit.owner !== OWNER_HCA) continue;
        const beforeUnit = beforeByReference.get(unit.referenceId);
        const displacement = beforeUnit
          ? Math.hypot(unit.x - beforeUnit.x, unit.y - beforeUnit.y)
          : 0;
        if (displacement * 60 > STATIONARY_SPEED_TPS + EPSILON) continue;
        const target = targetFor(unit, byReference);
        if (unit.action === "idle") {
          allStationaryIdleRows.push({
            seed,
            tick: world.tick,
            second: round(world.tick / 60, 4),
            unitId: unit.referenceId,
            targetId: target?.referenceId ?? null,
            targetState: !target
              ? "no-live-target"
              : isWithinReach(unit, target)
                ? "in-reach"
                : "out-of-reach",
            acquireTicks: unit.actionTimers.acquire,
            pursuitTargetId: unit.pursuitTargetId,
            engagedTargetId: unit.engagedTargetId,
            attackTargetId: unit.attackTargetId,
          });
        }
        if (!target || isWithinReach(unit, target)) continue;
        const targets = targetSummary(unit, byReference);
        const blockedEvent = blockedByActor.get(unit.referenceId) ?? null;
        const blockers = candidateBlockers(
          unit,
          beforeByReference,
          blockedEvent,
          pairInteractions,
        );
        const mapBlockers = candidateMapBlockers(
          unit,
          scenario.map,
          beforeByReference,
          blockedEvent,
        );
        const reachDistance = collisionRadius(unit) + collisionRadius(target)
          + unit.mechanics.attack_range_tiles;
        const outlineReachDistance = unit.mechanics.outline_size_tiles.x
          + target.mechanics.outline_size_tiles.x
          + unit.mechanics.attack_range_tiles + 0.1;
        const targetDistance = Math.hypot(target.x - unit.x, target.y - unit.y);
        const nearestAlly = nearest(unit, live, (other) => other.owner === unit.owner);
        const nearestEnemy = nearest(unit, live, (other) => other.owner !== unit.owner);
        const cause = causeFor(unit, target, targets, blockedEvent, displacement, unit.moveOrder);
        rows.push({
          seed,
          tick: world.tick,
          second: round(world.tick / 60, 4),
          unitId: unit.referenceId,
          x: round(unit.x, 5),
          y: round(unit.y, 5),
          action: unit.action,
          actionTimers: { ...unit.actionTimers },
          metricTargetId: target.referenceId,
          targetDistance: round(targetDistance, 5),
          collisionStopDistance: round(reachDistance, 5),
          outlineReachDistance: round(outlineReachDistance, 5),
          rangeExcess: round(targetDistance - outlineReachDistance, 5),
          displacement: round(displacement, 7),
          speedTilesPerSecond: round(displacement * 60, 5),
          cause,
          targets,
          moveOrder: unit.moveOrder ? { ...unit.moveOrder } : null,
          openingAcquisitionComplete: unit.openingAcquisitionComplete === true,
          avoidance: unit.avoidance ? { ...unit.avoidance } : null,
          blockedEvent: blockedEvent ? {
            proposedDx: blockedEvent.proposedDx,
            proposedDy: blockedEvent.proposedDy,
            actualDx: blockedEvent.actualDx,
            actualDy: blockedEvent.actualDy,
          } : null,
          candidateBlockers: blockers,
          candidateMapBlockers: mapBlockers,
          nearestAlly,
          nearestEnemy,
          pursuitLoadOnTarget: pursuitLoads.get(unit.pursuitTargetId) ?? 0,
          events: world.events.filter(({ actorId }) => actorId === unit.referenceId)
            .filter(({ type }) => type !== "blocked" && type !== "move")
            .map((entry) => ({ ...entry })),
        });
        seedStationaryTicks += 1;
      }
      const livePrincipalOwners = new Set(world.units
        .filter(({ alive, owner }) => alive && (owner === 2 || owner === 3))
        .map(({ owner }) => owner));
      if (livePrincipalOwners.size <= 1) {
        terminalTick = world.tick;
        break;
      }
    }
    const survivors = world.units.filter(({ alive }) => alive);
    const survivorOwners = [...new Set(survivors.map(({ owner }) => owner))];
    seedSummaries.push({
      seed,
      terminalTick: terminalTick ?? world.tick,
      winnerOwner: survivorOwners.length === 1 ? survivorOwners[0] : null,
      winnerHp: survivors.reduce((total, { hp }) => total + hp, 0),
      stationarySeekingUnitTicks: seedStationaryTicks,
      stationarySeekingUnitSeconds: round(seedStationaryTicks / 60, 4),
      hcaAttackStartsAfterFive: [...hcaAttackStartsAfterFive.values()]
        .reduce((total, count) => total + count, 0),
      hcaWithAttackStartAfterFive: hcaAttackStartsAfterFive.size,
      hcaWithoutAttackStartAfterFive: [...hcaAliveTicksAfterFive]
        .filter(([referenceId]) => !hcaAttackStartsAfterFive.has(referenceId))
        .map(([referenceId, aliveTicks]) => ({
          referenceId,
          aliveSeconds: round(aliveTicks / 60, 4),
        })),
    });
  }
  rows.sort((left, right) => (
    left.seed - right.seed || left.tick - right.tick || left.unitId - right.unitId
  ));
  const episodes = buildEpisodes(rows);
  const causeRows = aggregate(rows, "cause");
  const blockerRelationTicks = { ally: 0, enemy: 0 };
  const hardBlockerRelationTicks = { ally: 0, enemy: 0 };
  const interactionKindTicks = {};
  const solverRows = rows.filter(({ cause }) => cause === "movement_solver_rejected_attempt");
  for (const row of solverRows) {
    const relations = new Set(row.candidateBlockers.map(({ relation }) => relation));
    for (const relation of relations) blockerRelationTicks[relation] += 1;
    const hardRelations = new Set(row.candidateBlockers
      .filter(({ pathObstructs }) => pathObstructs)
      .map(({ relation }) => relation));
    for (const relation of hardRelations) hardBlockerRelationTicks[relation] += 1;
    for (const kind of new Set(
      row.candidateBlockers.map(({ interactionKind }) => interactionKind),
    )) {
      interactionKindTicks[kind] = (interactionKindTicks[kind] ?? 0) + 1;
    }
  }
  const avoidanceKinds = {};
  const avoidanceObstacleCounts = {};
  const avoidanceUnitCounts = {};
  for (const row of solverRows) {
    const avoidance = row.avoidance;
    const kind = avoidance?.blockerObstacleIndex !== undefined
      ? "map_obstacle_route"
      : avoidance?.blockerReferenceId !== undefined
        ? "unit_body_route"
        : "no_persistent_route";
    avoidanceKinds[kind] = (avoidanceKinds[kind] ?? 0) + 1;
    if (kind === "map_obstacle_route") {
      avoidanceObstacleCounts[avoidance.blockerObstacleIndex]
        = (avoidanceObstacleCounts[avoidance.blockerObstacleIndex] ?? 0) + 1;
    } else if (kind === "unit_body_route") {
      avoidanceUnitCounts[avoidance.blockerReferenceId]
        = (avoidanceUnitCounts[avoidance.blockerReferenceId] ?? 0) + 1;
    }
  }
  const output = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    scope: {
      matchup: "27 Chinese Arbalesters vs 18 Saracen Heavy Cavalry Archers",
      seeds: SEEDS,
      startSecond: 5,
      endTickLimitExclusive: END_TICK,
      ownerAnalyzed: OWNER_HCA,
      engineMutation: false,
    },
    metricDefinition: {
      stationarySeeking: "alive HCA with a live hostile target outside DAT outline attack reach and realized speed <= 0.05 tiles/s",
      metricTargetPriority: "attackTargetId, then engagedTargetId, then pursuitTargetId",
      outlineAttackReach: "center distance <= actor outline radius + target outline radius + DAT attack range + 0.1 tile tolerance",
      solverRejectedAttempt: "nonzero raw movement proposal and realized movement <= 0.05 tiles/s",
      candidateBlocker: "an alive body whose collision extent intersects the raw proposed landing point; diagnostic attribution, not a solver-internal proof",
    },
    scenarioFacts: {
      hcaAttackRange: scenario.mechanics.hca.attack_range_tiles,
      hcaOutlineRadius: scenario.mechanics.hca.outline_size_tiles.x,
      hcaCollisionRadius: scenario.mechanics.hca.collision_size_tiles.x,
      arbalesterOutlineRadius: scenario.mechanics.arbalester.outline_size_tiles.x,
      arbalesterCollisionRadius: scenario.mechanics.arbalester.collision_size_tiles.x,
      hcaVsArbalesterOutlineCenterReach: round(
        scenario.mechanics.hca.attack_range_tiles
          + scenario.mechanics.hca.outline_size_tiles.x
          + scenario.mechanics.arbalester.outline_size_tiles.x + 0.1,
        4,
      ),
      hcaVsArbalesterCollisionStopDistance: round(
        scenario.mechanics.hca.attack_range_tiles
          + scenario.mechanics.hca.collision_size_tiles.x
          + scenario.mechanics.arbalester.collision_size_tiles.x,
        4,
      ),
    },
    summary: {
      stationarySeekingUnitTicks: rows.length,
      stationarySeekingUnitSeconds: round(rows.length / 60, 4),
      meanStationaryHcaAcrossWindowAndSeeds: round(
        rows.length / Math.max(1, seedSummaries.reduce((total, seed) => (
          total + Math.max(0, seed.terminalTick - START_TICK)
        ), 0)),
        4,
      ),
      causeRows,
      solverRejectedShare: round(solverRows.length / Math.max(1, rows.length), 6),
      solverCandidateBlockerTickPresence: {
        ally: blockerRelationTicks.ally,
        enemy: blockerRelationTicks.enemy,
        neither: solverRows.filter(({ candidateBlockers }) => candidateBlockers.length === 0).length,
      },
      solverHardBlockerTickPresence: {
        ally: hardBlockerRelationTicks.ally,
        enemy: hardBlockerRelationTicks.enemy,
        map: solverRows.filter(({ candidateMapBlockers }) => candidateMapBlockers.length > 0).length,
        none: solverRows.filter((row) => row.candidateMapBlockers.length === 0
          && !row.candidateBlockers.some(({ pathObstructs }) => pathObstructs)).length,
      },
      solverCandidateInteractionKinds: Object.entries(interactionKindTicks)
        .map(([kind, ticks]) => ({ kind, ticks, unitSeconds: round(ticks / 60, 4) }))
        .sort((left, right) => right.ticks - left.ticks),
      solverAvoidanceState: Object.entries(avoidanceKinds)
        .map(([kind, ticks]) => ({ kind, ticks, unitSeconds: round(ticks / 60, 4) }))
        .sort((left, right) => right.ticks - left.ticks),
      topAvoidanceMapObstacles: Object.entries(avoidanceObstacleCounts)
        .map(([obstacleIndex, ticks]) => {
          const obstacle = scenario.map.obstacles[Number(obstacleIndex)];
          return {
            obstacleIndex: Number(obstacleIndex),
            referenceId: obstacle?.referenceId ?? null,
            x: obstacle?.x ?? null,
            y: obstacle?.y ?? null,
            ticks,
            unitSeconds: round(ticks / 60, 4),
          };
        })
        .sort((left, right) => right.ticks - left.ticks || left.obstacleIndex - right.obstacleIndex)
        .slice(0, 12),
      topAvoidanceUnitBlockers: Object.entries(avoidanceUnitCounts)
        .map(([referenceId, ticks]) => ({
          referenceId: Number(referenceId),
          ticks,
          unitSeconds: round(ticks / 60, 4),
        }))
        .sort((left, right) => right.ticks - left.ticks || left.referenceId - right.referenceId)
        .slice(0, 12),
      distinctHcaAffected: new Set(rows.map(({ unitId }) => unitId)).size,
      episodeCount: episodes.length,
      stationaryIdleActionUnitTicks: allStationaryIdleRows.length,
      stationaryIdleActionUnitSeconds: round(allStationaryIdleRows.length / 60, 4),
      stationaryIdleActionByTargetState: Object.entries(
        allStationaryIdleRows.reduce((counts, row) => {
          counts[row.targetState] = (counts[row.targetState] ?? 0) + 1;
          return counts;
        }, {}),
      ).map(([targetState, ticks]) => ({
        targetState,
        ticks,
        unitSeconds: round(ticks / 60, 4),
      })).sort((left, right) => right.ticks - left.ticks),
    },
    seedSummaries,
    perSecond: perSecond(rows, Math.max(...seedSummaries.map(({ terminalTick }) => terminalTick))),
    perUnit: perUnit(rows),
    episodes,
    representativeRows: rows
      .filter((row, index) => index === 0
        || row.tick % 60 === 0
        || row.cause !== rows[index - 1]?.cause
        || row.metricTargetId !== rows[index - 1]?.metricTargetId)
      .slice(0, 500),
    stationaryIdleActionRows: allStationaryIdleRows,
    sources: {
      engineWorld: "aoe2x/js_simulation/src/combat/world.js",
      localAvoidance: "aoe2x/js_simulation/src/combat/local-avoidance.js",
      scenarioFormation: "aoe2x/js_simulation/fixtures/current_ranged_golden_formations.json",
      map: "aoe2x/js_simulation/fixtures/golden_map.json",
      arbalesterMechanics: "aoe2x/js_simulation/fixtures/unit_stats/arbalester_chinese_imperial.json",
      hcaMechanics: "aoe2x/js_simulation/fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json",
    },
  };
  await mkdir(dirname(fileURLToPath(OUTPUT)), { recursive: true });
  await writeFile(OUTPUT, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${fileURLToPath(OUTPUT)}\n`);
}


await main();
