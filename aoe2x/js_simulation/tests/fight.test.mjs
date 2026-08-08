import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { runFight } from "../src/fight.js";
import { UNIT_SLUGS } from "../src/unit-registry.js";

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
    // referenceId, x, y, facing, hp, alive, action, pursuitTargetId,
    // engagedTargetId, attackTargetId.
    assert.equal(record.length, 10);
    assert.ok(Object.isFrozen(record));
    assert.equal(typeof record[0], "number");
  }
  assert.equal(JSON.stringify(fight).includes("provenance"), false,
    "mechanics provenance must not be serialised per tick");
});

test("per-tick move and blocked events are excluded from the wire log, everything else survives", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 5, side3Slug: "paladin", n3: 3,
  });
  const wireTypes = new Set();
  for (const snapshot of fight.snapshots) {
    for (const entry of snapshot.events) wireTypes.add(entry.type);
  }
  assert.ok(!wireTypes.has("move"), "move is fully observable from unit positions");
  assert.ok(!wireTypes.has("blocked"), "blocked is fully observable from unit positions");
  // A resolved fight always produces at least one death; that event type
  // (and others besides move/blocked) must still reach the wire.
  assert.ok(wireTypes.has("death"), `expected a death event among ${[...wireTypes]}`);
});

test("the top-level event log is not duplicated; eventLogHash still covers the full log", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 3, side3Slug: "champion", n3: 3,
  });
  assert.equal(fight.events, undefined,
    "events must live only inside each snapshot, not duplicated at the top level");
  assert.equal(typeof fight.eventLogHash, "string");
  assert.equal(fight.eventLogHash.length, 64, "sha256 hex digest");
});

test("unitIndex carries the per-type fields the renderer needs beyond maxHp", async () => {
  const fight = await runFight(root, {
    side2Slug: "champion", n2: 2, side3Slug: "paladin", n3: 2,
  });
  for (const record of Object.values(fight.unitIndex)) {
    assert.equal(typeof record.master, "number");
    assert.ok(record.master > 0);
    assert.equal(typeof record.collisionRadius, "number");
    assert.ok(record.collisionRadius > 0);
    assert.equal(typeof record.attackRange, "number");
    assert.ok(record.attackRange >= 0);
  }
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

// The melee case above is the cheap path (~1000 ticks). Kite fights run
// 2500-4500 ticks, and this is the pairing measured (pre-fix) at 33.7 MB --
// the worst of the three the review round flagged -- so it is the one that
// has to hold the same budget once the wire format changes, not another easy
// melee case.
test("imp_elite_skirm vs halberdier at derived counts (worst measured case) serialises under 10 MB", async () => {
  const fight = await runFight(root, { side2Slug: "imp_elite_skirm", side3Slug: "halberdier" });
  assert.equal(fight.family, "kite");
  assert.equal(fight.side2.count, 21);
  assert.equal(fight.side3.count, 21);
  const bytes = Buffer.byteLength(JSON.stringify(fight));
  assert.ok(bytes < 10 * 1024 * 1024,
    `imp_elite_skirm vs halberdier serialised to ${(bytes / 1048576).toFixed(1)} MB`);
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

test("exactly one explicit count is rejected, not silently re-derived", async () => {
  await assert.rejects(
    () => runFight(root, { side2Slug: "champion", n2: 3, side3Slug: "paladin" }),
    /n2 and n3 must both be given, or both omitted/);
  await assert.rejects(
    () => runFight(root, { side2Slug: "champion", side3Slug: "paladin", n3: 3 }),
    /n2 and n3 must both be given, or both omitted/);
});

test("an explicit count that exceeds its side's family capacity is rejected", async () => {
  // champion (owner 2) paired with siege_onager (owner 3) resolves to the
  // "siege" family, whose owner-2 block holds only 16 cells -- the global
  // FIGHT_SIDE_CAP (21) alone would let this slip through to placeArmy.
  await assert.rejects(
    () => runFight(root, { side2Slug: "champion", n2: 21, side3Slug: "siege_onager", n3: 4 }),
    /count must be an integer 1-16 for owner 2's siege formation/);
});

// A placement-capacity error is the one this sweep exists to catch (Finding
// 2: a derived count that exceeds its side's placement block, e.g. "owner 2
// family siege has only 16 cells, asked for 21"). Anything else that a fight
// can throw -- in particular the engine's own runaway-fight guard -- is a
// different bug class, not this test's job to assert on; see the report for
// what the sweep turned up outside that scope.
const CAPACITY_ERROR_PATTERN = /count must be an integer|has only \d+ cells/;

test("every ordered pair of registered units resolves at derived counts "
  + "without a placement-capacity error", async () => {
  const capacityFailures = [];
  const otherFailures = [];
  for (const side2Slug of UNIT_SLUGS) {
    for (const side3Slug of UNIT_SLUGS) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await runFight(root, { side2Slug, side3Slug });
      } catch (error) {
        const message = error?.message ?? String(error);
        const entry = `${side2Slug} vs ${side3Slug}: ${message}`;
        (CAPACITY_ERROR_PATTERN.test(message) ? capacityFailures : otherFailures).push(entry);
      }
    }
  }
  if (otherFailures.length > 0) {
    // Not asserted on: logged so a real, separate finding is visible rather
    // than silently swallowed by a test scoped to capacity errors only.
    console.warn(`${otherFailures.length} pair(s) failed for a reason other than `
      + `placement capacity:\n${otherFailures.join("\n")}`);
  }
  assert.deepEqual(capacityFailures, [],
    `${capacityFailures.length}/${UNIT_SLUGS.length * UNIT_SLUGS.length} ordered pairs threw `
    + "a placement-capacity error");
});
