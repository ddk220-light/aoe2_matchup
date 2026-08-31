import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { createGunzip } from "node:zlib";


const here = path.dirname(fileURLToPath(import.meta.url));
const simRoot = path.resolve(here, "..");
const captureRoot = path.resolve(process.argv[2] ?? path.join(
  simRoot,
  "calibration",
  "live_observations",
  "spanish_champion_vs_halberdier_5x_2026-08-28",
));
const EXPECTED = Object.freeze({ 2: Object.freeze({ master: 567, count: 23 }),
  3: Object.freeze({ master: 359, count: 27 }) });
const WAYPOINT_SECONDS = 3;


async function sha256(file) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest("hex").toUpperCase();
}


function quantiles(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const median = sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
  return Object.freeze({
    min: Number(sorted[0].toFixed(4)),
    median: Number(median.toFixed(4)),
    mean: Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(4)),
    max: Number(sorted.at(-1).toFixed(4)),
  });
}


async function decodeRun(runNumber) {
  const runName = `run_${String(runNumber).padStart(3, "0")}`;
  const decoded = path.join(captureRoot, runName, "decoded");
  const unitsFile = path.join(decoded, "spanish_champion_vs_halberdier.units.jsonl.gz");
  const commandsFile = path.join(decoded, "spanish_champion_vs_halberdier.commands.jsonl");
  const initial = new Map();
  const firstMovement = new Map();
  const waypoint = new Map();
  let firstTime = null;
  let waypointTime = null;
  const lines = createInterface({
    input: createReadStream(unitsFile).pipe(createGunzip()),
    crlfDelay: Infinity,
  });
  for await (const line of lines) {
    const unit = JSON.parse(line);
    const expected = EXPECTED[unit.owner];
    if (!expected || unit.master !== expected.master) continue;
    if (firstTime === null) firstTime = unit.t;
    if (!initial.has(unit.id)) {
      initial.set(unit.id, unit);
      continue;
    }
    const start = initial.get(unit.id);
    if (!firstMovement.has(unit.id)
        && Math.hypot(unit.x - start.x, unit.y - start.y) > 0.01) {
      firstMovement.set(unit.id, unit.t - firstTime);
    }
    const elapsed = unit.t - firstTime;
    if (elapsed >= WAYPOINT_SECONDS && !waypoint.has(unit.id)) {
      waypoint.set(unit.id, unit);
      waypointTime ??= elapsed;
    }
  }
  const commands = (await readFile(commandsFile, "utf8"))
    .split(/\r?\n/u)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  const firstAiOrder = commands.find(({ kind }) => kind === "aiOrder");
  if (!firstAiOrder || !Number.isFinite(firstAiOrder.t)) {
    throw new Error(`${commandsFile}: missing first aiOrder`);
  }
  const byOwner = {};
  for (const owner of [2, 3]) {
    const roster = [...initial.values()]
      .filter((unit) => unit.owner === owner)
      .sort((left, right) => left.id - right.id);
    if (roster.length !== EXPECTED[owner].count) {
      throw new Error(`${runName}: owner ${owner} roster has ${roster.length} units`);
    }
    byOwner[owner] = roster.map((unit, index) => {
      const point = waypoint.get(unit.id);
      if (!point) throw new Error(`${runName}: owner ${owner} slot ${index + 1} has no waypoint`);
      return Object.freeze({ slot: index + 1, x: point.x, y: point.y });
    });
  }
  return Object.freeze({
    repeat: runNumber,
    unitsFile: path.relative(simRoot, unitsFile),
    unitsSha256: await sha256(unitsFile),
    commandsFile: path.relative(simRoot, commandsFile),
    commandsSha256: await sha256(commandsFile),
    firstAiOrderSeconds: firstAiOrder.t,
    movementStarts: [...firstMovement.values()],
    waypointSeconds: waypointTime,
    byOwner,
  });
}


const manifest = JSON.parse(await readFile(path.join(captureRoot, "capture_manifest.json"), "utf8"));
const grpcReportFile = path.join(captureRoot, "grpc_opening_variance.json");
const grpcReport = JSON.parse(await readFile(grpcReportFile, "utf8"));
const runs = await Promise.all([1, 2, 3, 4, 5].map(decodeRun));
const targetVectors = grpcReport.runs.map((run) => new Map(run.units.map((unit) => (
  [`${unit.owner}:${unit.slot}`, unit.first_target_slot]
))));
const targetMedoidIndex = targetVectors.map((vector, index) => ({
  index,
  distance: targetVectors.reduce((total, other) => total
    + [...vector].filter(([key, target]) => other.get(key) !== target).length, 0),
})).sort((left, right) => left.distance - right.distance || left.index - right.index)[0].index;
const variants = runs.map((run, runIndex) => ({
  repeat: run.repeat,
  movement_start_seconds: quantiles(run.movementStarts),
  ai_order_sweep_start_seconds: run.firstAiOrderSeconds,
  waypoint_seconds: Number(run.waypointSeconds.toFixed(4)),
  by_owner: Object.fromEntries([2, 3].map((owner) => [
    owner,
    run.byOwner[owner].map((point, index) => {
      const observed = grpcReport.runs[runIndex].units.find((unit) => (
        unit.owner === owner && unit.slot === index + 1
      ));
      if (!observed || !Number.isSafeInteger(observed.first_target_slot)
          || !Number.isFinite(observed.first_target_t)) {
        throw new Error(`run ${run.repeat} has incomplete owner ${owner} slot ${index + 1}`);
      }
      return {
        slot: index + 1,
        position: { x: point.x, y: point.y },
        first_target_slot: observed.first_target_slot,
        first_target_seconds: { mean: observed.first_target_t },
      };
    }),
  ])),
}));
const profile = {
  schema_version: 1,
  matchup: "23 Spanish Champions vs 27 Spanish Halberdiers",
  source_golden_sha256: manifest.golden.sha256,
  grpc_report_sha256: await sha256(grpcReportFile),
  derivation: "Mean per-slot position at the first decoded frame at or after 3 game seconds",
  representative_target_run: targetMedoidIndex + 1,
  representative_target_rule: "Minimum total per-slot target Hamming distance to the five runs",
  variants,
  sources: runs.map((run) => ({
    repeat: run.repeat,
    units_file: run.unitsFile,
    units_sha256: run.unitsSha256,
    commands_file: run.commandsFile,
    commands_sha256: run.commandsSha256,
    first_ai_order_seconds: run.firstAiOrderSeconds,
    waypoint_seconds: Number(run.waypointSeconds.toFixed(4)),
  })),
  movement_start_seconds: quantiles(runs.flatMap(({ movementStarts }) => movementStarts)),
  ai_order_sweep_start_seconds: quantiles(runs.map(({ firstAiOrderSeconds }) => firstAiOrderSeconds)),
  waypoint_seconds: WAYPOINT_SECONDS,
  by_owner: Object.fromEntries([2, 3].map((owner) => [
    owner,
    Array.from({ length: EXPECTED[owner].count }, (_, index) => {
      const observed = grpcReport.runs.map((run) => run.units.find((unit) => (
        unit.owner === owner && unit.slot === index + 1
      )));
      if (observed.some((unit) => !unit || !Number.isSafeInteger(unit.first_target_slot)
          || !Number.isFinite(unit.first_target_t))) {
        throw new Error(`gRPC report has incomplete owner ${owner} slot ${index + 1} targeting`);
      }
      const targetCounts = new Map();
      for (const unit of observed) {
        targetCounts.set(unit.first_target_slot,
          (targetCounts.get(unit.first_target_slot) ?? 0) + 1);
      }
      // Select one coherent observed assignment vector. Independent per-slot
      // modes can combine into a target concentration that occurred in no run.
      const selectedTarget = observed[targetMedoidIndex].first_target_slot;
      return {
        slot: index + 1,
        position: {
          x: Number((runs.reduce((sum, run) => sum + run.byOwner[owner][index].x, 0)
            / runs.length).toFixed(4)),
          y: Number((runs.reduce((sum, run) => sum + run.byOwner[owner][index].y, 0)
            / runs.length).toFixed(4)),
        },
        first_target_slot: selectedTarget,
        first_target_slot_counts: Object.fromEntries([...targetCounts.entries()]
          .sort((left, right) => left[0] - right[0])),
        first_target_seconds: quantiles(observed.map((unit) => unit.first_target_t)),
      };
    }),
  ])),
};
await writeFile(path.join(captureRoot, "opening_profile.json"),
  `${JSON.stringify(profile, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({
  output: path.join(captureRoot, "opening_profile.json"),
  movementStartSeconds: profile.movement_start_seconds,
  aiOrderSweepStartSeconds: profile.ai_order_sweep_start_seconds,
}, null, 2)}\n`);
