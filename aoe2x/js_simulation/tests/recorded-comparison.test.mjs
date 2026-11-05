import assert from "node:assert/strict";
import test from "node:test";
import { compareRecordedResult } from "../node/compare-recorded.mjs";

test("comparison reports winner flips and signed HP without outcome correction", () => {
  const result = compareRecordedResult({ jobId: "example",
    recordingClock: { rows: "video_seconds", gameSpeed: 1.7 }, expected: { outcome: {
    winnerOwner: 3, winnerHp: 500, survivors: 10, signedRemainingHpPercent: -50,
    eliminationTimeSeconds: 20,
  } } }, {
    jobId: "example", winnerOwner: 2, winnerHp: 200, startingHpByOwner: { 2: 1000 },
    ticks: 1500, remainingByOwner: { 2: { units: 4, hp: 200 } },
  });
  assert.equal(result.winnerMatches, false);
  assert.equal(result.simulation.signedRemainingHpPercent, 20);
  assert.equal(result.signedHpPercentagePointDifference, 70);
  assert.equal(result.recorded.eliminationGameSeconds, 34);
  assert.equal(result.durationDifferenceSeconds, -9);
  assert.equal(result.simulation.survivors, 4);
  assert.equal(result.status, "preliminary");
});

test("failed simulation is an error, not a match or tie", () => {
  const result = compareRecordedResult({ jobId: "bad", expected: { outcome: {} } },
    { jobId: "bad", error: { message: "unsupported effect" } });
  assert.equal(result.status, "error");
  assert.equal(result.error.message, "unsupported effect");
  assert.equal(result.winnerMatches, undefined);
});

test("timeouts have no elimination time, HP score or recorded-winner comparison", () => {
  const result = compareRecordedResult({ jobId: "timeout",
    recordingClock: { rows: "video_seconds", gameSpeed: 1.7 }, expected: { outcome: {
      winnerOwner: 2, signedRemainingHpPercent: 50, eliminationTimeSeconds: 20,
    } } }, { outcome: "timeout", winnerOwner: null, winnerHp: 0, ticks: 9000,
    remainingByOwner: { 2: { units: 1, hp: 10 }, 3: { units: 1, hp: 10 } } });
  assert.equal(result.status, "timeout");
  assert.equal(result.winnerMatches, null);
  assert.equal(result.simulation.eliminationTimeSeconds, null);
  assert.equal(result.simulation.signedRemainingHpPercent, null);
  assert.equal(result.durationDifferenceSeconds, null);
  assert.equal(result.signedHpPercentagePointDifference, null);
});
