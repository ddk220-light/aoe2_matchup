import { writeFile } from "node:fs/promises";

import {
  PHASE2_MAX_TICKS,
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  scenarioFromPhase2Batch1Row,
} from "../../../src/phase2-batch1-comparison.js";
import { createWorld, runWorld } from "../../../src/combat/world.js";
import { signedScore } from "../../../src/standard-units-comparison.js";


const ROOT = new URL("../../../", import.meta.url);
const CANDIDATE_DEPTHS = Object.freeze([0.1, 0.2, 0.3]);
const SAMPLE_INDEX = 0;
const SEED = 20260817;
const WAR_WAGON_MASTER = 829;

const truth = await loadPhase2Batch1Truth(ROOT);
const context = await loadPhase2Batch1Context(ROOT, truth);
const row = truth.rows.find(({ id }) => id === "elite_war_wagon_vs_paladin");
if (!row) throw new Error("missing Elite War Wagon versus Paladin truth row");

const candidates = [];
for (const depthTiles of CANDIDATE_DEPTHS) {
  const baseScenario = scenarioFromPhase2Batch1Row({
    row,
    sampleIndex: SAMPLE_INDEX,
    seed: SEED,
    context,
  });
  const scenario = Object.freeze({
    ...baseScenario,
    warWagonEnemyOverlapDepthTiles: depthTiles,
  });
  let result;
  try {
    result = runWorld(createWorld(scenario), {
      maxTicks: PHASE2_MAX_TICKS,
      retainSnapshots: true,
    });
  } catch (error) {
    if (!String(error?.message ?? error).includes("world exceeded")) throw error;
    candidates.push(Object.freeze({ depthTiles, outcome: "timeout" }));
    process.stdout.write(`${JSON.stringify(candidates.at(-1))}\n`);
    continue;
  }
  const live = result.world.units.filter(({ alive }) => alive);
  const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
  const outcomeScore = signedScore({
    winnerOwner: result.winner,
    winnerHp,
    startingHpByOwner: row.runs[0].starting_hp_by_owner,
  });
  const candidate = Object.freeze({
    depthTiles,
    outcome: "win",
    winnerOwner: result.winner,
    winnerHp: round(winnerHp),
    score: round(outcomeScore),
    ticks: result.ticks,
    overlap: analyzeOverlap(result.snapshots, row.side3.master),
    attacks: Object.freeze({
      warWagonStarts: result.events.filter(({ type, actorId }) => (
        type === "attack-start"
        && result.world.units.find(({ referenceId }) => referenceId === actorId)?.owner === 2
      )).length,
      paladinStarts: result.events.filter(({ type, actorId }) => (
        type === "attack-start"
        && result.world.units.find(({ referenceId }) => referenceId === actorId)?.owner === 3
      )).length,
      warWagonDamageEvents: result.events.filter(({ type, actorId }) => (
        type === "damage"
        && result.world.units.find(({ referenceId }) => referenceId === actorId)?.owner === 2
      )).length,
      paladinDamageEvents: result.events.filter(({ type, actorId }) => (
        type === "damage"
        && result.world.units.find(({ referenceId }) => referenceId === actorId)?.owner === 3
      )).length,
    }),
  });
  candidates.push(candidate);
  process.stdout.write(`${JSON.stringify(candidate)}\n`);
}

const output = Object.freeze({
  generatedAt: new Date().toISOString(),
  source: Object.freeze({
    archive: truth.archive,
    archiveSha256: truth.zip_sha256,
    rowId: row.id,
    startingUnitsHash: row.runs[0].starting_units_hash,
  }),
  simulation: Object.freeze({ sampleIndex: SAMPLE_INDEX, seed: SEED }),
  tape: Object.freeze({
    meanScore: round(row.runs.reduce((sum, run) => sum + run.signed_score, 0) / row.runs.length),
    minScore: round(Math.min(...row.runs.map(({ signed_score }) => signed_score))),
    maxScore: round(Math.max(...row.runs.map(({ signed_score }) => signed_score))),
  }),
  candidates: Object.freeze(candidates),
});
await writeFile(
  new URL("sweep_results.json", import.meta.url),
  `${JSON.stringify(output, null, 2)}\n`,
  "utf8",
);


function analyzeOverlap(snapshots, enemyMaster) {
  let eligibleFrames = 0;
  let framesWithOverlap = 0;
  let pairObservations = 0;
  let overlappingPairObservations = 0;
  let wagonObservations = 0;
  let enemyObservations = 0;
  let wagonOverlapObservations = 0;
  let enemyOverlapObservations = 0;
  let maximumSimultaneousPairs = 0;
  let maximumEnemiesPerWagon = 0;
  let maximumWagonsPerEnemy = 0;
  const depths = [];
  for (const snapshot of snapshots) {
    if (snapshot.tick === 0) continue;
    const wagons = snapshot.units.filter(({ alive, owner, unitMaster }) => (
      alive && owner === 2 && unitMaster === WAR_WAGON_MASTER
    ));
    const enemies = snapshot.units.filter(({ alive, owner, unitMaster }) => (
      alive && owner === 3 && unitMaster === enemyMaster
    ));
    if (!wagons.length || !enemies.length) continue;
    eligibleFrames += 1;
    wagonObservations += wagons.length;
    enemyObservations += enemies.length;
    const wagonContacts = new Map(wagons.map(({ referenceId }) => [referenceId, 0]));
    const enemyContacts = new Map(enemies.map(({ referenceId }) => [referenceId, 0]));
    let framePairs = 0;
    for (const wagon of wagons) {
      for (const enemy of enemies) {
        pairObservations += 1;
        const extent = wagon.mechanics.collision_size_tiles.x
          + enemy.mechanics.collision_size_tiles.x;
        const gap = Math.max(
          Math.abs(wagon.x - enemy.x),
          Math.abs(wagon.y - enemy.y),
        ) - extent;
        if (gap >= -1e-9) continue;
        framePairs += 1;
        overlappingPairObservations += 1;
        depths.push(-gap);
        wagonContacts.set(wagon.referenceId, wagonContacts.get(wagon.referenceId) + 1);
        enemyContacts.set(enemy.referenceId, enemyContacts.get(enemy.referenceId) + 1);
      }
    }
    if (framePairs > 0) framesWithOverlap += 1;
    wagonOverlapObservations += [...wagonContacts.values()].filter(Boolean).length;
    enemyOverlapObservations += [...enemyContacts.values()].filter(Boolean).length;
    maximumSimultaneousPairs = Math.max(maximumSimultaneousPairs, framePairs);
    maximumEnemiesPerWagon = Math.max(maximumEnemiesPerWagon, ...wagonContacts.values());
    maximumWagonsPerEnemy = Math.max(maximumWagonsPerEnemy, ...enemyContacts.values());
  }
  return Object.freeze({
    eligibleFrames,
    framesWithOverlapShare: ratio(framesWithOverlap, eligibleFrames),
    overlappingPairObservationShare: ratio(
      overlappingPairObservations,
      pairObservations,
    ),
    wagonUnitObservationShare: ratio(wagonOverlapObservations, wagonObservations),
    enemyUnitObservationShare: ratio(enemyOverlapObservations, enemyObservations),
    depthTiles: quantiles(depths),
    maximumSimultaneousPairs,
    maximumEnemiesPerWagon,
    maximumWagonsPerEnemy,
  });
}


function quantiles(values) {
  const sorted = values.toSorted((left, right) => left - right);
  if (!sorted.length) return Object.freeze({ min: null, median: null, p90: null, max: null });
  const at = (fraction) => sorted[Math.floor((sorted.length - 1) * fraction)];
  return Object.freeze({
    min: round(at(0)),
    median: round(at(0.5)),
    p90: round(at(0.9)),
    max: round(at(1)),
  });
}


function ratio(numerator, denominator) {
  return denominator ? round(numerator / denominator) : null;
}


function round(value, digits = 4) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
