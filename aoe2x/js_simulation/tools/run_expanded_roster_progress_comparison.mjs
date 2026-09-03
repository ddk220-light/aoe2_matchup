// Build a point-in-time comparison for only the expanded-roster matchups that
// already have the full requested live sample. The live recorder may continue
// appending later matchups while this snapshot is calculated.
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { runExpandedComparison } from "./run_expanded_roster_comparison.mjs";


const DEFAULT_CAPTURE = new URL(
  "../calibration/live_observations/expanded_roster_5x_2026-08-31/",
  import.meta.url,
);
const DEFAULT_OUTPUT = new URL(
  "../calibration/reports/expanded_roster_progress_2026-08-31/simulation_5x.json",
  import.meta.url,
);


function argument(prefix) {
  return process.argv.find((value) => value.startsWith(prefix))?.slice(prefix.length);
}


const captureDirectory = argument("--capture=") ?? fileURLToPath(DEFAULT_CAPTURE);
const outputFile = argument("--output=") ?? fileURLToPath(DEFAULT_OUTPUT);
const requiredRuns = Number.parseInt(argument("--required-runs=") ?? "5", 10);
const seedCount = Number.parseInt(argument("--seed-count=") ?? "5", 10);
if (!Number.isSafeInteger(requiredRuns) || requiredRuns < 1) {
  throw new RangeError("--required-runs must be a positive integer");
}
if (!Number.isSafeInteger(seedCount) || seedCount < 1) {
  throw new RangeError("--seed-count must be a positive integer");
}

const capture = JSON.parse(await readFile(
  resolve(captureDirectory, "capture_manifest.json"), "utf8"));
const matchupKeys = capture.matchup_keys.filter((key) => (
  (capture.runs?.[key] ?? []).length >= requiredRuns
));
if (matchupKeys.length === 0) {
  throw new Error(`no matchups have ${requiredRuns} completed live runs`);
}

const openingSeeds = Array.from({ length: seedCount }, (_, seed) => seed);
let existing = null;
try {
  existing = JSON.parse(await readFile(resolve(outputFile), "utf8"));
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
}
if (existing) {
  const compatibleSeeds = existing.config?.openingSeeds?.length === openingSeeds.length
    && existing.config.openingSeeds.every((seed, index) => seed === openingSeeds[index]);
  if (!compatibleSeeds
      || existing.config?.rangedOpportunityRetargeting !== "generic-in-range-opportunity"
      || existing.config?.retainSimulationSnapshots !== false) {
    throw new Error("existing progress output uses an incompatible simulation configuration");
  }
}

const rowsByKey = new Map((existing?.rows ?? []).map((row) => [row.key, row]));
let report = existing;
for (const key of matchupKeys.filter((current) => !rowsByKey.has(current))) {
  const partial = await runExpandedComparison({
    captureDirectory,
    outputFile: `${resolve(outputFile)}.${key}.part.json`,
    openingSeeds,
    matchupKeys: [key],
    retainSimulationSnapshots: false,
  });
  rowsByKey.set(key, partial.rows[0]);
  const rows = matchupKeys.filter((current) => rowsByKey.has(current))
    .map((current) => rowsByKey.get(current));
  const failures = rows.filter(({ simulationSummary }) => simulationSummary.success !== true);
  report = {
    ...partial,
    generatedAt: new Date().toISOString(),
    summary: {
      matchups: rows.length,
      successes: rows.length - failures.length,
      failures: failures.length,
      wrongWinnerMatchups: failures.filter(({ liveSummary, simulationSummary }) => (
        liveSummary.winnerOwners.every((owner) => owner === liveSummary.winnerOwners[0])
          && simulationSummary.winnerOwners.some(
            (owner) => owner !== liveSummary.winnerOwners[0],
          )
      )).length,
      aboveTenPercentHp: failures.filter(({ simulationSummary }) => (
        simulationSummary.relativeWinnerHpDelta >= 0.10
      )).length,
    },
    failureKeys: failures.map(({ key: failureKey }) => failureKey),
    rows,
  };
  await writeFile(resolve(outputFile), `${JSON.stringify(report, null, 2)}\n`);
  process.stderr.write(
    `checkpointed ${rows.length}/${matchupKeys.length} live-complete matchups\n`,
  );
}
if (!report) {
  throw new Error("no comparison rows were produced");
}

process.stdout.write(`${JSON.stringify({
  ...report.summary,
  completedMatchups: matchupKeys,
  captureManifestMatchups: capture.matchup_keys.length,
  requiredRuns,
  seedCount,
})}\n`);
