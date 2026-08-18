import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  deriveKiteProfile,
  warWagonChasePolicy,
} from "../src/combat/kite-timing.js";


const fixtureRoot = new URL("../fixtures/unit_stats/", import.meta.url);

async function mechanics(name) {
  return JSON.parse(await readFile(new URL(name, fixtureRoot), "utf8"));
}


test("mechanics-derived timing reproduces every accepted recurring kiting profile", async () => {
  const rows = [
    {
      fixture: "arbalester_chinese_imperial.json",
      policy: {},
      expected: {
        beatTicks: 120,
        firstBeatTick: 120,
        moveOffsetTicks: [40],
        topupOffsetTicks: [],
        preMoveTicks: [80],
      },
    },
    {
      fixture: "heavy_cav_archer_saracens_imperial.json",
      policy: { firstBeatTick: 40, topupOffsetTicks: [40] },
      expected: {
        beatTicks: 120,
        firstBeatTick: 40,
        moveOffsetTicks: [80],
        topupOffsetTicks: [40],
        preMoveTicks: [],
      },
    },
    {
      fixture: "elite_skirmisher_chinese_imperial.json",
      policy: {},
      expected: {
        beatTicks: 200,
        firstBeatTick: 200,
        moveOffsetTicks: [40, 120],
        topupOffsetTicks: [],
        preMoveTicks: [80, 160],
      },
    },
    {
      fixture: "hand_cannoneer_bohemians_imperial.json",
      policy: {
        firstBeatTick: 12,
        formationMotion: "translated_offsets",
        volleyPursuit: "close_to_fire",
      },
      expected: {
        beatTicks: 240,
        firstBeatTick: 12,
        moveOffsetTicks: [68, 148, 228],
        topupOffsetTicks: [],
        preMoveTicks: [],
        formationMotion: "translated_offsets",
        volleyPursuit: "close_to_fire",
      },
    },
  ];

  for (const { fixture, policy, expected } of rows) {
    assert.deepEqual(deriveKiteProfile(await mechanics(fixture), policy), expected, fixture);
  }
});


test("a new ranged unit receives timing from mechanics without a calibrated profile row", () => {
  assert.deepEqual(deriveKiteProfile({
    reload_seconds: 2.25,
    attack_delay_seconds: 0.5,
  }), {
    beatTicks: 160,
    firstBeatTick: 160,
    moveOffsetTicks: [40, 120],
    topupOffsetTicks: [],
    preMoveTicks: [80],
  });
});


test("Heavy Scorpion derives a normal mechanics cycle without a siege-only timer", async () => {
  assert.deepEqual(
    deriveKiteProfile(await mechanics("heavy_scorpion_japanese_imperial.json")),
    {
      beatTicks: 240,
      firstBeatTick: 240,
      moveOffsetTicks: [40, 120, 200],
      topupOffsetTicks: [],
      preMoveTicks: [80, 160],
    },
  );
});


test("invalid timing mechanics and policy are rejected instead of silently defaulting", () => {
  assert.throws(() => deriveKiteProfile({
    reload_seconds: 0,
    attack_delay_seconds: 0.2,
  }), /reload_seconds must be positive/);
  assert.throws(() => deriveKiteProfile({
    reload_seconds: 2,
    attack_delay_seconds: -0.1,
  }), /attack_delay_seconds must be non-negative/);
  assert.throws(() => deriveKiteProfile({
    reload_seconds: 2,
    attack_delay_seconds: 0.2,
  }, { firstBeatTick: 0 }), /firstBeatTick must be a positive integer/);
});


test("War Wagon chase contact derives from the chaser body instead of matchup constants", () => {
  assert.deepEqual(warWagonChasePolicy("elite_war_wagon", {
    collision_size_tiles: { x: 0.25, y: 0.25 },
  }), {
    attackMoveTargetPressureTiles: 0.5,
    attackMoveStickyPursuit: true,
    warWagonEnemyOverlapDepthTiles: 0.09999999999999998,
    warWagonEnemyOverlapMode: "always",
  });
  assert.deepEqual(warWagonChasePolicy("elite_war_wagon", {
    collision_size_tiles: { x: 0.2, y: 0.2 },
  }), {
    attackMoveTargetPressureTiles: 0.4,
    attackMoveStickyPursuit: true,
    warWagonEnemyOverlapDepthTiles: 0,
    warWagonEnemyOverlapMode: "always",
  });
  assert.deepEqual(warWagonChasePolicy("arbalester", {
    collision_size_tiles: { x: 0.25, y: 0.25 },
  }), {});
});
