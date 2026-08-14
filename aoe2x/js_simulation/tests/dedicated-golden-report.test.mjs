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
