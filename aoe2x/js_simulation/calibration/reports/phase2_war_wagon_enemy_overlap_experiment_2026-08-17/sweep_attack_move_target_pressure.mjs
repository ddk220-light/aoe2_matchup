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
const OUTPUT = new URL("attack_move_target_pressure_results.json", import.meta.url);
const TEMPORARY = new URL("attack_move_target_pressure_results.json.tmp", import.meta.url);
const PRESSURES_TILES = Object.freeze([0.25, 0.5]);
const ROW_IDS = Object.freeze([
  "elite_war_wagon_vs_paladin",
  "elite_war_wagon_vs_champion",
]);
const SAMPLE_INDEX = 0;
const SEED = 20260817;

const truth = await loadPhase2Batch1Truth(ROOT);
const context = await loadPhase2Batch1Context(ROOT, truth);
const candidates = await resumeCandidates();

for (const pressureTiles of PRESSURES_TILES) {
  for (const rowId of ROW_IDS) {
    if (candidates.some((candidate) => (
      candidate.pressureTiles === pressureTiles && candidate.rowId === rowId
    ))) continue;
    const row = truth.rows.find(({ id }) => id === rowId);
    if (!row) throw new Error(`missing Phase 2 truth row ${rowId}`);
    const base = scenarioFromPhase2Batch1Row({
      row,
      sampleIndex: SAMPLE_INDEX,
      seed: SEED,
      context,
    });
    const scenario = Object.freeze({
      ...base,
      attackMoveTargetPressureTiles: pressureTiles,
    });
    let result;
    try {
      result = runWorld(createWorld(scenario), {
        maxTicks: PHASE2_MAX_TICKS,
        retainSnapshots: false,
      });
    } catch (error) {
      if (!String(error?.message ?? error).includes("world exceeded")) throw error;
      candidates.push(Object.freeze({ pressureTiles, rowId, outcome: "timeout" }));
      await publish();
      process.stdout.write(`${JSON.stringify(candidates.at(-1))}\n`);
      continue;
    }
    const ownerById = new Map(result.world.units.map(({ referenceId, owner }) => (
      [referenceId, owner]
    )));
    const live = result.world.units.filter(({ alive }) => alive);
    const winnerHp = live.reduce((total, unit) => total + unit.hp, 0);
    const score = signedScore({
      winnerOwner: result.winner,
      winnerHp,
      startingHpByOwner: row.runs[0].starting_hp_by_owner,
    });
    const tapeMean = mean(row.runs.map(({ signed_score: value }) => value));
    candidates.push(Object.freeze({
      pressureTiles,
      rowId,
      ratio: `${row.side2.count}v${row.side3.count}`,
      outcome: "win",
      winnerOwner: result.winner,
      winnerHp: round(winnerHp),
      score: round(score),
      ticks: result.ticks,
      tapeMean: round(tapeMean),
      absoluteDelta: round(Math.abs(score - tapeMean)),
      correctWinner: Math.sign(score) === Math.sign(tapeMean),
      attackStarts: Object.freeze({
        owner2: result.events.filter(({ type, actorId }) => (
          type === "attack-start" && ownerById.get(actorId) === 2
        )).length,
        owner3: result.events.filter(({ type, actorId }) => (
          type === "attack-start" && ownerById.get(actorId) === 3
        )).length,
      }),
      chaserTargetDistribution: Object.freeze(
        targetDistribution(result.events, ownerById, 3, [60, 120, 180, 240, 360, 600]),
      ),
    }));
    await publish();
    process.stdout.write(`${JSON.stringify(candidates.at(-1))}\n`);
  }
}


async function resumeCandidates() {
  try {
    const previous = JSON.parse(await readFile(OUTPUT, "utf8"));
    return Array.isArray(previous.candidates) ? [...previous.candidates] : [];
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
      pressuresTiles: PRESSURES_TILES,
      sampleIndex: SAMPLE_INDEX,
      seed: SEED,
      placements: "exact canonical golden starting positions",
      overlapPolicy: "baseline; no War Wagon enemy-overlap allowance",
    }),
    candidates: Object.freeze([...candidates]),
  });
  await writeFile(TEMPORARY, `${JSON.stringify(output, null, 2)}\n`, "utf8");
  await rename(TEMPORARY, OUTPUT);
}


function targetDistribution(events, ownerById, owner, sampleTicks) {
  const changes = events.filter(({ type, actorId }) => (
    type === "pursuit-acquired" && ownerById.get(actorId) === owner
  ));
  const targets = new Map();
  let index = 0;
  return sampleTicks.map((tick) => {
    while (index < changes.length && changes[index].tick <= tick) {
      targets.set(changes[index].actorId, changes[index].targetId);
      index += 1;
    }
    const loads = new Map();
    for (const targetId of targets.values()) {
      loads.set(targetId, (loads.get(targetId) ?? 0) + 1);
    }
    return Object.freeze({
      tick,
      seconds: tick / 60,
      assigned: targets.size,
      distinctTargets: loads.size,
      maximumTargetLoad: Math.max(0, ...loads.values()),
    });
  });
}


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function round(value, digits = 4) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
