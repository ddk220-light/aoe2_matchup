import assert from "node:assert/strict";
import test from "node:test";

import {
  DEDICATED_GOLDEN_MATCHUPS,
  loadDedicatedGoldenCorpus,
} from "../src/dedicated-golden-corpus.js";


const ROOT = new URL("../", import.meta.url);


test("dedicated ranged-melee corpus admits exactly the 19 authorized pair archives", () => {
  assert.equal(DEDICATED_GOLDEN_MATCHUPS.length, 19);
  assert.deepEqual(
    [...new Set(DEDICATED_GOLDEN_MATCHUPS.map(({ rangedSlug }) => rangedSlug))].sort(),
    ["arbalester", "hand_cannoneer", "heavy_cav_archer", "heavy_scorpion", "imp_elite_skirm"],
  );
  assert.deepEqual(
    DEDICATED_GOLDEN_MATCHUPS
      .filter(({ rangedSlug }) => rangedSlug === "heavy_scorpion")
      .map(({ meleeSlug }) => meleeSlug)
      .sort(),
    ["champion", "paladin"],
  );
  assert.deepEqual(
    DEDICATED_GOLDEN_MATCHUPS
      .filter(({ rangedSlug }) => rangedSlug === "hand_cannoneer")
      .map(({ meleeSlug }) => meleeSlug)
      .sort(),
    ["champion", "paladin"],
  );
  assert.equal(
    DEDICATED_GOLDEN_MATCHUPS.some(({ rangedSlug, meleeSlug }) => (
      rangedSlug === "siege_onager"
      || meleeSlug === "heavy_camel"
    )),
    false,
  );
});


test("manifested dedicated corpus contains every ratio and every tape repeat", async () => {
  const corpus = await loadDedicatedGoldenCorpus(ROOT);

  assert.equal(corpus.matchups.length, 19);
  assert.equal(corpus.rows.length, 95);
  assert.equal(corpus.runs.length, 475);
  assert.equal(new Set(corpus.matchups.map(({ zipSha256 }) => zipSha256)).size, 19);

  for (const matchup of corpus.matchups) {
    assert.equal(matchup.ratios.length, 5, matchup.id);
    assert.equal(matchup.runs.length, 25, matchup.id);
    assert.match(matchup.archive, /^aoe2_golden_(?:kiting|ranged)_/);
    assert.match(matchup.zipSha256, /^[A-F0-9]{64}$/);
    assert.equal(matchup.manifestZipSha256, matchup.zipSha256);
  }
  for (const row of corpus.rows) assert.equal(row.runs.length, 5, row.id);
});
