// Compare the current engine with the five-repeat 2026-08-29 ranged matrix.
// Truth is read only from the fresh capture manifests; placements and patrols
// come from the SHA-pinned current golden scenarios.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildArenaPhysicsMap } from "../src/arena-physics-map.js";
import { runFight } from "../src/fight.js";
import { unitBySlug } from "../src/unit-registry.js";


const ROOT = new URL("../", import.meta.url);
const CAPTURE_ROOT = new URL(
  "../calibration/live_observations/ranged_matrix_5x_2026-08-29/",
  import.meta.url,
);
const FRESH_CAPTURE_ROOT = new URL(
  "../calibration/live_observations/remaining_six_fresh_5x_2026-08-31/",
  import.meta.url,
);
const DEFAULT_OUTPUT = new URL(
  "../calibration/reports/ranged_matrix_current_engine_2026-08-29/",
  import.meta.url,
);


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function summary(values) {
  return Object.freeze({
    mean: mean(values),
    min: Math.min(...values),
    max: Math.max(...values),
  });
}


function nullableSummary(values) {
  return values.length === 0 ? null : summary(values);
}


function positionInSnapshot(snapshot, referenceId) {
  const row = snapshot?.units.find(([id]) => id === referenceId);
  return row ? { x: row[1], y: row[2] } : null;
}


function eventDistance(snapshotByTick, current) {
  const snapshot = snapshotByTick.get(current.tick);
  const actor = positionInSnapshot(snapshot, current.actorId);
  const target = positionInSnapshot(snapshot, current.targetId);
  return actor && target ? Math.hypot(target.x - actor.x, target.y - actor.y) : null;
}


async function loadMechanics(unit) {
  return JSON.parse(await readFile(new URL(`../fixtures/unit_stats/${unit.fixture}`, import.meta.url)));
}


function score(owner, hp, startingHp) {
  const magnitude = 100 * hp / startingHp[owner];
  return owner === 2 ? -magnitude : magnitude;
}


function loadSummary(targetIds) {
  const counts = new Map();
  for (const targetId of targetIds) {
    counts.set(targetId, (counts.get(targetId) ?? 0) + 1);
  }
  const histogram = new Map();
  for (const load of counts.values()) {
    histogram.set(load, (histogram.get(load) ?? 0) + 1);
  }
  return {
    actors: targetIds.length,
    uniqueTargets: counts.size,
    maximumLoad: Math.max(0, ...counts.values()),
    loadHistogram: Object.fromEntries([...histogram].sort((left, right) => left[0] - right[0])),
    targetCounts: Object.fromEntries([...counts].sort((left, right) => left[0] - right[0])),
  };
}


function simulationMechanics(run) {
  const events = run.snapshots.flatMap(({ events }) => events);
  const ownerOf = (referenceId) => run.unitIndex[referenceId]?.owner;
  const snapshotByTick = new Map(run.snapshots.map((snapshot) => [snapshot.tick, snapshot]));
  const initialPositionById = new Map(run.snapshots[0].units.map(([
    referenceId, x, y,
  ]) => [referenceId, { x, y }]));
  const firstTargetByActor = new Map();
  const firstAcquisitionTickByActor = new Map();
  const firstAttackTickByActor = new Map();
  const firstAcquisitionByActor = new Map();
  const firstAttackByActor = new Map();
  for (const current of events) {
    if (current.type === "pursuit-acquired" && !firstTargetByActor.has(current.actorId)) {
      firstTargetByActor.set(current.actorId, current.targetId);
      firstAcquisitionTickByActor.set(current.actorId, current.tick);
      firstAcquisitionByActor.set(current.actorId, current);
    }
    if (current.type === "attack-start" && !firstAttackTickByActor.has(current.actorId)) {
      firstAttackTickByActor.set(current.actorId, current.tick);
      firstAttackByActor.set(current.actorId, current);
    }
  }
  const firstTargetDistributionByOwner = {};
  for (const owner of [2, 3, 4]) {
    const ownerEdges = [...firstTargetByActor]
      .filter(([actorId]) => ownerOf(actorId) === owner)
      .map(([actorId, targetId]) => ({ actorId, targetId }));
    const targets = ownerEdges.map(({ targetId }) => targetId);
    if (targets.length === 0) continue;
    const distances = ownerEdges.map(({ actorId, targetId }) => {
      const actor = initialPositionById.get(actorId);
      const target = initialPositionById.get(targetId);
      return Math.hypot(target.x - actor.x, target.y - actor.y);
    });
    firstTargetDistributionByOwner[owner] = {
      targets: Object.fromEntries(
        [...new Set(targets)].sort((left, right) => left - right).map((targetId) => [
          targetId,
          targets.filter((value) => value === targetId).length,
        ]),
      ),
      initialDistance: summary(distances),
    };
  }
  const damage = events.filter(({ type }) => type === "damage");
  const totalAttacksByOwner = Object.fromEntries([2, 3, 4].map((owner) => [
    owner,
    events.filter(({ type, actorId }) => (
      type === "attack-start" && ownerOf(actorId) === owner
    )).length,
  ]));
  const totalDamageByOwner = Object.fromEntries([2, 3, 4].map((owner) => {
    const rows = damage.filter(({ actorId }) => ownerOf(actorId) === owner);
    return [owner, {
      hits: rows.length,
      amount: rows.reduce((total, { amount }) => total + amount, 0),
    }];
  }));
  const totalDamageByOwnerAndTargetOwner = Object.fromEntries([2, 3, 4].map((owner) => [
    owner,
    Object.fromEntries([2, 3, 4]
      .filter((targetOwner) => targetOwner !== owner)
      .map((targetOwner) => {
        const rows = damage.filter(({ actorId, targetId }) => (
          ownerOf(actorId) === owner && ownerOf(targetId) === targetOwner
        ));
        return [targetOwner, {
          hits: rows.length,
          amount: rows.reduce((total, { amount }) => total + amount, 0),
        }];
      })),
  ]));
  const attackStartDistanceByOwnerAndTargetOwner = Object.fromEntries(
    [2, 3, 4].map((owner) => [
      owner,
      Object.fromEntries([2, 3, 4]
        .filter((targetOwner) => targetOwner !== owner)
        .map((targetOwner) => {
          const distances = events.filter(({ type, actorId, targetId }) => (
            type === "attack-start"
              && ownerOf(actorId) === owner && ownerOf(targetId) === targetOwner
          )).map((current) => eventDistance(snapshotByTick, current)).filter(Number.isFinite);
          return [targetOwner, nullableSummary(distances)];
        })),
    ]),
  );
  const firstDeathSecondsByOwner = Object.fromEntries([2, 3, 4].map((owner) => {
    const first = events.find(({ type, targetId }) => (
      type === "death" && ownerOf(targetId) === owner
    ));
    return [owner, first ? first.tick / 60 : null];
  }));
  const firstDamageTick = damage[0]?.tick ?? null;
  const openingDamage = firstDamageTick === null
    ? []
    : damage.filter(({ tick }) => tick <= firstDamageTick + 120);
  const openingByOwner = Object.fromEntries([2, 3, 4].map((owner) => {
    const rows = openingDamage.filter(({ actorId }) => ownerOf(actorId) === owner);
    const acquisitionTicks = [...firstAcquisitionTickByActor]
      .filter(([actorId]) => ownerOf(actorId) === owner)
      .map(([, tick]) => tick / 60);
    const attackTicks = [...firstAttackTickByActor]
      .filter(([actorId]) => ownerOf(actorId) === owner)
      .map(([, tick]) => tick / 60);
    const acquisitionToAttackSeconds = [...firstAttackTickByActor]
      .filter(([actorId]) => (
        ownerOf(actorId) === owner && firstAcquisitionTickByActor.has(actorId)
      ))
      .map(([actorId, attackTick]) => (
        (attackTick - firstAcquisitionTickByActor.get(actorId)) / 60
      ));
    const firstAcquisitionDistances = [...firstAcquisitionByActor]
      .filter(([actorId]) => ownerOf(actorId) === owner)
      .map(([, current]) => eventDistance(snapshotByTick, current))
      .filter(Number.isFinite);
    const firstAttackDistances = [...firstAttackByActor]
      .filter(([actorId]) => ownerOf(actorId) === owner)
      .map(([, current]) => eventDistance(snapshotByTick, current))
      .filter(Number.isFinite);
    return [owner, {
      hits: rows.length,
      firstDamageSeconds: rows.length ? rows[0].tick / 60 : null,
      uniqueAttackers: new Set(rows.map(({ actorId }) => actorId)).size,
      uniqueVictims: new Set(rows.map(({ targetId }) => targetId)).size,
      uniqueEngagementPairs: new Set(rows.map(({ actorId, targetId }) => (
        `${actorId}|${targetId}`
      ))).size,
      firstAcquisitionSeconds: nullableSummary(acquisitionTicks),
      firstAttackSeconds: nullableSummary(attackTicks),
      acquisitionToAttackSeconds: nullableSummary(acquisitionToAttackSeconds),
      firstAcquisitionDistance: nullableSummary(firstAcquisitionDistances),
      firstAttackDistance: nullableSummary(firstAttackDistances),
    }];
  }));
  const motionSnapshot = snapshotByTick.get(180) ?? run.snapshots.at(-1);
  const motionAtThreeSeconds = Object.fromEntries([2, 3, 4].flatMap((owner) => {
    const rows = motionSnapshot.units
      .filter(([referenceId]) => ownerOf(referenceId) === owner)
      .map(([referenceId, x, y]) => {
        const initial = initialPositionById.get(referenceId);
        const dx = x - initial.x;
        const dy = y - initial.y;
        return { dx, dy, distance: Math.hypot(dx, dy) };
      });
    return rows.length === 0 ? [] : [[owner, {
      dx: summary(rows.map(({ dx }) => dx)),
      dy: summary(rows.map(({ dy }) => dy)),
      distance: summary(rows.map(({ distance }) => distance)),
    }]];
  }));
  const player4DefeatTick = events.find(({ type, owner }) => (
    type === "owner-defeated" && owner === 4
  ))?.tick ?? null;
  const player4DefeatSnapshot = player4DefeatTick === null
    ? null
    : snapshotByTick.get(player4DefeatTick) ?? null;
  const stateByOwnerAtPlayer4Defeat = player4DefeatSnapshot === null
    ? null
    : Object.fromEntries([2, 3, 4].map((owner) => {
      const rows = player4DefeatSnapshot.units.filter(([referenceId]) => (
        ownerOf(referenceId) === owner
      ));
      return [owner, {
        live: rows.filter(([, , , , , alive]) => alive === 1).length,
        hp: rows.reduce((total, [, , , , hp]) => total + hp, 0),
      }];
    }));
  const targetLoadPerSecond = [];
  for (let tick = 0; tick <= run.ticks; tick += 60) {
    const snapshot = snapshotByTick.get(tick);
    if (!snapshot) continue;
    const byId = new Map(snapshot.units.map((row) => [row[0], row]));
    const byOwner = Object.fromEntries([2, 3].map((owner) => {
      const assigned = [];
      const attacking = [];
      const active = [];
      const aliveRows = snapshot.units.filter(([referenceId, , , , , alive]) => (
        alive === 1 && ownerOf(referenceId) === owner
      ));
      for (const [referenceId, , , , , alive, action,
        pursuitTargetId, engagedTargetId, attackTargetId] of snapshot.units) {
        if (alive !== 1 || ownerOf(referenceId) !== owner) continue;
        const targetId = attackTargetId ?? engagedTargetId ?? pursuitTargetId;
        const target = byId.get(targetId);
        if (!target || target[5] !== 1 || ownerOf(targetId) === owner) continue;
        assigned.push(targetId);
        if (action === "attacking") attacking.push(targetId);
        if (action === "attacking" || action === "reload") active.push(targetId);
      }
      return [owner, {
        assigned: loadSummary(assigned),
        attacking: loadSummary(attacking),
        active: loadSummary(active),
        geometry: aliveRows.length === 0 ? null : {
          alive: aliveRows.length,
          meanX: mean(aliveRows.map(([, x]) => x)),
          meanY: mean(aliveRows.map(([, , y]) => y)),
          minX: Math.min(...aliveRows.map(([, x]) => x)),
          maxX: Math.max(...aliveRows.map(([, x]) => x)),
          minY: Math.min(...aliveRows.map(([, , y]) => y)),
          maxY: Math.max(...aliveRows.map(([, , y]) => y)),
        },
      }];
    }));
    targetLoadPerSecond.push({ tick, second: tick / 60, byOwner });
  }
  return {
    firstTargetDistributionByOwner,
    firstDamageSeconds: firstDamageTick === null ? null : firstDamageTick / 60,
    openingHits: openingDamage.length,
    openingUniqueEngagementPairs: new Set(openingDamage.map(({ actorId, targetId }) => (
      `${actorId}|${targetId}`
    ))).size,
    openingByOwner,
    motionAtThreeSeconds,
    firstDeathSecondsByOwner,
    totalAttacksByOwner,
    totalDamageByOwner,
    totalDamageByOwnerAndTargetOwner,
    attackStartDistanceByOwnerAndTargetOwner,
    player4DefeatSeconds: player4DefeatTick === null ? null : player4DefeatTick / 60,
    stateByOwnerAtPlayer4Defeat,
    targetLoadPerSecond,
  };
}


export async function runComparison({
  outputDirectory = DEFAULT_OUTPUT,
  openingSeeds = [0],
  matchupKeys = null,
} = {}) {
  if (!Array.isArray(openingSeeds) || openingSeeds.length === 0
      || openingSeeds.some((seed) => !Number.isSafeInteger(seed) || seed < 0)) {
    throw new RangeError("opening seeds must be a nonempty array of nonnegative integers");
  }
  const [capture, grpcAnalysis, freshCapture, freshGateAnalysis,
    formations, mapFixture] = await Promise.all([
    readFile(new URL("capture_manifest.json", CAPTURE_ROOT), "utf8").then(JSON.parse),
    readFile(new URL("grpc_matrix_analysis.json", CAPTURE_ROOT), "utf8").then(JSON.parse),
    readFile(new URL("capture_manifest.json", FRESH_CAPTURE_ROOT), "utf8").then(JSON.parse),
    readFile(new URL("grpc_player4_gate_analysis.json", FRESH_CAPTURE_ROOT), "utf8")
      .then(JSON.parse),
    readFile(new URL("../fixtures/current_ranged_golden_formations.json", import.meta.url), "utf8").then(JSON.parse),
    readFile(new URL("../fixtures/golden_map.json", import.meta.url), "utf8").then(JSON.parse),
  ]);
  if (capture.completed_runs !== 70) {
    throw new Error(`ranged capture matrix is incomplete: ${capture.completed_runs ?? 0}/70`);
  }
  if (freshCapture.completed_runs !== 30) {
    throw new Error(
      `fresh remaining-six capture is incomplete: ${freshCapture.completed_runs ?? 0}/30`,
    );
  }
  const map = buildArenaPhysicsMap(mapFixture);
  const rows = [];
  const selectedKeys = matchupKeys ?? capture.matchup_keys;
  for (const key of selectedKeys) {
    if (!capture.matchup_keys.includes(key)) throw new RangeError(`unknown matchup key ${key}`);
    const usesFreshCapture = freshCapture.matchup_keys.includes(key);
    const selectedCapture = usesFreshCapture ? freshCapture : capture;
    const selectedCaptureRoot = usesFreshCapture
      ? "calibration/live_observations/remaining_six_fresh_5x_2026-08-31"
      : "calibration/live_observations/ranged_matrix_5x_2026-08-29";
    const matchup = selectedCapture.matchups[key];
    const runs = selectedCapture.runs[key]
      .toSorted((left, right) => left.repeat - right.repeat);
    if (runs.length !== 5) throw new Error(`${key} does not have five repeats`);
    const side2 = unitBySlug(matchup.side1.slug);
    const side3 = unitBySlug(matchup.side2.slug);
    const [mechanics2, mechanics3] = await Promise.all([
      loadMechanics(side2), loadMechanics(side3),
    ]);
    const count2 = matchup.side1.count;
    const count3 = matchup.side2.count;
    const startingHp = {
      2: count2 * mechanics2.hp,
      3: count3 * mechanics3.hp,
    };
    const tapeScores = runs.map(({ capture: observed }) => {
      const owner = observed.winner === side2.slug ? 2 : 3;
      return score(owner, observed.winner_hp, startingHp);
    });
    const formation = formations.families[matchup.family];
    const placementByOwner = {
      2: formation.sides["2"].map(({ position }) => ({ x: position.x, y: position.y })),
      3: formation.sides["3"].map(({ position }) => ({ x: position.x, y: position.y })),
    };
    const simulationRuns = [];
    for (const openingSeed of openingSeeds) {
      try {
        const run = await runFight(pathToFileURL(fileURLToPath(ROOT)), {
          side2Slug: side2.slug,
          n2: count2,
          side3Slug: side3.slug,
          n3: count3,
          map,
          placementByOwner,
          ...(formation.sides["4"]?.length ? {
            auxiliaryArmiesByOwner: {
              4: {
                slug: "scout_cavalry",
                cells: formation.sides["4"].map(({ position }) => ({
                  x: position.x, y: position.y,
                })),
              },
            },
          } : {}),
          diplomacyByOwner: formation.initial_diplomacy,
          triggers: formation.triggers,
          victoryTeams: matchup.family === "ranged_vs_melee"
            ? [{ winnerOwner: 2, owners: [2, 4] }, { winnerOwner: 3, owners: [3] }]
            : undefined,
          preserveOwnerOrientation: true,
          disableAiOrders: true,
          disableKiting: true,
          openingSeed,
        });
        simulationRuns.push({
          openingSeed,
          winnerOwner: run.winnerOwner,
          winnerHp: run.winnerHp,
          ticks: run.ticks,
          score: score(run.winnerOwner, run.winnerHp, startingHp),
          mechanics: simulationMechanics(run),
        });
      } catch (error) {
        const timeoutWorld = error?.world;
        const liveUnits = timeoutWorld?.units?.filter(({ alive }) => alive) ?? [];
        simulationRuns.push({
          openingSeed,
          error: String(error?.message ?? error),
          ...(timeoutWorld ? {
            timeoutDiagnostic: {
              tick: timeoutWorld.tick,
              liveByOwner: Object.fromEntries([...new Set(liveUnits.map(({ owner }) => owner))]
                .sort((left, right) => left - right)
                .map((owner) => [owner, liveUnits.filter((unit) => unit.owner === owner).length])),
              liveUnits: liveUnits.map((unit) => ({
                referenceId: unit.referenceId,
                owner: unit.owner,
                x: unit.x,
                y: unit.y,
                hp: unit.hp,
                action: unit.action,
                pursuitTargetId: unit.pursuitTargetId,
                engagedTargetId: unit.engagedTargetId,
                attackTargetId: unit.attackTargetId,
              })),
              recoveryRoutes: [...(timeoutWorld.pursuitRecoveryState?.routes ?? [])],
              recoveryRetargetReady: [...(timeoutWorld.pursuitRecoveryState?.retargetReady ?? [])],
              recoveryFailedTargets: [...(timeoutWorld.pursuitRecoveryState?.failedTargets ?? [])]
                .map(([referenceId, targets]) => [referenceId, [...targets]]),
              finalEvents: timeoutWorld.events,
            },
          } : {}),
        });
      }
    }
    const resolvedSimulationRuns = simulationRuns.filter(({ score: value }) => (
      Number.isFinite(value)
    ));
    const simulationScore = resolvedSimulationRuns.length === openingSeeds.length
      ? mean(resolvedSimulationRuns.map(({ score: value }) => value))
      : null;
    const tape = summary(tapeScores);
    const tapeWinnerHpMean = mean(runs.map(({ capture: observed }) => observed.winner_hp));
    const simulationWinnerHpMean = resolvedSimulationRuns.length === openingSeeds.length
      ? mean(resolvedSimulationRuns.map(({ winnerHp }) => winnerHp))
      : null;
    const relativeWinnerHpDelta = simulationWinnerHpMean === null
      ? null
      : Math.abs(simulationWinnerHpMean - tapeWinnerHpMean) / tapeWinnerHpMean;
    rows.push({
      key,
      family: matchup.family,
      side2: { slug: side2.slug, civ: matchup.side1.civ, count: count2 },
      side3: { slug: side3.slug, civ: matchup.side2.civ, count: count3 },
      tape: {
        ...tape,
        sourceCaptureManifest: `${selectedCaptureRoot}/capture_manifest.json`,
        sources: runs.map(({ repeat }) => ({
          repeat,
          framesBin: `${selectedCaptureRoot}/${key}/run_${String(repeat).padStart(3, "0")}`
            + `/raw recordings/${key}.frames.bin`,
        })),
        winnerOwners: runs.map(({ capture: observed }) => observed.winner === side2.slug ? 2 : 3),
        survivorCounts: runs.map(({ capture: observed }) => observed.survivors),
        winnerHp: runs.map(({ capture: observed }) => observed.winner_hp),
        eliminationSeconds: runs.map(({ capture: observed }) => observed.elimination_time_s),
        grpcOpening: (usesFreshCapture ? freshGateAnalysis : grpcAnalysis)
          .matchups[key]?.summary ?? null,
      },
      simulation: simulationScore === null ? { runs: simulationRuns } : {
        runs: simulationRuns,
        winnerOwners: resolvedSimulationRuns.map(({ winnerOwner }) => winnerOwner),
        winnerHp: summary(resolvedSimulationRuns.map(({ winnerHp }) => winnerHp)),
        ticks: summary(resolvedSimulationRuns.map(({ ticks }) => ticks)),
        score: simulationScore,
        meanDelta: simulationScore - tape.mean,
        absoluteMeanDelta: Math.abs(simulationScore - tape.mean),
        tapeWinnerHpMean,
        relativeWinnerHpDelta,
      },
    });
    process.stderr.write(`${key}: tape ${tape.mean.toFixed(2)}, sim ${simulationScore?.toFixed(2) ?? "unresolved"}\n`);
  }
  const resolved = rows.filter(({ simulation }) => Number.isFinite(simulation.score));
  const report = {
    schemaVersion: 1,
    lane: "current_ranged_goldens_exact_first_n",
    source: {
      captureManifests: [
        "calibration/live_observations/ranged_matrix_5x_2026-08-29/capture_manifest.json",
        "calibration/live_observations/remaining_six_fresh_5x_2026-08-31/capture_manifest.json",
      ],
      sourceSelection: "latest relevant five-run capture overrides the older matrix",
      formationFixture: "fixtures/current_ranged_golden_formations.json",
      mapFixture: "fixtures/golden_map.json",
    },
    config: {
      placements: "literal first-N scenario order",
      openingSeeds,
      openingPatrols: "scenario triggers",
      aiOrderSweep: false,
      firstAcquisition: "seeded; concentrate when not outnumbered, otherwise fan to floor(hostile roster / 4) anchors; Player 4 concentrated",
      rangedVsRangedTargeting: "ordinary shared engine targeting",
      rangedVsMeleeNavigation: "ordinary DAT movement and collision mechanics",
      rangedVsMeleeOpeningOrder: "golden scenario patrol trigger",
      player4DiplomacyGate: "live Player 4 army, directional diplomacy, and owner-defeat trigger",
    },
    summary: {
      matchups: rows.length,
      resolved: resolved.length,
      wrongWinners: resolved.filter(({ tape, simulation }) => (
        Math.sign(tape.mean) !== Math.sign(simulation.score)
      )).length,
      meanAbsoluteMeanDelta: resolved.length
        ? mean(resolved.map(({ simulation }) => simulation.absoluteMeanDelta))
        : null,
      rowsWithin20PercentWinnerHp: resolved.filter(({ simulation }) => (
        simulation.relativeWinnerHpDelta < 0.2
      )).length,
    },
    rows,
  };
  await mkdir(outputDirectory, { recursive: true });
  await writeFile(resolveOutput(outputDirectory, "results.json"), `${JSON.stringify(report, null, 2)}\n`);
  return report;
}


function resolveOutput(directory, filename) {
  return directory instanceof URL ? new URL(filename, directory) : resolve(directory, filename);
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const matchupArgument = process.argv.find((value) => value.startsWith("--matchup="));
  const outputArgument = process.argv.find((value) => value.startsWith("--output="));
  const seedCountArgument = process.argv.find((value) => value.startsWith("--seed-count="));
  const seedCount = seedCountArgument
    ? Number.parseInt(seedCountArgument.slice("--seed-count=".length), 10)
    : process.argv.includes("--five-seeds") ? 5 : 1;
  if (!Number.isSafeInteger(seedCount) || seedCount < 1) {
    throw new RangeError("--seed-count must be a positive integer");
  }
  const report = await runComparison({
    outputDirectory: outputArgument
      ? resolve(outputArgument.slice("--output=".length))
      : matchupArgument
        ? new URL("../calibration/reports/ranged_matrix_mechanics_probe_2026-08-29/", import.meta.url)
        : DEFAULT_OUTPUT,
    openingSeeds: Array.from({ length: seedCount }, (_, seed) => seed),
    matchupKeys: matchupArgument ? [matchupArgument.slice("--matchup=".length)] : null,
  });
  process.stdout.write(`${JSON.stringify(report.summary)}\n`);
}
