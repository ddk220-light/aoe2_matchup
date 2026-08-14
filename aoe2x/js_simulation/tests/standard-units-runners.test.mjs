import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  runSchedule,
  runStandardUnitsSuite,
} from "../tools/run_standard_units_suite.mjs";
import { runStandardUnitsProductSuite } from "../tools/run_standard_units_product_suite.mjs";


const ROOT = new URL("../", import.meta.url);
const truth = JSON.parse(await readFile(
  new URL("../calibration/fixtures/standard_units/standard_units_truth.json", import.meta.url),
  "utf8",
));


test("schedule runs five samples for stable rows and 100 total for volatile rows", () => {
  const stable = truth.rows.find((row) => row.matchup === "Arbalester vs Champion");
  const volatile = truth.rows.find((row) => row.matchup === "Paladin vs Champion");
  const schedule = runSchedule({ rows: [stable, volatile], samples: 5, volatileSamples: 100 });

  assert.equal(schedule.filter(({ row }) => row.id === stable.id).length, 5);
  assert.equal(schedule.filter(({ row }) => row.id === volatile.id).length, 100);
  assert.deepEqual(schedule.slice(0, 5).map(({ sampleIndex }) => sampleIndex), [0, 1, 2, 3, 4]);
});


test("tape-conditioned runner preserves the approved schedule in its report", async () => {
  const row = truth.rows.find((candidate) => candidate.matchup === "Champion vs Paladin");
  const report = await runStandardUnitsSuite({
    root: ROOT,
    truth: { ...truth, rows: [row] },
    samples: 1,
    volatileSamples: 1,
    seed: 20260411,
  });

  assert.equal(report.lane, "tape_conditioned_canonical_start");
  assert.equal(report.rows.length, 1);
  assert.equal(report.schedule.totalRuns, 1);
  assert.equal(report.rows[0].samples.length, 1);
  assert.equal(typeof report.rows[0].comparison.bandError, "number");
});


test("standard benchmark keeps HCA as owner 2 and excludes the reversed mirror", async () => {
  const canonical = truth.rows.find(
    (candidate) => candidate.matchup === "Heavy Cavalry Archer vs Arbalester",
  );
  const reversed = truth.rows.find(
    (candidate) => candidate.matchup === "Arbalester vs Heavy Cavalry Archer",
  );
  const report = await runStandardUnitsSuite({
    root: ROOT,
    truth: { ...truth, rows: [canonical, reversed] },
    samples: 1,
    volatileSamples: 1,
    seed: 20260411,
  });

  assert.deepEqual(report.rows.map(({ matchup }) => matchup), [
    "Heavy Cavalry Archer vs Arbalester",
  ]);
  assert.equal(report.schedule.totalRuns, 1);
});


test("product controls contain normal, repeat, and reversed input", async () => {
  const row = truth.rows.find((candidate) => candidate.matchup === "Champion vs Paladin");
  const report = await runStandardUnitsProductSuite({ root: ROOT, rows: [row] });

  assert.equal(report.lane, "generated_placement_product_path");
  assert.deepEqual(report.rows[0].controls.map(({ name }) => name), [
    "normal", "repeat", "reversed",
  ]);
  assert.equal(report.rows[0].controls[0].finalStateHash, report.rows[0].controls[1].finalStateHash);
});


test("product controls record a 9000-tick engine timeout instead of aborting the corpus", async () => {
  const row = truth.rows.find((candidate) => candidate.matchup === "Champion vs Paladin");
  const report = await runStandardUnitsProductSuite({
    root: ROOT,
    rows: [row],
    runFightImpl: async () => { throw new Error("world exceeded 9000 ticks"); },
  });

  assert.equal(report.summary.unresolvedControls, 3);
  assert.deepEqual(report.rows[0].controls.map(({ outcome }) => outcome), [
    "timeout", "timeout", "timeout",
  ]);
});
