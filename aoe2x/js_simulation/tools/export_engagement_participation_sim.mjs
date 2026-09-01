// Export first-20-second engagement participation from the current simulation
// for the exact 27 Chinese Arbalester vs 18 Saracen Heavy Cavalry Archer
// ranged-vs-ranged golden scenario. The output is diagnostic evidence only;
// it does not feed runtime matchup parameters back into the engine.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";
import { unitBySlug } from "../src/unit-registry.js";


const ROOT = new URL("../", import.meta.url);
const DEFAULT_MATCHUP_KEY = "arbalester_vs_heavy_cav_archer";
const WINDOW_SECONDS = 20;
const OUTPUT = new URL(
  "../calibration/reports/arbalester_hca_participation_2026-08-30/"
    + "simulation_participation.json",
  import.meta.url,
);
const DEFAULT_CAPTURE_ROOT = new URL(
  "../calibration/live_observations/ranged_matrix_5x_2026-08-29/",
  import.meta.url,
);


function round(value, digits = 4) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}


function slugMechanics(unit, mechanics) {
  return Object.freeze({
    slug: unit.slug,
    attackRange: mechanics.attack_range_tiles,
    minRange: mechanics.ranged?.min_range_tiles ?? 0,
    outlineRadius: mechanics.outline_size_tiles.x,
    collisionRadius: mechanics.collision_size_tiles.x,
  });
}


function withinReach(actor, target, mechanicsBySlug) {
  const actorMechanics = mechanicsBySlug.get(actor.slug);
  const targetMechanics = mechanicsBySlug.get(target.slug);
  const distance = Math.hypot(target.x - actor.x, target.y - actor.y);
  if (actorMechanics.minRange > 0 && distance < actorMechanics.minRange - 1e-12) {
    return false;
  }
  return distance - actorMechanics.outlineRadius - targetMechanics.outlineRadius
    <= actorMechanics.attackRange + 0.1 + 1e-12;
}


function stateRows(run, mechanicsBySlug) {
  const snapshots = run.snapshots;
  const index = run.unitIndex;
  const rows = [];
  for (let snapshotIndex = 0; snapshotIndex < snapshots.length; snapshotIndex += 1) {
    const snapshot = snapshots[snapshotIndex];
    if (snapshot.tick >= WINDOW_SECONDS * 60) break;
    const prior = snapshots[Math.max(0, snapshotIndex - 1)];
    const priorById = new Map(prior.units.map((unit) => [unit[0], unit]));
    const byId = new Map(snapshot.units.map((unit) => [unit[0], unit]));
    const countsByOwner = {};
    const targetIdsByOwner = { 2: [], 3: [] };
    for (const owner of [2, 3]) {
      countsByOwner[owner] = {
        alive: 0,
        active: 0,
        firing: 0,
        notFiring: 0,
        windup: 0,
        reload: 0,
        inRangeNotFiring: 0,
        seekingMoving: 0,
        seekingStationary: 0,
        untargetedMoving: 0,
        untargetedStationary: 0,
        staleTarget: 0,
      };
    }
    for (const raw of snapshot.units) {
      const [referenceId, x, y, , , alive, action, pursuitTargetId,
        engagedTargetId, attackTargetId] = raw;
      if (alive !== 1) continue;
      const meta = index[referenceId];
      if (!meta || !countsByOwner[meta.owner]) continue;
      const counts = countsByOwner[meta.owner];
      counts.alive += 1;
      const actor = { referenceId, owner: meta.owner, slug: meta.slug, x, y };
      const rawTargetId = attackTargetId ?? engagedTargetId ?? pursuitTargetId;
      const targetRaw = rawTargetId === null || rawTargetId === undefined
        ? null
        : byId.get(rawTargetId);
      const targetMeta = targetRaw ? index[targetRaw[0]] : null;
      const target = targetRaw && targetRaw[5] === 1 && targetMeta
        && targetMeta.owner !== meta.owner
        ? {
          referenceId: targetRaw[0], owner: targetMeta.owner, slug: targetMeta.slug,
          x: targetRaw[1], y: targetRaw[2],
        }
        : null;
      if (target) targetIdsByOwner[meta.owner].push(target.referenceId);
      const inReach = target ? withinReach(actor, target, mechanicsBySlug) : false;
      const firing = target && inReach && action === "attacking";
      if (firing) {
        counts.active += 1;
        counts.firing += 1;
        counts.windup += 1;
        continue;
      }
      counts.notFiring += 1;
      if (action === "reload") {
        counts.reload += 1;
        if (target && inReach) counts.active += 1;
        continue;
      }
      const previous = priorById.get(referenceId);
      const dt = Math.max(1, snapshot.tick - prior.tick) / 60;
      const speed = previous
        ? Math.hypot(x - previous[1], y - previous[2]) / dt
        : 0;
      const moving = speed > 0.05;
      if (rawTargetId !== null && rawTargetId !== undefined && target === null) {
        counts.staleTarget += 1;
      }
      if (target && inReach) {
        counts.inRangeNotFiring += 1;
      } else if (target) {
        counts[moving ? "seekingMoving" : "seekingStationary"] += 1;
      } else {
        counts[moving ? "untargetedMoving" : "untargetedStationary"] += 1;
      }
    }
    for (const owner of [2, 3]) {
      const targetCounts = new Map();
      for (const targetId of targetIdsByOwner[owner]) {
        targetCounts.set(targetId, (targetCounts.get(targetId) ?? 0) + 1);
      }
      countsByOwner[owner].uniqueTargets = targetCounts.size;
      countsByOwner[owner].maximumTargetLoad = Math.max(0, ...targetCounts.values());
      const own = snapshot.units.filter((raw) => (
        raw[5] === 1 && index[raw[0]]?.owner === owner
      ));
      countsByOwner[owner].xSpan = own.length === 0
        ? 0
        : Math.max(...own.map((raw) => raw[1])) - Math.min(...own.map((raw) => raw[1]));
      countsByOwner[owner].ySpan = own.length === 0
        ? 0
        : Math.max(...own.map((raw) => raw[2])) - Math.min(...own.map((raw) => raw[2]));
    }
    rows.push({
      tick: snapshot.tick,
      countsByOwner,
      pairsByOwner: pairMetrics(snapshot, index, mechanicsBySlug),
    });
  }
  return rows;
}


function pairMetrics(snapshot, index, mechanicsBySlug) {
  const output = {};
  for (const owner of [2, 3]) {
    const units = snapshot.units.filter((raw) => (
      raw[5] === 1 && index[raw[0]]?.owner === owner
    ));
    let overlapPairs = 0;
    let overlapDepthSum = 0;
    let maxOverlapDepth = 0;
    let committedCommittedOverlapPairs = 0;
    let mixedCommittedOverlapPairs = 0;
    let uncommittedUncommittedOverlapPairs = 0;
    let tripleStacks = 0;
    let fourStacks = 0;
    let maxSharedTripleFraction = 0;
    let maxSharedFourFraction = 0;
    const overlapped = new Set();
    const nearest = new Map(units.map((raw) => [raw[0], Number.POSITIVE_INFINITY]));
    for (let leftIndex = 0; leftIndex < units.length; leftIndex += 1) {
      const left = units[leftIndex];
      const leftMechanics = mechanicsBySlug.get(index[left[0]].slug);
      for (let rightIndex = leftIndex + 1; rightIndex < units.length; rightIndex += 1) {
        const right = units[rightIndex];
        const rightMechanics = mechanicsBySlug.get(index[right[0]].slug);
        const distance = Math.max(
          Math.abs(right[1] - left[1]),
          Math.abs(right[2] - left[2]),
        );
        nearest.set(left[0], Math.min(nearest.get(left[0]), distance));
        nearest.set(right[0], Math.min(nearest.get(right[0]), distance));
        const overlapDepth = leftMechanics.collisionRadius
          + rightMechanics.collisionRadius - distance;
        if (overlapDepth > 1e-12) {
          overlapPairs += 1;
          overlapDepthSum += overlapDepth;
          maxOverlapDepth = Math.max(maxOverlapDepth, overlapDepth);
          overlapped.add(left[0]);
          overlapped.add(right[0]);
          const leftCommitted = left[6] === "attacking" || left[6] === "reload";
          const rightCommitted = right[6] === "attacking" || right[6] === "reload";
          if (leftCommitted && rightCommitted) committedCommittedOverlapPairs += 1;
          else if (leftCommitted || rightCommitted) mixedCommittedOverlapPairs += 1;
          else uncommittedUncommittedOverlapPairs += 1;
        }
      }
    }
    const sharedFraction = (members) => {
      const entries = members.map((raw) => ({
        raw,
        radius: mechanicsBySlug.get(index[raw[0]].slug).collisionRadius,
      }));
      const width = Math.max(0,
        Math.min(...entries.map(({ raw, radius }) => raw[1] + radius))
          - Math.max(...entries.map(({ raw, radius }) => raw[1] - radius)));
      const height = Math.max(0,
        Math.min(...entries.map(({ raw, radius }) => raw[2] + radius))
          - Math.max(...entries.map(({ raw, radius }) => raw[2] - radius)));
      const smallestArea = Math.min(...entries.map(({ radius }) => (2 * radius) ** 2));
      return width * height / smallestArea;
    };
    for (let a = 0; a < units.length; a += 1) {
      for (let b = a + 1; b < units.length; b += 1) {
        for (let c = b + 1; c < units.length; c += 1) {
          const tripleFraction = sharedFraction([units[a], units[b], units[c]]);
          if (tripleFraction <= 1e-12) continue;
          tripleStacks += 1;
          maxSharedTripleFraction = Math.max(maxSharedTripleFraction, tripleFraction);
          for (let d = c + 1; d < units.length; d += 1) {
            const fourFraction = sharedFraction([units[a], units[b], units[c], units[d]]);
            if (fourFraction <= 1e-12) continue;
            fourStacks += 1;
            maxSharedFourFraction = Math.max(maxSharedFourFraction, fourFraction);
          }
        }
      }
    }
    const nearestValues = [...nearest.values()].filter(Number.isFinite);
    output[owner] = {
      alive: units.length,
      possiblePairs: units.length * (units.length - 1) / 2,
      overlapPairs,
      overlapDepthSum,
      maxOverlapDepth,
      committedCommittedOverlapPairs,
      mixedCommittedOverlapPairs,
      uncommittedUncommittedOverlapPairs,
      tripleStacks,
      fourStacks,
      maxSharedTripleFraction,
      maxSharedFourFraction,
      overlappedUnits: overlapped.size,
      nearestDistanceSum: nearestValues.reduce((total, value) => total + value, 0),
      nearestDistanceCount: nearestValues.length,
    };
  }
  return output;
}


function summarizePairRows(rows, owner) {
  const source = rows.map(({ pairsByOwner }) => pairsByOwner[owner]);
  const sum = (field) => source.reduce((total, row) => total + row[field], 0);
  return {
    meanOverlapPairs: round(sum("overlapPairs") / Math.max(source.length, 1)),
    meanPossiblePairs: round(sum("possiblePairs") / Math.max(source.length, 1)),
    overlapPairShare: round(sum("overlapPairs") / Math.max(sum("possiblePairs"), 1), 6),
    meanOverlappedUnits: round(sum("overlappedUnits") / Math.max(source.length, 1)),
    overlappedUnitShare: round(sum("overlappedUnits") / Math.max(sum("alive"), 1), 6),
    meanOverlapDepth: round(sum("overlapDepthSum") / Math.max(sum("overlapPairs"), 1), 6),
    meanCommittedCommittedOverlapPairs: round(
      sum("committedCommittedOverlapPairs") / Math.max(source.length, 1),
    ),
    meanMixedCommittedOverlapPairs: round(
      sum("mixedCommittedOverlapPairs") / Math.max(source.length, 1),
    ),
    meanUncommittedUncommittedOverlapPairs: round(
      sum("uncommittedUncommittedOverlapPairs") / Math.max(source.length, 1),
    ),
    maxOverlapDepth: round(Math.max(0, ...source.map(({ maxOverlapDepth }) => maxOverlapDepth)), 6),
    meanTripleStacks: round(sum("tripleStacks") / Math.max(source.length, 1)),
    meanFourStacks: round(sum("fourStacks") / Math.max(source.length, 1)),
    maxSharedTripleFraction: round(Math.max(
      0,
      ...source.map(({ maxSharedTripleFraction }) => maxSharedTripleFraction),
    ), 6),
    maxSharedFourFraction: round(Math.max(
      0,
      ...source.map(({ maxSharedFourFraction }) => maxSharedFourFraction),
    ), 6),
    meanNearestFriendlyDistance: round(
      sum("nearestDistanceSum") / Math.max(sum("nearestDistanceCount"), 1), 6,
    ),
  };
}


function attackStartRanges(run, mechanicsBySlug) {
  const rows = [];
  for (const snapshot of run.snapshots) {
    if (snapshot.tick >= WINDOW_SECONDS * 60) break;
    const byId = new Map(snapshot.units.map((unit) => [unit[0], unit]));
    for (const event of snapshot.events) {
      if (event.type !== "attack-start") continue;
      const actorRaw = byId.get(event.actorId);
      const targetRaw = byId.get(event.targetId);
      const actorMeta = run.unitIndex[event.actorId];
      const targetMeta = run.unitIndex[event.targetId];
      if (!actorRaw || !targetRaw || !actorMeta || !targetMeta) continue;
      if (actorMeta.owner === targetMeta.owner) continue;
      const actorMechanics = mechanicsBySlug.get(actorMeta.slug);
      const targetMechanics = mechanicsBySlug.get(targetMeta.slug);
      if (!actorMechanics || !targetMechanics) continue;
      const centerDistance = Math.hypot(targetRaw[1] - actorRaw[1], targetRaw[2] - actorRaw[2]);
      const edgeDistance = centerDistance
        - actorMechanics.outlineRadius - targetMechanics.outlineRadius;
      rows.push({
        tick: snapshot.tick,
        second: snapshot.tick / 60,
        owner: actorMeta.owner,
        actorId: event.actorId,
        targetId: event.targetId,
        centerDistance: round(centerDistance, 6),
        edgeDistance: round(edgeDistance, 6),
        nominalRange: actorMechanics.attackRange,
        rangeUtilization: round(edgeDistance / actorMechanics.attackRange, 6),
        nominalHeadroom: round(actorMechanics.attackRange - edgeDistance, 6),
      });
    }
  }
  return rows;
}


function perSecond(run, mechanicsBySlug) {
  const rows = stateRows(run, mechanicsBySlug);
  const events = run.snapshots.flatMap(({ events }) => events);
  return Array.from({ length: WINDOW_SECONDS }, (_, second) => {
    const samples = rows.filter(({ tick }) => tick >= second * 60 && tick < (second + 1) * 60);
    const result = { second };
    for (const owner of [2, 3]) {
      const ownerRows = samples.map(({ countsByOwner }) => countsByOwner[owner]);
      const fields = Object.keys(ownerRows[0] ?? {});
      const metrics = Object.fromEntries(fields.map((field) => [
        field,
        round(ownerRows.reduce((total, row) => total + row[field], 0)
          / Math.max(1, ownerRows.length)),
      ]));
      const attackStarts = events.filter(({ type, tick, actorId }) => (
        type === "attack-start"
        && tick >= second * 60 && tick < (second + 1) * 60
        && indexOwner(run, actorId) === owner
      ));
      const damage = events.filter(({ type, tick, actorId }) => (
        type === "damage"
        && tick >= second * 60 && tick < (second + 1) * 60
        && indexOwner(run, actorId) === owner
      ));
      const canceled = events.filter(({ type, tick, actorId }) => (
        type === "attack-canceled"
        && tick >= second * 60 && tick < (second + 1) * 60
        && indexOwner(run, actorId) === owner
      ));
      const retargeted = events.filter(({ type, tick, actorId }) => (
        type === "attack-retargeted"
        && tick >= second * 60 && tick < (second + 1) * 60
        && indexOwner(run, actorId) === owner
      ));
      result[owner] = {
        ...metrics,
        ...summarizePairRows(samples, owner),
        shotStarts: attackStarts.length,
        uniqueShotStarters: new Set(attackStarts.map(({ actorId }) => actorId)).size,
        damageHits: damage.length,
        damageAmount: round(damage.reduce((total, { amount }) => total + amount, 0)),
        uniqueDamageDealers: new Set(damage.map(({ actorId }) => actorId)).size,
        attackCanceled: canceled.length,
        attackRetargeted: retargeted.length,
      };
    }
    return result;
  });
}


function indexOwner(run, referenceId) {
  return run.unitIndex[referenceId]?.owner ?? null;
}


function eventSummary(run) {
  const events = run.snapshots.flatMap(({ events }) => events);
  return Object.fromEntries([2, 3].map((owner) => {
    const owned = (type) => events.filter(({ type: current, actorId }) => (
      current === type && indexOwner(run, actorId) === owner
    ));
    const starts = owned("attack-start");
    const canceled = owned("attack-canceled");
    const retargeted = owned("attack-retargeted");
    const damage = owned("damage");
    const firstAcquisitionByActor = new Map();
    const firstAcquisitionSamples = [];
    for (const acquired of owned("pursuit-acquired")) {
      if (!firstAcquisitionByActor.has(acquired.actorId)) {
        firstAcquisitionByActor.set(acquired.actorId, acquired.tick / 60);
        const snapshot = run.snapshots[acquired.tick];
        const actor = snapshot?.units.find((raw) => raw[0] === acquired.actorId);
        const target = snapshot?.units.find((raw) => raw[0] === acquired.targetId);
        firstAcquisitionSamples.push({
          actorId: acquired.actorId,
          targetId: acquired.targetId,
          second: acquired.tick / 60,
          centerDistance: actor && target
            ? round(Math.hypot(target[1] - actor[1], target[2] - actor[2]), 6)
            : null,
        });
      }
    }
    const invalidations = owned("pursuit-invalidated")
      .filter(({ reason }) => reason === "target-dead");
    const reacquisitionDelays = invalidations.map((lost) => {
      const acquired = events.find(({ type, actorId, tick }) => (
        type === "pursuit-acquired"
        && actorId === lost.actorId
        && tick >= lost.tick
      ));
      return acquired ? (acquired.tick - lost.tick) / 60 : null;
    }).filter((value) => value !== null);
    return [owner, {
      attackStarts: starts.length,
      attackCanceled: canceled.length,
      attackCanceledByReason: Object.fromEntries([...new Set(canceled.map(({ reason }) => reason))]
        .sort().map((reason) => [
          reason,
          canceled.filter((event) => event.reason === reason).length,
        ])),
      attackRetargeted: retargeted.length,
      damageHits: damage.length,
      damageAmount: round(damage.reduce((total, { amount }) => total + amount, 0)),
      firstAcquisitionSeconds: [...firstAcquisitionByActor.values()]
        .sort((left, right) => left - right),
      firstAcquisitionSamples,
      targetDeathInvalidations: invalidations.length,
      targetDeathReacquisitions: reacquisitionDelays.length,
      targetDeathReacquisitionDelaySeconds: reacquisitionDelays.length === 0
        ? null
        : {
          mean: round(reacquisitionDelays.reduce((total, value) => total + value, 0)
            / reacquisitionDelays.length, 6),
          maximum: round(Math.max(...reacquisitionDelays), 6),
          immediate: reacquisitionDelays.filter((value) => value === 0).length,
        },
    }];
  }));
}


function meanRows(runs) {
  return Array.from({ length: WINDOW_SECONDS }, (_, second) => {
    const output = { second };
    for (const owner of [2, 3]) {
      const rows = runs.map((run) => run.perSecond[second][owner]);
      output[owner] = Object.fromEntries(Object.keys(rows[0]).map((field) => [
        field,
        round(rows.reduce((total, row) => total + row[field], 0) / rows.length),
      ]));
    }
    return output;
  });
}


async function main() {
  const singleRun = process.argv.includes("--single-run");
  const seedArgument = process.argv.find((value) => value.startsWith("--seed="));
  const outputArgument = process.argv.find((value) => value.startsWith("--output="));
  const matchupArgument = process.argv.find((value) => value.startsWith("--matchup="));
  const captureArgument = process.argv.find((value) => value.startsWith("--capture="));
  const pressureOwnerArgument = process.argv.find(
    (value) => value.startsWith("--ranged-target-pressure-owner="),
  );
  const windupOwnerArgument = process.argv.find(
    (value) => value.startsWith("--ranged-windup-retarget-owner="),
  );
  const matchupKey = matchupArgument?.slice("--matchup=".length) ?? DEFAULT_MATCHUP_KEY;
  const captureRoot = captureArgument === undefined
    ? DEFAULT_CAPTURE_ROOT
    : pathToFileURL(`${resolve(captureArgument.slice("--capture=".length))}\\`);
  const rangedTargetPressureOwner = pressureOwnerArgument === undefined
    ? null
    : Number(pressureOwnerArgument.slice("--ranged-target-pressure-owner=".length));
  const rangedWindupRetargetOwner = windupOwnerArgument === undefined
    ? null
    : Number(windupOwnerArgument.slice("--ranged-windup-retarget-owner=".length));
  if (rangedTargetPressureOwner !== null
      && (!Number.isSafeInteger(rangedTargetPressureOwner)
        || rangedTargetPressureOwner < 1)) {
    throw new RangeError("--ranged-target-pressure-owner must be a positive integer");
  }
  if (rangedWindupRetargetOwner !== null
      && (!Number.isSafeInteger(rangedWindupRetargetOwner)
        || rangedWindupRetargetOwner < 1)) {
    throw new RangeError("--ranged-windup-retarget-owner must be a positive integer");
  }
  const requestedSeed = seedArgument === undefined
    ? null
    : Number(seedArgument.slice("--seed=".length));
  if (requestedSeed !== null
      && (!Number.isSafeInteger(requestedSeed) || requestedSeed < 0)) {
    throw new RangeError("--seed must be a nonnegative integer");
  }
  const openingSeeds = requestedSeed === null
    ? (singleRun ? [0] : [0, 1, 2, 3, 4])
    : [requestedSeed];
  const outputPath = outputArgument === undefined
    ? fileURLToPath(OUTPUT)
    : resolve(outputArgument.slice("--output=".length));
  const [capture, formations, mapFixture] = await Promise.all([
    readFile(new URL("capture_manifest.json", captureRoot), "utf8").then(JSON.parse),
    readFile(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/golden_map.json", import.meta.url), "utf8").then(JSON.parse),
  ]);
  const matchup = capture.matchups[matchupKey];
  if (!matchup) throw new Error(`missing ${matchupKey} in capture manifest`);
  const side2 = unitBySlug(matchup.side1.slug);
  const side3 = unitBySlug(matchup.side2.slug);
  const [mechanics2, mechanics3] = await Promise.all([
    readFile(new URL(`../fixtures/unit_stats/${side2.fixture}`, import.meta.url), "utf8")
      .then(JSON.parse),
    readFile(new URL(`../fixtures/unit_stats/${side3.fixture}`, import.meta.url), "utf8")
      .then(JSON.parse),
  ]);
  const mechanicsBySlug = new Map([
    [side2.slug, slugMechanics(side2, mechanics2)],
    [side3.slug, slugMechanics(side3, mechanics3)],
  ]);
  const formation = formations.families[matchup.family];
  const auxiliaryUnit = formation.sides["4"]?.length
    ? {
      slug: "scout_cavalry",
      fixture: "scout_cavalry_spanish_imperial.json",
    }
    : null;
  if (auxiliaryUnit !== null) {
    const auxiliaryMechanics = JSON.parse(await readFile(new URL(
      `../fixtures/unit_stats/${auxiliaryUnit.fixture}`,
      import.meta.url,
    ), "utf8"));
    mechanicsBySlug.set(
      auxiliaryUnit.slug,
      slugMechanics(auxiliaryUnit, auxiliaryMechanics),
    );
  }
  const placementByOwner = {
    2: formation.sides["2"].map(({ position }) => ({ x: position.x, y: position.y })),
    3: formation.sides["3"].map(({ position }) => ({ x: position.x, y: position.y })),
  };
  const auxiliaryArmiesByOwner = formation.sides["4"]?.length
    ? {
      4: {
        slug: auxiliaryUnit.slug,
        cells: formation.sides["4"].map(({ position }) => ({
          x: position.x,
          y: position.y,
        })),
      },
    }
    : undefined;
  const victoryTeams = matchup.family === "ranged_vs_melee"
    ? [{ winnerOwner: 2, owners: [2, 4] }, { winnerOwner: 3, owners: [3] }]
    : matchup.family === "melee_vs_ranged"
      ? [{ winnerOwner: 2, owners: [2] }, { winnerOwner: 3, owners: [3, 4] }]
      : undefined;
  const map = buildArenaPhysicsMap(mapFixture);
  const runs = [];
  for (const openingSeed of openingSeeds) {
    const run = await runFight(pathToFileURL(fileURLToPath(ROOT)), {
      side2Slug: side2.slug,
      n2: matchup.side1.count,
      side3Slug: side3.slug,
      n3: matchup.side2.count,
      map,
      placementByOwner,
      ...(auxiliaryArmiesByOwner === undefined ? {} : { auxiliaryArmiesByOwner }),
      diplomacyByOwner: formation.initial_diplomacy,
      triggers: formation.triggers,
      ...(victoryTeams === undefined ? {} : { victoryTeams }),
      preserveOwnerOrientation: true,
      disableAiOrders: true,
      disableKiting: true,
      openingSeed,
      ...(rangedTargetPressureOwner === null
        ? {}
        : { rangedTargetPressureOwner }),
      ...(rangedWindupRetargetOwner === null
        ? {}
        : { rangedWindupRetargetOwner }),
    });
    runs.push({
      openingSeed,
      winnerOwner: run.winnerOwner,
      winnerHp: run.winnerHp,
      ticks: run.ticks,
      attackStartRanges: attackStartRanges(run, mechanicsBySlug),
      eventSummary: eventSummary(run),
      perSecond: perSecond(run, mechanicsBySlug),
    });
  }
  const output = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    matchup: {
      key: matchupKey,
      side2: { slug: side2.slug, civilization: matchup.side1.civ, count: matchup.side1.count },
      side3: { slug: side3.slug, civilization: matchup.side2.civ, count: matchup.side2.count },
    },
    metricDefinition: {
      windowSeconds: WINDOW_SECONDS,
      active: "alive, hostile target resolves, target is in the DAT attack envelope, and action is attacking or reload",
      firing: "alive, hostile target resolves inside the DAT attack envelope, and action is attacking/windup",
      notFiring: "alive minus firing; reload and every movement/targeting state remain included",
      seekingStationary: "alive with a valid hostile target outside attack range and speed <= 0.05 tiles/s",
      seekingMoving: "alive with a valid hostile target outside attack range and speed > 0.05 tiles/s",
      inRangeNotFiring: "alive with a valid hostile target inside attack range but not attacking/reloading",
      shotStarts: "attack-start engine events in the one-second bucket",
      engagementRange: "center and outline-edge distance at each attack-start event; nominalHeadroom is DAT range minus edge distance",
    },
    sources: {
      captureManifest: fileURLToPath(new URL("capture_manifest.json", captureRoot)),
      formationFixture: fileURLToPath(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url)),
      mapFixture: fileURLToPath(new URL("../fixtures/golden_map.json", import.meta.url)),
      engine: fileURLToPath(new URL("../src/fight.js", import.meta.url)),
    },
    config: {
      openingSeeds,
      rangedTargetPressureOwner,
      rangedOpportunityRetargeting: "generic-in-range-opportunity",
      rangedWindupRetargetOwner,
    },
    runs,
    meanPerSecond: meanRows(runs),
  };
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  process.stdout.write(`${outputPath}\n`);
}


await main();
