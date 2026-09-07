import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";


const activeSources = await Promise.all([
  "../src/combat/world.js",
  "../src/fight.js",
  "../server.mjs",
].map((path) => readFile(new URL(path, import.meta.url), "utf8")));


test("active world API has no replay trajectory or per-matchup release inputs", () => {
  for (const source of activeSources) {
    assert.equal(source.includes("attackReleaseTickByOwner"), false);
    assert.equal(source.includes("openingPatrolProfile"), false);
    assert.equal(source.includes("profileWaypoints"), false);
    assert.equal(source.includes("waypointUntilTick"), false);
  }
});


test("the retired ranged-vs-melee gate fixture is absent", async () => {
  await assert.rejects(
    access(new URL("../fixtures/current_ranged_vs_melee_gate_profile.json", import.meta.url)),
    { code: "ENOENT" },
  );
});
