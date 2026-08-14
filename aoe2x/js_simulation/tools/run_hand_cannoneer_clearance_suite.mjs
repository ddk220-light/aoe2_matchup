import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  compareRow,
  loadStandardUnitsTruth,
  runTapeConditioned,
  summarizeTape,
} from "../src/standard-units-comparison.js";

const ROOT = new URL("../", import.meta.url);
const BASELINE = new URL(
  "../calibration/reports/standard_units_simulation_results_2026-08-08.json",
  import.meta.url,
);
const HCA_CONTROL = new URL(
  "../calibration/fixtures/standard_units/hca_vs_champion_pre_hc_escape_control_2026-08-08.json",
  import.meta.url,
);
const OUTPUT_JSON = new URL(
  "../calibration/reports/hand_cannoneer_kited_escape_results_2026-08-08.json",
  import.meta.url,
);
const OUTPUT_MD = new URL(
  "../calibration/reports/hand_cannoneer_kited_escape_results_2026-08-08.md",
  import.meta.url,
);
const HC_MASTER = 5;
const MELEE_MASTERS = new Set([359, 441, 567, 1903, 330, 569, 1134, 1372]);
const HCA_VS_CHAMPION = "Heavy Cavalry Archer vs Champion";

export function handCannoneerRows(truth) {
  return truth.rows.filter((row) => (
    row.side2.master === HC_MASTER && MELEE_MASTERS.has(row.side3.master)
  ));
}

export function evaluateAcceptance(rows, hcaIdentity) {
  const baselineBandError = sum(rows.map(({ baseline }) => baseline.bandError));
  const candidateBandError = sum(rows.map(({ candidate }) => candidate.bandError));
  const stableWinnerFailures = rows.filter(({ candidate }) => candidate.wrongStableWinner);
  const goodRowRegressions = rows.filter(({ baseline, candidate }) => (
    baseline.bandError <= 10 && candidate.bandError - baseline.bandError > 10
  ));
  const unresolvedRuns = sum(rows.map(({ candidate }) => candidate.unresolvedRuns));
  return Object.freeze({
    accepted: stableWinnerFailures.length === 0
      && goodRowRegressions.length === 0
      && unresolvedRuns === 0
      && hcaIdentity
      && candidateBandError < baselineBandError,
    baselineBandError,
    candidateBandError,
    improvement: baselineBandError - candidateBandError,
    stableWinnerFailures: stableWinnerFailures.map(({ matchup }) => matchup),
    goodRowRegressions: goodRowRegressions.map(({ matchup }) => matchup),
    unresolvedRuns,
    hcaIdentity,
    over25: rows.filter(({ candidate }) => candidate.bandError > 25)
      .map(({ matchup, candidate }) => ({ matchup, delta: candidate.bandError })),
  });
}

export async function runClearanceSuite() {
  const [truth, baseline, hcaControl] = await Promise.all([
    loadStandardUnitsTruth(ROOT),
    readFile(BASELINE, "utf8").then(JSON.parse),
    readFile(HCA_CONTROL, "utf8").then(JSON.parse),
  ]);
  if (truth.archive.zip_sha256 !== baseline.source.zip_sha256) {
    throw new Error("baseline and active truth archive hashes differ");
  }
  const seed = baseline.config.seed;
  const rows = [];
  for (const row of handCannoneerRows(truth)) {
    const tape = summarizeTape(row);
    const count = tape.volatile ? 100 : 5;
    const samples = [];
    for (let sampleIndex = 0; sampleIndex < count; sampleIndex += 1) {
      samples.push(await runTapeConditioned(
        ROOT,
        row,
        sampleIndex,
        seed,
        { kitedEscape: true },
      ));
    }
    const baselineRow = baseline.rows.find(({ id }) => id === row.id);
    if (!baselineRow) throw new Error(`baseline missing ${row.id}`);
    rows.push(Object.freeze({
      id: row.id,
      matchup: row.matchup,
      tape,
      baseline: baselineRow.comparison,
      candidate: compareRow({ row, tape, simulationScores: samples.map(({ score }) => score) }),
      samples,
    }));
  }

  const hcaTruth = truth.rows.find(({ matchup }) => matchup === HCA_VS_CHAMPION);
  if (!hcaTruth || hcaControl.matchup !== HCA_VS_CHAMPION) {
    throw new Error("HCA-vs-Champion identity row is missing");
  }
  if (hcaControl.archive_zip_sha256 !== truth.archive.zip_sha256) {
    throw new Error("HCA identity control uses a different tape archive");
  }
  const hcaSamples = [];
  for (let sampleIndex = 0; sampleIndex < 5; sampleIndex += 1) {
    const current = await runTapeConditioned(ROOT, hcaTruth, sampleIndex, hcaControl.seed);
    const before = hcaControl.samples[sampleIndex];
    hcaSamples.push(Object.freeze({
      sampleIndex,
      scoreIdentical: current.score === before.score,
      finalStateHashIdentical: current.finalStateHash === before.final_state_hash,
      eventLogHashIdentical: current.eventLogHash === before.event_log_hash,
      before: Object.freeze({
        score: before.score,
        finalStateHash: before.final_state_hash,
        eventLogHash: before.event_log_hash,
      }),
      current: Object.freeze({
        score: current.score,
        finalStateHash: current.finalStateHash,
        eventLogHash: current.eventLogHash,
      }),
    }));
  }
  const hcaIdentity = hcaSamples.every((sample) => (
    sample.scoreIdentical
    && sample.finalStateHashIdentical
    && sample.eventLogHashIdentical
  ));
  const acceptance = evaluateAcceptance(rows, hcaIdentity);
  return Object.freeze({
    schemaVersion: 1,
    source: truth.archive,
    config: Object.freeze({ stableSamples: 5, volatileSamples: 100, seed }),
    acceptance,
    rows,
    hcaGate: Object.freeze({ matchup: HCA_VS_CHAMPION, identical: hcaIdentity, samples: hcaSamples }),
  });
}

function markdown(report) {
  const lines = [
    "# Hand Cannoneer HCA-style kited-escape A/B results",
    "",
    `- Decision: **${report.acceptance.accepted ? "ACCEPT" : "REJECT"}**`,
    `- Source SHA-256: \`${report.source.zip_sha256}\``,
    `- Samples: ${report.config.stableSamples} stable; ${report.config.volatileSamples} volatile`,
    `- Aggregate HC band error: ${fmt(report.acceptance.baselineBandError)} -> ${fmt(report.acceptance.candidateBandError)} (${fmt(report.acceptance.improvement)} better)`,
    `- HCA-vs-Champion hashes bit-identical: ${report.hcaGate.identical ? "yes" : "no"}`,
    "",
    "| Matchup | Runs | Tape mean / band | Baseline mean | Candidate mean | Baseline error | Candidate error | Candidate side-3 win rate |",
    "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ...report.rows.map((row) => `| ${row.matchup} | ${row.candidate.simulationRuns} | ${fmt(row.tape.mean)} / ${fmt(row.tape.min)}…${fmt(row.tape.max)} | ${fmt(row.baseline.mean)} | ${fmt(row.candidate.mean)} | ${fmt(row.baseline.bandError)} | ${fmt(row.candidate.bandError)} | ${fmt(100 * row.candidate.side3WinRate)}% |`),
    "",
    "## Failures and greater-than-25-point deltas",
    "",
    report.acceptance.stableWinnerFailures.length
      ? `- Wrong stable winners: ${report.acceptance.stableWinnerFailures.join(", ")}`
      : "- Wrong stable winners: none.",
    report.acceptance.goodRowRegressions.length
      ? `- Greater-than-10-point regressions on good rows: ${report.acceptance.goodRowRegressions.join(", ")}`
      : "- Greater-than-10-point regressions on good rows: none.",
    ...report.acceptance.over25.map(({ matchup, delta }) => `- ${matchup}: ${fmt(delta)} points outside the tape band.`),
  ];
  return `${lines.join("\n")}\n`;
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

function fmt(value) {
  return Number.isFinite(value) ? Number(value.toFixed(3)).toString() : "—";
}

export async function main() {
  const report = await runClearanceSuite();
  await mkdir(new URL("../calibration/reports/", import.meta.url), { recursive: true });
  await Promise.all([
    writeFile(OUTPUT_JSON, `${JSON.stringify(report, null, 2)}\n`, "utf8"),
    writeFile(OUTPUT_MD, markdown(report), "utf8"),
  ]);
  return report;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const report = await main();
  console.log(markdown(report));
  if (!report.acceptance.accepted) process.exitCode = 1;
}
