import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { deriveCounts, weightedCost } from "../src/purchase.js";

const corpus = JSON.parse(await readFile(
  new URL("../docs/data/standard_units_2026-08-07.json", import.meta.url), "utf8"));

// The corpus labels units by display name; the registry keys by slug.
const SLUG_BY_LABEL = {
  "Arbalester": "arbalester",
  "Champion": "champion",
  "Elite Battle Elephant": "elite_elephant",
  "Elite Fire Lancer": "elite_fire_lancer",
  "Elite Skirmisher": "imp_elite_skirm",
  "Elite Steppe Lancer": "elite_steppe",
  "Halberdier": "halberdier",
  "Hand Cannoneer": "hand_cannoneer",
  "Heavy Camel Rider": "heavy_camel",
  "Heavy Cav Archer": "heavy_cav_archer",
  "Heavy Scorpion": "heavy_scorpion",
  "Hussar": "hussar",
  "Paladin": "paladin",
  "Siege Onager": "siege_onager",
};

test("weightedCost charges gold at 1.5", () => {
  assert.equal(weightedCost({ food: 0, wood: 25, gold: 45 }), 92.5);
  assert.equal(weightedCost({ food: 80, wood: 0, gold: 0 }), 80);
});

test("deriveCounts reproduces every recorded army size", () => {
  assert.equal(corpus.length, 101);
  const wrong = [];
  for (const row of corpus) {
    const slugA = SLUG_BY_LABEL[row.side2.unit];
    const slugB = SLUG_BY_LABEL[row.side3.unit];
    const { countA, countB, costA, costB } = deriveCounts(slugA, slugB);
    if (countA !== row.side2.n || countB !== row.side3.n
        || costA !== row.side2.cost || costB !== row.side3.cost) {
      wrong.push(`${row.matchup}: got ${countA}v${countB} (${costA}/${costB}), `
        + `want ${row.side2.n}v${row.side3.n} (${row.side2.cost}/${row.side3.cost})`);
    }
  }
  assert.deepEqual(wrong, []);
});

test("a mirror matchup buys the cap on both sides", () => {
  const { countA, countB } = deriveCounts("champion", "champion");
  assert.equal(countA, 21);
  assert.equal(countB, 21);
});

test("an unknown slug is rejected", () => {
  assert.throws(() => deriveCounts("paladin", "trebuchet"), /unknown unit trebuchet/);
});
