import assert from "node:assert/strict";
import test from "node:test";
import { loadLabScenario } from "../src/lab-scenario.js";
import { deriveRecordedBattleSetup as setup } from "../src/battle-setup.js";

const root = new URL("../", import.meta.url);
const descriptor = (cost, unitClass = "melee") => ({ class: unitClass, effectiveCost: cost });
const food = (value, unitClass) => descriptor({ food: value, wood: 0, gold: 0 }, unitClass);

test("full discounted weighted prices reproduce Hearth Troop versus Composite Bowman", async () => {
  const actual = await setup(
    descriptor({ food: 0, wood: 64, gold: 28 }),
    descriptor({ food: 0, wood: 35, gold: 45 }, "mobile_ranged"),
  );
  assert.deepEqual(actual, { n2: 26, n3: 27, cost2: 88.4, cost3: 81,
    player4Count: 6, rangedOwner: 3,
    policy: "geometric_full_discount_weighted_resources_v3",
    bufferPolicy: "fielded_weighted_cost_v1" });
});

test("documented per-physical-unit prices produce literal Paladin counts", async () => {
  const paladin = descriptor({ food: 60, wood: 0, gold: 75 });
  for (const [price, paladins] of [[62.5, 18], [77.5, 20], [40.5, 14]]) {
    const result = await setup(food(price), paladin);
    assert.deepEqual([result.n2, result.n3, result.player4Count], [27, paladins, 0]);
  }
});

test("P4 uses the rounded fielded ranged army and supports either owner", async () => {
  const result = await setup(food(135.5, "mobile_ranged"), food(93));
  assert.deepEqual([result.n2, result.n3, result.rangedOwner, result.player4Count], [22, 27, 2, 6]);
  const reduced = await setup(food(450, "siege_ranged"), food(88.4));
  assert.deepEqual([reduced.n2, reduced.n3, reduced.player4Count], [12, 27, 7]);
});

test("documented P4 endpoints and half-up examples", async () => {
  for (const [total, count] of [[500, 5], [1093.5, 5], [2700, 6], [5500, 8], [10000, 10], [12000, 10]]) {
    const result = await setup(food(total, "mobile_ranged"), food(total), { cap: 1 });
    assert.equal(result.player4Count, count, `fielded weighted cost ${total}`);
  }
  const half = await setup(food(1), food(4), { cap: 27 });
  assert.deepEqual([half.n2, half.n3], [27, 14]);
});

test("ranged versus ranged has no buffer even when both armies are costly", async () => {
  const result = await setup(food(450, "mobile_ranged"), food(450, "siege_ranged"));
  assert.deepEqual([result.n2, result.n3, result.player4Count, result.rangedOwner], [27, 27, 0, null]);
});

test("dynamic screens preserve first golden slots, Spanish Hussar identity, and gates", async () => {
  for (const [left, right] of [["arbalester", "paladin"], ["paladin", "arbalester"]]) {
    const legacy = await loadLabScenario(root, left, right);
    for (const count of [1, 5, 6, 7, 10]) {
      const scenario = await loadLabScenario(root, left, right, { player4Count: count });
      const buffer = scenario.auxiliaryArmiesByOwner[4];
      assert.equal(buffer.cells.length, count);
      assert.equal(buffer.slug, "scout_cavalry");
      assert.deepEqual(buffer.cells.slice(0, 9), legacy.auxiliaryArmiesByOwner[4].cells.slice(0, count));
      assert.deepEqual(scenario.diplomacyByOwner, legacy.diplomacyByOwner);
      assert.deepEqual(scenario.triggers, legacy.triggers);
      assert.deepEqual(scenario.victoryTeams, legacy.victoryTeams);
      if (count === 10) {
        assert.deepEqual(buffer.cells[9], { x: 7.5, y: 5.5 });
        assert.equal(scenario.map.obstacles.some(({ x, y }) => x === 7.5 && y === 5.5), false);
        assert.equal([...scenario.placementByOwner[2], ...scenario.placementByOwner[3], ...buffer.cells.slice(0, 9)]
          .some(({ x, y }) => x === 7.5 && y === 5.5), false);
      }
    }
  }
});

test("explicit zero screen disables the gate like includeBuffer false", async () => {
  const disabled = await loadLabScenario(root, "paladin", "arbalester", { includeBuffer: false });
  const zero = await loadLabScenario(root, "paladin", "arbalester", { player4Count: 0 });
  assert.deepEqual(zero, disabled);
});
