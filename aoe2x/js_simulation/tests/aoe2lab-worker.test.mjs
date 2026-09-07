import assert from "node:assert/strict";
import test from "node:test";

import { createLabPlan } from "../tools/aoe2lab_worker.mjs";
import { unitBySlug } from "../src/unit-registry.js";

test("recording roster preserves Tiger P2 and ranged screens for melee-damage throwers", () => {
  for (const slug of ["elite_composite_bowman_armenians", "elite_throwing_axeman",
    "elite_gbeto", "elite_mameluke_saracens", "elite_ratha_(ranged)_bengalis"]) {
    const plan = createLabPlan(request({
      side2: { slug: "elite_tiger_cavalry_wei" }, side3: { slug },
    }));
    assert.equal(plan.side2.slug, "elite_tiger_cavalry_wei");
    assert.equal(plan.side3.slug, slug);
    assert.equal(plan.scenario.family, "melee_vs_ranged");
    assert.equal(plan.scenario.hasPlayer4Gate, true);
  }
  const jaguar = createLabPlan(request({
    side2: { slug: "elite_tiger_cavalry_wei" },
    side3: { slug: "elite_jaguar_warrior_aztecs" },
  }));
  assert.equal(jaguar.scenario.family, "melee_vs_melee");
  assert.equal(jaguar.side3.weightedCost, 90);
  assert.equal(unitBySlug("elite_jaguar_warrior_aztecs"), undefined);
  assert.equal(unitBySlug("elite_composite_bowman_armenians"), undefined);
});


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
