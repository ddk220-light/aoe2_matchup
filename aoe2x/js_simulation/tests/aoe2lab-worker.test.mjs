import assert from "node:assert/strict";
import test from "node:test";

import { createLabPlan } from "../tools/aoe2lab_worker.mjs";


function request(overrides = {}) {
  return {
    schemaVersion: 1,
    side2: { slug: "arbalester", civ: "Chinese" },
    side3: { slug: "paladin", civ: "Spanish" },
    balance: {
      mode: "equal_resources",
      cap: 27,
      weights: { food: 1, wood: 1, gold: 1 },
    },
    ...overrides,
  };
}


test("AOE2 Lab plan derives equal-resource counts and immutable provenance", () => {
  const plan = createLabPlan(request());
  assert.equal(plan.matchupId, "arbalester_vs_paladin");
  assert.equal(plan.side2.count, 27);
  assert.equal(plan.side3.count, 14);
  assert.equal(plan.side2.armyWeightedResources, 1890);
  assert.equal(plan.side3.armyWeightedResources, 1890);
  assert.equal(plan.scenario.family, "ranged_vs_melee");
  assert.equal(plan.scenario.hasPlayer4Gate, true);
  assert.match(plan.planHash, /^[a-f0-9]{64}$/);
  assert.equal(createLabPlan(request()).planHash, plan.planHash);
});


test("AOE2 Lab plan applies resource weights and explicit counts without fitting", () => {
  const weighted = createLabPlan(request({
    balance: {
      mode: "equal_resources",
      cap: 27,
      weights: { food: 1, wood: 1, gold: 1.5 },
    },
  }));
  assert.equal(weighted.side2.weightedCost, 92.5);
  assert.equal(weighted.side3.weightedCost, 172.5);
  assert.equal(weighted.side2.count, 27);
  assert.equal(weighted.side3.count, 14);

  const explicit = createLabPlan(request({
    balance: {
      mode: "explicit", cap: 27, n2: 20, n3: 13,
      weights: { food: 1, wood: 1, gold: 1 },
    },
  }));
  assert.equal(explicit.side2.count, 20);
  assert.equal(explicit.side3.count, 13);
});


test("AOE2 Lab plan rejects unknown units and invalid counts", () => {
  assert.throws(() => createLabPlan(request({
    side2: { slug: "not_a_unit" },
  })), /unknown unit/);
  assert.throws(() => createLabPlan(request({
    balance: {
      mode: "explicit", cap: 27, n2: 28, n3: 1,
      weights: { food: 1, wood: 1, gold: 1 },
    },
  })), /n2 must be an integer/);
});
