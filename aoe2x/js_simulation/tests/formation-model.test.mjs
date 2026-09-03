import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  formationOpeningPatrol,
  formationUnits,
  validateFormationFixture,
} from "../src/formation-model.js";


const fixtureUrl = new URL("../fixtures/golden_formation_27v27.json", import.meta.url);

async function loadFixture() {
  return JSON.parse(await readFile(fixtureUrl, "utf8"));
}


test("formation fixture exposes the exact 27 current melee source units per side", async () => {
  const fixture = validateFormationFixture(await loadFixture());
  const units = formationUnits(fixture);

  assert.equal(units.length, 54);
  assert.deepEqual(units.slice(0, 2).map((unit) => unit.reference_id), [2087, 2066]);
  assert.deepEqual(units.slice(-2).map((unit) => unit.reference_id), [2114, 2115]);
  assert.equal(units.filter((unit) => unit.player_id === 2).length, 27);
  assert.equal(units.filter((unit) => unit.player_id === 3).length, 27);
  assert.deepEqual(formationOpeningPatrol(fixture), {
    2: { x: 2, y: 13 },
    3: { x: 13, y: 2 },
  });
  assert.ok(Object.isFrozen(fixture));
  assert.ok(Object.isFrozen(units));
});


test("current melee formation rejects missing patrol trigger provenance", async () => {
  const fixture = await loadFixture();
  delete fixture.opening_patrol;

  assert.throws(
    () => validateFormationFixture(fixture),
    /record its patrol trigger/,
  );
});


test("formation fixture rejects an incomplete side", async () => {
  const fixture = await loadFixture();
  fixture.sides["2"].pop();

  assert.throws(
    () => validateFormationFixture(fixture),
    /exactly 27 units for player 2/,
  );
});


test("formation fixture rejects a different scenario source", async () => {
  const fixture = await loadFixture();
  fixture.source.sha256 = "0".repeat(64);

  assert.throws(
    () => validateFormationFixture(fixture),
    /source hash does not match/,
  );
});
