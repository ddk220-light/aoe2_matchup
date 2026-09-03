import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { runFight } from "../src/fight.js";
import { loadStandardUnitsTruth, signedScore, summarizeTape } from "../src/standard-units-comparison.js";
import { UNIT_REGISTRY } from "../src/unit-registry.js";


const ROOT_URL = new URL("../", import.meta.url);
const DEFAULT_OUTPUT_JSON = new URL(
  "../calibration/reports/standard_units_product_results_2026-08-08.json",
  import.meta.url,
);
const DEFAULT_OUTPUT_MARKDOWN = new URL(
  "../calibration/reports/standard_units_product_results_2026-08-08.md",
  import.meta.url,
);
const unitByMaster = new Map(UNIT_REGISTRY.map((unit) => [unit.master, unit]));


export async function runStandardUnitsProductSuite({
  root = ROOT_URL,
  rows = undefined,
  runFightImpl = runFight,
} = {}) {
  const selectedRows = rows ?? (await loadStandardUnitsTruth(root)).rows;
  const reportRows = [];
  for (const row of selectedRows) {
    const side2 = requireUnit(row.side2.master);
    const side3 = requireUnit(row.side3.master);
    const startHp = row.runs[0].starting_hp_by_owner;
    const normal = await runControl("normal", runFightImpl, root, {
      side2Slug: side2.slug, n2: row.side2.count, side3Slug: side3.slug, n3: row.side3.count,
    }, startHp, false);
    const repeat = await runControl("repeat", runFightImpl, root, {
      side2Slug: side2.slug, n2: row.side2.count, side3Slug: side3.slug, n3: row.side3.count,
    }, startHp, false);
    const reversed = await runControl("reversed", runFightImpl, root, {
      side2Slug: side3.slug, n2: row.side3.count, side3Slug: side2.slug, n3: row.side2.count,
    }, startHp, true);
    reportRows.push(Object.freeze({
      id: row.id,
      matchup: row.matchup,
      tape: summarizeTape(row),
      controls: Object.freeze([normal, repeat, reversed]),
      repeatMatchesNormal: normal.outcome === "win" && repeat.outcome === "win"
        ? normal.finalStateHash === repeat.finalStateHash
        && normal.eventLogHash === repeat.eventLogHash
        : null,
      reversedWinnerMatchesNormal: normal.outcome === "win" && reversed.outcome === "win"
        ? normal.winnerOwner === reversed.winnerOwner
        : null,
    }));
  }
  return Object.freeze({
    schemaVersion: 1,
    lane: "generated_placement_product_path",
    summary: Object.freeze({
      rowCount: reportRows.length,
      controlRuns: reportRows.length * 3,
      unresolvedControls: reportRows.flatMap(({ controls }) => controls)
        .filter(({ outcome }) => outcome === "timeout").length,
      repeatDeterminismFailures: reportRows.filter(({ repeatMatchesNormal }) => !repeatMatchesNormal).length,
      reversedWinnerMismatches: reportRows.filter(({ reversedWinnerMatchesNormal }) => !reversedWinnerMatchesNormal).length,
    }),
    rows: Object.freeze(reportRows),
  });
}


export function serializeStandardUnitsProductReport(report) {
  return `${JSON.stringify(report, null, 2)}\n`;
}


export function renderStandardUnitsProductMarkdown(report) {
  const lines = [
    "# Standard-units product-path controls",
    "",
    "This report measures generated placement through `runFight`; it is not merged into tape-conditioned fidelity KPIs.",
    "",
    `- Rows: ${report.summary.rowCount}`,
    `- Controls: ${report.summary.controlRuns}`,
    `- Repeat determinism failures: ${report.summary.repeatDeterminismFailures}`,
    `- Unresolved controls: ${report.summary.unresolvedControls}`,
    `- Reversed-input winner mismatches: ${report.summary.reversedWinnerMismatches}`,
    "",
    "| Matchup | Normal score | Repeat hash matches | Reversed winner matches |",
    "| --- | ---: | --- | --- |",
    ...report.rows.map((row) => `| ${row.matchup} | ${format(row.controls[0].score)} | ${row.repeatMatchesNormal ? "yes" : "no"} | ${row.reversedWinnerMatchesNormal ? "yes" : "no"} |`),
  ];
  return `${lines.join("\n")}\n`;
}


export async function writeStandardUnitsProductReport({ report, outputJson, outputMarkdown } = {}) {
  if (!outputJson || !outputMarkdown) {
    throw new TypeError("both JSON and Markdown output paths are required");
  }
  await Promise.all([
    mkdir(parentDirectory(outputJson), { recursive: true }),
    mkdir(parentDirectory(outputMarkdown), { recursive: true }),
  ]);
  await Promise.all([
    writeFile(outputJson, serializeStandardUnitsProductReport(report), "utf8"),
    writeFile(outputMarkdown, renderStandardUnitsProductMarkdown(report), "utf8"),
  ]);
}


export async function main(argv = process.argv.slice(2)) {
  if (argv.length !== 0) throw new Error("usage: run_standard_units_product_suite.mjs");
  const report = await runStandardUnitsProductSuite();
  await writeStandardUnitsProductReport({
    report,
    outputJson: DEFAULT_OUTPUT_JSON,
    outputMarkdown: DEFAULT_OUTPUT_MARKDOWN,
  });
  return report;
}


function requireUnit(master) {
  const unit = unitByMaster.get(master);
  if (!unit) throw new RangeError(`no product unit registry entry for master ${master}`);
  return unit;
}


function summarizeControl(name, result, startingHpByOwner, reverseOwners) {
  const winnerOwner = reverseOwners && result.winnerOwner !== null
    ? result.winnerOwner === 2 ? 3 : 2
    : result.winnerOwner;
  return Object.freeze({
    name,
    outcome: "win",
    winnerOwner,
    winnerHp: result.winnerHp,
    score: signedScore({ winnerOwner, winnerHp: result.winnerHp, startingHpByOwner }),
    ticks: result.ticks,
    finalStateHash: result.finalStateHash,
    eventLogHash: result.eventLogHash,
    orientationNormalised: result.orientationNormalised,
  });
}


async function runControl(name, runFightImpl, root, selection, startingHpByOwner, reverseOwners) {
  try {
    return summarizeControl(
      name,
      await runFightImpl(root, selection),
      startingHpByOwner,
      reverseOwners,
    );
  } catch (error) {
    if (!String(error?.message ?? error).includes("world exceeded 9000 ticks")) {
      throw error;
    }
    return Object.freeze({
      name,
      outcome: "timeout",
      winnerOwner: null,
      winnerHp: null,
      score: null,
      ticks: 9000,
      finalStateHash: null,
      eventLogHash: null,
      orientationNormalised: null,
    });
  }
}


function parentDirectory(pathOrUrl) {
  return pathOrUrl instanceof URL ? new URL(".", pathOrUrl) : dirname(resolve(pathOrUrl));
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
