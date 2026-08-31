import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";


const DEFAULT_KEYS = Object.freeze([
  "arbalester_vs_heavy_cav_archer",
  "hand_cannoneer_vs_paladin",
  "hand_cannoneer_vs_elite_steppe",
  "arbalester_vs_paladin",
  "heavy_cav_archer_vs_champion",
  "heavy_cav_archer_vs_elite_steppe",
  "heavy_cav_archer_vs_paladin",
]);
const DEFAULT_OUTPUT = resolve(
  "calibration/reports/ranged_crowding_seven_failures_2026-08-30",
);
const RUNNER = resolve("tools/run_live_ranged_matrix_comparison.mjs");


function argument(name) {
  const prefix = `--${name}=`;
  return process.argv.find((value) => value.startsWith(prefix))?.slice(prefix.length);
}


async function runWorker(key, outputRoot) {
  const output = resolve(outputRoot, "runs", key);
  await mkdir(output, { recursive: true });
  await new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(process.execPath, [
      RUNNER,
      "--five-seeds",
      `--matchup=${key}`,
      `--output=${output}`,
    ], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", rejectPromise);
    child.on("exit", (code) => {
      if (code === 0) {
        process.stderr.write(`[done] ${key}\n${stderr}`);
        resolvePromise();
      } else {
        rejectPromise(new Error(`${key} exited ${code}\n${stdout}\n${stderr}`));
      }
    });
  });
  return JSON.parse(await readFile(resolve(output, "results.json"), "utf8"));
}


async function mapLimit(values, limit, operation) {
  const results = new Array(values.length);
  let nextIndex = 0;
  async function worker() {
    while (nextIndex < values.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await operation(values[index]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, worker));
  return results;
}


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


const outputRoot = resolve(argument("output") ?? DEFAULT_OUTPUT);
const concurrency = Number.parseInt(argument("concurrency") ?? "4", 10);
const keys = argument("matchups")?.split(",").filter(Boolean) ?? DEFAULT_KEYS;
if (!Number.isSafeInteger(concurrency) || concurrency < 1) {
  throw new RangeError("concurrency must be a positive integer");
}
await mkdir(outputRoot, { recursive: true });
const reports = await mapLimit(keys, concurrency, (key) => runWorker(key, outputRoot));
const rows = reports.flatMap(({ rows }) => rows);
const resolved = rows.filter(({ simulation }) => Number.isFinite(simulation.score));
const report = {
  ...reports[0],
  lane: "ranged_crowding_seven_previous_failures_five_seeds",
  generatedAt: new Date().toISOString(),
  execution: {
    processConcurrency: concurrency,
    seedsPerMatchup: [0, 1, 2, 3, 4],
    selectedMatchups: keys,
  },
  summary: {
    matchups: rows.length,
    attempts: rows.reduce((total, row) => total + row.simulation.runs.length, 0),
    resolved: resolved.length,
    wrongWinnerMatchups: resolved.filter(({ tape, simulation }) => (
      simulation.runs.some(({ winnerOwner }) => (
        Number.isFinite(winnerOwner) && !tape.winnerOwners.includes(winnerOwner)
      ))
    )).length,
    wrongWinnerRuns: resolved.reduce((total, { tape, simulation }) => (
      total + simulation.runs.filter(({ winnerOwner }) => (
        Number.isFinite(winnerOwner) && !tape.winnerOwners.includes(winnerOwner)
      )).length
    ), 0),
    rowsWithin5PercentWinnerHp: resolved.filter(({ tape, simulation }) => {
      const liveOwner = new Set(tape.winnerOwners).size === 1 ? tape.winnerOwners[0] : null;
      return liveOwner !== null
        && simulation.runs.every(({ winnerOwner }) => winnerOwner === liveOwner)
        && simulation.relativeWinnerHpDelta < 0.05;
    }).length,
    meanAbsoluteMeanDelta: resolved.length
      ? mean(resolved.map(({ simulation }) => simulation.absoluteMeanDelta))
      : null,
  },
  rows,
};
await writeFile(resolve(outputRoot, "results.json"), `${JSON.stringify(report, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ output: resolve(outputRoot, "results.json"), ...report.summary })}\n`);
