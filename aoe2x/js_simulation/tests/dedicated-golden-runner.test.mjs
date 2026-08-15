import assert from "node:assert/strict";
import test from "node:test";

import { loadDedicatedGoldenCorpus } from "../src/dedicated-golden-corpus.js";
import { runDedicatedGoldenSuite } from "../tools/run_dedicated_ranged_melee_suite.mjs";


const ROOT = new URL("../", import.meta.url);


test("dedicated suite schedules all 425 exact tape repeats", async () => {
  const corpus = await loadDedicatedGoldenCorpus(ROOT);
  const progress = [];
  const report = await runDedicatedGoldenSuite({
    root: ROOT,
    corpus,
    context: Object.freeze({}),
    runImpl: ({ row, run }) => ({
      rowId: row.id,
      repeat: run.repeat,
      outcome: "win",
      score: run.signed_score,
      tapeScore: run.signed_score,
      delta: 0,
    }),
    onProgress: (event) => progress.push(event),
  });

  assert.equal(report.schedule.matchups, 17);
  assert.equal(report.schedule.rows, 85);
  assert.equal(report.schedule.totalRuns, 425);
  assert.equal(report.rows.length, 85);
  assert.equal(report.summary.rowsOver25PointDelta, 0);
  assert.equal(report.summary.unresolvedRuns, 0);
  assert.equal(report.summary.meanAbsoluteMeanDelta, 0);
  assert.equal(progress.at(-1).completed, 425);
});


test("dedicated suite records an engine exception and continues the corpus", async () => {
  const corpus = await loadDedicatedGoldenCorpus(ROOT);
  let calls = 0;
  const report = await runDedicatedGoldenSuite({
    root: ROOT,
    corpus,
    context: Object.freeze({}),
    runImpl: ({ row, run }) => {
      calls += 1;
      if (calls === 1) throw new Error("collision constraints did not converge");
      return {
        rowId: row.id,
        repeat: run.repeat,
        outcome: "win",
        score: run.signed_score,
        tapeScore: run.signed_score,
        delta: 0,
      };
    },
  });

  assert.equal(calls, 425);
  assert.equal(report.summary.unresolvedRuns, 1);
  assert.equal(report.rows[0].samples[0].outcome, "error");
  assert.match(report.rows[0].samples[0].failure, /collision constraints/);
});


test("dedicated suite can run a deterministic four-way matchup shard", async () => {
  const corpus = await loadDedicatedGoldenCorpus(ROOT);
  const report = await runDedicatedGoldenSuite({
    root: ROOT,
    corpus,
    context: Object.freeze({}),
    shardIndex: 0,
    shardCount: 4,
    runImpl: ({ row, run }) => ({
      rowId: row.id,
      repeat: run.repeat,
      outcome: "win",
      score: run.signed_score,
      tapeScore: run.signed_score,
      delta: 0,
    }),
  });

  assert.equal(report.schedule.matchups, 5);
  assert.equal(report.schedule.rows, 25);
  assert.equal(report.schedule.totalRuns, 125);
  assert.deepEqual(report.matchupSummaries.map(({ matchupId }) => matchupId), [
    "arbalester_vs_champion",
    "arbalester_vs_elite_steppe",
    "imp_elite_skirm_vs_paladin",
    "heavy_cav_archer_vs_elite_fire_lancer",
    "heavy_scorpion_vs_paladin",
  ]);
});


test("dedicated suite can isolate one named matchup for a recoverable worker", async () => {
  const corpus = await loadDedicatedGoldenCorpus(ROOT);
  const report = await runDedicatedGoldenSuite({
    root: ROOT,
    corpus,
    context: Object.freeze({}),
    matchupIds: ["heavy_cav_archer_vs_champion"],
    runImpl: ({ row, run }) => ({
      rowId: row.id,
      repeat: run.repeat,
      outcome: "win",
      score: run.signed_score,
      tapeScore: run.signed_score,
      delta: 0,
    }),
  });

  assert.equal(report.schedule.matchups, 1);
  assert.equal(report.schedule.rows, 5);
  assert.equal(report.schedule.totalRuns, 25);
  assert.deepEqual(report.matchupSummaries.map(({ matchupId }) => matchupId), [
    "heavy_cav_archer_vs_champion",
  ]);
});


test("dedicated suite can isolate one named ratio row", async () => {
  const corpus = await loadDedicatedGoldenCorpus(ROOT);
  const report = await runDedicatedGoldenSuite({
    root: ROOT,
    corpus,
    context: Object.freeze({}),
    rowIds: ["heavy_cav_archer_vs_elite_steppe_20v20"],
    runImpl: ({ row, run }) => ({
      rowId: row.id,
      repeat: run.repeat,
      outcome: "win",
      score: run.signed_score,
      tapeScore: run.signed_score,
      delta: 0,
    }),
  });

  assert.equal(report.schedule.matchups, 1);
  assert.equal(report.schedule.rows, 1);
  assert.equal(report.schedule.totalRuns, 5);
  assert.deepEqual(report.rows.map(({ id }) => id), [
    "heavy_cav_archer_vs_elite_steppe_20v20",
  ]);
});
