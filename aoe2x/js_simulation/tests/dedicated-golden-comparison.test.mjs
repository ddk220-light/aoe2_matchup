import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  compareDedicatedRow,
  scenarioFromDedicatedRun,
} from "../src/dedicated-golden-comparison.js";


const hcaMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/heavy_cav_archer_saracens_imperial.json", import.meta.url),
  "utf8",
));
const championMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/champion_chinese_imperial.json", import.meta.url),
  "utf8",
));


test("dedicated scenario uses the exact repeat placement and current viewer policy", () => {
  const row = {
    id: "heavy_cav_archer_vs_champion_5v10",
    ratio: "5v10",
    rangedSlug: "heavy_cav_archer",
    meleeSlug: "champion",
  };
  const run = {
    starting_units: [
      { id: 100, owner: 2, master: 474, x: 6.5, y: 4.5, hp: 80 },
      { id: 200, owner: 3, master: 567, x: 4.5, y: 12.5, hp: 70 },
    ],
  };
  const scenario = scenarioFromDedicatedRun({
    row,
    run,
    mechanicsByMaster: new Map([
      [474, hcaMechanics],
      [567, championMechanics],
    ]),
    map: { id: "golden-map" },
  });

  assert.deepEqual(scenario.units.map(({ referenceId, owner, x, y }) => ({
    referenceId, owner, x, y,
  })), [
    { referenceId: 100, owner: 2, x: 6.5, y: 4.5 },
    { referenceId: 200, owner: 3, x: 4.5, y: 12.5 },
  ]);
  assert.equal(scenario.kiteOwner, 2);
  assert.equal(scenario.kiteNavigation, "cohesive");
  assert.equal(scenario.kiteMeleeOpeningOrder, "attack-move-all");
  assert.equal(scenario.chaseCapture, true);
  assert.equal(scenario.kiteChaseDwellTicks, 0);
  assert.equal(scenario.pairwiseAlliedTransit, false);
  assert.equal(scenario.preventiveContactSteering, true);
  assert.equal(scenario.map.id, "golden-map");
});


test("dedicated row comparison scores all five exact tape repeats", () => {
  const row = {
    id: "example_5v10",
    runs: [-30, -20, -10, 10, 20].map((signed_score, index) => ({
      repeat: index + 1,
      signed_score,
    })),
  };
  const samples = [-25, -15, -5, 15, 25].map((score, index) => ({
    repeat: index + 1,
    score,
    outcome: "win",
  }));
  const result = compareDedicatedRow(row, samples);

  assert.equal(result.tape.runs, 5);
  assert.equal(result.simulation.runs, 5);
  assert.equal(result.meanDelta, 5);
  assert.equal(result.absoluteMeanDelta, 5);
  assert.deepEqual(result.repeatDeltas, [5, 5, 5, 5, 5]);
  assert.equal(result.unresolvedRuns, 0);
});
