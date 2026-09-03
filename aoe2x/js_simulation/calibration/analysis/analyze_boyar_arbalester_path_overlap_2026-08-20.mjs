import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";

import { createWorld, stepWorld } from "../../src/combat/world.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../../src/phase2-batch1-comparison.js";
import {
  normalizeSimulationSnapshots,
  normalizeTapeFrames,
} from "../../tools/measure_pair_contact_states.mjs";
import { analyzePairContactFrames, percentile } from "../../tools/pair-contact-metrics.mjs";


const ROOT = new URL("../../", import.meta.url);
const ROW_ID = "elite_boyar_vs_arbalester";
const EXPECTED_SHA256 = "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6";
const TRACE = new URL(
  "boyar_arbalester_2026-08-20/tape/"
    + "elite_boyar_slavs__vs__arbalester.tape_trace.jsonl",
  import.meta.url,
);
const OUTPUT = new URL("boyar_arbalester_2026-08-20/report.json", import.meta.url);
const CADENCE_MS = 100;
const SAMPLES = 5;
const SEED = 20260817;
const TICKS_PER_SECOND = 60;
const CENTER = Object.freeze({ x: 9, y: 7, radius: 1.5 });


const truth = await loadPhase2Batch1Truth(ROOT);
const row = truth.rows.find(({ id }) => id === ROW_ID);
if (!row || row.runs.length !== 1 || truth.archive?.zip_sha256 !== EXPECTED_SHA256) {
  throw new Error("missing authorized Arbalester-Elite Boyar row");
}
const archivePath = new URL(`../../${truth.archive.path}`, ROOT);
const observedHash = await sha256(archivePath);
if (observedHash !== EXPECTED_SHA256) {
  throw new Error(`Phase 2 archive hash mismatch: ${observedHash}`);
}
const context = await loadPhase2Batch1Context(ROOT, truth);
const rosterIds = new Set(row.runs[0].starting_units.map(({ id }) => id));
const rawTapeFrames = await readTapeTrace(TRACE, rosterIds);
const tapeFrames = trimCombatFrames(normalizeTapeFrames(
  rawTapeFrames,
  context.mechanicsByMaster,
  { cadenceMs: CADENCE_MS },
));

const simulationRuns = [];
for (let sampleIndex = 0; sampleIndex < SAMPLES; sampleIndex += 1) {
  simulationRuns.push(runSimulation({ row, sampleIndex, context }));
}

const tape = analyzeFrames(tapeFrames);
const simulation = simulationRuns.map(({ sampleIndex, outcome, ticks, frames }) => Object.freeze({
  sampleIndex,
  outcome,
  ticks,
  durationSeconds: ticks / TICKS_PER_SECOND,
  ...analyzeFrames(frames),
}));
const report = Object.freeze({
  schemaVersion: 1,
  rowId: ROW_ID,
  matchup: row.matchup,
  source: Object.freeze({
    archive: truth.archive.name,
    expectedZipSha256: EXPECTED_SHA256,
    observedZipSha256: observedHash,
    tapeTrace: TRACE.pathname,
  }),
  sampling: Object.freeze({ cadenceMs: CADENCE_MS, simulationSamples: SAMPLES, seed: SEED }),
  obstacle: Object.freeze({
    center: CENTER,
    routeSide: "cardinal sector around (9, 7), selected by the dominant center offset",
    aroundThreshold: "individual angular span around center >= 90 degrees",
    coreClearance: "Euclidean center distance minus (1.5-tile solid core + unit radius)",
  }),
  roster: Object.freeze({ side2: row.side2, side3: row.side3 }),
  tape: Object.freeze({
    repeat: row.runs[0].repeat,
    frames: tapeFrames.length,
    durationSeconds: frameDuration(tapeFrames),
    outcome: Object.freeze({
      winnerOwner: row.runs[0].winner_owner,
      winnerHp: row.runs[0].winner_hp,
      signedScore: row.runs[0].signed_score,
    }),
    ...tape,
  }),
  simulation: Object.freeze({
    runs: Object.freeze(simulation),
    aggregate: aggregateSimulation(simulation),
  }),
});

await mkdir(new URL("boyar_arbalester_2026-08-20/", import.meta.url), { recursive: true });
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);


async function sha256(url) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(url)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}


async function readTapeTrace(url, roster) {
  const frames = [];
  let timeMs = null;
  let units = [];
  const lines = createInterface({ input: createReadStream(url), crlfDelay: Infinity });
  for await (const line of lines) {
    if (!line) continue;
    const raw = JSON.parse(line);
    if (!roster.has(raw.id)) continue;
    if (timeMs !== null && raw.t_ms !== timeMs) {
      frames.push({ timeMs, units });
      units = [];
    }
    timeMs = raw.t_ms;
    units.push(raw);
  }
  if (timeMs !== null) frames.push({ timeMs, units });
  if (frames.length === 0) throw new Error("decoded tape trace has no canonical roster frames");
  return frames;
}


function runSimulation({ row: selectedRow, sampleIndex, context: selectedContext }) {
  const scenario = scenarioFromPhase2Batch1Row({
    row: selectedRow,
    sampleIndex,
    seed: SEED,
    context: selectedContext,
  });
  let world = createWorld(scenario);
  const snapshots = [{ tick: 0, units: world.units }];
  let outcome = "timeout";
  for (let elapsed = 0; elapsed < PHASE2_MAX_TICKS; elapsed += 1) {
    world = stepWorld(world);
    if (world.tick % 6 === 0) snapshots.push({ tick: world.tick, units: world.units });
    if (liveOwnerCount(world.units) <= 1) {
      outcome = "win";
      if (snapshots.at(-1)?.tick !== world.tick) {
        snapshots.push({ tick: world.tick, units: world.units });
      }
      break;
    }
    world = Object.freeze({ ...world, snapshots: Object.freeze([]), eventLog: Object.freeze([]) });
  }
  return Object.freeze({
    sampleIndex,
    outcome,
    ticks: world.tick,
    frames: trimCombatFrames(normalizeSimulationSnapshots(snapshots, { cadenceMs: CADENCE_MS })),
  });
}


function analyzeFrames(frames) {
  return Object.freeze({
    route: analyzeArbalesterRoute(frames),
    overlap: Object.freeze({
      arbalesterAllies: overlapForOwner(frames, 2),
      boyarAllies: overlapForOwner(frames, 3),
      enemies: overlapSummary(
        analyzePairContactFrames(frames).relationships.enemies,
      ),
    }),
  });
}


function overlapForOwner(frames, owner) {
  const filtered = frames.map((frame) => Object.freeze({
    ...frame,
    units: Object.freeze(frame.units.filter((unit) => unit.owner === owner)),
  }));
  return overlapSummary(
    analyzePairContactFrames(filtered).relationships["same-master-allies"],
  );
}


function overlapSummary(metric) {
  if (!metric) return null;
  return Object.freeze({
    pairObservations: metric.pairFrames,
    overlappingPairObservations: metric.overlapPairs,
    overlapPairShare: metric.overlapPairShare,
    frameCount: metric.frameCount,
    framesWithOverlap: metric.framesWithOverlap,
    frameOverlapShare: ratio(metric.framesWithOverlap, metric.frameCount),
    medianDepth: metric.medianDepth,
    p95Depth: metric.p95Depth,
    maximumDepth: metric.maximumDepth,
    medianContactWindowMs: metric.contactWindowMs?.median ?? null,
    maximumContactWindowMs: metric.contactWindowMs?.maximum ?? null,
    maximumLocalDegree: metric.maximumLocalDegree,
    maximumComponentSize: metric.maximumComponentSize,
    maximumTriangles: metric.maximumTriangles,
    maximumFourCliques: metric.maximumFourCliques,
  });
}


function analyzeArbalesterRoute(frames) {
  const byId = new Map();
  const centroidSamples = [];
  const sideFrameCounts = new Map([
    ["below", 0], ["right", 0], ["above", 0], ["left", 0],
  ]);
  let framesSplitAcrossSides = 0;
  let minimumCoreClearance = Infinity;
  for (const frame of frames) {
    const units = frame.units.filter(({ owner, hp }) => owner === 2 && hp > 0);
    if (units.length === 0) continue;
    const centroid = {
      timeMs: frame.timeMs,
      x: units.reduce((sum, unit) => sum + unit.x, 0) / units.length,
      y: units.reduce((sum, unit) => sum + unit.y, 0) / units.length,
      count: units.length,
    };
    centroid.side = centerSide(centroid);
    centroidSamples.push(centroid);
    sideFrameCounts.set(centroid.side, sideFrameCounts.get(centroid.side) + 1);
    const occupiedSides = new Set();
    for (const unit of units) {
      occupiedSides.add(centerSide(unit));
      minimumCoreClearance = Math.min(
        minimumCoreClearance,
        Math.hypot(unit.x - CENTER.x, unit.y - CENTER.y) - CENTER.radius - unit.radius,
      );
      if (!byId.has(unit.id)) byId.set(unit.id, []);
      byId.get(unit.id).push({
        timeMs: frame.timeMs,
        x: unit.x,
        y: unit.y,
        radius: unit.radius,
      });
    }
    if (occupiedSides.size > 1) framesSplitAcrossSides += 1;
  }
  const unitRoutes = [...byId].map(([id, samples]) => summarizeAngularRoute(id, samples));
  const centroidRoute = summarizeAngularRoute("centroid", centroidSamples);
  const aroundCount = unitRoutes.filter(({ angularSpanDegrees }) => angularSpanDegrees >= 90).length;
  return Object.freeze({
    center: CENTER,
    centroid: centroidRoute,
    centroidSideSequence: Object.freeze(compressSideSequence(centroidSamples)),
    centroidSideFrameShare: Object.freeze(Object.fromEntries(
      [...sideFrameCounts].map(([side, count]) => [side, ratio(count, centroidSamples.length)]),
    )),
    framesSplitAcrossSides,
    splitAcrossSidesShare: ratio(framesSplitAcrossSides, centroidSamples.length),
    trackedArbalesters: unitRoutes.length,
    arbalestersWithAtLeastQuarterTurn: aroundCount,
    arbalesterQuarterTurnShare: ratio(aroundCount, unitRoutes.length),
    individualAngularSpanDegrees: distribution(
      unitRoutes.map(({ angularSpanDegrees }) => angularSpanDegrees),
    ),
    minimumCoreClearance: clean(minimumCoreClearance),
    unitsEnteringSolidCore: unitRoutes.filter(({ minimumCoreClearance }) => (
      minimumCoreClearance < -1e-9
    )).length,
    unitRoutes: Object.freeze(unitRoutes),
  });
}


function summarizeAngularRoute(id, samples) {
  let previousAngle = null;
  let unwrapped = 0;
  let minimum = 0;
  let maximum = 0;
  let minimumCoreClearance = Infinity;
  const sides = new Set();
  for (const sample of samples) {
    const angle = Math.atan2(sample.y - CENTER.y, sample.x - CENTER.x);
    if (previousAngle !== null) {
      let delta = angle - previousAngle;
      while (delta > Math.PI) delta -= 2 * Math.PI;
      while (delta < -Math.PI) delta += 2 * Math.PI;
      unwrapped += delta;
      minimum = Math.min(minimum, unwrapped);
      maximum = Math.max(maximum, unwrapped);
    }
    previousAngle = angle;
    sides.add(centerSide(sample));
    const radius = sample.radius ?? 0;
    minimumCoreClearance = Math.min(
      minimumCoreClearance,
      Math.hypot(sample.x - CENTER.x, sample.y - CENTER.y) - CENTER.radius - radius,
    );
  }
  return Object.freeze({
    id,
    observations: samples.length,
    start: samples.length ? Object.freeze({ x: clean(samples[0].x), y: clean(samples[0].y) }) : null,
    end: samples.length ? Object.freeze({ x: clean(samples.at(-1).x), y: clean(samples.at(-1).y) }) : null,
    angularSpanDegrees: clean(180 * (maximum - minimum) / Math.PI),
    netAngularDegrees: clean(180 * unwrapped / Math.PI),
    sidesVisited: Object.freeze([...sides]),
    minimumCoreClearance: clean(minimumCoreClearance),
  });
}


function centerSide(point) {
  const dx = point.x - CENTER.x;
  const dy = point.y - CENTER.y;
  if (Math.abs(dx) > Math.abs(dy)) return dx >= 0 ? "right" : "left";
  return dy >= 0 ? "above" : "below";
}


function compressSideSequence(samples) {
  const result = [];
  for (const sample of samples) {
    const side = sample.side ?? centerSide(sample);
    if (result.at(-1)?.side === side) {
      result.at(-1).endMs = sample.timeMs;
      continue;
    }
    result.push({ side, startMs: sample.timeMs, endMs: sample.timeMs });
  }
  return result;
}


function aggregateSimulation(runs) {
  const overlap = {};
  for (const relationship of ["arbalesterAllies", "boyarAllies", "enemies"]) {
    overlap[relationship] = {};
    for (const field of [
      "overlapPairShare", "frameOverlapShare", "medianDepth", "p95Depth", "maximumDepth",
      "medianContactWindowMs", "maximumLocalDegree", "maximumComponentSize",
    ]) {
      overlap[relationship][field] = distribution(
        runs.map((run) => run.overlap[relationship]?.[field]).filter(Number.isFinite),
      );
    }
  }
  return Object.freeze({
    overlap: Object.freeze(overlap),
    route: Object.freeze({
      centroidAngularSpanDegrees: distribution(
        runs.map((run) => run.route.centroid.angularSpanDegrees),
      ),
      arbalesterQuarterTurnShare: distribution(
        runs.map((run) => run.route.arbalesterQuarterTurnShare),
      ),
      splitAcrossSidesShare: distribution(
        runs.map((run) => run.route.splitAcrossSidesShare),
      ),
      minimumCoreClearance: distribution(
        runs.map((run) => run.route.minimumCoreClearance),
      ),
    }),
  });
}


function trimCombatFrames(frames) {
  const first = frames.findIndex(({ units }) => liveOwnerCount(units) >= 2);
  if (first < 0) throw new Error("no two-owner combat frame");
  let last = frames.length - 1;
  for (let index = first + 1; index < frames.length; index += 1) {
    if (liveOwnerCount(frames[index].units) < 2) {
      last = index;
      break;
    }
  }
  return frames.slice(first, last + 1);
}


function liveOwnerCount(units) {
  return new Set(units.filter(({ hp, alive = hp > 0 }) => alive && hp > 0)
    .map(({ owner }) => owner)).size;
}


function frameDuration(frames) {
  return (frames.at(-1).timeMs - frames[0].timeMs) / 1000;
}


function distribution(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  return Object.freeze({
    count: sorted.length,
    minimum: sorted.length ? clean(sorted[0]) : null,
    median: percentile(sorted, 0.5),
    maximum: sorted.length ? clean(sorted.at(-1)) : null,
  });
}


function ratio(numerator, denominator) {
  return denominator > 0 ? clean(numerator / denominator) : 0;
}


function clean(value) {
  return Number.isFinite(value) ? Math.round(value * 1e12) / 1e12 : null;
}
