import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { UNIT_REGISTRY, UNIT_SLUGS, unitBySlug } from "../src/unit-registry.js";

// The cost scalars the calibrated corpus was purchased with.
const CALIBRATED_COST = {
  arbalester: 92.5,
  champion: 80.0,
  elite_elephant: 205.0,
  elite_fire_lancer: 112.5,
  elite_steppe: 130.0,
  halberdier: 60.0,
  hand_cannoneer: 120.0,
  heavy_camel: 145.0,
  heavy_cav_archer: 130.0,
  heavy_scorpion: 187.5,
  hussar: 80.0,
  imp_elite_skirm: 60.0,
  paladin: 172.5,
  siege_onager: 362.5,
};

test("registry holds exactly the fourteen fixtured units", () => {
  assert.equal(UNIT_REGISTRY.length, 14);
  assert.deepEqual([...UNIT_SLUGS].sort(), Object.keys(CALIBRATED_COST).sort());
});

test("base costs reproduce the calibrated cost scalars", () => {
  for (const row of UNIT_REGISTRY) {
    const { food, wood, gold } = row.baseCost;
    assert.equal(food + wood + 1.5 * gold, CALIBRATED_COST[row.slug], row.slug);
  }
});

test("every registry row points at a real mechanics fixture with a matching master", async () => {
  for (const row of UNIT_REGISTRY) {
    const mechanics = JSON.parse(await readFile(
      new URL(`../fixtures/unit_stats/${row.fixture}`, import.meta.url), "utf8"));
    assert.equal(mechanics.unit_master, row.master, `${row.slug} master`);
    assert.equal(mechanics.civilization, row.civ, `${row.slug} civ`);
  }
});

test("exactly four units are mobile ranged", () => {
  const kiters = UNIT_REGISTRY.filter((row) => row.class === "mobile_ranged").map((r) => r.slug);
  assert.deepEqual(kiters.sort(),
    ["arbalester", "hand_cannoneer", "heavy_cav_archer", "imp_elite_skirm"]);
});

test("class matches the fixture's attack range", async () => {
  for (const row of UNIT_REGISTRY) {
    const mechanics = JSON.parse(await readFile(
      new URL(`../fixtures/unit_stats/${row.fixture}`, import.meta.url), "utf8"));
    const ranged = row.class === "mobile_ranged" || row.class === "siege_ranged";
    // Elite Steppe Lancer is a reach fighter at range 1, not a ranged unit.
    const expectRanged = mechanics.attack_range_tiles > 1.0;
    assert.equal(ranged, expectRanged, `${row.slug} range ${mechanics.attack_range_tiles}`);
  }
});

test("unitBySlug finds and misses cleanly", () => {
  assert.equal(unitBySlug("paladin").master, 569);
  assert.equal(unitBySlug("not_a_unit"), undefined);
});
