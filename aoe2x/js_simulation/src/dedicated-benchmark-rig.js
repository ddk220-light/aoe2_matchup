import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { resolve } from "node:path";


let atomicWriteSequence = 0;


export function computeWorkerCount({ availableParallelism, pendingTasks }) {
  if (!Number.isSafeInteger(availableParallelism) || availableParallelism < 1) {
    throw new RangeError("availableParallelism must be a positive integer");
  }
  if (!Number.isSafeInteger(pendingTasks) || pendingTasks < 0) {
    throw new RangeError("pendingTasks must be a non-negative integer");
  }
  if (pendingTasks === 0) return 0;
  return Math.min(pendingTasks, Math.max(1, Math.floor(availableParallelism * 0.8)));
}


export async function runRecoverableDedicatedQueue({
  matchupIds,
  outputDirectory,
  runSignature,
  concurrency,
  runMatchup,
  onProgress = undefined,
}) {
  validateQueueInputs({ matchupIds, outputDirectory, runSignature, concurrency, runMatchup });
  const checkpointsDirectory = resolve(outputDirectory, "checkpoints");
  await mkdir(checkpointsDirectory, { recursive: true });
  const reports = new Map();

  for (const matchupId of matchupIds) {
    const checkpoint = await readCheckpoint(checkpointsDirectory, matchupId);
    if (!checkpoint) continue;
    validateCheckpoint(checkpoint, { matchupId, runSignature });
    reports.set(matchupId, checkpoint.report);
  }

  const pending = matchupIds.filter((matchupId) => !reports.has(matchupId));
  const startedAt = Date.now();
  const initialReused = reports.size;
  let executedMatchups = 0;
  let cursor = 0;
  let firstFailure;

  const writeProgress = async (activeMatchups = []) => {
    const completedMatchups = reports.size;
    const elapsedSeconds = (Date.now() - startedAt) / 1000;
    const completedThisRun = Math.max(0, completedMatchups - initialReused);
    const averageSecondsPerMatchup = completedThisRun > 0
      ? elapsedSeconds / completedThisRun
      : null;
    const pendingMatchups = matchupIds.length - completedMatchups;
    const progress = {
      schemaVersion: 1,
      runSignature,
      totalMatchups: matchupIds.length,
      completedMatchups,
      reusedMatchups: initialReused,
      executedMatchups,
      pendingMatchups,
      activeMatchups,
      elapsedSeconds,
      estimatedRemainingSeconds: averageSecondsPerMatchup === null
        ? null
        : averageSecondsPerMatchup * pendingMatchups / Math.max(1, concurrency),
      updatedAt: new Date().toISOString(),
    };
    await writeAtomicJson(resolve(outputDirectory, "progress.json"), progress);
    onProgress?.(progress);
  };

  await writeProgress();
  const active = new Set();
  const workers = Array.from({ length: Math.min(concurrency, pending.length) }, async () => {
    while (cursor < pending.length && !firstFailure) {
      const matchupId = pending[cursor];
      cursor += 1;
      active.add(matchupId);
      try {
        const report = await runMatchup(matchupId);
        validateMatchupReport(report, matchupId);
        await writeAtomicJson(
          resolve(checkpointsDirectory, `${matchupId}.json`),
          {
            checkpointVersion: 1,
            runSignature,
            matchupId,
            completedAt: new Date().toISOString(),
            report,
          },
        );
        reports.set(matchupId, report);
        executedMatchups += 1;
      } catch (error) {
        firstFailure ??= error;
      } finally {
        active.delete(matchupId);
        await writeProgress([...active].toSorted());
      }
    }
  });
  await Promise.allSettled(workers);
  if (firstFailure) throw firstFailure;

  const orderedReports = matchupIds.map((matchupId) => reports.get(matchupId));
  return Object.freeze({
    totalMatchups: matchupIds.length,
    completedMatchups: reports.size,
    reusedMatchups: initialReused,
    executedMatchups,
    reports: Object.freeze(orderedReports),
  });
}


export async function seedDedicatedCheckpoints({
  mergedReport,
  outputDirectory,
  runSignature,
}) {
  if (!mergedReport || !Array.isArray(mergedReport.matchupSummaries) || !Array.isArray(mergedReport.rows)) {
    throw new TypeError("a merged dedicated report is required");
  }
  if (typeof runSignature !== "string" || !runSignature) {
    throw new TypeError("runSignature is required");
  }
  const checkpointsDirectory = resolve(outputDirectory, "checkpoints");
  await mkdir(checkpointsDirectory, { recursive: true });
  let seededMatchups = 0;
  let reusedMatchups = 0;

  for (const summary of mergedReport.matchupSummaries) {
    const matchupId = summary.matchupId;
    const existing = await readCheckpoint(checkpointsDirectory, matchupId);
    if (existing) {
      validateCheckpoint(existing, { matchupId, runSignature });
      reusedMatchups += 1;
      continue;
    }
    const report = extractMatchupReport(mergedReport, matchupId);
    validateMatchupReport(report, matchupId);
    await writeAtomicJson(resolve(checkpointsDirectory, `${matchupId}.json`), {
      checkpointVersion: 1,
      runSignature,
      matchupId,
      completedAt: new Date().toISOString(),
      seededFromCompletedReport: true,
      report,
    });
    seededMatchups += 1;
  }
  return Object.freeze({ seededMatchups, reusedMatchups });
}


export function mergeDedicatedMatchupReports(reports, {
  expectedMatchups = 17,
  expectedRows = 85,
  expectedRuns = 425,
} = {}) {
  if (!Array.isArray(reports) || reports.length !== expectedMatchups) {
    throw new Error(`expected ${expectedMatchups} completed matchup reports`);
  }
  const matchupIds = reports.map((report) => report.matchupSummaries?.[0]?.matchupId);
  if (new Set(matchupIds).size !== reports.length) {
    throw new Error("duplicate or missing dedicated matchup report");
  }
  reports.forEach((report, index) => validateMatchupReport(report, matchupIds[index]));
  const rows = reports.flatMap((report) => report.rows);
  const matchupSummaries = reports.flatMap((report) => report.matchupSummaries);
  const totalRuns = rows.reduce((total, row) => total + row.samples.length, 0);
  if (rows.length !== expectedRows || totalRuns !== expectedRuns) {
    throw new Error(
      `incomplete dedicated corpus: ${reports.length} matchups, ${rows.length} rows, ${totalRuns} attempts`,
    );
  }
  if (new Set(rows.map(({ id }) => id)).size !== rows.length) {
    throw new Error("duplicate dedicated row across matchup checkpoints");
  }
  const unresolvedRuns = rows.reduce((total, row) => total + row.comparison.unresolvedRuns, 0);
  const finiteDeltas = rows
    .map(({ comparison }) => comparison.absoluteMeanDelta)
    .filter(Number.isFinite);
  const summary = Object.freeze({
    matchups: reports.length,
    rows: rows.length,
    totalRuns,
    resolvedRuns: totalRuns - unresolvedRuns,
    unresolvedRuns,
    fullyUnresolvedRows: rows.filter(({ comparison }) => comparison.simulation.runs === 0).length,
    partiallyUnresolvedRows: rows.filter(({ comparison }) => (
      comparison.simulation.runs > 0 && comparison.unresolvedRuns > 0
    )).length,
    rowsOver25PointDelta: rows.filter(({ comparison }) => (
      comparison.absoluteMeanDelta > 25
    )).length,
    rowsInsideTapeBand: rows.filter(({ comparison }) => comparison.tapeBandError === 0).length,
    wrongWinnerRuns: rows.reduce((total, row) => total + row.comparison.wrongWinnerRuns, 0),
    meanAbsoluteMeanDelta: mean(finiteDeltas),
    medianAbsoluteMeanDelta: median(finiteDeltas),
    maximumAbsoluteMeanDelta: finiteDeltas.length ? Math.max(...finiteDeltas) : null,
  });
  return Object.freeze({
    ...reports[0],
    schedule: Object.freeze({
      matchups: reports.length,
      rows: rows.length,
      tapeRunsPerRow: 5,
      totalRuns,
      execution: "recoverable-per-matchup-checkpoints",
    }),
    summary,
    matchupSummaries: Object.freeze(matchupSummaries.toSorted((left, right) => (
      left.matchupId.localeCompare(right.matchupId)
    ))),
    rows: Object.freeze(rows.toSorted((left, right) => left.id.localeCompare(right.id))),
  });
}


export function validateMatchupReport(report, matchupId) {
  const valid = report
    && report.lane === "dedicated_golden_exact_repeat_starts"
    && report.schedule?.matchups === 1
    && report.schedule?.rows === 5
    && report.schedule?.totalRuns === 25
    && report.matchupSummaries?.length === 1
    && report.matchupSummaries[0].matchupId === matchupId
    && report.rows?.length === 5
    && report.rows.every((row) => (
      row.matchupId === matchupId && Array.isArray(row.samples) && row.samples.length === 5
    ));
  if (!valid) throw new Error(`invalid matchup report for ${matchupId}`);
  return true;
}


async function readCheckpoint(checkpointsDirectory, matchupId) {
  try {
    return JSON.parse(await readFile(resolve(checkpointsDirectory, `${matchupId}.json`), "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    if (error instanceof SyntaxError) {
      throw new Error(`invalid checkpoint JSON for ${matchupId}: ${error.message}`);
    }
    throw error;
  }
}


function validateCheckpoint(checkpoint, { matchupId, runSignature }) {
  const valid = checkpoint?.checkpointVersion === 1
    && checkpoint.runSignature === runSignature
    && checkpoint.matchupId === matchupId;
  if (!valid) throw new Error(`invalid checkpoint metadata for ${matchupId}`);
  try {
    validateMatchupReport(checkpoint.report, matchupId);
  } catch (error) {
    throw new Error(`invalid checkpoint for ${matchupId}: ${error.message}`);
  }
}


function extractMatchupReport(mergedReport, matchupId) {
  const rows = mergedReport.rows.filter((row) => row.matchupId === matchupId);
  const matchupSummaries = mergedReport.matchupSummaries.filter((summary) => (
    summary.matchupId === matchupId
  ));
  const unresolvedRuns = rows.reduce((total, row) => total + row.comparison.unresolvedRuns, 0);
  const finiteDeltas = rows
    .map(({ comparison }) => comparison.absoluteMeanDelta)
    .filter(Number.isFinite);
  return {
    ...mergedReport,
    schedule: {
      matchups: 1,
      rows: 5,
      tapeRunsPerRow: 5,
      totalRuns: 25,
    },
    summary: {
      matchups: 1,
      rows: 5,
      totalRuns: 25,
      rowsOver25PointDelta: rows.filter(({ comparison }) => comparison.absoluteMeanDelta > 25).length,
      rowsInsideTapeBand: rows.filter(({ comparison }) => comparison.tapeBandError === 0).length,
      wrongWinnerRuns: rows.reduce((total, row) => total + row.comparison.wrongWinnerRuns, 0),
      unresolvedRuns,
      meanAbsoluteMeanDelta: mean(finiteDeltas),
      medianAbsoluteMeanDelta: median(finiteDeltas),
      maximumAbsoluteMeanDelta: finiteDeltas.length ? Math.max(...finiteDeltas) : null,
    },
    matchupSummaries,
    rows,
  };
}


async function writeAtomicJson(path, value) {
  const sequence = atomicWriteSequence;
  atomicWriteSequence += 1;
  const temporary = `${path}.tmp-${process.pid}-${Date.now()}-${sequence}`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf8",
    flush: true,
  });
  await rename(temporary, path);
}


function validateQueueInputs({ matchupIds, outputDirectory, runSignature, concurrency, runMatchup }) {
  if (!Array.isArray(matchupIds) || !matchupIds.length || new Set(matchupIds).size !== matchupIds.length) {
    throw new TypeError("unique matchupIds are required");
  }
  if (typeof outputDirectory !== "string" || !outputDirectory) {
    throw new TypeError("outputDirectory is required");
  }
  if (typeof runSignature !== "string" || !runSignature) {
    throw new TypeError("runSignature is required");
  }
  if (!Number.isSafeInteger(concurrency) || concurrency < 1) {
    throw new RangeError("concurrency must be a positive integer");
  }
  if (typeof runMatchup !== "function") throw new TypeError("runMatchup is required");
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
