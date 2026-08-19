import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import {
  access,
  mkdir,
  open,
  readFile,
  rename,
} from "node:fs/promises";
import { join, resolve } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath, pathToFileURL } from "node:url";

import { createWorld, stepWorld } from "../src/combat/world.js";
import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  scenarioFromPhase2Batch1Row,
} from "../src/phase2-batch1-comparison.js";
import { analyzePairContactFrames, percentile } from "./pair-contact-metrics.mjs";

const ROOT = new URL("../", import.meta.url);
const EMPTY = Object.freeze([]);
const DEFAULT_SEED = 20260817;
const DEFAULT_CADENCE_MS = 100;
const TICKS_PER_SECOND = 60;
const TAPE_ATTACK_STATE = 7;
const MOVEMENT_EPSILON = 1e-9;

export const PHASE2_ARCHIVE = Object.freeze({
  name: "aoe2_golden_phase2_WITH_TAPES.zip",
  zipSha256: "B16971F01C2B88397F9278DDE3752C2949D470F966F99CDBE1E72E9FF3CE3AC6",
});

export function validateAnalysisSource(archive) {
  const name = archive?.name ?? archive?.archive;
  const zipSha256 = archive?.zip_sha256 ?? archive?.zipSha256;
  if (name !== PHASE2_ARCHIVE.name || zipSha256 !== PHASE2_ARCHIVE.zipSha256) {
    throw new Error("pair-contact analysis requires the authorized Phase 2 archive");
  }
  return true;
}

export function normalizeTapeFrames(
  rawFrames,
  mechanicsByMaster,
  { cadenceMs = DEFAULT_CADENCE_MS } = {},
) {
  requireMechanicsMap(mechanicsByMaster);
  const sampled = resampleFrames(rawFrames, cadenceMs);
  return normalizeSampledFrames(sampled, mechanicsByMaster, (raw) => {
    const targetId = Number.isSafeInteger(raw.target_id) && raw.target_id >= 0
      ? raw.target_id
      : null;
    const attacking = raw.action_state === TAPE_ATTACK_STATE;
    return {
      id: raw.id,
      owner: raw.owner,
      master: raw.master,
      x: raw.x,
      y: raw.y,
      hp: raw.hp,
      attacking,
      pursuitTargetId: targetId,
      engagedTargetId: targetId,
      attackTargetId: attacking ? targetId : null,
    };
  });
}

export function normalizeSimulationSnapshots(snapshots, { cadenceMs = DEFAULT_CADENCE_MS } = {}) {
  const rawFrames = snapshots.map((snapshot) => ({
    timeMs: 1000 * snapshot.tick / TICKS_PER_SECOND,
    units: snapshot.units.map((unit) => ({
      id: unit.referenceId,
      owner: unit.owner,
      master: unit.mechanics.unit_master,
      x: unit.x,
      y: unit.y,
      hp: unit.hp,
      attacking: unit.action === "attacking",
      pursuitTargetId: unit.pursuitTargetId,
      engagedTargetId: unit.engagedTargetId,
      attackTargetId: unit.attackTargetId,
      mechanics: unit.mechanics,
    })),
  }));
  const sampled = resampleFrames(rawFrames, cadenceMs);
  const previous = new Map();
  return sampled.map((frame) => {
    const units = frame.units.map((raw) => {
      const before = previous.get(raw.id);
      const moving = before !== undefined
        && Math.hypot(raw.x - before.x, raw.y - before.y) > MOVEMENT_EPSILON;
      previous.set(raw.id, raw);
      return Object.freeze({
        id: raw.id,
        owner: raw.owner,
        master: raw.master,
        x: raw.x,
        y: raw.y,
        hp: raw.hp,
        radius: collisionRadius(raw.mechanics),
        minCollisionMultiplier: minimumCollisionMultiplier(raw.mechanics),
        moving,
        attacking: raw.attacking,
        pursuitTargetId: raw.pursuitTargetId ?? null,
        engagedTargetId: raw.engagedTargetId ?? null,
        attackTargetId: raw.attackTargetId ?? null,
      });
    });
    return Object.freeze({ timeMs: frame.timeMs, units: Object.freeze(units) });
  });
}

export async function runPairContactAnalysis({
  rowIds,
  traceDirectories,
  outputDirectory,
  samples = 5,
  seed = DEFAULT_SEED,
  cadenceMs = DEFAULT_CADENCE_MS,
  root = ROOT,
}) {
  requireRunOptions({ rowIds, traceDirectories, outputDirectory, samples, seed, cadenceMs });
  const truth = await loadPhase2Batch1Truth(root);
  validateAnalysisSource(truth.archive);
  const sourceManifest = JSON.parse(await readFile(
    new URL("calibration/source/phase2_source.json", root),
    "utf8",
  ));
  validateAnalysisSource(sourceManifest);
  if (sourceManifest.authorized !== true) {
    throw new Error("Phase 2 source manifest is not authorized");
  }
  const archivePath = resolve(
    fileURLToPath(new URL("../../", root)),
    truth.archive.path,
  );
  const observedArchiveHash = await sha256File(archivePath);
  if (observedArchiveHash !== PHASE2_ARCHIVE.zipSha256) {
    throw new Error(`authorized Phase 2 archive hash mismatch: ${observedArchiveHash}`);
  }

  const selectedRows = selectRows(truth.rows, rowIds);
  const context = await loadPhase2Batch1Context(root, truth);
  const rows = [];
  for (const row of selectedRows) {
    rows.push(await analyzeRow({
      row,
      traceDirectories,
      context,
      samples,
      seed,
      cadenceMs,
    }));
  }

  const report = Object.freeze({
    schemaVersion: 1,
    source: Object.freeze({
      name: PHASE2_ARCHIVE.name,
      zipSha256: PHASE2_ARCHIVE.zipSha256,
      projectLocalPath: truth.archive.path,
      observedZipSha256: observedArchiveHash,
    }),
    sampling: Object.freeze({
      cadenceMs,
      simulationTicksPerSample: Math.round(cadenceMs * TICKS_PER_SECOND / 1000),
      samples,
      seed,
    }),
    geometry: Object.freeze({
      separation: "Chebyshev max(abs(dx), abs(dy))",
      fullExtent: "left collision radius + right collision radius",
      movement: "sample-to-sample center displacement",
    }),
    rows: Object.freeze(rows),
  });
  const markdown = renderPairContactMarkdown(report);
  const manifest = Object.freeze({
    schemaVersion: 1,
    source: report.source,
    rowIds: Object.freeze(rows.map(({ id }) => id)),
    traceDirectories: Object.freeze(traceDirectories.map((directory) => resolve(directory))),
    samples,
    seed,
    cadenceMs,
    completedRows: rows.length,
    files: Object.freeze(["report.json", "report.md", "run-manifest.json"]),
  });

  await mkdir(outputDirectory, { recursive: true });
  await atomicWrite(join(outputDirectory, "report.json"), `${JSON.stringify(report, null, 2)}\n`);
  await atomicWrite(join(outputDirectory, "report.md"), markdown);
  await atomicWrite(
    join(outputDirectory, "run-manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );
  return report;
}

export function renderPairContactMarkdown(report) {
  if (!report?.source?.name || !report?.source?.zipSha256 || !Array.isArray(report.rows)) {
    throw new TypeError("pair-contact report source and rows are required");
  }
  const lines = [
    "# Generic melee pair-contact analysis",
    "",
    `- Golden archive: \`${report.source.name}\``,
    `- SHA-256: \`${report.source.zipSha256}\``,
    `- Sampling cadence: ${report.sampling?.cadenceMs ?? "unknown"} ms`,
    `- Simulation samples per row: ${report.sampling?.samples ?? "unknown"}`,
    `- Seed: ${report.sampling?.seed ?? "unknown"}`,
    "",
    "Pair populations are named `relationship|motion|attack|intent|phase`.",
    "Depth uses axis-aligned collision extents. Contact windows remain relationship-wide.",
    "",
  ];
  for (const row of report.rows) {
    lines.push(`## ${row.matchup ?? row.id}`, "", `Row ID: \`${row.id}\``, "");
    lines.push(
      "| Source | Run | Population | Pair share | p05 depth | Median depth | p95 depth | Window median (ms) | Max local degree | Max component | Triangles | Four-cliques |",
      "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    );
    let populationCount = 0;
    for (const [sourceName, source] of [["Tape", row.tape], ["Simulation", row.simulation]]) {
      for (const run of source?.runs ?? []) {
        for (const [key, metrics] of Object.entries(run.metrics?.populations ?? {})) {
          populationCount += 1;
          lines.push([
            sourceName,
            run.label,
            `\`${key}\``,
            formatNumber(metrics.overlapPairShare),
            formatNumber(metrics.p05Depth),
            formatNumber(metrics.medianDepth),
            formatNumber(metrics.p95Depth),
            formatNumber(metrics.contactWindowMs?.median),
            formatNumber(metrics.maximumLocalDegree),
            formatNumber(metrics.maximumComponentSize),
            formatNumber(metrics.maximumTriangles),
            formatNumber(metrics.maximumFourCliques),
          ].join(" | ").replace(/^/, "| ").replace(/$/, " |"));
        }
      }
    }
    if (populationCount === 0) {
      lines.push("| — | — | No contact populations | — | — | — | — | — | — | — | — | — |");
    }
    lines.push("");
  }
  return `${lines.join("\n").trimEnd()}\n`;
}

export async function main(argv = process.argv.slice(2)) {
  const options = parseArguments(argv);
  const report = await runPairContactAnalysis(options);
  process.stdout.write(`${JSON.stringify({
    rows: report.rows.length,
    samples: report.sampling.samples,
    source: report.source.name,
    zipSha256: report.source.zipSha256,
    outputDirectory: resolve(options.outputDirectory),
  }, null, 2)}\n`);
}

async function analyzeRow({ row, traceDirectories, context, samples, seed, cadenceMs }) {
  const tapeRuns = [];
  for (const run of row.runs) {
    const tracePath = await findTracePath(traceDirectories, run.tag);
    const rawFrames = await readTapeTrace(tracePath, new Set(run.starting_units.map(({ id }) => id)));
    const frames = trimCombatFrames(normalizeTapeFrames(
      rawFrames,
      context.mechanicsByMaster,
      { cadenceMs },
    ));
    tapeRuns.push(Object.freeze({
      label: `repeat-${run.repeat}`,
      repeat: run.repeat,
      trace: Object.freeze({
        file: tracePath,
        sha256: await sha256File(tracePath),
      }),
      frameCount: frames.length,
      metrics: analyzePairContactFrames(frames),
    }));
  }

  const simulationRuns = [];
  for (let sampleIndex = 0; sampleIndex < samples; sampleIndex += 1) {
    const result = runSimulationFrames({ row, sampleIndex, seed, context, cadenceMs });
    simulationRuns.push(Object.freeze({
      label: `sample-${sampleIndex}`,
      sampleIndex,
      outcome: result.outcome,
      ticks: result.ticks,
      frameCount: result.frames.length,
      metrics: analyzePairContactFrames(result.frames),
    }));
  }
  return Object.freeze({
    id: row.id,
    matchup: row.matchup,
    side2: row.side2,
    side3: row.side3,
    tape: Object.freeze({
      runs: Object.freeze(tapeRuns),
      aggregate: aggregateMetricRuns(tapeRuns),
    }),
    simulation: Object.freeze({
      runs: Object.freeze(simulationRuns),
      aggregate: aggregateMetricRuns(simulationRuns),
    }),
  });
}

function runSimulationFrames({ row, sampleIndex, seed, context, cadenceMs }) {
  const scenario = scenarioFromPhase2Batch1Row({ row, sampleIndex, seed, context });
  let world = createWorld(scenario);
  const snapshots = [{ tick: 0, units: world.units }];
  let outcome = "timeout";
  for (let elapsed = 0; elapsed < PHASE2_MAX_TICKS; elapsed += 1) {
    world = stepWorld(world);
    const shouldSample = Math.abs(
      (1000 * world.tick / TICKS_PER_SECOND) / cadenceMs
        - Math.round((1000 * world.tick / TICKS_PER_SECOND) / cadenceMs),
    ) < 1e-9;
    if (shouldSample) snapshots.push({ tick: world.tick, units: world.units });
    const liveOwners = new Set(world.units.filter(({ alive }) => alive).map(({ owner }) => owner));
    if (liveOwners.size <= 1) {
      outcome = "win";
      if (snapshots.at(-1)?.tick !== world.tick) {
        snapshots.push({ tick: world.tick, units: world.units });
      }
      break;
    }
    world = Object.freeze({ ...world, snapshots: EMPTY, eventLog: EMPTY });
  }
  return Object.freeze({
    outcome,
    ticks: world.tick,
    frames: trimCombatFrames(normalizeSimulationSnapshots(snapshots, { cadenceMs })),
  });
}

function normalizeSampledFrames(sampled, mechanicsByMaster, convert) {
  const previous = new Map();
  return sampled.map((frame) => {
    const units = frame.units.map((raw) => {
      const converted = convert(raw);
      const mechanics = mechanicsByMaster.get(converted.master);
      if (!mechanics) throw new Error(`missing mechanics for master ${converted.master}`);
      const before = previous.get(converted.id);
      const moving = before !== undefined
        && Math.hypot(converted.x - before.x, converted.y - before.y) > MOVEMENT_EPSILON;
      previous.set(converted.id, converted);
      return Object.freeze({
        ...converted,
        radius: collisionRadius(mechanics),
        minCollisionMultiplier: minimumCollisionMultiplier(mechanics),
        moving,
      });
    });
    return Object.freeze({ timeMs: frame.timeMs, units: Object.freeze(units) });
  });
}

function resampleFrames(rawFrames, cadenceMs) {
  if (!Array.isArray(rawFrames)) throw new TypeError("raw frames must be an array");
  if (!Number.isFinite(cadenceMs) || cadenceMs <= 0) {
    throw new RangeError("cadenceMs must be positive");
  }
  if (rawFrames.length === 0) return [];
  const ordered = [...rawFrames].sort((left, right) => left.timeMs - right.timeMs);
  const sampled = [];
  let cursor = 0;
  for (
    let target = ordered[0].timeMs;
    target <= ordered.at(-1).timeMs + MOVEMENT_EPSILON;
    target += cadenceMs
  ) {
    while (cursor + 1 < ordered.length
        && Math.abs(ordered[cursor + 1].timeMs - target)
          <= Math.abs(ordered[cursor].timeMs - target)) {
      cursor += 1;
    }
    if (sampled.at(-1) !== ordered[cursor]) sampled.push(ordered[cursor]);
  }
  return sampled;
}

async function readTapeTrace(tracePath, rosterIds) {
  const frames = [];
  let timeMs = null;
  let units = [];
  const lines = createInterface({
    input: createReadStream(tracePath),
    crlfDelay: Infinity,
  });
  for await (const line of lines) {
    if (!line) continue;
    const raw = JSON.parse(line);
    if (!rosterIds.has(raw.id)) continue;
    if (!Number.isFinite(raw.t_ms)) {
      throw new Error(`trace has invalid t_ms: ${tracePath}`);
    }
    if (timeMs !== null && raw.t_ms !== timeMs) {
      frames.push({ timeMs, units });
      units = [];
    }
    timeMs = raw.t_ms;
    units.push(raw);
  }
  if (timeMs !== null) frames.push({ timeMs, units });
  if (frames.length === 0) throw new Error(`trace has no canonical roster frames: ${tracePath}`);
  return frames;
}

function trimCombatFrames(frames) {
  const first = frames.findIndex(({ units }) => liveOwnerCount(units) >= 2);
  if (first < 0) throw new Error("pair-contact run has no frame with two live owners");
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
  return new Set(units.filter(({ hp }) => hp > 0).map(({ owner }) => owner)).size;
}

function aggregateMetricRuns(runs) {
  const aggregate = { populations: {}, relationships: {} };
  for (const category of ["populations", "relationships"]) {
    const keys = new Set(runs.flatMap((run) => Object.keys(run.metrics[category])));
    for (const key of [...keys].sort()) {
      const present = runs.map((run) => run.metrics[category][key]).filter(Boolean);
      const fields = {};
      for (const field of [
        "overlapPairShare",
        "p05Depth",
        "medianDepth",
        "p95Depth",
        "maximumLocalDegree",
        "maximumComponentSize",
        "maximumTriangles",
        "maximumFourCliques",
      ]) {
        const values = present.map((metrics) => metrics[field]).filter(Number.isFinite);
        fields[field] = metricRange(values);
      }
      const windows = present
        .map((metrics) => metrics.contactWindowMs?.median)
        .filter(Number.isFinite);
      fields.medianContactWindowMs = metricRange(windows);
      aggregate[category][key] = Object.freeze({
        presentRuns: present.length,
        totalRuns: runs.length,
        metrics: Object.freeze(fields),
      });
    }
  }
  return Object.freeze({
    populations: Object.freeze(aggregate.populations),
    relationships: Object.freeze(aggregate.relationships),
  });
}

function metricRange(values) {
  return Object.freeze({
    count: values.length,
    minimum: values.length ? Math.min(...values) : null,
    median: percentile(values, 0.5),
    maximum: values.length ? Math.max(...values) : null,
  });
}

function selectRows(rows, rowIds) {
  const byId = new Map(rows.map((row) => [row.id, row]));
  const selected = rowIds.map((rowId) => {
    const row = byId.get(rowId);
    if (!row) throw new RangeError(`unknown Phase 2 row: ${rowId}`);
    return row;
  });
  if (new Set(rowIds).size !== rowIds.length) {
    throw new Error("Phase 2 row IDs must be unique");
  }
  return selected;
}

async function findTracePath(traceDirectories, tag) {
  for (const directory of traceDirectories) {
    const candidate = resolve(directory, `${tag}.tape_trace.jsonl`);
    try {
      await access(candidate);
      return candidate;
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
  }
  throw new Error(
    `missing manifested tape trace for ${tag}; decode that exact archive member before analysis`,
  );
}

function collisionRadius(mechanics) {
  const radius = Math.max(
    mechanics?.collision_size_tiles?.x ?? NaN,
    mechanics?.collision_size_tiles?.y ?? NaN,
  );
  if (!Number.isFinite(radius) || radius < 0) {
    throw new Error(`invalid sourced collision radius for master ${mechanics?.unit_master}`);
  }
  return radius;
}

function minimumCollisionMultiplier(mechanics) {
  const multiplier = mechanics?.min_collision_size_multiplier ?? 1;
  if (!Number.isFinite(multiplier) || multiplier <= 0 || multiplier > 1) {
    throw new Error(`invalid sourced minimum collision multiplier for master ${mechanics?.unit_master}`);
  }
  return multiplier;
}

function requireMechanicsMap(mechanicsByMaster) {
  if (!(mechanicsByMaster instanceof Map)) {
    throw new TypeError("mechanicsByMaster must be a Map");
  }
}

function requireRunOptions({ rowIds, traceDirectories, outputDirectory, samples, seed, cadenceMs }) {
  if (!Array.isArray(rowIds) || rowIds.length === 0 || rowIds.some((id) => !id)) {
    throw new TypeError("rowIds must be a nonempty array");
  }
  if (!Array.isArray(traceDirectories) || traceDirectories.length === 0) {
    throw new TypeError("traceDirectories must be a nonempty array");
  }
  if (typeof outputDirectory !== "string" || !outputDirectory) {
    throw new TypeError("outputDirectory is required");
  }
  if (!Number.isSafeInteger(samples) || samples < 1 || samples > 15) {
    throw new RangeError("samples must be a safe integer from 1 through 15");
  }
  if (!Number.isSafeInteger(seed)) throw new RangeError("seed must be a safe integer");
  if (!Number.isFinite(cadenceMs) || cadenceMs <= 0) {
    throw new RangeError("cadenceMs must be positive");
  }
}

function parseArguments(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!flag?.startsWith("--") || value === undefined) {
      throw new Error(`expected --flag value, got ${flag ?? "end of arguments"}`);
    }
    if (values.has(flag)) throw new Error(`duplicate argument: ${flag}`);
    values.set(flag, value);
  }
  const allowed = new Set([
    "--row-ids",
    "--trace-dirs",
    "--output-dir",
    "--samples",
    "--seed",
    "--cadence-ms",
  ]);
  for (const flag of values.keys()) {
    if (!allowed.has(flag)) throw new Error(`unknown argument: ${flag}`);
  }
  return {
    rowIds: (values.get("--row-ids") ?? "").split(",").filter(Boolean),
    traceDirectories: (values.get("--trace-dirs") ?? "").split(",").filter(Boolean),
    outputDirectory: values.get("--output-dir") ?? "",
    samples: Number(values.get("--samples") ?? 5),
    seed: Number(values.get("--seed") ?? DEFAULT_SEED),
    cadenceMs: Number(values.get("--cadence-ms") ?? DEFAULT_CADENCE_MS),
  };
}

async function sha256File(path) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}

async function atomicWrite(path, contents) {
  const temporary = `${path}.${process.pid}.tmp`;
  const handle = await open(temporary, "w");
  try {
    await handle.writeFile(contents, "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
  await rename(temporary, path);
}

function formatNumber(value) {
  return Number.isFinite(value) ? String(Math.round(value * 10000) / 10000) : "—";
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : null;
if (invokedPath === import.meta.url) {
  main().catch((error) => {
    process.stderr.write(`${error?.stack ?? error}\n`);
    process.exitCode = 1;
  });
}
