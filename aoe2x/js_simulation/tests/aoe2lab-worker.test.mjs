import assert from "node:assert/strict";
import test from "node:test";

import { createLabPlan, runSeed } from "../tools/aoe2lab_worker.mjs";
import { unitBySlug } from "../src/unit-registry.js";

test("subject colors follow ownership without changing armies or legacy plans", () => {
  const base = request();
  const legacy = createLabPlan(base);
  assert.equal(legacy.scenario.playerColors, undefined);
  for (const owner of [2, 3]) {
    const colored = createLabPlan({...base, scenario: {...base.scenario, subjectOwner: owner}});
    assert.deepEqual(colored.scenario.playerColors, owner === 2 ? {2: 0, 3: 1} : {2: 1, 3: 0});
    assert.equal(colored.scenario.subjectOwner, owner);
    assert.equal(colored.scenario.colorPolicy, "subject_blue_opponent_red_v1");
    assert.deepEqual(colored.side2, legacy.side2);
    assert.deepEqual(colored.side3, legacy.side3);
    assert.deepEqual(colored.balance, legacy.balance);
    assert.notEqual(colored.planHash, legacy.planHash);
  }
  assert.equal(createLabPlan(base).planHash, legacy.planHash);
  for (const subjectOwner of [0, 1, 4, true, "2", null]) {
    assert.throws(() => createLabPlan({...base, scenario: {subjectOwner}}), /subjectOwner/);
  }
});

test("reviewed scenery is frozen into recording identity and cannot silently simulate", async () => {
  const base = request();
  const scenery = {path: "winter.aoe2scenario", sha256: "a".repeat(64),
    auditPath: "winter.audit.json", auditSha256: "b".repeat(64)};
  const ordinary = createLabPlan(base);
  const themed = createLabPlan({...base, scenario: {...base.scenario, scenery}});
  assert.notEqual(themed.planHash, ordinary.planHash);
  assert.deepEqual(themed.side2, ordinary.side2);
  assert.deepEqual(themed.side3, ordinary.side3);
  assert.deepEqual(themed.scenario.scenery, scenery);
  assert.equal(themed.scenario.goldenSha256, ordinary.scenario.goldenSha256);
  assert.throws(() => createLabPlan({...base, scenario: {scenery: {...scenery, sha256: "bad"}}}), /scenery/);
  await assert.rejects(runSeed(themed, 1), /recording-only/);
});

test("five-Hussar experiment changes only the screen and cannot run default-screen simulation", async () => {
  const base = {schemaVersion: 1, side2: {slug: "elite_blackwood_archer_tupi"},
    side3: {slug: "elite_jaguar_warrior_aztecs"},
    scenario: {player4Buffer: "golden"},
    balance: {mode: "equal_resources", cap: 27, maxResources: 5000}};
  const ordinary = createLabPlan(base);
  const reduced = createLabPlan({...base, scenario: {player4Count: 5}});
  assert.equal(ordinary.scenario.player4Count, undefined);
  assert.equal(reduced.scenario.player4Count, 5);
  assert.equal(reduced.scenario.hasPlayer4Gate, true);
  assert.equal(reduced.scenario.goldenSha256, ordinary.scenario.goldenSha256);
  assert.deepEqual(reduced.side2, ordinary.side2);
  assert.deepEqual(reduced.side3, ordinary.side3);
  assert.notEqual(reduced.planHash, ordinary.planHash);
  assert.equal(createLabPlan({...base, scenario: {player4Count: 10}}).scenario.player4Count, 10);
  for (const count of [0, -1, 11, 5.5, "5", null]) {
    assert.throws(() => createLabPlan({...base, scenario: {player4Count: count}}), /player4Count/);
  }
  assert.throws(() => createLabPlan({...base, scenario: {player4Count: 5, player4Buffer: "none"}}), /player4Count/);
  assert.throws(() => createLabPlan({...base, side3: {slug: "elite_mameluke_saracens"},
    scenario: {player4Count: 5}}), /player4Count/);
  await assert.rejects(runSeed(reduced, 1), /custom P4 count is recording-only/);
});

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
  assert.equal(unitBySlug("elite_jaguar_warrior_aztecs").master, 726);
  assert.equal(unitBySlug("elite_composite_bowman_armenians").master, 1802);
});


function request(overrides = {}) {
  return {
    schemaVersion: 1,
    scenario: {player4Buffer: "golden"},
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

test("new Arena plans have no buffer and Donut requires ranged P2 versus melee P3", async () => {
  const input = request({scenario: {}});
  const arena = createLabPlan(input);
  assert.equal(arena.scenario.player4Buffer, "none");
  assert.equal(arena.scenario.hasPlayer4Gate, false);
  assert.equal(arena.scenario.family, "ranged_vs_ranged");
  const donut = {path: "winter-donut.aoe2scenario", sha256: "a".repeat(64),
    auditPath: "winter-donut.audit.json", auditSha256: "b".repeat(64)};
  const plan = createLabPlan({...input, scenario: {donut}});
  assert.equal(plan.scenario.layout, "Donut");
  assert.deepEqual(plan.side2, arena.side2);
  assert.deepEqual(plan.side3, arena.side3);
  assert.notEqual(plan.planHash, arena.planHash);
  await assert.rejects(runSeed(plan, 1), /recording-only/);
  assert.throws(() => createLabPlan({...input, side2: input.side3, side3: input.side2,
    scenario: {donut}}), /ranged P2/);
  assert.throws(() => createLabPlan({...input, side3: {slug: "arbalester"},
    scenario: {donut}}), /ranged P2/);
});

test("explicit Arbalester/Jarl Donut exception preserves ranged classes and ownership", async () => {
  const donut = {path: "winter-donut.aoe2scenario", sha256: "a".repeat(64),
    auditPath: "winter-donut.audit.json", auditSha256: "b".repeat(64)};
  const input = request({side2: {slug: "arbalester_saracens"},
    side3: {slug: "elite_jarl_varangians"},
    scenario: {donut, subjectOwner: 3, donutExperiment: "arbalester_kites_jarl_v1"}});
  const plan = createLabPlan(input);
  assert.equal(plan.side2.ranged, true);
  assert.equal(plan.side3.ranged, true);
  assert.deepEqual(plan.scenario.playerColors, {2: 1, 3: 0});
  assert.equal(plan.scenario.donutExperiment, "arbalester_kites_jarl_v1");
  await assert.rejects(runSeed(plan, 1), /recording-only/);
  for (const replacement of [{side3: {slug: "arbalester_saracens"}},
      {scenario: {...input.scenario, subjectOwner: 2}},
      {scenario: {...input.scenario, donutExperiment: "any_ranged"}}]) {
    assert.throws(() => createLabPlan({...input, ...replacement}), /donutExperiment/);
  }
});

test("native ranged Golden accepts explicit no buffer with identical combat outcome", async () => {
  const input = request({ side2: {slug: "arbalester"}, side3: {slug: "elite_composite_bowman_armenians"}, balance: {mode: "explicit", n2: 1, n3: 1} });
  const ordinary = await runSeed(createLabPlan(input), 1);
  const explicit = await runSeed(createLabPlan({...input, scenario: {player4Buffer: "none"}}), 1);
  for (const key of ["winnerOwner", "winnerHp", "ticks", "startingHpByOwner"]) assert.deepEqual(explicit[key], ordinary[key]);
  await assert.rejects(runSeed(createLabPlan(request({scenario: {player4Buffer: "none"}})), 1), /matching simulation scenario/);
  await assert.rejects(runSeed(createLabPlan(request({side2: {slug: "flaming_camel_tatars"}, scenario: {player4Buffer: "none", goldenFamily: "ranged_vs_ranged"}})), 1), /matching simulation scenario/);
});

test("Flaming Camel uses the complete ranged Golden without changing unit combat classes", () => {
  for (const slug of ["elite_composite_bowman_armenians", "elite_jaguar_warrior_aztecs"]) {
    const ordinary = createLabPlan(request({side2: {slug: "flaming_camel_tatars"}, side3: {slug}}));
    const plan = createLabPlan(request({
      side2: {slug: "flaming_camel_tatars"}, side3: {slug},
      scenario: {goldenFamily: "ranged_vs_ranged", player4Buffer: "none"},
    }));
    const ranged = createLabPlan(request({side3: {slug: "arbalester"}}));
    assert.equal(plan.scenario.family, "ranged_vs_ranged");
    assert.equal(plan.scenario.goldenSha256, ranged.scenario.goldenSha256);
    assert.equal(plan.scenario.hasPlayer4Gate, false);
    assert.equal(plan.side2.ranged, false);
    assert.deepEqual(plan.side2, ordinary.side2);
    assert.deepEqual(plan.side3, ordinary.side3);
    assert.notEqual(plan.planHash, ordinary.planHash);
  }
  assert.throws(() => createLabPlan(request({scenario: {goldenFamily: "invalid"}})), /goldenFamily/);
});


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
