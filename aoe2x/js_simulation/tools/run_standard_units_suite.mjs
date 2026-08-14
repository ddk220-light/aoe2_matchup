import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  compareRow,
  loadStandardUnitsTruth,
  runTapeConditioned,
  summarizeTape,
} from "../src/standard-units-comparison.js";
import { resolveFamily } from "../src/placement.js";
import { UNIT_REGISTRY } from "../src/unit-registry.js";


const ROOT_URL = new URL("../", import.meta.url);
const DEFAULT_OUTPUT_JSON = new URL(
  "../calibration/reports/standard_units_simulation_results_2026-08-08.json",
  import.meta.url,
);
const DEFAULT_OUTPUT_MARKDOWN = new URL(
  "../calibration/reports/standard_units_simulation_results_2026-08-08.md",
  import.meta.url,
);
const DEFAULT_SEED = 20260411;
const EXPECTED_ARCHIVE_SHA256 = "38E07C38344F06E527C28CD9B235ADA59AD1E722CDB8EC171296B877E8C1956D";
const unitByMaster = new Map(UNIT_REGISTRY.map((unit) => [unit.master, unit]));


export function runSchedule({ rows, samples, volatileSamples }) {
  requirePositiveInteger(samples, "samples");
  requirePositiveInteger(volatileSamples, "volatileSamples");
  if (volatileSamples < samples) {
    throw new RangeError("volatileSamples must be at least samples");
  }
  return rows.flatMap((row) => {
    const tape = summarizeTape(row);
    const count = tape.volatile ? volatileSamples : samples;
    return Array.from({ length: count }, (_, sampleIndex) => ({ row, tape, sampleIndex }));
  });
}


export async function runStandardUnitsSuite({
  root = ROOT_URL,
  truth = undefined,
  samples = 5,
  volatileSamples = 100,
  seed = DEFAULT_SEED,
} = {}) {
  if (!Number.isSafeInteger(seed)) throw new RangeError(`seed must be a safe integer, got ${seed}`);
  const loadedTruth = truth ?? await loadStandardUnitsTruth(root);
  requireAuthorizedTruth(loadedTruth);
  const benchmarkRows = loadedTruth.rows.filter((row) => !(
    row.side2.master === 492 && row.side3.master === 474
  ));
  const schedule = runSchedule({ rows: benchmarkRows, samples, volatileSamples });
  const samplesByRow = new Map(benchmarkRows.map((row) => [row.id, []]));

  for (const item of schedule) {
    samplesByRow.get(item.row.id).push(await runTapeConditioned(
      root,
      item.row,
      item.sampleIndex,
      seed,
    ));
  }

  const rows = benchmarkRows.map((row) => {
    const tape = summarizeTape(row);
    const rowSamples = samplesByRow.get(row.id);
    const comparison = compareRow({
      row,
      tape,
      simulationScores: rowSamples.map(({ score }) => score),
    });
    return Object.freeze({
      id: row.id,
      matchup: row.matchup,
      category: categoryFor(row),
      side2: row.side2,
      side3: row.side3,
      tape,
      comparison,
      samples: rowSamples,
    });
  });
  return Object.freeze({
    schemaVersion: 1,
    lane: "tape_conditioned_canonical_start",
    source: loadedTruth.archive,
    config: Object.freeze({ samples, volatileSamples, seed, maxTicks: 9000 }),
    schedule: Object.freeze({
      stableRows: rows.filter(({ tape }) => !tape.volatile).length,
      volatileRows: rows.filter(({ tape }) => tape.volatile).length,
      totalRuns: schedule.length,
    }),
    summary: summarizeReport(rows),
    rows,
  });
}


export function serializeStandardUnitsReport(report) {
  return `${JSON.stringify(report, null, 2)}\n`;
}


export function renderStandardUnitsMarkdown(report) {
  const summary = report.summary;
  const lines = [
    "# Standard-units tape-conditioned simulation results",
    "",
    `- Source SHA-256: \`${report.source.zip_sha256}\``,
    `- Samples: ${report.config.samples} stable; ${report.config.volatileSamples} volatile`,
    `- Seed: ${report.config.seed}`,
    `- Executed runs: ${report.schedule.totalRuns}`,
    `- Wrong stable winners: ${summary.wrongStableWinnerCount}`,
    `- Unresolved simulations: ${summary.unresolvedRuns}`,
    `- Total tape-band error: ${format(summary.totalBandError)}`,
    `- Mean tape-band coverage: ${format(summary.meanTapeBandCoverage * 100)}%`,
    "",
    "| Matchup | Category | Tape mean / band | Sim mean | Band error | Stable winner wrong? |",
    "| --- | --- | --- | ---: | ---: | --- |",
    ...report.rows.map((row) => [
      row.matchup,
      row.category,
      `${format(row.tape.mean)} / ${format(row.tape.min)}…${format(row.tape.max)}`,
      format(row.comparison.mean),
      format(row.comparison.bandError),
      row.comparison.wrongStableWinner ? "yes" : "no",
    ].map((value) => `| ${value} `).join("|") + "|"),
    "",
    "Rows with split tape winners are intentionally graded by band and winner distribution, not wrong-winner count.",
  ];
  return `${lines.join("\n")}\n`;
}


export async function writeStandardUnitsReport({ report, outputJson, outputMarkdown } = {}) {
  if (!outputJson || !outputMarkdown) {
    throw new TypeError("both JSON and Markdown output paths are required");
  }
  await Promise.all([
    mkdir(parentDirectory(outputJson), { recursive: true }),
    mkdir(parentDirectory(outputMarkdown), { recursive: true }),
  ]);
  await Promise.all([
    writeFile(outputJson, serializeStandardUnitsReport(report), "utf8"),
    writeFile(outputMarkdown, renderStandardUnitsMarkdown(report), "utf8"),
  ]);
}


export async function main(argv = process.argv.slice(2)) {
  const options = parseArguments(argv);
  const report = await runStandardUnitsSuite(options);
  await writeStandardUnitsReport({
    report,
    outputJson: options.outputJson ?? DEFAULT_OUTPUT_JSON,
    outputMarkdown: options.outputMarkdown ?? DEFAULT_OUTPUT_MARKDOWN,
  });
  return report;
}


function requireAuthorizedTruth(truth) {
  if (truth?.archive?.zip_sha256 !== EXPECTED_ARCHIVE_SHA256) {
    throw new Error("standard-units suite requires the verified standard-units truth fixture");
  }
  if (!Array.isArray(truth.rows) || truth.rows.length === 0) {
    throw new Error("standard-units suite requires at least one truth row");
  }
}


function categoryFor(row) {
  const side2 = unitByMaster.get(row.side2.master);
  const side3 = unitByMaster.get(row.side3.master);
  if (!side2 || !side3) throw new RangeError(`unknown unit master in ${row.id}`);
  return resolveFamily({ side2Class: side2.class, side3Class: side3.class });
}


function summarizeReport(rows) {
  const comparisons = rows.map(({ comparison }) => comparison);
  const bandErrors = comparisons.map(({ bandError }) => bandError).filter(Number.isFinite);
  const coverage = comparisons.map(({ tapeBandCoverage }) => tapeBandCoverage).filter(Number.isFinite);
  return Object.freeze({
    rowCount: rows.length,
    wrongStableWinnerCount: comparisons.filter(({ wrongStableWinner }) => wrongStableWinner).length,
    unresolvedRuns: comparisons.reduce((total, { unresolvedRuns }) => total + unresolvedRuns, 0),
    totalBandError: bandErrors.reduce((total, value) => total + value, 0),
    meanBandError: average(bandErrors),
    meanTapeBandCoverage: average(coverage),
    categories: Object.fromEntries(["kite", "rvr", "waves"].map((category) => {
      const inCategory = rows.filter((row) => row.category === category);
      return [category, {
        rows: inCategory.length,
        wrongStableWinnerCount: inCategory.filter(({ comparison }) => comparison.wrongStableWinner).length,
        totalBandError: inCategory.reduce((total, { comparison }) => total + (comparison.bandError ?? 0), 0),
      }];
    })),
  });
}


function parseArguments(argv) {
  const options = { samples: 5, volatileSamples: 100, seed: DEFAULT_SEED };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!value || ![
      "--samples", "--volatile-samples", "--seed", "--output-json", "--output-md",
    ].includes(flag)) {
      throw new Error("usage: run_standard_units_suite.mjs [--samples N] [--volatile-samples N] [--seed N] [--output-json FILE] [--output-md FILE]");
    }
    if (flag === "--samples") options.samples = Number(value);
    if (flag === "--volatile-samples") options.volatileSamples = Number(value);
    if (flag === "--seed") options.seed = Number(value);
    if (flag === "--output-json") options.outputJson = resolve(value);
    if (flag === "--output-md") options.outputMarkdown = resolve(value);
  }
  return options;
}


function parentDirectory(pathOrUrl) {
  return pathOrUrl instanceof URL ? new URL(".", pathOrUrl) : dirname(resolve(pathOrUrl));
}


function requirePositiveInteger(value, name) {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new RangeError(`${name} must be a positive safe integer, got ${value}`);
  }
}


function average(values) {
  return values.length === 0 ? 0 : values.reduce((total, value) => total + value, 0) / values.length;
}


function format(value) {
  return Number.isFinite(value) ? Number(value.toFixed(3)).toString() : "—";
}


if (
  process.argv[1]
  && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))
) {
  await main();
}
