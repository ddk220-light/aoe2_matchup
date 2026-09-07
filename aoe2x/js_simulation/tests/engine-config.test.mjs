import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
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

// ENGINE_CONFIG is computed once, at module load, from process.env -- so these
// two cases can't be exercised by mutating process.env in this process (the
// module is already loaded and cached). Each spawns a fresh `node -e` child
// with a controlled environment instead, which forces a fresh module load.
const engineConfigHref = pathToFileURL(
  path.resolve(here, "..", "src", "engine-config.js"),
).href;

function readEngineConfigInChild(overrides) {
  // Strip any AOE2X_EXP_* the outer process happens to have, so the child's
  // environment is exactly what the test declares -- not ambient shell state.
  const base = Object.fromEntries(
    Object.entries(process.env).filter(([key]) => !key.startsWith("AOE2X_EXP_")),
  );
  const script = `import(${JSON.stringify(engineConfigHref)})`
    + `.then((mod) => { process.stdout.write(JSON.stringify(mod.ENGINE_CONFIG)); });`;
  const output = execFileSync(process.execPath, ["-e", script], {
    env: { ...base, ...overrides },
    encoding: "utf8",
  });
  return JSON.parse(output);
}

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

test("AOE2X_EXP_ENGAGEMENT=free yields the baseline (un-calibrated) engine", () => {
  // PowerShell's `$env:AOE2X_EXP_ENGAGEMENT = ""` deletes the variable rather
  // than setting it empty, so "free" is the only reachable way to ask for
  // baseline engagement from this project's documented shell.
  const config = readEngineConfigInChild({ AOE2X_EXP_ENGAGEMENT: "free" });
  assert.equal(config.engagement, "");
});

test("an explicitly-set variable is not overridden by the calibrated default", () => {
  // Both defaults are non-empty ("pursuit" / true), so an explicit "" must
  // win over them -- proof that only a genuinely UNSET variable falls back,
  // not merely an empty one.
  const config = readEngineConfigInChild({
    AOE2X_EXP_ENGAGEMENT: "",
    AOE2X_EXP_ORDERS: "",
  });
  assert.equal(config.engagement, "", "explicit empty string must not fall back to the pursuit default");
  assert.equal(config.orders, false, "explicit empty string must not fall back to the orders default");
});
