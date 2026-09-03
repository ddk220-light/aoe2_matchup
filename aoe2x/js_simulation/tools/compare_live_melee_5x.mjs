import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";
import { formationOpeningPatrol, validateFormationFixture } from "../src/formation-model.js";
import { TICKS_PER_SECOND } from "../src/simulation-clock.js";


const here = path.dirname(fileURLToPath(import.meta.url));
const simRoot = path.resolve(here, "..");
const captureRoot = path.resolve(process.argv[2]);
const side2Slug = process.argv[3];
const side3Slug = process.argv[4];
if (!process.argv[2] || !side2Slug || !side3Slug) {
  throw new Error("usage: node compare_live_melee_5x.mjs <capture-root> <side2-slug> <side3-slug>");
}


function rounded(value, digits = 4) {
  return Number(value.toFixed(digits));
}


function distribution(values) {
  const finite = values.filter(Number.isFinite);
  if (finite.length === 0) throw new Error("distribution has no finite values");
  const sorted = [...finite].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
  return {
    min: sorted[0],
    median: rounded(median),
    mean: rounded(finite.reduce((sum, value) => sum + value, 0) / finite.length),
    max: sorted.at(-1),
  };
}


function slotIndex(referenceId, owner) {
  return referenceId - (owner === 2 ? 9000 : 9500) + 1;
}


function engineOverlap(snapshots, unitIndex, firstDamageTick) {
  const phases = Object.fromEntries(["preDamage", "opening2s"].map((phase) => [phase, {
    frames: 0, alliedPairSum: 0, crossPairSum: 0,
    peakAlliedPairs: 0, peakCrossPairs: 0,
    maximumAlliedPenetration: 0, maximumCrossPenetration: 0,
  }]));
  for (const snapshot of snapshots) {
    if (snapshot.tick > firstDamageTick + 2 * TICKS_PER_SECOND) break;
    const live = snapshot.units.filter((unit) => unit[5] === 1);
    let alliedPairs = 0;
    let crossPairs = 0;
    let alliedPenetration = 0;
    let crossPenetration = 0;
    for (let leftIndex = 0; leftIndex < live.length; leftIndex += 1) {
      const left = live[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < live.length; rightIndex += 1) {
        const right = live[rightIndex];
        const threshold = unitIndex[left[0]].collisionRadius + unitIndex[right[0]].collisionRadius;
        const penetration = threshold - Math.hypot(left[1] - right[1], left[2] - right[2]);
        if (penetration <= 1e-9) continue;
        if (unitIndex[left[0]].owner === unitIndex[right[0]].owner) {
          alliedPairs += 1;
          alliedPenetration = Math.max(alliedPenetration, penetration);
        } else {
          crossPairs += 1;
          crossPenetration = Math.max(crossPenetration, penetration);
        }
      }
    }
    const selected = ["opening2s"];
    if (snapshot.tick <= firstDamageTick) selected.push("preDamage");
    for (const phase of selected) {
      const row = phases[phase];
      row.frames += 1;
      row.alliedPairSum += alliedPairs;
      row.crossPairSum += crossPairs;
      row.peakAlliedPairs = Math.max(row.peakAlliedPairs, alliedPairs);
      row.peakCrossPairs = Math.max(row.peakCrossPairs, crossPairs);
      row.maximumAlliedPenetration = Math.max(row.maximumAlliedPenetration, alliedPenetration);
      row.maximumCrossPenetration = Math.max(row.maximumCrossPenetration, crossPenetration);
    }
  }
  return Object.fromEntries(Object.entries(phases).map(([phase, row]) => [phase, {
    frames: row.frames,
    meanAlliedPairs: rounded(row.alliedPairSum / row.frames),
    meanCrossPairs: rounded(row.crossPairSum / row.frames),
    peakAlliedPairs: row.peakAlliedPairs,
    peakCrossPairs: row.peakCrossPairs,
    maximumAlliedPenetration: rounded(row.maximumAlliedPenetration),
    maximumCrossPenetration: rounded(row.maximumCrossPenetration),
  }]));
}


function acquisition(result, firstDamageTick) {
  const firstTargets = new Map();
  for (const snapshot of result.snapshots) {
    for (const unit of snapshot.units) {
      if (firstTargets.has(unit[0])) continue;
      const actorOwner = result.unitIndex[unit[0]].owner;
      const targetId = [unit[9], unit[8], unit[7]].find((id) => (
        id !== null && id !== undefined && result.unitIndex[id]?.owner !== actorOwner
      ));
      if (targetId === undefined) continue;
      firstTargets.set(unit[0], { targetId, tick: snapshot.tick });
    }
    if (snapshot.tick > firstDamageTick + 2 * TICKS_PER_SECOND
        && firstTargets.size === result.side2.count + result.side3.count) break;
  }
  return Object.fromEntries([2, 3].map((owner) => {
    const rows = [...firstTargets.entries()].filter(([id]) => result.unitIndex[id].owner === owner);
    const counts = new Map();
    for (const [, { targetId }] of rows) {
      const targetOwner = result.unitIndex[targetId].owner;
      const slot = slotIndex(targetId, targetOwner);
      counts.set(slot, (counts.get(slot) ?? 0) + 1);
    }
    return [`side${owner}`, {
      unitsWithEnemyTarget: rows.length,
      uniqueFirstTargets: counts.size,
      maximumUnitsSharingFirstTarget: Math.max(...counts.values()),
      firstTargetTimesSeconds: distribution(rows.map(([, row]) => row.tick / TICKS_PER_SECOND)),
      targetSlotCounts: Object.fromEntries([...counts.entries()].sort((a, b) => a[0] - b[0])),
    }];
  }));
}


function summarizeEngine(result, repeat) {
  const damage = result.snapshots.flatMap(({ events }) => events)
    .filter(({ type }) => type === "damage");
  const firstDamage = damage[0];
  if (!firstDamage) throw new Error(`engine repeat ${repeat} produced no damage`);
  const openingDamage = damage.filter(({ tick }) => (
    tick <= firstDamage.tick + 2 * TICKS_PER_SECOND
  ));
  const final = result.snapshots.at(-1);
  const living = final.units.filter((unit) => unit[5] === 1);
  const winner = result.winnerOwner;
  return {
    repeat,
    winnerOwner: winner,
    survivors: living.filter((unit) => result.unitIndex[unit[0]].owner === winner).length,
    winnerHp: rounded(living.filter((unit) => result.unitIndex[unit[0]].owner === winner)
      .reduce((sum, unit) => sum + unit[4], 0)),
    durationSeconds: rounded(result.ticks / TICKS_PER_SECOND),
    finalStateHash: result.finalStateHash,
    eventLogHash: result.eventLogHash,
    firstDamage: {
      tSeconds: rounded(firstDamage.tick / TICKS_PER_SECOND),
      attackerOwner: result.unitIndex[firstDamage.actorId].owner,
      attackerSlot: slotIndex(firstDamage.actorId, result.unitIndex[firstDamage.actorId].owner),
      victimOwner: result.unitIndex[firstDamage.targetId].owner,
      victimSlot: slotIndex(firstDamage.targetId, result.unitIndex[firstDamage.targetId].owner),
      damage: firstDamage.amount,
    },
    firstTwoSeconds: {
      hits: openingDamage.length,
      uniqueEngagementPairs: new Set(openingDamage.map(({ actorId, targetId }) => (
        `${actorId}:${targetId}`
      ))).size,
    },
    acquisition: acquisition(result, firstDamage.tick),
    overlap: engineOverlap(result.snapshots, result.unitIndex, firstDamage.tick),
  };
}


function summarizeGame(manifest, grpc) {
  return manifest.runs.map((manifestRun, index) => {
    const observed = grpc.runs[index];
    const winnerOwner = manifestRun.capture.winner === side2Slug ? 2 : 3;
    return {
      repeat: index + 1,
      winnerOwner,
      survivors: manifestRun.capture.survivors,
      winnerHp: manifestRun.capture.winner_hp,
      durationSeconds: observed.elimination_t_game_s,
      videoDurationSeconds: manifestRun.capture.elimination_time_s,
      firstDamage: observed.first_damage,
      firstTwoSeconds: observed.first_two_game_seconds,
      acquisition: observed.acquisition,
      overlap: observed.overlap,
      framesSha256: manifestRun.capture.frames_sha256,
    };
  });
}


function summary(gameRuns, engineRuns) {
  const metrics = (runs, source) => ({
    winnerSurvivors: distribution(runs.map((run) => run.survivors)),
    winnerHp: distribution(runs.map((run) => run.winnerHp)),
    durationSeconds: distribution(runs.map((run) => run.durationSeconds)),
    firstDamageSeconds: distribution(runs.map((run) => (
      source === "game" ? run.firstDamage.t_game_s : run.firstDamage.tSeconds
    ))),
    preDamagePeakAlliedOverlapPairs: distribution(runs.map((run) => (
      source === "game" ? run.overlap.pre_damage.peak_allied_pairs
        : run.overlap.preDamage.peakAlliedPairs
    ))),
    openingUniqueEngagementPairs: distribution(runs.map((run) => (
      source === "game" ? run.firstTwoSeconds.unique_engagement_pairs
        : run.firstTwoSeconds.uniqueEngagementPairs
    ))),
    side2UniqueFirstTargets: distribution(runs.map((run) => (
      source === "game" ? run.acquisition.side2.unique_first_targets
        : run.acquisition.side2.uniqueFirstTargets
    ))),
    side2MaximumFirstTargetFocus: distribution(runs.map((run) => (
      source === "game" ? run.acquisition.side2.maximum_units_sharing_first_target
        : run.acquisition.side2.maximumUnitsSharingFirstTarget
    ))),
    side3UniqueFirstTargets: distribution(runs.map((run) => (
      source === "game" ? run.acquisition.side3.unique_first_targets
        : run.acquisition.side3.uniqueFirstTargets
    ))),
    side3MaximumFirstTargetFocus: distribution(runs.map((run) => (
      source === "game" ? run.acquisition.side3.maximum_units_sharing_first_target
        : run.acquisition.side3.maximumUnitsSharingFirstTarget
    ))),
  });
  const game = metrics(gameRuns, "game");
  const engine = metrics(engineRuns, "engine");
  return {
    winnerAgreement: engineRuns.every((engineRun) => (
      gameRuns.every((gameRun) => gameRun.winnerOwner === engineRun.winnerOwner)
    )),
    game,
    engine: {
      ...engine,
      uniqueOutcomeHashes: new Set(engineRuns.map((run) => (
        `${run.finalStateHash}:${run.eventLogHash}`
      ))).size,
    },
    deltasVsGameMean: {
      winnerSurvivors: rounded(engine.winnerSurvivors.mean - game.winnerSurvivors.mean),
      winnerHp: rounded(engine.winnerHp.mean - game.winnerHp.mean),
      durationSeconds: rounded(engine.durationSeconds.mean - game.durationSeconds.mean),
      firstDamageSeconds: rounded(engine.firstDamageSeconds.mean - game.firstDamageSeconds.mean),
    },
  };
}


const [mapBody, formationBody, captureBody, grpcBody] = await Promise.all([
  readFile(path.join(simRoot, "fixtures", "golden_map.json"), "utf8"),
  readFile(path.join(simRoot, "fixtures", "golden_formation_27v27.json"), "utf8"),
  readFile(path.join(captureRoot, "capture_manifest.json"), "utf8"),
  readFile(path.join(captureRoot, "grpc_opening_variance.json"), "utf8"),
]);
const map = buildArenaPhysicsMap(JSON.parse(mapBody));
const formation = validateFormationFixture(JSON.parse(formationBody));
const manifest = JSON.parse(captureBody);
const grpc = JSON.parse(grpcBody);
const placementByOwner = Object.freeze(Object.fromEntries([2, 3].map((owner) => [
  owner,
  Object.freeze(formation.sides[String(owner)].map(({ position }) => Object.freeze({
    x: position.x, y: position.y,
  }))),
])));
const gameRuns = summarizeGame(manifest, grpc);
const engineRuns = [];
for (let repeat = 1; repeat <= 5; repeat += 1) {
  const result = await runFight(pathToFileURL(`${simRoot}${path.sep}`), {
    side2Slug,
    n2: manifest.matchup.player2.count,
    side3Slug,
    n3: manifest.matchup.player3.count,
    map,
    placementByOwner,
    openingPatrolByOwner: formationOpeningPatrol(formation),
    openingSeed: repeat - 1,
    disableAiOrders: true,
    displayCivBySide: {
      2: manifest.matchup.player2.civ,
      3: manifest.matchup.player3.civ,
    },
  });
  const row = summarizeEngine(result, repeat);
  engineRuns.push(row);
  process.stdout.write(`${JSON.stringify(row)}\n`);
}
const report = {
  schemaVersion: 1,
  matchup: grpc.matchup,
  sourceGoldenSha256: manifest.golden.sha256,
  overlapMetric: "Euclidean center distance below the sum of sourced collision radii",
  aiOrderPolicy: "disabled; first acquisition varies only through the generic opening seed",
  gameRuns,
  engineRuns,
  summary: summary(gameRuns, engineRuns),
};
await writeFile(path.join(captureRoot, "game_vs_engine_comparison.json"),
  `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(report.summary, null, 2)}\n`);
