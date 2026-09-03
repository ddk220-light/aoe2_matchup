import { writeFile } from "node:fs/promises";

import {
  loadPhase2Batch1Context,
  loadPhase2Batch1Truth,
  runPhase2Batch1Sample,
} from "../../../src/phase2-batch1-comparison.js";


const ROOT = new URL("../../../", import.meta.url);
const OUTPUT = new URL("final_diagnostic_results.json", import.meta.url);
const ROW_IDS = Object.freeze([
  "elite_war_wagon_vs_paladin",
  "elite_war_wagon_vs_champion",
]);
const SAMPLE_INDEX = 0;
const SEED = 20260817;

const truth = await loadPhase2Batch1Truth(ROOT);
const context = await loadPhase2Batch1Context(ROOT, truth);
const comparisons = [];

for (const rowId of ROW_IDS) {
  const row = truth.rows.find(({ id }) => id === rowId);
  if (!row) throw new Error(`missing Phase 2 truth row ${rowId}`);
  const sample = runPhase2Batch1Sample({
    row,
    sampleIndex: SAMPLE_INDEX,
    seed: SEED,
    context,
  });
  const tapeScores = row.runs.map(({ signed_score: score }) => score);
  const tapeMean = mean(tapeScores);
  const comparison = Object.freeze({
    rowId,
    ratio: `${row.side2.count}v${row.side3.count}`,
    tape: Object.freeze({
      samples: row.runs.length,
      meanScore: round(tapeMean),
      minScore: round(Math.min(...tapeScores)),
      maxScore: round(Math.max(...tapeScores)),
      winnerOwner: winnerFromScore(tapeMean),
    }),
    simulation: sample,
    absoluteDelta: sample.score === null ? null : round(Math.abs(sample.score - tapeMean)),
    correctWinner: sample.score === null
      ? false
      : winnerFromScore(sample.score) === winnerFromScore(tapeMean),
  });
  comparisons.push(comparison);
  await publish();
  process.stdout.write(`${JSON.stringify(comparison)}\n`);
}


async function publish() {
  const result = Object.freeze({
    generatedAt: new Date().toISOString(),
    source: Object.freeze({
      archive: truth.archive,
      archiveSha256: truth.archive.zip_sha256,
    }),
    simulation: Object.freeze({ sampleIndex: SAMPLE_INDEX, seed: SEED }),
    comparisons: Object.freeze([...comparisons]),
  });
  const temporary = new URL("final_diagnostic_results.json.tmp", import.meta.url);
  await writeFile(temporary, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  const { rename } = await import("node:fs/promises");
  await rename(temporary, OUTPUT);
}


function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}


function winnerFromScore(score) {
  if (score > 0) return 3;
  if (score < 0) return 2;
  return null;
}


function round(value, digits = 4) {
  return Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
}
