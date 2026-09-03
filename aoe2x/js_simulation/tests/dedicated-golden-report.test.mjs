import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  buildDedicatedGoldenAnalysis,
  buildDedicatedGoldenArtifact,
} from "../tools/build_dedicated_ranged_melee_report.mjs";


const RESULTS = new URL(
  "../calibration/reports/dedicated_ranged_melee_current_engine_2026-08-14/results.json",
  import.meta.url,
);


test("dedicated report analysis keeps failures out of resolved delta denominators", async () => {
  const report = JSON.parse(await readFile(RESULTS, "utf8"));
  const analysis = buildDedicatedGoldenAnalysis(report);

  assert.equal(analysis.coverage.totalRows, 85);
  assert.equal(analysis.coverage.resolvedRows, 59);
  assert.equal(analysis.coverage.failedRows, 26);
  assert.equal(analysis.coverage.totalAttempts, 425);
  assert.equal(analysis.coverage.resolvedAttempts, 295);
  assert.equal(analysis.thresholds.rowsOver25Points, 9);
  assert.equal(analysis.thresholds.rowsAtOrUnder25Points, 50);
  assert.equal(analysis.failureCategories.length, 1);
  assert.equal(analysis.failureCategories[0].category, "collision convergence");
  assert.equal(analysis.failureCategories[0].rows, 26);
  assert.equal(analysis.rowsOver25[0].rowId, "heavy_scorpion_vs_paladin_15v20");
  assert.equal(analysis.rowsOver25[0].absoluteMeanDelta, 164.3777777777778);
});


test("dedicated report classifies a fully timed-out row as a tick-limit failure", async () => {
  const report = structuredClone(JSON.parse(await readFile(RESULTS, "utf8")));
  const row = report.rows[0];
  row.comparison.absoluteMeanDelta = null;
  row.comparison.meanDelta = null;
  row.comparison.tapeBandError = null;
  row.comparison.unresolvedRuns = 5;
  row.samples = row.samples.map((sample) => ({
    ...sample,
    outcome: "timeout",
    ticks: 9000,
    score: null,
    delta: null,
  }));
  const analysis = buildDedicatedGoldenAnalysis(report);
  const failedRow = analysis.allRows.find(({ rowId }) => rowId === row.id);

  assert.equal(failedRow.status, "engine failure");
  assert.equal(failedRow.failure, "world exceeded 9000 ticks");
  assert.ok(analysis.failureCategories.some(({ category }) => category === "tick limit"));
});


test("dedicated artifact exposes the complete 85-row audit table and required technical sections", async () => {
  const report = JSON.parse(await readFile(RESULTS, "utf8"));
  const analysis = buildDedicatedGoldenAnalysis(report);
  const artifact = buildDedicatedGoldenArtifact({ report, analysis });

  assert.equal(artifact.surface, "report");
  assert.equal(artifact.snapshot.status, "ready");
  assert.equal(artifact.snapshot.datasets.all_rows.length, 85);
  assert.equal(artifact.snapshot.datasets.rows_over_25.length, 9);
  assert.equal(artifact.snapshot.datasets.failure_categories.length, 1);
  assert.deepEqual(
    artifact.manifest.blocks.filter(({ type }) => type === "markdown").map(({ id }) => id),
    [
      "title",
      "technical-summary",
      "key-findings-heading",
      "threshold-interpretation",
      "failures-heading",
      "scope-definitions",
      "methodology",
      "limitations",
      "next-steps",
      "further-questions",
    ],
  );
  assert.equal(artifact.manifest.sources.length, 4);
});


test("dedicated artifact derives findings and execution details from the supplied run", async () => {
  const report = JSON.parse(await readFile(RESULTS, "utf8"));
  const baseline = buildDedicatedGoldenAnalysis(report);
  const analysis = {
    ...baseline,
    coverage: {
      ...baseline.coverage,
      resolvedRows: 85,
      failedRows: 0,
      resolvedAttempts: 425,
      failedAttempts: 0,
      fullyUnresolvedRows: 0,
      partiallyUnresolvedRows: 0,
    },
    accuracy: {
      ...baseline.accuracy,
      meanAbsoluteMeanDelta: 4.25,
      medianAbsoluteMeanDelta: 3.5,
      maximumAbsoluteMeanDelta: 12.75,
      rowsInsideTapeBand: 70,
      wrongWinnerRuns: 2,
    },
    thresholds: {
      resolvedRows: 85,
      rowsAtOrUnder25Points: 85,
      rowsOver25Points: 0,
    },
    failureCategories: [],
    rowsOver25: [],
  };
  const artifact = buildDedicatedGoldenArtifact({
    report,
    analysis,
    execution: {
      workers: 19,
      availableParallelism: 24,
      checkpointUnit: "one complete ratio row (5 exact tape repeats)",
    },
  });
  const markdown = artifact.manifest.blocks
    .filter(({ type }) => type === "markdown")
    .map(({ body }) => body)
    .join("\n");

  assert.match(markdown, /all \*\*425 attempts\*\* resolved/);
  assert.match(markdown, /median absolute tape delta is \*\*3\.5 percentage points\*\*/);
  assert.match(markdown, /\*\*85\/85 \(100%\)\*\* are at or below 25 points/);
  assert.match(markdown, /\*\*19 child processes\*\* across 24 available logical CPUs/);
  assert.match(markdown, /No ratio row exceeds 25 points/);
  assert.doesNotMatch(markdown, /six of the nine rows|Four deterministic matchup shards|19\.19-point/);
});
