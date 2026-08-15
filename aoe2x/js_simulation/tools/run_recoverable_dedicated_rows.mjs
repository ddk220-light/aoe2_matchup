import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readdir, readFile, writeFile } from "node:fs/promises";
import { availableParallelism } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  computeWorkerCount,
  mergeDedicatedRowReports,
  runRecoverableDedicatedQueue,
  validateRowReport,
} from "../src/dedicated-benchmark-rig.js";
import { loadDedicatedGoldenCorpus } from "../src/dedicated-golden-corpus.js";
import { renderDedicatedCsv } from "./run_dedicated_ranged_melee_suite.mjs";


const ROOT = resolve(fileURLToPath(new URL("../", import.meta.url)));
const DEFAULT_OUTPUT = resolve(
  ROOT,
  "calibration/reports/dedicated_ranged_melee_collision_recovery_selective_2026-08-14",
);
const WORKER = resolve(ROOT, "tools/run_dedicated_row_worker.mjs");
const ENGINE_HASH_ROOTS = [
  resolve(ROOT, "src"),
  resolve(ROOT, "fixtures/golden_map.json"),
  resolve(ROOT, "fixtures/unit_stats"),
  resolve(ROOT, "calibration/source/dedicated_ranged_melee_sources.json"),
  resolve(
    ROOT,
    "calibration/fixtures/dedicated_ranged_melee/dedicated_ranged_melee_truth.json",
  ),
  resolve(ROOT, "tools/run_dedicated_ranged_melee_suite.mjs"),
  resolve(ROOT, "tools/run_dedicated_row_worker.mjs"),
  resolve(ROOT, "tools/run_recoverable_dedicated_rows.mjs"),
];


export async function main(argv = process.argv.slice(2)) {
  const options = parseArgs(argv);
  const corpus = await loadDedicatedGoldenCorpus(new URL("../", import.meta.url));
  const rowIds = corpus.matchups.flatMap(({ ratios }) => ratios.map(({ id }) => id));
  const runSignature = await hashRunInputs(ENGINE_HASH_ROOTS);
  const detectedParallelism = availableParallelism();
  const concurrency = options.workers ?? computeWorkerCount({
    availableParallelism: detectedParallelism,
    pendingTasks: rowIds.length,
  });

  process.stderr.write(
    `recoverable dedicated run: ${rowIds.length} rows, ${concurrency} workers, `
      + `${detectedParallelism} available CPUs, signature ${runSignature.slice(0, 12)}\n`,
  );
  const queue = await runRecoverableDedicatedQueue({
    matchupIds: rowIds,
    outputDirectory: options.outputDirectory,
    runSignature,
    concurrency,
    runMatchup: runRowInChild,
    validateReport: validateRowReport,
    onProgress: ({ completedMatchups, totalMatchups, activeMatchups, estimatedRemainingSeconds }) => {
      const eta = estimatedRemainingSeconds === null
        ? "calculating"
        : `${Math.ceil(estimatedRemainingSeconds)}s`;
      process.stderr.write(
        `[${completedMatchups}/${totalMatchups}] active=${activeMatchups.length} eta=${eta}\n`,
      );
    },
  });
  const merged = mergeDedicatedRowReports(queue.reports);
  await Promise.all([
    writeFile(
      resolve(options.outputDirectory, "results.json"),
      `${JSON.stringify(merged, null, 2)}\n`,
      { encoding: "utf8", flush: true },
    ),
    writeFile(
      resolve(options.outputDirectory, "results.csv"),
      renderDedicatedCsv(merged),
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
        checkpointUnit: "one complete ratio row (5 exact tape repeats)",
        checkpointWrite: "temporary file, flush, atomic rename",
        resumePolicy: "validate signature and shape, skip completed row checkpoints",
      }, null, 2)}\n`,
      { encoding: "utf8", flush: true },
    ),
  ]);
  process.stdout.write(`${JSON.stringify({ ...queue, reports: undefined, summary: merged.summary })}\n`);
  return merged;
}


async function runRowInChild(rowId) {
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
  const entry = await readdir(path, { withFileTypes: true }).catch((error) => {
    if (error?.code === "ENOTDIR") return null;
    throw error;
  });
  if (entry === null) return [path];
  const nested = await Promise.all(entry.map((item) => {
    const child = resolve(path, item.name);
    return item.isDirectory() ? listFiles(child) : [child];
  }));
  return nested.flat();
}


function parseArgs(argv) {
  const options = { outputDirectory: DEFAULT_OUTPUT, workers: undefined };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!value || !["--output-dir", "--workers"].includes(flag)) {
      throw new Error(
        "usage: run_recoverable_dedicated_rows.mjs [--output-dir DIR] [--workers N]",
      );
    }
    if (flag === "--output-dir") options.outputDirectory = resolve(value);
    if (flag === "--workers") {
      options.workers = Number(value);
      if (!Number.isSafeInteger(options.workers) || options.workers < 1) {
        throw new RangeError("workers must be a positive integer");
      }
    }
  }
  return options;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
