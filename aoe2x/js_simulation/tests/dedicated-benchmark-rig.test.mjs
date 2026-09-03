import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  computeWorkerCount,
  mergeDedicatedMatchupReports,
  mergeDedicatedRowReports,
  runRecoverableDedicatedQueue,
  seedDedicatedCheckpoints,
} from "../src/dedicated-benchmark-rig.js";


test("80-percent worker count uses available parallelism without exceeding pending work", () => {
  assert.equal(computeWorkerCount({ availableParallelism: 32, pendingTasks: 100 }), 25);
  assert.equal(computeWorkerCount({ availableParallelism: 32, pendingTasks: 4 }), 4);
  assert.equal(computeWorkerCount({ availableParallelism: 1, pendingTasks: 4 }), 1);
});


test("recoverable queue checkpoints completed matchups and resumes only missing work", async () => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "dedicated-rig-resume-"));
  const firstCalls = [];

  await assert.rejects(
    runRecoverableDedicatedQueue({
      matchupIds: ["alpha", "bravo", "charlie"],
      outputDirectory,
      runSignature: "engine-a",
      concurrency: 1,
      runMatchup: async (matchupId) => {
        firstCalls.push(matchupId);
        if (matchupId === "charlie") throw new Error("simulated process crash");
        return fakeMatchupReport(matchupId);
      },
    }),
    /simulated process crash/,
  );
  assert.deepEqual(firstCalls, ["alpha", "bravo", "charlie"]);

  const secondCalls = [];
  const resumed = await runRecoverableDedicatedQueue({
    matchupIds: ["alpha", "bravo", "charlie"],
    outputDirectory,
    runSignature: "engine-a",
    concurrency: 2,
    runMatchup: async (matchupId) => {
      secondCalls.push(matchupId);
      return fakeMatchupReport(matchupId);
    },
  });

  assert.deepEqual(secondCalls, ["charlie"]);
  assert.equal(resumed.reusedMatchups, 2);
  assert.equal(resumed.executedMatchups, 1);
  assert.equal(resumed.completedMatchups, 3);
  const progress = JSON.parse(await readFile(join(outputDirectory, "progress.json"), "utf8"));
  assert.equal(progress.completedMatchups, 3);
  assert.equal(progress.pendingMatchups, 0);
});


test("recoverable queue refuses a malformed committed checkpoint instead of silently skipping it", async () => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "dedicated-rig-invalid-"));
  await seedDedicatedCheckpoints({
    mergedReport: fakeMergedReport(["alpha"]),
    outputDirectory,
    runSignature: "engine-a",
  });
  const checkpointPath = join(outputDirectory, "checkpoints", "alpha.json");
  const checkpoint = JSON.parse(await readFile(checkpointPath, "utf8"));
  checkpoint.report.rows.pop();
  await writeFile(checkpointPath, JSON.stringify(checkpoint), "utf8");

  await assert.rejects(
    runRecoverableDedicatedQueue({
      matchupIds: ["alpha"],
      outputDirectory,
      runSignature: "engine-a",
      concurrency: 1,
      runMatchup: async () => fakeMatchupReport("alpha"),
    }),
    /invalid checkpoint.*alpha/i,
  );
});


test("seeded completed report becomes valid per-matchup checkpoints and merges exactly", async () => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "dedicated-rig-seed-"));
  const merged = fakeMergedReport(["alpha", "bravo"]);
  const seeded = await seedDedicatedCheckpoints({
    mergedReport: merged,
    outputDirectory,
    runSignature: "engine-a",
  });
  assert.equal(seeded.seededMatchups, 2);

  const resumed = await runRecoverableDedicatedQueue({
    matchupIds: ["alpha", "bravo"],
    outputDirectory,
    runSignature: "engine-a",
    concurrency: 2,
    runMatchup: async () => {
      throw new Error("seeded matchup must not run again");
    },
  });
  const remerged = mergeDedicatedMatchupReports(resumed.reports, {
    expectedMatchups: 2,
    expectedRows: 10,
    expectedRuns: 50,
  });

  assert.equal(resumed.executedMatchups, 0);
  assert.equal(resumed.reusedMatchups, 2);
  assert.equal(remerged.summary.matchups, 2);
  assert.equal(remerged.summary.rows, 10);
  assert.equal(remerged.summary.totalRuns, 50);
});


test("recoverable queue can checkpoint individual rows and merge them by matchup", async () => {
  const outputDirectory = await mkdtemp(join(tmpdir(), "dedicated-rig-rows-"));
  const reportsByRow = new Map([
    ["alpha_0", fakeRowReport("alpha", 0)],
    ["alpha_1", fakeRowReport("alpha", 1)],
    ["bravo_0", fakeRowReport("bravo", 0)],
    ["bravo_1", fakeRowReport("bravo", 1)],
  ]);
  const rowIds = [...reportsByRow.keys()];
  const queue = await runRecoverableDedicatedQueue({
    matchupIds: rowIds,
    outputDirectory,
    runSignature: "engine-rows",
    concurrency: 2,
    runMatchup: async (rowId) => reportsByRow.get(rowId),
    validateReport: (report, rowId) => {
      assert.equal(report.rows.length, 1);
      assert.equal(report.rows[0].id, rowId);
    },
  });
  const merged = mergeDedicatedRowReports(queue.reports, {
    expectedMatchups: 2,
    expectedRows: 4,
    expectedRuns: 20,
  });

  assert.equal(queue.completedMatchups, 4);
  assert.equal(merged.schedule.execution, "recoverable-per-row-checkpoints");
  assert.equal(merged.summary.matchups, 2);
  assert.equal(merged.summary.rows, 4);
  assert.equal(merged.summary.totalRuns, 20);
  assert.deepEqual(merged.matchupSummaries.map(({ matchupId, rows }) => (
    [matchupId, rows]
  )), [["alpha", 2], ["bravo", 2]]);
});


function fakeMergedReport(matchupIds) {
  const reports = matchupIds.map(fakeMatchupReport);
  return mergeDedicatedMatchupReports(reports, {
    expectedMatchups: matchupIds.length,
    expectedRows: matchupIds.length * 5,
    expectedRuns: matchupIds.length * 25,
  });
}


function fakeMatchupReport(matchupId) {
  const rows = Array.from({ length: 5 }, (_, rowIndex) => ({
    id: `${matchupId}_${rowIndex}`,
    matchupId,
    matchup: matchupId,
    comparison: {
      absoluteMeanDelta: rowIndex,
      tapeBandError: 0,
      wrongWinnerRuns: 0,
      unresolvedRuns: 0,
      simulation: { runs: 5 },
    },
    samples: Array.from({ length: 5 }, (_, repeatIndex) => ({
      repeat: repeatIndex + 1,
      outcome: "win",
    })),
  }));
  return {
    schemaVersion: 1,
    lane: "dedicated_golden_exact_repeat_starts",
    source: { manifest: "manifest.json", truth: "truth.json", archives: [] },
    config: { engine: "test" },
    schedule: { matchups: 1, rows: 5, tapeRunsPerRow: 5, totalRuns: 25 },
    summary: {
      matchups: 1,
      rows: 5,
      totalRuns: 25,
      rowsOver25PointDelta: 0,
      rowsInsideTapeBand: 5,
      wrongWinnerRuns: 0,
      unresolvedRuns: 0,
      meanAbsoluteMeanDelta: 2,
      medianAbsoluteMeanDelta: 2,
      maximumAbsoluteMeanDelta: 4,
    },
    matchupSummaries: [{
      matchupId,
      matchup: matchupId,
      rows: 5,
      tapeRuns: 25,
      meanAbsoluteMeanDelta: 2,
      maxAbsoluteMeanDelta: 4,
      rowsOver25PointDelta: 0,
      rowsInsideTapeBand: 5,
      wrongWinnerRuns: 0,
      unresolvedRuns: 0,
    }],
    rows,
  };
}


function fakeRowReport(matchupId, rowIndex) {
  const source = fakeMatchupReport(matchupId);
  const row = source.rows[rowIndex];
  return {
    ...source,
    schedule: { matchups: 1, rows: 1, tapeRunsPerRow: 5, totalRuns: 5 },
    summary: {
      matchups: 1,
      rows: 1,
      totalRuns: 5,
      rowsOver25PointDelta: 0,
      rowsInsideTapeBand: 1,
      wrongWinnerRuns: 0,
      unresolvedRuns: 0,
      meanAbsoluteMeanDelta: row.comparison.absoluteMeanDelta,
      medianAbsoluteMeanDelta: row.comparison.absoluteMeanDelta,
      maximumAbsoluteMeanDelta: row.comparison.absoluteMeanDelta,
    },
    matchupSummaries: [{
      ...source.matchupSummaries[0],
      rows: 1,
      tapeRuns: 5,
      meanAbsoluteMeanDelta: row.comparison.absoluteMeanDelta,
      maxAbsoluteMeanDelta: row.comparison.absoluteMeanDelta,
    }],
    rows: [row],
  };
}
