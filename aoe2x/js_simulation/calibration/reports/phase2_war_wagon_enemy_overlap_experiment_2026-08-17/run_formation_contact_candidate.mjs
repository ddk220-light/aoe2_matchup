import { readFile, rename, writeFile } from "node:fs/promises";

import {
  PHASE2_MAX_TICKS,
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  scenarioFromPhase2Batch1Row,
} from "../../../src/phase2-batch1-comparison.js";
import { createWorld, runWorld } from "../../../src/combat/world.js";
import { signedScore } from "../../../src/standard-units-comparison.js";


const ROOT = new URL("../../../", import.meta.url);
const CONTACT_DEPTH_TILES = Number(process.env.AOE2X_WW_CONTACT_DEPTH ?? "0.2");
if (!Number.isFinite(CONTACT_DEPTH_TILES) || CONTACT_DEPTH_TILES < 0) {
  throw new RangeError("AOE2X_WW_CONTACT_DEPTH must be nonnegative and finite");
}
const outputSuffix = String(CONTACT_DEPTH_TILES).replace(".", "_");
const OUTPUT = new URL(`formation_contact_${outputSuffix}_candidate_results.json`, import.meta.url);
const TEMPORARY = new URL(
  `formation_contact_${outputSuffix}_candidate_results.json.tmp`,
  import.meta.url,
);
const ALL_ROW_IDS = Object.freeze([
  "elite_war_wagon_vs_paladin",
  "elite_war_wagon_vs_champion",
]);
const requestedRow = process.env.AOE2X_WW_ROW ?? null;
if (requestedRow !== null && !ALL_ROW_IDS.includes(requestedRow)) {
  throw new RangeError(`unknown War Wagon comparison row ${requestedRow}`);
}
const ROW_IDS = requestedRow === null ? ALL_ROW_IDS : Object.freeze([requestedRow]);
const SAMPLE_INDEX = 0;
const SEED = 20260817;

const truth = await loadPhase2Batch1Truth(ROOT);
const context = await loadPhase2Batch1Context(ROOT, truth);
const comparisons = await resume();

for (const rowId of ROW_IDS) {
  if (comparisons.some((comparison) => comparison.rowId === rowId)) continue;
  const row = truth.rows.find(({ id }) => id === rowId);
  if (!row) throw new Error(`missing Phase 2 truth row ${rowId}`);
  const base = scenarioFromPhase2Batch1Row({
    row,
    sampleIndex: SAMPLE_INDEX,
    seed: SEED,
    context,
  });
  const chaserMechanics = context.mechanicsByMaster.get(row.side3.master);
  const scenario = Object.freeze({
    ...base,
    kiteProfile: Object.freeze({
      ...base.kiteProfile,
      formationSpacingTiles: 0.6,
    }),
    attackMoveTargetPressureTiles: 2 * chaserMechanics.collision_size_tiles.x,
    attackMoveStickyPursuit: true,
    warWagonEnemyOverlapDepthTiles: CONTACT_DEPTH_TILES,
    warWagonEnemyOverlapMode: "always",
  });
  let result;
  try {
    result = runWorld(createWorld(scenario), {
      maxTicks: PHASE2_MAX_TICKS,
      retainSnapshots: false,
    });
  } catch (error) {
    if (!String(error?.message ?? error).includes("world exceeded")) throw error;
    result = Object.freeze({
      winner: null,
      ticks: PHASE2_MAX_TICKS,
      world: error.world,
      events: error.world?.eventLog ?? [],
    });
  }
  const remainingHp = Object.fromEntries([2, 3].map((owner) => [
    owner,
    result.world.units
      .filter((unit) => unit.owner === owner && unit.alive)
      .reduce((sum, unit) => sum + unit.hp, 0),
  ]));
  const score = result.winner === null
    ? null
    : signedScore({
      winnerOwner: result.winner,
      winnerHp: remainingHp[result.winner],
      startingHpByOwner: row.runs[0].starting_hp_by_owner,
    });
  const tapeScores = row.runs.map(({ signed_score: value }) => value);
  const tapeMean = mean(tapeScores);
  const ownerById = new Map(result.world.units.map(({ referenceId, owner }) => (
    [referenceId, owner]
  )));
  comparisons.push(Object.freeze({
    rowId,
    ratio: `${row.side2.count}v${row.side3.count}`,
    tapeMean: round(tapeMean),
    tapeBand: Object.freeze({
      min: round(Math.min(...tapeScores)),
      max: round(Math.max(...tapeScores)),
    }),
    winnerOwner: result.winner,
    remainingHp: Object.freeze({ owner2: remainingHp[2], owner3: remainingHp[3] }),
    score: round(score),
    absoluteDelta: score === null ? null : round(Math.abs(score - tapeMean)),
    correctWinner: score !== null && Math.sign(score) === Math.sign(tapeMean),
    ticks: result.ticks,
    attackStarts: Object.freeze(Object.fromEntries([2, 3].map((owner) => [
      `owner${owner}`,
      result.events.filter(({ type, actorId }) => (
        type === "attack-start" && ownerById.get(actorId) === owner
      )).length,
    ]))),
  }));
  await publish();
  process.stdout.write(`${JSON.stringify(comparisons.at(-1))}\n`);
}


async function resume() {
  try {
    const previous = JSON.parse(await readFile(OUTPUT, "utf8"));
    return Array.isArray(previous.comparisons) ? [...previous.comparisons] : [];
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
}


async function publish() {
  const output = Object.freeze({
    generatedAt: new Date().toISOString(),
    source: Object.freeze({
      archive: truth.archive,
      archiveSha256: truth.archive.zip_sha256,
    }),
    simulation: Object.freeze({
      sampleIndex: SAMPLE_INDEX,
      seed: SEED,
      formationSpacingTiles: 0.6,
      overlapDepthTiles: CONTACT_DEPTH_TILES,
      overlapMode: "always",
      targetPressure: "chaser collision diameter",
      stickyPursuit: true,
    }),
    comparisons: Object.freeze([...comparisons]),
  });
  await writeFile(TEMPORARY, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  await rename(TEMPORARY, OUTPUT);
}


function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}


function round(value, digits = 4) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
