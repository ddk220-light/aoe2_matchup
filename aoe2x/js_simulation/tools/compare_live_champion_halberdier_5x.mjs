import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";
import {
  formationOpeningPatrol,
  validateFormationFixture,
} from "../src/formation-model.js";
import { TICKS_PER_SECOND } from "../src/simulation-clock.js";


const here = path.dirname(fileURLToPath(import.meta.url));
const simRoot = path.resolve(here, "..");
const defaultCaptureRoot = path.join(
  simRoot,
  "calibration",
  "live_observations",
  "spanish_champion_vs_halberdier_5x_2026-08-28",
);


function rounded(value, digits = 4) {
  return Number(value.toFixed(digits));
}


function distribution(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
  return Object.freeze({
    min: Math.min(...values),
    median: rounded(median),
    mean: rounded(values.reduce((total, value) => total + value, 0) / values.length),
    max: Math.max(...values),
  });
}


function slotIndex(referenceId, owner) {
  return referenceId - (owner === 2 ? 9000 : 9500) + 1;
}


function openingOverlap(snapshots, unitIndex, firstDamageTick) {
  const phases = Object.fromEntries(["preDamage", "opening2s", "wholeFight"].map((phase) => [
    phase,
    {
      frames: 0,
      alliedPairSum: 0,
      crossPairSum: 0,
      alliedOverlapFrames: 0,
      crossOverlapFrames: 0,
      peakAlliedPairs: 0,
      peakCrossPairs: 0,
      maximumAlliedPenetration: 0,
      maximumCrossPenetration: 0,
      alliedUnits: new Set(),
      crossUnits: new Set(),
    },
  ]));

  for (const snapshot of snapshots) {
    const live = snapshot.units.filter((unit) => unit[5] === 1);
    let alliedPairs = 0;
    let crossPairs = 0;
    let alliedPenetration = 0;
    let crossPenetration = 0;
    const alliedUnits = new Set();
    const crossUnits = new Set();
    for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
      const left = live[leftIndex];
      const leftMeta = unitIndex[left[0]];
      for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
        const right = live[rightIndex];
        const rightMeta = unitIndex[right[0]];
        const threshold = leftMeta.collisionRadius + rightMeta.collisionRadius;
        const penetration = threshold - Math.hypot(left[1] - right[1], left[2] - right[2]);
        if (penetration <= 1e-9) continue;
        if (leftMeta.owner === rightMeta.owner) {
          alliedPairs += 1;
          alliedPenetration = Math.max(alliedPenetration, penetration);
          alliedUnits.add(left[0]);
          alliedUnits.add(right[0]);
        } else {
          crossPairs += 1;
          crossPenetration = Math.max(crossPenetration, penetration);
          crossUnits.add(left[0]);
          crossUnits.add(right[0]);
        }
      }
    }
    const selected = ["wholeFight"];
    if (snapshot.tick <= firstDamageTick) selected.push("preDamage");
    if (snapshot.tick <= firstDamageTick + (2 * TICKS_PER_SECOND)) selected.push("opening2s");
    for (const phase of selected) {
      const row = phases[phase];
      row.frames += 1;
      row.alliedPairSum += alliedPairs;
      row.crossPairSum += crossPairs;
      row.alliedOverlapFrames += Number(alliedPairs > 0);
      row.crossOverlapFrames += Number(crossPairs > 0);
      row.peakAlliedPairs = Math.max(row.peakAlliedPairs, alliedPairs);
      row.peakCrossPairs = Math.max(row.peakCrossPairs, crossPairs);
      row.maximumAlliedPenetration = Math.max(
        row.maximumAlliedPenetration, alliedPenetration,
      );
      row.maximumCrossPenetration = Math.max(
        row.maximumCrossPenetration, crossPenetration,
      );
      alliedUnits.forEach((id) => row.alliedUnits.add(id));
      crossUnits.forEach((id) => row.crossUnits.add(id));
    }
  }

  return Object.fromEntries(Object.entries(phases).map(([phase, row]) => [phase, {
    frames: row.frames,
    meanAlliedPairs: rounded(row.alliedPairSum / row.frames),
    meanCrossPairs: rounded(row.crossPairSum / row.frames),
    alliedOverlapFrameShare: rounded(row.alliedOverlapFrames / row.frames),
    crossOverlapFrameShare: rounded(row.crossOverlapFrames / row.frames),
    peakAlliedPairs: row.peakAlliedPairs,
    peakCrossPairs: row.peakCrossPairs,
    maximumAlliedPenetration: rounded(row.maximumAlliedPenetration),
    maximumCrossPenetration: rounded(row.maximumCrossPenetration),
    alliedUnitsEverOverlapping: row.alliedUnits.size,
    crossUnitsEverOverlapping: row.crossUnits.size,
  }]));
}


function openingCheckpoints(snapshots, unitIndex) {
  return [0, 1, 2, 3, 4, 5, 6].map((seconds) => {
    const targetTick = seconds * TICKS_PER_SECOND;
    const snapshot = snapshots.find(({ tick }) => tick >= targetTick) ?? snapshots.at(-1);
    const row = { seconds: rounded(snapshot.tick / TICKS_PER_SECOND) };
    let totalPairs = 0;
    for (const owner of [2, 3]) {
      const units = snapshot.units.filter((unit) => (
        unit[5] === 1 && unitIndex[unit[0]].owner === owner
      ));
      let pairs = 0;
      let maximumPenetration = 0;
      for (let left = 0; left < units.length; left += 1) {
        for (let right = left + 1; right < units.length; right += 1) {
          const threshold = unitIndex[units[left][0]].collisionRadius
            + unitIndex[units[right][0]].collisionRadius;
          const penetration = threshold - Math.hypot(
            units[left][1] - units[right][1],
            units[left][2] - units[right][2],
          );
          if (penetration > 1e-9) {
            pairs += 1;
            maximumPenetration = Math.max(maximumPenetration, penetration);
          }
        }
      }
      totalPairs += pairs;
      const xs = units.map((unit) => unit[1]);
      const ys = units.map((unit) => unit[2]);
      row[`side${owner}`] = {
        centerX: rounded(xs.reduce((sum, value) => sum + value, 0) / xs.length),
        centerY: rounded(ys.reduce((sum, value) => sum + value, 0) / ys.length),
        width: rounded(Math.max(...xs) - Math.min(...xs)),
        height: rounded(Math.max(...ys) - Math.min(...ys)),
        alliedPairs: pairs,
        maximumPenetration: rounded(maximumPenetration),
      };
    }
    row.alliedPairs = totalPairs;
    return row;
  });
}


function summarizeEngineRun(result, repeat) {
  const events = result.snapshots.flatMap(({ events }) => events);
  const damage = events.filter(({ type }) => type === "damage");
  const firstDamage = damage[0];
  const firstDamageByActor = new Map();
  for (const event of damage) {
    if (!firstDamageByActor.has(event.actorId)) firstDamageByActor.set(event.actorId, event.tick);
  }
  const openingDamage = damage.filter(
    ({ tick }) => tick <= firstDamage.tick + (2 * TICKS_PER_SECOND),
  );
  const firstTarget = new Map();
  const lastTarget = new Map();
  const targetChanges = new Map();
  const movement = new Map();
  for (const snapshot of result.snapshots) {
    const byId = new Map(snapshot.units.map((unit) => [unit[0], unit]));
    for (const unit of snapshot.units) {
      const actorId = unit[0];
      const actorOwner = result.unitIndex[actorId].owner;
      if (!movement.has(actorId)) {
        movement.set(actorId, { lastX: unit[1], lastY: unit[2], pathBeforeFirstDamage: 0 });
      }
      const movementRow = movement.get(actorId);
      const step = Math.hypot(unit[1] - movementRow.lastX, unit[2] - movementRow.lastY);
      if (snapshot.tick <= (firstDamageByActor.get(actorId) ?? firstDamage.tick)) {
        movementRow.pathBeforeFirstDamage += step;
      }
      movementRow.lastX = unit[1];
      movementRow.lastY = unit[2];
      const candidates = [unit[9], unit[8], unit[7]];
      const targetId = candidates.find((id) => (
        id !== null && id !== undefined
        && result.unitIndex[id]?.owner !== actorOwner
      ));
      if (targetId === undefined) continue;
      if (!firstTarget.has(actorId)) {
        const target = byId.get(targetId);
        firstTarget.set(actorId, {
          tick: snapshot.tick,
          targetId,
          distance: target ? Math.hypot(unit[1] - target[1], unit[2] - target[2]) : null,
        });
      }
      if (snapshot.tick <= firstDamage.tick && lastTarget.has(actorId)
          && lastTarget.get(actorId) !== targetId) {
        targetChanges.set(actorId, (targetChanges.get(actorId) ?? 0) + 1);
      }
      lastTarget.set(actorId, targetId);
    }
  }
  const acquisition = {};
  for (const owner of [2, 3]) {
    const rows = [...firstTarget.entries()]
      .filter(([actorId]) => result.unitIndex[actorId].owner === owner);
    const targetCounts = new Map();
    for (const [, { targetId }] of rows) {
      const targetOwner = result.unitIndex[targetId].owner;
      const targetSlot = slotIndex(targetId, targetOwner);
      targetCounts.set(targetSlot, (targetCounts.get(targetSlot) ?? 0) + 1);
    }
    acquisition[`side${owner}`] = {
      units: result[`side${owner}`].count,
      unitsWithEnemyTarget: rows.length,
      uniqueFirstTargets: targetCounts.size,
      maximumUnitsSharingFirstTarget: Math.max(...targetCounts.values()),
      firstTargetTimesSeconds: distribution(
        rows.map(([, { tick }]) => tick / TICKS_PER_SECOND),
      ),
      firstTargetDistances: distribution(
        rows.map(([, { distance }]) => distance).filter((value) => value !== null),
      ),
      pathBeforeFirstDamageDealt: distribution(
        rows.map(([actorId]) => movement.get(actorId).pathBeforeFirstDamage),
      ),
      targetChangesBeforeFirstDamage: rows.reduce(
        (total, [actorId]) => total + (targetChanges.get(actorId) ?? 0), 0,
      ),
      targetSlotCounts: Object.fromEntries([...targetCounts.entries()].sort((a, b) => a[0] - b[0])),
    };
  }

  const final = result.snapshots.at(-1);
  const living = final.units.filter((unit) => unit[5] === 1);
  const survivorsByOwner = Object.fromEntries([2, 3].map((owner) => [
    owner,
    living.filter((unit) => result.unitIndex[unit[0]].owner === owner).length,
  ]));
  const hpByOwner = Object.fromEntries([2, 3].map((owner) => [
    owner,
    living.filter((unit) => result.unitIndex[unit[0]].owner === owner)
      .reduce((total, unit) => total + unit[4], 0),
  ]));
  const uniqueEngagementPairs = new Set(
    openingDamage.map(({ actorId, targetId }) => `${actorId}:${targetId}`),
  ).size;
  return {
    repeat,
    winnerOwner: result.winnerOwner,
    survivors: survivorsByOwner[result.winnerOwner],
    winnerHp: rounded(hpByOwner[result.winnerOwner]),
    ticks: result.ticks,
    durationSeconds: rounded(result.ticks / TICKS_PER_SECOND),
    finalStateHash: result.finalStateHash,
    eventLogHash: result.eventLogHash,
    firstDamage: {
      tick: firstDamage.tick,
      tSeconds: rounded(firstDamage.tick / TICKS_PER_SECOND),
      attackerOwner: result.unitIndex[firstDamage.actorId].owner,
      attackerSlot: slotIndex(firstDamage.actorId, result.unitIndex[firstDamage.actorId].owner),
      victimOwner: result.unitIndex[firstDamage.targetId].owner,
      victimSlot: slotIndex(firstDamage.targetId, result.unitIndex[firstDamage.targetId].owner),
      damage: firstDamage.amount,
    },
    firstTwoSeconds: {
      hits: openingDamage.length,
      uniqueAttackers: new Set(openingDamage.map(({ actorId }) => actorId)).size,
      uniqueVictims: new Set(openingDamage.map(({ targetId }) => targetId)).size,
      uniqueEngagementPairs,
      hitsBySide: Object.fromEntries([2, 3].map((owner) => [
        owner,
        openingDamage.filter(({ actorId }) => result.unitIndex[actorId].owner === owner).length,
      ])),
    },
    acquisition,
    overlap: openingOverlap(result.snapshots, result.unitIndex, firstDamage.tick),
    openingCheckpoints: openingCheckpoints(result.snapshots, result.unitIndex),
  };
}


function gameRunSummary(captureManifest, grpcReport, decodedSummary, decodedMeta) {
  return captureManifest.runs.map((manifestRun, index) => {
    const grpc = grpcReport.runs[index];
    const summary = decodedSummary[index];
    const meta = decodedMeta[index];
    return {
      repeat: index + 1,
      winnerOwner: summary.outcome === "side2" ? 2 : 3,
      survivors: summary.sides[summary.outcome].survivors,
      winnerHp: summary.sides[summary.outcome].hp_remaining,
      damageEvents: meta.damage_events,
      firstDamageGameSeconds: grpc.first_damage.t_game_s,
      firstDamageAttackerSlot: grpc.first_damage.attacker_slot,
      firstDamageVictimSlot: grpc.first_damage.victim_slot,
      firstTwoSeconds: grpc.first_two_game_seconds,
      acquisition: grpc.acquisition,
      movement: Object.fromEntries([2, 3].map((owner) => [
        `side${owner}`,
        {
          pathBeforeFirstDamageDealt: distribution(
            grpc.units
              .filter((unit) => unit.owner === owner)
              .map((unit) => unit.path_before_first_damage_dealt),
          ),
        },
      ])),
      overlap: grpc.overlap,
      framesSha256: manifestRun.capture.frames_sha256,
    };
  });
}


function comparisonSummary(gameRuns, engineRuns) {
  const engine = engineRuns[0];
  const engineHashes = new Set(engineRuns.map(
    ({ finalStateHash, eventLogHash }) => `${finalStateHash}:${eventLogHash}`,
  ));
  return {
    winnerAgreement: gameRuns.every(({ winnerOwner }) => winnerOwner === engine.winnerOwner),
    game: {
      championSurvivors: distribution(gameRuns.map(({ survivors }) => survivors)),
      championHp: distribution(gameRuns.map(({ winnerHp }) => winnerHp)),
      damageEvents: distribution(gameRuns.map(({ damageEvents }) => damageEvents)),
      firstDamageGameSeconds: distribution(gameRuns.map(({ firstDamageGameSeconds }) => firstDamageGameSeconds)),
      firstDamageAttackerSlots: gameRuns.map(({ firstDamageAttackerSlot }) => firstDamageAttackerSlot),
      firstDamageVictimSlots: gameRuns.map(({ firstDamageVictimSlot }) => firstDamageVictimSlot),
      preDamagePeakAlliedOverlapPairs: distribution(
        gameRuns.map(({ overlap }) => overlap.pre_damage.peak_allied_pairs),
      ),
      openingUniqueEngagementPairs: distribution(
        gameRuns.map(({ firstTwoSeconds }) => firstTwoSeconds.unique_engagement_pairs),
      ),
      championUniqueFirstTargets: distribution(
        gameRuns.map(({ acquisition }) => acquisition.side2.unique_first_targets),
      ),
      championMaximumFirstTargetFocus: distribution(
        gameRuns.map(({ acquisition }) => acquisition.side2.maximum_units_sharing_first_target),
      ),
      halberdierUniqueFirstTargets: distribution(
        gameRuns.map(({ acquisition }) => acquisition.side3.unique_first_targets),
      ),
      halberdierMaximumFirstTargetFocus: distribution(
        gameRuns.map(({ acquisition }) => acquisition.side3.maximum_units_sharing_first_target),
      ),
      championMeanPathBeforeFirstDamage: distribution(
        gameRuns.map(({ movement }) => movement.side2.pathBeforeFirstDamageDealt.mean),
      ),
      halberdierMeanPathBeforeFirstDamage: distribution(
        gameRuns.map(({ movement }) => movement.side3.pathBeforeFirstDamageDealt.mean),
      ),
    },
    engine: {
      deterministicAcrossFiveRuns: engineHashes.size === 1,
      uniqueOutcomeHashes: engineHashes.size,
      championSurvivors: distribution(engineRuns.map(({ survivors }) => survivors)),
      championHp: distribution(engineRuns.map(({ winnerHp }) => winnerHp)),
      durationSeconds: distribution(engineRuns.map(({ durationSeconds }) => durationSeconds)),
      firstDamageSeconds: distribution(engineRuns.map(({ firstDamage }) => firstDamage.tSeconds)),
      firstDamageAttackerSlots: engineRuns.map(({ firstDamage }) => firstDamage.attackerSlot),
      firstDamageVictimSlots: engineRuns.map(({ firstDamage }) => firstDamage.victimSlot),
      preDamagePeakAlliedOverlapPairs: distribution(
        engineRuns.map(({ overlap }) => overlap.preDamage.peakAlliedPairs),
      ),
      openingUniqueEngagementPairs: distribution(
        engineRuns.map(({ firstTwoSeconds }) => firstTwoSeconds.uniqueEngagementPairs),
      ),
      championUniqueFirstTargets: distribution(
        engineRuns.map(({ acquisition }) => acquisition.side2.uniqueFirstTargets),
      ),
      championMaximumFirstTargetFocus: distribution(
        engineRuns.map(({ acquisition }) => acquisition.side2.maximumUnitsSharingFirstTarget),
      ),
      halberdierUniqueFirstTargets: distribution(
        engineRuns.map(({ acquisition }) => acquisition.side3.uniqueFirstTargets),
      ),
      halberdierMaximumFirstTargetFocus: distribution(
        engineRuns.map(({ acquisition }) => acquisition.side3.maximumUnitsSharingFirstTarget),
      ),
      championMeanPathBeforeFirstDamage: distribution(
        engineRuns.map(({ acquisition }) => acquisition.side2.pathBeforeFirstDamageDealt.mean),
      ),
      halberdierMeanPathBeforeFirstDamage: distribution(
        engineRuns.map(({ acquisition }) => acquisition.side3.pathBeforeFirstDamageDealt.mean),
      ),
      outcomeHashes: engineRuns.map(({ finalStateHash, eventLogHash }) => ({
        finalStateHash,
        eventLogHash,
      })),
    },
    deltasVsGameMean: {
      championSurvivors: rounded(distribution(engineRuns.map(({ survivors }) => survivors)).mean
        - distribution(
        gameRuns.map(({ survivors }) => survivors),
      ).mean),
      championHp: rounded(distribution(engineRuns.map(({ winnerHp }) => winnerHp)).mean
        - distribution(
        gameRuns.map(({ winnerHp }) => winnerHp),
      ).mean),
      firstDamageSeconds: rounded(distribution(
        engineRuns.map(({ firstDamage }) => firstDamage.tSeconds),
      ).mean - distribution(
        gameRuns.map(({ firstDamageGameSeconds }) => firstDamageGameSeconds),
      ).mean),
    },
  };
}


async function main() {
  const captureRoot = path.resolve(process.argv[2] ?? defaultCaptureRoot);
  const engineRepeats = Number(process.env.AOE2X_ENGINE_REPEATS ?? 5);
  if (!Number.isSafeInteger(engineRepeats) || engineRepeats < 1 || engineRepeats > 5) {
    throw new RangeError("AOE2X_ENGINE_REPEATS must be an integer from 1 to 5");
  }
  const sweepOverride = process.env.AOE2X_SWEEP_OVERRIDE === undefined
    ? null
    : Number(process.env.AOE2X_SWEEP_OVERRIDE);
  if (sweepOverride !== null && (!Number.isFinite(sweepOverride) || sweepOverride < 0)) {
    throw new RangeError("AOE2X_SWEEP_OVERRIDE must be nonnegative and finite");
  }
  const [mapBody, formationBody, captureBody, grpcBody] = await Promise.all([
    readFile(path.join(simRoot, "fixtures", "golden_map.json"), "utf8"),
    readFile(path.join(simRoot, "fixtures", "golden_formation_27v27.json"), "utf8"),
    readFile(path.join(captureRoot, "capture_manifest.json"), "utf8"),
    readFile(path.join(captureRoot, "grpc_opening_variance.json"), "utf8"),
  ]);
  const map = buildArenaPhysicsMap(JSON.parse(mapBody));
  const formation = validateFormationFixture(JSON.parse(formationBody));
  const openingPatrolByOwner = formationOpeningPatrol(formation);
  const placementByOwner = Object.freeze({
    2: Object.freeze(formation.sides["2"].map(({ position }) => Object.freeze({
      x: position.x, y: position.y,
    }))),
    3: Object.freeze(formation.sides["3"].map(({ position }) => Object.freeze({
      x: position.x, y: position.y,
    }))),
  });
  const captureManifest = JSON.parse(captureBody);
  const grpcReport = JSON.parse(grpcBody);
  const firstAiOrderTimes = [];
  const decodedSummary = [];
  const decodedMeta = [];
  for (let repeat = 1; repeat <= 5; repeat += 1) {
    const decoded = path.join(captureRoot, `run_${String(repeat).padStart(3, "0")}`, "decoded");
    decodedSummary.push(JSON.parse(await readFile(
      path.join(decoded, "spanish_champion_vs_halberdier.summary.json"), "utf8",
    )));
    decodedMeta.push(JSON.parse(await readFile(
      path.join(decoded, "spanish_champion_vs_halberdier.meta.json"), "utf8",
    )));
    const commandRows = (await readFile(
      path.join(decoded, "spanish_champion_vs_halberdier.commands.jsonl"), "utf8",
    )).trim().split(/\r?\n/u).map((row) => JSON.parse(row));
    const firstAiOrder = commandRows.find(({ kind }) => kind === "aiOrder");
    if (!firstAiOrder || !Number.isFinite(firstAiOrder.t)) {
      throw new Error(`run ${repeat} has no finite first aiOrder timestamp`);
    }
    firstAiOrderTimes.push(firstAiOrder.t);
  }
  const aiOrderSweepStartSeconds = firstAiOrderTimes.reduce((sum, value) => sum + value, 0)
    / firstAiOrderTimes.length;
  const gameRuns = gameRunSummary(captureManifest, grpcReport, decodedSummary, decodedMeta);
  const engineRuns = [];
  for (let repeat = 1; repeat <= engineRepeats; repeat += 1) {
    const result = await runFight(
      pathToFileURL(`${simRoot}${path.sep}`),
      {
        side2Slug: "champion",
        n2: 23,
        side3Slug: "halberdier",
        n3: 27,
        map,
        placementByOwner,
        openingPatrolByOwner,
        openingSeed: repeat - 1,
        ...(sweepOverride === null
          ? { disableAiOrders: true }
          : { aiOrderSweepStartSeconds: sweepOverride }),
        displayCivBySide: { 2: "Spanish", 3: "Spanish" },
      },
    );
    const summary = summarizeEngineRun(result, repeat);
    engineRuns.push(summary);
    process.stdout.write(`${JSON.stringify(summary)}\n`);
  }
  const report = {
    schemaVersion: 1,
    matchup: "23 Spanish Champions vs 27 Spanish Halberdiers",
    sourceGoldenSha256: captureManifest.golden.sha256,
    clocks: {
      game: "raw gRPC game seconds",
      engine: `ticks / ${TICKS_PER_SECOND}`,
    },
    overlapMetric: "center distance < sum of the 0.2-tile collision radii",
    observedAiOrderSweepStartSeconds: {
      runs: firstAiOrderTimes,
      mean: aiOrderSweepStartSeconds,
    },
    aiOrderPolicy: sweepOverride === null
      ? "disabled: current captures expose timestamps but not enough command semantics to reuse the legacy sweep"
      : `diagnostic sweep override at ${sweepOverride} seconds`,
    gameRuns,
    engineRuns,
    summary: comparisonSummary(gameRuns, engineRuns),
  };
  await writeFile(
    path.join(captureRoot, "game_vs_engine_comparison.json"),
    `${JSON.stringify(report, null, 2)}\n`,
    "utf8",
  );
  process.stdout.write(`${JSON.stringify(report.summary, null, 2)}\n`);
}


await main();
