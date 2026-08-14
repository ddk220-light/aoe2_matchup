import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  compareDedicatedRow,
  loadDedicatedComparisonContext,
  runDedicatedTapeRepeat,
} from "../src/dedicated-golden-comparison.js";
import { loadDedicatedGoldenCorpus } from "../src/dedicated-golden-corpus.js";
import { UNIT_REGISTRY } from "../src/unit-registry.js";


const ROOT = new URL("../", import.meta.url);
const DEFAULT_OUTPUT = new URL(
  "../calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/",
  import.meta.url,
);
const labelBySlug = new Map(UNIT_REGISTRY.map(({ slug, label }) => [slug, label]));


export async function runDedicatedGoldenSuite({
  root = ROOT,
  corpus = undefined,
  context = undefined,
  runImpl = runDedicatedTapeRepeat,
  onProgress = undefined,
  shardIndex = 0,
  shardCount = 1,
  matchupIds = undefined,
} = {}) {
  if (!Number.isSafeInteger(shardCount) || shardCount < 1
      || !Number.isSafeInteger(shardIndex) || shardIndex < 0 || shardIndex >= shardCount) {
    throw new RangeError("shard index/count are invalid");
  }
  const selectedCorpus = corpus ?? await loadDedicatedGoldenCorpus(root);
  const selectedContext = context ?? await loadDedicatedComparisonContext(root);
  let selectedMatchups = selectedCorpus.matchups.filter((_, index) => (
    index % shardCount === shardIndex
  ));
  if (matchupIds !== undefined) {
    if (!Array.isArray(matchupIds) || !matchupIds.length || new Set(matchupIds).size !== matchupIds.length) {
      throw new TypeError("matchupIds must be a non-empty unique list");
    }
    const requested = new Set(matchupIds);
    selectedMatchups = selectedMatchups.filter(({ id }) => requested.has(id));
    const missing = matchupIds.filter((id) => !selectedMatchups.some((matchup) => matchup.id === id));
    if (missing.length) throw new Error(`unknown or unselected dedicated matchup: ${missing.join(", ")}`);
  }
  const totalRuns = selectedMatchups.reduce((total, matchup) => total + matchup.runs.length, 0);
  let completed = 0;
  const rows = [];

  for (const matchup of selectedMatchups) {
    for (const row of matchup.ratios) {
      const samples = [];
      for (const run of row.runs) {
        try {
          samples.push(await runImpl({ row, run, context: selectedContext }));
        } catch (error) {
          samples.push(Object.freeze({
            rowId: row.id,
            repeat: run.repeat,
            outcome: "error",
            winnerOwner: null,
            winnerHp: null,
            score: null,
            ticks: null,
            tapeScore: run.signed_score,
            delta: null,
            failure: String(error?.message ?? error),
          }));
        }
        completed += 1;
        onProgress?.({
          completed,
          total: totalRuns,
          matchupId: matchup.id,
          rowId: row.id,
          ratio: row.ratio,
          repeat: run.repeat,
        });
      }
      rows.push(Object.freeze({
        id: row.id,
        matchupId: matchup.id,
        matchup: `${labelBySlug.get(matchup.rangedSlug)} vs ${labelBySlug.get(matchup.meleeSlug)}`,
        ranged: Object.freeze({
          slug: matchup.rangedSlug,
          label: labelBySlug.get(matchup.rangedSlug),
          count: row.runs[0].starting_units.filter(({ owner }) => owner === 2).length,
        }),
        melee: Object.freeze({
          slug: matchup.meleeSlug,
          label: labelBySlug.get(matchup.meleeSlug),
          count: row.runs[0].starting_units.filter(({ owner }) => owner === 3).length,
        }),
        ratio: row.ratio,
        archive: row.archive,
        zipSha256: row.zipSha256,
        comparison: compareDedicatedRow(row, samples),
        samples: Object.freeze(samples),
      }));
    }
  }

  const matchupSummaries = selectedMatchups.map((matchup) => {
    const matchupRows = rows.filter(({ matchupId }) => matchupId === matchup.id);
    return Object.freeze({
      matchupId: matchup.id,
      matchup: matchupRows[0].matchup,
      rangedSlug: matchup.rangedSlug,
      meleeSlug: matchup.meleeSlug,
      rows: matchupRows.length,
      tapeRuns: matchupRows.length * 5,
      meanAbsoluteMeanDelta: mean(matchupRows.map(({ comparison }) => (
        comparison.absoluteMeanDelta
      ))),
      maxAbsoluteMeanDelta: Math.max(...matchupRows.map(({ comparison }) => (
        comparison.absoluteMeanDelta
      ))),
      rowsOver25PointDelta: matchupRows.filter(({ comparison }) => (
        comparison.absoluteMeanDelta > 25
      )).length,
      rowsInsideTapeBand: matchupRows.filter(({ comparison }) => (
        comparison.tapeBandError === 0
      )).length,
      wrongWinnerRuns: matchupRows.reduce((total, { comparison }) => (
        total + comparison.wrongWinnerRuns
      ), 0),
      unresolvedRuns: matchupRows.reduce((total, { comparison }) => (
        total + comparison.unresolvedRuns
      ), 0),
    });
  });
  const absoluteDeltas = rows.map(({ comparison }) => comparison.absoluteMeanDelta);
  return Object.freeze({
    schemaVersion: 1,
    lane: "dedicated_golden_exact_repeat_starts",
    source: Object.freeze({
      manifest: "aoe2x/js_simulation/calibration/source/dedicated_ranged_melee_sources.json",
      truth: "aoe2x/js_simulation/calibration/fixtures/dedicated_ranged_melee/dedicated_ranged_melee_truth.json",
      archives: Object.freeze(selectedCorpus.manifest.archives.map(({ archive, zip_sha256 }) => (
        Object.freeze({ archive, zipSha256: zip_sha256 })
      ))),
    }),
    config: Object.freeze({
      engine: "current checked-out JavaScript engine",
      placements: "exact starting_units from each individual tape repeat",
      goldenMap: true,
      navigation: "cohesive",
      meleeOpeningOrder: "attack-move-all",
      chaseCapture: true,
      meleeEngagementDwellTicks: 0,
      pairwiseAlliedTransit: false,
      preventiveContactSteering: true,
      kitingClock: "mechanics-derived",
      maxTicks: 9000,
    }),
    schedule: Object.freeze({
      matchups: selectedMatchups.length,
      rows: rows.length,
      tapeRunsPerRow: 5,
      totalRuns,
      shardIndex,
      shardCount,
    }),
    summary: Object.freeze({
      matchups: matchupSummaries.length,
      rows: rows.length,
      totalRuns,
      rowsOver25PointDelta: rows.filter(({ comparison }) => (
        comparison.absoluteMeanDelta > 25
      )).length,
      rowsInsideTapeBand: rows.filter(({ comparison }) => (
        comparison.tapeBandError === 0
      )).length,
      wrongWinnerRuns: rows.reduce((total, { comparison }) => (
        total + comparison.wrongWinnerRuns
      ), 0),
      unresolvedRuns: rows.reduce((total, { comparison }) => (
        total + comparison.unresolvedRuns
      ), 0),
      meanAbsoluteMeanDelta: mean(absoluteDeltas),
      medianAbsoluteMeanDelta: median(absoluteDeltas),
      maximumAbsoluteMeanDelta: Math.max(...absoluteDeltas),
    }),
    matchupSummaries: Object.freeze(matchupSummaries),
    rows: Object.freeze(rows),
  });
}


export function renderDedicatedCsv(report) {
  const header = [
    "matchup", "ratio", "ranged_count", "melee_count", "tape_mean", "tape_min",
    "tape_max", "simulation_mean", "simulation_min", "simulation_max", "mean_delta",
    "absolute_mean_delta", "tape_band_error", "tape_band_coverage", "wrong_winner_runs",
    "unresolved_runs", "archive", "zip_sha256",
  ];
  const values = report.rows.map((row) => [
    row.matchup, row.ratio, row.ranged.count, row.melee.count,
    row.comparison.tape.mean, row.comparison.tape.min, row.comparison.tape.max,
    row.comparison.simulation.mean, row.comparison.simulation.min,
    row.comparison.simulation.max, row.comparison.meanDelta,
    row.comparison.absoluteMeanDelta, row.comparison.tapeBandError,
    row.comparison.tapeBandCoverage, row.comparison.wrongWinnerRuns,
    row.comparison.unresolvedRuns, row.archive, row.zipSha256,
  ]);
  return `${[header, ...values].map((record) => record.map(csvCell).join(",")).join("\n")}\n`;
}


export async function writeDedicatedOutputs(report, outputDirectory = DEFAULT_OUTPUT) {
  await mkdir(outputDirectory, { recursive: true });
  await Promise.all([
    writeFile(resolveOutput(outputDirectory, "results.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8"),
    writeFile(resolveOutput(outputDirectory, "results.csv"), renderDedicatedCsv(report), "utf8"),
  ]);
}


export async function main(argv = process.argv.slice(2)) {
  const options = { outputDirectory: DEFAULT_OUTPUT, shardIndex: 0, shardCount: 1 };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!value || !["--output-dir", "--shard-index", "--shard-count"].includes(flag)) {
      throw new Error("usage: run_dedicated_ranged_melee_suite.mjs [--output-dir DIR] [--shard-index N --shard-count N]");
    }
    if (flag === "--output-dir") options.outputDirectory = resolve(value);
    if (flag === "--shard-index") options.shardIndex = Number(value);
    if (flag === "--shard-count") options.shardCount = Number(value);
  }
  let lastReported = 0;
  const report = await runDedicatedGoldenSuite({
    shardIndex: options.shardIndex,
    shardCount: options.shardCount,
    onProgress: ({ completed, total, matchupId, ratio }) => {
      if (completed === total || completed - lastReported >= 5) {
        lastReported = completed;
        process.stderr.write(`[${completed}/${total}] ${matchupId} ${ratio}\n`);
      }
    },
  });
  await writeDedicatedOutputs(report, options.outputDirectory);
  process.stdout.write(`${JSON.stringify(report.summary)}\n`);
  return report;
}


function resolveOutput(directory, fileName) {
  return directory instanceof URL ? new URL(fileName, directory) : resolve(directory, fileName);
}


function csvCell(value) {
  const string = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(string) ? `"${string.replaceAll('"', '""')}"` : string;
}


function mean(values) {
  const finite = values.filter(Number.isFinite);
  return finite.length ? finite.reduce((total, value) => total + value, 0) / finite.length : 0;
}


function median(values) {
  const sorted = values.filter(Number.isFinite).toSorted((left, right) => left - right);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}


if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  await main();
}
