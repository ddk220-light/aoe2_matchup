import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  formationUnits,
  validateFormationFixture,
} from "../src/formation-model.js";


const fixtureUrl = new URL("../fixtures/golden_formation_21v21.json", import.meta.url);

async function loadFixture() {
  return JSON.parse(await readFile(fixtureUrl, "utf8"));
}


test("formation fixture exposes the exact 21 source units per side", async () => {
  const fixture = validateFormationFixture(await loadFixture());
  const units = formationUnits(fixture);

  assert.equal(units.length, 42);
  assert.deepEqual(units.slice(0, 2).map((unit) => unit.reference_id), [1628, 1629]);
  assert.deepEqual(units.slice(-2).map((unit) => unit.reference_id), [1718, 1719]);
  assert.equal(units.filter((unit) => unit.player_id === 2).length, 21);
  assert.equal(units.filter((unit) => unit.player_id === 3).length, 21);
  assert.ok(Object.isFrozen(fixture));
  assert.ok(Object.isFrozen(units));
});


test("formation fixture rejects an incomplete side", async () => {
  const fixture = await loadFixture();
  fixture.sides["2"].pop();

  assert.throws(
    () => validateFormationFixture(fixture),
    /exactly 21 units for player 2/,
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
