import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { PLACEMENT_PROVENANCE, PLACEMENT_TABLE } from "../src/placement-table.js";
import { FAMILIES, placeArmy, resolveFamily, sideCapacity } from "../src/placement.js";
import { UNIT_REGISTRY } from "../src/unit-registry.js";

const spawns = JSON.parse(await readFile(
  new URL("../../../calibration/fixtures/spawns.json", import.meta.url), "utf8"));
const derivePlacementSource = await readFile(
  new URL("../tools/derive_placement.py", import.meta.url), "utf8");

const SIEGE = new Set(["heavy_scorpion", "siege_onager"]);
const MOBILE = new Set(["arbalester", "hand_cannoneer", "heavy_cav_archer", "imp_elite_skirm"]);
const classOf = (unit) => (
  SIEGE.has(unit) ? "siege_ranged" : MOBILE.has(unit) ? "mobile_ranged" : "melee");
const key = (points) => points.map(([x, y]) => `${x},${y}`).sort().join(" ");

// The recorded label names both units, so resolveFamily can be driven from the
// archive itself rather than from a second hand-written classification.
function familyOfLabel(label) {
  const [left, right] = label.replace(/_r\d+$/, "").split("__vs__");
  return resolveFamily({ side2Class: classOf(left), side3Class: classOf(right) });
}

test("placeArmy regenerates every recorded side-layout exactly", () => {
  let checked = 0;
  for (const [label, sides] of Object.entries(spawns)) {
    const family = familyOfLabel(label);
    for (const owner of [2, 3]) {
      const points = sides[String(owner)];
      const produced = placeArmy({ owner, count: points.length, family });
      assert.equal(
        key(produced.map(({ x, y }) => [x, y])),
        key(points),
        `${label} side ${owner} (${points.length} units, family ${family})`,
      );
      checked += 1;
    }
  }
  assert.equal(checked, 678, "every recorded side-layout must be checked");
});

test("the derivation left no residue", () => {
  assert.equal(PLACEMENT_PROVENANCE.residue, 0);
  assert.equal(PLACEMENT_PROVENANCE.exact, 678);
  assert.equal(PLACEMENT_PROVENANCE.sideLayouts, 678);
});

// The generated table was derived by classifying the recorded labels in
// tools/derive_placement.py; /api/fight classifies the SAME units from
// unit-registry.js. If the two ever disagree -- a 15th unit added to the
// registry but not to the tool, say -- the 678-layout gate above stays green
// (it only replays labels the tool already knew) while a live fight picks a
// different block. So the two classifications are pinned to each other here.
test("the registry's classes are the ones derive_placement.py classified with", () => {
  const pythonSet = (name) => {
    const match = new RegExp(`^${name} = \\{([^}]*)\\}`, "m").exec(derivePlacementSource);
    assert.ok(match, `derive_placement.py no longer defines ${name}`);
    return new Set([...match[1].matchAll(/"([a-z0-9_]+)"/g)].map(([, slug]) => slug));
  };
  const fromPython = { siege_ranged: pythonSet("SIEGE"), mobile_ranged: pythonSet("MOBILE") };

  // Same three restatements the gate above and the engine both rely on.
  assert.deepEqual([...fromPython.siege_ranged].sort(), [...SIEGE].sort());
  assert.deepEqual([...fromPython.mobile_ranged].sort(), [...MOBILE].sort());

  for (const { slug, class: unitClass } of UNIT_REGISTRY) {
    const inSiege = fromPython.siege_ranged.has(slug);
    const inMobile = fromPython.mobile_ranged.has(slug);
    const pythonClass = inSiege ? "siege_ranged" : inMobile ? "mobile_ranged" : "melee";
    assert.equal(unitClass, pythonClass,
      `${slug} is ${unitClass} in the registry but ${pythonClass} to derive_placement.py`);
  }
  // ...and nothing the tool classifies is missing from the registry.
  const registered = new Set(UNIT_REGISTRY.map(({ slug }) => slug));
  for (const slug of [...fromPython.siege_ranged, ...fromPython.mobile_ranged]) {
    assert.ok(registered.has(slug), `derive_placement.py knows ${slug}, the registry does not`);
  }
});

test("FAMILIES is exported so nothing has to hand-mirror it", () => {
  assert.deepEqual([...FAMILIES], ["rvr", "kite", "siege", "waves"]);
  for (const family of FAMILIES) {
    assert.ok(PLACEMENT_TABLE[`2@${family}`], `FAMILIES names ${family} with no table entry`);
  }
});

test("families are decided by combat class", () => {
  assert.equal(resolveFamily({ side2Class: "melee", side3Class: "melee" }), "waves");
  assert.equal(resolveFamily({ side2Class: "siege_ranged", side3Class: "melee" }), "siege");
  assert.equal(resolveFamily({ side2Class: "melee", side3Class: "siege_ranged" }), "siege");
  assert.equal(resolveFamily({ side2Class: "mobile_ranged", side3Class: "melee" }), "kite");
  assert.equal(resolveFamily({ side2Class: "melee", side3Class: "mobile_ranged" }), "kite");
  assert.equal(resolveFamily({ side2Class: "mobile_ranged", side3Class: "mobile_ranged" }), "rvr");
  assert.equal(resolveFamily({ side2Class: "mobile_ranged", side3Class: "siege_ranged" }), "rvr");
  assert.equal(resolveFamily({ side2Class: "siege_ranged", side3Class: "siege_ranged" }), "rvr");
});

test("every family has a derived sequence and the recorded capacities", () => {
  for (const owner of [2, 3]) {
    for (const family of ["rvr", "kite", "siege", "waves"]) {
      assert.ok(PLACEMENT_TABLE[`${owner}@${family}`], `missing ${owner}@${family}`);
    }
  }
  // Side 2's siege block is the one the archive never grew past 16.
  assert.equal(sideCapacity(2, "siege"), 16);
  assert.equal(sideCapacity(3, "siege"), 21);
  assert.equal(sideCapacity(2, "waves"), 21);
  assert.equal(sideCapacity(3, "kite"), 21);
});

test("positions within one army are distinct", () => {
  for (const owner of [2, 3]) {
    for (const family of ["rvr", "kite", "siege", "waves"]) {
      const cells = placeArmy({ owner, count: sideCapacity(owner, family), family });
      const seen = new Set(cells.map(({ x, y }) => `${x},${y}`));
      assert.equal(seen.size, cells.length, `${owner}@${family} has duplicate cells`);
    }
  }
});

test("a count beyond the derived sequence is rejected", () => {
  assert.throws(
    () => placeArmy({ owner: 2, count: 17, family: "siege" }),
    /only 16 cells/);
  assert.throws(
    () => placeArmy({ owner: 3, count: 22, family: "waves" }),
    /only 21 cells/);
});

test("bad arguments are rejected", () => {
  assert.throws(() => placeArmy({ owner: 1, count: 5, family: "waves" }), /owner must be 2 or 3/);
  assert.throws(() => placeArmy({ owner: 2, count: 0, family: "waves" }), /count must be/);
  assert.throws(() => placeArmy({ owner: 2, count: 5, family: "nope" }), /unknown family nope/);
});
