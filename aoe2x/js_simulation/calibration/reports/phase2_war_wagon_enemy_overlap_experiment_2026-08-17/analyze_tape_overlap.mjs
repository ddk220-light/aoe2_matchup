import { readdir, readFile, writeFile } from "node:fs/promises";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
} from "../../../src/phase2-batch1-comparison.js";


const ROOT = new URL("../../../", import.meta.url);
const TAPE_DIRECTORY = new URL("tape/", import.meta.url);
const OUTPUT = new URL("tape_overlap.json", import.meta.url);
const ROW_ID = "elite_war_wagon_vs_champion";

const truth = await loadPhase2Batch1Truth(ROOT);
if (truth.archive?.zip_sha256 !== "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6") {
  throw new Error(`unexpected authorized archive hash ${truth.archive?.zip_sha256}`);
}
const context = await loadPhase2Batch1Context(ROOT, truth);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row) throw new Error(`missing Phase 2 truth row ${ROW_ID}`);
const canonical = row.runs[0].starting_units;
const wagonIds = new Set(canonical.filter(({ owner }) => owner === 2).map(({ id }) => id));
const opponentIds = new Set(canonical.filter(({ owner }) => owner === 3).map(({ id }) => id));
const wagonRadius = context.mechanicsByMaster.get(row.side2.master).collision_size_tiles.x;
const opponentRadius = context.mechanicsByMaster.get(row.side3.master).collision_size_tiles.x;
const fullExtent = wagonRadius + opponentRadius;
const files = (await readdir(TAPE_DIRECTORY))
  .filter((name) => name.endsWith(".tape_trace.jsonl"))
  .sort();
if (files.length !== row.runs.length) {
  throw new Error(`expected ${row.runs.length} tape traces, found ${files.length}`);
}

const repeats = [];
for (const file of files) {
  const rows = (await readFile(new URL(file, TAPE_DIRECTORY), "utf8"))
    .split(/\r?\n/)
    .filter(Boolean)
    .map(JSON.parse);
  repeats.push(Object.freeze({ file, ...analyze(rows) }));
}

const result = Object.freeze({
  generatedAt: new Date().toISOString(),
  source: Object.freeze({
    archive: truth.archive,
    archiveSha256: truth.archive.zip_sha256,
    rowId: row.id,
    startingUnitsHash: row.runs[0].starting_units_hash,
  }),
  geometry: Object.freeze({
    metric: "Chebyshev center separation below summed collision half-extents",
    wagonRadius,
    opponentRadius,
    fullExtent,
  }),
  repeats: Object.freeze(repeats),
});
await writeFile(OUTPUT, `${JSON.stringify(result, null, 2)}\n`, "utf8");


function analyze(rows) {
  let currentTime = null;
  let wagons = [];
  let opponents = [];
  let eligibleFrames = 0;
  let framesWithOverlap = 0;
  let pairObservations = 0;
  let overlappingPairObservations = 0;
  let wagonObservations = 0;
  let opponentObservations = 0;
  let wagonOverlapObservations = 0;
  let opponentOverlapObservations = 0;
  let maximumSimultaneousPairs = 0;
  let maximumOpponentsPerWagon = 0;
  let maximumWagonsPerOpponent = 0;
  const depths = [];

  const flush = () => {
    if (!wagons.length || !opponents.length) return;
    eligibleFrames += 1;
    wagonObservations += wagons.length;
    opponentObservations += opponents.length;
    const wagonContacts = new Map(wagons.map(({ id }) => [id, 0]));
    const opponentContacts = new Map(opponents.map(({ id }) => [id, 0]));
    let framePairs = 0;
    for (const wagon of wagons) {
      for (const opponent of opponents) {
        pairObservations += 1;
        const separation = Math.max(
          Math.abs(wagon.x - opponent.x),
          Math.abs(wagon.y - opponent.y),
        );
        const depth = fullExtent - separation;
        if (depth <= 1e-9) continue;
        framePairs += 1;
        overlappingPairObservations += 1;
        depths.push(depth);
        wagonContacts.set(wagon.id, wagonContacts.get(wagon.id) + 1);
        opponentContacts.set(opponent.id, opponentContacts.get(opponent.id) + 1);
      }
    }
    if (framePairs > 0) framesWithOverlap += 1;
    wagonOverlapObservations += [...wagonContacts.values()].filter(Boolean).length;
    opponentOverlapObservations += [...opponentContacts.values()].filter(Boolean).length;
    maximumSimultaneousPairs = Math.max(maximumSimultaneousPairs, framePairs);
    maximumOpponentsPerWagon = Math.max(
      maximumOpponentsPerWagon,
      ...wagonContacts.values(),
    );
    maximumWagonsPerOpponent = Math.max(
      maximumWagonsPerOpponent,
      ...opponentContacts.values(),
    );
  };

  for (const unit of rows) {
    if (unit.t_ms !== currentTime) {
      flush();
      currentTime = unit.t_ms;
      wagons = [];
      opponents = [];
    }
    if (!(unit.hp > 0)) continue;
    if (wagonIds.has(unit.id)) wagons.push(unit);
    if (opponentIds.has(unit.id)) opponents.push(unit);
  }
  flush();

  return Object.freeze({
    eligibleFrames,
    framesWithOverlapShare: ratio(framesWithOverlap, eligibleFrames),
    overlappingPairObservationShare: ratio(
      overlappingPairObservations, pairObservations,
    ),
    wagonUnitObservationShare: ratio(wagonOverlapObservations, wagonObservations),
    opponentUnitObservationShare: ratio(
      opponentOverlapObservations, opponentObservations,
    ),
    depthTiles: quantiles(depths),
    maximumSimultaneousPairs,
    maximumOpponentsPerWagon,
    maximumWagonsPerOpponent,
  });
}


function quantiles(values) {
  const sorted = values.sort((left, right) => left - right);
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
