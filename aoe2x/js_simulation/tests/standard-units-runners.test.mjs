import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import * as standardUnitsRunner from "../tools/run_standard_units_suite.mjs";
import { runStandardUnitsProductSuite } from "../tools/run_standard_units_product_suite.mjs";


const { runSchedule, runStandardUnitsSuite } = standardUnitsRunner;


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


test("ranged-versus-melee selection contains exactly the 48 authorized tape ratios", () => {
  assert.equal(typeof standardUnitsRunner.selectRangedVsMeleeRows, "function");
  const rows = standardUnitsRunner.selectRangedVsMeleeRows(truth.rows);
  const schedule = runSchedule({ rows, samples: 5, volatileSamples: 100 });

  assert.equal(rows.length, 48);
  assert.deepEqual([...new Set(rows.map(({ side2 }) => side2.master))].sort((a, b) => a - b), [
    5, 6, 474, 492, 542, 588,
  ]);
  assert.deepEqual([...new Set(rows.map(({ side3 }) => side3.master))].sort((a, b) => a - b), [
    330, 359, 441, 567, 569, 1134, 1372, 1903,
  ]);
  assert.equal(rows.filter((row) => row.runs.some(({ signed_score: score }) => score < 0)
    && row.runs.some(({ signed_score: score }) => score > 0)).length, 6);
  assert.equal(schedule.length, 810);
});


test("tape-conditioned runner preserves the approved schedule in its report", async () => {
  const row = truth.rows.find((candidate) => candidate.matchup === "Champion vs Paladin");
  const progress = [];
  const report = await runStandardUnitsSuite({
    root: ROOT,
    truth: { ...truth, rows: [row] },
    samples: 1,
    volatileSamples: 1,
    seed: 20260411,
    onProgress: (event) => progress.push(event),
  });

  assert.equal(report.lane, "tape_conditioned_canonical_start");
  assert.equal(report.rows.length, 1);
  assert.equal(report.schedule.totalRuns, 1);
  assert.equal(report.rows[0].samples.length, 1);
  assert.equal(typeof report.rows[0].comparison.bandError, "number");
  assert.deepEqual(progress.map(({ completed, total, rowId }) => ({ completed, total, rowId })), [
    { completed: 1, total: 1, rowId: row.id },
  ]);
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
