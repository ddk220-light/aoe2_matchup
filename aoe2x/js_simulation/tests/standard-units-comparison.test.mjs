import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  compareRow,
  runTapeConditioned,
  signedScore,
  summarizeTape,
} from "../src/standard-units-comparison.js";


const ROOT = new URL("../", import.meta.url);
const truth = JSON.parse(await readFile(
  new URL("../calibration/fixtures/standard_units/standard_units_truth.json", import.meta.url),
  "utf8",
));
const acceptedHandCannoneer = JSON.parse(await readFile(
  new URL(
    "../calibration/reports/hand_cannoneer_translated_persistent_measured_phase_results_2026-08-09.json",
    import.meta.url,
  ),
  "utf8",
));
const SEED = 20260411;


function tapeRow(scores) {
  return {
    runs: scores.map((signed_score) => ({
      status: "scored",
      signed_score,
      winner_owner: signed_score < 0 ? 2 : 3,
    })),
  };
}


test("signed score preserves owner direction and tape HP denominator", () => {
  assert.equal(signedScore({
    winnerOwner: 2,
    winnerHp: 45,
    startingHpByOwner: { 2: 90, 3: 120 },
  }), -50);
  assert.equal(signedScore({
    winnerOwner: 3,
    winnerHp: 30,
    startingHpByOwner: { 2: 90, 3: 120 },
  }), 25);
  assert.equal(signedScore({ winnerOwner: null, winnerHp: null, startingHpByOwner: {} }), null);
});


test("row comparison gives zero band error inside a tape band", () => {
  const row = tapeRow([-20, -10, -15]);
  const tape = summarizeTape(row);
  const comparison = compareRow({ row, tape, simulationScores: [-12, -14] });

  assert.deepEqual(tape, {
    scoredRuns: 3,
    timeoutRuns: 0,
    mean: -15,
    min: -20,
    max: -10,
    side3WinRate: 0,
    volatile: false,
  });
  assert.equal(comparison.bandError, 0);
  assert.equal(comparison.wrongStableWinner, false);
});


test("row comparison calls the opposite sign wrong only for stable tape winners", () => {
  const stable = tapeRow([-20, -10]);
  const volatile = tapeRow([-20, 10]);

  assert.equal(compareRow({
    row: stable,
    tape: summarizeTape(stable),
    simulationScores: [15],
  }).wrongStableWinner, true);
  assert.equal(compareRow({
    row: volatile,
    tape: summarizeTape(volatile),
    simulationScores: [15],
  }).wrongStableWinner, false);
});


test("a tape-conditioned sample is deterministic for its canonical start and seed", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Champion vs Paladin");
  assert.ok(row, "Champion vs Paladin row must be present in authorized truth");

  const first = await runTapeConditioned(ROOT, row, 0, SEED);
  const second = await runTapeConditioned(ROOT, row, 0, SEED);

  assert.deepEqual(second, first);
  assert.equal(first.sampleIndex, 0);
  assert.equal(first.seed, SEED);
  assert.equal(typeof first.score, "number");
  assert.equal(typeof first.finalStateHash, "string");
  assert.equal(typeof first.eventLogHash, "string");
});


test("mobile ranged versus siege uses the recorded ranged-vs-ranged control path", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Elite Skirmisher vs Siege Onager");
  assert.ok(row, "Elite Skirmisher vs Siege Onager row must be present in authorized truth");

  const result = await runTapeConditioned(ROOT, row, 0, SEED);

  assert.equal(result.winnerOwner, 3);
  assert.ok(result.score > 0, `expected the Siege Onager side to win, got ${result.score}`);
});


test("elite skirmisher versus heavy camel enables the recorded contact capture", async () => {
  const row = truth.rows.find(
    ({ matchup }) => matchup === "Elite Skirmisher vs Heavy Camel Rider",
  );
  assert.ok(row, "Elite Skirmisher vs Heavy Camel Rider row must be present in authorized truth");

  const results = await Promise.all(
    Array.from({ length: 5 }, (_, sampleIndex) => (
      runTapeConditioned(ROOT, row, sampleIndex, SEED)
    )),
  );
  const camelWins = results.filter(({ winnerOwner }) => winnerOwner === 3).length;
  const meanScore = results.reduce((total, { score }) => total + score, 0) / results.length;

  assert.ok(camelWins >= 3, `expected a Heavy Camel majority, got ${camelWins}/5`);
  assert.ok(meanScore > 0, `expected a Heavy Camel mean win, got ${meanScore}`);
});


test("heavy cavalry archer versus champion enables the recorded kited escape", async () => {
  const row = truth.rows.find(
    ({ matchup }) => matchup === "Heavy Cavalry Archer vs Champion",
  );
  assert.ok(row, "Heavy Cavalry Archer vs Champion row must be present in authorized truth");

  const results = await Promise.all(
    Array.from({ length: 5 }, (_, sampleIndex) => (
      runTapeConditioned(ROOT, row, sampleIndex, SEED)
    )),
  );
  const hcaWins = results.filter(({ winnerOwner }) => winnerOwner === 2).length;
  const meanScore = results.reduce((total, { score }) => total + score, 0) / results.length;

  assert.ok(hcaWins >= 3, `expected a Heavy Cavalry Archer majority, got ${hcaWins}/5`);
  assert.ok(meanScore < 0, `expected a Heavy Cavalry Archer mean win, got ${meanScore}`);
});


test("Hand Cannoneer HCA-style escape stays an explicit calibration experiment", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Champion");
  assert.ok(row, "Hand Cannoneer vs Champion row must be present in authorized truth");

  const baseline = await runTapeConditioned(ROOT, row, 0, SEED);
  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { kitedEscape: true },
  );

  assert.equal(typeof baseline.score, "number");
  assert.equal(typeof candidate.score, "number");
  assert.notEqual(candidate.finalStateHash, baseline.finalStateHash);
  assert.notEqual(candidate.eventLogHash, baseline.eventLogHash);
});


test("Hand Cannoneer cohort motion stays an explicit calibration experiment", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Champion");
  assert.ok(row, "Hand Cannoneer vs Champion row must be present in authorized truth");

  const baseline = await runTapeConditioned(ROOT, row, 0, SEED);
  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { cohortMotion: "contact_heading" },
  );

  assert.notEqual(candidate.finalStateHash, baseline.finalStateHash);
  assert.notEqual(candidate.eventLogHash, baseline.eventLogHash);
});


test("rejected Hand Cannoneer spacing is inert under accepted translated motion", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Champion");
  assert.ok(row, "Hand Cannoneer vs Champion row must be present in authorized truth");

  const baseline = await runTapeConditioned(ROOT, row, 0, SEED);
  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { formationSpacingTiles: 0.35 },
  );
  const repeat = await runTapeConditioned(ROOT, row, 0, SEED);

  assert.equal(candidate.finalStateHash, baseline.finalStateHash);
  assert.equal(candidate.eventLogHash, baseline.eventLogHash);
  assert.equal(repeat.finalStateHash, baseline.finalStateHash);
  assert.equal(repeat.eventLogHash, baseline.eventLogHash);
  assert.ok(candidate.diagnostics.damageEventsByOwner["2"] > 0);
  assert.ok(candidate.diagnostics.damageEventsByOwner["3"] > 0);
  assert.ok(candidate.diagnostics.damageAmountByOwner["2"] > 0);
  assert.ok(Number.isSafeInteger(candidate.diagnostics.firstDamageTickByOwner["2"]));
});


test("accepted Hand Cannoneer translated formation is the product default", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Champion");
  assert.ok(row, "Hand Cannoneer vs Champion row must be present in authorized truth");

  const baseline = await runTapeConditioned(ROOT, row, 0, SEED);
  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { formationMotion: "translated_offsets" },
  );
  const repeat = await runTapeConditioned(ROOT, row, 0, SEED);

  assert.equal(candidate.finalStateHash, baseline.finalStateHash);
  assert.equal(candidate.eventLogHash, baseline.eventLogHash);
  assert.equal(repeat.finalStateHash, baseline.finalStateHash);
  assert.equal(repeat.eventLogHash, baseline.eventLogHash);
});


test("Hand Cannoneer measured opening volley stays an explicit calibration experiment", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Champion");
  assert.ok(row, "Hand Cannoneer vs Champion row must be present in authorized truth");

  const baseline = await runTapeConditioned(ROOT, row, 0, SEED);
  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { firstBeatTick: 40 },
  );
  const repeat = await runTapeConditioned(ROOT, row, 0, SEED);

  assert.notEqual(candidate.finalStateHash, baseline.finalStateHash);
  assert.notEqual(candidate.eventLogHash, baseline.eventLogHash);
  assert.equal(repeat.finalStateHash, baseline.finalStateHash);
  assert.equal(repeat.eventLogHash, baseline.eventLogHash);
});


test("Hand Cannoneer in-progress opening attack stays an explicit calibration experiment", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Champion");
  assert.ok(row, "Hand Cannoneer vs Champion row must be present in authorized truth");

  const baseline = await runTapeConditioned(ROOT, row, 0, SEED);
  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { firstBeatTick: 1 },
  );

  assert.notEqual(candidate.finalStateHash, baseline.finalStateHash);
  assert.ok(candidate.diagnostics.firstDamageTickByOwner["2"]
    < baseline.diagnostics.firstDamageTickByOwner["2"]);
});


test("Hand Cannoneer closing opening persists until an early shot can land", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Champion");
  assert.ok(row, "Hand Cannoneer vs Champion row must be present in authorized truth");

  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { firstBeatTick: 1, openingVolley: "close_to_fire" },
  );

  assert.ok(candidate.diagnostics.firstDamageTickByOwner["2"] < 200,
    `expected an opening-volley hit before tick 200, got ${candidate.diagnostics.firstDamageTickByOwner["2"]}`);
});


test("Hand Cannoneer persistent volley pursuit resolves the translated Paladin endgame", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Paladin");
  assert.ok(row, "Hand Cannoneer vs Paladin row must be present in authorized truth");

  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    {
      formationMotion: "translated_offsets",
      firstBeatTick: 1,
      volleyPursuit: "close_to_fire",
    },
  );

  assert.equal(candidate.outcome, "win");
  assert.ok(candidate.diagnostics.firstDamageTickByOwner["2"] < 200);
});


test("Hand Cannoneer contact capture stays an explicit calibration experiment", async () => {
  const row = truth.rows.find(({ matchup }) => matchup === "Hand Cannoneer vs Elite Steppe Lancer");
  assert.ok(row, "Hand Cannoneer vs Elite Steppe Lancer row must be present in authorized truth");

  const experiment = {
    formationMotion: "translated_offsets",
    firstBeatTick: 1,
    volleyPursuit: "close_to_fire",
  };
  const baseline = await runTapeConditioned(ROOT, row, 0, SEED, experiment);
  const candidate = await runTapeConditioned(
    ROOT,
    row,
    0,
    SEED,
    { ...experiment, chaseCapture: true },
  );

  assert.notEqual(candidate.eventLogHash, baseline.eventLogHash);
});


test("the product Hand Cannoneer profile reproduces every accepted sample-zero hash", async () => {
  assert.equal(acceptedHandCannoneer.accepted, true);
  assert.equal(acceptedHandCannoneer.volatileExpansionRan, true);

  for (const reported of acceptedHandCannoneer.rows) {
    const row = truth.rows.find(({ id }) => id === reported.id);
    const expected = reported.samples.find(({ sampleIndex }) => sampleIndex === 0);
    assert.ok(row && expected, `accepted report is missing sample zero for ${reported.id}`);
    const current = await runTapeConditioned(ROOT, row, 0, SEED);
    assert.equal(current.score, expected.score, `${reported.matchup} score`);
    assert.equal(current.finalStateHash, expected.finalStateHash,
      `${reported.matchup} final state`);
    assert.equal(current.eventLogHash, expected.eventLogHash,
      `${reported.matchup} event log`);
  }
});
