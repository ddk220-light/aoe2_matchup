import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  computeWorkerCount,
  mergeDedicatedMatchupReports,
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
