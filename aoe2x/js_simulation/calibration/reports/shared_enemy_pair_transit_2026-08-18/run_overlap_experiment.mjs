import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readdir, readFile, rename, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";

import { createWorld, stepWorld } from "../../../src/combat/world.js";
import {
  loadDedicatedComparisonContext,
  scenarioFromDedicatedRun,
} from "../../../src/dedicated-golden-comparison.js";
import { loadDedicatedGoldenCorpus } from "../../../src/dedicated-golden-corpus.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  scenarioFromPhase2Batch1Row,
} from "../../../src/phase2-batch1-comparison.js";
import { signedScore } from "../../../src/standard-units-comparison.js";


const ROOT = new URL("../../../", import.meta.url);
const CHECKPOINTS = new URL("checkpoints/", import.meta.url);
const REPORT_JSON = new URL("report.json", import.meta.url);
const REPORT_MD = new URL("report.md", import.meta.url);
const MAX_TICKS = 9000;
const SEED = 20260818;
const PHASE2_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const HCA_PALADIN_SHA256 = "8902DE64B120E6302860F8F9B35B572523B29B4C0F305C65A7DA6D0C286F7968";
const EXPERIMENT_REVISION = 7;
const ROW_IDS = Object.freeze([
  "elite_war_wagon_vs_paladin",
  "elite_war_wagon_vs_champion",
  "heavy_cav_archer_vs_paladin_20v15",
  "elite_boyar_vs_heavy_cav_archer",
]);


const args = new Map(process.argv.slice(2).map((value) => {
  const [key, raw = "true"] = value.replace(/^--/, "").split("=", 2);
  return [key, raw];
}));
const rowFilter = args.get("row") ?? null;
const sampleCount = Number(args.get("samples") ?? 5);
if (rowFilter !== null && !ROW_IDS.includes(rowFilter)) {
  throw new RangeError(`unknown row ${rowFilter}`);
}
if (!Number.isSafeInteger(sampleCount) || sampleCount < 1 || sampleCount > 5) {
  throw new RangeError("samples must be an integer from 1 through 5");
}
const ENGINE_SIGNATURE = await buildEngineSignature();

const [phase2Truth, dedicatedCorpus] = await Promise.all([
  loadPhase2Batch1Truth(ROOT),
  loadDedicatedGoldenCorpus(ROOT),
]);
if (phase2Truth.archive?.zip_sha256 !== PHASE2_SHA256) {
  throw new Error(`unexpected Phase 2 archive hash ${phase2Truth.archive?.zip_sha256}`);
}
const hcaPaladinRow = dedicatedCorpus.rows.find(({ id }) => (
  id === "heavy_cav_archer_vs_paladin_20v15"
));
if (hcaPaladinRow?.zipSha256 !== HCA_PALADIN_SHA256) {
  throw new Error(`unexpected HCA-Paladin archive hash ${hcaPaladinRow?.zipSha256}`);
}
const [phase2Context, dedicatedContext, tapeTargets] = await Promise.all([
  loadPhase2Batch1Context(ROOT, phase2Truth),
  loadDedicatedComparisonContext(ROOT),
  loadTapeTargets(phase2Truth, hcaPaladinRow),
]);

if (args.has("report-only")) {
  await buildReport(tapeTargets);
  process.exit(0);
}

for (const rowId of ROW_IDS.filter((id) => rowFilter === null || rowFilter === id)) {
  const checkpointUrl = new URL(`${rowId}.json`, CHECKPOINTS);
  const samples = await loadCheckpointSamples(checkpointUrl, rowId, sampleCount);
  for (let sampleIndex = samples.length; sampleIndex < sampleCount; sampleIndex += 1) {
    const scenarioContext = buildScenario(rowId, sampleIndex);
    const result = runObservedScenario(scenarioContext);
    samples.push(result);
    await atomicJson(checkpointUrl, Object.freeze({
      schemaVersion: 1,
      experimentRevision: EXPERIMENT_REVISION,
      engineSignature: ENGINE_SIGNATURE,
      rowId,
      samplesRequested: sampleCount,
      sourceHashes: Object.freeze({ phase2: PHASE2_SHA256, hcaPaladin: HCA_PALADIN_SHA256 }),
      samples: Object.freeze([...samples]),
    }));
    process.stdout.write(`${rowId} sample ${sampleIndex + 1}/${sampleCount}: `
      + `pair=${percent(result.overlap.pairShare)} depth=${result.overlap.depthTiles.median} `
      + `score=${result.outcome.score} ticks=${result.outcome.ticks}\n`);
  }
}
await buildReport(tapeTargets);


function buildScenario(rowId, sampleIndex) {
  if (rowId === hcaPaladinRow.id) {
    const run = hcaPaladinRow.runs[sampleIndex % hcaPaladinRow.runs.length];
    const scenario = scenarioFromDedicatedRun({
      row: hcaPaladinRow,
      run,
      mechanicsByMaster: dedicatedContext.mechanicsByMaster,
      map: dedicatedContext.map,
    });
    return Object.freeze({
      rowId,
      sampleIndex,
      startingHpByOwner: run.starting_hp_by_owner,
      scenario: withSharedTransit(scenario),
    });
  }
  const row = phase2Truth.rows.find(({ id }) => id === rowId);
  if (!row) throw new Error(`missing Phase 2 row ${rowId}`);
  const scenario = scenarioFromPhase2Batch1Row({
    row,
    sampleIndex,
    seed: SEED,
    context: phase2Context,
  });
  return Object.freeze({
    rowId,
    sampleIndex,
    startingHpByOwner: row.runs[0].starting_hp_by_owner,
    scenario: withSharedTransit(scenario),
  });
}


function withSharedTransit(scenario) {
  const {
    warWagonEnemyOverlapDepthTiles: _legacyDepth,
    warWagonEnemyOverlapMode: _legacyMode,
    ...shared
  } = scenario;
  return Object.freeze({
    ...shared,
    pairwiseEnemyTransit: true,
    ...(args.has("allied") ? { pairwiseAlliedTransit: true } : {}),
  });
}


function runObservedScenario({ rowId, sampleIndex, scenario, startingHpByOwner }) {
  let world = createWorld(scenario);
  const overlap = createOverlapAccumulator();
  const movement = new Map();
  let acquired = 0;
  let released = 0;
  let maximumReservations = 0;
  const releaseReasons = new Map();
  const acquisitionReasons = new Map();
  const acquisitionSeparations = [];
  observeWorld(overlap, world);
  let timedOut = true;
  for (let elapsed = 0; elapsed < MAX_TICKS; elapsed += 1) {
    const beforeUnits = new Map(world.units.map((unit) => [unit.referenceId, unit]));
    world = stepWorld(world);
    observeMovement(movement, beforeUnits, world.units);
    observeWorld(overlap, world);
    acquired += world.enemyTransitDiagnostics.filter(({ type }) => (
      type === "enemy-transit-acquired"
    )).length;
    released += world.enemyTransitDiagnostics.filter(({ type }) => (
      type === "enemy-transit-released"
    )).length;
    for (const diagnostic of world.enemyTransitDiagnostics) {
      if (diagnostic.type === "enemy-transit-acquired") {
        acquisitionSeparations.push(diagnostic.currentSeparation);
        acquisitionReasons.set(
          diagnostic.reason,
          (acquisitionReasons.get(diagnostic.reason) ?? 0) + 1,
        );
      }
      if (diagnostic.type !== "enemy-transit-released") continue;
      releaseReasons.set(
        diagnostic.reason,
        (releaseReasons.get(diagnostic.reason) ?? 0) + 1,
      );
    }
    maximumReservations = Math.max(maximumReservations, world.enemyTransitState.reservations.size);
    const owners = new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner));
    if (owners.size <= 1) {
      timedOut = false;
      break;
    }
    world = Object.freeze({ ...world, eventLog: Object.freeze([]), snapshots: Object.freeze([]) });
  }
  const live = world.units.filter(({ alive }) => alive);
  const liveOwners = new Set(live.map(({ owner }) => owner));
  const winnerOwner = !timedOut && liveOwners.size === 1 ? [...liveOwners][0] : null;
  const winnerHp = winnerOwner === null
    ? null : live.reduce((total, unit) => total + unit.hp, 0);
  return Object.freeze({
    rowId,
    sampleIndex,
    outcome: Object.freeze({
      kind: timedOut ? "timeout" : "win",
      winnerOwner,
      winnerHp,
      score: winnerOwner === null ? null : round(signedScore({
        winnerOwner,
        winnerHp,
        startingHpByOwner,
      })),
      ticks: world.tick,
    }),
    overlap: finalizeOverlap(overlap),
    movement: finalizeMovement(movement),
    transit: Object.freeze({
      acquired,
      released,
      maximumReservations,
      releaseReasons: Object.freeze(Object.fromEntries(releaseReasons)),
      acquisitionReasons: Object.freeze(Object.fromEntries(acquisitionReasons)),
      acquisitionSeparations: quantiles(acquisitionSeparations),
    }),
  });
}


function observeMovement(accumulator, beforeByReference, afterUnits) {
  for (const after of afterUnits) {
    const before = beforeByReference.get(after.referenceId);
    if (!before?.alive) continue;
    const entry = accumulator.get(before.owner) ?? {
      distance: 0,
      aliveObservations: 0,
      movingObservations: 0,
      attackingObservations: 0,
      startingIds: new Set(),
    };
    const distance = Math.hypot(after.x - before.x, after.y - before.y);
    entry.distance += distance;
    entry.aliveObservations += 1;
    if (distance > 1e-7) entry.movingObservations += 1;
    if (after.action === "attacking") entry.attackingObservations += 1;
    entry.startingIds.add(after.referenceId);
    accumulator.set(before.owner, entry);
  }
}


function finalizeMovement(accumulator) {
  return Object.freeze(Object.fromEntries([...accumulator].map(([owner, entry]) => [
    owner,
    Object.freeze({
      meanPathTilesPerStartingUnit: round(entry.distance / entry.startingIds.size),
      effectiveSpeedWhileMovingTilesPerSecond: round(
        ratio(entry.distance * 60, entry.movingObservations),
      ),
      progressSpeedAcrossAliveTimeTilesPerSecond: round(
        ratio(entry.distance * 60, entry.aliveObservations),
      ),
      movingShareOfAliveObservations: ratio(
        entry.movingObservations,
        entry.aliveObservations,
      ),
      attackingShareOfAliveObservations: ratio(
        entry.attackingObservations,
        entry.aliveObservations,
      ),
    }),
  ])));
}


function createOverlapAccumulator() {
  return {
    eligibleFrames: 0,
    framesWithOverlap: 0,
    pairObservations: 0,
    overlaps: 0,
    depths: [],
    maximumPairsInFrame: 0,
    overlapSources: new Map(),
    reservationDepthsByMode: new Map(),
    activeOverlapPairs: new Map(),
    episodeDurationTicks: [],
    lastTick: 0,
  };
}


function observeWorld(accumulator, world) {
  const observedTick = Number.isSafeInteger(world.tick)
    ? world.tick
    : accumulator.lastTick + 1;
  accumulator.lastTick = observedTick;
  const left = world.units.filter(({ alive, owner }) => alive && owner === 2);
  const right = world.units.filter(({ alive, owner }) => alive && owner === 3);
  if (!left.length || !right.length) return;
  const byReference = new Map(world.units.map((unit) => [unit.referenceId, unit]));
  for (const reservation of world.enemyTransitState?.reservations.values() ?? []) {
    const a = byReference.get(reservation.chaserId);
    const b = byReference.get(reservation.blockerId);
    if (!a?.alive || !b?.alive) continue;
    const extent = a.mechanics.collision_size_tiles.x + b.mechanics.collision_size_tiles.x;
    const separation = Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y));
    const values = accumulator.reservationDepthsByMode.get(reservation.mode) ?? [];
    values.push(extent - separation);
    accumulator.reservationDepthsByMode.set(reservation.mode, values);
  }
  accumulator.eligibleFrames += 1;
  let framePairs = 0;
  const activeNow = new Set();
  for (const a of left) {
    for (const b of right) {
      accumulator.pairObservations += 1;
      const extent = a.mechanics.collision_size_tiles.x + b.mechanics.collision_size_tiles.x;
      const separation = Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y));
      const depth = extent - separation;
      if (depth <= 1e-9) continue;
      accumulator.overlaps += 1;
      framePairs += 1;
      accumulator.depths.push(depth);
      const pairKey = a.referenceId < b.referenceId
        ? `${a.referenceId}:${b.referenceId}`
        : `${b.referenceId}:${a.referenceId}`;
      activeNow.add(pairKey);
      const reservation = world.enemyTransitState?.reservations.get(pairKey);
      const source = reservation?.mode
        ?? (world.enemyTransitState?.inheritedContactExtents.has(pairKey)
          ? "inherited"
          : "unreserved");
      accumulator.overlapSources.set(
        source,
        (accumulator.overlapSources.get(source) ?? 0) + 1,
      );
    }
  }
  for (const [pairKey, startedTick] of accumulator.activeOverlapPairs) {
    if (activeNow.has(pairKey)) continue;
    accumulator.episodeDurationTicks.push(observedTick - startedTick);
  }
  for (const pairKey of activeNow) {
    if (accumulator.activeOverlapPairs.has(pairKey)) continue;
    accumulator.activeOverlapPairs.set(pairKey, observedTick);
  }
  accumulator.activeOverlapPairs = new Map(
    [...accumulator.activeOverlapPairs].filter(([pairKey]) => activeNow.has(pairKey)),
  );
  if (framePairs > 0) accumulator.framesWithOverlap += 1;
  accumulator.maximumPairsInFrame = Math.max(accumulator.maximumPairsInFrame, framePairs);
}


function finalizeOverlap(accumulator) {
  const completedEpisodeTicks = [
    ...accumulator.episodeDurationTicks,
    ...[...accumulator.activeOverlapPairs.values()].map((startedTick) => (
      accumulator.lastTick - startedTick + 1
    )),
  ];
  return Object.freeze({
    eligibleFrames: accumulator.eligibleFrames,
    frameShare: ratio(accumulator.framesWithOverlap, accumulator.eligibleFrames),
    pairObservations: accumulator.pairObservations,
    overlappingPairObservations: accumulator.overlaps,
    pairShare: ratio(accumulator.overlaps, accumulator.pairObservations),
    depthTiles: quantiles(accumulator.depths),
    maximumPairsInFrame: accumulator.maximumPairsInFrame,
    episodes: Object.freeze({
      count: completedEpisodeTicks.length,
      durationSeconds: quantiles(completedEpisodeTicks.map((ticks) => ticks / 60)),
    }),
    overlapSources: Object.freeze(Object.fromEntries(accumulator.overlapSources)),
    reservationDepthsByMode: Object.freeze(Object.fromEntries(
      [...accumulator.reservationDepthsByMode].map(([mode, values]) => [mode, quantiles(values)]),
    )),
  });
}


async function loadTapeTargets(truth, dedicatedRow) {
  const [warWagonEvidence, hcaEvidence, hcaEpisodes, boyarOverlap] = await Promise.all([
    readFile(new URL("../phase2_war_wagon_enemy_overlap_experiment_2026-08-17/contact_state_analysis.json", import.meta.url), "utf8").then(JSON.parse),
    readFile(new URL("../phase2_boyar_hca_diagnosis_2026-08-17/overlap_analysis.json", import.meta.url), "utf8").then(JSON.parse),
    analyzeHcaTapeEpisodes(),
    analyzeBoyarTape(),
  ]);
  const targets = new Map();
  for (const rowId of ["elite_war_wagon_vs_paladin", "elite_war_wagon_vs_champion"]) {
    const evidence = warWagonEvidence.matchups.find((row) => row.rowId === rowId);
    const truthRow = truth.rows.find((row) => row.id === rowId);
    targets.set(rowId, Object.freeze({
      archiveSha256: PHASE2_SHA256,
      tapeRuns: evidence.runs.length,
      pairShare: band(evidence.runs.map((run) => run.overlappingPairObservationShare)),
      depthMedian: band(evidence.runs.map((run) => run.depthTiles.median)),
      frameShare: null,
      episodeCount: band(evidence.runs.map((run) => run.episodeCount)),
      episodeDurationMedianSeconds: band(
        evidence.runs.map((run) => run.episodeDurationSeconds.median),
      ),
      outcomeScore: band(truthRow.runs.map((run) => run.signed_score)),
    }));
  }
  const paladinRelations = hcaEvidence.tape.runs.map((run) => run.relations.hca_paladin);
  targets.set(dedicatedRow.id, Object.freeze({
    archiveSha256: HCA_PALADIN_SHA256,
    tapeRuns: paladinRelations.length,
    pairShare: band(paladinRelations.map((relation) => relation.categories.all.overlapShare)),
    depthMedian: band(paladinRelations.map((relation) => relation.categories.all.boxOverlapDepthTiles.median)),
    frameShare: band(paladinRelations.map((relation) => relation.frameOverlapShare)),
    episodeCount: band(hcaEpisodes.map((overlap) => overlap.episodes.count)),
    episodeDurationMedianSeconds: band(
      hcaEpisodes.map((overlap) => overlap.episodes.durationSeconds.median),
    ),
    outcomeScore: band(dedicatedRow.runs.map((run) => run.signed_score)),
  }));
  const boyarRow = truth.rows.find(({ id }) => id === "elite_boyar_vs_heavy_cav_archer");
  targets.set(boyarRow.id, Object.freeze({
    archiveSha256: PHASE2_SHA256,
    tapeRuns: 1,
    pairShare: band([boyarOverlap.pairShare]),
    depthMedian: band([boyarOverlap.depthTiles.median]),
    frameShare: band([boyarOverlap.frameShare]),
    episodeCount: band([boyarOverlap.episodes.count]),
    episodeDurationMedianSeconds: band([boyarOverlap.episodes.durationSeconds.median]),
    outcomeScore: band(boyarRow.runs.map((run) => run.signed_score)),
  }));
  return targets;
}


async function analyzeBoyarTape() {
  return analyzeTapeTrace(new URL(
    "../phase2_boyar_hca_diagnosis_2026-08-17/elite_boyar_slavs__vs__heavy_cav_archer.tape_trace.jsonl",
    import.meta.url,
  ));
}


async function analyzeHcaTapeEpisodes() {
  const directory = new URL(
    "../phase2_boyar_hca_diagnosis_2026-08-17/paladin_tape/",
    import.meta.url,
  );
  const names = (await readdir(directory))
    .filter((name) => /^20v15(?:_r\d+)?\.tape_trace\.jsonl$/.test(name))
    .sort();
  return Promise.all(names.map((name) => analyzeTapeTrace(new URL(name, directory))));
}


async function analyzeTapeTrace(url) {
  const input = createInterface({
    input: createReadStream(url),
    crlfDelay: Number.POSITIVE_INFINITY,
  });
  const accumulator = createOverlapAccumulator();
  let currentTime = null;
  let frame = [];
  const flush = () => {
    if (!frame.length) return;
    const pseudoWorld = { units: frame.map((unit) => ({
      ...unit,
      alive: unit.hp > 0,
      mechanics: { collision_size_tiles: { x: 0.25 } },
    })) };
    observeWorld(accumulator, pseudoWorld);
  };
  for await (const line of input) {
    if (!line) continue;
    const unit = JSON.parse(line);
    if (currentTime !== null && unit.t_ms !== currentTime) {
      flush();
      frame = [];
    }
    currentTime = unit.t_ms;
    frame.push(unit);
  }
  flush();
  return finalizeOverlap(accumulator);
}


async function buildReport(tapeTargets) {
  const files = (await readdir(CHECKPOINTS)).filter((name) => name.endsWith(".json"));
  const checkpoints = await Promise.all(files.map((name) => (
    readFile(new URL(name, CHECKPOINTS), "utf8").then(JSON.parse)
  )));
  const rows = ROW_IDS.map((rowId) => {
    const checkpoint = checkpoints.find((entry) => (
      entry.rowId === rowId
      && entry.engineSignature === ENGINE_SIGNATURE
      && entry.experimentRevision === EXPERIMENT_REVISION
      && entry.sourceHashes?.phase2 === PHASE2_SHA256
      && entry.sourceHashes?.hcaPaladin === HCA_PALADIN_SHA256
    ));
    if (!checkpoint) return null;
    const target = tapeTargets.get(rowId);
    const availableSamples = checkpoint.samples;
    // A tape-vs-sim gate must compare like with like. In particular, the
    // Boyar-HCA archive has one recorded fight; later simulation samples only
    // reshuffle synthetic acquisition ranks against that same fixed tape and
    // are useful stress diagnostics, not additional tape-matched evidence.
    const samples = availableSamples.slice(0, target.tapeRuns);
    const stressSamples = availableSamples.slice(target.tapeRuns);
    return Object.freeze({
      rowId,
      tape: target,
      simulation: Object.freeze({
        samples: samples.length,
        availableSamples: availableSamples.length,
        pairShare: band(samples.map((sample) => sample.overlap.pairShare)),
        depthMedian: band(samples.map((sample) => sample.overlap.depthTiles.median)),
        frameShare: band(samples.map((sample) => sample.overlap.frameShare)),
        outcomeScore: band(samples.map((sample) => sample.outcome.score).filter(Number.isFinite)),
        winnerOwners: Object.freeze(samples.map((sample) => sample.outcome.winnerOwner)),
        ticks: band(samples.map((sample) => sample.outcome.ticks)),
        maximumReservations: band(samples.map((sample) => sample.transit.maximumReservations)),
        episodeCount: band(samples.map((sample) => sample.overlap.episodes.count)),
        episodeDurationMedianSeconds: band(
          samples.map((sample) => sample.overlap.episodes.durationSeconds.median),
        ),
      }),
      stressDiagnostics: Object.freeze(stressSamples.map((sample) => Object.freeze({
        sampleIndex: sample.sampleIndex,
        pairShare: sample.overlap.pairShare,
        depthMedian: sample.overlap.depthTiles.median,
        outcomeScore: sample.outcome.score,
        winnerOwner: sample.outcome.winnerOwner,
      }))),
      gates: Object.freeze({
        pairShareComparable: comparable(target.pairShare, band(samples.map((sample) => sample.overlap.pairShare))),
        depthComparable: comparable(target.depthMedian, band(samples.map((sample) => sample.overlap.depthTiles.median))),
        correctWinner: samples.every((sample) => (
          Number.isFinite(sample.outcome.score)
          && Math.sign(sample.outcome.score) === Math.sign(target.outcomeScore.median)
        )),
      }),
    });
  }).filter(Boolean);
  const report = Object.freeze({
    generatedAt: new Date().toISOString(),
    experiment: "shared pairwise enemy transit; legacy War Wagon overlap depth disabled",
    experimentRevision: EXPERIMENT_REVISION,
    engineSignature: ENGINE_SIGNATURE,
    sourceHashes: Object.freeze({ phase2: PHASE2_SHA256, hcaPaladin: HCA_PALADIN_SHA256 }),
    tapeTargets: Object.freeze(Object.fromEntries(tapeTargets)),
    rows: Object.freeze(rows),
  });
  await atomicJson(REPORT_JSON, report);
  const table = [
    "# Shared enemy pair-transit overlap experiment",
    "",
    `Generated ${report.generatedAt}. Percentages below are all live enemy-pair observations, not frames. Gates use at most one simulation run per recorded golden tape; extra synthetic acquisition-order runs remain in report.json as stress diagnostics.`,
    "",
    "| Golden row | Tape pair overlap | Sim pair overlap | Tape conditional median depth | Sim conditional median depth | Winner | Gate |",
    "|---|---:|---:|---:|---:|---|---|",
    ...rows.map((row) => (
      `| ${row.rowId} | ${percent(row.tape.pairShare.median)} | ${percent(row.simulation.pairShare.median)} | `
      + `${row.tape.depthMedian.median} | ${row.simulation.depthMedian.median} | `
      + `${row.gates.correctWinner ? "correct" : "wrong"} | `
      + `${row.gates.pairShareComparable && row.gates.depthComparable ? "comparable" : "miss"} |`
    )),
    "",
  ].join("\n");
  await writeFile(REPORT_MD, table, "utf8");
  process.stdout.write(`${table}\n`);
}


async function atomicJson(url, value) {
  const temporary = new URL(`${url.pathname}.${process.pid}.tmp`, url);
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await rename(temporary, url);
}


async function loadCheckpointSamples(url, rowId, requested) {
  let checkpoint;
  try {
    checkpoint = JSON.parse(await readFile(url, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
  const reusable = checkpoint.rowId === rowId
    && checkpoint.engineSignature === ENGINE_SIGNATURE
    && checkpoint.experimentRevision === EXPERIMENT_REVISION
    && checkpoint.sourceHashes?.phase2 === PHASE2_SHA256
    && checkpoint.sourceHashes?.hcaPaladin === HCA_PALADIN_SHA256
    && Array.isArray(checkpoint.samples);
  if (!reusable) return [];
  const samples = checkpoint.samples.slice(0, requested);
  process.stdout.write(`${rowId}: resuming ${samples.length}/${requested} signed samples\n`);
  return samples;
}


function comparable(tape, simulation) {
  if (!Number.isFinite(tape?.median) || !Number.isFinite(simulation?.median)) return false;
  const lower = Math.max(0, tape.min * 0.75);
  const upper = tape.max * 1.25;
  return simulation.median >= lower && simulation.median <= upper;
}


function band(values) {
  const sorted = values.filter(Number.isFinite).sort((left, right) => left - right);
  if (!sorted.length) return Object.freeze({ min: null, median: null, max: null });
  return Object.freeze({
    min: round(sorted[0]),
    median: round(sorted[Math.floor((sorted.length - 1) / 2)]),
    max: round(sorted.at(-1)),
  });
}


function quantiles(values) {
  const sorted = values.sort((left, right) => left - right);
  if (!sorted.length) return Object.freeze({ min: null, median: null, p90: null, max: null });
  const at = (fraction) => sorted[Math.floor((sorted.length - 1) * fraction)];
  return Object.freeze({ min: round(at(0)), median: round(at(0.5)), p90: round(at(0.9)), max: round(at(1)) });
}


function ratio(numerator, denominator) {
  return denominator ? round(numerator / denominator) : null;
}


function percent(value) {
  return Number.isFinite(value) ? `${(100 * value).toFixed(3)}%` : "n/a";
}


function round(value, digits = 6) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}


async function buildEngineSignature() {
  const combatRoot = new URL("src/combat/", ROOT);
  const combatFiles = (await readdir(combatRoot))
    .filter((name) => name.endsWith(".js"))
    .sort()
    .map((name) => new URL(name, combatRoot));
  const scenarioFiles = [
    "src/dedicated-golden-comparison.js",
    "src/phase2-batch1-comparison.js",
    "src/standard-units-comparison.js",
  ].map((name) => new URL(name, ROOT));
  const hash = createHash("sha256");
  hash.update(`experiment-revision:${EXPERIMENT_REVISION}\n`);
  hash.update(`pairwise-allied-transit:${args.has("allied")}\n`);
  for (const url of [...combatFiles, ...scenarioFiles]) {
    hash.update(`${url.pathname}\n`);
    hash.update(await readFile(url));
  }
  return hash.digest("hex").toUpperCase();
}
