import assert from "node:assert/strict";
import test from "node:test";

import {
  GOLDEN_SCENARIO_SHA256,
  loadLabScenario,
  scenarioFamilyFor,
} from "../src/lab-scenario.js";
import { unitBySlug } from "../src/unit-registry.js";


const root = new URL("../", import.meta.url);


test("AOE2 Lab classifies all four authored scenario families generically", () => {
  const champion = unitBySlug("champion");
  const paladin = unitBySlug("paladin");
  const arbalester = unitBySlug("arbalester");
  const handCannoneer = unitBySlug("hand_cannoneer");
  assert.equal(scenarioFamilyFor(champion, paladin), "melee_vs_melee");
  assert.equal(scenarioFamilyFor(arbalester, handCannoneer), "ranged_vs_ranged");
  assert.equal(scenarioFamilyFor(arbalester, paladin), "ranged_vs_melee");
  assert.equal(scenarioFamilyFor(paladin, arbalester), "melee_vs_ranged");
});


test("AOE2 Lab loads the exact melee golden placement and patrol", async () => {
  const scenario = await loadLabScenario(root, "champion", "paladin");
  assert.equal(scenario.family, "melee_vs_melee");
  assert.equal(scenario.goldenSha256, GOLDEN_SCENARIO_SHA256.melee_vs_melee);
  assert.equal(scenario.placementByOwner[2].length, 27);
  assert.equal(scenario.placementByOwner[3].length, 27);
  assert.deepEqual(Object.keys(scenario.openingPatrolByOwner), ["2", "3"]);
  assert.equal(scenario.auxiliaryArmiesByOwner, undefined);
});


test("AOE2 Lab mixed families preserve P4, diplomacy, and trigger gate", async () => {
  for (const [side2, side3, family] of [
    ["arbalester", "paladin", "ranged_vs_melee"],
    ["paladin", "arbalester", "melee_vs_ranged"],
  ]) {
    const scenario = await loadLabScenario(root, side2, side3);
    assert.equal(scenario.family, family);
    assert.equal(scenario.goldenSha256, GOLDEN_SCENARIO_SHA256[family]);
    assert.equal(scenario.placementByOwner[2].length, 27);
    assert.equal(scenario.placementByOwner[3].length, 27);
    assert.equal(scenario.auxiliaryArmiesByOwner[4].cells.length, 9);
    assert.equal(scenario.triggers.length, 2);
    assert.equal(scenario.preserveOwnerOrientation, true);
    const rangedOwner = family === "ranged_vs_melee" ? 2 : 3;
    assert.ok(scenario.victoryTeams.some(({ owners }) => (
      owners.includes(rangedOwner) && owners.includes(4)
    )));
  }
});
