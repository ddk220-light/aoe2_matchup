import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { loadStandardUnitsTruth } from "../src/standard-units-comparison.js";
import {
  runStandardUnitsSuite,
  selectRangedVsMeleeRows,
  serializeStandardUnitsReport,
} from "./run_standard_units_suite.mjs";


const ROOT_URL = new URL("../", import.meta.url);
const DEFAULT_OUTPUT_DIRECTORY = new URL(
  "../calibration/reports/ranged_vs_melee_current_engine_2026-08-13/",
  import.meta.url,
);
const DEFAULT_SEED = 20260411;


export function buildRangedVsMeleeAnalysis(report) {
  if (!Array.isArray(report?.rows)) throw new TypeError("report rows are required");
  const rows = report.rows.map((row) => {
    const signedMeanDelta = row.comparison.mean - row.tape.mean;
    const unresolvedRuns = row.comparison.unresolvedRuns;
    return Object.freeze({
      id: row.id,
      matchup: row.matchup,
      category: row.category,
      ranged: row.side2,
      melee: row.side3,
      tape: row.tape,
      simulation: Object.freeze({
        mean: row.comparison.mean,
        min: row.comparison.min,
        max: row.comparison.max,
        runs: row.comparison.simulationRuns,
        unresolvedRuns,
        side3WinRate: row.comparison.side3WinRate,
      }),
      signedMeanDelta,
      absoluteMeanDelta: Math.abs(signedMeanDelta),
      tapeBandError: row.comparison.bandError,
      tapeBandCoverage: row.comparison.tapeBandCoverage,
      side3WinRateError: row.comparison.side3WinRateError,
      winnerAgreement: row.tape.volatile
        ? "volatile"
        : (row.comparison.wrongStableWinner ? "mismatch" : "match"),
      failure: unresolvedRuns > 0 ? `${unresolvedRuns} unresolved runs` : "",
    });
  });
  const absoluteDeltas = rows.map(({ absoluteMeanDelta }) => absoluteMeanDelta);
  return Object.freeze({
    schemaVersion: 1,
    lane: report.lane,
    source: report.source,
    config: report.config,
    schedule: report.schedule,
    scoreSemantics: Object.freeze({
      rangedWin: "negative",
      meleeWin: "positive",
      signedMeanDelta: "simulation mean minus tape mean; negative favors ranged relative to tape",
    }),
    summary: Object.freeze({
      rowCount: rows.length,
      totalRuns: report.schedule.totalRuns,
      stableRows: report.schedule.stableRows,
      volatileRows: report.schedule.volatileRows,
      rowsOver25PointDelta: rows.filter(({ absoluteMeanDelta }) => absoluteMeanDelta > 25).length,
      rowsInsideTapeBand: rows.filter(({ tapeBandError }) => tapeBandError === 0).length,
      wrongStableWinnerCount: rows.filter(({ winnerAgreement }) => winnerAgreement === "mismatch").length,
      unresolvedRuns: rows.reduce((total, row) => total + row.simulation.unresolvedRuns, 0),
      meanAbsoluteMeanDelta: average(absoluteDeltas),
      medianAbsoluteMeanDelta: median(absoluteDeltas),
      meanTapeBandError: average(rows.map(({ tapeBandError }) => tapeBandError)),
    }),
    rows: Object.freeze(rows),
  });
}


export function renderRangedVsMeleeCsv(analysis) {
  const header = [
    "id", "matchup", "ranged_unit", "ranged_count", "melee_unit", "melee_count",
    "tape_mean", "tape_min", "tape_max", "simulation_mean", "simulation_min",
    "simulation_max", "signed_mean_delta", "absolute_mean_delta", "tape_band_error",
    "tape_band_coverage", "winner_agreement", "simulation_runs", "unresolved_runs", "failure",
  ];
  const records = analysis.rows.map((row) => [
    row.id,
    row.matchup,
    row.ranged.unit,
    row.ranged.count,
    row.melee.unit,
    row.melee.count,
    row.tape.mean,
    row.tape.min,
    row.tape.max,
    row.simulation.mean,
    row.simulation.min,
    row.simulation.max,
    row.signedMeanDelta,
    row.absoluteMeanDelta,
    row.tapeBandError,
    row.tapeBandCoverage,
    row.winnerAgreement,
    row.simulation.runs,
    row.simulation.unresolvedRuns,
    row.failure,
  ]);
  return `${[header, ...records].map((record) => record.map(csvCell).join(",")).join("\n")}\n`;
}


export async function runRangedVsMeleeSuite({
  root = ROOT_URL,
  samples = 5,
  volatileSamples = 100,
  seed = DEFAULT_SEED,
  onProgress = undefined,
} = {}) {
  const truth = await loadStandardUnitsTruth(root);
  const rows = selectRangedVsMeleeRows(truth.rows);
  if (rows.length !== 48) {
    throw new Error(`expected exactly 48 ranged-versus-melee tape rows, got ${rows.length}`);
  }
  return runStandardUnitsSuite({
    root,
    truth: { ...truth, rows },
    samples,
    volatileSamples,
    seed,
    onProgress,
  });
}


export async function writeRangedVsMeleeOutputs({ report, outputDirectory }) {
  if (!outputDirectory) throw new TypeError("outputDirectory is required");
  const analysis = buildRangedVsMeleeAnalysis(report);
  await mkdir(outputDirectory, { recursive: true });
  await Promise.all([
    writeFile(resolvePath(outputDirectory, "results.json"), serializeStandardUnitsReport(report), "utf8"),
    writeFile(resolvePath(outputDirectory, "analysis.json"), `${JSON.stringify(analysis, null, 2)}\n`, "utf8"),
    writeFile(resolvePath(outputDirectory, "results.csv"), renderRangedVsMeleeCsv(analysis), "utf8"),
  ]);
  return analysis;
}


export async function main(argv = process.argv.slice(2)) {
  const options = parseArguments(argv);
  let lastReported = 0;
  const report = await runRangedVsMeleeSuite({
    samples: options.samples,
    volatileSamples: options.volatileSamples,
    seed: options.seed,
    onProgress: ({ completed, total, matchup }) => {
      if (completed === total || completed - lastReported >= 10) {
        lastReported = completed;
        process.stderr.write(`[${completed}/${total}] ${matchup}\n`);
      }
    },
  });
  const analysis = await writeRangedVsMeleeOutputs({
    report,
    outputDirectory: options.outputDirectory ?? DEFAULT_OUTPUT_DIRECTORY,
  });
  process.stdout.write(`${JSON.stringify(analysis.summary)}\n`);
  return analysis;
}


function parseArguments(argv) {
  const options = { samples: 5, volatileSamples: 100, seed: DEFAULT_SEED };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!value || !["--samples", "--volatile-samples", "--seed", "--output-dir"].includes(flag)) {
      throw new Error("usage: run_ranged_vs_melee_suite.mjs [--samples N] [--volatile-samples N] [--seed N] [--output-dir DIR]");
    }
    if (flag === "--samples") options.samples = Number(value);
    if (flag === "--volatile-samples") options.volatileSamples = Number(value);
    if (flag === "--seed") options.seed = Number(value);
    if (flag === "--output-dir") options.outputDirectory = resolve(value);
  }
  return options;
}


function resolvePath(directory, fileName) {
  return directory instanceof URL ? new URL(fileName, directory) : resolve(directory, fileName);
}


function csvCell(value) {
  const string = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(string) ? `"${string.replaceAll('"', '""')}"` : string;
}


function average(values) {
  const finite = values.filter(Number.isFinite);
  return finite.length === 0 ? 0 : finite.reduce((total, value) => total + value, 0) / finite.length;
}


function median(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  if (sorted.length === 0) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}


if (
  process.argv[1]
  && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))
) {
  await main();
}
