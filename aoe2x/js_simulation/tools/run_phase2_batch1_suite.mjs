import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  PHASE2_MAX_TICKS,
  runPhase2Batch1Sample,
} from "../src/phase2-batch1-comparison.js";
import { compareRow, summarizeTape } from "../src/standard-units-comparison.js";


const ROOT = new URL("../", import.meta.url);
const DEFAULT_SEED = 20260817;
const DEFAULT_OUTPUT = new URL(
  "../calibration/reports/phase2_batch1_current_engine_2026-08-17/",
  import.meta.url,
);


export function runSchedule(rows, { samples = 5, volatileSamples = 100 } = {}) {
  requirePositiveInteger(samples, "samples");
  requirePositiveInteger(volatileSamples, "volatileSamples");
  if (volatileSamples < samples) throw new RangeError("volatileSamples must be at least samples");
  return rows.flatMap((row) => {
    const tape = summarizeTape(row);
    const count = tape.volatile ? volatileSamples : samples;
    return Array.from({ length: count }, (_, sampleIndex) => ({ row, tape, sampleIndex }));
  });
}


export async function runPhase2Batch1Suite({
  root = ROOT,
  truth = undefined,
  context = undefined,
  rowIds = undefined,
  samples = 5,
  volatileSamples = 100,
  seed = DEFAULT_SEED,
  runImpl = runPhase2Batch1Sample,
  onProgress = undefined,
} = {}) {
  const selectedTruth = truth ?? await loadPhase2Batch1Truth(root);
  const selectedContext = context ?? await loadPhase2Batch1Context(root, selectedTruth);
  const rows = selectRows(selectedTruth.rows, rowIds);
  const schedule = runSchedule(rows, { samples, volatileSamples });
  const samplesByRow = new Map(rows.map((row) => [row.id, []]));
  for (let index = 0; index < schedule.length; index += 1) {
    const item = schedule[index];
    let result;
    try {
      result = await runImpl({
        row: item.row,
        sampleIndex: item.sampleIndex,
        seed,
        context: selectedContext,
      });
    } catch (error) {
      result = Object.freeze({
        rowId: item.row.id,
        sampleIndex: item.sampleIndex,
        seed,
        outcome: "error",
        winnerOwner: null,
        winnerHp: null,
        score: null,
        ticks: null,
        finalStateHash: null,
        eventLogHash: null,
        failure: String(error?.stack ?? error?.message ?? error),
      });
    }
    samplesByRow.get(item.row.id).push(result);
    onProgress?.(Object.freeze({
      completed: index + 1,
      total: schedule.length,
      rowId: item.row.id,
      sampleIndex: item.sampleIndex,
    }));
  }

  const reportRows = rows.map((row) => {
    const tape = summarizeTape(row);
    const rowSamples = samplesByRow.get(row.id);
    return Object.freeze({
      id: row.id,
      subjectSlug: row.subject_slug,
      opponentSlug: row.opponent_slug,
      matchup: row.matchup,
      side2: row.side2,
      side3: row.side3,
      tape,
      comparison: compareRow({
        row,
        tape,
        simulationScores: rowSamples.map(({ score }) => score),
      }),
      samples: Object.freeze(rowSamples),
    });
  });
  return Object.freeze({
    schemaVersion: 1,
    lane: "phase2_batch1_exact_golden_starts",
    source: Object.freeze({
      manifest: "aoe2x/js_simulation/calibration/source/phase2_source.json",
      truth: "aoe2x/js_simulation/calibration/fixtures/phase2/batch1_truth.json",
      archive: selectedTruth.archive,
    }),
    config: Object.freeze({
      engine: "current checked-out JavaScript engine",
      samples,
      volatileSamples,
      seed,
      placements: "exact canonical starting_units from the authorized golden tape row",
      goldenMap: true,
      navigation: "cohesive",
      meleeOpeningOrder: "attack-move-all",
      chaseCapture: true,
      meleeEngagementDwellTicks: 0,
      pairwiseAlliedTransit: false,
      reachMeleeWedgeTransit: "derived from melee reach",
      preventiveContactSteering: true,
      kitingClock: "mechanics-derived",
      maxTicks: PHASE2_MAX_TICKS,
    }),
    schedule: Object.freeze({
      rows: reportRows.length,
      stableRows: reportRows.filter(({ tape }) => !tape.volatile).length,
      volatileRows: reportRows.filter(({ tape }) => tape.volatile).length,
      totalRuns: schedule.length,
    }),
    summary: summarizeReport(reportRows),
    rows: Object.freeze(reportRows),
  });
}


export function renderPhase2Batch1Csv(report) {
  const header = [
    "subject", "opponent", "matchup", "side2_count", "side3_count", "tape_runs",
    "tape_mean", "tape_min", "tape_max", "simulation_runs", "simulation_mean",
    "simulation_min", "simulation_max", "absolute_mean_delta", "tape_band_error",
    "wrong_stable_winner", "unresolved_runs",
  ];
  const rows = report.rows.map((row) => [
    row.subjectSlug, row.opponentSlug, row.matchup, row.side2.count, row.side3.count,
    row.tape.scoredRuns, row.tape.mean, row.tape.min, row.tape.max,
    row.comparison.simulationRuns, row.comparison.mean, row.comparison.min,
    row.comparison.max, row.comparison.mean === null
      ? null
      : Math.abs(row.comparison.mean - row.tape.mean),
    row.comparison.bandError, row.comparison.wrongStableWinner,
    row.comparison.unresolvedRuns,
  ]);
  return `${[header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n")}\n`;
}


export async function writePhase2Batch1Outputs(report, outputDirectory = DEFAULT_OUTPUT) {
  await mkdir(outputDirectory, { recursive: true });
  await Promise.all([
    writeFile(resolveOutput(outputDirectory, "results.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8"),
    writeFile(resolveOutput(outputDirectory, "results.csv"), renderPhase2Batch1Csv(report), "utf8"),
  ]);
}


function selectRows(rows, rowIds) {
  if (rowIds === undefined) return rows;
  if (!Array.isArray(rowIds) || !rowIds.length || new Set(rowIds).size !== rowIds.length) {
    throw new TypeError("rowIds must be a non-empty unique list");
  }
  const byId = new Map(rows.map((row) => [row.id, row]));
  const missing = rowIds.filter((id) => !byId.has(id));
  if (missing.length) throw new RangeError(`unknown Phase 2 row: ${missing.join(", ")}`);
  return rowIds.map((id) => byId.get(id));
}


function summarizeReport(rows) {
  const absoluteDeltas = rows.map((row) => (
    Number.isFinite(row.comparison.mean) ? Math.abs(row.comparison.mean - row.tape.mean) : null
  )).filter(Number.isFinite);
  return Object.freeze({
    rows: rows.length,
    totalRuns: rows.reduce((total, row) => total + row.samples.length, 0),
    unresolvedRuns: rows.reduce((total, row) => total + row.comparison.unresolvedRuns, 0),
    rowsOver25PointDelta: rows.filter((row) => (
      Number.isFinite(row.comparison.mean)
      && Math.abs(row.comparison.mean - row.tape.mean) > 25
    )).length,
    wrongStableWinnerCount: rows.filter((row) => row.comparison.wrongStableWinner).length,
    rowsInsideTapeBand: rows.filter((row) => row.comparison.bandError === 0).length,
    meanAbsoluteMeanDelta: mean(absoluteDeltas),
    medianAbsoluteMeanDelta: median(absoluteDeltas),
    maximumAbsoluteMeanDelta: absoluteDeltas.length ? Math.max(...absoluteDeltas) : null,
  });
}


function resolveOutput(directory, fileName) {
  return directory instanceof URL ? new URL(fileName, directory) : resolve(directory, fileName);
}


function csvCell(value) {
  const string = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(string) ? `"${string.replaceAll('"', '""')}"` : string;
}


function requirePositiveInteger(value, name) {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new RangeError(`${name} must be a positive safe integer, got ${value}`);
  }
}


function mean(values) {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : null;
}


function median(values) {
  const sorted = values.toSorted((left, right) => left - right);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}


export async function main(argv = process.argv.slice(2)) {
  const options = { outputDirectory: DEFAULT_OUTPUT, rowIds: undefined };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!value || !["--output-dir", "--row-ids"].includes(flag)) {
      throw new Error("usage: run_phase2_batch1_suite.mjs [--output-dir DIR] [--row-ids ID,ID]");
    }
    if (flag === "--output-dir") options.outputDirectory = resolve(value);
    if (flag === "--row-ids") options.rowIds = value.split(",").filter(Boolean);
  }
  const report = await runPhase2Batch1Suite({
    rowIds: options.rowIds,
    onProgress: ({ completed, total, rowId }) => {
      if (completed === total || completed % 5 === 0) {
        process.stderr.write(`[${completed}/${total}] ${rowId}\n`);
      }
    },
  });
  await writePhase2Batch1Outputs(report, options.outputDirectory);
  process.stdout.write(`${JSON.stringify(report.summary)}\n`);
  return report;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
