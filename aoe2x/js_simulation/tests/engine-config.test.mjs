import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { ENGINE_CONFIG } from "../src/engine-config.js";
import { ENGAGEMENT_FOLLOWS_PURSUIT } from "../src/combat/experiments.js";
import { ORDERS_ENABLED } from "../src/combat/ai-orders.js";
import { matchupPlayback } from "../src/matchup-playback.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");

test("calibrated configuration is the committed default", () => {
  assert.equal(ENGINE_CONFIG.engagement, "pursuit");
  assert.equal(ENGINE_CONFIG.orders, true);
  assert.equal(ENGAGEMENT_FOLLOWS_PURSUIT, true);
  assert.equal(ORDERS_ENABLED, true);
});

test("pinning the config changes no engine output", async () => {
  const baseline = JSON.parse(await readFile(
    new URL("./fixtures/config_baseline.json", import.meta.url), "utf8"));
  assert.ok(baseline.rows.length > 0, "baseline must not be empty");
  for (const row of baseline.rows) {
    const playback = await matchupPlayback(root, row.name, row.ratio);
    assert.equal(playback.ticks, row.ticks, `${row.name} ${row.ratio} ticks`);
    assert.equal(playback.winnerOwner, row.winnerOwner, `${row.name} ${row.ratio} winner`);
    assert.equal(playback.winnerHp, row.winnerHp, `${row.name} ${row.ratio} winnerHp`);
    assert.equal(playback.finalStateHash, row.finalStateHash, `${row.name} ${row.ratio} state hash`);
    assert.equal(playback.eventLogHash, row.eventLogHash, `${row.name} ${row.ratio} event hash`);
  }
});
