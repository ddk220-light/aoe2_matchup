import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { availableParallelism } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  computeWorkerCount,
  runRecoverableDedicatedQueue,
} from "../src/dedicated-benchmark-rig.js";
import { loadPhase2Batch1Truth } from "../src/phase2-batch1-comparison.js";
import { renderPhase2Batch1Csv } from "./run_phase2_batch1_suite.mjs";


const ROOT = resolve(fileURLToPath(new URL("../", import.meta.url)));
const ROOT_URL = new URL("../", import.meta.url);
const DEFAULT_OUTPUT = resolve(
  ROOT,
  "calibration/reports/phase2_batch1_current_engine_2026-08-17",
);
const WORKER = resolve(ROOT, "tools/run_phase2_batch1_worker.mjs");
const ENGINE_HASH_ROOTS = Object.freeze([
  resolve(ROOT, "src"),
  resolve(ROOT, "fixtures/golden_map.json"),
  resolve(ROOT, "fixtures/unit_stats"),
  resolve(ROOT, "calibration/source/phase2_source.json"),
  resolve(ROOT, "calibration/fixtures/phase2/batch1_truth.json"),
  resolve(ROOT, "tools/run_phase2_batch1_suite.mjs"),
  resolve(ROOT, "tools/run_phase2_batch1_worker.mjs"),
  resolve(ROOT, "tools/run_recoverable_phase2_batch1.mjs"),
]);


export async function main(argv = process.argv.slice(2)) {
  const options = parseArguments(argv);
  const truth = await loadPhase2Batch1Truth(ROOT_URL);
  const rowIds = selectRowIds(truth.rows, options.rowIds);
  const runSignature = await hashRunInputs(ENGINE_HASH_ROOTS);
  const detectedParallelism = availableParallelism();
  const concurrency = options.workers ?? computeWorkerCount({
    availableParallelism: detectedParallelism,
    pendingTasks: rowIds.length,
  });

  process.stderr.write(
    `recoverable Phase 2 Batch 1 run: ${rowIds.length} rows, ${concurrency} workers, `
      + `${detectedParallelism} available CPUs, signature ${runSignature.slice(0, 12)}\n`,
  );
  const queue = await runRecoverableDedicatedQueue({
    matchupIds: rowIds,
    outputDirectory: options.outputDirectory,
    runSignature,
    concurrency,
    runMatchup: runRowInChild,
    validateReport: validatePhase2Batch1RowReport,
    onProgress: ({
      completedMatchups,
      totalMatchups,
      activeMatchups,
      estimatedRemainingSeconds,
    }) => {
      const eta = estimatedRemainingSeconds === null
        ? "calculating"
        : `${Math.ceil(estimatedRemainingSeconds)}s`;
      process.stderr.write(
        `[${completedMatchups}/${totalMatchups}] active=${activeMatchups.length} eta=${eta}\n`,
      );
    },
  });
  const merged = mergePhase2Batch1RowReports(queue.reports, rowIds);
  await Promise.all([
    writeFile(
      resolve(options.outputDirectory, "results.json"),
      `${JSON.stringify(merged, null, 2)}\n`,
      { encoding: "utf8", flush: true },
    ),
    writeFile(
      resolve(options.outputDirectory, "results.csv"),
      renderPhase2Batch1Csv(merged),
      { encoding: "utf8", flush: true },
    ),
    writeFile(
      resolve(options.outputDirectory, "run-manifest.json"),
      `${JSON.stringify({
        schemaVersion: 1,
        runSignature,
        cpuUtilizationTarget: 0.8,
        availableParallelism: detectedParallelism,
        workers: concurrency,
        rowIds,
        checkpointUnit: "one complete exact golden matchup row",
        checkpointWrite: "temporary file, flush, atomic rename",
        resumePolicy: "validate signature and shape, skip completed row checkpoints",
        stableSamples: 5,
        volatileSamples: 100,
      }, null, 2)}\n`,
      { encoding: "utf8", flush: true },
    ),
  ]);
  process.stdout.write(`${JSON.stringify({ ...queue, reports: undefined, summary: merged.summary })}\n`);
  return merged;
}


export function validatePhase2Batch1RowReport(report, rowId) {
  const row = report?.rows?.[0];
  const expectedRuns = row?.tape?.volatile ? 100 : 5;
  const valid = report
    && report.lane === "phase2_batch1_exact_golden_starts"
    && report.schedule?.rows === 1
    && report.schedule?.totalRuns === expectedRuns
    && report.rows?.length === 1
    && row?.id === rowId
    && Array.isArray(row.samples)
    && row.samples.length === expectedRuns;
  if (!valid) throw new Error(`invalid Phase 2 Batch 1 row report for ${rowId}`);
  return true;
}


export function mergePhase2Batch1RowReports(reports, expectedRowIds) {
  if (!Array.isArray(reports) || reports.length !== expectedRowIds.length) {
    throw new Error(`expected ${expectedRowIds.length} Phase 2 row reports`);
  }
  reports.forEach((report, index) => validatePhase2Batch1RowReport(report, expectedRowIds[index]));
  const rows = reports.flatMap((report) => report.rows);
  if (new Set(rows.map(({ id }) => id)).size !== rows.length) {
    throw new Error("duplicate Phase 2 Batch 1 row checkpoint");
  }
  const totalRuns = rows.reduce((total, row) => total + row.samples.length, 0);
  const unresolvedRuns = rows.reduce((total, row) => total + row.comparison.unresolvedRuns, 0);
  const absoluteDeltas = rows.map((row) => (
    Number.isFinite(row.comparison.mean) ? Math.abs(row.comparison.mean - row.tape.mean) : null
  )).filter(Number.isFinite);
  const subjectSlugs = [...new Set(rows.map(({ subjectSlug }) => subjectSlug))].toSorted();
  return Object.freeze({
    ...reports[0],
    schedule: Object.freeze({
      rows: rows.length,
      stableRows: rows.filter(({ tape }) => !tape.volatile).length,
      volatileRows: rows.filter(({ tape }) => tape.volatile).length,
      totalRuns,
      execution: "recoverable-per-row-checkpoints",
    }),
    summary: Object.freeze({
      subjects: subjectSlugs.length,
      rows: rows.length,
      totalRuns,
      resolvedRuns: totalRuns - unresolvedRuns,
      unresolvedRuns,
      fullyUnresolvedRows: rows.filter(({ comparison }) => comparison.simulationRuns === 0).length,
      rowsOver25PointDelta: rows.filter((row) => (
        Number.isFinite(row.comparison.mean)
        && Math.abs(row.comparison.mean - row.tape.mean) > 25
      )).length,
      wrongStableWinnerCount: rows.filter(({ comparison }) => comparison.wrongStableWinner).length,
      rowsInsideTapeBand: rows.filter(({ comparison }) => comparison.bandError === 0).length,
      meanAbsoluteMeanDelta: mean(absoluteDeltas),
      medianAbsoluteMeanDelta: median(absoluteDeltas),
      maximumAbsoluteMeanDelta: absoluteDeltas.length ? Math.max(...absoluteDeltas) : null,
    }),
    subjectSummaries: Object.freeze(subjectSlugs.map((subjectSlug) => {
      const subjectRows = rows.filter((row) => row.subjectSlug === subjectSlug);
      return Object.freeze({
        subjectSlug,
        rows: subjectRows.length,
        totalRuns: subjectRows.reduce((total, row) => total + row.samples.length, 0),
        rowsOver25PointDelta: subjectRows.filter((row) => (
          Number.isFinite(row.comparison.mean)
          && Math.abs(row.comparison.mean - row.tape.mean) > 25
        )).length,
        wrongStableWinnerCount: subjectRows.filter(
          ({ comparison }) => comparison.wrongStableWinner,
        ).length,
      });
    })),
    rows: Object.freeze(rows.toSorted((left, right) => left.id.localeCompare(right.id))),
  });
}


function runRowInChild(rowId) {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(process.execPath, [WORKER, "--row-id", rowId], {
      cwd: ROOT,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const stdout = [];
    const stderr = [];
    child.stdout.on("data", (chunk) => stdout.push(chunk));
    child.stderr.on("data", (chunk) => {
      stderr.push(chunk);
      process.stderr.write(`[${rowId}] ${chunk}`);
    });
    child.once("error", rejectPromise);
    child.once("close", (code, signal) => {
      if (code !== 0) {
        rejectPromise(new Error(
          `worker ${rowId} failed with code ${code} signal ${signal ?? "none"}: `
            + Buffer.concat(stderr).toString("utf8"),
        ));
        return;
      }
      try {
        resolvePromise(JSON.parse(Buffer.concat(stdout).toString("utf8")));
      } catch (error) {
        rejectPromise(new Error(`worker ${rowId} returned invalid JSON: ${error.message}`));
      }
    });
  });
}


async function hashRunInputs(paths) {
  const files = (await Promise.all(paths.map(listFiles))).flat().toSorted();
  const hash = createHash("sha256");
  for (const path of files) {
    hash.update(path.replaceAll("\\", "/"));
    hash.update("\0");
    hash.update(await readFile(path));
    hash.update("\0");
  }
  return hash.digest("hex");
}


async function listFiles(path) {
  const entries = await readdir(path, { withFileTypes: true }).catch((error) => {
    if (error?.code === "ENOTDIR") return null;
    throw error;
  });
  if (entries === null) return [path];
  const nested = await Promise.all(entries.map((entry) => {
    const child = resolve(path, entry.name);
    return entry.isDirectory() ? listFiles(child) : [child];
  }));
  return nested.flat();
}


function selectRowIds(rows, requested) {
  if (requested === undefined) return rows.map(({ id }) => id);
  if (!Array.isArray(requested) || !requested.length || new Set(requested).size !== requested.length) {
    throw new TypeError("row IDs must be a non-empty unique list");
  }
  const available = new Set(rows.map(({ id }) => id));
  const missing = requested.filter((id) => !available.has(id));
  if (missing.length) throw new RangeError(`unknown Phase 2 row: ${missing.join(", ")}`);
  return requested;
}


function parseArguments(argv) {
  const options = { outputDirectory: DEFAULT_OUTPUT, workers: undefined, rowIds: undefined };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!value || !["--output-dir", "--workers", "--row-ids"].includes(flag)) {
      throw new Error(
        "usage: run_recoverable_phase2_batch1.mjs [--output-dir DIR] "
          + "[--workers N] [--row-ids ID,ID]",
      );
    }
    if (flag === "--output-dir") options.outputDirectory = resolve(value);
    if (flag === "--workers") {
      options.workers = Number(value);
      if (!Number.isSafeInteger(options.workers) || options.workers < 1) {
        throw new RangeError("workers must be a positive integer");
      }
    }
    if (flag === "--row-ids") {
      options.rowIds = value.split(",").map((entry) => entry.trim()).filter(Boolean);
    }
  }
  return options;
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


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
