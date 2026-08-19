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
const steppeMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/elite_steppe_lancer_cumans_imperial.json", import.meta.url),
  "utf8",
));
const scorpionMechanics = JSON.parse(await readFile(
  new URL("../fixtures/unit_stats/heavy_scorpion_japanese_imperial.json", import.meta.url),
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
  assert.equal(scenario.pairwiseEnemyTransit, undefined);
  assert.equal(scenario.reachMeleeWedgeTransit, false);
  assert.equal(scenario.meleeCrowdOwner, undefined);
  assert.equal(scenario.meleeCrowdOwners, undefined);
  assert.equal(scenario.preventiveContactSteering, true);
  assert.equal(scenario.map.id, "golden-map");
});


test("dedicated scenario enables reach-wedge transit only for sourced reach melee", () => {
  const scenario = scenarioFromDedicatedRun({
    row: {
      id: "heavy_cav_archer_vs_elite_steppe_5v10",
      ratio: "5v10",
      rangedSlug: "heavy_cav_archer",
      meleeSlug: "elite_steppe",
    },
    run: {
      starting_units: [
        { id: 100, owner: 2, master: 474, x: 6.5, y: 4.5, hp: 80 },
        { id: 200, owner: 3, master: 1372, x: 4.5, y: 12.5, hp: 100 },
      ],
    },
    mechanicsByMaster: new Map([
      [474, hcaMechanics],
      [1372, steppeMechanics],
    ]),
    map: { id: "golden-map" },
  });

  assert.equal(scenario.reachMeleeWedgeTransit, true);
});


test("dedicated Heavy Scorpion scenario uses native siege AI instead of cohesive kiting", () => {
  const scenario = scenarioFromDedicatedRun({
    row: {
      id: "heavy_scorpion_vs_champion_8v21",
      ratio: "8v21",
      rangedSlug: "heavy_scorpion",
      meleeSlug: "champion",
    },
    run: {
      starting_units: [
        { id: 100, owner: 2, master: 542, x: 6.5, y: 4.5, hp: 110 },
        { id: 200, owner: 3, master: 567, x: 4.5, y: 12.5, hp: 70 },
      ],
    },
    mechanicsByMaster: new Map([
      [542, scorpionMechanics],
      [567, championMechanics],
    ]),
    map: { id: "golden-map" },
  });

  assert.equal(scenario.kiteOwner, undefined);
  assert.equal(scenario.kiteProfile, undefined);
  assert.equal(scenario.kiteNavigation, undefined);
  assert.equal(scenario.kiteMeleeOpeningOrder, undefined);
  assert.equal(scenario.chaseCapture, undefined);
  assert.equal(scenario.kiteChaseDwellTicks, undefined);
  assert.equal(scenario.meleeCrowdOwner, undefined);
  assert.equal(scenario.meleeCrowdOwners, undefined);
  assert.equal(scenario.pairwiseEnemyTransit, undefined);
  assert.equal(scenario.preventiveContactSteering, true);
  assert.equal(scenario.units[0].mechanics.ranged.min_range_tiles, 2,
    "native Heavy Scorpion AI must retain its sourced individual minimum range");
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
