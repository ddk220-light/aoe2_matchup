import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { runFight } from "../src/fight.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = pathToFileURL(path.resolve(here, "..") + "/");

test("a melee fight resolves and reports both sides", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 5, side3Slug: "paladin", n3: 3,
  });
  assert.equal(fight.side2.count, 5);
  assert.equal(fight.side3.count, 3);
  assert.equal(fight.side2.label, "Champion");
  assert.equal(fight.kiteOwner, null);
  assert.equal(fight.family, "waves");
  assert.ok(fight.ticks > 0);
  assert.ok(fight.winnerOwner === 2 || fight.winnerOwner === 3);
});

test("exactly one mobile-ranged side sets kiteOwner", async () => {
  const kiting = await runFight(root, {
    side2Slug: "arbalester", n2: 6, side3Slug: "champion", n3: 6,
  });
  assert.equal(kiting.kiteOwner, 2);
  assert.equal(kiting.family, "kite");

  const both = await runFight(root, {
    side2Slug: "arbalester", n2: 6, side3Slug: "imp_elite_skirm", n3: 6,
  });
  assert.equal(both.kiteOwner, null);
  assert.equal(both.family, "rvr");
});

test("snapshots carry no mechanics blob but keep the viewer's contract", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 3, side3Slug: "champion", n3: 3,
  });
  const [first] = fight.snapshots;
  // simulation-review.js:26 and map-renderer.js:116 both require exactly this.
  assert.ok(Object.isFrozen(first));
  assert.equal(first.tick, 0);
  assert.ok(Array.isArray(first.units) && Object.isFrozen(first.units));
  assert.ok(Array.isArray(first.events) && Object.isFrozen(first.events));
  assert.equal(first.units.length, 6);
  for (const record of first.units) {
    assert.equal(record.length, 9);
    assert.ok(Object.isFrozen(record));
    assert.equal(typeof record[0], "number");
  }
  assert.equal(JSON.stringify(fight).includes("provenance"), false,
    "mechanics provenance must not be serialised per tick");
});

test("every snapshot tick equals its index", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 2, side3Slug: "champion", n3: 2,
  });
  fight.snapshots.forEach((snapshot, index) => {
    assert.equal(snapshot.tick, index);
  });
});

test("max HP is reachable once per unit", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 2, side3Slug: "paladin", n3: 2,
  });
  const ids = Object.keys(fight.unitIndex);
  assert.equal(ids.length, 4);
  assert.equal(fight.unitIndex[ids[0]].maxHp > 0, true);
});

test("a 20v20 fight serialises under 10 MB", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 20, side3Slug: "paladin", n3: 20,
  });
  const bytes = Buffer.byteLength(JSON.stringify(fight));
  assert.ok(bytes < 10 * 1024 * 1024, `20v20 serialised to ${(bytes / 1048576).toFixed(1)} MB`);
});

test("omitting both counts derives them from the purchase rule", async () => {
  // champion (weighted cost 80) vs elite_elephant (weighted cost 205) is the
  // pairing that actually reproduces 21v8 from deriveCounts; the brief names
  // siege_onager here, but that pairing's real deriveCounts split is 21v4 and,
  // moreover, an owner-2 siege family caps at 16 (placement-table.js), so a
  // champion count of 21 assigned to owner 2 would throw before the assertion
  // is ever reached. See task-5-report.md for the measurement.
  const fight = await runFight(root, { side2Slug: "champion", side3Slug: "elite_elephant" });
  assert.equal(fight.derivedCounts, true);
  assert.equal(fight.side2.count, 21);
  assert.equal(fight.side3.count, 8);

  const explicit = await runFight(root, {
    side2Slug: "champion", n2: 21, side3Slug: "elite_elephant", n3: 8,
  });
  assert.equal(explicit.derivedCounts, false);
  assert.equal(explicit.finalStateHash, fight.finalStateHash,
    "deriving the counts must produce the same fight as passing them");
});

test("bad input is rejected", async () => {
  await assert.rejects(
    () => runFight(root, { side2Slug: "trebuchet", n2: 5, side3Slug: "champion", n3: 5 }),
    /unknown unit trebuchet/);
  await assert.rejects(
    () => runFight(root, { side2Slug: "champion", n2: 0, side3Slug: "champion", n3: 5 }),
    /count must be an integer/);
  await assert.rejects(
    () => runFight(root, { side2Slug: "champion", n2: 22, side3Slug: "champion", n3: 5 }),
    /count must be an integer/);
});
