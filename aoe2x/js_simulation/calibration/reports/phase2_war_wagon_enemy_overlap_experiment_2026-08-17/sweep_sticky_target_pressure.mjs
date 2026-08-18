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
const OUTPUT = new URL("sticky_target_pressure_results.json", import.meta.url);
const TEMPORARY = new URL("sticky_target_pressure_results.json.tmp", import.meta.url);
const ROW_IDS = Object.freeze([
  "elite_war_wagon_vs_paladin",
  "elite_war_wagon_vs_champion",
]);
const SAMPLE_INDICES = Object.freeze([0]);
const VARIANTS = Object.freeze([
  "sticky-pressure",
  "sticky-pressure-pairwise-transit",
]);
const SEED = 20260817;

const truth = await loadPhase2Batch1Truth(ROOT);
const context = await loadPhase2Batch1Context(ROOT, truth);
const candidates = await resumeCandidates();

for (const sampleIndex of SAMPLE_INDICES) {
  for (const variant of VARIANTS) {
    for (const rowId of ROW_IDS) {
      if (candidates.some((candidate) => (
        candidate.sampleIndex === sampleIndex
          && candidate.variant === variant
          && candidate.rowId === rowId
      ))) continue;
    const row = truth.rows.find(({ id }) => id === rowId);
    if (!row) throw new Error(`missing Phase 2 truth row ${rowId}`);
    const base = scenarioFromPhase2Batch1Row({ row, sampleIndex, seed: SEED, context });
    const chaserMechanics = context.mechanicsByMaster.get(row.side3.master);
    const pressureTiles = 2 * chaserMechanics.collision_size_tiles.x;
    const scenario = Object.freeze({
      ...base,
      attackMoveTargetPressureTiles: pressureTiles,
      attackMoveStickyPursuit: true,
      ...(variant === "sticky-pressure-pairwise-transit"
        ? { pairwiseAlliedTransit: true, reachMeleeWedgeTransit: false }
        : {}),
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
        outcome: "timeout",
        winner: null,
        ticks: PHASE2_MAX_TICKS,
        world: error.world,
        events: error.events,
      });
    }
    const ownerById = new Map(result.world.units.map(({ referenceId, owner }) => (
      [referenceId, owner]
    )));
    const startingHp = row.runs[0].starting_hp_by_owner;
    const remainingHp = Object.freeze(Object.fromEntries([2, 3].map((owner) => [
      owner,
      result.world.units
        .filter((unit) => unit.owner === owner && unit.alive)
        .reduce((total, unit) => total + unit.hp, 0),
    ])));
    const score = result.outcome === "win"
      ? signedScore({
        winnerOwner: result.winner,
        winnerHp: remainingHp[result.winner],
        startingHpByOwner: startingHp,
      })
      : null;
    const tapeMean = mean(row.runs.map(({ signed_score: value }) => value));
    candidates.push(Object.freeze({
      variant,
      sampleIndex,
      seed: SEED,
      pressureTiles,
      pressureFormula: "two times the chaser collision half-extent",
      stickyPursuit: true,
      rowId,
      ratio: `${row.side2.count}v${row.side3.count}`,
      outcome: result.outcome,
      winnerOwner: result.winner,
      remainingHp: Object.freeze({ owner2: remainingHp[2], owner3: remainingHp[3] }),
      remainingHpPercent: Object.freeze({
        owner2: round(100 * remainingHp[2] / startingHp[2]),
        owner3: round(100 * remainingHp[3] / startingHp[3]),
      }),
      score: round(score),
      ticks: result.ticks,
      tapeMean: round(tapeMean),
      absoluteDelta: score === null ? null : round(Math.abs(score - tapeMean)),
      correctWinner: score === null ? null : Math.sign(score) === Math.sign(tapeMean),
      pursuitAcquisitions: result.events.filter(({ type, actorId }) => (
        type === "pursuit-acquired" && ownerById.get(actorId) === 3
      )).length,
      attackStarts: Object.freeze({
        owner2: result.events.filter(({ type, actorId }) => (
          type === "attack-start" && ownerById.get(actorId) === 2
        )).length,
        owner3: result.events.filter(({ type, actorId }) => (
          type === "attack-start" && ownerById.get(actorId) === 3
        )).length,
      }),
    }));
    await publish();
    process.stdout.write(`${JSON.stringify(candidates.at(-1))}\n`);
    }
  }
}


async function resumeCandidates() {
  try {
    const previous = JSON.parse(await readFile(OUTPUT, "utf8"));
    return Array.isArray(previous.candidates)
      ? previous.candidates.map((candidate) => Object.freeze({
        variant: candidate.variant ?? "sticky-pressure",
        ...candidate,
      }))
      : [];
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
}


async function publish() {
  const output = Object.freeze({
    generatedAt: new Date().toISOString(),
    source: Object.freeze({ archive: truth.archive, archiveSha256: truth.archive.zip_sha256 }),
    simulation: Object.freeze({
      sampleIndices: SAMPLE_INDICES,
      variants: VARIANTS,
      seed: SEED,
      placements: "exact canonical golden starting positions",
      overlapPolicy: "baseline; no War Wagon enemy-overlap allowance",
    }),
    candidates: Object.freeze([...candidates]),
  });
  await writeFile(TEMPORARY, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  await rename(TEMPORARY, OUTPUT);
}


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function round(value, digits = 4) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
